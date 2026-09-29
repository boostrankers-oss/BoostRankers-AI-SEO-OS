$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backendFile = Join-Path $root "backend\ai_search_optimization.py"

if (-not (Test-Path -LiteralPath $backendFile)) {
    throw "backend\ai_search_optimization.py not found: $backendFile"
}

$content = [System.IO.File]::ReadAllText($backendFile)

$startMarker = "def _extract_page(html: str, url: str, focus_keyword: str) -> dict[str, Any]:"
$endMarker = "async def _fetch_public_page(url: str) -> str:"

$start = $content.IndexOf($startMarker, [System.StringComparison]::Ordinal)
$end = $content.IndexOf($endMarker, [System.StringComparison]::Ordinal)

if ($start -lt 0 -or $end -lt 0 -or $end -le $start) {
    throw "Could not locate the complete _extract_page function. No changes made."
}

$newFunction = @'
def _schema_type_names(value: Any) -> set[str]:
    """Normalize JSON-LD @type values, including schema.org URLs and arrays."""
    values = value if isinstance(value, list) else [value]
    result: set[str] = set()
    for item in values:
        if not item:
            continue
        text = str(item).strip()
        if not text:
            continue
        # Handles:
        #   LocalBusiness
        #   https://schema.org/LocalBusiness
        #   http://schema.org/LocalBusiness
        normalized = text.rstrip("/").rsplit("/", 1)[-1].split(":", 1)[-1]
        result.add(normalized)
    return result


def _extract_page(html: str, url: str, focus_keyword: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    # JSON-LD MUST be extracted before script tags are removed.
    schema_types: set[str] = set()
    json_ld_detected = False
    schema_parse_errors = 0
    faq_schema_question_count = 0
    local_business_schema_present = False

    def visit_schema(item: Any) -> None:
        nonlocal faq_schema_question_count, local_business_schema_present

        if isinstance(item, list):
            for child in item:
                visit_schema(child)
            return

        if not isinstance(item, dict):
            return

        types = _schema_type_names(item.get("@type"))
        schema_types.update(types)

        if "LocalBusiness" in types or any(
            name.endswith("LocalBusiness") for name in types
        ):
            local_business_schema_present = True

        if "FAQPage" in types:
            main_entity = item.get("mainEntity")
            questions = main_entity if isinstance(main_entity, list) else [main_entity]
            for question in questions:
                if not isinstance(question, dict):
                    continue
                q_types = _schema_type_names(question.get("@type"))
                if "Question" in q_types or question.get("name") or question.get("acceptedAnswer"):
                    faq_schema_question_count += 1

        graph = item.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                visit_schema(child)

        # Some implementations nest structured entities under other object
        # properties. Walk dict/list children without relying on a fixed graph shape.
        for key, value in item.items():
            if key in {"@context", "@type", "@id", "@graph", "mainEntity"}:
                continue
            if isinstance(value, (dict, list)):
                visit_schema(value)

    schema_scripts = soup.find_all(
        "script",
        attrs={"type": re.compile(r"^\s*application/ld\+json\s*$", re.I)},
    )

    for script in schema_scripts:
        json_ld_detected = True
        raw = script.string if script.string is not None else script.get_text()
        raw = (raw or "").strip()

        # Be tolerant of HTML comments occasionally wrapped around JSON-LD.
        raw = re.sub(r"^\s*<!--\s*", "", raw)
        raw = re.sub(r"\s*-->\s*$", "", raw)

        if not raw:
            schema_parse_errors += 1
            continue

        try:
            visit_schema(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            schema_parse_errors += 1

            # Do not pretend malformed JSON-LD is valid. However, preserve
            # obvious @type evidence so the UI can explain a parser problem
            # instead of incorrectly saying that no schema exists.
            raw_types = re.findall(
                r'"@type"\s*:\s*(?:"([^"]+)"|\[\s*([^\]]+)\])',
                raw,
                flags=re.I | re.S,
            )
            for single, array_body in raw_types:
                if single:
                    schema_types.update(_schema_type_names(single))
                elif array_body:
                    for value in re.findall(r'"([^"]+)"', array_body):
                        schema_types.update(_schema_type_names(value))

    # Remove executable/presentation-only elements only AFTER schema extraction.
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True).strip() if soup.title else ""
    meta_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = str(meta_tag.get("content") or "").strip() if meta_tag else ""
    canonical = ""
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if canonical_tag:
        canonical = str(canonical_tag.get("href") or "").strip()

    h1s = [
        re.sub(r"\s+", " ", x.get_text(" ", strip=True)).strip()
        for x in soup.find_all("h1")
    ]
    headings = [
        {
            "level": int(tag.name[1]),
            "text": re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip(),
        }
        for tag in soup.find_all(["h2", "h3", "h4"])
        if tag.get_text(" ", strip=True)
    ]

    main = soup.find("main") or soup.find("article") or soup.body or soup
    content_html = str(main)[:120000]
    text = _strip_html(content_html)
    word_count = _word_count(text)
    first_200 = " ".join(text.split()[:200])

    host = urlparse(url).netloc.lower().lstrip("www.")
    internal_links = 0
    external_links = 0
    for anchor in main.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc.lower().lstrip("www.") != host:
            external_links += 1
        else:
            internal_links += 1

    answer_headings = [
        h["text"]
        for h in headings
        if re.search(r"\b(what|why|how|when|where|who|which|can|does|is|are)\b", h["text"], re.I)
    ]

    # Visible author/date signals plus JSON-LD author/date signals.
    author_present = bool(
        soup.find("meta", attrs={"name": re.compile("^author$", re.I)})
        or soup.find(attrs={"rel": "author"})
        or soup.find(class_=re.compile("author", re.I))
    )
    date_present = bool(
        soup.find("time")
        or soup.find("meta", attrs={"property": re.compile("article:(published|modified)_time", re.I)})
    )

    kw = focus_keyword.strip()
    schema_type_count = len(schema_types)
    title_score = 100 if 30 <= len(title) <= 65 else 70 if title else 0
    meta_score = 100 if 120 <= len(meta_description) <= 165 else 70 if meta_description else 0
    h1_score = 100 if len(h1s) == 1 else 50 if h1s else 0
    content_score = min(100, round(word_count / 18))
    answer_score = min(
        100,
        len(answer_headings) * 20
        + (20 if re.search(r"\b(is|are|means|refers to|typically)\b", first_200, re.I) else 0),
    )

    # A valid LocalBusiness/FAQPage is stronger entity evidence than merely
    # counting arbitrary JSON-LD types.
    entity_score = min(
        100,
        schema_type_count * 15
        + (25 if local_business_schema_present else 0)
        + (15 if "FAQPage" in schema_types else 0)
        + (15 if author_present else 0)
        + (10 if date_present else 0),
    )

    checks = [
        {"key": "title", "label": "Title tag", "score": title_score, "detail": f"{len(title)} characters" if title else "Missing title tag"},
        {"key": "meta_description", "label": "Meta description", "score": meta_score, "detail": f"{len(meta_description)} characters" if meta_description else "Missing meta description"},
        {"key": "h1", "label": "H1 structure", "score": h1_score, "detail": f"{len(h1s)} H1 tag(s) detected"},
        {"key": "content_depth", "label": "Content depth", "score": content_score, "detail": f"{word_count:,} words"},
        {"key": "answer_engine", "label": "Answer-engine structure", "score": answer_score, "detail": f"{len(answer_headings)} question-style heading(s)"},
        {
            "key": "entity",
            "label": "Entity/trust signals",
            "score": entity_score,
            "detail": (
                f"{schema_type_count} JSON-LD type(s), "
                f"LocalBusiness={'yes' if local_business_schema_present else 'no'}, "
                f"FAQPage={'yes' if 'FAQPage' in schema_types else 'no'}, "
                f"author={'yes' if author_present else 'no'}, "
                f"date={'yes' if date_present else 'no'}"
            ),
        },
        {"key": "internal_links", "label": "Internal linking", "score": min(100, internal_links * 15), "detail": f"{internal_links} internal link(s)"},
    ]

    if kw:
        checks.extend([
            {
                "key": "keyword_title",
                "label": "Focus keyword in title",
                "score": 100 if _keyword_count(title, kw) else 0,
                "detail": "Present" if _keyword_count(title, kw) else "Missing",
            },
            {
                "key": "keyword_h1",
                "label": "Focus keyword in H1",
                "score": 100 if any(_keyword_count(h, kw) for h in h1s) else 0,
                "detail": "Present" if any(_keyword_count(h, kw) for h in h1s) else "Missing",
            },
            {
                "key": "keyword_intro",
                "label": "Focus keyword in introduction",
                "score": 100 if _keyword_count(first_200, kw) else 0,
                "detail": "Present" if _keyword_count(first_200, kw) else "Missing",
            },
        ])

    overall = round(sum(int(x["score"]) for x in checks) / len(checks)) if checks else 0

    return {
        "url": url,
        "title": title,
        "meta_title": title,
        "meta_description": meta_description,
        "canonical": canonical,
        "h1s": h1s,
        "headings": headings[:80],
        "word_count": word_count,
        "schema_types": sorted(schema_types),
        "json_ld_detected": json_ld_detected,
        "schema_parse_errors": schema_parse_errors,
        "faq_schema_present": "FAQPage" in schema_types,
        "faq_schema_question_count": faq_schema_question_count,
        "local_business_schema_present": local_business_schema_present,
        "internal_links": internal_links,
        "external_links": external_links,
        "focus_keyword": kw,
        "focus_keyword_occurrences": _keyword_count(text, kw),
        "checks": checks,
        "measured_score": overall,
        "content_html": content_html,
        "content_text_excerpt": _safe_excerpt(text),
        "answer_headings": answer_headings[:20],
        "author_present": author_present,
        "date_present": date_present,
    }


'@

$updated = $content.Substring(0, $start) + $newFunction + $content.Substring($end)

# Also increase the response capture limit so schema placed late in a large
# homepage is not silently truncated before parsing.
$oldFetchReturn = 'return response.text[:MAX_CONTENT_CHARS * 4]'
$newFetchReturn = 'return response.text[:300000]'

if ($updated.Contains($oldFetchReturn)) {
    $updated = $updated.Replace($oldFetchReturn, $newFetchReturn)
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$backendFile.bak-ai-schema-robust-$timestamp"
Copy-Item -LiteralPath $backendFile -Destination $backup -Force

[System.IO.File]::WriteAllText(
    $backendFile,
    $updated,
    (New-Object System.Text.UTF8Encoding($false))
)

# Verification.
$verify = [System.IO.File]::ReadAllText($backendFile)
$required = @(
    "def _schema_type_names(value: Any) -> set[str]:",
    "json_ld_detected = False",
    "faq_schema_question_count = 0",
    "local_business_schema_present = False",
    '"local_business_schema_present": local_business_schema_present',
    '"faq_schema_question_count": faq_schema_question_count',
    "return response.text[:300000]"
)

foreach ($marker in $required) {
    if (-not $verify.Contains($marker)) {
        Copy-Item -LiteralPath $backup -Destination $backendFile -Force
        throw "Verification failed for marker: $marker. Original file restored."
    }
}

$pythonExe = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = "python"
}

Push-Location (Join-Path $root "backend")
try {
    & $pythonExe -m py_compile "ai_search_optimization.py"
    if ($LASTEXITCODE -ne 0) {
        Copy-Item -LiteralPath $backup -Destination $backendFile -Force
        throw "Python syntax check failed. Original file restored."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Robust AI Search schema detection fix installed successfully." -ForegroundColor Green
Write-Host "Changed: backend\ai_search_optimization.py"
Write-Host "Backup : $backup"
Write-Host ""
Write-Host "Detected schema is now normalized across @graph, arrays, schema.org URLs, and nested entities." -ForegroundColor Cyan
Write-Host "FAQPage/Question and LocalBusiness evidence are returned explicitly." -ForegroundColor Cyan
Write-Host "Homepage HTML capture increased to 300,000 characters to avoid late-schema truncation." -ForegroundColor Cyan

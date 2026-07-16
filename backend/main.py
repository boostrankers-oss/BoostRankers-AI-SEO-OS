"""
Boost Rankers AI SEO OS — FastAPI Audit Engine
==============================================

This backend powers the React frontend with live, streaming SEO audits.
It uses Server-Sent Events (SSE) to push results to the UI in real-time.

CLAUDE AI INTEGRATION
---------------------
To enable Claude-powered deep SEO analysis:
1. Install the Anthropic SDK: pip install anthropic python-dotenv
2. Set your API key in backend/.env: ANTHROPIC_API_KEY=sk-ant-...
3. The Claude SEO Agent will automatically activate and provide expert-level
   content recommendations, EEAT analysis, and AI search optimization.

RUN
---
    cd backend
    pip install fastapi uvicorn httpx beautifulsoup4 lxml anthropic python-dotenv
    uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import os
import re
from typing import AsyncGenerator

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl

# Claude AI Integration
try:
    from anthropic import AsyncAnthropic
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    load_dotenv()
    
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    claude_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except ImportError:
    claude_client = None
    ANTHROPIC_API_KEY = None

app = FastAPI(title="Boost Rankers AI SEO OS — Audit Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ────────────────────────────────────────────────

class AuditRequest(BaseModel):
    url: str
    primary_keyword: str = ""
    location: str = ""
    competitors: list[str] = []


# ─── SSE Helpers ───────────────────────────────────────────────────

def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─── Page Fetcher ───────────────────────────────────────────────────

async def fetch_page(client: httpx.AsyncClient, url: str) -> tuple[int, str, dict]:
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        return resp.status_code, resp.text, dict(resp.headers)
    except Exception:
        return 0, "", {}


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ─── Claude SEO Agent ──────────────────────────────────────────────

async def agent_claude_seo(client: httpx.AsyncClient, url: str, keyword: str, location: str) -> tuple[list[dict], int]:
    """
    Uses Claude AI to perform deep, expert-level SEO analysis.
    Evaluates content quality, EEAT signals, and AI search readiness.
    """
    if not claude_client:
        return [{
            "check": "AI Deep Analysis",
            "status": "info",
            "detail": "Claude API not configured. Set ANTHROPIC_API_KEY to enable.",
            "recommendation": "Add Anthropic API key for AI-powered recommendations"
        }], 60

    status, html, _ = await fetch_page(client, url)
    if not html:
        return [{"check": "AI Deep Analysis", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    
    title = soup.find("title")
    title_text = title.text.strip() if title else "Missing"
    
    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_text = meta_desc["content"] if meta_desc and meta_desc.get("content") else "Missing"
    
    h1 = soup.find("h1")
    h1_text = h1.text.strip() if h1 else "Missing"
    
    text_content = soup.get_text(separator=" ", strip=True)[:4000]
    word_count = len(text_content.split())
    h2_count = len(soup.find_all("h2"))
    img_count = len(soup.find_all("img"))
    link_count = len(soup.find_all("a", href=True))
    
    prompt = f"""You are a Senior SEO Expert analyzing a webpage. Provide a concise, actionable audit.

Page URL: {url}
Primary Keyword: {keyword or "Not specified"}
Location: {location or "Not specified"}

Page Data:
- Title: {title_text}
- Meta Description: {desc_text}
- H1: {h1_text}
- Word Count: {word_count}
- H2 Count: {h2_count}
- Image Count: {img_count}
- Link Count: {link_count}

Content Excerpt:
{text_content[:2000]}

Respond with ONLY a valid JSON array of findings. Each finding must have:
- "check": short name (e.g., "Content Quality", "EEAT Signals")
- "status": one of "critical", "warning", "passed", "info"
- "detail": specific observation about this page
- "recommendation": actionable fix

Provide 4-5 findings covering content depth, EEAT, keyword usage, and AI search optimization."""

    try:
        response = await claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text if response.content else "[]"
        
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            findings = json.loads(json_match.group())
            valid_findings = []
            for f in findings:
                if all(k in f for k in ["check", "status", "detail", "recommendation"]):
                    if f["status"] in ["critical", "warning", "passed", "info"]:
                        valid_findings.append(f)
            
            if valid_findings:
                score = _compute_score(valid_findings)
                return valid_findings, score
                
    except Exception as e:
        return [{
            "check": "AI Deep Analysis",
            "status": "info", 
            "detail": f"Claude analysis error: {str(e)[:100]}",
            "recommendation": "Check API key and network connection"
        }], 50
    
    return [{"check": "AI Deep Analysis", "status": "info", "detail": "Analysis unavailable", "recommendation": "Try again later"}], 50


# ─── Standard Audit Agents ──────────────────────────────────────────

async def agent_technical(client: httpx.AsyncClient, url: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, headers = await fetch_page(client, url)

    if status == 0:
        findings.append({"check": "HTTP Status", "status": "critical", "detail": "Site unreachable", "recommendation": "Check server availability and DNS"})
    elif status >= 400:
        findings.append({"check": "HTTP Status", "status": "critical", "detail": f"Returned {status}", "recommendation": "Fix server errors"})
    else:
        findings.append({"check": "HTTP Status", "status": "passed", "detail": f"Returned {status}", "recommendation": "No action needed"})

    if url.startswith("https://"):
        findings.append({"check": "HTTPS", "status": "passed", "detail": "Valid HTTPS connection", "recommendation": "No action needed"})
    else:
        findings.append({"check": "HTTPS", "status": "critical", "detail": "Not using HTTPS", "recommendation": "Install SSL certificate and redirect HTTP to HTTPS"})

    if html:
        soup = parse_html(html)
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            findings.append({"check": "Canonical Tags", "status": "passed", "detail": f"Canonical: {canonical['href']}", "recommendation": "No action needed"})
        else:
            findings.append({"check": "Canonical Tags", "status": "warning", "detail": "No canonical tag found", "recommendation": "Add rel=canonical to all indexable pages"})

        title = soup.find("title")
        if title and title.text.strip():
            title_len = len(title.text.strip())
            if title_len < 30:
                findings.append({"check": "Title Tag", "status": "warning", "detail": f"Title too short ({title_len} chars)", "recommendation": "Use 50-60 character titles with primary keyword"})
            elif title_len > 65:
                findings.append({"check": "Title Tag", "status": "warning", "detail": f"Title too long ({title_len} chars)", "recommendation": "Keep titles under 60 characters"})
            else:
                findings.append({"check": "Title Tag", "status": "passed", "detail": f"Title: {title.text.strip()[:60]}", "recommendation": "No action needed"})
        else:
            findings.append({"check": "Title Tag", "status": "critical", "detail": "Missing title tag", "recommendation": "Add a descriptive title tag"})

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc_len = len(meta_desc["content"])
            if desc_len < 120:
                findings.append({"check": "Meta Description", "status": "warning", "detail": f"Description short ({desc_len} chars)", "recommendation": "Use 150-160 character descriptions"})
            else:
                findings.append({"check": "Meta Description", "status": "passed", "detail": f"Description: {meta_desc['content'][:80]}...", "recommendation": "No action needed"})
        else:
            findings.append({"check": "Meta Description", "status": "critical", "detail": "Missing meta description", "recommendation": "Add a meta description with target keyword"})

        h1s = soup.find_all("h1")
        if len(h1s) == 1:
            findings.append({"check": "H1 Structure", "status": "passed", "detail": f"Single H1: {h1s[0].text.strip()[:60]}", "recommendation": "No action needed"})
        elif len(h1s) == 0:
            findings.append({"check": "H1 Structure", "status": "critical", "detail": "No H1 found", "recommendation": "Add exactly one H1 per page"})
        else:
            findings.append({"check": "H1 Structure", "status": "warning", "detail": f"{len(h1s)} H1s found", "recommendation": "Use only one H1 per page"})

        images = soup.find_all("img")
        missing_alt = [img for img in images if not img.get("alt")]
        if images:
            if missing_alt:
                findings.append({"check": "Image Alt Text", "status": "warning", "detail": f"{len(missing_alt)} of {len(images)} images missing alt", "recommendation": "Add descriptive alt text to all images"})
            else:
                findings.append({"check": "Image Alt Text", "status": "passed", "detail": f"All {len(images)} images have alt text", "recommendation": "No action needed"})

        json_ld = soup.find_all("script", type="application/ld+json")
        if json_ld:
            findings.append({"check": "Structured Data", "status": "passed", "detail": f"{len(json_ld)} JSON-LD blocks found", "recommendation": "No action needed"})
        else:
            findings.append({"check": "Structured Data", "status": "warning", "detail": "No JSON-LD detected", "recommendation": "Add Organization and LocalBusiness schema"})

        viewport = soup.find("meta", attrs={"name": "viewport"})
        if viewport:
            findings.append({"check": "Mobile Friendly", "status": "passed", "detail": "Viewport meta tag present", "recommendation": "No action needed"})
        else:
            findings.append({"check": "Mobile Friendly", "status": "critical", "detail": "No viewport meta tag", "recommendation": "Add responsive viewport meta tag"})

    robots_url = url.rstrip("/") + "/robots.txt"
    r_status, r_html, _ = await fetch_page(client, robots_url)
    if r_status == 200 and r_html:
        findings.append({"check": "Robots.txt", "status": "passed", "detail": "Robots.txt found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Robots.txt", "status": "warning", "detail": "No robots.txt found", "recommendation": "Add a robots.txt file"})

    sitemap_url = url.rstrip("/") + "/sitemap.xml"
    s_status, s_html, _ = await fetch_page(client, sitemap_url)
    if s_status == 200 and "<urlset" in (s_html or "").lower():
        findings.append({"check": "XML Sitemap", "status": "passed", "detail": "Sitemap detected", "recommendation": "Submit to Google Search Console"})
    else:
        findings.append({"check": "XML Sitemap", "status": "warning", "detail": "No XML sitemap found", "recommendation": "Generate and submit an XML sitemap"})

    if "content-encoding" in {k.lower() for k in headers}:
        findings.append({"check": "Compression", "status": "passed", "detail": f"Encoding: {headers.get('content-encoding', 'gzip')}", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Compression", "status": "warning", "detail": "No compression detected", "recommendation": "Enable gzip or brotli compression"})

    score = _compute_score(findings)
    return findings, score


async def agent_content(client: httpx.AsyncClient, url: str, keyword: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, _ = await fetch_page(client, url)

    if not html:
        return [{"check": "Content Analysis", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    text = soup.get_text(separator=" ", strip=True)
    word_count = len(text.split())

    if word_count < 300:
        findings.append({"check": "Content Depth", "status": "critical", "detail": f"Only {word_count} words", "recommendation": "Expand to 800+ words with valuable information"})
    elif word_count < 600:
        findings.append({"check": "Content Depth", "status": "warning", "detail": f"{word_count} words (thin content)", "recommendation": "Add more detailed sections"})
    else:
        findings.append({"check": "Content Depth", "status": "passed", "detail": f"{word_count} words", "recommendation": "No action needed"})

    title = soup.find("title")
    if keyword and title and keyword.lower() in title.text.lower():
        findings.append({"check": "Keyword in Title", "status": "passed", "detail": f"'{keyword}' found in title", "recommendation": "No action needed"})
    elif keyword:
        findings.append({"check": "Keyword in Title", "status": "warning", "detail": f"'{keyword}' not in title", "recommendation": "Include primary keyword in title tag"})

    h1 = soup.find("h1")
    if keyword and h1 and keyword.lower() in h1.text.lower():
        findings.append({"check": "Keyword in H1", "status": "passed", "detail": f"'{keyword}' found in H1", "recommendation": "No action needed"})
    elif keyword:
        findings.append({"check": "Keyword in H1", "status": "warning", "detail": f"'{keyword}' not in H1", "recommendation": "Include primary keyword in H1 heading"})

    if keyword and word_count > 0:
        density = (text.lower().count(keyword.lower()) / word_count) * 100
        if density < 0.5:
            findings.append({"check": "Keyword Density", "status": "warning", "detail": f"{density:.1f}% density (low)", "recommendation": "Use keyword naturally 2-3 times"})
        elif density > 3:
            findings.append({"check": "Keyword Density", "status": "warning", "detail": f"{density:.1f}% density (high)", "recommendation": "Reduce keyword stuffing"})
        else:
            findings.append({"check": "Keyword Density", "status": "passed", "detail": f"{density:.1f}% density", "recommendation": "No action needed"})

    h2s = soup.find_all("h2")
    if len(h2s) >= 3:
        findings.append({"check": "Subheadings", "status": "passed", "detail": f"{len(h2s)} H2 sections", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Subheadings", "status": "warning", "detail": f"Only {len(h2s)} H2s", "recommendation": "Add more H2 sections for structure"})

    links = soup.find_all("a", href=True)
    internal = [l for l in links if l["href"].startswith("/") or url in l["href"]]
    if len(internal) >= 5:
        findings.append({"check": "Internal Links", "status": "passed", "detail": f"{len(internal)} internal links", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Internal Links", "status": "warning", "detail": f"Only {len(internal)} internal links", "recommendation": "Add more internal links to related pages"})

    faq = soup.find(string=re.compile(r"faq|frequently asked", re.I))
    if faq:
        findings.append({"check": "FAQ Section", "status": "passed", "detail": "FAQ section detected", "recommendation": "No action needed"})
    else:
        findings.append({"check": "FAQ Section", "status": "warning", "detail": "No FAQ section found", "recommendation": "Add FAQ with 5+ common questions"})

    score = _compute_score(findings)
    return findings, score


async def agent_local(client: httpx.AsyncClient, url: str, location: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, _ = await fetch_page(client, url)

    if not html:
        return [{"check": "Local Analysis", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    text = soup.get_text(separator=" ", strip=True)

    phone_pattern = re.compile(r"\+?1?[\(\)\-\s]?\d{3}[\)\-\s]?\d{3}[\-\s]?\d{4}")
    phone_found = phone_pattern.search(text)
    if phone_found:
        findings.append({"check": "Phone Number", "status": "passed", "detail": f"Phone: {phone_found.group()}", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Phone Number", "status": "warning", "detail": "No phone number found", "recommendation": "Display business phone prominently"})

    if location and location.lower() in text.lower():
        findings.append({"check": "Location Mention", "status": "passed", "detail": f"'{location}' found in content", "recommendation": "No action needed"})
    elif location:
        findings.append({"check": "Location Mention", "status": "warning", "detail": f"'{location}' not found in content", "recommendation": "Mention city/region in page content"})

    json_ld = soup.find_all("script", type="application/ld+json")
    has_local_schema = False
    for script in json_ld:
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict) and data.get("@type") in ("LocalBusiness", "Organization"):
                has_local_schema = True
        except (json.JSONDecodeError, TypeError):
            pass
    if has_local_schema:
        findings.append({"check": "Local Schema", "status": "passed", "detail": "LocalBusiness/Organization schema found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Local Schema", "status": "critical", "detail": "No LocalBusiness schema", "recommendation": "Add LocalBusiness JSON-LD with NAP details"})

    iframe = soup.find("iframe", src=re.compile(r"google\.com/maps"))
    if iframe:
        findings.append({"check": "Google Maps", "status": "passed", "detail": "Google Maps embed found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Google Maps", "status": "warning", "detail": "No Google Maps embed", "recommendation": "Embed a Google Map on contact/location page"})

    score = _compute_score(findings)
    return findings, score


async def agent_schema(client: httpx.AsyncClient, url: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, _ = await fetch_page(client, url)

    if not html:
        return [{"check": "Schema Analysis", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    json_ld_scripts = soup.find_all("script", type="application/ld+json")

    schema_types: list[str] = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                schema_types.append(data.get("@type", "Unknown"))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        schema_types.append(item.get("@type", "Unknown"))
        except (json.JSONDecodeError, TypeError):
            findings.append({"check": "Schema Validation", "status": "warning", "detail": "Invalid JSON-LD detected", "recommendation": "Fix JSON-LD syntax errors"})

    expected = ["Organization", "LocalBusiness", "Service", "FAQPage", "BreadcrumbList", "Article", "Review", "Product"]
    found = [t for t in expected if any(t in s for s in schema_types)]
    missing = [t for t in expected if t not in found]

    if found:
        findings.append({"check": "Schema Types", "status": "passed", "detail": f"Found: {', '.join(found)}", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Schema Types", "status": "critical", "detail": "No structured data found", "recommendation": "Add JSON-LD schema markup"})

    if missing:
        findings.append({"check": "Missing Schema", "status": "warning", "detail": f"Missing: {', '.join(missing[:4])}", "recommendation": "Add missing schema types for richer snippets"})

    score = _compute_score(findings)
    return findings, score


async def agent_eeat(client: httpx.AsyncClient, url: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, _ = await fetch_page(client, url)

    if not html:
        return [{"check": "EEAT Analysis", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    text_lower = soup.get_text(separator=" ", strip=True).lower()

    about_link = soup.find("a", href=re.compile(r"/about", re.I))
    if about_link:
        findings.append({"check": "About Page", "status": "passed", "detail": "About page link found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "About Page", "status": "warning", "detail": "No about page link", "recommendation": "Create a detailed about page"})

    contact_link = soup.find("a", href=re.compile(r"/contact", re.I))
    if contact_link:
        findings.append({"check": "Contact Page", "status": "passed", "detail": "Contact page link found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Contact Page", "status": "warning", "detail": "No contact page link", "recommendation": "Add a contact page with multiple methods"})

    privacy_link = soup.find("a", href=re.compile(r"privacy", re.I))
    if privacy_link:
        findings.append({"check": "Privacy Policy", "status": "passed", "detail": "Privacy policy link found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Privacy Policy", "status": "warning", "detail": "No privacy policy link", "recommendation": "Add a privacy policy page"})

    author = soup.find(attrs={"rel": "author"}) or soup.find("span", class_=re.compile(r"author", re.I))
    if author:
        findings.append({"check": "Author Info", "status": "passed", "detail": "Author attribution found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Author Info", "status": "critical", "detail": "No author attribution", "recommendation": "Add author bylines and bio pages"})

    trust_keywords = ["testimonial", "review", "certified", "licensed", "award", "trusted", "since"]
    trust_found = [kw for kw in trust_keywords if kw in text_lower]
    if len(trust_found) >= 2:
        findings.append({"check": "Trust Signals", "status": "passed", "detail": f"Found: {', '.join(trust_found[:3])}", "recommendation": "No action needed"})
    elif trust_found:
        findings.append({"check": "Trust Signals", "status": "warning", "detail": f"Limited: {', '.join(trust_found)}", "recommendation": "Add testimonials, certifications, and awards"})
    else:
        findings.append({"check": "Trust Signals", "status": "warning", "detail": "No trust signals found", "recommendation": "Add reviews, certifications, and trust badges"})

    score = _compute_score(findings)
    return findings, score


async def agent_internal_linking(client: httpx.AsyncClient, url: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, _ = await fetch_page(client, url)

    if not html:
        return [{"check": "Internal Linking", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    links = soup.find_all("a", href=True)
    internal = [l for l in links if l["href"].startswith("/") or url in l["href"]]

    generic = ["click here", "read more", "learn more", "here", "more"]
    generic_anchors = [l for l in internal if l.text.strip().lower() in generic]
    if generic_anchors:
        findings.append({"check": "Anchor Text", "status": "warning", "detail": f"{len(generic_anchors)} generic anchors", "recommendation": "Use descriptive keyword-rich anchor text"})
    else:
        findings.append({"check": "Anchor Text", "status": "passed", "detail": "No generic anchor text", "recommendation": "No action needed"})

    if len(internal) >= 10:
        findings.append({"check": "Link Count", "status": "passed", "detail": f"{len(internal)} internal links", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Link Count", "status": "warning", "detail": f"Only {len(internal)} internal links", "recommendation": "Add more internal links to related content"})

    breadcrumb = soup.find(class_=re.compile(r"breadcrumb", re.I))
    if breadcrumb:
        findings.append({"check": "Breadcrumbs", "status": "passed", "detail": "Breadcrumb navigation found", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Breadcrumbs", "status": "warning", "detail": "No breadcrumbs detected", "recommendation": "Add breadcrumb navigation with schema"})

    score = _compute_score(findings)
    return findings, score


async def agent_competitor(client: httpx.AsyncClient, url: str, competitors: list[str]) -> tuple[list[dict], int]:
    findings: list[dict] = []

    if not competitors:
        findings.append({"check": "Competitor Setup", "status": "info", "detail": "No competitors provided", "recommendation": "Add competitor URLs for gap analysis"})
        return findings, 70

    _, target_html, _ = await fetch_page(client, url)
    target_words = len(parse_html(target_html).get_text().split()) if target_html else 0

    for comp_url in competitors[:3]:
        _, comp_html, _ = await fetch_page(client, comp_url)
        comp_words = len(parse_html(comp_html).get_text().split()) if comp_html else 0

        if comp_words > target_words * 1.3:
            findings.append({"check": f"Content vs {comp_url}", "status": "warning", "detail": f"Competitor has {comp_words} words vs your {target_words}", "recommendation": "Expand content to match or exceed competitor depth"})
        elif comp_html:
            findings.append({"check": f"Content vs {comp_url}", "status": "passed", "detail": f"Content depth comparable ({target_words} vs {comp_words})", "recommendation": "No action needed"})
        else:
            findings.append({"check": f"Content vs {comp_url}", "status": "info", "detail": "Competitor unreachable", "recommendation": "Verify competitor URL"})

    score = _compute_score(findings)
    return findings, score


async def agent_backlink(client: httpx.AsyncClient, url: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    findings.append({"check": "Referring Domains", "status": "info", "detail": "Connect Ahrefs/Majestic API for full data", "recommendation": "Integrate a backlink API for detailed analysis"})
    findings.append({"check": "Backlink Profile", "status": "info", "detail": "Requires third-party API", "recommendation": "Use Moz, Ahrefs, or Semrush for backlink audit"})
    score = _compute_score(findings)
    return findings, score


async def agent_ai_search(client: httpx.AsyncClient, url: str, keyword: str) -> tuple[list[dict], int]:
    findings: list[dict] = []
    status, html, _ = await fetch_page(client, url)

    if not html:
        return [{"check": "AI Search Analysis", "status": "critical", "detail": "Page unreachable", "recommendation": "Ensure page is accessible"}], 25

    soup = parse_html(html)
    text = soup.get_text(separator=" ", strip=True)

    question_patterns = [r"what is", r"how to", r"why", r"when", r"where", r"how much", r"how long"]
    questions_found = sum(1 for p in question_patterns if re.search(p, text, re.I))
    if questions_found >= 4:
        findings.append({"check": "Question Coverage", "status": "passed", "detail": f"{questions_found} question patterns found", "recommendation": "No action needed"})
    elif questions_found >= 2:
        findings.append({"check": "Question Coverage", "status": "warning", "detail": f"Only {questions_found} question patterns", "recommendation": "Add more Q&A format content"})
    else:
        findings.append({"check": "Question Coverage", "status": "critical", "detail": "Few question patterns found", "recommendation": "Add FAQ section with common questions"})

    entities = re.findall(r"\b[A-Z][a-z]{3,}\b", text)
    unique_entities = set(entities) - {"The", "This", "That", "These", "Those", "Monday", "Tuesday"}
    if len(unique_entities) >= 10:
        findings.append({"check": "Entity Coverage", "status": "passed", "detail": f"{len(unique_entities)} unique entities", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Entity Coverage", "status": "warning", "detail": f"Only {len(unique_entities)} entities", "recommendation": "Add more specific entity mentions"})

    word_count = len(text.split())
    if word_count >= 800:
        findings.append({"check": "Semantic Depth", "status": "passed", "detail": f"{word_count} words of content", "recommendation": "No action needed"})
    else:
        findings.append({"check": "Semantic Depth", "status": "warning", "detail": f"Only {word_count} words", "recommendation": "Expand content for better AI comprehension"})

    json_ld = soup.find_all("script", type="application/ld+json")
    if json_ld:
        findings.append({"check": "AI-Readable Schema", "status": "passed", "detail": f"{len(json_ld)} schema blocks", "recommendation": "No action needed"})
    else:
        findings.append({"check": "AI-Readable Schema", "status": "critical", "detail": "No structured data for AI", "recommendation": "Add schema so AI engines can parse content"})

    score = _compute_score(findings)
    return findings, score


# ─── Score Computation ────────────────────────────────────────────

def _compute_score(findings: list[dict]) -> int:
    weights = {"passed": 100, "info": 80, "warning": 55, "critical": 25}
    if not findings:
        return 70
    total = sum(weights.get(f["status"], 50) for f in findings)
    return round(total / len(findings))


# ─── Agent Registry ───────────────────────────────────────────────

AGENTS = [
    ("Technical SEO", agent_technical),
    ("Content SEO", agent_content),
    ("Local SEO", agent_local),
    ("Schema", agent_schema),
    ("EEAT", agent_eeat),
    ("Internal Linking", agent_internal_linking),
    ("Competitor", agent_competitor),
    ("Backlink", agent_backlink),
    ("AI Search", agent_ai_search),
    ("Claude AI Deep Analysis", agent_claude_seo),
]


# ─── SSE Stream Endpoint ──────────────────────────────────────────

@app.post("/api/audit/stream")
async def audit_stream(req: AuditRequest):
    async def event_generator() -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient() as client:
            scores: dict[str, int] = {}

            for agent_name, agent_func in AGENTS:
                yield sse_event({"type": "agent_start", "agent": agent_name})
                await asyncio.sleep(0.1)

                try:
                    if agent_name == "Content SEO":
                        findings, score = await agent_func(client, req.url, req.primary_keyword)
                    elif agent_name == "Local SEO":
                        findings, score = await agent_func(client, req.url, req.location)
                    elif agent_name == "Competitor":
                        findings, score = await agent_func(client, req.url, req.competitors)
                    elif agent_name == "AI Search":
                        findings, score = await agent_func(client, req.url, req.primary_keyword)
                    elif agent_name == "Claude AI Deep Analysis":
                        findings, score = await agent_func(client, req.url, req.primary_keyword, req.location)
                    else:
                        findings, score = await agent_func(client, req.url)

                    for f in findings:
                        f["agent"] = agent_name
                        yield sse_event({"type": "finding", **f})
                        await asyncio.sleep(0.05)

                    key = "Technical" if agent_name == "Technical SEO" else "Content" if agent_name == "Content SEO" else agent_name
                    scores[key] = score
                    yield sse_event({"type": "agent_done", "agent": agent_name, "score": score})

                except Exception as e:
                    yield sse_event({"type": "error", "agent": agent_name, "message": str(e)})

                await asyncio.sleep(0.15)

            overall = round(sum(scores.values()) / len(scores)) if scores else 0
            yield sse_event({"type": "audit_complete", "scores": scores, "overall": overall})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok", 
        "engine": "Boost Rankers AI SEO OS",
        "claude_enabled": claude_client is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
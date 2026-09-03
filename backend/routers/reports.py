from __future__ import annotations

import io
import re
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.deps.current_user import get_current_company
from database.database import get_db
from models.company import Company
from services.report_service import ReportService


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


def _report_payload(report):
    return {
        "id": str(report.id),
        "title": report.title,
        "client_name": (
            report.client.business_name
            if report.client
            else "N/A"
        ),
        "date": (
            report.generated_at.isoformat()
            if report.generated_at
            else None
        ),
        "score": float(report.score or 0),
        "format": report.format,
        "content": report.content or "",
        "summary": report.summary or "",
        "audit_id": (
            str(report.audit_id)
            if report.audit_id
            else None
        ),
    }


@router.get("/")
def get_reports(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = ReportService(db)

    reports = service.get_reports_for_company(
        str(company.id),
        limit,
    )

    return [
        _report_payload(report)
        for report in reports
    ]


@router.get("/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = ReportService(db)

    report = service.get_report(
        report_id,
        str(company.id),
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    return _report_payload(report)


@router.delete("/{report_id}")
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    service = ReportService(db)

    if not service.delete_report(
        report_id,
        str(company.id),
    ):
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    return {
        "success": True,
        "message": "Report deleted successfully.",
    }



def _safe_filename(value: str, extension: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", str(value or "")).strip(" .")
    value = re.sub(r"\s+", " ", value)
    return f"{value or 'seo-audit-report'}.{extension}"


def _clean(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _audit_value(audit, *names, default=0):
    for name in names:
        value = getattr(audit, name, None) if audit is not None else None
        if value is not None:
            return value
    return default


def _extract_urls(content: str) -> list[str]:
    urls = re.findall(r"https?://[^\s<>'\")\],]+", content or "")
    result = []
    seen = set()
    for url in urls:
        url = url.rstrip(".,;:")
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _extract_findings(content: str) -> list[dict]:
    """
    Read findings already stored in Report.content.

    This export layer never invents audit findings. It supports both:
    1. structured dictionary-like findings stored by older report versions;
    2. severity-led Markdown findings.
    """
    content = content or ""
    findings = []

    dict_pattern = re.compile(
        r"""\{['"]severity['"]\s*:\s*['"](?P<severity>[^'"]+)['"]
        .*?['"]title['"]\s*:\s*['"](?P<title>.*?)['"]
        .*?['"]detail['"]\s*:\s*['"](?P<detail>.*?)['"]
        .*?['"]recommendation['"]\s*:\s*['"](?P<recommendation>.*?)['"]
        .*?['"]evidence['"]\s*:\s*['"](?P<evidence>.*?)['"]\s*\}""",
        re.I | re.S | re.X,
    )

    for match in dict_pattern.finditer(content):
        item = {k: _clean(v) for k, v in match.groupdict().items()}
        findings.append(item)

    if findings:
        return findings

    severity_re = re.compile(
        r"^\s*(?:[-*]\s*)?(CRITICAL|HIGH|MEDIUM|LOW)\s*(?:—|-|:)\s*(.+)$",
        re.I,
    )

    current = None
    for raw in content.splitlines():
        line = _clean(raw)
        if not line:
            continue

        match = severity_re.match(line)
        if match:
            if current:
                findings.append(current)
            current = {
                "severity": match.group(1).lower(),
                "title": _clean(match.group(2)),
                "detail": "",
                "recommendation": "",
                "evidence": "",
            }
            urls = _extract_urls(current["title"])
            current["url"] = urls[0] if urls else ""
            continue

        if current is None:
            continue

        lower = line.lower()
        if lower.startswith("evidence:"):
            current["evidence"] = _clean(line.split(":", 1)[1])
        elif lower.startswith("recommended action:"):
            current["recommendation"] = _clean(line.split(":", 1)[1])
        elif lower.startswith("recommendation:"):
            current["recommendation"] = _clean(line.split(":", 1)[1])
        elif lower.startswith("what the crawl reports:"):
            current["detail"] = _clean(line.split(":", 1)[1])
        elif not current["detail"] and not line.startswith("#"):
            current["detail"] = line

    if current:
        findings.append(current)

    return findings


def _escape_pdf(value: str) -> str:
    return (
        _clean(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _build_docx(report) -> bytes:
    try:
        from docx import Document
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor
    except ImportError as exc:
        raise RuntimeError(
            "python-docx is required for DOCX generation."
        ) from exc

    NAVY = "0B1220"
    BLUE = "123B5D"
    TEAL = "0F766E"
    LIGHT = "F5F7FA"
    BORDER = "D7DEE8"
    TEXT = "263241"
    MUTED = "667085"

    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.62)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.68)
    section.right_margin = Inches(0.68)

    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(9)
    styles["Normal"].font.color.rgb = RGBColor.from_string(TEXT)

    for name, size, color in (
        ("Title", 25, NAVY),
        ("Heading 1", 17, NAVY),
        ("Heading 2", 12.5, BLUE),
        ("Heading 3", 10.5, NAVY),
    ):
        style = styles[name]
        style.font.name = "Aptos Display"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)

    def shade(cell, fill):
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = tc_pr.find(qn("w:shd"))
        if shd is None:
            shd = OxmlElement("w:shd")
            tc_pr.append(shd)
        shd.set(qn("w:fill"), fill)

    def cell_text(cell, text, bold=False, color=TEXT, size=8.5):
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(_clean(text))
        run.bold = bold
        run.font.name = "Aptos"
        run.font.size = Pt(size)
        run.font.color.rgb = RGBColor.from_string(color)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

    def cell_margins(cell, top=90, start=100, bottom=90, end=100):
        tc_pr = cell._tc.get_or_add_tcPr()
        tc_mar = tc_pr.first_child_found_in("w:tcMar")
        if tc_mar is None:
            tc_mar = OxmlElement("w:tcMar")
            tc_pr.append(tc_mar)
        for name, value in (
            ("top", top), ("start", start), ("bottom", bottom), ("end", end)
        ):
            node = tc_mar.find(qn(f"w:{name}"))
            if node is None:
                node = OxmlElement(f"w:{name}")
                tc_mar.append(node)
            node.set(qn("w:w"), str(value))
            node.set(qn("w:type"), "dxa")

    def bottom_border(cell):
        tc_pr = cell._tc.get_or_add_tcPr()
        borders = tc_pr.first_child_found_in("w:tcBorders")
        if borders is None:
            borders = OxmlElement("w:tcBorders")
            tc_pr.append(borders)
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "0")
        bottom.set(qn("w:color"), BORDER)
        borders.append(bottom)

    header = section.header.paragraphs[0]
    header.text = "BOOST RANKERS  •  AI SEO OS"
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.bold = True
    header.runs[0].font.color.rgb = RGBColor.from_string(BLUE)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = footer.add_run("Page ")
    run.font.size = Pt(7.5)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(end)

    audit = getattr(report, "audit", None)
    content = report.content or ""
    findings = _extract_findings(content)
    website = _clean(_audit_value(audit, "website", "url", default=""))

    # Cover page
    for _ in range(7):
        document.add_paragraph()

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("BOOST RANKERS")
    r.bold = True
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor.from_string(TEAL)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Professional SEO Audit Report")
    r.bold = True
    r.font.size = Pt(27)
    r.font.color.rgb = RGBColor.from_string(NAVY)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(website or report.title or "Website SEO Audit")
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor.from_string(MUTED)

    document.add_paragraph()

    cover = document.add_table(rows=5, cols=2)
    cover.alignment = WD_TABLE_ALIGNMENT.CENTER
    cover_data = [
        ("Overall SEO Score", f"{float(report.score or 0):.1f}/100"),
        (
            "Audit Date",
            report.generated_at.strftime("%d %B %Y %H:%M UTC")
            if report.generated_at else "N/A",
        ),
        ("Pages Discovered", _audit_value(audit, "pages_discovered", default=0)),
        ("Pages Crawled", _audit_value(audit, "pages_crawled", default=0)),
        (
            "Pages Successful / Failed",
            f"{_audit_value(audit, 'pages_successful', default=0)} / "
            f"{_audit_value(audit, 'pages_failed', default=0)}",
        ),
    ]
    for i, (label, value) in enumerate(cover_data):
        cell_text(cover.rows[i].cells[0], label, bold=True, color=BLUE)
        cell_text(cover.rows[i].cells[1], value, color=TEXT)
        shade(cover.rows[i].cells[0], LIGHT)
        cell_margins(cover.rows[i].cells[0])
        cell_margins(cover.rows[i].cells[1])

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "Generated from the same completed Report and Audit record shown in the Reports tab."
    )
    r.font.size = Pt(8.5)
    r.font.color.rgb = RGBColor.from_string(MUTED)

    document.add_page_break()

    # Executive summary
    document.add_heading("1. Executive Summary", level=1)
    p = document.add_paragraph()
    p.add_run("Overall SEO score: ").bold = True
    p.add_run(f"{float(report.score or 0):.1f}/100")
    p.add_run(
        f". The stored report contains {len(findings)} structured findings."
    )

    if report.summary:
        document.add_paragraph(_clean(report.summary))

    # Scorecard
    document.add_heading("2. SEO Scorecard", level=1)
    scorecard = [
        ("Technical SEO", _audit_value(audit, "technical_score", default=0)),
        ("Content SEO", _audit_value(audit, "content_score", default=0)),
        ("Local SEO", _audit_value(audit, "local_seo_score", "local_score", default=0)),
        ("Schema", _audit_value(audit, "schema_score", default=0)),
        ("EEAT", _audit_value(audit, "eeat_score", "eeat", default=0)),
        ("AI Search", _audit_value(audit, "ai_search_score", "ai_score", default=0)),
        ("Internal Linking", _audit_value(audit, "internal_linking_score", default=0)),
        ("Backlinks", _audit_value(audit, "backlink_score", "backlinks_score", default=0)),
    ]

    table = document.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_text(table.rows[0].cells[0], "SEO Area", bold=True, color="FFFFFF")
    cell_text(table.rows[0].cells[1], "Score", bold=True, color="FFFFFF")
    shade(table.rows[0].cells[0], BLUE)
    shade(table.rows[0].cells[1], BLUE)

    for label, value in scorecard:
        cells = table.add_row().cells
        cell_text(cells[0], label)
        cell_text(cells[1], f"{float(value or 0):.1f}/100", bold=True, color=NAVY)
        shade(cells[1], LIGHT)
        bottom_border(cells[0])
        bottom_border(cells[1])

    # Crawl evidence
    document.add_heading("3. Real Crawl Evidence", level=1)
    metrics = [
        ("Pages discovered", _audit_value(audit, "pages_discovered", default=0)),
        ("Pages crawled", _audit_value(audit, "pages_crawled", default=0)),
        ("Pages successful", _audit_value(audit, "pages_successful", default=0)),
        ("Pages failed", _audit_value(audit, "pages_failed", default=0)),
        ("Internal links", _audit_value(audit, "internal_links", default=0)),
        ("External links", _audit_value(audit, "external_links", default=0)),
        ("Broken internal links", _audit_value(audit, "broken_internal_links", default=0)),
        ("Orphan pages", _audit_value(audit, "orphan_pages_count", default=0)),
        ("Sitemap found", "Yes" if _audit_value(audit, "sitemap_found", default=False) else "No"),
        ("Robots.txt found", "Yes" if _audit_value(audit, "robots_found", default=False) else "No"),
        ("Schema detected", "Yes" if _audit_value(audit, "schema_found", default=False) else "No"),
    ]

    table = document.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_text(table.rows[0].cells[0], "Measured metric", bold=True, color="FFFFFF")
    cell_text(table.rows[0].cells[1], "Value", bold=True, color="FFFFFF")
    shade(table.rows[0].cells[0], TEAL)
    shade(table.rows[0].cells[1], TEAL)

    for label, value in metrics:
        cells = table.add_row().cells
        cell_text(cells[0], label)
        cell_text(cells[1], value, bold=True, color=NAVY)
        shade(cells[1], LIGHT)
        bottom_border(cells[0])
        bottom_border(cells[1])

    # Findings
    document.add_page_break()
    document.add_heading("4. Findings by SEO Skill", level=1)

    if not findings:
        document.add_paragraph(
            "No structured findings were available in the stored report content."
        )
    else:
        severity_colors = {
            "CRITICAL": "B42318",
            "HIGH": "B54708",
            "MEDIUM": "175CD3",
            "LOW": "667085",
        }

        for index, finding in enumerate(findings, 1):
            severity = _clean(finding.get("severity", "INFO")).upper()
            severity_color = severity_colors.get(severity, MUTED)

            card = document.add_table(rows=1, cols=1)
            cell = card.cell(0, 0)
            shade(cell, "F8FAFC")
            cell_margins(cell, 110, 130, 110, 130)

            p = cell.paragraphs[0]
            r = p.add_run(f"{index:02d}  {severity}  ")
            r.bold = True
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor.from_string(severity_color)

            r = p.add_run(_clean(finding.get("title", "SEO finding")))
            r.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor.from_string(NAVY)

            url = _clean(finding.get("url", ""))
            if not url:
                urls = _extract_urls(finding.get("title", ""))
                url = urls[0] if urls else ""

            if url:
                p = cell.add_paragraph()
                r = p.add_run("Affected URL: ")
                r.bold = True
                r.font.size = Pt(8)
                r.font.color.rgb = RGBColor.from_string(BLUE)
                r = p.add_run(url)
                r.font.size = Pt(8)

            for label, key in (
                ("What the crawl reports", "detail"),
                ("Recommended action", "recommendation"),
                ("Evidence", "evidence"),
            ):
                value = _clean(finding.get(key, ""))
                if not value:
                    continue
                p = cell.add_paragraph()
                r = p.add_run(f"{label}: ")
                r.bold = True
                r.font.size = Pt(8)
                r.font.color.rgb = RGBColor.from_string(BLUE)
                r = p.add_run(value)
                r.font.size = Pt(8)

            document.add_paragraph()

    # URL evidence
    document.add_page_break()
    document.add_heading("5. Page-Level URL Evidence", level=1)
    urls = _extract_urls(content)

    for finding in findings:
        url = _clean(finding.get("url", ""))
        if url and url not in urls:
            urls.append(url)

    if urls:
        document.add_paragraph(
            "These URLs are extracted from the stored report content. "
            "The export layer does not invent page URLs."
        )

        table = document.add_table(rows=1, cols=3)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, heading in enumerate(("No.", "Page URL", "Related finding")):
            cell_text(table.rows[0].cells[i], heading, bold=True, color="FFFFFF", size=8)
            shade(table.rows[0].cells[i], BLUE)

        for index, url in enumerate(urls, 1):
            related = "URL referenced by audit evidence"
            for finding in findings:
                if url == _clean(finding.get("url", "")):
                    related = _clean(finding.get("title", related))
                    break

            cells = table.add_row().cells
            cell_text(cells[0], index, bold=True, color=NAVY, size=7)
            cell_text(cells[1], url, size=7)
            cell_text(cells[2], related, size=7)
            for cell in cells:
                cell_margins(cell, 70, 70, 70, 70)
                bottom_border(cell)
    else:
        document.add_paragraph(
            "No explicit page URLs were available in the stored report content."
        )

    # Integrity and action plan
    document.add_heading("6. Data Integrity", level=1)
    integrity = [
        ("Crawler verified", "HTTP status, titles, metadata, headings, canonicals, robots, schema, links and crawl metrics when present in the stored audit."),
        ("Derived metrics", "Counts and scores calculated from the stored audit evidence."),
        ("AI analysis", "Priorities, impact interpretation and recommendations already stored in the report."),
        ("External data", "Search Console, backlink authority and competitor ranking metrics are only reported when their integrations provide them."),
    ]

    table = document.add_table(rows=1, cols=2)
    for i, heading in enumerate(("Evidence class", "Meaning")):
        cell_text(table.rows[0].cells[i], heading, bold=True, color="FFFFFF")
        shade(table.rows[0].cells[i], BLUE)

    for label, value in integrity:
        cells = table.add_row().cells
        cell_text(cells[0], label, bold=True, color=NAVY)
        cell_text(cells[1], value)
        shade(cells[0], LIGHT)
        bottom_border(cells[0])
        bottom_border(cells[1])

    document.add_heading("7. Recommended Action Plan", level=1)
    for action in (
        "Resolve critical technical and indexability findings first.",
        "Fix duplicate titles, missing metadata, heading issues and broken internal links identified by the stored audit.",
        "Improve internal architecture and reduce excessive crawl depth.",
        "Verify local entity, Contact/About, schema and trust signals.",
        "Apply structured data only where it is supported by the actual page content.",
        "Connect external SEO integrations before reporting external ranking/backlink metrics.",
    ):
        document.add_paragraph(action, style="List Number")

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("BOOST RANKERS AI SEO OS  •  Professional evidence-based reporting")
    r.bold = True
    r.font.size = Pt(8)
    r.font.color.rgb = RGBColor.from_string(MUTED)

    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _build_pdf(report) -> bytes:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is required for PDF generation."
        ) from exc

    NAVY = colors.HexColor("#0B1220")
    BLUE = colors.HexColor("#123B5D")
    TEAL = colors.HexColor("#0F766E")
    LIGHT = colors.HexColor("#F5F7FA")
    BORDER = colors.HexColor("#D7DEE8")
    TEXT = colors.HexColor("#263241")
    MUTED = colors.HexColor("#667085")

    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=17 * mm,
        bottomMargin=14 * mm,
        title=report.title or "SEO Audit Report",
        author="Boost Rankers AI SEO OS",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BRTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=23,
        leading=27,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "BRSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
    h1_style = ParagraphStyle(
        "BRH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=NAVY,
        spaceBefore=6,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BRBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=TEXT,
        spaceAfter=5,
    )
    small_style = ParagraphStyle(
        "BRSmall",
        parent=body_style,
        fontSize=7.5,
        leading=10,
    )
    center_style = ParagraphStyle(
        "BRCenter",
        parent=small_style,
        alignment=TA_CENTER,
    )

    def header_footer(canvas, doc):
        canvas.saveState()
        width, height = A4
        canvas.setFont("Helvetica-Bold", 7.5)
        canvas.setFillColor(BLUE)
        canvas.drawString(18 * mm, height - 10 * mm, "BOOST RANKERS  •  AI SEO OS")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 8 * mm, "Evidence-based SEO audit")
        canvas.drawRightString(192 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    audit = getattr(report, "audit", None)
    content = report.content or ""
    findings = _extract_findings(content)
    website = _clean(_audit_value(audit, "website", "url", default=""))

    story = [
        Spacer(1, 45 * mm),
        Paragraph(
            "BOOST RANKERS",
            ParagraphStyle(
                "BRBrand",
                parent=center_style,
                fontName="Helvetica-Bold",
                fontSize=10,
                textColor=TEAL,
            ),
        ),
        Paragraph("Professional SEO Audit Report", title_style),
        Paragraph(
            _escape_pdf(website or report.title or "Website SEO Audit"),
            subtitle_style,
        ),
        Spacer(1, 8 * mm),
    ]

    cover_data = [
        [Paragraph("<b>Overall SEO Score</b>", small_style),
         Paragraph(f"{float(report.score or 0):.1f}/100", small_style)],
        [Paragraph("<b>Audit Date</b>", small_style),
         Paragraph(
             _escape_pdf(
                 report.generated_at.strftime("%d %B %Y %H:%M UTC")
                 if report.generated_at else "N/A"
             ),
             small_style,
         )],
        [Paragraph("<b>Pages Discovered</b>", small_style),
         Paragraph(_escape_pdf(_audit_value(audit, "pages_discovered", default=0)), small_style)],
        [Paragraph("<b>Pages Crawled</b>", small_style),
         Paragraph(_escape_pdf(_audit_value(audit, "pages_crawled", default=0)), small_style)],
        [Paragraph("<b>Successful / Failed</b>", small_style),
         Paragraph(
             f"{_audit_value(audit, 'pages_successful', default=0)} / "
             f"{_audit_value(audit, 'pages_failed', default=0)}",
             small_style,
         )],
    ]

    cover_table = Table(cover_data, colWidths=[65 * mm, 65 * mm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story += [
        cover_table,
        Spacer(1, 8 * mm),
        Paragraph(
            "Generated from the same completed Report and Audit record shown in the Reports tab.",
            center_style,
        ),
        PageBreak(),
        Paragraph("1. Executive Summary", h1_style),
        Paragraph(
            f"<b>Overall SEO score:</b> {float(report.score or 0):.1f}/100. "
            f"The stored report contains {len(findings)} structured findings.",
            body_style,
        ),
    ]

    if report.summary:
        story.append(Paragraph(_escape_pdf(report.summary), body_style))

    story.append(Paragraph("2. SEO Scorecard", h1_style))

    scorecard = [
        ("Technical SEO", _audit_value(audit, "technical_score", default=0)),
        ("Content SEO", _audit_value(audit, "content_score", default=0)),
        ("Local SEO", _audit_value(audit, "local_seo_score", "local_score", default=0)),
        ("Schema", _audit_value(audit, "schema_score", default=0)),
        ("EEAT", _audit_value(audit, "eeat_score", "eeat", default=0)),
        ("AI Search", _audit_value(audit, "ai_search_score", "ai_score", default=0)),
        ("Internal Linking", _audit_value(audit, "internal_linking_score", default=0)),
        ("Backlinks", _audit_value(audit, "backlink_score", "backlinks_score", default=0)),
    ]

    rows = [[Paragraph("<b>SEO Area</b>", small_style),
             Paragraph("<b>Score</b>", small_style)]]
    rows += [
        [Paragraph(_escape_pdf(label), small_style),
         Paragraph(f"<b>{float(value or 0):.1f}/100</b>", small_style)]
        for label, value in scorecard
    ]

    table = Table(rows, colWidths=[100 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (1, 1), (1, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    story.append(Paragraph("3. Real Crawl Evidence", h1_style))

    metrics = [
        ("Pages discovered", _audit_value(audit, "pages_discovered", default=0)),
        ("Pages crawled", _audit_value(audit, "pages_crawled", default=0)),
        ("Pages successful", _audit_value(audit, "pages_successful", default=0)),
        ("Pages failed", _audit_value(audit, "pages_failed", default=0)),
        ("Internal links", _audit_value(audit, "internal_links", default=0)),
        ("External links", _audit_value(audit, "external_links", default=0)),
        ("Broken internal links", _audit_value(audit, "broken_internal_links", default=0)),
        ("Orphan pages", _audit_value(audit, "orphan_pages_count", default=0)),
        ("Sitemap found", "Yes" if _audit_value(audit, "sitemap_found", default=False) else "No"),
        ("Robots.txt found", "Yes" if _audit_value(audit, "robots_found", default=False) else "No"),
        ("Schema detected", "Yes" if _audit_value(audit, "schema_found", default=False) else "No"),
    ]

    rows = [[Paragraph("<b>Measured metric</b>", small_style),
             Paragraph("<b>Value</b>", small_style)]]
    rows += [
        [Paragraph(_escape_pdf(label), small_style),
         Paragraph(_escape_pdf(value), small_style)]
        for label, value in metrics
    ]

    table = Table(rows, colWidths=[100 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (1, 1), (1, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, PageBreak(), Paragraph("4. Findings by SEO Skill", h1_style)]

    if not findings:
        story.append(
            Paragraph(
                "No structured findings were available in the stored report content.",
                body_style,
            )
        )
    else:
        severity_colors = {
            "CRITICAL": "#B42318",
            "HIGH": "#B54708",
            "MEDIUM": "#175CD3",
            "LOW": "#667085",
        }

        for index, finding in enumerate(findings, 1):
            severity = _clean(finding.get("severity", "INFO")).upper()
            severity_color = severity_colors.get(severity, "#667085")

            rows = [[
                Paragraph(
                    f"<font color='{severity_color}'><b>{index:02d} {severity}</b></font>",
                    small_style,
                ),
                Paragraph(
                    f"<b>{_escape_pdf(finding.get('title', 'SEO finding'))}</b>",
                    body_style,
                ),
            ]]

            url = _clean(finding.get("url", ""))
            if not url:
                extracted = _extract_urls(finding.get("title", ""))
                url = extracted[0] if extracted else ""

            if url:
                rows.append([
                    Paragraph("<b>Affected URL</b>", small_style),
                    Paragraph(_escape_pdf(url), small_style),
                ])

            for label, key in (
                ("What the crawl reports", "detail"),
                ("Recommended action", "recommendation"),
                ("Evidence", "evidence"),
            ):
                value = _clean(finding.get(key, ""))
                if value:
                    rows.append([
                        Paragraph(f"<b>{label}</b>", small_style),
                        Paragraph(_escape_pdf(value), small_style),
                    ])

            table = Table(rows, colWidths=[42 * mm, 88 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story += [KeepTogether(table), Spacer(1, 3 * mm)]

    story += [PageBreak(), Paragraph("5. Page-Level URL Evidence", h1_style)]

    urls = _extract_urls(content)
    for finding in findings:
        url = _clean(finding.get("url", ""))
        if url and url not in urls:
            urls.append(url)

    if urls:
        story.append(
            Paragraph(
                "These URLs are extracted from the stored report content. "
                "The export layer does not invent page URLs.",
                body_style,
            )
        )

        rows = [[
            Paragraph("<b>No.</b>", small_style),
            Paragraph("<b>Page URL</b>", small_style),
            Paragraph("<b>Related finding</b>", small_style),
        ]]

        for index, url in enumerate(urls, 1):
            related = "URL referenced by audit evidence"
            for finding in findings:
                if url == _clean(finding.get("url", "")):
                    related = _clean(finding.get("title", related))
                    break

            rows.append([
                Paragraph(str(index), small_style),
                Paragraph(_escape_pdf(url), small_style),
                Paragraph(_escape_pdf(related), small_style),
            ])

        table = Table(rows, colWidths=[12 * mm, 75 * mm, 43 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
    else:
        story.append(
            Paragraph(
                "No explicit page URLs were available in the stored report content.",
                body_style,
            )
        )

    story.append(Paragraph("6. Data Integrity", h1_style))

    integrity = [
        ("Crawler verified", "HTTP status, titles, metadata, headings, canonicals, robots, schema, links and crawl metrics when present in the stored audit."),
        ("Derived metrics", "Counts and scores calculated from the stored audit evidence."),
        ("AI analysis", "Priorities, impact interpretation and recommendations already stored in the report."),
        ("External data", "Search Console, backlink authority and competitor ranking metrics are only reported when their integrations provide them."),
    ]

    rows = [[
        Paragraph("<b>Evidence class</b>", small_style),
        Paragraph("<b>Meaning</b>", small_style),
    ]]
    rows += [
        [
            Paragraph(f"<b>{_escape_pdf(label)}</b>", small_style),
            Paragraph(_escape_pdf(value), small_style),
        ]
        for label, value in integrity
    ]

    table = Table(rows, colWidths=[42 * mm, 88 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (0, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)

    story.append(Paragraph("7. Recommended Action Plan", h1_style))
    for action in (
        "Resolve critical technical and indexability findings first.",
        "Fix duplicate titles, missing metadata, heading issues and broken internal links identified by the stored audit.",
        "Improve internal architecture and reduce excessive crawl depth.",
        "Verify local entity, Contact/About, schema and trust signals.",
        "Apply structured data only where it is supported by the actual page content.",
        "Connect external SEO integrations before reporting external ranking/backlink metrics.",
    ):
        story.append(Paragraph("• " + _escape_pdf(action), body_style))

    document.build(
        story,
        onFirstPage=header_footer,
        onLaterPages=header_footer,
    )
    return output.getvalue()


@router.get("/{report_id}/download")
def download_report(
    report_id: str,
    format: str = Query(
        default="pdf",
        pattern="^(pdf|docx)$",
    ),
    db: Session = Depends(get_db),
    company: Company = Depends(get_current_company),
):
    """
    Export the exact Report record shown in the Reports tab.

    No new audit is started.
    No crawler is executed.
    No Claude/AI request is made.
    The exporter reads only the stored Report and its related Audit.
    """
    service = ReportService(db)

    report = service.get_report(
        report_id,
        str(company.id),
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail="Report not found",
        )

    try:
        if format == "docx":
            content = _build_docx(report)
            filename = _safe_filename(report.title, "docx")
            media_type = (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        else:
            content = _build_pdf(report)
            filename = _safe_filename(report.title, "pdf")
            media_type = "application/pdf"

    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Report export failed: {exc}",
        ) from exc

    safe_filename = quote(filename)

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{safe_filename}"
            ),
            "Cache-Control": "no-store",
        },
    )
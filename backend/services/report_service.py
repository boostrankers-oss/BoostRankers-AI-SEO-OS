from __future__ import annotations

import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models.report import Report
from models.audit import Audit


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def generate_report_from_audit(self, audit: Audit) -> Report:
        """Generate a report from a completed audit."""
        title = f"SEO Audit Report - {audit.website[:30]}"
        summary = f"Overall Score: {audit.overall_score:.1f}/100. Issues: {audit.critical_issues} critical, {audit.high_priority_issues} high priority."
        content = f"# SEO Audit Report\n\n## Summary\n{summary}\n\n## Details\n- Website: {audit.website}\n- Score: {audit.overall_score}\n- Pages crawled: {audit.pages_crawled}\n- Critical issues: {audit.critical_issues}"

        report = Report(
            company_id=audit.company_id,
            client_id=audit.client_id,
            audit_id=audit.id,
            title=title,
            content=content,
            summary=summary,
            score=audit.overall_score,
            generated_at=datetime.now(timezone.utc),
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_reports_for_company(self, company_id: str, limit: int = 50) -> list[Report]:
        return (
            self.db.query(Report)
            .filter(Report.company_id == company_id)
            .order_by(Report.generated_at.desc())
            .limit(limit)
            .all()
        )

    def get_report(self, report_id: str, company_id: str) -> Report | None:
        return (
            self.db.query(Report)
            .filter(Report.id == report_id, Report.company_id == company_id)
            .first()
        )

    def delete_report(self, report_id: str, company_id: str) -> bool:
        report = self.get_report(report_id, company_id)
        if not report:
            return False
        self.db.delete(report)
        self.db.commit()
        return True
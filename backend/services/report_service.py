from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.audit import Audit
from models.report import Report
from services.report_builder import ReportBuilder


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.builder = ReportBuilder()

    def generate_report_from_audit(
        self,
        audit: Audit,
        results=None,
    ) -> Report:
        """
        Build and persist the full report from the actual audit results.
        """

        content, summary = self.builder.build_markdown(
            audit,
            results,
        )

        title = (
            f"SEO Audit Report - "
            f"{(audit.website or 'Website')[:200]}"
        )

        # Prevent duplicate reports for the same audit.
        existing = (
            self.db.query(Report)
            .filter(
                Report.company_id == audit.company_id,
                Report.audit_id == audit.id,
            )
            .first()
        )

        if existing:
            existing.title = title
            existing.content = content
            existing.summary = summary
            existing.score = float(
                audit.overall_score or 0
            )
            existing.format = "MD"
            existing.generated_at = datetime.now(
                timezone.utc
            )

            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)

            return existing

        report = Report(
            company_id=audit.company_id,
            client_id=audit.client_id,
            audit_id=audit.id,
            title=title,
            content=content,
            summary=summary,
            score=float(
                audit.overall_score or 0
            ),
            format="MD",
            generated_at=datetime.now(
                timezone.utc
            ),
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        return report

    def get_reports_for_company(
        self,
        company_id: str,
        limit: int = 50,
    ) -> list[Report]:
        return (
            self.db.query(Report)
            .filter(
                Report.company_id == company_id
            )
            .order_by(
                Report.generated_at.desc()
            )
            .limit(limit)
            .all()
        )

    def get_report(
        self,
        report_id: str,
        company_id: str,
    ) -> Report | None:
        return (
            self.db.query(Report)
            .filter(
                Report.id == report_id,
                Report.company_id == company_id,
            )
            .first()
        )

    def delete_report(
        self,
        report_id: str,
        company_id: str,
    ) -> bool:
        report = self.get_report(
            report_id,
            company_id,
        )

        if not report:
            return False

        self.db.delete(report)
        self.db.commit()

        return True
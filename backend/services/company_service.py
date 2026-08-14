"""
Boost Rankers AI SEO OS
Production Company Service
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.company import Company
from schemas.company import (
    CompanyCreate,
    CompanyUpdate,
    CompanyFilters,
)


class CompanyService:
    """
    Production Company Service.

    Handles:

    - CRUD
    - Search
    - Dashboard
    - Validation
    - Pagination
    - Archive
    - Restore
    - Statistics
    """

    def __init__(self, db: Session):
        self.db = db
        
            # ============================================================
    # Helpers
    # ============================================================

    @staticmethod
    def generate_slug(name: str) -> str:
        """
        Generate a URL-friendly slug.
        """
        return (
            name.lower()
            .strip()
            .replace("&", "and")
            .replace(" ", "-")
        )

    def company_exists(self, name: str) -> bool:
        """
        Check if a company already exists.
        """
        stmt = select(Company).where(
            func.lower(Company.name) == name.lower()
        )

        return self.db.execute(stmt).scalar_one_or_none() is not None

    def get_by_id(
        self,
        company_id: str,
    ) -> Optional[Company]:
        """
        Get company by ID.
        """
        stmt = select(Company).where(
            Company.id == company_id
        )

        return self.db.execute(stmt).scalar_one_or_none()
        
            # ============================================================
    # CREATE
    # ============================================================

    def create_company(
        self,
        data: CompanyCreate,
    ) -> Company:
        """
        Create a new company.
        """

        if self.company_exists(data.name):
            raise ValueError(
                f"Company '{data.name}' already exists."
            )

        slug = self.generate_slug(data.name)

        company = Company(
            id=str(uuid.uuid4()),
            slug=slug,
            **data.model_dump(exclude_unset=True),
        )

        self.db.add(company)

        try:
            self.db.commit()
            self.db.refresh(company)

        except IntegrityError:
            self.db.rollback()
            raise

        return company
        
            # ============================================================
    # UPDATE
    # ============================================================

    def update_company(
        self,
        company_id: str,
        data: CompanyUpdate,
    ) -> Company:
        """
        Update an existing company.
        """

        company = self.get_by_id(company_id)

        if company is None:
            raise ValueError("Company not found.")

        values = data.model_dump(
            exclude_none=True,
            exclude_unset=True,
        )

        for field, value in values.items():
            setattr(company, field, value)

        company.updated_at = datetime.utcnow()

        try:
            self.db.commit()
            self.db.refresh(company)

        except IntegrityError:
            self.db.rollback()
            raise

        return company
        
            # ============================================================
    # DELETE
    # ============================================================

    def delete_company(
        self,
        company_id: str,
    ) -> bool:
        """
        Soft delete a company.
        """

        company = self.get_by_id(company_id)

        if company is None:
            return False

        company.deleted_at = datetime.utcnow()
        company.is_active = False
        company.is_archived = True

        self.db.commit()

        return True
        
            # ============================================================
    # ARCHIVE
    # ============================================================

    def archive_company(
        self,
        company_id: str,
    ) -> Company:

        company = self.get_by_id(company_id)

        if company is None:
            raise ValueError("Company not found.")

        company.is_archived = True
        company.is_active = False
        company.status = "ARCHIVED"
        company.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(company)

        return company

    # ============================================================
    # RESTORE
    # ============================================================

    def restore_company(
        self,
        company_id: str,
    ) -> Company:

        company = self.get_by_id(company_id)

        if company is None:
            raise ValueError("Company not found.")

        company.is_archived = False
        company.is_active = True
        company.status = "ACTIVE"
        company.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(company)

        return company
        
            # ============================================================
    # LIST COMPANIES
    # ============================================================

    def get_all_companies(
        self,
        filters: CompanyFilters | None = None,
    ) -> tuple[list[Company], int]:
        """
        Returns companies with filtering, searching,
        sorting and pagination.
        """

        query = select(Company).where(
            Company.deleted_at.is_(None)
        )

        if filters:

            # ------------------------------------
            # Search
            # ------------------------------------

            if filters.search:

                keyword = f"%{filters.search.lower()}%"

                query = query.where(
                    or_(
                        func.lower(Company.name).like(keyword),
                        func.lower(Company.website).like(keyword),
                        func.lower(Company.email).like(keyword),
                        func.lower(Company.city).like(keyword),
                        func.lower(Company.country).like(keyword),
                    )
                )

            # ------------------------------------
            # Industry
            # ------------------------------------

            if filters.industry:
                query = query.where(
                    Company.industry == filters.industry
                )

            # ------------------------------------
            # Country
            # ------------------------------------

            if filters.country:
                query = query.where(
                    Company.country == filters.country
                )

            # ------------------------------------
            # Status
            # ------------------------------------

            if filters.status:
                query = query.where(
                    Company.status == filters.status
                )

            # ------------------------------------
            # Subscription
            # ------------------------------------

            if filters.subscription_plan:
                query = query.where(
                    Company.subscription_plan
                    == filters.subscription_plan
                )

            # ------------------------------------
            # Company Size
            # ------------------------------------

            if filters.company_size:
                query = query.where(
                    Company.company_size
                    == filters.company_size
                )

            # ------------------------------------
            # Active
            # ------------------------------------

            if filters.is_active is not None:
                query = query.where(
                    Company.is_active == filters.is_active
                )

        # --------------------------------------------------
        # Total Count
        # --------------------------------------------------

        total = self.db.execute(
            select(func.count()).select_from(
                query.subquery()
            )
        ).scalar_one()

        # --------------------------------------------------
        # Sorting
        # --------------------------------------------------

        if filters:

            sort_column = getattr(
                Company,
                filters.sort_by,
                Company.created_at,
            )

            if filters.sort_order.lower() == "asc":
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())

        else:

            query = query.order_by(
                Company.created_at.desc()
            )

        # --------------------------------------------------
        # Pagination
        # --------------------------------------------------

        page = filters.page if filters else 1
        page_size = filters.page_size if filters else 20

        offset = (page - 1) * page_size

        query = (
            query.offset(offset)
            .limit(page_size)
        )

        companies = self.db.execute(query).scalars().all()

        return companies, total
        
            # ============================================================
    # COMPANY COUNTS
    # ============================================================

    def total_companies(self) -> int:

        return self.db.scalar(
            select(func.count(Company.id))
            .where(Company.deleted_at.is_(None))
        ) or 0


    def active_companies(self) -> int:

        return self.db.scalar(
            select(func.count(Company.id))
            .where(
                Company.deleted_at.is_(None),
                Company.is_active.is_(True),
            )
        ) or 0


    def inactive_companies(self) -> int:

        return self.db.scalar(
            select(func.count(Company.id))
            .where(
                Company.deleted_at.is_(None),
                Company.is_active.is_(False),
            )
        ) or 0


    def archived_companies(self) -> int:

        return self.db.scalar(
            select(func.count(Company.id))
            .where(
                Company.deleted_at.is_(None),
                Company.is_archived.is_(True),
            )
        ) or 0
        
            # ============================================================
    # DASHBOARD
    # ============================================================

    def dashboard_statistics(self) -> dict:

        companies = (
            self.db.execute(
                select(Company).where(
                    Company.deleted_at.is_(None)
                )
            )
            .scalars()
            .all()
        )

        if not companies:

            return {
                "total_companies": 0,
                "active_companies": 0,
                "inactive_companies": 0,
                "trial_companies": 0,
                "total_users": 0,
                "total_clients": 0,
                "total_projects": 0,
                "total_audits": 0,
                "total_reports": 0,
                "average_seo_score": 0,
            }

        return {

            "total_companies": len(companies),

            "active_companies":
                sum(c.is_active for c in companies),

            "inactive_companies":
                sum(not c.is_active for c in companies),

            "trial_companies":
                sum(
                    c.subscription_status == "TRIAL"
                    for c in companies
                ),

            "total_users":
                sum(c.total_users for c in companies),

            "total_clients":
                sum(c.total_clients for c in companies),

            "total_projects":
                sum(c.total_projects for c in companies),

            "total_audits":
                sum(c.total_audits for c in companies),

            "total_reports":
                sum(c.total_reports for c in companies),

            "average_seo_score":
                round(
                    sum(
                        c.average_seo_score
                        for c in companies
                    ) / len(companies),
                    2,
                ),
        }
        
            # ============================================================
    # BULK OPERATIONS
    # ============================================================

    def bulk_archive(
        self,
        company_ids: list[str],
    ) -> int:
        """
        Archive multiple companies.
        """

        companies = (
            self.db.execute(
                select(Company).where(
                    Company.id.in_(company_ids),
                    Company.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        for company in companies:
            company.is_archived = True
            company.is_active = False
            company.status = "ARCHIVED"
            company.updated_at = datetime.utcnow()

        self.db.commit()

        return len(companies)

    def bulk_restore(
        self,
        company_ids: list[str],
    ) -> int:
        """
        Restore archived companies.
        """

        companies = (
            self.db.execute(
                select(Company).where(
                    Company.id.in_(company_ids),
                    Company.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        for company in companies:
            company.is_archived = False
            company.is_active = True
            company.status = "ACTIVE"
            company.updated_at = datetime.utcnow()

        self.db.commit()

        return len(companies)

    def bulk_delete(
        self,
        company_ids: list[str],
    ) -> int:
        """
        Soft delete multiple companies.
        """

        companies = (
            self.db.execute(
                select(Company).where(
                    Company.id.in_(company_ids),
                    Company.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        now = datetime.utcnow()

        for company in companies:
            company.deleted_at = now
            company.is_active = False
            company.is_archived = True

        self.db.commit()

        return len(companies)

    # ============================================================
    # EXPORT
    # ============================================================

    def export_companies(self) -> list[dict]:
        """
        Export companies.
        """

        companies = (
            self.db.execute(
                select(Company).where(
                    Company.deleted_at.is_(None)
                )
            )
            .scalars()
            .all()
        )

        return [
            company.to_dict()
            for company in companies
        ]

    # ============================================================
    # VALIDATION
    # ============================================================

    def slug_exists(
        self,
        slug: str,
    ) -> bool:

        return (
            self.db.execute(
                select(Company).where(
                    Company.slug == slug
                )
            ).scalar_one_or_none()
            is not None
        )

    def website_exists(
        self,
        website: str,
    ) -> bool:

        return (
            self.db.execute(
                select(Company).where(
                    Company.website == website
                )
            ).scalar_one_or_none()
            is not None
        )

    # ============================================================
    # HELPERS
    # ============================================================

    def commit(self):
        """
        Commit current transaction.
        """

        try:
            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

    def refresh(
        self,
        company: Company,
    ):
        """
        Refresh entity.
        """

        self.db.refresh(company)

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    def health(self) -> dict:
        """
        Service health.
        """

        return {
            "service": "CompanyService",
            "database": "connected",
            "utc": datetime.utcnow().isoformat(),
        }
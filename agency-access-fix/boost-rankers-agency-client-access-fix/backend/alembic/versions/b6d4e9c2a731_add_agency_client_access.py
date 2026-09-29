"""add explicit agency to client access relationships

Revision ID: b6d4e9c2a731
Revises: 7f1c2e9a11b4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b6d4e9c2a731"
down_revision: Union[str, Sequence[str], None] = "7f1c2e9a11b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agency_client_access",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agency_company_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("granted_by", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["agency_company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_company_id", "client_id", name="uq_agency_client_access"),
    )
    op.create_index("ix_agency_client_access_agency", "agency_client_access", ["agency_company_id"], unique=False)
    op.create_index("ix_agency_client_access_client", "agency_client_access", ["client_id"], unique=False)
    op.create_index("ix_agency_client_access_status", "agency_client_access", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agency_client_access_status", table_name="agency_client_access")
    op.drop_index("ix_agency_client_access_client", table_name="agency_client_access")
    op.drop_index("ix_agency_client_access_agency", table_name="agency_client_access")
    op.drop_table("agency_client_access")

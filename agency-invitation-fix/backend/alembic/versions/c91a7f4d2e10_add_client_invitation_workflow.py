"""add client invitation workflow

Revision ID: c91a7f4d2e10
Revises: b6d4e9c2a731
Create Date: 2026-09-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "c91a7f4d2e10"
down_revision = "b6d4e9c2a731"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_invitations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("agency_company_id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by", sa.String(length=36), nullable=True),
        sa.Column("accepted_by", sa.String(length=36), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["agency_company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_client_invitations_token_hash", "client_invitations", ["token_hash"], unique=True)
    op.create_index("ix_client_invitations_email", "client_invitations", ["email"])
    op.create_index("ix_client_invitations_client_id", "client_invitations", ["client_id"])
    op.create_index("ix_client_invitations_agency_company_id", "client_invitations", ["agency_company_id"])
    op.create_index("ix_client_invitations_status", "client_invitations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_client_invitations_status", table_name="client_invitations")
    op.drop_index("ix_client_invitations_agency_company_id", table_name="client_invitations")
    op.drop_index("ix_client_invitations_client_id", table_name="client_invitations")
    op.drop_index("ix_client_invitations_email", table_name="client_invitations")
    op.drop_index("ix_client_invitations_token_hash", table_name="client_invitations")
    op.drop_table("client_invitations")

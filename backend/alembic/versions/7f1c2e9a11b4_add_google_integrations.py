"""add google integrations

Revision ID: 7f1c2e9a11b4
Revises: 208c9f8cbb66
Create Date: 2026-08-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "7f1c2e9a11b4"
down_revision = "208c9f8cbb66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "google_integrations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=30), nullable=False, server_default="Bearer"),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("account_email", sa.String(length=320), nullable=True),
        sa.Column("selected_property", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "provider", name="uq_google_integrations_company_provider"),
    )

    op.create_index(
        "ix_google_integrations_company_id",
        "google_integrations",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_google_integrations_user_id",
        "google_integrations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_google_integrations_company_provider",
        "google_integrations",
        ["company_id", "provider"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_google_integrations_company_provider", table_name="google_integrations")
    op.drop_index("ix_google_integrations_user_id", table_name="google_integrations")
    op.drop_index("ix_google_integrations_company_id", table_name="google_integrations")
    op.drop_table("google_integrations")

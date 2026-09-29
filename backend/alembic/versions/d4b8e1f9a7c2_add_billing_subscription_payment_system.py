"""add billing settings subscriptions and payment transactions

Revision ID: d4b8e1f9a7c2
Revises: c91a7f4d2e10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4b8e1f9a7c2"
down_revision: Union[str, Sequence[str], None] = "c91a7f4d2e10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("single_workspace_price", sa.Numeric(12, 2), nullable=False, server_default="5000.00"),
        sa.Column("agency_price", sa.Numeric(12, 2), nullable=False, server_default="15000.00"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("upi_id", sa.String(255), nullable=False, server_default="mdarif921@ybl"),
        sa.Column("account_holder_name", sa.String(255), nullable=False, server_default="MD ARIF ALAM"),
        sa.Column("account_number", sa.String(50), nullable=False, server_default="50100497971201"),
        sa.Column("ifsc_code", sa.String(20), nullable=False, server_default="HDFC0000609"),
        sa.Column("micr_code", sa.String(20), nullable=True),
        sa.Column("swift_code", sa.String(20), nullable=True),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("status", sa.String(30), nullable=False, server_default="trial"),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_billing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grandfathered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_subscriptions_company_id", "subscriptions", ["company_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.String(36), sa.ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payment_method", sa.String(30), nullable=False, server_default="upi"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("transaction_reference", sa.String(255), nullable=True),
        sa.Column("bank_reference", sa.String(255), nullable=True),
        sa.Column("proof_url", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_transactions_company_id", "payment_transactions", ["company_id"])
    op.create_index("ix_payment_transactions_subscription_id", "payment_transactions", ["subscription_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])
    op.create_index("ix_payment_transactions_transaction_reference", "payment_transactions", ["transaction_reference"])

    op.execute(
        "INSERT INTO billing_settings "
        "(id, single_workspace_price, agency_price, currency, billing_cycle, trial_days, upi_id, account_holder_name, account_number, ifsc_code, micr_code, swift_code) "
        "VALUES (1, 5000.00, 15000.00, 'INR', 'monthly', 1, 'mdarif921@ybl', 'MD ARIF ALAM', '50100497971201', 'HDFC0000609', '110240098', 'HDFCINBBDEL')"
    )


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_transaction_reference", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_subscription_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_company_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_company_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("billing_settings")

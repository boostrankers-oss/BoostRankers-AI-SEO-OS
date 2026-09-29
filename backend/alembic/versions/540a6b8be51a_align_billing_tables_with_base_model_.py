"""align billing tables with base model audit fields

Revision ID: 540a6b8be51a
Revises: d4b8e1f9a7c2
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "540a6b8be51a"
down_revision: Union[str, Sequence[str], None] = "d4b8e1f9a7c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add BaseModel soft-delete and audit fields to billing tables."""

    for table_name in (
        "billing_settings",
        "subscriptions",
        "payment_transactions",
    ):
        op.add_column(
            table_name,
            sa.Column(
                "deleted_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

        op.add_column(
            table_name,
            sa.Column(
                "created_by",
                sa.String(length=36),
                nullable=True,
            ),
        )

        op.add_column(
            table_name,
            sa.Column(
                "updated_by",
                sa.String(length=36),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """Remove BaseModel soft-delete and audit fields from billing tables."""

    for table_name in (
        "payment_transactions",
        "subscriptions",
        "billing_settings",
    ):
        op.drop_column(table_name, "updated_by")
        op.drop_column(table_name, "created_by")
        op.drop_column(table_name, "deleted_at")
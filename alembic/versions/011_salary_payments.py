"""Phase 6.6: salary payments ledger

Records when a salary was actually paid to a worker AND for which
accounting period it applies. The `paid_on` date may differ from the
`period_year`/`period_month` — e.g. salary paid on 2026-05-05 covering
April 2026 work. This separation is essential for accounting correctness.

Revision ID: 011
Revises: 010
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "recorded_by_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_salary_payments_user_paid_on",
        "salary_payments",
        ["user_id", "paid_on"],
    )
    op.create_index(
        "ix_salary_payments_user_period",
        "salary_payments",
        ["user_id", "period_year", "period_month"],
    )


def downgrade() -> None:
    op.drop_index("ix_salary_payments_user_period", table_name="salary_payments")
    op.drop_index("ix_salary_payments_user_paid_on", table_name="salary_payments")
    op.drop_table("salary_payments")

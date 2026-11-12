"""Add the shared rate-limit windows table

Revision ID: 603f60b9d53b
Revises: 0001_initial
"""

import sqlalchemy as sa

from alembic import op

revision = "603f60b9d53b"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "rate_limit_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("subject_digest", sa.LargeBinary(length=32), nullable=False),
        sa.Column("resets_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_windows")),
        sa.UniqueConstraint(
            "scope", "subject_digest", name=op.f("uq_rate_limit_windows_scope")
        ),
        schema="iam",
    )
    op.create_index(
        "ix_rate_limit_windows_resets_at",
        "rate_limit_windows",
        ["resets_at"],
        unique=False,
        schema="iam",
    )


def downgrade() -> None:
    """Revert the schema change."""
    op.drop_index(
        "ix_rate_limit_windows_resets_at", table_name="rate_limit_windows", schema="iam"
    )
    op.drop_table("rate_limit_windows", schema="iam")

"""Add the security events audit table

Revision ID: 84cde24fe297
Revises: 603f60b9d53b
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "84cde24fe297"
down_revision = "603f60b9d53b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply the schema change."""
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["iam.users.id"],
            name=op.f("fk_security_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
        schema="iam",
    )
    op.create_index(
        "ix_security_events_user_created",
        "security_events",
        ["user_id", "created_at"],
        unique=False,
        schema="iam",
    )


def downgrade() -> None:
    """Revert the schema change."""
    op.drop_index(
        "ix_security_events_user_created", table_name="security_events", schema="iam"
    )
    op.drop_table("security_events", schema="iam")

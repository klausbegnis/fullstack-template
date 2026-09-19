"""Create the iam schema, users, authentication sessions and refresh tokens.

Revision ID: 0001_initial
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_USER_ROLE = postgresql.ENUM(
    "admin", "member", name="user_role", schema="iam", create_type=False
)


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    now = sa.text("CURRENT_TIMESTAMP")
    op.execute('CREATE SCHEMA IF NOT EXISTS "iam"')
    _USER_ROLE.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "users",
        sa.Column("id", uuid, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", _USER_ROLE, nullable=False, server_default="member"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=now
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email))",
            name=op.f("ck_users_email_normalized_matches_email"),
        ),
        sa.CheckConstraint(
            "password_hash LIKE '$argon2id$%'",
            name=op.f("ck_users_password_hash_argon2id"),
        ),
        sa.UniqueConstraint("email_normalized", name="uq_users_email_normalized"),
        schema="iam",
    )
    op.create_index(
        "ix_users_email_normalized",
        "users",
        ["email_normalized"],
        unique=False,
        schema="iam",
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", uuid, nullable=False),
        sa.Column("user_id", uuid, nullable=False),
        sa.Column("csrf_token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=now
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=now,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            ondelete="CASCADE",
            name="fk_auth_sessions_user_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        schema="iam",
    )
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "revoked_at", "expires_at"],
        schema="iam",
    )
    op.create_table(
        "auth_refresh_tokens",
        sa.Column("id", uuid, nullable=False),
        sa.Column("session_id", uuid, nullable=False),
        sa.Column("secret_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=now
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", uuid, nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["iam.auth_sessions.id"],
            ondelete="CASCADE",
            name="fk_auth_refresh_tokens_session_id_auth_sessions",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["iam.auth_refresh_tokens.id"],
            name="fk_auth_refresh_tokens_replaced_by_id_auth_refresh_tokens",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_refresh_tokens"),
        sa.UniqueConstraint("secret_hash", name="uq_auth_refresh_tokens_secret_hash"),
        schema="iam",
    )
    op.create_index(
        "ix_auth_refresh_tokens_session_state",
        "auth_refresh_tokens",
        ["session_id", "consumed_at", "revoked_at"],
        schema="iam",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_refresh_tokens_session_state",
        table_name="auth_refresh_tokens",
        schema="iam",
    )
    op.drop_table("auth_refresh_tokens", schema="iam")
    op.drop_index(
        "ix_auth_sessions_user_active", table_name="auth_sessions", schema="iam"
    )
    op.drop_table("auth_sessions", schema="iam")
    op.drop_index("ix_users_email_normalized", table_name="users", schema="iam")
    op.drop_table("users", schema="iam")
    _USER_ROLE.drop(op.get_bind(), checkfirst=True)
    op.execute('DROP SCHEMA IF EXISTS "iam"')

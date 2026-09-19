"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""

import sqlalchemy as sa
${imports if imports else ""}
from alembic import op

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """Apply the schema change."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Revert the schema change."""
    ${downgrades if downgrades else "pass"}

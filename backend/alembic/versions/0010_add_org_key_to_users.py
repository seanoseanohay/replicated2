"""add org_key to users

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("org_key", sa.String(32), nullable=True),
    )
    op.create_index("ix_users_org_key", "users", ["org_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_org_key", table_name="users")
    op.drop_column("users", "org_key")

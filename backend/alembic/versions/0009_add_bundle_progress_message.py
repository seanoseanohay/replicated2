"""add bundle progress_message

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bundles", sa.Column("progress_message", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("bundles", "progress_message")

"""add chat_messages table

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bundle_id"], ["bundles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_chat_messages_finding_id", "chat_messages", ["finding_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_finding_id", table_name="chat_messages")
    op.drop_table("chat_messages")

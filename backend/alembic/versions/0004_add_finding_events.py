"""add finding_events table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("actor", sa.String(256), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("old_value", sa.String(512), nullable=True),
        sa.Column("new_value", sa.String(512), nullable=True),
        sa.Column("note", sa.String(2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_finding_events_finding_id", "finding_events", ["finding_id"])
    op.create_index(
        "ix_finding_events_finding_id_created_at",
        "finding_events",
        ["finding_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_finding_events_finding_id_created_at", table_name="finding_events")
    op.drop_index("ix_finding_events_finding_id", table_name="finding_events")
    op.drop_table("finding_events")

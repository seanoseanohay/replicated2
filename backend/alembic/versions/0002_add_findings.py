"""add findings table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("bundle_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("summary", sa.String(2048), nullable=False),
        sa.Column("evidence_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(256), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("ai_remediation", sa.Text(), nullable=True),
        sa.Column("ai_explained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["bundles.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index("ix_findings_bundle_id", "findings", ["bundle_id"])
    op.create_index(
        "ix_findings_bundle_id_severity", "findings", ["bundle_id", "severity"]
    )
    op.create_index(
        "ix_findings_bundle_id_status", "findings", ["bundle_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_findings_bundle_id_status", table_name="findings")
    op.drop_index("ix_findings_bundle_id_severity", table_name="findings")
    op.drop_index("ix_findings_bundle_id", table_name="findings")
    op.drop_table("findings")

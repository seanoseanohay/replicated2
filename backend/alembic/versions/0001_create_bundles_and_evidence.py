"""create bundles and evidence tables

Revision ID: 0001
Revises:
Create Date: 2026-03-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bundles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("tenant_id", sa.String(256), nullable=False, server_default="default"),
        sa.Column("s3_key", sa.String(1024), nullable=True),
        sa.Column("error_message", sa.String(2048), nullable=True),
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
    )

    op.create_table(
        "evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("bundle_id", UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("namespace", sa.String(256), nullable=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("source_path", sa.String(1024), nullable=False, server_default=""),
        sa.Column("raw_data", JSONB(), nullable=False),
        sa.Column(
            "created_at",
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

    op.create_index("ix_evidence_bundle_id", "evidence", ["bundle_id"])
    op.create_index("ix_evidence_bundle_id_kind", "evidence", ["bundle_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_evidence_bundle_id_kind", table_name="evidence")
    op.drop_index("ix_evidence_bundle_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_table("bundles")

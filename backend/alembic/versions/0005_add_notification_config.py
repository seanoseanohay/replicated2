"""add notification_configs table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("email_recipients", sa.String(2048), nullable=True),
        sa.Column("slack_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("slack_webhook_url", sa.String(512), nullable=True),
        sa.Column(
            "notify_on_severities",
            sa.String(128),
            nullable=False,
            server_default="critical,high",
        ),
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

    op.create_index("ix_notification_configs_tenant_id", "notification_configs", ["tenant_id"])
    op.create_unique_constraint(
        "uq_notification_configs_tenant_id", "notification_configs", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_notification_configs_tenant_id", "notification_configs", type_="unique")
    op.drop_index("ix_notification_configs_tenant_id", table_name="notification_configs")
    op.drop_table("notification_configs")

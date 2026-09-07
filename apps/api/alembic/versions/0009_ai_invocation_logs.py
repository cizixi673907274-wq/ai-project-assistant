"""Add AI invocation telemetry logs

Revision ID: 0009_ai_invocation_logs
Revises: 0008_soft_delete_projects
"""
from alembic import op
import sqlalchemy as sa

revision="0009_ai_invocation_logs"
down_revision="0008_soft_delete_projects"
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    if not bind.dialect.has_table(bind, "ai_invocation_logs"):
        op.create_table(
            "ai_invocation_logs",
            sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
            sa.Column("service", sa.String(length=20), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("request_id", sa.String(length=36), nullable=True),
            sa.Column("token_usage", sa.JSON(), nullable=True),
            sa.Column("cost_estimate", sa.Float(), nullable=False, server_default="0"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("record_id", sa.String(length=36), nullable=True),
            sa.Column("media_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["record_id"], ["records.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["media_id"], ["record_media.id"], ondelete="SET NULL"),
        )


def downgrade():
    op.drop_table("ai_invocation_logs")

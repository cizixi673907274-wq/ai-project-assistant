"""durable export jobs and retention

Revision ID: 0007_durable_export_jobs
Revises: 0006_export_templates_jobs
"""
from alembic import op
import sqlalchemy as sa

revision="0007_durable_export_jobs"
down_revision="0006_export_templates_jobs"
branch_labels=None
depends_on=None


def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("export_jobs")}
    if "attempt_count" not in columns:
        op.add_column("export_jobs",sa.Column("attempt_count",sa.Integer(),server_default="0",nullable=False))
    if "expires_at" not in columns:
        op.add_column("export_jobs",sa.Column("expires_at",sa.DateTime(timezone=True),nullable=True))
        op.create_index(op.f("ix_export_jobs_expires_at"),"export_jobs",["expires_at"])


def downgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("export_jobs")}
    if "expires_at" in columns:
        op.drop_index(op.f("ix_export_jobs_expires_at"),table_name="export_jobs")
        op.drop_column("export_jobs","expires_at")
    if "attempt_count" in columns: op.drop_column("export_jobs","attempt_count")

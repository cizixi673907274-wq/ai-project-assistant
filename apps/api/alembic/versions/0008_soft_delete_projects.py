"""add project soft delete

Revision ID: 0008_soft_delete_projects
Revises: 0007_durable_export_jobs
"""
from alembic import op
import sqlalchemy as sa

revision="0008_soft_delete_projects"
down_revision="0007_durable_export_jobs"
branch_labels=None
depends_on=None


def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}
    if "deleted_at" not in columns:
        op.add_column("projects",sa.Column("deleted_at",sa.DateTime(timezone=True),nullable=True))


def downgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}
    if "deleted_at" in columns: op.drop_column("projects","deleted_at")

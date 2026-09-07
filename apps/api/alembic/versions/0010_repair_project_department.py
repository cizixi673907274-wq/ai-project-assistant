"""Repair project department column for existing local databases

Revision ID: 0010_repair_project_department
Revises: 0009_ai_invocation_logs
"""
from alembic import op
import sqlalchemy as sa

revision="0010_repair_project_department"
down_revision="0009_ai_invocation_logs"
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    columns={column["name"] for column in sa.inspect(bind).get_columns("projects")}
    if "department_id" not in columns:
        op.add_column("projects",sa.Column("department_id",sa.String(length=36),nullable=True))


def downgrade():
    bind=op.get_bind()
    columns={column["name"] for column in sa.inspect(bind).get_columns("projects")}
    if "department_id" in columns:
        op.drop_column("projects","department_id")

"""project report export history

Revision ID: 0004_project_reports
Revises: 0003_task_deadlines
"""
from alembic import op
import sqlalchemy as sa

revision="0004_project_reports"
down_revision="0003_task_deadlines"
branch_labels=None
depends_on=None

def upgrade():
    if "report_exports" in sa.inspect(op.get_bind()).get_table_names(): return
    op.create_table(
        "report_exports",
        sa.Column("user_id",sa.String(length=36),nullable=False),
        sa.Column("project_id",sa.String(length=36),nullable=False),
        sa.Column("format",sa.String(length=20),nullable=False),
        sa.Column("status",sa.String(length=20),nullable=False),
        sa.Column("filename",sa.String(length=255),nullable=False),
        sa.Column("record_count",sa.Integer(),nullable=False),
        sa.Column("filters_json",sa.JSON(),nullable=True),
        sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("id",sa.String(length=36),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(["project_id"],["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"],["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_report_exports_project_id"),"report_exports",["project_id"])
    op.create_index(op.f("ix_report_exports_status"),"report_exports",["status"])
    op.create_index(op.f("ix_report_exports_user_id"),"report_exports",["user_id"])

def downgrade():
    op.drop_table("report_exports")

"""export templates and asynchronous jobs

Revision ID: 0006_export_templates_jobs
Revises: 0005_ai_provider_observability
"""
from alembic import op
import sqlalchemy as sa

revision="0006_export_templates_jobs"
down_revision="0005_ai_provider_observability"
branch_labels=None
depends_on=None


def upgrade():
    tables=sa.inspect(op.get_bind()).get_table_names()
    if "export_templates" not in tables:
        op.create_table(
            "export_templates",
            sa.Column("name",sa.String(120),nullable=False),
            sa.Column("format",sa.String(20),nullable=False),
            sa.Column("fields_json",sa.JSON(),nullable=False),
            sa.Column("is_default",sa.Boolean(),nullable=False),
            sa.Column("is_active",sa.Boolean(),nullable=False),
            sa.Column("creator_id",sa.String(36),nullable=True),
            sa.Column("id",sa.String(36),primary_key=True),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
            sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
            sa.ForeignKeyConstraint(["creator_id"],["users.id"]),
            sa.UniqueConstraint("name"),
        )
        op.create_index(op.f("ix_export_templates_is_active"),"export_templates",["is_active"])
        op.create_index(op.f("ix_export_templates_is_default"),"export_templates",["is_default"])
    if "export_jobs" not in tables:
        op.create_table(
            "export_jobs",
            sa.Column("creator_id",sa.String(36),nullable=False),
            sa.Column("template_id",sa.String(36),nullable=False),
            sa.Column("format",sa.String(20),nullable=False),
            sa.Column("filters_json",sa.JSON(),nullable=True),
            sa.Column("status",sa.String(20),nullable=False),
            sa.Column("file_key",sa.String(500),nullable=True),
            sa.Column("filename",sa.String(255),nullable=True),
            sa.Column("record_count",sa.Integer(),nullable=False),
            sa.Column("error",sa.Text(),nullable=True),
            sa.Column("completed_at",sa.DateTime(timezone=True),nullable=True),
            sa.Column("id",sa.String(36),primary_key=True),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
            sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
            sa.ForeignKeyConstraint(["creator_id"],["users.id"]),
            sa.ForeignKeyConstraint(["template_id"],["export_templates.id"]),
        )
        op.create_index(op.f("ix_export_jobs_creator_id"),"export_jobs",["creator_id"])
        op.create_index(op.f("ix_export_jobs_status"),"export_jobs",["status"])
        op.create_index(op.f("ix_export_jobs_template_id"),"export_jobs",["template_id"])


def downgrade():
    tables=sa.inspect(op.get_bind()).get_table_names()
    if "export_jobs" in tables: op.drop_table("export_jobs")
    if "export_templates" in tables: op.drop_table("export_templates")

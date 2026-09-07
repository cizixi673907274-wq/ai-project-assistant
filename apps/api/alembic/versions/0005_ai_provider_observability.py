"""AI provider observability fields

Revision ID: 0005_ai_provider_observability
Revises: 0004_project_reports
"""
from alembic import op
import sqlalchemy as sa

revision="0005_ai_provider_observability"
down_revision="0004_project_reports"
branch_labels=None
depends_on=None


def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("ai_analyses")}
    if "token_usage" not in columns: op.add_column("ai_analyses",sa.Column("token_usage",sa.JSON(),nullable=True))
    if "cost_estimate" not in columns: op.add_column("ai_analyses",sa.Column("cost_estimate",sa.Float(),nullable=False,server_default="0"))
    if "attempt_count" not in columns: op.add_column("ai_analyses",sa.Column("attempt_count",sa.Integer(),nullable=False,server_default="1"))


def downgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("ai_analyses")}
    if "attempt_count" in columns: op.drop_column("ai_analyses","attempt_count")
    if "cost_estimate" in columns: op.drop_column("ai_analyses","cost_estimate")
    if "token_usage" in columns: op.drop_column("ai_analyses","token_usage")

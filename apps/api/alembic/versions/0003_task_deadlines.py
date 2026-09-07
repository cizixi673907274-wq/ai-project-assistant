"""task deadline reminders

Revision ID: 0003_task_deadlines
Revises: 0002_phase2_collaboration
"""
from alembic import op
import sqlalchemy as sa

revision="0003_task_deadlines"
down_revision="0002_phase2_collaboration"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("tasks")}
    with op.batch_alter_table("tasks") as batch:
        if "reminder_count" not in columns: batch.add_column(sa.Column("reminder_count",sa.Integer(),nullable=False,server_default="0"))
        if "last_reminded_at" not in columns: batch.add_column(sa.Column("last_reminded_at",sa.DateTime(timezone=True),nullable=True))

def downgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("tasks")}
    with op.batch_alter_table("tasks") as batch:
        if "last_reminded_at" in columns: batch.drop_column("last_reminded_at")
        if "reminder_count" in columns: batch.drop_column("reminder_count")

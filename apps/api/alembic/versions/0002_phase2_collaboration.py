"""phase 2 collaboration

Revision ID: 0002_phase2_collaboration
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision="0002_phase2_collaboration"
down_revision="0001"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("record_comments",
        sa.Column("record_id",sa.String(36),sa.ForeignKey("records.id",ondelete="CASCADE"),nullable=False),
        sa.Column("author_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("content",sa.Text(),nullable=False),
        sa.Column("kind",sa.String(30),nullable=False,server_default="COMMENT"),
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_record_comments_record_id","record_comments",["record_id"])
    op.create_index("ix_record_comments_author_id","record_comments",["author_id"])
    op.create_table("notifications",
        sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),
        sa.Column("type",sa.String(50),nullable=False,server_default="SYSTEM"),
        sa.Column("title",sa.String(200),nullable=False),
        sa.Column("content",sa.Text(),nullable=False),
        sa.Column("related_record_id",sa.String(36),sa.ForeignKey("records.id",ondelete="CASCADE"),nullable=True),
        sa.Column("is_read",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("read_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_notifications_user_id","notifications",["user_id"])
    op.create_index("ix_notifications_related_record_id","notifications",["related_record_id"])
    op.create_index("ix_notifications_is_read","notifications",["is_read"])

def downgrade():
    op.drop_table("notifications")
    op.drop_table("record_comments")

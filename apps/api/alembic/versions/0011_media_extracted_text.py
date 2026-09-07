"""Add OCR extracted text to record media

Revision ID: 0011_media_extracted_text
Revises: 0010_repair_project_department
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_media_extracted_text"
down_revision = "0010_repair_project_department"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("record_media")}
    if "extracted_text" not in columns:
        op.add_column("record_media", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("record_media")}
    if "extracted_text" in columns:
        op.drop_column("record_media", "extracted_text")

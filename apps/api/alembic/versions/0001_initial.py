"""initial core schema

Revision ID: 0001
"""
from alembic import op
from app.db.base import Base
from app.models import entities  # noqa
revision="0001"; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    # Keep the initial revision stable as later models are added to metadata.
    tables=[table for name,table in Base.metadata.tables.items() if name not in {"record_comments","notifications","report_exports","export_templates","export_jobs"}]
    Base.metadata.create_all(bind=op.get_bind(),tables=tables)
def downgrade(): Base.metadata.drop_all(bind=op.get_bind())

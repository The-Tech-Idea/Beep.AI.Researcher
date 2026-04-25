"""Add persisted retention action to retention_policies.

Revision ID: add_retention_action_20260410
Revises: add_project_rag_quality_mode_20260409
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "add_retention_action_20260410"
down_revision = "add_project_rag_quality_mode_20260409"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "retention_policies" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("retention_policies")}
    if "action" not in existing_columns:
        op.add_column("retention_policies", sa.Column("action", sa.String(length=20), nullable=True))
        connection.execute(sa.text("UPDATE retention_policies SET action = 'flag' WHERE action IS NULL"))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "retention_policies" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("retention_policies")}
    if "action" in existing_columns:
        op.drop_column("retention_policies", "action")

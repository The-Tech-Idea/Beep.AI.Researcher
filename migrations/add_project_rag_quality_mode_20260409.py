"""Add persisted Researcher RAG quality mode to research_projects.

Revision ID: add_project_rag_quality_mode_20260409
Revises: phase_a_enhancement_models
Create Date: 2026-04-09
"""

from alembic import op
import sqlalchemy as sa


revision = "add_project_rag_quality_mode_20260409"
down_revision = "phase_a_enhancement_models"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "research_projects" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("research_projects")}
    if "rag_quality_mode" not in existing_columns:
        op.add_column("research_projects", sa.Column("rag_quality_mode", sa.String(length=50), nullable=True))


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "research_projects" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("research_projects")}
    if "rag_quality_mode" in existing_columns:
        op.drop_column("research_projects", "rag_quality_mode")

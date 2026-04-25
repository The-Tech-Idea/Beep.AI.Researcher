"""Add manuscripts and manuscript_sections tables (Phase 04 Writing Studio).

Revision ID: add_manuscript_studio_20260412
Revises: add_retention_action_20260410
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa


revision = "add_manuscript_studio_20260412"
down_revision = "add_retention_action_20260410"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = inspector.get_table_names()

    if "manuscripts" not in existing:
        op.create_table(
            "manuscripts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "project_id",
                sa.Integer,
                sa.ForeignKey("research_projects.id"),
                nullable=False,
            ),
            sa.Column("title", sa.String(512), nullable=False),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
        op.create_index(
            "ix_manuscripts_project_id", "manuscripts", ["project_id"]
        )

    if "manuscript_sections" not in existing:
        op.create_table(
            "manuscript_sections",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "manuscript_id",
                sa.Integer,
                sa.ForeignKey("manuscripts.id"),
                nullable=False,
            ),
            sa.Column(
                "parent_id",
                sa.Integer,
                sa.ForeignKey("manuscript_sections.id"),
                nullable=True,
            ),
            sa.Column("sort_order", sa.Integer, nullable=False, default=0),
            sa.Column("title", sa.String(512), nullable=False, default="Untitled Section"),
            sa.Column("content", sa.Text, nullable=True),
            sa.Column("status", sa.String(20), nullable=False, default="draft"),
            sa.Column("synopsis", sa.Text, nullable=True),
            sa.Column("linked_reference_ids_json", sa.Text, nullable=True, default="[]"),
        )
        op.create_index(
            "ix_manuscript_sections_manuscript_id",
            "manuscript_sections",
            ["manuscript_id"],
        )
        op.create_index(
            "ix_manuscript_sections_parent_id",
            "manuscript_sections",
            ["parent_id"],
        )


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing = inspector.get_table_names()
    if "manuscript_sections" in existing:
        op.drop_index("ix_manuscript_sections_parent_id", table_name="manuscript_sections")
        op.drop_index("ix_manuscript_sections_manuscript_id", table_name="manuscript_sections")
        op.drop_table("manuscript_sections")
    if "manuscripts" in existing:
        op.drop_index("ix_manuscripts_project_id", table_name="manuscripts")
        op.drop_table("manuscripts")

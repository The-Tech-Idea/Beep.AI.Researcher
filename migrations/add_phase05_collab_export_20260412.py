"""Phase 05 collaboration & export schema changes.

Revision ID: add_phase05_collab_export_20260412
Revises: add_manuscript_studio_20260412
Create Date: 2026-04-12

Changes:
- project_comments: add manuscript_section_id (nullable FK), resolved_at (nullable DateTime)
- research_projects: add submission_checklist_json (nullable Text)
- export_jobs: new table
"""

from alembic import op
import sqlalchemy as sa


revision = "add_phase05_collab_export_20260412"
down_revision = "add_manuscript_studio_20260412"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # --- project_comments: new columns ----------------------------------------
    if "project_comments" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("project_comments")}
        if "manuscript_section_id" not in existing_cols:
            op.add_column(
                "project_comments",
                sa.Column(
                    "manuscript_section_id",
                    sa.Integer,
                    sa.ForeignKey("manuscript_sections.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            op.create_index(
                "ix_project_comments_manuscript_section_id",
                "project_comments",
                ["manuscript_section_id"],
            )
        if "resolved_at" not in existing_cols:
            op.add_column(
                "project_comments",
                sa.Column("resolved_at", sa.DateTime, nullable=True),
            )

    # --- research_projects: submission checklist column -----------------------
    if "research_projects" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("research_projects")}
        if "submission_checklist_json" not in existing_cols:
            op.add_column(
                "research_projects",
                sa.Column("submission_checklist_json", sa.Text, nullable=True),
            )

    # --- export_jobs: new table -----------------------------------------------
    if "export_jobs" not in existing_tables:
        op.create_table(
            "export_jobs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "project_id",
                sa.Integer,
                sa.ForeignKey("research_projects.id"),
                nullable=False,
            ),
            sa.Column(
                "manuscript_id",
                sa.Integer,
                sa.ForeignKey("manuscripts.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("format", sa.String(30), nullable=False, default="markdown_zip"),
            sa.Column("status", sa.String(20), nullable=False, default="pending"),
            sa.Column("artifact_path", sa.Text, nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )
        op.create_index("ix_export_jobs_project_id", "export_jobs", ["project_id"])


def downgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    if "export_jobs" in existing_tables:
        op.drop_index("ix_export_jobs_project_id", table_name="export_jobs")
        op.drop_table("export_jobs")

    if "project_comments" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("project_comments")}
        if "manuscript_section_id" in existing_cols:
            op.drop_index(
                "ix_project_comments_manuscript_section_id",
                table_name="project_comments",
            )
            op.drop_column("project_comments", "manuscript_section_id")
        if "resolved_at" in existing_cols:
            op.drop_column("project_comments", "resolved_at")

    if "research_projects" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("research_projects")}
        if "submission_checklist_json" in existing_cols:
            op.drop_column("research_projects", "submission_checklist_json")

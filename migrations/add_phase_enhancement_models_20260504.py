"""Add Phase 2-6 enhancement models.

Revision ID: 20260504_phase_enhancements
Revises: phase_a_enhancement_models
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260504_phase_enhancements"
down_revision = "phase_a_enhancement_models"
branch_labels = None
depends_on = None


def upgrade():
    # Phase 2 — Evidence Synthesis
    op.create_table(
        "synthesis_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=True),
        sa.Column("supporting_count", sa.Integer(), nullable=True),
        sa.Column("contradicting_count", sa.Integer(), nullable=True),
        sa.Column("mentioning_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("llm_model_used", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["research_projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_synthesis_reports_project_id"),
        "synthesis_reports",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_synthesis_reports_status"),
        "synthesis_reports",
        ["status"],
        unique=False,
    )

    op.create_table(
        "retraction_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("doi", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("retraction_date", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_retraction_records_doi"), "retraction_records", ["doi"], unique=True
    )

    # Phase 3 — Knowledge Map
    op.create_table(
        "knowledge_graph_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("nodes_json", sa.JSON(), nullable=True),
        sa.Column("edges_json", sa.JSON(), nullable=True),
        sa.Column("clusters_json", sa.JSON(), nullable=True),
        sa.Column("built_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_graph_cache_user_id"),
        "knowledge_graph_cache",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_graph_cache_project_id"),
        "knowledge_graph_cache",
        ["project_id"],
        unique=False,
    )

    # Phase 4 — Writing Assistant
    op.create_table(
        "auto_extraction_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("document_hash", sa.String(length=64), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("findings_json", sa.JSON(), nullable=True),
        sa.Column("tables_json", sa.JSON(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )

    # Phase 6 — Citation Intelligence
    op.create_table(
        "citation_context_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("citing_doi", sa.String(length=255), nullable=False),
        sa.Column("cited_doi", sa.String(length=255), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("polarity", sa.String(length=20), nullable=True),
        sa.Column("polarity_score", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("citing_doi", "cited_doi", name="uq_citation_context"),
    )
    op.create_index(
        op.f("ix_citation_context_records_citing_doi"),
        "citation_context_records",
        ["citing_doi"],
        unique=False,
    )
    op.create_index(
        op.f("ix_citation_context_records_cited_doi"),
        "citation_context_records",
        ["cited_doi"],
        unique=False,
    )

    op.create_table(
        "duplicate_merge_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kept_id", sa.Integer(), nullable=False),
        sa.Column("removed_id", sa.Integer(), nullable=False),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.Column("merged_by", sa.Integer(), nullable=True),
        sa.Column("revert_payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["merged_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("duplicate_merge_logs")
    op.drop_index(
        op.f("ix_citation_context_records_cited_doi"),
        table_name="citation_context_records",
    )
    op.drop_index(
        op.f("ix_citation_context_records_citing_doi"),
        table_name="citation_context_records",
    )
    op.drop_table("citation_context_records")
    op.drop_table("auto_extraction_cache")
    op.drop_index(
        op.f("ix_knowledge_graph_cache_project_id"), table_name="knowledge_graph_cache"
    )
    op.drop_index(
        op.f("ix_knowledge_graph_cache_user_id"), table_name="knowledge_graph_cache"
    )
    op.drop_table("knowledge_graph_cache")
    op.drop_index(op.f("ix_retraction_records_doi"), table_name="retraction_records")
    op.drop_table("retraction_records")
    op.drop_index(op.f("ix_synthesis_reports_status"), table_name="synthesis_reports")
    op.drop_index(
        op.f("ix_synthesis_reports_project_id"), table_name="synthesis_reports"
    )
    op.drop_table("synthesis_reports")

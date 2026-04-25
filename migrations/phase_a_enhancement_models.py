"""Phase A enhancement models: ResearchBrief, EvidenceItem, Claim/ClaimEvidence,
ReviewStep (PRISMA), and SourceProvenance.

Revision ID: phase_a_enhancement_models
Revises: phase_41_references
Create Date: 2026-06-01

Adds five new tables that support:
- Sector-aware research briefs (law, medical, real-estate, education, government)
- Systematic review evidence tracking with GRADE-style strength ratings
- Argument/claim mapping with supporting and contrasting evidence links
- PRISMA-compliant review audit log
- Document lineage and provenance chain

No existing tables are modified; all additions are additive.
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase_a_enhancement_models'
down_revision = 'phase_41_references'
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # research_briefs
    # Purpose: store a structured summary / briefing document for a project,
    #          tagged with the target sector and optional compliance context.
    # ------------------------------------------------------------------
    op.create_table(
        'research_briefs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('research_projects.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('created_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        # Sector tag: law | medical | real_estate | education | government | general
        sa.Column('sector', sa.String(50), nullable=False, server_default='general'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('summary_text', sa.Text()),
        # JSON array of compliance framework IDs (e.g. ["HIPAA","GDPR"])
        sa.Column('compliance_frameworks', sa.JSON()),
        # JSON dict of key findings keyed by section
        sa.Column('key_findings', sa.JSON()),
        sa.Column('status', sa.String(30), server_default='draft'),   # draft|review|final
        sa.Column('llm_model_used', sa.String(100)),
        sa.Column('generation_metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_research_briefs_project', 'research_briefs', ['project_id'])
    op.create_index('ix_research_briefs_sector',  'research_briefs', ['sector'])

    # ------------------------------------------------------------------
    # evidence_items
    # Purpose: individual pieces of evidence extracted during systematic review,
    #          linked to a source document and graded for strength.
    # ------------------------------------------------------------------
    op.create_table(
        'evidence_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('research_projects.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('document_id', sa.Integer(),
                  sa.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
                  nullable=True),
        # Short claim text (≤500 chars for indexed look-up)
        sa.Column('claim_text', sa.String(500), nullable=False),
        sa.Column('verbatim_quote', sa.Text()),
        # GRADE-style strength: high | moderate | low | very_low
        sa.Column('strength', sa.String(20), server_default='low'),
        # Direction: supports | refutes | neutral
        sa.Column('direction', sa.String(20), server_default='neutral'),
        sa.Column('evidence_type', sa.String(50)),   # RCT | case_study | expert_opinion …
        # Page / section reference inside source doc
        sa.Column('source_location', sa.String(100)),
        sa.Column('extraction_method', sa.String(30), server_default='manual'),  # manual|llm
        sa.Column('confidence_score', sa.Float()),
        sa.Column('tags', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_evidence_items_project',  'evidence_items', ['project_id'])
    op.create_index('ix_evidence_items_document', 'evidence_items', ['document_id'])
    op.create_index('ix_evidence_items_strength', 'evidence_items', ['strength'])

    # ------------------------------------------------------------------
    # claims
    # Purpose: high-level argumentative claims that aggregate evidence items.
    #          Supports argument-mapping workflows.
    # ------------------------------------------------------------------
    op.create_table(
        'claims',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('research_projects.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        # Taxonomy: factual | normative | predictive | policy
        sa.Column('claim_type', sa.String(50), server_default='factual'),
        sa.Column('sector', sa.String(50)),
        # Overall verdict after weighing evidence: supported | contested | refuted | unclear
        sa.Column('verdict', sa.String(30), server_default='unclear'),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('source_brief_id', sa.Integer(),
                  sa.ForeignKey('research_briefs.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_claims_project', 'claims', ['project_id'])
    op.create_index('ix_claims_verdict', 'claims', ['verdict'])

    # ------------------------------------------------------------------
    # claim_evidence  (join table: many claims ↔ many evidence_items)
    # ------------------------------------------------------------------
    op.create_table(
        'claim_evidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_id', sa.Integer(),
                  sa.ForeignKey('claims.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('evidence_id', sa.Integer(),
                  sa.ForeignKey('evidence_items.id', ondelete='CASCADE'),
                  nullable=False),
        # Role of this evidence for the claim
        sa.Column('role', sa.String(20), server_default='supporting'),  # supporting|refuting|neutral
        sa.Column('added_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('claim_id', 'evidence_id', name='uq_claim_evidence'),
    )
    op.create_index('ix_claim_evidence_claim',    'claim_evidence', ['claim_id'])
    op.create_index('ix_claim_evidence_evidence', 'claim_evidence', ['evidence_id'])

    # ------------------------------------------------------------------
    # review_steps
    # Purpose: PRISMA-compliant audit log for systematic review screening.
    #          Each row records one decision on one document at one review stage.
    # ------------------------------------------------------------------
    op.create_table(
        'review_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('research_projects.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('document_id', sa.Integer(),
                  sa.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
                  nullable=True),
        # PRISMA stages: identification | screening | eligibility | included | excluded
        sa.Column('stage', sa.String(30), nullable=False),
        # Decision: pass | exclude | uncertain
        sa.Column('decision', sa.String(20), nullable=False, server_default='uncertain'),
        # Reason code (e.g. "irrelevant_population", "duplicate", "low_quality")
        sa.Column('exclusion_reason', sa.String(100)),
        sa.Column('notes', sa.Text()),
        sa.Column('performed_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        # Flag for records that were auto-decided by LLM
        sa.Column('is_automated', sa.Boolean(), server_default='0'),
        sa.Column('automation_confidence', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_review_steps_project',  'review_steps', ['project_id'])
    op.create_index('ix_review_steps_stage',    'review_steps', ['stage'])
    op.create_index('ix_review_steps_decision', 'review_steps', ['decision'])
    op.create_index('ix_review_steps_document', 'review_steps', ['document_id'])

    # ------------------------------------------------------------------
    # source_provenance
    # Purpose: tracks the full import/transformation lineage of each document.
    #          Supports audit trails for compliance-heavy sectors.
    # ------------------------------------------------------------------
    op.create_table(
        'source_provenance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(),
                  sa.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('research_projects.id', ondelete='CASCADE'),
                  nullable=False),
        # Event type: imported | transformed | chunked | extracted | redacted | exported
        sa.Column('event_type', sa.String(50), nullable=False),
        # Free-form JSON describing what happened (tool, params, etc.)
        sa.Column('event_detail', sa.JSON()),
        # SHA-256 hash of content at this stage (for integrity verification)
        sa.Column('content_hash', sa.String(64)),
        sa.Column('parent_document_id', sa.Integer(),
                  sa.ForeignKey('researcher_documents.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('performed_by', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('tool_name', sa.String(100)),
        sa.Column('tool_version', sa.String(30)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_source_provenance_document',   'source_provenance', ['document_id'])
    op.create_index('ix_source_provenance_project',    'source_provenance', ['project_id'])
    op.create_index('ix_source_provenance_event_type', 'source_provenance', ['event_type'])


def downgrade():
    # Drop in reverse dependency order
    op.drop_index('ix_source_provenance_event_type', 'source_provenance')
    op.drop_index('ix_source_provenance_project',    'source_provenance')
    op.drop_index('ix_source_provenance_document',   'source_provenance')
    op.drop_table('source_provenance')

    op.drop_index('ix_review_steps_document', 'review_steps')
    op.drop_index('ix_review_steps_decision', 'review_steps')
    op.drop_index('ix_review_steps_stage',    'review_steps')
    op.drop_index('ix_review_steps_project',  'review_steps')
    op.drop_table('review_steps')

    op.drop_index('ix_claim_evidence_evidence', 'claim_evidence')
    op.drop_index('ix_claim_evidence_claim',    'claim_evidence')
    op.drop_table('claim_evidence')

    op.drop_index('ix_claims_verdict',  'claims')
    op.drop_index('ix_claims_project',  'claims')
    op.drop_table('claims')

    op.drop_index('ix_evidence_items_strength', 'evidence_items')
    op.drop_index('ix_evidence_items_document', 'evidence_items')
    op.drop_index('ix_evidence_items_project',  'evidence_items')
    op.drop_table('evidence_items')

    op.drop_index('ix_research_briefs_sector',  'research_briefs')
    op.drop_index('ix_research_briefs_project', 'research_briefs')
    op.drop_table('research_briefs')

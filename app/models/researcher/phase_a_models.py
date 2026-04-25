"""Phase A enhancement models.

Provides:
- ResearchBrief       — sector-aware project briefs
- EvidenceItem        — GRADE-style evidence records for systematic review
- Claim               — high-level argumentative claims
- ClaimEvidence       — many-to-many join: claims ↔ evidence_items
- ReviewStep          — PRISMA audit log entries
- SourceProvenance    — document lineage / transformation chain
"""
from app.core.time_utils import utcnow_naive
from app.database import db


class ResearchBrief(db.Model):
    """Sector-tagged structured brief generated from or linked to a project."""
    __tablename__ = 'research_briefs'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))

    # Sector: law | medical | real_estate | education | government | general
    sector = db.Column(db.String(50), nullable=False, default='general', index=True)
    title = db.Column(db.String(255), nullable=False)
    summary_text = db.Column(db.Text)

    # JSON list of framework IDs e.g. ["HIPAA", "GDPR"]
    compliance_frameworks = db.Column(db.JSON)

    # JSON dict keyed by section name
    key_findings = db.Column(db.JSON)

    # draft | review | final
    status = db.Column(db.String(30), default='draft')
    llm_model_used = db.Column(db.String(100))
    generation_metadata = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    # ── relationships ─────────────────────────────────────────────────
    project = db.relationship('ResearchProject', backref='briefs')
    claims = db.relationship('Claim', backref='brief', foreign_keys='Claim.source_brief_id')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'sector': self.sector,
            'title': self.title,
            'summary_text': self.summary_text,
            'compliance_frameworks': self.compliance_frameworks or [],
            'key_findings': self.key_findings or {},
            'status': self.status,
            'llm_model_used': self.llm_model_used,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class EvidenceItem(db.Model):
    """A single piece of evidence extracted from a source document."""
    __tablename__ = 'evidence_items'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    document_id = db.Column(
        db.Integer, db.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
        index=True,
    )

    claim_text = db.Column(db.String(500), nullable=False)
    verbatim_quote = db.Column(db.Text)

    # GRADE-style: high | moderate | low | very_low
    strength = db.Column(db.String(20), default='low', index=True)

    # supports | refutes | neutral
    direction = db.Column(db.String(20), default='neutral')

    # RCT | case_study | expert_opinion | systematic_review | observational | legislative | other
    evidence_type = db.Column(db.String(50))

    # Page / section reference inside the source document
    source_location = db.Column(db.String(100))

    # manual | llm
    extraction_method = db.Column(db.String(30), default='manual')
    confidence_score = db.Column(db.Float)
    tags = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=utcnow_naive)

    # ── relationships ─────────────────────────────────────────────────
    project = db.relationship('ResearchProject', backref='evidence_items')
    document = db.relationship('ResearcherDocument', backref='evidence_items')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'document_id': self.document_id,
            'claim_text': self.claim_text,
            'verbatim_quote': self.verbatim_quote,
            'strength': self.strength,
            'direction': self.direction,
            'evidence_type': self.evidence_type,
            'source_location': self.source_location,
            'extraction_method': self.extraction_method,
            'confidence_score': self.confidence_score,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Claim(db.Model):
    """A high-level argumentative claim supported or refuted by EvidenceItems."""
    __tablename__ = 'claims'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    claim_text = db.Column(db.Text, nullable=False)

    # factual | normative | predictive | policy
    claim_type = db.Column(db.String(50), default='factual')
    sector = db.Column(db.String(50))

    # supported | contested | refuted | unclear
    verdict = db.Column(db.String(30), default='unclear', index=True)
    confidence_score = db.Column(db.Float)

    source_brief_id = db.Column(
        db.Integer, db.ForeignKey('research_briefs.id', ondelete='SET NULL'),
    )
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    # ── relationships ─────────────────────────────────────────────────
    project = db.relationship('ResearchProject', backref='claims')
    claim_evidence = db.relationship('ClaimEvidence', backref='claim',
                                     cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'claim_text': self.claim_text,
            'claim_type': self.claim_type,
            'sector': self.sector,
            'verdict': self.verdict,
            'confidence_score': self.confidence_score,
            'source_brief_id': self.source_brief_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ClaimEvidence(db.Model):
    """Join table: many Claim ↔ many EvidenceItem, with a role annotation."""
    __tablename__ = 'claim_evidence'
    __table_args__ = (
        db.UniqueConstraint('claim_id', 'evidence_id', name='uq_claim_evidence'),
    )

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(
        db.Integer, db.ForeignKey('claims.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    evidence_id = db.Column(
        db.Integer, db.ForeignKey('evidence_items.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    # supporting | refuting | neutral
    role = db.Column(db.String(20), default='supporting')
    added_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    added_at = db.Column(db.DateTime, default=utcnow_naive)

    evidence = db.relationship('EvidenceItem', backref='claim_links')

    def to_dict(self):
        return {
            'id': self.id,
            'claim_id': self.claim_id,
            'evidence_id': self.evidence_id,
            'role': self.role,
            'added_at': self.added_at.isoformat() if self.added_at else None,
        }


class ReviewStep(db.Model):
    """PRISMA audit log: one decision per document at one review stage."""
    __tablename__ = 'review_steps'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    document_id = db.Column(
        db.Integer, db.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
        index=True,
    )

    # identification | screening | eligibility | included | excluded
    stage = db.Column(db.String(30), nullable=False, index=True)

    # pass | exclude | uncertain
    decision = db.Column(db.String(20), nullable=False, default='uncertain', index=True)

    # short code for why excluded e.g. "irrelevant_population", "duplicate"
    exclusion_reason = db.Column(db.String(100))
    notes = db.Column(db.Text)

    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    is_automated = db.Column(db.Boolean, default=False)
    automation_confidence = db.Column(db.Float)

    created_at = db.Column(db.DateTime, default=utcnow_naive)

    # ── relationships ─────────────────────────────────────────────────
    project = db.relationship('ResearchProject', backref='review_steps')
    document = db.relationship('ResearcherDocument', backref='review_steps')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'document_id': self.document_id,
            'stage': self.stage,
            'decision': self.decision,
            'exclusion_reason': self.exclusion_reason,
            'notes': self.notes,
            'is_automated': self.is_automated,
            'automation_confidence': self.automation_confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class SourceProvenance(db.Model):
    """Lineage record for a document: tracks every import, transform, redaction, etc."""
    __tablename__ = 'source_provenance'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    # imported | transformed | chunked | extracted | redacted | exported
    event_type = db.Column(db.String(50), nullable=False, index=True)

    # Free-form dict: tool params, source URL, pipeline stage, etc.
    event_detail = db.Column(db.JSON)

    # SHA-256 of content at this stage for integrity checks
    content_hash = db.Column(db.String(64))

    # If derived from another document (e.g. redacted copy of original)
    parent_document_id = db.Column(
        db.Integer, db.ForeignKey('researcher_documents.id', ondelete='SET NULL'),
    )

    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    tool_name = db.Column(db.String(100))
    tool_version = db.Column(db.String(30))

    created_at = db.Column(db.DateTime, default=utcnow_naive)

    # ── relationships ─────────────────────────────────────────────────
    document = db.relationship('ResearcherDocument', foreign_keys=[document_id],
                               backref='provenance_records')
    parent_document = db.relationship('ResearcherDocument', foreign_keys=[parent_document_id])

    def to_dict(self):
        return {
            'id': self.id,
            'document_id': self.document_id,
            'project_id': self.project_id,
            'event_type': self.event_type,
            'event_detail': self.event_detail or {},
            'content_hash': self.content_hash,
            'parent_document_id': self.parent_document_id,
            'tool_name': self.tool_name,
            'tool_version': self.tool_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

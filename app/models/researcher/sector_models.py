"""Phase C.3 — Sector-specific DB models.

Models:
  Hypothesis          — Education: tracks research hypotheses
  HypothesisEvidence  — Join table: Hypothesis ↔ EvidenceItem
  PlagiarismCheck     — Education: similarity check results
  EvidenceGrade       — Medical: evidence quality grading (GRADE/Oxford)
  ClauseTemplate      — Legal: reusable contract clause library
  CitationValidation  — Legal: validated legal citation records
"""
from datetime import datetime
from app.database import db


# ─────────────────────────────────────────────────────────────
#  Education — Hypothesis & Literature Support
# ─────────────────────────────────────────────────────────────

class Hypothesis(db.Model):
    """A research hypothesis within a project (Education sector)."""
    __tablename__ = 'hypotheses'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    statement = db.Column(db.Text, nullable=False)

    # null_hypothesis | alternative | research
    hypothesis_type = db.Column(db.String(50), default='research')

    # draft | active | supported | rejected | inconclusive
    status = db.Column(db.String(30), default='draft', index=True)

    # qualitative | quantitative | mixed | systematic_review
    methodology = db.Column(db.String(50))

    # Number of literature sources that support this hypothesis
    literature_support_count = db.Column(db.Integer, default=0)

    sector = db.Column(db.String(50), default='education')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship('ResearchProject', backref='hypotheses')
    evidence_links = db.relationship(
        'HypothesisEvidence', backref='hypothesis', cascade='all, delete-orphan'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'statement': self.statement,
            'hypothesis_type': self.hypothesis_type,
            'status': self.status,
            'methodology': self.methodology,
            'literature_support_count': self.literature_support_count,
            'sector': self.sector,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class HypothesisEvidence(db.Model):
    """Join table: Hypothesis ↔ EvidenceItem."""
    __tablename__ = 'hypothesis_evidence'
    __table_args__ = (
        db.UniqueConstraint('hypothesis_id', 'evidence_id', name='uq_hyp_evidence'),
    )

    id = db.Column(db.Integer, primary_key=True)
    hypothesis_id = db.Column(
        db.Integer, db.ForeignKey('hypotheses.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    evidence_id = db.Column(
        db.Integer, db.ForeignKey('evidence_items.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    # supports | refutes | neutral
    role = db.Column(db.String(20), default='supports')
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    evidence = db.relationship('EvidenceItem', backref='hypothesis_links')

    def to_dict(self):
        return {
            'id': self.id,
            'hypothesis_id': self.hypothesis_id,
            'evidence_id': self.evidence_id,
            'role': self.role,
            'added_at': self.added_at.isoformat() if self.added_at else None,
        }


class PlagiarismCheck(db.Model):
    """Plagiarism-similarity check result for a document."""
    __tablename__ = 'plagiarism_checks'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    document_id = db.Column(
        db.Integer, db.ForeignKey('researcher_documents.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    # Which service was used (internal_rag | crossref | turnitin | etc.)
    service = db.Column(db.String(50), default='internal_rag')

    # Overall similarity percentage (0-100)
    similarity_score = db.Column(db.Float)

    # [{"text": "...", "source": "...", "similarity": 0.85}, ...]
    flagged_passages_json = db.Column(db.JSON)

    status = db.Column(db.String(20), default='pending')  # pending | completed | error

    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    project = db.relationship('ResearchProject', backref='plagiarism_checks')
    document = db.relationship('ResearcherDocument', backref='plagiarism_checks')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'document_id': self.document_id,
            'service': self.service,
            'similarity_score': self.similarity_score,
            'flagged_passages': self.flagged_passages_json or [],
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


# ─────────────────────────────────────────────────────────────
#  Medical — Evidence Grading (GRADE / Oxford)
# ─────────────────────────────────────────────────────────────

class EvidenceGrade(db.Model):
    """Quality-of-evidence grading for a single EvidenceItem."""
    __tablename__ = 'evidence_grades'

    id = db.Column(db.Integer, primary_key=True)
    evidence_item_id = db.Column(
        db.Integer, db.ForeignKey('evidence_items.id', ondelete='CASCADE'),
        nullable=False, unique=True, index=True,
    )

    # A | B | C | D  (Oxford) or  HIGH | MODERATE | LOW | VERY_LOW (GRADE)
    grade = db.Column(db.String(20), nullable=False)
    # System used: oxford | grade | custom
    grading_system = db.Column(db.String(30), default='oxford')
    grade_reason = db.Column(db.Text)

    graded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    graded_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evidence_item = db.relationship('EvidenceItem', backref=db.backref('grade', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'evidence_item_id': self.evidence_item_id,
            'grade': self.grade,
            'grading_system': self.grading_system,
            'grade_reason': self.grade_reason,
            'graded_by': self.graded_by,
            'graded_at': self.graded_at.isoformat() if self.graded_at else None,
        }


# ─────────────────────────────────────────────────────────────
#  Legal — Clause Library & Citation Validation
# ─────────────────────────────────────────────────────────────

class ClauseTemplate(db.Model):
    """Reusable contract clause template (Legal sector)."""
    __tablename__ = 'clause_templates'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=True, index=True,    # None = global/shared template
    )

    name = db.Column(db.String(255), nullable=False)

    # indemnification | limitation_of_liability | arbitration | confidentiality |
    # ip_assignment | force_majeure | governing_law | termination | warranty | etc.
    clause_type = db.Column(db.String(100), index=True)

    # US-CA | US-NY | UK | EU | etc.
    jurisdiction = db.Column(db.String(50))

    # high | medium | low
    risk_level = db.Column(db.String(20), default='medium')

    reference_text = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text)

    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = db.relationship('ResearchProject', backref='clause_templates')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'clause_type': self.clause_type,
            'jurisdiction': self.jurisdiction,
            'risk_level': self.risk_level,
            'reference_text': self.reference_text,
            'notes': self.notes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CitationValidation(db.Model):
    """Validated legal citation record."""
    __tablename__ = 'citation_validations'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    citation_text = db.Column(db.Text, nullable=False)

    # cfr | usc | case_law | statute | regulation | unknown
    citation_type = db.Column(db.String(50))

    is_valid = db.Column(db.Boolean)
    normalized_form = db.Column(db.Text)
    validation_errors_json = db.Column(db.JSON)

    # Which validator performed the check
    validator = db.Column(db.String(50), default='regex')

    validated_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    validated_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('ResearchProject', backref='citation_validations')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'citation_text': self.citation_text,
            'citation_type': self.citation_type,
            'is_valid': self.is_valid,
            'normalized_form': self.normalized_form,
            'validation_errors': self.validation_errors_json or [],
            'validator': self.validator,
            'validated_at': self.validated_at.isoformat() if self.validated_at else None,
        }

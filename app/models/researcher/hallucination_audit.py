"""HallucinationAuditLog model for tracking anti-hallucination compliance."""
from app.database import db
from app.core.time_utils import utcnow_naive

class HallucinationAuditLog(db.Model):
    """
    Phase 4: Tracks and persists hallucination detection events.
    Records per-step RAG grounding scores, detected contradictions, and overall flag status.
    """
    __tablename__ = 'hallucination_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False, index=True)
    session_id = db.Column(db.String(36), nullable=True, index=True)
    step_name = db.Column(db.String(100), nullable=False)
    prompt_hash = db.Column(db.String(64), nullable=True)
    answer_text = db.Column(db.Text, nullable=False)
    grounding_score = db.Column(db.Float, nullable=True)
    ungrounded_sentences = db.Column(db.JSON, nullable=True)
    contradictions_found = db.Column(db.JSON, nullable=True)
    rag_chunk_ids = db.Column(db.JSON, nullable=True)
    temperature_used = db.Column(db.Float, nullable=True)
    flagged = db.Column(db.Boolean, default=False, nullable=False, index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)

    # Relationships
    project = db.relationship('ResearchProject', backref='hallucination_logs')
    reviewer = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'session_id': self.session_id,
            'step_name': self.step_name,
            'prompt_hash': self.prompt_hash,
            'answer_text': self.answer_text,
            'grounding_score': self.grounding_score,
            'ungrounded_sentences': self.ungrounded_sentences,
            'contradictions_found': self.contradictions_found,
            'rag_chunk_ids': self.rag_chunk_ids,
            'temperature_used': self.temperature_used,
            'flagged': self.flagged,
            'reviewed_by': self.reviewed_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

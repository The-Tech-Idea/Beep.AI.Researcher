"""Code, CodedReference, DocumentAnnotation models."""
from app.core.time_utils import utcnow_naive
from app.database import db


class Code(db.Model):
    __tablename__ = 'researcher_codes'
    __table_args__ = (db.UniqueConstraint('project_id', 'name', name='uq_code_project_name'),)
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('researcher_codes.id'))
    color = db.Column(db.String(7), default='#6366f1')
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='codes')
    parent = db.relationship('Code', remote_side=[id], backref='children')


class CodedReference(db.Model):
    __tablename__ = 'coded_references'
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.Integer, db.ForeignKey('researcher_codes.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'), nullable=False)
    chunk_id = db.Column(db.String(100), nullable=False)
    start_offset = db.Column(db.Integer, nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)
    memo = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    code = db.relationship('Code', backref='references')
    document = db.relationship('ResearcherDocument', backref='coded_references')
    created_by = db.relationship('User', backref='coded_references')


class DocumentAnnotation(db.Model):
    __tablename__ = 'document_annotations'
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'), nullable=False)
    chunk_id = db.Column(db.String(100), nullable=False)
    start_offset = db.Column(db.Integer, nullable=False)
    end_offset = db.Column(db.Integer, nullable=False)
    note = db.Column(db.Text)
    highlight_color = db.Column(db.String(7), default='#fef08a')
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    document = db.relationship('ResearcherDocument', backref='document_annotations')
    created_by = db.relationship('User', backref='document_annotations')

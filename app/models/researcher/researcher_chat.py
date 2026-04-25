"""ChatSession, ChatMessage models."""
from app.core.time_utils import utcnow_naive
from app.database import db


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='chat_sessions')
    messages = db.relationship('ChatMessage', backref='session', cascade='all, delete-orphan')


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    citations_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

"""Task notification model for ResearchTask events."""
from datetime import datetime
from app.core.time_utils import utcnow_naive

from app.database import db


class TaskNotification(db.Model):
    __tablename__ = 'task_notifications'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('research_tasks.id'), nullable=False)
    event = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(32), default='system')
    created_by_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    delivered_at = db.Column(db.DateTime)

    task = db.relationship('ResearchTask', backref='notifications')

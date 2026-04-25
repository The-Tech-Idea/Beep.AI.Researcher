"""ResearchTask model for project planning and context-linked work."""

from app.database import db
from app.core.time_utils import utcnow_naive


class ResearchTask(db.Model):
    __tablename__ = 'research_tasks'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='todo')
    priority = db.Column(db.String(30), default='normal')
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'))
    code_id = db.Column(db.Integer, db.ForeignKey('researcher_codes.id'))
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    project = db.relationship('ResearchProject', backref='tasks')
    document = db.relationship('ResearcherDocument', backref='tasks')
    code = db.relationship('Code', backref='tasks')

    def __init__(self, **kwargs):
        # Compatibility with legacy/task integration tests that use `name`.
        if 'name' in kwargs and 'title' not in kwargs:
            kwargs['title'] = kwargs.pop('name')
        super().__init__(**kwargs)

    @property
    def name(self):
        return self.title

    @name.setter
    def name(self, value):
        self.title = value

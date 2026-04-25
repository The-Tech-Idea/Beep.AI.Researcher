"""ResearchProject, ProjectMember models (Phase 3 collaboration)."""
from app.database import db
from app.core.time_utils import utcnow_naive


class ProjectMember(db.Model):
    """Phase 3: Shared project membership (viewer, contributor, admin)."""
    __tablename__ = 'project_members'
    __table_args__ = (db.UniqueConstraint('project_id', 'user_id', name='uq_project_member'),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(50), default='viewer')  # viewer | contributor | admin
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='members')
    user = db.relationship('User', backref='project_memberships')


class ProjectComment(db.Model):
    """Phase 3/B: Threaded comments on projects (supports replies & @mentions)."""
    __tablename__ = 'project_comments'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    content = db.Column(db.Text, nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'))  # Optional: comment on doc

    # Phase B.3 — threading support
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey('project_comments.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    # Phase B.3 — @mention list: [{"user_id": 1, "username": "alice"}, …]
    mentions_json = db.Column(db.JSON)

    # Phase 05 — manuscript section anchor and resolution
    manuscript_section_id = db.Column(
        db.Integer, db.ForeignKey('manuscript_sections.id', ondelete='SET NULL'), nullable=True, index=True
    )
    resolved_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    project = db.relationship('ResearchProject', backref='comments')
    user = db.relationship('User', backref='project_comments')
    replies = db.relationship(
        'ProjectComment',
        backref=db.backref('parent', remote_side='ProjectComment.id'),
        cascade='all, delete-orphan',
        lazy='dynamic',
        foreign_keys='ProjectComment.parent_id',
    )


class ResearchProject(db.Model):
    __tablename__ = 'research_projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, default=1)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True)
    collection_id = db.Column(db.String(255), nullable=True)  # Beep.AI.Server RAG collection
    chunk_template_slug = db.Column(db.String(255), nullable=True)  # last-applied chunk template slug
    rag_quality_mode = db.Column(db.String(50), nullable=True)

    # AI / Chat Settings
    custom_instructions = db.Column(db.Text, nullable=True)
    citation_format = db.Column(db.String(50), default='apa')
    ai_language = db.Column(db.String(50), default='en')
    
    status = db.Column(db.String(50), default='draft')
    # Phase 05 — submission checklist: JSON dict {step_key: {checked, note}}
    submission_checklist_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    owner = db.relationship('User', backref='research_projects')
    tenant = db.relationship('Tenant', backref='projects')

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'description': self.description,
            'owner_id': self.owner_id, 'tenant_id': self.tenant_id,
            'collection_id': self.collection_id, 'status': self.status,
            'chunk_template_slug': self.chunk_template_slug,
            'rag_quality_mode': self.rag_quality_mode,
            'custom_instructions': self.custom_instructions,
            'citation_format': self.citation_format,
            'ai_language': self.ai_language,
            'member_count': len(self.members) if hasattr(self, 'members') else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ResearchReportDraft(db.Model):
    __tablename__ = 'research_report_drafts'
    __table_args__ = (
        db.UniqueConstraint('project_id', name='uq_research_report_draft_project'),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)
    html_content = db.Column(db.Text, nullable=False, default='')
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    project = db.relationship('ResearchProject', backref=db.backref('report_draft', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'title': self.title,
            'html_content': self.html_content or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

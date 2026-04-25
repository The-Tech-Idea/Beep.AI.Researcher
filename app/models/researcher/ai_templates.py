"""AI Templates & Workflows - AI-powered research assistance."""
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.database import db


class AITemplate(db.Model):
    """AI writing/analysis templates (like SciSpace's AI templates)"""
    __tablename__ = 'ai_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(100), unique=True)  # Slug for URL routing
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))  # 'writing', 'analysis', 'transcription', 'critique'
    icon = db.Column(db.String(50))  # Bootstrap icon name
    description = db.Column(db.Text)
    prompt_template = db.Column(db.Text)  # Jinja2 template for AI prompt
    input_schema = db.Column(db.JSON)  # {fields: [{name, type, label, required}]}
    output_format = db.Column(db.String(50))  # 'text', 'markdown', 'json', 'structured'
    max_result_length = db.Column(db.Integer, default=10000)
    creativity_level = db.Column(db.String(50), default='balanced')  # 'precise', 'balanced', 'creative'
    creativity_default = db.Column(db.Integer, default=70)  # Default creativity percentage (0-100)
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # Built-in vs user-created
    usage_count = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    
    creator = db.relationship('User', backref='ai_templates_created')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'icon': self.icon,
            'description': self.description,
            'output_format': self.output_format,
            'max_result_length': self.max_result_length,
            'creativity_level': self.creativity_level,
            'is_system': self.is_system,
            'usage_count': self.usage_count,
        }


class AIWorkflowExecution(db.Model):
    """Track AI template executions"""
    __tablename__ = 'ai_workflow_executions'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('ai_templates.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Input/Output
    input_data = db.Column(db.JSON)  # User inputs
    output_data = db.Column(db.JSON)  # Generated result (can be dict or text)
    result_text = db.Column(db.Text)  # Plain text result for easy access
    tokens_used = db.Column(db.Integer)
    
    # Metadata
    status = db.Column(db.String(50), default='pending')  # pending, running, completed, failed
    error_message = db.Column(db.Text)
    execution_time_ms = db.Column(db.Integer)
    started_at = db.Column(db.DateTime)  # When execution started
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    template = db.relationship('AITemplate', backref='executions')
    project = db.relationship('ResearchProject', backref='ai_executions')
    user = db.relationship('User', backref='ai_executions')
    
    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'template_name': self.template.name if self.template else None,
            'project_id': self.project_id,
            'status': self.status,
            'tokens_used': self.tokens_used,
            'execution_time_ms': self.execution_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class AIWorkbook(db.Model):
    """Workbooks for organizing AI-generated content (like SciSpace workbooks)"""
    __tablename__ = 'ai_workbooks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    description = db.Column(db.Text)
    is_shared = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    project = db.relationship('ResearchProject', backref='workbooks')
    user = db.relationship('User', backref='workbooks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'project_id': self.project_id,
            'is_shared': self.is_shared,
            'document_count': len(self.documents) if hasattr(self, 'documents') else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkbookDocument(db.Model):
    """Documents within workbooks"""
    __tablename__ = 'workbook_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    workbook_id = db.Column(db.Integer, db.ForeignKey('ai_workbooks.id'), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text)  # Rich text content
    content_type = db.Column(db.String(50), default='markdown')  # markdown, html, plaintext
    notes = db.Column(db.Text)  # Additional notes/metadata
    
    # Source tracking
    source_type = db.Column(db.String(50))  # 'template_execution', 'document', 'manual'
    template_id = db.Column(db.Integer, db.ForeignKey('ai_templates.id'))
    execution_id = db.Column(db.Integer, db.ForeignKey('ai_workflow_executions.id'))
    source_template_id = db.Column(db.Integer, db.ForeignKey('ai_templates.id'))
    source_execution_id = db.Column(db.Integer, db.ForeignKey('ai_workflow_executions.id'))
    source_document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'))
    
    # Organization
    order_index = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    workbook = db.relationship('AIWorkbook', backref='documents')
    template = db.relationship('AITemplate', foreign_keys=[template_id])
    execution = db.relationship('AIWorkflowExecution', foreign_keys=[execution_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'workbook_id': self.workbook_id,
            'title': self.title,
            'content_type': self.content_type,
            'order_index': self.order_index,
            'is_pinned': self.is_pinned,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

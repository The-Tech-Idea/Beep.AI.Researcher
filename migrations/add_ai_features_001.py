"""Add AI templates, transcription, and user preferences models

Revision ID: add_ai_features_001
Revises: 
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers
revision = 'add_ai_features_001'
down_revision = None  # Update with your latest migration ID
branch_labels = None
depends_on = None


def upgrade():
    # AI Templates table
    op.create_table(
        'ai_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('identifier', sa.String(100), unique=True),  # NEW: URL slug
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100)),
        sa.Column('icon', sa.String(50)),
        sa.Column('description', sa.Text()),
        sa.Column('prompt_template', sa.Text()),
        sa.Column('input_schema', sa.JSON()),
        sa.Column('output_format', sa.String(50)),
        sa.Column('max_result_length', sa.Integer(), server_default='10000'),
        sa.Column('creativity_level', sa.String(50), server_default='balanced'),
        sa.Column('creativity_default', sa.Integer(), server_default='70'),  # NEW: Default %
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('is_system', sa.Boolean(), server_default='0'),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # AI Workflow Executions table
    op.create_table(
        'ai_workflow_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('ai_templates.id')),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('research_projects.id')),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('input_data', sa.JSON()),
        sa.Column('output_data', sa.JSON()),  # CHANGED: From Text to JSON
        sa.Column('result_text', sa.Text()),  # NEW: Cached text result
        sa.Column('tokens_used', sa.Integer()),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('error_message', sa.Text()),
        sa.Column('execution_time_ms', sa.Integer()),
        sa.Column('started_at', sa.DateTime()),  # NEW: Execution start time
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # AI Workbooks table
    op.create_table(
        'ai_workbooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('research_projects.id')),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('description', sa.Text()),
        sa.Column('is_shared', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Workbook Documents table
    op.create_table(
        'workbook_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workbook_id', sa.Integer(), sa.ForeignKey('ai_workbooks.id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('notes', sa.Text()),  # NEW: User notes
        sa.Column('source_type', sa.String(50)),  # NEW: Source tracking type
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('ai_templates.id')),  # NEW: Direct link
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('ai_workflow_executions.id')),  # NEW: Direct link
        sa.Column('content', sa.Text()),
        sa.Column('content_type', sa.String(50), server_default='markdown'),
        sa.Column('source_template_id', sa.Integer(), sa.ForeignKey('ai_templates.id')),
        sa.Column('source_execution_id', sa.Integer(), sa.ForeignKey('ai_workflow_executions.id')),
        sa.Column('source_document_id', sa.Integer(), sa.ForeignKey('researcher_documents.id')),
        sa.Column('order_index', sa.Integer(), server_default='0'),
        sa.Column('is_pinned', sa.Boolean(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Audio Transcriptions table
    op.create_table(
        'audio_transcriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('research_projects.id')),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('original_filename', sa.String(500)),
        sa.Column('file_path', sa.String(1000)),
        sa.Column('file_size_bytes', sa.BigInteger()),
        sa.Column('duration_seconds', sa.Integer()),
        sa.Column('audio_format', sa.String(50)),
        sa.Column('source_language', sa.String(10), server_default='auto'),
        sa.Column('target_language', sa.String(10), server_default='en'),
        sa.Column('audio_description', sa.Text()),
        sa.Column('transcript_text', sa.Text()),
        sa.Column('transcript_json', sa.JSON()),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('error_message', sa.Text()),
        sa.Column('processing_time_ms', sa.Integer()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Transcription Segments table
    op.create_table(
        'transcription_segments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transcription_id', sa.Integer(), sa.ForeignKey('audio_transcriptions.id'), nullable=False),
        sa.Column('start_time_ms', sa.Integer()),
        sa.Column('end_time_ms', sa.Integer()),
        sa.Column('text', sa.Text()),
        sa.Column('speaker_id', sa.String(50)),
        sa.Column('confidence', sa.Float()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Transcription Annotations table
    op.create_table(
        'transcription_annotations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transcription_id', sa.Integer(), sa.ForeignKey('audio_transcriptions.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('start_time_ms', sa.Integer()),
        sa.Column('end_time_ms', sa.Integer()),
        sa.Column('annotation_text', sa.Text()),
        sa.Column('code_id', sa.Integer(), sa.ForeignKey('researcher_codes.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # User Preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), unique=True, nullable=False),
        sa.Column('theme', sa.String(20), server_default='dark'),
        sa.Column('font_size', sa.String(20), server_default='medium'),
        sa.Column('editor_theme', sa.String(50), server_default='monokai'),
        sa.Column('sidebar_collapsed', sa.Boolean(), server_default='0'),
        sa.Column('ai_creativity_default', sa.String(50), server_default='balanced'),
        sa.Column('ai_max_tokens_default', sa.Integer(), server_default='1500'),
        sa.Column('ai_language_preference', sa.String(10), server_default='en'),
        sa.Column('email_notifications', sa.Boolean(), server_default='1'),
        sa.Column('browser_notifications', sa.Boolean(), server_default='1'),
        sa.Column('collaboration_alerts', sa.Boolean(), server_default='1'),
        sa.Column('default_workbook_id', sa.Integer(), sa.ForeignKey('ai_workbooks.id')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('user_preferences')
    op.drop_table('transcription_annotations')
    op.drop_table('transcription_segments')
    op.drop_table('audio_transcriptions')
    op.drop_table('workbook_documents')
    op.drop_table('ai_workbooks')
    op.drop_table('ai_workflow_executions')
    op.drop_table('ai_templates')

"""Add RBAC models for Phase 1.8 - Role & Permission Management

Revision ID: add_rbac_phase18
Revises: add_ai_features_001
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers
revision = 'add_rbac_phase18'
down_revision = 'add_ai_features_001'
branch_labels = None
depends_on = None


def upgrade():
    """Create RBAC tables for Phase 1.8.
    
    Creates:
    - rbac_roles: Role definitions
    - user_roles: User role assignments (with scope and expiry)
    - document_access: Document access control
    - user_groups: Groups for document sharing
    """
    
    # RBAC Roles table
    op.create_table(
        'rbac_roles',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('permissions', sa.JSON(), default=[]),
        sa.Column('is_builtin', sa.Boolean(), default=False),
        sa.Column('tenant_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('created_by', sa.String(100), nullable=True),
    )
    op.create_index('idx_role_name', 'rbac_roles', ['name'])
    op.create_index('idx_role_tenant', 'rbac_roles', ['tenant_id'])
    
    # User Roles table
    op.create_table(
        'user_roles',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(100), nullable=False),
        sa.Column('role_id', sa.String(36), sa.ForeignKey('rbac_roles.id'), nullable=False),
        sa.Column('scope', sa.String(20), default='global'),
        sa.Column('scope_id', sa.String(36), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('created_by', sa.String(100), nullable=True),
    )
    op.create_index('idx_user_id_scope', 'user_roles', ['user_id', 'scope'])
    op.create_index('idx_user_id_scope_id', 'user_roles', ['user_id', 'scope_id'])
    op.create_index('idx_expires_at', 'user_roles', ['expires_at'])
    
    # Document Access table
    op.create_table(
        'document_access',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('document_id', sa.String(36), nullable=False),
        sa.Column('owner_id', sa.String(100), nullable=False),
        sa.Column('access_level', sa.String(20), default='private'),
        sa.Column('shared_with', sa.JSON(), default={'groups': [], 'users': [], 'roles': []}),
        sa.Column('default_permissions', sa.JSON(), default=['read']),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
    )
    op.create_index('idx_document_id', 'document_access', ['document_id'])
    op.create_index('idx_owner_id', 'document_access', ['owner_id'])
    op.create_index('idx_access_level', 'document_access', ['access_level'])
    
    # User Groups table
    op.create_table(
        'user_groups',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('members', sa.JSON(), default=[]),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.Column('created_by', sa.String(100), nullable=True),
    )
    op.create_index('idx_group_name', 'user_groups', ['name'])
    op.create_index('idx_project_id', 'user_groups', ['project_id'])
    
    print("✓ Created RBAC tables for Phase 1.8")


def downgrade():
    """Drop RBAC tables."""
    op.drop_index('idx_project_id', 'user_groups')
    op.drop_index('idx_group_name', 'user_groups')
    op.drop_table('user_groups')
    
    op.drop_index('idx_access_level', 'document_access')
    op.drop_index('idx_owner_id', 'document_access')
    op.drop_index('idx_document_id', 'document_access')
    op.drop_table('document_access')
    
    op.drop_index('idx_expires_at', 'user_roles')
    op.drop_index('idx_user_id_scope_id', 'user_roles')
    op.drop_index('idx_user_id_scope', 'user_roles')
    op.drop_table('user_roles')
    
    op.drop_index('idx_role_tenant', 'rbac_roles')
    op.drop_index('idx_role_name', 'rbac_roles')
    op.drop_table('rbac_roles')
    
    print("✓ Dropped RBAC tables")

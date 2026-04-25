"""RBAC Models for Phase 1.8 - Role & Permission Management System.

Provides:
- Role: Named set of permissions
- UserRole: Assignment of role to user (with scope and expiry)
- DocumentAccess: Access control for individual documents
- UserGroup: Groups for document sharing
- Permission: Reference class for permission constants
"""

from datetime import datetime, UTC
from enum import Enum
import uuid
from sqlalchemy import Index
from sqlalchemy.orm.attributes import flag_modified
from app.database import db


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class Permission:
    """Permission naming convention: resource:action."""
    
    # Document permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_SHARE = "document:share"
    DOCUMENT_EXPORT = "document:export"
    DOCUMENT_DELETE = "document:delete"
    
    # Project permissions
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"
    PROJECT_SHARE = "project:share"
    PROJECT_DELETE = "project:delete"
    
    # Code permissions
    CODE_READ = "code:read"
    CODE_WRITE = "code:write"
    CODE_DELETE = "code:delete"
    
    # Extraction permissions
    EXTRACTION_READ = "extraction:read"
    EXTRACTION_WRITE = "extraction:write"
    
    # Chat permissions
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    
    # Task permissions
    TASK_READ = "task:read"
    TASK_WRITE = "task:write"
    TASK_ASSIGN = "task:assign"
    
    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_ROLES = "admin:roles"
    ADMIN_AUDIT = "admin:audit"
    ADMIN_SETTINGS = "admin:settings"
    
    # Wildcard
    ALL = "*:*"


class RBACRole(db.Model):
    """Role model for RBAC - named set of permissions.
    
    Advanced role/permission system for Phase 1.8+.
    Built-in roles: viewer, contributor, lead, admin
    """
    __tablename__ = 'rbac_roles'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), nullable=True)
    
    # Permissions as JSON array: ["document:read", "document:write", ...]
    permissions = db.Column(db.JSON, default=list)
    
    # Is this a built-in role (viewer, contributor, lead, admin)?
    is_builtin = db.Column(db.Boolean, default=False)
    
    # For future: tenant_id for multi-tenant support
    tenant_id = db.Column(db.String(36), nullable=True)
    
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    created_by = db.Column(db.String(100), nullable=True)
    
    # Relationships
    user_roles = db.relationship('UserRole', backref='rbac_role', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    def has_permission(self, permission: str) -> bool:
        """Check if role has a specific permission."""
        if not self.permissions:
            return False
        return permission in self.permissions or Permission.ALL in self.permissions
    
    def add_permission(self, permission: str):
        """Add a permission to this role."""
        if not self.permissions:
            self.permissions = []
        if permission not in self.permissions:
            self.permissions.append(permission)
            flag_modified(self, 'permissions')
    
    def remove_permission(self, permission: str):
        """Remove a permission from this role."""
        if self.permissions and permission in self.permissions:
            self.permissions.remove(permission)
            flag_modified(self, 'permissions')


class UserRole(db.Model):
    """User role assignment with scope and expiry support.
    
    Models:
    - Global scope: user has role everywhere
    - Project scope: user has role in specific project
    - Document scope: user has role for specific document
    """
    __tablename__ = 'user_roles'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID
    user_id = db.Column(db.String(100), nullable=False)
    role_id = db.Column(db.String(36), db.ForeignKey('rbac_roles.id'), nullable=False)
    
    # Scope: 'global', 'project', or 'document'
    scope = db.Column(db.String(20), default='global')
    
    # scope_id: project_id or document_id (null for global scope)
    scope_id = db.Column(db.String(36), nullable=True)
    
    # When does this assignment expire? (null = permanent)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=_utcnow)
    created_by = db.Column(db.String(100), nullable=True)
    
    # Indexes for fast lookups
    __table_args__ = (
        Index('idx_user_id_scope', 'user_id', 'scope'),
        Index('idx_user_id_scope_id', 'user_id', 'scope_id'),
        Index('idx_expires_at', 'expires_at'),
    )
    
    def __repr__(self):
        return f'<UserRole user={self.user_id} role={self.role_id} scope={self.scope}>'
    
    def is_expired(self) -> bool:
        """Check if this assignment is expired."""
        if not self.expires_at:
            return False
        return datetime.now(UTC).replace(tzinfo=None) > self.expires_at


class AccessLevel(str, Enum):
    """Document access levels."""
    PRIVATE = "PRIVATE"      # Only owner
    OWNER = "OWNER"          # Owner only
    PROJECT = "PROJECT"      # Everyone in project
    GROUP = "GROUP"          # Specific group(s)
    SHARED = "SHARED"        # Specific users
    PUBLIC = "PUBLIC"        # Everyone in tenant


class DocumentAccess(db.Model):
    """Access control model for individual documents.
    
    Supports:
    - PRIVATE: owner only
    - GROUP: specific group(s)
    - SHARED: specific user(s)
    - PUBLIC: everyone
    """
    __tablename__ = 'document_access'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID
    document_id = db.Column(db.String(36), nullable=False)  # Foreign key to Document
    
    # Owner of document (can change access)
    owner_id = db.Column(db.String(100), nullable=False)
    
    # Access level: private, group, shared, public
    access_level = db.Column(db.String(20), default=AccessLevel.PRIVATE.value)
    
    # Who has access (JSON)
    # {
    #   "groups": ["group_1", "group_2"],
    #   "users": ["user_123", "user_456"],
    #   "roles": []
    # }
    # Keep this user-centric list for API/test compatibility.
    shared_with = db.Column(db.JSON, default=list)
    
    # Default permissions for shared users: ['read'] or ['read', 'write']
    default_permissions = db.Column(db.JSON, default=lambda: ['read'])
    
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Indexes for fast lookups
    __table_args__ = (
        Index('idx_document_id', 'document_id'),
        Index('idx_owner_id', 'owner_id'),
        Index('idx_access_level', 'access_level'),
    )
    
    def __repr__(self):
        return f'<DocumentAccess doc={self.document_id} level={self.access_level}>'
    
    def is_shared_with(self, user_id: str) -> bool:
        """Check if document is shared with specific user."""
        if not self.shared_with:
            return False
        if isinstance(self.shared_with, list):
            return user_id in self.shared_with
        return user_id in self.shared_with.get('users', [])
    
    def is_shared_with_group(self, group_id: str) -> bool:
        """Check if document is shared with specific group."""
        if not self.shared_with:
            return False
        if isinstance(self.shared_with, list):
            return False
        return group_id in self.shared_with.get('groups', [])
    
    def share_with_user(self, user_id: str, permissions: list = None):
        """Share document with specific user."""
        if not self.shared_with:
            self.shared_with = []

        if isinstance(self.shared_with, dict):
            users = self.shared_with.setdefault('users', [])
            if user_id not in users:
                users.append(user_id)
                flag_modified(self, 'shared_with')
        elif user_id not in self.shared_with:
            self.shared_with.append(user_id)
            flag_modified(self, 'shared_with')

        self.access_level = AccessLevel.SHARED.value
        if permissions:
            self.default_permissions = permissions if isinstance(permissions, list) else [permissions]
    
    def share_with_group(self, group_id: str, permissions: list = None):
        """Share document with group."""
        if not self.shared_with or isinstance(self.shared_with, list):
            self.shared_with = {'groups': [], 'users': [], 'roles': []}

        if group_id not in self.shared_with['groups']:
            self.shared_with['groups'].append(group_id)
            flag_modified(self, 'shared_with')

        self.access_level = AccessLevel.GROUP.value
        if permissions:
            self.default_permissions = permissions if isinstance(permissions, list) else [permissions]
    
    def unshare_with_user(self, user_id: str):
        """Remove document sharing with specific user."""
        if not self.shared_with:
            return
        if isinstance(self.shared_with, list):
            if user_id in self.shared_with:
                self.shared_with.remove(user_id)
                flag_modified(self, 'shared_with')
            return
        if user_id in self.shared_with.get('users', []):
            self.shared_with['users'].remove(user_id)
            flag_modified(self, 'shared_with')
    
    def unshare_with_group(self, group_id: str):
        """Remove document sharing with group."""
        if isinstance(self.shared_with, dict) and group_id in self.shared_with.get('groups', []):
            self.shared_with['groups'].remove(group_id)
            flag_modified(self, 'shared_with')
    
    def make_private(self):
        """Make document private (owner only)."""
        self.access_level = AccessLevel.PRIVATE.value
        self.shared_with = []
    
    def make_public(self):
        """Make document public (everyone in tenant)."""
        self.access_level = AccessLevel.PUBLIC.value
        self.default_permissions = ['read']


class UserGroup(db.Model):
    """Groups for document sharing and team management.
    
    Supports group-based sharing and access control.
    """
    __tablename__ = 'user_groups'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    
    # Members: JSON array of user IDs
    members = db.Column(db.JSON, default=list)
    
    # Optional: tie to specific project
    project_id = db.Column(db.String(36), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    created_by = db.Column(db.String(100), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_group_name', 'name'),
        Index('idx_project_id', 'project_id'),
    )
    
    def __repr__(self):
        return f'<UserGroup {self.name}>'
    
    def add_member(self, user_id: str):
        """Add member to group."""
        if not self.members:
            self.members = []
        if user_id not in self.members:
            self.members.append(user_id)
            flag_modified(self, 'members')
    
    def remove_member(self, user_id: str):
        """Remove member from group."""
        if self.members and user_id in self.members:
            self.members.remove(user_id)
            flag_modified(self, 'members')
    
    def has_member(self, user_id: str) -> bool:
        """Check if user is member of group."""
        return user_id in (self.members or [])
    
    def get_members_count(self) -> int:
        """Get number of members."""
        return len(self.members or [])


# Built-in roles definition
BUILTIN_ROLES = {
    'viewer': {
        'description': 'Read-only access to documents and codes',
        'permissions': [
            Permission.DOCUMENT_READ,
            Permission.PROJECT_READ,
            Permission.CODE_READ,
            Permission.EXTRACTION_READ,
            Permission.CHAT_READ,
            Permission.TASK_READ,
        ]
    },
    'contributor': {
        'description': 'Can read, write, and upload documents',
        'permissions': [
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_WRITE,
            Permission.DOCUMENT_EXPORT,
            Permission.PROJECT_READ,
            Permission.CODE_READ,
            Permission.CODE_WRITE,
            Permission.EXTRACTION_READ,
            Permission.EXTRACTION_WRITE,
            Permission.CHAT_READ,
            Permission.CHAT_WRITE,
            Permission.TASK_READ,
            Permission.TASK_WRITE,
        ]
    },
    'lead': {
        'description': 'Can manage projects and team members',
        'permissions': [
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_WRITE,
            Permission.DOCUMENT_SHARE,
            Permission.DOCUMENT_EXPORT,
            Permission.PROJECT_READ,
            Permission.PROJECT_WRITE,
            Permission.PROJECT_SHARE,
            Permission.CODE_READ,
            Permission.CODE_WRITE,
            Permission.EXTRACTION_READ,
            Permission.EXTRACTION_WRITE,
            Permission.CHAT_READ,
            Permission.CHAT_WRITE,
            Permission.TASK_READ,
            Permission.TASK_WRITE,
            Permission.TASK_ASSIGN,
        ]
    },
    'admin': {
        'description': 'Full access',
        'permissions': [Permission.ALL]
    }
}

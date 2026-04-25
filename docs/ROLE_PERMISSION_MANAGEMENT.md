# Role & Permission Management Implementation Guide

**Date**: February 7, 2026  
**Purpose**: Complete reference for implementing role-based access control (RBAC) and document-level permissions

---

## Overview

This system allows:
- **Admins** create custom roles and assign permissions
- **Users** get assigned roles (admin, contributor, viewer, custom)
- **Documents** can be private, shared with groups, or public
- **Projects** have their own access control
- **Permissions** are granular (read, write, delete, share, export)

---

## 1. Data Models

### Role Model
```python
# beep/models/role.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, JSON
from beep.database import db

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(100), unique=True, nullable=False)  # admin, contributor, viewer, custom_role_1
    description = Column(String(500), nullable=True)
    
    # Permissions (JSON array of permission names)
    # Examples: ['document:read', 'document:write', 'document:delete', 'document:share', 
    #           'project:read', 'project:write', 'code:read', 'code:write', 'extraction:read', ...]
    permissions = Column(JSON, default=[])
    
    # Is this a built-in role or custom?
    is_builtin = Column(Boolean, default=False)
    
    # Tenant-specific roles (null = global)
    tenant_id = Column(String(36), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
```

### User Role Assignment
```python
# beep/models/user_role.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from beep.database import db

class UserRole(db.Model):
    __tablename__ = 'user_roles'
    
    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(100), nullable=False)
    role_id = Column(String(36), ForeignKey('roles.id'), nullable=False)
    
    # Scope: global, project, or document
    scope = Column(String(20), default='global')  # global, project, document
    scope_id = Column(String(36), nullable=True)  # project_id or document_id
    
    # When does this assignment expire? (for temporary access)
    expires_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
```

### Document Access Control
```python
# beep/models/document_access.py
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, ForeignKey
from beep.database import db

class AccessLevel(str, Enum):
    PRIVATE = "private"        # Only owner
    OWNER = "owner"            # Owner only (future: collaborators)
    PROJECT = "project"        # Everyone in project
    GROUP = "group"            # Specific group(s)
    SHARED = "shared"          # Shared with specific users
    PUBLIC = "public"          # Everyone in tenant

class DocumentAccess(db.Model):
    __tablename__ = 'document_access'
    
    id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey('documents.id'), nullable=False)
    
    # Owner of document (can change access)
    owner_id = Column(String(100), nullable=False)
    
    # Access level: private, project, group, shared, public
    access_level = Column(String(20), default=AccessLevel.PRIVATE)
    
    # Who has access (JSON)
    # {
    #   "groups": ["group_1", "group_2"],
    #   "users": ["user_123", "user_456"],
    #   "roles": ["viewer", "contributor"]
    # }
    shared_with = Column(JSON, default={'groups': [], 'users': [], 'roles': []})
    
    # Default permissions for shared users
    # Examples: ['read'], ['read', 'comment'], ['read', 'write']
    default_permissions = Column(JSON, default=['read'])
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Permission Model (Reference)
```python
# beep/models/permission.py
from sqlalchemy import Column, String

# This is a reference model - permissions are defined as strings
# Examples: 'document:read', 'document:write', 'document:delete', 'code:write'

class Permission:
    """
    Permission naming convention: resource:action
    
    Resources:
    - document: read, write, delete, share, export
    - project: read, write, delete, share
    - code: read, write, delete
    - extraction: read, write, delete
    - task: read, write, delete, assign
    - user: read, write  (for admin)
    - role: read, write, delete  (for admin)
    
    Standard set for Researcher:
    """
    
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"  # Upload, delete
    DOCUMENT_SHARE = "document:share"
    DOCUMENT_EXPORT = "document:export"
    
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"  # Create, update, delete
    PROJECT_SHARE = "project:share"
    
    CODE_READ = "code:read"
    CODE_WRITE = "code:write"  # Create, update, delete, merge
    
    EXTRACTION_READ = "extraction:read"
    EXTRACTION_WRITE = "extraction:write"
    
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    
    TASK_READ = "task:read"
    TASK_WRITE = "task:write"
    TASK_ASSIGN = "task:assign"
    
    ADMIN_USERS = "admin:users"       # Manage users (assign roles, suspend)
    ADMIN_ROLES = "admin:roles"       # Create/modify roles
    ADMIN_AUDIT = "admin:audit"       # View audit logs
    ADMIN_SETTINGS = "admin:settings" # Tenant settings

# Built-in roles (seeded at startup)
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
        'permissions': [
            # All permissions
            '*:*'
        ]
    }
}
```

---

## 2. Permission Checking Service

### Create Permission Service
```python
# beep/services/permission_service.py
from beep.models.role import Role
from beep.models.user_role import UserRole
from beep.models.document_access import DocumentAccess, AccessLevel
from beep.database import db

class PermissionService:
    """Service for checking user permissions"""
    
    @staticmethod
    def user_has_permission(user_id: str, permission: str, scope: str = 'global', scope_id: str = None) -> bool:
        """
        Check if user has permission.
        
        Args:
            user_id: User identifier
            permission: Permission name (e.g., 'document:write')
            scope: 'global' or 'project'
            scope_id: project_id if scope is 'project'
        
        Returns:
            True if user has permission
        """
        # Get user's roles
        user_roles = UserRole.query.filter(
            UserRole.user_id == user_id,
            UserRole.scope == scope
        )
        
        if scope_id:
            user_roles = user_roles.filter(UserRole.scope_id == scope_id)
        
        user_roles = user_roles.all()
        
        for user_role in user_roles:
            role = Role.query.get(user_role.role_id)
            if role and (permission in role.permissions or '*:*' in role.permissions):
                return True
        
        return False
    
    @staticmethod
    def can_access_document(user_id: str, document_id: str) -> bool:
        """Check if user can read a document"""
        doc_access = DocumentAccess.query.filter_by(document_id=document_id).first()
        
        if not doc_access:
            return False
        
        # Owner can always access
        if doc_access.owner_id == user_id:
            return True
        
        # Public access
        if doc_access.access_level == AccessLevel.PUBLIC:
            return True
        
        # Project access - check if user in project
        if doc_access.access_level == AccessLevel.PROJECT:
            # TODO: Check if user is member of project
            return True
        
        # Group access
        if doc_access.access_level == AccessLevel.GROUP:
            shared_with = doc_access.shared_with
            return any(
                is_user_in_group(user_id, group) 
                for group in shared_with.get('groups', [])
            )
        
        # Shared with specific users
        if doc_access.access_level == AccessLevel.SHARED:
            shared_with = doc_access.shared_with
            return user_id in shared_with.get('users', [])
        
        # Private - only owner
        return False
    
    @staticmethod
    def can_write_document(user_id: str, document_id: str) -> bool:
        """Check if user can write/edit a document"""
        doc_access = DocumentAccess.query.filter_by(document_id=document_id).first()
        
        if not doc_access:
            return False
        
        # Owner can always write
        if doc_access.owner_id == user_id:
            return True
        
        # Check if user has write permission for this access level
        shared_with = doc_access.shared_with
        user_perms = doc_access.default_permissions
        
        if 'write' not in user_perms:
            return False
        
        # Check if user is in allowed list
        if user_id in shared_with.get('users', []):
            return True
        
        # Check if user is in group
        return any(
            is_user_in_group(user_id, group) 
            for group in shared_with.get('groups', [])
        )
    
    @staticmethod
    def get_accessible_documents(user_id: str, project_id: str = None) -> list:
        """Get all documents user can access"""
        query = DocumentAccess.query.join(Document).filter(
            (DocumentAccess.owner_id == user_id) |  # Owner
            (DocumentAccess.access_level == AccessLevel.PUBLIC) |  # Public
            # More complex filters for group/shared...
        )
        
        if project_id:
            query = query.filter(Document.project_id == project_id)
        
        return query.all()


def is_user_in_group(user_id: str, group_id: str) -> bool:
    """Helper: Check if user is member of group"""
    # TODO: Implement group membership check
    # This would check UserGroup table
    pass
```

### Permission Decorator
```python
# beep/decorators/permissions.py
from functools import wraps
from flask import jsonify, request, current_app
from beep.services.permission_service import PermissionService

def require_permission(permission: str, scope: str = 'global'):
    """
    Decorator to check user has permission before executing route.
    
    Usage:
        @app.route('/projects/<id>/documents')
        @require_permission('document:read', scope='project')
        def get_documents(id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = request.headers.get('X-User-ID')
            scope_id = kwargs.get('id')  # project_id or document_id
            
            if not PermissionService.user_has_permission(user_id, permission, scope, scope_id):
                return jsonify({'error': 'Forbidden', 'message': f'Missing permission: {permission}'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator

def require_document_access(access_type: str = 'read'):
    """
    Decorator to check document access.
    
    Usage:
        @require_document_access('read')
        def get_document(doc_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = request.headers.get('X-User-ID')
            document_id = kwargs.get('doc_id')
            
            if access_type == 'read':
                can_access = PermissionService.can_access_document(user_id, document_id)
            elif access_type == 'write':
                can_access = PermissionService.can_write_document(user_id, document_id)
            else:
                can_access = False
            
            if not can_access:
                return jsonify({'error': 'Forbidden'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
```

---

## 3. Admin Routes

### Role Management Routes
```python
# beep/routes/admin/roles.py
from flask import Blueprint, request, jsonify
from beep.models.role import Role, BUILTIN_ROLES
from beep.models.user_role import UserRole
from beep.decorators.permissions import require_permission
from beep.database import db
import uuid
from datetime import datetime

role_admin_bp = Blueprint('role_admin', __name__, url_prefix='/admin/roles')

@role_admin_bp.route('', methods=['GET'])
@require_permission('admin:roles')
def list_roles():
    """List all roles"""
    roles = Role.query.all()
    return jsonify({
        'success': True,
        'roles': [
            {
                'id': r.id,
                'name': r.name,
                'description': r.description,
                'permissions': r.permissions,
                'is_builtin': r.is_builtin,
                'created_at': r.created_at.isoformat(),
            }
            for r in roles
        ]
    })

@role_admin_bp.route('', methods=['POST'])
@require_permission('admin:roles')
def create_role():
    """Create new role"""
    data = request.get_json()
    
    # Validate
    if not data.get('name'):
        return jsonify({'error': 'Role name required'}), 400
    
    if Role.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Role already exists'}), 409
    
    role = Role(
        id=str(uuid.uuid4()),
        name=data['name'],
        description=data.get('description', ''),
        permissions=data.get('permissions', []),
        is_builtin=False,
        created_by=request.headers.get('X-User-ID')
    )
    
    db.session.add(role)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'role': {
            'id': role.id,
            'name': role.name,
            'permissions': role.permissions
        }
    }), 201

@role_admin_bp.route('/<role_id>', methods=['PUT'])
@require_permission('admin:roles')
def update_role(role_id):
    """Update role permissions"""
    role = Role.query.get(role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    if role.is_builtin:
        return jsonify({'error': 'Cannot modify built-in roles'}), 403
    
    data = request.get_json()
    
    if 'permissions' in data:
        role.permissions = data['permissions']
    
    if 'description' in data:
        role.description = data['description']
    
    role.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'role': {'id': role.id, 'name': role.name}})

@role_admin_bp.route('/<role_id>', methods=['DELETE'])
@require_permission('admin:roles')
def delete_role(role_id):
    """Delete custom role"""
    role = Role.query.get(role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    if role.is_builtin:
        return jsonify({'error': 'Cannot delete built-in roles'}), 403
    
    # Check if any users have this role
    user_count = UserRole.query.filter_by(role_id=role_id).count()
    if user_count > 0:
        return jsonify({'error': f'{user_count} users have this role. Remove role assignment first.'}), 409
    
    db.session.delete(role)
    db.session.commit()
    
    return jsonify({'success': True})
```

### User Role Assignment Routes
```python
# beep/routes/admin/user_roles.py
from flask import Blueprint, request, jsonify
from beep.models.user_role import UserRole
from beep.models.role import Role
from beep.decorators.permissions import require_permission
from beep.database import db
import uuid
from datetime import datetime, timedelta

user_role_admin_bp = Blueprint('user_role_admin', __name__, url_prefix='/admin/users')

@user_role_admin_bp.route('/<user_id>/roles', methods=['GET'])
@require_permission('admin:users')
def get_user_roles(user_id):
    """Get all roles assigned to user"""
    user_roles = UserRole.query.filter_by(user_id=user_id).all()
    
    return jsonify({
        'success': True,
        'user_id': user_id,
        'roles': [
            {
                'role_id': ur.role_id,
                'role_name': Role.query.get(ur.role_id).name,
                'scope': ur.scope,
                'scope_id': ur.scope_id,
                'expires_at': ur.expires_at.isoformat() if ur.expires_at else None,
                'created_at': ur.created_at.isoformat(),
            }
            for ur in user_roles
        ]
    })

@user_role_admin_bp.route('/<user_id>/roles', methods=['POST'])
@require_permission('admin:users')
def assign_role(user_id):
    """Assign role to user"""
    data = request.get_json()
    
    role_id = data.get('role_id')
    role = Role.query.get(role_id)
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    # Check if already assigned
    if UserRole.query.filter_by(user_id=user_id, role_id=role_id,
                                scope=data.get('scope', 'global'),
                                scope_id=data.get('scope_id')).first():
        return jsonify({'error': 'Role already assigned to this user'}), 409
    
    expires_at = None
    if data.get('expires_in_days'):
        expires_at = datetime.utcnow() + timedelta(days=data['expires_in_days'])
    
    user_role = UserRole(
        id=str(uuid.uuid4()),
        user_id=user_id,
        role_id=role_id,
        scope=data.get('scope', 'global'),
        scope_id=data.get('scope_id'),
        expires_at=expires_at,
        created_by=request.headers.get('X-User-ID')
    )
    
    db.session.add(user_role)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Assigned {role.name} role to user {user_id}'
    }), 201

@user_role_admin_bp.route('/<user_id>/roles/<role_id>', methods=['DELETE'])
@require_permission('admin:users')
def revoke_role(user_id, role_id):
    """Revoke role from user"""
    user_role = UserRole.query.filter_by(user_id=user_id, role_id=role_id).first()
    
    if not user_role:
        return jsonify({'error': 'Role assignment not found'}), 404
    
    db.session.delete(user_role)
    db.session.commit()
    
    return jsonify({'success': True})
```

---

## 4. Document Access Control Routes

### Document Access Routes
```python
# beep/routes/documents/access.py
from flask import Blueprint, request, jsonify
from beep.models.document_access import DocumentAccess, AccessLevel
from beep.decorators.permissions import require_document_access
from beep.database import db
import uuid

doc_access_bp = Blueprint('doc_access', __name__, url_prefix='/projects/<project_id>/documents/<doc_id>/access')

@doc_access_bp.route('', methods=['GET'])
@require_document_access('read')
def get_document_access(project_id, doc_id):
    """Get document access settings"""
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()
    
    if not access:
        return jsonify({'error': 'Document not found'}), 404
    
    return jsonify({
        'success': True,
        'access': {
            'owner_id': access.owner_id,
            'access_level': access.access_level,
            'shared_with': access.shared_with,
            'default_permissions': access.default_permissions,
        }
    })

@doc_access_bp.route('', methods=['PUT'])
@require_document_access('write')
def update_document_access(project_id, doc_id):
    """Update document access settings"""
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()
    
    if not access:
        return jsonify({'error': 'Document not found'}), 404
    
    user_id = request.headers.get('X-User-ID')
    if access.owner_id != user_id:
        return jsonify({'error': 'Only owner can change access'}), 403
    
    data = request.get_json()
    
    # Update access level
    if 'access_level' in data:
        if data['access_level'] not in [e.value for e in AccessLevel]:
            return jsonify({'error': 'Invalid access level'}), 400
        access.access_level = data['access_level']
    
    # Update shared_with
    if 'shared_with' in data:
        access.shared_with = data['shared_with']
    
    # Update default permissions
    if 'default_permissions' in data:
        access.default_permissions = data['default_permissions']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Document access updated'
    })

@doc_access_bp.route('/share-user', methods=['POST'])
@require_document_access('write')
def share_document_with_user(project_id, doc_id):
    """Share document with specific user"""
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()
    
    if not access:
        return jsonify({'error': 'Document not found'}), 404
    
    user_id = request.headers.get('X-User-ID')
    if access.owner_id != user_id:
        return jsonify({'error': 'Only owner can share'}), 403
    
    data = request.get_json()
    target_user = data.get('user_id')
    perms = data.get('permissions', ['read'])
    
    if target_user not in access.shared_with['users']:
        access.shared_with['users'].append(target_user)
    
    access.default_permissions = perms
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Shared with {target_user}'})

@doc_access_bp.route('/share-group', methods=['POST'])
@require_document_access('write')
def share_document_with_group(project_id, doc_id):
    """Share document with group"""
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()
    
    if not access:
        return jsonify({'error': 'Document not found'}), 404
    
    user_id = request.headers.get('X-User-ID')
    if access.owner_id != user_id:
        return jsonify({'error': 'Only owner can share'}), 403
    
    data = request.get_json()
    group_id = data.get('group_id')
    perms = data.get('permissions', ['read'])
    
    if group_id not in access.shared_with['groups']:
        access.shared_with['groups'].append(group_id)
    
    access.default_permissions = perms
    access.access_level = AccessLevel.GROUP
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Shared with group {group_id}'})

@doc_access_bp.route('/make-private', methods=['POST'])
@require_document_access('write')
def make_document_private(project_id, doc_id):
    """Make document private (only owner)"""
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()
    
    if not access:
        return jsonify({'error': 'Document not found'}), 404
    
    user_id = request.headers.get('X-User-ID')
    if access.owner_id != user_id:
        return jsonify({'error': 'Only owner can change'}), 403
    
    access.access_level = AccessLevel.PRIVATE
    access.shared_with = {'groups': [], 'users': [], 'roles': []}
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Document is now private'})

@doc_access_bp.route('/make-public', methods=['POST'])
@require_document_access('write')
def make_document_public(project_id, doc_id):
    """Make document public (everyone in tenant)"""
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()
    
    if not access:
        return jsonify({'error': 'Document not found'}), 404
    
    user_id = request.headers.get('X-User-ID')
    if access.owner_id != user_id:
        return jsonify({'error': 'Only owner can change'}), 403
    
    access.access_level = AccessLevel.PUBLIC
    access.default_permissions = ['read']
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Document is now public'})
```

---

## 5. Integration with Existing Routes

Add to existing document/project routes:

```python
# In beep/routes/documents.py
from beep.decorators.permissions import require_document_access

@documents_bp.route('/<doc_id>', methods=['GET'])
@require_document_access('read')
def get_document(doc_id):
    """Get document (with access check)"""
    # ... existing code ...

@documents_bp.route('', methods=['POST'])
@require_permission('document:write')
def upload_document():
    """Upload document (with permission check)"""
    # ... create DocumentAccess with owner = current user ...
    # ... existing code ...
```

---

## 6. Database Migrations

```bash
# Create migration
flask db migrate -m "Add role and permission tables"

# Files generated will include:
# - Role table
# - UserRole table  
# - DocumentAccess table
# - Indexes on user_id, role_id, owner_id
```

---

## 7. Seed Built-in Roles

```python
# beep/scripts/seed_roles.py
from beep.models.role import Role, BUILTIN_ROLES
from beep.database import db
import uuid

def seed_builtin_roles():
    """Seed built-in roles at startup"""
    for role_name, role_data in BUILTIN_ROLES.items():
        if Role.query.filter_by(name=role_name, is_builtin=True).first():
            continue
        
        role = Role(
            id=str(uuid.uuid4()),
            name=role_name,
            description=role_data['description'],
            permissions=role_data['permissions'],
            is_builtin=True
        )
        db.session.add(role)
    
    db.session.commit()

# Call in app initialization:
# seed_builtin_roles()
```

---

## 8. Usage Examples

### Admin Creates Custom Role
```bash
POST /admin/roles
{
  "name": "data_analyst",
  "description": "Can analyze and export data",
  "permissions": [
    "document:read",
    "document:export",
    "extraction:read",
    "code:read"
  ]
}
```

### Assign Role to User
```bash
POST /admin/users/user_123/roles
{
  "role_id": "role_uuid",
  "scope": "global"
}
```

### Share Document with Group
```bash
POST /projects/proj_1/documents/doc_1/access/share-group
{
  "group_id": "research_team",
  "permissions": ["read", "comment"]
}
```

### Make Document Private
```bash
POST /projects/proj_1/documents/doc_1/access/make-private
```

---

## 9. Testing

```python
def test_create_role():
    response = client.post('/admin/roles', json={
        'name': 'test_role',
        'permissions': ['document:read']
    }, headers={'X-User-ID': 'admin_1'})
    assert response.status_code == 201

def test_assign_role():
    response = client.post('/admin/users/user_1/roles', json={
        'role_id': 'role_uuid'
    }, headers={'X-User-ID': 'admin_1'})
    assert response.status_code == 201

def test_document_access_control():
    # User A uploads document (owner)
    # User B cannot access (private)
    # User A shares with User B (read-only)
    # User B can read, cannot write
    pass
```

---

## 10. Frontend Integration

### Example: Document Permissions UI
```javascript
// Show access level selector
<select value={accessLevel} onChange={handleAccessChange}>
  <option value="private">Private (only me)</option>
  <option value="shared">Shared with specific users/groups</option>
  <option value="project">Everyone in project</option>
  <option value="public">Public (everyone in tenant)</option>
</select>

// Show shared with list
{accessLevel === 'shared' && (
  <div>
    <h4>Shared with:</h4>
    {sharedWith.users.map(u => (
      <div key={u}>
        {u} - 
        <select onChange={(e) => changePermission(u, e.target.value)}>
          <option>read</option>
          <option>read, write</option>
        </select>
      </div>
    ))}
  </div>
)}
```

### Example: Role Management UI (Admin)
```javascript
// Create role
<form onSubmit={createRole}>
  <input placeholder="Role name" />
  <textarea placeholder="Description" />
  <div>
    <h4>Permissions:</h4>
    {permissionList.map(p => (
      <label key={p}>
        <input type="checkbox" value={p} /> {p}
      </label>
    ))}
  </div>
  <button>Create Role</button>
</form>

// Assign role to user
<select onChange={(e) => assignRole(userId, e.target.value)}>
  <option>Select role...</option>
  {roles.map(r => (
    <option key={r.id} value={r.id}>{r.name}</option>
  ))}
</select>
```

---

## Summary

This implementation provides:
- ✅ Role-based access control (RBAC)
- ✅ Document-level permissions (private, shared, public)
- ✅ Group and user-based sharing
- ✅ Admin interface for role management
- ✅ Decorators for permission checking
- ✅ Built-in roles (viewer, contributor, lead, admin)
- ✅ Custom role creation
- ✅ Temporary role assignments (with expiry)

All built on SQLite - no external systems needed!

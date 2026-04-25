"""Unit tests for RBAC model classes - Phase 1.8.11"""
import pytest
import uuid
from datetime import datetime, timedelta
from app.database import db
from app.models.rbac import (
    RBACRole, UserRole, DocumentAccess, UserGroup,
    Permission, BUILTIN_ROLES
)


class TestRoleModel:
    """Tests for Role model."""
    
    def test_create_role(self, app):
        """Test creating a basic role."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_role',
                description='A test role',
                permissions=['document:read', 'document:write'],
                is_builtin=False
            )
            db.session.add(role)
            db.session.commit()
            
            retrieved = RBACRole.query.filter_by(name='test_role').first()
            assert retrieved is not None
            assert retrieved.name == 'test_role'
            assert len(retrieved.permissions) == 2
    
    def test_role_has_permission(self, app):
        """Test Role.has_permission() method."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='contributor',
                permissions=['document:read', 'document:write', 'code:write']
            )
            db.session.add(role)
            db.session.commit()
            
            assert role.has_permission('document:read') is True
            assert role.has_permission('document:write') is True
            assert role.has_permission('code:read') is False
    
    def test_role_wildcard_permission(self, app):
        """Test wildcard permission matching."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='admin',
                permissions=['*:*']  # All permissions
            )
            db.session.add(role)
            db.session.commit()
            
            assert role.has_permission('document:read') is True
            assert role.has_permission('admin:roles') is True
            assert role.has_permission('anything:here') is True
    
    def test_role_add_permission(self, app):
        """Test adding permission to role."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_role',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            role.add_permission('document:write')
            db.session.commit()
            
            retrieved = RBACRole.query.filter_by(name='test_role').first()
            assert 'document:write' in retrieved.permissions
            assert len(retrieved.permissions) == 2
    
    def test_role_add_duplicate_permission(self, app):
        """Test adding duplicate permission (should not duplicate)."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_role',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            role.add_permission('document:read')
            db.session.commit()
            
            assert len(role.permissions) == 1
    
    def test_role_remove_permission(self, app):
        """Test removing permission from role."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_role',
                permissions=['document:read', 'document:write']
            )
            db.session.add(role)
            db.session.commit()
            
            role.remove_permission('document:read')
            db.session.commit()
            
            assert 'document:read' not in role.permissions
            assert len(role.permissions) == 1


class TestUserRoleModel:
    """Tests for UserRole model."""
    
    def test_create_user_role(self, app):
        """Test assigning a role to a user."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='viewer',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            retrieved = UserRole.query.filter_by(user_id=user_id).first()
            assert retrieved is not None
            assert retrieved.role_id == role.id
    
    def test_user_role_with_expiry(self, app):
        """Test UserRole with expiration date."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='temp_role',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            future = datetime.utcnow() + timedelta(days=7)
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                scope='global',
                expires_at=future
            )
            db.session.add(user_role)
            db.session.commit()
            
            assert user_role.expires_at is not None
            assert not user_role.is_expired()
    
    def test_user_role_is_expired(self, app):
        """Test UserRole.is_expired() method."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='expired_role',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            past = datetime.utcnow() - timedelta(days=1)
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                scope='global',
                expires_at=past
            )
            db.session.add(user_role)
            db.session.commit()
            
            assert user_role.is_expired() is True
    
    def test_user_role_project_scope(self, app):
        """Test UserRole with project scope."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='project_role',
                permissions=['project:write']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            project_id = 123
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                scope='project',
                scope_id=project_id
            )
            db.session.add(user_role)
            db.session.commit()
            
            retrieved = UserRole.query.filter_by(
                user_id=user_id,
                scope='project',
                scope_id=project_id
            ).first()
            assert retrieved is not None


class TestDocumentAccessModel:
    """Tests for DocumentAccess model."""
    
    def test_create_document_access(self, app):
        """Test creating document access control."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            retrieved = DocumentAccess.query.filter_by(
                document_id=doc_id
            ).first()
            assert retrieved is not None
            assert retrieved.owner_id == owner_id
    
    def test_document_access_share_with_user(self, app):
        """Test sharing document with specific user."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            share_user_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='SHARED'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            doc_access.share_with_user(share_user_id, 'read')
            db.session.commit()
            
            retrieved = DocumentAccess.query.filter_by(
                document_id=doc_id
            ).first()
            assert retrieved.is_shared_with(share_user_id) is True
    
    def test_document_access_make_private(self, app):
        """Test making document private."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PUBLIC',
                shared_with=['user1', 'user2']
            )
            db.session.add(doc_access)
            db.session.commit()
            
            doc_access.make_private()
            db.session.commit()
            
            retrieved = DocumentAccess.query.filter_by(
                document_id=doc_id
            ).first()
            assert retrieved.access_level == 'PRIVATE'
            assert len(retrieved.shared_with) == 0
    
    def test_document_access_make_public(self, app):
        """Test making document public."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            doc_access.make_public()
            db.session.commit()
            
            retrieved = DocumentAccess.query.filter_by(
                document_id=doc_id
            ).first()
            assert retrieved.access_level == 'PUBLIC'
            assert 'read' in retrieved.default_permissions


class TestUserGroupModel:
    """Tests for UserGroup model."""
    
    def test_create_user_group(self, app):
        """Test creating a user group."""
        with app.app_context():
            group = UserGroup(
                name='test_group',
                description='A test group'
            )
            db.session.add(group)
            db.session.commit()
            
            retrieved = UserGroup.query.filter_by(name='test_group').first()
            assert retrieved is not None
            assert retrieved.name == 'test_group'
    
    def test_group_add_member(self, app):
        """Test adding member to group."""
        with app.app_context():
            user_id = str(uuid.uuid4())
            group = UserGroup(
                name='test_group'
            )
            db.session.add(group)
            db.session.commit()
            
            group.add_member(user_id)
            db.session.commit()
            
            retrieved = UserGroup.query.filter_by(name='test_group').first()
            assert retrieved.has_member(user_id) is True
    
    def test_group_has_member(self, app):
        """Test checking group membership."""
        with app.app_context():
            user_id = str(uuid.uuid4())
            other_user = str(uuid.uuid4())
            
            group = UserGroup(
                name='test_group',
                members=[user_id]
            )
            db.session.add(group)
            db.session.commit()
            
            assert group.has_member(user_id) is True
            assert group.has_member(other_user) is False


class TestBuiltinRoles:
    """Tests for built-in role definitions."""
    
    def test_builtin_roles_exist(self):
        """Test that all required built-in roles are defined."""
        required_roles = ['viewer', 'contributor', 'lead', 'admin']
        for role_name in required_roles:
            assert role_name in BUILTIN_ROLES
            role_def = BUILTIN_ROLES[role_name]
            assert 'permissions' in role_def
            assert len(role_def['permissions']) > 0
    
    def test_viewer_role_permissions(self):
        """Test viewer role has read-only permissions."""
        viewer = BUILTIN_ROLES['viewer']
        assert 'document:read' in viewer['permissions']
        assert 'code:read' in viewer['permissions']
        assert 'document:write' not in viewer['permissions']
    
    def test_admin_role_permissions(self):
        """Test admin role has all permissions."""
        admin = BUILTIN_ROLES['admin']
        # Admin should have very broad permissions
        has_admin_perms = any(
            'admin:' in perm or perm == '*:*'
            for perm in admin['permissions']
        )
        assert has_admin_perms


class TestPermissionConstants:
    """Tests for Permission string constants."""
    
    def test_permission_constants_exist(self):
        """Test that permission constants are defined."""
        required_perms = [
            'document:read', 'document:write', 'document:delete',
            'code:read', 'code:write', 'code:delete',
            'project:read', 'project:write', 'project:delete',
            'admin:roles', 'admin:users'
        ]
        for perm in required_perms:
            assert hasattr(Permission, perm.replace(':', '_').upper())

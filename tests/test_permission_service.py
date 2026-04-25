"""Unit tests for PermissionService - Phase 1.8.11"""
import pytest
import uuid
from datetime import datetime, timedelta
from app.database import db
from app.models.rbac import RBACRole, UserRole, DocumentAccess, UserGroup
from app.services.permission_service import PermissionService


class TestPermissionServiceBasic:
    """Tests for basic permission checking."""
    
    def test_user_has_permission_global_scope(self, app):
        """Test checking global scope permission."""
        with app.app_context():
            # Create role with permission
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_contributor',
                permissions=['document:write']
            )
            db.session.add(role)
            db.session.commit()
            
            # Assign role to user
            user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            # Test permission check
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is True
    
    def test_user_lacks_permission(self, app):
        """Test checking permission user doesn't have."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_viewer',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is False
    
    def test_user_no_roles(self, app):
        """Test user with no assigned roles."""
        with app.app_context():
            user_id = str(uuid.uuid4())
            
            assert PermissionService.user_has_permission(
                user_id, 'document:read', 'global'
            ) is False
    
    def test_permission_wildcard(self, app):
        """Test wildcard permission matching."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_admin',
                permissions=['*:*']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            # Wildcard should match any permission
            assert PermissionService.user_has_permission(
                user_id, 'anything:here', 'global'
            ) is True


class TestPermissionServiceScopes:
    """Tests for permission scoping."""
    
    def test_project_scope_permission(self, app):
        """Test project-scoped permission."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='project_contributor',
                permissions=['project:write']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            project_id = 123
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='project',
                scope_id=project_id
            )
            db.session.add(user_role)
            db.session.commit()
            
            # Should have permission in project
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', project_id
            ) is True
            
            # Should not have permission in different project
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', 999
            ) is False
    
    def test_multiple_roles_different_scopes(self, app):
        """Test user with roles in different scopes."""
        with app.app_context():
            # Global role
            global_role = RBACRole(
                id=str(uuid.uuid4()),
                name='global_viewer',
                permissions=['document:read']
            )
            db.session.add(global_role)
            
            # Project-specific role
            project_role = RBACRole(
                id=str(uuid.uuid4()),
                name='project_contributor',
                permissions=['project:write']
            )
            db.session.add(project_role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            project_id = 456
            
            # Assign both roles
            UserRole.query.delete()
            user_role_global = UserRole(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=global_role.id,
                scope='global'
            )
            user_role_project = UserRole(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=project_role.id,
                scope='project',
                scope_id=project_id
            )
            db.session.add(user_role_global)
            db.session.add(user_role_project)
            db.session.commit()
            
            # Test global permissions
            assert PermissionService.user_has_permission(
                user_id, 'document:read', 'global'
            ) is True
            
            # Test project permissions
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', project_id
            ) is True


class TestPermissionServiceExpiry:
    """Tests for permission expiration."""
    
    def test_expired_permission_not_granted(self, app):
        """Test that expired permissions are not granted."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='temp_role',
                permissions=['document:write']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            past = datetime.utcnow() - timedelta(days=1)
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global',
                expires_at=past
            )
            db.session.add(user_role)
            db.session.commit()
            
            # Expired permission should not be granted
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is False
    
    def test_future_expiry_permission_granted(self, app):
        """Test that permissions with future expiry are granted."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='temp_role',
                permissions=['document:write']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            future = datetime.utcnow() + timedelta(days=7)
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global',
                expires_at=future
            )
            db.session.add(user_role)
            db.session.commit()
            
            # Non-expired permission should be granted
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is True


class TestDocumentAccess:
    """Tests for document access control."""
    
    def test_owner_can_access_document(self, app):
        """Test that document owner can always access."""
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
            
            # Owner can access
            assert PermissionService.can_access_document(
                owner_id, doc_id, 'read'
            ) is True
    
    def test_non_owner_cannot_access_private_document(self, app):
        """Test that non-owner cannot access private document."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            other_user = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            # Non-owner cannot access
            assert PermissionService.can_access_document(
                other_user, doc_id, 'read'
            ) is False
    
    def test_can_access_public_document(self, app):
        """Test that anyone can access public document."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            other_user = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PUBLIC'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            # Anyone can access public document
            assert PermissionService.can_access_document(
                other_user, doc_id, 'read'
            ) is True
    
    def test_can_access_shared_document(self, app):
        """Test that shared users can access document."""
        with app.app_context():
            doc_id = str(uuid.uuid4())
            owner_id = str(uuid.uuid4())
            shared_user = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='SHARED'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            doc_access.share_with_user(shared_user, 'read')
            db.session.commit()
            
            # Shared user can access
            assert PermissionService.can_access_document(
                shared_user, doc_id, 'read'
            ) is True


class TestGetUserRoles:
    """Tests for retrieving user roles."""
    
    def test_get_user_roles_global(self, app):
        """Test retrieving global scope roles."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_viewer',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            roles = PermissionService.get_user_roles(user_id, 'global')
            assert len(roles) == 1
            assert roles[0].name == 'viewer'
    
    def test_get_user_roles_project_scope(self, app):
        """Test retrieving project scope roles."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_contributor',
                permissions=['project:write']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            project_id = 789
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='project',
                scope_id=project_id
            )
            db.session.add(user_role)
            db.session.commit()
            
            roles = PermissionService.get_user_roles(user_id, 'project', project_id)
            assert len(roles) == 1
            assert roles[0].name == 'contributor'
    
    def test_get_user_roles_includes_non_expired_only(self, app):
        """Test that expired roles are not returned."""
        with app.app_context():
            role1 = RBACRole(
                id=str(uuid.uuid4()),
                name='current',
                permissions=['document:read']
            )
            role2 = RBACRole(
                id=str(uuid.uuid4()),
                name='expired',
                permissions=['document:write']
            )
            db.session.add_all([role1, role2])
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            
            # Non-expired
            user_role1 = UserRole(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=role1.id,
                scope='global'
            )
            # Expired
            user_role2 = UserRole(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=role2.id,
                scope='global',
                expires_at=datetime.utcnow() - timedelta(days=1)
            )
            db.session.add_all([user_role1, user_role2])
            db.session.commit()
            
            roles = PermissionService.get_user_roles(user_id, 'global')
            # Should only return non-expired role
            assert len(roles) == 1
            assert roles[0].name == 'current'


class TestGetAllPermissions:
    """Tests for getting aggregated permissions."""
    
    def test_get_all_permissions_from_single_role(self, app):
        """Test getting permissions from single role."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_viewer',
                permissions=['document:read', 'code:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            perms = PermissionService.get_all_permissions(user_id, 'global')
            assert 'document:read' in perms
            assert 'code:read' in perms
    
    def test_get_all_permissions_from_multiple_roles(self, app):
        """Test getting permissions from multiple roles."""
        with app.app_context():
            role1 = RBACRole(
                id=str(uuid.uuid4()),
                name='reader',
                permissions=['document:read']
            )
            role2 = RBACRole(
                id=str(uuid.uuid4()),
                name='test_admin',
                permissions=['admin:roles', 'admin:users']
            )
            db.session.add_all([role1, role2])
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            user_role1 = UserRole(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=role1.id,
                scope='global'
            )
            user_role2 = UserRole(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=role2.id,
                scope='global'
            )
            db.session.add_all([user_role1, user_role2])
            db.session.commit()
            
            perms = PermissionService.get_all_permissions(user_id, 'global')
            assert 'document:read' in perms
            assert 'admin:roles' in perms
            assert 'admin:users' in perms





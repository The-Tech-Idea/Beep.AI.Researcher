"""Integration tests for RBAC API endpoints - Phase 1.8.11"""
import pytest
import json
from app.database import db
from app.models.rbac import RBACRole, UserRole


class TestRoleAdminAPI:
    """Tests for role management API endpoints."""
    
    def test_list_roles(self, client, app):
        """Test GET /admin/roles endpoint."""
        with app.app_context():
            # Seed a role
            role = RBACRole(
                name='test_role',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
        
        response = client.get(
            '/admin/roles',
            headers={'X-User-ID': 'admin-user'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'roles' in data
        assert isinstance(data['roles'], list)
    
    def test_create_role_requires_auth(self, client):
        """Test that creating role requires X-User-ID header."""
        response = client.post(
            '/admin/roles',
            json={'name': 'new_role', 'permissions': ['document:read']}
        )
        
        # Should return 401 without auth header
        assert response.status_code == 401
    
    def test_create_role_with_permission(self, client, app):
        """Test creating role with proper permission."""
        # This test assumes admin user has permission
        # In real scenario, need to set up admin role first
        
        with app.app_context():
            # Create admin role
            admin_role = RBACRole(
                name='admin',
                permissions=['admin:roles', '*:*']
            )
            db.session.add(admin_role)
            db.session.commit()
            
            admin_id = 'admin-user-id'
            user_role = UserRole(
                user_id=admin_id,
                role_id=admin_role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
        
        response = client.post(
            '/admin/roles',
            json={
                'name': 'custom_role',
                'description': 'Custom test role',
                'permissions': ['document:read', 'document:write']
            },
            headers={'X-User-ID': 'admin-user-id'}
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['role']['name'] == 'custom_role'
        assert 'document:read' in data['role']['permissions']
    
    def test_get_role_details(self, client, app):
        """Test GET /admin/roles/<role_id> endpoint."""
        with app.app_context():
            role = RBACRole(
                name='test_role',
                description='Test role',
                permissions=['document:read', 'document:write']
            )
            db.session.add(role)
            db.session.commit()
            role_id = role.id
        
        response = client.get(
            f'/admin/roles/{role_id}',
            headers={'X-User-ID': 'user-id'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['role']['name'] == 'test_role'
        assert len(data['role']['permissions']) == 2
    
    def test_delete_role_forbidden_for_builtin(self, client, app):
        """Test that built-in roles cannot be deleted."""
        with app.app_context():
            role = RBACRole(
                name='builtin_role',
                is_builtin=True,
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            role_id = role.id
        
        response = client.delete(
            f'/admin/roles/{role_id}',
            headers={'X-User-ID': 'admin-user'}
        )
        
        # Should return 409 for built-in role
        assert response.status_code in [400, 403, 409]


class TestUserRoleAdminAPI:
    """Tests for user role assignment API endpoints."""
    
    def test_list_user_roles(self, client, app):
        """Test GET /admin/users/<user_id>/roles endpoint."""
        with app.app_context():
            role = RBACRole(
                name='test_role',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            user_id = 'test-user-id'
            user_role = UserRole(
                user_id=user_id,
                role_id=role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
        
        response = client.get(
            '/admin/users/test-user-id/roles',
            headers={'X-User-ID': 'admin-user'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'assignments' in data
        assert len(data['assignments']) == 1
    
    def test_assign_role_to_user(self, client, app):
        """Test POST /admin/users/<user_id>/roles endpoint."""
        with app.app_context():
            # Create admin role
            admin_role = RBACRole(
                name='admin',
                permissions=['admin:users']
            )
            db.session.add(admin_role)
            db.session.commit()
            
            admin_id = 'admin-user-id'
            user_role = UserRole(
                user_id=admin_id,
                role_id=admin_role.id,
                scope='global'
            )
            db.session.add(user_role)
            
            # Create target role to assign
            target_role = RBACRole(
                name='contributor',
                permissions=['document:write']
            )
            db.session.add(target_role)
            db.session.commit()
            target_role_id = target_role.id
        
        response = client.post(
            '/admin/users/new-user-id/roles',
            json={
                'role_id': target_role_id,
                'scope': 'global'
            },
            headers={'X-User-ID': admin_id}
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'assignment' in data
    
    def test_cannot_assign_nonexistent_role(self, client, app):
        """Test that assigning non-existent role returns error."""
        with app.app_context():
            admin_role = RBACRole(
                name='admin',
                permissions=['admin:users']
            )
            db.session.add(admin_role)
            db.session.commit()
            
            admin_id = 'admin-user-id'
            user_role = UserRole(
                user_id=admin_id,
                role_id=admin_role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
        
        response = client.post(
            '/admin/users/new-user-id/roles',
            json={
                'role_id': 'nonexistent-role-id',
                'scope': 'global'
            },
            headers={'X-User-ID': admin_id}
        )
        
        assert response.status_code in [400, 404]


class TestDocumentAccessAPI:
    """Tests for document access control API endpoints."""
    
    def test_get_document_access(self, client, app):
        """Test GET /documents/<doc_id>/access endpoint."""
        from app.models.rbac import DocumentAccess
        import uuid
        
        with app.app_context():
            owner_id = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
        
        response = client.get(
            f'/documents/{doc_id}/access',
            headers={'X-User-ID': owner_id}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['access']['document_id'] == doc_id
        assert data['access']['access_level'] == 'PRIVATE'
    
    def test_make_document_public(self, client, app):
        """Test POST /documents/<doc_id>/access/make-public endpoint."""
        from app.models.rbac import DocumentAccess
        import uuid
        
        with app.app_context():
            owner_id = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
        
        response = client.post(
            f'/documents/{doc_id}/access/make-public',
            headers={'X-User-ID': owner_id}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['access']['access_level'] == 'PUBLIC'
    
    def test_make_document_private(self, client, app):
        """Test POST /documents/<doc_id>/access/make-private endpoint."""
        from app.models.rbac import DocumentAccess
        import uuid
        
        with app.app_context():
            owner_id = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PUBLIC'
            )
            db.session.add(doc_access)
            db.session.commit()
        
        response = client.post(
            f'/documents/{doc_id}/access/make-private',
            headers={'X-User-ID': owner_id}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['access']['access_level'] == 'PRIVATE'
    
    def test_share_document_with_user(self, client, app):
        """Test POST /documents/<doc_id>/access/share-user endpoint."""
        from app.models.rbac import DocumentAccess
        import uuid
        
        with app.app_context():
            owner_id = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())
            share_user_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
        
        response = client.post(
            f'/documents/{doc_id}/access/share-user',
            json={
                'user_id': share_user_id,
                'access_level': 'read'
            },
            headers={'X-User-ID': owner_id}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert share_user_id in data['access']['shared_with']
    
    def test_can_only_share_own_document(self, client, app):
        """Test that non-owner cannot share document."""
        from app.models.rbac import DocumentAccess
        import uuid
        
        with app.app_context():
            owner_id = str(uuid.uuid4())
            other_user = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())
            
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
        
        # Try to share as non-owner
        response = client.post(
            f'/documents/{doc_id}/access/share-user',
            json={
                'user_id': other_user,
                'access_level': 'read'
            },
            headers={'X-User-ID': other_user}
        )
        
        # Should return 403 Forbidden
        assert response.status_code == 403


class TestDecoratorIntegration:
    """Integration tests for permission decorators on routes."""
    
    def test_decorator_blocks_unauthorized_access(self, client, app):
        """Test that decorator blocks access without permission."""
        # Try to access admin endpoint without proper permission
        response = client.post(
            '/admin/roles',
            json={'name': 'test', 'permissions': ['document:read']},
            headers={'X-User-ID': 'regular-user'}
        )
        
        # Should return 403 Forbidden (no permission)
        assert response.status_code in [401, 403]
    
    def test_decorator_allows_authorized_access(self, client, app):
        """Test that decorator allows access with permission."""
        with app.app_context():
            # Create role with admin permission
            admin_role = RBACRole(
                name='admin',
                permissions=['admin:roles', 'admin:users']
            )
            db.session.add(admin_role)
            db.session.commit()
            
            admin_id = 'admin-user'
            user_role = UserRole(
                user_id=admin_id,
                role_id=admin_role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
        
        response = client.get(
            '/admin/roles',
            headers={'X-User-ID': 'admin-user'}
        )
        
        # Should succeed
        assert response.status_code == 200

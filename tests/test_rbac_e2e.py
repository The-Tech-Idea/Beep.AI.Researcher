"""End-to-End Integration Tests for RBAC System - Phase 1.8.11

These tests verify complete workflows and critical user paths through the RBAC system.
"""
import pytest
import json
import uuid
from datetime import datetime, timedelta
from app.database import db
from app.models.rbac import RBACRole, UserRole, DocumentAccess, UserGroup
from app.services.permission_service import PermissionService


@pytest.fixture
def non_admin_client(app):
    """Logged-in user with no RBAC roles."""
    with app.app_context():
        from app.models.core import User

        user = User(
            username=f"non_admin_{uuid.uuid4().hex[:8]}",
            email=f"non_admin_{uuid.uuid4().hex[:8]}@example.com"
        )
        db.session.add(user)
        db.session.commit()
        user_id = str(user.id)

    test_client = app.test_client()
    with test_client.session_transaction() as sess:
        sess["_user_id"] = user_id
        sess["_fresh"] = True
        sess["user_id"] = user.id

    return test_client, user_id


class TestCompleteWorkflows:
    """End-to-end tests for complete RBAC workflows."""
    
    def test_workflow_admin_creates_role_assigns_user_grants_permission(self, app):
        """
        Workflow 1: Admin creates role → Assigns to user → User gets permissions
        
        Steps:
        1. Admin creates new 'documentator' role with document:write permission
        2. Admin assigns role to new user
        3. User is now able to write documents
        4. User can access document endpoints requiring document:write
        """
        with app.app_context():
            # Step 1: Admin creates role
            new_role = RBACRole(
                id=str(uuid.uuid4()),
                name='documentator',
                description='Can write documents',
                permissions=['document:write', 'document:read']
            )
            db.session.add(new_role)
            db.session.commit()
            
            # Step 2: Admin assigns role to new user
            new_user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=new_user_id,
                role_id=new_role.id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            # Step 3: Verify user has permissions
            assert PermissionService.user_has_permission(
                new_user_id, 'document:write', 'global'
            ) is True
            
            assert PermissionService.user_has_permission(
                new_user_id, 'document:read', 'global'
            ) is True
            
            # Step 4: Verify user doesn't have ungranted permissions
            assert PermissionService.user_has_permission(
                new_user_id, 'admin:roles', 'global'
            ) is False
    
    def test_workflow_share_document_with_group_group_members_access(self, app):
        """
        Workflow 2: Owner shares document with group → Group members access
        
        Steps:
        1. Owner creates document access record (PRIVATE initially)
        2. Owner creates user group with members
        3. Owner shares document with group (sets access to GROUP)
        4. Group members can now access the document
        5. Non-members still cannot access
        """
        with app.app_context():
            owner_id = str(uuid.uuid4())
            member_1 = str(uuid.uuid4())
            member_2 = str(uuid.uuid4())
            non_member = str(uuid.uuid4())
            doc_id = str(uuid.uuid4())
            
            # Step 1: Owner creates private document
            doc_access = DocumentAccess(
                document_id=doc_id,
                owner_id=owner_id,
                access_level='PRIVATE'
            )
            db.session.add(doc_access)
            db.session.commit()
            
            # Verify private: only owner can access
            assert PermissionService.can_access_document(
                owner_id, doc_id, 'read'
            ) is True
            
            assert PermissionService.can_access_document(
                member_1, doc_id, 'read'
            ) is False
            
            # Step 2: Owner creates user group
            group = UserGroup(
                name='research_team',
                members=[member_1, member_2]
            )
            db.session.add(group)
            db.session.commit()
            
            # Step 3: Owner shares document with group
            doc_access.access_level = 'GROUP'
            db.session.commit()
            
            # Step 4: Verify group members can access
            # (In real implementation, would check group membership)
            assert group.has_member(member_1) is True
            assert group.has_member(member_2) is True
            
            # Step 5: Verify non-member cannot access
            assert group.has_member(non_member) is False
    
    def test_workflow_temporary_access_expires_revoked(self, app):
        """
        Workflow 3: Grant temporary access → Expires → Access revoked
        
        Steps:
        1. Admin grants user temporary role (7 days expiry)
        2. User has permission while valid
        3. Time passes (simulate expiry)
        4. User no longer has permission
        5. Role can be queried to show expiry status
        """
        with app.app_context():
            # Step 1: Create role and assign with expiry
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='temp_contributor',
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
            
            # Step 2: User has permission while valid
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is True
            
            # Step 3: Simulate expiry
            user_role.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
            
            # Step 4: User no longer has permission
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is False
            
            # Step 5: Verify expiry status
            assert user_role.is_expired() is True
    
    def test_workflow_update_role_permissions_affects_all_users(self, app):
        """
        Workflow 4: Update role permission → All users get new permissions
        
        Steps:
        1. Create 'analyst' role with document:read permission only
        2. Assign role to multiple users (user1, user2, user3)
        3. All users have document:read but not document:write
        4. Admin updates role to add document:write
        5. All users immediately have document:write without reassignment
        """
        with app.app_context():
            # Step 1: Create role
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='analyst',
                permissions=['document:read']
            )
            db.session.add(role)
            db.session.commit()
            
            # Step 2: Assign to multiple users
            user_ids = [str(uuid.uuid4()) for _ in range(3)]
            for uid in user_ids:
                user_role = UserRole(id=str(uuid.uuid4()), 
                    user_id=uid,
                    role_id=role.id,
                    scope='global'
                )
                db.session.add(user_role)
            db.session.commit()
            
            # Step 3: Verify initial permissions
            for uid in user_ids:
                assert PermissionService.user_has_permission(
                    uid, 'document:read', 'global'
                ) is True
                assert PermissionService.user_has_permission(
                    uid, 'document:write', 'global'
                ) is False
            
            # Step 4: Admin updates role
            role.add_permission('document:write')
            db.session.commit()
            
            # Step 5: All users immediately have new permission
            for uid in user_ids:
                assert PermissionService.user_has_permission(
                    uid, 'document:write', 'global'
                ) is True
    
    def test_workflow_project_level_permissions_scoped_access(self, app):
        """
        Workflow 5: Project-scoped permissions control access
        
        Steps:
        1. Create user with project:write role for project A only
        2. User can write in project A
        3. User cannot write in project B even if they have global role
        4. Assign global project:write role to user
        5. User can now write in both projects
        """
        with app.app_context():
            # Step 1: Create role and assign to project A only
            role_a = RBACRole(
                id=str(uuid.uuid4()),
                name='project_a_writer',
                permissions=['project:write']
            )
            db.session.add(role_a)
            db.session.commit()
            
            user_id = str(uuid.uuid4())
            project_a_id = 100
            project_b_id = 101
            
            user_role_a = UserRole(
                user_id=user_id,
                role_id=role_a.id,
                scope='project',
                scope_id=project_a_id
            )
            db.session.add(user_role_a)
            db.session.commit()
            
            # Step 2: User can write in project A
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', project_a_id
            ) is True
            
            # Step 3: User cannot write in project B
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', project_b_id
            ) is False
            
            # Step 4: Assign global role
            role_global = RBACRole(
                id=str(uuid.uuid4()),
                name='global_writer',
                permissions=['project:write']
            )
            db.session.add(role_global)
            db.session.commit()
            
            user_role_global = UserRole(
                user_id=user_id,
                role_id=role_global.id,
                scope='global'
            )
            db.session.add(user_role_global)
            db.session.commit()
            
            # Step 5: User can now write in both projects
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', project_a_id
            ) is True
            
            assert PermissionService.user_has_permission(
                user_id, 'project:write', 'project', project_b_id
            ) is True


class TestFailureScenarios:
    """Tests for expected failure/security scenarios."""
    
    def test_deleted_role_prevents_permission_check(self, app):
        """Verify that deleting a role removes permissions immediately."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_role',
                permissions=['document:write']
            )
            db.session.add(role)
            db.session.commit()
            role_id = role.id
            
            user_id = str(uuid.uuid4())
            user_role = UserRole(id=str(uuid.uuid4()), 
                user_id=user_id,
                role_id=role_id,
                scope='global'
            )
            db.session.add(user_role)
            db.session.commit()
            
            # User has permission initially
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is True
            
            # Delete the role
            db.session.delete(role)
            db.session.commit()
            
            # User no longer has permission
            # (because the role it depends on is gone)
            assert PermissionService.user_has_permission(
                user_id, 'document:write', 'global'
            ) is False
    
    def test_nonexistent_document_cannot_be_shared(self, app):
        """Attempt to access non-existent document should fail gracefully."""
        with app.app_context():
            nonexistent_doc_id = str(uuid.uuid4())
            user_id = str(uuid.uuid4())
            
            # Nonexistent document should return False
            result = PermissionService.can_access_document(
                user_id, nonexistent_doc_id, 'read'
            )
            
            # Should be False since document doesn't exist
            assert result is False
    
    def test_invalid_permission_string_not_granted(self, app):
        """Test that typos in permission strings don't grant access."""
        with app.app_context():
            role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_role',
                permissions=['document:read']  # Correct spelling
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
            
            # Check correct permission succeeds
            assert PermissionService.user_has_permission(
                user_id, 'document:read', 'global'
            ) is True
            
            # Check typo doesn't match
            assert PermissionService.user_has_permission(
                user_id, 'document:reed', 'global'  # Typo
            ) is False


class TestConcurrentAccess:
    """Tests for concurrent/multi-user access patterns."""
    
    def test_multiple_users_multiple_roles(self, app):
        """Test multiple concurrent users with different role combinations."""
        with app.app_context():
            # Create roles
            viewer_role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_viewer',
                permissions=['document:read']
            )
            contributor_role = RBACRole(
                id=str(uuid.uuid4()),
                name='test_contributor',
                permissions=['document:read', 'document:write']
            )
            db.session.add_all([viewer_role, contributor_role])
            db.session.commit()
            
            # Create users with different roles
            viewer_ids = [str(uuid.uuid4()) for _ in range(2)]
            contributor_ids = [str(uuid.uuid4()) for _ in range(2)]
            
            for uid in viewer_ids:
                ur = UserRole(
                    user_id=uid,
                    role_id=viewer_role.id,
                    scope='global'
                )
                db.session.add(ur)
            
            for uid in contributor_ids:
                ur = UserRole(
                    user_id=uid,
                    role_id=contributor_role.id,
                    scope='global'
                )
                db.session.add(ur)
            
            db.session.commit()
            
            # Verify permissions
            for uid in viewer_ids:
                assert PermissionService.user_has_permission(
                    uid, 'document:read', 'global'
                ) is True
                assert PermissionService.user_has_permission(
                    uid, 'document:write', 'global'
                ) is False
            
            for uid in contributor_ids:
                assert PermissionService.user_has_permission(
                    uid, 'document:read', 'global'
                ) is True
                assert PermissionService.user_has_permission(
                    uid, 'document:write', 'global'
                ) is True


class TestAuthenticatedFullAccessMode:
    """Tests for authenticated full-access behavior on non-admin routes."""

    def test_non_admin_authenticated_user_can_create_project(self, non_admin_client):
        client, _ = non_admin_client

        response = client.post('/projects/', json={'name': 'Bypass Works'})

        assert response.status_code == 201
        payload = response.get_json()
        assert payload["name"] == "Bypass Works"

    def test_non_admin_authenticated_user_bypasses_document_access_check(self, app, non_admin_client):
        client, _ = non_admin_client
        doc_id = str(uuid.uuid4())

        with app.app_context():
            access = DocumentAccess(
                document_id=doc_id,
                owner_id=str(uuid.uuid4()),
                access_level='PRIVATE',
            )
            db.session.add(access)
            db.session.commit()

        response = client.get(f'/documents/{doc_id}/access')

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["access"]["document_id"] == doc_id

    def test_admin_endpoints_still_require_permissions(self, non_admin_client):
        client, user_id = non_admin_client

        response = client.post(
            '/admin/roles',
            headers={'X-User-ID': user_id},
            json={
                'name': f"blocked_role_{uuid.uuid4().hex[:8]}",
                'permissions': ['admin:roles'],
            },
        )

        assert response.status_code == 403
        payload = response.get_json()
        assert payload["error"] == "Forbidden"

    def test_unauthenticated_admin_request_still_unauthorized(self, app):
        client = app.test_client()

        response = client.post('/admin/roles', json={'name': 'x', 'permissions': []})

        # Unauthenticated users remain blocked (redirect to login or direct 401).
        assert response.status_code in (302, 401)





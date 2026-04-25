"""Tests for plugin permissions system (Phase 4.1)."""
import pytest
import uuid
from datetime import datetime, timedelta
from app.models.researcher.plugin_permissions import (
    PluginPermission, PluginRoleAssignment, PluginAudit, AccessLevel,
    get_user_plugin_access_level
)
from app.models.researcher.plugins import Plugin, PluginConfiguration
from app.models.core import User
from app.models.rbac import RBACRole
from app.services.plugin_permissions import PluginPermissionService
from app.database import db


class TestAccessLevel:
    """Tests for AccessLevel enum."""
    
    def test_access_level_values(self):
        """Test AccessLevel enum values."""
        assert AccessLevel.NONE.value == 0
        assert AccessLevel.READ.value == 1
        assert AccessLevel.EXECUTE.value == 2
        assert AccessLevel.CONFIGURE.value == 3
        assert AccessLevel.ADMIN.value == 4
    
    def test_access_level_comparison(self):
        """Test AccessLevel comparison operators."""
        assert AccessLevel.NONE < AccessLevel.READ
        assert AccessLevel.READ < AccessLevel.EXECUTE
        assert AccessLevel.EXECUTE < AccessLevel.CONFIGURE
        assert AccessLevel.CONFIGURE < AccessLevel.ADMIN
        assert AccessLevel.ADMIN >= AccessLevel.EXECUTE


class TestPluginPermissionModel:
    """Tests for PluginPermission model."""
    
    @pytest.fixture
    def test_data(self):
        """Create test data."""
        plugin = Plugin(
            name='test_plugin',
            enabled=True,
            created_by=1,
            description='Test plugin'
        )
        db.session.add(plugin)
        db.session.flush()
        
        role = RBACRole(id=str(uuid.uuid4()), name='test_role')
        db.session.add(role)
        db.session.flush()
        
        yield {'plugin': plugin, 'role': role}
        
        db.session.delete(plugin)
        db.session.delete(role)
        db.session.commit()
    
    def test_create_permission(self, test_data):
        """Test creating a plugin permission."""
        permission = PluginPermission(
            plugin_id=test_data['plugin'].id,
            role_id=test_data['role'].id,
            can_execute=True,
            can_configure=False,
            can_view_logs=True,
            can_test=True
        )
        db.session.add(permission)
        db.session.commit()
        
        assert permission.id is not None
        assert permission.can_execute is True
        assert permission.can_configure is False
        assert permission.can_view_logs is True
        assert permission.can_test is True
        
        db.session.delete(permission)
        db.session.commit()
    
    def test_permission_to_dict(self, test_data):
        """Test permission serialization."""
        permission = PluginPermission(
            plugin_id=test_data['plugin'].id,
            role_id=test_data['role'].id,
            can_execute=True,
            can_configure=False,
            created_by=1
        )
        db.session.add(permission)
        db.session.commit()
        
        perm_dict = permission.to_dict()
        
        assert perm_dict['plugin_id'] == test_data['plugin'].id
        assert perm_dict['role_id'] == test_data['role'].id
        assert perm_dict['can_execute'] is True
        assert perm_dict['can_configure'] is False
        assert 'created_at' in perm_dict
        
        db.session.delete(permission)
        db.session.commit()


class TestPluginRoleAssignment:
    """Tests for PluginRoleAssignment model."""
    
    @pytest.fixture
    def test_data(self):
        """Create test data."""
        user = User(username='test_user', email='test@example.com')
        db.session.add(user)
        db.session.flush()
        
        plugin = Plugin(
            name='test_plugin',
            enabled=True,
            created_by=1,
            description='Test plugin'
        )
        db.session.add(plugin)
        db.session.flush()
        
        yield {'user': user, 'plugin': plugin}
        
        db.session.delete(user)
        db.session.delete(plugin)
        db.session.commit()
    
    def test_create_assignment(self, test_data):
        """Test creating a user-level assignment."""
        assignment = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE,
            reason='Clinical trial'
        )
        db.session.add(assignment)
        db.session.commit()
        
        assert assignment.id is not None
        assert assignment.access_level == AccessLevel.EXECUTE
        assert assignment.reason == 'Clinical trial'
        assert not assignment.is_expired()
        
        db.session.delete(assignment)
        db.session.commit()
    
    def test_assignment_expiry(self, test_data):
        """Test assignment expiry check."""
        past_date = datetime.utcnow() - timedelta(days=1)
        future_date = datetime.utcnow() + timedelta(days=30)
        
        # Expired assignment
        expired = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE,
            expiry_date=past_date
        )
        db.session.add(expired)
        db.session.commit()
        
        assert expired.is_expired()
        
        # Valid assignment
        valid = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE,
            expiry_date=future_date
        )
        db.session.add(valid)
        db.session.commit()
        
        assert not valid.is_expired()
        
        db.session.delete(expired)
        db.session.delete(valid)
        db.session.commit()
    
    def test_get_access_level_name(self, test_data):
        """Test access level name retrieval."""
        assignment = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.CONFIGURE
        )
        db.session.add(assignment)
        db.session.commit()
        
        assert assignment.get_access_level_name() == 'CONFIGURE'
        
        db.session.delete(assignment)
        db.session.commit()
    
    def test_assignment_to_dict(self, test_data):
        """Test assignment serialization."""
        assignment = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE,
            reason='Test reason',
            assigned_by=1
        )
        db.session.add(assignment)
        db.session.commit()
        
        assign_dict = assignment.to_dict()
        
        assert assign_dict['user_id'] == test_data['user'].id
        assert assign_dict['plugin_id'] == test_data['plugin'].id
        assert assign_dict['access_level'] == AccessLevel.EXECUTE
        assert assign_dict['access_level_name'] == 'EXECUTE'
        assert assign_dict['reason'] == 'Test reason'
        assert 'created_at' in assign_dict
        
        db.session.delete(assignment)
        db.session.commit()


class TestPluginAuditModel:
    """Tests for PluginAudit model."""
    
    @pytest.fixture
    def test_data(self):
        """Create test data."""
        user = User(username='test_user', email='test@example.com')
        db.session.add(user)
        db.session.flush()
        
        plugin = Plugin(
            name='test_plugin',
            enabled=True,
            created_by=1,
            description='Test plugin'
        )
        db.session.add(plugin)
        db.session.flush()
        
        yield {'user': user, 'plugin': plugin}
        
        db.session.delete(user)
        db.session.delete(plugin)
        db.session.commit()
    
    def test_create_audit_log(self, test_data):
        """Test creating an audit log entry."""
        audit = PluginAudit(
            plugin_id=test_data['plugin'].id,
            user_id=test_data['user'].id,
            action='execute',
            success=True,
            ip_address='192.168.1.1',
            execution_time_ms=150.5
        )
        db.session.add(audit)
        db.session.commit()
        
        assert audit.id is not None
        assert audit.action == 'execute'
        assert audit.success is True
        assert audit.execution_time_ms == 150.5
        
        db.session.delete(audit)
        db.session.commit()
    
    def test_audit_failure_logging(self, test_data):
        """Test logging failed actions."""
        audit = PluginAudit(
            plugin_id=test_data['plugin'].id,
            user_id=test_data['user'].id,
            action='configure',
            success=False,
            error_message='Insufficient permissions'
        )
        db.session.add(audit)
        db.session.commit()
        
        assert audit.success is False
        assert audit.error_message == 'Insufficient permissions'
        
        db.session.delete(audit)
        db.session.commit()
    
    def test_audit_to_dict(self, test_data):
        """Test audit log serialization."""
        audit = PluginAudit(
            plugin_id=test_data['plugin'].id,
            user_id=test_data['user'].id,
            action='execute',
            success=True,
            ip_address='10.0.0.1',
            execution_time_ms=200.0
        )
        db.session.add(audit)
        db.session.commit()
        
        audit_dict = audit.to_dict()
        
        assert audit_dict['plugin_id'] == test_data['plugin'].id
        assert audit_dict['user_id'] == test_data['user'].id
        assert audit_dict['action'] == 'execute'
        assert audit_dict['success'] is True
        assert 'timestamp' in audit_dict
        
        db.session.delete(audit)
        db.session.commit()


class TestGetUserPluginAccessLevel:
    """Tests for get_user_plugin_access_level helper function."""
    
    @pytest.fixture
    def test_data(self):
        """Create test data."""
        user = User(username='test_user', email='test@example.com')
        db.session.add(user)
        db.session.flush()
        
        role = RBACRole(id=str(uuid.uuid4()), name='test_role')
        db.session.add(role)
        db.session.flush()
        
        user_role = UserRole(user_id=user.id, role_id=role.id)
        db.session.add(user_role)
        
        plugin = Plugin(
            name='test_plugin',
            enabled=True,
            created_by=1,
            description='Test plugin'
        )
        db.session.add(plugin)
        db.session.flush()
        
        db.session.commit()
        
        yield {'user': user, 'role': role, 'plugin': plugin}
        
        db.session.delete(user_role)
        db.session.delete(user)
        db.session.delete(role)
        db.session.delete(plugin)
        db.session.commit()
    
    def test_user_access_from_role_permission(self, test_data):
        """Test user access derived from role permission."""
        permission = PluginPermission(
            plugin_id=test_data['plugin'].id,
            role_id=test_data['role'].id,
            can_execute=True,
            can_view_logs=True
        )
        db.session.add(permission)
        db.session.commit()
        
        access = get_user_plugin_access_level(test_data['user'].id, test_data['plugin'].id)
        assert access == AccessLevel.EXECUTE
        
        db.session.delete(permission)
        db.session.commit()
    
    def test_user_access_from_direct_assignment(self, test_data):
        """Test user access from direct assignment overrides roles."""
        # Create role permission
        permission = PluginPermission(
            plugin_id=test_data['plugin'].id,
            role_id=test_data['role'].id,
            can_execute=True
        )
        db.session.add(permission)
        db.session.commit()
        
        # Create direct assignment with higher access
        assignment = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.CONFIGURE
        )
        db.session.add(assignment)
        db.session.commit()
        
        # Direct assignment should override role-based
        access = get_user_plugin_access_level(test_data['user'].id, test_data['plugin'].id)
        assert access == AccessLevel.CONFIGURE
        
        db.session.delete(assignment)
        db.session.delete(permission)
        db.session.commit()
    
    def test_user_no_access(self, test_data):
        """Test user with no access."""
        access = get_user_plugin_access_level(test_data['user'].id, test_data['plugin'].id)
        assert access == AccessLevel.NONE


class TestPluginPermissionService:
    """Tests for PluginPermissionService."""
    
    @pytest.fixture
    def test_data(self):
        """Create test data."""
        user = User(username='test_user', email='test@example.com')
        db.session.add(user)
        db.session.flush()
        
        plugin = Plugin(
            name='test_plugin',
            enabled=True,
            created_by=1,
            description='Test plugin'
        )
        db.session.add(plugin)
        db.session.flush()
        
        role = RBACRole(id=str(uuid.uuid4()), name='test_role')
        db.session.add(role)
        db.session.flush()
        
        db.session.commit()
        
        yield {'user': user, 'plugin': plugin, 'role': role}
        
        db.session.delete(user)
        db.session.delete(plugin)
        db.session.delete(role)
        db.session.commit()
    
    def test_grant_permission(self, test_data):
        """Test granting permission to a role."""
        success, message, permission = PluginPermissionService.grant_permission(
            plugin_id=test_data['plugin'].id,
            role_id=test_data['role'].id,
            can_execute=True,
            can_view_logs=True
        )
        
        assert success is True
        assert permission is not None
        assert permission.can_execute is True
        
        db.session.delete(permission)
        db.session.commit()
    
    def test_grant_permission_invalid_plugin(self):
        """Test granting permission with invalid plugin."""
        success, message, permission = PluginPermissionService.grant_permission(
            plugin_id=99999,
            role_id=1
        )
        
        assert success is False
        assert 'not found' in message
    
    def test_revoke_permission(self, test_data):
        """Test revoking permission."""
        # Create permission first
        permission = PluginPermission(
            plugin_id=test_data['plugin'].id,
            role_id=test_data['role'].id,
            can_execute=True
        )
        db.session.add(permission)
        db.session.commit()
        perm_id = permission.id
        
        # Revoke it
        success, message = PluginPermissionService.revoke_permission(
            test_data['plugin'].id,
            test_data['role'].id
        )
        
        assert success is True
        assert db.session.get(PluginPermission, perm_id) is None
    
    def test_assign_user_access(self, test_data):
        """Test assigning direct user access."""
        success, message, assignment = PluginPermissionService.assign_user_access(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE,
            reason='Testing'
        )
        
        assert success is True
        assert assignment is not None
        assert assignment.access_level == AccessLevel.EXECUTE
        
        db.session.delete(assignment)
        db.session.commit()
    
    def test_assign_user_access_with_expiry(self, test_data):
        """Test assigning access with expiry date."""
        future_date = datetime.utcnow() + timedelta(days=30)
        
        success, message, assignment = PluginPermissionService.assign_user_access(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.CONFIGURE,
            expiry_date=future_date
        )
        
        assert success is True
        assert assignment.expiry_date is not None
        assert not assignment.is_expired()
        
        db.session.delete(assignment)
        db.session.commit()
    
    def test_revoke_user_access(self, test_data):
        """Test revoking user access."""
        # Create assignment first
        assignment = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE
        )
        db.session.add(assignment)
        db.session.commit()
        assign_id = assignment.id
        
        # Revoke it
        success, message = PluginPermissionService.revoke_user_access(
            test_data['user'].id,
            test_data['plugin'].id
        )
        
        assert success is True
        assert db.session.get(PluginRoleAssignment, assign_id) is None
    
    def test_check_user_access(self, test_data):
        """Test checking user access for action."""
        assignment = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE
        )
        db.session.add(assignment)
        db.session.commit()
        
        # User should have execute access
        has_access, message, level = PluginPermissionService.check_user_access(
            test_data['user'].id,
            test_data['plugin'].id,
            'execute'
        )
        
        assert has_access is True
        assert level == AccessLevel.EXECUTE
        
        # User should not have configure access
        has_access, message, level = PluginPermissionService.check_user_access(
            test_data['user'].id,
            test_data['plugin'].id,
            'configure'
        )
        
        assert has_access is False
        
        db.session.delete(assignment)
        db.session.commit()
    
    def test_get_audit_logs(self, test_data):
        """Test retrieving audit logs."""
        # Create some audit logs
        for i in range(5):
            audit = PluginAudit(
                plugin_id=test_data['plugin'].id,
                user_id=test_data['user'].id,
                action='execute',
                success=True
            )
            db.session.add(audit)
        db.session.commit()
        
        success, message, logs = PluginPermissionService.get_audit_logs(
            plugin_id=test_data['plugin'].id
        )
        
        assert success is True
        assert len(logs) >= 5
        
        # Clean up
        PluginAudit.query.delete()
        db.session.commit()
    
    def test_cleanup_expired_assignments(self, test_data):
        """Test cleaning up expired assignments."""
        past = datetime.utcnow() - timedelta(days=1)
        future = datetime.utcnow() + timedelta(days=30)
        
        # Create expired assignment
        expired = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.EXECUTE,
            expiry_date=past
        )
        db.session.add(expired)
        
        # Create valid assignment
        valid = PluginRoleAssignment(
            user_id=test_data['user'].id,
            plugin_id=test_data['plugin'].id,
            access_level=AccessLevel.READ,
            expiry_date=future
        )
        db.session.add(valid)
        db.session.commit()
        
        expired_id = expired.id
        valid_id = valid.id
        
        success, message, deleted_count = PluginPermissionService.cleanup_expired_assignments()
        
        assert success is True
        assert deleted_count >= 1
        assert db.session.get(PluginRoleAssignment, expired_id) is None
        assert db.session.get(PluginRoleAssignment, valid_id) is not None
        
        db.session.delete(valid)
        db.session.commit()




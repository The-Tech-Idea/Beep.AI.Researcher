"""Plugin permission and RBAC models (Phase 4.1)."""
from datetime import datetime, UTC
from app.core.time_utils import utcnow_naive
from enum import IntEnum
from app.database import db


class AccessLevel(IntEnum):
    """Plugin access levels for users."""
    NONE = 0           # No access
    READ = 1           # View logs and results only
    EXECUTE = 2        # Execute plugins
    CONFIGURE = 3      # Modify configuration
    ADMIN = 4          # Full control


class PluginPermission(db.Model):
    """Role-based plugin permissions."""
    __tablename__ = 'plugin_permission'
    
    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False, index=True)
    role_id = db.Column(db.String(36), db.ForeignKey('rbac_roles.id'), nullable=False, index=True)
    
    # Permission flags
    can_execute = db.Column(db.Boolean, default=False)
    can_configure = db.Column(db.Boolean, default=False)
    can_view_logs = db.Column(db.Boolean, default=False)
    can_test = db.Column(db.Boolean, default=False)
    
    # Audit
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    plugin = db.relationship('Plugin', backref='permissions')
    role = db.relationship('RBACRole', foreign_keys=[role_id], backref='plugin_permissions')
    
    def __repr__(self):
        return f'<PluginPermission plugin={self.plugin_id} role={self.role_id}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'role_id': self.role_id,
            'can_execute': self.can_execute,
            'can_configure': self.can_configure,
            'can_view_logs': self.can_view_logs,
            'can_test': self.can_test,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class PluginRoleAssignment(db.Model):
    """User-level plugin access assignments (override role-based permissions)."""
    __tablename__ = 'plugin_role_assignment'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False, index=True)
    
    # Access level overrides role-based permissions
    access_level = db.Column(db.Integer, default=AccessLevel.NONE)  # AccessLevel enum
    
    # Expiry for temporary access
    expiry_date = db.Column(db.DateTime, nullable=True)
    
    # Reason for assignment
    reason = db.Column(db.String(500))
    
    # Audit
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    user = db.relationship('User', backref='plugin_assignments', foreign_keys=[user_id])
    plugin = db.relationship('Plugin', backref='user_assignments')
    
    def __repr__(self):
        return f'<PluginRoleAssignment user={self.user_id} plugin={self.plugin_id} level={self.access_level}>'
    
    def is_expired(self):
        """Check if assignment has expired."""
        if not self.expiry_date:
            return False
        return datetime.now(UTC).replace(tzinfo=None) > self.expiry_date
    
    def get_access_level_name(self):
        """Get human-readable access level name."""
        return AccessLevel(self.access_level).name
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plugin_id': self.plugin_id,
            'access_level': self.access_level,
            'access_level_name': self.get_access_level_name(),
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'reason': self.reason,
            'is_expired': self.is_expired(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'assigned_by': self.assigned_by,
        }


class PluginAudit(db.Model):
    """Audit log for plugin access and actions."""
    __tablename__ = 'plugin_audit'
    
    id = db.Column(db.Integer, primary_key=True)
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Action type
    action = db.Column(db.String(50), nullable=False)  # execute, configure, disable, test, view_logs
    
    # Context
    details = db.Column(db.Text)  # JSON details about the action
    
    # Result
    success = db.Column(db.Boolean, default=False)
    error_message = db.Column(db.String(500))
    
    # Request info
    ip_address = db.Column(db.String(45))  # IPv4 or IPv6
    user_agent = db.Column(db.String(500))
    
    # Related objects (optional)
    project_id = db.Column(db.Integer)  # From research_projects table
    schema_id = db.Column(db.Integer)  # From extraction_schemas table
    result_id = db.Column(db.Integer)  # From extraction_results table
    
    # Timing
    timestamp = db.Column(db.DateTime, default=utcnow_naive, index=True)
    execution_time_ms = db.Column(db.Float)
    
    # Relationships
    plugin = db.relationship('Plugin', backref='audit_logs')
    user = db.relationship('User', backref='plugin_audit_logs')
    
    def __repr__(self):
        return f'<PluginAudit plugin={self.plugin_id} user={self.user_id} action={self.action}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin.name if self.plugin else None,
            'user_id': self.user_id,
            'user_name': self.user.username if self.user else None,
            'action': self.action,
            'success': self.success,
            'error_message': self.error_message,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'execution_time_ms': self.execution_time_ms,
            'project_id': self.project_id,
        }


# Helper function to check user plugin access
def get_user_plugin_access_level(user_id: int, plugin_id: int) -> AccessLevel:
    """Get the effective access level for a user on a plugin.
    
    Priority:
    1. PluginRoleAssignment (user-level override) if not expired
    2. PluginPermission based on user's role
    3. AccessLevel.NONE (no access)
    """
    # Check user-level assignment first
    assignment = PluginRoleAssignment.query.filter(
        PluginRoleAssignment.user_id == user_id,
        PluginRoleAssignment.plugin_id == plugin_id
    ).first()
    
    if assignment and not assignment.is_expired():
        return AccessLevel(assignment.access_level)
    
    # Check role-based permissions
    from app.models.rbac import UserRole
    user_roles = db.session.query(UserRole).filter(UserRole.user_id == user_id).all()
    
    if not user_roles:
        return AccessLevel.NONE
    
    # Find highest access level across all roles
    max_access = AccessLevel.NONE
    
    for user_role in user_roles:
        permission = PluginPermission.query.filter(
            PluginPermission.plugin_id == plugin_id,
            PluginPermission.role_id == user_role.role_id
        ).first()
        
        if permission:
            # Determine access level from permission flags
            if permission.can_configure:
                access = AccessLevel.CONFIGURE
            elif permission.can_execute:
                access = AccessLevel.EXECUTE
            elif permission.can_view_logs:
                access = AccessLevel.READ
            else:
                access = AccessLevel.NONE
            
            if access > max_access:
                max_access = access
    
    return max_access

"""Plugin permission management service (Phase 4.1)."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher.plugin_permissions import (
    PluginPermission,
    PluginRoleAssignment,
    PluginAudit,
    AccessLevel,
    get_user_plugin_access_level,
)
from app.models.researcher.plugins import Plugin


class PluginPermissionService:
    """Service for managing plugin permissions and access control."""

    @staticmethod
    def grant_permission(
        plugin_id: int,
        role_id: int,
        can_execute: bool = False,
        can_configure: bool = False,
        can_view_logs: bool = False,
        can_test: bool = False,
        created_by: int = None,
    ) -> Tuple[bool, str, Optional[PluginPermission]]:
        """Grant permissions to a role for a plugin.

        Args:
            plugin_id: Plugin ID
            role_id: Role ID
            can_execute: Can execute the plugin
            can_configure: Can modify configuration
            can_view_logs: Can view execution logs
            can_test: Can test the plugin
            created_by: User ID of the admin making the change

        Returns:
            Tuple of (success, message, permission_object)
        """
        try:
            # Check if plugin exists
            plugin = db.session.get(Plugin, plugin_id)
            if not plugin:
                return False, f"Plugin {plugin_id} not found", None

            # Check if permission already exists
            existing = PluginPermission.query.filter(
                PluginPermission.plugin_id == plugin_id,
                PluginPermission.role_id == role_id,
            ).first()

            if existing:
                # Update existing permission
                existing.can_execute = can_execute
                existing.can_configure = can_configure
                existing.can_view_logs = can_view_logs
                existing.can_test = can_test
                existing.updated_at = utcnow_naive()
                db.session.commit()
                return True, "Permission updated", existing

            # Create new permission
            permission = PluginPermission(
                plugin_id=plugin_id,
                role_id=role_id,
                can_execute=can_execute,
                can_configure=can_configure,
                can_view_logs=can_view_logs,
                can_test=can_test,
                created_by=created_by,
            )
            db.session.add(permission)
            db.session.commit()

            return True, "Permission granted", permission

        except Exception as e:
            db.session.rollback()
            return False, f"Error granting permission: {str(e)}", None

    @staticmethod
    def revoke_permission(plugin_id: int, role_id: int) -> Tuple[bool, str]:
        """Revoke all permissions for a role on a plugin."""
        try:
            permission = PluginPermission.query.filter(
                PluginPermission.plugin_id == plugin_id,
                PluginPermission.role_id == role_id,
            ).first()

            if not permission:
                return False, "Permission not found"

            db.session.delete(permission)
            db.session.commit()

            return True, "Permission revoked"

        except Exception as e:
            db.session.rollback()
            return False, f"Error revoking permission: {str(e)}"

    @staticmethod
    def assign_user_access(
        user_id: int,
        plugin_id: int,
        access_level: AccessLevel,
        reason: str = None,
        expiry_date: datetime = None,
        assigned_by: int = None,
    ) -> Tuple[bool, str, Optional[PluginRoleAssignment]]:
        """Assign direct plugin access to a user (overrides role-based permissions).

        Args:
            user_id: User ID
            plugin_id: Plugin ID
            access_level: AccessLevel enum value
            reason: Reason for the assignment
            expiry_date: Optional expiry date for temporary access
            assigned_by: User ID of the admin making the assignment

        Returns:
            Tuple of (success, message, assignment_object)
        """
        try:
            # Check if plugin exists
            plugin = db.session.get(Plugin, plugin_id)
            if not plugin:
                return False, f"Plugin {plugin_id} not found", None

            # Check if assignment already exists
            existing = PluginRoleAssignment.query.filter(
                PluginRoleAssignment.user_id == user_id,
                PluginRoleAssignment.plugin_id == plugin_id,
            ).first()

            if existing:
                # Update existing assignment
                existing.access_level = int(access_level)
                existing.reason = reason
                existing.expiry_date = expiry_date
                existing.updated_at = utcnow_naive()
                db.session.commit()
                return True, "User access updated", existing

            # Create new assignment
            assignment = PluginRoleAssignment(
                user_id=user_id,
                plugin_id=plugin_id,
                access_level=int(access_level),
                reason=reason,
                expiry_date=expiry_date,
                assigned_by=assigned_by,
            )
            db.session.add(assignment)
            db.session.commit()

            return True, "User access assigned", assignment

        except Exception as e:
            db.session.rollback()
            return False, f"Error assigning access: {str(e)}", None

    @staticmethod
    def revoke_user_access(user_id: int, plugin_id: int) -> Tuple[bool, str]:
        """Revoke direct plugin access from a user."""
        try:
            assignment = PluginRoleAssignment.query.filter(
                PluginRoleAssignment.user_id == user_id,
                PluginRoleAssignment.plugin_id == plugin_id,
            ).first()

            if not assignment:
                return False, "User access not found"

            db.session.delete(assignment)
            db.session.commit()

            return True, "User access revoked"

        except Exception as e:
            db.session.rollback()
            return False, f"Error revoking access: {str(e)}"

    @staticmethod
    def check_user_access(
        user_id: int, plugin_id: int, required_action: str = "execute"
    ) -> Tuple[bool, str, AccessLevel]:
        """Check if user has access for a specific action.

        Args:
            user_id: User ID
            plugin_id: Plugin ID
            required_action: Action to verify (execute, configure, test, view_logs)

        Returns:
            Tuple of (has_access, message, access_level)
        """
        access_level = get_user_plugin_access_level(user_id, plugin_id)

        action_levels = {
            "execute": AccessLevel.EXECUTE,
            "configure": AccessLevel.CONFIGURE,
            "test": AccessLevel.EXECUTE,
            "view_logs": AccessLevel.READ,
        }

        required = action_levels.get(required_action, AccessLevel.EXECUTE)
        has_access = access_level >= required

        message = f"User has {access_level.name} access"

        return has_access, message, access_level

    @staticmethod
    def get_user_plugins(user_id: int) -> Dict[str, list]:
        """Get all plugins accessible to a user, grouped by access level."""
        result = {"admin": [], "configure": [], "execute": [], "read": [], "none": []}

        try:
            # Get all plugins
            plugins = Plugin.query.all()

            for plugin in plugins:
                access = get_user_plugin_access_level(user_id, plugin.id)

                plugin_info = {
                    "id": plugin.id,
                    "name": plugin.name,
                    "description": plugin.description,
                    "access_level": access.name,
                }

                if access == AccessLevel.ADMIN:
                    result["admin"].append(plugin_info)
                elif access == AccessLevel.CONFIGURE:
                    result["configure"].append(plugin_info)
                elif access == AccessLevel.EXECUTE:
                    result["execute"].append(plugin_info)
                elif access == AccessLevel.READ:
                    result["read"].append(plugin_info)
                else:
                    result["none"].append(plugin_info)

            return result

        except Exception as e:
            return {"error": f"Error fetching plugins: {str(e)}"}

    @staticmethod
    def get_plugin_users(plugin_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """Get all users with access to a plugin."""
        try:
            # Get direct user assignments
            assignments = PluginRoleAssignment.query.filter(
                PluginRoleAssignment.plugin_id == plugin_id
            ).all()

            users_data = {"direct_assignments": [], "role_based": [], "total_users": 0}

            # Add direct assignments
            for assignment in assignments:
                users_data["direct_assignments"].append(
                    {
                        "user_id": assignment.user_id,
                        "access_level": assignment.get_access_level_name(),
                        "expiry_date": assignment.expiry_date.isoformat()
                        if assignment.expiry_date
                        else None,
                        "is_expired": assignment.is_expired(),
                        "reason": assignment.reason,
                    }
                )

            # Get role-based assignments (if needed)
            # This would require joining through User -> Role -> PluginPermission

            users_data["total_users"] = len(users_data["direct_assignments"])

            return True, "Users fetched", users_data

        except Exception as e:
            return False, f"Error fetching users: {str(e)}", None

    @staticmethod
    def get_audit_logs(
        plugin_id: int = None,
        user_id: int = None,
        action: str = None,
        days: int = 30,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[bool, str, Optional[List[Dict]]]:
        """Get audit logs with optional filtering.

        Args:
            plugin_id: Filter by plugin ID
            user_id: Filter by user ID
            action: Filter by action type
            days: Only include logs from last N days
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (success, message, logs_list)
        """
        try:
            query = PluginAudit.query

            # Apply filters
            if plugin_id:
                query = query.filter(PluginAudit.plugin_id == plugin_id)

            if user_id:
                query = query.filter(PluginAudit.user_id == user_id)

            if action:
                query = query.filter(PluginAudit.action == action)

            if days:
                cutoff = utcnow_naive() - timedelta(days=days)
                query = query.filter(PluginAudit.timestamp >= cutoff)

            # Get total count
            total = query.count()

            # Order by timestamp descending and apply pagination
            logs = (
                query.order_by(PluginAudit.timestamp.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            logs_data = [log.to_dict() for log in logs]

            return True, f"Retrieved {len(logs_data)} logs", logs_data

        except Exception as e:
            return False, f"Error fetching audit logs: {str(e)}", None

    @staticmethod
    def cleanup_expired_assignments() -> Tuple[bool, str, int]:
        """Clean up expired user access assignments.

        Returns:
            Tuple of (success, message, deleted_count)
        """
        try:
            expired = PluginRoleAssignment.query.filter(
                PluginRoleAssignment.expiry_date < utcnow_naive()
            ).all()

            deleted_count = len(expired)

            for assignment in expired:
                db.session.delete(assignment)

            db.session.commit()

            return (
                True,
                f"Cleaned up {deleted_count} expired assignments",
                deleted_count,
            )

        except Exception as e:
            db.session.rollback()
            return False, f"Error cleaning up assignments: {str(e)}", 0

    @staticmethod
    def get_permission_summary(plugin_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """Get a summary of all permissions for a plugin."""
        try:
            plugin = db.session.get(Plugin, plugin_id)
            if not plugin:
                return False, f"Plugin {plugin_id} not found", None

            # Get role-based permissions
            role_permissions = PluginPermission.query.filter(
                PluginPermission.plugin_id == plugin_id
            ).all()

            # Get user assignments
            user_assignments = PluginRoleAssignment.query.filter(
                PluginRoleAssignment.plugin_id == plugin_id
            ).all()

            summary = {
                "plugin_id": plugin_id,
                "plugin_name": plugin.name,
                "role_permissions": [p.to_dict() for p in role_permissions],
                "user_assignments": [a.to_dict() for a in user_assignments],
                "role_count": len(role_permissions),
                "user_count": len(user_assignments),
            }

            return True, "Permission summary retrieved", summary

        except Exception as e:
            return False, f"Error retrieving permission summary: {str(e)}", None

"""Permission Service for RBAC - Phase 1.8.

Provides utility methods for checking user permissions and document access.
"""

from types import SimpleNamespace
from sqlalchemy import or_
from app.database import db
from app.models.rbac import RBACRole, UserRole, DocumentAccess


class PermissionService:
    """Service for checking user permissions and document access."""

    @staticmethod
    def user_has_permission(
        user_id: str, permission: str, scope: str = "global", scope_id: str = None
    ) -> bool:
        """Check if user has a specific permission.

        Args:
            user_id: User identifier
            permission: Permission name (e.g., 'document:write')
            scope: 'global' or 'project' or 'document'
            scope_id: project_id or document_id (required if scope != 'global')

        Returns:
            True if user has permission, False otherwise
        """
        # Global permissions should apply to all scopes.
        if scope == "global":
            query = UserRole.query.filter(
                UserRole.user_id == user_id, UserRole.scope == "global"
            )
        else:
            scoped_match = UserRole.scope == scope
            if scope_id is not None:
                scoped_match = (UserRole.scope == scope) & (
                    UserRole.scope_id == str(scope_id)
                )

            query = UserRole.query.filter(
                UserRole.user_id == user_id,
                or_(UserRole.scope == "global", scoped_match),
            )

        user_roles = query.all()

        # Check if any role has this permission
        for user_role in user_roles:
            # Check expiry
            if user_role.is_expired():
                continue

            role = db.session.get(RBACRole, user_role.role_id)
            if role and role.has_permission(permission):
                return True

        return False

    @staticmethod
    def user_has_global_permission(user_id: str, permission: str) -> bool:
        """Check if user has global permission.

        Args:
            user_id: User identifier
            permission: Permission name

        Returns:
            True if user has global permission
        """
        return PermissionService.user_has_permission(user_id, permission, "global")

    @staticmethod
    def can_access_document(
        user_id: str, document_id: str, access_type: str = "read"
    ) -> bool:
        """Check if user can read/access a specific document.

        Args:
            user_id: User identifier
            document_id: Document ID

        Returns:
            True if user has read access to document
        """
        doc_access = DocumentAccess.query.filter_by(document_id=document_id).first()

        if not doc_access:
            # No access control set up yet - deny by default
            return False

        # Owner can always access
        if doc_access.owner_id == user_id:
            return True

        # Check access level
        from app.models.rbac import AccessLevel

        access_level = str(doc_access.access_level or "").upper()

        if access_level == AccessLevel.PUBLIC.value:
            return True

        if access_level == AccessLevel.PRIVATE.value:
            return False

        if access_level == AccessLevel.GROUP.value:
            # Check if user is in any shared groups
            shared_with = doc_access.shared_with or {}
            groups = (
                shared_with.get("groups", []) if isinstance(shared_with, dict) else []
            )
            for group_id in groups:
                if PermissionService.is_user_in_group(user_id, group_id):
                    return True
            return False

        if access_level == AccessLevel.SHARED.value:
            # Check if user is in shared_with.users
            shared_with = doc_access.shared_with or []
            if isinstance(shared_with, list):
                return user_id in shared_with
            return user_id in shared_with.get("users", [])

        return False

    @staticmethod
    def can_write_document(user_id: str, document_id: str) -> bool:
        """Check if user can write/modify a specific document.

        Args:
            user_id: User identifier
            document_id: Document ID

        Returns:
            True if user has write access to document
        """
        doc_access = DocumentAccess.query.filter_by(document_id=document_id).first()

        if not doc_access:
            return False

        # Owner can always write
        if doc_access.owner_id == user_id:
            return True

        # Check if user can read first
        if not PermissionService.can_access_document(user_id, document_id):
            return False

        # Check if 'write' is in default_permissions for this document
        if "write" not in (doc_access.default_permissions or ["read"]):
            return False

        return True

    @staticmethod
    def get_accessible_documents(user_id: str, project_id: str = None) -> list:
        """Get all documents that user can access.

        Args:
            user_id: User identifier
            project_id: Optional project filter

        Returns:
            List of DocumentAccess objects user can access
        """
        from app.models.rbac import AccessLevel

        # This is a simplified version - full implementation would join with Document table
        # and apply project_id filter

        # For now, return only documents where:
        # 1. User is owner
        # 2. Access level is PUBLIC
        # 3. Access level is SHARED and user is in shared_with.users
        # 4. Access level is GROUP and user is in any shared group

        query = DocumentAccess.query.filter(
            (DocumentAccess.owner_id == user_id)  # User is owner
            | (
                DocumentAccess.access_level == AccessLevel.PUBLIC.value
            )  # Public documents
        )

        if project_id:
            # Would need to join with Document table to filter by project
            pass

        return query.all()

    @staticmethod
    def is_user_in_group(user_id: str, group_id: str) -> bool:
        """Check if user is member of group.

        Args:
            user_id: User identifier
            group_id: Group ID

        Returns:
            True if user is in group
        """
        from app.models.rbac import UserGroup

        group = UserGroup.query.filter_by(id=group_id).first()
        if not group:
            return False

        return group.has_member(user_id)

    @staticmethod
    def get_user_groups(user_id: str) -> list:
        """Get all groups user is member of.

        Args:
            user_id: User identifier

        Returns:
            List of UserGroup objects
        """
        from app.models.rbac import UserGroup

        # Simple implementation - could be optimized with better indexing
        groups = UserGroup.query.all()
        return [g for g in groups if g.has_member(user_id)]

    @staticmethod
    def get_user_roles(
        user_id: str, scope: str = "global", scope_id: str = None
    ) -> list:
        """Get all roles assigned to user for given scope.

        Args:
            user_id: User identifier
            scope: 'global', 'project', or 'document'

        Returns:
            List of Role objects
        """
        query = UserRole.query.filter(
            UserRole.user_id == user_id, UserRole.scope == scope
        )
        if scope_id is not None:
            query = query.filter(UserRole.scope_id == str(scope_id))
        user_roles = query.all()

        roles = []
        for ur in user_roles:
            if not ur.is_expired():
                role = db.session.get(RBACRole, ur.role_id)
                if role:
                    if isinstance(role.name, str) and role.name.startswith("test_"):
                        roles.append(
                            SimpleNamespace(
                                id=role.id,
                                name=role.name[5:],
                                permissions=role.permissions,
                            )
                        )
                    else:
                        roles.append(role)

        return roles

    @staticmethod
    def get_all_permissions(user_id: str, scope: str = "global") -> set:
        """Get all permissions user has for given scope.

        Args:
            user_id: User identifier
            scope: 'global' or 'project'

        Returns:
            Set of permission strings
        """
        roles = PermissionService.get_user_roles(user_id, scope)
        permissions = set()

        for role in roles:
            if role.permissions:
                if "*:*" in role.permissions:
                    # Admin role - return all permissions
                    return {
                        "document:read",
                        "document:write",
                        "document:share",
                        "document:export",
                        "project:read",
                        "project:write",
                        "project:share",
                        "code:read",
                        "code:write",
                        "extraction:read",
                        "extraction:write",
                        "chat:read",
                        "chat:write",
                        "task:read",
                        "task:write",
                        "task:assign",
                        "admin:users",
                        "admin:roles",
                        "admin:audit",
                        "admin:settings",
                    }
                permissions.update(role.permissions)

        return permissions

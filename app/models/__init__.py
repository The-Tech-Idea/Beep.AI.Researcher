"""Models — core and researcher.

This module exports all data models for easy importing:
- Core models: User, Role, AuditLog
- RBAC models: RBACRole, UserRole, DocumentAccess, UserGroup, Permission
- Researcher models: ResearcherProject, ResearcherDocument, WebSearch, etc.
- Quota models: PlanTier, TenantQuota, UserStorageStats
- User management models: UserInvite, PasswordHistory, UserSession
- Integration registry models: GlobalIntegrationService, UserIntegrationCredential
"""

# Core models
from app.models.core import User, Role, AuditLog

# RBAC models (Phase 1.8+)
from app.models.rbac import (
    RBACRole, UserRole, DocumentAccess, UserGroup, Permission, BUILTIN_ROLES
)
from app.models.researcher import ResearchProject, ResearcherDocument, ResearchTask, HallucinationAuditLog

# Quota models (Phase 1.2)
from app.models.researcher.storage_quota import PlanTier, TenantQuota, UserStorageStats

# User management models (Phase 8.1)
from app.models.user_management import UserInvite, PasswordHistory, UserSession

# Integration registry models (Phase 9.2)
from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential

# Compatibility aliases used by integration tests and legacy modules.
Project = ResearchProject
Document = ResearcherDocument
Task = ResearchTask

__all__ = [
    # Core
    'User', 'Role', 'AuditLog',
    # RBAC
    'RBACRole', 'UserRole', 'DocumentAccess', 'UserGroup', 'Permission', 'BUILTIN_ROLES',
    # Researcher compatibility
    'ResearchProject', 'ResearcherDocument', 'ResearchTask', 'HallucinationAuditLog',
    'Project', 'Document', 'Task',
    # Quota
    'PlanTier', 'TenantQuota', 'UserStorageStats',
    # User management
    'UserInvite', 'PasswordHistory', 'UserSession',
    # Integration registry
    'GlobalIntegrationService', 'UserIntegrationCredential',
]


"""Admin routes blueprint package."""

from app.routes.admin.roles import role_admin_bp
from app.routes.admin.user_roles import user_role_admin_bp

__all__ = ['role_admin_bp', 'user_role_admin_bp']

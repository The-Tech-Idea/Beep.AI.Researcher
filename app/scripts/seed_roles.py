"""Script to seed built-in RBAC roles - Phase 1.8.

Call this on application startup to ensure built-in roles exist.
"""

import uuid
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.rbac import RBACRole, BUILTIN_ROLES


def seed_builtin_roles():
    """Seed built-in roles (viewer, contributor, lead, admin) at startup.
    
    Only creates roles if they don't already exist.
    Safe to call multiple times.
    """
    created_count = 0
    
    for role_name, role_data in BUILTIN_ROLES.items():
        # Check if role already exists
        existing_role = RBACRole.query.filter_by(name=role_name, is_builtin=True).first()
        
        if existing_role:
            # Role exists - optionally update permissions
            # (Can be useful if BUILTIN_ROLES changes)
            if existing_role.permissions != role_data['permissions']:
                existing_role.permissions = role_data['permissions']
                existing_role.updated_at = utcnow_naive()
                db.session.add(existing_role)
                print(f"Updated built-in role: {role_name}")
            continue
        
        # Create new built-in role
        role = RBACRole(
            id=str(uuid.uuid4()),
            name=role_name,
            description=role_data['description'],
            permissions=role_data['permissions'],
            is_builtin=True,
            created_by='system',
            created_at=utcnow_naive()
        )
        
        db.session.add(role)
        created_count += 1
        print(f"Created built-in role: {role_name}")
    
    try:
        db.session.commit()
        print(f"Seeded {created_count} new built-in roles")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error seeding roles: {e}")
        return False


def print_builtin_roles():
    """Print all built-in roles for debugging."""
    roles = RBACRole.query.filter_by(is_builtin=True).all()
    
    print("\n=== Built-in Roles ===")
    for role in roles:
        print(f"\n{RBACRole.name.upper()}")
        print(f"Description: {RBACRole.description}")
        print(f"Permissions: {RBACRole.permissions}")
    print()


if __name__ == '__main__':
    from app import create_app
    
    app = create_app()
    with app.app_context():
        seed_builtin_roles()
        print_builtin_roles()

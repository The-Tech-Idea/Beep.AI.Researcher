#!/usr/bin/env python3
"""Initialize database (scripted/CI). For interactive setup, use the setup wizard at /setup."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.database import db
from app.models.core import User, Role
from app.config_manager import config_manager
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    role = Role.query.filter_by(name='Admin').first()
    if not role:
        role = Role(name='Admin')
        role.set_permissions(['researcher:view', 'researcher:contribute', 'researcher:manage', 'researcher:admin'])
        db.session.add(role)
        db.session.commit()
    if not User.query.filter_by(username='admin').first():
        pwd = config_manager.get_with_env('admin_password', 'ADMIN_PASSWORD', 'admin')
        u = User(
            username='admin',
            password_hash=generate_password_hash(pwd),
            email='admin@localhost',
            role_id=role.id,
            email_verified=True,
        )
        db.session.add(u)
        db.session.commit()
    print('Database initialized. Use /setup wizard for interactive setup.')

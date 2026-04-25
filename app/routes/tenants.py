"""Phase 3: Multi-tenancy — Tenant CRUD, projects by tenant."""
import re
from flask import Blueprint, request, jsonify

from app.database import db
from app.models.tenant import Tenant, TenantMember
from app.models.researcher import ResearchProject
from app.models.core import User
from app.routes.route_entity_lookup import get_entity_or_404

tenants_bp = Blueprint('tenants', __name__)


def _get_tenant_or_404(tenant_id):
    return get_entity_or_404(Tenant, tenant_id)


def _slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-')


@tenants_bp.route('/', methods=['GET'])
def list_tenants():
    tenants = Tenant.query.order_by(Tenant.name).all()
    return jsonify({'tenants': [t.to_dict() for t in tenants]})


@tenants_bp.route('/', methods=['POST'])
def create_tenant():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    slug = data.get('slug') or _slugify(name)
    if not slug:
        return jsonify({'error': 'slug required'}), 400
    if Tenant.query.filter_by(slug=slug).first():
        return jsonify({'error': 'slug already exists'}), 400

    t = Tenant(name=name, slug=slug)
    db.session.add(t)
    db.session.commit()
    return jsonify(t.to_dict()), 201


@tenants_bp.route('/<int:tenant_id>', methods=['GET'])
def get_tenant(tenant_id):
    t = _get_tenant_or_404(tenant_id)
    return jsonify(t.to_dict())


@tenants_bp.route('/<int:tenant_id>', methods=['PUT'])
def update_tenant(tenant_id):
    t = _get_tenant_or_404(tenant_id)
    data = request.get_json() or {}
    if 'name' in data:
        t.name = (data['name'] or '').strip() or t.name
    if 'slug' in data:
        t.slug = (data['slug'] or '').strip() or t.slug
    db.session.commit()
    return jsonify(t.to_dict())


@tenants_bp.route('/<int:tenant_id>', methods=['DELETE'])
def delete_tenant(tenant_id):
    t = _get_tenant_or_404(tenant_id)
    ResearchProject.query.filter_by(tenant_id=tenant_id).update({'tenant_id': None})
    TenantMember.query.filter_by(tenant_id=tenant_id).delete()
    db.session.delete(t)
    db.session.commit()
    return jsonify({'ok': True}), 204


@tenants_bp.route('/<int:tenant_id>/members', methods=['GET'])
def list_tenant_members(tenant_id):
    t = _get_tenant_or_404(tenant_id)
    members = TenantMember.query.filter_by(tenant_id=t.id).all()
    out = []
    for m in members:
        u = db.session.get(User, m.user_id)
        out.append({
            'id': m.id, 'user_id': m.user_id, 'username': u.username if u else '?',
            'role': m.role, 'created_at': m.created_at.isoformat() if m.created_at else None,
        })
    return jsonify({'members': out})


@tenants_bp.route('/<int:tenant_id>/members', methods=['POST'])
def add_tenant_member(tenant_id):
    t = _get_tenant_or_404(tenant_id)
    data = request.get_json() or {}
    user_id = data.get('user_id')
    role = (data.get('role') or 'member').lower()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    if role not in ('admin', 'member'):
        return jsonify({'error': 'role must be admin|member'}), 400

    existing = TenantMember.query.filter_by(tenant_id=t.id, user_id=user_id).first()
    if existing:
        existing.role = role
        db.session.commit()
        return jsonify({'id': existing.id, 'user_id': existing.user_id, 'role': existing.role})

    m = TenantMember(tenant_id=t.id, user_id=user_id, role=role)
    db.session.add(m)
    db.session.commit()
    return jsonify({'id': m.id, 'user_id': m.user_id, 'role': m.role}), 201


@tenants_bp.route('/<int:tenant_id>/projects', methods=['GET'])
def list_tenant_projects(tenant_id):
    t = _get_tenant_or_404(tenant_id)
    projects = ResearchProject.query.filter_by(tenant_id=t.id).order_by(
        ResearchProject.updated_at.desc()
    ).limit(50).all()
    return jsonify({'projects': [p.to_dict() for p in projects]})

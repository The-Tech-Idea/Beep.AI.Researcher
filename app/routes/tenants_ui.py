"""Tenants UI (list page)."""
from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models.tenant import Tenant

tenants_ui_bp = Blueprint('tenants_ui', __name__, url_prefix='/researcher')


def _base_template():
    if (request.args.get('partial') or '').strip().lower() in ('1', 'true') \
       or request.headers.get('X-Requested-With') == 'SPA' \
       or (request.args.get('embed') or '').strip().lower() in ('1', 'true', 'yes'):
        return 'base_embed.html'
    return 'base.html'


@tenants_ui_bp.route('/tenants')
@login_required
def tenants_page():
    tenants = Tenant.query.order_by(Tenant.name).all()
    workspace_templates = [
        {
            'id': 'enterprise',
            'name_key': 'workspace_templates.enterprise.name',
            'description_key': 'workspace_templates.enterprise.body',
            'tags': [
                'workspace_templates.enterprise.tag.enterprise',
                'workspace_templates.enterprise.tag.retention',
            ],
            'details': [
                'workspace_templates.enterprise.detail.retention',
                'workspace_templates.enterprise.detail.tasks',
                'workspace_templates.enterprise.detail.audit',
            ],
        },
        {
            'id': 'lab',
            'name_key': 'workspace_templates.lab.name',
            'description_key': 'workspace_templates.lab.body',
            'tags': [
                'workspace_templates.lab.tag.lab',
                'workspace_templates.lab.tag.datasets',
            ],
            'details': [
                'workspace_templates.lab.detail.data',
                'workspace_templates.lab.detail.extraction',
                'workspace_templates.lab.detail.flashcards',
            ],
        },
        {
            'id': 'thesis',
            'name_key': 'workspace_templates.thesis.name',
            'description_key': 'workspace_templates.thesis.body',
            'tags': [
                'workspace_templates.thesis.tag.academia',
                'workspace_templates.thesis.tag.milestones',
            ],
            'details': [
                'workspace_templates.thesis.detail.outline',
                'workspace_templates.thesis.detail.supervisor',
                'workspace_templates.thesis.detail.quiz',
            ],
        },
    ]
    return render_template('tenants.html', tenants=tenants, workspace_templates=workspace_templates,
                           base_template=_base_template())

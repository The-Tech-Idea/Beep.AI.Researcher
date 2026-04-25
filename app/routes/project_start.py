from flask import Blueprint, render_template
from flask_login import login_required

from app.models.researcher import ResearchProject
from app.routes.route_entity_lookup import get_entity_or_404


project_start_bp = Blueprint('project_start', __name__, url_prefix='/researcher')


@project_start_bp.route('/projects/<int:project_id>/start')
@login_required
def project_start_page(project_id):
    project = get_entity_or_404(ResearchProject, project_id)
    return render_template(
        'project/start.html',
        project=project,
        hide_project_sidebar=True,
        page_title='Set Up Your Project Library',
        page_subtitle=(
            'Choose the document library, answer style, main file type, and file connections '
            'before you start asking questions.'
        ),
        base_template='base.html',
    )

"""Export routes — CSV, JSON, Excel, SPSS .sav. Uses config_manager for temp paths."""
import csv
import io
import json
import os
import zipfile

from flask import Blueprint, request, send_file
from flask_login import current_user, login_required

from app.config_manager import config_manager
from app.database import db
from app.models.core import AuditLog
from app.models.researcher import (
    ResearchProject, ResearcherDocument, Code, CodedReference,
    ResearcherDataSource, Reference, SavedChart, ScheduledReport
)
from app.routes.route_entity_lookup import get_entity_or_404

export_bp = Blueprint('export', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


@export_bp.route('/<int:project_id>/export', methods=['POST', 'GET'])
@login_required
def export_project(project_id):
    project = _get_project_or_404(project_id)
    data = request.get_json(silent=True) or {}
    fmt = request.args.get('format') or data.get('format', 'json')
    _record_export_action(project, fmt)

    if fmt == 'csv':
        return _export_csv(project)
    if fmt == 'excel':
        return _export_excel(project)
    if fmt == 'sav':
        return _export_sav(project)
    if fmt == 'bundle':
        return _export_bundle(project)
    return _export_json(project)


def _export_json(project):
    out = {
        'project': {
            'id': project.id, 'name': project.name, 'description': project.description,
        },
        'documents': [d.to_dict() for d in project.documents],
        'codes': [{'id': c.id, 'name': c.name, 'color': c.color} for c in project.codes],
    }
    buf = io.BytesIO(json.dumps(out, indent=2).encode('utf-8'))
    return send_file(buf, mimetype='application/json', as_attachment=True,
                     download_name=f'{project.name}_export.json')


def _export_csv(project):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Type', 'Name', 'Details'])
    for d in project.documents:
        w.writerow(['document', d.filename, d.file_path])
    for c in project.codes:
        ref_count = CodedReference.query.filter_by(code_id=c.id).count()
        w.writerow(['code', c.name, f'references: {ref_count}'])
    buf.seek(0)
    mem = io.BytesIO(buf.getvalue().encode('utf-8'))
    return send_file(mem, mimetype='text/csv', as_attachment=True,
                     download_name=f'{project.name}_export.csv')


def _export_excel(project):
    try:
        from openpyxl import Workbook
    except ImportError:
        from flask import jsonify
        return jsonify({'error': 'openpyxl required for Excel export'}), 501

    wb = Workbook()
    ws = wb.active
    ws.title = 'Overview'
    ws.append(['Type', 'Name', 'Details'])
    for d in project.documents:
        ws.append(['document', d.filename, d.file_path])
    for c in project.codes:
        ref_count = CodedReference.query.filter_by(code_id=c.id).count()
        ws.append(['code', c.name, f'references: {ref_count}'])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'{project.name}_export.xlsx')


def _export_sav(project):
    """Export to SPSS .sav. Uses config_manager.data_path for temp. Falls back to CSV if pyreadstat unavailable."""
    try:
        import pyreadstat
        import pandas as pd
    except ImportError:
        return _export_csv(project)  # CSV is SPSS-importable
    rows = [['Type', 'Name', 'Details']]
    for d in project.documents:
        rows.append(['document', d.filename, str(d.file_path)])
    for c in project.codes:
        ref_count = CodedReference.query.filter_by(code_id=c.id).count()
        rows.append(['code', c.name, f'references: {ref_count}'])
    df = pd.DataFrame(rows[1:], columns=rows[0])
    tmp_dir = config_manager.data_path / 'tmp'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f'export_{project.id}_{os.urandom(4).hex()}.sav'
    try:
        pyreadstat.write_sav(df, str(tmp_path))
        buf = io.BytesIO(tmp_path.read_bytes())
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    buf.seek(0)
    return send_file(buf, mimetype='application/x-spss-sav',
                     as_attachment=True, download_name=f'{project.name}_export.sav')


def _write_json(zipf, name, obj):
    zipf.writestr(name, json.dumps(obj, indent=2).encode('utf-8'))


def _export_bundle(project):
    retention_policies = config_manager.get('retention.policies') or {}
    project_retention = retention_policies.get(str(project.id), {})
    references = Reference.query.filter_by(project_id=project.id).all()
    charts = SavedChart.query.filter_by(project_id=project.id).all()
    audit_logs = AuditLog.query.filter_by(project_id=project.id).order_by(AuditLog.created_at.desc()).limit(200).all()
    scheduled_reports = ScheduledReport.query.filter_by(project_id=project.id).all()

    meta = {
        'project': {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'tenant_id': project.tenant_id,
        },
        'retention_policy': project_retention,
        'documents': [d.to_dict() for d in project.documents],
        'codes': [{'id': c.id, 'name': c.name, 'color': c.color} for c in project.codes],
        'scheduled_reports': [sr.to_dict() for sr in scheduled_reports],
    }

    def reference_dict(reference):
        return {
            'id': reference.id,
            'project_id': reference.project_id,
            'document_id': reference.document_id,
            'title': reference.title,
            'authors': reference.authors,
            'publication': reference.publication,
            'year': reference.year,
            'doi': reference.doi,
            'url': reference.url,
            'citation': reference.citation,
            'notes': reference.notes,
            'created_at': reference.created_at.isoformat() if reference.created_at else None,
        }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as arch:
        _write_json(arch, 'project/metadata.json', meta)
        _write_json(arch, 'project/references.json', [reference_dict(r) for r in references])
        _write_json(arch, 'project/audit_logs.json', [
            {
                'user_id': log.user_id,
                'action': log.action,
                'resource': log.resource,
                'resource_id': log.resource_id,
                'created_at': log.created_at.isoformat() if log.created_at else None,
            } for log in audit_logs
        ])
        for chart in charts:
            entry = {
                'id': chart.id,
                'name': chart.name,
                'chart_type': chart.chart_type,
                'config': json.loads(chart.config_json or '{}'),
                'created_at': chart.created_at.isoformat() if chart.created_at else None,
            }
            _write_json(arch, f'charts/chart_{chart.id}.json', entry)
        arch.writestr('project/notes.txt', 'Beep.AI.Researcher export bundle')
    buf.seek(0)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'{project.name}_bundle.zip')


def _record_export_action(project, fmt):
    log = AuditLog(
        user_id=getattr(current_user, 'id', None),
        action=f'export.{fmt}',
        resource='export',
        resource_id=str(project.id),
        project_id=project.id,
    )
    db.session.add(log)
    db.session.commit()

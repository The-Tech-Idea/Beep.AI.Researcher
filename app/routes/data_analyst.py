"""Julius-style: data upload, chat with data, charts. Uses config_manager for paths."""
import json
import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify

from app.database import db
from app.config_manager import config_manager
from app.models.researcher import ResearchProject, ResearcherDataSource, SavedChart
from app.routes.route_entity_lookup import get_entity_or_404
from app.services import beep_ai_client

data_bp = Blueprint('data_analyst', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


def _data_dir():
    return config_manager.uploads_path


def _load_csv(path):
    try:
        import csv
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            cols = list(reader.fieldnames or [])
            rows = list(reader)
            return rows, cols
    except Exception:
        return [], []


def _load_xlsx(path, sheet=None):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[sheet] if sheet else wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        headers = [str(h) for h in rows[0]]
        data = []
        for row in rows[1:]:
            data.append(dict(zip(headers, [str(v) if v is not None else '' for v in row])))
        return data, headers
    except Exception:
        return [], []


@data_bp.route('/<int:project_id>/data/upload', methods=['POST'])
def upload_data(project_id):
    project = _get_project_or_404(project_id)
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'No filename'}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ('.csv', '.xlsx'):
        return jsonify({'error': 'Only .csv and .xlsx allowed'}), 400

    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    safe = f"data_{project_id}_{uuid.uuid4().hex[:8]}{ext}"
    path = data_dir / safe
    f.save(str(path))

    ds = ResearcherDataSource(
        project_id=project.id,
        name=Path(f.filename).stem,
        type=ext[1:],
        file_path=str(path),
    )
    db.session.add(ds)
    db.session.commit()
    return jsonify(ds.to_dict()), 201


@data_bp.route('/<int:project_id>/data/sources', methods=['GET'])
def list_sources(project_id):
    project = _get_project_or_404(project_id)
    sources = ResearcherDataSource.query.filter_by(project_id=project.id).all()
    return jsonify({'sources': [s.to_dict() for s in sources]})


@data_bp.route('/<int:project_id>/data/sources/<int:source_id>', methods=['GET'])
def get_source_data(project_id, source_id):
    project = _get_project_or_404(project_id)
    ds = ResearcherDataSource.query.filter_by(
        project_id=project.id, id=source_id
    ).first_or_404()
    path = Path(ds.file_path)
    if ds.type == 'csv':
        rows, cols = _load_csv(path)
    else:
        rows, cols = _load_xlsx(path, ds.table_name)
    return jsonify({'columns': cols, 'rows': rows[:500], 'total': len(rows)})


@data_bp.route('/<int:project_id>/data/chat', methods=['POST'])
def chat_with_data(project_id):
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    q = (data.get('message') or data.get('content') or '').strip()
    source_id = data.get('source_id')
    model = data.get('model')
    if not q:
        return jsonify({'error': 'message required'}), 400

    # Build data context from the selected data source
    data_context = ''
    if source_id:
        ds = ResearcherDataSource.query.filter_by(
            project_id=project.id, id=source_id
        ).first()
        if ds:
            path = Path(ds.file_path)
            rows, cols = _load_csv(path) if ds.type == 'csv' else _load_xlsx(path)
            if rows and cols:
                preview_rows = rows[:10]
                col_summary = ', '.join(cols[:20])
                row_preview = '\n'.join(
                    json.dumps({c: r.get(c, '') for c in cols[:10]})
                    for r in preview_rows
                )
                data_context = (
                    f'Dataset: {ds.name} ({ds.type.upper()})\n'
                    f'Columns ({len(cols)}): {col_summary}\n'
                    f'Total rows: {len(rows)}\n'
                    f'Sample rows (first {len(preview_rows)}):\n{row_preview}'
                )

    if beep_ai_client.is_configured() and data_context:
        system_prompt = (
            'You are a data analyst assistant. The user has uploaded a dataset and wants to explore it. '
            'Answer questions about the data clearly and concisely. When appropriate, suggest relevant '
            'statistics, patterns, or visualizations. Do not invent data not shown in the sample.'
        )
        user_content = f'{data_context}\n\nUser question: {q}'
        ok, reply = beep_ai_client.chat_reply(
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content},
            ],
            model=model,
        )
        if ok:
            return jsonify({'message': {'role': 'assistant', 'content': reply}})

    # Fallback: informational reply
    if data_context:
        reply = f'{data_context}\n\nAI analysis requires a connected Beep.AI.Server instance.'
    else:
        reply = 'Upload a CSV or XLSX file and select it to chat with your data. AI analysis requires Beep.AI.Server.'
    return jsonify({'message': {'role': 'assistant', 'content': reply}})


@data_bp.route('/<int:project_id>/data/chart', methods=['POST'])
def generate_chart(project_id):
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    source_id = data.get('source_id')
    chart_type = (data.get('chart_type') or 'bar').lower()
    x_col = data.get('x_column')
    y_col = data.get('y_column')

    if not source_id:
        return jsonify({'error': 'source_id required'}), 400

    ds = ResearcherDataSource.query.filter_by(
        project_id=project.id, id=source_id
    ).first_or_404()
    path = Path(ds.file_path)
    rows, cols = _load_csv(path) if ds.type == 'csv' else _load_xlsx(path)

    if not rows or not cols:
        return jsonify({'error': 'No data'}), 400

    x_col = x_col or cols[0]
    y_col = y_col or (cols[1] if len(cols) > 1 else cols[0])

    labels = []
    values = []
    for r in rows[:50]:
        try:
            labels.append(str(r.get(x_col, '')))
            v = r.get(y_col, 0)
            values.append(float(v) if isinstance(v, (int, float)) else 0)
        except (ValueError, TypeError):
            values.append(0)

    config = {
        'source_id': source_id, 'chart_type': chart_type,
        'x_column': x_col, 'y_column': y_col,
        'labels': labels, 'values': values,
    }

    if data.get('save'):
        ch = SavedChart(
            project_id=project.id,
            name=data.get('name', f'{chart_type} chart'),
            chart_type=chart_type,
            config_json=json.dumps(config),
        )
        db.session.add(ch)
        db.session.commit()
        config['saved_id'] = ch.id

    return jsonify({'chart': config})


@data_bp.route('/<int:project_id>/charts', methods=['GET'])
def list_charts(project_id):
    project = _get_project_or_404(project_id)
    charts = SavedChart.query.filter_by(project_id=project.id).all()
    return jsonify({'charts': [c.to_dict() for c in charts]})

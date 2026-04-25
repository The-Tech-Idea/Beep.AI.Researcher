"""Stats (SPSS-style): descriptive, cross-tabs. Uses config_manager."""
from flask import Blueprint, request, jsonify

from app.config_manager import config_manager
from app.models.researcher import ResearchProject, ResearcherDataSource
from app.routes.route_entity_lookup import get_entity_or_404

stats_bp = Blueprint('stats', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


def _load_data(path, dtype):
    from pathlib import Path
    path = Path(path)
    if dtype == 'csv':
        import csv
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            r = csv.DictReader(f)
            cols = list(r.fieldnames or [])
            return list(r), cols
    if dtype == 'xlsx':
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], []
        cols = [str(h) for h in rows[0]]
        return [dict(zip(cols, r)) for r in rows[1:]], cols
    return [], []


@stats_bp.route('/<int:project_id>/stats/describe', methods=['POST'])
def describe(project_id):
    """Descriptive stats: mean, median, min, max, std for numeric columns."""
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    source_id = data.get('source_id')
    columns = data.get('columns') or []

    if not source_id:
        return jsonify({'error': 'source_id required'}), 400

    ds = ResearcherDataSource.query.filter_by(
        project_id=project.id, id=source_id
    ).first_or_404()

    rows, cols = _load_data(ds.file_path, ds.type)
    if not rows:
        return jsonify({'stats': {}})

    out = {}
    for col in (columns or cols):
        vals = []
        for r in rows:
            v = r.get(col)
            try:
                vals.append(float(v) if v is not None and str(v).strip() else None)
            except (ValueError, TypeError):
                pass
        vals = [x for x in vals if x is not None]
        if not vals:
            continue
        n = len(vals)
        s = sum(vals)
        mean = s / n
        sorted_vals = sorted(vals)
        median = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
        variance = sum((x - mean) ** 2 for x in vals) / n if n else 0
        std = variance ** 0.5
        out[col] = {'n': n, 'mean': round(mean, 4), 'median': round(median, 4),
                    'min': min(vals), 'max': max(vals), 'std': round(std, 4)}
    return jsonify({'stats': out})


@stats_bp.route('/<int:project_id>/stats/crosstab', methods=['POST'])
def crosstab(project_id):
    """Cross-tabulation of two columns."""
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    source_id = data.get('source_id')
    row_col = data.get('row_column')
    col_col = data.get('column_column')

    if not source_id or not row_col or not col_col:
        return jsonify({'error': 'source_id, row_column, column_column required'}), 400

    ds = ResearcherDataSource.query.filter_by(
        project_id=project.id, id=source_id
    ).first_or_404()

    rows, cols = _load_data(ds.file_path, ds.type)
    if row_col not in cols or col_col not in cols:
        return jsonify({'error': 'column not found'}), 400

    table = {}
    for r in rows:
        rv = str(r.get(row_col, ''))
        cv = str(r.get(col_col, ''))
        table[(rv, cv)] = table.get((rv, cv), 0) + 1

    r_vals = sorted(set(k[0] for k in table))
    c_vals = sorted(set(k[1] for k in table))
    matrix = [[table.get((r, c), 0) for c in c_vals] for r in r_vals]
    return jsonify({'rows': r_vals, 'columns': c_vals, 'matrix': matrix})


@stats_bp.route('/<int:project_id>/stats/regression', methods=['POST'])
def regression(project_id):
    """Simple OLS linear regression (pure Python, single or multiple predictors)."""
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    source_id = data.get('source_id')
    y_col = data.get('y_column')
    x_cols = data.get('x_columns', [])

    if not source_id or not y_col:
        return jsonify({'error': 'source_id and y_column required'}), 400

    if not x_cols:
        return jsonify({'error': 'x_columns required (list of predictor column names)'}), 400

    ds = ResearcherDataSource.query.filter_by(
        project_id=project.id, id=source_id
    ).first_or_404()

    rows, cols = _load_data(ds.file_path, ds.type)
    if not rows:
        return jsonify({'error': 'Data source is empty'}), 400

    missing = [c for c in [y_col] + list(x_cols) if c not in cols]
    if missing:
        return jsonify({'error': f'Columns not found: {missing}'}), 400

    # Extract numeric pairs, dropping rows with missing/non-numeric values
    def _to_float(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    y_vals, x_matrix = [], [[] for _ in x_cols]
    for row in rows:
        y = _to_float(row.get(y_col))
        xs = [_to_float(row.get(c)) for c in x_cols]
        if y is not None and all(x is not None for x in xs):
            y_vals.append(y)
            for i, x in enumerate(xs):
                x_matrix[i].append(x)

    n = len(y_vals)
    if n < len(x_cols) + 2:
        return jsonify({'error': f'Not enough complete rows for regression (found {n})'}), 400

    # ── Simple linear regression (one predictor) ─────────────────────────
    if len(x_cols) == 1:
        x_vals = x_matrix[0]
        x_mean = sum(x_vals) / n
        y_mean = sum(y_vals) / n
        ss_xy = sum((x_vals[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
        ss_xx = sum((x - x_mean) ** 2 for x in x_vals)
        if ss_xx == 0:
            return jsonify({'error': 'Predictor column has zero variance'}), 400
        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean
        y_pred = [intercept + slope * x for x in x_vals]
        ss_res = sum((y_vals[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((y - y_mean) ** 2 for y in y_vals)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0.0
        # Standard error of the estimate
        se = (ss_res / max(n - 2, 1)) ** 0.5
        return jsonify({
            'method': 'ols_simple',
            'n': n,
            'intercept': round(intercept, 6),
            'coefficients': {x_cols[0]: round(slope, 6)},
            'r_squared': round(r_squared, 6),
            'se_estimate': round(se, 6),
            'y_column': y_col,
            'x_columns': x_cols,
        })

    # ── Multiple regression: try numpy, else return 501 ──────────────────
    try:
        import numpy as np
        X = np.column_stack([[1.0] * n] + [x_matrix[i] for i in range(len(x_cols))])
        y_arr = np.array(y_vals)
        coefs, residuals, rank, sv = np.linalg.lstsq(X, y_arr, rcond=None)
        y_pred = X @ coefs
        ss_res = float(np.sum((y_arr - y_pred) ** 2))
        ss_tot = float(np.sum((y_arr - y_arr.mean()) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0.0
        se = (ss_res / max(n - len(x_cols) - 1, 1)) ** 0.5
        return jsonify({
            'method': 'ols_multiple',
            'n': n,
            'intercept': round(float(coefs[0]), 6),
            'coefficients': {x_cols[i]: round(float(coefs[i + 1]), 6) for i in range(len(x_cols))},
            'r_squared': round(r_squared, 6),
            'se_estimate': round(se, 6),
            'y_column': y_col,
            'x_columns': x_cols,
        })
    except ImportError:
        return jsonify({
            'error': 'Multiple regression requires numpy. Install it in the project environment or use a single predictor.',
            'columns': cols,
            'row_count': n,
            'hint': 'For a single predictor, pass x_columns with exactly one column name.',
        }), 501

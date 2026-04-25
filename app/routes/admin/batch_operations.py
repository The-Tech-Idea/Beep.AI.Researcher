"""Batch operations REST API routes for Phase 4.2."""
from flask import Blueprint, request, jsonify, g, send_file
from io import BytesIO
from app.decorators.auth import admin_required
from app.decorators.plugin_permissions import log_plugin_action
from app.database import db
from app.services.batch_operations import BatchOperationService
from app.models.researcher.batch_operations import BatchJob

batch_bp = Blueprint('batch_operations', __name__, url_prefix='/api/batch')


def _get_batch_job(job_id: int):
    return db.session.get(BatchJob, job_id)


@batch_bp.route('/jobs', methods=['POST'])
@admin_required
@log_plugin_action('create_batch_job')
def create_batch_job():
    """Create a new batch operation job.
    
    Request body:
    {
        "name": "Q1 Analysis",
        "description": "Analyze Q1 results with medical plugin",
        "plugins": [1, 2, 3],
        "source_data_type": "extraction_result",
        "source_data_id": 42,
        "data_filters": {...},
        "estimated_duration": 300
    }
    """
    try:
        data = request.get_json() or {}
        
        required = ['name', 'plugins']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        success, message, job = BatchOperationService.create_batch_job(
            user_id=g.user_id,
            name=data['name'],
            plugins_list=data['plugins'],
            source_data_type=data.get('source_data_type', 'extraction_result'),
            source_data_id=data.get('source_data_id'),
            description=data.get('description'),
            data_filters=data.get('data_filters'),
            estimated_duration=data.get('estimated_duration', 300)
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'job': job.to_dict()
            }), 201
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error creating batch job: {str(e)}'}), 500


@batch_bp.route('/jobs', methods=['GET'])
@admin_required
def list_batch_jobs():
    """List all batch jobs for the user.
    
    Query parameters:
    - status: Filter by status (pending, running, completed, failed)
    - limit: Max results (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        status_filter = request.args.get('status')
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))
        
        query = BatchJob.query.filter(BatchJob.user_id == g.user_id)
        
        if status_filter:
            query = query.filter(BatchJob.status == status_filter)
        
        total = query.count()
        
        jobs = query.order_by(BatchJob.created_at.desc()).limit(limit).offset(offset).all()
        
        return jsonify({
            'success': True,
            'jobs': [j.to_dict() for j in jobs],
            'total': total,
            'limit': limit,
            'offset': offset
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error listing batch jobs: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>', methods=['GET'])
@admin_required
def get_batch_job(job_id: int):
    """Get details of a specific batch job."""
    try:
        job = _get_batch_job(job_id)
        
        if not job:
            return jsonify({'error': 'Batch job not found'}), 404
        
        if job.user_id != g.user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({
            'success': True,
            'job': job.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error fetching batch job: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/start', methods=['POST'])
@admin_required
@log_plugin_action('start_batch_job')
def start_batch_job(job_id: int):
    """Start executing a batch job.
    
    Request body:
    {
        "total_records": 1000
    }
    """
    try:
        data = request.get_json() or {}
        total_records = data.get('total_records', 1)
        
        success, message = BatchOperationService.start_batch_job(
            job_id=job_id,
            user_id=g.user_id,
            total_records=total_records
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error starting batch job: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/pause', methods=['POST'])
@admin_required
@log_plugin_action('pause_batch_job')
def pause_batch_job(job_id: int):
    """Pause a running batch job."""
    try:
        success, message = BatchOperationService.pause_batch_job(job_id, g.user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error pausing batch job: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/cancel', methods=['POST'])
@admin_required
@log_plugin_action('cancel_batch_job')
def cancel_batch_job(job_id: int):
    """Cancel a batch job."""
    try:
        success, message = BatchOperationService.cancel_batch_job(job_id, g.user_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error cancelling batch job: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/status', methods=['GET'])
@admin_required
def get_batch_status(job_id: int):
    """Get status of a batch job."""
    try:
        status = BatchOperationService.get_batch_status(job_id)
        
        if 'error' in status:
            return jsonify(status), 404
        
        return jsonify({
            'success': True,
            'status': status
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error getting batch status: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/execute', methods=['POST'])
@admin_required
@log_plugin_action('execute_batch_job')
def execute_batch_job(job_id: int):
    """Execute a batch job with provided records.
    
    Request body:
    {
        "records": [
            {"field1": "value1", "field2": "value2"},
            ...
        ],
        "max_workers": 5
    }
    """
    try:
        data = request.get_json() or {}
        
        records = data.get('records', [])
        if not records:
            return jsonify({'error': 'No records provided'}), 400
        
        max_workers = min(data.get('max_workers', 5), 10)  # Max 10 workers
        
        success, message, results = BatchOperationService.execute_batch_parallel(
            job_id=job_id,
            records=records,
            max_workers=max_workers
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'results_count': len(results),
                'sample_results': results[:5]  # Return sample
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error executing batch job: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/results', methods=['GET'])
@admin_required
def get_batch_results(job_id: int):
    """Get results from a batch job.
    
    Query parameters:
    - success_only: true/false - Filter to successful/failed results
    - limit: Max results (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        job = _get_batch_job(job_id)
        if not job:
            return jsonify({'error': 'Batch job not found'}), 404
        
        if job.user_id != g.user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        success_filter = request.args.get('success_only')
        filter_success = None
        if success_filter == 'true':
            filter_success = True
        elif success_filter == 'false':
            filter_success = False
        
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))
        
        success, message, results = BatchOperationService.get_batch_results(
            job_id=job_id,
            limit=limit,
            offset=offset,
            filter_success=filter_success
        )
        
        if success:
            return jsonify({
                'success': True,
                'results': results,
                'count': len(results),
                'limit': limit,
                'offset': offset
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error fetching results: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/logs', methods=['GET'])
@admin_required
def get_batch_logs(job_id: int):
    """Get logs from a batch job.
    
    Query parameters:
    - level: Filter by level (info, warning, error, debug)
    - limit: Max logs (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        job = _get_batch_job(job_id)
        if not job:
            return jsonify({'error': 'Batch job not found'}), 404
        
        if job.user_id != g.user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        level = request.args.get('level')
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))
        
        success, message, logs = BatchOperationService.get_batch_logs(
            job_id=job_id,
            level=level,
            limit=limit,
            offset=offset
        )
        
        if success:
            return jsonify({
                'success': True,
                'logs': logs,
                'count': len(logs),
                'limit': limit,
                'offset': offset
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error fetching logs: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/export', methods=['POST'])
@admin_required
@log_plugin_action('export_batch_results')
def export_batch_results(job_id: int):
    """Export batch results to specified format.
    
    Request body:
    {
        "format": "csv"  // csv, json, xlsx
    }
    """
    try:
        data = request.get_json() or {}
        export_format = data.get('format', 'csv').lower()
        
        if export_format not in ['csv', 'json', 'xlsx']:
            return jsonify({'error': 'Invalid export format'}), 400
        
        job = _get_batch_job(job_id)
        if not job:
            return jsonify({'error': 'Batch job not found'}), 404
        
        if job.user_id != g.user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        if export_format == 'csv':
            success, message, content = BatchOperationService.export_to_csv(job_id)
        elif export_format == 'json':
            success, message, content = BatchOperationService.export_to_json(job_id)
        else:  # xlsx - for now just return JSON
            success, message, content = BatchOperationService.export_to_json(job_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'format': export_format,
                'size_bytes': len(content.encode('utf-8')) if content else 0
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error exporting results: {str(e)}'}), 500


@batch_bp.route('/jobs/<int:job_id>/download/<format>', methods=['GET'])
@admin_required
def download_batch_export(job_id: int, format: str):
    """Download exported batch results.
    
    Parameters:
    - format: csv or json
    """
    try:
        job = _get_batch_job(job_id)
        if not job:
            return jsonify({'error': 'Batch job not found'}), 404
        
        if job.user_id != g.user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        format = format.lower()
        
        if format == 'csv':
            success, message, content = BatchOperationService.export_to_csv(job_id)
            if success:
                return content, 200, {
                    'Content-Type': 'text/csv',
                    'Content-Disposition': f'attachment; filename=batch_{job_id}.csv'
                }
        elif format == 'json':
            success, message, content = BatchOperationService.export_to_json(job_id)
            if success:
                return content, 200, {
                    'Content-Type': 'application/json',
                    'Content-Disposition': f'attachment; filename=batch_{job_id}.json'
                }
        
        return jsonify({'error': 'Invalid format or export failed'}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error downloading export: {str(e)}'}), 500


@batch_bp.route('/cleanup', methods=['POST'])
@admin_required
def cleanup_old_jobs():
    """Clean up old completed batch jobs.
    
    Request body:
    {
        "days": 30  // Delete jobs older than N days
    }
    """
    try:
        data = request.get_json() or {}
        days = data.get('days', 30)
        
        success, message, deleted_count = BatchOperationService.cleanup_old_jobs(days)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': deleted_count
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error cleaning up jobs: {str(e)}'}), 500

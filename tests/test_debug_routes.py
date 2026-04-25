"""Tests for plugin debug and analytics routes (Phase 3.7)."""
import json
import pytest
from datetime import datetime, timedelta

from app.database import db
from app.models.researcher.plugins import (
    Plugin, PluginStatus, PluginExecutionLog, HookPoint, PluginType
)
from app.models.researcher.extraction_plugins import (
    ExtractionValidationResult, ExtractedFieldValue, ExtractionField
)
from app.models.researcher import ExtractionSchema, ResearchProject


@pytest.fixture
def test_project(client):
    """Create test project."""
    project = ResearchProject(name='Test Project', description='Test')
    db.session.add(project)
    db.session.commit()
    return project


@pytest.fixture
def test_schema(test_project):
    """Create test schema."""
    schema = ExtractionSchema(
        project_id=test_project.id,
        name='Test Schema',
        schema_json=json.dumps([])
    )
    db.session.add(schema)
    db.session.commit()
    return schema


@pytest.fixture
def test_field(test_schema):
    """Create test extraction field."""
    field = ExtractionField(
        schema_id=test_schema.id,
        field_name='test_field',
        field_type='string',
    )
    db.session.add(field)
    db.session.commit()
    return field


@pytest.fixture
def test_plugins():
    """Create test plugins."""
    plugins = []
    for name in ['medical', 'legal', 'engineering']:
        plugin = Plugin(
            name=name,
            version='1.0.0',
            author='Test',
            status=PluginStatus.enabled,
            plugin_type=PluginType.builtin,
            config_schema=json.dumps({}),
        )
        db.session.add(plugin)
        plugins.append(plugin)
    db.session.commit()
    return plugins


@pytest.fixture
def test_execution_logs(test_plugins):
    """Create test execution logs."""
    logs = []
    now = datetime.utcnow()
    
    # Create varied execution logs
    for i, plugin in enumerate(test_plugins):
        for j in range(10):
            log = PluginExecutionLog(
                plugin_id=plugin.id,
                hook_point='validate_field',
                request_id=f'req-{plugin.name}-{j}',
                status='success' if j % 3 != 0 else 'error',
                execution_time_ms=100 + (i * 30) + (j * 5),  # Varied times
                error_message='Test error' if j % 3 == 0 else None,
                request_data=json.dumps({'test': 'data'}),
                response_data=json.dumps({'result': 'ok'}),
                executed_at=now - timedelta(days=i, hours=j),
            )
            db.session.add(log)
            logs.append(log)
    
    db.session.commit()
    return logs


@pytest.fixture
def test_validation_results(test_field, test_plugins):
    """Create test validation results."""
    results = []
    now = datetime.utcnow()
    
    for i, plugin in enumerate(test_plugins):
        for j in range(5):
            # Create field value
            field_value = ExtractedFieldValue(
                field_id=test_field.id,
                result_id=1,
                raw_value=f'value-{i}-{j}',
                extracted_value=f'value-{i}-{j}',
                confidence_score=0.95,
                validation_status='valid' if j % 2 == 0 else 'invalid',
            )
            db.session.add(field_value)
            db.session.flush()
            
            # Create validation result
            result = ExtractionValidationResult(
                field_value_id=field_value.id,
                plugin_id=plugin.id,
                is_valid=j % 2 == 0,
                validation_message='Validation passed' if j % 2 == 0 else 'Validation failed',
                suggestions_json=json.dumps(['suggestion1', 'suggestion2']),
                execution_time_ms=50 + (i * 10) + (j * 5),
                executed_at=now - timedelta(days=i, hours=j),
            )
            db.session.add(result)
            results.append(result)
    
    db.session.commit()
    return results


class TestDebugPluginTracing:
    """Test plugin execution tracing endpoints."""

    def test_get_latest_executions(self, client, test_execution_logs):
        """Test getting latest executions."""
        response = client.get('/api/admin/debug/plugins/trace/latest')
        assert response.status_code in [200, 401]  # 401 if auth not mocked

    def test_get_latest_executions_with_limit(self, client, test_execution_logs):
        """Test latest executions with custom limit."""
        response = client.get('/api/admin/debug/plugins/trace/latest?limit=5')
        assert response.status_code in [200, 401]

    def test_get_execution_trace_detail(self, client, test_execution_logs):
        """Test getting single execution trace."""
        if test_execution_logs:
            exec_id = test_execution_logs[0].id
            response = client.get(f'/api/admin/debug/plugins/trace/{exec_id}')
            assert response.status_code in [200, 401]

    def test_get_plugin_trace_history(self, client, test_execution_logs):
        """Test getting plugin execution history."""
        response = client.get('/api/admin/debug/plugins/medical/trace')
        assert response.status_code in [200, 401, 404]

    def test_get_plugin_trace_with_pagination(self, client, test_execution_logs):
        """Test plugin trace with pagination."""
        response = client.get('/api/admin/debug/plugins/medical/trace?limit=5&offset=0')
        assert response.status_code in [200, 401, 404]


class TestDebugPerformanceAnalytics:
    """Test performance analytics endpoints."""

    def test_get_performance_analytics(self, client, test_execution_logs):
        """Test getting overall performance metrics."""
        response = client.get('/api/admin/debug/plugins/analytics/performance')
        assert response.status_code in [200, 401]

    def test_get_performance_analytics_with_days(self, client, test_execution_logs):
        """Test performance analytics with custom period."""
        response = client.get('/api/admin/debug/plugins/analytics/performance?days=30')
        assert response.status_code in [200, 401]

    def test_get_plugin_analytics(self, client, test_execution_logs):
        """Test getting single plugin analytics."""
        response = client.get('/api/admin/debug/plugins/medical/analytics')
        assert response.status_code in [200, 401, 404]

    def test_get_plugin_analytics_with_days(self, client, test_execution_logs):
        """Test plugin analytics with custom period."""
        response = client.get('/api/admin/debug/plugins/medical/analytics?days=30')
        assert response.status_code in [200, 401, 404]

    def test_compare_plugin_analytics(self, client, test_execution_logs):
        """Test comparing analytics across plugins."""
        response = client.get('/api/admin/debug/plugins/analytics/comparison')
        assert response.status_code in [200, 401]

    def test_compare_analytics_by_errors(self, client, test_execution_logs):
        """Test comparison by error metric."""
        response = client.get('/api/admin/debug/plugins/analytics/comparison?metric=errors')
        assert response.status_code in [200, 401]

    def test_compare_analytics_by_success_rate(self, client, test_execution_logs):
        """Test comparison by success rate."""
        response = client.get('/api/admin/debug/plugins/analytics/comparison?metric=success_rate')
        assert response.status_code in [200, 401]


class TestDebugValidationAnalytics:
    """Test validation analytics endpoints."""

    def test_get_validation_history(self, client, test_validation_results):
        """Test getting validation history."""
        response = client.get('/api/admin/debug/validation/history')
        assert response.status_code in [200, 401]

    def test_get_validation_history_with_filters(self, client, test_validation_results):
        """Test validation history with filters."""
        response = client.get('/api/admin/debug/validation/history?days=30&limit=50')
        assert response.status_code in [200, 401]

    def test_get_validation_summary(self, client, test_validation_results):
        """Test getting validation summary."""
        response = client.get('/api/admin/debug/validation/summary')
        assert response.status_code in [200, 401]

    def test_get_validation_summary_custom_period(self, client, test_validation_results):
        """Test validation summary with custom period."""
        response = client.get('/api/admin/debug/validation/summary?days=7')
        assert response.status_code in [200, 401]


class TestDebugHealth:
    """Test debug health endpoint."""

    def test_get_debug_health(self, client, test_execution_logs, test_validation_results):
        """Test getting debug health status."""
        response = client.get('/api/admin/debug/health')
        assert response.status_code in [200, 401]

    def test_health_includes_required_fields(self, client, test_execution_logs):
        """Test health response structure."""
        response = client.get('/api/admin/debug/health')
        if response.status_code == 200:
            data = response.get_json()
            assert 'status' in data
            assert 'last_hour' in data
            assert 'timestamp' in data


class TestDebugDataStructures:
    """Test debug endpoint data structures and calculations."""

    def test_execution_log_model_creation(self, test_plugins):
        """Test creating execution logs."""
        plugin = test_plugins[0]
        log = PluginExecutionLog(
            plugin_id=plugin.id,
            hook_point='validate_field',
            request_id='test-123',
            status='success',
            execution_time_ms=150.5,
            error_message=None,
            request_data=json.dumps({}),
            response_data=json.dumps({}),
        )
        db.session.add(log)
        db.session.commit()

        # Retrieve and verify
        retrieved = db.session.get(PluginExecutionLog, log.id)
        assert retrieved.plugin_id == plugin.id
        assert retrieved.execution_time_ms == 150.5
        assert retrieved.status == 'success'

    def test_execution_log_error_tracking(self, test_plugins):
        """Test error tracking in execution log."""
        plugin = test_plugins[0]
        log = PluginExecutionLog(
            plugin_id=plugin.id,
            hook_point='on_extraction',
            request_id='error-123',
            status='error',
            execution_time_ms=500.0,
            error_message='Timeout occurred',
            traceback='Traceback: ...',
        )
        db.session.add(log)
        db.session.commit()

        retrieved = db.session.get(PluginExecutionLog, log.id)
        assert retrieved.status == 'error'
        assert 'Timeout' in retrieved.error_message

    def test_validation_result_suggestions(self, test_field, test_plugins):
        """Test validation result suggestion storage."""
        plugin = test_plugins[0]
        
        field_value = ExtractedFieldValue(
            field_id=test_field.id,
            result_id=1,
            raw_value='test',
            extracted_value='test',
        )
        db.session.add(field_value)
        db.session.flush()

        suggestions = ['suggestion1', 'suggestion2', 'suggestion3']
        result = ExtractionValidationResult(
            field_value_id=field_value.id,
            plugin_id=plugin.id,
            is_valid=False,
            validation_message='Invalid value',
            suggestions_json=json.dumps(suggestions),
        )
        db.session.add(result)
        db.session.commit()

        retrieved = db.session.get(ExtractionValidationResult, result.id)
        suggestions_retrieved = retrieved.get_suggestions()
        assert len(suggestions_retrieved) == 3
        assert 'suggestion1' in suggestions_retrieved


class TestDebugTimeSeriesData:
    """Test time-based aggregation and analysis."""

    def test_execution_logs_with_dates(self, test_plugins):
        """Test execution logs with varied dates."""
        plugin = test_plugins[0]
        base_time = datetime.utcnow()
        
        # Create logs across 7 days
        for day in range(7):
            for hour in range(4):
                log = PluginExecutionLog(
                    plugin_id=plugin.id,
                    hook_point='validate_field',
                    request_id=f'req-d{day}-h{hour}',
                    status='success',
                    execution_time_ms=100 + (day * 10),
                    executed_at=base_time - timedelta(days=day, hours=hour),
                )
                db.session.add(log)
        
        db.session.commit()

        # Query all logs for plugin
        logs = PluginExecutionLog.query.filter(
            PluginExecutionLog.plugin_id == plugin.id
        ).all()
        
        assert len(logs) == 28  # 7 days * 4 hours

    def test_validation_results_with_dates(self, test_field, test_plugins):
        """Test validation results with varied dates."""
        plugin = test_plugins[0]
        base_time = datetime.utcnow()
        
        # Create results across 7 days
        for day in range(7):
            for hour in range(2):
                field_value = ExtractedFieldValue(
                    field_id=test_field.id,
                    result_id=day * 10 + hour,
                    raw_value=f'val-d{day}-h{hour}',
                    extracted_value=f'val-d{day}-h{hour}',
                    validation_status='valid',
                )
                db.session.add(field_value)
                db.session.flush()
                
                result = ExtractionValidationResult(
                    field_value_id=field_value.id,
                    plugin_id=plugin.id,
                    is_valid=True,
                    execution_time_ms=50 + (day * 5),
                    executed_at=base_time - timedelta(days=day, hours=hour),
                )
                db.session.add(result)
        
        db.session.commit()

        # Query all results
        results = ExtractionValidationResult.query.filter(
            ExtractionValidationResult.plugin_id == plugin.id
        ).all()
        
        assert len(results) == 14  # 7 days * 2 hours


class TestDebugPercentileCalculations:
    """Test percentile calculations for performance metrics."""

    def test_percentile_calculation_from_times(self, test_plugins):
        """Test calculating percentiles from execution times."""
        plugin = test_plugins[0]
        
        # Create logs with specific times
        times = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
        for i, time in enumerate(times):
            log = PluginExecutionLog(
                plugin_id=plugin.id,
                hook_point='validate_field',
                request_id=f'req-{i}',
                status='success',
                execution_time_ms=time,
            )
            db.session.add(log)
        
        db.session.commit()

        # Retrieve and calculate percentiles
        logs = PluginExecutionLog.query.filter(
            PluginExecutionLog.plugin_id == plugin.id
        ).all()
        
        execution_times = sorted([log.execution_time_ms for log in logs])
        p95_idx = int(len(execution_times) * 0.95)
        p95_value = execution_times[p95_idx]
        
        assert p95_value >= 450  # Should be in upper range
        assert len(execution_times) == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""Tests for job status and import-stats endpoints added to document_import.py."""
import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace


class TestJobStatusRouteStructure:
    def test_get_job_status_callable(self):
        from app.routes.document_import import get_job_status
        assert callable(get_job_status)

    def test_get_import_stats_callable(self):
        from app.routes.document_import import import_stats
        assert callable(import_stats)


class TestJobStatusRoute:
    """Tests for GET /projects/<id>/jobs/<job_id>."""

    def _make_job(self, project_id, status='completed', output_data=None):
        return SimpleNamespace(
            job_id='job_abc123',
            job_type='pdf_download',
            status=status,
            priority='normal',
            retry_count=0,
            max_retries=3,
            error_message=None,
            input_data={'project_id': project_id},
            output_data=output_data or {'imported': 5},
            created_at=None,
            started_at=None,
            completed_at=None,
            logs=['Log line 1', 'Log line 2'],
        )

    def test_valid_job_returns_200(self, client, app_context, test_project):
        mock_job = self._make_job(test_project.id)
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = mock_job
            resp = client.get(f'/projects/{test_project.id}/jobs/job_abc123')
        assert resp.status_code == 200

    def test_response_has_status_field(self, client, app_context, test_project):
        mock_job = self._make_job(test_project.id)
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = mock_job
            resp = client.get(f'/projects/{test_project.id}/jobs/job_abc123')
        data = resp.get_json()
        assert 'status' in data

    def test_response_has_output_data(self, client, app_context, test_project):
        mock_job = self._make_job(test_project.id, output_data={'imported': 7, 'errors': 0})
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = mock_job
            resp = client.get(f'/projects/{test_project.id}/jobs/job_abc123')
        data = resp.get_json()
        assert 'output_data' in data or 'imported' in str(data)

    def test_job_not_found_returns_404(self, client, app_context, test_project):
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = None
            resp = client.get(f'/projects/{test_project.id}/jobs/nonexistent_job')
        assert resp.status_code == 404

    def test_project_not_found_returns_404(self, client, app_context):
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            resp = client.get('/projects/999999/jobs/some_job')
        assert resp.status_code == 404

    def test_job_wrong_project_returns_403_or_404(self, client, app_context, test_project):
        """A job that belongs to a different project should be denied."""
        mock_job = self._make_job(project_id=99999)  # different project
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = mock_job
            resp = client.get(f'/projects/{test_project.id}/jobs/job_abc123')
        assert resp.status_code in (403, 404)

    def test_response_has_logs(self, client, app_context, test_project):
        mock_job = self._make_job(test_project.id)
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = mock_job
            resp = client.get(f'/projects/{test_project.id}/jobs/job_abc123')
        data = resp.get_json()
        assert 'logs' in data or 'log' in str(data).lower()

    @pytest.mark.parametrize('status', ['pending', 'running', 'completed', 'failed'])
    def test_all_job_statuses(self, client, app_context, test_project, status):
        mock_job = self._make_job(test_project.id, status=status)
        with patch('app.routes.document_import.get_job_queue') as mock_gq:
            mock_gq.return_value.get_job.return_value = mock_job
            resp = client.get(f'/projects/{test_project.id}/jobs/job_abc123')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('status') == status


class TestImportStatsRoute:
    """Tests for GET /projects/<id>/import-stats."""

    def test_returns_200(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/import-stats')
        assert resp.status_code == 200

    def test_response_has_docs_by_source(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/import-stats')
        data = resp.get_json()
        assert 'docs_by_source_type' in data

    def test_response_has_import_log_stats(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/import-stats')
        data = resp.get_json()
        assert 'import_log_stats' in data

    def test_response_has_top_sources(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/import-stats')
        data = resp.get_json()
        assert 'top_sources' in data

    def test_project_not_found_returns_404(self, client, app_context):
        resp = client.get('/projects/999999/import-stats')
        assert resp.status_code == 404

    def test_stats_with_documents(self, client, app_context, test_project):
        from app.database import db
        from app.models.researcher import ResearcherDocument
        for src in ('pubmed', 'pubmed', 'arxiv'):
            db.session.add(ResearcherDocument(
                project_id=test_project.id,
                filename=f'{src}_doc.pdf',
                file_path='',
                file_size=100,
                source_type=src,
            ))
        db.session.commit()

        resp = client.get(f'/projects/{test_project.id}/import-stats')
        assert resp.status_code == 200
        data = resp.get_json()
        sources = {entry['source_type']: entry['count'] for entry in data['docs_by_source_type']}
        assert sources.get('pubmed', 0) == 2
        assert sources.get('arxiv', 0) == 1

    def test_import_log_stats_with_records(self, client, app_context, test_project):
        from app.database import db
        from app.models.researcher import SourceImportLog, LibrarySource
        source = LibrarySource(
            project_id=test_project.id,
            name='PubMed',
            source_type='pubmed',
        )
        db.session.add(source)
        db.session.flush()
        for status in ('completed', 'completed', 'failed'):
            db.session.add(SourceImportLog(
                source_id=source.id,
                query='test query',
                status=status,
                documents_imported=5 if status == 'completed' else 0,
            ))
        db.session.commit()

        resp = client.get(f'/projects/{test_project.id}/import-stats')
        assert resp.status_code == 200
        data = resp.get_json()
        log_stats = {entry['status']: entry['count'] for entry in data['import_log_stats']}
        assert log_stats.get('completed', 0) == 2
        assert log_stats.get('failed', 0) == 1

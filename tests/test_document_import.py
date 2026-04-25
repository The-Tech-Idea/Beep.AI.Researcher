import importlib


module = importlib.import_module('app.jobs.pdf_download_handler')


class DummyJob:
    def __init__(self, input_data):
        self.input_data = input_data


def test_handle_pdf_download_missing_params():
    """Handler should return error when required params are missing."""
    job = DummyJob(input_data={})
    result = module.handle_pdf_download(job)
    assert isinstance(result, dict)
    assert result.get('success') is False
    assert 'Missing document_id' in result.get('error', '')


def test_handle_pdf_download_no_requests(monkeypatch):
    """If requests is unavailable, handler returns an explanatory error."""
    module = importlib.import_module('app.jobs.pdf_download_handler')
    # Ensure requests is treated as None inside module (non-raising)
    monkeypatch.setattr(module, 'requests', None, raising=False)
    job = DummyJob(input_data={'document_id': '1', 'pdf_url': 'https://example.com/test.pdf', 'project_id': 1})
    result = module.handle_pdf_download(job)
    assert isinstance(result, dict)
    assert result.get('success') is False
    assert 'requests library not available' in result.get('error', '')

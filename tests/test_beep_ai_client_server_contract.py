from types import SimpleNamespace

from app.config_manager import config_manager
from app.services import beep_ai_client


class _FakeResponse:
    def __init__(self, payload=None, status_code=200, content_type='application/json'):
        self._payload = payload or {}
        self.status_code = status_code
        self.headers = {'content-type': content_type}

    def json(self):
        return self._payload



def test_chat_reply_uses_openai_v1_with_application_token(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(
            payload={
                'choices': [
                    {'message': {'content': 'Answer from server'}}
                ]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    ok, text = beep_ai_client.chat_reply(
        messages=[{'role': 'user', 'content': 'Summarize this paper'}],
        user_id='42',
        user_role='admin',
        temperature=0.2,
    )

    assert ok is True
    assert text == 'Answer from server'
    assert captured['url'] == 'http://localhost:5000/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured['headers']['X-User-ID'] == '42'
    assert captured['json']['execution_context']['application_id'] == 'researcher'
    assert captured['json']['execution_context']['user_id'] == '42'
    assert captured['json']['execution_context']['role_name'] == 'admin'



def test_query_project_rag_uses_v1_rag_with_scoped_payload_and_token(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(
            payload={
                'results': [{'content': 'Chunk 1'}],
                'citations': [{'id': 'doc-1', 'source': 'Paper A'}]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(
        id=7,
        collection_id='collection-7',
        tenant_id=9,
        owner_id=42,
        members=[],
    )

    ok, result = beep_ai_client.query_project_rag(
        project=project,
        query='effects of policy change',
        max_results=4,
        user_id=42,
        quality_mode='high',
        rewrite_query=True,
        hybrid_search=True,
        rerank=True,
        return_full=True,
    )

    assert ok is True
    assert result['results'][0]['content'] == 'Chunk 1'
    assert captured['url'] == 'http://localhost:5000/v1/rag/query'
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured['json']['app_id'] == 'researcher'
    assert captured['json']['collection_id'] == 'collection-7'
    assert captured['json']['collection_ids'] == ['collection-7']
    assert captured['json']['user_id'] == '42'
    assert captured['json']['user_role'] == 'admin'
    assert captured['json']['project_id'] == '7'
    assert captured['json']['tenant_id'] == '9'
    assert captured['json']['quality_mode'] == 'high'
    assert captured['json']['rewrite_query'] is True
    assert captured['json']['hybrid_search'] is True
    assert captured['json']['rerank'] is True
    assert captured['json']['filters']['project_id'] == '7'



def test_query_project_rag_uses_saved_project_quality_mode_when_omitted(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(payload={'results': []})

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(
        id=7,
        collection_id='collection-7',
        tenant_id=9,
        owner_id=42,
        members=[],
        rag_quality_mode='deep',
    )

    ok, result = beep_ai_client.query_project_rag(
        project=project,
        query='effects of policy change',
        max_results=4,
        user_id=42,
        return_full=True,
    )

    assert ok is True
    assert result['results'] == []
    assert captured['json']['quality_mode'] == 'deep'


def test_add_document_to_project_rag_uses_saved_project_quality_mode_when_omitted(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(payload={'success': True, 'indexed_count': 1})

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(
        id=7,
        collection_id='collection-7',
        tenant_id=9,
        owner_id=42,
        members=[],
        rag_quality_mode='deep',
    )

    ok, result = beep_ai_client.add_document_to_project_rag(
        project=project,
        document_content='Study content',
        source='study.pdf',
        user_id=42,
        metadata={'document_kind': 'research-paper'},
    )

    assert ok is True
    assert result['indexed_count'] == 1
    assert captured['url'] == 'http://localhost:5000/v1/rag/documents'
    assert captured['json']['metadata']['quality_mode'] == 'deep'


def test_agent_plan_endpoints_use_middleware_with_application_token(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured_posts = []
    captured_gets = []

    def fake_post(url, json=None, headers=None, timeout=None):
        captured_posts.append({
            'url': url,
            'json': json,
            'headers': headers,
            'timeout': timeout,
        })
        return _FakeResponse(payload={'success': True, 'session_id': 'sess-1'})

    def fake_get(url, headers=None, timeout=None):
        captured_gets.append({
            'url': url,
            'headers': headers,
            'timeout': timeout,
        })
        return _FakeResponse(payload={'success': True, 'sessions': [{'session_id': 'sess-1'}]})

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)
    monkeypatch.setattr(beep_ai_client.requests, 'get', fake_get)

    ok_create, result_create = beep_ai_client.create_agent_plan(
        objective='Review the related literature',
        context={'project_id': 7},
        user_id='42',
        user_role='admin',
    )
    ok_list, result_list = beep_ai_client.list_agent_sessions(limit=5)

    assert ok_create is True
    assert result_create['session_id'] == 'sess-1'
    assert captured_posts[0]['url'] == 'http://localhost:5000/ai-middleware/api/agent/plan'
    assert captured_posts[0]['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured_posts[0]['json']['goal'] == 'Review the related literature'
    assert captured_posts[0]['json']['context']['project_id'] == 7
    assert captured_posts[0]['json']['user_id'] == '42'
    assert captured_posts[0]['json']['user_role'] == 'admin'

    assert ok_list is True
    assert result_list['sessions'][0]['session_id'] == 'sess-1'
    assert captured_gets[0]['url'] == 'http://localhost:5000/ai-middleware/api/agent/sessions?limit=5'
    assert captured_gets[0]['headers']['Authorization'] == 'Bearer researcher-token'



def test_extract_structured_uses_openai_v1_with_application_token(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(
            payload={
                'choices': [
                    {'message': {'content': '{"title":"Paper title"}'}}
                ]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(id=7, collection_id='collection-7', tenant_id=9, owner_id=42, members=[])
    ok, result = beep_ai_client.extract_structured(
        project=project,
        document_text='Sample abstract text',
        schema_fields=[{'name': 'title', 'description': 'Paper title', 'field_type': 'string', 'required': True}],
        schema_name='Paper schema',
        document_id='doc-7',
        user_id=42,
    )

    assert ok is True
    assert result['extracted_fields']['title'] == 'Paper title'
    assert captured['url'] == 'http://localhost:5000/v1/chat/completions'
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured['headers']['X-User-ID'] == '42'
    assert captured['json']['execution_context']['application_id'] == 'researcher'
    assert captured['json']['execution_context']['user_id'] == '42'
    assert captured['json']['execution_context']['role_name'] == 'admin'
    assert 'Schema: Paper schema' in captured['json']['messages'][1]['content']
    assert 'Document ID: doc-7' in captured['json']['messages'][1]['content']
    assert 'Sample abstract text' in captured['json']['messages'][1]['content']


def test_extract_structured_includes_supporting_library_evidence_when_provided(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['json'] = json
        return _FakeResponse(
            payload={
                'choices': [
                    {'message': {'content': '{"title":"Paper title"}'}}
                ]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(id=7, collection_id='collection-7', tenant_id=9, owner_id=42, members=[])
    ok, result = beep_ai_client.extract_structured(
        project=project,
        document_text='Sample abstract text',
        schema_fields=[{'name': 'title', 'description': 'Paper title', 'field_type': 'string', 'required': True}],
        schema_name='Paper schema',
        document_id='doc-7',
        user_id=42,
        supporting_context='[1] Paper A [Doc 10]: Supporting evidence for terminology.',
    )

    assert ok is True
    assert result['extracted_fields']['title'] == 'Paper title'
    assert 'Supporting library evidence:' in captured['json']['messages'][1]['content']
    assert 'Supporting evidence for terminology.' in captured['json']['messages'][1]['content']



def test_detect_contradictions_uses_rag_query_and_openai_v1(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({
            'url': url,
            'json': json,
            'headers': headers,
            'timeout': timeout,
        })
        if url.endswith('/v1/rag/query'):
            return _FakeResponse(
                payload={
                    'results': [
                        {'document_id': '10', 'source': 'Paper A', 'content': 'The treatment works well.', 'score': 0.91},
                        {'document_id': '11', 'source': 'Paper B', 'content': 'The treatment does not work.', 'score': 0.88},
                    ]
                }
            )
        return _FakeResponse(
            payload={
                'choices': [
                    {
                        'message': {
                            'content': (
                                '{"contradictions":[{"claim_a":"The treatment works well.",'
                                '"source_a":{"document_id":"10","filename":"Paper A"},'
                                '"claim_b":"The treatment does not work.",'
                                '"source_b":{"document_id":"11","filename":"Paper B"},'
                                '"severity":"high","explanation":"The sources disagree on treatment efficacy."}],'
                                '"total_sources_checked":2}'
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(id=7, collection_id=None, tenant_id=None, owner_id=42, members=[])
    ok, result = beep_ai_client.detect_contradictions(
        project=project,
        query='Does the treatment work?',
        document_ids=['10', '11'],
        max_sources=6,
        user_id=42,
    )

    assert ok is True
    assert result['total_sources_checked'] == 2
    assert len(result['contradictions']) == 1

    rag_call = calls[0]
    assert rag_call['url'] == 'http://localhost:5000/v1/rag/query'
    assert rag_call['headers']['Authorization'] == 'Bearer researcher-token'
    assert rag_call['json']['collection_id'] == 'researcher_project_7'
    assert rag_call['json']['collection_ids'] == ['researcher_project_7']
    assert rag_call['json']['project_id'] == '7'
    assert rag_call['json']['user_id'] == '42'

    chat_call = calls[1]
    assert chat_call['url'] == 'http://localhost:5000/v1/chat/completions'
    assert chat_call['headers']['Authorization'] == 'Bearer researcher-token'
    assert chat_call['headers']['X-User-ID'] == '42'
    assert chat_call['json']['execution_context']['application_id'] == 'researcher'
    assert 'Does the treatment work?' in chat_call['json']['messages'][1]['content']


def test_find_citations_uses_v1_rag_query_route(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({
            'url': url,
            'json': json,
            'headers': headers,
            'timeout': timeout,
        })
        return _FakeResponse(
            payload={
                'results': [
                    {'document_id': '10', 'source': 'Paper A', 'content': 'The intervention reduced symptoms significantly.', 'score': 0.93},
                    {'document_id': '11', 'source': 'Paper B', 'content': 'The intervention improved adherence in older adults.', 'score': 0.81},
                ]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(id=7, collection_id='collection-7', tenant_id=9, owner_id=42, members=[])
    ok, result = beep_ai_client.find_citations_for_draft(
        project=project,
        draft_text='The intervention appears to reduce symptoms and improve adherence.',
        max_citations=2,
        user_id=42,
    )

    assert ok is True
    assert len(result['citations']) == 2
    assert result['citations'][0]['document_id'] == '10'
    assert calls[0]['url'] == 'http://localhost:5000/v1/rag/query'
    assert calls[0]['headers']['Authorization'] == 'Bearer researcher-token'
    assert calls[0]['json']['collection_ids'] == ['collection-7']
    assert calls[0]['json']['project_id'] == '7'
    assert calls[0]['json']['user_id'] == '42'


def test_query_with_context_uses_v1_rag_query_route(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(
            payload={
                'results': [
                    {'document_id': '10', 'source': 'Paper A', 'content': 'Relevant excerpt', 'score': 0.91, 'page': 4, 'section': 'Results'}
                ]
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(id=7, collection_id='collection-7', tenant_id=9, owner_id=42, members=[])
    ok, result = beep_ai_client.query_with_context(
        project=project,
        query='Find related evidence',
        max_results=3,
        return_provenance=True,
        context_window=2,
        user_id=42,
    )

    assert ok is True
    assert result['results'][0]['document_id'] == '10'
    assert captured['url'] == 'http://localhost:5000/v1/rag/query'
    assert captured['json']['collection_ids'] == ['collection-7']
    assert captured['json']['project_id'] == '7'
    assert captured['json']['user_id'] == '42'
    assert result['return_provenance'] is True
    assert result['context_window'] == 2


def test_check_health_falls_back_to_openai_health_endpoint(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    urls = []

    def fake_get(url, headers=None, timeout=None):
        urls.append(url)
        if url.endswith('/v1/health'):
            return _FakeResponse(payload={'status': 'ok'})
        return _FakeResponse(payload={'error': 'not found'}, status_code=404)

    monkeypatch.setattr(beep_ai_client.requests, 'get', fake_get)

    ok, result = beep_ai_client.check_health()

    assert ok is True
    assert result['status'] == 'ok'
    assert urls == [
        'http://localhost:5000/ai-middleware/api/health',
        'http://localhost:5000/ai-middleware/api/operational-status',
        'http://localhost:5000/v1/health',
    ]


def test_collection_organization_profile_routes_use_v1(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured_get = {}
    captured_put = {}

    def fake_get(url, headers=None, timeout=None):
        captured_get['url'] = url
        captured_get['headers'] = headers
        captured_get['timeout'] = timeout
        return _FakeResponse(
            payload={
                'success': True,
                'organization_profile': {
                    'chunking': {'strategy': 'semantic', 'chunk_size_chars': 3200, 'chunk_overlap_chars': 480}
                }
            }
        )

    def fake_put(url, json=None, headers=None, timeout=None):
        captured_put['url'] = url
        captured_put['json'] = json
        captured_put['headers'] = headers
        captured_put['timeout'] = timeout
        return _FakeResponse(payload={'success': True, 'organization_profile': json['organization_profile']})

    monkeypatch.setattr(beep_ai_client.requests, 'get', fake_get)
    monkeypatch.setattr(beep_ai_client.requests, 'put', fake_put)

    ok_get, profile = beep_ai_client.get_collection_organization_profile('collection-7', user_id='42', quality_mode='balanced')
    ok_put, result = beep_ai_client.update_collection_organization_profile(
        'collection-7',
        {'chunking': {'strategy': 'hierarchical', 'chunk_size_chars': 2400, 'chunk_overlap_chars': 600}},
        metadata_schema={'version': '2.0'},
        graph_extraction_profile_id='system-research-citation-graph',
        user_id='42',
        user_role='admin',
    )

    assert ok_get is True
    assert profile['chunking']['strategy'] == 'semantic'
    assert captured_get['url'] == 'http://localhost:5000/v1/rag/collections/collection-7/organization-profile?quality_mode=balanced'
    assert captured_get['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured_get['headers']['X-User-ID'] == '42'

    assert ok_put is True
    assert result['organization_profile']['chunking']['strategy'] == 'hierarchical'
    assert captured_put['url'] == 'http://localhost:5000/v1/rag/collections/collection-7/organization-profile'
    assert captured_put['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured_put['json']['user_id'] == '42'
    assert captured_put['json']['user_role'] == 'admin'
    assert captured_put['json']['metadata_schema']['version'] == '2.0'
    assert captured_put['json']['graph_extraction_profile_id'] == 'system-research-citation-graph'


def test_collection_document_inspection_routes_use_v1(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = []

    def fake_get(url, headers=None, timeout=None):
        captured.append({'url': url, 'headers': headers, 'timeout': timeout})
        return _FakeResponse(payload={'success': True, 'document_id': 'doc-7', 'chunks': []})

    monkeypatch.setattr(beep_ai_client.requests, 'get', fake_get)

    ok_chunks, chunks = beep_ai_client.get_collection_document_chunks(
        'collection-7',
        'doc-7',
        user_id='42',
        include_content=True,
        preview_chars=320,
    )
    ok_lineage, lineage = beep_ai_client.get_collection_document_lineage(
        'collection-7',
        'doc-7',
        user_id='42',
    )

    assert ok_chunks is True
    assert ok_lineage is True
    assert chunks['document_id'] == 'doc-7'
    assert lineage['document_id'] == 'doc-7'
    assert captured[0]['url'] == 'http://localhost:5000/v1/rag/documents/doc-7/chunks?include_content=true&preview_chars=320&collection_id=collection-7'
    assert captured[0]['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured[0]['headers']['X-User-ID'] == '42'
    assert captured[1]['url'] == 'http://localhost:5000/v1/rag/documents/doc-7/lineage?collection_id=collection-7'
    assert captured[1]['headers']['Authorization'] == 'Bearer researcher-token'
    assert captured[1]['headers']['X-User-ID'] == '42'


def test_graph_extraction_profile_options_use_middleware(monkeypatch):
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured['url'] = url
        captured['headers'] = headers
        captured['timeout'] = timeout
        return _FakeResponse(
            payload={
                'success': True,
                'profiles': [
                    {'profile_id': 'system-balanced-graph-extraction', 'name': 'Balanced Graph Extraction'},
                ],
            }
        )

    monkeypatch.setattr(beep_ai_client.requests, 'get', fake_get)

    ok, profiles = beep_ai_client.list_graph_extraction_profile_options()

    assert ok is True
    assert profiles[0]['profile_id'] == 'system-balanced-graph-extraction'
    assert captured['url'] == 'http://localhost:5000/ai-middleware/api/rag/runtime/graph-extraction-profiles/options'
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'


# ---------------------------------------------------------------------------
# Phase 07 — correlation ID and reference metadata ingest
# ---------------------------------------------------------------------------


def test_headers_always_emit_x_request_id(monkeypatch):
    """Every call to Beep.AI.Server must include an X-Request-ID trace header."""
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['headers'] = headers
        return _FakeResponse(payload={'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(id=7, collection_id='collection-7', tenant_id=9, owner_id=42, members=[])
    beep_ai_client.chat_reply(
        messages=[{'role': 'user', 'content': 'hello'}],
        user_id=42,
    )

    import uuid as _uuid
    request_id = captured['headers'].get('X-Request-ID', '')
    # Must be a valid UUID4
    parsed = _uuid.UUID(request_id, version=4)
    assert str(parsed) == request_id


def test_headers_propagate_custom_correlation_id(monkeypatch):
    """When a correlation_id is supplied to _headers it must be forwarded verbatim."""
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['headers'] = headers
        return _FakeResponse(payload={'choices': [{'message': {'content': 'ok'}}]})

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    fixed_id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
    headers = beep_ai_client._headers(user_id=1, correlation_id=fixed_id)
    assert headers['X-Request-ID'] == fixed_id


def test_add_document_to_project_rag_sends_collection_and_reference_metadata(monkeypatch):
    """Ingesting a reference chunk must route to the project collection and carry metadata."""
    config_manager.set('beep_ai_server_url', 'http://localhost:5000')
    config_manager.set('beep_ai_server_token', 'researcher-token')

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['json'] = json
        captured['headers'] = headers
        return _FakeResponse(payload={'success': True, 'indexed_count': 1})

    monkeypatch.setattr(beep_ai_client.requests, 'post', fake_post)

    project = SimpleNamespace(
        id=3,
        collection_id='collection-3',
        tenant_id=5,
        owner_id=7,
        members=[],
    )

    ok, result = beep_ai_client.add_document_to_project_rag(
        project=project,
        document_content='Title: On the Origin of Species\nAuthors: Darwin, C.\nAbstract: Natural selection.',
        source='on_the_origin.pdf',
        document_id='reference_42',
        user_id=7,
        metadata={
            'source_type': 'reference',
            'reference_id': '42',
            'citation_key': 'Darwin1859',
        },
    )

    assert ok is True
    assert result['indexed_count'] == 1
    assert captured['url'] == 'http://localhost:5000/v1/rag/documents'
    assert captured['json']['collection_id'] == 'collection-3'
    # Authorization uses application token
    assert captured['headers']['Authorization'] == 'Bearer researcher-token'
    # Stable document key must be forwarded
    doc = captured['json']
    assert doc['id'] == 'reference_42'
    # Reference metadata must survive into the chunk payload
    assert doc['metadata']['reference_id'] == '42'
    assert doc['metadata']['citation_key'] == 'Darwin1859'
    assert doc['metadata']['source_type'] == 'reference'

from app.database import db
from app.models.researcher import ResearchProject
from app.routes import projects as project_routes
from app.services.chunk_template_service import get_document_type_template_contract
from app.services.graph_reading_mode_service import get_graph_reading_mode_contract


def _set_project_collection(project_id, collection_id):
    project = db.session.get(ResearchProject, project_id)
    project.collection_id = collection_id
    db.session.commit()
    return project


def _set_project_quality_mode(project_id, quality_mode):
    project = db.session.get(ResearchProject, project_id)
    project.rag_quality_mode = quality_mode
    db.session.commit()
    return project


def test_get_project_rag_organization_profile_forwards_collection_scope(client, app_context, test_project, monkeypatch):
    _set_project_collection(test_project.id, 'collection-42')

    captured = {}

    def fake_get(collection_id, user_id=None, quality_mode=None):
        captured['collection_id'] = collection_id
        captured['user_id'] = user_id
        captured['quality_mode'] = quality_mode
        return True, {
            'chunking': {
                'strategy': 'semantic',
                'chunk_size_chars': 3200,
                'chunk_overlap_chars': 480,
            },
            'chunking_source': 'collection_override',
            'metadata_defaults': {'language': 'en'},
            'metadata_defaults_source': 'collection_override',
            'metadata_schema': {'version': '2.0', 'filterable_fields': ['language']},
            'metadata_schema_source': 'collection_override',
            'database_default_chunk_template_id': 'system-research-corpus',
            'database_default_chunk_template_name': 'Research Papers',
            'chunk_template_name': 'Detailed Paper Reading',
            'collection_graph_extraction_profile_id': 'system-research-citation-graph',
            'database_default_graph_extraction_profile_id': 'system-balanced-graph-extraction',
            'graph_extraction_profile_id': 'system-research-citation-graph',
        }

    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)
    monkeypatch.setattr(project_routes, 'get_collection_organization_profile', fake_get)
    monkeypatch.setattr(
        project_routes,
        'list_graph_extraction_profile_options',
        lambda: (True, [{'profile_id': 'system-balanced-graph-extraction', 'name': 'Balanced Graph Extraction'}]),
    )

    response = client.get(f'/projects/{test_project.id}/rag/organization-profile?quality_mode=deep')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['collection_id'] == 'collection-42'
    assert payload['quality_mode'] == 'deep'
    assert payload['quality_mode_source'] == 'saved_project_choice'
    assert payload['organization_profile']['chunking']['strategy'] == 'semantic'
    assert payload['organization_profile']['chunking_source'] == 'collection_override'
    assert payload['organization_profile']['metadata_defaults_source'] == 'collection_override'
    assert payload['organization_profile']['metadata_schema_source'] == 'collection_override'
    assert payload['organization_profile']['database_default_chunk_template_name'] == 'Research Papers'
    assert payload['organization_profile']['chunk_template_name'] == 'Detailed Paper Reading'
    assert payload['graph_reading_mode']['mode'] == 'citations_and_evidence'
    assert payload['graph_reading_mode']['database_default_graph_extraction_profile_label'] == 'General relationships'
    assert payload['graph_reading_mode']['effective_graph_extraction_profile_label'] == 'Citations and evidence'
    assert captured['collection_id'] == 'collection-42'
    assert captured['quality_mode'] == 'deep'
    assert captured['user_id']


def test_put_project_rag_organization_profile_forwards_schema_scope(client, app_context, test_project, monkeypatch):
    _set_project_collection(test_project.id, 'collection-42')

    captured = {}

    def fake_put(collection_id, organization_profile, **kwargs):
        captured['collection_id'] = collection_id
        captured['organization_profile'] = organization_profile
        captured['kwargs'] = kwargs
        return True, {
            'organization_profile': {
                **organization_profile,
                'metadata_schema': kwargs.get('metadata_schema'),
                'chunking_source': 'collection_override',
                'metadata_defaults_source': 'collection_override',
                'metadata_schema_source': 'collection_override',
                'database_default_chunk_template_id': 'system-research-corpus',
                'database_default_chunk_template_name': 'Research Papers',
                'chunk_template_name': 'Detailed Paper Reading',
                'collection_graph_extraction_profile_id': kwargs.get('graph_extraction_profile_id'),
                'database_default_graph_extraction_profile_id': 'system-balanced-graph-extraction',
                'graph_extraction_profile_id': kwargs.get('graph_extraction_profile_id'),
            }
        }

    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)
    monkeypatch.setattr(project_routes, 'update_collection_organization_profile', fake_put)
    monkeypatch.setattr(
        project_routes,
        'list_graph_extraction_profile_options',
        lambda: (True, [{'profile_id': 'system-balanced-graph-extraction', 'name': 'Balanced Graph Extraction'}]),
    )

    response = client.put(
        f'/projects/{test_project.id}/rag/organization-profile',
        json={
            'quality_mode': 'balanced',
            'graph_extraction_profile_id': 'system-research-citation-graph',
            'organization_profile': {
                'chunking': {
                    'strategy': 'hierarchical',
                    'chunk_size_chars': 2400,
                    'chunk_overlap_chars': 600,
                    'enrich_context': True,
                },
                'metadata_defaults': {
                    'language': 'en',
                    'document_kind': 'paper',
                    'source_type': 'uploaded',
                },
                'metadata_schema': {
                    'version': '2.0',
                    'filterable_fields': ['document_kind', 'source_type'],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['collection_id'] == 'collection-42'
    assert payload['quality_mode'] == 'balanced'
    assert payload['quality_mode_source'] == 'saved_project_choice'
    assert payload['organization_profile']['chunking_source'] == 'collection_override'
    assert payload['organization_profile']['metadata_defaults_source'] == 'collection_override'
    assert payload['organization_profile']['metadata_schema_source'] == 'collection_override'
    assert payload['organization_profile']['database_default_chunk_template_name'] == 'Research Papers'
    assert payload['organization_profile']['chunk_template_name'] == 'Detailed Paper Reading'
    assert payload['graph_reading_mode']['mode'] == 'citations_and_evidence'
    assert payload['graph_reading_mode']['database_default_graph_extraction_profile_label'] == 'General relationships'
    assert payload['graph_reading_mode']['effective_graph_extraction_profile_label'] == 'Citations and evidence'
    assert captured['collection_id'] == 'collection-42'
    assert captured['organization_profile']['chunking']['strategy'] == 'hierarchical'
    assert captured['kwargs']['quality_mode'] == 'balanced'
    assert captured['kwargs']['graph_extraction_profile_id'] == 'system-research-citation-graph'
    assert captured['kwargs']['user_id']
    assert captured['kwargs']['metadata_schema']['version'] == '2.0'
    assert 'metadata_schema' not in captured['organization_profile']
    project = db.session.get(ResearchProject, test_project.id)
    assert project.rag_quality_mode == 'balanced'


def test_get_project_rag_template_mapping_contract_returns_simple_document_type_mapping(client, app_context):
    response = client.get('/projects/rag/template-mapping-contract')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['contract'] == get_document_type_template_contract()


def test_get_project_rag_graph_reading_contract_returns_simple_mode_mapping(client, app_context, monkeypatch):
    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)
    monkeypatch.setattr(
        project_routes,
        'list_graph_extraction_profile_options',
        lambda: (True, [{'profile_id': 'system-balanced-graph-extraction', 'name': 'Balanced Graph Extraction'}]),
    )

    response = client.get('/projects/rag/graph-reading-contract')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['contract'] == get_graph_reading_mode_contract()
    assert payload['available_profiles'][0]['profile_id'] == 'system-balanced-graph-extraction'


def test_project_rag_organization_profile_requires_collection(client, app_context, test_project, monkeypatch):
    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)

    response = client.get(f'/projects/{test_project.id}/rag/organization-profile')

    assert response.status_code == 400
    payload = response.get_json()
    assert payload['success'] is False
    assert 'document library' in payload['error']


def test_get_project_rag_organization_profile_uses_saved_project_quality_mode_when_request_omits_it(
    client,
    app_context,
    test_project,
    monkeypatch,
):
    _set_project_collection(test_project.id, 'collection-42')
    _set_project_quality_mode(test_project.id, 'deep')

    captured = {}

    def fake_get(collection_id, user_id=None, quality_mode=None):
        captured['collection_id'] = collection_id
        captured['quality_mode'] = quality_mode
        return True, {
            'chunking': {
                'strategy': 'hierarchical',
                'chunk_size_chars': 2400,
                'chunk_overlap_chars': 600,
            },
            'chunking_source': 'database_template_default',
            'metadata_defaults': {'language': 'en'},
            'metadata_defaults_source': 'library_default',
            'metadata_schema': {'version': '2.0', 'filterable_fields': ['language']},
            'metadata_schema_source': 'collection_override',
            'database_default_graph_extraction_profile_id': 'system-balanced-graph-extraction',
            'graph_extraction_profile_id': 'system-balanced-graph-extraction',
        }

    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)
    monkeypatch.setattr(project_routes, 'get_collection_organization_profile', fake_get)
    monkeypatch.setattr(
        project_routes,
        'list_graph_extraction_profile_options',
        lambda: (True, [{'profile_id': 'system-balanced-graph-extraction', 'name': 'Balanced Graph Extraction'}]),
    )

    response = client.get(f'/projects/{test_project.id}/rag/organization-profile')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['quality_mode'] == 'deep'
    assert payload['quality_mode_source'] == 'saved_project_choice'
    assert payload['organization_profile']['chunking_source'] == 'database_template_default'
    assert payload['organization_profile']['metadata_defaults_source'] == 'library_default'
    assert payload['organization_profile']['metadata_schema_source'] == 'collection_override'
    assert captured['quality_mode'] == 'deep'


def test_get_project_rag_document_chunks_forwards_collection_scope(client, app_context, test_project, monkeypatch):
    _set_project_collection(test_project.id, 'collection-42')

    captured = {}

    def fake_get(collection_id, document_id, **kwargs):
        captured['collection_id'] = collection_id
        captured['document_id'] = document_id
        captured['kwargs'] = kwargs
        return True, {
            'success': True,
            'document_id': document_id,
            'root_document_id': 'doc-root',
            'chunk_count': 2,
            'chunks': [{'chunk_id': 'chunk-1'}],
        }

    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)
    monkeypatch.setattr(project_routes, 'get_collection_document_chunks', fake_get)

    response = client.get(
        f'/projects/{test_project.id}/rag/documents/doc-7/chunks?include_content=true&preview_chars=360'
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['document_id'] == 'doc-7'
    assert captured['collection_id'] == 'collection-42'
    assert captured['document_id'] == 'doc-7'
    assert captured['kwargs']['include_content'] is True
    assert captured['kwargs']['preview_chars'] == 360
    assert captured['kwargs']['user_id']


def test_get_project_rag_document_lineage_forwards_collection_scope(client, app_context, test_project, monkeypatch):
    _set_project_collection(test_project.id, 'collection-42')

    captured = {}

    def fake_get(collection_id, document_id, **kwargs):
        captured['collection_id'] = collection_id
        captured['document_id'] = document_id
        captured['kwargs'] = kwargs
        return True, {
            'success': True,
            'document_id': document_id,
            'root_document_id': 'doc-root',
            'lineage': {'chunking_strategy': 'semantic'},
            'chunks': [{'chunk_id': 'chunk-1'}],
        }

    monkeypatch.setattr(project_routes, 'is_configured', lambda: True)
    monkeypatch.setattr(project_routes, 'get_collection_document_lineage', fake_get)

    response = client.get(f'/projects/{test_project.id}/rag/documents/doc-7/lineage')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['lineage']['chunking_strategy'] == 'semantic'
    assert captured['collection_id'] == 'collection-42'
    assert captured['document_id'] == 'doc-7'
    assert captured['kwargs']['user_id']

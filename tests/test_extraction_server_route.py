import json
from unittest.mock import patch

from app.database import db
from app.models.researcher import ExtractionSchema, ResearcherDocument



def test_run_extraction_uses_server_result(client, app_context, test_project, test_document):
    schema = ExtractionSchema(
        project_id=test_project.id,
        name='Paper Schema',
        schema_json=json.dumps([
            {
                'name': 'title',
                'description': 'Extract the paper title',
                'field_type': 'string',
                'required': True,
            }
        ]),
    )
    db.session.add(schema)
    db.session.commit()

    with patch('app.routes.extraction.beep_ai_client.is_configured', return_value=True),          patch('app.routes.extraction.beep_ai_client.extract_structured', return_value=(True, {
             'extracted_fields': {'title': 'A Server-Extracted Title'},
             'confidence': 0.91,
         })) as extract_mock:
        resp = client.post(
            f'/projects/{test_project.id}/extract',
            json={
                'schema_id': schema.id,
                'document_id': test_document.id,
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'completed'
    assert data['schema_id'] == schema.id
    assert data['total_processed'] == 1
    assert data['results'][0]['document_id'] == test_document.id
    assert data['results'][0]['extracted']['title'] == 'A Server-Extracted Title'
    assert data['results'][0]['confidence'] == 0.91

    extract_mock.assert_called_once()
    _, kwargs = extract_mock.call_args
    assert kwargs['project'].id == test_project.id
    assert kwargs['document_id'] == str(test_document.id)
    assert kwargs['schema_name'] == 'Paper Schema'
    assert kwargs['schema_fields'][0]['name'] == 'title'


def test_run_extraction_honors_selected_document_ids(client, app_context, test_project, test_document):
    other_document = ResearcherDocument(
        project_id=test_project.id,
        filename='other-paper.txt',
        file_path='',
        text_content='This is another readable project file.',
        file_size=128,
        source_type='test',
    )
    schema = ExtractionSchema(
        project_id=test_project.id,
        name='Quick Table',
        schema_json=json.dumps([
            {
                'name': 'title',
                'description': 'Extract the title',
                'field_type': 'string',
                'required': True,
            }
        ]),
    )
    db.session.add_all([other_document, schema])
    db.session.commit()

    with patch('app.routes.extraction.beep_ai_client.is_configured', return_value=True), \
         patch('app.routes.extraction.beep_ai_client.extract_structured', return_value=(True, {
             'extracted_fields': {'title': 'Chosen File'},
             'confidence': 0.88,
         })) as extract_mock:
        resp = client.post(
            f'/projects/{test_project.id}/extract',
            json={
                'schema_id': schema.id,
                'document_ids': [other_document.id],
            },
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['total_processed'] == 1
    assert data['results'][0]['document_id'] == other_document.id

    extract_mock.assert_called_once()
    _, kwargs = extract_mock.call_args
    assert kwargs['document_id'] == str(other_document.id)


def test_run_extraction_passes_grounded_library_evidence(client, app_context, test_project, test_document):
    schema = ExtractionSchema(
        project_id=test_project.id,
        name='Paper Schema',
        schema_json=json.dumps([
            {
                'name': 'title',
                'description': 'Extract the paper title',
                'field_type': 'string',
                'required': True,
            }
        ]),
    )
    db.session.add(schema)
    db.session.commit()

    with patch('app.routes.extraction.beep_ai_client.is_configured', return_value=True), \
         patch('app.routes.extraction.build_project_grounded_context', return_value={
             'context_text': 'Supporting library evidence:\n[1] Paper A [Doc 10]: Terminology reference.',
             'sources': [{'source': 'Paper A', 'document_id': '10', 'snippet': 'Terminology reference.'}],
         }), \
         patch('app.routes.extraction.beep_ai_client.extract_structured', return_value=(True, {
             'extracted_fields': {'title': 'A Server-Extracted Title'},
             'confidence': 0.91,
         })) as extract_mock:
        resp = client.post(
            f'/projects/{test_project.id}/extract',
            json={
                'schema_id': schema.id,
                'document_id': test_document.id,
            },
        )

    assert resp.status_code == 200
    extract_mock.assert_called_once()
    _, kwargs = extract_mock.call_args
    assert 'Supporting library evidence:' in kwargs['supporting_context']
    assert resp.get_json()['results'][0]['supporting_sources'][0]['document_id'] == '10'

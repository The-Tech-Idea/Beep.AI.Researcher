from app.database import db
from app.models.researcher import DocumentAnnotation


def test_document_annotation_routes_create_list_and_delete(client, app_context, test_project, test_document):
    with client.session_transaction() as session:
        user_id = int(session["_user_id"])

    create_response = client.post(
        f"/projects/{test_project.id}/documents/{test_document.id}/annotations",
        json={
            "start_offset": 10,
            "end_offset": 24,
            "note": "Keep this quote for the literature review",
            "highlight_color": "#fef08a",
        },
    )

    assert create_response.status_code == 201
    created = create_response.get_json()
    assert created["created_by_id"] == user_id
    assert created["selected_text"] == "test document"
    assert created["note"] == "Keep this quote for the literature review"

    annotation_row = db.session.get(DocumentAnnotation, created["id"])
    assert annotation_row is not None
    assert annotation_row.created_by_id == user_id

    list_response = client.get(
        f"/projects/{test_project.id}/documents/{test_document.id}/annotations"
    )
    assert list_response.status_code == 200
    annotations = list_response.get_json()["annotations"]
    assert len(annotations) == 1
    assert annotations[0]["context_preview"]

    delete_response = client.delete(
        f"/projects/{test_project.id}/documents/{test_document.id}/annotations/{created['id']}"
    )
    assert delete_response.status_code == 200
    assert delete_response.get_json()["ok"] is True
    assert db.session.get(DocumentAnnotation, created["id"]) is None


def test_document_annotation_routes_reject_invalid_offsets(client, app_context, test_project, test_document):
    response = client.post(
        f"/projects/{test_project.id}/documents/{test_document.id}/annotations",
        json={
            "start_offset": 22,
            "end_offset": 12,
            "note": "bad",
        },
    )

    assert response.status_code == 400
    assert "greater than start_offset" in response.get_json()["error"]

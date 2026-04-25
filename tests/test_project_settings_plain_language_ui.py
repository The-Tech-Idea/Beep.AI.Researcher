from pathlib import Path


RESEARCHER_ROOT = Path(__file__).resolve().parents[1]


def test_project_settings_page_uses_plain_language_for_document_reading(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/settings")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "How The Assistant Uses Your Project Files" in page
    assert "Document Library Connection" in page
    assert "Choose document library" in page
    assert "Reading Setup" in page
    assert "Use Suggested Setup" in page
    assert "Saved reading setup" in page
    assert "Use This Setup" in page
    assert "Use Library Default" in page
    assert "Most Common Document Type" in page
    assert "How Files Connect" in page
    assert "File connections" in page
    assert "Loading file connection options..." in page
    assert "Current Library Setup" in page
    assert "Saved setup currently in use for this project." in page
    assert "Saved setup quick view" in page
    assert "Answer style: Balanced help" in page
    assert "Save Library Connection" in page
    assert "Save Reading Settings" in page
    assert "css/project/settings.css" in page
    assert "js/project/settings.js" in page
    assert "onclick=" not in page
    assert "data-export-format=\"json\"" in page
    assert "data-export-format=\"zip\"" in page
    assert "alert alert-secondary py-2 small mb-3" not in page
    assert "alert py-2 small mb-3" not in page
    assert "btn btn-outline-secondary btn-sm" not in page
    assert "btn btn-outline-primary btn-sm" not in page
    assert "btn btn-outline-danger btn-sm" not in page
    assert "btn btn-primary btn-sm" not in page
    assert "btn btn-danger btn-sm" not in page
    assert "text-muted small" not in page
    assert "exportProject(" not in page
    assert "archiveProject(" not in page
    assert "deleteProject(" not in page
    assert "connectRAG()" not in page
    assert "RAG Chunking &amp; Metadata" not in page
    assert "Save RAG Profile" not in page
    assert "Document Reading Setup" not in page
    assert "Advanced template choice" not in page
    assert "Apply Template" not in page
    assert "Remove Template" not in page
    assert "Relationship View" not in page
    assert "Use Recommended Setup" not in page


def test_project_settings_script_uses_page_owned_status_and_toast_handling():
    settings_js = (RESEARCHER_ROOT / "static/js/project/settings.js").read_text(encoding="utf-8")

    assert "window.alert(message)" not in settings_js
    assert "alert py-2 small mb-3 alert-" not in settings_js
    assert "buildStatusClass(" not in settings_js


def test_project_start_page_uses_plain_language_onboarding_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/start")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Set Up Your Project Library" in page
    assert "Choose how this project should read your files" in page
    assert "Document library" in page
    assert "Choose document library" in page
    assert "Reading choices" in page
    assert "Most common file type" in page
    assert "How files connect" in page
    assert "Suggested reading setup" in page
    assert "Save Setup And Open Project" in page
    assert "Open Full Settings" in page
    assert "css/project/start.css" in page
    assert "js/project/start.js" in page
    assert "onclick=" not in page
    assert "Relationship View" not in page
    assert "Document Reading Setup" not in page


def test_project_search_page_uses_plain_language_for_answer_support(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/search")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Ask in natural language." in page
    assert "Why this answer" in page
    assert "Used from your files" in page
    assert "Answer style" in page
    assert "data-library-setup-summary" in page
    assert "css/project/search.css" in page
    assert "css/project/library_setup_summary.css" in page
    assert "js/project/search_controls.js" in page
    assert "js/project-search.js" in page
    assert "js/project/library_setup_summary.js" in page
    assert 'class="btn btn-outline-secondary btn-sm" id="clearChatBtn"' not in page
    assert "RAG Mode" not in page
    assert "research-chat-setup {" not in page
    assert "applySlider(val)" not in page


def test_project_search_script_uses_page_owned_runtime_classes():
    search_js = (RESEARCHER_ROOT / "static/js/project-search.js").read_text(encoding="utf-8")

    assert "btn btn-outline-secondary btn-sm add-to-report-btn" not in search_js
    assert 'style="font-size:.75rem;"' not in search_js
    assert "welcomeMessage.style.display = 'none'" not in search_js


def test_dashboard_shell_uses_plain_language_helper_copy(client, app_context):
    response = client.get("/researcher/")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Research Tools" in page
    assert "Writing Help" in page
    assert 'id="spa-loading" hidden' in page
    assert "css/dashboard_page.css" in page
    assert "js/base_shell.js" in page
    assert "js/flow_notifications.js" in page
    assert "js/dashboard_page.js" in page
    assert "js/dashboard.js" not in page
    assert "const themeButtons = document.querySelectorAll('.theme-btn');" not in page
    assert "const sc = document.getElementById('ai-server-status'), st = document.getElementById('ai-status-text');" not in page
    assert "onclick=" not in page
    assert "const createBtn = document.getElementById('btnCreateProject');" not in page
    assert 'style="min-width:140px;"' not in page
    assert 'style="margin-top: 2rem;"' not in page
    assert 'id="aiTemplateModal"' not in page
    assert "AI Assistant" not in page
    assert "AI Research Tools" not in page


def test_legacy_dashboard_modal_assets_are_removed():
    assert not (RESEARCHER_ROOT / "static/js/dashboard.js").exists()
    assert not (RESEARCHER_ROOT / "static/js/ai_template_modal.js").exists()
    assert not (RESEARCHER_ROOT / "templates/components/ai_template_modal.html").exists()


def test_live_project_route_files_avoid_legacy_primary_key_query_helpers():
    dashboard_routes = (RESEARCHER_ROOT / "app/routes/dashboard.py").read_text(encoding="utf-8")
    project_start_routes = (RESEARCHER_ROOT / "app/routes/project_start.py").read_text(encoding="utf-8")
    training_models = (RESEARCHER_ROOT / "app/models/researcher/researcher_training.py").read_text(encoding="utf-8")

    assert "owner = User.query.get(project.owner_id)" not in dashboard_routes
    assert "ResearcherDocument.query.get(r.document_id)" not in dashboard_routes
    assert "project = ResearchProject.query.get_or_404(project_id)" not in project_start_routes
    assert "project = get_entity_or_404(ResearchProject, project_id)" in project_start_routes
    assert "default=datetime.utcnow" not in training_models


def test_shared_ui_feedback_helper_exposes_notification_and_loading_contract():
    helper_js = (RESEARCHER_ROOT / "static/js/flow_notifications.js").read_text(encoding="utf-8")

    assert "window.beepUI.notify = notify;" in helper_js
    assert "window.beepUI.setButtonLoading = setButtonLoading;" in helper_js
    assert "function ensureToastContainer()" in helper_js


def test_live_project_scripts_use_shared_ui_feedback_helper():
    script_paths = [
        "static/js/dashboard_page.js",
        "static/js/flashcards.js",
        "static/js/quizzes.js",
        "static/js/extraction.js",
        "static/js/project-documents.js",
        "static/js/project-report.js",
        "static/js/project/report_page.js",
        "static/js/project/settings.js",
        "static/js/project/data.js",
        "static/js/project/report_share.js",
        "static/js/project/references.js",
    ]

    for relative_path in script_paths:
        content = (RESEARCHER_ROOT / relative_path).read_text(encoding="utf-8")
        assert "typeof window.beepUI.showToast === 'function'" not in content
        assert 'typeof window.beepUI.showToast === "function"' not in content


def test_workspace_controller_uses_page_owned_runtime_states():
    workspace_js = (RESEARCHER_ROOT / "static/js/workspace.js").read_text(encoding="utf-8")

    assert "text-center py-5" not in workspace_js
    assert 'style="font-size:3rem;"' not in workspace_js
    assert 'style="font-size:4rem;"' not in workspace_js
    assert "onclick=" not in workspace_js
    assert "contentInner.style.opacity = '0.4'" not in workspace_js
    assert "prompt('Project name:')" not in workspace_js
    assert "alert('Failed to create project.')" not in workspace_js
    assert "alert('Error creating project.')" not in workspace_js


def test_dashboard_page_script_uses_non_blocking_project_creation_feedback():
    dashboard_js = (RESEARCHER_ROOT / "static/js/dashboard_page.js").read_text(encoding="utf-8")

    assert "alert(config.projectNameRequired)" not in dashboard_js
    assert "alert(result.payload.error || config.createFailed)" not in dashboard_js


def test_references_library_page_uses_asset_based_workflow_copy(client, app_context):
    response = client.get("/references")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/references_page.css" in page
    assert "js/references_page.js" in page
    assert "<script>" not in page
    assert 'style="gap:1.5rem;"' not in page
    assert 'style="flex:0 0 280px;"' not in page
    assert 'style="width:auto;"' not in page
    assert "referenceExportBtn.addEventListener" not in page
    assert 'id="referenceImportStatus" class="text-muted"' not in page
    assert 'id="doiResult" class="mt-2 small"' not in page
    assert 'id="doiBatchResult" class="mt-2 small"' not in page


def test_references_library_script_uses_page_owned_validation_states():
    references_js = (RESEARCHER_ROOT / "static/js/references_page.js").read_text(encoding="utf-8")

    assert "text-muted" not in references_js
    assert "text-success" not in references_js
    assert "text-danger" not in references_js
    assert "bg-secondary" not in references_js
    assert "bg-success" not in references_js
    assert "bg-danger" not in references_js
    assert "bg-warning" not in references_js


def test_project_references_script_uses_shared_ui_loading_and_notifications():
    references_js = (RESEARCHER_ROOT / "static/js/project/references.js").read_text(encoding="utf-8")

    assert "window.alert(" not in references_js
    assert "spinner-border" not in references_js
    assert "window.beepUI.setButtonLoading(" in references_js
    assert "window.beepUI.notify(" in references_js
    assert "bibliographyPreviewUrl" in references_js
    assert 'document.getElementById("bibliographyCopyBtn")' in references_js
    assert "importUrl" in references_js
    assert 'document.getElementById("referenceImportBtn")' in references_js


def test_project_reference_detail_page_uses_asset_based_detail_workflow(client, app_context, test_project, test_document):
    from app.database import db
    from app.models.researcher import DocumentAnnotation
    from app.models.researcher.researcher_references import Reference, ReferenceSourceType

    reference = Reference(
        project_id=test_project.id,
        document_id=test_document.id,
        title="Source detail review",
        source="Journal of Testing",
        publication="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        citation_key="SourceDetailReview2026",
        year=2026,
        doi="10.1000/source-detail-review",
        url="https://example.com/source-detail-review",
        citation_count=2,
    )
    reference.set_authors(["Smith, A.", "Jones, B."])
    reference.set_keywords(["methods", "review"])
    reference.set_metadata_dict({
        "tags": ["chapter 2", "methods"],
        "external_library": {
            "provider": "zotero",
            "item_key": "ABCD1234",
            "library_type": "user",
            "synced_at": "2026-04-12T08:30:00",
            "attachments": [{
                "item_key": "ATT-99",
                "title": "Methods appendix",
                "filename": "appendix.pdf",
                "content_type": "application/pdf",
                "link_mode": "imported_file",
                "item_url": "https://www.zotero.org/users/123/items/ATT-99",
            }],
        },
    })
    db.session.add(reference)
    db.session.flush()
    db.session.add(
        DocumentAnnotation(
            document_id=test_document.id,
            chunk_id="chunk-0",
            start_offset=10,
            end_offset=24,
            note="Keep this section for the literature review",
            highlight_color="#fef08a",
        )
    )
    db.session.commit()

    response = client.get(f"/researcher/projects/{test_project.id}/references/{reference.id}")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Review linked files, notes, and export this source" in page
    assert "Back to reference library" in page
    assert "Formatted citation" in page
    assert "Linked files" in page
    assert "Library sync details" in page
    assert "External attachments" in page
    assert "Open attachment" in page
    assert "Add to project files" in page
    assert 'id="referenceExternalAttachmentsList"' in page
    assert "Copy citation" in page
    assert "Download current style" in page
    assert "Open file" in page
    assert "css/project/reference_detail.css" in page
    assert "js/project/reference_detail.js" in page
    assert "data-library-setup-summary" in page
    assert 'id="reference-detail-config"' in page
    assert "externalAttachmentsUrl" in page
    assert "attachmentImportUrlTemplate" in page
    assert "onclick=" not in page
    assert "alert(" not in page


def test_reference_detail_script_uses_shared_feedback_and_loading_helpers():
    reference_detail_js = (RESEARCHER_ROOT / "static/js/project/reference_detail.js").read_text(encoding="utf-8")

    assert "window.beepUI.notify(" in reference_detail_js
    assert "window.beepUI.setButtonLoading(" in reference_detail_js
    assert "alert(" not in reference_detail_js
    assert "spinner-border" not in reference_detail_js
    assert "referenceCopyBtn" in reference_detail_js
    assert "data-reference-remove-document" in reference_detail_js
    assert "referenceExternalAttachmentsList" in reference_detail_js
    assert "externalAttachmentsUrl" in reference_detail_js
    assert "data-reference-import-attachment" in reference_detail_js
    assert "attachmentImportUrlTemplate" in reference_detail_js


def test_agent_plans_page_uses_asset_based_plan_workflow_copy(client, app_context):
    response = client.get("/researcher/agent-plans")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/agent_plans_page.css" in page
    assert "js/agent_plans_page.js" in page
    assert 'style="cursor:pointer;"' not in page
    assert 'style="max-height: 260px; overflow:auto;"' not in page
    assert "setButtonsEnabled(false);" not in page
    assert "text-bg-warning" not in page


def test_members_page_uses_asset_based_member_workflow(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/members")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/members_page.css" in page
    assert "js/members_page.js" in page
    assert 'id="members-config"' in page
    assert "onclick=" not in page
    assert "document.addEventListener('DOMContentLoaded', function () {" not in page
    assert "fetch(`/projects/${projectId}/members`" not in page
    assert "confirm(config.confirm_remove)" not in page
    assert "badge bg-primary" not in page


def test_project_overview_uses_plain_language_actions(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/overview")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Ask a question" in page
    assert "Search and ask questions about your files" in page
    assert "data-library-setup-summary" in page
    assert "css/project/overview.css" in page
    assert "css/project/library_setup_summary.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "btn btn-outline-secondary btn-sm dropdown-toggle" not in page
    assert "text-muted" not in page
    assert "bg-success" not in page
    assert "bg-secondary bg-opacity-25 text-secondary" not in page
    assert "btn btn-outline-primary btn-sm" not in page
    assert "text-success" not in page
    assert "text-decoration-line-through" not in page
    assert "sidebar-rdot{display:inline-block" not in page
    assert "Ask AI" not in page
    assert ".overview-action-card" not in page


def test_document_viewer_uses_plain_language_review_copy(client, app_context, test_project, test_document):
    from app.database import db
    from app.models.researcher.researcher_references import Reference, ReferenceSourceType

    reference = Reference(
        project_id=test_project.id,
        document_id=test_document.id,
        title="Viewer source reference",
        source="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        citation_key="ViewerSourceReference2026",
        year=2026,
        doi="10.1000/viewer-source-reference",
    )
    reference.set_authors(["Smith, A."])
    db.session.add(reference)
    db.session.commit()

    response = client.get(
        f"/researcher/projects/{test_project.id}/documents/{test_document.id}?source_view=reference&reference_id={reference.id}"
    )

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Review this file in context" in page
    assert "Opened from this source" in page
    assert "Back to source detail" in page
    assert "Sources linked to this file" in page
    assert "File text" in page
    assert "Notes and highlights" in page
    assert "Save highlighted note" in page
    assert 'id="annotationSelectionPreview"' in page
    assert 'id="annotationNoteInput"' in page
    assert 'id="btnSaveAnnotation"' in page
    assert "Saved passages" in page
    assert "data-library-setup-summary" in page
    assert "data-supporting-sources-panel" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/supporting_sources_summary.css" in page
    assert "css/project/document_viewer.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/supporting_sources_summary.js" in page
    assert "js/project/document_viewer.js" in page
    assert "Document content" not in page
    assert "const projectId =" not in page


def test_document_viewer_script_uses_shared_feedback_and_annotation_flow():
    document_viewer_js = (RESEARCHER_ROOT / "static/js/project/document_viewer.js").read_text(encoding="utf-8")

    assert "window.beepUI.notify(" in document_viewer_js
    assert "window.beepUI.setButtonLoading(" in document_viewer_js
    assert "annotationSelectionPreview" in document_viewer_js
    assert "btnSaveAnnotation" in document_viewer_js
    assert "referenceContextMessage" in document_viewer_js
    assert "alert(" not in document_viewer_js


def test_contradictions_page_uses_plain_language_review_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/contradictions")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Check a statement" in page
    assert "Review Files" in page
    assert "Files to include" in page
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/components/document_selector.css" in page
    assert "css/project/contradictions.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/contradictions.js" in page
    assert "<style>" not in page
    assert ".review-guide-card {" not in page
    assert "Detect Contradictions" not in page
    assert "Claim / Statement" not in page
    assert "btn btn-warning w-100" not in page
    assert "text-muted mb-1" not in page
    assert "alert alert-light border mt-3 d-none" not in page


def test_contradictions_script_uses_page_owned_runtime_classes():
    contradictions_js = (RESEARCHER_ROOT / "static/js/contradictions.js").read_text(encoding="utf-8")

    assert "alert(i18n.missingQuery" not in contradictions_js
    assert "alert alert-danger" not in contradictions_js
    assert "alert alert-success" not in contradictions_js
    assert "text-muted" not in contradictions_js
    assert "text-warning" not in contradictions_js
    assert "classList.remove('d-none')" not in contradictions_js
    assert "classList.add('d-none')" not in contradictions_js


def test_extraction_page_uses_plain_language_data_collection_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/extraction")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Turn your files into a data table" in page
    assert "Create a data table" in page
    assert "Columns to fill in" in page
    assert "Collected results" in page
    assert "data-library-setup-summary" in page
    assert "data-supporting-sources-panel" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/supporting_sources_summary.css" in page
    assert "css/components/document_selector.css" in page
    assert "css/project/extraction.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/extraction_page.js" in page
    assert "js/project/supporting_sources_summary.js" in page
    assert "onclick=" not in page
    assert "New Extraction Template" not in page
    assert "Fields to extract" not in page
    assert "alert alert-success" not in page
    assert 'class="btn btn-outline-secondary btn-sm preset-btn"' not in page
    assert 'class="btn btn-sm btn-outline-success d-none" id="btnInsertReport"' not in page
    assert 'class="btn btn-sm btn-outline-secondary d-none" id="btnExportCSV"' not in page
    assert 'class="badge bg-secondary d-none"' not in page
    assert "btn-close" not in page
    assert "list-group-item list-group-item-action" not in page
    assert 'id="runFieldCallout" class="py-2 px-3 mb-3 small d-none collection-soft-surface extraction-run-field-callout"' not in page
    assert 'id="extractProgress" class="d-none mt-2"' not in page
    assert 'id="extractionStatsBanner" class="d-flex align-items-center gap-3 mt-3 d-none extraction-stats-banner"' not in page
    assert 'id="whatNextPanel" class="row g-2 mt-2 d-none"' not in page
    assert "form-label small fw-medium" not in page
    assert "btn btn-primary btn-sm w-100" not in page
    assert "text-muted" not in page
    assert ".collection-guide-card {" not in page


def test_report_page_uses_plain_language_writing_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/report")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Write your report in clear research language" in page
    assert "Add Project Material" in page
    assert "Draft a Section" in page
    assert "data-library-setup-summary" in page
    assert "data-supporting-sources-panel" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/supporting_sources_summary.css" in page
    assert "css/project/report.css" in page
    assert "js/project/report_page.js" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/supporting_sources_summary.js" in page
    assert "js/project-report.js" in page
    assert "onclick=" not in page
    assert "window.REPORT_I18N = {" not in page
    assert "text-primary" not in page
    assert "alert alert-light" not in page
    assert "bg-light" not in page
    assert "btn btn-outline-secondary btn-sm" not in page
    assert "btn btn-outline-primary btn-sm" not in page
    assert "btn btn-primary btn-sm" not in page
    assert "btn btn-secondary btn-sm" not in page
    assert "btn btn-sm btn-light" not in page
    assert "btn-close" not in page
    assert "shadow-lg border-0" not in page
    assert "border-bottom-0 pb-0" not in page
    assert "p-0 mt-3 border-top" not in page
    assert "form-label small fw-medium" not in page
    assert "report-modal-button report-modal-button--insert mt-2" not in page
    assert "list-group-item list-group-item-action" not in page
    assert "text-muted small" not in page
    assert "AI Assistant" not in page
    assert "Insert Project Data" not in page
    assert ".report-guide-card {" not in page


def test_references_page_uses_plain_language_and_real_save_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/references")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Manage citations and build your bibliography" in page
    assert "Collections" in page
    assert "Search this library" in page
    assert "Tags" in page
    assert "Bibliography preview" in page
    assert "Preview the current library view as a bibliography before downloading it." in page
    assert "Citation style" in page
    assert "Copy bibliography" in page
    assert "Download bibliography" in page
    assert "Import reference file" in page
    assert "Bring BibTeX, RIS, or JSON references into the citation library for this project." in page
    assert "Import references" in page
    assert "Refresh library" in page
    assert "Sync from Zotero" in page
    assert "Import from Zotero" in page
    assert "Add citations to track your research sources" in page
    assert "Save reference" in page
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/references.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/references.js" in page
    assert "<style>" not in page
    assert "const _projectId =" not in page
    assert ".reference-banner {" not in page
    assert ".references-library-controls {" not in page
    assert 'id="bibliographyPreviewBtn"' in page
    assert '"bibliographyPreviewUrl":' in page
    assert 'id="referenceImportBtn"' in page
    assert '"importUrl":' in page
    assert 'id="zoteroStatusText"' in page
    assert '"zoteroStatusUrl":' in page
    assert "Failed to save reference." not in page


def test_report_share_page_uses_plain_language_share_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/report/share")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Share &amp; Export Report" in page
    assert "Check the draft before sending or downloading it" in page
    assert "Download PDF" in page
    assert "Email this report" in page
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/report_share.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/report_share.js" in page
    assert "<style>" not in page
    assert "onclick=" not in page
    assert "const projectId =" not in page
    assert "handleSecurePdfExport" not in page
    assert ".share-guide-card {" not in page
    assert "spinner-border" not in page


def test_report_share_script_uses_page_owned_runtime_states():
    report_share_js = (RESEARCHER_ROOT / "static/js/project/report_share.js").read_text(encoding="utf-8")

    assert "window.alert(message)" not in report_share_js
    assert "text-danger" not in report_share_js
    assert "text-muted" not in report_share_js
    assert "text-center" not in report_share_js
    assert "spinner-border" not in report_share_js
    assert "window.beepUI.setButtonLoading(" in report_share_js


def test_flashcards_page_uses_plain_language_study_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/flashcards")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Turn project reading into quick study cards" in page
    assert "Create study cards" in page
    assert "Which files do you want to review?" in page
    assert "data-library-setup-summary" in page
    assert "data-supporting-sources-panel" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/supporting_sources_summary.css" in page
    assert "css/components/document_selector.css" in page
    assert "css/project/flashcards.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/supporting_sources_summary.js" in page
    assert "<style>" not in page
    assert "bg-light" not in page
    assert "text-warning" not in page
    assert "btn-warning" not in page
    assert "btn btn-primary w-100" not in page
    assert "text-muted mt-1 d-block" not in page
    assert 'id="genProgress" class="mt-2 d-none"' not in page
    assert 'id="flashcardsQuizCta" class="flashcards-quiz-cta mt-3 d-none"' not in page
    assert "text-muted small ms-1" not in page
    assert "btn btn-sm flashcards-quiz-cta-button ms-3 flex-shrink-0" not in page
    assert ".study-helper-card {" not in page
    assert "AI-generated flashcards" not in page
    assert "> Generate<" not in page


def test_quizzes_page_uses_plain_language_quiz_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/quizzes")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Already have study cards?" in page
    assert "Create a quiz" in page
    assert "Which documents do you want to test yourself on?" in page
    assert "data-library-setup-summary" in page
    assert "data-supporting-sources-panel" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/supporting_sources_summary.css" in page
    assert "css/components/document_selector.css" in page
    assert "css/project/quizzes.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/supporting_sources_summary.js" in page
    assert "<style>" not in page
    assert "alert-dismissible" not in page
    assert "alert-link" not in page
    assert "btn-close" not in page
    assert "btn btn-primary w-100" not in page
    assert "btn btn-outline-success btn-sm" not in page
    assert "btn btn-outline-primary btn-sm" not in page
    assert "btn btn-outline-danger btn-sm" not in page
    assert "text-muted" not in page
    assert 'id="genProgress" class="mt-2 d-none"' not in page
    assert ".study-banner {" not in page
    assert "Generate Quiz" not in page
    assert "MCQ quizzes from your research" not in page
    assert "onclick=" not in page


def test_take_quiz_page_uses_plain_language_review_copy(client, app_context, test_project):
    from app.database import db
    from app.models.researcher import Quiz, QuizQuestion

    quiz = Quiz(project_id=test_project.id, name="Knowledge Check")
    db.session.add(quiz)
    db.session.flush()
    db.session.add(
        QuizQuestion(
            quiz_id=quiz.id,
            question="What does the report conclude?",
            options_json='["A","B","C","D"]',
            correct_index=0,
            source_chunk_id='chunk-0',
        )
    )
    db.session.commit()

    response = client.get(f"/researcher/projects/{test_project.id}/quizzes/{quiz.id}/take")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Check what you remember from this project" in page
    assert "Loading questions" in page
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/take_quiz.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/take-quiz.js" in page
    assert 'style="width:150px;height:6px;"' not in page
    assert 'style="width:0%"' not in page
    assert "Failed to load quiz." not in page


def test_study_page_scripts_use_page_owned_runtime_classes():
    flashcards_js = (RESEARCHER_ROOT / "static/js/flashcards.js").read_text(encoding="utf-8")
    quizzes_js = (RESEARCHER_ROOT / "static/js/quizzes.js").read_text(encoding="utf-8")
    take_quiz_js = (RESEARCHER_ROOT / "static/js/take-quiz.js").read_text(encoding="utf-8")

    assert "alert alert-danger" not in flashcards_js
    assert "alert(" not in flashcards_js
    assert "text-muted" not in flashcards_js
    assert "text-primary" not in flashcards_js
    assert "text-warning" not in flashcards_js
    assert "btn-outline-danger" not in flashcards_js
    assert "classList.remove('d-none')" not in flashcards_js
    assert "classList.toggle('d-none')" not in flashcards_js

    assert "alert alert-danger" not in quizzes_js
    assert "alert(" not in quizzes_js
    assert "text-muted" not in quizzes_js
    assert "btn btn-sm btn-primary" not in quizzes_js
    assert "btn-outline-danger" not in quizzes_js
    assert "classList.remove('d-none')" not in quizzes_js
    assert "classList.add('d-none')" not in quizzes_js

    assert "alert alert-danger" not in take_quiz_js
    assert "bg-secondary" not in take_quiz_js
    assert "btn btn-success text-start" not in take_quiz_js
    assert "btn btn-danger text-start" not in take_quiz_js
    assert "progress-bar bg-" not in take_quiz_js
    assert "text-' + tone" not in take_quiz_js


def test_extraction_script_uses_page_owned_runtime_classes():
    extraction_js = (RESEARCHER_ROOT / "static/js/extraction.js").read_text(encoding="utf-8")
    document_selector_js = (RESEARCHER_ROOT / "static/js/components/document-selector.js").read_text(encoding="utf-8")

    assert "alert alert-danger" not in extraction_js
    assert "btn-outline-danger" not in extraction_js
    assert "text-muted" not in extraction_js
    assert "text-danger" not in extraction_js
    assert "table-dark" not in extraction_js
    assert "spinner-border" not in extraction_js
    assert 'style="width:90px;"' not in extraction_js
    assert "alert(" not in extraction_js
    assert "classList.remove('d-none')" not in extraction_js
    assert "classList.add('d-none')" not in extraction_js
    assert "list-group-item list-group-item-action" not in extraction_js
    assert 'class="table table-sm table-bordered"' not in extraction_js
    assert 'class="table table-sm table-bordered table-hover"' not in extraction_js

    assert "text-muted" not in document_selector_js
    assert "d-flex align-items-center" not in document_selector_js
    assert 'style="' not in document_selector_js


def test_document_map_page_uses_asset_based_map_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/map")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/document_map.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/document_map_page.js" in page
    assert "js/document-map.js" in page
    assert "onclick=" not in page
    assert "alert alert-info" not in page
    assert 'id="mapEmptyState" class="text-center py-5 d-none"' not in page
    assert "btn btn-primary btn-sm" not in page
    assert "text-muted" not in page
    assert "localStorage.getItem('map_banner')" not in page
    assert 'style="min-height:400px;"' not in page
    assert 'style="font-size:.8rem;"' not in page
    assert 'style="background:#3b82f6;width:10px;height:10px;display:inline-block;"' not in page


def test_report_matrix_and_documents_scripts_use_page_owned_runtime_classes():
    report_js = (RESEARCHER_ROOT / "static/js/project-report.js").read_text(encoding="utf-8")
    report_page_js = (RESEARCHER_ROOT / "static/js/project/report_page.js").read_text(encoding="utf-8")
    matrix_js = (RESEARCHER_ROOT / "static/js/matrix.js").read_text(encoding="utf-8")
    documents_js = (RESEARCHER_ROOT / "static/js/project-documents.js").read_text(encoding="utf-8")

    assert "spinner-border" not in report_js
    assert "btn btn-sm report-insert-action" not in report_js
    assert "text-center py-5" not in report_js
    assert "text-center py-3" not in report_js
    assert "alert(" not in report_js
    assert "text-primary" not in report_js
    assert "text-danger" not in report_js
    assert "btn-light text-primary" not in report_js
    assert "border-light-subtle" not in report_js
    assert "mb-1 report-runtime-card-title" not in report_js
    assert "small report-runtime-card-summary mb-2" not in report_js
    assert 'style="' not in report_js

    assert "spinner-border" not in report_page_js
    assert "alert(error.message)" not in report_page_js
    assert "generateButton.innerHTML =" not in report_page_js

    assert "spinner-border" not in matrix_js
    assert "bg-dark text-white" not in matrix_js
    assert "bg-warning text-dark" not in matrix_js
    assert "table-secondary" not in matrix_js
    assert 'style="' not in matrix_js

    assert "spinner-border text-primary" not in documents_js


def test_stats_page_uses_asset_based_stats_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/stats")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/stats.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/stats.js" in page
    assert "text-primary stats-summary-icon" not in page
    assert "text-info stats-summary-icon" not in page
    assert "text-warning stats-summary-icon" not in page
    assert "text-success stats-summary-icon" not in page
    assert "text-muted" not in page
    assert "bg-dark text-light" not in page
    assert "btn btn-outline-primary btn-sm" not in page
    assert "btn btn-sm btn-primary" not in page
    assert "card border-0 shadow-sm" not in page
    assert 'style="font-size:1.5rem;"' not in page
    assert 'style="height:300px;"' not in page
    assert 'style="max-height:300px;overflow:auto;"' not in page
    assert 'style="font-size:2.5rem;opacity:.5;"' not in page


def test_stats_script_uses_configured_theme_values():
    stats_js = (RESEARCHER_ROOT / "static/js/stats.js").read_text(encoding="utf-8")

    assert "label: 'Documents Added'" not in stats_js
    assert "backgroundColor: 'rgba(99, 102, 241, 0.6)'" not in stats_js
    assert "var colors = ['#6366f1'" not in stats_js
    assert "|| 'UNKNOWN'" not in stats_js


def test_data_page_uses_asset_based_analysis_workflow_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/data")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/project/data.css" in page
    assert "js/project/data.js" in page
    assert 'id="data-page-config"' in page
    assert "onclick=" not in page
    assert "function refreshChart()" not in page
    assert "alert alert-info" not in page
    assert "text-bg-secondary" not in page
    assert "btn btn-outline-primary" not in page
    assert "text-muted" not in page
    assert 'style="font-size:.7rem;"' not in page
    assert 'style="width:auto;"' not in page


def test_hallucination_audit_page_uses_asset_based_review_workflow_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/hallucination-audit")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/project/hallucination_audit.css" in page
    assert "js/project/hallucination_audit.js" in page
    assert "<script>" not in page
    assert 'style="cursor:pointer;"' not in page
    assert 'style="font-size:.75rem;"' not in page
    assert 'style="max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"' not in page
    assert "new bootstrap.Popover(el);" not in page


def test_scheduled_reports_page_uses_asset_based_schedule_workflow_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/scheduled-reports")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/project/scheduled_reports.css" in page
    assert "js/scheduled-reports.js" in page
    assert 'id="scheduled-reports-config"' in page
    assert "window.__CONFIG__" not in page
    assert "btn btn-primary btn-sm" not in page
    assert "btn btn-outline-secondary btn-sm" not in page
    assert "btn btn-secondary" not in page
    assert "text-muted" not in page
    assert 'style="font-size:.75rem;"' not in page


def test_retention_page_uses_asset_based_policy_workflow_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/retention")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/project/retention.css" in page
    assert "js/retention.js" in page
    assert 'id="retention-config"' in page
    assert "<script>" not in page
    assert "actionSel.addEventListener('change'" not in page
    assert "text-muted" not in page
    assert "btn btn-primary w-100" not in page
    assert 'id="deleteWarning" class="retention-delete-warning mt-2 small py-2 d-none"' not in page
    assert 'class="badge retention-affected-count"' not in page
    assert "badge bg-warning" not in page
    assert "alert alert-danger" not in page
    assert "bg-light" not in page
    assert "text-primary" not in page


def test_retention_script_uses_page_owned_runtime_classes():
    retention_js = (RESEARCHER_ROOT / "static/js/retention.js").read_text(encoding="utf-8")

    assert "classList.toggle('d-none'" not in retention_js
    assert "alert('Saved.')" not in retention_js
    assert 'class="badge retention-age-badge"' not in retention_js
    assert "text-muted" not in retention_js


def test_documents_page_uses_asset_based_document_workflow_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/documents")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/documents.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project-documents.js" in page
    assert 'style="display: none;"' not in page
    assert 'style="font-size:1rem; font-weight:600; margin-bottom:0.25rem;"' not in page
    assert 'style="background:#e8d5fb33;color:#9b59b6;border-color:#9b59b633 !important;"' not in page
    assert "Load per-document activity badges" not in page
    assert 'style="display:none; position:fixed; bottom:1.5rem; left:50%; transform:translateX(-50%); z-index:50; background:var(--spa-surface); border:1px solid var(--spa-border); border-radius:var(--spa-radius); padding:0.5rem 1rem; box-shadow:var(--spa-shadow); display:none; align-items:center; gap:0.75rem;"' not in page
    assert "btn btn-primary btn-sm" not in page
    assert "btn btn-outline-secondary btn-sm" not in page
    assert "btn btn-outline-info btn-sm" not in page
    assert "btn btn-outline-primary btn-sm" not in page
    assert "btn btn-outline-danger btn-sm" not in page
    assert 'documents-activity-badge documents-activity-badge-codes d-none' not in page
    assert 'documents-activity-badge documents-activity-badge-extractions d-none' not in page
    assert 'documents-activity-badge documents-activity-badge-flashcards d-none' not in page


def test_project_documents_script_uses_page_owned_runtime_classes():
    documents_js = (RESEARCHER_ROOT / "static/js/project-documents.js").read_text(encoding="utf-8")

    assert "alert(" not in documents_js
    assert "classList.remove('d-none')" not in documents_js


def test_matrix_page_uses_asset_based_matrix_workflow_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/matrix")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "css/project/matrix.css" in page
    assert "js/matrix.js" in page
    assert "alert alert-light" not in page
    assert "text-primary" not in page
    assert 'style="width:420px;"' not in page


def test_codes_page_uses_asset_based_code_review_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/codes")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/codes.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project-codes.js" in page
    assert "alert alert-info alert-dismissible" not in page
    assert 'class="btn btn-outline-secondary btn-sm" id="exportCodesBtn"' not in page
    assert 'class="btn btn-sm btn-outline-primary" id="addCodeBtn"' not in page
    assert "text-muted" not in page
    assert "btn btn-outline-danger btn-sm excerpt-remove-btn" not in page
    assert '<button class="btn btn-outline-secondary btn-sm"><i class="bi bi-pencil me-1"></i>' not in page
    assert "display:none!important" not in page
    assert 'style="display:none; padding: 0.75rem;"' not in page
    assert 'style="background:#6366f1"' not in page
    assert 'style="padding:2rem"' not in page
    assert 'style="min-height:400px;"' not in page


def test_project_codes_script_uses_page_owned_runtime_classes():
    codes_js = (RESEARCHER_ROOT / "static/js/project-codes.js").read_text(encoding="utf-8")

    assert "el.style.background =" not in codes_js
    assert "el.style.borderLeft =" not in codes_js
    assert 'class="text-primary"' not in codes_js
    assert 'class="btn btn-outline-danger btn-sm excerpt-remove-btn"' not in codes_js


def test_tasks_page_uses_asset_based_task_board_copy(client, app_context, test_project):
    response = client.get(f"/researcher/projects/{test_project.id}/tasks")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "data-library-setup-summary" in page
    assert "css/project/library_setup_summary.css" in page
    assert "css/project/tasks.css" in page
    assert "js/project/library_setup_summary.js" in page
    assert "js/project/tasks.js" in page
    assert "onclick=" not in page
    assert "<script>" not in page
    assert 'style="text-decoration:line-through; opacity:.7;"' not in page
    assert "showAddTask('todo')" not in page
    assert "saveTask()" not in page
    assert 'style="cursor:pointer"' not in page
    assert "btn btn-outline-secondary btn-sm" not in page
    assert "btn btn-primary btn-sm" not in page
    assert "btn btn-sm p-0 text-muted" not in page
    assert "badge bg-light text-dark border small" not in page
    assert "badge bg-light text-muted border small" not in page
    assert "btn btn-secondary" not in page


def test_tasks_script_uses_page_owned_runtime_classes():
    tasks_js = (RESEARCHER_ROOT / "static/js/project/tasks.js").read_text(encoding="utf-8")

    assert "alert alert-light border mb-0" not in tasks_js
    assert "list-group mt-2" not in tasks_js
    assert "list-group-item list-group-item-action" not in tasks_js
    assert "spinner-border spinner-border-sm" not in tasks_js
    assert "me-1" not in tasks_js

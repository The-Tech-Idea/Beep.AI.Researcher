"""Reference management routes (list/create/update/delete)."""

from collections import defaultdict
from io import BytesIO
import json

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app.database import db
from app.models.researcher import (
    Code,
    Reference,
    ResearchProject,
    ResearchTask,
    ResearcherDocument,
)
from app.models.researcher.researcher_references import DocumentReference
from app.routes.route_entity_lookup import (
    get_entity,
    get_entity_or_404,
    get_project_or_404,
)
from app.services.citation_library_service import (
    build_project_citation_library,
    set_reference_tags,
)
from app.services.reference_bibliography_service import (
    build_project_bibliography_preview,
    export_project_bibliography,
    normalize_bibliography_style,
)
from app.services.reference_external_attachment_service import (
    get_project_reference_external_attachments,
)
from app.services.reference_detail_service import (
    build_project_reference_detail,
    build_reference_download_buffer,
    export_project_reference,
    normalize_single_reference_style,
)
from app.services.reference_attachment_ingest_service import (
    import_project_reference_attachment,
)
from app.services.reference_import_service import import_references
from app.services.quota_service import QuotaExceededError
from app.services.reference_service import (
    clean_value,
    create_reference,
    link_reference_to_document,
    reference_to_dict,
    unlink_reference_from_document,
    validate_doi,
    validate_citation_batch,
)
from app.services.zotero_library_sync_service import (
    get_project_zotero_sync_status,
    sync_project_references_from_zotero,
)

references_bp = Blueprint("references", __name__)


def _get_payload():
    if request.is_json:
        return request.get_json() or {}
    return request.form.to_dict()


def _project_sidebar_counts(project_id):
    return {
        "document_count": ResearcherDocument.query.filter_by(
            project_id=project_id
        ).count(),
        "code_count": Code.query.filter_by(project_id=project_id).count(),
        "task_count": ResearchTask.query.filter_by(project_id=project_id).count(),
    }


@references_bp.route("/references", methods=["GET", "POST"])
@login_required
def references_page():
    if request.method == "POST":
        payload = _get_payload()
        project_id = int(payload.get("project_id") or 0)
        if project_id:
            project = _get_project(project_id)
            if project:
                _save_reference(project, payload)
        return redirect(url_for("references.references_page"))

    projects = ResearchProject.query.order_by(ResearchProject.name).all()
    indices = defaultdict(list)
    references = Reference.query.order_by(Reference.created_at.desc()).all()
    for reference in references:
        indices[reference.project_id].append(reference)
    prefill_project_id = request.args.get("project_id", type=int)
    prefill_document_id = request.args.get("document_id", type=int)
    prefill_title = request.args.get("title") or ""
    prefill_authors = request.args.get("authors") or ""
    prefill_publication = request.args.get("publication") or ""
    prefill_year = request.args.get("year") or ""
    prefill_doi = request.args.get("doi") or ""
    prefill_url = request.args.get("url") or ""
    prefill_citation = request.args.get("citation") or ""
    prefill_notes = request.args.get("notes") or ""
    base_template = (
        "base_embed.html"
        if (
            (request.args.get("embed") or "").strip().lower() in ("1", "true", "yes")
            or (request.args.get("partial") or "").strip().lower() in ("1", "true")
            or request.headers.get("X-Requested-With") == "SPA"
        )
        else "base.html"
    )
    return render_template(
        "references.html",
        projects=projects,
        grouped_references=indices,
        total_references=len(references),
        latest_references=references,
        prefill_project_id=prefill_project_id,
        prefill_document_id=prefill_document_id,
        prefill_title=prefill_title,
        prefill_authors=prefill_authors,
        prefill_publication=prefill_publication,
        prefill_year=prefill_year,
        prefill_doi=prefill_doi,
        prefill_url=prefill_url,
        prefill_citation=prefill_citation,
        prefill_notes=prefill_notes,
        base_template=base_template,
    )


def _save_reference(project, payload):
    if not payload.get("title"):
        payload["title"] = "Untitled reference"
    return create_reference(project, payload)


@references_bp.route("/projects/<int:project_id>/references", methods=["GET"])
@login_required
def list_references(project_id):
    project = get_project_or_404(project_id)
    library_view = build_project_citation_library(
        project,
        collection=request.args.get("collection"),
        tag=request.args.get("tag"),
        query=request.args.get("q"),
    )
    return jsonify(
        {
            "references": [
                reference_to_dict(ref) for ref in library_view["references"]
            ],
            "collections": library_view["collections"],
            "tags": library_view["tags"],
            "selected_collection": library_view["selected_collection"],
            "selected_tag": library_view["selected_tag"],
            "query": library_view["search_query"],
            "result_count": library_view["result_count"],
        }
    )


@references_bp.route(
    "/researcher/projects/<int:project_id>/references/<int:reference_id>"
)
@login_required
def reference_detail_page(project_id, reference_id):
    project = get_project_or_404(project_id)
    detail = build_project_reference_detail(project, reference_id)
    if detail is None:
        abort(404)

    documents = (
        ResearcherDocument.query.filter_by(project_id=project.id)
        .order_by(ResearcherDocument.filename)
        .all()
    )
    return render_template(
        "project/reference_detail.html",
        project=project,
        reference=detail["reference"],
        reference_authors=detail["authors"],
        reference_keywords=detail["keywords"],
        reference_tags=detail["tags"],
        reference_external_library=detail["external_library"],
        reference_external_attachments=detail["external_attachments"],
        reference_attachment_count=detail["attachment_count"],
        reference_formatted_exports=detail["formatted_exports"],
        reference_linked_documents=detail["linked_documents"],
        reference_annotation_count=detail["annotation_count"],
        documents=documents,
        active_page="references",
        **_project_sidebar_counts(project.id),
    )


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>/external-attachments",
    methods=["GET"],
)
@login_required
def reference_external_attachments(project_id, reference_id):
    project = get_project_or_404(project_id)
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    try:
        payload = get_project_reference_external_attachments(
            project,
            reference,
            user_id=current_user.id,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>/external-attachments/<attachment_key>/import",
    methods=["POST"],
)
@login_required
def import_reference_external_attachment(project_id, reference_id, attachment_key):
    project = get_project_or_404(project_id)
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    try:
        result = import_project_reference_attachment(
            project,
            reference,
            attachment_item_key=attachment_key,
            user_id=current_user.id,
        )
    except QuotaExceededError as exc:
        return jsonify(
            {
                "error": str(exc),
                "quota_type": exc.quota_type,
                "used": exc.used,
                "limit": exc.limit,
            }
        ), 413
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "ok": True,
            "created": result["created"],
            "linked": result["linked"],
            "message": result["message"],
            "document": result["document"].to_dict(),
            "rag_sync": result["rag_sync"],
        }
    ), 201 if result["created"] else 200


@references_bp.route("/projects/<int:project_id>/references", methods=["POST"])
@login_required
def create_reference_entry(project_id):
    project = get_project_or_404(project_id)
    payload = _get_payload()
    if not payload.get("title"):
        return jsonify({"error": "title required"}), 400
    reference = create_reference(project, payload)
    return jsonify(reference_to_dict(reference)), 201


@references_bp.route(
    "/projects/<int:project_id>/references/zotero/status", methods=["GET"]
)
@login_required
def zotero_sync_status(project_id):
    project = get_project_or_404(project_id)
    status = get_project_zotero_sync_status(project, user_id=current_user.id)
    return jsonify(status)


@references_bp.route(
    "/projects/<int:project_id>/references/zotero/sync", methods=["POST"]
)
@login_required
def sync_project_zotero_references(project_id):
    project = get_project_or_404(project_id)
    payload = _get_payload()
    collection_key = (payload.get("collection_key") or "").strip() or None
    try:
        limit = int(payload.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100

    try:
        result = sync_project_references_from_zotero(
            project,
            user_id=current_user.id,
            collection_key=collection_key,
            limit=limit,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result), 200


@references_bp.route(
    "/projects/<int:project_id>/references/bibliography-preview", methods=["GET"]
)
@login_required
def preview_project_bibliography(project_id):
    project = get_project_or_404(project_id)
    preview = build_project_bibliography_preview(
        project,
        style=request.args.get("style"),
        collection=request.args.get("collection"),
        tag=request.args.get("tag"),
        query=request.args.get("q"),
        limit=request.args.get("limit", type=int),
    )
    return jsonify(preview)


@references_bp.route("/projects/<int:project_id>/references/export")
@login_required
def export_project_references(project_id):
    project = get_project_or_404(project_id)
    content, mimetype, filename = export_project_bibliography(
        project,
        style=normalize_bibliography_style(request.args.get("style")),
        collection=request.args.get("collection"),
        tag=request.args.get("tag"),
        query=request.args.get("q"),
    )
    buf = BytesIO(content.encode("utf-8"))
    return send_file(buf, mimetype=mimetype, as_attachment=True, download_name=filename)


@references_bp.route("/projects/<int:project_id>/references/<int:reference_id>/export")
@login_required
def export_single_reference(project_id, reference_id):
    project = get_project_or_404(project_id)
    detail = build_project_reference_detail(project, reference_id)
    if detail is None:
        return jsonify({"error": "reference not found"}), 404

    content, mimetype, filename = export_project_reference(
        detail["reference"],
        normalize_single_reference_style(request.args.get("style")),
    )
    return send_file(
        build_reference_download_buffer(content),
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename,
    )


@references_bp.route("/projects/<int:project_id>/references/import", methods=["POST"])
@login_required
def import_project_references(project_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "project not found"}), 404

    payload = _get_payload()
    import_format = (
        payload.get("format") or request.args.get("format") or "json"
    ).lower()
    content = payload.get("content")

    if not content and request.files.get("file"):
        upload = request.files["file"]
        content = upload.read().decode("utf-8", errors="ignore")
        if (
            import_format == "json"
            and upload.filename
            and upload.filename.lower().endswith(".bib")
        ):
            import_format = "bibtex"
        elif (
            import_format == "json"
            and upload.filename
            and upload.filename.lower().endswith(".ris")
        ):
            import_format = "ris"

    if not content and payload.get("references") is not None:
        content = payload.get("references")
        if not isinstance(content, str):
            content = json.dumps(content)

    if not content:
        return jsonify({"error": "No content provided for import"}), 400

    try:
        result = import_references(project, content, import_format)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    status = 201 if result.get("created", 0) else 200
    return jsonify(result), status


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>", methods=["PUT"]
)
@login_required
def update_reference(project_id, reference_id):
    project = get_project_or_404(project_id)
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    payload = _get_payload()
    if "title" in payload:
        reference.title = clean_value(payload.get("title")) or reference.title
    if "authors" in payload:
        authors = payload.get("authors")
        if isinstance(authors, str):
            authors = [item.strip() for item in authors.split(";") if item.strip()]
        elif not isinstance(authors, list):
            authors = []
        reference.set_authors(authors)
    if "publication" in payload:
        publication = clean_value(payload.get("publication"))
        reference.publication = publication
        reference.source = publication
    if "year" in payload:
        year = payload.get("year")
        reference.year = int(year) if year and str(year).isdigit() else None
    if "doi" in payload:
        reference.doi = clean_value(payload.get("doi"))
    if "url" in payload:
        reference.url = clean_value(payload.get("url"))
    if "citation" in payload:
        reference.citation = clean_value(payload.get("citation"))
    if "notes" in payload:
        reference.notes = clean_value(payload.get("notes"))
    if "tags" in payload:
        set_reference_tags(reference, payload.get("tags"))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update reference"}), 500
    return jsonify(reference_to_dict(reference))


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>", methods=["DELETE"]
)
@login_required
def delete_reference(project_id, reference_id):
    project = get_project_or_404(project_id)
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    db.session.delete(reference)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete reference"}), 500
    return jsonify({"ok": True}), 204


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>/documents",
    methods=["GET"],
)
@login_required
def list_reference_documents(project_id, reference_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "project not found"}), 404
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    links = [
        link.to_dict()
        for link in DocumentReference.query.filter_by(reference_id=reference.id)
        .order_by(DocumentReference.id.desc())
        .all()
    ]
    return jsonify(
        {
            "reference_id": reference.id,
            "documents": links,
            "citation_count": reference.citation_count,
        }
    ), 200


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>/link-document",
    methods=["POST"],
)
@login_required
def link_reference_document(project_id, reference_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "project not found"}), 404
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    payload = _get_payload()
    document_id = payload.get("document_id")
    if not document_id:
        return jsonify({"error": "document_id required"}), 400
    try:
        document_id = int(document_id)
    except (TypeError, ValueError):
        return jsonify({"error": "document_id must be numeric"}), 400

    document = db.session.get(ResearcherDocument, document_id)
    if not document or document.project_id != project.id:
        return jsonify({"error": "document not found in project"}), 404

    try:
        link = link_reference_to_document(reference, document_id, payload)
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to link document to reference"}), 500
    return jsonify(
        {"ok": True, "link": link.to_dict(), "citation_count": reference.citation_count}
    ), 201


@references_bp.route(
    "/projects/<int:project_id>/references/<int:reference_id>/link-document/<int:document_id>",
    methods=["DELETE"],
)
@login_required
def unlink_reference_document(project_id, reference_id, document_id):
    project = _get_project(project_id)
    if not project:
        return jsonify({"error": "project not found"}), 404
    reference = Reference.query.filter_by(
        project_id=project.id, id=reference_id
    ).first_or_404()
    try:
        removed = unlink_reference_from_document(reference, document_id)
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to unlink document from reference"}), 500
    if not removed:
        return jsonify({"error": "link not found"}), 404
    return jsonify({"ok": True, "citation_count": reference.citation_count}), 200


@references_bp.route(
    "/projects/<int:project_id>/references/validate-doi", methods=["POST"]
)
@login_required
def validate_single_doi(project_id):
    """Validate a single DOI via the middleware API."""
    get_project_or_404(project_id)
    payload = _get_payload()
    doi = (payload.get("doi") or "").strip()
    if not doi:
        return jsonify({"error": "doi required"}), 400
    result = validate_doi(doi)
    return jsonify(result)


@references_bp.route(
    "/projects/<int:project_id>/references/validate-citations", methods=["POST"]
)
@login_required
def validate_project_citations(project_id):
    """Bulk-validate every DOI in this project's references."""
    project = get_project_or_404(project_id)
    result = validate_citation_batch(project)
    return jsonify(result)


# ===========================================================================
# Phase 6 — Citation Intelligence Routes
# ===========================================================================


@references_bp.route("/references/smart-import", methods=["POST"])
@login_required
def smart_import():
    """Resolve a single identifier and preview metadata.

    Request body::

        {"identifier": "10.1038/s41586-021-03873-x"}
    """
    from app.services.smart_import_service import SmartImportService

    data = _get_payload()
    identifier = (data.get("identifier") or "").strip()
    if not identifier:
        return jsonify({"error": "identifier required"}), 400

    svc = SmartImportService()
    metadata = svc.resolve(identifier)
    if not metadata:
        return jsonify(
            {"error": "Could not resolve identifier", "identifier": identifier}
        ), 404

    return jsonify({"ok": True, "metadata": metadata})


@references_bp.route(
    "/projects/<int:project_id>/references/smart-import-bulk", methods=["POST"]
)
@login_required
def smart_import_bulk(project_id):
    """Bulk import references from a list of identifiers.

    Request body::

        {"identifiers": ["10.1000/a", "34567890", "2101.00001"]}
    """
    from app.services.smart_import_service import SmartImportService

    project = get_project_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    data = _get_payload()
    identifiers = data.get("identifiers") or []
    if not identifiers:
        return jsonify({"error": "identifiers list required"}), 400

    svc = SmartImportService()
    imported = []
    skipped = []

    for ident in identifiers:
        metadata = svc.resolve(ident)
        if not metadata:
            skipped.append({"identifier": ident, "reason": "Could not resolve"})
            continue

        dup = svc.check_duplicate(project.id, metadata)
        if dup:
            skipped.append(
                {"identifier": ident, "reason": "Duplicate exists", "ref_id": dup.id}
            )
            continue

        ref = svc.create_reference(project.id, metadata)
        imported.append({"identifier": ident, "ref_id": ref.id, "title": ref.title})

    return jsonify({"ok": True, "imported": imported, "skipped": skipped})


@references_bp.route(
    "/projects/<int:project_id>/references/duplicates", methods=["GET"]
)
@login_required
def list_duplicates(project_id):
    """Return duplicate reference pairs for a project."""
    from app.services.deduplication_service import DeduplicationService

    get_project_or_404(project_id)
    pairs = DeduplicationService().find_duplicates(project_id)

    return jsonify(
        {
            "pairs": [
                {
                    "a": {"id": a.id, "title": a.title, "doi": a.doi},
                    "b": {"id": b.id, "title": b.title, "doi": b.doi},
                    "strategy": strategy,
                    "score": score,
                }
                for a, b, strategy, score in pairs
            ]
        }
    )


@references_bp.route("/projects/<int:project_id>/references/merge", methods=["POST"])
@login_required
def merge_duplicates(project_id):
    """Merge two duplicate references.

    Request body::

        {"kept_id": 1, "removed_id": 2}
    """
    from app.services.deduplication_service import DeduplicationService

    get_project_or_404(project_id)
    data = _get_payload()
    kept_id = data.get("kept_id")
    removed_id = data.get("removed_id")
    if not kept_id or not removed_id:
        return jsonify({"error": "kept_id and removed_id required"}), 400

    try:
        ok, msg = DeduplicationService().merge(
            kept_id, removed_id, merged_by=current_user.id
        )
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "message": "Failed to merge references"}), 500
    return jsonify({"ok": ok, "message": msg})


@references_bp.route(
    "/projects/<int:project_id>/references/citation-styles", methods=["GET"]
)
@login_required
def list_citation_styles(project_id):
    """Return available CSL citation styles."""
    from app.services.citation_formatter_service import CSL_STYLES, SUPPORTED_STYLES

    built_in = [{"id": s, "name": s.title()} for s in SUPPORTED_STYLES]
    csl = [{"id": k, "name": v} for k, v in sorted(CSL_STYLES.items())]

    return jsonify(
        {
            "built_in": built_in,
            "csl_styles": csl,
            "total": len(built_in) + len(csl),
        }
    )


@references_bp.route(
    "/projects/<int:project_id>/references/export-bibliography", methods=["POST"]
)
@login_required
def export_bibliography(project_id):
    """Export a formatted bibliography.

    Request body::

        {"style": "apa", "format": "text"}
    """
    project = get_project_or_404(project_id)
    data = _get_payload()
    style = (data.get("style") or "apa").lower()

    refs = Reference.query.filter_by(project_id=project.id).all()
    from app.services.citation_formatter_service import format_reference_list

    citations = format_reference_list(refs, style)

    return jsonify({"style": style, "citations": citations})


@references_bp.route("/references/<int:ref_id>/citation-context", methods=["GET"])
@login_required
def get_citation_context(ref_id):
    """Return cached citation contexts for a reference."""
    from app.services.citation_context_service import CitationContextService

    ref = get_entity_or_404(Reference, ref_id)
    if not ref.doi:
        return jsonify({"error": "Reference has no DOI"}), 400

    svc = CitationContextService()
    contexts = svc.get_contexts_for_doi(ref.doi)
    summary = svc.get_polarity_summary(ref.doi)

    return jsonify({"doi": ref.doi, "contexts": contexts, "summary": summary})


@references_bp.route(
    "/references/<int:ref_id>/citation-context/refresh", methods=["POST"]
)
@login_required
def refresh_citation_context(ref_id):
    """Fetch fresh citation contexts from Semantic Scholar."""
    from app.services.citation_context_service import CitationContextService

    ref = get_entity_or_404(Reference, ref_id)
    if not ref.doi:
        return jsonify({"error": "Reference has no DOI"}), 400

    svc = CitationContextService()
    contexts = svc.fetch_contexts(ref.doi)

    return jsonify(
        {
            "doi": ref.doi,
            "contexts_fetched": len(contexts),
        }
    )


@references_bp.route("/references/analytics", methods=["GET"])
@login_required
def references_analytics():
    """Library analytics page."""
    return render_template("references/analytics.html")


@references_bp.route("/references/analytics/data", methods=["GET"])
@login_required
def references_analytics_data():
    """Return analytics data for the user's projects."""
    from app.services.library_analytics_service import LibraryAnalyticsService

    projects = ResearchProject.query.filter_by(owner_id=current_user.id).all()
    all_scores = []
    growth = {"by_year": {}}

    for proj in projects:
        svc = LibraryAnalyticsService()
        scores = svc.get_usage_scores(proj.id)
        for s in scores:
            s["project_id"] = proj.id
            s["project_name"] = proj.name
        all_scores.extend(scores)

        g = svc.get_temporal_growth(proj.id)
        for entry in g.get("by_year", []):
            y = entry["year"]
            growth["by_year"][y] = growth["by_year"].get(y, 0) + entry["count"]

    return jsonify(
        {
            "top_references": sorted(all_scores, key=lambda x: -x["usage_score"])[:20],
            "temporal_growth": sorted(
                [{"year": k, "count": v} for k, v in growth["by_year"].items()],
                key=lambda x: x["year"],
            ),
        }
    )

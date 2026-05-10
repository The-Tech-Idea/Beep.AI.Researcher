"""Documents routes blueprint package."""

import io
import logging
import uuid
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, session
from flask_login import login_required

from app.database import db
from app.core.time_utils import utcnow_naive
from app.models.researcher import ResearchProject, ResearcherDocument
from app.routes.documents.access import doc_access_bp
from app.routes.route_entity_lookup import (
    get_entity,
    get_entity_or_404,
    get_project_or_404,
)
from app.services.beep_ai_client import (
    is_configured,
    remove_document_from_project_rag,
    sync_document_to_rag,
)
from app.services.document_manager_service import DocumentManagerService
from app.services.quota_service import QuotaExceededError, quota_service
from app.services.reference_service import create_reference
from app.services.storage import StorageError, get_storage_backend

documents_bp = Blueprint("documents", __name__)
logger = logging.getLogger(__name__)


@documents_bp.route("/<int:project_id>/documents", methods=["GET"])
@login_required
def list_documents(project_id):
    project = get_project_or_404(project_id)
    docs = (
        ResearcherDocument.query.filter_by(project_id=project.id)
        .order_by(ResearcherDocument.created_at.desc())
        .all()
    )
    return jsonify({"documents": [doc.to_dict() for doc in docs]})


@documents_bp.route("/<int:project_id>/documents/upload", methods=["POST"])
@login_required
def upload_document(project_id):
    project = get_project_or_404(project_id)
    if "file" not in request.files:
        return jsonify({"error": "No file in request"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No filename"}), 400

    filename = Path(file.filename).name
    ext = Path(filename).suffix.lower()
    allowed = DocumentManagerService.allowed_upload_extensions
    if ext not in allowed:
        return jsonify({"error": f"File type {ext} not allowed"}), 400

    raw_bytes = file.read()
    size = len(raw_bytes)
    document_hash = DocumentManagerService.bytes_hash(raw_bytes)
    duplicate = DocumentManagerService.find_duplicate_document(
        project_id=project.id,
        document_hash=document_hash,
    )

    user_id = session.get("user_id")
    if user_id:
        try:
            quota_service.check_quota(
                user_id=user_id,
                upload_size_bytes=size,
                tenant_id=project.tenant_id,
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

    safe_key = f"{project_id}_{uuid.uuid4().hex[:8]}_{Path(filename).name}"
    backend = get_storage_backend()
    try:
        storage_key = backend.save(io.BytesIO(raw_bytes), safe_key)
    except StorageError as exc:
        return jsonify({"error": f"File storage failed: {exc}"}), 500

    document_manager = DocumentManagerService()
    extraction = document_manager.extract_document(
        filename=filename,
        raw_bytes=raw_bytes,
        content_type=file.content_type,
    )
    text_content = extraction.text

    doc = ResearcherDocument(
        project_id=project.id,
        filename=filename,
        file_path=storage_key,
        mime_type=file.content_type or "application/octet-stream",
        text_content=text_content,
        file_size=size,
        status="ready" if text_content else "pending",
        rag_document_id=DocumentManagerService.build_rag_document_id(
            project.id, filename
        ),
        rag_collection_id=project.collection_id,
        rag_content_hash=DocumentManagerService.content_hash(text_content),
        rag_sync_status="not_indexed" if text_content else "unavailable",
        rag_sync_message=None
        if text_content
        else "No text could be extracted for AI search.",
        document_hash=document_hash,
    )
    DocumentManagerService.apply_extraction_result(doc, extraction)
    db.session.add(doc)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to save document: {exc}"}), 500
    DocumentManagerService.record_ingestion_state(doc, duplicate_of=duplicate)

    if user_id:
        try:
            quota_service.record_upload(
                user_id=user_id,
                file_size_bytes=size,
                tenant_id=project.tenant_id,
            )
        except Exception as exc:
            logger.warning("quota record_upload failed: %s", exc)

    rag_sync_result = None
    if duplicate and duplicate.rag_sync_status == "indexed":
        doc.rag_sync_status = "skipped_duplicate"
        doc.rag_sync_message = (
            f"Same content already indexed as document {duplicate.id}."
        )
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return jsonify({"error": f"Failed to update document: {exc}"}), 500
        DocumentManagerService.record_ingestion_state(doc, duplicate_of=duplicate)
        rag_sync_result = {
            "synced": True,
            "message": doc.rag_sync_message,
            "duplicate_of_document_id": duplicate.id,
        }
    elif text_content and is_configured() and project.collection_id:
        ok, rag_result = sync_document_to_rag(project, doc, user_id=user_id)
        doc.rag_sync_status = "indexed" if ok else "failed"
        doc.rag_sync_message = (
            "Document indexed for AI search" if ok else str(rag_result)
        )
        doc.rag_document_id = doc.rag_document_id or f"researcher_doc_{doc.id}"
        doc.rag_collection_id = project.collection_id
        doc.rag_content_hash = DocumentManagerService.content_hash(text_content)
        if ok:
            doc.rag_synced_at = utcnow_naive()
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return jsonify({"error": f"Failed to update document: {exc}"}), 500
        DocumentManagerService.record_ingestion_state(
            doc, last_error=None if ok else str(rag_result)
        )
        rag_sync_result = {
            "synced": ok,
            "message": "Document indexed for AI search" if ok else str(rag_result),
        }
    elif text_content and not project.collection_id:
        doc.rag_sync_status = "unavailable"
        doc.rag_sync_message = "Project is not linked to a document library yet."
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return jsonify({"error": f"Failed to update document: {exc}"}), 500
        DocumentManagerService.record_ingestion_state(doc)

    reference_data = None
    create_ref = (request.form.get("reference_create") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    if create_ref or request.form.get("reference_title"):
        ref_payload = {
            "document_id": doc.id,
            "title": request.form.get("reference_title") or doc.filename,
            "authors": request.form.get("reference_authors"),
            "publication": request.form.get("reference_publication"),
            "year": request.form.get("reference_year"),
            "doi": request.form.get("reference_doi"),
            "url": request.form.get("reference_url"),
            "citation": request.form.get("reference_citation"),
            "notes": request.form.get("reference_notes"),
        }
        reference = create_reference(project, ref_payload)
        reference_data = reference.to_dict()

    payload = doc.to_dict()
    if reference_data:
        payload["reference"] = reference_data
    if rag_sync_result:
        payload["rag_sync"] = rag_sync_result
    payload["extraction"] = {
        "status": doc.extraction_status,
        "parser_name": doc.parser_name,
        "parser_version": doc.parser_version,
        "quality": doc.extraction_quality,
        "page_count": doc.page_count,
        "table_count": doc.table_count,
        "image_count": doc.image_count,
        "warnings": doc.extraction_warnings,
    }
    payload["ingestion_state"] = (
        doc.ingestion_state.to_dict() if getattr(doc, "ingestion_state", None) else None
    )
    return jsonify(payload), 201


@documents_bp.route("/<int:project_id>/documents/<int:doc_id>", methods=["GET"])
@login_required
def get_document(project_id, doc_id):
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()
    return jsonify(doc.to_dict())


@documents_bp.route("/<int:project_id>/documents/<int:doc_id>/content", methods=["GET"])
@login_required
def get_document_content(project_id, doc_id):
    from app.models.researcher import Code, CodedReference

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()
    refs = CodedReference.query.filter_by(document_id=doc.id).all()
    coded_references = []
    for ref in refs:
        code = get_entity(Code, ref.code_id)
        coded_references.append(
            {
                "id": ref.id,
                "code_id": ref.code_id,
                "code_name": code.name if code else "",
                "code_color": code.color if code else "#6366f1",
                "chunk_id": ref.chunk_id,
                "start_offset": ref.start_offset,
                "end_offset": ref.end_offset,
                "memo": ref.memo,
            }
        )

    return jsonify(
        {
            "document_id": doc.id,
            "filename": doc.filename,
            "text_content": doc.text_content or "",
            "coded_references": coded_references,
        }
    )


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/download", methods=["GET"]
)
@login_required
def download_document(project_id, doc_id):
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    if not doc.file_path:
        return jsonify({"error": "No storage key recorded for this document"}), 404

    backend = get_storage_backend()
    try:
        return backend.send_file_response(doc.file_path, doc.filename, doc.mime_type)
    except StorageError as exc:
        return jsonify({"error": f"File not found: {exc}"}), 404


@documents_bp.route("/<int:project_id>/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_document(project_id, doc_id):
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    rag_removed = False
    if is_configured() and project.collection_id:
        user_id = session.get("user_id")
        rag_doc_id = doc.rag_document_id or f"researcher_doc_{doc.id}"
        ok, _ = remove_document_from_project_rag(
            project=project,
            document_ids=[rag_doc_id],
            user_id=user_id,
        )
        rag_removed = ok

    if doc.file_path:
        backend = get_storage_backend()
        try:
            backend.delete(doc.file_path)
        except StorageError:
            pass

    delete_user_id = session.get("user_id")
    if delete_user_id and doc.file_size:
        try:
            quota_service.record_delete(
                user_id=delete_user_id,
                file_size_bytes=doc.file_size,
                tenant_id=project.tenant_id,
            )
        except Exception as exc:
            logger.warning("quota record_delete failed: %s", exc)

    db.session.delete(doc)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to delete document: {exc}"}), 500
    return jsonify(
        {
            "deleted": True,
            "document_id": doc_id,
            "rag_removed": rag_removed,
        }
    )


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/sync-rag", methods=["POST"]
)
@login_required
def sync_document_rag(project_id, doc_id):
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    if not doc.text_content:
        return jsonify({"error": "Document has no text content to sync"}), 400
    if not is_configured():
        return jsonify(
            {"error": "The document library service is not configured."}
        ), 400
    if not project.collection_id:
        return jsonify(
            {"error": "Project is not linked to a document library yet."}
        ), 400

    user_id = session.get("user_id")
    ok, result = sync_document_to_rag(project, doc, user_id=user_id)
    doc.rag_document_id = doc.rag_document_id or f"researcher_doc_{doc.id}"
    doc.rag_collection_id = project.collection_id
    doc.rag_content_hash = DocumentManagerService.content_hash(doc.text_content)
    if ok:
        doc.rag_sync_status = "indexed"
        doc.rag_sync_message = "Document indexed for AI search"
        doc.rag_synced_at = utcnow_naive()
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return jsonify({"error": f"Failed to update document: {exc}"}), 500
        DocumentManagerService.record_ingestion_state(doc)
        return jsonify(
            {
                "synced": True,
                "document_id": doc_id,
                "message": "Document indexed for AI search",
            }
        )
    doc.rag_sync_status = "failed"
    doc.rag_sync_message = str(result)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to update document: {exc}"}), 500
    DocumentManagerService.record_ingestion_state(doc, last_error=str(result))
    return jsonify(
        {
            "synced": False,
            "document_id": doc_id,
            "error": str(result),
        }
    ), 500


@documents_bp.route("/<int:project_id>/documents/<int:doc_id>/repair", methods=["POST"])
@login_required
def repair_document(project_id, doc_id):
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    try:
        result = DocumentManagerService().repair_document(doc.id, sync_to_rag=True)
        repaired_doc = result["document"]
        return jsonify(
            {
                "repaired": True,
                "document_id": repaired_doc.id,
                "extraction_status": repaired_doc.extraction_status,
                "rag_sync_status": repaired_doc.rag_sync_status,
                "message": result["rag_sync"].get("message"),
                "document": repaired_doc.to_dict(),
                "ingestion_state": repaired_doc.ingestion_state.to_dict()
                if repaired_doc.ingestion_state
                else None,
            }
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 500


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/related-reading", methods=["GET"]
)
@login_required
def get_related_reading(project_id, doc_id):
    from app.config_manager import is_feature_enabled
    from app.services.recommendation_service import RecommendationService

    if not is_feature_enabled("ai_discovery_enabled"):
        return jsonify({"error": "Feature not enabled"}), 404

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    raw_limit = request.args.get("limit")
    if raw_limit in (None, ""):
        limit = 10
    else:
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be an integer between 1 and 30"}), 400
        if limit < 1:
            return jsonify({"error": "limit must be an integer between 1 and 30"}), 400
        limit = min(limit, 30)

    try:
        items = RecommendationService().get_related_reading_for_document(
            doc.id,
            project.owner_id,
            limit=limit,
        )
    except LookupError:
        return jsonify({"error": "Document not found"}), 404

    return jsonify(
        {
            "items": [
                {
                    "title": item.title,
                    "authors": item.authors,
                    "abstract": item.abstract,
                    "source": item.source,
                    "url": item.url,
                    "publication_date": item.publication_date,
                    "relevance_score": item.relevance_score,
                }
                for item in items
            ]
        }
    )


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/audio-summary", methods=["GET"]
)
@login_required
def get_audio_summary(project_id, doc_id):
    from app.config_manager import is_feature_enabled
    from app.services.audio_summary_service import AudioSummaryService

    if not is_feature_enabled("ai_discovery_enabled"):
        return jsonify({"error": "Feature not enabled"}), 404

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    voice = request.args.get("voice") or None
    try:
        service = AudioSummaryService()
        result = service.generate_audio_summary(doc.id, voice=voice)
    except (LookupError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    audio_data = service.extract_audio_bytes(result)
    if not audio_data:
        return jsonify({"error": "No audio returned from TTS service"}), 502

    content_type = result.get("content_type") if isinstance(result, dict) else None
    return Response(audio_data, mimetype=content_type or "audio/mpeg")


__all__ = ["documents_bp", "doc_access_bp", "_get_project_or_404", "ResearcherDocument"]


# ===========================================================================
# Phase 4 — Document AI Panels (auto-extract, flashcards, finding-to-extraction)
# ===========================================================================


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/auto-extract", methods=["GET"]
)
@login_required
def auto_extract(project_id, doc_id):
    """Extract summary, key findings, and data tables from a document (schema-free)."""
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    from app.services.auto_extraction_service import AutoExtractionService

    text = doc.text_content or ""
    if not text.strip():
        return jsonify({"error": "Document has no text content to extract from"}), 400

    payload, status_code = AutoExtractionService().extract(doc.id, text)
    return jsonify(payload), status_code


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/generate-flashcards", methods=["POST"]
)
@login_required
def generate_flashcards_preview(project_id, doc_id):
    """Generate flashcard preview from a document's text.

    Request body::

        {"count": 6}  // optional, default 6
    """
    from app.config_manager import is_feature_enabled

    if not is_feature_enabled("ai_discovery_enabled"):
        return jsonify({"error": "Feature not enabled"}), 404

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    text = doc.text_content or ""
    if not text.strip():
        return jsonify({"error": "Document has no text content"}), 400

    from app.services.training_service import TrainingService

    data = request.get_json(silent=True) or {}
    count = int(data.get("count", 6))
    count = max(1, min(count, 20))

    service = TrainingService()
    try:
        flashcards = service.generate_flashcards_from_text(text, count=count)
        return jsonify({"flashcards": flashcards})
    except Exception as exc:
        logger.exception("Flashcard generation failed for doc %d", doc_id)
        return jsonify({"error": str(exc)}), 500


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/save-flashcards", methods=["POST"]
)
@login_required
def save_flashcards(project_id, doc_id):
    """Save selected flashcards to the document's training set.

    Request body::

        {"flashcards": [{"question": "...", "answer": "..."}]}
    """
    from app.config_manager import is_feature_enabled

    if not is_feature_enabled("ai_discovery_enabled"):
        return jsonify({"error": "Feature not enabled"}), 404

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    data = request.get_json(silent=True) or {}
    cards = data.get("flashcards")
    if not cards or not isinstance(cards, list):
        return jsonify({"error": "flashcards array required"}), 400

    from app.models.researcher import Flashcard
    from app.services.training_service import TrainingService

    service = TrainingService()
    saved = []
    for card in cards:
        q = (card.get("question") or "").strip()
        a = (card.get("answer") or "").strip()
        if not q or not a:
            continue
        fc = service.create_flashcard(project_id, doc_id, q, a)
        saved.append(
            fc.to_dict() if hasattr(fc, "to_dict") else {"id": fc.id, "question": q}
        )

    return jsonify({"saved": saved, "count": len(saved)})


@documents_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/finding-to-extraction", methods=["POST"]
)
@login_required
def finding_to_extraction(project_id, doc_id):
    """Promote an auto-extracted finding to a structured ExtractionResult.

    Request body::

        {"finding": "The treatment reduced symptoms by 40%"}
    """
    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    data = request.get_json(silent=True) or {}
    finding = (data.get("finding") or "").strip()
    if not finding:
        return jsonify({"error": "finding text is required"}), 400

    from app.models.researcher import DocumentAnnotation

    annotation = DocumentAnnotation(
        document_id=doc.id,
        user_id=session.get("user_id"),
        text=finding,
        annotation_type="finding",
        page_number=None,
        start_offset=0,
        end_offset=len(finding),
    )
    db.session.add(annotation)
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to save annotation: {exc}"}), 500

    return jsonify({"ok": True, "annotation_id": annotation.id})

"""Projects API routes. Uses config_manager for limits."""

from flask import Blueprint, request, jsonify, url_for
from flask_login import login_required, current_user

from app.config_manager import config_manager
from app.database import db
from app.models.researcher import ResearchProject
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.services.beep_ai_client import (
    get_collection_document_chunks,
    get_collection_document_lineage,
    get_collection_organization_profile,
    is_configured,
    list_graph_extraction_profile_options,
    list_chunk_templates,
    list_rag_collections,
    update_collection_organization_profile,
)
from app.services.chunk_template_service import (
    apply_template_to_project,
    ensure_researcher_templates,
    get_document_type_template_contract,
    get_project_template,
    remove_template_from_project,
    suggest_template_slug,
    RESEARCHER_TEMPLATES,
)
from app.services.graph_reading_mode_service import (
    get_graph_reading_mode_contract,
    resolve_graph_reading_mode,
)
from app.services.project_rag_preferences_service import resolve_project_quality_mode
from app.decorators.permissions import require_permission

projects_bp = Blueprint("projects", __name__)


def _current_user_role():
    """Best-effort role extraction for middleware scope context."""
    role = getattr(current_user, "role", None)
    if role is None:
        role = getattr(current_user, "user_role", None)
    if role is None and hasattr(current_user, "is_admin"):
        return "admin" if current_user.is_admin else "user"
    return str(role) if role is not None else "user"


@projects_bp.route("/rag/collections", methods=["GET"])
@login_required
def list_rag_collections_for_project():
    """List document libraries available for project connection."""
    if not is_configured():
        return jsonify(
            {
                "collections": [],
                "message": "Connect the document library service in Admin settings first.",
            }
        )
    ok, colls = list_rag_collections()
    if not ok:
        return jsonify({"collections": [], "error": str(colls)})
    return jsonify({"collections": colls})


@projects_bp.route("/rag/template-mapping-contract", methods=["GET"])
@login_required
def get_rag_template_mapping_contract():
    """Return a simple document-type to template mapping contract for Researcher."""
    return jsonify(
        {
            "success": True,
            "contract": get_document_type_template_contract(),
        }
    )


@projects_bp.route("/rag/graph-reading-contract", methods=["GET"])
@login_required
def get_graph_reading_contract():
    """Return a simple graph-reading mode contract plus available profile options."""
    available_profiles: list = []
    if is_configured():
        ok, profiles = list_graph_extraction_profile_options()
        if ok and isinstance(profiles, list):
            available_profiles = profiles

    return jsonify(
        {
            "success": True,
            "contract": get_graph_reading_mode_contract(),
            "available_profiles": available_profiles,
        }
    )


@projects_bp.route("/", methods=["GET"])
@login_required
def list_projects():
    tenant_id = request.args.get("tenant_id", type=int)
    limit = int(config_manager.get_setting("project_list_limit", default=50))
    q = ResearchProject.query
    if tenant_id is not None:
        q = q.filter_by(tenant_id=tenant_id)
    projects = q.order_by(ResearchProject.updated_at.desc()).limit(limit).all()
    return jsonify({"projects": [p.to_dict() for p in projects]})


@projects_bp.route("/", methods=["POST"])
@login_required
def create_project():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    owner_id = data.get("owner_id") or current_user.id
    project = ResearchProject(
        name=name,
        description=data.get("description", ""),
        owner_id=owner_id,
        tenant_id=data.get("tenant_id"),
        status="draft",
    )
    db.session.add(project)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create project"}), 500
    payload = project.to_dict()
    payload["start_url"] = url_for(
        "project_start.project_start_page", project_id=project.id
    )
    payload["overview_url"] = url_for(
        "researcher.project_overview", project_id=project.id
    )
    payload["settings_url"] = url_for(
        "researcher.project_settings", project_id=project.id
    )
    return jsonify(payload), 201


@projects_bp.route("/<int:project_id>", methods=["GET"])
@login_required
def get_project(project_id):
    project = get_project_or_404(project_id)
    return jsonify(project.to_dict())


@projects_bp.route("/<int:project_id>/rag/organization-profile", methods=["GET"])
@login_required
def get_project_rag_organization_profile(project_id):
    project = get_project_or_404(project_id)
    if not project.collection_id:
        return jsonify(
            {
                "success": False,
                "error": "Project is not linked to a document library yet.",
            }
        ), 400
    if not is_configured():
        return jsonify(
            {
                "success": False,
                "error": "The document library service is not configured.",
            }
        ), 503

    quality_mode, quality_mode_source = resolve_project_quality_mode(
        project,
        (request.args.get("quality_mode") or "").strip() or None,
    )
    ok, profile = get_collection_organization_profile(
        project.collection_id,
        user_id=str(current_user.id),
        quality_mode=quality_mode,
    )
    if not ok:
        return jsonify({"success": False, "error": str(profile)}), 502

    available_profiles = []
    ok_profiles, profiles = list_graph_extraction_profile_options()
    if ok_profiles and isinstance(profiles, list):
        available_profiles = profiles

    return jsonify(
        {
            "success": True,
            "project_id": project.id,
            "collection_id": project.collection_id,
            "quality_mode": quality_mode,
            "quality_mode_source": quality_mode_source,
            "organization_profile": profile,
            "graph_reading_mode": resolve_graph_reading_mode(
                collection_graph_extraction_profile_id=profile.get(
                    "collection_graph_extraction_profile_id"
                ),
                database_default_graph_extraction_profile_id=profile.get(
                    "database_default_graph_extraction_profile_id"
                ),
                effective_graph_extraction_profile_id=profile.get(
                    "graph_extraction_profile_id"
                ),
                available_profiles=available_profiles,
            ),
        }
    )


@projects_bp.route("/<int:project_id>/rag/organization-profile", methods=["PUT"])
@login_required
def update_project_rag_organization_profile(project_id):
    project = get_project_or_404(project_id)
    if not project.collection_id:
        return jsonify(
            {
                "success": False,
                "error": "Project is not linked to a document library yet.",
            }
        ), 400
    if not is_configured():
        return jsonify(
            {
                "success": False,
                "error": "The document library service is not configured.",
            }
        ), 503

    data = request.get_json() or {}
    organization_profile = (
        data.get("organization_profile")
        if isinstance(data.get("organization_profile"), dict)
        else {}
    )
    organization_profile = dict(organization_profile)
    metadata_schema = (
        data.get("metadata_schema")
        if isinstance(data.get("metadata_schema"), dict)
        else None
    )
    requested_quality_mode = (data.get("quality_mode") or "").strip() or None
    graph_extraction_profile_id = None
    if "graph_extraction_profile_id" in data:
        graph_extraction_profile_id = (
            data.get("graph_extraction_profile_id") or ""
        ).strip()
    if metadata_schema is None and isinstance(
        organization_profile.get("metadata_schema"), dict
    ):
        metadata_schema = dict(organization_profile.get("metadata_schema"))
    organization_profile.pop("metadata_schema", None)

    ok, result = update_collection_organization_profile(
        project.collection_id,
        organization_profile,
        metadata_schema=metadata_schema,
        graph_extraction_profile_id=graph_extraction_profile_id,
        user_id=str(current_user.id),
        user_role=_current_user_role(),
        quality_mode=requested_quality_mode,
        chunk_template_id=data.get("chunk_template_id"),
    )
    if not ok:
        return jsonify({"success": False, "error": str(result)}), 502

    if requested_quality_mode:
        project.rag_quality_mode = requested_quality_mode
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify(
                {"success": False, "error": "Failed to save quality mode"}
            ), 500

    available_profiles = []
    ok_profiles, profiles = list_graph_extraction_profile_options()
    if ok_profiles and isinstance(profiles, list):
        available_profiles = profiles

    return jsonify(
        {
            "success": True,
            "project_id": project.id,
            "collection_id": project.collection_id,
            "quality_mode": project.rag_quality_mode or "balanced",
            "quality_mode_source": "saved_project_choice",
            "graph_reading_mode": resolve_graph_reading_mode(
                collection_graph_extraction_profile_id=(
                    result.get("organization_profile", {}).get(
                        "collection_graph_extraction_profile_id"
                    )
                    if isinstance(result, dict)
                    else None
                ),
                database_default_graph_extraction_profile_id=(
                    result.get("organization_profile", {}).get(
                        "database_default_graph_extraction_profile_id"
                    )
                    if isinstance(result, dict)
                    else None
                ),
                effective_graph_extraction_profile_id=(
                    result.get("organization_profile", {}).get(
                        "graph_extraction_profile_id"
                    )
                    if isinstance(result, dict)
                    else None
                ),
                available_profiles=available_profiles,
            ),
            **(result if isinstance(result, dict) else {"result": result}),
        }
    )


@projects_bp.route(
    "/<int:project_id>/rag/documents/<document_id>/chunks", methods=["GET"]
)
@login_required
def get_project_rag_document_chunks(project_id, document_id):
    project = get_project_or_404(project_id)
    if not project.collection_id:
        return jsonify(
            {
                "success": False,
                "error": "Project is not linked to a document library yet.",
            }
        ), 400
    if not is_configured():
        return jsonify(
            {
                "success": False,
                "error": "The document library service is not configured.",
            }
        ), 503

    ok, result = get_collection_document_chunks(
        project.collection_id,
        document_id,
        user_id=str(current_user.id),
        include_content=(request.args.get("include_content") or "").strip().lower()
        in {"1", "true", "yes", "on"},
        preview_chars=request.args.get("preview_chars", type=int),
    )
    if not ok:
        return jsonify({"success": False, "error": str(result)}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "result": result}
    )


@projects_bp.route(
    "/<int:project_id>/rag/documents/<document_id>/lineage", methods=["GET"]
)
@login_required
def get_project_rag_document_lineage(project_id, document_id):
    project = get_project_or_404(project_id)
    if not project.collection_id:
        return jsonify(
            {
                "success": False,
                "error": "Project is not linked to a document library yet.",
            }
        ), 400
    if not is_configured():
        return jsonify(
            {
                "success": False,
                "error": "The document library service is not configured.",
            }
        ), 503

    ok, result = get_collection_document_lineage(
        project.collection_id,
        document_id,
        user_id=str(current_user.id),
    )
    if not ok:
        return jsonify({"success": False, "error": str(result)}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "result": result}
    )


@projects_bp.route("/<int:project_id>", methods=["PUT"])
@login_required
def update_project(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    if "name" in data:
        project.name = (data["name"] or "").strip() or project.name
    if "description" in data:
        project.description = data["description"]
    if "status" in data:
        project.status = data["status"]
    if "collection_id" in data:
        project.collection_id = (data["collection_id"] or "").strip() or None
    if "chunk_template_slug" in data:
        project.chunk_template_slug = (
            data["chunk_template_slug"] or ""
        ).strip() or None
    if "rag_quality_mode" in data:
        project.rag_quality_mode = (data["rag_quality_mode"] or "").strip() or None
    if "custom_instructions" in data:
        project.custom_instructions = data["custom_instructions"]
    if "citation_format" in data:
        project.citation_format = data["citation_format"]
    if "ai_language" in data:
        project.ai_language = data["ai_language"]
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update project"}), 500
    return jsonify(project.to_dict())


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):
    project = get_project_or_404(project_id)
    db.session.delete(project)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete project"}), 500
    return jsonify({"ok": True}), 204


# ---------------------------------------------------------------------------
# RAG Chunk Template routes
# ---------------------------------------------------------------------------


@projects_bp.route("/rag/chunk-templates", methods=["GET"])
@login_required
def list_available_chunk_templates():
    """List all chunk templates available on the server.

    Query params:
        include_researcher (bool, default true) — include researcher-specific
            template definitions even if they are not yet provisioned.
        suggest_for (str) — optional project type hint; returns a
            ``suggested_slug`` field in the response.
    """
    if not is_configured():
        return jsonify(
            {"templates": [], "message": "Document library service not configured."}
        )

    ok, templates = list_chunk_templates()
    if not ok:
        return jsonify({"templates": [], "error": str(templates)})

    include_researcher = request.args.get("include_researcher", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    suggest_for = (request.args.get("suggest_for") or "").strip() or None

    resp: dict = {"templates": templates}

    if include_researcher:
        resp["researcher_templates"] = [
            {
                "slug": slug,
                "name": spec["name"],
                "description": spec["description"],
                "chunking_config": spec["chunking_config"],
            }
            for slug, spec in RESEARCHER_TEMPLATES.items()
        ]

    if suggest_for:
        resp["suggested_slug"] = suggest_template_slug(suggest_for)

    return jsonify(resp)


@projects_bp.route("/rag/chunk-templates/provision", methods=["POST"])
@login_required
@require_permission("admin")
def provision_researcher_templates():
    """Provision all researcher-specific chunk templates on the server.

    Idempotent — already-existing templates are skipped.
    """
    if not is_configured():
        return jsonify(
            {"success": False, "error": "Document library service not configured."}
        ), 503

    result = ensure_researcher_templates()
    return jsonify({"success": True, **result})


@projects_bp.route("/<int:project_id>/rag/chunk-template", methods=["GET"])
@login_required
def get_project_chunk_template(project_id):
    """Get the chunk template currently applied to a project's collection."""
    project = get_project_or_404(project_id)
    if not is_configured():
        return jsonify(
            {"success": False, "error": "Document library service not configured."}
        ), 503

    ok, tpl = get_project_template(project)
    if not ok:
        return jsonify({"success": False, "error": str(tpl)}), 502

    suggested = suggest_template_slug(getattr(project, "project_type", None))
    return jsonify(
        {
            "success": True,
            "project_id": project_id,
            "collection_id": getattr(project, "collection_id", None),
            "template": tpl,
            "suggested_slug": suggested,
        }
    )


@projects_bp.route("/<int:project_id>/rag/chunk-template", methods=["PUT"])
@login_required
def apply_project_chunk_template(project_id):
    """Apply a chunk template to a project's collection.

    Body JSON:
        template_id (str, required) — ID, slug or name of the template to apply.
    """
    project = get_project_or_404(project_id)
    if not is_configured():
        return jsonify(
            {"success": False, "error": "Document library service not configured."}
        ), 503

    data = request.get_json() or {}
    template_id = (data.get("template_id") or "").strip()
    if not template_id:
        return jsonify({"success": False, "error": "template_id is required."}), 400

    ok, result = apply_template_to_project(
        project,
        template_id,
        user_id=current_user.id,
    )
    if not ok:
        return jsonify({"success": False, "error": str(result)}), 502

    return jsonify(
        {
            "success": True,
            "project_id": project_id,
            "collection_id": getattr(project, "collection_id", None),
            "template_id": template_id,
            **(result if isinstance(result, dict) else {}),
        }
    )


@projects_bp.route("/<int:project_id>/rag/chunk-template", methods=["DELETE"])
@login_required
def remove_project_chunk_template(project_id):
    """Remove any chunk template assignment from a project's collection."""
    project = get_project_or_404(project_id)
    if not is_configured():
        return jsonify(
            {"success": False, "error": "Document library service not configured."}
        ), 503

    ok, result = remove_template_from_project(project)
    if not ok:
        return jsonify({"success": False, "error": str(result)}), 502

    return jsonify(
        {
            "success": True,
            "project_id": project_id,
            "collection_id": getattr(project, "collection_id", None),
        }
    )

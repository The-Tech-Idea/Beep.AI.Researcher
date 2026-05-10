"""Dashboard routes. Uses config_manager for limits."""

from sqlalchemy import func

from flask import Blueprint, flash, redirect, render_template, request, jsonify, url_for
from flask_login import login_required, current_user

from app.config_manager import config_manager
from app.database import db
from app.routes.route_entity_lookup import (
    get_entity,
    get_entity_or_404,
    _base_template,
    get_project_or_404,
)
from app.services import beep_ai_client
from app.services.citation_library_service import build_project_citation_library
from app.services.document_reference_navigation_service import (
    build_document_reference_navigation,
)
from app.services.project_grounded_context_service import build_project_grounded_context
from app.services.project_grounded_prompt_service import merge_supporting_sources
from app.services.project_rag_preferences_service import (
    resolve_project_generation_temperature,
)
from app.models.researcher import (
    Code,
    ResearchProject,
    ResearchTask,
    ResearcherDocument,
    CodedReference,
    ExtractionResult,
    ExtractionSchema,
    Flashcard,
    Quiz,
    ResearchReportDraft,
    ChatSession,
)
from app.models.tenant import Tenant

dashboard_bp = Blueprint("researcher", __name__, url_prefix="/researcher")


def _embed():
    """True when page is loaded in iframe (e.g. tab content)."""
    v = (request.args.get("embed") or "").strip().lower()
    return v in ("1", "true", "yes")


def _project_sidebar_counts(project_id):
    """Shared sidebar badge counts for project pages."""
    return {
        "document_count": ResearcherDocument.query.filter_by(
            project_id=project_id
        ).count(),
        "code_count": Code.query.filter_by(project_id=project_id).count(),
        "task_count": ResearchTask.query.filter_by(project_id=project_id).count(),
    }


def _default_report_html():
    return (
        "<h1>Untitled Report</h1>"
        "<p><em>Write your overview here...</em></p>"
        "<h2>Introduction</h2>"
        "<p>Start explaining the background and why this topic matters.</p>"
        "<h2>Methods</h2>"
        "<p>Describe how you gathered and reviewed your material.</p>"
        "<h2>Results</h2>"
        "<p>Summarize the main findings from your project files and notes.</p>"
        "<h2>Discussion</h2>"
        "<p>Explain what the findings mean and how they connect together.</p>"
        "<h2>Conclusion</h2>"
        "<p>Finish with the main takeaway and any next steps.</p>"
    )


@dashboard_bp.route("/")
@login_required
def index():
    tenant_id = request.args.get("tenant_id", type=int)
    limit = int(config_manager.get_setting("dashboard_project_limit", default=20))
    q = ResearchProject.query
    if tenant_id is not None:
        q = q.filter_by(tenant_id=tenant_id)
    projects = q.order_by(ResearchProject.updated_at.desc()).limit(limit).all()
    tenants = Tenant.query.order_by(Tenant.name).all()
    status_counts = {}
    for p in projects:
        key = (p.status or "unknown").lower()
        status_counts[key] = status_counts.get(key, 0) + 1
    project_ids = [p.id for p in projects]
    document_counts = {}
    code_counts = {}
    task_counts = {}
    total_documents = total_codes = total_tasks = 0
    if project_ids:
        document_counts = dict(
            db.session.query(
                ResearcherDocument.project_id, func.count(ResearcherDocument.id)
            )
            .filter(ResearcherDocument.project_id.in_(project_ids))
            .group_by(ResearcherDocument.project_id)
            .all()
        )
        code_counts = dict(
            db.session.query(Code.project_id, func.count(Code.id))
            .filter(Code.project_id.in_(project_ids))
            .group_by(Code.project_id)
            .all()
        )
        task_counts = dict(
            db.session.query(ResearchTask.project_id, func.count(ResearchTask.id))
            .filter(ResearchTask.project_id.in_(project_ids))
            .group_by(ResearchTask.project_id)
            .all()
        )
        total_documents = sum(document_counts.values())
        total_codes = sum(code_counts.values())
        total_tasks = sum(task_counts.values())
    return render_template(
        "dashboard.html",
        projects=projects,
        tenants=tenants,
        selected_tenant_id=tenant_id,
        status_counts=status_counts,
        project_totals={
            "documents": total_documents,
            "codes": total_codes,
            "tasks": total_tasks,
        },
        project_counts={
            "documents": document_counts,
            "codes": code_counts,
            "tasks": task_counts,
        },
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    """Redirect to new modular overview page"""
    from flask import redirect, url_for

    return redirect(url_for("researcher.project_overview", project_id=project_id))


@dashboard_bp.route("/projects/<int:project_id>/overview")
@login_required
def project_overview(project_id):
    """Project overview/dashboard page"""
    project = get_project_or_404(project_id)

    document_count = ResearcherDocument.query.filter_by(project_id=project.id).count()
    code_count = Code.query.filter_by(project_id=project.id).count()
    task_count = ResearchTask.query.filter_by(project_id=project.id).count()
    chat_count = ChatSession.query.filter_by(project_id=project.id).count()

    # Additional pipeline counts
    extraction_count = (
        db.session.query(func.count(ExtractionResult.id))
        .join(ExtractionSchema, ExtractionResult.schema_id == ExtractionSchema.id)
        .filter(ExtractionSchema.project_id == project.id)
        .scalar()
        or 0
    )
    flashcard_count = Flashcard.query.filter_by(project_id=project.id).count()
    quiz_count = Quiz.query.filter_by(project_id=project.id).count()

    recent_documents = (
        ResearcherDocument.query.filter_by(project_id=project.id)
        .order_by(ResearcherDocument.created_at.desc())
        .limit(3)
        .all()
    )
    recent_tasks = (
        ResearchTask.query.filter_by(project_id=project.id)
        .order_by(ResearchTask.updated_at.desc())
        .limit(3)
        .all()
    )
    activities = [
        {"type": "document", "title": doc.filename, "created_at": doc.created_at}
        for doc in recent_documents
    ] + [
        {"type": "task", "title": task.title, "created_at": task.updated_at}
        for task in recent_tasks
    ]
    activities.sort(
        key=lambda item: (
            item.get("created_at").timestamp() if item.get("created_at") else 0
        ),
        reverse=True,
    )

    return render_template(
        "project/overview.html",
        project=project,
        document_count=document_count,
        code_count=code_count,
        task_count=task_count,
        chat_count=chat_count,
        extraction_count=extraction_count,
        flashcard_count=flashcard_count,
        quiz_count=quiz_count,
        activities=activities,
        active_page="overview",
        base_template=_base_template(),
    )


@dashboard_bp.route("/api/projects-list")
@login_required
def api_projects_list():
    """JSON endpoint for SPA project selector."""
    projects = ResearchProject.query.order_by(ResearchProject.updated_at.desc()).all()
    return jsonify(
        [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status or "active",
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in projects
        ]
    )


@dashboard_bp.route("/workspace")
@login_required
def workspace():
    """Legacy workspace route — now just redirects to SPA home."""
    from flask import redirect, url_for

    return redirect(url_for("researcher.index"))


@dashboard_bp.route("/documents")
@login_required
def my_documents():
    """User-owned document registry across visible projects."""
    from app.services.document_manager_service import document_manager_service

    page = request.args.get("page", 1, type=int)
    project_filter = request.args.get("project_id", type=int)
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    file_type = request.args.get("file_type", "").strip()

    result = document_manager_service.search_user_documents(
        user_id=current_user.id,
        page=page,
        per_page=50,
        project_id=project_filter,
        search=search,
        status=status_filter,
        file_type=file_type,
    )
    projects = document_manager_service.list_user_projects(current_user.id)

    return render_template(
        "documents/my_documents.html",
        documents=result.pagination.items,
        pagination=result.pagination,
        total_count=result.total_count,
        total_storage=result.total_storage,
        projects=projects,
        project_filter=project_filter,
        search=search,
        status_filter=status_filter,
        file_type=file_type,
        base_template=_base_template(),
    )


@dashboard_bp.route("/documents/upload", methods=["POST"])
@login_required
def upload_my_document():
    """Upload a document from the user document registry."""
    from app.services.document_manager_service import document_manager_service
    from app.services.quota_service import QuotaExceededError

    project_id = request.form.get("project_id", type=int)
    if not project_id:
        flash("Choose a project before uploading a document.", "warning")
        return redirect(url_for("researcher.my_documents"))

    try:
        result = document_manager_service.upload_user_document(
            user_id=current_user.id,
            project_id=project_id,
            file_storage=request.files.get("file"),
        )
        document = result["document"]
        rag_sync = result["rag_sync"]
        if rag_sync.get("synced"):
            flash(
                f'Document "{document.filename}" uploaded and indexed for AI search.',
                "success",
            )
        else:
            flash(
                f'Document "{document.filename}" uploaded. {rag_sync.get("message")}',
                "warning",
            )
    except QuotaExceededError as exc:
        flash(str(exc), "danger")
    except (LookupError, PermissionError, ValueError) as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        db.session.rollback()
        flash(f"Document upload failed: {exc}", "danger")

    return redirect(url_for("researcher.my_documents", project_id=project_id))


@dashboard_bp.route("/documents/<int:document_id>/sync-rag", methods=["POST"])
@login_required
def sync_my_document_rag(document_id):
    """Retry AI Server RAG indexing from the user document registry."""
    from app.services.document_manager_service import document_manager_service

    try:
        result = document_manager_service.sync_document_to_rag(
            document_id=document_id,
            user_id=current_user.id,
        )
        category = "success" if result.get("synced") else "warning"
        flash(result.get("message") or "RAG sync completed.", category)
    except (LookupError, PermissionError) as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        db.session.rollback()
        flash(f"RAG sync failed: {exc}", "danger")

    return redirect(request.referrer or url_for("researcher.my_documents"))


@dashboard_bp.route("/projects/<int:project_id>/documents")
@login_required
def project_documents(project_id):
    """Document management page"""
    from app.models.researcher import ResearcherDocument
    from app.services.package_manager_service import check_optional_feature

    project = get_project_or_404(project_id)
    documents = (
        ResearcherDocument.query.filter_by(project_id=project.id)
        .order_by(ResearcherDocument.created_at.desc())
        .all()
    )
    packages = {
        "docling_extraction": check_optional_feature("docling_extraction").get(
            "installed", False
        ),
    }

    return render_template(
        "project/documents.html",
        project=project,
        documents=documents,
        packages=packages,
        active_page="documents",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/search")
@login_required
def project_search(project_id):
    """Search and chat page"""
    from app.models.researcher import ChatMessage

    project = get_project_or_404(project_id)
    chat_history = (
        ChatMessage.query.filter_by(project_id=project.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "project/search.html",
        project=project,
        chat_history=chat_history,
        active_page="search",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/codes")
@login_required
def project_codes(project_id):
    """Codes and themes page"""
    from app.models.researcher import Code, CodedReference

    project = get_project_or_404(project_id)
    codes = Code.query.filter_by(project_id=project.id).order_by(Code.name).all()

    # Add excerpt counts
    for code in codes:
        code.excerpt_count = CodedReference.query.filter_by(code_id=code.id).count()
        code.excerpts = []  # Load on demand via API

    return render_template(
        "project/codes.html",
        project=project,
        codes=codes,
        active_page="codes",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/tasks")
@login_required
def project_tasks(project_id):
    """Task management (Kanban) page"""
    from app.models.researcher import ResearchTask

    project = get_project_or_404(project_id)

    tasks_todo = ResearchTask.query.filter_by(
        project_id=project.id, status="todo"
    ).all()
    tasks_in_progress = ResearchTask.query.filter_by(
        project_id=project.id, status="in_progress"
    ).all()
    tasks_done = ResearchTask.query.filter_by(
        project_id=project.id, status="done"
    ).all()

    return render_template(
        "project/tasks.html",
        project=project,
        tasks_todo=tasks_todo,
        tasks_in_progress=tasks_in_progress,
        tasks_done=tasks_done,
        active_page="tasks",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/report")
@login_required
def project_report(project_id):
    """Report builder page"""
    project = get_project_or_404(project_id)
    report = ResearchReportDraft.query.filter_by(project_id=project.id).first()
    return render_template(
        "project/report.html",
        project=project,
        report=report,
        active_page="report",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route(
    "/api/projects/<int:project_id>/report/draft", methods=["GET", "PUT"]
)
@login_required
def report_draft_api(project_id):
    """Load or save the current report draft for a project."""
    project = get_project_or_404(project_id)
    draft = ResearchReportDraft.query.filter_by(project_id=project.id).first()

    if request.method == "GET":
        if not draft:
            return jsonify(
                {
                    "draft": {
                        "title": project.name or "Untitled Report",
                        "html_content": _default_report_html(),
                        "is_new": True,
                    }
                }
            )
        return jsonify({"draft": draft.to_dict()})

    data = request.get_json(force=True) or {}
    html_content = (data.get("html_content") or "").strip()
    title = (data.get("title") or "").strip() or (project.name or "Untitled Report")

    if not html_content:
        return jsonify({"error": "Add some report content before saving."}), 400

    if draft is None:
        draft = ResearchReportDraft(project_id=project.id)
        db.session.add(draft)

    draft.title = title
    draft.html_content = html_content
    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Failed to save draft: {exc}"}), 500
    return jsonify(
        {
            "message": "Draft saved.",
            "draft": draft.to_dict(),
        }
    )


@dashboard_bp.route("/api/projects/<int:project_id>/write-section", methods=["POST"])
@login_required
def write_section_api(project_id):
    """Generate a report section in plain language from a user prompt."""
    from app.models.researcher import ExtractionSchema, Reference

    project = get_project_or_404(project_id)
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Describe what you want this section to cover."}), 400

    document_count = ResearcherDocument.query.filter_by(project_id=project.id).count()
    code_count = Code.query.filter_by(project_id=project.id).count()
    extraction_count = ExtractionSchema.query.filter_by(project_id=project.id).count()
    reference_count = Reference.query.filter_by(project_id=project.id).count()

    if beep_ai_client.is_configured():
        context_bits = [
            f"Project name: {project.name}",
            f"Documents available: {document_count}",
            f"Codes available: {code_count}",
            f"Data tables available: {extraction_count}",
            f"References available: {reference_count}",
        ]
        if project.custom_instructions:
            context_bits.append(
                f"Project writing instructions: {project.custom_instructions}"
            )

        grounded_context = build_project_grounded_context(
            project,
            prompt,
            max_results=4,
            max_chars_per_result=320,
        )
        if grounded_context.get("context_text"):
            context_bits.append(grounded_context["context_text"])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research writing assistant for non-technical users. "
                    "Write clear, well-structured report prose in plain, professional language. "
                    "Do not mention AI systems, retrieval, prompts, or internal tools. "
                    "Return only the requested section text."
                ),
            },
            {
                "role": "user",
                "content": (
                    "\n".join(context_bits)
                    + "\n\nWrite a report section based on this request:\n"
                    + prompt
                ),
            },
        ]
        ok, result = beep_ai_client.chat_reply(
            messages,
            temperature=resolve_project_generation_temperature(project),
        )
        if ok:
            return jsonify(
                {
                    "text": (result or "").strip(),
                    "method": "llm",
                    "message": "A draft section is ready.",
                    "supporting_sources": merge_supporting_sources(
                        [], grounded_context
                    ),
                }
            )

    fallback_text = (
        "Suggested section outline:\n\n"
        f"- Focus: {prompt}\n"
        f"- Project files available: {document_count}\n"
        f"- Saved codes available: {code_count}\n"
        f"- Saved data tables available: {extraction_count}\n"
        f"- Saved references available: {reference_count}\n\n"
        "The writing assistant is not available right now, so this outline can help you draft the section manually."
    )
    return jsonify(
        {
            "text": fallback_text,
            "method": "fallback",
            "message": "A guided outline is ready.",
            "supporting_sources": [],
        }
    )


@dashboard_bp.route("/projects/<int:project_id>/settings")
@login_required
def project_settings(project_id):
    """Project settings page"""
    from app.models.researcher import ResearcherDocument

    project = get_project_or_404(project_id)
    document_count = ResearcherDocument.query.filter_by(project_id=project.id).count()

    # Calculate storage used
    total_size = (
        db.session.query(func.sum(ResearcherDocument.file_size))
        .filter_by(project_id=project.id)
        .scalar()
        or 0
    )
    storage_used_formatted = _format_file_size(total_size)
    code_count = Code.query.filter_by(project_id=project.id).count()
    task_count = ResearchTask.query.filter_by(project_id=project.id).count()

    return render_template(
        "project/settings.html",
        project=project,
        document_count=document_count,
        code_count=code_count,
        task_count=task_count,
        storage_used_formatted=storage_used_formatted,
        active_page="settings",
        base_template=_base_template(),
    )


def _current_user_role():
    """Best-effort role extraction for middleware scope context."""
    role = getattr(current_user, "role", None)
    if role is None:
        role = getattr(current_user, "user_role", None)
    if role is None and hasattr(current_user, "is_admin"):
        return "admin" if current_user.is_admin else "user"
    return str(role) if role is not None else "user"


@dashboard_bp.route("/agent-plans")
@login_required
def agent_plans():
    """Non-technical UI for creating/running/approving AI agent plans."""
    from app.services.beep_ai_client import list_agent_sessions

    sessions = []
    load_error = None
    ok, result = list_agent_sessions(limit=20)
    if ok and isinstance(result, dict):
        sessions = result.get("sessions") or []
    elif ok and isinstance(result, list):
        sessions = result
    else:
        load_error = result

    return render_template(
        "agent_plans.html",
        sessions=sessions,
        load_error=load_error,
        base_template=_base_template(),
    )


@dashboard_bp.route("/api/agent-plans/list")
@login_required
def api_agent_plans_list():
    from app.services.beep_ai_client import list_agent_sessions

    limit = request.args.get("limit", type=int) or 20
    ok, result = list_agent_sessions(limit=max(1, limit))
    if not ok:
        return jsonify({"success": False, "error": result}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "sessions": result}
    )


@dashboard_bp.route("/api/agent-plans/create", methods=["POST"])
@login_required
def api_agent_plans_create():
    from app.services.beep_ai_client import create_agent_plan

    data = request.get_json(silent=True) or {}
    objective = (data.get("objective") or "").strip()
    if not objective:
        return jsonify({"success": False, "error": "objective is required"}), 400

    context = data.get("context") if isinstance(data.get("context"), dict) else {}
    project_id = data.get("project_id")
    if project_id:
        project = ResearchProject.query.filter_by(id=project_id).first()
        if project:
            context.setdefault("project_id", project.id)
            context.setdefault("project_name", project.name)
            if project.collection_id:
                context.setdefault("collection_id", project.collection_id)
            if project.tenant_id:
                context.setdefault("tenant_id", project.tenant_id)

    ok, result = create_agent_plan(
        objective=objective,
        context=context or None,
        user_id=str(current_user.id),
        user_role=_current_user_role(),
    )
    if not ok:
        return jsonify({"success": False, "error": result}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "data": result}
    )


@dashboard_bp.route("/api/agent-plans/<session_id>/execute", methods=["POST"])
@login_required
def api_agent_plans_execute(session_id):
    from app.services.beep_ai_client import execute_agent_plan

    data = request.get_json(silent=True) or {}
    max_iterations = data.get("max_iterations")
    timeout_seconds = data.get("timeout_seconds")

    ok, result = execute_agent_plan(
        session_id=session_id,
        max_iterations=max_iterations,
        timeout_seconds=timeout_seconds,
        user_id=str(current_user.id),
        user_role=_current_user_role(),
    )
    if not ok:
        return jsonify({"success": False, "error": result}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "data": result}
    )


@dashboard_bp.route("/api/agent-plans/<session_id>/approve", methods=["POST"])
@login_required
def api_agent_plans_approve(session_id):
    from app.services.beep_ai_client import approve_agent_step

    data = request.get_json(silent=True) or {}
    approved = bool(data.get("approved", True))
    notes = (data.get("notes") or "").strip() or None

    ok, result = approve_agent_step(
        session_id=session_id,
        approved=approved,
        notes=notes,
        user_id=str(current_user.id),
        user_role=_current_user_role(),
    )
    if not ok:
        return jsonify({"success": False, "error": result}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "data": result}
    )


@dashboard_bp.route("/api/agent-plans/<session_id>/status")
@login_required
def api_agent_plans_status(session_id):
    from app.services.beep_ai_client import get_agent_session_status

    ok, result = get_agent_session_status(session_id)
    if not ok:
        return jsonify({"success": False, "error": result}), 502
    return jsonify(
        result if isinstance(result, dict) else {"success": True, "data": result}
    )


def _format_file_size(size_bytes):
    """Format file size in human-readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


@dashboard_bp.route("/projects/<int:project_id>/documents/<int:doc_id>")
@login_required
def document_viewer(project_id, doc_id):
    from app.models.researcher import ResearcherDocument, Code, CodedReference

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()
    codes = Code.query.filter_by(project_id=project.id).all()
    refs = CodedReference.query.filter_by(document_id=doc.id).all()
    reference_navigation = build_document_reference_navigation(
        project,
        doc,
        highlighted_reference_id=request.args.get("reference_id", type=int),
    )
    return render_template(
        "document_viewer.html",
        project=project,
        doc=doc,
        codes=codes,
        refs=refs,
        linked_document_references=reference_navigation["linked_references"],
        active_document_reference=reference_navigation["active_reference"],
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/documents/<int:doc_id>/download")
@login_required
def document_download(project_id, doc_id):
    from app.models.researcher import ResearcherDocument
    import os
    from flask import send_file, abort

    project = get_project_or_404(project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()
    if not doc.file_path or not os.path.exists(doc.file_path):
        abort(404)
    return send_file(
        doc.file_path,
        as_attachment=True,
        download_name=doc.filename,
    )


@dashboard_bp.route("/projects/<int:project_id>/map")
@login_required
def document_map(project_id):
    project = get_project_or_404(project_id)
    return render_template(
        "project/document_map.html",
        project=project,
        active_page="map",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


def _ref_meta(r):
    from app.models.researcher import ResearcherDocument

    doc = get_entity(ResearcherDocument, r.document_id)
    snippet = ""
    if doc and doc.text_content:
        text = doc.text_content
        start = max(0, r.start_offset - 15)
        end = min(len(text), r.end_offset + 15)
        snippet = text[start:end].replace("\n", " ")
    return {
        "id": r.id,
        "document_id": r.document_id,
        "start_offset": r.start_offset,
        "end_offset": r.end_offset,
        "filename": doc.filename if doc else "?",
        "snippet": snippet,
    }


@dashboard_bp.route("/projects/<int:project_id>/chat")
@login_required
def chat_page(project_id):
    from flask import redirect, url_for

    get_project_or_404(project_id)
    return redirect(
        url_for("researcher.project_overview", project_id=project_id, openChat=1)
    )


@dashboard_bp.route("/projects/<int:project_id>/stats")
@login_required
def stats_page(project_id):
    from app.models.researcher import ResearcherDataSource

    project = get_project_or_404(project_id)
    sources = ResearcherDataSource.query.filter_by(project_id=project.id).all()
    return render_template(
        "project/stats.html",
        project=project,
        sources=sources,
        active_page="stats",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/data")
@login_required
def data_page(project_id):
    from app.models.researcher import ResearcherDataSource, SavedChart

    project = get_project_or_404(project_id)
    sources = ResearcherDataSource.query.filter_by(project_id=project.id).all()
    charts = SavedChart.query.filter_by(project_id=project.id).all()
    counts = _project_sidebar_counts(project.id)
    return render_template(
        "project/data.html",
        project=project,
        sources=sources,
        charts=charts,
        active_page="data",
        document_count=counts["document_count"],
        code_count=counts["code_count"],
        task_count=counts["task_count"],
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/extraction")
@login_required
def extraction_page(project_id):
    from app.models.researcher import ExtractionSchema
    from app.services.package_manager_service import check_optional_feature

    project = get_project_or_404(project_id)
    schemas = ExtractionSchema.query.filter_by(project_id=project.id).all()
    packages = {
        "docling_extraction": check_optional_feature("docling_extraction").get(
            "installed", False
        ),
    }
    return render_template(
        "project/extraction.html",
        project=project,
        schemas=schemas,
        packages=packages,
        active_page="extraction",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/report/share")
@login_required
def report_share_page(project_id):
    """Dedicated child page for Emailing and Exporting (Secure PDF, Word, etc)."""
    project = get_project_or_404(project_id)
    return render_template(
        "project/report_share.html",
        project=project,
        active_page="report",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/report/email", methods=["POST"])
@login_required
def email_report_api(project_id):
    """API endpoint to send the report HTML via email."""
    from app.services.email_service import send_email, is_configured

    project = get_project_or_404(project_id)
    data = request.get_json(silent=True) or {}

    to_email = data.get("email")
    subject = data.get("subject") or f"Research Report: {project.name}"
    content = data.get("content")

    if not is_configured():
        return jsonify(
            {"success": False, "error": "Server email (SMTP) is not configured."}
        ), 500

    if not to_email or not content:
        return jsonify(
            {
                "success": False,
                "error": "Email address and report content are required.",
            }
        ), 400

    # Send the email
    html_body = f"""
    <html>
        <head><style>body {{ font-family: sans-serif; line-height: 1.6; color: #333; }}</style></head>
        <body>
            <h2 style="color: #2563eb;">{project.name}</h2>
            <hr/>
            {content}
            <br><hr/><small>Sent directly from Beep.AI.Researcher</small>
        </body>
    </html>
    """

    success, error_msg = send_email(subject, html_body, [to_email])

    if success:
        return jsonify({"success": True, "message": "Report emailed successfully."})
    else:
        return jsonify(
            {"success": False, "error": error_msg or "Failed to send email."}
        ), 500


@dashboard_bp.route("/projects/<int:project_id>/report/export-pdf", methods=["POST"])
@login_required
def export_pdf_api(project_id):
    """API endpoint to generate a Secure PDF from the report HTML."""
    import io
    from flask import send_file

    try:
        from xhtml2pdf import pisa
    except ImportError:
        return jsonify(
            {"error": "PDF generation is currently unavailable. Install xhtml2pdf."}
        ), 500

    project = get_project_or_404(project_id)
    html_content = request.form.get("html_content") or ""

    # xhtml2pdf uses slightly different CSS for print layouts
    full_html = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset="utf-8">
            <title>Research Report - {project.name}</title>
            <style>
                @page {{
                    size: a4 portrait;
                    @frame header_frame {{
                        -pdf-frame-content: header_content;
                        left: 50pt; width: 512pt; top: 50pt; height: 40pt;
                    }}
                    @frame content_frame {{
                        left: 50pt; width: 512pt; top: 90pt; height: 632pt;
                    }}
                    @frame footer_frame {{
                        -pdf-frame-content: footer_content;
                        left: 50pt; width: 512pt; top: 772pt; height: 20pt;
                    }}
                }}
                body {{ font-family: Helvetica, sans-serif; font-size: 12pt; line-height: 1.5; color: #000; }}
                h1, h2, h3 {{ color: #1a365d; }}
                h1 {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }}
                blockquote {{ border-left: 4px solid #cbd5e1; margin-left: 0; padding-left: 1rem; color: #475569; font-style: italic; }}
            </style>
        </head>
        <body>
            <div id="header_content">
                <strong>{project.name}</strong> - Research Report
            </div>
            
            <div id="footer_content" style="text-align: right; color: #94a3b8; font-size: 9pt;">
                Securely Generated by Beep.AI.Researcher // Page <pdf:pagenumber>
            </div>
            
            <div>
                {html_content}
            </div>
        </body>
    </html>
    """

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(full_html, dest=buffer)

    if pisa_status.err:
        return jsonify({"error": "Failed to generate PDF document."}), 500

    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Report_{project.name.replace(' ', '_')}.pdf",
    )


@dashboard_bp.route("/projects/<int:project_id>/members")
@login_required
def members_page(project_id):
    from app.models.core import User
    from app.models.researcher import ProjectMember

    project = get_project_or_404(project_id)
    members = ProjectMember.query.filter_by(project_id=project.id).all()
    owner = get_entity(User, project.owner_id)
    users = (
        User.query.filter(User.is_active, User.id != project.owner_id)
        .order_by(User.username)
        .all()
    )
    return render_template(
        "members.html",
        project=project,
        members=members,
        owner=owner,
        users=users,
        active_page="members",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/matrix")
@login_required
def matrix_page(project_id):
    project = get_project_or_404(project_id)
    return render_template(
        "project/matrix.html",
        project=project,
        active_page="matrix",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/flashcards")
@login_required
def flashcards_page(project_id):
    project = get_project_or_404(project_id)
    return render_template(
        "project/flashcards.html",
        project=project,
        active_page="flashcards",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/quizzes")
@login_required
def quizzes_page(project_id):
    project = get_project_or_404(project_id)
    return render_template(
        "project/quizzes.html",
        project=project,
        active_page="quizzes",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/quizzes/<int:quiz_id>/take")
@login_required
def take_quiz_page(project_id, quiz_id):
    from app.models.researcher import Quiz

    project = get_project_or_404(project_id)
    quiz = Quiz.query.filter_by(project_id=project.id, id=quiz_id).first_or_404()
    return render_template(
        "project/take_quiz.html",
        project=project,
        quiz=quiz,
        active_page="quizzes",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
        embed=_embed(),
    )


@dashboard_bp.route("/projects/<int:project_id>/scheduled-reports")
@login_required
def scheduled_reports_page(project_id):
    from app.models.researcher import ScheduledReport

    project = get_project_or_404(project_id)
    reports = ScheduledReport.query.filter_by(project_id=project.id).all()
    return render_template(
        "project/scheduled_reports.html",
        project=project,
        reports=reports,
        active_page="reports",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/retention")
@login_required
def retention_page(project_id):
    project = get_project_or_404(project_id)
    return render_template(
        "project/retention.html",
        project=project,
        active_page="retention",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/contradictions")
@login_required
def contradictions_page(project_id):
    project = get_project_or_404(project_id)
    return render_template(
        "project/contradictions.html",
        project=project,
        active_page="contradictions",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/projects/<int:project_id>/hallucination-audit")
@login_required
def hallucination_audit_page(project_id):
    """Hallucination audit dashboard page."""
    from app.models.researcher import HallucinationAuditLog
    from sqlalchemy import func

    project = get_project_or_404(project_id)
    total = HallucinationAuditLog.query.filter_by(project_id=project.id).count()
    flagged = HallucinationAuditLog.query.filter_by(
        project_id=project.id, flagged=True
    ).count()
    avg_score = (
        db.session.query(func.avg(HallucinationAuditLog.grounding_score))
        .filter(HallucinationAuditLog.project_id == project.id)
        .scalar()
    )
    recent = (
        HallucinationAuditLog.query.filter_by(project_id=project.id)
        .order_by(HallucinationAuditLog.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "project/hallucination_audit.html",
        project=project,
        total=total,
        flagged=flagged,
        avg_score=round(avg_score or 0, 2),
        recent=[r.to_dict() for r in recent],
        active_page="hallucination",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )


@dashboard_bp.route("/api/projects/<int:project_id>/hallucination-audit")
@login_required
def hallucination_audit_api(project_id):
    """JSON API for hallucination audit data."""
    from app.models.researcher import HallucinationAuditLog
    from sqlalchemy import func

    project = get_project_or_404(project_id)
    total = HallucinationAuditLog.query.filter_by(project_id=project.id).count()
    flagged = HallucinationAuditLog.query.filter_by(
        project_id=project.id, flagged=True
    ).count()
    avg_score = (
        db.session.query(func.avg(HallucinationAuditLog.grounding_score))
        .filter(HallucinationAuditLog.project_id == project.id)
        .scalar()
    )
    recent = (
        HallucinationAuditLog.query.filter_by(project_id=project.id)
        .order_by(HallucinationAuditLog.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify(
        {
            "total": total,
            "flagged": flagged,
            "avg_score": round(avg_score or 0, 2),
            "recent": [r.to_dict() for r in recent],
        }
    )


@dashboard_bp.route("/api/projects/<int:project_id>/document-activity")
@login_required
def document_activity_api(project_id):
    """Per-document activity counts: codes, extractions, flashcards."""
    project = get_project_or_404(project_id)
    docs = ResearcherDocument.query.filter_by(project_id=project.id).all()

    # Per-document code references
    code_counts = dict(
        db.session.query(CodedReference.document_id, func.count(CodedReference.id))
        .join(Code, CodedReference.code_id == Code.id)
        .filter(Code.project_id == project.id)
        .group_by(CodedReference.document_id)
        .all()
    )
    # Per-document extraction results
    extraction_counts = dict(
        db.session.query(ExtractionResult.document_id, func.count(ExtractionResult.id))
        .join(ExtractionSchema, ExtractionResult.schema_id == ExtractionSchema.id)
        .filter(ExtractionSchema.project_id == project.id)
        .group_by(ExtractionResult.document_id)
        .all()
    )
    # Per-document flashcards
    flashcard_counts = dict(
        db.session.query(Flashcard.document_id, func.count(Flashcard.id))
        .filter(Flashcard.project_id == project.id)
        .group_by(Flashcard.document_id)
        .all()
    )

    result = {}
    for doc in docs:
        result[str(doc.id)] = {
            "codes": code_counts.get(doc.id, 0),
            "extractions": extraction_counts.get(doc.id, 0),
            "flashcards": flashcard_counts.get(doc.id, 0),
        }
    return jsonify(result)


@dashboard_bp.route("/api/projects/<int:project_id>/suggest-tasks", methods=["POST"])
@login_required
def suggest_tasks_api(project_id):
    """AI-powered task suggestions based on project documents."""
    project = get_project_or_404(project_id)
    try:
        from app.services.llm_manager import llm_manager

        docs = (
            ResearcherDocument.query.filter_by(project_id=project.id, status="ready")
            .limit(5)
            .all()
        )
        doc_names = ", ".join([d.name for d in docs]) if docs else "No documents yet"
        prompt = (
            f"You are a research assistant. For a project named '{project.name}' "
            f"with documents: {doc_names}, suggest 5 focused research tasks. "
            f"Return a JSON array of objects with keys: title, description, priority (low/medium/high)."
        )
        raw = llm_manager.generate(prompt, max_tokens=512)
        import json

        # Extract JSON array from response
        start = raw.find("[")
        end = raw.rfind("]") + 1
        suggestions = json.loads(raw[start:end]) if start != -1 else []
        return jsonify({"suggestions": suggestions[:5]})
    except Exception as e:
        return jsonify({"error": str(e), "suggestions": []}), 500


@dashboard_bp.route("/api/projects/<int:project_id>/report/append", methods=["POST"])
@login_required
def report_append_api(project_id):
    """Queue an AI answer block to be inserted into the report editor.
    The content is echoed back so the client can write it to localStorage
    for the report page to pick up on next load."""
    project = get_project_or_404(project_id)
    data = request.get_json(force=True) or {}
    content = (data.get("content") or "").strip()
    sources = data.get("sources") or []

    if not content:
        return jsonify({"error": "content is required"}), 400

    return jsonify(
        {
            "status": "queued",
            "content": content,
            "sources": sources,
            "storage_key": f"report_pending_{project.id}",
        }
    )


@dashboard_bp.route("/projects/<int:project_id>/references")
@login_required
def project_references_page(project_id):
    """Project-scoped references page with DOI tooltip and Report integration."""
    from app.models.researcher import ResearcherDocument
    from app.services.reference_bibliography_service import (
        get_bibliography_style_options,
    )

    project = get_project_or_404(project_id)
    library_view = build_project_citation_library(
        project,
        collection=request.args.get("collection"),
        tag=request.args.get("tag"),
        query=request.args.get("q"),
    )
    documents = (
        ResearcherDocument.query.filter_by(project_id=project.id)
        .order_by(ResearcherDocument.filename)
        .all()
    )
    return render_template(
        "project/references.html",
        project=project,
        references=library_view["references"],
        reference_collections=library_view["collections"],
        reference_tags=library_view["tags"],
        reference_tags_by_id=library_view["reference_tags_by_id"],
        selected_reference_collection=library_view["selected_collection"],
        selected_reference_tag=library_view["selected_tag"],
        reference_search_query=library_view["search_query"],
        reference_result_count=library_view["result_count"],
        reference_has_active_filters=library_view["has_active_filters"],
        bibliography_style_options=get_bibliography_style_options(),
        documents=documents,
        active_page="references",
        **_project_sidebar_counts(project.id),
        base_template=_base_template(),
    )

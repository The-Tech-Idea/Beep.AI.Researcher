"""Beep.AI Middleware HTTP client — RAG, chat, token validation (config via config_manager).

This client connects to Beep.AI.Server middleware APIs and the canonical OpenAI chat route.
Middleware URL pattern: {beep_ai_server_url}/ai-middleware/api/...
Examples:
  - Middleware: http://localhost:5000/ai-middleware/api/health
  - Chat (canonical): http://localhost:5000/v1/chat/completions

Configuration:
    beep_ai_server_url: The main server URL (e.g., http://localhost:5000)
    beep_ai_server_token: API token for authentication

RAG scoping:
    Canonical RAG operations are scoped by the application token. Project,
    tenant, and user identifiers are sent as metadata labels or filters only.
"""
import json

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from typing import Optional, Dict, Any, List
from flask import session
from app.config_manager import config_manager
from app.services.project_rag_preferences_service import resolve_project_quality_mode

# AI Middleware prefix on main server
MIDDLEWARE_PREFIX = "/ai-middleware"


# =====================
# Scoping Context Helper
# =====================

def get_scope_context(project=None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Build metadata context for RAG operations.
    
    Args:
        project: ResearchProject instance (optional)
        user_id: Explicit user ID (optional, falls back to session)
    
    Returns:
        Dict with scoping parameters:
        - user_id: Current user ID metadata label
        - user_role: User's role metadata label in the project (if project provided)
        - project_id: Project ID (if project provided)
        - collection_id: RAG collection ID (if project has one)
        - tenant_id: Tenant ID (if project has one)
        - app_id: Application identifier
    """
    context = {
        'app_id': 'researcher',  # Identify this as the Researcher app
    }
    
    # Get user_id from session if not explicitly provided
    if user_id is None:
        user_id = session.get('user_id') if session else None
    
    if user_id:
        context['user_id'] = str(user_id)
    
    # Extract project-specific scoping
    if project:
        context['project_id'] = str(project.id)
        if project.collection_id:
            context['collection_id'] = project.collection_id
        if project.tenant_id:
            context['tenant_id'] = str(project.tenant_id)
        
        # Determine user role in project
        if user_id and hasattr(project, 'members'):
            for member in project.members:
                if member.user_id == user_id:
                    context['user_role'] = member.role
                    break
            else:
                # Check if user is owner
                if project.owner_id == user_id:
                    context['user_role'] = 'admin'
    
    return context


def build_scoped_collection_id(project) -> Optional[str]:
    """
    Build a scoped collection ID for a project.
    
    If project has a collection_id, use it directly.
    Otherwise, generate one based on project ID for auto-provisioning.
    
    Format: researcher_project_{project_id}
    """
    if project.collection_id:
        return project.collection_id
    return f"researcher_project_{project.id}"


def _server_root():
    """Get Beep.AI.Server root URL (without middleware suffix)."""
    server_url = config_manager.get_setting('beep_ai_server_url', env_var='BEEP_AI_SERVER_URL')
    if not server_url:
        return ''
    root = server_url.rstrip('/')
    if root.endswith(MIDDLEWARE_PREFIX):
        root = root[:-len(MIDDLEWARE_PREFIX)]
    return root

def _base_url():
    """Get AI Middleware base URL ({server}/ai-middleware)."""
    server_root = _server_root()
    if not server_root:
        return ''
    return f"{server_root}{MIDDLEWARE_PREFIX}"


def _api_token():
    return config_manager.get_setting('beep_ai_server_token', env_var='BEEP_AI_SERVER_TOKEN') or ''


def is_configured():
    """True if Beep.AI.Server URL and token are set."""
    return bool(_base_url() and _api_token() and HAS_REQUESTS)


def _headers(user_id: Optional[str] = None, correlation_id: Optional[str] = None):
    """Get authorization headers with optional user context and correlation ID."""
    import uuid as _uuid
    headers = {}
    token = _api_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if user_id:
        headers["X-User-ID"] = str(user_id)
    # Propagate or generate a correlation ID so Researcher→Server calls are traceable
    headers["X-Request-ID"] = correlation_id or str(_uuid.uuid4())
    return headers

def _extract_error_message(payload, status_code: int) -> str:
    """Normalize both middleware and OpenAI-style error payloads."""
    if isinstance(payload, dict):
        error_value = payload.get('error')
        if isinstance(error_value, dict):
            return error_value.get('message') or error_value.get('error') or str(error_value)
        if error_value:
            return str(error_value)
        if payload.get('message'):
            return str(payload.get('message'))
    return f"HTTP {status_code}"


def _get(endpoint, timeout=15, user_id: Optional[str] = None):
    """GET from Beep.AI.Server; returns (ok, data_or_error)."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    base = _base_url()
    if not base:
        return False, "Server URL not configured"
    url = f"{base}{endpoint}"
    headers = _headers(user_id)
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def _get_server(endpoint, timeout=15, user_id: Optional[str] = None):
    """GET from Beep.AI.Server root endpoints (e.g. /v1/health)."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    server_root = _server_root()
    if not server_root:
        return False, "Server URL not configured"
    url = f"{server_root}{endpoint}"
    headers = _headers(user_id)
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def _post(endpoint, json_data=None, timeout=30, user_id: Optional[str] = None):
    """POST to Beep.AI.Server; returns (ok, data_or_error)."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    base = _base_url()
    if not base:
        return False, "Server URL not configured"
    url = f"{base}{endpoint}"
    headers = _headers(user_id)
    try:
        r = requests.post(url, json=json_data or {}, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)

def _post_v1(endpoint, json_data=None, timeout=30, user_id: Optional[str] = None):
    """POST to Beep.AI.Server root endpoints (e.g. /v1/chat/completions)."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    server_root = _server_root()
    if not server_root:
        return False, "Server URL not configured"
    url = f"{server_root}{endpoint}"
    headers = _headers(user_id)
    try:
        r = requests.post(url, json=json_data or {}, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def _put_v1(endpoint, json_data=None, timeout=30, user_id: Optional[str] = None):
    """PUT to Beep.AI.Server root endpoints."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    server_root = _server_root()
    if not server_root:
        return False, "Server URL not configured"
    url = f"{server_root}{endpoint}"
    headers = _headers(user_id)
    try:
        r = requests.put(url, json=json_data or {}, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def _delete_v1(endpoint, timeout=30, user_id: Optional[str] = None):
    """DELETE to Beep.AI.Server root endpoints."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    server_root = _server_root()
    if not server_root:
        return False, "Server URL not configured"
    url = f"{server_root}{endpoint}"
    headers = _headers(user_id)
    try:
        r = requests.delete(url, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def _delete(endpoint, json_data=None, timeout=30):
    """DELETE to Beep.AI.Server; returns (ok, data_or_error)."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    base = _base_url()
    if not base:
        return False, "Server URL not configured"
    url = f"{base}{endpoint}"
    headers = _headers()
    try:
        r = requests.delete(url, json=json_data or {}, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def _put(endpoint, json_data=None, timeout=30):
    """PUT to Beep.AI.Server; returns (ok, data_or_error)."""
    if not HAS_REQUESTS:
        return False, "requests library not installed"
    base = _base_url()
    if not base:
        return False, "Server URL not configured"
    url = f"{base}{endpoint}"
    headers = _headers()
    try:
        r = requests.put(url, json=json_data or {}, headers=headers, timeout=timeout)
        out = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        if r.status_code >= 400:
            return False, _extract_error_message(out, r.status_code)
        return True, out
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to Beep.AI.Server"
    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


# =====================
# Health & Token Validation
# =====================

def check_health():
    """
    Check if AI Middleware is reachable and healthy.
    Returns (ok, status_dict_or_error).
    No token required.
    """
    if not _server_root():
        return False, "Beep.AI.Server URL not configured"

    last_error = "Health check failed"
    for getter, endpoint in (
        (_get, "/api/health"),
        (_get, "/api/operational-status"),
        (_get_server, "/v1/health"),
        (_get_server, "/health"),
    ):
        ok, result = getter(endpoint)
        if ok:
            return True, result
        last_error = result
    return False, last_error


def check_token():
    """
    Check if the configured API token is valid.
    Returns (ok, result_dict_or_error).
    
    Result dict contains:
        - valid: bool
        - server_status: str
        - user: dict (if valid) with user_id, username, scopes
        - error: str (if invalid)
    """
    if not _base_url():
        return False, "AI Middleware URL not configured"
    if not _api_token():
        return False, "API token not configured"
    return _get("/api/tokens/check")


def get_connection_status():
    """
    Get comprehensive connection status.
    Returns dict with:
        - configured: bool - URL and token are set
        - server_reachable: bool - server responds
        - token_valid: bool - token is accepted
        - user: dict - user info if authenticated
        - error: str - any error message
    """
    result = {
        'configured': is_configured(),
        'server_reachable': False,
        'token_valid': False,
        'user': None,
        'error': None
    }
    
    if not _base_url():
        result['error'] = "Middleware URL not configured"
        return result
    
    # Check health (server reachable)
    ok, health = check_health()
    if ok:
        result['server_reachable'] = True
    else:
        result['error'] = f"Server unreachable: {health}"
        return result
    
    # Check token
    if not _api_token():
        result['error'] = "API token not configured"
        return result
    
    ok, token_result = check_token()
    if ok and token_result.get('valid'):
        result['token_valid'] = True
        result['user'] = token_result.get('user')
    else:
        result['error'] = token_result.get('error') if ok else token_result
    
    return result


# =====================
# Agent Orchestration
# =====================

def create_agent_plan(
    objective: str,
    context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> tuple:
    """Create a new agent plan session."""
    payload: Dict[str, Any] = {"goal": objective, "objective": objective}
    if context:
        payload["context"] = context
    if user_id:
        payload["user_id"] = str(user_id)
    if user_role:
        payload["user_role"] = user_role
    return _post("/api/agent/plan", json_data=payload)


def execute_agent_plan(
    session_id: str,
    max_iterations: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> tuple:
    """Execute or resume an existing plan session."""
    payload: Dict[str, Any] = {"session_id": session_id}
    if max_iterations is not None:
        payload["max_iterations"] = max_iterations
    if timeout_seconds is not None:
        payload["timeout_seconds"] = timeout_seconds
    if user_id:
        payload["user_id"] = str(user_id)
    if user_role:
        payload["user_role"] = user_role
    return _post("/api/agent/execute", json_data=payload)


def approve_agent_step(
    session_id: str,
    approved: bool = True,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None
) -> tuple:
    """Approve or reject the current waiting step."""
    payload: Dict[str, Any] = {"session_id": session_id, "approved": bool(approved)}
    if notes:
        payload["notes"] = notes
    if user_id:
        payload["user_id"] = str(user_id)
    if user_role:
        payload["user_role"] = user_role
    return _post("/api/agent/approve", json_data=payload)


def get_agent_session_status(session_id: str) -> tuple:
    """Get the latest status for a plan session."""
    return _get(f"/api/agent/status/{session_id}")


def list_agent_sessions(limit: int = 20) -> tuple:
    """List recent plan sessions."""
    return _get(f"/api/agent/sessions?limit={max(1, int(limit))}")


# =====================
# IAM Agent Tool Policies
# =====================

def list_agent_tool_policies(application_id: int) -> tuple:
    """List per-tool policy rows for an application."""
    return _get(f"/api/iam/applications/{application_id}/agent-tool-policies")


def create_agent_tool_policy(
    application_id: int,
    tool_name: str,
    effect: str = "allow",
    scope: Optional[str] = None,
    is_enabled: bool = True
) -> tuple:
    """Create a per-tool allow/deny policy row."""
    payload: Dict[str, Any] = {
        "tool_name": tool_name,
        "effect": effect,
        "is_enabled": bool(is_enabled)
    }
    if scope:
        payload["scope"] = scope
    return _post(f"/api/iam/applications/{application_id}/agent-tool-policies", json_data=payload)


def update_agent_tool_policy(policy_id: int, updates: Dict[str, Any]) -> tuple:
    """Update an existing policy row."""
    return _put(f"/api/iam/agent-tool-policies/{policy_id}", json_data=updates)


def delete_agent_tool_policy(policy_id: int) -> tuple:
    """Delete a policy row."""
    return _delete(f"/api/iam/agent-tool-policies/{policy_id}")


# =====================
# RAG Operations
# =====================

def list_rag_collections(user_id: Optional[str] = None, include_public: bool = True):
    """
    GET list of RAG collections from Beep.AI.Server.
    
    user_id is accepted for caller convenience but is not sent as access context.
    
    Args:
        user_id: Optional app user metadata label; not used for access
        include_public: Include public collections (default True)
    
    Returns:
        (ok, list_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    endpoint = f"/v1/rag/collections?include_public={str(include_public).lower()}"
    ok, out = _get_server(endpoint)
    if not ok:
        return False, out
    colls = out.get('collections') if out.get('success') else []
    return True, colls if isinstance(colls, list) else []


def create_rag_collection(
    name: str,
    user_id: Optional[str] = None,
    *,
    description: str = "",
    is_public: bool = False,
    allowed_tiers: Optional[list] = None,
    embedding_model: Optional[str] = None,
    chunk_template_id: Optional[str] = None,
) -> tuple:
    """
    POST to create a new RAG collection on Beep.AI.Server.

    Returns:
        (ok, collection_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    payload: Dict[str, Any] = {
        "name": name,
        "description": description,
        "is_public": is_public,
        "app_id": "researcher",
    }
    metadata: Dict[str, Any] = {}
    if user_id:
        metadata["app_user_id"] = str(user_id)
        metadata["user_id"] = str(user_id)
    if allowed_tiers is not None:
        payload["allowed_tiers"] = allowed_tiers
    if embedding_model is not None:
        payload["embedding_model"] = embedding_model
    if chunk_template_id is not None:
        payload["chunk_template_id"] = chunk_template_id

    if metadata:
        payload["metadata"] = metadata
    ok, out = _post_v1("/v1/rag/collections", json_data=payload)
    if not ok:
        return False, out
    return True, out.get("collection") if out.get("success") else out


def get_collection_organization_profile(
    collection_id: str,
    user_id: Optional[str] = None,
    quality_mode: Optional[str] = None,
):
    """Get the effective chunking and metadata organization profile for a collection."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    endpoint = f"/v1/rag/collections/{collection_id}/organization-profile"
    if quality_mode:
        endpoint += f"?quality_mode={quality_mode}"
    ok, out = _get_server(endpoint)
    if not ok:
        return False, out
    return True, out.get('organization_profile') if out.get('success') else out


def update_collection_organization_profile(
    collection_id: str,
    organization_profile: Dict[str, Any],
    *,
    metadata_schema: Optional[Dict[str, Any]] = None,
    graph_extraction_profile_id: Optional[str] = None,
    user_id: Optional[str] = None,
    user_role: Optional[str] = None,
    quality_mode: Optional[str] = None,
    chunk_template_id: Optional[str] = None,
) -> tuple:
    """Persist chunking defaults and metadata schema for a collection."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    payload: Dict[str, Any] = {
        "organization_profile": organization_profile,
        "app_id": "researcher",
    }
    if metadata_schema is not None:
        payload["metadata_schema"] = metadata_schema
    if graph_extraction_profile_id is not None:
        payload["graph_extraction_profile_id"] = graph_extraction_profile_id
    if quality_mode:
        payload["quality_mode"] = quality_mode
    if chunk_template_id is not None:
        payload["chunk_template_id"] = chunk_template_id

    return _put_v1(f"/v1/rag/collections/{collection_id}/organization-profile", json_data=payload)


def get_collection_document_chunks(
    collection_id: str,
    document_id: str,
    *,
    user_id: Optional[str] = None,
    include_content: bool = False,
    preview_chars: Optional[int] = None,
):
    """Get scoped chunk previews for a collection document."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    endpoint = f"/v1/rag/documents/{document_id}/chunks"
    query_parts = []
    if include_content:
        query_parts.append("include_content=true")
    if preview_chars is not None:
        query_parts.append(f"preview_chars={int(preview_chars)}")
    if query_parts:
        endpoint = f"{endpoint}?{'&'.join(query_parts)}"
    query_parts.append(f"collection_id={collection_id}")
    endpoint = f"/v1/rag/documents/{document_id}/chunks?{'&'.join(query_parts)}"
    return _get_server(endpoint)


def get_collection_document_lineage(
    collection_id: str,
    document_id: str,
    *,
    user_id: Optional[str] = None,
):
    """Get lineage and chunking metadata for a collection document."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    endpoint = f"/v1/rag/documents/{document_id}/lineage?collection_id={collection_id}"
    return _get_server(endpoint)


def rag_query(query: str, collection_id: str, max_results: int = 5, 
              user_id: Optional[str] = None, user_role: Optional[str] = None,
              project_id: Optional[str] = None, tenant_id: Optional[str] = None,
              app_id: str = 'researcher', filters: Optional[Dict] = None,
              quality_mode: Optional[str] = None,
              rewrite_query: Optional[bool] = None,
              hybrid_search: Optional[bool] = None,
              rerank: Optional[bool] = None,
              return_citations: bool = True,
              grounded_only: bool = True) -> tuple:
    """
    Query application-scoped RAG collections with optional metadata filters.
    
    Args:
        query: Search query text
        collection_id: RAG collection to search
        max_results: Maximum results to return
        user_id: Optional app user metadata label for filters or auditing
        user_role: Optional app user role metadata label
        project_id: Project ID for scoping
        tenant_id: Tenant ID for multi-tenant scoping
        app_id: Application identifier
        filters: Additional metadata filters
    
    Returns:
        (ok, results_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    payload = {
        "query": query, 
        "collection_id": collection_id, 
        "collection_ids": [collection_id],
        "max_results": max_results,
        "app_id": app_id,
    }
    
    if project_id:
        payload["project_id"] = str(project_id)
        # Add project filter to scope results
        if not filters:
            filters = {}
        filters["project_id"] = str(project_id)
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    if filters:
        payload["filters"] = filters
    if quality_mode:
        payload["quality_mode"] = quality_mode
    if rewrite_query is not None:
        payload["rewrite_query"] = rewrite_query
    if hybrid_search is not None:
        payload["hybrid_search"] = hybrid_search
    if rerank is not None:
        payload["rerank"] = rerank
    payload["return_citations"] = return_citations
    payload["grounded_only"] = grounded_only
    
    return _post_v1("/v1/rag/query", json_data=payload)


def rag_add_documents(documents: List[Dict], collection_id: str, 
                      user_id: Optional[str] = None, user_role: Optional[str] = None,
                      user_email: Optional[str] = None,
                      project_id: Optional[str] = None, tenant_id: Optional[str] = None,
                      app_id: str = 'researcher',
                      quality_mode: Optional[str] = None) -> tuple:
    """
    Add documents to RAG collection with scoping metadata.
    
    Each document should include:
    - content: Document text
    - source: Source filename/URL
    - metadata: Additional metadata (will be enriched with scoping)
    
    Args:
        documents: List of document dicts
        collection_id: Target RAG collection
        user_id: Optional app user metadata label
        user_role: User's role
        project_id: Project ID (embedded in document metadata)
        tenant_id: Tenant ID (for multi-tenant)
        app_id: Application identifier
    
    Returns:
        (ok, result_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    # Enrich documents with scoping metadata
    enriched_docs = []
    for doc in documents:
        enriched = dict(doc)
        metadata = enriched.get('metadata', {})
        
        # Add scoping metadata to each document
        metadata['app_id'] = app_id
        if project_id:
            metadata['project_id'] = str(project_id)
        if tenant_id:
            metadata['tenant_id'] = str(tenant_id)
        if user_id:
            metadata['owner_id'] = str(user_id)
            metadata['app_user_id'] = str(user_id)
        if user_email:
            metadata['app_user_email'] = user_email
        if quality_mode:
            metadata['quality_mode'] = quality_mode
        metadata.setdefault('ingestion_method', 'api')
        
        enriched['metadata'] = metadata
        enriched_docs.append(enriched)
    
    created = []
    for document in enriched_docs:
        ok, out = _post_v1(
            "/v1/rag/documents",
            json_data=_rag_document_create_payload(document, collection_id),
            timeout=60,
        )
        if not ok:
            return False, out
        created.append(out)

    return True, {"success": True, "indexed_count": len(created), "documents": created}


def rag_remove_documents(document_ids: List[str], collection_id: str,
                         user_id: Optional[str] = None, user_role: Optional[str] = None,
                         project_id: Optional[str] = None) -> tuple:
    """
    Remove documents from an application-scoped RAG collection.
    
    Args:
        document_ids: List of document IDs to remove
        collection_id: RAG collection
        user_id: Optional app user metadata label; not used for access
        user_role: User's role
        project_id: Project scope (optional, for filtering)
    
    Returns:
        (ok, result_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    payload = {
        "document_ids": document_ids, 
        "collection_id": collection_id,
        "app_id": "researcher",
    }
    if project_id:
        payload["project_id"] = str(project_id)
    
    deleted = []
    for document_id in document_ids:
        ok, out = _delete_v1(f"/v1/rag/documents/{document_id}")
        if not ok:
            return False, out
        deleted.append(document_id)

    return True, {"success": True, "deleted_count": len(deleted), "deleted": deleted}


def _rag_document_create_payload(document: Dict[str, Any], collection_id: str) -> Dict[str, Any]:
    metadata = dict(document.get("metadata") or {})
    payload: Dict[str, Any] = {
        "collection_id": collection_id,
        "title": document.get("title") or document.get("source") or document.get("id") or document.get("document_id"),
        "content": document.get("content"),
        "metadata": metadata,
    }
    document_id = document.get("id") or document.get("document_id")
    if document_id:
        payload["id"] = document_id
    return payload


# =====================
# RAG Chunk Templates
# =====================

def list_chunk_templates(database_profile_id: Optional[str] = None) -> tuple:
    """
    List available RAG chunk templates.

    Args:
        database_profile_id: Filter templates scoped to a specific database profile.

    Returns:
        (ok, list_of_templates_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    endpoint = "/v1/rag/chunk-templates"
    if database_profile_id:
        endpoint += f"?database_profile_id={database_profile_id}"
    ok, out = _get_server(endpoint)
    if not ok:
        return False, out
    templates = out.get("templates") if isinstance(out, dict) else []
    return True, templates if isinstance(templates, list) else []


def list_graph_extraction_profile_options(database_profile_id: Optional[str] = None) -> tuple:
    """
    List graph extraction profile options available for external apps.

    Args:
        database_profile_id: Optional database scope filter.

    Returns:
        (ok, list_of_profiles_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    endpoint = "/api/rag/runtime/graph-extraction-profiles/options"
    if database_profile_id:
        endpoint += f"?database_profile_id={database_profile_id}"
    ok, out = _get(endpoint)
    if not ok:
        return False, out
    profiles = out.get("profiles") if isinstance(out, dict) else []
    return True, profiles if isinstance(profiles, list) else []


def get_chunk_template(template_id: str) -> tuple:
    """
    Get a single chunk template by ID, slug, or name.

    Returns:
        (ok, template_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    ok, out = _get_server(f"/v1/rag/chunk-templates/{template_id}")
    if not ok:
        return False, out
    return True, out.get("template", out)


def create_chunk_template(
    name: str,
    chunking_config: Dict[str, Any],
    *,
    slug: Optional[str] = None,
    description: str = "",
    is_default: bool = False,
    database_profile_id: Optional[str] = None,
) -> tuple:
    """
    Create a new chunk template on the server.

    Returns:
        (ok, template_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    payload: Dict[str, Any] = {
        "name": name,
        "chunking_config": chunking_config,
        "description": description,
        "is_default": is_default,
    }
    if slug is not None:
        payload["slug"] = slug
    if database_profile_id is not None:
        payload["database_profile_id"] = database_profile_id

    return _post_v1("/v1/rag/chunk-templates", json_data=payload)


def update_chunk_template(template_id: str, updates: Dict[str, Any]) -> tuple:
    """Update fields of an existing chunk template."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _put_v1(f"/v1/rag/chunk-templates/{template_id}", json_data=updates)


def delete_chunk_template(template_id: str) -> tuple:
    """Delete a chunk template by ID/slug/name."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _delete_v1(f"/v1/rag/chunk-templates/{template_id}")


def apply_chunk_template_to_collection(template_id: str, collection_id: str) -> tuple:
    """Apply a chunk template to a RAG collection."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _post_v1(f"/v1/rag/chunk-templates/{template_id}/apply/collection/{collection_id}")


def remove_chunk_template_from_collection(collection_id: str) -> tuple:
    """Remove any chunk template assignment from a RAG collection."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _delete_v1(f"/v1/rag/chunk-templates/collection/{collection_id}")


def apply_chunk_template_to_database_profile(template_id: str, profile_id: str) -> tuple:
    """Apply a chunk template to a database profile."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _post_v1(f"/v1/rag/chunk-templates/{template_id}/apply/database-profile/{profile_id}")


# =====================
# LLM / Chat Operations
# =====================

def _build_chat_payload(
    messages,
    model=None,
    user_id=None,
    user_role=None,
    temperature=None,
    max_tokens: Optional[int] = None,
):
    payload = {"messages": messages}
    if model:
        payload["model"] = model
    if user_id:
        payload["user_id"] = str(user_id)
    if user_role:
        payload["user_role"] = user_role
    if temperature is not None:
        payload["temperature"] = float(temperature)
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    execution_context = payload.get("execution_context")
    if not isinstance(execution_context, dict):
        execution_context = {}
    if user_id and "user_id" not in execution_context:
        execution_context["user_id"] = str(user_id)
    if user_role and "role_name" not in execution_context:
        execution_context["role_name"] = user_role
    if "application_id" not in execution_context:
        execution_context["application_id"] = "researcher"
    payload["execution_context"] = execution_context
    return payload


def _extract_chat_content(response_payload: Dict[str, Any]) -> str:
    """Extract assistant text from an OpenAI chat completion payload."""
    try:
        message = response_payload.get("choices", [{}])[0].get("message", {})
    except (AttributeError, IndexError, TypeError):
        return ""

    content = message.get("content", "")
    if isinstance(content, list):
        text_parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text") or ""))
            elif isinstance(item, str):
                text_parts.append(item)
        return "".join(text_parts).strip()
    return str(content or "").strip()


def _extract_json_payload(content: str):
    """Parse a JSON object or array from an LLM response."""
    text = str(content or "").strip()
    if not text:
        return False, "Empty chat completion response"

    candidates = [text]
    for fence_marker in ("```json", "```JSON", "```"):
        if fence_marker in text:
            parts = text.split(fence_marker)
            for part in parts[1:]:
                candidate = part.split("```", 1)[0].strip()
                if candidate:
                    candidates.append(candidate)

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start != -1 and object_end > object_start:
        candidates.append(text[object_start:object_end + 1].strip())

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start != -1 and array_end > array_start:
        candidates.append(text[array_start:array_end + 1].strip())

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return True, json.loads(candidate)
        except (TypeError, ValueError):
            continue

    return False, "Chat completion did not return valid JSON"


def _structured_chat_completion(
    messages,
    *,
    model=None,
    user_id=None,
    user_role=None,
    temperature: float = 0.0,
    max_tokens: int = 1200,
):
    """Run a JSON-oriented prompt through the supported OpenAI chat route."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    payload = _build_chat_payload(
        messages,
        model=model,
        user_id=user_id,
        user_role=user_role,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    ok, response_payload = _post_v1(
        "/v1/chat/completions",
        json_data=payload,
        timeout=60,
        user_id=str(user_id) if user_id else None,
    )
    if not ok:
        return False, response_payload

    ok, parsed = _extract_json_payload(_extract_chat_content(response_payload))
    if not ok:
        return False, parsed
    return True, parsed


def _coerce_rag_results(result: Any) -> List[Dict[str, Any]]:
    """Normalize RAG result payloads into a list of item dicts."""
    if isinstance(result, dict):
        items = result.get("results") or result.get("documents") or result.get("sources") or []
        return items if isinstance(items, list) else []
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    return []


def _coerce_result_document_id(item: Dict[str, Any]) -> Optional[str]:
    """Extract a stable document identifier from a RAG result item."""
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    document_id = (
        item.get("document_id")
        or metadata.get("document_id")
        or metadata.get("researcher_doc_id")
        or metadata.get("id")
    )
    if document_id in (None, ""):
        return None
    return str(document_id)


def chat(messages, model=None, user_id=None, user_role=None, temperature=None):
    """Chat completion via canonical OpenAI route; returns (ok, response_dict_or_error)."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    payload = _build_chat_payload(
        messages,
        model=model,
        user_id=user_id,
        user_role=user_role,
        temperature=temperature,
    )

    return _post_v1("/v1/chat/completions", json_data=payload, user_id=str(user_id) if user_id else None)


def get_embeddings(texts, model=None, user_id=None):
    """Call the canonical embeddings endpoint; returns (ok, vectors_or_error)."""
    if not texts:
        return True, []
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    payload = {"input": list(texts)}
    if model:
        payload["model"] = model

    ok, out = _post_v1("/v1/embeddings", json_data=payload, user_id=str(user_id) if user_id else None)
    if not ok:
        return False, out

    vectors = []
    for item in out.get("data", []) or []:
        embedding = item.get("embedding") if isinstance(item, dict) else None
        if isinstance(embedding, list):
            vectors.append(embedding)
    return True, vectors


def chat_reply(messages, model=None, user_id=None, user_role=None, temperature=None):
    """Chat and return assistant text; returns (ok, text_or_error)."""
    ok, out = chat(messages, model, user_id, user_role, temperature)
    if not ok:
        return False, out
    try:
        text = out.get("choices", [{}])[0].get("message", {}).get("content", "")
        return True, text or "(No reply)"
    except (IndexError, KeyError, TypeError):
        return False, "Unexpected response format"


# =====================
# Service Calls (Generic)
# =====================

def call_service(service_type, method, **kwargs):
    """
    Call any AI service through middleware.
    
    Args:
        service_type: llm, text_to_image, text_to_speech, speech_to_text, etc.
        method: generate, generate_image, synthesize, transcribe, etc.
        **kwargs: Service-specific parameters
    
    Returns:
        (ok, result_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _post(f"/api/services/{service_type}/{method}", json_data=kwargs)


def list_services():
    """List available AI services."""
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _get("/api/services")


# =====================
# Text-to-Image
# =====================

def generate_image(prompt, width=512, height=512, **kwargs):
    """Generate image from text prompt."""
    return call_service('text_to_image', 'generate_image', 
                       prompt=prompt, width=width, height=height, **kwargs)


# =====================
# Text-to-Speech
# =====================

def synthesize_speech(text, voice=None, **kwargs):
    """Convert text to speech."""
    params = {'text': text}
    if voice:
        params['voice'] = voice
    params.update(kwargs)
    return call_service('text_to_speech', 'synthesize', **params)


# =====================
# Speech-to-Text
# =====================

def transcribe_audio(audio_data, format='wav', **kwargs):
    """Transcribe audio to text."""
    params = {'audio_data': audio_data, 'format': format}
    params.update(kwargs)
    return call_service('speech_to_text', 'transcribe', **params)


# =====================
# Project-Scoped RAG Operations (Convenience Functions)
# =====================

def query_project_rag(project, query: str, max_results: int = 5,
                      user_id: Optional[int] = None,
                      quality_mode: Optional[str] = None,
                      rewrite_query: Optional[bool] = None,
                      hybrid_search: Optional[bool] = None,
                      rerank: Optional[bool] = None,
                      return_citations: bool = True,
                      grounded_only: bool = True,
                      return_full: bool = False) -> tuple:
    """
    Query RAG for a specific research project with automatic scoping.
    
    Args:
        project: ResearchProject model instance
        query: Search query text
        max_results: Maximum results to return
        user_id: User performing query (for access control)
    
    Returns:
        (ok, results_list_or_error)
    """
    collection_id = build_scoped_collection_id(project)
    if not collection_id:
        return False, "Project has no RAG collection configured"
    effective_quality_mode, _ = resolve_project_quality_mode(project, quality_mode)
    scope = get_scope_context(project, user_id)
    
    ok, result = rag_query(
        query=query,
        collection_id=collection_id,
        max_results=max_results,
        user_id=scope.get('user_id'),
        user_role=scope.get('user_role'),
        project_id=scope.get('project_id'),
        tenant_id=scope.get('tenant_id'),
        quality_mode=effective_quality_mode,
        rewrite_query=rewrite_query,
        hybrid_search=hybrid_search,
        rerank=rerank,
        return_citations=return_citations,
        grounded_only=grounded_only,
    )
    
    if not ok:
        return False, result
    
    if return_full and isinstance(result, dict):
        return True, result

    # Extract results list
    if isinstance(result, dict):
        docs = result.get('results') or result.get('documents') or []
        return True, docs
    
    return True, result if isinstance(result, list) else []


def add_document_to_project_rag(project, document_content: str, source: str,
                                 document_id: Optional[str] = None,
                                 user_id: Optional[int] = None,
                                 metadata: Optional[Dict] = None,
                                 quality_mode: Optional[str] = None) -> tuple:
    """
    Add a document to a project's RAG collection with proper scoping.
    
    Args:
        project: ResearchProject model instance
        document_content: Document text content
        source: Source filename or URL
        document_id: Optional document ID (generated if not provided)
        user_id: User adding the document
        metadata: Additional metadata to store
    
    Returns:
        (ok, result_dict_or_error)
    """
    import uuid
    
    collection_id = build_scoped_collection_id(project)
    if not collection_id:
        return False, "Project has no RAG collection"
    effective_quality_mode, _ = resolve_project_quality_mode(project, quality_mode)
    scope = get_scope_context(project, user_id)
    
    # Build document with metadata
    doc_metadata = metadata or {}
    doc_metadata['source'] = source
    doc_metadata['document_id'] = document_id or str(uuid.uuid4())
    
    documents = [{
        'content': document_content,
        'source': source,
        'document_id': doc_metadata['document_id'],
        'metadata': doc_metadata,
    }]
    
    return rag_add_documents(
        documents=documents,
        collection_id=collection_id,
        user_id=scope.get('user_id'),
        user_role=scope.get('user_role'),
        user_email=scope.get('user_email') if isinstance(scope, dict) else None,
        project_id=scope.get('project_id'),
        tenant_id=scope.get('tenant_id'),
        quality_mode=effective_quality_mode,
    )


def remove_document_from_project_rag(project, document_ids: List[str],
                                      user_id: Optional[int] = None) -> tuple:
    """
    Remove documents from a project's RAG collection.
    
    Args:
        project: ResearchProject model instance
        document_ids: List of document IDs to remove
        user_id: User requesting removal (for access check)
    
    Returns:
        (ok, result_dict_or_error)
    """
    collection_id = build_scoped_collection_id(project)
    if not collection_id:
        return False, "Project has no RAG collection"
    
    scope = get_scope_context(project, user_id)
    
    return rag_remove_documents(
        document_ids=document_ids,
        collection_id=collection_id,
        user_id=scope.get('user_id'),
        user_role=scope.get('user_role'),
        project_id=scope.get('project_id'),
    )


def sync_document_to_rag(project, researcher_doc, user_id: Optional[int] = None) -> tuple:
    """
    Sync a ResearcherDocument to the project's RAG collection.
    
    This is called after document upload to index the content for search.
    
    Args:
        project: ResearchProject model instance
        researcher_doc: ResearcherDocument model instance with text_content
        user_id: User who uploaded the document
    
    Returns:
        (ok, result_dict_or_error)
    """
    if not researcher_doc.text_content:
        return False, "Document has no text content to index"
    
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    metadata = {
        'researcher_doc_id': str(researcher_doc.id),
        'filename': researcher_doc.filename,
        'mime_type': researcher_doc.mime_type,
        'file_size': researcher_doc.file_size,
    }
    
    return add_document_to_project_rag(
        project=project,
        document_content=researcher_doc.text_content,
        source=researcher_doc.filename,
        document_id=f"researcher_doc_{researcher_doc.id}",
        user_id=user_id,
        metadata=metadata,
    )


# =====================
# App User Management
# =====================

def register_app_user(user_id: str, display_name: Optional[str] = None, 
                      email: Optional[str] = None, tier: Optional[str] = None,
                      role: str = 'user', metadata: Optional[Dict] = None) -> tuple:
    """
    Register an app user with the AI Server.
    
    Args:
        user_id: Unique user identifier within this app
        display_name: User's display name
        email: User's email address
        tier: Subscription tier (free, basic, pro, enterprise)
        role: User role (user, admin, guest)
        metadata: Additional user metadata
    
    Returns:
        (ok, user_info_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    payload = {"user_id": user_id, "role": role}
    if display_name:
        payload["display_name"] = display_name
    if email:
        payload["email"] = email
    if tier:
        payload["tier"] = tier
    if metadata:
        payload["metadata"] = metadata
    
    return _post("/api/app-users", json_data=payload)


def get_app_user(user_id: str) -> tuple:
    """
    Get app user information.
    
    Returns:
        (ok, user_info_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _get(f"/api/app-users/{user_id}")


def get_app_user_usage(user_id: str) -> tuple:
    """
    Get app user's current usage and quota status.
    
    Returns:
        (ok, usage_dict_or_error) with fields like:
        - rag_queries_today, rag_documents_count
        - llm_tokens_today, llm_requests_today
        - image_generations_today, etc.
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _get(f"/api/app-users/{user_id}/usage")


def update_app_user(user_id: str, display_name: Optional[str] = None,
                    email: Optional[str] = None, role: Optional[str] = None,
                    is_active: Optional[bool] = None, 
                    metadata: Optional[Dict] = None) -> tuple:
    """
    Update app user information.
    
    Returns:
        (ok, user_info_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    payload = {}
    if display_name is not None:
        payload["display_name"] = display_name
    if email is not None:
        payload["email"] = email
    if role is not None:
        payload["role"] = role
    if is_active is not None:
        payload["is_active"] = is_active
    if metadata is not None:
        payload["metadata"] = metadata
    
    return _post(f"/api/app-users/{user_id}", json_data=payload)


def set_app_user_tier(user_id: str, tier: str) -> tuple:
    """
    Change app user's subscription tier.
    
    Args:
        user_id: User identifier
        tier: New tier name (free, basic, pro, enterprise)
    
    Returns:
        (ok, result_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    return _post(f"/api/app-users/{user_id}/tier", json_data={"tier": tier})


def list_tiers() -> tuple:
    """
    List available subscription tiers.
    
    Returns:
        (ok, tiers_list_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    ok, out = _get("/api/tiers")
    if not ok:
        return False, out
    tiers = out.get('tiers') if out.get('success') else []
    return True, tiers if isinstance(tiers, list) else []


def check_quota(user_id: str, resource_type: str, amount: int = 1) -> tuple:
    """
    Check if user has quota for a resource.
    
    Args:
        user_id: User identifier
        resource_type: rag_queries, llm_requests, image_generations, etc.
        amount: Amount to check (default 1)
    
    Returns:
        (ok, quota_check_dict_or_error) with fields:
        - allowed: bool
        - quota: int or 'unlimited'
        - used: int
        - remaining: int or 'unlimited'
        - reason: str (if not allowed)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"
    
    # Get user usage and tier info to check locally
    ok, user = get_app_user(user_id)
    if not ok:
        return False, user
    
    ok, usage = get_app_user_usage(user_id)
    if not ok:
        return False, usage
    
    # Basic local check (server does authoritative check)
    return True, {
        'allowed': True,  # Server will enforce actual limits
        'user': user.get('user', {}),
        'usage': usage.get('usage', {})
    }


def ensure_app_user(user_id: str, display_name: Optional[str] = None,
                    email: Optional[str] = None) -> tuple:
    """
    Ensure an app user exists, creating if necessary.
    
    This is useful for auto-registering users on first API call.
    
    Returns:
        (ok, user_info_dict_or_error)
    """
    # Try to get existing user
    ok, result = get_app_user(user_id)
    if ok and result.get('success'):
        return True, result
    
    # User doesn't exist, register with default tier
    return register_app_user(user_id, display_name, email)


# =====================
# LLM Extraction
# =====================

def extract_structured(
    project,
    document_text: str,
    schema_fields: List[Dict[str, Any]],
    schema_name: Optional[str] = None,
    document_id: Optional[str] = None,
    user_id: Optional[int] = None,
    supporting_context: Optional[str] = None,
) -> tuple:
    """
    Run structured LLM extraction against a document using a field schema.

    Calls the supported /v1/chat/completions route on Beep.AI.Server.

    Args:
        project: ResearchProject model instance (for scoping).
        document_text: Raw text of the document to extract from.
        schema_fields: List of dicts with keys: name (str), description (str),
                       field_type (str, e.g. 'string'|'number'|'date'|'list'),
                       required (bool).
        schema_name: Human-readable name for the schema (optional).
        document_id: Researcher document ID for reference in metadata (optional).
        user_id: User triggering extraction.
        supporting_context: Optional grounded library evidence block for terminology
            alignment or disambiguation. The document text remains the primary source.

    Returns:
        (ok, result_dict_or_error)
        result_dict keys: extracted_fields (dict), confidence (float, 0-1),
                          model_used (str), tokens_used (int).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    field_lines = []
    for field in schema_fields:
        if not isinstance(field, dict):
            continue
        field_name = str(field.get("name") or "").strip()
        if not field_name:
            continue
        required_flag = "required" if field.get("required") else "optional"
        field_lines.append(
            f"- {field_name} ({field.get('field_type') or 'string'}, {required_flag}): "
            f"{field.get('description') or 'No description provided.'}"
        )

    schema_title = schema_name or "Research Extraction Schema"
    document_label = str(document_id) if document_id else "unknown"
    messages = [
        {
            "role": "system",
            "content": (
                "You extract structured data from research documents. "
                "Return only a single JSON object using the exact requested field names. "
                "Use null when a value is not present in the source text. "
                "Treat the document text as the primary source of truth. "
                "Use supporting library evidence only for terminology alignment or clarification."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Schema: {schema_title}\n"
                f"Project ID: {scope.get('project_id') or 'unknown'}\n"
                f"Document ID: {document_label}\n"
                f"Fields:\n" + "\n".join(field_lines) + "\n\n"
                f"Document text:\n{document_text}"
                + (
                    f"\n\nSupporting library evidence:\n{supporting_context}"
                    if supporting_context else ""
                )
            ),
        },
    ]

    ok, parsed = _structured_chat_completion(
        messages,
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        max_tokens=1400,
    )
    if not ok:
        return False, parsed
    if not isinstance(parsed, dict):
        return False, "Structured extraction response was not a JSON object"
    return True, {
        "success": True,
        "extracted_fields": parsed,
        "schema_name": schema_title,
        "document_id": document_label,
    }


# =====================
# Contradiction Detection
# =====================

def detect_contradictions(
    project,
    query: str,
    document_ids: Optional[List[str]] = None,
    max_sources: int = 10,
    user_id: Optional[int] = None,
) -> tuple:
    """
    Detect contradictions across sources for a given research question.

    Uses the supported Beep.AI.Server RAG query plus /v1/chat/completions routes.

    Args:
        project: ResearchProject model instance.
        query: Research question or claim to check.
        document_ids: Optional list of specific document IDs to constrain the check.
        max_sources: Maximum number of RAG results to feed the LLM.
        user_id: User triggering the check.

    Returns:
        (ok, result_dict_or_error)
        result_dict keys: contradictions (list of dicts with sources, claim_a, claim_b,
                          severity, explanation), total_sources_checked (int).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    collection_id = build_scoped_collection_id(project)
    target_document_ids = {str(doc_id) for doc_id in (document_ids or []) if doc_id not in (None, "")}

    ok, rag_result = rag_query(
        query=query,
        collection_id=collection_id,
        max_results=max_sources,
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        project_id=scope.get("project_id"),
        tenant_id=scope.get("tenant_id"),
        return_citations=True,
        grounded_only=False,
    )
    if not ok:
        return False, rag_result

    contexts = []
    for item in _coerce_rag_results(rag_result):
        doc_id = _coerce_result_document_id(item)
        if target_document_ids and doc_id not in target_document_ids:
            continue
        contexts.append(
            {
                "document_id": doc_id,
                "filename": item.get("source") or item.get("filename") or "",
                "score": item.get("score") or item.get("confidence"),
                "content": str(item.get("content") or item.get("snippet") or "")[:1200],
            }
        )
        if len(contexts) >= max_sources:
            break

    if len(contexts) < 2:
        return True, {"contradictions": [], "total_sources_checked": len(contexts)}

    messages = [
        {
            "role": "system",
            "content": (
                "You compare retrieved research passages and identify only direct contradictions. "
                "Return only JSON with keys contradictions and total_sources_checked."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Research question or claim: {query}\n\n"
                "Sources:\n"
                f"{json.dumps(contexts, ensure_ascii=True)}\n\n"
                "Return JSON in this form: "
                '{"contradictions":[{"claim_a":"","source_a":{"document_id":"","filename":""},'
                '"claim_b":"","source_b":{"document_id":"","filename":""},"severity":"low|medium|high",'
                '"explanation":""}],"total_sources_checked":0}.'
            ),
        },
    ]

    ok, parsed = _structured_chat_completion(
        messages,
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        max_tokens=1400,
    )
    if not ok:
        return False, parsed
    if not isinstance(parsed, dict):
        return False, "Contradiction detection response was not a JSON object"
    contradictions = parsed.get("contradictions")
    if not isinstance(contradictions, list):
        contradictions = []
    total_sources_checked = parsed.get("total_sources_checked")
    try:
        total_sources_checked = int(total_sources_checked)
    except (TypeError, ValueError):
        total_sources_checked = len(contexts)
    return True, {
        "contradictions": contradictions,
        "total_sources_checked": total_sources_checked,
    }


# =====================
# Citation Finder
# =====================

def find_citations_for_draft(
    project,
    draft_text: str,
    max_citations: int = 5,
    user_id: Optional[int] = None,
) -> tuple:
    """
    Find citation matches for a draft passage using semantic RAG search.

    Uses the supported AI.Server RAG query route to suggest citations.

    Args:
        project: ResearchProject model instance.
        draft_text: The passage or paragraph needing citations.
        max_citations: Maximum citations to return.
        user_id: User triggering citation search.

    Returns:
        (ok, result_dict_or_error)
        result_dict keys: citations (list of dicts with document_id, source,
                          snippet, relevance_score, suggested_inline_citation).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    collection_id = build_scoped_collection_id(project)

    ok, rag_result = rag_query(
        query=draft_text,
        collection_id=collection_id,
        max_results=max(max_citations * 2, max_citations),
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        project_id=scope.get("project_id"),
        tenant_id=scope.get("tenant_id"),
        return_citations=True,
        grounded_only=False,
    )
    if not ok:
        return False, rag_result

    citations = []
    seen_document_ids = set()
    for item in _coerce_rag_results(rag_result):
        document_id = _coerce_result_document_id(item)
        dedupe_key = document_id or f"source::{item.get('source') or item.get('filename') or ''}"
        if dedupe_key in seen_document_ids:
            continue
        seen_document_ids.add(dedupe_key)
        citations.append(
            {
                "document_id": document_id,
                "source": item.get("source") or item.get("filename") or "",
                "snippet": str(item.get("content") or item.get("snippet") or "")[:300],
                "relevance_score": item.get("score") or item.get("confidence") or item.get("relevance_score"),
                "suggested_inline_citation": "",
            }
        )
        if len(citations) >= max_citations:
            break

    return True, {"citations": citations}


# =====================
# PHI / PII Scanning & Redaction
# =====================

def scan_phi(
    project,
    text: str,
    sector: str = "medical",
    user_id: Optional[int] = None,
) -> tuple:
    """
    Scan text for Protected Health Information (PHI) or PII.

    Calls POST /api/tools/phi_scan on Beep.AI.Server.

    Args:
        project: ResearchProject model instance.
        text: Text to scan for PHI/PII.
        sector: Domain context - 'medical' | 'legal' | 'education'.
        user_id: User requesting the scan.

    Returns:
        (ok, result_dict_or_error)
        result_dict keys: phi_found (bool), entities (list of dicts with type,
                          value, start, end, confidence), risk_level (low/medium/high).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    payload: Dict[str, Any] = {
        "text": text,
        "sector": sector,
        "app_id": "researcher",
    }
    if scope.get("project_id"):
        payload["project_id"] = scope["project_id"]
    if scope.get("user_id"):
        payload["user_id"] = scope["user_id"]

    return _post("/api/tools/phi_scan", json_data=payload, timeout=30)


def redact_phi(
    project,
    text: str,
    sector: str = "medical",
    replacement_char: str = "[REDACTED]",
    user_id: Optional[int] = None,
) -> tuple:
    """
    Redact PHI/PII from text, replacing with placeholder tokens.

    Calls POST /api/tools/phi_redact on Beep.AI.Server.

    Args:
        project: ResearchProject model instance.
        text: Text containing PHI/PII to redact.
        sector: Domain context - 'medical' | 'legal' | 'education'.
        replacement_char: Placeholder for redacted content.
        user_id: User requesting redaction.

    Returns:
        (ok, result_dict_or_error)
        result_dict keys: redacted_text (str), entities_redacted (int),
                          entity_types (list of types found and removed).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    payload: Dict[str, Any] = {
        "text": text,
        "sector": sector,
        "replacement": replacement_char,
        "app_id": "researcher",
    }
    if scope.get("project_id"):
        payload["project_id"] = scope["project_id"]
    if scope.get("user_id"):
        payload["user_id"] = scope["user_id"]

    return _post("/api/tools/phi_redact", json_data=payload, timeout=30)


# =====================
# Collection Sector Policy
# =====================

def set_collection_sector_policy(
    project,
    sector: str,
    compliance_frameworks: Optional[List[str]] = None,
    user_id: Optional[int] = None,
) -> tuple:
    """
    Set sector-specific compliance policy for a project's RAG collection.

    Calls PUT /v1/rag/collections/{collection_id}/sector-policy on Beep.AI.Server.

    Args:
        project: ResearchProject model instance.
        sector: 'medical' | 'legal' | 'education' | 'real_estate' | 'government'.
        compliance_frameworks: List of applicable frameworks e.g. ['HIPAA', 'GDPR'].
        user_id: User setting the policy (must be admin/owner).

    Returns:
        (ok, result_dict_or_error)
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    collection_id = build_scoped_collection_id(project)

    payload: Dict[str, Any] = {
        "sector": sector,
        "app_id": "researcher",
    }
    if compliance_frameworks:
        payload["compliance_frameworks"] = compliance_frameworks
    if scope.get("user_id"):
        payload["user_id"] = scope["user_id"]

    return _put_v1(
        f"/v1/rag/collections/{collection_id}/sector-policy",
        json_data=payload,
        user_id=scope.get("user_id"),
    )


def get_collection_compliance_status(
    project,
    user_id: Optional[int] = None,
) -> tuple:
    """
    Get compliance status and policy details for a project's RAG collection.

    Calls GET /v1/rag/collections/{collection_id}/compliance-status on Beep.AI.Server.

    Args:
        project: ResearchProject model instance.
        user_id: User requesting the status.

    Returns:
        (ok, status_dict_or_error)
        status_dict keys: sector, compliance_frameworks, status (compliant/warning/violation),
                          violations (list), last_audit (datetime).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    collection_id = build_scoped_collection_id(project)
    return _get_server(f"/v1/rag/collections/{collection_id}/compliance-status", user_id=str(user_id) if user_id else None)


# =====================
# RAG with Provenance Context
# =====================

def query_with_context(
    project,
    query: str,
    max_results: int = 5,
    return_provenance: bool = True,
    context_window: int = 3,
    user_id: Optional[int] = None,
) -> tuple:
    """
    Query RAG with full provenance context — source passages, page refs, confidence.

    Uses the canonical /v1/rag/query route on Beep.AI.Server.

    Args:
        project: ResearchProject model instance.
        query: Semantic search query.
        max_results: Maximum matching passages to return.
        return_provenance: Include source document page/section references.
        context_window: Number of surrounding sentences to include per passage.
        user_id: User performing the query.

    Returns:
        (ok, result_dict_or_error)
        result_dict keys: results (list of dicts with content, source, document_id,
                          page, section, confidence, provenance), answer (str, LLM synthesised).
    """
    if not is_configured():
        return False, "Beep.AI.Server not configured"

    scope = get_scope_context(project, user_id)
    collection_id = build_scoped_collection_id(project)

    ok, result = rag_query(
        query=query,
        collection_id=collection_id,
        max_results=max_results,
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        project_id=scope.get("project_id"),
        tenant_id=scope.get("tenant_id"),
        return_citations=return_provenance,
        grounded_only=False,
    )
    if not ok:
        return False, result
    if isinstance(result, dict):
        if not isinstance(result.get("results"), list) and isinstance(result.get("documents"), list):
            result["results"] = result.get("documents")
        result.setdefault("return_provenance", bool(return_provenance))
        result.setdefault("context_window", int(context_window))
        return True, result
    if isinstance(result, list):
        return True, {
            "results": result,
            "return_provenance": bool(return_provenance),
            "context_window": int(context_window),
        }
    return False, "Unexpected RAG response format"


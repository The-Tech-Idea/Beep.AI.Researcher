"""Researcher-specific RAG chunk template management.

Provides researcher-optimised chunk template definitions and helpers for
applying them to project collections.

Researcher template slugs
--------------------------
researcher-academic-paper
    Proposition-based chunking for academic papers.  Breaks the text into
    atomic propositions (~80 tokens each) so that precise fact-level retrieval
    and citation attribution are reliable.

researcher-literature-review
    RAPTOR-tree chunking for literature reviews and survey documents.
    Builds a hierarchical summary tree so broad thematic queries retrieve
    relevant sections even when exact keywords differ.

researcher-technical-paper
    Parent/child hierarchical chunking for technical reports and engineering
    papers.  Index with small child chunks (~384 tokens) but retrieve together
    with their parent (~1 536 tokens) for full context.

researcher-quick-notes
    Compact fixed-size chunking for personal research notes, annotations and
    short memos where dense exact-match retrieval is more important than
    semantic coherence across chunks.
"""

from typing import Any, Dict, Optional, Tuple

from app.services import beep_ai_client as bac

# ---------------------------------------------------------------------------
# Researcher-specific template definitions
# ---------------------------------------------------------------------------

RESEARCHER_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "researcher-academic-paper": {
        "name": "Academic Paper (Researcher)",
        "slug": "researcher-academic-paper",
        "description": (
            "Proposition-based chunking for academic papers. "
            "Extracts atomic propositions (~80 tokens) for precise "
            "fact-level retrieval and citation attribution."
        ),
        "chunking_config": {
            "strategy": "proposition",
            "max_proposition_tokens": 80,
            "chunk_size": 400,
            "chunk_overlap": 40,
            "separator": "\n\n",
            "min_chunk_length": 30,
        },
    },
    "researcher-literature-review": {
        "name": "Literature Review (Researcher)",
        "slug": "researcher-literature-review",
        "description": (
            "RAPTOR-tree chunking for literature reviews and survey papers. "
            "Builds a hierarchical summary tree so broad thematic queries "
            "match relevant sections even when keywords differ."
        ),
        "chunking_config": {
            "strategy": "raptor_tree",
            "base_chunk_size": 512,
            "chunk_overlap": 50,
            "max_tree_depth": 3,
            "summary_model": "default",
        },
    },
    "researcher-technical-paper": {
        "name": "Technical Paper (Researcher)",
        "slug": "researcher-technical-paper",
        "description": (
            "Parent/child hierarchical chunking for technical reports and "
            "engineering papers. Small child chunks for precise retrieval, "
            "large parent chunks for full context."
        ),
        "chunking_config": {
            "strategy": "parent_child",
            "parent_chunk_size": 1536,
            "child_chunk_size": 384,
            "child_overlap": 40,
            "separator": "\n\n",
        },
    },
    "researcher-quick-notes": {
        "name": "Quick Notes (Researcher)",
        "slug": "researcher-quick-notes",
        "description": (
            "Compact fixed-size chunking for personal research notes, "
            "annotations and short memos where dense exact-match retrieval "
            "is more useful than wide semantic coverage."
        ),
        "chunking_config": {
            "strategy": "fixed_size",
            "chunk_size": 256,
            "chunk_overlap": 64,
            "separator": "\n",
        },
    },
}

# Map project types / purposes to the recommended researcher template slug.
_PROJECT_TYPE_TEMPLATE_MAP: Dict[str, str] = {
    "academic": "researcher-academic-paper",
    "paper": "researcher-academic-paper",
    "research": "researcher-academic-paper",
    "literature": "researcher-literature-review",
    "review": "researcher-literature-review",
    "survey": "researcher-literature-review",
    "technical": "researcher-technical-paper",
    "engineering": "researcher-technical-paper",
    "report": "researcher-technical-paper",
    "notes": "researcher-quick-notes",
    "annotations": "researcher-quick-notes",
    "memo": "researcher-quick-notes",
}

# Default when project type gives no match.
_DEFAULT_RESEARCHER_SLUG = "researcher-academic-paper"

_DOCUMENT_TYPE_TEMPLATE_CONTRACT: Dict[str, Dict[str, str]] = {
    "academic_paper": {
        "label": "Academic Paper",
        "template_slug": "researcher-academic-paper",
        "collection_family": "academic-papers",
        "description": "Journal papers, conference papers, and formal research manuscripts.",
    },
    "literature_review": {
        "label": "Literature Review",
        "template_slug": "researcher-literature-review",
        "collection_family": "literature-reviews",
        "description": "Surveys, review articles, and broad evidence summaries.",
    },
    "technical_report": {
        "label": "Technical Report",
        "template_slug": "researcher-technical-paper",
        "collection_family": "technical-reports",
        "description": "Engineering reports, whitepapers, and technical specifications.",
    },
    "research_notes": {
        "label": "Research Notes",
        "template_slug": "researcher-quick-notes",
        "collection_family": "research-notes",
        "description": "Short notes, annotations, excerpts, and working memos.",
    },
}


# ---------------------------------------------------------------------------
# Template provisioning
# ---------------------------------------------------------------------------

def ensure_researcher_templates() -> Dict[str, Any]:
    """Idempotently create all researcher-specific templates on the server.

    Templates whose slug already exists on the server are skipped.

    Returns:
        dict with keys ``created`` (list of slugs), ``skipped`` (list of slugs),
        ``errors`` (dict slug -> error message).
    """
    created, skipped, errors = [], [], {}

    for slug, spec in RESEARCHER_TEMPLATES.items():
        ok, out = bac.get_chunk_template(slug)
        if ok:
            skipped.append(slug)
            continue

        ok, result = bac.create_chunk_template(
            name=spec["name"],
            chunking_config=spec["chunking_config"],
            slug=slug,
            description=spec["description"],
            is_default=False,
        )
        if ok:
            created.append(slug)
        else:
            errors[slug] = str(result)

    return {"created": created, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Project collection helpers
# ---------------------------------------------------------------------------

def get_project_template(project) -> Tuple[bool, Any]:
    """Return the chunk template currently applied to a project's collection.

    Returns ``(True, template_dict)`` or ``(False, error_string)``.
    """
    collection_id = _collection_id(project)
    if not collection_id:
        return False, "Project is not linked to a document library"

    ok, templates = bac.list_chunk_templates()
    if not ok:
        return False, templates

    # The server returns all templates; the one applied to the collection
    # has the collection in its linked_collections list (server populates this).
    # A simpler approach: look for a template whose collection_id matches.
    for tpl in (templates or []):
        linked = tpl.get("linked_collection_ids") or []
        if collection_id in linked:
            return True, tpl

    return True, None  # no template is applied


def apply_template_to_project(
    project,
    template_id: str,
    *,
    user_id: Optional[int] = None,
) -> Tuple[bool, Any]:
    """Apply a chunk template (by ID, slug or name) to the project's collection.

    Returns ``(True, result_dict)`` or ``(False, error_string)``.
    """
    collection_id = _collection_id(project)
    if not collection_id:
        return False, "Project is not linked to a document library"

    return bac.apply_chunk_template_to_collection(template_id, collection_id)


def remove_template_from_project(project) -> Tuple[bool, Any]:
    """Remove any chunk template assignment from the project's collection.

    Returns ``(True, result_dict)`` or ``(False, error_string)``.
    """
    collection_id = _collection_id(project)
    if not collection_id:
        return False, "Project is not linked to a document library"

    return bac.remove_chunk_template_from_collection(collection_id)


def suggest_template_slug(project_type: Optional[str] = None) -> str:
    """Return the recommended researcher template slug for a given project type.

    ``project_type`` is matched case-insensitively against known keywords.
    Falls back to ``researcher-academic-paper`` when no match is found.
    """
    if not project_type:
        return _DEFAULT_RESEARCHER_SLUG

    key = project_type.strip().lower()
    return _PROJECT_TYPE_TEMPLATE_MAP.get(key, _DEFAULT_RESEARCHER_SLUG)


def get_document_type_template_contract() -> Dict[str, Any]:
    """Return a simple document-type to template mapping contract for Researcher."""
    return {
        "default_template_slug": _DEFAULT_RESEARCHER_SLUG,
        "document_types": [
            {
                "document_type": document_type,
                **definition,
            }
            for document_type, definition in _DOCUMENT_TYPE_TEMPLATE_CONTRACT.items()
        ],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collection_id(project) -> Optional[str]:
    """Extract collection_id from a project model, or generate the default."""
    cid = getattr(project, "collection_id", None)
    if cid:
        return str(cid)
    pid = getattr(project, "id", None)
    if pid is not None:
        return f"researcher_project_{pid}"
    return None

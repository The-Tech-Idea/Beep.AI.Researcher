"""Compatibility shim for document routes.

The canonical runtime implementation lives in the package-backed
``app.routes.documents`` module. This file remains only for source-path
compatibility checks and documentation references.
"""

from app.models.researcher import ResearchProject
from app.routes.documents import documents_bp
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404

__all__ = ["documents_bp"]

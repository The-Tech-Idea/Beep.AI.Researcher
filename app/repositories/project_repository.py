"""Project repository — data access for ResearchProject."""

from __future__ import annotations

from typing import List, Optional

from app.repositories.base import BaseRepository
from app.models.researcher.researcher_projects import ResearchProject


class ProjectRepository(BaseRepository[ResearchProject]):
    """Repository for ResearchProject CRUD and project-specific queries."""

    @property
    def model_class(self) -> type[ResearchProject]:
        return ResearchProject

    def get_by_owner(self, owner_id: int) -> List[ResearchProject]:
        """Get all projects owned by a user."""
        return self._session.query(ResearchProject).filter_by(owner_id=owner_id).all()

    def get_by_tenant(self, tenant_id: int) -> List[ResearchProject]:
        """Get all projects in a tenant."""
        return self._session.query(ResearchProject).filter_by(tenant_id=tenant_id).all()

    def get_user_accessible(self, user_id: int) -> List[ResearchProject]:
        """Get projects where user is owner OR member."""
        from app.models.researcher.researcher_projects import ProjectMember

        owned = self._session.query(ResearchProject).filter_by(owner_id=user_id).all()
        member_project_ids = (
            self._session.query(ProjectMember.project_id)
            .filter_by(user_id=user_id)
            .all()
        )
        member_ids = [row[0] for row in member_project_ids]
        if member_ids:
            members = (
                self._session.query(ResearchProject)
                .filter(ResearchProject.id.in_(member_ids))
                .all()
            )
            # Deduplicate by id
            seen = {p.id for p in owned}
            return owned + [m for m in members if m.id not in seen]
        return owned

    def get_by_collection(self, collection_id: str) -> List[ResearchProject]:
        """Get projects linked to a specific RAG collection."""
        return (
            self._session.query(ResearchProject)
            .filter_by(collection_id=collection_id)
            .all()
        )

"""Project service — business logic for project operations.

Uses ProjectRepository for data access. Never imports db directly.
"""

from __future__ import annotations

from typing import List, Optional

from app.repositories.project_repository import ProjectRepository
from app.models.researcher.researcher_projects import ResearchProject


class ProjectService:
    """Business logic for projects.

    All data access goes through ProjectRepository.
    This class handles authorization checks, validation, and orchestration.
    """

    def __init__(self, repo: ProjectRepository):
        self._repo = repo

    def get_project(self, project_id: int, user_id: int) -> Optional[ResearchProject]:
        """Get a project only if the user has access (owner or member)."""
        projects = self._repo.get_user_accessible(user_id)
        for p in projects:
            if p.id == project_id:
                return p
        return None

    def list_user_projects(self, user_id: int) -> List[ResearchProject]:
        """List all projects accessible to a user."""
        return self._repo.get_user_accessible(user_id)

    def create_project(
        self,
        owner_id: int,
        name: str,
        description: str = "",
        tenant_id: Optional[int] = None,
    ) -> ResearchProject:
        """Create a new project. Returns the persisted entity."""
        project = ResearchProject(
            owner_id=owner_id,
            name=name,
            description=description,
            tenant_id=tenant_id,
        )
        self._repo.add(project)
        self._repo.commit()
        return project

    def update_project(
        self,
        project_id: int,
        user_id: int,
        **changes,
    ) -> Optional[ResearchProject]:
        """Update a project if user has access. Allowed fields only."""
        project = self.get_project(project_id, user_id)
        if project is None:
            return None

        # Only allow safe fields to be updated
        allowed = {"name", "description", "collection_id", "status"}
        safe_changes = {k: v for k, v in changes.items() if k in allowed}

        if safe_changes:
            self._repo.update(project, **safe_changes)
            self._repo.commit()

        return project

    def delete_project(self, project_id: int, user_id: int) -> bool:
        """Delete a project if user is the owner. Returns success."""
        project = self._repo.get(project_id)
        if project is None or project.owner_id != user_id:
            return False

        self._repo.delete(project)
        self._repo.commit()
        return True

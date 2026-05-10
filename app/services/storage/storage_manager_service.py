"""Storage backend health and consistency helpers for admin UI."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func

from app.database import db


@dataclass(frozen=True)
class StorageHealth:
    """Storage backend health summary."""

    backend: str
    healthy: bool
    message: str
    capabilities: dict[str, bool]
    configured_root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "healthy": self.healthy,
            "message": self.message,
            "capabilities": self.capabilities,
            "configured_root": self.configured_root,
        }


@dataclass(frozen=True)
class StorageUsageSummary:
    """Storage usage derived from document records."""

    document_count: int
    total_bytes: int
    missing_objects: int
    checked_objects: int
    size_mismatches: int = 0


@dataclass(frozen=True)
class StorageConsistencyIssue:
    """One DB/storage inconsistency."""

    document_id: int
    filename: str
    project_id: int | None
    issue_type: str
    storage_key: str | None
    storage_reference: dict[str, str | None]
    expected_size: int | None = None
    actual_size: int | None = None
    message: str = ""


class StorageManagerService:
    """Admin-facing storage backend inspection service."""

    def backend_name(self) -> str:
        from app.config_manager import config_manager

        return config_manager.get("storage_backend", "local") or "local"

    def health(self) -> StorageHealth:
        from app.config_manager import config_manager
        from app.services.storage import StorageError, get_storage_backend

        backend_name = self.backend_name()
        capabilities = {
            "save": True,
            "load": True,
            "delete": True,
            "exists": True,
            "file_size": True,
            "archive": False,
        }
        configured_root = None
        try:
            backend = get_storage_backend()
            if backend_name == "local":
                configured_root = str(config_manager.uploads_path)
                Path(configured_root).mkdir(parents=True, exist_ok=True)
            return StorageHealth(
                backend=backend.backend_name,
                healthy=True,
                message="Storage backend is available.",
                capabilities=capabilities,
                configured_root=configured_root,
            )
        except StorageError as exc:
            return StorageHealth(
                backend=backend_name,
                healthy=False,
                message=str(exc),
                capabilities=capabilities,
                configured_root=configured_root,
            )
        except Exception as exc:
            return StorageHealth(
                backend=backend_name,
                healthy=False,
                message=f"Storage health check failed: {exc}",
                capabilities=capabilities,
                configured_root=configured_root,
            )

    def usage_summary(self, *, sample_limit: int = 100) -> StorageUsageSummary:
        from app.models.researcher import ResearcherDocument

        total_bytes = db.session.query(func.coalesce(func.sum(ResearcherDocument.file_size), 0)).scalar() or 0
        document_count = ResearcherDocument.query.count()
        scan = self.consistency_scan(limit=sample_limit)

        missing = sum(1 for issue in scan if issue.issue_type == "missing_object")
        size_mismatches = sum(1 for issue in scan if issue.issue_type == "size_mismatch")

        return StorageUsageSummary(
            document_count=document_count,
            total_bytes=int(total_bytes),
            missing_objects=missing,
            checked_objects=min(document_count, sample_limit),
            size_mismatches=size_mismatches,
        )

    def consistency_scan(self, *, limit: int = 250) -> list[StorageConsistencyIssue]:
        """Scan document DB records against active storage objects."""

        from app.models.researcher import ResearcherDocument
        from app.services.storage import get_storage_backend

        docs = (
            ResearcherDocument.query
            .order_by(ResearcherDocument.created_at.desc())
            .limit(limit)
            .all()
        )
        issues: list[StorageConsistencyIssue] = []
        try:
            backend = get_storage_backend()
        except Exception as exc:
            return [
                StorageConsistencyIssue(
                    document_id=doc.id,
                    filename=doc.filename,
                    project_id=doc.project_id,
                    issue_type="backend_unavailable",
                    storage_key=self.storage_key_for_document(doc),
                    storage_reference=self.safe_storage_reference(self.storage_key_for_document(doc)),
                    expected_size=doc.file_size,
                    message=str(exc),
                )
                for doc in docs
            ]

        for doc in docs:
            key = self.storage_key_for_document(doc)
            if not key:
                issues.append(StorageConsistencyIssue(
                    document_id=doc.id,
                    filename=doc.filename,
                    project_id=doc.project_id,
                    issue_type="missing_key",
                    storage_key=None,
                    storage_reference=self.safe_storage_reference(None),
                    expected_size=doc.file_size,
                    message="Document has no storage key.",
                ))
                continue
            try:
                exists = backend.exists(key)
            except Exception as exc:
                issues.append(StorageConsistencyIssue(
                    document_id=doc.id,
                    filename=doc.filename,
                    project_id=doc.project_id,
                    issue_type="exists_check_failed",
                    storage_key=key,
                    storage_reference=self.safe_storage_reference(key),
                    expected_size=doc.file_size,
                    message=str(exc),
                ))
                continue
            if not exists:
                issues.append(StorageConsistencyIssue(
                    document_id=doc.id,
                    filename=doc.filename,
                    project_id=doc.project_id,
                    issue_type="missing_object",
                    storage_key=key,
                    storage_reference=self.safe_storage_reference(key),
                    expected_size=doc.file_size,
                    message="DB record exists, but storage object is missing.",
                ))
                continue
            try:
                actual_size = backend.file_size(key)
            except Exception:
                actual_size = None
            if actual_size is not None and doc.file_size is not None and int(doc.file_size or 0) != int(actual_size):
                issues.append(StorageConsistencyIssue(
                    document_id=doc.id,
                    filename=doc.filename,
                    project_id=doc.project_id,
                    issue_type="size_mismatch",
                    storage_key=key,
                    storage_reference=self.safe_storage_reference(key),
                    expected_size=doc.file_size,
                    actual_size=actual_size,
                    message="DB file size does not match the stored object size.",
                ))
        return issues

    def object_exists(self, key: str | None) -> bool:
        if not key:
            return False
        try:
            from app.services.storage import get_storage_backend

            return get_storage_backend().exists(key)
        except Exception:
            return False

    def repair_document_size(self, document_id: int, *, actor_user_id: int | None = None) -> int:
        """Refresh one document's DB file size from the active storage backend."""

        from app.models.core import AuditLog
        from app.models.researcher import ResearcherDocument
        from app.routes.route_entity_lookup import get_entity_or_404
        from app.services.storage import get_storage_backend

        doc = get_entity_or_404(ResearcherDocument, document_id)
        key = self.storage_key_for_document(doc)
        if not key:
            raise ValueError("Document has no storage key.")

        actual_size = get_storage_backend().file_size(key)
        doc.file_size = int(actual_size)
        if actor_user_id:
            db.session.add(AuditLog(
                user_id=actor_user_id,
                action="admin.storage.repair_size",
                resource=doc.filename,
                resource_id=str(doc.id),
                project_id=doc.project_id,
            ))
        db.session.commit()
        return int(actual_size)

    @staticmethod
    def storage_key_for_document(doc) -> str | None:
        return getattr(doc, "storage_key", None) or doc.file_path or doc.filename

    @staticmethod
    def safe_storage_reference(storage_key: str | None) -> dict[str, str | None]:
        """Return storage identifiers safe for admin display without exposing paths."""

        if not storage_key:
            return {"name": None, "sha256": None}
        key_text = str(storage_key)
        return {
            "name": key_text.replace("\\", "/").rsplit("/", 1)[-1],
            "sha256": hashlib.sha256(key_text.encode("utf-8")).hexdigest(),
        }


storage_manager_service = StorageManagerService()

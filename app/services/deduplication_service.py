"""Phase 6 Deduplication Service — detects and merges duplicate references
using DOI normalization, title similarity, and cascaded relationship repair.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.time_utils import utcnow_naive

from app.database import db
from app.models.researcher import Reference

logger = logging.getLogger(__name__)


class DuplicateMergeLog(db.Model):
    """Audit log for deduplication merges — allows reversal within 30 days."""

    __tablename__ = "duplicate_merge_logs"

    id = db.Column(db.Integer, primary_key=True)
    kept_id = db.Column(db.Integer, nullable=False)
    removed_id = db.Column(db.Integer, nullable=False)
    merged_at = db.Column(db.DateTime, default=utcnow_naive)
    merged_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    revert_payload = db.Column(db.JSON)  # Snapshot of removed ref for undo

    def to_dict(self):
        return {
            "id": self.id,
            "kept_id": self.kept_id,
            "removed_id": self.removed_id,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
        }


class DeduplicationService:
    """Detect and merge duplicate references in a project."""

    # Jaro-Winkler threshold for title matching
    TITLE_SIMILARITY_THRESHOLD = 0.92

    def __init__(self, reference_repo=None):
        self._reference_repo = reference_repo

    @property
    def _ref_repo(self):
        if self._reference_repo is None:
            from app.repositories.reference_repository import ReferenceRepository

            self._reference_repo = ReferenceRepository()
        return self._reference_repo

    def find_duplicates(
        self, project_id: int
    ) -> list[tuple[Reference, Reference, str, float]]:
        """Find duplicate pairs in a project.

        Returns list of (ref_a, ref_b, strategy, score).
        """
        refs = self._ref_repo.get_by_project(project_id)
        pairs = []
        seen = set()

        for i, a in enumerate(refs):
            for j in range(i + 1, len(refs)):
                b = refs[j]
                pair_key = (min(a.id, b.id), max(a.id, b.id))
                if pair_key in seen:
                    continue

                strategy, score = self._check_duplicate(a, b)
                if strategy:
                    pairs.append((a, b, strategy, score))
                    seen.add(pair_key)

        return pairs

    def merge(
        self, kept_id: int, removed_id: int, *, merged_by: int | None = None
    ) -> tuple[bool, str]:
        """Merge removed into kept reference.

        Returns (success, message).
        """
        kept = db.session.get(Reference, kept_id)
        removed = db.session.get(Reference, removed_id)

        if not kept or not removed:
            return False, "Reference not found"

        if kept.project_id != removed.project_id:
            return False, "References must be in the same project"

        # Save snapshot for undo
        snapshot = {
            "title": removed.title,
            "doi": removed.doi,
            "authors_json": removed.authors_json,
            "abstract": removed.abstract,
            "year": removed.year,
            "citation_key": removed.citation_key,
            "url": removed.url,
        }

        # Merge metadata — fill gaps in kept from removed
        if not kept.doi and removed.doi:
            kept.doi = removed.doi
        if not kept.abstract and removed.abstract:
            kept.abstract = removed.abstract
        if not kept.url and removed.url:
            kept.url = removed.url
        if not kept.year and removed.year:
            kept.year = removed.year

        # Log merge
        log = DuplicateMergeLog(
            kept_id=kept_id,
            removed_id=removed_id,
            merged_by=merged_by,
            revert_payload=snapshot,
        )
        db.session.add(log)

        # Delete removed
        self._ref_repo.delete(removed)
        self._ref_repo.commit()

        return True, f"Merged #{removed_id} into #{kept_id}"

    def revert(self, merge_log_id: int) -> tuple[bool, str]:
        """Revert a merge if within 30 days."""
        log = db.session.get(DuplicateMergeLog, merge_log_id)
        if not log:
            return False, "Merge log not found"

        age = utcnow_naive() - log.merged_at
        if age.days > 30:
            return False, "Merge is older than 30 days and cannot be reverted"

        # Check kept still exists
        kept = db.session.get(Reference, log.kept_id)
        if not kept:
            return False, "Kept reference no longer exists"

        # Re-create removed reference
        payload = log.revert_payload or {}
        restored = Reference(
            project_id=kept.project_id,
            title=payload.get("title", "Restored"),
            doi=payload.get("doi"),
            authors_json=payload.get("authors_json"),
            abstract=payload.get("abstract"),
            year=payload.get("year"),
            url=payload.get("url"),
            citation_key=payload.get(
                "citation_key", f"Restored{payload.get('year', '')}"
            ),
        )
        self._ref_repo.add(restored)
        db.session.delete(log)
        self._ref_repo.commit()

        return True, "Merge reverted successfully"

    def _check_duplicate(self, a: Reference, b: Reference) -> tuple[str | None, float]:
        """Check if two references are duplicates. Returns (strategy, score)."""
        # Exact DOI match
        if a.doi and b.doi:
            norm_a = self._normalize_doi(a.doi)
            norm_b = self._normalize_doi(b.doi)
            if norm_a == norm_b:
                return ("doi_exact", 1.0)

        # DOI normalized match (case, slash)
        if a.doi and b.doi and norm_a and norm_b and norm_a.lower() == norm_b.lower():
            return ("doi_normalized", 0.95)

        # Title + year match
        if a.title and b.title and a.publication_year and b.publication_year:
            if (
                self._normalize_title(a.title) == self._normalize_title(b.title)
                and a.publication_year == b.publication_year
            ):
                return ("title_year", 0.98)

        return (None, 0.0)

    @staticmethod
    def _normalize_doi(doi: str) -> str | None:
        """Normalize DOI: lowercase, remove URL prefix."""
        if not doi:
            return None
        doi = doi.lower().strip()
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "")
        return doi if doi.startswith("10.") else None

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for comparison."""
        import re

        t = title.lower().strip()
        t = re.sub(r"[^\w\s]", "", t)
        t = re.sub(r"\s+", " ", t)
        return t

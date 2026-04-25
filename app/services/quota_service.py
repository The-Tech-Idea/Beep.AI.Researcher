"""QuotaService — enforce and track per-user storage / document limits.

Hierarchy (first match wins):
  1. User-level override    (users.storage_quota_bytes / document_quota)
  2. Tenant pool quota      (tenant_quotas row for the user's tenant)
  3. Plan tier              (plan_tiers row via user.plan_tier_id
                             or tenant.plan_tier_id)
  4. Global defaults        (config_manager settings)

Usage
-----
::

    from app.services.quota_service import quota_service

    # Before accepting an upload:
    quota_service.check_quota(user_id=42, upload_size_bytes=5_000_000)
    # → raises QuotaExceededError if over limit

    # After a successful save:
    quota_service.record_upload(user_id=42, file_size_bytes=5_000_000)

    # After a delete:
    quota_service.record_delete(user_id=42, file_size_bytes=5_000_000)

    # Periodic recalculation (scheduled task or admin action):
    quota_service.recalculate_user(user_id=42)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Custom exception
# ─────────────────────────────────────────────────────────────────────────────

class QuotaExceededError(Exception):
    """Raised when an operation would violate the user's storage quota."""

    def __init__(self, reason: str, used: int = 0, limit: int = 0,
                 quota_type: str = 'storage'):
        super().__init__(reason)
        self.reason = reason
        self.used = used
        self.limit = limit
        self.quota_type = quota_type   # 'storage' | 'documents' | 'upload_size'


# ─────────────────────────────────────────────────────────────────────────────
# Value object returned by get_effective_quota / get_usage
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EffectiveQuota:
    """The resolved limits and current usage for a user."""
    user_id: int
    # Limits (None = unlimited)
    storage_quota_bytes: Optional[int]
    document_quota: Optional[int]
    max_upload_size_bytes: Optional[int]
    # Current usage
    used_storage_bytes: int
    document_count: int
    # Source info (for transparency in admin UI)
    source: str  # 'user_override', 'tenant', 'plan_tier', 'global_default'

    @property
    def storage_remaining_bytes(self) -> Optional[int]:
        if self.storage_quota_bytes is None:
            return None
        return max(0, self.storage_quota_bytes - self.used_storage_bytes)

    @property
    def storage_percent_used(self) -> Optional[float]:
        if not self.storage_quota_bytes:
            return None
        return round(self.used_storage_bytes / self.storage_quota_bytes * 100, 1)

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'storage_quota_bytes': self.storage_quota_bytes,
            'document_quota': self.document_quota,
            'max_upload_size_bytes': self.max_upload_size_bytes,
            'used_storage_bytes': self.used_storage_bytes,
            'document_count': self.document_count,
            'storage_remaining_bytes': self.storage_remaining_bytes,
            'storage_percent_used': self.storage_percent_used,
            'source': self.source,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Service class
# ─────────────────────────────────────────────────────────────────────────────

class QuotaService:
    """Stateless service — uses SQLAlchemy session for all DB access."""

    # ── Quota resolution ──────────────────────────────────────────────────────

    def get_effective_quota(self, user_id: int) -> EffectiveQuota:
        """Resolve the effective quota for ``user_id``.

        Priority: user override > tenant pool > plan tier > global defaults.
        """
        from app.database import db
        from app.models.core import User
        from app.models.researcher.storage_quota import (
            PlanTier, TenantQuota, UserStorageStats,
        )
        from app.config_manager import config_manager as cm

        user = db.session.get(User, user_id)
        if user is None:
            raise ValueError(f'User {user_id} not found')

        # Current usage
        stats = UserStorageStats.query.filter_by(user_id=user_id).first()
        used_bytes = stats.used_storage_bytes if stats else 0
        doc_count = stats.document_count if stats else 0

        # ── 1. User-level override ────────────────────────────────────────────
        if user.storage_quota_bytes is not None or user.document_quota is not None:
            plan_max_upload = self._plan_max_upload(user, cm)
            return EffectiveQuota(
                user_id=user_id,
                storage_quota_bytes=user.storage_quota_bytes,
                document_quota=user.document_quota,
                max_upload_size_bytes=plan_max_upload,
                used_storage_bytes=used_bytes,
                document_count=doc_count,
                source='user_override',
            )

        # ── 2. Tenant pool quota ──────────────────────────────────────────────
        tenant_id = getattr(user, 'tenant_id', None)
        if tenant_id:
            tq = TenantQuota.query.filter_by(tenant_id=tenant_id).first()
            if tq and (tq.storage_quota_bytes is not None
                       or tq.document_quota is not None):
                plan_max_upload = self._plan_max_upload(user, cm)
                return EffectiveQuota(
                    user_id=user_id,
                    storage_quota_bytes=tq.storage_quota_bytes,
                    document_quota=tq.document_quota,
                    max_upload_size_bytes=(
                        tq.max_upload_size_bytes or plan_max_upload
                    ),
                    used_storage_bytes=used_bytes,
                    document_count=doc_count,
                    source='tenant',
                )

        # ── 3. Plan tier ──────────────────────────────────────────────────────
        plan_tier_id = getattr(user, 'plan_tier_id', None)
        if plan_tier_id is None and tenant_id:
            # Check tenant's plan tier
            from app.models.tenant import Tenant
            tenant = db.session.get(Tenant, tenant_id)
            if tenant:
                plan_tier_id = getattr(tenant, 'plan_tier_id', None)

        if plan_tier_id:
            tier = db.session.get(PlanTier, plan_tier_id)
            if tier:
                return EffectiveQuota(
                    user_id=user_id,
                    storage_quota_bytes=tier.storage_quota_bytes,
                    document_quota=tier.document_quota,
                    max_upload_size_bytes=tier.max_upload_size_bytes,
                    used_storage_bytes=used_bytes,
                    document_count=doc_count,
                    source='plan_tier',
                )

        # ── 4. Global defaults ────────────────────────────────────────────────
        return EffectiveQuota(
            user_id=user_id,
            storage_quota_bytes=cm.get('default_storage_quota_bytes'),
            document_quota=cm.get('default_document_quota'),
            max_upload_size_bytes=cm.get('default_max_upload_size_bytes'),
            used_storage_bytes=used_bytes,
            document_count=doc_count,
            source='global_default',
        )

    @staticmethod
    def _plan_max_upload(user, cm) -> Optional[int]:
        """Resolve max upload size from plan tier or global default."""
        from app.database import db
        from app.models.researcher.storage_quota import PlanTier
        plan_tier_id = getattr(user, 'plan_tier_id', None)
        if plan_tier_id:
            tier = db.session.get(PlanTier, plan_tier_id)
            if tier and tier.max_upload_size_bytes:
                return tier.max_upload_size_bytes
        return cm.get('default_max_upload_size_bytes')

    # ── Enforcement ───────────────────────────────────────────────────────────

    def check_quota(self, user_id: int, upload_size_bytes: int = 0) -> EffectiveQuota:
        """Assert the user can run this upload.

        Args:
            user_id: The user attempting the upload.
            upload_size_bytes: Size of the file to be saved.

        Returns:
            The resolved :class:`EffectiveQuota` (useful for callers that need
            to display quota info in the response).

        Raises:
            :class:`QuotaExceededError` if any limit would be broken.
        """
        from app.config_manager import config_manager as cm

        if not cm.get('quota_enforcement_enabled', True):
            # Enforcement globally disabled — still resolve quota for display
            return self.get_effective_quota(user_id)

        quota = self.get_effective_quota(user_id)

        # Max single file size
        if quota.max_upload_size_bytes and upload_size_bytes > quota.max_upload_size_bytes:
            raise QuotaExceededError(
                f'File too large: {upload_size_bytes:,} bytes exceeds the '
                f'{quota.max_upload_size_bytes:,} byte upload limit.',
                used=upload_size_bytes,
                limit=quota.max_upload_size_bytes,
                quota_type='upload_size',
            )

        # Total storage
        if quota.storage_quota_bytes is not None:
            projected = quota.used_storage_bytes + upload_size_bytes
            if projected > quota.storage_quota_bytes:
                raise QuotaExceededError(
                    f'Storage quota exceeded: {projected:,} bytes projected '
                    f'vs {quota.storage_quota_bytes:,} bytes allowed.',
                    used=quota.used_storage_bytes,
                    limit=quota.storage_quota_bytes,
                    quota_type='storage',
                )

        # Document count
        if quota.document_quota is not None:
            if quota.document_count >= quota.document_quota:
                raise QuotaExceededError(
                    f'Document quota exceeded: {quota.document_count} of '
                    f'{quota.document_quota} documents used.',
                    used=quota.document_count,
                    limit=quota.document_quota,
                    quota_type='documents',
                )

        return quota

    # ── Usage tracking: record_upload / record_delete / recalculate ───────────

    def record_upload(self, user_id: int, file_size_bytes: int,
                      tenant_id: Optional[int] = None) -> None:
        """Increment usage counters after a successful upload.

        Increments:
          - ``UserStorageStats.used_storage_bytes``
          - ``UserStorageStats.document_count``
          - ``TenantQuota.used_storage_bytes`` and ``document_count`` (if found)
        """
        from app.database import db
        from app.models.researcher.storage_quota import UserStorageStats, TenantQuota
        from app.core.time_utils import utcnow_naive

        stats = UserStorageStats.query.filter_by(user_id=user_id).first()
        if stats is None:
            stats = UserStorageStats(user_id=user_id,
                                     used_storage_bytes=0,
                                     document_count=0)
            db.session.add(stats)

        stats.used_storage_bytes = (stats.used_storage_bytes or 0) + file_size_bytes
        stats.document_count = (stats.document_count or 0) + 1
        stats.last_upload_at = utcnow_naive()

        # Mirror to tenant pool if applicable
        resolved_tenant_id = tenant_id or self._get_tenant_id(user_id)
        if resolved_tenant_id:
            tq = TenantQuota.query.filter_by(tenant_id=resolved_tenant_id).first()
            if tq is not None:
                tq.used_storage_bytes = (tq.used_storage_bytes or 0) + file_size_bytes
                tq.document_count = (tq.document_count or 0) + 1

        db.session.commit()
        logger.debug('Quota.record_upload user=%d size=%d', user_id, file_size_bytes)

    def record_delete(self, user_id: int, file_size_bytes: int,
                      tenant_id: Optional[int] = None) -> None:
        """Decrement usage counters after a document deletion."""
        from app.database import db
        from app.models.researcher.storage_quota import UserStorageStats, TenantQuota

        stats = UserStorageStats.query.filter_by(user_id=user_id).first()
        if stats is not None:
            stats.used_storage_bytes = max(
                0, (stats.used_storage_bytes or 0) - file_size_bytes
            )
            stats.document_count = max(0, (stats.document_count or 0) - 1)

        resolved_tenant_id = tenant_id or self._get_tenant_id(user_id)
        if resolved_tenant_id:
            tq = TenantQuota.query.filter_by(tenant_id=resolved_tenant_id).first()
            if tq is not None:
                tq.used_storage_bytes = max(
                    0, (tq.used_storage_bytes or 0) - file_size_bytes
                )
                tq.document_count = max(0, (tq.document_count or 0) - 1)

        db.session.commit()
        logger.debug('Quota.record_delete user=%d size=%d', user_id, file_size_bytes)

    def recalculate_user(self, user_id: int) -> UserStorageStats:
        """Recompute usage from the database for a user.

        Queries ``ResearcherDocument`` for the actual totals which may differ
        from running counters after manual DB edits or data migrations.
        """
        from app.database import db
        from app.models.researcher import ResearcherDocument
        from app.models.researcher.storage_quota import UserStorageStats
        from app.core.time_utils import utcnow_naive
        from sqlalchemy import func

        # Aggregate from documents owned by this user
        row = (
            db.session.query(
                func.coalesce(func.sum(ResearcherDocument.file_size), 0),
                func.count(ResearcherDocument.id),
            )
            .join(
                __import__('app.models.researcher', fromlist=['ResearchProject']).ResearchProject,
                ResearcherDocument.project_id == __import__('app.models.researcher', fromlist=['ResearchProject']).ResearchProject.id,
            )
            .filter(
                __import__('app.models.researcher', fromlist=['ResearchProject']).ResearchProject.user_id == user_id
            )
            .first()
        )

        total_bytes, doc_count = row if row else (0, 0)

        stats = UserStorageStats.query.filter_by(user_id=user_id).first()
        if stats is None:
            stats = UserStorageStats(user_id=user_id)
            db.session.add(stats)
        stats.used_storage_bytes = int(total_bytes)
        stats.document_count = int(doc_count)
        stats.last_recalculated_at = utcnow_naive()
        db.session.commit()

        logger.info('Quota.recalculate user=%d → %d bytes / %d docs',
                    user_id, stats.used_storage_bytes, stats.document_count)
        return stats

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _get_tenant_id(user_id: int) -> Optional[int]:
        try:
            from app.database import db
            from app.models.core import User
            user = db.session.get(User, user_id)
            return getattr(user, 'tenant_id', None)
        except Exception:
            return None

    @staticmethod
    def _get_user_stats(user_id: int):
        from app.models.researcher.storage_quota import UserStorageStats
        return UserStorageStats.query.filter_by(user_id=user_id).first()


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────

quota_service: QuotaService = QuotaService()

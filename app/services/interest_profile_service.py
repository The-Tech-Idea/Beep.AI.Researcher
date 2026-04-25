"""Declared interest profile management for Phase 1 AI discovery."""
from __future__ import annotations

from typing import Any

from app.core.job_queue import get_job_queue, get_job_registry
from app.database import db
from app.models.researcher import ResearchInterestProfile
from app.services.ai_discovery_utils import normalize_topic_list


INTEREST_INFERENCE_JOB_TYPE = "interest_profile_inference"


class InterestProfileService:
    """Manage declared research interests and inference triggers."""

    DEFAULT_SOURCES = ["semantic_scholar", "pubmed", "arxiv", "crossref"]
    ALLOWED_SOURCES = set(DEFAULT_SOURCES)

    def __init__(self, inference_service=None, recommendation_service=None, job_queue_factory=get_job_queue):
        self._inference_service = inference_service
        self._recommendation_service = recommendation_service
        self._job_queue_factory = job_queue_factory

    def get_or_create_profile(self, user_id: int) -> ResearchInterestProfile:
        profile = ResearchInterestProfile.query.filter_by(user_id=user_id).first()
        if profile is None:
            profile = ResearchInterestProfile(
                user_id=user_id,
                preferred_sources=list(self.DEFAULT_SOURCES),
            )
            db.session.add(profile)
            db.session.commit()
        elif not profile.preferred_sources:
            profile.preferred_sources = list(self.DEFAULT_SOURCES)
            db.session.commit()
        return profile

    def get_profile_dict(self, user_id: int) -> dict[str, Any]:
        return self.get_or_create_profile(user_id).to_dict()

    def update_profile(
        self,
        user_id: int,
        *,
        declared_topics=None,
        preferred_sources=None,
        inference_enabled: bool | None = None,
        trigger_inference: bool = True,
        run_async: bool = True,
    ) -> ResearchInterestProfile:
        profile = self.get_or_create_profile(user_id)

        if declared_topics is not None:
            profile.declared_topics = normalize_topic_list(declared_topics)
        if preferred_sources is not None:
            profile.preferred_sources = self._normalize_sources(preferred_sources)
        if inference_enabled is not None:
            profile.inference_enabled = bool(inference_enabled)

        db.session.add(profile)
        db.session.commit()

        self._get_recommendation_service().invalidate_user_feed(user_id)

        if trigger_inference and profile.inference_enabled:
            self.trigger_inference(user_id, run_async=run_async)

        return profile

    def effective_topics(self, user_id: int, *, limit: int = 10) -> list[str]:
        profile = self.get_or_create_profile(user_id)
        topics: list[str] = []
        seen: set[str] = set()

        for topic in normalize_topic_list(profile.declared_topics, limit=limit):
            key = topic.casefold()
            if key in seen:
                continue
            seen.add(key)
            topics.append(topic)
            if len(topics) >= limit:
                return topics

        for item in profile.inferred_topics or []:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic") or "").strip()
            if not topic:
                continue
            key = topic.casefold()
            if key in seen:
                continue
            seen.add(key)
            topics.append(topic)
            if len(topics) >= limit:
                break

        return topics

    def trigger_inference(self, user_id: int, *, run_async: bool = True):
        if run_async:
            queue = self._job_queue_factory()
            job = queue.create_job(
                job_type=INTEREST_INFERENCE_JOB_TYPE,
                input_data={"user_id": user_id},
                metadata={"feature": "ai_discovery"},
            )
            return job.job_id

        return self._get_inference_service().update_profile(user_id)

    def _normalize_sources(self, sources) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for source in sources or []:
            key = str(source or "").strip().lower()
            if key not in self.ALLOWED_SOURCES or key in seen:
                continue
            seen.add(key)
            cleaned.append(key)
        return cleaned or list(self.DEFAULT_SOURCES)

    def _get_inference_service(self):
        if self._inference_service is None:
            from app.services.interest_inference_service import InterestInferenceService
            self._inference_service = InterestInferenceService()
        return self._inference_service

    def _get_recommendation_service(self):
        if self._recommendation_service is None:
            from app.services.recommendation_service import RecommendationService
            self._recommendation_service = RecommendationService()
        return self._recommendation_service


def handle_interest_profile_inference_job(input_data: dict[str, Any]) -> dict[str, Any]:
    user_id = int(input_data.get("user_id"))
    inferred_topics = InterestProfileService().trigger_inference(user_id, run_async=False)
    return {"user_id": user_id, "inferred_topics": inferred_topics}


get_job_registry().register(INTEREST_INFERENCE_JOB_TYPE, handle_interest_profile_inference_job)
"""Recommendation ranking and feed persistence for Phase 1 AI discovery."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

from app.core.time_utils import utcnow_naive
from app.database import db
from app.integrations.search.search_manager import SearchManager
from app.models.researcher import FeedRecommendation, ReadingListItem, Reference, ResearchProject, ResearcherDocument
from app.services import beep_ai_client
from app.services.ai_discovery_utils import (
    build_candidate_text,
    canonical_external_id,
    collapse_whitespace,
    compute_topic_overlap,
    cosine_similarity,
    normalize_identifier,
    normalize_for_match,
    parse_publication_date,
)


@dataclass
class PaperRecommendation:
    external_id: str
    title: str
    authors: list[str]
    abstract: str
    source: str
    source_id: str | None
    url: str | None
    publication_date: str | None
    doi: str | None
    relevance_score: float = 0.0
    reason: str | None = None

    @classmethod
    def from_search_result(cls, result):
        return cls(
            external_id=canonical_external_id(
                result.source,
                source_id=result.source_id,
                doi=result.doi,
                title=result.title,
            ),
            title=result.title,
            authors=list(result.authors or []),
            abstract=result.abstract or "",
            source=result.source,
            source_id=result.source_id,
            url=result.url,
            publication_date=result.publication_date,
            doi=result.doi,
        )


class RecommendationService:
    """Build and cache personalized reading recommendations."""

    DEFAULT_SOURCES = ["semantic_scholar", "pubmed", "arxiv", "crossref"]

    def __init__(self, search_manager=None, ai_client_module=beep_ai_client):
        self.search_manager = search_manager or SearchManager.get_instance()
        self.ai_client = ai_client_module

    def invalidate_user_feed(self, user_id: int) -> None:
        (
            FeedRecommendation.query
            .filter(FeedRecommendation.user_id == user_id, FeedRecommendation.dismissed.is_(False))
            .delete(synchronize_session=False)
        )
        db.session.commit()

    def refresh_feed(self, user_id: int, *, force: bool = False, limit: int = 50, sources=None) -> list[FeedRecommendation]:
        today = utcnow_naive().date()

        if not force:
            cached = self._load_cached_feed(user_id, today, limit=limit)
            if cached:
                return cached

        from app.services.interest_inference_service import InterestInferenceService
        from app.services.interest_profile_service import InterestProfileService

        profile_service = InterestProfileService()
        profile = profile_service.get_or_create_profile(user_id)
        topics = profile_service.effective_topics(user_id, limit=12)
        if not topics and profile.inference_enabled:
            InterestInferenceService(ai_client_module=self.ai_client).update_profile(user_id)
            topics = profile_service.effective_topics(user_id, limit=12)
        if not topics:
            return []

        candidates = self.fetch_candidates(topics, sources=sources or profile.preferred_sources)
        scored = self.score_candidates(
            candidates,
            topics=topics,
            preferred_sources=profile.preferred_sources or self.DEFAULT_SOURCES,
        )
        filtered = self._filter_candidates(user_id, scored)[:limit]
        return self._persist_feed(user_id, filtered, today)

    def fetch_candidates(self, topics: list[str], *, sources=None, per_topic_limit: int = 8) -> list[PaperRecommendation]:
        chosen_sources = [source for source in (sources or self.DEFAULT_SOURCES) if source in self.search_manager.providers]
        recommendations: list[PaperRecommendation] = []

        for topic in topics:
            for source in chosen_sources:
                provider = self.search_manager.providers.get(source)
                if provider is None:
                    continue
                try:
                    if hasattr(provider, "search_by_topic"):
                        results = provider.search_by_topic(topic, limit=per_topic_limit)
                    else:
                        results = provider.search(topic, limit=per_topic_limit)
                except Exception:
                    results = []
                for result in results or []:
                    recommendations.append(PaperRecommendation.from_search_result(result))

        deduped: dict[str, PaperRecommendation] = {}
        for recommendation in recommendations:
            existing = deduped.get(recommendation.external_id)
            if existing is None or len(recommendation.abstract or "") > len(existing.abstract or ""):
                deduped[recommendation.external_id] = recommendation
        return list(deduped.values())

    def score_candidates(self, candidates: list[PaperRecommendation], *, topics: list[str], preferred_sources: list[str] | None = None) -> list[PaperRecommendation]:
        if not candidates:
            return []

        candidate_texts = [build_candidate_text(item.title, item.abstract) for item in candidates]
        profile_text = "; ".join(topics)
        embedding_scores = self._score_with_embeddings(profile_text, candidate_texts)

        preferred_set = {str(source).lower() for source in (preferred_sources or [])}
        scored: list[PaperRecommendation] = []
        for index, candidate in enumerate(candidates):
            candidate_text = candidate_texts[index]
            overlap_score, best_topic = compute_topic_overlap(candidate_text, topics)
            embedding_score = embedding_scores[index] if index < len(embedding_scores) else overlap_score
            base_score = (overlap_score * 0.45) + (embedding_score * 0.55)

            source_boost = 0.03 if candidate.source.lower() in preferred_set else 0.0
            recency_factor = self._recency_factor(candidate.publication_date)
            candidate.relevance_score = round(min(1.0, (base_score + source_boost) * recency_factor), 4)
            candidate.reason = (
                f"Matches your interest in {best_topic}" if best_topic else f"Recommended from {candidate.source.replace('_', ' ')}"
            )
            scored.append(candidate)

        scored.sort(key=lambda item: (-item.relevance_score, item.title.lower()))
        return scored

    def dismiss_recommendation(self, user_id: int, *, recommendation_id: int | None = None, external_id: str | None = None) -> FeedRecommendation:
        query = FeedRecommendation.query.filter_by(user_id=user_id)
        if recommendation_id is not None:
            recommendation = query.filter_by(id=recommendation_id).first()
        elif external_id is not None:
            recommendation = query.filter_by(external_id=external_id).order_by(FeedRecommendation.created_at.desc()).first()
        else:
            recommendation = None

        if recommendation is None:
            raise LookupError("Recommendation not found")

        recommendation.dismissed = True
        db.session.commit()
        return recommendation

    def mark_saved(self, user_id: int, external_id: str) -> FeedRecommendation | None:
        recommendation = (
            FeedRecommendation.query
            .filter_by(user_id=user_id, external_id=external_id)
            .order_by(FeedRecommendation.created_at.desc())
            .first()
        )
        if recommendation is None:
            return None
        recommendation.saved = True
        db.session.commit()
        return recommendation

    def get_related_reading_for_document(self, document_id: int, user_id: int, *, limit: int = 10) -> list[PaperRecommendation]:
        document = db.session.get(ResearcherDocument, document_id)
        if document is None:
            raise LookupError("Document not found")

        seed_text = build_candidate_text(document.filename, document.text_content)
        if not seed_text:
            return []

        topics = [fragment for fragment in seed_text.split(".")[:2] if fragment.strip()]
        if not topics:
            topics = [document.filename]
        candidates = self.fetch_candidates(topics, sources=["semantic_scholar"], per_topic_limit=max(limit, 6))
        scored = self.score_candidates(candidates, topics=topics, preferred_sources=["semantic_scholar"])
        return self._filter_candidates(user_id, scored)[:limit]

    def _load_cached_feed(self, user_id: int, feed_date: date, *, limit: int) -> list[FeedRecommendation]:
        return (
            FeedRecommendation.query
            .filter_by(user_id=user_id, feed_date=feed_date, dismissed=False, saved=False)
            .order_by(FeedRecommendation.relevance_score.desc(), FeedRecommendation.created_at.desc())
            .limit(limit)
            .all()
        )

    def _persist_feed(self, user_id: int, recommendations: list[PaperRecommendation], feed_date: date) -> list[FeedRecommendation]:
        (
            FeedRecommendation.query
            .filter(FeedRecommendation.user_id == user_id, FeedRecommendation.feed_date == feed_date, FeedRecommendation.dismissed.is_(False))
            .delete(synchronize_session=False)
        )

        persisted: list[FeedRecommendation] = []
        for item in recommendations:
            record = FeedRecommendation(
                user_id=user_id,
                external_id=item.external_id,
                title=collapse_whitespace(item.title) or "Untitled",
                authors=item.authors,
                abstract=item.abstract,
                source=item.source,
                source_id=collapse_whitespace(item.source_id) or None,
                url=collapse_whitespace(item.url) or None,
                publication_date=collapse_whitespace(item.publication_date) or None,
                doi=normalize_identifier(item.doi),
                relevance_score=item.relevance_score,
                reason=item.reason,
                feed_date=feed_date,
            )
            db.session.add(record)
            persisted.append(record)

        db.session.commit()
        return persisted

    def _filter_candidates(self, user_id: int, candidates: list[PaperRecommendation]) -> list[PaperRecommendation]:
        dismissed_ids = {
            row.external_id
            for row in FeedRecommendation.query.filter_by(user_id=user_id, dismissed=True).all()
        }
        known_ids = self._known_saved_external_ids(user_id)
        known_titles = self._known_saved_titles(user_id)

        filtered: list[PaperRecommendation] = []
        for candidate in candidates:
            if candidate.external_id in dismissed_ids or candidate.external_id in known_ids:
                continue
            if normalize_for_match(candidate.title) in known_titles:
                continue
            filtered.append(candidate)
        return filtered

    def _saved_feed_records(self, user_id: int) -> list[FeedRecommendation]:
        return FeedRecommendation.query.filter_by(user_id=user_id, saved=True).all()

    def _known_saved_external_ids(self, user_id: int) -> set[str]:
        identifiers: set[str] = set()
        references = (
            Reference.query
            .join(ResearchProject, Reference.project_id == ResearchProject.id)
            .filter(ResearchProject.owner_id == user_id)
            .all()
        )
        for reference in references:
            if reference.doi:
                identifiers.add(canonical_external_id("doi", doi=reference.doi))
            if reference.pubmed_id:
                identifiers.add(canonical_external_id("pubmed", source_id=reference.pubmed_id))
            if reference.arxiv_id:
                identifiers.add(canonical_external_id("arxiv", source_id=reference.arxiv_id))

        for item in ReadingListItem.query.filter_by(user_id=user_id).all():
            if item.external_id:
                identifiers.add(item.external_id)

        for recommendation in self._saved_feed_records(user_id):
            if recommendation.external_id:
                identifiers.add(recommendation.external_id)
        return identifiers

    def _known_saved_titles(self, user_id: int) -> set[str]:
        titles = {
            normalize_for_match(reference.title)
            for reference in (
                Reference.query
                .join(ResearchProject, Reference.project_id == ResearchProject.id)
                .filter(ResearchProject.owner_id == user_id)
                .all()
            )
            if reference.title
        }

        titles.update(
            normalize_for_match(item.title)
            for item in ReadingListItem.query.filter_by(user_id=user_id).all()
            if item.title
        )
        titles.update(
            normalize_for_match(recommendation.title)
            for recommendation in self._saved_feed_records(user_id)
            if recommendation.title
        )
        return titles

    def _score_with_embeddings(self, profile_text: str, candidate_texts: list[str]) -> list[float]:
        ok, payload = self.ai_client.get_embeddings([profile_text, *candidate_texts])
        if not ok or not isinstance(payload, list) or len(payload) != len(candidate_texts) + 1:
            return [0.0] * len(candidate_texts)

        profile_vector = payload[0]
        return [max(0.0, cosine_similarity(profile_vector, vector)) for vector in payload[1:]]

    def _recency_factor(self, publication_date: str | None) -> float:
        parsed = parse_publication_date(publication_date)
        if parsed is None:
            return 0.92

        age_days = max(0, (utcnow_naive().date() - parsed).days)
        age_years = age_days / 365.25
        if age_years <= 3.0:
            return 1.0
        return max(0.45, math.exp(-0.18 * (age_years - 3.0)))
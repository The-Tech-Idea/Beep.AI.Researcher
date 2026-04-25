"""Interest inference for Phase 1 AI discovery."""
from __future__ import annotations

from app.database import db
from app.models.researcher import FeedRecommendation, ReadingListItem, Reference, ResearchInterestProfile, ResearchProject, ResearcherDocument
from app.services import beep_ai_client
from app.services.ai_discovery_utils import average_vector, build_candidate_text, cosine_similarity, extract_candidate_topics


class InterestInferenceService:
    """Infer user research topics from their library corpus."""

    def __init__(self, ai_client_module=beep_ai_client):
        self.ai_client = ai_client_module

    def collect_user_corpus(self, user_id: int) -> list[str]:
        texts: list[str] = []

        document_rows = (
            ResearcherDocument.query
            .join(ResearchProject, ResearcherDocument.project_id == ResearchProject.id)
            .filter(ResearchProject.owner_id == user_id)
            .all()
        )
        for document in document_rows:
            text = build_candidate_text(document.filename, document.text_content)
            if text:
                texts.append(text)

        reference_rows = (
            Reference.query
            .join(ResearchProject, Reference.project_id == ResearchProject.id)
            .filter(ResearchProject.owner_id == user_id)
            .all()
        )
        for reference in reference_rows:
            text = build_candidate_text(
                reference.title,
                reference.abstract,
                " ".join(reference.get_keywords()),
            )
            if text:
                texts.append(text)

        reading_list_rows = ReadingListItem.query.filter_by(user_id=user_id).all()
        reading_list_external_ids = sorted(
            {
                item.external_id
                for item in reading_list_rows
                if item.external_id and not item.reference_id
            }
        )
        recommendation_lookup: dict[str, FeedRecommendation] = {}
        if reading_list_external_ids:
            recommendation_rows = (
                FeedRecommendation.query
                .filter(
                    FeedRecommendation.user_id == user_id,
                    FeedRecommendation.external_id.in_(reading_list_external_ids),
                )
                .order_by(FeedRecommendation.created_at.desc())
                .all()
            )
            for recommendation in recommendation_rows:
                recommendation_lookup.setdefault(recommendation.external_id, recommendation)

        for item in reading_list_rows:
            if item.reference_id:
                continue
            recommendation = recommendation_lookup.get(item.external_id)
            text = build_candidate_text(
                item.title,
                getattr(recommendation, "abstract", None),
                " ".join(item.topic_tags or []),
                getattr(recommendation, "reason", None),
            )
            if text:
                texts.append(text)

        return texts

    def infer_topics(self, user_id: int, *, max_topics: int = 10) -> list[dict]:
        corpus = self.collect_user_corpus(user_id)
        if not corpus:
            return []

        candidate_scores = extract_candidate_topics(corpus, max_candidates=max(max_topics * 4, 20))
        if not candidate_scores:
            return []

        max_tfidf = max(score for _, score in candidate_scores) or 1.0
        candidates = [topic for topic, _ in candidate_scores]
        embedding_scores = self._score_candidates_with_embeddings(corpus, candidates)

        scored_topics: list[dict] = []
        for topic, tfidf_score in candidate_scores:
            normalized_tfidf = tfidf_score / max_tfidf
            embedding_score = embedding_scores.get(topic, normalized_tfidf)
            combined_score = (normalized_tfidf * 0.65) + (embedding_score * 0.35)
            scored_topics.append({
                "topic": topic,
                "score": round(min(1.0, combined_score), 4),
            })

        scored_topics.sort(key=lambda item: (-item["score"], item["topic"]))
        return scored_topics[:max_topics]

    def update_profile(self, user_id: int, *, max_topics: int = 10) -> list[dict]:
        inferred_topics = self.infer_topics(user_id, max_topics=max_topics)
        profile = ResearchInterestProfile.query.filter_by(user_id=user_id).first()
        if profile is None:
            profile = ResearchInterestProfile(user_id=user_id)
            db.session.add(profile)

        profile.inferred_topics = inferred_topics
        db.session.commit()
        return inferred_topics

    def _score_candidates_with_embeddings(self, corpus: list[str], candidates: list[str]) -> dict[str, float]:
        if not corpus or not candidates:
            return {}

        corpus_summary = "\n\n".join(corpus)[:8000]
        ok, payload = self.ai_client.get_embeddings([corpus_summary, *candidates])
        if not ok or not isinstance(payload, list) or len(payload) != len(candidates) + 1:
            return {}

        corpus_vector = average_vector([payload[0]])
        if not corpus_vector:
            return {}

        return {
            candidate: max(0.0, cosine_similarity(corpus_vector, vector))
            for candidate, vector in zip(candidates, payload[1:])
        }
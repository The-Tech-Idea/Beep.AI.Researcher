"""Reading-list management for Phase 1 AI discovery."""
from __future__ import annotations

from app.database import db
from app.models.researcher import FeedRecommendation, ReadingListItem, Reference, ResearchProject
from app.services.ai_discovery_payloads import reading_list_item_to_payload
from app.services.ai_discovery_utils import parse_publication_date, source_to_reference_type, split_external_id
from app.services.reference_service import create_reference


class ReadingListService:
    """CRUD and move-to-project operations for reading list items."""

    VALID_STATUSES = {"unread", "reading", "done"}

    def list_items(self, user_id: int, *, status: str | None = None, topic_tag: str | None = None, source: str | None = None) -> list[ReadingListItem]:
        query = ReadingListItem.query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)

        items = query.order_by(ReadingListItem.saved_at.desc()).all()
        if topic_tag:
            items = [item for item in items if topic_tag in (item.topic_tags or [])]
        if source:
            source_key = source.strip().lower()
            items = [item for item in items if self.item_to_dict(item).get("source") == source_key]
        return items

    def save_item(self, user_id: int, *, title: str, external_id: str | None = None, topic_tags=None, reference_id: int | None = None) -> ReadingListItem:
        item = None
        if external_id:
            item = ReadingListItem.query.filter_by(user_id=user_id, external_id=external_id).first()
        if item is None and reference_id:
            item = ReadingListItem.query.filter_by(user_id=user_id, reference_id=reference_id).first()

        if item is None:
            item = ReadingListItem(user_id=user_id)
            db.session.add(item)

        item.title = title
        item.external_id = external_id
        item.reference_id = reference_id
        item.topic_tags = list(topic_tags or [])
        db.session.commit()
        return item

    def save_recommendation(self, user_id: int, recommendation_id: int) -> ReadingListItem:
        recommendation = self._get_recommendation(user_id, recommendation_id)

        item = self.save_item(
            user_id,
            title=recommendation.title,
            external_id=recommendation.external_id,
            topic_tags=self._topic_tags_from_recommendation(recommendation),
        )
        recommendation.saved = True
        db.session.commit()
        return item

    def save_recommendation_to_project(self, user_id: int, recommendation_id: int, project_id: int) -> Reference:
        recommendation = self._get_recommendation(user_id, recommendation_id)
        project = self._get_owned_project(user_id, project_id)

        payload = self._build_reference_payload(
            title=recommendation.title,
            external_id=recommendation.external_id,
            recommendation=recommendation,
            topic_tags=self._topic_tags_from_recommendation(recommendation),
        )
        reference = self._get_or_create_reference(project, payload)
        recommendation.saved = True
        db.session.commit()
        return reference

    def update_status(self, user_id: int, item_id: int, status: str) -> ReadingListItem:
        if status not in self.VALID_STATUSES:
            raise ValueError("Invalid reading-list status")

        item = ReadingListItem.query.filter_by(id=item_id, user_id=user_id).first()
        if item is None:
            raise LookupError("Reading list item not found")

        item.status = status
        db.session.commit()
        return item

    def delete_item(self, user_id: int, item_id: int) -> None:
        item = ReadingListItem.query.filter_by(id=item_id, user_id=user_id).first()
        if item is None:
            raise LookupError("Reading list item not found")
        db.session.delete(item)
        db.session.commit()

    def move_to_project(self, user_id: int, item_id: int, project_id: int) -> Reference:
        item = ReadingListItem.query.filter_by(id=item_id, user_id=user_id).first()
        if item is None:
            raise LookupError("Reading list item not found")

        project = self._get_owned_project(user_id, project_id)

        if item.reference_id:
            existing_reference = db.session.get(Reference, item.reference_id)
            if existing_reference is not None and existing_reference.project_id == project.id:
                return existing_reference

        recommendation = self._latest_recommendation(user_id, item.external_id)
        payload = self._build_reference_payload(
            title=item.title,
            external_id=item.external_id,
            recommendation=recommendation,
            topic_tags=item.topic_tags,
        )
        reference = self._get_or_create_reference(project, payload)

        item.reference_id = reference.id
        db.session.commit()
        return reference

    def item_to_dict(self, item: ReadingListItem) -> dict:
        data = reading_list_item_to_payload(item)
        recommendation = self._latest_recommendation(item.user_id, item.external_id)
        data["source"] = recommendation.source if recommendation else data.get("source")
        data["abstract"] = recommendation.abstract if recommendation else None
        data["authors"] = recommendation.authors if recommendation else []
        data["url"] = getattr(recommendation, "url", None) or data.get("url")
        data["publication_date"] = getattr(recommendation, "publication_date", None)
        data["doi"] = getattr(recommendation, "doi", None)
        data["source_id"] = getattr(recommendation, "source_id", None)
        return data

    def _get_recommendation(self, user_id: int, recommendation_id: int) -> FeedRecommendation:
        recommendation = FeedRecommendation.query.filter_by(
            id=recommendation_id,
            user_id=user_id,
        ).first()
        if recommendation is None:
            raise LookupError("Recommendation not found")
        return recommendation

    def _get_owned_project(self, user_id: int, project_id: int) -> ResearchProject:
        project = ResearchProject.query.filter_by(id=project_id, owner_id=user_id).first()
        if project is None:
            raise LookupError("Project not found")
        return project

    def _build_reference_payload(
        self,
        *,
        title: str,
        external_id: str | None,
        recommendation: FeedRecommendation | None,
        topic_tags: list[str] | None,
    ) -> dict:
        publication_date = parse_publication_date(getattr(recommendation, "publication_date", None))
        payload = {
            "title": title,
            "abstract": recommendation.abstract if recommendation else None,
            "authors": recommendation.authors if recommendation else None,
            "source": recommendation.source if recommendation else None,
            "source_type": source_to_reference_type(recommendation.source if recommendation else None),
            "keywords": list(topic_tags or []),
            "url": getattr(recommendation, "url", None),
            "year": publication_date.year if publication_date else None,
        }

        scheme, identifier = split_external_id(external_id)
        if scheme == "doi":
            payload["doi"] = identifier
        elif scheme == "pubmed":
            payload["pubmed_id"] = identifier
        elif scheme == "arxiv":
            payload["arxiv_id"] = identifier
        elif getattr(recommendation, "doi", None):
            payload["doi"] = recommendation.doi
        return payload

    def _get_or_create_reference(self, project: ResearchProject, payload: dict) -> Reference:
        reference = self._find_existing_reference(project.id, payload)
        if reference is None:
            reference = create_reference(project, payload, commit=False)
            if payload.get("pubmed_id"):
                reference.pubmed_id = payload["pubmed_id"]
            if payload.get("arxiv_id"):
                reference.arxiv_id = payload["arxiv_id"]
            db.session.add(reference)
            db.session.flush()
        return reference

    def _latest_recommendation(self, user_id: int, external_id: str | None) -> FeedRecommendation | None:
        if not external_id:
            return None
        return (
            FeedRecommendation.query
            .filter_by(user_id=user_id, external_id=external_id)
            .order_by(FeedRecommendation.created_at.desc())
            .first()
        )

    def _find_existing_reference(self, project_id: int, payload: dict) -> Reference | None:
        if payload.get("doi"):
            match = Reference.query.filter_by(project_id=project_id, doi=payload["doi"]).first()
            if match:
                return match
        if payload.get("pubmed_id"):
            match = Reference.query.filter_by(project_id=project_id, pubmed_id=payload["pubmed_id"]).first()
            if match:
                return match
        if payload.get("arxiv_id"):
            match = Reference.query.filter_by(project_id=project_id, arxiv_id=payload["arxiv_id"]).first()
            if match:
                return match
        return Reference.query.filter_by(project_id=project_id, title=payload.get("title")).first()

    def _topic_tags_from_recommendation(self, recommendation: FeedRecommendation) -> list[str]:
        reason = (recommendation.reason or "").strip()
        if reason.lower().startswith("matches your interest in "):
            return [reason.split("interest in ", 1)[1].strip()]
        return []
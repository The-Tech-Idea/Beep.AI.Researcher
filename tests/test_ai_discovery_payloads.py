from datetime import date

from app.models.researcher.phase_1_models import FeedRecommendation, PaperAlert, ReadingListItem
from app.services.ai_discovery_payloads import (
    build_external_url,
    feed_recommendation_to_payload,
    paper_alert_to_payload,
    reading_list_item_to_payload,
)


def test_feed_payload_adds_ui_aliases_and_url(test_user):
    item = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/example",
        title="Example Feed Paper",
        authors=["A. Author"],
        source="crossref",
        dismissed=True,
        saved=False,
        feed_date=date(2026, 4, 13),
    )

    payload = feed_recommendation_to_payload(item)

    assert payload["is_dismissed"] is True
    assert payload["is_saved"] is False
    assert payload.get("publication_date") is None
    assert payload["recommended_date"] == "2026-04-13"
    assert payload["url"] == "https://doi.org/10.1000/example"


def test_reading_list_payload_builds_external_url_and_source(test_user):
    item = ReadingListItem(
        user_id=test_user.id,
        external_id="pubmed:12345",
        title="Saved Reading Item",
        status="unread",
        topic_tags=[],
    )

    payload = reading_list_item_to_payload(item)

    assert payload["source"] == "pubmed"
    assert payload["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"


def test_alert_payload_exposes_matched_at_and_url(test_user):
    item = PaperAlert(
        user_id=test_user.id,
        external_id="arxiv:2401.12345",
        title="Fresh Alert",
        source="arxiv",
        alert_date=date(2026, 4, 13),
    )

    payload = paper_alert_to_payload(item)

    assert payload["matched_at"] == "2026-04-13"
    assert payload["url"] == "https://arxiv.org/abs/2401.12345"


def test_build_external_url_ignores_title_only_identifiers():
    assert build_external_url("semantic_scholar", "semantic_scholar:title:example paper") is None
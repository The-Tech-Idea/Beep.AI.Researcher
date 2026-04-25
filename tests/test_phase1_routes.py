"""Phase 1 AI Discovery - route acceptance tests.

Patch strategy
--------------
- Feature flag: imported at module level in each route -> patch at route module ns
  e.g.  patch("app.routes.feed.is_feature_enabled", return_value=True)
- Services: deferred (inside-function) imports -> patch at the service source module
  e.g.  patch("app.services.recommendation_service.RecommendationService")
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _json(resp):
    return json.loads(resp.data)


@contextmanager
def _feature_on(route_module: str):
    with patch(
        f"app.routes.{route_module}.is_feature_enabled", return_value=True
    ):
        yield


@contextmanager
def _app_feature_on():
    with patch("app.config_manager.is_feature_enabled", return_value=True):
        yield


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

_REC_SVC = "app.services.recommendation_service.RecommendationService"
_RL_SVC = "app.services.reading_list_service.ReadingListService"


class TestFeedRoutes:

    def test_index_returns_200(self, client):
        with _feature_on("feed"):
            resp = client.get("/feed")
        assert resp.status_code == 200

    def test_get_feed_empty(self, client):
        with _feature_on("feed"), patch(_REC_SVC) as M:
            M.return_value.refresh_feed.return_value = []
            resp = client.get("/feed/data")
        assert resp.status_code == 200
        assert _json(resp)["items"] == []

    def test_get_feed_returns_serialised_dicts(self, client):
        item = MagicMock()
        item.to_dict.return_value = {"id": 1, "title": "Test Paper"}
        with _feature_on("feed"), patch(_REC_SVC) as M:
            M.return_value.refresh_feed.return_value = [item]
            resp = client.get("/feed/data")
        assert _json(resp)["items"][0]["title"] == "Test Paper"
        item.to_dict.assert_called_once()

    def test_get_feed_normalises_payload_fields(self, client):
        item = MagicMock()
        item.to_dict.return_value = {
            "id": 1,
            "title": "Test Paper",
            "external_id": "doi:10.1000/example",
            "source": "crossref",
            "feed_date": "2026-04-13",
            "dismissed": True,
            "saved": False,
        }
        with _feature_on("feed"), patch(_REC_SVC) as M:
            M.return_value.refresh_feed.return_value = [item]
            resp = client.get("/feed/data")

        payload = _json(resp)["items"][0]
        assert payload["is_dismissed"] is True
        assert payload["is_saved"] is False
        assert payload.get("publication_date") is None
        assert payload["recommended_date"] == "2026-04-13"
        assert payload["url"] == "https://doi.org/10.1000/example"

    def test_refresh_uses_force_true(self, client):
        item = MagicMock()
        item.to_dict.return_value = {"id": 2}
        with _feature_on("feed"), patch(_REC_SVC) as M:
            M.return_value.refresh_feed.return_value = [item]
            resp = client.post("/feed/refresh")
        assert resp.status_code == 200
        call = M.return_value.refresh_feed.call_args
        assert call.kwargs.get("force") is True or (
            len(call.args) > 1 and call.args[1] is True
        )

    def test_dismiss_ok(self, client):
        with _feature_on("feed"), patch(_REC_SVC) as M:
            M.return_value.dismiss_recommendation.return_value = MagicMock()
            resp = client.post("/feed/42/dismiss")
        assert resp.status_code == 200
        assert _json(resp)["ok"] is True

    def test_dismiss_not_found(self, client):
        with _feature_on("feed"), patch(_REC_SVC) as M:
            M.return_value.dismiss_recommendation.side_effect = LookupError()
            resp = client.post("/feed/99/dismiss")
        assert resp.status_code == 404

    def test_save_ok(self, client):
        saved = MagicMock()
        saved.to_dict.return_value = {"id": 7}
        with _feature_on("feed"), patch(_RL_SVC) as M:
            M.return_value.save_recommendation.return_value = saved
            resp = client.post("/feed/7/save")
        assert resp.status_code == 200
        assert _json(resp)["ok"] is True

    def test_save_not_found(self, client):
        with _feature_on("feed"), patch(_RL_SVC) as M:
            M.return_value.save_recommendation.side_effect = LookupError()
            resp = client.post("/feed/999/save")
        assert resp.status_code == 404

    def test_save_to_project_ok(self, client):
        reference = object()
        with _feature_on("feed"), patch(_RL_SVC) as M, patch(
            "app.services.reference_service.reference_to_dict",
            return_value={"id": 5, "title": "Saved Ref"},
        ) as ref_to_dict:
            M.return_value.save_recommendation_to_project.return_value = reference
            resp = client.post(
                "/feed/7/save-to-project",
                data=json.dumps({"project_id": "5"}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert _json(resp)["reference"]["id"] == 5
        args = M.return_value.save_recommendation_to_project.call_args.args
        assert args[1] == 7
        assert args[2] == 5
        ref_to_dict.assert_called_once_with(reference)

    def test_save_to_project_invalid_project_id(self, client):
        with _feature_on("feed"):
            resp = client.post(
                "/feed/7/save-to-project",
                data=json.dumps({"project_id": "abc"}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_audio_summary_streams_base64_audio(self, client):
        with _feature_on("feed"), patch(
            "app.services.audio_summary_service.AudioSummaryService.generate_recommendation_audio_summary"
        ) as generate_audio:
            generate_audio.return_value = {
                "audio_base64": "bXAzLWJ5dGVz",
                "content_type": "audio/mpeg",
            }
            resp = client.get("/feed/7/audio-summary")

        assert resp.status_code == 200
        assert resp.mimetype == "audio/mpeg"
        assert resp.data == b"mp3-bytes"
        args = generate_audio.call_args.args
        assert args[0] == 7

    def test_feature_disabled_404(self, client):
        with patch("app.routes.feed.is_feature_enabled", return_value=False):
            resp = client.get("/feed")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reading list
# ---------------------------------------------------------------------------

class TestReadingListRoutes:

    def test_index_returns_200(self, client):
        with _feature_on("reading_list"):
            resp = client.get("/reading-list")
        assert resp.status_code == 200

    def test_list_empty(self, client):
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.list_items.return_value = []
            resp = client.get("/reading-list/data")
        assert resp.status_code == 200
        assert _json(resp)["items"] == []

    def test_list_serialised(self, client):
        item = MagicMock()
        item.to_dict.return_value = {"id": 1, "title": "Read Me"}
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.list_items.return_value = [item]
            resp = client.get("/reading-list/data")
        assert _json(resp)["items"][0]["title"] == "Read Me"
        item.to_dict.assert_called_once()

    def test_list_normalises_external_url(self, client):
        item = MagicMock()
        item.to_dict.return_value = {
            "id": 1,
            "title": "Read Me",
            "external_id": "pubmed:12345",
            "status": "unread",
            "topic_tags": [],
        }
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.list_items.return_value = [item]
            resp = client.get("/reading-list/data")

        payload = _json(resp)["items"][0]
        assert payload["source"] == "pubmed"
        assert payload["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"

    def test_add_item_ok(self, client):
        created = MagicMock()
        created.to_dict.return_value = {"id": 3, "title": "New Item"}
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.save_item.return_value = created
            resp = client.post(
                "/reading-list",
                data=json.dumps({"title": "New Item"}),
                content_type="application/json",
            )
        assert resp.status_code == 201
        assert _json(resp)["item"]["id"] == 3

    def test_add_item_missing_title(self, client):
        with _feature_on("reading_list"):
            resp = client.post(
                "/reading-list",
                data=json.dumps({}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_update_status_ok(self, client):
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.update_status.return_value = MagicMock()
            resp = client.put(
                "/reading-list/5/status",
                data=json.dumps({"status": "reading"}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert _json(resp)["ok"] is True

    def test_update_status_passes_user_id_first(self, client):
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.update_status.return_value = MagicMock()
            client.put(
                "/reading-list/5/status",
                data=json.dumps({"status": "done"}),
                content_type="application/json",
            )
        args = M.return_value.update_status.call_args.args
        assert args[0] != 5, "user_id must be first arg, not item_id"
        assert args[1] == 5, "item_id must be second arg"

    def test_update_status_invalid(self, client):
        with _feature_on("reading_list"):
            resp = client.put(
                "/reading-list/5/status",
                data=json.dumps({"status": "invalid"}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_update_status_not_found(self, client):
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.update_status.side_effect = LookupError()
            resp = client.put(
                "/reading-list/99/status",
                data=json.dumps({"status": "done"}),
                content_type="application/json",
            )
        assert resp.status_code == 404

    def test_move_to_project_ok(self, client):
        reference = object()
        with _feature_on("reading_list"), patch(_RL_SVC) as M, patch(
            "app.services.reference_service.reference_to_dict",
            return_value={"id": 12, "title": "Moved"},
        ) as ref_to_dict:
            M.return_value.move_to_project.return_value = reference
            resp = client.post(
                "/reading-list/5/move",
                data=json.dumps({"project_id": "12"}),
                content_type="application/json",
            )

        assert resp.status_code == 200
        assert _json(resp)["reference"]["id"] == 12
        args = M.return_value.move_to_project.call_args.args
        assert args[1] == 5
        assert args[2] == 12
        ref_to_dict.assert_called_once_with(reference)

    def test_move_to_project_missing_project_id(self, client):
        with _feature_on("reading_list"):
            resp = client.post(
                "/reading-list/5/move",
                data=json.dumps({}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_move_to_project_invalid_project_id(self, client):
        with _feature_on("reading_list"):
            resp = client.post(
                "/reading-list/5/move",
                data=json.dumps({"project_id": "abc"}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_delete_ok(self, client):
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.delete_item.return_value = None
            resp = client.delete("/reading-list/10")
        assert resp.status_code == 200
        assert _json(resp)["ok"] is True

    def test_delete_not_found(self, client):
        with _feature_on("reading_list"), patch(_RL_SVC) as M:
            M.return_value.delete_item.side_effect = LookupError()
            resp = client.delete("/reading-list/99")
        assert resp.status_code == 404

    def test_feature_disabled_404(self, client):
        with patch("app.routes.reading_list.is_feature_enabled", return_value=False):
            resp = client.get("/reading-list")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

_ALERT_SVC = "app.services.alert_service.AlertService"


class TestAlertsRoutes:

    def test_index_returns_200(self, client):
        with _feature_on("alerts"):
            resp = client.get("/alerts")
        assert resp.status_code == 200

    def test_list_empty(self, client):
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.list_alerts.return_value = []
            resp = client.get("/alerts/data")
        assert resp.status_code == 200
        assert _json(resp)["alerts"] == []

    def test_list_serialised(self, client):
        alert = MagicMock()
        alert.to_dict.return_value = {"id": 1, "title": "Match"}
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.list_alerts.return_value = [alert]
            resp = client.get("/alerts/data")
        assert _json(resp)["alerts"][0]["title"] == "Match"
        alert.to_dict.assert_called_once()

    def test_list_normalises_alert_payload(self, client):
        alert = MagicMock()
        alert.to_dict.return_value = {
            "id": 1,
            "title": "Match",
            "external_id": "arxiv:2401.12345",
            "source": "arxiv",
            "alert_date": "2026-04-13",
            "is_read": False,
        }
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.list_alerts.return_value = [alert]
            resp = client.get("/alerts/data")

        payload = _json(resp)["alerts"][0]
        assert payload["matched_at"] == "2026-04-13"
        assert payload["url"] == "https://arxiv.org/abs/2401.12345"

    def test_unread_count_zero_for_new_user(self, client):
        with _feature_on("alerts"):
            resp = client.get("/alerts/count")
        assert resp.status_code == 200
        assert _json(resp)["count"] == 0

    def test_mark_read_ok(self, client):
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.mark_read.return_value = MagicMock()
            resp = client.post("/alerts/5/read")
        assert resp.status_code == 200
        assert _json(resp)["ok"] is True

    def test_mark_read_user_id_first(self, client):
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.mark_read.return_value = MagicMock()
            client.post("/alerts/5/read")
        args = M.return_value.mark_read.call_args.args
        assert args[1] == 5, "alert_id must be second arg"

    def test_mark_read_not_found(self, client):
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.mark_read.side_effect = LookupError()
            resp = client.post("/alerts/99/read")
        assert resp.status_code == 404

    def test_mark_all_read(self, client):
        with _feature_on("alerts"), patch(_ALERT_SVC) as M:
            M.return_value.mark_all_read.return_value = 4
            resp = client.post("/alerts/mark-all-read")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["ok"] is True
        assert data["updated"] == 4

    def test_feature_disabled_404(self, client):
        with patch("app.routes.alerts.is_feature_enabled", return_value=False):
            resp = client.get("/alerts")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Research interests
# ---------------------------------------------------------------------------

_INT_SVC = "app.services.interest_profile_service.InterestProfileService"


class TestResearchInterestsRoutes:

    def _mock_profile(self):
        p = MagicMock()
        p.declared_topics = []
        p.inferred_topics = []
        p.preferred_sources = []
        p.to_dict.return_value = {"declared_topics": []}
        return p

    def test_index_returns_200(self, client):
        p = self._mock_profile()
        with _feature_on("research_interests"), patch(_INT_SVC) as M:
            M.return_value.get_or_create_profile.return_value = p
            resp = client.get("/settings/research-interests")
        assert resp.status_code == 200

    def test_update_topics_ok(self, client):
        p = self._mock_profile()
        p.to_dict.return_value = {"declared_topics": ["AI", "ML"]}
        with _feature_on("research_interests"), patch(_INT_SVC) as M:
            M.return_value.update_profile.return_value = p
            resp = client.post(
                "/settings/research-interests",
                data=json.dumps({"declared_topics": ["AI", "ML"]}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        assert _json(resp)["ok"] is True
        kw = M.return_value.update_profile.call_args.kwargs
        assert kw.get("declared_topics") == ["AI", "ML"]

    def test_update_sources_ok(self, client):
        p = self._mock_profile()
        with _feature_on("research_interests"), patch(_INT_SVC) as M:
            M.return_value.update_profile.return_value = p
            resp = client.post(
                "/settings/research-interests",
                data=json.dumps({"preferred_sources": ["arxiv"]}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        kw = M.return_value.update_profile.call_args.kwargs
        assert kw.get("preferred_sources") == ["arxiv"]

    def test_invalid_topics_shape(self, client):
        with _feature_on("research_interests"):
            resp = client.post(
                "/settings/research-interests",
                data=json.dumps({"declared_topics": "not-a-list"}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_invalid_sources_shape(self, client):
        with _feature_on("research_interests"):
            resp = client.post(
                "/settings/research-interests",
                data=json.dumps({"preferred_sources": "not-a-list"}),
                content_type="application/json",
            )
        assert resp.status_code == 400

    def test_trigger_inference(self, client):
        with _feature_on("research_interests"), patch(_INT_SVC) as M:
            M.return_value.trigger_inference.return_value = "job-abc"
            resp = client.post("/settings/research-interests/trigger-inference")
        assert resp.status_code == 200
        data = _json(resp)
        assert data["ok"] is True
        assert data["job_id"] == "job-abc"

    def test_feature_disabled_404(self, client):
        with patch(
            "app.routes.research_interests.is_feature_enabled", return_value=False
        ):
            resp = client.get("/settings/research-interests")
        assert resp.status_code == 404


_DOC_REC_SVC = "app.services.recommendation_service.RecommendationService"
_AUDIO_SVC = "app.services.audio_summary_service.AudioSummaryService"


class TestDocumentDiscoveryRoutes:

    def test_related_reading_rejects_invalid_limit(self, client):
        with _app_feature_on(), patch(
            "app.routes.documents._get_project_or_404",
            return_value=SimpleNamespace(id=7, owner_id=22),
        ), patch("app.routes.documents.ResearcherDocument") as D:
            D.query.filter_by.return_value.first_or_404.return_value = SimpleNamespace(id=11)
            resp = client.get(
                "/projects/7/documents/11/related-reading?limit=abc"
            )

        assert resp.status_code == 400

    def test_related_reading_ok(self, client):
        result = SimpleNamespace(
            title="Suggested Paper",
            authors=["A. Author"],
            abstract="Related reading.",
            source="semantic_scholar",
            url="https://example.com/paper",
            publication_date="2024-01-01",
            relevance_score=0.83,
        )

        with _app_feature_on(), patch(
            "app.routes.documents._get_project_or_404",
            return_value=SimpleNamespace(id=7, owner_id=22),
        ), patch("app.routes.documents.ResearcherDocument") as D, patch(_DOC_REC_SVC) as M:
            D.query.filter_by.return_value.first_or_404.return_value = SimpleNamespace(id=11)
            M.return_value.get_related_reading_for_document.return_value = [result]
            resp = client.get("/projects/7/documents/11/related-reading?limit=5")

        assert resp.status_code == 200
        assert _json(resp)["items"][0]["url"] == "https://example.com/paper"
        args = M.return_value.get_related_reading_for_document.call_args.args
        assert args[0] == 11
        assert args[1] == 22
        assert M.return_value.get_related_reading_for_document.call_args.kwargs["limit"] == 5

    def test_audio_summary_streams_audio(self, client):
        with _app_feature_on(), patch(
            "app.routes.documents._get_project_or_404",
            return_value=SimpleNamespace(id=7, owner_id=22),
        ), patch("app.routes.documents.ResearcherDocument") as D, patch(
            "app.services.audio_summary_service.AudioSummaryService.generate_audio_summary"
        ) as generate_audio:
            D.query.filter_by.return_value.first_or_404.return_value = SimpleNamespace(id=11)
            generate_audio.return_value = {"audio": b"mp3-bytes"}
            resp = client.get("/projects/7/documents/11/audio-summary")

        assert resp.status_code == 200
        assert resp.mimetype == "audio/mpeg"
        assert resp.data == b"mp3-bytes"

    def test_audio_summary_streams_base64_audio(self, client):
        with _app_feature_on(), patch(
            "app.routes.documents._get_project_or_404",
            return_value=SimpleNamespace(id=7, owner_id=22),
        ), patch("app.routes.documents.ResearcherDocument") as D, patch(
            "app.services.audio_summary_service.AudioSummaryService.generate_audio_summary"
        ) as generate_audio:
            D.query.filter_by.return_value.first_or_404.return_value = SimpleNamespace(id=11)
            generate_audio.return_value = {
                "audio_base64": "bXAzLWJ5dGVz",
                "content_type": "audio/mpeg",
            }
            resp = client.get("/projects/7/documents/11/audio-summary")

        assert resp.status_code == 200
        assert resp.mimetype == "audio/mpeg"
        assert resp.data == b"mp3-bytes"

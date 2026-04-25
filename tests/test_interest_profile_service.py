from types import SimpleNamespace

from app.services.interest_profile_service import INTEREST_INFERENCE_JOB_TYPE, InterestProfileService


class DummyRecommendationService:
    def __init__(self):
        self.invalidations = []

    def invalidate_user_feed(self, user_id):
        self.invalidations.append(user_id)


class DummyInferenceService:
    def __init__(self):
        self.calls = []

    def update_profile(self, user_id):
        self.calls.append(user_id)
        return [{"topic": "machine learning", "score": 0.95}]


class DummyQueue:
    def __init__(self):
        self.jobs = []

    def create_job(self, **kwargs):
        self.jobs.append(kwargs)
        return SimpleNamespace(job_id="job-123")


def test_get_or_create_profile_defaults(app_context, test_user):
    service = InterestProfileService(
        inference_service=DummyInferenceService(),
        recommendation_service=DummyRecommendationService(),
    )

    profile = service.get_or_create_profile(test_user.id)

    assert profile.user_id == test_user.id
    assert profile.declared_topics == []
    assert profile.preferred_sources == ["semantic_scholar", "pubmed", "arxiv", "crossref"]


def test_update_profile_invalidates_feed_and_can_run_sync(app_context, test_user):
    inference_service = DummyInferenceService()
    recommendation_service = DummyRecommendationService()
    service = InterestProfileService(
        inference_service=inference_service,
        recommendation_service=recommendation_service,
    )

    profile = service.update_profile(
        test_user.id,
        declared_topics=["  Machine Learning  ", "machine learning", "Clinical AI"],
        preferred_sources=["PubMed", "arxiv", "invalid"],
        trigger_inference=True,
        run_async=False,
    )

    assert profile.declared_topics == ["Machine Learning", "Clinical AI"]
    assert profile.preferred_sources == ["pubmed", "arxiv"]
    assert inference_service.calls == [test_user.id]
    assert recommendation_service.invalidations == [test_user.id]


def test_trigger_inference_queues_background_job(app_context, test_user):
    queue = DummyQueue()
    service = InterestProfileService(
        inference_service=DummyInferenceService(),
        recommendation_service=DummyRecommendationService(),
        job_queue_factory=lambda: queue,
    )

    job_id = service.trigger_inference(test_user.id, run_async=True)

    assert job_id == "job-123"
    assert queue.jobs[0]["job_type"] == INTEREST_INFERENCE_JOB_TYPE
    assert queue.jobs[0]["input_data"] == {"user_id": test_user.id}
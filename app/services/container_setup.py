"""Dependency injection container setup.

Registers all services and repositories so they can be resolved
via Container.get() in route handlers.
"""

from __future__ import annotations

from flask import Flask

from app.services.container import Container
from app.extensions import db


def setup_container(app: Flask) -> None:
    """Register all services and repositories in the DI container.

    Called once inside create_app() during app context initialization.
    """
    with app.app_context():
        # ── Repositories ────────────────────────────────────────────────────
        from app.repositories.project_repository import ProjectRepository
        from app.repositories.feed_recommendation_repository import (
            FeedRecommendationRepository,
        )
        from app.repositories.user_repository import UserRepository
        from app.repositories.document_repository import DocumentRepository
        from app.repositories.reference_repository import ReferenceRepository
        from app.repositories.reading_list_repository import ReadingListRepository
        from app.repositories.paper_alert_repository import PaperAlertRepository
        from app.repositories.interest_profile_repository import (
            InterestProfileRepository,
        )
        from app.repositories.synthesis_report_repository import (
            SynthesisReportRepository,
        )
        from app.repositories.auto_extraction_cache_repository import (
            AutoExtractionCacheRepository,
        )
        from app.repositories.knowledge_graph_cache_repository import (
            KnowledgeGraphCacheRepository,
        )

        Container.register(
            ProjectRepository,
            lambda: ProjectRepository(db.session),
        )
        Container.register(
            FeedRecommendationRepository,
            lambda: FeedRecommendationRepository(),
        )
        Container.register(
            UserRepository,
            lambda: UserRepository(),
        )
        Container.register(
            DocumentRepository,
            lambda: DocumentRepository(),
        )
        Container.register(
            ReferenceRepository,
            lambda: ReferenceRepository(),
        )
        Container.register(
            ReadingListRepository,
            lambda: ReadingListRepository(),
        )
        Container.register(
            PaperAlertRepository,
            lambda: PaperAlertRepository(),
        )
        Container.register(
            InterestProfileRepository,
            lambda: InterestProfileRepository(),
        )
        Container.register(
            SynthesisReportRepository,
            lambda: SynthesisReportRepository(),
        )
        Container.register(
            AutoExtractionCacheRepository,
            lambda: AutoExtractionCacheRepository(),
        )
        Container.register(
            KnowledgeGraphCacheRepository,
            lambda: KnowledgeGraphCacheRepository(),
        )

        # ── Services ────────────────────────────────────────────────────────
        from app.services.project_service import ProjectService
        from app.services.recommendation_service import RecommendationService
        from app.services.reading_list_service import ReadingListService
        from app.services.alert_service import AlertService
        from app.services.interest_profile_service import InterestProfileService
        from app.services.smart_import_service import SmartImportService
        from app.services.deduplication_service import DeduplicationService
        from app.services.evidence_synthesis_service import EvidenceSynthesisService
        from app.services.auto_extraction_service import AutoExtractionService
        from app.services.knowledge_graph_service import KnowledgeGraphService

        Container.register(
            ProjectService,
            lambda: ProjectService(Container.get(ProjectRepository)),
        )
        Container.register(
            RecommendationService,
            lambda: RecommendationService(
                feed_repo=Container.get(FeedRecommendationRepository),
            ),
        )
        Container.register(
            ReadingListService,
            lambda: ReadingListService(
                reading_list_repo=Container.get(ReadingListRepository),
                feed_repo=Container.get(FeedRecommendationRepository),
                reference_repo=Container.get(ReferenceRepository),
                project_repo=Container.get(ProjectRepository),
            ),
        )
        Container.register(
            AlertService,
            lambda: AlertService(
                recommendation_service=Container.get(RecommendationService),
                alert_repo=Container.get(PaperAlertRepository),
            ),
        )
        Container.register(
            InterestProfileService,
            lambda: InterestProfileService(
                profile_repo=Container.get(InterestProfileRepository),
                recommendation_service=Container.get(RecommendationService),
            ),
        )
        Container.register(
            SmartImportService,
            lambda: SmartImportService(
                reference_repo=Container.get(ReferenceRepository),
            ),
        )
        Container.register(
            DeduplicationService,
            lambda: DeduplicationService(
                reference_repo=Container.get(ReferenceRepository),
            ),
        )
        Container.register(
            EvidenceSynthesisService,
            lambda: EvidenceSynthesisService(
                report_repo=Container.get(SynthesisReportRepository),
            ),
        )
        Container.register(
            AutoExtractionService,
            lambda: AutoExtractionService(
                cache_repo=Container.get(AutoExtractionCacheRepository),
            ),
        )
        Container.register(
            KnowledgeGraphService,
            lambda: KnowledgeGraphService(
                cache_repo=Container.get(KnowledgeGraphCacheRepository),
            ),
        )

        # ── Singletons (created once, shared everywhere) ────────────────────
        from app.config_manager import config_manager

        Container.register(
            type(config_manager),
            lambda: config_manager,
            singleton=True,
        )

"""Researcher models."""

# Import extraction and plugin models first (dependencies for other models)
from app.models.researcher.researcher_extraction import (
    ExtractionSchema,
    ExtractionResult,
)
from app.models.researcher.extraction_plugins import (
    ExtractionField,
    ExtractedFieldValue,
    ExtractionValidationResult,
)
from app.models.researcher.plugins import (
    Plugin,
    PluginConfiguration,
    PluginHookRegistration,
    PluginValidator,
    PluginExecutionLog,
    PluginRegistry,
)

# Import other core models
from app.models.researcher.researcher_projects import (
    ResearchProject,
    ProjectMember,
    ProjectComment,
    ResearchReportDraft,
)
from app.models.researcher.researcher_documents import ResearcherDocument
from app.models.researcher.document_ingestion import DocumentIngestionState
from app.models.researcher.researcher_coding import (
    Code,
    CodedReference,
    DocumentAnnotation,
)
from app.models.researcher.researcher_chat import ChatSession, ChatMessage
from app.models.researcher.researcher_data import (
    ResearcherDataSource,
    SavedChart,
    ScheduledReport,
)
from app.models.researcher.researcher_training import (
    Flashcard,
    Quiz,
    QuizQuestion,
    QuizAttempt,
)
from app.models.researcher.researcher_tasks import ResearchTask
from app.models.researcher.researcher_notifications import TaskNotification
from app.models.researcher.researcher_references import Reference, DocumentReference
from app.models.researcher.library_sources import (
    LibrarySource,
    SourceConnection,
    SourceImportLog,
)
from app.models.researcher.search_cache import SearchCache, SearchIndex
from app.models.researcher.phase_a_models import (
    ResearchBrief,
    EvidenceItem,
    Claim,
    ClaimEvidence,
    ReviewStep,
    SourceProvenance,
    SynthesisReport,
    RetractionRecord,
)
from app.models.researcher.phase_b_models import (
    RetentionPolicy,
    CompliancePolicyTemplate,
)
from app.models.researcher.sector_models import (
    Hypothesis,
    HypothesisEvidence,
    PlagiarismCheck,
    EvidenceGrade,
    ClauseTemplate,
    CitationValidation,
)
from app.models.researcher.hallucination_audit import HallucinationAuditLog
from app.models.researcher.manuscripts import Manuscript, ManuscriptSection
from app.models.researcher.export_jobs import ExportJob
from app.models.researcher.phase_1_models import (
    ResearchInterestProfile,
    FeedRecommendation,
    ReadingListItem,
    PaperAlert,
)

__all__ = [
    "ResearchProject",
    "ProjectMember",
    "ProjectComment",
    "ResearchReportDraft",
    "ResearcherDocument",
    "DocumentIngestionState",
    "Code",
    "CodedReference",
    "DocumentAnnotation",
    "ChatSession",
    "ChatMessage",
    "ResearcherDataSource",
    "SavedChart",
    "ScheduledReport",
    "ExtractionSchema",
    "ExtractionResult",
    "ExtractionField",
    "ExtractedFieldValue",
    "ExtractionValidationResult",
    "Plugin",
    "PluginConfiguration",
    "PluginHookRegistration",
    "PluginValidator",
    "PluginExecutionLog",
    "PluginRegistry",
    "Flashcard",
    "Quiz",
    "QuizQuestion",
    "QuizAttempt",
    "ResearchTask",
    "Reference",
    "DocumentReference",
    "TaskNotification",
    "LibrarySource",
    "SourceConnection",
    "SourceImportLog",
    "SearchCache",
    "SearchIndex",
    # Phase A
    "ResearchBrief",
    "EvidenceItem",
    "Claim",
    "ClaimEvidence",
    "ReviewStep",
    "SourceProvenance",
    "SynthesisReport",
    "RetractionRecord",
    # Phase B
    "RetentionPolicy",
    "CompliancePolicyTemplate",
    # Phase C
    "Hypothesis",
    "HypothesisEvidence",
    "PlagiarismCheck",
    "EvidenceGrade",
    "ClauseTemplate",
    "CitationValidation",
    # Phase 4 (Anti-Hallucination)
    "HallucinationAuditLog",
    # Phase 04 Writing Studio
    "Manuscript",
    "ManuscriptSection",
    # Phase 05 Collaboration & Export
    "ExportJob",
    # Phase 1 — AI Discovery
    "ResearchInterestProfile",
    "FeedRecommendation",
    "ReadingListItem",
    "PaperAlert",
]

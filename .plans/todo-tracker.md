# Implementation Todo Tracker

Track progress across all 7 phases. Update status as work starts and completes.

**Status key**: `[ ]` not started - `[~]` in progress - `[x]` done - `[!]` blocked

---

## Phase 7 - Admin Document Manager, Quota & Storage Operations
Feature flag: `admin_document_manager_enabled`

Goal: give administrators one website/session-auth service for managing researcher documents, storage backends, storage usage, quota plans, and quota enforcement. Build on the existing `ResearcherDocument`, `PlanTier`, `TenantQuota`, `UserStorageStats`, `quota_service`, storage backend modules, and admin route surface instead of creating a parallel document system.

### Architecture / Ownership
- [ ] Keep canonical admin pages under website/session-auth admin routes, not token/API middleware routes
- [ ] Keep page responsibilities split:
  - [ ] `/admin/documents` = document registry/list and document actions only
  - [ ] `/admin/storage` = storage backend health, configuration summary, and capacity only
  - [ ] `/admin/quota` = quota plans, tenant limits, user overrides, and usage only
  - [~] `/admin/document-manager/jobs` = cleanup, recalculation, archive, and repair jobs only
- [ ] Split implementation by responsibility:
  - [x] `app/routes/admin/admin_documents.py` stays thin and delegates to services
  - [x] `app/routes/admin/admin_storage.py` for storage management pages
  - [x] `app/routes/admin/admin_quotas.py` for quota pages and form handlers
  - [~] `app/services/document_manager_service.py` for admin document operations
  - [~] `app/services/storage/storage_manager_service.py` for backend inspection and storage actions
  - [~] `app/services/quota_service.py` for quota resolution, enforcement, recalculation, and overrides
  - [x] `startup_dependency_bootstrap.py` for stdlib-only requirements install before Flask imports
  - [x] `app/services/startup/dependency_bootstrap.py` for requirements startup checks/install
  - [x] `app/services/startup/database_bootstrap.py` for model import, table creation, migrations, and seed data

### Packages / Startup Dependency Bootstrap
- [x] Treat `requirements.txt` as the package source of truth for app runtime dependencies
- [x] Add required storage/document packages to `requirements.txt` so fresh startup installs the complete document-manager stack:
  - [x] `boto3` for S3-compatible/MinIO storage
  - [x] `azure-storage-blob` for Azure Blob Storage
  - [x] `smbprotocol` for SMB/NAS storage
  - [x] `python-docx`, `xhtml2pdf`, `pypdf`, `openpyxl`, and existing document parsing/export packages
  - [x] `docling[easyocr,rapidocr,htmlrender,onnxruntime,asr,xbrl,vlm,remote-serving]` for structured PDF/DOCX/PPTX/XLSX/HTML/image/audio conversion, OCR, table recognition, reading order, formulas, chart understanding, JSON/Markdown export, ASR, and RAG-ready document structure
  - [x] `pymupdf4llm` and `PyMuPDF` for fast local PDF layout extraction, Markdown/JSON/TXT output, OCR routing, page chunking, and LlamaIndex/LangChain output support
  - [x] `unstructured[all-docs,local-inference]`, `pdfplumber`, `pytesseract`, and `Pillow` for fallback partitioning, OCR, tables, and image/document preprocessing
  - [x] `llama-index-core`, `llama-index-readers-file`, `llama-index-storage-docstore-redis`, and `llama-index-storage-docstore-mongodb` for ingestion pipelines, document hashes, duplicate detection, and upsert-aware document stores
- [~] Implement startup dependency bootstrap:
  - [x] Read and validate `requirements.txt`
  - [x] Detect missing packages before app services start
  - [x] Install missing packages with the active Python executable and `pip`
  - [x] Log installed/missing/failed packages clearly
  - [x] Fail fast when a required package cannot install and the feature depends on it
  - [x] Support an env/config guard such as `AUTO_INSTALL_REQUIREMENTS_ON_STARTUP`
- [x] Add tests for dependency detection without performing real network installs
- [x] Document startup behavior in `docs/DEPLOYMENT_GUIDE.md` and `docs/CONFIGURATION_GUIDE.md`

### Database / Startup Schema Automation
- [x] Replace ad hoc startup DB logic in `run.py` with `database_bootstrap.run_startup_database_updates(app)`
- [x] Ensure startup imports all model modules that define admin document, quota, storage, tenant, user, and integration tables
- [x] Run `db.create_all()` for missing tables in development/bootstrap scenarios
- [x] Run idempotent migration helpers for additive schema changes
- [ ] Add or extend migration coverage for:
  - [x] `plan_tiers`
  - [x] `tenant_quotas`
  - [x] `user_storage_stats`
  - [x] user-level quota override columns
  - [x] tenant plan/quota references
  - [ ] document storage metadata columns (`storage_key`, backend/provider, checksum, content type, deleted/archive timestamps if missing)
  - [x] document RAG sync status columns (`rag_sync_status`, `rag_sync_message`, `rag_synced_at`)
  - [x] document RAG tracking columns (`rag_document_id`, `rag_collection_id`, `rag_content_hash`)
  - [x] document extraction metadata columns/table (`parser_name`, `parser_version`, `extraction_status`, `extraction_quality`, `page_count`, `table_count`, `image_count`, `formula_count`, `chart_count`, `audio_duration_seconds`, `document_hash`, `language`, `extraction_warnings`)
  - [ ] document audit/event tables if new admin actions need immutable history
- [x] Seed default plan tiers on startup: Free, Standard, Enterprise, Custom
- [ ] Seed default storage backend configuration only as typed config/defaults, not JSON behavior
- [x] Add startup health logging for schema version, pending migrations, and seed results
- [x] Add tests that create a blank test DB and verify startup creates required tables/models automatically

### Models
- [ ] Audit existing `ResearcherDocument` fields for admin management needs
- [ ] Extend models only where missing:
  - [ ] `DocumentStorageEvent` for upload, delete, archive, restore, move, backend repair, quota recalculation
  - [ ] `DocumentExtractionRun` for parser, OCR, chunking, hash, quality, warning, and AI Server sync attempt metadata
  - [x] `DocumentIngestionState` for docstore/hash/upsert tracking across Researcher and AI Server
  - [ ] `StorageBackendConfig` only if backend configuration must be persisted by admins
  - [ ] `DocumentRetentionState` only if archive/delete workflow needs separate lifecycle records
- [ ] Keep quota models as the canonical quota source: `PlanTier`, `TenantQuota`, `UserStorageStats`
- [ ] Add typed validators for quota values, max upload sizes, backend names, and storage keys
- [ ] Add `to_dict()` / view DTO helpers only for actual route/UI needs

### Services
- [~] Create `DocumentManagerService`:
  - [~] Paginated admin document search across users, tenants, projects, file types, status, and date range
  - [x] Document detail lookup with owner/project/quota/storage metadata
  - [x] Safe admin delete with backend delete + DB cleanup + quota counter update
  - [~] Required extraction pipeline:
    - [x] Use Docling as the primary parser for PDF, DOCX, PPTX, XLSX, HTML, images, audio, WebVTT, LaTeX, plain text, XBRL, and structured scientific/business documents
    - [~] Enable OCR, table structure recognition, reading order recovery, formulas, code blocks, chart understanding, image classification, JSON export, Markdown export, and RAG-ready document structure
    - [x] Use PyMuPDF4LLM as the fast local PDF parser for Markdown/JSON/TXT output, layout-aware extraction, page chunking, image/vector references, and native-text PDFs
    - [x] Use Unstructured as the fallback partitioner for PDFs, Office documents, email-like content, scanned files, OCR, and table extraction when Docling/PyMuPDF cannot complete
    - [~] OCR routing step that classifies pages as native text vs scanned before invoking heavy OCR
    - [~] Researcher ingestion-state pipeline that stores `doc_id -> document_hash`, detects duplicates/changed documents, and avoids unnecessary AI Server re-index calls
    - [ ] Full LlamaIndex docstore adapter for Redis/Mongo backed ingestion state when external docstores are configured
    - [x] Store extraction quality, parser name/version, page count, table count, image count, audio duration, formula count, chart count, language, document hash, and extraction warnings in document metadata/audit records
    - [ ] Keep advanced parser controls behind `Show Advanced`; normal users only see upload, status, and retry
  - [x] Archive/restore workflow when storage backend supports it
  - [~] Recalculate/repair workflow reloads storage object, reruns extraction, refreshes ingestion state, and retries AI Server sync
  - [~] Bulk delete/archive/recalculate actions through job queue
  - [x] Bulk repair/delete actions are available from admin document management and project document management
  - [~] Audit event creation for every admin action
- [ ] Extend `QuotaService`:
  - [x] Resolve effective quota for user/tenant/plan/global defaults
  - [x] Enforce upload size, document count, and storage usage before uploads
  - [~] Recalculate per-user, per-tenant, and global usage from source document records
  - [x] Per-user, per-tenant, and all-user quota recalculation actions are available from admin quota management
  - [ ] Return admin-friendly usage summaries and percent-used warnings
  - [x] Support admin override with explicit audit event
- [~] Create `StorageManagerService`:
  - [x] Inspect active backend and supported capabilities
  - [~] Check local/S3/Azure/SMB backend health
  - [x] Report used storage, missing DB-backed objects, and size mismatches
  - [x] Repair counters and optionally queue cleanup jobs
  - [x] Keep provider-specific behavior inside backend adapters
- [x] Wire upload/delete flows to `quota_service.check_quota()`, `record_upload()`, and `record_delete()`
- [ ] Publish EventBus events for document admin actions and quota threshold warnings

### AI Server API / RAG Workflow Alignment
- [x] Use canonical AI Server `/v1/rag/documents`, `/v1/rag/query`, and `/v1/rag/documents/{id}` APIs for document indexing, search, and delete
- [x] Keep Beep-specific middleware only for compatibility/orchestration APIs that do not have a standards/canonical route
- [x] Store local `rag_document_id`, `rag_collection_id`, `rag_content_hash`, `rag_sync_status`, `rag_sync_message`, and `rag_synced_at` on `ResearcherDocument`
- [~] Normalize all document creation paths to pass the same stable RAG tracking metadata:
  - [x] User My Documents upload
  - [x] Project document upload API
  - [x] Zotero/reference attachment import
  - [ ] YouTube/video imports if they create `ResearcherDocument`
  - [ ] Future cloud-drive imports
- [ ] Add an AI Server sync-state repair job:
  - [ ] Find local documents whose `rag_sync_status` is stale or failed
  - [ ] Re-index changed documents when `rag_content_hash` differs
  - [ ] Remove AI Server RAG documents when local documents were deleted/archive-purged
  - [ ] Report documents missing from AI Server collection without changing user data automatically
- [ ] Decide ownership boundary for ingestion document-management:
  - [ ] Prefer AI Server as canonical vector/RAG store and Researcher as document metadata/source-of-truth
  - [~] Use required LlamaIndex-style local docstore/upsert semantics for Researcher-side duplicate detection and changed-document detection before calling AI Server
  - [ ] Keep Researcher `rag_document_id` as the cross-system correlation key for all retries, deletes, updates, and audit logs

### Admin Routes
- [~] Improve `GET /admin/documents`:
  - [x] Default compact table/list view
  - [x] Filters for user, tenant, project, file type, status, and date range
  - [x] Sort by created date, size, owner, project, and status
  - [x] Row actions: details, download, recalculate, archive, restore, delete
  - [x] Detail popup or detail page for full metadata
- [~] Add website/session-auth JSON endpoints under admin routes only:
  - [x] `GET /admin/documents/<id>/details`
  - [x] `POST /admin/documents/<id>/recalculate`
  - [x] `POST /admin/documents/<id>/archive`
  - [x] `POST /admin/documents/<id>/restore`
  - [x] `POST /admin/documents/bulk-action`
- [ ] Improve `GET /admin/quota`:
  - [x] Plan tier CRUD
  - [x] Tenant quota CRUD
  - [x] User override CRUD
  - [ ] Usage top lists and warning thresholds
  - [x] Recalculate counters action
- [~] Add `GET /admin/storage`:
  - [x] Active backend summary
  - [x] Backend health check
  - [x] Storage capacity and usage summary
  - [x] Missing object and size mismatch scan results
  - [x] Repair/cleanup action links for scanned consistency issues
  - [x] Add `GET /admin/document-manager/jobs` for document manager operation history

### User Routes
- [x] Add `GET /researcher/documents` for a user-owned document registry across visible projects
- [x] Add `POST /researcher/documents/upload` for user uploads into a selected project
- [x] Upload flow stores the document, updates quota counters, extracts text, and indexes to AI Server RAG when the selected project has a linked collection
- [x] Add user-visible RAG indexing status and retry action per document
- [x] Add project-level document repair action to rerun extraction and retry AI Server indexing from the project document manager

### Templates / UX
- [x] Keep default multi-item lists as rows/tables with optional card/detail view
- [x] Hide backend credentials, raw storage keys, and technical repair controls behind `Show Advanced`
- [ ] Templates:
  - [x] `templates/admin/document_management.html`
  - [x] `templates/admin/document_detail.html` or detail modal partial
  - [x] `templates/admin/quota_management.html`
  - [x] `templates/admin/storage_management.html`
  - [x] `templates/documents/my_documents.html`
  - [ ] `templates/admin/document_manager_jobs.html`
- [ ] JavaScript:
  - [x] `static/js/admin_document_management_page.js`
  - [x] `static/js/admin_quota_management_page.js`
  - [x] `static/js/admin/storage_management.js`
- [ ] CSS:
  - [ ] `static/css/admin/document_manager.css`
- [ ] Empty, loading, success, warning, error, and locked/unauthorized states for every page
- [ ] Mobile-safe layouts for the document and quota tables

### Storage Backends
- [x] Keep `app/services/storage/` as the canonical backend abstraction
- [~] Verify local backend supports delete, exists, size, health, and path safety
- [ ] Verify S3 backend supports delete, exists, metadata, health, and bucket prefix config
- [ ] Verify Azure backend supports delete, exists, metadata, health, and container config
- [ ] Verify SMB backend supports delete, exists, metadata, health, and path safety
- [x] Add backend capability reporting so UI only exposes supported actions
- [ ] Add storage consistency scan:
  - [ ] DB record exists but object missing
  - [ ] Object exists but DB record missing
  - [ ] Size mismatch
  - [ ] Checksum mismatch when checksum exists

### Security / Permissions
- [x] Use `login_required` + `admin_required` / permission decorators for website/admin pages
- [x] Do not use application-token auth for admin website routes
- [ ] Add explicit permissions if RBAC supports them:
  - [ ] `admin.documents.view`
  - [ ] `admin.documents.delete`
  - [ ] `admin.documents.archive`
  - [ ] `admin.quota.manage`
  - [ ] `admin.storage.manage`
- [x] Add audit logs for quota changes, document deletes, archive/restore, and storage repairs
- [x] Prevent path traversal and direct filesystem path exposure in UI
- [ ] Confirm admin delete cannot remove files outside configured storage roots

### Tests
- [x] Unit tests for `DocumentManagerService`
- [x] Unit tests for `StorageManagerService`
- [x] Unit tests for `QuotaService` recalculation and override hierarchy
- [x] Route tests for all admin pages with admin/non-admin users
- [ ] Route tests for locked/forbidden states
- [ ] Startup tests for requirements bootstrap in dry-run mode
- [x] Startup tests for database bootstrap against an empty SQLite DB
- [ ] Integration tests for upload quota enforcement
- [ ] Integration tests for My Documents upload and AI Server RAG sync behavior
- [~] Integration tests for delete/archive updating storage counters
- [ ] Integration tests for storage health and consistency scan
- [x] Regression tests that admin website pages do not call token-only APIs

### Acceptance
- [ ] Fresh checkout startup can install/verify packages from `requirements.txt` when enabled
- [x] Fresh database startup creates/imports all required document, quota, storage, tenant, and user models
- [ ] Admin can list all documents in compact rows and filter by user/project/tenant/status
- [x] User can list and upload their documents from `/researcher/documents`
- [x] User uploads can index extracted document text to AI Server RAG when the project is linked to a collection
- [x] Admin can inspect a document's storage metadata without exposing unsafe filesystem paths
- [x] Admin delete removes the backend object, DB record, and quota usage consistently
- [x] Quota enforcement blocks upload when storage, document count, or max upload size would be exceeded
- [x] Admin can edit plan tiers, tenant quotas, and user overrides
- [x] Admin can recalculate usage counters and see accurate totals after manual DB/storage changes
- [x] Storage health page reports backend availability and consistency scan results
- [x] All destructive admin actions are audited
- [x] All new pages follow one-page/one-business-function and rows-first UX rules



---

## Phase 1 — AI Discovery & Personalised Reading Feed
Feature flag: `ai_discovery_enabled`

### Models
- [ ] `ResearchInterestProfile` — declared + inferred topics per user
- [ ] `FeedRecommendation` — persisted ranked results with user feedback
- [ ] `ReadingListItem` — personal save list separate from project library
- [ ] `PaperAlert` — new-paper alert records

### Services
- [ ] `InterestProfileService` — declared topic CRUD; trigger inference job
- [ ] `InterestInferenceService` — TF-IDF / embedding extraction from user library
- [ ] `RecommendationService` — score + rank candidates; dedup against library
- [ ] Extend `SemanticScholarProvider` — add topic-query and related-paper fetch
- [ ] `ReadingListService` — CRUD on `ReadingListItem`; move-to-project
- [ ] `AlertService` — alert generation, dedup, APScheduler daily job, email digest
- [ ] `AudioSummaryService` — abstract extraction + calls existing `beep_ai_client.text_to_speech()`

### Routes
- [ ] `GET /feed/` — personalised feed page
- [ ] `GET /feed/data` — feed JSON (AJAX)
- [ ] `POST /feed/dismiss` — dismiss recommendation
- [ ] `POST /feed/save` — save to reading list or project
- [ ] `GET /reading-list/` — reading list page
- [ ] `GET /reading-list/data` — reading list JSON (AJAX)
- [ ] `PATCH /reading-list/<id>/status` — update read status
- [ ] `POST /reading-list/<id>/move` — move to project library
- [ ] `DELETE /reading-list/<id>` — remove item
- [ ] `GET /alerts/` — alerts inbox page
- [ ] `POST /alerts/<id>/read` — mark alert read
- [ ] `POST /alerts/mark-all-read` — bulk read
- [ ] `GET /documents/<id>/related-reading` — related papers JSON (wraps existing `related.py`)
- [ ] `GET /documents/<id>/audio-summary` — stream TTS audio
- [ ] `GET /settings/research-interests` — interest profile settings page
- [ ] `POST /settings/research-interests` — save interest profile

### Templates
- [ ] `templates/feed/feed.html`
- [ ] `templates/reading_list/reading_list.html`
- [ ] `templates/alerts/alerts.html`
- [ ] `templates/settings/research_interests.html`
- [ ] `templates/project/document_detail.html` — hub extension (related reading + flashcard panels)

### JS / CSS
- [ ] `static/js/feed/feed.js` + `static/css/feed/feed.css`
- [ ] `static/js/reading_list/reading_list.js` + `static/css/reading_list/reading_list.css`
- [ ] `static/js/alerts/alerts.js`
- [ ] `static/js/settings/research_interests.js`
- [ ] `static/js/project/document_detail_ai_panels.js` + `static/css/project/document_detail_ai_panels.css`

### Migration
- [ ] Alembic migration for: `ResearchInterestProfile`, `FeedRecommendation`, `ReadingListItem`, `PaperAlert`

### Acceptance
- [ ] Researcher can declare ≥ 1 topic and see a feed on `/feed/`
- [ ] Feed deduplicates against existing library by DOI
- [ ] "Not interested" dismissal removes paper from current + future feeds
- [ ] Reading list persists across sessions
- [ ] Daily alert job runs without blocking request thread
- [ ] Audio summary streams without page reload
- [ ] Related-reading panel loads async < 500 ms
- [ ] All new pages pass keyboard nav + mobile
- [ ] `ai_discovery_enabled=False` hides all new routes cleanly

---

## Phase 2 — Evidence Synthesis Engine
Feature flag: `evidence_synthesis_enabled`

> **Reuse**: `phase_a_models.py` (`ResearchBrief`, `EvidenceItem`, `Claim`, `ClaimEvidence`) · `overlap_checker_service.py` · `HallucinationAuditLog` · `EvidenceGrade`

### Models
- [ ] `SynthesisReport` — persisted synthesis (query, answer, citations JSON, scores)
- [ ] `RetractionRecord` — DOI-indexed retraction metadata with acknowledgement status

### Services
- [ ] `EvidenceSynthesisService` — orchestrate retrieval → assembly → LLM → labelling
- [ ] `PolarityClassifier` — classify each evidence snippet (supporting / contradicting / mentioning)
- [ ] `LiteratureReviewDraftService` — multi-step: cluster → draft sections → assemble
- [ ] `RetractionAlertService` — DOI checks, record creation, alert dispatch
- [ ] `RetractionWatchAdapter` — HTTP adapter for Crossref + Retraction Watch APIs

### Routes
- [ ] `GET /synthesis/` — synthesis main page
- [ ] `POST /synthesis/query` — submit research question; returns job ID
- [ ] `GET /synthesis/<id>` — view synthesis report
- [ ] `GET /synthesis/<id>/evidence` — evidence table JSON
- [ ] `POST /synthesis/<id>/evidence/<row>/flag` — flag incorrect polarity label
- [ ] `POST /synthesis/literature-review` — start literature review draft
- [ ] `GET /synthesis/<id>/export` — export as PDF
- [ ] `POST /synthesis/<id>/send-to-manuscript` — create manuscript sections from draft
- [ ] `GET /projects/<pid>/hypotheses/<hid>/synthesis` — hypothesis synthesis result
- [ ] `POST /projects/<pid>/hypotheses/<hid>/synthesise` — trigger hypothesis synthesis

### Templates
- [ ] `templates/synthesis/synthesis.html`
- [ ] `templates/synthesis/report.html`
- [ ] `templates/project/references.html` — hub extension for AI toolbar (shared with Phase 6)

### JS / CSS
- [ ] `static/js/synthesis/synthesis.js` + `static/css/synthesis/synthesis.css`
- [ ] `static/js/synthesis/report.js`
- [ ] `static/js/project/references_ai_toolbar.js` (shared with Phase 6)

### Migration
- [ ] Alembic migration for: `SynthesisReport`, `RetractionRecord`

### Acceptance
- [ ] Submitting a research question returns a grounded answer with ≥ 1 citation
- [ ] Every claim links to a source document
- [ ] Evidence table shows stance badge (green/red/grey) for each row
- [ ] Table sorting by stance/year works client-side
- [ ] Literature review draft produces ≥ 2 thematic sections + 1 gap section
- [ ] "Send to Writing Studio" creates correct manuscript sections
- [ ] Retraction badge appears for DOI that hits Retraction Watch
- [ ] Streaming response shows incremental output
- [ ] `evidence_synthesis_enabled=False` returns 404 for all synthesis routes

---

## Phase 3 — Visual Knowledge Mapping
Feature flag: `knowledge_map_enabled`

> **Preserved**: `routes/document_map.py` `GET /<pid>/map` + `document_map.html` (code/doc bipartite) — untouched

### Models
- [ ] `KnowledgeGraphCache` — serialised graph JSON per (user, project, date); status field

### Services
- [ ] `KnowledgeGraphService` — build nodes/edges; assign clusters; node expansion
- [ ] `SemanticScholarCitationAdapter` — fetch citation + reference lists
- [ ] `ClusteringService` — K-Means over embeddings; top-term labelling

### Routes  (`knowledge_map.py` — new route file)
- [ ] `GET /knowledge-map` — global citation map page
- [ ] `GET /knowledge-map/data` — global graph JSON
- [ ] `GET /projects/<pid>/knowledge-map` — project citation map page
- [ ] `GET /projects/<pid>/knowledge-map/data` — project graph JSON (async)
- [ ] `POST /projects/<pid>/knowledge-map/expand` — expand node (fetch neighbours)
- [ ] `POST /projects/<pid>/knowledge-map/add-node` — add ghost node to library
- [ ] `GET /projects/<pid>/knowledge-map/export` — export graph image

### Templates
- [ ] `templates/knowledge_map/knowledge_map.html`
- [ ] `templates/knowledge_map/global_map.html`

### JS / CSS
- [ ] `static/js/knowledge_map/knowledge_map.js` + `static/css/knowledge_map/knowledge_map.css`

### Migration
- [ ] Alembic migration for: `KnowledgeGraphCache`

### Acceptance
- [ ] Project with ≥ 2 papers renders a visible graph
- [ ] Citation edges from Semantic Scholar appear within 10 s
- [ ] Ghost nodes appear for papers citing library papers not yet in library
- [ ] "Add to library" from graph creates `ReadingListItem` without page reload
- [ ] Topic clusters appear as coloured hulls with keyword labels
- [ ] Timeline layout places papers in correct year lanes
- [ ] Year slider filters in < 100 ms (client-side)
- [ ] Graph exports as PNG with all visible nodes
- [ ] Graphs > 500 nodes are thinned server-side before delivery
- [ ] `knowledge_map_enabled=False` returns 404 for all graph routes

---

## Phase 4 — AI Writing Assistant
Feature flag: `writing_assistant_enabled`

> **Preserved**: `report_writing.py` (11 assist actions, `format-citations`, `citation-scan`, `overlap-check`) · `training.py` (flashcards + quizzes) · `overlap_checker_service.py`
> **Report template**: `templates/project/report.html` (NOT manuscripts.html — that file does not exist)

### Models
- [ ] `AutoExtractionCache` — one per document; caches summary, findings, tables JSON

### Model changes
- [ ] `ManuscriptSection` — add `last_quality_score FLOAT NULLABLE` column

### Services
- [ ] `WritingQualityService` — LLM-based scoring; issue extraction; fix application
- [ ] `FlashcardGenerationService` — chunk → LLM → dedup → flashcard creation (wraps existing `training.py` endpoint)
- [ ] `AutoExtractionService` — summary + key findings + data table extraction per document
- [ ] `CitationDraftService` — themed paragraph draft; delegates citation lookup to existing `POST /<pid>/writing/citations`
- [ ] `ReadabilityService` — rule-based passive/hedge/length metrics (no LLM)

### Routes  (in existing files — NOT new route files)
- [ ] `POST /<pid>/writing/analyse` — writing quality analysis JSON → add to **`report_writing.py`**
- [ ] `POST /manuscripts/<mid>/sections/<sid>/apply-fix` → **`manuscripts.py`**
- [ ] `GET /manuscripts/<mid>/sections/<sid>/readability` → **`manuscripts.py`**
- [ ] `POST /manuscripts/<mid>/sections/<sid>/citation-draft` → **`manuscripts.py`**
- [ ] `POST /manuscripts/<mid>/sections/<sid>/insert-draft` → **`manuscripts.py`**
- [ ] `POST /documents/<id>/generate-flashcards` → **`documents.py`**
- [ ] `POST /documents/<id>/save-flashcards` → **`documents.py`**
- [ ] `GET /documents/<id>/auto-extract` → **`documents.py`**
- [ ] `POST /documents/<id>/finding-to-extraction` → **`documents.py`**

### Templates (extensions only — no new top-level template files)
- [ ] `templates/project/report.html` — add analyse toolbar row, annotation overlay, readability panel
- [ ] `templates/project/document_detail.html` — add auto-extract panel + flashcard preview panel

### JS / CSS
- [ ] `static/js/project/writing_assistant.js` + `static/css/project/writing_assistant.css`
- [ ] `static/js/project/document_detail_ai_panels.js` + `static/css/project/document_detail_ai_panels.css` (shared with Phase 1)

### Migration
- [ ] Alembic migration for: `AutoExtractionCache`, `ManuscriptSection.last_quality_score`

### Acceptance
- [ ] Analysing a section returns overall score + ≥ 1 issue if text is unpolished
- [ ] "Apply fix" patches section content at correct offset without corrupting surrounding text
- [ ] Quick flashcard generation from abstract produces 4–6 flashcards in < 5 s
- [ ] Auto-extract returns summary + ≥ 1 finding for any real PDF
- [ ] Cache prevents re-extraction on second request for the same document
- [ ] Citation draft markers convert correctly to APA/MLA on insertion
- [ ] Readability panel passive-voice % is correct for known test sentences
- [ ] Section content is never modified unless user explicitly accepts a fix
- [ ] `writing_assistant_enabled=False` returns 404 for all new routes

---

## Phase 5 — Researcher Social Network
Feature flag: `social_network_enabled`

> **Foundation**: `routes/collaboration.py` · `ProjectMember` · `ResearchTask` / `TaskNotification` · `Quiz`/`Flashcard` · `static/js/profile.js` + `templates/profile.html` (partial scaffold)

### Models
- [ ] `ResearcherProfile` — display name, bio, ORCID, institution, visibility, metrics flags
- [ ] `Follow` — `(follower_id, followee_user_id NULLABLE, followee_project_id NULLABLE)`
- [ ] `ActivityEvent` — actor user FK, event_type, payload JSON, visibility
- [ ] `CitationCountCache` — DOI-indexed external citation count with fetch timestamp

### Services
- [ ] `ProfileService` — CRUD; visibility enforcement; metric aggregation
- [ ] `FollowService` — follow/unfollow; list followers; permission checks
- [ ] `ImpactMetricsService` — aggregate library/collab metrics; external citation counts
- [ ] `ActivityFeedService` — event creation; feed query; pagination

### Routes  (`social.py` + `profile.py` — new route files)
- [ ] `GET /researchers/<username>` — public researcher profile
- [ ] `GET /settings/profile` — edit profile page
- [ ] `POST /settings/profile` — save profile
- [ ] `POST /researchers/<username>/follow` — follow researcher
- [ ] `DELETE /researchers/<username>/follow` — unfollow researcher
- [ ] `POST /projects/<pid>/follow` — follow project
- [ ] `DELETE /projects/<pid>/follow` — unfollow project
- [ ] `GET /network/` — activity feed page
- [ ] `GET /network/data` — paginated activity JSON
- [ ] `GET /profile/impact` — impact dashboard page
- [ ] `GET /profile/impact/data` — metrics JSON
- [ ] `GET /profile/network-data` — collaboration graph JSON

### Templates
- [ ] `templates/social/researcher_profile.html`
- [ ] `templates/social/network_feed.html`
- [ ] `templates/social/impact_dashboard.html`
- [ ] `templates/settings/profile.html` — extends / replaces partial `profile.html` scaffold

### JS / CSS
- [ ] `static/js/social/researcher_profile.js` + `static/css/social/researcher_profile.css`
- [ ] `static/js/social/network_feed.js`
- [ ] `static/js/social/impact_dashboard.js` + `static/css/social/impact_dashboard.css`
- [ ] `static/js/settings/profile.js`

### Migration
- [ ] Alembic migration for: `ResearcherProfile`, `Follow`, `ActivityEvent`, `CitationCountCache`

### Acceptance
- [ ] Private profile is invisible to all other users (returns 404)
- [ ] Platform-only profile is visible to logged-in users but 404 to unauthenticated
- [ ] Following a researcher adds their events to follower's activity feed
- [ ] Activity feed is paginated ≤ 50 events per page
- [ ] Impact dashboard paper count matches `ResearcherDocument` records
- [ ] External citation count is cached and not re-fetched within 7 days
- [ ] Collaboration network graph loads in < 2 s for < 50 collaborators
- [ ] No social data is created until user opts in via Settings → Profile
- [ ] `social_network_enabled=False` returns 404 for all social routes

---

## Phase 6 — Citation Intelligence
Feature flag: `citation_intelligence_enabled`

> **Preserved**: reference CRUD · Zotero sync · `citation_formatter_service.py` (4 styles) · `reference_import_service.py` dedup logic
> **Reuse**: `youtube_ingester_service.py` · `video_summary_service.py` · `library_sources.py` models

### Models
- [ ] `CitationContextRecord` — citing DOI, cited DOI, snippet, intent, polarity, score
- [ ] `DuplicateMergeLog` — kept ID, removed ID, merge timestamp, reversal payload

### Model changes
- [ ] `ResearchProject` — add `citation_style TEXT NULLABLE` column

### Services
- [ ] `SmartImportService` — detect identifier type; route to existing providers; conflict check
- [ ] `CitationContextService` — Semantic Scholar context fetch + polarity classify
- [ ] `DeduplicationService` — surface existing `reference_import_service` dedup logic; cascaded merge; merge log
- [ ] `LibraryAnalyticsService` — usage scoring; coverage map; growth chart data
- [ ] Extend `CrossRefProvider` — add `fetch_by_doi(doi)` method
- [ ] Extend `PubMedProvider` — add `fetch_by_pmid(pmid)` method
- [ ] Extend `ArxivProvider` — add `fetch_by_id(arxiv_id)` method
- [ ] Extend `SemanticScholarProvider` — add `fetch_by_id(id)` + citation-list methods
- [ ] Extend `CitationFormatterService` — add CSL engine; expand to 50+ styles
- [ ] Extend `BibliographyService` — add DOCX output
- [ ] Add `LibrarySource` admin routes — management UI for the existing `LibrarySource` model
- [ ] Add `youtube_ingester_service` entry-point route — expose existing service via document-creation route

### Routes  (in `references.py` or new `citation_intelligence.py`)
- [ ] `POST /references/smart-import` — resolve single identifier preview
- [ ] `POST /references/bulk-import` — bulk identifier import
- [ ] `GET /references/<id>/citation-context` — how-it's-cited panel JSON
- [ ] `POST /references/<id>/refresh-context` — trigger context refresh
- [ ] `GET /references/citation-styles` — available CSL styles
- [ ] `POST /projects/<pid>/references/export-bibliography` — styled bibliography export
- [ ] `GET /projects/<pid>/references/duplicates` — duplicate pairs JSON
- [ ] `POST /projects/<pid>/references/merge` — execute merge
- [ ] `POST /projects/<pid>/references/dismiss-duplicate` — dismiss pair
- [ ] `GET /references/analytics` — library analytics page
- [ ] `GET /references/analytics/data` — analytics JSON

### Templates
- [ ] `templates/project/references.html` — hub extension (smart import drawer, dedup toolbar, analytics link)
- [ ] `templates/references/citation_context.html`
- [ ] `templates/references/analytics.html`

### JS / CSS
- [ ] `static/js/project/references_ai_toolbar.js` (shared with Phase 2)
- [ ] `static/js/references/citation_context.js`
- [ ] `static/js/references/analytics.js` + `static/css/references/analytics.css`

### Migration
- [ ] Alembic migration for: `CitationContextRecord`, `DuplicateMergeLog`, `ResearchProject.citation_style`

### Acceptance
- [ ] Pasting a valid DOI autofills all reference fields within 2 s
- [ ] Duplicate warning shows before saving a DOI already in library
- [ ] Bulk import of 20 DOIs completes and reports per-item success/failure
- [ ] "How it's cited" tab shows ≥ 1 context record for a well-cited DOI
- [ ] Dedup detects exact-DOI and high-title-similarity pairs
- [ ] Merge re-points all `CodedReference` records to the surviving reference
- [ ] Merged reference can be identified for reversal within 30 days via merge log
- [ ] Bibliography export in APA, MLA, Chicago, and IEEE all produce valid output
- [ ] `citation_intelligence_enabled=False` returns 404 for all new routes

---

## Cross-Phase Shared Deliverables

These items are created once and shared across phases.

- [ ] `templates/project/document_detail.html` — hub template with panels for Phases 1 + 4
- [ ] `static/js/project/document_detail_ai_panels.js` + CSS — shared by Phases 1 + 4
- [ ] `static/js/project/references_ai_toolbar.js` — shared by Phases 2 + 6
- [ ] Nav additions in `templates/base.html` — Feed, Synthesis, Knowledge Map (feature-flag-gated)
- [ ] Settings nav additions — Research Interests (P1), Public Profile + Following (P5), Chunk Templates

---

## Alembic Migrations Summary

| Phase | Models requiring migration |
|---|---|
| 1 | `ResearchInterestProfile`, `FeedRecommendation`, `ReadingListItem`, `PaperAlert` |
| 2 | `SynthesisReport`, `RetractionRecord` |
| 3 | `KnowledgeGraphCache` |
| 4 | `AutoExtractionCache`, `ManuscriptSection.last_quality_score` |
| 5 | `ResearcherProfile`, `Follow`, `ActivityEvent`, `CitationCountCache` |
| 6 | `CitationContextRecord`, `DuplicateMergeLog`, `ResearchProject.citation_style` |

---

*Last updated: 2026-05-01*

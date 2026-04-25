# Implementation Todo Tracker

Track progress across all 6 phases. Update status as work starts and completes.

**Status key**: `[ ]` not started · `[~]` in progress · `[x]` done · `[!]` blocked

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

*Last updated: 2026-04-13*

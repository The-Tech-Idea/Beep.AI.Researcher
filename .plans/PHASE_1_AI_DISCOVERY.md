# Phase 1 — AI Discovery & Personalised Reading Feed

> **Feature flag**: `ai_discovery_enabled`
> **Inspired by**: R Discovery, Research Rabbit, Keenious
> **Depends on**: None (base phase)
> **Unlocks**: Phase 3 (knowledge graph edges), Phase 6 (library enrichment)
>
> **Existing features preserved (do NOT touch)**:
> - `routes/data_analyst.py` + `templates/project/data.html` — Julius-style data upload,
>   chart generator, AI chat with dataset. Phase 1 is about **paper discovery**, not data analysis.
>   These are completely separate features.
> - `routes/stats.py` + `templates/project/stats.html` — SPSS-style stats (describe/crosstab/regression).
>   Phase 1 does NOT add quantitative analysis; those pages exist and are fully functional.
> - `routes/global_chat.py` `POST /api/chat` — global AI assistant without project context.
>   Phase 1's personalised feed is NOT a chat replacement; both coexist.

---

## 1. Goal

Give every researcher a personalised feed of papers they did not know they
needed. Replace the passive "I'll search when I need something" workflow with
active discovery that meets researchers where they are.

A researcher opens the app and sees papers matched to their interests, derived
from their reading history and explicit preferences — no manual curation needed.

---

## 2. Features

### 2.1 Research Interest Profile

A user-owned profile that records declared and inferred research interests.

**User actions**
- Declare up to 20 topics on first use (onboarding wizard step).
- Edit declared topics at any time from Settings → Research Interests.
- See inferred topics derived from their document library and search history.
- Opt out of inference per-topic.

**System behaviour**
- After each document upload and each search, the system re-scores topics.
- Inference uses TF-IDF over document abstracts stored already in `ResearcherDocument`.
- Inferred topics are stored separately from declared ones; they never overwrite user text.

**Architecture**
- New model: `ResearchInterestProfile` (one per user, FK to `User`).
- New service: `InterestProfileService` — declared CRUD + inference trigger.
- Inference is a background task via the existing `job_scheduler`; no synchronous cost.

### 2.2 Personalised Reading Feed

A ranked list of paper recommendations displayed on a dedicated Feed page.

**User actions**
- View feed showing up to 50 ranked papers.
- Each card shows: title, authors, abstract snippet, match reason, source badge.
- One-click save to project library or personal reading list.
- Mark a paper as "not interested" (hides it and nudges the model).
- Filter feed by source (PubMed, arXiv, Crossref, Semantic Scholar).
- Refresh feed manually; auto-refreshed daily by scheduler.

**System behaviour**
- Recommendation pipeline:
  1. Fetch candidate papers from existing search adapters using interest topics.
  2. Score each candidate against the full interest profile (cosine similarity via existing sentence-transformer infrastructure in Beep.AI.Server).
  3. Deduplicate against the user's existing library (match on DOI).
  4. Rank by score, recency-adjusted (decay function penalises papers >3 years old).
  5. Cache result for 24 h; invalidate on interest profile change.
- "Not interested" signals are stored and used to filter future candidates.

**Architecture**
- New service: `RecommendationService` — single responsibility: rank a list of candidates.
- New adapter: `SemanticScholarAdapter` — **already exists** as `SemanticScholarProvider` at
  `app/integrations/search/providers/semantic_scholar.py`; extend with topic-query and
  recommendation-specific methods rather than creating a new file.
- Existing adapters (PubMed, arXiv, Crossref) are already implemented in
  `app/integrations/search/providers/`; extend each with a topic-query mode.
- New model: `FeedRecommendation` — persisted ranked results with feedback signal.
- New model: `ReadingListItem` — user's personal save list (separate from project library).
- Route: `GET /feed/` — returns personalised feed page.
- Route: `POST /feed/dismiss` — records "not interested".
- Route: `POST /feed/save` — saves to reading list or project library.

### 2.3 Reading List

A lightweight personal library separate from project-linked references.

**User actions**
- View all saved papers in a flat list (not tied to any project).
- Move a reading list item into a project library.
- Mark items as read / unread.
- Filter by read status, topic tag, source.
- Delete items.

**Architecture**
- `ReadingListItem` model: FK to `User`, optional FK to `Reference`, stores
  external_id (DOI/arXiv), status enum (`unread | reading | done`).
- Service: `ReadingListService` — CRUD, status updates, move-to-project.
- Route: `GET /reading-list/` — list page.
- Route: `PATCH /reading-list/<id>/status` — update read status.
- Route: `POST /reading-list/<id>/move` — move to project.

### 2.4 New Paper Alerts

Background alerting when papers matching a researcher's interests are published.

**User actions**
- Toggle alerts on/off in Settings → Alerts.
- Set alerting frequency: daily digest, weekly digest, or none.
- See alerts collected in a dedicated Alerts inbox.
- Click an alert to open the paper and save it.

**System behaviour**
- Scheduler job runs at configured frequency, generates recommendations, and only
  surfaces papers not seen before by the user.
- Alert records stored in `PaperAlert` model.
- Digest email sent through the existing notification stack.

**Architecture**
- New model: `PaperAlert` — FK to `User`, stores external_id, timestamp, read flag.
- New service: `AlertService` — alert generation, deduplication, email trigger.
- Scheduler job: `paper_alert_job` registered with `job_scheduler`.
- Route: `GET /alerts/` — alert inbox page.
- Route: `POST /alerts/<id>/read` — mark as read.

### 2.5 "Readers Also Read" Recommendations

On any document or reference detail page, show a panel of papers that co-readers
(or co-citation patterns) suggest are related.

**User actions**
- See a sidebar panel "Readers also read" on any document page.
- Click a recommendation to view abstract or save.
- Dismiss individual suggestions.

**System behaviour**
- Initial implementation: content-based (similar abstract embedding).
- Future: can be upgraded to collaborative filtering once enough users exist.
- Panel loaded asynchronously after page load to avoid blocking.

**Architecture**
> **Existing foundation**: `routes/related.py` already provides
> `GET /<pid>/documents/<did>/related` — Jaccard/LLM similarity within a project.
> Phase 1 's "Related Reading" panel calls this **existing endpoint** for in-library results
> and extends it to include Semantic Scholar recommendations for papers not yet in the library.
> No new similarity algorithm is added for the in-library case.
- Extended API endpoint: `GET /documents/<id>/related-reading` — wrapper that calls
  existing `related.py` logic for in-library papers, then augments with external
  `SemanticScholarProvider` results for out-of-library candidates.
- `RecommendationService` wraps both sources; returns uniform `PaperRecommendation` list.
- Frontend: small JS panel injected into existing document detail page.

### 2.6 Text-to-Speech (Listen Mode)

Allow researchers to listen to a paper's abstract and key sections while away
from screen.

**User actions**
- Press "Listen" on any document card or detail page.
- Control playback (play, pause, skip section).
- Choose reading speed.

**System behaviour**
- Delegates to the existing Beep.AI.Server TTS service via `BeepAIClient`.
  `beep_ai_client.text_to_speech()` **already exists** in
  `app/services/beep_ai_client.py`; this phase adds the route + audio summary layer
  on top of it.
- Streams audio; does not store audio files.
- Only abstract + extracted key findings sent to TTS (not full body) to control cost.

**Architecture**
- Route: `GET /documents/<id>/audio-summary` — streams audio from server TTS.
- New service: `AudioSummaryService` — extracts abstract + key findings, calls the
  **existing** `beep_ai_client.text_to_speech()` method.
- Frontend: minimal HTML5 audio player, no heavy library.

---

## 3. New Models

### `ResearchInterestProfile`
```
id              INTEGER PK
user_id         INTEGER FK(user.id) UNIQUE NOT NULL
declared_topics JSON NOT NULL DEFAULT '[]'
inferred_topics JSON NOT NULL DEFAULT '[]'
preferred_sources JSON NOT NULL DEFAULT '[]'
updated_at      DATETIME NOT NULL
inference_enabled BOOLEAN NOT NULL DEFAULT TRUE
```
Migration: `add_research_interest_profile`

### `FeedRecommendation`
```
id              INTEGER PK
user_id         INTEGER FK(user.id) NOT NULL
external_id     TEXT NOT NULL        -- DOI or arXiv ID
title           TEXT NOT NULL
authors         JSON NOT NULL DEFAULT '[]'
abstract        TEXT
source          TEXT NOT NULL        -- 'pubmed' | 'arxiv' | 'semantic_scholar'
relevance_score FLOAT NOT NULL
reason          TEXT
dismissed       BOOLEAN NOT NULL DEFAULT FALSE
saved           BOOLEAN NOT NULL DEFAULT FALSE
feed_date       DATE NOT NULL
created_at      DATETIME NOT NULL
```
Index: `(user_id, feed_date, dismissed)`

### `ReadingListItem`
```
id              INTEGER PK
user_id         INTEGER FK(user.id) NOT NULL
reference_id    INTEGER FK(reference.id) NULLABLE
external_id     TEXT                 -- DOI/arXiv if not yet in library
title           TEXT NOT NULL
status          TEXT NOT NULL DEFAULT 'unread'  -- unread|reading|done
topic_tags      JSON NOT NULL DEFAULT '[]'
saved_at        DATETIME NOT NULL
updated_at      DATETIME NOT NULL
```
Index: `(user_id, status)`

### `PaperAlert`
```
id              INTEGER PK
user_id         INTEGER FK(user.id) NOT NULL
external_id     TEXT NOT NULL
title           TEXT NOT NULL
source          TEXT NOT NULL
is_read         BOOLEAN NOT NULL DEFAULT FALSE
alert_date      DATE NOT NULL
created_at      DATETIME NOT NULL
```
Index: `(user_id, is_read, alert_date)`

---

## 4. New Services

| Service | Responsibilities |
|---|---|
| `InterestProfileService` | Declared topic CRUD; trigger inference job |
| `InterestInferenceService` | TF-IDF / embedding extraction from user's library |
| `RecommendationService` | Score + rank candidates; dedup against library |
| *(extend)* `SemanticScholarProvider` | Add topic-query and related-paper fetch methods |
| `ReadingListService` | CRUD on ReadingListItem; move-to-project |
| `AlertService` | Alert generation, dedup, email digests |
| `AudioSummaryService` | Abstract extraction + calls **existing** `beep_ai_client.text_to_speech()` |

---

## RAG / Chunk Template Notes

**Personal library collection** must use the `system-parent-child` chunk template
(slug `system-parent-child`). Small child chunks give precise recall for feed
scoring; the larger parent chunk is returned as reading context to the LLM.

Create the per-user collection once on first `/feed/` load:
```python
ok, templates = beep_ai_client.list_chunk_templates()
slug_map = {t["slug"]: t["template_id"] for t in templates}

ok, coll = beep_ai_client.create_rag_collection(
    name=f"personal_library_{user_id}",
    user_id=str(user_id),
    is_public=False,
    chunk_template_id=slug_map["system-parent-child"],
)
```

Embeddings for interest scoring (`InterestInferenceService`) call
`beep_ai_client.get_embeddings(texts)` (the **new** method described in
`MODEL.md` section 9.4) — do **not** run sentence-transformers locally.

> **Custom templates**: Users can swap the personal library collection to any
> built-in or user-created template via `Settings → Chunk Templates`. See
> `MODEL.md` section 9.10 for the full customisation design.

---

## 5. New Routes

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/feed/` | Personalised feed page |
| `GET` | `/feed/data` | JSON feed data (AJAX) |
| `POST` | `/feed/dismiss` | Dismiss a recommendation |
| `POST` | `/feed/save` | Save recommendation to reading list or project |
| `GET` | `/reading-list/` | Reading list page |
| `GET` | `/reading-list/data` | JSON reading list (AJAX) |
| `PATCH` | `/reading-list/<id>/status` | Update read status |
| `POST` | `/reading-list/<id>/move` | Move to project library |
| `DELETE` | `/reading-list/<id>` | Remove item |
| `GET` | `/alerts/` | Alerts inbox page |
| `POST` | `/alerts/<id>/read` | Mark alert as read |
| `POST` | `/alerts/mark-all-read` | Bulk read |
| `GET` | `/documents/<id>/related-reading` | Related papers JSON |
| `GET` | `/documents/<id>/audio-summary` | Stream TTS audio |
| `GET` | `/settings/research-interests` | Interest profile settings page |
| `POST` | `/settings/research-interests` | Save interest profile |

---

## 6. UI Design

> See **MODEL.md §10** for the global nav changes, hub architecture, shared components, and the full file inventory.
> This section covers the interaction design unique to Phase 1.

### 6.1 File Pairs

| Template | JS | CSS |
|---|---|---|
| `templates/feed/feed.html` | `static/js/feed/feed.js` | `static/css/feed/feed.css` |
| `templates/reading_list/reading_list.html` | `static/js/reading_list/reading_list.js` | `static/css/reading_list/reading_list.css` |
| `templates/alerts/alerts.html` | `static/js/alerts/alerts.js` | *(shared theme)* |
| `templates/settings/research_interests.html` | `static/js/settings/research_interests.js` | *(shared theme)* |
| *(hub extension)* `templates/project/document_detail.html` | `static/js/project/document_detail_ai_panels.js` | `static/css/project/document_detail_ai_panels.css` |

### 6.2 Feed Page (`/feed/`)

**Layout**: single-column card list; filter chips at top (All / Unread / Saved / By Source).

**PaperCard anatomy** (reused from `static/js/components/paper_card.js`):
```
+------------------------------------------+
| [SourceBadge]  Title                     |
| Authors · Journal · Year                 |
| Match reason pill: "based on Topic X"    |
| Abstract snippet (2 lines, expandable)   |
| [Save v] [Dismiss] [Listen] [...]        |
+------------------------------------------+
```
- **Save ▾** — dropdown: "Save to Reading List" (default), "Save to Project…" (opens project picker modal).
- **Dismiss** — hides the card; queues negative signal for recommendation engine.
- **Listen** — triggers `POST /documents/<id>/audio-summary` (streaming); inline mini-player replaces button.
- **…** (overflow menu) — "Open in Knowledge Map", "Synthesise around this paper", "Report as irrelevant".

**Inline audio mini-player** (inside card, not full-page):
```
[Play/Pause]  [0:00 --------------- 3:42]  [Speed: 1x v]  [X]
```
Speed options: 0.75×, 1×, 1.25×, 1.5×, 2×. State persisted to `localStorage`.

**Interest onboarding wizard** — shown as a modal overlay on the first `/feed/` visit if `ResearchInterestProfile.topics` is empty:
1. **Step 1**: Paste paper titles, topics, or keywords (free text).
2. **Step 2**: Confirm inferred topics (tag list with toggle chips).
3. **Step 3**: Choose preferred sources (checkboxes: PubMed, arXiv, Crossref, Semantic Scholar).

Feed is read-only until Step 3 is completed — "Skip" is not offered.

**Empty state**: "Your feed is empty. [Update Research Interests]" — button links to `/settings/research-interests`.
**Loading state**: 3 skeleton `PaperCard` placeholders while recommendations are fetched.
**Error state**: toast + "Retry" button.

### 6.3 Related Reading Panel (Document Detail Hub)

Lazy-loaded via `document_detail_ai_panels.js` when `<details data-panel="related-reading">` is opened.

- Shows up to 6 `PaperCard` (compact variant — no abstract, just title + authors + reason pill).
- Single "Add all to Reading List" action at panel bottom.
- If 0 results: "No related papers found for this document. Ensure the project RAG collection is indexed."

### 6.4 Alerts (`/alerts/`)

- List of alert cards, each showing: topic label, matched paper title, source, date, [Read] [Dismiss] actions.
- Unread count badge displayed in main nav (MODEL.md §10.1).
- Mark-all-read button in list header.
- Empty state: "No alerts. Configure your topics in [Research Interests]."

---

## 7. Tests

| File | Scope |
|---|---|
| `tests/test_interest_profile_service.py` | Declared CRUD, inference trigger contract |
| `tests/test_interest_inference_service.py` | TF-IDF extraction; mocked library |
| `tests/test_recommendation_service.py` | Scoring, dedup, ranking; mocked adapter |
| `tests/test_semantic_scholar_adapter.py` | HTTP contract; mocked responses |
| `tests/test_reading_list_service.py` | CRUD, status transitions, move-to-project |
| `tests/test_alert_service.py` | Detection, dedup, read marking |
| `tests/test_audio_summary_service.py` | Text extraction; mocked TTS |
| `tests/test_feed_routes.py` | Route contracts for feed endpoints |
| `tests/test_reading_list_routes.py` | Route contracts for reading-list endpoints |

---

## 8. Acceptance Criteria

- [ ] Researcher can declare ≥ 1 topic and see a personalised feed on `/feed/`.
- [ ] Feed deduplicates against researcher's existing library by DOI.
- [ ] "Not interested" dismissal removes paper from current and future feeds.
- [ ] Reading list persists correctly across sessions.
- [ ] Daily scheduler job generates alerts without blocking request thread.
- [ ] Audio playback streams and controls (play/pause/speed) work without page reload.
- [ ] Related-reading panel loads asynchronously with < 500 ms to first byte.
- [ ] All new pages pass keyboard navigation and mobile responsiveness checks.
- [ ] Feature flag `ai_discovery_enabled=False` hides all new routes cleanly.

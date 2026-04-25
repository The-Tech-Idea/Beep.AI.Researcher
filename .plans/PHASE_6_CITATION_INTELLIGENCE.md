# Phase 6 — Citation Intelligence

> **Feature flag**: `citation_intelligence_enabled`
> **Inspired by**: Zotero, Mendeley, Scite, Crossref
> **Depends on**: None (enrichment base layer)
> **Unlocks**: Phase 1 (library enrichment), Phase 2 (citation context for synthesis),
>              Phase 3 (citation edges for knowledge graph)
>
> **Existing features preserved**:
> - Full reference CRUD, tagging, collections — `routes/references.py` + `templates/project/references.html`. Untouched.
> - Zotero 2-way sync — `services/zotero_library_sync_service.py`. Untouched.
> - 4-style bibliography formatter (APA, MLA, Chicago, BibTeX) — `services/reference_bibliography_service.py`. Untouched; Phase 6 adds more styles alongside.
> - Import dedup detection — `services/reference_import_service.py`. Phase 6's `DeduplicationService` reuses the existing detection; it adds merge UI and an audit log on top.
>
> **Existing services/models to REUSE (do NOT reimplement)**:
> - `services/youtube_ingester_service.py` — YouTube metadata/caption ingestion already implemented.
>   Phase 6 adds a UI/route entry point; NOT reimplementing ingestion logic.
> - `services/video_summary_service.py` — long-video → structured research notes already implemented.
>   Phase 6 exposes it as a document enrichment option; logic untouched.
> - `app/models/researcher/library_sources.py` — `LibrarySource`, `SourceConnection`, `SourceImportLog`
>   are **fully implemented** DB models for multi-source library management (PubMed, arXiv, Semantic Scholar,
>   Crossref). Phase 6 builds admin routes + UI on top of this existing model layer; NOT redefining them.

---

## 1. Goal

Make every citation the researcher touches richer, more trustworthy, and more
actionable. Auto-import from any identifier, understand *how* papers cite each
other, alert on retractions, export in any style, and surface duplicate
references before they silently corrupt a bibliography.

This phase is the enrichment foundation that all other phases draw from.

---

## 2. Features

### 2.1 Smart Citation Import

Allow researchers to add a reference by pasting any identifier and have the
system fetch full metadata automatically.

**Supported identifiers**
- DOI (e.g., `10.1038/s41586-023-05802-x`)
- arXiv ID (e.g., `2301.07041` or URL)
- PubMed ID / PMID
- Semantic Scholar ID
- URL (web page — fallback to best-effort scrape + Crossref lookup)
- BibTeX text (paste or file upload)
- RIS file upload

**User actions**
- On the References page or any Add Reference dialog, paste an identifier or upload a file.
- System resolves and fills all fields automatically.
- User reviews and confirms or edits before saving.
- Bulk import: paste multiple DOIs/PMIDs (one per line).

**System behaviour**
- Resolution order: DOI → Crossref API; PMID → PubMed API; arXiv → arXiv API.
- URL fallback: Crossref `/works?query.bibliographic=<title>` lookup.
- BibTeX/RIS: parsed client-side (pure JS); structured data sent to server for storage.
- Conflict detection: if a resolved DOI already exists in the library, warn and
  offer to view the existing record instead of duplicating.

**Architecture**
- *(extend)* `CrossRefProvider` at `app/integrations/search/providers/crossref.py` —
  already exists; add a `fetch_by_doi(doi)` metadata-only method.
- *(extend)* `PubMedProvider` at `app/integrations/search/providers/pubmed.py` —
  already exists; add a `fetch_by_pmid(pmid)` metadata-only method.
- *(extend)* `SemanticScholarProvider` (Phase 1) — add `fetch_by_id(id)` method.
- *(extend)* `ArxivProvider` at `app/integrations/search/providers/arxiv.py` —
  already exists; add a `fetch_by_id(arxiv_id)` metadata-only method.
- New service: `SmartImportService` — detects identifier type, routes to the **existing**
  provider, normalises to `Reference` schema, checks for duplicates via
  **existing** `reference_import_service._build_project_reference_index()` logic.
- Route: `POST /references/smart-import` — returns resolved metadata JSON preview.
- Route: `POST /references/bulk-import` — processes list of identifiers, returns results.

### 2.2 Citation Context Mining

For any paper in the library, show *how* it is cited by other papers: the
sentence containing the citation and a polarity label (supporting, contradicting,
mentioning).

**User actions**
- On a reference detail page, open the "How it's cited" tab.
- See a list of citing papers with the citation sentence and stance badge.
- Filter by stance (all / supporting / contradicting).
- Click a citing paper to view its abstract or save it.

**System behaviour**
- Data sourced from Semantic Scholar's citation endpoint
  (`/paper/{id}/citations?fields=contexts,intents`).
- Semantic Scholar provides intent labels natively (`background`, `methodology`,
  `result`). These are mapped to our polarity taxonomy:
  - `result` → `supporting` or `contradicting` (requires a secondary classifier)
  - `background` / `methodology` → `mentioning`
- Secondary classifier: thin LLM call on the context sentence.
- Results stored in `CitationContextRecord` model and refreshed at most weekly.

**Architecture**
- New service: `CitationContextService` — fetch from Semantic Scholar, classify,
  store in `CitationContextRecord`.
- New model: `CitationContextRecord` (citing_doi, cited_doi, snippet, intent, polarity, score).
- Route: `GET /references/<id>/citation-context` — returns context records JSON.
- Route: `POST /references/<id>/refresh-context` — triggers background refresh.

### 2.3 Advanced Bibliography Export

> **Existing foundation**: `CitationFormatterService` already supports 4 styles
> (`apa`, `mla`, `chicago`, `bibtex`). `Reference.to_bibtex()` and `Reference.to_ris()`
> exist. This phase extends the formatter to 50+ styles via CSL without replacing it.

Export a bibliography or citation list in any of 50+ citation styles via the
Citation Style Language (CSL) standard.

**User actions**
- From any project's References page or a personal library view, click "Export bibliography".
- Choose style from a searchable dropdown (APA 7th, MLA 9th, Chicago 17th, Vancouver,
  Harvard, IEEE, Nature, Cell, JAMA, AMA, and 40+ others).
- Choose output format: formatted text (HTML), plain text, BibTeX, RIS, Word DOCX.
- Download or copy to clipboard.
- Save a style preference per project.

**System behaviour**
- CSL processing via `citeproc-py` library (runs in-process; no external service).
- BibTeX and RIS export: built locally from `Reference` fields (no external dep).
- DOCX: simple formatted Word document using `python-docx`.
- Exports larger than 500 references split into chunks.

**Architecture**
- Extend **existing** `CitationFormatterService` — add CSL engine (citeproc-py) and
  a 50-style registry; keep existing `SUPPORTED_STYLES` intact for backwards compat.
- Extend **existing** `BibliographyService` with DOCX output; RIS and BibTeX already work.
- Route: `POST /projects/<pid>/references/export-bibliography` — returns file.
- Route: `GET /references/citation-styles` — returns available styles list.

### 2.4 Smart Deduplication

> **Existing foundation**: `reference_import_service.py` already deduplicates during
> import using exact DOI, citation-key, and title+year matching. This phase surfaces
> that logic as a user-facing tool for the existing library and adds a cascaded merge
> with a reversible log.

Detect and merge duplicate references within a library, even when DOIs or titles
differ slightly.

**User actions**
- On the References page, click "Find duplicates".
- See a list of suspected duplicate pairs with a match reason (same DOI / very
  similar title / same authors + year).
- Click "Merge" on any pair to keep one record and re-point all annotations,
  coded references, and extraction results to the surviving record.
- Click "Not a duplicate" to dismiss a pair.

**System behaviour**
- Detection strategy:
  1. Exact DOI match: definitive duplicate.
  2. DOI normalisation: strip protocol variants, uppercase.
  3. Title similarity: Jaro-Winkler ≥ 0.92 AND same first-author surname.
  4. No DOI + same title + same year: probable duplicate.
- Merge cascades FK updates for: `CodedReference`, `ExtractedFieldValue`,
  `DocumentAnnotation`, `ReadingListItem` (Phase 1), `FeedRecommendation` (Phase 1).
- The merge is reversible for 30 days via a stored `DuplicateMergeLog`.

**Architecture**
- New service: `DeduplicationService` — reuses the detection logic from
  `reference_import_service._build_project_reference_index()` and exposes it as a
  standalone scan; adds cascaded merge and revert log.
- New model: `DuplicateMergeLog` (kept_id, removed_id, merged_at, merged_by_user_id).
- Route: `GET /projects/<pid>/references/duplicates` — returns pairs JSON.
- Route: `POST /projects/<pid>/references/merge` — executes merge.
- Route: `POST /projects/<pid>/references/dismiss-duplicate` — dismisses pair.

### 2.5 Library Usage Analytics

Show researchers what in their library is actually being used across projects,
which papers are never annotated or cited, and where gaps exist.

**User actions**
- From References page sidebar, click "Library Analytics".
- See:
  - Most-cited (in their own manuscripts and synthesis reports) papers.
  - Least-used papers (saved but never annotated, never cited).
  - Coverage map: which research areas have many papers vs few.
  - Temporal growth chart: papers added per month.
- Export analytics as CSV.

**System behaviour**
- Usage score: sum of annotation count + coded reference count + synthesis citation
  count + manuscript citation count for each reference.
- Coverage map: cluster references by Phase 1 interest topics; show count per cluster.
- Computed at request time within SQLite query limits; no separate aggregation job.

**Architecture**
- New service: `LibraryAnalyticsService` — aggregation queries over existing tables.
- Route: `GET /references/analytics` — analytics page.
- Route: `GET /references/analytics/data` — JSON data.

### 2.6 Citation Style Preference per Project

Each project saves a preferred citation style so all exports default to it.

**User actions**
- In Project Settings, select "Default citation style".
- All bibliography exports in that project default to this style.

**Architecture**
- `ResearchProject` model extended with `citation_style TEXT NULLABLE`.
- Migration: `research_project_add_citation_style`.

---

## 3. New Models

### `CitationContextRecord`
```
id              INTEGER PK
citing_doi      TEXT NOT NULL
cited_doi       TEXT NOT NULL
citing_title    TEXT
snippet         TEXT NOT NULL
intent          TEXT          -- 'background' | 'methodology' | 'result'
polarity        TEXT          -- 'supporting' | 'contradicting' | 'mentioning'
polarity_score  FLOAT
source          TEXT NOT NULL DEFAULT 'semantic_scholar'
fetched_at      DATETIME NOT NULL
UNIQUE (citing_doi, cited_doi, snippet)
```
Index: `(cited_doi, polarity)`
Migration: `add_citation_context_record`

### `DuplicateMergeLog`
```
id              INTEGER PK
kept_id         INTEGER NOT NULL      -- reference that survived
removed_id      INTEGER NOT NULL      -- reference that was deleted
merged_at       DATETIME NOT NULL
merged_by       INTEGER FK(user.id) NOT NULL
revert_payload  JSON NOT NULL         -- enough to undo the merge
```
Migration: `add_duplicate_merge_log`

---

## 4. Modified Models

### `ResearchProject` (add column)
```
citation_style  TEXT NULLABLE
```
Migration: `research_project_add_citation_style`

---

## 5. New Services

| Service | Responsibilities |
|---|---|
| `SmartImportService` | Detect identifier type, route to existing providers, conflict check |
| `CitationContextService` | Semantic Scholar context fetch + polarity classify |
| `DeduplicationService` | Surface existing dedup logic; cascaded merge; merge log |
| `LibraryAnalyticsService` | Usage scoring; coverage map; growth chart |

---

## 6. Extended Services / Adapters

| Service / Adapter | Extension |
|---|---|
| `CrossRefProvider` (`crossref.py`) | Add `fetch_by_doi(doi)` metadata method |
| `PubMedProvider` (`pubmed.py`) | Add `fetch_by_pmid(pmid)` metadata method |
| `ArxivProvider` (`arxiv.py`) | Add `fetch_by_id(arxiv_id)` metadata method |
| `SemanticScholarProvider` (`semantic_scholar.py`) | Add `fetch_by_id(id)` + citation-list methods |
| `CitationFormatterService` | Add CSL engine; expand to 50+ styles |
| `BibliographyService` | Add DOCX output (RIS + BibTeX already work) |

---

## 7. New Routes

| Method | URL | Purpose |
|---|---|---|
| `POST` | `/references/smart-import` | Resolve single identifier preview |
| `POST` | `/references/bulk-import` | Bulk identifier import |
| `GET` | `/references/<id>/citation-context` | How-it's-cited panel JSON |
| `POST` | `/references/<id>/refresh-context` | Trigger context refresh |
| `GET` | `/references/citation-styles` | Available CSL styles |
| `POST` | `/projects/<pid>/references/export-bibliography` | Styled bibliography export |
| `GET` | `/projects/<pid>/references/duplicates` | Duplicate pairs JSON |
| `POST` | `/projects/<pid>/references/merge` | Execute merge |
| `POST` | `/projects/<pid>/references/dismiss-duplicate` | Dismiss pair |
| `GET` | `/references/analytics` | Library analytics page |
| `GET` | `/references/analytics/data` | Analytics JSON |

---

## 8. UI Design

> See **MODEL.md §10** for global nav, hub architecture, shared components, and the full file inventory.
> This section covers the interaction design unique to Phase 6.

### 8.1 File Pairs

| Template | JS | CSS |
|---|---|---|
| *(hub extension)* `templates/project/references.html` | `static/js/project/references_ai_toolbar.js` | *(shared theme)* |
| `templates/references/citation_context.html` | `static/js/references/citation_context.js` | *(shared theme)* |
| `templates/references/analytics.html` | `static/js/references/analytics.js` | `static/css/references/analytics.css` |

### 8.2 References AI Toolbar (Hub B Extension)

Added to `references.html` list header when `citation_intelligence_enabled`:

```
[Smart Import]  [Dedup (3)]  [Analytics ->]  [Synthesis ->]
```

- **Smart Import** — slides in the Universal Import Drawer (§8.3).
- **Dedup (n)** — badge showing duplicate count; click opens Dedup Diff Viewer (§8.5). Hidden when count = 0.
- **Analytics** — navigates to `/references/<pid>/analytics`.
- **Synthesis** — navigates to Phase 2 synthesis page with project scope pre-selected.

**Retraction warning banner**: amber full-width banner when any reference has a known retraction: "[n] retracted papers in this project. [Review]". Each flagged row shows a warning retraction badge (icon + tooltip). The same CSS class `retraction-badge` is used in the Synthesis evidence table (Phase 2) and Writing Studio citation sidebar (Phase 4).

### 8.3 Universal Import Drawer

Slides in from the right (600 px wide on desktop, full-screen on mobile):

```
+-- Import Reference -----------------------------------------[X]--+
| Paste DOI, PMID, arXiv ID, or URL:                               |
| [10.1000/xyz123                                    ] [Resolve ->] |
|                                                                   |
| -- Preview -------------------------------------------------------+
| Title:   Paper title here                                         |
| Authors: Smith J., et al.                                         |
| Journal: Nature · 2023                                            |
| ! Retraction notice found (link)                                  |
|                                                                   |
| [Edit details]  [Cancel]  [Add to References]                     |
+-------------------------------------------------------------------+
```

- Retraction warning shown before user confirms — not after.
- "Edit details" expands an inline form with all metadata fields editable before saving.
- Duplicate detection: "This paper is already in your library. [View existing]"

### 8.4 Citation Context Page (`/references/<pid>/context/<ref_id>`)

Lists all papers that cite this reference, each with:
- `StanceBadge` (supporting / contradicting / mentioning).
- Snippet of the citing sentence.
- [Open citing paper] link.
- Filter chips at top: All | Supporting | Contradicting | Mentioning.

### 8.5 Dedup Diff Viewer

Side-by-side two-record comparison:
```
+-- Duplicate found ------------------------------------------------+
|  Record A (in library)      |   Record B (duplicate)             |
|  Title:  Same title         |   Same title                       |
|  DOI:    10.1000/abc (ok)   |   - (missing)                      |
|  Year:   2021               |   2021                             |
|  Source: PubMed             |   arXiv                            |
|                                                                   |
|  [Keep A, discard B]  [Keep B, discard A]  [Cancel]              |
+-------------------------------------------------------------------+
```
Merge action requires `ConfirmDialog`. The surviving record shows merged source badges.

### 8.6 Library Analytics (`/references/<pid>/analytics`)

Three chart panels (Chart.js from CDN):
- **By source**: donut chart (PubMed / arXiv / Manual / etc.).
- **By year**: bar chart (publication year distribution).
- **Top 10 cited**: ranked list with citation count badge.

Metrics row above charts: Total references · With full text · With DOI · Retracted.
Export: [Download as CSV] button.

---

## 9. Tests

| File | Scope |
|---|---|
| `tests/test_smart_import_service.py` | Identifier detection; provider routing; conflict detection |
| `tests/test_crossref_provider_metadata.py` | `fetch_by_doi` — mocked Crossref response |
| `tests/test_pubmed_provider_metadata.py` | `fetch_by_pmid` — mocked PubMed response |
| `tests/test_arxiv_provider_metadata.py` | `fetch_by_id` — mocked arXiv response |
| `tests/test_citation_context_service.py` | Fetch + classify; cache refresh |
| `tests/test_deduplication_service.py` | Detection strategies; merge cascades; revert payload |
| `tests/test_library_analytics_service.py` | Usage scoring; coverage; growth |
| `tests/test_citation_formatter_csl.py` | CSL output for 5 representative styles |
| `tests/test_citation_intelligence_routes.py` | Route contracts; auth enforcement |

---

## 10. Acceptance Criteria

- [ ] Pasting a valid DOI autofills all reference fields within 2 s.
- [ ] Duplicate warning shows for DOI already in library before saving.
- [ ] Bulk import of 20 DOIs completes and reports per-item success/failure.
- [ ] "How it's cited" tab shows at least 1 context record for a well-cited DOI.
- [ ] Deduplication detects exact-DOI and high-title-similarity pairs correctly.
- [ ] Merge re-points all `CodedReference` records to the surviving reference.
- [ ] Merged reference can be identified for reversal within 30 days via merge log.
- [ ] Bibliography export in APA, MLA, Chicago, and IEEE all produce valid output.
- [ ] Library analytics usage score ranks an annotated paper above an unused one.
- [ ] All citation intelligence routes return 404 when `citation_intelligence_enabled=False`.

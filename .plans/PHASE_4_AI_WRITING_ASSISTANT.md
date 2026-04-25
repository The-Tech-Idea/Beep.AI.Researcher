# Phase 4 — AI Writing Assistant

> **Feature flag**: `writing_assistant_enabled`
> **Inspired by**: Writefull, Grammarly, Scholarcy, Elicit
> **Depends on**: Phase 2 (evidence snippets for citation suggestions)
> **Unlocks**: Phase 5 (published sections update researcher profile)
>
> **Existing features to REUSE (do NOT recreate)**:
> - `routes/training.py` — flashcard generation (`POST /<pid>/flashcards`) AND full quiz system
>   (`POST /<pid>/quiz`, `Quiz`, `QuizQuestion`, `QuizAttempt`, `templates/project/quizzes.html`,
>   `take_quiz.html`) are **both** fully implemented. Phase 4 adds per-document flashcard
>   preview UI only. It does NOT add new quiz generation logic.
> - `routes/report_writing.py` — 4 routes already exist: `writing/assist` (11 actions),
>   `writing/format-citations`, `writing/citation-scan`, `writing/overlap-check`.
>   Phase 4 adds `writing/analyse` (structured quality scorer) alongside these.
> - `services/overlap_checker_service.py` — project-grounded plagiarism detection already
>   implemented. The `writing/overlap-check` route calls it. Phase 4 does NOT add a second
>   plagiarism layer.
> - `routes/related.py` `POST /<pid>/writing/citations` — citation finding from text already
>   exists. `CitationDraftService` delegates to this.

---

## 1. Goal

Help researchers write better manuscripts faster. The assistant surfaces
academic grammar and clarity issues, auto-generates structured paper summaries
and flashcards, extracts key findings and data tables from PDFs, and integrates
evidence-backed citation suggestions inline in the Writing Studio.

It augments the existing Writing Studio (Manuscript model) rather than
replacing it.

---

## 2. Features

### 2.1 Academic Writing Quality Scorer

Score any manuscript section on academic tone, clarity, grammar, and style.
Inline annotations explain each issue and suggest an improvement.

> **Existing foundation**: `report_writing.py` already provides `POST /<pid>/writing/assist`
> with 11 text-transform actions (grammar, paraphrase, tone, summarize, expand,
> academic_rewrite, simplify, legal_plain, medical_lay, academic_paraphrase_v2, clarity).
> These return a replacement text string. This phase adds a **companion route**
> `POST /<pid>/writing/analyse` that returns structured feedback JSON with offset-mapped
> issues instead of a text replacement. The two routes coexist in `report_writing.py`.
> The 11 existing actions are NOT modified.

**User actions**
- In the Writing Studio, click "Analyse section" on any section.
- See an overall score (0–100) and a breakdown: tone, clarity, grammar, structure.
- Inline annotations appear on the text with coloured underlines.
- Click an annotation to see the issue description and one-click "Apply fix".
- Accept or dismiss each suggestion individually.
- Re-analyse after edits to see the updated score.

**System behaviour**
- Calls LLM via `BeepAIClient` with a structured prompt requesting JSON output:
  `{ score, tone_score, clarity_score, grammar_score, issues: [...] }`.
- Each issue has: `type`, `severity`, `text`, `suggestion`, `offset`, `length`
  (matching the `WritingFeedback` contract in MODEL.md).
- Applied fixes: JS patches `section.content` at the given offset/length.
- Re-analysis stores the delta score so progress is visible.
- Section content is never automatically modified without user accepting a fix.

**Architecture**
- New service: `WritingQualityService` — calls LLM, parses response, maps offsets.
- `ManuscriptSection` model extended with `last_score FLOAT NULLABLE`.
- New route in `report_writing.py`: `POST /<pid>/writing/analyse` — returns JSON feedback.
- New route in `manuscripts.py`: `POST /manuscripts/<mid>/sections/<sid>/apply-fix` — applies one accepted fix.

### 2.2 Automated Paper Summary Flashcards

> **Existing foundation**: `training_bp` already has `POST /projects/<pid>/flashcards`
> which generates flashcards from project documents via LLM with grounded context.
> This phase adds a per-document surface (document detail page → preview → selective
> save) on top of that foundation rather than rebuilding generation from scratch.

Generate a set of flashcards from any uploaded document's content, ready to
add to the existing Flashcard system.

**User actions**
- On any document detail page, click "Generate flashcards".
- Choose depth: "Quick" (5 cards, abstract only) or "Deep" (20 cards, full text).
- Preview the generated cards with front/back visible.
- Select which cards to keep (multi-select with "keep all" default).
- Click "Add to project flashcard deck" — creates `Flashcard` records in the
  chosen project.

**System behaviour**
- LLM prompt instructs extraction of key concepts, definitions, findings, and
  relationships as Q&A pairs.
- For "Deep" mode, document text chunked and processed in parallel sub-calls.
- Generated cards de-duplicated against existing flashcards in the same project
  by fuzzy front-text match.

**Architecture**
- New service: `FlashcardGenerationService` — thin wrapper that calls the **existing**
  `training_bp` generation logic with a single document scope; adds preview/selective-save
  semantics and deduplication against the target project deck.
- Extends existing `Flashcard` model — no schema change, new creation path only.
- Route: `POST /documents/<id>/generate-flashcards` — returns preview JSON.
- Route: `POST /documents/<id>/save-flashcards` — saves selected cards to project.

### 2.3 Key Findings & Data Table Extractor

Extract structured summaries, key findings, and tabular data from PDFs —
going beyond the existing `ExtractionSchema` system (which is user-defined) to
provide an automatic, schema-free extraction.

**User actions**
- On any document, click "Auto-extract key findings".
- View results as three panels:
  - **Summary**: 3-sentence plain-language summary.
  - **Key Findings**: bulleted list of main findings with their evidence type label
    (observational, RCT, systematic review, etc.).
  - **Data Tables**: any numeric tables in the paper, formatted as HTML tables.
- Download as JSON or copy to clipboard.
- Push individual finding to an existing `ExtractionResult` for formal storage.

**System behaviour**
- Summary: LLM call on abstract + introduction.
- Key findings: LLM call on results + conclusion sections (identified by heading
  heuristic or existing section detection).
- Data tables: extracted from PDF text by regex + LLM disambiguation; images not
  supported in V1.
- Results are cached per document (stored in `AutoExtractionCache` model) to avoid
  re-running on every view.

**Architecture**
- New service: `AutoExtractionService` — orchestrates three extraction passes.
- New model: `AutoExtractionCache` (one per document, JSONB fields for each section).
- Route: `GET /documents/<id>/auto-extract` — returns cached result or triggers fresh run.
- Route: `POST /documents/<id>/finding-to-extraction` — saves one finding as `ExtractionResult`.

### 2.4 Literature Review Section Writer

Given a set of papers and a user-defined theme, draft a literature review section
with inline citations, ready to paste into the Writing Studio.

**User actions**
- In the Writing Studio, inside any section, click "Add citations with AI".
- A drawer opens: pick papers from the project library.
- Optionally provide a theme sentence ("Compare approaches to X").
- Click "Draft paragraph" — receives an LLM-generated paragraph with `[Cite: DOI]`
  markers.
- Accept and insert into section, or edit before accepting.
- `[Cite: DOI]` markers converted to formatted in-text citations on acceptance.

**System behaviour**
- Retrieves abstracts of selected papers, sends to LLM with instruction to produce
  a thematic paragraph and mark every claim.
- `[Cite: DOI]` → `(Author, Year)` conversion uses existing `CitationFormatterService`.
- Accepted paragraph appended or inserted at cursor in `ManuscriptSection.content`.

**Architecture**
> **Existing foundation**: `routes/related.py` already provides
> `POST /<pid>/writing/citations` — finds citations for a text selection via LLM + RAG.
> `CitationDraftService` **calls this existing endpoint** to get citation candidates; it
> does NOT re-implement citation search. It adds the themed-paragraph generation layer on top.
>
> Also already in `routes/report_writing.py` (do NOT recreate):
> - `POST /<pid>/writing/format-citations` — deterministic APA/MLA/Chicago/BibTeX formatting
> - `POST /<pid>/writing/citation-scan` — scans text for unformatted references
> - `POST /<pid>/writing/overlap-check` — plagiarism/overlap detection
>
> Phase 4 adds only `POST /<pid>/writing/analyse` (structured quality scoring) alongside these.
- New service: `CitationDraftService` — themed paragraph generation; delegates citation lookup to existing `POST /<pid>/writing/citations`.
- Extends `ManuscriptSection` editing routes (no new model).
- Route: `POST /manuscripts/<mid>/sections/<sid>/citation-draft` — returns draft JSON.
- Route: `POST /manuscripts/<mid>/sections/<sid>/insert-draft` — writes to section content.

### 2.5 Readability & Academic Tone Checker (Passive Voice, Hedging, Jargon)

Lightweight rule-based checks that complement the LLM scorer with deterministic
signals: passive voice density, hedge-word density (might, could, appears to),
sentence length distribution, and jargon ratio.

**User actions**
- View a "Readability panel" on any section alongside the quality score.
- See bar charts: % passive sentences, % hedge sentences, avg sentence length.
- Click "Highlight passive sentences" to see underlines.
- Each metric has a contextual advice tooltip (e.g., "Academic writing uses
  passive voice intentionally, but > 70% indicates unclear agency").

**System behaviour**
- All computation rule-based (no LLM call). Uses spaCy or regex patterns.
- Runs synchronously; result cached per section content hash.

**Architecture**
- New service: `ReadabilityService` — pure Python, no LLM.
- Route: `GET /manuscripts/<mid>/sections/<sid>/readability` — returns JSON metrics.

---

## 3. New Models

### `AutoExtractionCache`
```
id              INTEGER PK
document_id     INTEGER FK(researcher_document.id) NOT NULL UNIQUE
summary_text    TEXT
findings_json   TEXT      -- JSON list of finding dicts
tables_json     TEXT      -- JSON list of table dicts
extracted_at    DATETIME NOT NULL
```
Migration: `add_auto_extraction_cache`

---

## 4. Modified Models

### `ManuscriptSection` (add column)
```
last_quality_score  FLOAT NULLABLE    -- most recent WritingQualityService score
```
Migration: `manuscript_section_add_quality_score`

---

## 5. New Services

| Service | Responsibilities |
|---|---|
| `WritingQualityService` | LLM-based scoring; issue extraction; fix application |
| `FlashcardGenerationService` | Chunk → LLM → dedup → flashcard creation |
| `AutoExtractionService` | Summary + key findings + data table extraction |
| `CitationDraftService` | Themed paragraph draft with citation markers |
| `ReadabilityService` | Rule-based passive/hedge/length metrics |

---

## 6. New Routes

> Routes are placed in **existing** route files where they naturally belong.
> No new route file is created for this phase.

| Method | URL | Route file | Purpose |
|---|---|---|---|
| `POST` | `/<pid>/writing/analyse` | `report_writing.py` | Writing quality analysis — returns structured JSON (alongside existing `writing/assist`) |
| `POST` | `/manuscripts/<mid>/sections/<sid>/apply-fix` | `manuscripts.py` | Apply accepted fix to section content |
| `GET` | `/manuscripts/<mid>/sections/<sid>/readability` | `manuscripts.py` | Readability metrics |
| `POST` | `/manuscripts/<mid>/sections/<sid>/citation-draft` | `manuscripts.py` | AI draft paragraph |
| `POST` | `/manuscripts/<mid>/sections/<sid>/insert-draft` | `manuscripts.py` | Insert draft into section |
| `POST` | `/documents/<id>/generate-flashcards` | `documents.py` | Generate per-document flashcard preview |
| `POST` | `/documents/<id>/save-flashcards` | `documents.py` | Save selected flashcards (calls `training_bp` logic via service) |
| `GET` | `/documents/<id>/auto-extract` | `documents.py` | Schema-free extract or return cache |
| `POST` | `/documents/<id>/finding-to-extraction` | `documents.py` | Promote finding to formal `ExtractionResult` |

---

## 7. UI Design

> See **MODEL.md §10** for global nav, hub architecture, shared components, and the full file inventory.
> This section covers the interaction design unique to Phase 4.

### 7.1 File Pairs

| Template | JS | CSS |
|---|---|---|
| *(extends)* `templates/project/report.html` | `static/js/project/writing_assistant.js` | `static/css/project/writing_assistant.css` |
| *(hub, panels via document_detail)* | `static/js/project/document_detail_ai_panels.js` | `static/css/project/document_detail_ai_panels.css` |

### 7.2 Writing Studio Section Toolbar (Hub C)

The section editor in `report.html` gains a right-aligned toolbar row:
```
[Analyse] [Citation Draft v] [Readability: --]
```
- **[Analyse]** — `AsyncJobButton`; calls `POST /<pid>/writing/analyse`; on complete, loads annotation overlay.
- **[Citation Draft ▾]** — dropdown: "Suggest citations for selection" / "Insert citation for selected term".
- **Readability** — updated after Analyse; shows score 0–100 + label ("Academic", "Clear", "Dense").

### 7.3 Inline Annotation Overlay

After Analyse completes, `WritingFeedback.issues` are rendered as coloured underlines using an absolutely-positioned SVG layer (does not modify the textarea DOM):

| Issue type | Underline colour | Icon |
|---|---|---|
| `grammar` | `var(--color-danger)` red | x |
| `tone` / `passive_voice` | `var(--color-warning)` amber | ! |
| `clarity` | `var(--color-info)` blue | i |

Click underline — popover:
```
+----------------------------------------+
| ! Passive voice                         |
| "was demonstrated" -> "demonstrated"   |
| [Apply fix]  [Ignore]  [Ignore all]    |
+----------------------------------------+
```

**Score gauge** — ring dial widget top-right of section (CSS conic-gradient):
- 0–49: red; 50–74: amber; 75–100: green.
- Tooltip on hover: "Writing quality score: 82/100".

### 7.4 Auto-Extract Panels (Document Detail Hub)

All three panels are lazy-loaded via `document_detail_ai_panels.js`.

**Key Findings panel** (`data-panel="auto-extract"`):
- Three-tab layout — **Summary** | **Key Findings** | **Tables & Figures**.
- Summary: single paragraph (copyable).
- Key Findings: numbered list, each with copy-to-clipboard icon.
- Tables: rendered HTML tables; each has [Copy as CSV] button.

**Flashcard Preview panel** (`data-panel="flashcards"`):
- Up to 20 flashcard previews in a 2-column grid.
- Each card: front (question) / back (answer) toggle on click.
- Checkbox-select + [Add selected to Deck ▾] action.
- Deck picker lists the project's existing decks + "New deck…" option.
- Empty state: "No flashcards yet — [Generate Flashcards] from this document."

### 7.5 Citation Draft Sidebar

Slides in from the right when [Citation Draft ▾] is used:
- Free-text field: "What claim do you want to cite?"
- Below: list of `PaperCard` (compact) ranked by relevance with [Insert [n]] per card.
- Inserting a citation adds a `[CITE:DOI]` marker inline; marker renders as a hoverable badge `[n]` with a tooltip showing: paper title + `StanceBadge` from any Phase 2 evidence entry for that paper.
- [Export citations in style ▾] — opens `CitationStylePicker` component.

---

## 8. Tests

| File | Scope |
|---|---|
| `tests/test_writing_quality_service.py` | Scoring, issue parsing, fix application |
| `tests/test_flashcard_generation_service.py` | Chunking, LLM mock, dedup |
| `tests/test_auto_extraction_service.py` | Three-pass extraction; cache hit/miss |
| `tests/test_citation_draft_service.py` | Draft generation; marker-to-citation |
| `tests/test_readability_service.py` | Passive/hedge/length computation |
| `tests/test_writing_assistant_routes.py` | Route contracts, auth enforcement |

---

## 9. Acceptance Criteria

- [ ] Analysing a section returns overall score + at least 1 issue if text is unpolished.
- [ ] "Apply fix" patches section content at correct offset without corrupting surrounding text.
- [ ] "Quick" flashcard generation from abstract produces 4–6 flashcards in < 5 s.
- [ ] Auto-extract returns summary, ≥ 1 finding, and ≥ 0 tables for any real PDF.
- [ ] Cache prevents re-extraction on second request for the same document.
- [ ] Citation draft markers are correctly converted to APA/MLA on insertion.
- [ ] Readability panel computes passive-voice % correctly for known test sentences.
- [ ] All endpoints return 404 when `writing_assistant_enabled=False`.
- [ ] Section content is never modified unless user explicitly accepts a fix.

# Phase 2 — Evidence Synthesis Engine

> **Feature flag**: `evidence_synthesis_enabled`
> **Inspired by**: Consensus, Elicit, Scite
> **Depends on**: Phase 6 (citation context enrichment recommended but optional)
> **Unlocks**: Phase 4 (evidence snippets → writing assistant literature review)
>
> **Existing features preserved**:
> - `routes/chat.py` — RAG-backed project chat (question/answer within a project session).
>   Phase 2 Evidence Synthesis is a **separate** workflow: cross-project, multi-paper,
>   polarity-labelled, and produces a citable report. Chat is not replaced.
> - `routes/contradiction.py` + `templates/project/contradictions.html` — detailed
>   contradiction analysis page. Phase 2 surfaces contradictions inline in the evidence
>   table as `StanceBadge`; it does NOT replace the contradiction page. Both coexist.
>
> **Existing models to REUSE (not redefine)**:
> `app/models/researcher/phase_a_models.py` already defines the core evidence layer:
> - `ResearchBrief` — sector-tagged brief linked to a project (maps to Phase 2 `SynthesisReport`)
> - `EvidenceItem` — GRADE-style evidence records with source/quote/interpretation
> - `Claim` — high-level argumentative statements with confidence scores
> - `ClaimEvidence` — join table: Claim ↔ EvidenceItem with a `relationship` field (supports | contradicts | mentions)
> - `ReviewStep` — PRISMA audit log entries
> - `SourceProvenance` — document lineage / transformation chain
>
> Phase 2 routes and services SHOULD use these models directly. The `relationship`
> field on `ClaimEvidence` maps exactly to Phase 2's polarity labels.
> The `SynthesisReport` concept in the plan = `ResearchBrief` with `status='final'` and
> `key_findings` populated from the synthesis result.
>
> **Additional existing services to REUSE**:
> - `services/overlap_checker_service.py` — `check_overlap(project, passage, ...)` returns
>   RAG-grounded similarity matches with scores. Phase 2's grounding check should call this
>   service for hallucination prevention rather than reimplementing a grounding layer.
> - `HallucinationAuditLog` model + `templates/project/hallucination_audit.html` — a complete
>   grounding audit feature already exists. Phase 2 should persist synthesis grounding results
>   to `HallucinationAuditLog` so they appear on that page; NOT add a parallel audit page.
> - `EvidenceGrade` model (sector_models.py) — GRADE/Oxford medical quality grades for evidence.
>   Phase 2's evidence strength scoring USES this model; it is not redefined.

---

## 1. Goal

Allow researchers to ask "What does the research say about X?" and receive a
grounded, source-cited answer synthesised across multiple papers — not a
hallucinated summary, but reasoning anchored to evidence snippets with
polarity labels (supports, contradicts, mentions).

This replaces hours of manual literature synthesis with a first-draft answer
the researcher can audit, expand, and cite.

---

## 2. Features

### 2.1 Research Consensus Query

A dedicated query interface where the user poses a research question in natural
language and receives a structured synthesis answer.

**User actions**
- Navigate to `Synthesis` from the main nav.
- Enter a research question (e.g., "Does omega-3 supplementation reduce cognitive decline?").
- Optionally scope the query to a specific project library or search all indexed sources.
- Submit and wait (async, streamed response).
- Review the answer: summary paragraph + evidence table (paper, snippet, stance).
- Export synthesis as a PDF or copy citations in any supported format.
- Save synthesis to a project.

**System behaviour**

1. **Retrieval**: Query is embedded (using existing sentence-transformer infrastructure).
   Vector search across the user's library (`ResearcherDocument` embeddings) plus
   live external search (PubMed, arXiv, Semantic Scholar) for broader scope.
2. **Context assembly**: Top-K relevant passages retrieved and assembled into a
   prompt context window. Citations metadata attached (title, authors, DOI, year).
3. **Synthesis**: LLM call (via existing `BeepAIClient`) with a strict grounding
   prompt that forbids claims without inline citation.
4. **Polarity labelling**: A second classification pass labels each cited snippet as
   `supporting`, `contradicting`, or `mentioning`. Uses existing LLM capability.
5. **Aggregation**: System counts supporting vs contradicting papers and derives a
   confidence level: `strong` (≥70% same direction), `mixed` (30-70%), `insufficient`.
6. **Transparency**: Every claim in the answer is traceable to a source document.
   UI shows document title and page/position link.

**Architecture**
- New service: `EvidenceSynthesisService` — orchestrates retrieval → assembly → LLM → labelling.
- New service: `PolarityClassifier` — classifies each evidence snippet; thin wrapper.
- `GroundingClient` (existing) used for retrieval; extended with project-scope filter.
- New model: `SynthesisReport` — persisted synthesis (query, answer, citations JSON, scores).
- Routes under `/synthesis/`.

### 2.2 Evidence Table

The structured breakdown of all evidence used in a synthesis.

**User actions**
- View evidence table: each row is one snippet with stance badge and paper metadata.
- Sort by stance (supporting first), by year, by relevance score.
- Click a row to jump to the source document at the cited position.
- Flag a row as "incorrect label" (feedback loop for classifier improvement).

**Architecture**
- `SynthesisReport.citations` JSON stores the full evidence table.
- Route: `GET /synthesis/<id>/evidence` returns JSON evidence rows.
- Frontend renders sortable table client-side (no server round-trip per sort).

### 2.3 Multi-Paper Literature Review Draft

Generate a structured literature review outline and draft based on a topic, ready
to paste into the Writing Studio.

**User actions**
- From Synthesis or from Writing Studio, select "Generate literature review draft".
- Provide a topic and optional source set (project library or free search).
- Receive: an introduction paragraph, thematic sections with supporting evidence,
  a gap analysis paragraph, and a conclusion stub.
- Review and click "Send to Writing Studio" to create a new manuscript section.

**System behaviour**
- Multi-step LLM chain:
  1. Cluster evidence snippets by theme (using existing clustering capability).
  2. Generate one paragraph per theme, grounded in evidence.
  3. Identify themes with no supporting evidence (gap analysis).
  4. Assemble draft sections.
- Draft is stored as a `SynthesisReport` with `report_type = 'literature_review'`.

**Architecture**
- `EvidenceSynthesisService.generate_literature_review(topic, source_ids)` method.
- Route: `POST /synthesis/literature-review` — triggers generation, returns job ID.
- Integration with existing `ManuscriptSection` model: accepted drafts create sections.

### 2.4 Hypothesis Testing Interface

Given a research hypothesis, find all evidence in the library that supports or
contradicts it, with an overall verdict.

**User actions**
- Navigate to an existing `Hypothesis` (Phase A model, already exists).
- Click "Synthesise Evidence" button.
- View synthesis result inline: verdict badge + evidence table.
- Store verdict as a formal `EvidenceItem` on the hypothesis.

**System behaviour**
- Routes the hypothesis claim text through `EvidenceSynthesisService` with
  project scope forced to the hypothesis's project.
- Result stored as a `SynthesisReport` linked to the `Hypothesis`.

**Architecture**
- `EvidenceSynthesisService.synthesise_for_hypothesis(hypothesis_id)` method.
- Route: `POST /projects/<pid>/hypotheses/<hid>/synthesise` — triggers job.
- Route: `GET /projects/<pid>/hypotheses/<hid>/synthesis` — result page.

### 2.5 Retraction & Correction Alerts

Automatically detect when a paper in the researcher's library has been retracted
or issued an erratum, and alert them.

**User actions**
- See retraction badge on any reference card/row that has been retracted.
- Receive an Alert (Phase 1 `PaperAlert` reused) for newly detected retractions.
- View retraction details: reason, date, issuing journal.
- Mark retracted reference as "acknowledged" to dismiss the badge.

**System behaviour**
- Scheduler job checks DOIs in the user's library against the Crossref Retraction
  Watch API and the Retraction Watch Database (open API).
- Detection result stored in `RetractionRecord` model.
- On match: creates a `PaperAlert` with `alert_type = 'retraction'`.

**Architecture**
- New adapter: `RetractionWatchAdapter` — queries Crossref + Retraction Watch.
- New model: `RetractionRecord` (doi, reason, date, acknowledgement status).
- New service: `RetractionAlertService` — scheduler-driven detection + alert creation.
- `Reference` model gets `is_retracted` computed property (checks `RetractionRecord`).

---

## 3. New Models

### `SynthesisReport`
```
id                  INTEGER PK
user_id             INTEGER FK(user.id) NOT NULL
project_id          INTEGER FK(research_project.id) NULLABLE
query               TEXT NOT NULL
report_type         TEXT NOT NULL DEFAULT 'consensus'  -- 'consensus' | 'literature_review' | 'hypothesis'
answer              TEXT NOT NULL
confidence          TEXT NOT NULL                       -- 'strong' | 'mixed' | 'insufficient'
supporting_count    INTEGER NOT NULL DEFAULT 0
contradicting_count INTEGER NOT NULL DEFAULT 0
neutral_count       INTEGER NOT NULL DEFAULT 0
citations           JSON NOT NULL DEFAULT '[]'          -- list of CitationSnippet dicts
source_scope        TEXT NOT NULL DEFAULT 'all'         -- 'project' | 'all'
status              TEXT NOT NULL DEFAULT 'pending'     -- 'pending' | 'complete' | 'failed'
created_at          DATETIME NOT NULL
completed_at        DATETIME
hypothesis_id       INTEGER FK(hypothesis.id) NULLABLE
```
Index: `(user_id, project_id, created_at)`
Migration: `add_synthesis_report`

### `RetractionRecord`
```
id              INTEGER PK
doi             TEXT NOT NULL UNIQUE
reason          TEXT
retraction_date DATE
journal         TEXT
acknowledged_by JSON NOT NULL DEFAULT '[]'    -- list of user_ids
created_at      DATETIME NOT NULL
```
Index: `(doi)`
Migration: `add_retraction_record`

---

## 4. New Services

| Service | Responsibilities |
|---|---|
| `EvidenceSynthesisService` | Orchestrate retrieval → LLM → polarity → aggregate |
| `PolarityClassifier` | Label each snippet as supporting/contradicting/mentioning |
| `LiteratureReviewDraftService` | Multi-step chain: cluster → draft sections → assemble |
| `RetractionAlertService` | DOI checks, record creation, alert dispatch |
| `RetractionWatchAdapter` | HTTP adapter for Crossref + Retraction Watch APIs |

---

## RAG / Chunk Template Notes

**Project evidence collection** must use `system-semantic-fine`
(slug `system-semantic-fine`). The tight semantic split — lower breakpoint
threshold (85th percentile) — produces more, smaller passages, which maximises
retrieval precision for evidence queries and gives the polarity classifier
cleaner single-point snippets.

Apply when the project's RAG collection is first provisioned (or re-apply if it
was created with a different template):
```python
ok, templates = beep_ai_client.list_chunk_templates()
slug_map = {t["slug"]: t["template_id"] for t in templates}

# If collection already exists, re-apply the template (triggers async re-index):
beep_ai_client.apply_chunk_template_to_collection(
    template_id=slug_map["system-semantic-fine"],
    collection_id=project_collection_id,
)
```

For synthesis RAG queries always pass:
```python
beep_ai_client.rag_query(
    query=user_question,
    collection_id=project_collection_id,
    max_results=15,
    quality_mode="high",
    hybrid_search=True,
    rerank=True,
    return_citations=True,
    grounded_only=True,
)
```
After generating the synthesis answer, always call
`grounding_client.run_post_generation_checks()` to validate and log the
result before returning it to the user.

> **Custom templates**: The project owner can change the evidence collection's
> chunk template from `Project Settings` (e.g. switch to `system-parent-child`
> for longer context windows, or apply a custom domain template). Re-applying
> a template triggers an async re-index. See `MODEL.md` section 9.10.

---

## 5. New Routes

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/synthesis/` | Synthesis main page |
| `POST` | `/synthesis/query` | Submit research question; returns job ID |
| `GET` | `/synthesis/<id>` | View synthesis report |
| `GET` | `/synthesis/<id>/evidence` | Evidence table JSON |
| `POST` | `/synthesis/<id>/evidence/<row>/flag` | Flag incorrect polarity label |
| `POST` | `/synthesis/literature-review` | Start literature review draft |
| `GET` | `/synthesis/<id>/export` | Export synthesis as PDF |
| `POST` | `/synthesis/<id>/send-to-manuscript` | Create manuscript sections from draft |
| `GET` | `/projects/<pid>/hypotheses/<hid>/synthesis` | Hypothesis synthesis result |
| `POST` | `/projects/<pid>/hypotheses/<hid>/synthesise` | Trigger hypothesis synthesis |

---

## 6. UI Design

> See **MODEL.md §10** for global nav, hub architecture, shared components, and the full file inventory.
> This section covers the interaction design unique to Phase 2.

### 6.1 File Pairs

| Template | JS | CSS |
|---|---|---|
| `templates/synthesis/synthesis.html` | `static/js/synthesis/synthesis.js` | `static/css/synthesis/synthesis.css` |
| `templates/synthesis/report.html` | `static/js/synthesis/report.js` | *(shared theme)* |
| *(hub extension)* `templates/project/references.html` | `static/js/project/references_ai_toolbar.js` | *(shared theme)* |

### 6.2 Synthesis Query Page (`/synthesis/`)

**Layout**: centered single-column; large textarea + project scope picker above the fold.

**Query input area**:
- `<textarea>` with placeholder: "What does research say about…"
- Project scope picker: dropdown listing user's projects + "My whole library".
- [Synthesise] button — uses `AsyncJobButton`; shows "Analysing…" state while streaming.

**Streaming result** (replaces the button area while in progress):
```
+----------------------------------------------+
| Answer (streaming — text appends word by word)|
|                                               |
| Confidence:  [====------] Mixed               |
| Supporting: 7   Contradicting: 3   Other: 4   |
+----------------------------------------------+
```

**Confidence band** — a coloured bar using theme tokens:
- Strong (>=0.75): `var(--color-success)` green
- Mixed (0.4–0.74): `var(--color-warning)` amber
- Insufficient (<0.4): `var(--color-muted)` grey

### 6.3 Evidence Table (inside synthesis result)

Below the answer block, collapsible table of evidence passages:

| Title | Stance | Snippet | Retraction? | Actions |
|---|---|---|---|---|
| Paper title (link) | `StanceBadge` | "…quoted passage…" | warns if flagged | [Add to References] |

`StanceBadge` uses icon + colour (never colour alone — MODEL.md §10.7):
- Supporting: green check icon `var(--color-success)`
- Contradicting: red x icon `var(--color-danger)`
- Mentioning: grey dash icon `var(--color-muted)`

Retraction: amber warning icon + tooltip "Retraction: [reason]."

### 6.4 Synthesis Report Page (`/synthesis/<id>/report`)

- Renders the `EvidenceSynthesisResult` as a structured report (headings: Overview, Key Findings, Evidence, Limitations).
- Top-right toolbar: [Export ▾] (PDF / Copy Citations) → opens `CitationStylePicker` modal.
- **"Send to Writing Studio" button**: opens project picker → creates `ManuscriptSection` from report text (see MODEL.md §10.4).
- Print-friendly: `@media print` hides toolbar and nav.

---

## 7. Tests

| File | Scope |
|---|---|
| `tests/test_evidence_synthesis_service.py` | Retrieval, assembly, LLM mocked; aggregation logic |
| `tests/test_polarity_classifier.py` | Label classification; mocked LLM |
| `tests/test_literature_review_draft_service.py` | Multi-step chain; mocked LLM + retrieval |
| `tests/test_retraction_alert_service.py` | DOI check, record creation, alert dispatch |
| `tests/test_retraction_watch_adapter.py` | HTTP contract; mocked API responses |
| `tests/test_synthesis_routes.py` | Route status codes, async job response shape |

---

## 8. Acceptance Criteria

- [ ] Submitting a research question returns a grounded answer with ≥ 1 citation.
- [ ] Every claim in the synthesis answer links to a source document.
- [ ] Evidence table shows stance badge (green/red/grey) for each row.
- [ ] Sorting evidence table by stance/year works client-side without extra request.
- [ ] Literature review draft creates at least 2 thematic sections + a gap section.
- [ ] "Send to Writing Studio" creates correct manuscript sections.
- [ ] Retraction badge appears on any reference whose DOI hits Retraction Watch.
- [ ] Hypothesis synthesis stores a `SynthesisReport` linked to the hypothesis.
- [ ] All synthesis endpoints return 404 when `evidence_synthesis_enabled=False`.
- [ ] Streaming response shows incremental output (not blank page until done).

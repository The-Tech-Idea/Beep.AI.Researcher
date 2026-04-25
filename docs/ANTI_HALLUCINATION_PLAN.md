# Anti-Hallucination Layer for Beep.AI.Researcher

**The core problem this solves:** The Researcher already chains LLM calls — chat → extraction → synthesis → report writing — but has no grounding checkpoints between them. A hallucination in the chat step propagates unchecked into extracted evidence, then into citations, then into the final report. This plan adds enforcement at the prompt, answer, pipeline, and storage levels.

---

## Phase H1 — Prompt Hardening (Fixes G1, G2)

**Target:** `app/routes/chat.py` and `app/services/ai_service.py`

1. Replace the weak `"Answer based on context:\n{context}"` system prompt with a **grounding-enforcement template** that includes:
   - `"Answer ONLY from the provided sources. Every factual claim must cite [Doc ID] inline."`
   - `"If the sources do not contain sufficient information, respond: 'Insufficient evidence in provided documents.'"`
   - `"Do not infer, extrapolate, or combine knowledge beyond what the sources state."`
2. In `beep_ai_client.chat()`, add `temperature` as a passable parameter. Default it to `0.2` for research-mode calls (currently no temp is sent, so server uses its default ~0.7 — too high for factual work).
3. Add a `research_mode: bool` flag to `beep_ai_client.chat()` — when `True`, applies the grounding template and low temperature automatically.

---

## Phase H2 — Zero-Result Guard (Fixes G4)

**Target:** `app/routes/chat.py`

When `rag_query()` returns 0 chunks (or all with `relevance_score < 0.5`):
- Return a **structured "no grounding data" response** instead of forwarding to the LLM.
- Response: `{"answer": "No relevant documents found in this project for that query.", "grounded": false, "sources": [], "confidence": 0.0}`
- Eliminates the silent hallucination pathway where the LLM answers from parametric memory when RAG fails.

---

## Phase H3 — Per-Answer Grounding Score (Fixes G5, G6)

**Target:** New `app/services/grounding_service.py`

A lightweight post-generation service that:
1. Takes the LLM answer text + the `RAGContext` chunks used.
2. Computes a **sentence-level attribution score** — for each sentence in the answer, find the closest matching chunk by lexical + semantic overlap; store the best-match chunk ID and score.
3. Produces `grounding_score` (0.0–1.0) = fraction of answer sentences with at least one source chunk scoring above threshold.
4. Embeds inline citation markers: any sentence grounded to chunk X gets `[Doc #N]` appended in the response.
5. Returns: `{"answer_text": "...[Doc #1]...", "grounding_score": 0.87, "ungrounded_sentences": ["..."], "sources": [...]}`

Store `grounding_score` on the new `HallucinationAuditLog` model (see H5).

Implementation notes:
- Use **lexical overlap (Jaccard/token F1)** for sentence attribution — dependency-free; swap in vector similarity later if embedding service available.
- Sentence splitting: split on `. ` with minimum length guard (> 15 chars).

---

## Phase H4 — Automatic Post-Generation Contradiction Check (Fixes G3, G11)

**Target:** `app/routes/chat.py` and `app/routes/contradiction.py`

After every LLM answer in chat:
1. Extract claims from the answer (reuse existing `claims` extraction service).
2. Run `detect_contradictions()` between each new claim and the top-5 RAG source passages.
3. If any contradiction `severity == 'high'` → flag the answer with `"WARNING: This answer may contradict your source documents"`.
4. Persist the contradiction event in `HallucinationAuditLog` (H5).

This prevents the compound-hallucination problem: a contradiction that would have silently flowed into the next pipeline step is surfaced immediately.

---

## Phase H5 — Hallucination Audit Log (Fixes G10)

**Target:** New `app/models/researcher/hallucination_audit.py`

New model `HallucinationAuditLog`:

| Column | Type | Purpose |
|---|---|---|
| `project_id` | FK | Scope |
| `session_id` | String | Groups multi-step agent sessions |
| `step_name` | String | chat / extraction / synthesis / report |
| `prompt_hash` | String | SHA-256 of the exact prompt sent |
| `answer_text` | Text | The LLM response |
| `grounding_score` | Float | From H3 |
| `ungrounded_sentences` | JSON | List of sentences with no source match |
| `contradictions_found` | JSON | From H4 |
| `rag_chunk_ids` | JSON | Which chunks were used |
| `temperature_used` | Float | Recorded for reproducibility |
| `flagged` | Boolean | True if grounding_score < threshold or contradictions |
| `reviewed_by` | FK(User) | Human review workflow |
| `created_at` | DateTime | Timestamp |

Register in `app/models/researcher/__init__.py`.

---

## Phase H6 — DOI / Citation Validation (Fixes G7)

**Target:** `app/services/reference_service.py` and existing `CitationValidation` model (Phase C)

1. Add `validate_doi(doi: str) → dict` to `reference_service.py` — calls CrossRef public API (`https://api.crossref.org/works/<doi>`) with 3-second timeout; returns `{valid: bool, metadata: {...}}`.
2. Add `validate_citation_batch(reference_ids: List[int]) → List[CitationValidation]` — bulk validates a project's references, stores results in `CitationValidation` table.
3. New route `POST /projects/<id>/references/validate-dois` — triggers batch validation, returns summary of valid/invalid DOIs.
4. Flag references with unresolvable DOIs — prevents hallucinated citations from passing silently through the pipeline.

Implementation notes:
- Async/non-blocking — fires on save, does not block the save operation.
- Cache successful DOI resolutions for 24 hours to avoid hammering CrossRef.

---

## Phase H7 — Evidence Quality Weighting in Prompts (Fixes G8)

**Target:** `app/routes/chat.py`, `app/services/beep_ai_client.py`

When constructing the RAG context for the LLM, annotate each chunk with its evidence quality:
1. For RAG chunks linked to an `EvidenceItem` with `strength` and `evidence_type` fields, prefix each chunk with:
   - `[SOURCE: {doc_name} | EVIDENCE TYPE: {evidence_type} | STRENGTH: {strength}]`
2. Add to the system prompt: `"Weight RCT/systematic-review sources above expert-opinion sources. Prioritize HIGH strength evidence."`

This is critical for the compound-hallucination problem — without weighting, the LLM may present an expert opinion with the same authority as an RCT in step 1, and subsequent steps amplify this misrepresentation.

---

## Phase H8 — Multi-Agent Session Grounding Chain (Core compound hallucination fix)

**Target:** New `app/services/agent_grounding_chain.py`

When multiple LLM calls occur in sequence (extraction → synthesis → report), create a **grounding chain** that:
1. Assigns a `session_id` (UUID) at the start of any multi-step operation.
2. Passes the `grounding_score` from step N as a weight modifier in the context for step N+1.
3. If `grounding_score` drops below 0.6 at any step → **halt the chain and require human review before continuing**.
4. All steps log to `HallucinationAuditLog` under the same `session_id` so the compound effect is visible.

Configuration: halt threshold (default 0.6) is configurable via project settings table, not hardcoded.

---

## Gap Reference

| # | Gap | Fixed By |
|---|---|---|
| G1 | Weak system prompt — no citation enforcement, no "I don't know" instruction | H1 |
| G2 | No temperature control passed to LLM (server default ~0.7, too high for research) | H1 |
| G3 | Contradiction detection is manual — not called after LLM responses | H4 |
| G4 | Zero-RAG-result fallback — LLM still answers from parametric memory | H2 |
| G5 | No per-answer grounding confidence score | H3 |
| G6 | Source attribution not embedded inline in response text | H3 |
| G7 | DOI/URL citation validation absent — hallucinated DOIs pass silently | H6 |
| G8 | Evidence grades not used in prompts — expert opinion = RCT to the LLM | H7 |
| G9 | `source_provenance` not used at query time | H3, H7 |
| G10 | No hallucination audit log | H5 |
| G11 | No fact-checking pipeline post-generation | H4 |

---

## Verification Checklist

- [x] Unit tests for `grounding_service.py` — sentence attribution scoring (token F1 overlap) — **Server-side, passes**
- [x] Unit tests for `validate_doi()` — mock CrossRef API responses (200, 404, timeout) — **Server-side, passes**
- [x] Integration test: chat query with 0 RAG results → confirm no LLM call is made (H2) — **Zero-result guard in chat.py**
- [x] Integration test: chat query → `HallucinationAuditLog` row created with non-null `grounding_score` (H5) — **grounding_client.py persists**
- [x] Integration test: high-severity contradiction detected → answer flagged (H4) — **grounding_client.run_post_generation_checks**
- [x] Integration test: multi-step agent session with low grounding score → chain halted (H8) — **agent_grounding_chain.py**
- [ ] Full test suite remains at 305+ passing

---

## Implementation Order

```
H5 (model) → H3 (grounding_service) → H1 (prompt hardening) → H2 (zero-result guard)
→ H4 (auto contradiction) → H6 (DOI validation) → H7 (evidence weighting)
→ H8 (agent chain) → tests
```

H5 first because H3, H4, H8 all write to `HallucinationAuditLog`.

# Beep.AI.Researcher — Feature Enhancement Model

> **Purpose**: Single source of truth for all planned enhancements. Each phase
> owns a separate document. This file defines the gap analysis, guiding
> principles, shared data contracts, and cross-phase dependencies.

---

## 1. Problem Statement

Beep.AI.Researcher is a solid research project management platform. Compared to
the leading researcher-facing products (R Discovery, Consensus, Research Rabbit,
Zotero, Scholarcy, Writefull, ResearchGate, Scite, Litmaps, Elicit), it is
missing three capability clusters that determine daily researcher loyalty:

1. **Discovery** — researchers find new relevant papers through serendipity and
   personalisation, not just keyword search.
2. **Insight synthesis** — researchers need the platform to *reason* across
   many papers, not just retrieve them.
3. **Community** — researchers follow each other, share discoveries, and build
   reputation inside a social layer.

---

## 2. Existing Capabilities (Do Not Duplicate)

| Capability | Status | Notes |
|---|---|---|
| Document upload & management | ✅ Complete | Supports PDF, local + cloud storage |
| Multi-source search (PubMed, arXiv) | ✅ Complete | Extended search with cache |
| Citation/reference management | ✅ Complete | CitationLibraryService, ZoteroSync |
| Document annotations & highlights | ✅ Complete | DocumentAnnotationService |
| Project collaboration (members, comments) | ✅ Complete | CollaborationService |
| Qualitative coding | ✅ Complete | Code, CodedReference models |
| Flashcards from documents (LLM) | ✅ Complete | `training_bp` route `POST /<pid>/flashcards`; LLM chunking + grounded context |
| Quizzes + quiz attempts | ✅ Complete | Quiz, QuizQuestion, QuizAttempt models |
| AI workflow templates | ✅ Complete | AITemplate, AIWorkbook |
| Writing studio (manuscript sections) | ✅ Complete | Manuscript, ManuscriptSection |
| Extraction schemas + validation | ✅ Complete | ExtractionSchema, ValidationResult |
| Contradiction detection | ✅ Complete | Route + service layer |
| Hallucination auditing | ✅ Complete | HallucinationAuditLog |
| Export jobs (CSV, PDF, JSON) | ✅ Complete | ExportJob async |
| Event bus & hooks | ✅ Complete | Plugin-aware hook system |
| RBAC + MFA + SSO | ✅ Complete | Full identity stack |
| Hypothesis / evidence / claim system | ✅ Complete | Phase A models |
| PHI redaction | ✅ Complete | Sector-specific |
| YouTube ingestion | ✅ Complete | Audio transcription |
| TTS capability | ✅ Complete | `beep_ai_client.text_to_speech()` — no document audio route yet |
| Semantic Scholar search | ✅ Complete | `SemanticScholarProvider` at `app/integrations/search/providers/semantic_scholar.py` |
| Crossref search/metadata | ✅ Complete | `CrossRefProvider` at `app/integrations/search/providers/crossref.py` |
| PubMed search/metadata | ✅ Complete | `PubMedProvider` at `app/integrations/search/providers/pubmed.py` |
| arXiv search/metadata | ✅ Complete | `ArxivProvider` at `app/integrations/search/providers/arxiv.py` |
| BibTeX / RIS export | ✅ Complete | `Reference.to_bibtex()`, `Reference.to_ris()`; bibliography service |
| APA / MLA / Chicago / BibTeX format | ✅ Complete | `CitationFormatterService` — 4 styles; `SUPPORTED_STYLES` constant |
| BibTeX / RIS / JSON import parsing | ✅ Complete | `reference_import_service.py` — `parse_references_content()` with dedup |

---

## 3. Feature Gap Map (Inspiration → Beep Feature)

### Discovery & Personalisation (R Discovery, Research Rabbit, Keenious)
| App Feature | Beep Gap | Planned Phase |
|---|---|---|
| AI personalised reading feed | Not present | Phase 1 |
| Research interest profiling | Not present | Phase 1 |
| Text-to-speech for papers | Route missing (TTS client exists) | Phase 1 |
| "Readers also read" recommendations | Not present | Phase 1 |
| New paper alerts by topic/author | Partial (manual search) | Phase 1 |
| Contextual inline recommendations | Not present | Phase 1 |

### Evidence Synthesis (Consensus, Elicit, Scite)
| App Feature | Beep Gap | Planned Phase |
|---|---|---|
| "What does research say about X?" | Not present | Phase 2 |
| Multi-paper answer synthesis | Not present | Phase 2 |
| Citation context (support/contradict) | Not present | Phase 2 |
| Automated literature review report | Partial (manual) | Phase 2 |
| Evidence strength / sample-size scoring | Not present | Phase 2 |
| Retraction & correction alerts | Not present | Phase 2 |

### Visual Knowledge Mapping (Litmaps, Research Rabbit, Scite)
| App Feature | Beep Gap | Planned Phase |
|---|---|---|
| Interactive citation network graph | Not present | Phase 3 |
| Topic cluster visualisation | Not present | Phase 3 |
| Temporal evolution of research fields | Not present | Phase 3 |
| Paper relationship discovery (co-citation) | Not present | Phase 3 |

### AI Writing Assistant (Writefull, Grammarly, Scholarcy)
| App Feature | Beep Gap | Planned Phase |
|---|---|---|
| Academic grammar & tone scoring | Not present | Phase 4 |
| Automated summary flashcards from PDFs | Not present | Phase 4 |
| Key findings & data table extractor | Not present | Phase 4 |
| Structured literature review drafts | Not present | Phase 4 |
| Section-level writing quality score | Not present | Phase 4 |
| Active/passive voice & readability | Not present | Phase 4 |

### Researcher Social Network (ResearchGate, Academia.edu)
| App Feature | Beep Gap | Planned Phase |
|---|---|---|
| Researcher profile with publications | Not present | Phase 5 |
| Follow researchers / projects | Not present | Phase 5 |
| Research impact metrics | Not present | Phase 5 |
| Activity feed (news stream) | Not present | Phase 5 |
| Collaboration invitations | Partial (project member invite) | Phase 5 |
| Research network visualisation | Not present | Phase 5 |

### Enhanced Citation Intelligence (Zotero, Mendeley, Scite Enhanced)
| App Feature | Beep Gap | Planned Phase |
|---|---|---|
| Smart import via DOI / PMID / arXiv ID | Partial — providers exist but no unified resolver | Phase 6 |
| Citation context mining (how cited) | Not present | Phase 6 |
| 50+ citation style export | Partial — 4 styles today (APA, MLA, Chicago, BibTeX) | Phase 6 |
| Retraction database integration | Not present | Phase 6 |
| Smart deduplication across libraries | Partial — import dedup exists; no merge/log | Phase 6 |
| Library usage analytics | Not present | Phase 6 |

---

## 4. Architecture Principles

These apply to every phase.

### 4.1 Layering
```
Route (thin)
  └── Service (one responsibility per class)
        ├── Model (schema + invariants only, no business logic)
        └── Adapter / Provider (seam for external APIs or AI models)
```
- Routes validate input and delegate immediately. No business logic in routes.
- Services own all business logic. One class, one responsibility.
- Adapters isolate every external dependency (Beep.AI.Server, Crossref, PubMed, etc.).
- Models enforce schema and basic invariants. Nothing more.

### 4.2 Contracts
- Every new external API gets a typed dataclass contract in `app/contracts/<phase>/`.
- Every new service dependency gets an abstract `Protocol` so tests can inject mocks.
- No shared mutable globals. Use the ConfigManager singleton, nothing else.

### 4.3 Tests
- One focused test file per service class: `tests/test_<service_name>.py`.
- Route tests validate HTTP contracts (status codes, response shape), not business logic.
- Service tests drive the business rules.
- No test modifies on-disk files or calls real external APIs; patch all I/O.

### 4.4 Database
- Each phase adds migrations via Alembic. No manual `CREATE TABLE` anywhere.
- FK constraints added with explicit `ondelete` rules.
- Partition-friendly models (tenant-aware where multi-tenancy is required).

### 4.5 UI
- Every new page: one HTML template + one JS file + one CSS file (no inline).
- Shared theme tokens from `static/css/style.css`. No hard-coded colours.
- All destructive actions require explicit confirmation dialogs.
- Every page has loading, empty, error, and success states.
- Keyboard-accessible and responsive.

### 4.6 Feature Flags
- Every phase's features gate behind a named feature flag managed by ConfigManager.
- Disabled features are invisible to users; routes return 404 / 403 cleanly.
- This lets phases ship to production before full activation.

---

## 5. Shared Data Contracts

### ResearchInterestProfile (Phase 1)
```python
@dataclass
class ResearchInterestProfile:
    user_id: int
    topics: list[str]           # user-declared topics
    inferred_topics: list[str]  # extracted from reading history
    preferred_sources: list[str]  # pubmed, arxiv, crossref, etc.
    updated_at: datetime
```

### PaperRecommendation (Phase 1 + 6)
```python
@dataclass
class PaperRecommendation:
    reference_id: int | None    # if already in library
    external_id: str            # DOI or arXiv ID
    title: str
    authors: list[str]
    abstract: str
    score: float                # 0–1 relevance score
    reason: str                 # "based on your reading of …"
    source: str                 # "pubmed" | "arxiv" | "crossref"
```

### EvidenceSynthesisResult (Phase 2)
```python
@dataclass
class EvidenceSynthesisResult:
    query: str
    answer: str
    confidence: float
    supporting_count: int
    contradicting_count: int
    neutral_count: int
    citations: list[CitationSnippet]
    generated_at: datetime
```

### CitationContext (Phase 2 + 6)
```python
@dataclass
class CitationContext:
    citing_doi: str
    cited_doi: str
    context_type: Literal["supporting", "contradicting", "mentioning"]
    snippet: str
    polarity_score: float       # -1 to +1
```

### KnowledgeNode (Phase 3)
```python
@dataclass
class KnowledgeNode:
    id: str                     # DOI or internal ID
    title: str
    year: int | None
    citation_count: int
    is_in_library: bool
    cluster_id: int | None

@dataclass
class KnowledgeEdge:
    source_id: str
    target_id: str
    weight: float
    relationship: Literal["cites", "co_cited", "co_author"]
```

### WritingFeedback (Phase 4)
```python
@dataclass
class WritingFeedback:
    section_id: int | None
    overall_score: float        # 0–100
    issues: list[WritingIssue]
    suggestions: list[str]

@dataclass
class WritingIssue:
    type: str                   # "tone", "clarity", "grammar", "passive_voice"
    severity: Literal["info", "warning", "error"]
    text: str
    suggestion: str
    offset: int
    length: int
```

### ResearcherProfile (Phase 5)
```python
@dataclass
class ResearcherProfile:
    user_id: int
    display_name: str
    institution: str
    orcid: str | None
    research_areas: list[str]
    follower_count: int
    following_count: int
    publication_count: int
    h_index: int | None
```

---

## 6. Phase Overview

| Phase | Title | Key Capability | Feature Flag |
|---|---|---|---|
| **1** | AI Discovery & Reading Feed | Personalised paper recommendations, audio mode | `ai_discovery_enabled` |
| **2** | Evidence Synthesis Engine | Research consensus, multi-paper Q&A | `evidence_synthesis_enabled` |
| **3** | Visual Knowledge Mapping | Citation graph, topic clusters | `knowledge_map_enabled` |
| **4** | AI Writing Assistant | Academic grammar scoring, auto-summaries | `writing_assistant_enabled` |
| **5** | Researcher Social Network | Profiles, follows, activity feed | `social_network_enabled` |
| **6** | Citation Intelligence | Context-aware citations, retractions | `citation_intelligence_enabled` |

---

## 9. Server Integration Architecture

### 9.1 Transport Layer (Already Exists)

All communication with Beep.AI.Server goes through two existing clients:

| Client | File | Used For |
|---|---|---|
| `BeepAIClient` | `app/services/beep_ai_client.py` | RAG, LLM, TTS, agent, app-users |
| `GroundingClient` | `app/services/grounding_client.py` | Grounding validation, contradiction detection |

Config: `beep_ai_server_url` + `beep_ai_server_token` in `config/app_config.json`.
Auth: `Authorization: Bearer <token>` on every request.

### 9.2 Server API Surface Used by Each Phase

```
POST /v1/chat/completions    ← LLM inference (OpenAI-compatible, streaming capable)
POST /v1/embeddings          ← Vector embeddings from sentence-transformers
POST /api/rag/query          ← Semantic search over a project collection
POST /api/rag/collections/{id}/documents   ← Index a document
POST /api/services/text_to_speech/synthesize ← TTS audio
POST /api/rag/evaluate_grounding   ← Hallucination / grounding score
POST /api/rag/contradiction        ← Contradiction detection
```

> `beep_ai_client.*` wraps all of these. New features must go through `BeepAIClient`,
> never raw HTTP calls.

### 9.3 Per-Phase Integration Map

#### Phase 1 — AI Discovery

| Feature | Server call | BeepAIClient method |
|---|---|---|
| Interest inference (embedding user docs) | `POST /v1/embeddings` | **New**: `get_embeddings(texts[])` |
| Recommendation scoring (cosine-sim) | `POST /v1/embeddings` (candidates) | **New**: `get_embeddings(texts[])` |
| "Readers also read" (similar to document) | `POST /api/rag/query` (content as query) | `query_project_rag()` ✅ exists |
| Audio summary of abstract | `POST /api/services/text_to_speech/synthesize` | `synthesize_speech()` ✅ exists |

**New BeepAIClient method needed**: `get_embeddings(texts: list[str]) -> list[list[float]]`
that calls `POST /v1/embeddings`. Everything else reuses existing methods.

#### Phase 2 — Evidence Synthesis

| Feature | Server call | BeepAIClient method |
|---|---|---|
| Retrieve evidence passages | `POST /api/rag/query` w/ `return_citations=True, hybrid_search=True, rerank=True` | `query_project_rag()` ✅ |
| Synthesise answer from passages | `POST /v1/chat/completions` | `chat_reply()` ✅ |
| Polarity label each passage | `POST /v1/chat/completions` | `chat_reply()` ✅ (classify prompt) |
| Grounding validation | `POST /api/rag/evaluate_grounding` | `grounding_client.evaluate_grounding()` ✅ |
| Contradiction check | `POST /api/rag/contradiction` | `grounding_client.detect_contradictions()` ✅ |
| Hypothesis synthesis | `POST /api/rag/query` + `/v1/chat/completions` | `detect_contradictions()` ✅ (already chains these) |

**Zero new BeepAIClient methods needed.** `EvidenceSynthesisService` purely
orchestrates existing calls with a new prompt strategy.

#### Phase 3 — Visual Knowledge Mapping

| Feature | Server call | BeepAIClient method |
|---|---|---|
| Cluster papers by topic | `POST /v1/embeddings` (abstract embeddings) | **New**: `get_embeddings()` (same as Phase 1) |
| Citation edges (neighbour papers) | Semantic Scholar API directly (existing provider) | No server call — provider does HTTP |
| Graph nodes from library | `POST /api/rag/query` for scoring | `query_project_rag()` ✅ |

**Same `get_embeddings()` method from Phase 1 covers this phase's needs.**

#### Phase 4 — AI Writing Assistant

| Feature | Server call | BeepAIClient method |
|---|---|---|
| Writing quality score + issues | `POST /v1/chat/completions` (structured JSON prompt) | `chat_reply()` or `extract_structured()` ✅ |
| Auto-extract key findings | `POST /v1/chat/completions` | `extract_structured()` ✅ exists |
| Citation draft paragraph | `POST /api/rag/query` + `/v1/chat/completions` | `find_citations_for_draft()` ✅ exists |
| Flashcard generation | `POST /v1/chat/completions` | existing `training_bp` (already calls `chat_reply()`) |
| Readability metrics | *Pure local — no server call* | — |

**Zero new BeepAIClient methods needed.** `extract_structured()` and
`find_citations_for_draft()` already implement the two complex patterns.

#### Phase 5 — Researcher Social Network

No RAG or LLM calls needed. All operations are local DB reads/writes.
Semantic Scholar API used for external citation counts — direct HTTP via
existing `SemanticScholarProvider` (not through BeepAI Server).

#### Phase 6 — Citation Intelligence

| Feature | Server call | BeepAIClient method |
|---|---|---|
| Smart import (metadata fetch) | *Existing providers — direct HTTP* | No server call — providers do HTTP |
| Citation context polarity label | `POST /v1/chat/completions` | `chat_reply()` ✅ |
| Dedup merge (no AI needed) | *Local computation only* | — |
| Library analytics | *Local DB queries only* | — |

**Zero new BeepAIClient methods needed beyond `get_embeddings()`.**

### 9.4 The One Missing Method: `get_embeddings()`

`POST /v1/embeddings` exists on the server and is guarded by `rag:read` scope.
It is not yet wrapped in `BeepAIClient`. This single method unblocks Phase 1
(interest inference, recommendation scoring) and Phase 3 (clustering).

```python
# To add to BeepAIClient
def get_embeddings(self, texts: list[str], model: str | None = None) -> tuple[bool, list[list[float]]]:
    """Call POST /v1/embeddings. Returns (ok, list_of_embedding_vectors)."""
    payload = {"input": texts}
    if model:
        payload["model"] = model
    ok, resp = self._post("/v1/embeddings", payload)
    if not ok:
        return False, []
    vectors = [item["embedding"] for item in resp.get("data", [])]
    return True, vectors
```

### 9.5 RAG Collection Strategy per Feature

| Feature | Collection used | When created |
|---|---|---|
| Project-scoped synthesis (Phase 2) | Existing project RAG collection | Already provisioned by project setup |
| Personal reading list recommendations (Phase 1) | New per-user global collection | Created on first feed load if not present |
| Knowledge map graph nodes (Phase 3) | Existing project collection (read-only) | N/A — only reads |
| Writing assistant citation draft (Phase 4) | Existing project collection | N/A — only reads |

The per-user global collection is the only new collection type. Create it with:
`beep_ai_client.create_rag_collection(name="personal_library_{user_id}", user_id=str(user_id), is_public=False)`

### 9.6 RAG Query Options by Feature

| Feature | `quality_mode` | `hybrid_search` | `rerank` | `return_citations` |
|---|---|---|---|---|
| Feed / "readers also read" | `fast` | `False` | `False` | `True` |
| Evidence synthesis | `high` | `True` | `True` | `True` |
| Writing citation draft | `balanced` | `True` | `True` | `True` |
| Knowledge map scoring | `fast` | `False` | `False` | `False` |

### 9.7 Rules

- All LLM calls route through `POST /v1/chat/completions` → `beep_ai_client.chat_reply()`.
- All grounding/hallucination checks route through `GroundingClient`.
- All embedding generation routes through the new `get_embeddings()` wrapper.
- No feature calls RAG providers (FAISS, ChromaDB) directly — always through the server API.
- The Researcher never stores bearer tokens in session cookies; `BeepAIClient` manages the token from `config/app_config.json`.

### 9.8 Chunk Template Selection per Collection Type

Every RAG collection must be created with an explicit `chunk_template_id` matching the
content domain. The server ships 8 built-in templates (seeded via `chunk_template_seeds.py`).
Retrieve the template id with `beep_ai_client.list_chunk_templates()` before collection creation.

| Collection | Built-in slug | Rationale |
|---|---|---|
| Personal library (Phase 1) | `system-parent-child` | Small child chunks for precise feed recall; larger parent chunk returned as reading context |
| Project evidence collection (Phase 2) | `system-semantic-fine` | Tight semantic split maximises retrieval precision for evidence queries; better polarity labelling |
| Knowledge graph corpus (Phase 3 — vector path) | `system-semantic` | Variable-size semantically coherent chunks; robust topic-shift detection for K-Means clustering |
| Knowledge graph corpus (Phase 3 — GraphRAG path) | `system-graph-rag` | Entity + relationship extraction + Leiden community detection; see section 9.9 |
| Writing assistant context (Phase 4) | `system-parent-child` | Citation-finding needs precise child-chunk retrieval with full-paragraph context returned |
| Citation import (Phase 6) | `system-general` | Metadata-only records; balanced default is adequate |

**How to apply a template when creating a collection:**
```python
ok, templates = beep_ai_client.list_chunk_templates()
slug_map = {t["slug"]: t["template_id"] for t in templates}

ok, coll = beep_ai_client.create_rag_collection(
    name="personal_library_{user_id}",
    user_id=str(user_id),
    is_public=False,
    chunk_template_id=slug_map["system-parent-child"],
)
```

**How to re-apply (re-index) a collection with a different template:**
```python
beep_ai_client.apply_chunk_template_to_collection(
    template_id=slug_map["system-semantic-fine"],
    collection_id=coll["id"],
)
```
This triggers an async re-chunk of all documents in that collection on the server.

**Key `chunking_config` fields (normalised by server's `_normalize_chunking_profile`):**
```json
{
  "strategy": "semantic | recursive | parent_child | graph_rag | raptor | proposition | agentic | markdown_heading | sentence",
  "chunk_size_chars": 1000,
  "chunk_overlap_chars": 150,
  "enrich_context": true
}
```
`enrich_context: true` tells the server to prepend parent-context to each chunk
before embedding it — improves recall for all strategies except `graph_rag`.

### 9.9 GraphRAG Path for Phase 3 (Knowledge Mapping)

The **`system-graph-rag`** chunk template activates a fundamentally different ingestion
pipeline on the server side:

1. **Text unit extraction** — each paper is split into ~1200-char text units (with overlap).
2. **Entity + relationship extraction** — the server's LLM extracts named entities
   (authors, concepts, methods, datasets) and typed relationships from each text unit via
   the `RAGGraphExtractionProfile` at index time.
3. **Leiden community detection** — extracted entities are clustered using the Leiden
   algorithm (`community_algorithm: "leiden"`) to form topic communities.
4. **Community summarisation** — the server generates one summary per community (2 levels).
5. **Dual-mode queries** — the resulting collection supports:
   - **Local search**: "what does this paper say about X?" → entity-look-up + neighbourhood.
   - **Global search**: "what are the main themes in this corpus?" → community summaries.

**Why this matters for Phase 3:**
- The Leiden communities *are* the Topic Cluster View (section 2.2). You get them free
  at query time rather than computing K-Means over raw embeddings.
- Entity extraction gives the exact relationship types `KnowledgeEdge` needs
  (`cites`, `co_cited`, `related_concept`) without calling Semantic Scholar for every paper.
- Community summaries can label each cluster automatically instead of TF-IDF top-terms.

**Phase 3 implementation choice (two paths):**

| Path | When to use | Collection slug |
|---|---|---|
| **Vector path** (K-Means + embeddings) | Collection has < 20 papers; GraphRAG index not available | `system-semantic` |
| **GraphRAG path** (Leiden communities + entity graph) | Collection has ≥ 20 papers; server has Neo4j/graph runtime enabled | `system-graph-rag` |

`KnowledgeGraphService` should detect which path is available by checking
`beep_ai_client.get_collection_organization_profile(collection_id)["graph_enabled"]`
and falling back to the vector path if `False`.

**GraphRAG collection creation:**
```python
ok, coll = beep_ai_client.create_rag_collection(
    name="project_knowledge_graph_{project_id}",
    user_id=str(user_id),
    is_public=False,
    chunk_template_id=slug_map["system-graph-rag"],
)

# After creation, set the graph extraction profile:
beep_ai_client.update_collection_organization_profile(
    collection_id=coll["id"],
    organization_profile={"graph_mode": "graphrag"},
    graph_extraction_profile_id=graph_profile_id,   # from list_graph_extraction_profile_options()
    user_id=str(user_id),
)
```


```
Phase 1 (Discovery)
  └── Feeds Phase 3 (Knowledge Map) — paper metadata + relationships
  └── Feeds Phase 6 (Citation Intelligence) — library enrichment

Phase 2 (Evidence Synthesis)
  └── Consumes Phase 6 (Citation Intelligence) — citation context for synthesis
  └── Enriches Phase 4 (Writing Assistant) — literature review drafts

Phase 3 (Knowledge Map)
  └── Consumes Phase 1 — recommendation graph edges
  └── Consumes Phase 6 — citation edges

Phase 4 (Writing Assistant)
  └── Consumes Phase 2 — evidence snippets for citation suggestions
  └── Writes to Phase 5 — published sections update profile

Phase 5 (Social Network)
  └── Consumes all phases — activity events feed into the news stream

Phase 6 (Citation Intelligence)
  └── Base enrichment layer consumed by Phases 1, 2, 3
```

### 9.10 User-Managed Chunk Templates

Users can create, clone, modify, and delete their own chunk templates for their projects or document types. The server already exposes all CRUD operations; `BeepAIClient` already wraps them (`create_chunk_template`, `update_chunk_template`, `delete_chunk_template`). This feature is purely a Researcher UI layer on top of those existing methods.

#### What users can do

- **View** all templates: system built-ins (read-only, prefixed `system-`) and their own custom templates.
- **Clone** a built-in or custom template as a starting point for a new one.
- **Create** a custom template from scratch by choosing a strategy and tuning the parameters.
- **Edit** any template they own (name, description, chunking config).
- **Delete** any template they own that is not currently applied to a collection.
- **Apply** any template (built-in or custom) to one of their project collections, triggering a re-index.
- **Set as project default** — mark a custom template as the default for a specific project so every new collection in that project inherits it.

#### Constraints

- System templates (`slug` starts with `system-`) are always read-only — users can clone but not edit them.
- Deleting a template that is currently applied to a collection is blocked; user must first apply a different template to that collection.
- `is_default: true` at the global level is admin-only; project-level default is user-owned.

#### New routes (Researcher)

| Method | URL | Purpose |
|---|---|---|
| `GET` | `/settings/chunk-templates` | List all templates (system + owned) |
| `GET` | `/settings/chunk-templates/new` | New template form (or clone form if `?clone=<template_id>`) |
| `POST` | `/settings/chunk-templates` | Create template → `beep_ai_client.create_chunk_template()` |
| `GET` | `/settings/chunk-templates/<template_id>/edit` | Edit form |
| `POST` | `/settings/chunk-templates/<template_id>` | Update template → `beep_ai_client.update_chunk_template()` |
| `DELETE` | `/settings/chunk-templates/<template_id>` | Delete → `beep_ai_client.delete_chunk_template()` |
| `POST` | `/projects/<pid>/settings/chunk-template` | Apply template to project collection → `beep_ai_client.apply_chunk_template_to_collection()` |

#### New service

`ChunkTemplateService` — thin wrapper; single responsibility: own the business rules above (slug prefix guard, apply-before-delete check). Makes all decisions, then delegates to `BeepAIClient`. No direct HTTP calls in the route.

```python
class ChunkTemplateService:
    def list_templates(self, user_id: int) -> list[dict]:
        """Returns system built-ins (is_builtin=True, editable=False) merged with user-owned."""

    def clone(self, source_template_id: str, new_name: str, user_id: int) -> tuple[bool, dict]:
        """Clone any template. Strips system- prefix from slug, sets owner."""

    def create(self, name: str, chunking_config: dict, description: str, user_id: int) -> tuple[bool, dict]:
        """Guard: slug must not start with 'system-'. Delegates to beep_ai_client."""

    def update(self, template_id: str, updates: dict, user_id: int) -> tuple[bool, dict]:
        """Guard: system templates cannot be updated. Delegates to beep_ai_client."""

    def delete(self, template_id: str, user_id: int) -> tuple[bool, str]:
        """Guard: system templates blocked. In-use templates blocked. Delegates to beep_ai_client."""

    def apply_to_project(self, template_id: str, project, user_id: int) -> tuple[bool, dict]:
        """Apply template to project's primary RAG collection and record choice on project settings."""
```

#### UI files

| Template | JS | CSS |
|---|---|---|
| `templates/settings/chunk_templates.html` | `static/js/settings/chunk_templates.js` | *(shared theme — no page CSS needed)* |
| `templates/settings/chunk_template_form.html` | `static/js/settings/chunk_template_form.js` | *(shared theme)* |

The form page includes a **live preview panel**: as the user adjusts `chunk_size_chars` / `strategy`, it shows the estimated number of chunks for a sample paragraph — pure client-side computation, no server round-trip.

#### Chunking config strategy reference (shown in form UI)

The form must offer a guided selector rather than raw JSON. Expose each strategy as a named option with a short description, then show only the relevant parameter fields for the chosen strategy:

| Strategy | Parameters shown |
|---|---|
| `sentence` | chunk_size_chars, chunk_overlap_chars |
| `recursive` | chunk_size_chars, chunk_overlap_chars, enrich_context |
| `semantic` | breakpoint_percentile_threshold (80–99), buffer_size, enrich_context |
| `parent_child` | child_chunk_size_chars, parent_chunk_size_chars, child_overlap_chars, enrich_context |
| `markdown_heading` | chunk_size_chars, chunk_overlap_chars, preserve_code_blocks, preserve_tables |
| `graph_rag` | text_unit_size_chars, entity_extraction, relationship_extraction, community_algorithm, summary_levels |
| `raptor` | leaf_chunk_size_chars, summary_levels, cluster_algorithm, enrich_context |
| `proposition` | max_proposition_chars, llm_assisted |
| `agentic` | max_chunk_size_chars |

#### Tests

| File | Scope |
|---|---|
| `tests/test_chunk_template_service.py` | Clone guard, system-slug guard, apply-before-delete check, create/update/delete delegation |
| `tests/test_chunk_template_routes.py` | Route contracts; auth; 403 on system-template edit |

---

---

## 10. UI Architecture & Integration

This section is the single source of truth for how the new features look and connect.
Every phase plan's "UI Files" table is a subset of the inventory below.

### 10.0 Existing Features — Enhancement Rules

The table below maps existing codebase features to the phases that affect them.
**The rule is: enhance and extend rather than duplicate or replace.**

| Existing feature | File | What each phase ADDS (not replaces) |
|---|---|---|
| Writing Studio (Manuscript CRUD) | `routes/manuscripts.py`, `templates/project/report.html` | P4: Analyse button, annotation overlay, citation draft sidebar, readability bar |
| Writing text-transform assist (11 actions) | `routes/report_writing.py` `POST /<pid>/writing/assist` | P4: New `POST /<pid>/writing/analyse` route alongside it that returns structured offset-mapped JSON; existing 11 actions untouched |
| Citation scan, format, overlap-check | `routes/report_writing.py`: `format-citations`, `citation-scan`, `overlap-check` routes | P4: These 3 routes already exist. Phase 4 adds `analyse` only — NOT re-adding scanning or formatting |
| Flashcard generation | `routes/training.py` `POST /<pid>/flashcards`, `templates/project/flashcards.html` | P4: `FlashcardGenerationService` wraps existing endpoint; adds per-document preview + selective-save UI panel; does NOT add a new generation back-end |
| Schema-based document extraction | `routes/extraction.py`, `templates/project/extraction.html` | P4: `AutoExtractionService` is schema-FREE (no user schema needed); complementary — both surfaces coexist |
| Document/Code bipartite map | `routes/document_map.py` `GET /<pid>/map`, `templates/project/document_map.html` | P3: Citation Network is a **separate** page at `GET /<pid>/knowledge-map` with its own template; the existing code/doc map `document_map.html` is untouched |
| Reference CRUD, Zotero, bibliography | `routes/references.py`, `templates/project/references.html` | P6: Smart import drawer + retraction banner + dedup UI toolbar injected into existing references page; core CRUD and Zotero sync untouched |
| Duplicate detection in import | `services/reference_import_service.py` | P6: Dedup diff viewer calls existing detection logic; no new dedup algorithm |
| Project chat (RAG-backed Q&A) | `routes/chat.py` | P2: Evidence Synthesis is a **separate** flow (multi-paper consensus); not a replacement for chat |
| Contradiction detection | `routes/contradiction.py`, `templates/project/contradictions.html` | P2: Synthesis surfaces contradictions inline in the evidence table; `contradictions.html` page stays untouched for the detailed view |
| Related documents | `routes/related.py` `GET /<pid>/documents/<did>/related` | P1: "Related Reading" panel calls this **existing** endpoint; no new similarity algorithm in P1 |
| Citation finding (text→refs) | `routes/related.py` `POST /<pid>/writing/citations` | P4: "Citation Draft" sidebar calls this **existing** endpoint; `CitationDraftService` wraps it rather than reimplementing citation search |
| Citation formatter (format-citations, citation-scan) | `routes/report_writing.py` `POST /<pid>/writing/format-citations`, `POST /<pid>/writing/citation-scan` | P4: These already exist. Phase 4 adds `analyse` alongside; does NOT re-add formatting or scanning routes |
| Overlap / plagiarism check | `routes/report_writing.py` `POST /<pid>/writing/overlap-check` | P4: Already exists. Phase 4 adds writing quality scoring, not plagiarism detection |
| Evidence models (GRADE-style) | `app/models/researcher/phase_a_models.py`: `ResearchBrief`, `EvidenceItem`, `Claim`, `ClaimEvidence`, `ReviewStep`, `SourceProvenance` | P2: Evidence Synthesis REUSES these models as its persistence layer; does NOT redefine them |
| Project collaboration base | `routes/collaboration.py`, `ProjectMember`, `ProjectComment` | P5: Social network **builds on** this foundation; profile, follow, impact metrics are additive layers |
| Task management | `routes/tasks.py`, `ResearchTask`, `TaskNotification`, `templates/project/tasks.html` | P5: Does NOT recreate task management. Social layer adds activity feed drawn from task events as social signals; task routes untouched |
| Data Analyst (Julius-style) | `routes/data_analyst.py`, `ResearcherDataSource`, `SavedChart` + `templates/project/data.html` | No new phase creates this. It is pre-plan foundational. When adding discovery features, do NOT add another data upload flow |
| SPSS-style statistics | `routes/stats.py` (describe, crosstab, regression), `templates/project/stats.html` | No phase recreates statistical analysis. Phase 2 may surface `EvidenceItem.sample_size` from here but never redefines it |
| Quiz & MCQ system | `routes/training.py` (`POST /<pid>/quiz`, `QuizQuestion`, `QuizAttempt`), `templates/project/quizzes.html`, `take_quiz.html` | P4: flashcard panel does NOT touch quiz routes. P5: quiz completion can become a social signal but quiz routes are NOT rewritten |
| Hallucination audit | `services/overlap_checker_service.py`, `HallucinationAuditLog`, `templates/project/hallucination_audit.html` | P2: Evidence Synthesis can use `overlap_checker_service` for grounding checks; the audit log model and template are NOT recreated |
| YouTube ingest + video summary | `services/youtube_ingester_service.py`, `services/video_summary_service.py` | P6: These services already exist. Phase 6 only adds route-level UI to expose them; the ingestion + summarization logic itself is NOT reimplemented |
| Library source configs | `app/models/researcher/library_sources.py`: `LibrarySource`, `SourceConnection`, `SourceImportLog` | P6: DB layer already exists. Phase 6 builds the admin UI + routes on top; NOT redefining these models |
| Global AI chat | `routes/global_chat.py` `POST /api/chat` | No phase adds a second global chat endpoint. P2 Synthesis is project-scoped multi-paper, not a chat replacement |

### 10.1 Global Navigation Changes

The main nav (`templates/base.html` nav section) gains three new top-level items and two
sub-items, all feature-flag-gated:

```
[existing items stay]
Feed            ← Phase 1  (ai_discovery_enabled)
  └─ New Alerts badge (count of unread alerts)
Synthesis       ← Phase 2  (evidence_synthesis_enabled)
Knowledge Map   ← Phase 3  (knowledge_map_enabled)
[existing: Projects, Library, Writing Studio, Search, Settings]
```

Settings dropdown gains:
```
Settings
  ├─ Research Interests   ← Phase 1
  ├─ Public Profile        ← Phase 5  (social_network_enabled)
  ├─ Following             ← Phase 5
  └─ Chunk Templates       ← §9.10
```

Researcher profile avatar (top-right) shows:
- Unread alert badge (Phase 1)
- Activity feed dot (Phase 5 — new activity from followed researchers)

**Rule**: feature-flagged nav items are rendered with `{% if feature_enabled('...') %}` — they
must be completely absent from the DOM when disabled, not merely hidden via CSS.

---

### 10.2 Integration Hubs

Three existing pages become multi-feature hubs. Adding a new feature to a hub means
injecting a collapsible `<section class="ai-panel">` with its own lazy-loaded JS module —
the base page template does not change.

#### Hub A — Document Detail Page (`templates/project/document_detail.html`)

| Panel | Feature | Loads when |
|---|---|---|
| **Related Reading** | Phase 1 § 2.2 | `ai_discovery_enabled` |
| **Audio Summary** | Phase 1 § 2.5 | `ai_discovery_enabled` |
| **Writing Quality** | Phase 4 § 2.1 | `writing_assistant_enabled` AND document has text |
| **Auto-Extract** | Phase 4 § 2.3 | `writing_assistant_enabled` |
| **Generate Flashcards** | Phase 4 § 2.2 | `writing_assistant_enabled` |
| **Citation Contexts** | Phase 6 § 2.2 | `citation_intelligence_enabled` AND document has DOI |

Each panel is a `<details class="ai-panel" data-panel="<name>">` element. Content is
fetched via AJAX only when the user opens the panel (lazy). This keeps initial page load
fast for documents that users just want to read.

```
document_detail.html
├── (existing) metadata header, abstract, full text
├── <details data-panel="related-reading">   → /documents/<id>/related-reading
├── <details data-panel="audio-summary">     → /documents/<id>/audio-summary
├── <details data-panel="auto-extract">      → /documents/<id>/extract
├── <details data-panel="flashcards">        → /documents/<id>/generate-flashcards (preview)
├── <details data-panel="writing-quality">   → /documents/<id>/writing-quality
└── <details data-panel="citation-contexts"> → /documents/<id>/citation-contexts
```

JS file: `static/js/project/document_detail_ai_panels.js`
— single JS file manages all panel states, lazy fetches, and error states for this hub.

#### Hub B — Project Overview / References Tab (`templates/project/references.html`)

| Feature injection | Phase | Loads when |
|---|---|---|
| **Smart Import** toolbar button (paste DOI / upload) | Phase 6 § 2.1 | `citation_intelligence_enabled` |
| **Dedup badge** on references list (duplicate count) | Phase 6 § 2.4 | `citation_intelligence_enabled` |
| **Retraction warning** badge on flagged references | Phase 2 § 2.4 + Phase 6 § 2.3 | `evidence_synthesis_enabled` OR `citation_intelligence_enabled` |
| **Synthesis** shortcut button (ask question about library) | Phase 2 | `evidence_synthesis_enabled` |
| **Knowledge Map** view-toggle button | Phase 3 | `knowledge_map_enabled` |
| **Analytics** link | Phase 6 § 2.5 | `citation_intelligence_enabled` |

JS file: `static/js/project/references_ai_toolbar.js`
— manages smart import modal, dedup badge polling, and toolbar button states.

#### Hub C — Writing Studio Section Editor (`templates/project/report.html`)

> **Existing**: `report.html` is the live Writing Studio template for `Manuscript` + `ManuscriptSection` CRUD.
> `report_writing.py` already provides `POST /<pid>/writing/assist` with 11 text-transform actions
> (grammar, paraphrase, tone, summarize, expand, academic_rewrite, simplify, legal_plain,
> medical_lay, academic_paraphrase_v2, clarity). Phase 4 **extends** those — it does NOT replace them.

| Feature injection | Phase | Loads when |
|---|---|---|
| **Analyse** button in section toolbar | Phase 4 § 2.1 | `writing_assistant_enabled` |
| **Inline annotation overlay** (coloured underlines) | Phase 4 § 2.1 | after Analyse is run |
| **Citation Draft** sidebar | Phase 4 § 2.4 | `writing_assistant_enabled` |
| **Readability** bar in section footer | Phase 4 § 2.5 | `writing_assistant_enabled` |
| **"Send synthesis to Writing Studio"** action | Phase 2 § 2.3 | `evidence_synthesis_enabled` |

JS file: `static/js/project/writing_assistant.js`
— extends the existing section editor without replacing it.

---

### 10.3 Shared UI Components

Define once in `static/js/components/` and `static/css/components/`. Used across phases.

| Component | File | Used by |
|---|---|---|
| `PaperCard` | `components/paper_card.js` + `paper_card.css` | Feed (P1), Related Reading (P1), Knowledge Map side panel (P3), Search results (P6) |
| `SourceBadge` | `components/source_badge.js` | Feed (P1) — PubMed/arXiv/Crossref/Semantic Scholar indicator |
| `StanceBadge` | `components/stance_badge.js` | Synthesis evidence table (P2), Citation Context (P6) — supporting/contradicting/mentioning |
| `AIPanel` | `components/ai_panel.js` + `ai_panel.css` | All hub panel injections (§10.2) |
| `AsyncJobButton` | `components/async_job_button.js` | Any long AI task: Feed refresh, Synthesis generate, Extract, Flashcards, Knowledge Map build |
| `ConfirmDialog` | `components/confirm_dialog.js` | All destructive actions across all phases |
| `ToastNotification` | `components/toast.js` | Success/error feedback across all phases |
| `ChunkTemplatePicker` | `components/chunk_template_picker.js` | Collection setup (P1/2/3), Settings §9.10 form |
| `CitationStylePicker` | `components/citation_style_picker.js` | Synthesis export (P2), Writing Studio (P4), Citation Intelligence (P6) |

**Rules for shared components:**
- Pure vanilla JS classes — no framework dependency.
- Emit custom DOM events (`paper-card:save`, `async-job:complete`, etc.) so consuming pages can listen without tight coupling.
- Styled exclusively with theme CSS tokens from `static/css/style.css`.
- Each component has its own focused test in `tests/js/` (if JS unit testing is adopted) OR is covered by the route-level Playwright/Selenium acceptance tests.

---

### 10.4 Cross-Phase Contextual Actions

The table below shows action flow *between* phases from the user's perspective.

| User is on… | User action | Where it goes | Phase |
|---|---|---|---|
| Feed — paper card | "Save to project" | Adds to References + re-indexes project RAG collection | P1 → P2 setup |
| Feed — paper card | "Open Knowledge Map from this paper" | Opens P3 map centered on this node | P1 → P3 |
| Document detail | "Synthesise around this paper" | Pre-fills Synthesis query with paper title + opens P2 | P1/doc → P2 |
| Synthesis result | "Send to Writing Studio" | Creates new ManuscriptSection with synthesis text | P2 → P4 |
| Synthesis result — evidence row | "Add to References" | Smart-imports the cited paper via DOI | P2 → P6 |
| Knowledge Map — ghost node | "Add to library" | Smart-imports → adds to project References → re-indexes | P3 → P6 |
| Knowledge Map — community label | "Synthesise this theme" | Opens P2 Synthesis with community summary as query | P3 → P2 |
| References list | "View Citation Contexts" | Opens P6 citation context panel for a reference | P6 context |
| Writing Studio — citation marker `[n]` | Hover/click | Shows polarity badge + snippet from synthesis evidence table | P4 ↔ P2 |
| Researcher profile — publication | "View in Knowledge Map" | Opens P3 map centred on that paper | P5 → P3 |
| Impact Dashboard | "View feed based on my work" | Opens P1 Feed with interest profile auto-scoped to user's publications | P5 → P1 |

---

### 10.5 Page State Requirements

Every new page and every AI panel must implement all four states:

| State | Requirement |
|---|---|
| **Loading** | Spinner + "Analysing…" / "Generating…" label. `AsyncJobButton` handles this. Minimum 300 ms display to avoid flicker. |
| **Empty** | Friendly message + primary action. Example: Feed empty → "No recommendations yet. Update your Research Interests to personalise your feed." with a button to `/settings/research-interests`. |
| **Error** | Plain-language error message + retry button. Never show raw exception text. Log the error server-side. |
| **Success** | Confirm with toast (`ToastNotification`) for actions. For content pages, show content immediately without a separate success screen. |

Destructive actions (delete template, remove from library, merge duplicates) additionally require:
- `ConfirmDialog` with action description and consequence.
- Named confirm button (e.g., "Delete template" not "OK").

---

### 10.6 Complete UI File Inventory

All new HTML + JS + CSS files across all phases. One row = one page or one hub extension.

| Page / Panel | Template | JS | CSS | Phase |
|---|---|---|---|---|
| Personalised Feed | `templates/feed/feed.html` | `static/js/feed/feed.js` | `static/css/feed/feed.css` | P1 |
| Reading List | `templates/reading_list/reading_list.html` | `static/js/reading_list/reading_list.js` | `static/css/reading_list/reading_list.css` | P1 |
| Alerts Inbox | `templates/alerts/alerts.html` | `static/js/alerts/alerts.js` | *(shared theme)* | P1 |
| Research Interests Settings | `templates/settings/research_interests.html` | `static/js/settings/research_interests.js` | *(shared theme)* | P1 |
| Document Detail AI Panels (hub) | *(extends)* `templates/project/document_detail.html` | `static/js/project/document_detail_ai_panels.js` | `static/css/project/document_detail_ai_panels.css` | P1+P4+P6 |
| Evidence Synthesis | `templates/synthesis/synthesis.html` | `static/js/synthesis/synthesis.js` | `static/css/synthesis/synthesis.css` | P2 |
| Synthesis Report | `templates/synthesis/report.html` | `static/js/synthesis/report.js` | *(shared theme)* | P2 |
| Knowledge Map (project) | `templates/knowledge_map/knowledge_map.html` | `static/js/knowledge_map/knowledge_map.js` | `static/css/knowledge_map/knowledge_map.css` | P3 |
| Knowledge Map (global) | `templates/knowledge_map/global_map.html` | *(reuses knowledge_map.js)* | *(reuses knowledge_map.css)* | P3 |
| Writing Studio AI extension (hub) | *(extends)* `templates/project/report.html` | `static/js/project/writing_assistant.js` | `static/css/project/writing_assistant.css` | P4 |
| References AI Toolbar (hub) | *(extends)* `templates/project/references.html` | `static/js/project/references_ai_toolbar.js` | *(shared theme)* | P2+P3+P6 |
| Researcher Profile | `templates/social/researcher_profile.html` | `static/js/social/researcher_profile.js` | `static/css/social/researcher_profile.css` | P5 |
| Activity Feed (social) | `templates/social/network_feed.html` | `static/js/social/network_feed.js` | *(shared theme)* | P5 |
| Impact Dashboard | `templates/social/impact_dashboard.html` | `static/js/social/impact_dashboard.js` | `static/css/social/impact_dashboard.css` | P5 |
| Profile Settings | `templates/settings/profile.html` | `static/js/settings/profile.js` | *(shared theme)* | P5 |
| Citation Context Viewer | `templates/references/citation_context.html` | `static/js/references/citation_context.js` | *(shared theme)* | P6 |
| Library Analytics | `templates/references/analytics.html` | `static/js/references/analytics.js` | `static/css/references/analytics.css` | P6 |
| Chunk Template List | `templates/settings/chunk_templates.html` | `static/js/settings/chunk_templates.js` | *(shared theme)* | §9.10 |
| Chunk Template Form | `templates/settings/chunk_template_form.html` | `static/js/settings/chunk_template_form.js` | *(shared theme)* | §9.10 |
| **Shared components** | — | `static/js/components/paper_card.js` | `static/css/components/paper_card.css` | P1–P6 |
| | — | `static/js/components/stance_badge.js` | *(shared theme)* | P2+P6 |
| | — | `static/js/components/source_badge.js` | *(shared theme)* | P1+P6 |
| | — | `static/js/components/ai_panel.js` | `static/css/components/ai_panel.css` | P1–P6 |
| | — | `static/js/components/async_job_button.js` | *(shared theme)* | P1–P4 |
| | — | `static/js/components/confirm_dialog.js` | *(shared theme)* | All |
| | — | `static/js/components/toast.js` | *(shared theme)* | All |
| | — | `static/js/components/chunk_template_picker.js` | *(shared theme)* | P1–P3 + §9.10 |
| | — | `static/js/components/citation_style_picker.js` | *(shared theme)* | P2+P4+P6 |

---

### 10.7 Mobile & Accessibility Baseline

All new pages and panels must meet the following baseline before shipping:

| Requirement | How |
|---|---|
| **Keyboard navigation** | All interactive elements reachable by Tab. Modal dialogs trap focus. Escape closes modals/panels. |
| **Visible focus rings** | `:focus-visible` ring using `var(--focus-ring-color)` from shared theme. Never suppress with `outline: none` without a themed replacement. |
| **Touch targets** | Minimum 44×44 px for buttons, icons, and badge actions. |
| **Responsive breakpoints** | 320 px minimum width. Knowledge map graph collapses to list view below 600 px. |
| **Screen reader labels** | All icon-only buttons have `aria-label`. Dynamic content regions have `aria-live="polite"`. |
| **Colour contrast** | All text ≥ 4.5:1 against its background (WCAG AA). Stance badges (green/red/grey) must include an icon or label — never rely on colour alone. |
| **Reduced motion** | Wrap all CSS transitions/animations in `@media (prefers-reduced-motion: no-preference)`. |

---

## 8. Glossary

| Term | Definition |
|---|---|
| **Library** | A user or project's saved collection of References |
| **Feed** | Personalised stream of recommended papers |
| **Synthesis** | AI-generated answer grounded in multiple papers |
| **Citation context** | The sentence(s) in which paper A cites paper B |
| **Knowledge graph** | Network of papers, authors, and citation edges |
| **Impact score** | Computed metric combining citations, recency, and field norms |
| **ORCID** | Open Researcher and Contributor ID — global researcher identifier |
| **Retraction alert** | Notification that a paper has been retracted or corrected |

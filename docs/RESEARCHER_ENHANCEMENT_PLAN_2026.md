# Beep.AI.Researcher Enhancement Plan 2026
**Status:** Code-Verified | **Date:** February 2026 | **Based on:** Direct source code audit

---

## 1. Verified Current Feature Inventory

The following features are confirmed by direct code inspection. Each entry maps to a real route file.

### 1.1 Fully Implemented (Production-Ready)

| Feature Area | Route File(s) | What Is Real |
|---|---|---|
| Project management | `routes/projects.py` | Full CRUD for research projects, RAG collection linkage |
| Document upload | `routes/documents.py` | PDF, TXT, MD, HTML, DOCX, XLSX, CSV; auto-syncs to RAG |
| Local + RAG search | `routes/search.py` | Text search with snippet offsets; RAG fallback via `beep_ai_client` |
| Multi-source search | `routes/extended_search.py` | PubMed, arxiv, semantic_scholar, crossref, custom library sources |
| Library source management | `routes/library_sources.py` | Full CRUD, API key/token storage, health checks, import logs |
| Document import | `routes/document_import.py` | Single + batch import from search results; queues PDF download job |
| Collaboration | `routes/collaboration.py` | Project members (viewer/contributor/admin), project-level comments |
| Document annotations | `routes/annotations.py` | Inline highlights with offsets, notes, color coding per document chunk |
| Reference management | `routes/references.py` | Full CRUD, DOI/URL/citation fields, link to documents, import/export |
| Task management | `routes/tasks.py` | CRUD, status/priority, document/code linkage, real-time notifications |
| Data analysis | `routes/data_analyst.py`, `routes/stats.py` | CSV/XLSX upload, descriptive stats (mean/median/std), crosstabs |
| Qualitative coding | `routes/codes.py`, `routes/coding_matrices.py` | Hierarchical codebook, coded references, color tags, coding matrices |
| Export | `routes/export_routes.py` | JSON, CSV, Excel, SPSS .sav, bundle ZIP with full audit log |
| Plugin system | `services/plugin_manager.py` | Dynamic load from DB, hook lifecycle, execution logging |
| Legal plugin | `plugins/legal.py` | Clause extraction, risk scoring, compliance checking, legal term dictionary |
| Medical plugin | `plugins/medical.py` | ICD-10 validation, CPT lookup, drug interaction check, HIPAA term detection |
| Engineering plugin | `plugins/engineering.py` | ISO/IEEE/NIST standards, materials/parts lookup, safety/hazard checks, unit validation |
| RBAC | `routes/admin/roles.py`, `routes/admin/user_roles.py` | Roles, permissions, user-role assignment |
| Retention policies | `routes/retention.py` | Retention rule CRUD |
| Governance | `routes/admin_routes.py` | Audit log view, governance dashboard |
| Monitoring | `routes/admin/monitoring.py` | System metrics, WebSocket live updates |
| Caching | `services/search_cache_manager.py`, `routes/cache_management.py` | Search result caching, event-driven invalidation, management endpoints |
| Event bus | `core/event_bus.py` | Async event publishing and subscription |
| Job queue | `core/job_queue.py` | Async job scheduling with priority levels |
| Hooks | `core/hooks.py` | Pre/post hook registration for research events |
| Multi-tenancy | `routes/tenants.py` | Tenant isolation model |
| Dashboard | `routes/dashboard.py`, `routes/dashboard_updates.py` | Project-level dashboard, live updates |
| Scheduled reports | `routes/scheduled_reports.py` | Report schedule management |
| AI templates | `routes/ai_templates.py` | Template CRUD for AI-assisted workflows |
| Global chat | `routes/global_chat.py` | Cross-project chat sessions |
| Flashcards (basic) | `routes/training.py` | Text-chunk-based flashcard generation |
| Quiz (basic) | `routes/training.py` | One question per document stub |
| Chat with documents | `routes/chat.py` | Full RAG+LLM chat with session history (requires Beep.AI.Server) |
| Extraction schemas | `routes/extraction.py` | Schema CRUD with field definitions; execution is LLM stub |

### 1.2 Stubs — Route Exists but LLM Not Connected

These routes return HTTP 200 with a message asking to configure `beep_ai_server_url`, but have no real logic:

- `routes/report_writing.py` — grammar/paraphrase/tone assistant
- `routes/contradiction.py` — contradiction detection across sources
- `routes/extraction.py` → `run_extraction` — LLM extraction over documents
- `routes/related.py` → `related_documents` — returns all project docs, no semantic similarity
- `routes/related.py` → `find_citations` — basic text match, no RAG
- `routes/ai_coding.py` — code suggestions return existing codes by usage, no LLM

### 1.3 Documented but Missing from Code (Real Gaps)

| Missing Feature | Evidence |
|---|---|
| `GET/POST /search/advanced` with facets | No route found in `routes/search.py` or `routes/extended_search.py` |
| `GET /projects/{id}/jobs/{job_id}` import job status | No route found; only `job_id` is returned in response from `document_import.py` |
| `GET /projects/{id}/import-stats` | No route found |
| Provider-aware cache key scoping | `search_cache_manager.py` ignores `provider`/`sources` in uniqueness check |
| RBAC docs match code | Docs use `lowercase` AccessLevel; code uses uppercase enum values |
| Real estate domain plugin | No `plugins/real_estate.py` exists |
| Education / academic plugin | No such plugin file exists |
| Government / regulatory plugin | No such plugin file exists |
| PHI redaction service | `medical.py` detects HIPAA terms but does not redact/mask text |
| Actual citation format validation | Legal plugin checks risk keywords; no Bluebook/citation format validator |
| Plagiarism detection hook | No such service or route exists |
| Hypothesis tracker model/route | No database model or route |
| Literature review workflow | No dedicated model or route |
| IRB / ethics checklist | No model or route |
| Case law API connectors | `legal.py` plugin uses local dictionaries only; no external API integration |

---

## 2. Database Model Changes Required

All changes below are additions to the **Researcher database** (SQLite / PostgreSQL via SQLAlchemy). No existing tables are dropped or destructively altered. Migration scripts must be added to `migrations/`.

### 2.1 Shared Platform Models (All Sectors)

#### `research_briefs`
New table. Captures the intent and scope of a research project before document collection begins.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | CASCADE delete |
| `title` | String(255) | Required |
| `objective` | Text | Research question or goal |
| `scope` | Text | What is and is not included |
| `methodology` | String(100) | qualitative / quantitative / mixed / systematic_review |
| `status` | String(50) | draft / active / closed |
| `stakeholders_json` | JSON | List of `{user_id, role, name}` |
| `constraints_json` | JSON | Deadlines, budget, access limits |
| `created_by_id` | Integer FK → `users.id` | |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

#### `evidence_items`
New table. Links a document or snippet to a project claim with provenance and quality.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | |
| `document_id` | Integer FK → `researcher_documents.id` | Nullable; external sources may not have a doc |
| `source_url` | String(2048) | Nullable |
| `snippet` | Text | The specific text used as evidence |
| `start_offset` | Integer | Nullable; from `document_annotations` pattern |
| `end_offset` | Integer | Nullable |
| `quality_score` | Float | 0.0–1.0; set by plugin or manually |
| `source_type` | String(100) | pubmed / arxiv / case_law / property_record / etc. |
| `added_by_id` | Integer FK → `users.id` | |
| `created_at` | DateTime | |

---

#### `claims`
New table. A tracked assertion derived from evidence.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | |
| `brief_id` | Integer FK → `research_briefs.id` | Nullable |
| `statement` | Text | Required |
| `status` | String(50) | proposed / supported / refuted / inconclusive |
| `confidence` | Float | 0.0–1.0 |
| `created_by_id` | Integer FK → `users.id` | |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

#### `claim_evidence` (join table)
Maps many `EvidenceItem` records to one `Claim`.

| Column | Type | Notes |
|---|---|---|
| `claim_id` | Integer FK → `claims.id` | |
| `evidence_item_id` | Integer FK → `evidence_items.id` | |
| `direction` | String(20) | supports / contradicts / neutral |

---

#### `review_steps`
New table. Ordered approval gates for any research workflow.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | |
| `brief_id` | Integer FK → `research_briefs.id` | Nullable |
| `step_name` | String(255) | e.g. "IRB Approval", "Title Clear" |
| `step_order` | Integer | 1-based order |
| `status` | String(50) | pending / in_review / approved / rejected / blocked |
| `reviewer_id` | Integer FK → `users.id` | Nullable; may be unassigned |
| `due_date` | Date | Nullable |
| `signed_by_id` | Integer FK → `users.id` | Nullable; set on approval |
| `signed_at` | DateTime | Nullable |
| `signature_ip` | String(45) | Nullable; for 21 CFR Part 11 compliance |
| `notes` | Text | Nullable |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

#### `source_provenance`
New table. Chain-of-custody log for every imported document or evidence item.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `document_id` | Integer FK → `researcher_documents.id` | Nullable |
| `evidence_item_id` | Integer FK → `evidence_items.id` | Nullable |
| `sourced_from` | String(255) | pubmed / courtlistener / mls / manual / etc. |
| `source_query` | Text | The query that retrieved this item |
| `import_job_id` | String(64) | FK to job queue job_id |
| `importer_user_id` | Integer FK → `users.id` | |
| `imported_at` | DateTime | |
| `checksum_sha256` | String(64) | Nullable; for integrity audit |

---

#### Updates to existing `retention_policies` table
Add two new columns:

| Column | Type | Notes |
|---|---|---|
| `is_legal_hold` | Boolean | Default False; blocks all delete operations |
| `hold_reason` | Text | Nullable |
| `policy_template` | String(100) | hipaa / ferpa / gdpr / soc2 / foia / default; drives export profile |
| `destruction_certificate_json` | JSON | Nullable; records destruction event details |

---

#### Updates to existing `project_comments` table
Add threading support:

| Column | Type | Notes |
|---|---|---|
| `parent_id` | Integer FK → `project_comments.id` | Nullable; enables threaded replies |
| `mentions_json` | JSON | Nullable; list of mentioned user IDs |

---

### 2.2 Law Sector Models

#### `clause_templates`
New table. Library of approved or standard contract clauses.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | Nullable; NULL = global library |
| `name` | String(255) | e.g. "Force Majeure — Standard" |
| `clause_type` | String(100) | liability_cap / indemnification / termination / force_majeure / nda / governing_law |
| `jurisdiction` | String(100) | Nullable; US-NY, UK, EU, etc. |
| `risk_level` | String(20) | low / medium / high |
| `reference_text` | Text | The approved clause text |
| `notes` | Text | Nullable |
| `created_by_id` | Integer FK → `users.id` | |
| `created_at` | DateTime | |

---

#### `citation_validations`
New table. Stores the result of Bluebook citation format checks.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | |
| `document_id` | Integer FK → `researcher_documents.id` | Nullable |
| `citation_text` | Text | The original citation |
| `is_valid` | Boolean | |
| `normalized_form` | Text | Nullable; corrected form |
| `validation_errors_json` | JSON | List of error messages |
| `checked_at` | DateTime | |

---

#### Updates to `researcher_references` table
Add law-specific fields:

| Column | Type | Notes |
|---|---|---|
| `witness_type` | String(50) | Nullable; fact / expert / character |
| `opinion_area` | String(255) | Nullable; for expert witnesses |
| `court` | String(255) | Nullable; court name |
| `jurisdiction` | String(100) | Nullable |
| `case_outcome` | String(100) | Nullable; affirmed / reversed / settled / pending |

---

### 2.3 Real Estate Sector Models

#### New `plugins/real_estate.py` (code, not DB)
No new tables. Uses existing `ExtractionSchema` / `ExtractionField` / `ExtractedFieldValue` / `EvidenceItem`.

#### Updates to `researcher_documents` table
Add location metadata for map-based features:

| Column | Type | Notes |
|---|---|---|
| `latitude` | Float | Nullable |
| `longitude` | Float | Nullable |
| `parcel_id` | String(100) | Nullable |
| `property_address` | String(512) | Nullable |

---

#### Updates to `researcher_references` table
Add real estate deal fields:

| Column | Type | Notes |
|---|---|---|
| `tenant_name` | String(255) | Nullable |
| `credit_grade` | String(10) | Nullable; A / B / C / D |
| `investment_type` | String(50) | Nullable; acquisition / disposition / refinance / leasing |

---

### 2.4 Medical Sector Models

#### `evidence_grades`
New table. GRADE-style quality rating for evidence items.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `evidence_item_id` | Integer FK → `evidence_items.id` | Unique |
| `grade` | String(1) | A / B / C / D |
| `grade_reason` | Text | |
| `graded_by_id` | Integer FK → `users.id` | |
| `graded_at` | DateTime | |

---

#### Updates to `researcher_tasks` table
Add clinical adverse event fields:

| Column | Type | Notes |
|---|---|---|
| `event_type` | String(50) | Nullable; adverse_event / protocol_deviation / safety_signal |
| `severity` | String(30) | Nullable; mild / moderate / severe / life_threatening |
| `meddra_code` | String(20) | Nullable |

---

#### Updates to `researcher_documents` table
Add PHI tracking fields:

| Column | Type | Notes |
|---|---|---|
| `phi_detected` | Boolean | Default False |
| `phi_redacted` | Boolean | Default False |
| `phi_backup_json` | JSON | Nullable; original offsets before redaction |
| `contains_student_data` | Boolean | Default False; also used by education sector |

---

### 2.5 Education Sector Models

#### `hypotheses`
New table.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `research_projects.id` | |
| `statement` | Text | Required |
| `status` | String(50) | proposed / testing / supported / refuted / inconclusive |
| `methodology` | String(100) | Nullable |
| `literature_support_count` | Integer | Default 0 |
| `created_by_id` | Integer FK → `users.id` | |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

#### `hypothesis_evidence` (join table)

| Column | Type | Notes |
|---|---|---|
| `hypothesis_id` | Integer FK → `hypotheses.id` | |
| `evidence_item_id` | Integer FK → `evidence_items.id` | |
| `direction` | String(20) | supports / contradicts |

---

#### `plagiarism_checks`
New table.

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `document_id` | Integer FK → `researcher_documents.id` | |
| `checked_at` | DateTime | |
| `service` | String(50) | internal_rag / turnitin_api / external |
| `similarity_score` | Float | 0.0–1.0 |
| `report_url` | String(2048) | Nullable |
| `flagged_passages_json` | JSON | Nullable |
| `job_id` | String(64) | Nullable; async job reference |

---

### 2.6 Migration Script Requirements

Each new model needs an Alembic migration. Suggested naming:

| Migration File | Contents |
|---|---|
| `add_research_brief_claim_evidence.py` | `research_briefs`, `evidence_items`, `claims`, `claim_evidence` |
| `add_review_steps_provenance.py` | `review_steps`, `source_provenance` |
| `add_retention_legal_hold.py` | Alter `retention_policies` |
| `add_comment_threading.py` | Alter `project_comments` |
| `add_law_clause_citation.py` | `clause_templates`, `citation_validations`, alter `researcher_references` (law fields) |
| `add_realestate_document_fields.py` | Alter `researcher_documents` (lat/lon/parcel), alter `researcher_references` (RE fields) |
| `add_medical_evidence_grades.py` | `evidence_grades`, alter `researcher_tasks` (event fields), alter `researcher_documents` (PHI fields) |
| `add_education_hypothesis_plagiarism.py` | `hypotheses`, `hypothesis_evidence`, `plagiarism_checks` |

---

## 3. AI Middleware API Changes Required (Beep.AI.Server)

The Researcher communicates with Beep.AI.Server exclusively through `app/services/beep_ai_client.py` using application tokens with scopes (`rag:read`, `rag:write`). The following changes are needed in the AI Middleware (`Beep.AI.Server/app/routes/ai_middleware/`) to support Researcher sector features.

### 3.1 New Scopes Required

Add the following scopes to the application token system (`tokens.py` + IAM manager). These do not require new route files — they are enforced via `require_token_scope()` on new endpoints:

| Scope | Purpose |
|---|---|
| `research:sector` | Identifies the calling app's active sector (law / medical / realestate / education / government) |
| `phi:redact` | Authorised to call PHI detection and redaction endpoints |
| `phi:audit` | Read-only access to PHI audit logs |
| `extraction:write` | Submit structured extraction jobs |
| `extraction:read` | Read extraction results |
| `compliance:export` | Generate compliance-grade export bundles (HIPAA, FERPA, FOIA) |
| `tools:domain` | Execute domain-specific tools (legal, medical, real estate) |

---

### 3.2 New RAG Endpoints (`rag.py`)

#### `POST /api/rag/collections/{collection_id}/sector-policy`
Set a compliance policy on a RAG collection. Stored as metadata on the collection.

```
Scope: rag:write
Body: {
  "sector": "medical",          // law | medical | realestate | education | government
  "compliance_template": "hipaa",
  "phi_scan_on_ingest": true,
  "redact_before_index": false,
  "retention_days": 3650
}
```
Used by: Researcher when creating a project collection, to enforce sector-specific ingestion rules.

---

#### `POST /api/rag/collections/{collection_id}/query-with-context`
Extended RAG query that returns results with sector-aware context fields.

```
Scope: rag:read
Body: {
  "query": "...",
  "user_id": "...",
  "sector": "legal",
  "max_results": 10,
  "quality_mode": "balanced",
  "include_provenance": true     // NEW — return source chain-of-custody metadata
}
Response adds:
  "provenance": [{ "source_type", "import_job_id", "imported_at", "checksum_sha256" }]
```
Used by: Researcher `chat.py`, `search.py`, and `contradiction.py` (once activated).

---

#### `GET /api/rag/collections/{collection_id}/compliance-status`
Returns PHI scan summary and retention policy status for a collection.

```
Scope: rag:read, phi:audit
Response: {
  "collection_id": "...",
  "phi_documents_detected": 12,
  "phi_documents_redacted": 10,
  "retention_policy": "hipaa",
  "retention_expires_at": "2034-01-01",
  "legal_hold": false
}
```
Used by: Researcher admin/governance view and export bundle.

---

### 3.3 New Service Call — Structured Extraction (`service_calls.py`)

#### `POST /api/services/llm/extract-structured`
Run LLM extraction over a document using a JSON schema. This activates the Researcher's currently-stubbed `routes/extraction.py` → `run_extraction`.

```
Scope: extraction:write, llm:write
Body: {
  "application_id": "...",
  "user_id": "...",
  "collection_id": "...",       // optional — scope to RAG collection
  "document_text": "...",       // or
  "document_id": "...",         // Researcher doc ID, resolved by app
  "schema": [
    { "field": "parties", "description": "Names of contracting parties", "type": "list" },
    { "field": "governing_law", "description": "Applicable jurisdiction and law clause", "type": "string" }
  ],
  "sector": "legal",
  "quality_mode": "high"
}
Response: {
  "success": true,
  "extractions": {
    "parties": ["Acme Corp", "Widget LLC"],
    "governing_law": "State of New York"
  },
  "confidence": { "parties": 0.95, "governing_law": 0.88 },
  "model_used": "...",
  "tokens_used": 1240
}
```

---

#### `POST /api/services/llm/contradiction-detect`
Detect contradictions between multiple text passages. Activates Researcher `routes/contradiction.py`.

```
Scope: rag:read, llm:write
Body: {
  "passages": [
    { "id": "doc-1", "text": "..." },
    { "id": "doc-2", "text": "..." }
  ],
  "query_context": "...",
  "sector": "medical"
}
Response: {
  "contradictions": [
    {
      "passage_a_id": "doc-1",
      "passage_b_id": "doc-2",
      "description": "doc-1 states X; doc-2 states not-X",
      "confidence": 0.87
    }
  ]
}
```

---

#### `POST /api/services/llm/cite-as-written`
Find matching citations for a draft text passage. Activates Researcher `routes/related.py` → `find_citations`.

```
Scope: rag:read, llm:write
Body: {
  "draft_text": "...",
  "collection_id": "...",
  "max_citations": 5,
  "citation_style": "apa"      // apa | mla | chicago | bluebook | vancouver
}
Response: {
  "citations": [
    { "document_id": "...", "snippet": "...", "formatted_citation": "...", "relevance_score": 0.91 }
  ]
}
```

---

### 3.4 New PHI Tool (`tooling.py`)

Register a new domain tool in the tooling plugin registry for PHI detection and redaction. This is exposed via the existing `GET /api/tools` endpoint in OpenAI function-calling format.

#### Tool: `phi_scan`
```json
{
  "type": "function",
  "function": {
    "name": "phi_scan",
    "description": "Scan text for Protected Health Information (PHI) as defined by HIPAA. Returns detected PHI terms, categories, and character offsets.",
    "parameters": {
      "type": "object",
      "properties": {
        "text": { "type": "string", "description": "Text to scan" },
        "categories": {
          "type": "array",
          "items": { "type": "string" },
          "description": "PHI categories to check: name, ssn, mrn, dob, phone, email, address, insurance_id, provider_id"
        }
      },
      "required": ["text"]
    }
  }
}
```

#### Tool: `phi_redact`
```json
{
  "type": "function",
  "function": {
    "name": "phi_redact",
    "description": "Redact Protected Health Information from text, replacing matches with [REDACTED] or a custom token.",
    "parameters": {
      "type": "object",
      "properties": {
        "text": { "type": "string" },
        "replacement": { "type": "string", "default": "[REDACTED]" },
        "categories": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["text"]
    }
  }
}
```

Route to call both tools directly:
```
POST /api/tools/execute
Body: { "tool_name": "phi_scan", "parameters": { "text": "..." } }
Scope: phi:redact
```

---

### 3.5 New Domain Policy Rules (`middleware_rules.py`)

Add built-in routing rules that the Researcher app can activate via `POST /api/rules`:

| Rule Name | Type | Pattern | Action | Purpose |
|---|---|---|---|---|
| `sector_legal_llm` | service_routing | `sector=legal` | Route to a legal-prompt-tuned model if available | Prefer legal-capable LLM |
| `sector_medical_llm` | service_routing | `sector=medical` | Route to medical-capable model | Prefer medical-capable LLM |
| `phi_block_on_export` | content_filter | `phi_detected=true AND redacted=false` | Block | Prevent unredacted PHI in responses |
| `ferpa_student_data` | content_filter | `contains_student_data=true` | Require `phi:audit` scope | Protect student records |
| `compliance_rate_limit` | rate_limit | `scope=compliance:export` | Limit to 10/hour | Prevent bulk compliance exports |

---

### 3.6 New Access Policies (`middleware_policies.py`)

Add sector-specific access policies that restrict LLM and RAG access by sector configuration:

```
POST /api/policies
Body: {
  "name": "HIPAA Research Policy",
  "service": "rag",
  "resource": "collection",
  "conditions": {
    "sector": "medical",
    "requires_phi_scan": true,
    "block_unredacted_export": true,
    "audit_every_access": true
  },
  "actions": ["query", "add_documents"],
  "effect": "allow"
}
```

Policies to ship as built-in templates (loaded on startup):
- `HIPAA Research Policy` — medical sector
- `FERPA Academic Policy` — education sector
- `Legal Discovery Policy` — law sector
- `FOIA Government Policy` — government sector
- `Real Estate Diligence Policy` — real estate sector

---

### 3.7 App User Tier Extensions (`app_users.py`)

Add sector-specific tier metadata to `AppUser` records so the middleware can apply sector-appropriate rate limits and policy checks:

```
POST /api/app-users  (existing endpoint)
Body additions:
{
  "metadata": {
    "sector": "medical",
    "compliance_template": "hipaa",
    "phi_access": true,
    "student_data_access": false
  }
}
```

The `AppUser.metadata_json` field (already exists) stores these. The middleware reads `metadata.sector` on each RAG/LLM call to enforce the sector policy.

---

### 3.8 Changes to `beep_ai_client.py` in Researcher

The Researcher-side client (`app/services/beep_ai_client.py`) needs these additions to consume the new middleware endpoints:

| New Function | Calls | Purpose |
|---|---|---|
| `extract_structured(project, document_text, schema, sector)` | `POST /api/services/llm/extract-structured` | Activates extraction stub |
| `detect_contradictions(project, passages, query_context, sector)` | `POST /api/services/llm/contradiction-detect` | Activates contradiction stub |
| `find_citations_for_draft(project, draft_text, citation_style)` | `POST /api/services/llm/cite-as-written` | Activates citation finder |
| `scan_phi(text, categories)` | `POST /api/tools/execute` with `phi_scan` | Used by PHI redaction service |
| `redact_phi(text, replacement)` | `POST /api/tools/execute` with `phi_redact` | Used by PHI redaction service |
| `set_collection_sector_policy(collection_id, policy)` | `POST /api/rag/collections/{id}/sector-policy` | On project creation |
| `get_collection_compliance_status(collection_id)` | `GET /api/rag/collections/{id}/compliance-status` | Used by governance dashboard |
| `query_with_context(project, query, sector, include_provenance)` | `POST /api/rag/collections/{id}/query-with-context` | Replaces basic `query_project_rag` for sector queries |

---

## 4. Guiding Principles

> **Note:** Sections 2 and 3 define all database and AI Middleware changes. Sections 5–13 define what to build; each feature references the model rows and API calls above that it depends on.

- **Evidence-based:** Build on what is verified. No duplicate work on existing features.
- **Compliance-first:** HIPAA, FERPA, GDPR, SOC 2, FOIA, and sector-specific records retention.
- **Workflow-first:** Features must map to a real research task in each sector.
- **Extend, not replace:** New features hook into the existing plugin system, job queue, event bus, and export bundle pipeline.
- **Safe AI:** All LLM outputs must include citations, confidence levels, and human review gates.

---

## 5. Shared Platform Fixes (Must Do Before Sector Work)

These fix verified gaps that block all four sectors.

### 3.1 Fix Missing Core Endpoints

**Priority: Critical**

1. `GET /projects/{id}/jobs/{job_id}` — Return job status from `job_queue.py`.
2. `GET /projects/{id}/import-stats` — Aggregate from `SourceImportLog`.
3. `GET/POST /projects/{id}/search/advanced` — Add faceted search with date range, source type, language, and open access filters on top of existing `extended_search.py`.
4. `GET /projects/{id}/search/facets` — Aggregate available facet values from cached results.

### 3.2 Fix Provider-Aware Cache Keys

**Priority: High**

In `services/search_cache_manager.py`, include `provider` and `sources[]` in the cache key hash so results from PubMed and arxiv are stored separately and do not collide.

### 3.3 Fix RBAC Documentation Sync

**Priority: Medium**

Update docs to reflect uppercase `AccessLevel` enum values and the actual `shared_with` list structure from `models/rbac.py`. No code changes needed; documentation only.

### 3.4 Activate LLM Stubs

**Priority: High**

Connect existing stubs to `beep_ai_client.py` using the same pattern as `chat.py`:

- `routes/report_writing.py` → call `chat_reply` with a paraphrase/grammar prompt template.
- `routes/contradiction.py` → use `query_project_rag` + `chat_reply` to detect contradictions.
- `routes/extraction.py` → use `query_project_rag` per document chunk, structured output with schema fields.
- `routes/related.py` → use `query_project_rag` with document content as query for semantic similarity.
- `routes/ai_coding.py` → use `chat_reply` with codebook context to suggest qualitative codes.

### 3.5 Activate Flashcard/Quiz LLM Quality

**Priority: Medium**

Replace the text-chunk stub in `routes/training.py` with `chat_reply` calls using a Q&A prompt template so generated cards are meaningful and not raw text fragments.

---

## 6. Shared Platform Enhancements (All Sectors Benefit)

### 4.1 Research Lifecycle Model

Add new database models and routes to support a structured research lifecycle across all sectors:

**New Models:**
- `ResearchBrief` — title, objective, scope, methodology, stakeholders, status (draft/active/closed)
- `EvidenceItem` — links a document/snippet to a project claim with quality score
- `Claim` — a tracked assertion with supporting evidence items and status
- `ReviewStep` — an approval gate with reviewer, due date, sign-off status
- `SourceProvenance` — tracks chain of custody for any imported content (source, import time, importer, job ID)

**New Routes:**
- `POST/GET /projects/{id}/briefs` — research brief CRUD
- `POST/GET /projects/{id}/claims` — claims tracking
- `POST/GET /projects/{id}/evidence` — evidence item management
- `POST/GET /projects/{id}/reviews` — review step and sign-off management

### 4.2 Evidence Tables

Build on the existing `ExtractionSchema` and `ExtractionResult` models to support structured evidence comparison tables:

- A table where rows are documents and columns are extraction fields
- Cells link to the actual `ExtractedFieldValue` with source offsets
- Exportable as CSV/Excel via the existing `export_routes.py` bundle pipeline

### 4.3 Compliance Policy Templates

Extend the existing `retention.py` to support named policy profiles. Ship one built-in template per compliance framework:

| Template Name | Attributes |
|---|---|
| HIPAA Research | 6-year retention, PHI detection on export, access log required |
| FERPA Academic | Student data isolation, consent flag, 5-year retention |
| GDPR EU | Right to delete, data minimization tag, 3-year retention |
| SOC 2 Internal | Full audit trail, change management log, quarterly review |
| FOIA Government | 7-year retention, disclosure log, public records export format |
| Records Retention | Configurable duration, legal hold override, destruction certificate |

### 4.4 Collaboration Enhancements

Extend `routes/collaboration.py`:

- Threaded replies on `ProjectComment` (add `parent_id` field)
- `@mention` notification via the existing `task_notifications.py` pattern
- Document-level shared access log visible to project owner

### 4.5 Observability Dashboard

Extend `routes/admin/monitoring.py`:

- Per-project ingestion health: documents imported, failed, pending
- Per-source query volume and error rate from `SourceImportLog`
- Job queue depth and retry count from `job_queue.py`
- Search cache hit/miss ratio from `search_cache_manager.py`

---

## 7. Law Sector Plan

### 5.1 Context

The legal plugin (`plugins/legal.py`) is fully implemented with clause extraction, risk scoring, compliance checking, and a legal term dictionary. The gap is that it works only on extracted field values passed through the plugin hook — it has no direct document search connectors or citation format validation.

### 5.2 Main Plan

#### A. Legal Knowledge Connectors

Extend `routes/library_sources.py` with new `source_type` values:

- `westlaw_api` — connect to Westlaw REST API using API key stored in `LibrarySource.api_key`
- `courtlistener` — connect to CourtListener open API (free, no key required)
- `regulations_gov` — connect to Regulations.gov API for US federal regulatory text
- `pacer_scraper` — scheduled import of PACER docket data via job queue

Each connector follows the existing `SearchManager` integration pattern used for PubMed and arxiv.

#### B. Contract and Clause Workflow

Using the existing `ExtractionSchema` model, add a built-in **Legal Contract** schema:

| Field Name | Plugin Hook | Description |
|---|---|---|
| `parties` | on_extraction | Identifies contracting parties |
| `governing_law` | on_extraction | Jurisdiction and applicable law clause |
| `termination_clause` | on_extraction | Clause type, notice period, conditions |
| `liability_cap` | on_extraction | Dollar limits and carve-outs |
| `indemnification` | on_extraction | Risk level assessment via existing `assess_risk` |
| `force_majeure` | on_extraction | Detects clause presence and standard vs. non-standard language |
| `nda_obligations` | on_extraction | Confidentiality scope and duration |

Add a **Clause Library** model:
- `ClauseTemplate` — name, type, reference text, risk_level, jurisdiction
- `GET/POST /projects/{id}/clause-library` — manage approved clause templates
- `POST /projects/{id}/compare-clause` — compare extracted clause against library template (diff)

Add **Redlining** to the document comparison workflow:
- `POST /projects/{id}/documents/{id}/redline` — compare two documents using Python `difflib`, returns change blocks with metadata

#### C. Citation Integrity

Extend `plugins/legal.py`:

- `validate_citation(citation_text)` — parse and validate Bluebook citation format using regex patterns for case name, reporter, year, and court
- `suggest_pinpoint(citation_text, document)` — match citation to document section using `text_content` search

Add route:
- `POST /projects/{id}/citations/validate` — validate a list of citations using the plugin

#### D. Legal Hold Workflow

Using the existing `retention.py` model, add `is_legal_hold` boolean and `hold_reason` field. When a project or document is on legal hold, block all delete operations and flag in export bundle.

#### E. Discovery Export Bundle

Extend `export_routes.py` bundle format for legal sector:
- Include full audit log
- Include all annotations with offsets
- Include all coded references with code definitions
- Include retention/legal hold status
- Output format compatible with Relativity/EDRM XML standard

#### F. Sub-Features

- **Multi-jurisdiction comparison table** — use `EvidenceItem` rows keyed by jurisdiction, columns by legal test factors
- **Case outcome summarizer** — once LLM stub is connected, use `chat_reply` with a case outcome prompt template
- **Expert witness tracker** — extend `Reference` model with `witness_type`, `opinion_area`, `affiliation` fields
- **Conflict of interest checker** — compare `parties` fields across project documents to flag overlapping names

### 5.3 Compliance Deliverables for Law

| Framework | What to Implement |
|---|---|
| FOIA | Disclosure log on export, 7-year retention template, public records format |
| SOC 2 | Audit trail on all clause edits and code changes |
| GDPR | Right to delete workflow for client PII in documents |
| Records Retention | Legal hold override, destruction certificate in export bundle |

---

## 8. Real Estate Sector Plan

### 6.1 Context

No real estate plugin exists. The existing document upload, multi-source search, data analysis, reference management, and qualitative coding infrastructure can all be reused. A new plugin and source connectors are needed.

### 6.2 Main Plan

#### A. Real Estate Plugin (`plugins/real_estate.py`)

Create a new plugin following the exact `PluginBase` pattern from `plugins/legal.py`:

| Hook | Behavior |
|---|---|
| `on_extraction` for `address` fields | Normalize address format, suggest parcel ID format |
| `on_extraction` for `zoning` fields | Match against loaded zoning code dictionary, flag non-conforming use |
| `on_extraction` for `cap_rate` fields | Validate numeric range, flag outliers vs. market range |
| `on_extraction` for `lease_term` fields | Extract start/end dates, calculate duration, flag short-term vs. long-term |
| `on_extraction` for `title_defect` fields | Match against known defect types (lien, easement, encumbrance) |

Plugin loads:
- `zoning_codes` — local dictionary of common zoning classifications (R1, C2, I1, etc.)
- `property_types` — residential, commercial, industrial, mixed-use
- `compliance_triggers` — ADA, fire code, environmental flags

#### B. Property Data Connectors

Extend `routes/library_sources.py` with new `source_type` values:

- `county_assessor` — pull parcels from county assessor open data APIs
- `zillow_api` — Zillow property data (requires API key)
- `mls_rets` — RETS protocol connector for MLS feeds
- `costar_api` — CoStar commercial property database
- `fema_flood` — FEMA flood zone data for risk overlay

#### C. Property Research Extraction Schema

Built-in **Property Diligence** extraction schema fields:

| Field | Plugin Hook |
|---|---|
| `property_address` | Address normalization |
| `parcel_id` | Format validation |
| `zoning_classification` | Zoning compliance check |
| `legal_description` | Present/absent detection |
| `title_encumbrances` | Defect type classification |
| `lease_expiry_date` | Date extraction and duration calc |
| `annual_noi` | Numeric validation and cap rate derivation |
| `environmental_flags` | Hazard term detection |
| `building_permits` | Permit status and expiry |
| `flood_zone` | FEMA zone classification |

#### D. Deal Diligence Workflow

Using the `ResearchBrief` model (from shared 4.1):

- **Property Brief** template with fields: address, asset type, target price, diligence deadline, deal team
- **Deal Checklist** built on `ReviewStep` — title clear, zoning confirmed, environmental clean, lease reviewed, permits valid, financing committed
- **Comparable Sales Table** — evidence table where rows are comparable properties, columns are price, size, cap rate, date, distance

#### E. Lease Abstraction

Built-in **Commercial Lease** extraction schema:

| Field | Description |
|---|---|
| `tenant_name` | Party extraction |
| `base_rent` | Dollar amount per period |
| `rent_escalation` | Percentage or CPI-linked |
| `lease_commencement` | Start date |
| `lease_expiration` | End date, option terms |
| `security_deposit` | Amount and conditions |
| `permitted_use` | Use clause text |
| `assignment_subletting` | Restrictions |
| `landlord_obligations` | Maintenance responsibilities |
| `tenant_improvements` | TI allowance |

#### F. Market Report Builder

Extend `routes/scheduled_reports.py` with a real estate report template:
- Pulls comparable data from `EvidenceItem` rows
- Uses existing `SavedChart` model for cap rate / price per SF trend charts
- Exports via existing Excel/PDF export pipeline

#### G. Sub-Features

- **Map integration** — add `latitude`/`longitude` fields to `ResearcherDocument.metadata_json`; frontend maps can consume these without backend changes
- **Tenant credit notes** — extend `Reference` with `tenant_name`, `credit_score_range`, `lease_grade` fields
- **Environmental risk overlay** — add FEMA flood zone and EPA brownfield flags to extraction schema
- **Investment committee report** — export bundle variant for real estate with financial summary, diligence status, and risk flags

### 6.3 Compliance Deliverables for Real Estate

| Framework | What to Implement |
|---|---|
| SOC 2 | Audit trail on all deal document access |
| GDPR | PII redaction for tenant personal data in exports |
| Records Retention | 7-year retention for deal documents; legal hold for disputed properties |
| FOIA (public agencies) | Disclosure log for government-acquired property records |

---

## 9. Medical Sector Plan

### 7.1 Context

The medical plugin (`plugins/medical.py`) is fully implemented with ICD-10 validation, CPT lookup, drug interaction detection, and HIPAA term detection. The critical gap is that it detects PHI but does not redact it, has no clinical guideline API connectors, and has no adverse event or protocol tracking models.

### 7.2 Main Plan

#### A. PHI Redaction Service

Create `services/phi_redaction_service.py`:

- Uses the existing `_hipaa_sensitive_terms` dictionary from `medical.py` as a seed
- Adds regex patterns for: SSN, MRN, phone, email, birth date, insurance ID, provider ID
- `redact_text(text, replacement='[REDACTED]')` → returns cleaned text and a redaction map
- `redact_document(doc_id)` → applies redaction to `ResearcherDocument.text_content` in place, saves original in a `phi_backup_json` field, logs to audit log

Add route:
- `POST /projects/{id}/documents/{id}/redact` — trigger PHI redaction with confirmation flag
- `GET /projects/{id}/documents/{id}/phi-report` — list detected PHI terms with positions before redaction

#### B. Clinical Research Connectors

Extend `routes/library_sources.py` with:

- `pubmed` — already supported; ensure MeSH term filtering is passed through `SearchFilter`
- `clinicaltrials_gov` — connect to ClinicalTrials.gov API v2 (free, no key)
- `fda_openfda` — FDA OpenFDA drug label and adverse event API
- `cochrane_library` — Cochrane Reviews API (requires institutional key)
- `who_iris` — WHO IRIS open repository

#### C. Clinical Evidence Extraction Schema

Built-in **Clinical Study** extraction schema:

| Field | Plugin Hook |
|---|---|
| `study_design` | Identifies RCT, cohort, case-control, meta-analysis |
| `sample_size` | Numeric extraction and adequacy flag |
| `primary_endpoint` | Outcome measure description |
| `icd10_diagnosis` | ICD-10 validation via plugin |
| `intervention_drug` | Drug interaction check via plugin |
| `cpt_procedure` | CPT lookup via plugin |
| `adverse_events` | Adverse event term detection |
| `p_value` | Statistical significance extraction |
| `confidence_interval` | CI range extraction and format check |
| `funding_source` | COI flag if industry-funded |

#### D. Evidence Grading

Add `EvidenceGrade` model:
- `evidence_item_id` (FK to `EvidenceItem`)
- `grade` — GRADE levels: A (strong), B (moderate), C (weak), D (very weak)
- `grade_reason` — free text
- `graded_by_id`, `graded_at`

Add route:
- `POST /projects/{id}/evidence/{id}/grade`

#### E. Adverse Event Tracker

Using `ResearchTask` model extended with:
- `event_type` = `adverse_event`
- `severity` — mild/moderate/severe/life-threatening
- `meddra_code` — MedDRA term code
- Link to source document

Route:
- `GET /projects/{id}/adverse-events` — filtered view of tasks with `event_type = adverse_event`

#### F. Protocol Review Workflow

Using `ReviewStep` model (from shared 4.1):

- **Protocol Review** template with steps: concept approval, IRB submission, data safety plan, statistical analysis plan, final approval
- Each step has an assigned reviewer and sign-off timestamp
- Blocked progression — cannot advance to next step until previous is signed off

#### G. De-Identified Export Profile

Extend `export_routes.py` bundle with a `deidentified` flag:
- All fields flagged as PHI are replaced with `[REDACTED]` using `phi_redaction_service`
- Export manifest lists which fields were redacted and why
- SHA-256 hash of original document stored for integrity audit

### 7.3 Compliance Deliverables for Medical

| Framework | What to Implement |
|---|---|
| HIPAA | PHI redaction service, access log on every document open, de-identified export profile |
| GDPR | Right to delete PHI, data minimization on export |
| SOC 2 | Full audit trail on protocol changes, evidence grade changes |
| Records Retention | 10-year clinical research retention template, legal hold for trial data |
| 21 CFR Part 11 | Electronic signature fields on `ReviewStep.signed_by_id` with timestamp and IP |

---

## 10. Education Sector Plan

### 8.1 Context

No education plugin exists. The existing flashcard/quiz stub, reference management, export, collaboration, and data analysis infrastructure can all be reused. The sector needs an academic research lifecycle model, hypothesis tracking, literature review workflow, citation manager features, and plagiarism hook infrastructure.

### 8.2 Main Plan

#### A. Education Plugin (`plugins/education.py`)

Create a new plugin following the `PluginBase` pattern:

| Hook | Behavior |
|---|---|
| `on_extraction` for `citation` fields | Validate APA/MLA/Chicago format using regex |
| `on_extraction` for `author` fields | Detect institutional affiliation patterns |
| `on_extraction` for `methodology` fields | Classify: qualitative, quantitative, mixed methods |
| `on_extraction` for `dataset` fields | Detect dataset identifiers (DOI, accession numbers) |
| `on_extraction` for `sample_size` fields | Flag if below common power thresholds |

Plugin loads:
- `citation_patterns` — format regex for APA, MLA, Chicago, Vancouver, IEEE
- `common_methodologies` — taxonomy of research designs
- `ferpa_term_patterns` — student ID, grade, enrollment patterns for FERPA compliance

#### B. Academic Source Connectors

Extend `library_sources.py` with:

- `arxiv` — already supported
- `semantic_scholar` — already supported
- `jstor_api` — JSTOR API (requires institutional access)
- `eric_api` — ERIC education research database (free DOE API)
- `proquest_api` — ProQuest dissertations (requires key)
- `openaire_api` — OpenAIRE open access research
- `google_scholar_scraper` — scheduled scraper via job queue (no official API)

#### C. Hypothesis Tracker

Add new models:
- `Hypothesis` — project_id, statement, status (proposed/testing/supported/refuted/inconclusive), literature_support_count, created_by_id
- `HypothesisEvidence` — hypothesis_id, evidence_item_id, direction (supports/contradicts)

Routes:
- `POST/GET /projects/{id}/hypotheses`
- `PUT /projects/{id}/hypotheses/{id}` — update status, add evidence links

#### D. Literature Review Workflow

Using `ResearchBrief` + the extraction schema:

- **PRISMA Screening Form** built-in extraction schema:

| Field | Description |
|---|---|
| `title_abstract_screen` | Pass/Fail with reason |
| `full_text_screen` | Pass/Fail with exclusion code |
| `inclusion_criteria_met` | Boolean per criterion |
| `study_design` | Classified by education plugin |
| `population` | Target population description |
| `intervention` | Intervention or exposure |
| `outcome_measure` | Primary and secondary outcomes |
| `quality_score` | 1–10 using evidence grading |

- **PRISMA Flow Table** — aggregate from screened documents showing included/excluded counts

Route:
- `GET /projects/{id}/prisma-summary` — returns flow table JSON

#### E. Citation Manager

Extend existing `routes/references.py` with:

- Citation format selector (APA/MLA/Chicago) passed to export
- `POST /projects/{id}/references/validate` — run through `education.py` plugin citation validator
- `POST /projects/{id}/references/format` — reformat to selected style
- `GET /projects/{id}/references/export?format=bibtex` — export all references as BibTeX

#### F. Plagiarism Check Infrastructure

Add a `PlagiarismCheck` model:
- `document_id`, `checked_at`, `service` (internal_rag / turnitin_api / external)
- `similarity_score`, `report_url`, `flagged_passages_json`

Route:
- `POST /projects/{id}/documents/{id}/plagiarism-check` — for internal, use `query_project_rag` to find similar passages; for external, call configured API via job queue

#### G. Academic Integrity and FERPA Controls

Extend RBAC:
- Add `student_data_access` permission flag on `Role`
- Documents tagged with `contains_student_data = True` require this permission to open

Extend export bundle with `ferpa_compliant` mode:
- Strip all fields matching `ferpa_term_patterns`
- Add consent documentation to bundle manifest

#### H. Research Lifecycle Sub-Features

- **Thesis/dissertation workflow** — `ResearchBrief` template with chapters: introduction, literature review, methodology, findings, conclusions; each mapped to a `ReviewStep`
- **Grant proposal builder** — export bundle variant with AI-assisted narrative (via `chat_reply`) and budget table from data upload
- **IRB checklist** — `ReviewStep` template: risk assessment, informed consent, data security plan, FERPA review, IRB submission, approval received
- **Methodology template library** — built-in `ExtractionSchema` templates for RCT, quasi-experimental, ethnographic, case study, survey
- **Flashcard quality with LLM** — once LLM stub is connected, generate Q&A flashcards from literature review documents using `chat_reply`

### 8.3 Compliance Deliverables for Education

| Framework | What to Implement |
|---|---|
| FERPA | Student data permission flag, FERPA-clean export mode, retention 5 years |
| GDPR | Student data deletion workflow, consent tracking on `ResearchBrief` |
| SOC 2 | Audit trail on all grade/assessment data access |
| Records Retention | Academic records 7-year retention template |

---

## 11. Government Agency Sector (Additional)

### 9.1 Context

Government agencies use research platforms for policy analysis, regulatory review, public comment analysis, and FOIA compliance. No government-specific plugin exists.

### 9.2 Main Plan

#### A. Government Plugin (`plugins/government.py`)

| Hook | Behavior |
|---|---|
| `on_extraction` for `regulation_citation` | Parse CFR/USC citation format |
| `on_extraction` for `public_comment` | Sentiment classification and topic clustering |
| `on_extraction` for `agency_name` | Match against federal agency registry |
| `on_extraction` for `omb_control_number` | Validate OMB format |

#### B. Government Source Connectors

- `regulations_gov` — public comment and proposed rule data
- `federal_register_api` — Federal Register rules and notices
- `congress_gov_api` — Congressional bills and reports
- `gao_api` — GAO reports
- `usa_spending_api` — USASpending.gov grant/contract data

#### C. FOIA Workflow

Using `ReviewStep`:
- **FOIA Request** workflow: received, acknowledged, processing, responsive records identified, redaction review, released/denied
- Disclosure log records every document released, redacted, or withheld with exemption code
- Export bundle includes FOIA response package with index and exemption justifications

#### D. Regulatory Analysis

Built-in extraction schema for **Proposed Rule Analysis**:

| Field | Description |
|---|---|
| `agency_name` | Issuing agency |
| `cfr_part` | Affected CFR part |
| `rin_number` | RIN for cross-referencing |
| `comment_deadline` | Date extraction |
| `economic_impact` | Cost-benefit figures |
| `small_business_impact` | RFA analysis presence |
| `public_comments_count` | Numeric count |

### 9.3 Compliance Deliverables for Government

| Framework | What to Implement |
|---|---|
| FOIA | Disclosure log, exemption codes, response package export |
| SOC 2 | Full audit trail on all researcher access |
| Records Retention | NARA schedules; federal records minimum 7-10 years |
| FISMA / FedRAMP | Document metadata for FedRAMP impact level (Low/Moderate/High) |

---

## 12. Delivery Phases

### Phase A — Platform Integrity (Immediate, 4–6 weeks)

| Task | Maps to |
|---|---|
| Add missing job status and import stats endpoints | Section 5.1 |
| Add advanced search + facets endpoint | Section 5.1 |
| Fix provider-aware cache keys | Section 5.2 |
| Connect report writing, contradiction, extraction stubs to LLM | Section 5.4 + Section 3.3 |
| Connect AI coding and related documents to RAG | Section 5.4 + Section 3.8 |
| Connect flashcard/quiz to LLM quality generation | Section 5.5 |
| Run DB migrations: brief, evidence, claim, review_step tables | Section 2.1 |
| Apply new AI Middleware scopes and `beep_ai_client.py` additions | Section 3.1, 3.8 |

### Phase B — Shared Research Lifecycle (6–10 weeks)

| Task | Maps to |
|---|---|
| Add `ResearchBrief`, `EvidenceItem`, `Claim`, `ReviewStep` models | Section 6.1 + Section 2.1 |
| Add evidence table views | Section 6.2 |
| Add compliance policy templates | Section 6.3 |
| Add threaded comments and mention notifications | Section 6.4 + Section 2.1 (comment threading) |
| Add observability dashboard | Section 6.5 |
| Deploy sector access policies in AI Middleware | Section 3.6 |

### Phase C — Sector Foundations (10–18 weeks)

| Task | Maps to |
|---|---|
| Legal: Clause Library model + Bluebook validator | Section 7 + Section 2.2 |
| Legal: CourtListener + Regulations.gov connectors | Section 7.2A |
| Medical: PHI redaction service + PHI report route | Section 9.2A + Section 3.4 (phi tools) |
| Medical: ClinicalTrials.gov + FDA OpenFDA connectors | Section 9.2B |
| Education: `Hypothesis` + `HypothesisEvidence` models | Section 10.2C + Section 2.5 |
| Education: PRISMA schema + summary route | Section 10.2D |
| Real estate: `real_estate.py` plugin | Section 8.2A + Section 2.3 |
| Government: `government.py` plugin | Section 11.2A |
| Deploy structured extraction endpoint in AI Middleware | Section 3.3 |
| Run DB migrations: law, real estate, medical, education tables | Section 2.2–2.5 |

### Phase D — Sector Depth (18–28 weeks)

| Task | Maps to |
|---|---|
| Legal: Contract redlining, discovery export bundle | Section 7.2B, 7.2E |
| Medical: Adverse event tracker, protocol review, de-identified export | Section 9.2E, 9.2F, 9.2G |
| Education: Plagiarism check infrastructure, citation manager | Section 10.2F, 10.2E |
| Real estate: Lease abstraction schema, deal checklist | Section 8.2E, 8.2D |
| Government: FOIA workflow, regulatory extraction schema | Section 11.2C, 11.2D |
| Deploy contradiction-detect and cite-as-written in AI Middleware | Section 3.3 |
| Deploy domain routing rules in AI Middleware | Section 3.5 |

### Phase E — Compliance Hardening (28–36 weeks)

| Task | Maps to |
|---|---|
| FERPA export mode | Section 10.3 |
| 21 CFR Part 11 electronic signatures on ReviewStep | Section 9.3 + Section 2.1 (`signature_ip`) |
| Legal hold flow with destruction certificate | Section 7.3 + Section 2.1 (retention updates) |
| FOIA response package | Section 11.3 |
| SOC 2 audit trail completeness review | All sectors |
| PHI middleware policy: block unredacted collections from export | Section 3.5 (`phi_block_on_export` rule) |

---

## 13. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Stubs activated | 6 of 6 stubs connected to LLM | Route test confirms real LLM response |
| Missing endpoints added | 4 endpoints | OpenAPI spec updated |
| Search cache correctness | Zero provider collisions | Cache key unit test |
| Plugin coverage | 5 domain plugins (legal, medical, engineering, real estate, education) | Plugin registry count |
| Compliance templates | 6 templates shipped | Template list endpoint |
| Evidence table adoption | Used in 3+ sector workflows | EvidenceItem row count per project |
| Export bundle compliance | FOIA, HIPAA, FERPA export modes tested | Integration test pass |
| Review workflow adoption | ReviewStep sign-offs tracked | Signed-off step count |
| Import job visibility | Job status accessible for all async imports | API test |


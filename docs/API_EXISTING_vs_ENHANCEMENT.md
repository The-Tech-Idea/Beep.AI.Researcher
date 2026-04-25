# API Assessment: Existing Routes vs. Enhancement Plan

**Updated**: February 6, 2026 - **Python SDK now matches DotNet (v1.0 parity achieved)**

## Summary of Changes

### ✅ Python SDK Updated to Match DotNet

**Added Methods** (from DotNet):
- App User Management: `register_app_user`, `get_app_user`, `get_app_user_usage`, `update_app_user`, `set_app_user_tier`, `delete_app_user`, `list_app_users`, `list_tiers`
- User-Scoped RAG: `list_user_collections`, `create_user_collection`, `get_user_collection`, `update_user_collection`, `delete_user_collection`

**Status**: Sync complete - Both DotNet and Python SDKs now have feature parity

---

## Current Beep.AI.Researcher Routes (Production)

---

## Current Beep.AI.Researcher Routes (Production)

### Projects Management
```
GET    /projects/                    → List projects (projects.py:19)
POST   /projects/                    → Create project (projects.py:57)
GET    /projects/<id>                → Get project (projects.py:95)
PUT    /projects/<id>                → Update project (projects.py:125)
DELETE /projects/<id>                → Delete project (projects.py:155)
GET    /projects/rag/collections     → List RAG collections (projects.py:171)
```

### Documents
```
GET    /projects/<id>/documents                     → List docs (documents.py:25)
POST   /projects/<id>/documents/upload             → Upload (documents.py:78)
GET    /projects/<id>/documents/<doc_id>           → Get doc (documents.py:156)
GET    /projects/<id>/documents/<doc_id>/content   → Get content (documents.py:177)
```

### Search & Chat (Local + RAG)
```
POST/GET  /projects/<id>/search       → Local search or RAG (search.py:81)
POST      /projects/<id>/chat         → Send chat message (chat.py:31)
GET       /projects/<id>/chat/history → Get chat history (chat.py:101)
```

### Extraction (Elicit-style)
```
GET    /projects/<id>/extraction/schemas      → List schemas (extraction.py:10)
POST   /projects/<id>/extraction/schemas      → Create schema (extraction.py:36)
POST   /projects/<id>/extract                 → Run extraction (extraction.py:79)
GET    /projects/<id>/extractions             → List results (extraction.py:131)
```

### Codes (Annotation & Management)
```
(routes in codes.py - implicit CRUD)
```

### AI Templates (Modal System)
```
GET     /researcher/ai/templates/<id>            → Get template config (ai_templates.py:38)
POST    /researcher/ai/execute                   → Create execution (ai_templates.py:81)
GET     /researcher/ai/stream/<id>               → SSE stream (ai_templates.py:165)
GET     /researcher/ai/export/<id>/<format>      → Export result (ai_templates.py:207)
GET     /researcher/ai/workbooks                 → List workbooks (ai_templates.py:244)
POST    /researcher/ai/save-to-workbook          → Save to workbook (ai_templates.py:258)
GET     /researcher/ai/browse                    → Browse templates (ai_templates.py:290)
```

### Data Analysis (SPSS-style)
```
POST   /projects/<id>/stats/describe     → Descriptive stats (stats.py:25)
POST   /projects/<id>/stats/crosstab     → Cross-tabs (stats.py:69)
POST   /projects/<id>/stats/regression   → Regression (stub) (stats.py:116)
```

### Data Upload & Charts
```
(routes in data_analyst.py - implicit CRUD)
```

### Export
```
POST/GET  /projects/<id>/export    → Export (JSON/CSV/Excel/SPSS) (export_routes.py:20)
```

### Annotations (Highlights/Memos)
```
GET    /projects/<id>/documents/<doc_id>/annotations           → List (annotations.py:12)
POST   /projects/<id>/documents/<doc_id>/annotations           → Add (annotations.py:33)
DELETE /projects/<id>/documents/<doc_id>/annotations/<ann_id>  → Delete (annotations.py:54)
```

### Tasks
```
GET    /projects/<id>/tasks                    → List tasks (tasks.py:25)
POST   /projects/<id>/tasks                    → Create (tasks.py:46)
PUT    /projects/<id>/tasks/<id>               → Update (tasks.py:76)
DELETE /projects/<id>/tasks/<id>               → Delete (tasks.py:103)
GET    /projects/<id>/notifications            → List notifications (tasks.py:123)
```

### Scheduled Reports (Julius-style)
```
POST  /projects/<id>/reports/schedule      → Create scheduled report (scheduled_reports.py:10)
GET   /projects/<id>/reports/scheduled     → List scheduled reports (scheduled_reports.py:34)
```

### Contradiction Detection (Anara-style, Stub)
```
POST  /projects/<id>/contradictions    → Detect contradictions (contradiction.py:14)
```

### Coding Matrices
```
(routes in coding_matrices.py - implicit)
```

### Report Writing
```
(routes in report_writing.py - implicit)
```

### Collaboration (Phase 3)
```
(routes in collaboration.py - implicit)
```

### Retention Policies
```
GET  /projects/<id>/retention       → Get retention policy (retention.py:10)
PUT  /projects/<id>/retention       → Set retention policy (retention.py:29)
```

### References
```
(routes in references.py - implicit)
```

### Admin & Tenants
```
GET    /tenants/                     → List tenants (tenants.py:14)
POST   /tenants/                     → Create (tenants.py:38)
GET    /tenants/<id>                 → Get (tenants.py:64)
PUT    /tenants/<id>                 → Update (tenants.py:90)
DELETE /tenants/<id>                 → Delete (tenants.py:117)
GET    /tenants/<id>/members         → Members (tenants.py:143)
```

---

## Enhancement Plan Mapping

### ❌ PROBLEM: Proposed routes that ALREADY EXIST

The enhancement plan proposed:
```
GET    /api/v1/projects/{id}/documents
→ Already exists: GET /projects/{id}/documents
  
POST   /api/v1/projects/{id}/web-search
→ Partially exists: POST /projects/{id}/search
  (Does local search; enhancement adds external academic sources)
  
GET    /api/v1/projects/{id}/chat/sessions
→ Partially exists: GET /projects/{id}/chat/history
  (Gets messages; enhancement adds session management)
  
POST   /api/v1/projects/{id}/extraction/run
→ Already exists: POST /projects/{id}/extract
```

### ✅ SOLUTION: Map Enhancement to Real Gaps

The enhancement plan's **actual value** is:

#### PHASE 1: Feature Integration Bus + API Gateway

**What's needed** (NOT what's currently there):
- **Event Bus**: Makes features talk to each other without coupling
  - Example: When document uploaded → MedicalPlugin auto-extracts
  - Currently: Manual step-by-step process
  
- **Hook System**: Let plugins intercept operations
  - Example: Before chat reply → RobustnessPlugin adds disclaimer
  - Currently: No plugin system exists
  
- **Job Queue**: Background processing
  - Example: Web search API calls shouldn't block UI
  - Currently: All operations synchronous
  
- **Versioned API Gateway**: `/api/v1/` wrapping existing routes
  - Currently: Mixed `/projects/`, `/researcher/` prefixes
  - Value: Consistent versioning, deprecation path, feature flags

#### PHASE 2: Web Search + Library Connectors

**What's missing**:
- Currently has: Local document search + RAG (via Beep.AI.Server)
- Missing: External academic sources
  - Semantic Scholar, PubMed, arXiv, CrossRef, IEEE, JSTOR, etc.
  - Library authentication/credential management
  - Async ingestion into project RAG
  
**New endpoints needed**:
```
POST   /projects/<id>/web-search/academic
  With providers: ["pubmed", "arxiv", "semantic_scholar"]
  
GET    /admin/library-sources                      (new)
POST   /admin/library-sources/<id>/test-connection (new)
POST   /projects/<id>/library-search               (new)
```

#### PHASE 3: Plugin System

**What's missing**:
- Medical plugin (drug interactions, ICD-10, CPT codes)
- Legal plugin (contract review, case law)
- Engineering plugin (standards compliance, part numbers)
- Plugin admin UI
- Plugin API for AI templates, extraction schemas, validators

**New endpoints needed**:
```
GET    /admin/plugins                           (new)
POST   /admin/plugins/{id}/activate             (new)
POST   /admin/plugins/{id}/deactivate           (new)
DELETE /admin/plugins/{id}                      (new)
POST   /admin/plugins/{id}/config               (new)
```

#### PHASE 4: Research Features

**What's missing**:
- Literature reviews (PRISMA methodology)
- Hypothesis tracking with evidence linking
- Peer review comments with threading
- Document version history (git-style)
- Compliance mapping (HIPAA, GDPR, SOX)

**New endpoints needed**:
```
POST   /projects/<id>/literature-reviews           (new)
POST   /projects/<id>/hypotheses                   (new)
POST   /projects/<id>/hypotheses/<id>/evidence     (new)
GET    /projects/<id>/documents/<id>/versions      (new)
POST   /projects/<id>/compliance/map               (new)
GET    /projects/<id>/compliance/<standard>/status (new)
```

#### PHASE 5: Collaboration & Workflow

**What's missing**:
- WebSocket real-time sync (currently no real-time support)
- Workflow builder (node-based automation)
- Additional export formats (RDF, BibTeX, Zotero sync)

**New endpoints needed**:
```
WS     /projects/<id>/collaborate    (WebSocket, new)
POST   /projects/<id>/workflows      (new)
POST   /projects/<id>/workflows/<id>/execute  (new)
POST   /projects/<id>/export/rdf     (new)
POST   /projects/<id>/export/bibtex  (new)
```

#### PHASE 6: Analytics

**What's missing**:
- Research dashboard (metrics, progress)
- Recommendation engine
- Cross-project analysis

**New endpoints needed**:
```
GET    /projects/<id>/analytics/overview        (new)
GET    /projects/<id>/analytics/trends          (new)
GET    /projects/<id>/recommendations           (new)
```

---

## Updated Enhancement Plan Strategy

### DO NOT: Create `/api/v1/` namespace

**Reason**: Breaking change, forces clients to migrate. Old routes still used.

### DO: Extend existing routes with new features

**Example - Phase 2 Web Search**:
```python
# Current (local + RAG only)
POST /projects/<id>/search
  {query: "...", source: "local"}

# Phase 2 Enhancement (add external sources)
POST /projects/<id>/search
  {query: "...", source: "all"}  # local + rag
  
POST /projects/<id>/web-search  # NEW
  {query: "...", providers: ["pubmed", "arxiv"]}
```

### DO: Add new routes for new features

**Example - Phase 3 Plugin System**:
```python
# NEW routes (no existing equivalent)
GET    /admin/plugins
POST   /admin/plugins/{id}/activate
```

### DO: Use Event Bus & Hooks internally

**Example - Phase 1 integration**:
```python
# User uploads document
POST /projects/<id>/documents/upload
  # Internally triggers:
  # EventBus.publish("document.uploaded", {...})
  #   ├→ MedicalPluginHook.on_document_uploaded()
  #   ├→ ExtractionHook.auto_run()  
  #   └→ NotificationHook.alert_team()
  
  # UI sees automatic extractions completed
```

---

## Implementation Priority

### Phase 1: Foundation (2-3 weeks) - INTERNAL CHANGES
- ✅ Event Bus (internal feature communication)
- ✅ Hook System (plugin integration points)
- ✅ Job Queue (async processing)
- ✅ Route organization (not `/api/v1/` migration, just cleaner structure)

**No new routes exposed yet** - improves internals for Phases 2-6

### Phase 2: Search (2-3 weeks) - NEW ROUTES
- `POST /projects/<id>/web-search` (uses Phase 1 Job Queue)
- `GET /admin/library-sources` + CRUD
- Uses existing `/projects/<id>/search` alongside new endpoints

### Phase 3: Plugins (3-4 weeks) - NEW ROUTES + FRAMEWORK
- `/admin/plugins/*` routes
- Plugin manager, registry, loader
- Hooks for AI templates, extraction, validators

### Phase 4-6: Research, Collab, Analytics (9-13 weeks) - NEW ROUTES
- Hundreds of new endpoints for literature, hypothesis, compliance, workflow, etc.

---

## Recommendation

**Update ENHANCEMENT_PLAN.md to**:

1. ✅ Keep Phases 1-6 structure
2. ✅ Keep Phase 1 explanation (Event Bus, Hooks, Job Queue)
3. ⚠️ **FIX Phase 2**: Map to existing `/projects/{id}/search` + add `POST /web-search`
4. ⚠️ **FIX API examples**: Use `/projects/` prefix, not `/api/v1/`
5. ✅ Keep Phase 3-6 proposals as-is (genuinely new capabilities)
6. 📝 Add section: "**Integration with Existing Routes**" showing how Phase 1 enhances current endpoints

---

## Quick Reference: What Actually Needs Building

| Feature | Exists? | Where | Enhancement |
|---------|---------|-------|-------------|
| Documents CRUD | ✅ | `/projects/{id}/documents` | Add versioning |
| Search (local) | ✅ | `/projects/{id}/search` | Add external sources |
| Chat | ✅ | `/projects/{id}/chat` | Add real-time (WebSocket) |
| Extraction | ✅ | `/projects/{id}/extract` | Add plugin schemas + validators |
| Codes | ✅ | `/projects/{id}/codes` | Add plugin-defined code schemes |
| Export | ✅ | `/projects/{id}/export` | Add RDF, BibTeX, Zotero, GitHub |
| Tasks | ✅ | `/projects/{id}/tasks` | Add workflow automation |
| **Web Search** | ❌ | NEW | Phase 2 |
| **Library Auth** | ❌ | NEW | Phase 2 |
| **Plugins** | ❌ | NEW | Phase 3 |
| **Literature Reviews** | ❌ | NEW | Phase 4 |
| **Hypotheses** | ❌ | NEW | Phase 4 |
| **Peer Review Comments** | ⚠️ | Annotations exist, but limited | Phase 4 (enhance) |
| **Document Versions** | ❌ | NEW | Phase 4 |
| **Compliance Tracking** | ❌ | NEW | Phase 4 |
| **Real-time Collab** | ❌ | NEW | Phase 5 |
| **Workflows** | ❌ | NEW | Phase 5 |
| **Analytics Dashboard** | ❌ | NEW | Phase 6 |
| **Recommendations** | ❌ | NEW | Phase 6 |

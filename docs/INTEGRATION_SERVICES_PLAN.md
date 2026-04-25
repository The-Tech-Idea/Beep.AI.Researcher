# Integration Services Enhancement Plan

> **Goal:** Transform the current search-only integration layer into a comprehensive,
> production-grade integration framework modeled after best practices from Notion, Zotero,
> Obsidian, and modern research platforms.

---

## 1  Current State — Architecture Audit

### What Exists

| Layer | Files | Status |
|-------|-------|--------|
| **Search Providers** | `AbstractSearchProvider` → `PubMedProvider`, `ArxivProvider` | ✅ Working |
| **Search Manager** | `SearchManager` (singleton, dedup, cache, rate-limit) | ✅ Working |
| **AI Service** | `ai_service.py`, `beep_ai_client.py` (LLM, tool calling, vision) | ✅ Working |
| **Reference Service** | `reference_service.py` (BibTeX/RIS import, DOI validation) | ✅ Working |
| **Plugin System** | `plugin_base.py`, `plugin_manager.py`, `plugin_registry.py` | ✅ Working (extensible hooks) |

### What's Missing

| Gap | Impact |
|-----|--------|
| **5 planned providers never built** | Semantic Scholar, CrossRef, OpenAccessButton, IEEE, JSTOR listed in `ProviderType` enum but have no implementation |
| **No storage/cloud integrations** | No Google Drive, Dropbox, OneDrive, S3 for document import |
| **No citation manager sync** | No Zotero API or Mendeley API connector |
| **No export integrations** | No push to external services (Notion, Google Docs, LaTeX editors) |
| **No webhook/event system** | No outbound notifications when documents, codes, or analysis change |
| **No OAuth/API key management** | Each provider hardcodes credentials; no user-level API key vault |
| **No import from web sources** | No web page scraping, RSS feed, or URL-to-document pipeline |
| **Plugin system has no external connectors** | Hooks exist (`on_document_upload`, `on_extraction`) but no built-in plugins use external services |

---

## 2  Best Practices from Leading Apps

### How Notion Does It
- **API-first design** — every integration uses a unified REST API with OAuth 2.0
- **Webhook actions** — automations trigger HTTP POST on database changes
- **Connection model** — each integration is a "connection" with its own permissions scope
- **Rate limiting** — enforced per-integration with backoff/retry

### How Zotero Does It
- **Open API with API keys** — user-level keys with granular read/write permissions
- **Better BibTeX plugin** — structured export pipeline with citation key generation
- **Sync protocol** — incremental sync with version tracking (If-Modified-Since)
- **Library-level connections** — each library can connect to different services

### How Obsidian Does It
- **Local-first architecture** — all data stays local, integrations pull/push explicitly
- **Plugin-driven extensions** — community plugins for each external service
- **Template-based import** — configurable templates for how imported data renders
- **URI scheme** — external apps can push data into Obsidian via `obsidian://` URIs

### Common Patterns Across All

| Pattern | Description |
|---------|-------------|
| **Abstract Connection Interface** | All integrations implement a common interface: `connect()`, `sync()`, `disconnect()` |
| **Credential Vault** | API keys/tokens stored encrypted, per-user, with rotation support |
| **Event Bus** | Internal events (`document.created`, `code.applied`) trigger integration actions |
| **Retry + Circuit Breaker** | Exponential backoff with circuit breaker for failing providers |
| **Incremental Sync** | Track last sync timestamp; only fetch changes since then |
| **Unified Data Model** | All external data is normalized into internal models before storage |
| **User-configurable** | Users choose which integrations to enable per project |

---

## 3  Proposed Architecture

### 3.1  Layer Diagram

```
┌─────────────────────────────────────────────────────┐
│                  Routes / API                        │
├─────────────────────────────────────────────────────┤
│               Integration Manager                    │
│    ┌──────────┬──────────┬──────────┬────────────┐  │
│    │ Search   │ Storage  │ Citation │  Export     │  │
│    │ Providers│ Providers│ Sync     │  Connectors │  │
│    ├──────────┼──────────┼──────────┼────────────┤  │
│    │ PubMed   │ GDrive   │ Zotero   │ Notion     │  │
│    │ ArXiv    │ Dropbox  │ Mendeley │ Google Docs│  │
│    │ Semantic │ OneDrive │          │ LaTeX/Overl│  │
│    │ CrossRef │ S3       │          │ BibTeX     │  │
│    │ IEEE     │ URL/RSS  │          │ CSV/Excel  │  │
│    │ JSTOR    │          │          │ Markdown   │  │
│    └──────────┴──────────┴──────────┴────────────┘  │
├─────────────────────────────────────────────────────┤
│   Credential Vault │ Event Bus │ Sync Engine        │
├─────────────────────────────────────────────────────┤
│               Plugin System (existing)               │
└─────────────────────────────────────────────────────┘
```

### 3.2  New Files / Modules

```
app/integrations/
├── __init__.py                    # [MODIFY] Register all integration types
├── base_connector.py              # [NEW] Abstract base for all integrations
├── credential_vault.py            # [NEW] Encrypted API key storage
├── integration_manager.py         # [NEW] Central registry + lifecycle
├── sync_engine.py                 # [NEW] Incremental sync with versioning
├── event_bridge.py                # [NEW] Connect internal events → integrations
├── search/                        # [EXISTS] Academic search providers
│   ├── providers/
│   │   ├── semantic_scholar.py    # [NEW] Semantic Scholar API
│   │   ├── crossref.py            # [NEW] CrossRef API
│   │   └── openalex.py            # [NEW] OpenAlex API (replaces OpenAccessButton)
│   └── ...
├── storage/                       # [NEW] Cloud storage integrations
│   ├── __init__.py
│   ├── base_storage.py            # [NEW] Abstract storage provider
│   ├── google_drive.py            # [NEW] Google Drive import/export
│   ├── dropbox.py                 # [NEW] Dropbox import
│   ├── onedrive.py                # [NEW] OneDrive import
│   └── url_importer.py            # [NEW] URL/RSS → document pipeline
├── citation/                      # [NEW] Citation manager sync
│   ├── __init__.py
│   ├── base_citation.py           # [NEW] Abstract citation sync
│   ├── zotero_sync.py             # [NEW] Zotero API two-way sync
│   └── mendeley_sync.py           # [NEW] Mendeley API sync
├── export/                        # [NEW] Export/push connectors
│   ├── __init__.py
│   ├── base_export.py             # [NEW] Abstract export provider
│   ├── notion_export.py           # [NEW] Push to Notion databases
│   ├── google_docs_export.py      # [NEW] Push to Google Docs
│   ├── latex_export.py            # [NEW] Generate LaTeX/Overleaf
│   └── markdown_export.py         # [NEW] Export as structured Markdown
└── webhooks/                      # [NEW] Outbound webhook system
    ├── __init__.py
    ├── webhook_manager.py         # [NEW] Register + fire webhooks
    └── webhook_routes.py          # [NEW] API endpoints for webhook CRUD
```

---

## 4  Phased Implementation

### Phase 1 — Foundation (Infrastructure)

> Build the integration framework that all connectors will use.

#### [NEW] `base_connector.py`
Abstract base class for all integration types:
- `connect(credentials)` → establish connection
- `test_connection()` → verify credentials work
- `sync(since=None)` → incremental sync
- `disconnect()` → clean up
- `get_status()` → health check
- Built-in retry with exponential backoff + circuit breaker

#### [NEW] `credential_vault.py`
Encrypted credential storage:
- Model: `IntegrationCredential(user_id, integration_type, encrypted_data, expires_at)`
- Encrypt/decrypt using Fernet (from `cryptography` library)
- Per-user, per-integration key storage
- Rotation support with `rotate_key(integration_id)`

#### [NEW] `integration_manager.py`
Central registry following the existing `SearchManager` singleton pattern:
- `register_integration(name, connector_class)` → register provider
- `get_integration(name)` → get configured instance
- `list_integrations()` → all available + their status
- `enable_for_project(project_id, integration_name, credentials)` → project-level activation

#### [NEW] `event_bridge.py`
Connect the existing plugin hook system to integrations:
- Listen for internal events (`document.uploaded`, `code.created`, `extraction.completed`)
- Route events to enabled integrations (e.g., "on extraction complete → push to Notion")
- Configurable per-project event routing

#### [NEW] `sync_engine.py`
Incremental synchronization engine:
- Track `last_sync_at` per integration per project
- Fetch only changed items since last sync
- Conflict resolution: latest-timestamp-wins with audit log
- Background sync via existing job queue

---

### Phase 2 — Search Provider Expansion

> Implement the 3 most impactful missing academic search providers.

#### [NEW] `semantic_scholar.py`
- Free API, no key required for basic use
- Returns citation counts, influential citations, paper recommendations
- Rate limit: 100 requests/5 minutes (public), 1000/min (API key)

#### [NEW] `crossref.py`
- DOI-based metadata resolution
- Works and Members API for publisher metadata
- Polite pool: add `mailto` parameter for higher rate limits

#### [NEW] `openalex.py`
- Replaces OpenAccessButton (which is deprecated)
- 100M+ works, free, no auth required
- Rich filtering: by institution, journal, concept, year

---

### Phase 3 — Storage Integrations

> Enable document import from cloud storage services.

#### [NEW] `google_drive.py`
- OAuth 2.0 flow with refresh token
- List/search files → import as project documents
- Watch for changes (push notifications via webhook)

#### [NEW] `url_importer.py`
- Input: URL → extract text content → create document
- Support: HTML pages, PDF URLs, RSS/Atom feeds
- Uses `readability-lxml` for article extraction + `feedparser` for RSS
- Configurable: auto-import new RSS items on schedule

---

### Phase 4 — Citation Manager Sync

> Two-way sync with researcher's existing citation libraries.

#### [NEW] `zotero_sync.py`
- Zotero Web API v3
- Sync: Zotero collections ↔ project references
- Import: items + PDFs + annotations
- Delta sync using `If-Modified-Since-Version` header
- Map Zotero item types → internal `Reference` model

---

### Phase 5 — Export Connectors

> Push research outputs to external platforms.

#### [NEW] `notion_export.py`
- Create/update Notion database rows from extraction results
- Push flashcards as Notion pages
- Push report content as Notion blocks

#### [NEW] `latex_export.py`
- Generate `.tex` file from report content
- Include `\bibliography{}` from project references
- BibTeX export with proper citation keys

#### [NEW] `markdown_export.py`
- Export project as structured Markdown (report + references + codes)
- Compatible with Obsidian vault format
- Include YAML frontmatter with metadata

---

### Phase 6 — Webhooks & Event System

> Enable external systems to react to Beep.AI events.

#### [NEW] `webhook_manager.py`
- CRUD for webhook subscriptions per project
- Events: `document.created`, `document.deleted`, `extraction.completed`,
  `flashcard.generated`, `quiz.completed`, `code.created`
- Delivery: HTTP POST with HMAC signature verification
- Retry: 3 attempts with exponential backoff
- Delivery log with status tracking

#### [NEW] `webhook_routes.py`
- `POST /projects/<id>/webhooks` → create subscription
- `GET /projects/<id>/webhooks` → list subscriptions
- `DELETE /projects/<id>/webhooks/<wid>` → remove
- `GET /projects/<id>/webhooks/<wid>/deliveries` → delivery log

---

## 5  Database Changes

```sql
-- Integration credentials (Phase 1)
CREATE TABLE integration_credential (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user(id),
    integration_type VARCHAR(50) NOT NULL,    -- 'google_drive', 'zotero', etc.
    encrypted_data TEXT NOT NULL,              -- Fernet-encrypted JSON
    display_name VARCHAR(100),
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, integration_type)
);

-- Project integration enablement (Phase 1)
CREATE TABLE project_integration (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES research_project(id),
    integration_type VARCHAR(50) NOT NULL,
    credential_id INTEGER REFERENCES integration_credential(id),
    config_json TEXT DEFAULT '{}',
    enabled BOOLEAN DEFAULT 1,
    last_sync_at DATETIME,
    sync_status VARCHAR(20) DEFAULT 'idle',   -- idle, syncing, error
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Webhook subscriptions (Phase 6)
CREATE TABLE webhook_subscription (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES research_project(id),
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(100),                       -- For HMAC signing
    events TEXT NOT NULL,                       -- JSON array of event types
    active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Webhook delivery log (Phase 6)
CREATE TABLE webhook_delivery (
    id INTEGER PRIMARY KEY,
    subscription_id INTEGER NOT NULL REFERENCES webhook_subscription(id),
    event_type VARCHAR(50) NOT NULL,
    payload_json TEXT,
    response_status INTEGER,
    response_body TEXT,
    delivered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT 0
);
```

---

## 6  Priority Ranking

| Phase | Effort | Impact | Priority |
|-------|--------|--------|----------|
| **P1: Foundation** | Medium | Critical | 🔴 Must-do first |
| **P2: Search Expansion** | Low | High | 🟠 Quick wins |
| **P3: Storage** | Medium | High | 🟡 High value |
| **P4: Citation Sync** | Medium | High | 🟡 Research workflow |
| **P5: Export** | Medium | Medium | 🟢 Nice to have |
| **P6: Webhooks** | Low | Medium | 🟢 Developer-facing |

---

## 7  Verification Plan

### Automated Tests
Each new provider/connector should have:
1. **Unit test** — mock external API, verify data mapping
2. **Integration test** — call real API with test credentials (skipped in CI without keys)
3. `python -m pytest tests/integrations/ -v`

### Manual Verification
1. Start the app via `./run.bat`
2. Navigate to **Project Settings → Integrations** tab
3. Verify each integration can be enabled, credentials tested, and sync run
4. For search providers: verify results appear in Library search

> [!IMPORTANT]
> **Phase 1 (Foundation) must be implemented first** — all other phases depend on the
> `base_connector.py`, `credential_vault.py`, and `integration_manager.py` infrastructure.

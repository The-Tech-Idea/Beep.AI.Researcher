# Beep.AI.Researcher — Structure & Function Reorganization Plan

**Date:** 2026-02-05

This plan is based on a review of the existing architecture and implementation docs, plus current route, template, and service structure. It aligns the Researcher app with the newer AI apps pattern (collapsible AI assistant panel instead of a separate chat page).

---

## 1) Current Structure Snapshot (What exists today)

### Routes (Blueprints)
- Project-scoped APIs and pages are mixed under /projects via multiple blueprints in [app/__init__.py](app/__init__.py)
- Chat is implemented as project-scoped routes in [app/routes/chat.py](app/routes/chat.py) and rendered via [templates/chat.html](templates/chat.html)
- A new global chat API has been added in [app/routes/global_chat.py](app/routes/global_chat.py) but needs to become the primary UI entry

### Templates
- Many top-level pages live in [templates](templates)
- Layouts: [templates/base.html](templates/base.html), [templates/base_embed.html](templates/base_embed.html)
- Project pages live in [templates/project](templates/project)
- Components are minimal (only [templates/components/ai_template_modal.html](templates/components/ai_template_modal.html))

### Services
- AI integration is centralized in [app/services/beep_ai_client.py](app/services/beep_ai_client.py)
- Chat with documents uses RAG in project-scoped logic in [app/routes/chat.py](app/routes/chat.py)

### Documentation
- Architecture summary and flows are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Implementation status is in [docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md)
- UI/UX aspirations are outlined in [docs/ui_ux_enhancement_plan.md](docs/ui_ux_enhancement_plan.md)

---

## 2) Problems Observed

1. **Chat is a separate page** (templates/chat.html) instead of a collapsible AI assistant panel like newer apps.
2. **Mixed route structure**: UI routes and API routes are spread across multiple files without a clear boundary.
3. **Template organization is flat**: non-project pages, project pages, and AI flows are all at the root of templates.
4. **Inconsistent UX patterns**: some pages feel like legacy dashboard pages, others use newer components.

---

## 3) Target Structure (Proposed)

### 3.1 Blueprint & Route Organization
Create a clear separation between **UI pages** and **API endpoints**, and group by feature:

**UI Blueprints (pages)**
- ui_dashboard_bp → [app/routes/dashboard.py](app/routes/dashboard.py)
- ui_projects_bp → [app/routes/projects.py](app/routes/projects.py)
- ui_documents_bp → [app/routes/documents.py](app/routes/documents.py)
- ui_codes_bp → [app/routes/codes.py](app/routes/codes.py)
- ui_reports_bp → [app/routes/report_writing.py](app/routes/report_writing.py)

**API Blueprints (JSON only)**
- api_projects_bp → /api/projects
- api_documents_bp → /api/projects/<id>/documents
- api_search_bp → /api/projects/<id>/search
- api_chat_bp → /api/chat (global, non-project)
- api_project_chat_bp → /api/projects/<id>/chat (project-scoped)

This makes it clear which endpoints are meant for UI, and which are meant for JS clients.

### 3.2 Templates Structure
Reorganize templates by domain to reduce clutter:

```
templates/
  layouts/
    base.html
    base_embed.html
  pages/
    dashboard/
    project/
    documents/
    data/
    codes/
    reports/
    auth/
  components/
    ai_chat_panel.html
    nav.html
    modals/
```

- Move common UI elements into components
- Use includes for shared elements instead of duplicating markup

### 3.3 Global Chat Panel (Like Jarvis)
- Default AI assistant should be a collapsible panel (left or right) injected into base layout.
- The existing [templates/chat.html](templates/chat.html) should be deprecated or redirected.
- All AI interactions use /api/chat for general help, and /api/projects/<id>/chat for contextual project chat.

### 3.4 JavaScript/CSS Organization
- Split JS by feature:
  - static/js/chat-panel.js
  - static/js/documents.js
  - static/js/projects.js
  - static/js/codes.js
- Split CSS by feature:
  - static/css/chat-panel.css
  - static/css/pages/...

---

## 4) Phased Migration Plan

### Phase A — Stabilize Chat UX (Immediate)
1. Make collapsible AI chat panel the default UI (already added in base layout).
2. Keep project-scoped chat for RAG context.
3. Remove direct navigation to the old chat page or redirect it to a default project view.

### Phase B — Route Cleanup
1. Split UI vs API endpoints.
2. Introduce /api namespace for JSON routes.
3. Ensure all API routes return consistent JSON shape:
   - success, data, error

### Phase C — Template Reorganization
1. Create templates/layouts and templates/pages directories.
2. Move old templates into new structure.
3. Refactor base.html to include modular components.

### Phase D — Service Layer Standardization
1. Add service wrappers for each core domain:
   - ProjectService, DocumentService, ChatService
2. Move heavy logic out of route handlers.

---

## 5) Backward Compatibility & Risk Notes

- Keep existing routes working during migration.
- Add redirects for legacy endpoints (like /projects/<id>/chat page).
- Maintain the same database schema.

---

## 6) Acceptance Criteria

1. AI chat is available as a collapsible panel on every page.
2. Chat no longer requires a dedicated page.
3. Routes are clearly split between UI and API paths.
4. Templates are grouped by domain and use shared components.
5. Docs updated to reflect new structure.

---

## 7) Next Actions (If Approved)

1. Create new template folder structure and migrate pages.
2. Add a new /api namespace and update JS fetch calls.
3. Deprecate templates/chat.html and point to panel.
4. Update docs/ARCHITECTURE.md with new routing map.

---

## 8) Additional Functions (From Jenni-style reference UI)

These are **planned features**. If they are not implemented yet, they should be tracked as future work (post‑Phase A) and placed into the backlog.

1. **Grammar Checker**
  - Goal: Improve academic writing quality.
  - Proposed API: `/api/ai/grammar-check`
  - Status: Planned

2. **Paraphraser**
  - Goal: Improve fluency and academic tone.
  - Proposed API: `/api/ai/paraphrase`
  - Status: Planned

3. **Research & Cite**
  - Goal: Find citations/references from external sources.
  - Proposed API: `/api/ai/research-cite`
  - Status: Planned (requires external citation provider)

4. **AI Writing Assistant**
  - Goal: Contextual writing help in editor and chat panel.
  - Proposed API: `/api/ai/writing-assistant`
  - Status: Planned

5. **Chat with PDFs**
  - Goal: Document‑level Q&A without project setup.
  - Proposed API: `/api/ai/chat-pdf`
  - Status: Planned (reuse document ingestion + RAG)

6. **Online Translator**
  - Goal: Translate content in 50+ languages.
  - Proposed API: `/api/ai/translate`
  - Status: Planned (requires translation provider)

7. **Plagiarism Checker**
  - Goal: Similarity checking against public sources.
  - Proposed API: `/api/ai/plagiarism-check`
  - Status: Planned (requires external provider)

8. **Submission Checks**
  - Goal: Pre‑submission checklist for academic manuscripts.
  - Proposed API: `/api/ai/submission-checks`
  - Status: Planned

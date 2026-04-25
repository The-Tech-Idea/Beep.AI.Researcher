# Beep.AI.Researcher — UI/UX Fix & Enhancement Planprocee

> **Date:** 2026-02-25  
> **Status:** Draft  
> **Scope:** Project sidebar fix, accessibility, responsive design, dependency fixes, theme alignment with AI Server, template reorganization  
> **Estimated Effort:** ~10 hours across 6 phases

---

## Executive Summary

The project side menu (sidebar) is **missing on the Data & Charts page** because `data.html` extends `base.html` directly, skipping the `project/_layout.html` template that renders the sidebar. Additionally, **18 other UI/UX issues** were identified across accessibility, responsive design, CSS conflicts, missing Python dependencies, and theme inconsistency with the AI Server.

**Key decisions made:**
- Theme colors and fonts will align with AI Server (Indigo-Purple gradient, Outfit/Inter fonts)
- Fonts must support all languages including Arabic (add Noto Sans Arabic + RTL support)
- All 11 misplaced project-scoped templates will be moved into `templates/project/`

---

## Issue Inventory (19 issues)

| # | Priority | Issue | Files Affected |
|---|----------|-------|----------------|
| 1 | **CRITICAL** | `data.html` extends `base.html` instead of `project/_layout.html` — no project sidebar | `templates/data.html` |
| 2 | **CRITICAL** | `active_page` never passed from any route — sidebar highlighting broken everywhere | `app/routes/dashboard.py` |
| 3 | **HIGH** | `psutil` missing from requirements.txt — crashes `monitoring.py` on import | `requirements.txt`, `app/services/monitoring.py` |
| 4 | **HIGH** | `alembic` missing from requirements.txt — migration scripts fail | `requirements.txt` |
| 5 | **HIGH** | Mobile sidebar toggle class mismatch: JS looks for `.mobile-menu-btn`, HTML has `.spa-mobile-menu-btn` | `static/js/project/sidebar.js`, `templates/base.html` |
| 6 | **HIGH** | 30+ form labels missing `for` attributes (setup, register, login, flashcards, tasks, search, etc.) | Multiple templates |
| 7 | **HIGH** | Icon-only buttons missing `aria-label` (tasks +, search send, codes add) | `project/tasks.html`, `project/search.html`, `project/codes.html` |
| 8 | **HIGH** | No skip-to-content link in base.html | `templates/base.html` |
| 9 | **MEDIUM** | Dual sidebar conflict — SPA sidebar + project sidebar overlap on mobile | `templates/base.html`, `templates/project/_layout.html` |
| 10 | **MEDIUM** | Design system tokens mismatch — MASTER.md says cyan/Inter, CSS uses deep-blue/Fira, AI Server uses Indigo/Outfit | `design-system/MASTER.md`, `static/css/design-system.css` |
| 11 | **MEDIUM** | 7 overlapping CSS files redefine `.btn-primary`, `.card`, etc. | Multiple CSS files |
| 12 | **MEDIUM** | Chart.js (200KB) loaded globally in `<head>` on every page | `templates/base.html` |
| 13 | **MEDIUM** | `cryptography` missing from requirements.txt — credential vault falls back to insecure base64 | `requirements.txt`, `app/integrations/credential_vault.py` |
| 14 | **MEDIUM** | Project templates scattered — 11 project-scoped files at root of `templates/` instead of `templates/project/` | `templates/data.html`, `templates/contradictions.html`, etc. |
| 15 | **LOW** | SPA routes map incomplete — ~10 project views missing from `workspace.js` ROUTES | `static/js/workspace.js` |
| 16 | **LOW** | `beepUI.showToast()` called in data.html but may not be defined | `templates/data.html` |
| 17 | **LOW** | Random cache-buster `{{ range(1,100000) | random }}` defeats browser caching | `templates/base.html` |
| 18 | **LOW** | `charts` variable passed to data.html but never used in template | `app/routes/dashboard.py` |
| 19 | **LOW** | `<html lang="en">` hardcoded despite i18n support | `templates/base.html` |

---

## Phase 1: Critical Sidebar & Dependency Fixes

### 1.1 Fix `data.html` Template Inheritance

**Root Cause:** `data.html` extends `base_template or "base.html"` directly. Every other project page (overview, documents, codes, tasks, settings, search, report) extends `project/_layout.html` which includes `_sidebar.html`. The Data & Charts page skips this chain, so **no project sidebar renders**.

**Template inheritance chain (correct):**
```
base.html  →  project/_layout.html  →  individual page (e.g. overview.html)
                  ↳ includes _sidebar.html
                  ↳ provides workspace_content block
                  ↳ loads project/layout.css + project/sidebar.js
```

**Fix — Change `data.html`:**

| Current (broken) | Correct |
|---|---|
| `{% extends base_template or "base.html" %}` | `{% extends "project/_layout.html" %}` |
| `{% block content %}` | `{% block workspace_content %}` |
| `{% block extra_js %}` | `{% block page_js %}` |
| (not set) | `{% set active_page = 'data' %}` |
| Upload button inline in content | Move to `{% block header_actions %}` |
| Page title/subtitle inline | Remove (provided by `_layout.html` via `page_title`/`page_subtitle`) |

### 1.2 Pass `active_page` from ALL Project Routes

**Problem:** Route handlers in `dashboard.py` never pass `active_page`, so sidebar highlighting is broken on **every** project page.

**Fix — Add to every `render_template()` call in `dashboard.py`:**

| Route Function | `active_page` Value |
|----------------|---------------------|
| `project_overview()` | `'overview'` |
| `project_documents()` | `'documents'` |
| `project_codes()` | `'codes'` |
| `project_tasks()` | `'tasks'` |
| `data_page()` | `'data'` |
| `project_search()` | `'search'` |
| `project_report()` | `'report'` |
| `project_settings()` | `'settings'` |
| `project_extraction()` | `'extraction'` |
| `project_contradictions()` | `'contradictions'` |
| `project_stats()` | `'stats'` |
| `project_flashcards()` | `'flashcards'` |
| `project_quizzes()` | `'quizzes'` |
| `project_retention()` | `'retention'` |
| `project_matrix()` | `'matrix'` |
| `project_scheduled_reports()` | `'reports'` |
| `project_hallucination_audit()` | `'hallucination'` |

### 1.3 Fix `data_page()` Route Context

**Problem:** Route doesn't pass sidebar badge counts (`document_count`, `code_count`, `task_count`).

**Fix — Add count queries matching how `project_overview()` does it:**
```python
from app.models.researcher import ResearcherDocument, Code, ResearchTask
document_count = ResearcherDocument.query.filter_by(project_id=project.id).count()
code_count = Code.query.filter_by(project_id=project.id).count()
task_count = ResearchTask.query.filter_by(project_id=project.id).count()
```

### 1.4 Add Missing Python Packages to `requirements.txt`

| Package | Why Missing Matters | Severity |
|---------|---------------------|----------|
| `psutil>=5.9.0` | `app/services/monitoring.py` line 2 does `import psutil` at module level — **crashes on import** | **HIGH** |
| `alembic>=1.12.0` | Migration scripts in `migrations/` won't run without it | **MEDIUM** |
| `cryptography>=41.0.0` | `app/integrations/credential_vault.py` falls back to insecure base64 encoding | **MEDIUM** |

**Updated requirements.txt:**
```
# --- Core ---
Flask>=3.0.0
requests>=2.31.0
Flask-SQLAlchemy>=3.1.0
Flask-Login>=0.6.0
Werkzeug>=3.0.0
Jinja2>=3.1.2

# --- Document/Data ---
openpyxl>=3.1.0
python-docx>=0.8.11
xhtml2pdf>=0.2.14
markdown>=3.4.0

# --- Monitoring ---
psutil>=5.9.0

# --- Database Migrations ---
alembic>=1.12.0

# --- Security (credential vault encryption) ---
cryptography>=41.0.0

# --- Testing ---
pytest>=7.0.0

# --- Optional: SPSS export ---
# pyreadstat>=1.2.0
# pandas>=2.0.0

# --- Optional: Google Drive integration ---
# google-api-python-client>=2.0.0
# google-auth>=2.0.0
```

---

## Phase 2: Theme Alignment with AI Server

### 2.1 Update CSS Variables to Match AI Server Palette

**Current state:** `design-system.css` uses deep-blue (`#1E40AF`) + Fira Code/Fira Sans.  
**Target:** Match AI Server's Indigo-Purple gradient system.

**AI Server Design Tokens (source of truth):**

| Token | Value |
|-------|-------|
| **Primary (Indigo)** | `#6366f1` |
| **Accent (Purple)** | `#a855f7` |
| **Accent (Fuchsia)** | `#d946ef` |
| **Gradient Primary** | `linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #d946ef 100%)` |
| **Active Link (dark)** | `#818cf8` |
| **Active Link (light)** | `#4f46e5` |

**Semantic Colors:**

| Role | Value |
|------|-------|
| Success | `#22c55e` / `#4ade80` |
| Danger | `#ef4444` / `#f87171` |
| Info | `#6366f1` / `#a5b4fc` |
| Warning | `#ffc107` |
| Blue | `#0ea5e9` / `#3b82f6` |
| Orange | `#f97316` |

**Background Colors (Dark Mode):**

| Token | Value |
|-------|-------|
| `--bg-body` | `#030305` |
| `--bg-surface` | `rgba(18, 18, 28, 0.7)` |
| `--bg-surface-secondary` | `#0a0a12` |
| `--text-primary` | `#e2e8f0` |
| `--text-secondary` | `rgba(255, 255, 255, 0.6)` |
| `--border-color` | `rgba(255, 255, 255, 0.08)` |

**Background Colors (Light Mode):**

| Token | Value |
|-------|-------|
| `--bg-body` | `#f8fafc` |
| `--bg-surface` | `rgba(255, 255, 255, 0.7)` |
| `--bg-surface-secondary` | `#f1f5f9` |
| `--text-primary` | `#0f172a` |
| `--text-secondary` | `#475569` |

**Layout Tokens:**

| Token | Value |
|-------|-------|
| `--sidebar-width` | `280px` |
| `--header-height` | `70px` |
| `--border-radius-lg` | `16px` |
| `--border-radius-md` | `12px` |
| `--border-radius-sm` | `8px` |
| `--backdrop-blur` | `blur(20px)` |

### 2.2 Switch Fonts with Arabic Support

**Replace Fira Code/Fira Sans with AI Server font stack + Arabic fallback:**

| Purpose | Font Stack |
|---------|------------|
| **Headings** | `'Outfit', 'Noto Sans Arabic', sans-serif` |
| **Body / UI** | `'Inter', 'Noto Sans Arabic', sans-serif` |
| **Monospace** | `'JetBrains Mono', monospace` |

**Google Fonts `<link>` update in `base.html`:**
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&family=Outfit:wght@300;400;500;600;700;800&family=Noto+Sans+Arabic:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

### 2.3 Update MASTER.md Design System Document

Update `design-system/beep.ai.researcher/MASTER.md` to reflect the new AI Server-aligned tokens, including the Indigo palette, Outfit/Inter fonts, and Arabic support.

### 2.4 Reduce CSS Cascade Conflicts

**Problem:** 7 CSS files loaded in order redefine `.btn-primary`, `.card`, `.form-control`:
1. `vendor/bootstrap.min.css`
2. `vendor/bootstrap-icons.css`
3. `design-system.css`
4. `dashboard-theme.css`
5. `jenni-theme.css` (2159 lines)
6. `chat-panel.css`
7. `project/layout.css`

**Fix:**
1. Consolidate component overrides into `design-system.css` only
2. Remove redundant `.btn-primary`, `.card`, `.form-control` from `jenni-theme.css` and `layout.css`
3. Use CSS custom properties so overrides cascade cleanly

---

## Phase 3: Accessibility (WCAG 2.1 AA)

### 3.1 Add `for` Attributes to Form Labels

**30+ labels missing across:**
- `templates/setup.html` — ~15 form labels (Username, Password, etc.)
- `templates/register.html` — all auth form labels
- `templates/login.html` — username/password labels
- `templates/references.html` — ~10 form labels
- `templates/resend_verification.html` — email label
- `templates/flashcards.html` — "From Documents" label
- `templates/contradictions.html` — "Search In" label
- `templates/design_system_demo.html` — demo labels
- `templates/project/tasks.html` — task form labels
- `templates/project/search.html` — RAG mode label

### 3.2 Add `aria-label` to Icon-Only Buttons

**Affected:**
- `templates/project/tasks.html` — add task `+` button
- `templates/project/search.html` — send button (`bi-send` icon)
- `templates/project/codes.html` — add code button
- `templates/base.html` — `spa-sidebar-collapse-btn`
- `templates/project/_sidebar.html` — toggle buttons

### 3.3 Add Skip-to-Content Link

**File:** `templates/base.html`

Add at top of `<body>`:
```html
<a href="#spa-content" class="visually-hidden-focusable">Skip to content</a>
```

### 3.4 Dynamic `lang` and `dir` Attributes

**File:** `templates/base.html`

Change:
```html
<!-- Before -->
<html lang="en">

<!-- After -->
<html lang="{{ g.locale or 'en' }}" dir="{{ 'rtl' if g.locale == 'ar' else 'ltr' }}">
```

This enables proper RTL layout for Arabic users.

### 3.5 Add `aria-current="page"` to Active Sidebar Items

**File:** `templates/project/_sidebar.html`

When `active_page` matches a nav item, add `aria-current="page"` alongside the `active` class.

---

## Phase 4: Responsive Design Fixes

### 4.1 Fix Mobile Sidebar Toggle Class Mismatch

**Problem:** `static/js/project/sidebar.js` line 31 listens for `.mobile-menu-btn` clicks. `base.html` uses `.spa-mobile-menu-btn`. They don't match — mobile sidebar can never be toggled.

**Fix:** Add a dedicated hamburger inside `project/_layout.html` that only appears at `<=768px`:
```html
<button class="mobile-menu-btn d-md-none btn btn-sm btn-outline-secondary" aria-label="Toggle project menu">
    <i class="bi bi-list"></i>
</button>
```

### 4.2 Fix SPA Collapse Button on Touch Devices

**Problem:** `.spa-sidebar-collapse-btn` has `opacity: 0`, only shows on `:hover`. Touch devices can't hover.

**Fix in `jenni-theme.css`:**
```css
@media (hover: none) {
    .spa-sidebar-collapse-btn { opacity: 0.7; }
}
```

### 4.3 Scope `overflow: hidden` to SPA Pages Only

**Problem:** `jenni-theme.css` sets `body { overflow: hidden }`, breaking scrolling on login/setup pages.

**Fix:** Change from `body` to `.spa-layout`:
```css
/* Before */
body { overflow: hidden; }

/* After */
.spa-layout { overflow: hidden; }
```

---

## Phase 5: Template Reorganization

### 5.1 Move Project-Scoped Templates into `templates/project/`

| Current Location | Target Location |
|-----------------|----------------|
| `templates/data.html` | `templates/project/data.html` |
| `templates/contradictions.html` | `templates/project/contradictions.html` |
| `templates/document_map.html` | `templates/project/document_map.html` |
| `templates/extraction.html` | `templates/project/extraction.html` |
| `templates/flashcards.html` | `templates/project/flashcards.html` |
| `templates/matrix.html` | `templates/project/matrix.html` |
| `templates/quizzes.html` | `templates/project/quizzes.html` |
| `templates/retention.html` | `templates/project/retention.html` |
| `templates/scheduled_reports.html` | `templates/project/scheduled_reports.html` |
| `templates/stats.html` | `templates/project/stats.html` |
| `templates/take_quiz.html` | `templates/project/take_quiz.html` |

**Impact:** Must update all `render_template()` calls in `app/routes/dashboard.py` to use `project/` prefix.

### 5.2 Add Missing SPA Routes to `workspace.js`

**Missing from ROUTES map (currently causes full-page reload fallback):**
- `project-contradictions`
- `project-matrix`
- `project-document-map`
- `project-flashcards` / `project-quizzes`
- `project-stats`
- `project-scheduled-reports`
- `project-retention`

---

## Phase 6: Minor Fixes

### 6.1 Display Saved Charts in `data.html`

Route passes `charts=charts` but template never uses it. Add a "Saved Charts" section or remove the unused variable.

### 6.2 Define `beepUI.showToast()` or Replace

`data.html` calls `beepUI.showToast()` which may not be globally defined. Verify or replace with Bootstrap toast API.

### 6.3 Fix Cache-Buster Strategy

**Problem:** `{{ range(1, 100000) | random }}` generates random cache-buster per request, defeating browser caching.

**Fix in `base.html`:**
```html
<!-- Before -->
<script src="{{ url_for('static', filename='js/chat-panel.js', v=range(1, 100000) | random) }}"></script>

<!-- After -->
<script src="{{ url_for('static', filename='js/chat-panel.js') }}?v={{ config.APP_VERSION or '1.0' }}"></script>
```

### 6.4 Lazy-Load Chart.js

Move Chart.js v4.4.0 (~200KB) from global `<head>` to `{% block page_js %}` in only the templates that need it (`data.html`, `stats.html`), or add `defer` attribute at minimum.

### 6.5 Add `aria-live` Regions

Dynamic content areas (`#spa-content-inner`, `#chat-messages`, `#dataStatus`) should have `aria-live="polite"` to announce content changes to screen readers.

---

## Implementation Schedule

| Order | Phase | Task | Effort | Impact |
|-------|-------|------|--------|--------|
| 1 | 1.1 | Fix data.html template inheritance | 30 min | **Fixes sidebar immediately** |
| 2 | 1.2 | Pass `active_page` from all routes | 30 min | **Fixes sidebar highlighting** |
| 3 | 1.3 | Fix data_page() route context | 15 min | Sidebar badges work |
| 4 | 1.4 | Add missing packages to requirements.txt | 5 min | Prevents crashes |
| 5 | 4.1 | Fix mobile sidebar toggle | 30 min | Mobile usability |
| 6 | 3.1–3.5 | Accessibility fixes | 2 hr | WCAG compliance |
| 7 | 2.1–2.2 | Theme alignment + Arabic fonts | 2 hr | Visual consistency |
| 8 | 2.4 | CSS consolidation | 1 hr | Cleaner styles |
| 9 | 6.4 | Lazy-load Chart.js | 15 min | Performance |
| 10 | 5.1 | Reorganize templates | 1 hr | Maintainability |
| 11 | 5.2 | Add SPA routes | 30 min | SPA completeness |
| 12 | 6.1–6.5 | Minor fixes | 1 hr | Polish |

**Total estimated effort:** ~10 hours

---

## Verification Checklist

- [ ] Data & Charts page shows project sidebar with "Data" highlighted as active
- [ ] ALL project pages show sidebar with correct active item and badge counts
- [ ] App starts without `psutil` `ImportError`
- [ ] `alembic upgrade head` runs successfully
- [ ] Theme colors match AI Server (Indigo `#6366f1` primary, gradient `#6366f1 → #a855f7 → #d946ef`)
- [ ] Fonts render Arabic text correctly (test with `ar.json` locale)
- [ ] RTL layout works when locale is Arabic (`dir="rtl"`)
- [ ] Mobile: hamburger toggles project sidebar correctly
- [ ] Lighthouse accessibility score ≥ 90
- [ ] No console errors on Data & Charts page
- [ ] Chart.js only loaded on pages that use it (or loaded with `defer`)
- [ ] All 11 templates moved to `templates/project/`
- [ ] All `render_template()` calls updated with new paths

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dual sidebar (SPA + project) | **Keep both** | SPA sidebar handles top-level nav, project sidebar handles project-level nav. Fix mobile conflicts only. |
| Design tokens source | **AI Server** | Align with AI Server's Indigo-Purple gradient. Update MASTER.md and CSS. |
| Arabic font | **Noto Sans Arabic** | Best Google Fonts option — multiple weights, professional quality. |
| RTL support | **Add `dir="rtl"`** | Required for proper Arabic layout. Set dynamically via `g.locale`. |
| Template move | **Move all 11** | Cleaner organization — all project-scoped pages under `templates/project/`. |
| Chart.js loading | **Lazy per page** | 200KB library shouldn't load on every page. Move to `page_js` block. |

---

---

## Extraction Page — Non-Technical User Experience Enhancement

> **Target:** `/researcher/projects/{id}/extraction`  
> **Goal:** Enable researchers, students, and non-technical users to extract structured data from documents **without writing a single line of JSON or code**  
> **Effort:** ~6 hours  
> **Files:** `templates/project/extraction.html`, `static/js/extraction.js`

---

### Problem Analysis

The current extraction page has **7 critical UX barriers** for non-technical users:

| # | Problem | Impact |
|---|---------|--------|
| 1 | **JSON textarea for fields** — requires knowing `[{"field":"...","type":"..."}]` syntax | Blocks 100% of non-tech users from creating a schema |
| 2 | **"Schema" terminology** — abstract technical jargon | Users don't know what a "schema" is or why they need one |
| 3 | **"Fields (JSON)" label** — implies developer knowledge | Creates fear/confusion immediately |
| 4 | **No starter templates** — blank slate with no guidance | Users don't know what to extract |
| 5 | **Results show "Doc ID"** — meaningless number | Can't tell which document a result row belongs to |
| 6 | **No contextual help** — no explanation of what the page does | First-time users are completely lost |
| 7 | **No onboarding empty state** — just a blank list with "No schemas yet" | No call to action, no next-step guidance |

---

### Enhancement Plan

#### Change 1 — Rename "Schema" → "Extraction Template" across all UI

Non-technical users understand "template" intuitively. The word "schema" is developer vocabulary.

**Changes:**
- Card header `New Schema` → `New Extraction Template`
- Card header `Schemas` → `My Templates`
- Button `Create Schema` → `+ Create Template`
- Run panel `Run Extraction: [name]` → `Extract Data Using: [name]`
- Schema list item icon: `bi-diagram-3` → `bi-layout-text-window-reverse` (suggests a form/structure)
- `schemaName` placeholder: `e.g. Study Data Extraction` → `e.g. Clinical Trial Summary`

**i18n keys to add (all 4 locales):**
- `extraction.template_name_label` → "Template Name"
- `extraction.templates_list_header` → "My Templates"
- `extraction.new_template_header` → "New Extraction Template"
- `extraction.create_btn` → "Create Template"
- `extraction.run_header` → "Extract Data Using:"
- `extraction.no_templates` → "No templates yet — create your first one above."

---

#### Change 2 — Replace JSON textarea with a Visual Field Builder

Instead of a textarea requiring JSON, show a simple **field-by-field builder**: user types a field name, picks a type from a dropdown, clicks "Add Field". Fields appear as removable badges/chips.

**New UI (replaces the `Fields (JSON)` block):**

```
┌─────────────────────────────────────────────────────────┐
│  Fields to Extract                                      │
│  ┌─────────────────────────┐ ┌──────────┐ ┌─────────┐  │
│  │  Field name…            │ │  Text  ▾ │ │ + Add   │  │
│  └─────────────────────────┘ └──────────┘ └─────────┘  │
│                                                         │
│  [Author ×]  [Year ×]  [Sample Size ×]                 │
│                                                         │
│  Type options: Text / Number / Date / Yes/No / List    │
└─────────────────────────────────────────────────────────┘
```

**How it works:**
- Each added field is stored in a JS array `[{field, type}, ...]`
- On "Create Template", the array is `JSON.stringify()`-ed before sending to the API — user never sees JSON
- If an existing schema is loaded with a `schema_json`, it is **parsed** and displayed as chips (not raw JSON)
- Chips show `[FieldName ×]` — click `×` to remove
- Field name input gets focus after each "Add Field"

**Type dropdown options (user-friendly labels → API values):**
| Display label | API value |
|---|---|
| Text | `string` |
| Number | `number` |
| Date | `date` |
| Yes / No | `boolean` |
| List of values | `array` |

**i18n keys to add:**
- `extraction.fields_label` → "Fields to Extract"
- `extraction.field_name_placeholder` → "Field name (e.g. Author)"
- `extraction.add_field_btn` → "Add"
- `extraction.type.text` → "Text"
- `extraction.type.number` → "Number"
- `extraction.type.date` → "Date"
- `extraction.type.boolean` → "Yes / No"
- `extraction.type.array` → "List"
- `extraction.no_fields_hint` → "Add at least one field to extract."

---

#### Change 3 — Preset Template Library (Quick-Start Panel)

Show a collapsible "Quick-Start Templates" section above the create form. Clicking a preset **pre-fills** the template name and adds its fields as chips immediately — user just clicks "Create Template".

**Presets (4 templates, always visible, chosen for research context):**

| Preset Name | Fields |
|---|---|
| 📄 **Basic Citation** | Author (Text), Year (Number), Title (Text), Journal (Text) |
| 🔬 **Clinical Study** | Study Design (Text), Sample Size (Number), Outcome (Text), Conclusion (Text) |
| 📊 **Survey Result** | Question (Text), Response (Text), Percentage (Number) |
| 🗒️ **Key Finding** | Finding (Text), Evidence (Text), Source (Text), Confidence (Yes/No) |

**UI:**
```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ Quick-Start Templates                          [hide ▲] │
│  ┌──────────────┐ ┌──────────────┐ ┌─────────────┐         │
│  │ 📄 Basic     │ │ 🔬 Clinical  │ │ 📊 Survey   │  ...    │
│  │ Citation     │ │ Study        │ │ Result      │         │
│  └──────────────┘ └──────────────┘ └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

Clicking a preset card fills the form instantly. The user can modify fields before saving.

**i18n keys to add:**
- `extraction.quickstart_header` → "Quick-Start Templates"
- `extraction.quickstart_hint` → "Click a template to pre-fill the form, then customize."
- `extraction.preset.citation` → "Basic Citation"
- `extraction.preset.clinical` → "Clinical Study"
- `extraction.preset.survey` → "Survey Result"
- `extraction.preset.finding` → "Key Finding"

---

#### Change 4 — Improved Empty & Onboarding States

**Template list empty state** (replaces "No schemas yet."):
```
┌─────────────────────────────────────────────────────────────┐
│              📋  No templates yet                           │
│   Create your first template above to start extracting     │
│   structured data from your documents.                     │
│                                                             │
│   ↑  Use a Quick-Start Template to get started fast.       │
└─────────────────────────────────────────────────────────────┘
```

**Results empty state** (before a template is selected, replaces the arrow placeholder):
```
┌─────────────────────────────────────────────────────────────┐
│           How extraction works                              │
│                                                             │
│  1️⃣  Create a template — define what to extract            │
│  2️⃣  Select a template from the list on the left           │
│  3️⃣  Choose which documents to read                        │
│  4️⃣  Click "Extract" — AI reads and fills in the fields    │
│  5️⃣  Download results as a spreadsheet (CSV/Excel)         │
└─────────────────────────────────────────────────────────────┘
```

**i18n keys to add:**
- `extraction.empty_templates_title` → "No templates yet"
- `extraction.empty_templates_body` → "Create your first template above to start extracting structured data from your documents."
- `extraction.empty_results_title` → "How extraction works"
- `extraction.how_step1` → "Create a template — define what to extract"
- `extraction.how_step2` → "Select a template from the list on the left"
- `extraction.how_step3` → "Choose which documents to read"
- `extraction.how_step4` → "Click Extract — AI reads and fills in the fields"
- `extraction.how_step5` → "Download results as a spreadsheet"

---

#### Change 5 — Results Table: Show Document Name Instead of Doc ID

The current table header is `Doc ID` showing a meaningless number like `42`. Non-tech users need to see the document's actual title.

**Changes in `extraction.js` → `renderResults()`:**
- Change column header `Doc ID` → `Document`
- Resolve document ID to a name by either:
  - Passing a `docNames` map from the backend in the `/extractions` API response, **or**
  - Storing document names locally from the `DocumentSelector` component when it loads
- Display truncated document title (max 40 chars) with a tooltip showing full name
- Results table → add `table-striped` for readability

**i18n key to add:**
- `extraction.col.document` → "Document"
- `extraction.col.no_doc` → "Unknown document"

---

#### Change 6 — Inline Contextual Help (Tooltips & Helper Text)

Add small helper text and icons at key moments of friction:

| Location | Help text |
|---|---|
| Template Name field | Small grey text below: *Give your template a clear name — e.g., "Drug Trial Outcomes"* |
| Fields section | Small grey text below chips: *These are the pieces of information AI will look for in each document.* |
| Document selector | Label above: **Which documents should AI read?** (replaces the technical "From Documents") |
| Extract button | Tooltip on hover: *AI will read each selected document and fill in your template fields automatically.* |
| Export CSV button | Tooltip: *Download results as a spreadsheet you can open in Excel or Google Sheets* |

**i18n keys to add:**
- `extraction.template_name_hint` → "Give it a clear name e.g. "Drug Trial Outcomes""
- `extraction.fields_hint` → "These are the pieces of information AI will look for in each document."
- `extraction.docs_label` → "Which documents should AI read?"
- `extraction.export_tooltip` → "Download as a spreadsheet (Excel / Google Sheets compatible)"

---

#### Change 7 — Better Progress Feedback During Extraction

Replace the thin 4px animated progress bar with a more informative status message:

```
┌────────────────────────────────────────────────────────┐
│  🤖  AI is reading your documents…                    │
│  This may take 10–30 seconds depending on length.    │
│  ████████████░░░░░░░░  Processing…                   │
└────────────────────────────────────────────────────────┘
```

**Changes:**
- Progress bar height: `4px` → `8px`
- Add an icon and descriptive message above the bar
- Add estimated-time note: *"This may take 10–30 seconds"*
- After completion: show a brief success banner *"✓ Extraction complete — X rows extracted"* (auto-dismisses after 4 seconds)

**i18n keys to add:**
- `extraction.progress_title` → "AI is reading your documents…"
- `extraction.progress_hint` → "This may take 10–30 seconds depending on document length."
- `extraction.complete_msg` → "Extraction complete"

---

#### Change 8 — "What is this page?" Education Panel + Feature Connection Map

Users not only need to know how to use the form — they need to understand **why they are here** and **how this fits into their research workflow**. Without that mental model, even a simple form feels confusing.

##### 8a — Page-Level "What is Extraction?" Banner

A collapsible info banner at the top of the page (open by default for first-time users, dismissed with a ✕ and persisted in `localStorage`). It answers the three questions every new user has:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  📋  What is Data Extraction?                                    [✕ hide] │
│                                                                          │
│  Extraction lets you pull specific information from your documents        │
│  and organise it into a table — automatically, using AI.                 │
│                                                                          │
│  For example: if you have 50 research papers uploaded to this project,   │
│  you can create a template with fields like "Author", "Year",            │
│  "Sample Size", and "Conclusion" — and AI will read every document       │
│  and fill in the table for you.                                          │
│                                                                          │
│  ✅ You define WHAT to extract (the fields)                              │
│  📄 AI reads your DOCUMENTS (from the Documents page)                    │
│  📊 Results appear as a TABLE you can download or use in Analysis        │
└──────────────────────────────────────────────────────────────────────────┘
```

**Behaviour:**
- Rendered as a `<div class="alert alert-info">` with a dismiss button
- On dismiss, `localStorage.setItem('extraction_intro_dismissed', '1')` is set
- On page load, if `localStorage.getItem('extraction_intro_dismissed')` is set, the banner is hidden by default but a small "ℹ️ What is this page?" link remains visible to re-open it

**i18n keys to add:**
- `extraction.intro.title` → "What is Data Extraction?"
- `extraction.intro.body` → "Extraction lets you pull specific information from your documents and organise it into a table — automatically, using AI."
- `extraction.intro.example` → "For example: if you have 50 research papers, create a template with fields like "Author", "Year", "Conclusion" — AI reads every document and fills in the table for you."
- `extraction.intro.bullet1` → "You define WHAT to extract (the fields)"
- `extraction.intro.bullet2` → "AI reads your Documents"
- `extraction.intro.bullet3` → "Results appear as a table you can download"
- `extraction.intro.reopen` → "What is this page?"

---

##### 8b — Document Connection Callout (in the Run Panel)

When a user selects a template and the Run panel appears, show a clear callout explaining the link between the template and their documents — before they click Extract:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Extract Data Using: Clinical Study Template                             │
│                                                                          │
│  ℹ️  AI will read the documents you select below and look for:           │
│     Study Design · Sample Size · Outcome · Conclusion                    │
│     in each one. Results are added to the table on the right.           │
│                                                                          │
│  Which documents should AI read?                                         │
│  ☐ Smith et al. 2024          ☐ Jones & Brown 2023                      │
│  ☐ WHO Report 2022            ☑ All documents (12)                      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- A sentence dynamically listing the **field names** from the active template: *"AI will look for: Author, Year, Sample Size in each document."*
- This is generated in JS from the active schema's fields — reading `schema_json` and listing field names in plain language
- The sentence confirms the connection: *"Results are added to the table on the right."*

**i18n keys to add:**
- `extraction.run.ai_will_look_for` → "AI will read the selected documents and look for:"
- `extraction.run.results_added` → "Results are added to the table on the right."

---

##### 8c — Results-to-Features Connection Footer

Beneath the results table (visible once results exist), add a small "What can you do with these results?" row of action tiles connecting extraction to the rest of the app:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ✅ 8 rows extracted.  What can you do next?                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │ ⬇️ Download       │  │ 📊 Analyse in    │  │ 🏷️ Apply Codes   │       │
│  │ as Spreadsheet   │  │ Statistics page  │  │ to Documents     │       │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘       │
└──────────────────────────────────────────────────────────────────────────┘
```

**Each tile:**
- **Download as Spreadsheet** → triggers the existing CSV export
- **Analyse in Statistics** → links to `url_for('researcher.stats_page', project_id=...)` in a plain `<a>` tag
- **Apply Codes to Documents** → links to `url_for('researcher.codes_page', project_id=...)` with a note: *"Use coding to categorise the documents you just analysed"*

This closes the loop: the user now sees that extraction is not a dead end — its results feed directly into the next steps of their research workflow.

**i18n keys to add:**
- `extraction.next.title` → "What can you do next?"
- `extraction.next.download` → "Download as Spreadsheet"
- `extraction.next.stats` → "Analyse in Statistics"
- `extraction.next.codes` → "Apply Codes to Documents"
- `extraction.next.codes_hint` → "Use coding to categorise the documents you just analysed"
- `extraction.results_count` → "{n} rows extracted."

---

##### 8d — Template-to-Document Relationship Explained in Template List

Each template card in the "My Templates" list gains a subtitle line showing its **extraction count** and the **date last run**, giving users a sense of history and connection:

```
Before (current):
  [📋 icon]  Clinical Study Template          #3

After:
  [📋 icon]  Clinical Study Template
              Last run: 14 Feb 2026 · 8 results from 5 documents
```

If never run: *"Not yet used — select to run your first extraction"*

This teaches users that **one template can be run against many documents** — a core concept they wouldn't otherwise discover.

**i18n keys to add:**
- `extraction.template.last_run` → "Last run:"
- `extraction.template.results_from` → "{n} results from {d} documents"
- `extraction.template.never_run` → "Not used yet — select to run"

---

#### Change 9 — Live Functional Links Between Extraction, Documents, and Other Features

Change 8 explains links in words. Change 9 **builds them into the UI** so users can navigate the connections directly — clicking takes them somewhere real.

---

##### 9a — Document Selector Shows Real Document Names with Status Badges

The current `DocumentSelector` component shows checkboxes but does not communicate whether a document has **already been extracted** with the current template. Replace generic document rows with rich rows:

```
☑  Smith et al. 2024.pdf          ✅ Extracted  [view →]
☐  Jones & Brown 2023.pdf         ⚪ Not yet extracted
☑  WHO Report 2022.pdf            ✅ Extracted  [view →]
☐  Draft_Analysis_v3.docx         ⚪ Not yet extracted
```

**Implementation:**
- When a template is selected, `loadResults()` already fetches results for that `schema_id`
- Collect the set of `document_id` values from those results → `extractedDocIds`
- Pass `extractedDocIds` into the document selector's render function  
- Each document row renders a green `✅ Extracted` badge if its ID is in the set, or `⚪ Not yet` otherwise
- The `[view →]` link opens the document viewer: `url_for('researcher.document_viewer', project_id=..., doc_id=...)` — rendered as `data-doc-url` attributes so JS can build the URL client-side
- Clicking `[view →]` opens the document viewer in a new tab so the user doesn't lose their extraction context

**Why this matters:** Users can instantly see *"This template has already read these 3 documents but not these 2 — I need to run it on the new ones."*

**i18n keys:**
- `extraction.doc.extracted` → "Already extracted"
- `extraction.doc.not_extracted` → "Not yet extracted"
- `extraction.doc.view` → "View document"

---

##### 9b — Result Rows Link Directly to the Source Document

Every row in the results table currently shows a document name (after Change 5). Make each document name a **clickable link** opening the document viewer:

```
Before:
┌──────────────────┬──────────┬────────────────────────────┐
│  Document        │  Year    │  Conclusion                │
├──────────────────┼──────────┼────────────────────────────┤
│  Smith et al.    │  2024    │  No significant effect...  │
└──────────────────┴──────────┴────────────────────────────┘

After:
┌──────────────────────┬──────────┬────────────────────────────┐
│  Document            │  Year    │  Conclusion                │
├──────────────────────┼──────────┼────────────────────────────┤
│  🔗 Smith et al.     │  2024    │  No significant effect...  │
│     [open doc ↗]     │          │                            │
└──────────────────────┴──────────┴────────────────────────────┘
```

**Implementation:**
- In `renderResults()`, wrap the document name cell in `<a href="..." target="_blank" class="doc-link">` using the document viewer URL
- The document viewer URL is built from `document_id`: `/researcher/projects/{projectId}/documents/{docId}/view`
- Add a small `↗` icon (Bootstrap `bi-box-arrow-up-right`) after the name
- If the document viewer route doesn't support direct URL navigation yet, fall back to `/researcher/projects/{projectId}/documents` with `?highlight={docId}` as a query param

**Why this matters:** User sees a result row and thinks *"Wait, what was the full conclusion?"* — one click takes them straight to the original document without having to navigate away, find Documents, search, and re-find the paper.

**i18n keys:**
- `extraction.col.open_doc` → "Open source document"

---

##### 9c — "Extracted" Status Badge on the Documents Page

Add a **cross-page status indicator**: on the Documents page, each document row that has been processed by at least one extraction template shows a small `Extracted` badge.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Documents                                                               │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  📄 Smith et al. 2024.pdf      [Extracted ✓]  [Coded 3]  [View]  │  │
│  │  📄 Jones & Brown 2023.pdf     [View]                            │  │
│  │  📄 WHO Report 2022.pdf        [Extracted ✓]  [View]             │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Implementation:**
- The Documents page route (`app/routes/documents.py`) already fetches all documents for a project  
- Add a query to the extraction results table: `SELECT DISTINCT document_id FROM extraction_results WHERE project_id = ?`
- Pass the resulting set as `extracted_doc_ids` to `documents.html`
- In `documents.html`, render a green `Extracted` badge for each document whose ID is in `extracted_doc_ids`
- Make the badge a **link** to the extraction page: `href="{{ url_for('researcher.extraction_page', project_id=project.id) }}"` — clicking "Extracted" takes the user directly to the extraction results filtered to that document

**Why this matters:** A user browsing their Documents page can see exactly which papers have already been data-extracted and which haven't — without ever visiting the extraction page. The connections are visible passively.

**Backend changes:** `app/routes/documents.py` — add one SQL query to `documents_page()` route; `templates/project/documents.html` — add badge rendering.

**i18n keys (add to locale files + `documents.html`):**
- `extraction.badge.extracted` → "Extracted"
- `extraction.badge.extracted_tooltip` → "This document has been processed by an extraction template. Click to view results."

---

##### 9d — Template Card Shows Extracted Documents as Clickable Links

In the "My Templates" list (left panel), each template card expands on hover/click to show the **actual document names** that have been extracted with it — as links:

```
Before (current):
  [📋]  Clinical Study Template          #3

After (Change 8d):
  [📋]  Clinical Study Template
        Last run: 14 Feb 2026 · 8 results from 5 documents

After (Change 9d — adds actual links):
  [📋]  Clinical Study Template                        [▼ expand]
        Last run: 14 Feb 2026

        Documents extracted with this template:
        • 🔗 Smith et al. 2024          ✅  4 fields
        • 🔗 Jones & Brown 2023         ✅  3 fields
        • 🔗 WHO Report 2022            ✅  4 fields
        [+ Run on more documents →]
```

**Implementation:**
- When `renderSchemas()` runs, also store the results data in a JS map: `schemaResultsMap[schemaId] = [{docId, docName, fieldCount}, ...]`
- This data is already fetched by `loadResults()` — extend it to populate the map for all schemas (or lazily on expand)
- Each document link in the expand panel points to the document viewer
- The `[+ Run on more documents →]` button selects the template and scrolls to the run panel — no navigation away

**Why this matters:** The template list becomes a **live view of what has been done** — users can see the direct template→document relationship as concrete named links, not abstract counts.

---

##### 9e — "Go to Extraction" Shortcut from the Documents Page

On each document's row on the Documents page, add an **"Extract Data" action button** (alongside the existing View/Delete actions). Clicking it navigates directly to the Extraction page **with that document pre-selected** in the document selector:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  📄 Jones & Brown 2023.pdf           [View]  [Extract Data ↗]  [Delete] │
└──────────────────────────────────────────────────────────────────────────┘
```

**Implementation:**
- Link: `href="{{ url_for('researcher.extraction_page', project_id=project.id) }}?preselect_doc={{ doc.id }}"`
- On the Extraction page, JS reads `?preselect_doc=42` from the URL on load
- In `DocumentSelector.load()`, after documents render, check `URLSearchParams` for `preselect_doc` and tick that document's checkbox automatically
- If no templates exist yet, the empty state message changes to: *"Create a template first to extract data from this document."*

**Why this matters:** A user can be browsing a document and think *"I want to extract data from this"* — one click takes them to extraction with the right document already checked. This is the **reverse flow** of the normal path (template → document) and makes the connection bidirectional.

**Backend changes:** None — pure template change to `documents.html` + URL param handling in `extraction.js`.

**i18n keys (add to `documents.html` locale keys):**
- `documents.action.extract` → "Extract Data"

---

### Summary of All Changes

| # | Change | Effort | User Impact |
|---|--------|--------|-------------|
| 1 | Rename Schema → Extraction Template | 30 min | Removes jargon barrier |
| 2 | Visual field builder (no JSON) | 2 hrs | Unblocks 100% of non-tech users |
| 3 | Preset template library | 1 hr | Users can start in one click |
| 4 | Better empty & onboarding states | 30 min | New users know exactly what to do |
| 5 | Document name in results (not Doc ID) | 30 min | Results are readable and meaningful |
| 6 | Inline contextual help | 30 min | Reduces confusion at every step |
| 7 | Richer extraction progress | 30 min | Reduces anxiety during wait |
| 8a | "What is Extraction?" dismissible intro banner | 30 min | Users understand WHY the page exists |
| 8b | "AI will look for X, Y, Z" callout in run panel | 30 min | Makes template→document connection explicit in words |
| 8c | "What next?" tiles linking to Stats, Codes, Export | 45 min | Shows extraction feeds into the rest of the app |
| 8d | Template list shows run history & doc count | 30 min | Teaches one-template-many-documents concept |
| **9a** | **Doc selector shows Extracted/Not-yet badges + View links** | **45 min** | **Users see exactly which docs are linked to this template** |
| **9b** | **Result rows link directly to source document** | **30 min** | **One click from result → original document** |
| **9c** | **"Extracted" badge on Documents page linking back to results** | **1 hr** | **Bidirectional: documents know they've been extracted** |
| **9d** | **Template card expands to show extracted doc names as links** | **1 hr** | **Template→document relationship is visible as named links** |
| **9e** | **"Extract Data" button on each document row** | **30 min** | **Reverse flow: document → extraction page with doc pre-selected** |

**Total estimated effort: ~11 hours**  
**Files changed: `extraction.html`, `extraction.js`, `documents.html`, `app/routes/documents.py`, all 4 locale files**

---

### Verification Checklist — Extraction Page

- [ ] No JSON visible anywhere on the page for a new user
- [ ] Preset templates pre-fill form correctly
- [ ] Field chips appear after "Add Field", chips are removable
- [ ] "Create Template" disabled until name + at least 1 field exists
- [ ] Existing templates from API render as chips when selected
- [ ] Results table shows document name (not numeric ID)
- [ ] Progress block shows descriptive message during extraction
- [ ] Success toast shows row count after extraction
- [ ] Export CSV/Excel works and file opens correctly in Excel
- [ ] All strings use `t()` — page fully translates to AR/FR/ES
- [ ] Empty states show guidance for both templates list and results panel
- [ ] Intro banner appears on first visit, is dismissible, stays dismissed on reload
- [ ] "ℹ️ What is this page?" link re-opens the intro banner after dismissal
- [ ] Run panel callout lists field names dynamically from the active template
- [ ] "What can you do next?" tiles appear after first extraction result
- [ ] Stats and Codes links navigate to the correct project-scoped pages
- [ ] Template list items show last-run date and result/document counts
- [ ] Templates never run show "Not used yet" message
- [ ] Document selector rows show ✅ Extracted / ⚪ Not yet badges per template
- [ ] `[view →]` link in document selector opens the document viewer in a new tab
- [ ] Result row document names are clickable links to the document viewer
- [ ] Documents page shows "Extracted ✓" badge on documents processed by any template
- [ ] "Extracted" badge on Documents page links back to the Extraction results page
- [ ] Template card expand panel shows extracted document names as links
- [ ] Documents page has "Extract Data ↗" button on each document row
- [ ] Navigating to extraction with `?preselect_doc=42` auto-ticks that document in the selector

# Phase 7 + Admin Configuration Execution Plan

Status date: February 9, 2026
Scope: Beep.AI.Researcher template/UI alignment with `docs/TODO.md`, admin/user configuration completeness, theme/localization consistency.

## Goals

1. Complete missing TODO items for UI/UX modernization and admin/user configuration.
2. Preserve existing design language in `templates/base.html` and theme tokens in `static/css/design-system.css`, `static/css/dashboard-theme.css`, `static/css/jenni-theme.css`.
3. Remove configuration drift by unifying config reads/writes.
4. Ship with measurable acceptance criteria and regression tests.

## Current Gap Summary

1. UI exists but Phase 7 checklist in `docs/TODO.md` is largely open (dashboard/document/code/search/chat/extraction UX).
2. Admin governance page renders but still relies on placeholder data in `app/routes/admin_routes.py`.
3. Configuration is split between:
   - `app/config_manager.py`
   - `app/config/manager.py`
4. Localization and theme token usage are not yet enforced across all templates/components.

## Execution Order

## Sprint 1 (Foundation and Unification)

Objective: make core infrastructure safe for UI expansion.

Work items:
1. Config source-of-truth decision and migration
   - Keep `app/config/manager.py` as canonical runtime manager.
   - Make `app/config_manager.py` a compatibility wrapper (read/write pass-through) or remove usages.
   - Update `app/routes/admin_routes.py` to use one manager only.
2. Admin settings schema normalization
   - Build typed schema sections for:
     - Beep server integration
     - Mail
     - App/runtime
     - Limits
     - Feature flags
   - Render settings form from schema to avoid hardcoded duplication.
3. Governance backend minimum viability
   - Add concrete models for audit and export history if missing.
   - Wire real queries in `/admin/governance`.

Acceptance criteria:
1. No duplicate config writes across two managers.
2. Admin settings save/load path uses one config backend only.
3. Governance page shows real records in non-empty environments.

Tests:
1. `tests/test_configuration.py` updated for unified manager behavior.
2. Add admin settings route tests (save/load and validation failure).
3. Add governance route tests with seeded data.

## Sprint 2 (Component Library and Theme Enforcement)

Objective: establish reusable UI building blocks aligned with current theme.

Work items:
1. Create shared template components in `templates/components/`
   - `card.html`, `table.html`, `form_field.html`, `status_badge.html`, `toolbar.html`
2. Introduce UI token checklist for all pages
   - Typography classes
   - Color tokens
   - Spacing/radius/shadow
3. Refactor admin pages to use shared components
   - `templates/admin/index.html`
   - `templates/admin/users.html`
   - `templates/admin/settings.html`
   - `templates/admin/governance.html`
   - `templates/admin/localization.html`

Acceptance criteria:
1. Admin pages no longer rely on one-off inline styling patterns.
2. Token usage is consistent with base theme files.
3. All updated pages remain responsive on mobile/tablet/desktop.

Tests:
1. Template smoke tests for page render status.
2. Visual regression snapshots (if available in pipeline).

## Sprint 3 (Phase 7.2 + 7.3: Dashboard and Document UX)

Objective: close the top-impact user-facing TODO items first.

Work items:
1. Dashboard modernization
   - project summary cards
   - quick stats section
   - activity feed block
2. Document upload/management UX
   - bulk upload entry
   - richer filters/sorting controls
   - extraction progress visuals

Acceptance criteria:
1. Dashboard has card-based overview + activity feed.
2. Document list has sorting + filtering + status cues.
3. No regressions in existing project/document routes.

Tests:
1. Dashboard route/template tests.
2. Document route functional tests for filter/sort params.

## Sprint 4 (Phase 7.4 + 7.5: Codes and Search/RAG UX)

Objective: improve analysis workflows.

Work items:
1. Code management interface improvements
   - hierarchy browser support
   - quick actions (edit/delete/merge)
2. Search interface improvements
   - unified search/filter bar
   - improved result card metadata and actions

Acceptance criteria:
1. Code page supports hierarchy navigation and quick actions.
2. Search page supports richer filtering and clearer result metadata.

Tests:
1. Code route and UI behavior tests.
2. Search query/path tests with filter combinations.

## Sprint 5 (Phase 7.6 + 7.7 + 7.8)

Objective: finish chat/extraction flows and accessibility baseline.

Work items:
1. Chat UX upgrades
   - conversation history panel
   - richer citation rendering in messages
2. Extraction UX upgrades
   - schema picker/preview
   - inline edit and validation feedback
3. Accessibility pass
   - keyboard navigation
   - focus visibility
   - ARIA labels
   - contrast checks

Acceptance criteria:
1. Chat and extraction workflows are complete and consistent with theme.
2. WCAG AA checklist items in TODO are implemented for key pages.

Tests:
1. Keyboard navigation tests for critical templates.
2. Route + UI tests for extraction editing flow.

## Sprint 6 (Hardening and Completion)

Objective: close quality gates and update TODO statuses accurately.

Work items:
1. Localization completion pass for hardcoded strings.
2. Performance pass on key pages (<3s load target for heavy pages where feasible).
3. Update `docs/TODO.md` checkboxes with objective evidence.
4. Add/refresh docs:
   - component usage guide
   - admin configuration guide

Acceptance criteria:
1. TODO reflects real completion state.
2. Full test suite passes.
3. No unresolved blocker items for Phase 7 core sections.

## Implementation Matrix

1. Configuration and Admin Services
   - `app/config/manager.py`
   - `app/config/defaults.py`
   - `app/config_manager.py`
   - `app/routes/admin_routes.py`
2. Admin API Modules
   - `app/routes/admin/monitoring.py`
   - `app/routes/admin/plugin_management.py`
   - `app/routes/admin/permission_management.py`
   - `app/routes/admin/roles.py`
   - `app/routes/admin/user_roles.py`
3. Templates
   - `templates/base.html`
   - `templates/admin/*.html`
   - `templates/dashboard*.html`
   - `templates/project/*.html`
   - `templates/components/*.html` (new/expanded)
4. Styling and Frontend JS
   - `static/css/design-system.css`
   - `static/css/dashboard-theme.css`
   - `static/css/jenni-theme.css`
   - `static/js/workspace.js`
   - `static/js/dashboard_page.js`

## Delivery Rules

1. Keep color/theme tokens centralized; do not introduce ad-hoc color literals in templates.
2. Keep localization key-based text for new strings.
3. Add tests with each feature, not at the end.
4. Update TODO status only when:
   - code merged
   - tests added/passing
   - UI route reachable

## Immediate Next Step

Start Sprint 1 with config unification:
1. inventory all imports/usages of both config managers
2. choose canonical manager and implement compatibility layer
3. add tests for admin settings save/load against canonical manager

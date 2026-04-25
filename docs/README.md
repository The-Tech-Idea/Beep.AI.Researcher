# Beep.AI.Researcher

Internal research platform for documents and data. Confidential — all data stays on your infrastructure.

Follows [py-web skill](.cursor/skills/py-web): single CSS, theme switcher (light/dark/system), ConfigManager, lean code.

## Quick Start

```bash
# Windows
run.bat

# Linux/macOS
./run.sh
# or
python run_hostadmin.py

# Or directly (with venv/requirements installed)
python run.py
```

Runs on http://127.0.0.1:5005 by default. Use `run.bat 5006` or `run.sh 5006` to run on another port.

## Initialize Database

```bash
python init_database.py
```

## Features (Phase 1)

- **Projects** — Create, list, export (JSON, CSV, Excel)
- **Documents** — Upload .txt, .md, .html, .pdf, .docx; search; view
- **Document viewer** — Select text, apply codes (NVivo-style)
- **Code browser** — Tree of codes with references; jump to document
- **Chat** — Stub (requires Beep.AI.Server for LLM)
- **Data & charts** — Upload XLSX/CSV; Chart.js bar/line/pie
- **Stats** — Descriptive stats, cross-tabs
- **Extraction** — Schema CRUD, extract (stub)
- **Flashcards & Quiz** — Generate from docs
- **Document map** — Doc + code network
- **Related docs, writing assist** — Stub APIs
- **Export** — JSON, CSV, Excel
- **Governance & export bundles** — `/admin/governance` gives retention/audit visibility, `/projects/<id>/export?format=bundle` packages docs, references, charts, and audit logs for compliance handoff.

## Structure

- `app/` — Flask app, models, routes
- `run.py` — Entry point
- `run_hostadmin.py` — Venv + deps + run
- `run.bat` — Windows launcher
- `ARCHITECTURE.md` — System overview with ASCII diagrams of the document RAG search flow, chat session lifecycle, structured data upload pipeline, and deployment/integration stack (linking the sprint/backlog cards in `enhancement_sprint_tracking.md` and `enhancement_backlog_cards.md` for the same workstream). Refer to `enhancement_plan.md` for the UI/UX + feature roadmap and `enhancement_wireframes.md` for the refreshed hero/helper/flow sketches so teammates can spot the diagrams early in their sprint docs.

## Tests

```bash
pip install pytest
set DATABASE_URL=sqlite:///:memory:
pytest tests/ -v
```

See [Beep.AI.Researcher-Plan.md](../.github/Beep.AI.Researcher-Plan.md), [IMPLEMENTATION.md](IMPLEMENTATION.md), and [enhancement_sprint_tracking.md](enhancement_sprint_tracking.md) / [enhancement_backlog_cards.md](enhancement_backlog_cards.md) for the active planning/tracking artifacts.

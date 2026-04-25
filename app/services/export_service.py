"""Export service — manuscript Markdown + BibTeX bundle (Phase 05).

Builds export artifacts synchronously and stores the result on the
``ExportJob`` row.  For large projects this could be offloaded to a task
queue; the API stays unchanged because callers poll ``ExportJob.status``.
"""
from __future__ import annotations

import io
import json
import os
import pathlib
import tempfile
import zipfile
from typing import Optional

from app.database import db
from app.core.time_utils import utcnow_naive
from app.models.researcher.export_jobs import ExportJob


# ---------------------------------------------------------------------------
# Job lifecycle
# ---------------------------------------------------------------------------

def create_export_job(
    project,
    fmt: str,
    *,
    manuscript_id: Optional[int] = None,
) -> ExportJob:
    """Create an ``ExportJob`` row and immediately run the export synchronously."""
    if fmt not in ExportJob.FORMAT_VALUES:
        fmt = ExportJob.FORMAT_MARKDOWN_ZIP

    job = ExportJob(
        project_id=project.id,
        manuscript_id=manuscript_id,
        format=fmt,
        status=ExportJob.STATUS_RUNNING,
        created_at=utcnow_naive(),
    )
    db.session.add(job)
    db.session.commit()

    try:
        artifact_path = _run_export(project, job)
        job.artifact_path = artifact_path
        job.status = ExportJob.STATUS_DONE
    except Exception as exc:
        job.status = ExportJob.STATUS_FAILED
        job.error_message = str(exc)

    db.session.commit()
    return job


def get_export_job(job_id: int, project_id: int) -> Optional[ExportJob]:
    return ExportJob.query.filter_by(id=job_id, project_id=project_id).first()


def list_export_jobs(project_id: int) -> list[ExportJob]:
    return (
        ExportJob.query.filter_by(project_id=project_id)
        .order_by(ExportJob.created_at.desc())
        .limit(20)
        .all()
    )


# ---------------------------------------------------------------------------
# Export runners
# ---------------------------------------------------------------------------

def _run_export(project, job: ExportJob) -> str:
    """Dispatch to the correct runner; return absolute artifact path."""
    if job.format == ExportJob.FORMAT_BIBTEX:
        return _export_bibtex(project, job)
    return _export_markdown_zip(project, job)


def _export_bibtex(project, job: ExportJob) -> str:
    """Write all project references as a .bib file; return path."""
    from app.services.reference_bibliography_service import (
        _get_project_bibliography_references,
    )

    refs = _get_project_bibliography_references(project)
    content = "\n\n".join(r.to_bibtex() for r in refs) or "% No references yet."
    label = _safe_label(project.name)
    tmp_dir = _get_tmp_dir()
    path = tmp_dir / f"{label}_references.bib"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _export_markdown_zip(project, job: ExportJob) -> str:
    """Build a zip with manuscript.md + references.bib; return absolute path."""
    from app.services.manuscript_service import (
        export_manuscript_markdown,
        get_manuscript,
        list_manuscripts,
    )
    from app.services.reference_bibliography_service import (
        _get_project_bibliography_references,
    )

    # Resolve manuscript
    manuscript = None
    if job.manuscript_id:
        manuscript = get_manuscript(job.manuscript_id, project.id)
    if manuscript is None:
        # Fall back to most recent manuscript for the project
        all_ms = list_manuscripts(project.id)
        manuscript = all_ms[-1] if all_ms else None

    label = _safe_label(project.name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if manuscript:
            md_text = export_manuscript_markdown(manuscript)
            zf.writestr(f"{label}_manuscript.md", md_text.encode("utf-8"))
        else:
            zf.writestr(f"{label}_manuscript.md", b"# (no manuscript found)")

        # Bibliography
        refs = _get_project_bibliography_references(project)
        bib = "\n\n".join(r.to_bibtex() for r in refs) or "% No references yet."
        zf.writestr(f"{label}_references.bib", bib.encode("utf-8"))

        # Simple manifest
        manifest = json.dumps(
            {
                "project": project.name,
                "manuscript": manuscript.title if manuscript else None,
                "reference_count": len(refs),
            },
            ensure_ascii=False,
            indent=2,
        )
        zf.writestr("manifest.json", manifest.encode("utf-8"))

    tmp_dir = _get_tmp_dir()
    path = tmp_dir / f"{label}_export.zip"
    path.write_bytes(buf.getvalue())
    return str(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_label(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "-" for c in name)[:60]


def _get_tmp_dir() -> pathlib.Path:
    """Return (and create) a per-process temp directory for export artifacts."""
    tmp = pathlib.Path(tempfile.gettempdir()) / "beep_researcher_exports"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp

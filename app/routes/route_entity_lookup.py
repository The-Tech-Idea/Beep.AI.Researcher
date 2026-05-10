from flask import abort, request

from app.database import db


def get_entity(model, entity_id):
    if entity_id is None:
        return None
    return db.session.get(model, entity_id)


def get_entity_or_404(model, entity_id):
    entity = get_entity(model, entity_id)
    if entity is None:
        abort(404)
    return entity


def get_project_or_404(project_id):
    """Convenience: look up a ResearchProject by ID or 404."""
    from app.models.researcher import ResearchProject

    return get_entity_or_404(ResearchProject, project_id)


def _base_template():
    """Pick layout: partial fragment for SPA, embed for iframe, full otherwise."""
    if (
        (request.args.get("partial") or "").strip().lower()
        in (
            "1",
            "true",
        )
        or request.headers.get("X-Requested-With") == "SPA"
        or (request.args.get("embed") or "").strip().lower() in ("1", "true", "yes")
    ):
        return "base_embed.html"
    return "base.html"

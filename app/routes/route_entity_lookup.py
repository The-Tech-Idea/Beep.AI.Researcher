from flask import abort

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

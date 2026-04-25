"""
Webhook Routes — API endpoints for managing webhook subscriptions.

Endpoints:
  POST   /projects/<id>/webhooks          — Create subscription
  GET    /projects/<id>/webhooks          — List subscriptions
  DELETE /projects/<id>/webhooks/<wid>    — Remove subscription
  GET    /projects/<id>/webhooks/<wid>/deliveries — Delivery log
"""
from __future__ import annotations

import json
import secrets
from flask import Blueprint, request, jsonify
from app.database import db
from app.models.researcher.integrations import WebhookSubscription, WebhookDelivery

webhooks_bp = Blueprint('webhooks', __name__)


@webhooks_bp.route('/projects/<int:project_id>/webhooks', methods=['POST'])
def create_webhook(project_id: int):
    """Create a new webhook subscription."""
    data = request.get_json(silent=True) or {}

    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    events = data.get("events", ["*"])
    if isinstance(events, str):
        events = [events]

    # Generate a signing secret
    secret = data.get("secret") or secrets.token_hex(32)

    sub = WebhookSubscription(
        project_id=project_id,
        url=url,
        secret=secret,
        events=json.dumps(events),
        active=True,
    )
    db.session.add(sub)
    db.session.commit()

    result = sub.to_dict()
    result["secret"] = secret  # Only show secret on creation
    return jsonify(result), 201


@webhooks_bp.route('/projects/<int:project_id>/webhooks', methods=['GET'])
def list_webhooks(project_id: int):
    """List all webhook subscriptions for a project."""
    subs = WebhookSubscription.query.filter_by(project_id=project_id).all()
    return jsonify([s.to_dict() for s in subs])


@webhooks_bp.route('/projects/<int:project_id>/webhooks/<int:webhook_id>', methods=['DELETE'])
def delete_webhook(project_id: int, webhook_id: int):
    """Delete a webhook subscription."""
    sub = WebhookSubscription.query.filter_by(
        id=webhook_id, project_id=project_id
    ).first()
    if not sub:
        return jsonify({"error": "Webhook not found"}), 404

    db.session.delete(sub)
    db.session.commit()
    return jsonify({"deleted": True}), 200


@webhooks_bp.route('/projects/<int:project_id>/webhooks/<int:webhook_id>/deliveries', methods=['GET'])
def list_deliveries(project_id: int, webhook_id: int):
    """Get delivery log for a webhook."""
    sub = WebhookSubscription.query.filter_by(
        id=webhook_id, project_id=project_id
    ).first()
    if not sub:
        return jsonify({"error": "Webhook not found"}), 404

    limit = request.args.get("limit", 20, type=int)
    deliveries = WebhookDelivery.query.filter_by(
        subscription_id=webhook_id
    ).order_by(WebhookDelivery.delivered_at.desc()).limit(limit).all()

    return jsonify([{
        "id": d.id,
        "event_type": d.event_type,
        "response_status": d.response_status,
        "success": d.success,
        "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
    } for d in deliveries])

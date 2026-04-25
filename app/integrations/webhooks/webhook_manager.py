"""
Webhook Manager — Fire outbound webhooks when events occur.

Uses HMAC-SHA256 signing, retry with exponential backoff,
and delivery logging via the WebhookDelivery model.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from app.core.time_utils import utcnow_naive
from typing import Any, Dict, List, Optional
from threading import Thread

import requests

logger = logging.getLogger(__name__)


class WebhookManager:
    """
    Manages outbound webhook subscriptions and delivery.

    Usage:
        mgr = WebhookManager()
        mgr.fire("document.created", {"project_id": 1, "document_id": 42})
    """

    _instance: Optional["WebhookManager"] = None

    def __init__(self):
        self._subscriptions: List[Dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> "WebhookManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_subscriptions(self, project_id: int) -> List[Dict[str, Any]]:
        """Load active subscriptions for a project from the database."""
        try:
            from app.models.researcher.integrations import WebhookSubscription
            subs = WebhookSubscription.query.filter_by(
                project_id=project_id, active=True
            ).all()
            return [s.to_dict() for s in subs]
        except Exception as e:
            logger.error("Failed to load webhook subs: %s", e)
            return []

    def fire(self, event_type: str, data: Dict[str, Any],
             project_id: Optional[int] = None) -> int:
        """
        Fire a webhook event.

        If project_id is given, only delivers to that project's subscriptions.
        Delivery happens asynchronously in background threads.

        Returns: number of deliveries queued
        """
        subs = self._get_matching_subs(event_type, project_id)
        if not subs:
            return 0

        payload = {
            "event": event_type,
            "data": data,
            "timestamp": utcnow_naive().isoformat(),
        }

        count = 0
        for sub in subs:
            thread = Thread(
                target=self._deliver,
                args=(sub, payload),
                daemon=True,
            )
            thread.start()
            count += 1

        logger.info("Queued %d webhook deliveries for '%s'", count, event_type)
        return count

    def _get_matching_subs(self, event_type: str,
                           project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find subscriptions that match the event type."""
        try:
            from app.models.researcher.integrations import WebhookSubscription
            query = WebhookSubscription.query.filter_by(active=True)
            if project_id:
                query = query.filter_by(project_id=project_id)

            subs = query.all()
            matching = []
            for sub in subs:
                events = json.loads(sub.events) if isinstance(sub.events, str) else sub.events
                if event_type in events or "*" in events:
                    matching.append({
                        "id": sub.id,
                        "url": sub.url,
                        "secret": sub.secret,
                        "events": events,
                    })
            return matching
        except Exception as e:
            logger.error("Failed to get matching subs: %s", e)
            return []

    def _deliver(self, sub: Dict[str, Any], payload: Dict[str, Any]):
        """Deliver a webhook with HMAC signature and retry."""
        url = sub.get("url", "")
        secret = sub.get("secret", "")
        sub_id = sub.get("id")
        payload_json = json.dumps(payload, default=str)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": payload.get("event", ""),
            "X-Webhook-Timestamp": payload.get("timestamp", ""),
        }

        # HMAC-SHA256 signature
        if secret:
            signature = hmac.new(
                secret.encode("utf-8"),
                payload_json.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Retry up to 3 times
        last_status = 0
        last_body = ""
        success = False

        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    data=payload_json,
                    headers=headers,
                    timeout=10,
                )
                last_status = response.status_code
                last_body = response.text[:500]
                success = 200 <= last_status < 300

                if success:
                    break

                # 4xx errors → don't retry (client error)
                if 400 <= last_status < 500:
                    break

            except requests.RequestException as e:
                last_body = str(e)

            # Exponential backoff
            if attempt < 2:
                time.sleep(2 ** attempt)

        # Log delivery
        self._log_delivery(sub_id, payload, last_status, last_body, success)

    def _log_delivery(self, subscription_id: Optional[int], payload: Dict,
                      status: int, body: str, success: bool):
        """Record delivery result to the database."""
        try:
            from app.models.researcher.integrations import WebhookDelivery
            from app.database import db

            delivery = WebhookDelivery(
                subscription_id=subscription_id,
                event_type=payload.get("event", ""),
                payload_json=json.dumps(payload, default=str),
                response_status=status,
                response_body=body[:1000],
                success=success,
            )
            db.session.add(delivery)
            db.session.commit()
        except Exception as e:
            logger.error("Failed to log webhook delivery: %s", e)


def get_webhook_manager() -> WebhookManager:
    return WebhookManager.get_instance()

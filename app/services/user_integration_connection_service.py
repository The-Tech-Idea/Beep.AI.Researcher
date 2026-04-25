"""Resolve effective user/global integration connections for runtime services."""
from __future__ import annotations

import json
from typing import Any

from app.models.integrations_registry import GlobalIntegrationService
from app.services.integration_service import decrypt_secret, get_user_credential


def get_enabled_service_by_type(service_type: str) -> GlobalIntegrationService | None:
    """Return the enabled integration service definition for a service type."""
    return GlobalIntegrationService.query.filter_by(
        service_type=service_type,
        is_enabled=True,
    ).first()


def resolve_user_service_connection(user_id: int, service_type: str) -> dict[str, Any]:
    """Resolve the effective runtime connection for a user and integration service."""
    service = get_enabled_service_by_type(service_type)
    if service is None:
        return {
            "service": None,
            "credential": None,
            "connected": False,
            "source": "missing",
            "api_key": None,
            "display_name": None,
            "extra_data": {},
        }

    credential = get_user_credential(user_id, service.id)
    if credential and credential.api_key_encrypted:
        return {
            "service": service,
            "credential": credential,
            "connected": True,
            "source": "user",
            "api_key": _decrypt_or_none(credential.api_key_encrypted),
            "display_name": credential.display_name,
            "extra_data": _load_json_dict(credential.extra_data),
        }

    if service.global_api_key_encrypted:
        return {
            "service": service,
            "credential": None,
            "connected": True,
            "source": "global",
            "api_key": _decrypt_or_none(service.global_api_key_encrypted),
            "display_name": service.name,
            "extra_data": _load_json_dict(service.global_extra_config),
        }

    return {
        "service": service,
        "credential": credential,
        "connected": False,
        "source": "unconfigured",
        "api_key": None,
        "display_name": credential.display_name if credential else None,
        "extra_data": _load_json_dict(credential.extra_data) if credential else {},
    }


def _decrypt_or_none(blob: str | None) -> str | None:
    if not blob:
        return None
    try:
        return decrypt_secret(blob)
    except Exception:
        return None


def _load_json_dict(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}

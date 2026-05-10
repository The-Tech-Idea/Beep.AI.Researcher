"""UTC time helpers and config getter utilities."""

from datetime import datetime, timezone

from app.config_manager import config_manager


def utcnow_naive() -> datetime:
    """Return current UTC as naive datetime for DB columns expecting naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _gi(key: str, default: int) -> int:
    """Read an int config value with a fallback default."""
    v = config_manager.get(key)
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _gb(key: str, default: bool) -> bool:
    """Read a bool config value with a fallback default."""
    v = config_manager.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "yes")

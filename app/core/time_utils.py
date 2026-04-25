"""UTC time helpers."""
from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """Return current UTC as naive datetime for DB columns expecting naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


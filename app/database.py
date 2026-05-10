"""Database compatibility shim — re-exports from app.extensions.

All new code should import from app.extensions instead.
This file exists so existing imports continue to work during migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Re-export the extension instances so existing imports work
from app.extensions import db, Base  # noqa: F401
from app.config_manager import config_manager


def init_db(app):
    """Initialize the database extension with the Flask app."""
    db.init_app(app)


def get_db_uri(provider: str = "sqlite", **kwargs) -> str | None:
    """Construct DB URI. Cross-platform — works on Windows, Linux, macOS."""
    if provider == "sqlite":
        path = kwargs.get("path")
        if not path:
            path = str(config_manager.db_path)
        elif not str(path).startswith("/") and ":" not in str(path)[:2].replace(
            ":", ""
        ):
            path = str(config_manager.base_path / path)

        # Cross-platform: resolve to absolute, normalise separators
        resolved = Path(path).resolve()
        posix = resolved.as_posix()
        # Add timeout (5s) and WAL mode for multi-thread safety
        return f"sqlite:///{posix}?timeout=5000&check_same_thread=False"
    elif provider == "postgresql":
        u, p = kwargs.get("user"), kwargs.get("password")
        h, pt = kwargs.get("host", "localhost"), kwargs.get("port", 5432)
        dbn = kwargs.get("dbname")
        ssl = kwargs.get("sslmode", "")
        uri = f"postgresql://{u}:{p}@{h}:{pt}/{dbn}"
        return uri + f"?sslmode={ssl}" if ssl else uri
    elif provider == "mysql":
        u, p = kwargs.get("user"), kwargs.get("password")
        h, pt = kwargs.get("host", "localhost"), kwargs.get("port", 3306)
        dbn = kwargs.get("dbname")
        return f"mysql+pymysql://{u}:{p}@{h}:{pt}/{dbn}"
    elif provider == "sqlserver":
        u, p = kwargs.get("user"), kwargs.get("password")
        h, pt = kwargs.get("host"), kwargs.get("port", 1433)
        dbn = kwargs.get("dbname")
        driver = kwargs.get("driver", "ODBC Driver 17 for SQL Server")
        import urllib.parse

        enc = urllib.parse.quote_plus(driver)
        return f"mssql+pyodbc://{u}:{p}@{h}:{pt}/{dbn}?driver={enc}"
    elif provider == "cosmosdb":
        u, p = kwargs.get("user"), kwargs.get("password")
        h, pt = kwargs.get("host"), kwargs.get("port", 5432)
        dbn = kwargs.get("dbname", "citus")
        return f"postgresql://{u}:{p}@{h}:{pt}/{dbn}?sslmode=require"
    return None

"""Environment-specific configuration classes.

Usage:
    FLASK_ENV=development  -> DevelopmentConfig
    FLASK_ENV=testing      -> TestingConfig
    FLASK_ENV=production   -> ProductionConfig

If FLASK_ENV is not set, defaults to DevelopmentConfig.
"""

from __future__ import annotations

import os
from pathlib import Path
from app.config_manager import config_manager


class BaseConfig:
    """Shared configuration across all environments."""

    # Security
    SECRET_KEY = config_manager.get("secret_key", os.urandom(32).hex())
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Paths
    BASE_PATH = config_manager.base_path


class DevelopmentConfig(BaseConfig):
    """Development settings — debug on, echo SQL, relaxed security."""

    DEBUG = True
    SQLALCHEMY_ECHO = False  # Set True to log all SQL queries

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        path = config_manager.db_path.resolve().as_posix()
        return f"sqlite:///{path}?timeout=5000&check_same_thread=False"


class TestingConfig(BaseConfig):
    """Testing settings — in-memory DB, no CSRF, full debug."""

    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ECHO = False


class ProductionConfig(BaseConfig):
    """Production settings — debug off, secure cookies, no SQL echo."""

    DEBUG = False
    SQLALCHEMY_ECHO = False
    SESSION_COOKIE_SECURE = True  # HTTPS only (requires TLS termination)

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        path = config_manager.db_path.resolve().as_posix()
        return f"sqlite:///{path}?timeout=5000&check_same_thread=False"


# Config lookup by environment name
config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config_class() -> type[BaseConfig]:
    """Return the config class for the current environment."""
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)

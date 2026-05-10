"""Flask extension instances (unbound — attached in create_app).

All extensions are initialized here so they can be imported anywhere
without creating circular imports. Each extension is bound to the
Flask app inside create_app() via its init_app() method.
"""

from __future__ import annotations

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""

    pass


# SQLAlchemy ORM — no app bound yet
db = SQLAlchemy(model_class=Base, session_options={"expire_on_commit": False})

# Flask-Login — no app bound yet
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"

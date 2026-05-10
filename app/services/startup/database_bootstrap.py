"""Startup database imports, schema creation, lightweight migrations, and seeds."""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabaseBootstrapReport:
    """Summary returned after startup DB work."""

    tables_created: bool
    plan_tiers_seeded: int
    migrations_applied: bool


def run_startup_database_updates(app) -> DatabaseBootstrapReport:
    """Import models, create missing tables, apply additive migrations, and seed data."""

    from app.database import db

    with app.app_context():
        import_all_models()
        db.create_all()
        _migrate_quota_schema(db)
        _migrate_researcher_document_rag_columns(db)
        _migrate_document_ingestion_state_table(db)
        _apply_legacy_migrations(db)
        seeded = seed_default_plan_tiers()
        _log_startup_health(db, seeded_plan_tiers=seeded)
        return DatabaseBootstrapReport(
            tables_created=True,
            plan_tiers_seeded=seeded,
            migrations_applied=True,
        )


def import_all_models() -> None:
    """Import model modules so SQLAlchemy metadata is complete before create_all."""

    from app.models import core, integrations_registry, rbac, tenant, user_management  # noqa: F401
    from app.models.researcher import (  # noqa: F401
        ai_templates,
        batch_operations,
        document_ingestion,
        export_jobs,
        extraction_plugins,
        hallucination_audit,
        integrations,
        library_sources,
        manuscripts,
        monitoring,
        phase_1_models,
        phase_a_models,
        phase_b_models,
        plugin_permissions,
        plugins,
        researcher_chat,
        researcher_coding,
        researcher_data,
        researcher_documents,
        researcher_extraction,
        researcher_notifications,
        researcher_projects,
        researcher_references,
        researcher_tasks,
        researcher_training,
        search_cache,
        sector_models,
        storage_quota,
        transcriptions,
        user_preferences,
    )


def seed_default_plan_tiers() -> int:
    """Ensure built-in quota tiers exist."""

    from app.database import db
    from app.models.researcher.storage_quota import PlanTier

    defaults = [
        {
            "name": "Free",
            "storage_quota_bytes": 1_073_741_824,
            "document_quota": 500,
            "project_quota": 10,
            "api_calls_per_day": 1000,
            "max_upload_size_bytes": 52_428_800,
            "price_display": "$0/mo",
        },
        {
            "name": "Standard",
            "storage_quota_bytes": 10_737_418_240,
            "document_quota": 5000,
            "project_quota": 100,
            "api_calls_per_day": 10000,
            "max_upload_size_bytes": 262_144_000,
            "price_display": "Standard",
        },
        {
            "name": "Enterprise",
            "storage_quota_bytes": None,
            "document_quota": None,
            "project_quota": None,
            "api_calls_per_day": None,
            "max_upload_size_bytes": 1_073_741_824,
            "price_display": "Enterprise",
        },
        {
            "name": "Custom",
            "storage_quota_bytes": None,
            "document_quota": None,
            "project_quota": None,
            "api_calls_per_day": None,
            "max_upload_size_bytes": None,
            "price_display": "Custom",
        },
    ]

    seeded = 0
    for values in defaults:
        if PlanTier.query.filter_by(name=values["name"]).first():
            continue
        db.session.add(PlanTier(**values))
        seeded += 1

    if seeded:
        db.session.commit()
    return seeded


def _apply_legacy_migrations(db) -> None:
    """Run existing additive migration helpers when available."""

    try:
        from apply_migrations import apply_migrations

        apply_migrations(db, db.engine)
    except Exception as exc:
        db.session.rollback()
        logger.warning("Startup migration helpers skipped: %s", exc)


def _migrate_researcher_document_rag_columns(db) -> None:
    """Add RAG sync status columns for existing researcher document tables."""

    from sqlalchemy import inspect, text

    try:
        inspector = inspect(db.engine)
        if "researcher_documents" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("researcher_documents")}
    except Exception:
        db.session.rollback()
        return

    columns = [
        ("rag_document_id", "VARCHAR(255)"),
        ("rag_collection_id", "VARCHAR(255)"),
        ("rag_content_hash", "VARCHAR(64)"),
        ("rag_sync_status", "VARCHAR(30) DEFAULT 'not_indexed'"),
        ("rag_sync_message", "TEXT"),
        ("rag_synced_at", "DATETIME"),
        ("archived_at", "DATETIME"),
        ("deleted_at", "DATETIME"),
        ("parser_name", "VARCHAR(100)"),
        ("parser_version", "VARCHAR(100)"),
        ("extraction_status", "VARCHAR(30) DEFAULT 'pending'"),
        ("extraction_quality", "VARCHAR(50)"),
        ("page_count", "INTEGER"),
        ("table_count", "INTEGER"),
        ("image_count", "INTEGER"),
        ("formula_count", "INTEGER"),
        ("chart_count", "INTEGER"),
        ("audio_duration_seconds", "FLOAT"),
        ("document_hash", "VARCHAR(64)"),
        ("language", "VARCHAR(50)"),
        ("extraction_warnings", "TEXT"),
    ]
    for name, ddl_type in columns:
        if name in existing:
            continue
        try:
            db.session.execute(text(f"ALTER TABLE researcher_documents ADD COLUMN {name} {ddl_type}"))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _migrate_quota_schema(db) -> None:
    """Add quota columns used by the admin document manager to older databases."""

    _add_columns_if_missing(
        db,
        "plan_tiers",
        [
            ("storage_quota_bytes", "BIGINT"),
            ("document_quota", "INTEGER"),
            ("project_quota", "INTEGER"),
            ("api_calls_per_day", "INTEGER"),
            ("max_upload_size_bytes", "BIGINT"),
            ("price_display", "VARCHAR(40)"),
            ("description", "TEXT"),
            ("is_active", "BOOLEAN DEFAULT 1"),
            ("created_at", "DATETIME"),
            ("updated_at", "DATETIME"),
        ],
    )
    _add_columns_if_missing(
        db,
        "tenant_quotas",
        [
            ("plan_tier_id", "INTEGER"),
            ("storage_quota_bytes", "BIGINT"),
            ("document_quota", "INTEGER"),
            ("max_upload_size_bytes", "BIGINT"),
            ("used_storage_bytes", "BIGINT DEFAULT 0"),
            ("document_count", "INTEGER DEFAULT 0"),
            ("last_recalculated_at", "DATETIME"),
        ],
    )
    _add_columns_if_missing(
        db,
        "user_storage_stats",
        [
            ("used_storage_bytes", "BIGINT DEFAULT 0"),
            ("document_count", "INTEGER DEFAULT 0"),
            ("last_upload_at", "DATETIME"),
            ("last_recalculated_at", "DATETIME"),
        ],
    )
    _add_columns_if_missing(
        db,
        "users",
        [
            ("storage_quota_bytes", "BIGINT"),
            ("document_quota", "INTEGER"),
            ("plan_tier_id", "INTEGER"),
        ],
    )
    _add_columns_if_missing(
        db,
        "tenants",
        [
            ("plan_tier_id", "INTEGER"),
        ],
    )


def _add_columns_if_missing(db, table_name: str, columns: list[tuple[str, str]]) -> None:
    """Best-effort additive migration helper for startup bootstrap databases."""

    from sqlalchemy import inspect, text

    try:
        inspector = inspect(db.engine)
        if table_name not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns(table_name)}
    except Exception:
        db.session.rollback()
        return

    for name, ddl_type in columns:
        if name in existing:
            continue
        try:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl_type}"))
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.warning("Startup migration skipped column %s.%s: %s", table_name, name, exc)


def _migrate_document_ingestion_state_table(db) -> None:
    """Ensure the document ingestion state table exists in older databases."""

    from sqlalchemy import inspect

    try:
        inspector = inspect(db.engine)
        if "document_ingestion_states" in inspector.get_table_names():
            return
        from app.models.researcher.document_ingestion import DocumentIngestionState

        DocumentIngestionState.__table__.create(db.engine, checkfirst=True)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning("Document ingestion state migration skipped: %s", exc)


def _log_startup_health(db, *, seeded_plan_tiers: int) -> None:
    """Log a compact schema health summary after startup bootstrap."""

    from sqlalchemy import inspect

    required_tables = {
        "researcher_documents",
        "document_ingestion_states",
        "plan_tiers",
        "tenant_quotas",
        "user_storage_stats",
    }
    try:
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        missing = sorted(required_tables - table_names)
        logger.info(
            "Database startup update complete; tables=%s missing_required=%s seeded_plan_tiers=%s",
            len(table_names),
            ",".join(missing) if missing else "none",
            seeded_plan_tiers,
        )
    except Exception as exc:
        db.session.rollback()
        logger.warning("Database startup health logging skipped: %s", exc)

from sqlalchemy import inspect

from app.database import db
from app.models.researcher.storage_quota import PlanTier
from app.services.startup import database_bootstrap


def test_startup_database_bootstrap_creates_required_tables_on_blank_db(app_context, monkeypatch):
    monkeypatch.setattr(database_bootstrap, "_apply_legacy_migrations", lambda database: None)

    database_bootstrap.import_all_models()
    db.drop_all()

    report = database_bootstrap.run_startup_database_updates(app_context)

    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    researcher_document_columns = {
        column["name"] for column in inspector.get_columns("researcher_documents")
    }

    assert report.tables_created is True
    assert "researcher_documents" in table_names
    assert "document_ingestion_states" in table_names
    assert "plan_tiers" in table_names
    assert "tenant_quotas" in table_names
    assert "user_storage_stats" in table_names
    assert "rag_document_id" in researcher_document_columns
    assert "parser_name" in researcher_document_columns
    assert PlanTier.query.filter_by(name="Free").first() is not None

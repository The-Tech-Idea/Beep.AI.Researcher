"""Database initialization with migrations for testing.

This script applies all migrations to ensure the schema is up to date.
It's automatically run by the test conftest and app initialization.
"""

import os
import sys
from sqlalchemy import text, inspect


def apply_migration_phase_41_references(db, engine):
    """Apply Phase 4.1 References migration - adds columns to references table."""
    
    with engine.begin() as connection:
        inspector = inspect(engine)
        
        # Check if references table exists
        if 'references' not in inspector.get_table_names():
            # Table doesn't exist - will be created by db.create_all()
            return
        
        # Get existing columns
        existing_columns = {col['name'] for col in inspector.get_columns('references')}
        
        # Columns to add
        columns_to_add = [
            ('authors_json', 'TEXT'),
            ('keywords_json', 'TEXT'),
            ('metadata_json', 'TEXT'),
            ('abstract', 'TEXT'),
            ('volume', 'VARCHAR(50)'),
            ('issue', 'VARCHAR(50)'),
            ('pages', 'VARCHAR(50)'),
            ('published_date', 'DATETIME'),
            ('accessed_date', 'DATETIME'),
            ('pubmed_id', 'VARCHAR(50)'),
            ('arxiv_id', 'VARCHAR(50)'),
            ('isbn', 'VARCHAR(20)'),
            ('issn', 'VARCHAR(20)'),
            ('publication', 'VARCHAR(256)'),
            ('citation', 'TEXT'),
            ('notes', 'TEXT'),
            ('citation_count', 'INTEGER DEFAULT 0'),
            ('last_citation_date', 'DATETIME'),
            ('source_type', 'VARCHAR(50) DEFAULT \'other\''),
        ]
        
        # Add missing columns
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    sql = f'ALTER TABLE references ADD COLUMN {col_name} {col_type}'
                    connection.execute(text(sql))
                    print(f"✓ Added column: {col_name}")
                except Exception as e:
                    # Column might already exist, ignore
                    pass
        
        # Create indexes if they don't exist
        try:
            existing_indexes = {idx['name'] for idx in inspector.get_indexes('references')}
        except:
            existing_indexes = set()
        
        indexes_to_create = [
            ('ix_references_project_id', 'project_id'),
            ('ix_references_title', 'title'),
            ('ix_references_citation_key', 'citation_key'),
            ('ix_references_doi', 'doi'),
            ('ix_references_pubmed_id', 'pubmed_id'),
            ('ix_references_arxiv_id', 'arxiv_id'),
            ('ix_references_created_at', 'created_at'),
        ]
        
        for idx_name, col_name in indexes_to_create:
            if idx_name not in existing_indexes:
                try:
                    sql = f'CREATE INDEX IF NOT EXISTS {idx_name} ON references({col_name})'
                    connection.execute(text(sql))
                    print(f"✓ Created index: {idx_name}")
                except Exception as e:
                    # Index might already exist, ignore
                    pass
        
        connection.commit()


def apply_migration_phase_5_ai_settings(db, engine):
    """Apply Phase 5 AI Settings migration - adds config columns to research_projects."""
    with engine.begin() as connection:
        inspector = inspect(engine)
        if 'research_projects' not in inspector.get_table_names():
            return
            
        existing_columns = {col['name'] for col in inspector.get_columns('research_projects')}
        columns_to_add = [
            ('custom_instructions', 'TEXT'),
            ('citation_format', 'VARCHAR(50)'),
            ('ai_language', 'VARCHAR(50)'),
            ('chunk_template_slug', 'VARCHAR(255)'),
            ('rag_quality_mode', 'VARCHAR(50)'),
        ]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    sql = f'ALTER TABLE research_projects ADD COLUMN {col_name} {col_type}'
                    connection.execute(text(sql))
                    print(f"✓ Added column: {col_name} to research_projects")
                except Exception as e:
                    pass
        connection.commit()


def apply_migration_phase_5b_retention_action(db, engine):
    """Apply RetentionPolicy action migration - adds action column to retention_policies."""
    with engine.begin() as connection:
        inspector = inspect(engine)
        if 'retention_policies' not in inspector.get_table_names():
            return

        existing_columns = {col['name'] for col in inspector.get_columns('retention_policies')}
        if 'action' not in existing_columns:
            try:
                connection.execute(text("ALTER TABLE retention_policies ADD COLUMN action VARCHAR(20)"))
                connection.execute(text("UPDATE retention_policies SET action = 'flag' WHERE action IS NULL"))
                print("✓ Added column: action to retention_policies")
            except Exception:
                pass
        connection.commit()


def apply_migration_phase_1_feed_metadata(db, engine):
    """Apply Phase 1 AI discovery metadata migration for feed_recommendations."""
    with engine.begin() as connection:
        inspector = inspect(engine)
        if 'feed_recommendations' not in inspector.get_table_names():
            return

        existing_columns = {col['name'] for col in inspector.get_columns('feed_recommendations')}
        columns_to_add = [
            ('source_id', 'VARCHAR(255)'),
            ('url', 'TEXT'),
            ('publication_date', 'VARCHAR(40)'),
            ('doi', 'VARCHAR(255)'),
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                try:
                    connection.execute(text(f'ALTER TABLE feed_recommendations ADD COLUMN {col_name} {col_type}'))
                    print(f"✓ Added column: {col_name} to feed_recommendations")
                except Exception:
                    pass

        connection.commit()


def apply_migrations(db, engine):
    """Apply all pending migrations to the database."""
    
    print("Applying migrations...")
    
    try:
        apply_migration_phase_41_references(db, engine)
        print("✓ Phase 4.1 References migration applied")
    except Exception as e:
        print(f"⚠ Error applying Phase 4.1 migration: {e}")
        
    try:
        apply_migration_phase_5_ai_settings(db, engine)
        print("✓ Phase 5 AI Settings migration applied")
    except Exception as e:
        print(f"⚠ Error applying Phase 5 migration: {e}")

    try:
        apply_migration_phase_5b_retention_action(db, engine)
        print("✓ Phase 5B Retention action migration applied")
    except Exception as e:
        print(f"⚠ Error applying Phase 5B migration: {e}")

    try:
        apply_migration_phase_1_feed_metadata(db, engine)
        print("✓ Phase 1 feed metadata migration applied")
    except Exception as e:
        print(f"⚠ Error applying Phase 1 feed metadata migration: {e}")
    
    print("Migrations completed")


def init_database(app):
    """Initialize database with schema and migrations."""
    
    from app.database import db
    
    with app.app_context():
        # Create all tables first
        db.create_all()
        print("✓ Database tables created")
        
        # Apply any pending migrations
        apply_migrations(db, db.engine)


if __name__ == '__main__':
    # Run this script directly to initialize the database
    from app import create_app
    
    app = create_app()
    init_database(app)
    print("✓ Database initialization complete")

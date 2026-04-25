#!/usr/bin/env python
"""Initialize/migrate database for Phase 4.1 References."""
import os
import sys
import sqlite3

# Set up environment
os.environ['DATABASE_URL'] = 'sqlite:///researcher.db'

from app import create_app
from app.database import db

app = create_app()

with app.app_context():
    # First, try to clean up any SQL-level locks/issues
    try:
        connection = db.engine.raw_connection()
        cursor = connection.cursor()
        
        # Get all indexes and try to drop them
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'")
        indexes = cursor.fetchall()
        
        for idx in indexes:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {idx[0]}")
            except Exception as e:
                pass
        
        # Get all tables and drop them
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for tbl in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {tbl[0]}")
            except Exception as e:
                pass
        
        connection.commit()
        connection.close()
    except Exception as e:
        pass
    
    print("Creating all tables...")
    db.create_all()
    
    print("Database initialized successfully!")
    print("Tables created:")
    
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    for table in tables:
        columns = inspector.get_columns(table)
        print(f"\n{table}:")
        for col in columns:
            print(f"  - {col['name']}: {col['type']}")


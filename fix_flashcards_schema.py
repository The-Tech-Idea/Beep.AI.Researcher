"""
One-shot schema migration: add missing columns to researcher_flashcards.
Safe to run multiple times (checks before adding).
"""
import os
import sqlite3

# Resolve DB path relative to this script or from env
BASE = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE, 'data', 'researcher.db')

if not os.path.exists(db_path):
    print(f"ERROR: database not found at {db_path}")
    raise SystemExit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Check existing columns
cur.execute("PRAGMA table_info(researcher_flashcards)")
existing = {row[1] for row in cur.fetchall()}
print(f"Existing columns: {sorted(existing)}")

added = []

if 'difficulty' not in existing:
    cur.execute("ALTER TABLE researcher_flashcards ADD COLUMN difficulty VARCHAR(20) DEFAULT 'medium'")
    added.append('difficulty')

if 'source_chunk_id' not in existing:
    cur.execute("ALTER TABLE researcher_flashcards ADD COLUMN source_chunk_id VARCHAR(100)")
    added.append('source_chunk_id')

if added:
    conn.commit()
    print(f"Added columns: {added}")
else:
    print("No columns to add — schema already up to date.")

# Verify
cur.execute("PRAGMA table_info(researcher_flashcards)")
final = [row[1] for row in cur.fetchall()]
print(f"Final columns: {final}")
conn.close()

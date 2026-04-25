"""
Schema audit: compare live SQLite DB columns against SQLAlchemy model definitions.
Run from the project root: .venv/Scripts/python check_schema.py
"""
import sqlite3, os, re, sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'researcher.db')
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'app', 'models', 'researcher')

# --- 1. Read live DB schema ---
print(f"DB: {DB_PATH}  exists={os.path.exists(DB_PATH)}\n")
db = sqlite3.connect(DB_PATH)
db_schema = {}
for (tbl,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
    db_schema[tbl] = [r[1] for r in db.execute(f'PRAGMA table_info("{tbl}")').fetchall()]
db.close()

# --- 2. Parse model columns from source files ---
model_columns = {}  # tablename -> set of col names

for fname in os.listdir(MODELS_DIR):
    if not fname.endswith('.py'):
        continue
    src = open(os.path.join(MODELS_DIR, fname), encoding='utf-8').read()
    # Find class blocks with __tablename__
    for class_block in re.split(r'\nclass ', src):
        tn_match = re.search(r"__tablename__\s*=\s*['\"](\w+)['\"]", class_block)
        if not tn_match:
            continue
        tbl = tn_match.group(1)
        cols = re.findall(r'^\s{4}(\w+)\s*=\s*db\.Column\(', class_block, re.MULTILINE)
        model_columns.setdefault(tbl, set()).update(cols)

# --- 3. Compare ---
print("=" * 70)
all_ok = True
for tbl, model_cols in sorted(model_columns.items()):
    db_cols = set(db_schema.get(tbl, []))
    if not db_cols:
        print(f"[MISSING TABLE] {tbl}  (model defines it but table not in DB)")
        all_ok = False
        continue
    missing = model_cols - db_cols
    extra   = db_cols - model_cols
    if missing or extra:
        all_ok = False
        print(f"[MISMATCH] {tbl}")
        if missing:
            print(f"  In model but NOT in DB  : {sorted(missing)}")
        if extra:
            print(f"  In DB but NOT in model  : {sorted(extra)}")
    else:
        print(f"[OK] {tbl}")

# Tables in DB but no model at all
for tbl in sorted(db_schema):
    if tbl not in model_columns:
        print(f"[NO MODEL] {tbl}  (in DB but no matching model found)")

print("=" * 70)
if all_ok:
    print("All models match the DB schema.")
else:
    print("Schema drift found — see above.")

conn.close()

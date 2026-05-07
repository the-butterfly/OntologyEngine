"""Debug migration issue."""
import sqlite3

DB_PATH = "/Users/dingxuxu/.ontology_engine/data/meta.db"

conn = sqlite3.connect(DB_PATH)
cols_before = [row[1] for row in conn.execute("PRAGMA table_info(entities)").fetchall()]
print("Before:", cols_before)

existing = set(cols_before)
print("Existing set:", existing)

missing = []
for col in ["valid_from", "valid_to", "confidence", "source_pipeline",
            "source_content_hash", "feedback_weight", "domain_id",
            "created_at", "updated_at"]:
    if col not in existing:
        missing.append(col)
        print(f"  MISSING: {col}")
    else:
        print(f"  EXISTS: {col}")

if "created_at" in missing:
    print("Adding created_at...")
    conn.execute("ALTER TABLE entities ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'))")
    print("Added created_at")

if "updated_at" in missing:
    print("Adding updated_at...")
    conn.execute("ALTER TABLE entities ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'))")
    print("Added updated_at")

conn.commit()
cols_after = [row[1] for row in conn.execute("PRAGMA table_info(entities)").fetchall()]
print("After:", cols_after)
conn.close()

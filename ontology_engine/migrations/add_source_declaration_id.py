"""
Migration: Add source_declaration_id to rule_groups table

Run with: python -m ontology_engine.migrations.add_source_declaration_id <db_path>

This migration:
1. Adds source_declaration_id column to rule_groups if not exists
2. Prints current rule_declarations count for verification
"""

import sqlite3
import sys


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='rule_declarations'"
    )
    if cursor.fetchone() is None:
        print("No rule_declarations table found — nothing to migrate")
        conn.close()
        return

    old_count = conn.execute("SELECT COUNT(*) FROM rule_declarations").fetchone()[0]
    print(f"Found {old_count} rule_declarations")

    new_count = conn.execute("SELECT COUNT(*) FROM rule_groups").fetchone()[0]
    print(f"Found {new_count} rule_groups")

    try:
        conn.execute(
            "ALTER TABLE rule_groups ADD COLUMN source_declaration_id TEXT"
        )
        print("Added source_declaration_id column to rule_groups")
    except Exception as e:
        print(f"Column may already exist: {e}")

    print("Migration notes:")
    print("- source_declaration_id column will be NULL for all existing groups")
    print("- Old rule_declarations/rule_logics table deletion is a separate step (T5)")
    print("Migration complete.")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python -m ontology_engine.migrations.add_source_declaration_id <db_path>"
        )
        sys.exit(1)
    migrate(sys.argv[1])

"""
Migration: Add source_declaration_id to rule_groups table

Run with: python -m ontology_engine.migrations.add_source_declaration_id <db_path>

This migration:
1. Adds source_declaration_id column to rule_groups if not exists
2. Prints current rule_declarations count for verification
"""

import sys
import duckdb


def migrate(db_path: str) -> None:
    conn = duckdb.connect(db_path, read_only=False)

    # Check rule_declarations table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]

    if "rule_declarations" not in table_names:
        print("No rule_declarations table found — nothing to migrate")
        conn.close()
        return

    # Count old records
    old_count = conn.execute("SELECT COUNT(*) FROM rule_declarations").fetchone()[0]
    print(f"Found {old_count} rule_declarations")

    new_count = conn.execute("SELECT COUNT(*) FROM rule_groups").fetchone()[0]
    print(f"Found {new_count} rule_groups")

    # Migration: add source_declaration_id column if not exists
    try:
        conn.execute(
            "ALTER TABLE rule_groups ADD COLUMN IF NOT EXISTS source_declaration_id VARCHAR"
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

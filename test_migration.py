"""Test schema migration for old databases."""
import sqlite3
import tempfile
import os
import asyncio

from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.storage.base import EntityInstance
from datetime import datetime


def test_migration():
    db_path = tempfile.mktemp(suffix=".db")

    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE entities (
        concept TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        data TEXT NOT NULL,
        PRIMARY KEY (concept, entity_id)
    )""")
    conn.commit()
    cols_before = [row[1] for row in conn.execute("PRAGMA table_info(entities)").fetchall()]
    print(f"Before migration, entities columns: {cols_before}")
    conn.close()

    async def run():
        storage = SQLiteStorage(db_path=db_path)
        await storage.initialize()

        entity = EntityInstance(
            _fact_object="Company",
            entity_id="test_001",
            data={"name": "Test Corp"},
            valid_from=datetime(2024, 1, 1),
            valid_to=datetime(2025, 1, 1),
            confidence=0.95,
        )
        result = await storage.save_entity(entity)
        print(f"save_entity returned: {result}")

        loaded = await storage.get_entity("Company", "test_001")
        print(f"Loaded entity valid_from: {loaded.valid_from}")
        print(f"Loaded entity confidence: {loaded.confidence}")

        await storage.close()

    asyncio.run(run())
    os.unlink(db_path)
    print("Migration test PASSED!")


if __name__ == "__main__":
    test_migration()

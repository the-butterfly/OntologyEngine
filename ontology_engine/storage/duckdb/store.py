# ontology_engine/storage/duckdb/store.py
from __future__ import annotations

import asyncio
import json
from typing import Any

import duckdb

from ontology_engine.storage.base import (
    EntityInstance,
    RelationInstance,
    StorageBackend,
    StorageError,
)


class DuckDBStorage(StorageBackend):
    """DuckDB storage implementation.

    Uses ``asyncio.to_thread`` to run synchronous DuckDB operations
    in a thread pool, avoiding blocking the event loop.
    A single ``asyncio.Lock`` serializes all DB operations because
    DuckDB connections are not thread-safe.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._lock: asyncio.Lock | None = None

    def _ensure_initialized(self) -> None:
        if self._conn is None:
            raise StorageError("Storage not initialized. Call initialize() first.")

    async def initialize(self) -> None:
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)
        if self._lock is None:
            self._lock = asyncio.Lock()

        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS entities (
                concept VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                data JSON NOT NULL,
                PRIMARY KEY (concept, entity_id)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS relations (
                relation_type VARCHAR NOT NULL,
                from_entity_id VARCHAR NOT NULL,
                to_entity_id VARCHAR NOT NULL,
                data JSON,
                PRIMARY KEY (relation_type, from_entity_id, to_entity_id)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            "CREATE INDEX IF NOT EXISTS idx_entities_concept ON entities(concept)",
        )
        await asyncio.to_thread(
            self._conn.execute,
            "CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_entity_id)",
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS computed_metrics (
                entity_id VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                value JSON NOT NULL,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity_id, metric_name)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS category_tags (
                entity_id VARCHAR PRIMARY KEY,
                tags JSON NOT NULL,
                categorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS rule_execution_log (
                entity_id VARCHAR NOT NULL,
                rule_id VARCHAR NOT NULL,
                result VARCHAR NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        )

    async def save_entity(self, entity: EntityInstance) -> str:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO entities (concept, entity_id, data) VALUES (?, ?, ?)",
                [entity.concept, entity.entity_id, json.dumps(entity.data)],
            )
        return entity.entity_id

    async def get_entity(self, concept: str, entity_id: str) -> EntityInstance | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> tuple[str] | None:
                cursor = self._conn.execute(
                    "SELECT data FROM entities WHERE concept = ? AND entity_id = ?",
                    [concept, entity_id],
                )
                return cursor.fetchone()

            result = await asyncio.to_thread(_fetch)

        if result is None:
            return None
        return EntityInstance(concept=concept, entity_id=entity_id, data=json.loads(result[0]))

    async def query_entities(
        self,
        concept: str | None,
        filters: dict[str, Any] | None = None,
    ) -> list[EntityInstance]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> list[tuple[str, str, str]]:
                if concept:
                    cursor = self._conn.execute(
                        "SELECT concept, entity_id, data FROM entities WHERE concept = ? ORDER BY entity_id",
                        [concept],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT concept, entity_id, data FROM entities ORDER BY concept, entity_id"
                    )
                return cursor.fetchall()

            rows = await asyncio.to_thread(_fetch)

        entities = [
            EntityInstance(
                concept=row[0],
                entity_id=row[1],
                data=json.loads(row[2]),
            )
            for row in rows
        ]
        if not filters:
            return entities
        return [entity for entity in entities if self._matches_filters(entity.data, filters)]

    @staticmethod
    def _matches_filters(data: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            actual = DuckDBStorage._get_nested_value(data, key)
            if actual != expected:
                return False
        return True

    @staticmethod
    def _get_nested_value(data: dict[str, Any], path: str) -> Any:
        value: Any = data
        for key in path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    async def save_relation(self, relation: RelationInstance) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO relations
                    (relation_type, from_entity_id, to_entity_id, data)
                VALUES (?, ?, ?, ?)
                """,
                [
                    relation.relation_type,
                    relation.from_entity_id,
                    relation.to_entity_id,
                    json.dumps(relation.data),
                ],
            )

    async def get_relations(
        self,
        from_entity_id: str,
        relation_type: str | None = None,
    ) -> list[RelationInstance]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> list[tuple[str, str, str | None]]:
                if relation_type:
                    cursor = self._conn.execute(
                        """
                        SELECT relation_type, to_entity_id, data
                        FROM relations
                        WHERE from_entity_id = ? AND relation_type = ?
                        """,
                        [from_entity_id, relation_type],
                    )
                else:
                    cursor = self._conn.execute(
                        """
                        SELECT relation_type, to_entity_id, data
                        FROM relations
                        WHERE from_entity_id = ?
                        """,
                        [from_entity_id],
                    )
                return cursor.fetchall()

            results = await asyncio.to_thread(_fetch)

        return [
            RelationInstance(
                relation_type=row[0],
                from_entity_id=from_entity_id,
                to_entity_id=row[1],
                data=json.loads(row[2]) if row[2] else {},
            )
            for row in results
        ]

    async def save_metric(self, entity_id: str, metric_name: str, value: Any) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO computed_metrics
                    (entity_id, metric_name, value, computed_at)
                VALUES (?, ?, ?, NOW())
                """,
                [entity_id, metric_name, json.dumps(value)],
            )

    async def get_metric(self, entity_id: str, metric_name: str) -> Any | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> tuple[str] | None:
                cursor = self._conn.execute(
                    """
                    SELECT value FROM computed_metrics
                    WHERE entity_id = ? AND metric_name = ?
                    """,
                    [entity_id, metric_name],
                )
                return cursor.fetchone()

            result = await asyncio.to_thread(_fetch)
        if result is None:
            return None
        return json.loads(result[0])

    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str,
        direction: str = "outgoing",
    ) -> list[tuple[EntityInstance, RelationInstance]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> list[tuple[str, str, str, str, str, str, str | None]]:
                if direction == "outgoing":
                    cursor = self._conn.execute(
                        """
                        SELECT r.relation_type, r.from_entity_id, r.to_entity_id,
                               e.concept, e.entity_id, e.data, r.data
                        FROM relations r
                        JOIN entities e ON r.to_entity_id = e.entity_id
                        WHERE r.from_entity_id = ? AND r.relation_type = ?
                        """,
                        [entity_id, relation_type],
                    )
                else:
                    cursor = self._conn.execute(
                        """
                        SELECT r.relation_type, r.from_entity_id, r.to_entity_id,
                               e.concept, e.entity_id, e.data, r.data
                        FROM relations r
                        JOIN entities e ON r.from_entity_id = e.entity_id
                        WHERE r.to_entity_id = ? AND r.relation_type = ?
                        """,
                        [entity_id, relation_type],
                    )
                return cursor.fetchall()

            results = await asyncio.to_thread(_fetch)

        neighbors: list[tuple[EntityInstance, RelationInstance]] = []
        for row in results:
            entity = EntityInstance(
                concept=row[3],
                entity_id=row[4],
                data=json.loads(row[5]),
            )
            relation = RelationInstance(
                relation_type=row[0],
                from_entity_id=row[1],
                to_entity_id=row[2],
                data=json.loads(row[6]) if row[6] else {},
            )
            neighbors.append((entity, relation))
        return neighbors

    async def save_category_tags(self, entity_id: str, tags: dict[str, str]) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO category_tags
                    (entity_id, tags, categorized_at)
                VALUES (?, ?, NOW())
                """,
                [entity_id, json.dumps(tags)],
            )

    async def get_category_tags(self, entity_id: str) -> dict[str, str] | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> tuple[str] | None:
                cursor = self._conn.execute(
                    "SELECT tags FROM category_tags WHERE entity_id = ?",
                    [entity_id],
                )
                return cursor.fetchone()

            result = await asyncio.to_thread(_fetch)
        if result is None:
            return None
        return json.loads(result[0])

    async def log_rule_execution(self, entity_id: str, rule_id: str, result: str) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT INTO rule_execution_log (entity_id, rule_id, result, executed_at)
                VALUES (?, ?, ?, NOW())
                """,
                [entity_id, rule_id, result],
            )

    async def close(self) -> None:
        if self._conn is not None:
            if self._lock is not None:
                async with self._lock:
                    await asyncio.to_thread(self._conn.close)
            else:
                await asyncio.to_thread(self._conn.close)
            self._conn = None

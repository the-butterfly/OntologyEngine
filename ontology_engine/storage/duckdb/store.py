# ontology_engine/storage/duckdb/store.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
import asyncio
import json
import duckdb
from dataclasses import dataclass, field


class StorageError(Exception):
    """Storage operation error"""
    pass


@dataclass
class EntityInstance:
    """Entity instance with concept and data."""
    concept: str
    entity_id: str
    data: dict[str, Any]


@dataclass
class RelationInstance:
    """Relation between two entities."""
    relation_type: str
    from_entity_id: str
    to_entity_id: str
    data: dict[str, Any] = field(default_factory=dict)


class StorageBackend(ABC):
    """Abstract storage backend."""

    @abstractmethod
    async def save_entity(self, entity: EntityInstance) -> str:
        """Save entity, return ID."""
        pass

    @abstractmethod
    async def get_entity(self, concept: str, entity_id: str) -> EntityInstance | None:
        """Get entity by concept and ID."""
        pass

    @abstractmethod
    async def query_entities(
        self,
        concept: str,
        filters: dict[str, Any] | None = None
    ) -> list[EntityInstance]:
        """Query entities by concept with optional filters."""
        pass

    @abstractmethod
    async def save_relation(self, relation: RelationInstance) -> None:
        """Save relation."""
        pass

    @abstractmethod
    async def get_relations(
        self,
        from_entity_id: str,
        relation_type: str | None = None
    ) -> list[RelationInstance]:
        """Get relations from an entity."""
        pass


class DuckDBStorage(StorageBackend):
    """DuckDB storage implementation.

    Uses asyncio.to_thread() to run synchronous DuckDB operations
    in a thread pool, avoiding blocking the event loop.
    """

    def __init__(self, db_path: str = ":memory:"):
        """Initialize DuckDB storage.

        Args:
            db_path: Path to DuckDB database, or ":memory:" for in-memory
        """
        self.db_path = db_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _ensure_initialized(self) -> None:
        """Ensure database is initialized, raise if not."""
        if self._conn is None:
            raise StorageError("Storage not initialized. Call initialize() first.")

    async def initialize(self) -> None:
        """Initialize database tables."""
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path)

        # Create entities table
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS entities (
                concept VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                data JSON NOT NULL,
                PRIMARY KEY (concept, entity_id)
            )
        """)

        # Create relations table
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS relations (
                relation_type VARCHAR NOT NULL,
                from_entity_id VARCHAR NOT NULL,
                to_entity_id VARCHAR NOT NULL,
                data JSON,
                PRIMARY KEY (relation_type, from_entity_id, to_entity_id)
            )
        """)

        # Create indexes
        await asyncio.to_thread(self._conn.execute, """
            CREATE INDEX IF NOT EXISTS idx_entities_concept ON entities(concept)
        """)
        await asyncio.to_thread(self._conn.execute, """
            CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_entity_id)
        """)

        # Create computed_metrics table
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS computed_metrics (
                entity_id VARCHAR NOT NULL,
                metric_name VARCHAR NOT NULL,
                value JSON NOT NULL,
                computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity_id, metric_name)
            )
        """)

        # Create category_tags table
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS category_tags (
                entity_id VARCHAR PRIMARY KEY,
                tags JSON NOT NULL,
                categorized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create rule_execution_log table
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS rule_execution_log (
                id INTEGER PRIMARY KEY,
                entity_id VARCHAR NOT NULL,
                rule_id VARCHAR NOT NULL,
                result VARCHAR NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    async def save_entity(self, entity: EntityInstance) -> str:
        """Save entity to storage."""
        self._ensure_initialized()
        await asyncio.to_thread(
            self._conn.execute,
            "INSERT OR REPLACE INTO entities (concept, entity_id, data) VALUES (?, ?, ?)",
            [entity.concept, entity.entity_id, json.dumps(entity.data)]
        )
        return entity.entity_id

    async def get_entity(self, concept: str, entity_id: str) -> EntityInstance | None:
        """Get entity by concept and ID."""
        self._ensure_initialized()

        def _fetch():
            cursor = self._conn.execute(
                "SELECT data FROM entities WHERE concept = ? AND entity_id = ?",
                [concept, entity_id]
            )
            return cursor.fetchone()

        result = await asyncio.to_thread(_fetch)

        if result is None:
            return None

        data = json.loads(result[0])
        return EntityInstance(concept=concept, entity_id=entity_id, data=data)

    async def query_entities(
        self,
        concept: str,
        filters: dict[str, Any] | None = None
    ) -> list[EntityInstance]:
        """Query entities with optional filters."""
        self._ensure_initialized()

        def _fetch():
            if not filters:
                cursor = self._conn.execute(
                    "SELECT entity_id, data FROM entities WHERE concept = ?",
                    [concept]
                )
            else:
                # Build query with filters
                conditions = ["concept = ?"]
                params = [concept]

                for key, value in filters.items():
                    conditions.append(f"json_extract(data, '$.{key}') = ?")
                    params.append(value)

                query = f"SELECT entity_id, data FROM entities WHERE {' AND '.join(conditions)}"
                cursor = self._conn.execute(query, params)

            return cursor.fetchall()

        results = await asyncio.to_thread(_fetch)

        entities = []
        for row in results:
            data = json.loads(row[1])
            entities.append(EntityInstance(
                concept=concept,
                entity_id=row[0],
                data=data
            ))

        return entities

    async def save_relation(self, relation: RelationInstance) -> None:
        """Save relation."""
        self._ensure_initialized()
        await asyncio.to_thread(
            self._conn.execute,
            """INSERT OR REPLACE INTO relations
               (relation_type, from_entity_id, to_entity_id, data)
               VALUES (?, ?, ?, ?)""",
            [
                relation.relation_type,
                relation.from_entity_id,
                relation.to_entity_id,
                json.dumps(relation.data)
            ]
        )

    async def get_relations(
        self,
        from_entity_id: str,
        relation_type: str | None = None
    ) -> list[RelationInstance]:
        """Get relations from an entity."""
        self._ensure_initialized()

        def _fetch():
            if relation_type:
                cursor = self._conn.execute(
                    """SELECT relation_type, to_entity_id, data
                       FROM relations
                       WHERE from_entity_id = ? AND relation_type = ?""",
                    [from_entity_id, relation_type]
                )
            else:
                cursor = self._conn.execute(
                    """SELECT relation_type, to_entity_id, data
                       FROM relations
                       WHERE from_entity_id = ?""",
                    [from_entity_id]
                )
            return cursor.fetchall()

        results = await asyncio.to_thread(_fetch)

        relations = []
        for row in results:
            data = json.loads(row[2]) if row[2] else {}
            relations.append(RelationInstance(
                relation_type=row[0],
                from_entity_id=from_entity_id,
                to_entity_id=row[1],
                data=data
            ))

        return relations

    async def save_metric(
        self,
        entity_id: str,
        metric_name: str,
        value: Any
    ) -> None:
        """Save computed metric for an entity."""
        self._ensure_initialized()
        await asyncio.to_thread(
            self._conn.execute,
            """INSERT OR REPLACE INTO computed_metrics
               (entity_id, metric_name, value, computed_at)
               VALUES (?, ?, ?, NOW())""",
            [entity_id, metric_name, json.dumps(value)]
        )

    async def get_metric(
        self,
        entity_id: str,
        metric_name: str
    ) -> Any | None:
        """Get computed metric for an entity."""
        self._ensure_initialized()

        def _fetch():
            cursor = self._conn.execute(
                """SELECT value FROM computed_metrics
                   WHERE entity_id = ? AND metric_name = ?""",
                [entity_id, metric_name]
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
        direction: str = "outgoing"
    ) -> list[tuple[EntityInstance, RelationInstance]]:
        """Get neighboring entities via relation.

        Args:
            entity_id: The source entity ID
            relation_type: Type of relation to traverse
            direction: "outgoing" (has_invoice) or "incoming" (guaranteed_by)

        Returns:
            List of (neighbor_entity, relation) tuples
        """
        self._ensure_initialized()

        def _fetch():
            if direction == "outgoing":
                cursor = self._conn.execute(
                    """SELECT e.concept, e.entity_id, e.data, r.data
                       FROM relations r
                       JOIN entities e ON r.to_entity_id = e.entity_id
                       WHERE r.from_entity_id = ? AND r.relation_type = ?""",
                    [entity_id, relation_type]
                )
            else:
                cursor = self._conn.execute(
                    """SELECT e.concept, e.entity_id, e.data, r.data
                       FROM relations r
                       JOIN entities e ON r.from_entity_id = e.entity_id
                       WHERE r.to_entity_id = ? AND r.relation_type = ?""",
                    [entity_id, relation_type]
                )
            return cursor.fetchall()

        results = await asyncio.to_thread(_fetch)
        neighbors = []
        for row in results:
            entity = EntityInstance(
                concept=row[0],
                entity_id=row[1],
                data=json.loads(row[2])
            )
            rel = RelationInstance(
                relation_type=relation_type,
                from_entity_id=entity_id,
                to_entity_id=row[1],
                data=json.loads(row[3]) if row[3] else {}
            )
            neighbors.append((entity, rel))
        return neighbors

    async def save_category_tags(
        self,
        entity_id: str,
        tags: dict[str, str]
    ) -> None:
        """Save category tags for an entity."""
        self._ensure_initialized()
        await asyncio.to_thread(
            self._conn.execute,
            """INSERT OR REPLACE INTO category_tags
               (entity_id, tags, categorized_at)
               VALUES (?, ?, NOW())""",
            [entity_id, json.dumps(tags)]
        )

    async def get_category_tags(
        self,
        entity_id: str
    ) -> dict[str, str] | None:
        """Get category tags for an entity."""
        self._ensure_initialized()

        def _fetch():
            cursor = self._conn.execute(
                """SELECT tags FROM category_tags WHERE entity_id = ?""",
                [entity_id]
            )
            return cursor.fetchone()

        result = await asyncio.to_thread(_fetch)
        if result is None:
            return None
        return json.loads(result[0])

    async def log_rule_execution(
        self,
        entity_id: str,
        rule_id: str,
        result: str
    ) -> None:
        """Log rule execution for audit trail."""
        self._ensure_initialized()
        await asyncio.to_thread(
            self._conn.execute,
            """INSERT INTO rule_execution_log
               (entity_id, rule_id, result, executed_at)
               VALUES (?, ?, ?, NOW())""",
            [entity_id, rule_id, result]
        )

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

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

        # --- Phase 1 Enhancement Tables ---

        # Dataset management tables
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                description VARCHAR,
                scope JSON,
                source_type VARCHAR,
                version VARCHAR DEFAULT '1.0.0',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (dataset_id)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS entity_dataset_membership (
                entity_id VARCHAR NOT NULL,
                dataset_id VARCHAR NOT NULL,
                concept VARCHAR NOT NULL,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_line INTEGER,
                is_primary BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (entity_id, dataset_id)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS dataset_snapshots (
                snapshot_id VARCHAR NOT NULL,
                dataset_id VARCHAR NOT NULL,
                entity_count INTEGER,
                relation_count INTEGER,
                description VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (snapshot_id)
            )
            """,
        )

        # Dimension applicability table
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS dimension_applicability (
                dimension_id VARCHAR NOT NULL,
                object_type VARCHAR NOT NULL,
                required BOOLEAN DEFAULT FALSE,
                auto_categorize BOOLEAN DEFAULT TRUE,
                source_attribute VARCHAR,
                PRIMARY KEY (dimension_id, object_type)
            )
            """,
        )

        # Category rule mapping table
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS category_rule_mapping (
                dimension_id VARCHAR NOT NULL,
                dimension_value VARCHAR NOT NULL,
                rule_group_id VARCHAR NOT NULL,
                mapping_type VARCHAR NOT NULL DEFAULT 'applicable',
                override_rule_id VARCHAR,
                override_field VARCHAR,
                override_value JSON,
                PRIMARY KEY (dimension_id, dimension_value, rule_group_id)
            )
            """,
        )

        # Incremental update tracking tables
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS change_batches (
                batch_id VARCHAR NOT NULL,
                dataset_id VARCHAR,
                status VARCHAR DEFAULT 'pending',
                entity_count INTEGER,
                created_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                deleted_count INTEGER DEFAULT 0,
                unchanged_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (batch_id)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS entity_changes (
                batch_id VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                concept VARCHAR NOT NULL,
                change_type VARCHAR NOT NULL,
                field_changes JSON,
                old_data JSON,
                new_data JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (batch_id, entity_id)
            )
            """,
        )
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS entity_versions (
                entity_id VARCHAR NOT NULL,
                concept VARCHAR NOT NULL,
                version INTEGER DEFAULT 1,
                data JSON NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by VARCHAR DEFAULT 'system',
                PRIMARY KEY (entity_id, version)
            )
            """,
        )

        # --- Phase 2: Rule Orchestration Tables ---

        # Rule groups table (framework - four elements ①②③)
        # Note: UNIQUE constraint is on (name, schema_id) for semantic space isolation
        # schema_id NULL values are allowed but behave according to SQL standard
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS rule_groups (
                id                      VARCHAR PRIMARY KEY,
                name                    VARCHAR NOT NULL,
                description             TEXT,
                type                    VARCHAR NOT NULL,
                priority                INTEGER DEFAULT 100,
                applies_to              JSON,
                preconditions           JSON,
                inputs                  JSON,
                outputs                 JSON,
                enabled                 BOOLEAN DEFAULT TRUE,
                schema_id               VARCHAR,
                source_declaration_id   VARCHAR,
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (name, schema_id)
            )
            """,
        )

        # Migration: add source_declaration_id column for existing databases
        try:
            await asyncio.to_thread(
                self._conn.execute,
                "ALTER TABLE rule_groups ADD COLUMN IF NOT EXISTS source_declaration_id VARCHAR",
            )
        except Exception:
            pass  # Column may already exist

        # Rule steps table (logic - four element ④)
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS rule_steps (
                id           VARCHAR NOT NULL,
                rule_group   VARCHAR NOT NULL,
                step_order   INTEGER NOT NULL,
                name         VARCHAR,
                when_clause  JSON,
                then_clause  JSON,
                else_clause  JSON,
                enabled      BOOLEAN DEFAULT TRUE,
                description  TEXT,
                tags         JSON,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (rule_group, id)
            )
            """,
        )

        # Metric extensions table (value domain / thresholds / color)
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS metric_extensions (
                metric_name  VARCHAR PRIMARY KEY,
                value_domain JSON,
                thresholds   JSON,
                color        VARCHAR,
                unit         VARCHAR,
                updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        )

        # Operator registry table
        await asyncio.to_thread(
            self._conn.execute,
            """
            CREATE TABLE IF NOT EXISTS operator_registry (
                name         VARCHAR PRIMARY KEY,
                display_name VARCHAR,
                description  TEXT,
                category     VARCHAR,
                param_schema JSON,
                input_types  JSON,
                output_types JSON,
                enabled      BOOLEAN DEFAULT TRUE
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

    async def get_entity_by_id(self, entity_id: str) -> EntityInstance | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        async with self._lock:
            def _fetch() -> tuple[str, str] | None:
                cursor = self._conn.execute(
                    "SELECT concept, data FROM entities WHERE entity_id = ?",
                    [entity_id],
                )
                return cursor.fetchone()

            result = await asyncio.to_thread(_fetch)

        if result is None:
            return None
        return EntityInstance(concept=result[0], entity_id=entity_id, data=json.loads(result[1]))

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

    async def get_rule_execution_log(
        self,
        entity_id: str,
        rule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query rule execution log for an entity."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        if rule_id:
            query = """
                SELECT entity_id, rule_id, result, executed_at
                FROM rule_execution_log
                WHERE entity_id = ? AND rule_id = ?
                ORDER BY executed_at DESC
            """
            params: tuple[str, ...] = (entity_id, rule_id)
        else:
            query = """
                SELECT entity_id, rule_id, result, executed_at
                FROM rule_execution_log
                WHERE entity_id = ?
                ORDER BY executed_at DESC
            """
            params = (entity_id,)

        async with self._lock:
            rows = await asyncio.to_thread(
                self._conn.execute,
                query,
                list(params),
            )
            results = rows.fetchall()

        return [
            {
                "entity_id": row[0],
                "rule_id": row[1],
                "result": row[2],
                "executed_at": str(row[3]),
            }
            for row in results
        ]

    # =========================================================================
    # Phase 1 Enhancement: Dataset CRUD
    # =========================================================================

    async def create_dataset(
        self,
        dataset_id: str,
        name: str,
        scope: dict[str, Any] | None = None,
        source_type: str = "manual",
        description: str | None = None,
    ) -> None:
        """Create a new dataset."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT INTO datasets (dataset_id, name, description, scope, source_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                [dataset_id, name, description, json.dumps(scope or {}), source_type],
            )

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Get a dataset by ID."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT dataset_id, name, description, scope, source_type, version, created_at, updated_at FROM datasets WHERE dataset_id = ?",
                    [dataset_id],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "dataset_id": row[0],
            "name": row[1],
            "description": row[2],
            "scope": json.loads(row[3]),
            "source_type": row[4],
            "version": row[5],
            "created_at": str(row[6]),
            "updated_at": str(row[7]),
        }

    async def list_datasets(self) -> list[dict[str, Any]]:
        """List all datasets."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT dataset_id, name, description, scope, source_type, version, created_at, updated_at FROM datasets ORDER BY created_at"
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "dataset_id": r[0], "name": r[1], "description": r[2],
                "scope": json.loads(r[3]), "source_type": r[4], "version": r[5],
                "created_at": str(r[6]), "updated_at": str(r[7]),
            }
            for r in rows
        ]

    async def update_dataset(
        self,
        dataset_id: str,
        name: str | None = None,
        description: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> bool:
        """Update a dataset."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        sets: list[str] = []
        params: list[Any] = []
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if scope is not None:
            sets.append("scope = ?")
            params.append(json.dumps(scope))
        if not sets:
            return False
        sets.append("updated_at = NOW()")
        params.append(dataset_id)
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                f"UPDATE datasets SET {', '.join(sets)} WHERE dataset_id = ?",
                params,
            )
        return True

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and its memberships."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM entity_dataset_membership WHERE dataset_id = ?",
                [dataset_id],
            )
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM dataset_snapshots WHERE dataset_id = ?",
                [dataset_id],
            )
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM datasets WHERE dataset_id = ?",
                [dataset_id],
            )
        return True

    # =========================================================================
    # Phase 1 Enhancement: Entity Dataset Membership
    # =========================================================================

    async def add_entity_to_dataset(
        self,
        entity_id: str,
        dataset_id: str,
        concept: str,
        is_primary: bool = False,
        source_line: int | None = None,
    ) -> None:
        """Add an entity to a dataset."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO entity_dataset_membership
                    (entity_id, dataset_id, concept, is_primary, source_line)
                VALUES (?, ?, ?, ?, ?)
                """,
                [entity_id, dataset_id, concept, is_primary, source_line],
            )

    async def get_dataset_entities(
        self,
        dataset_id: str,
        concept: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get entities in a dataset."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if concept:
                    cursor = self._conn.execute(
                        "SELECT entity_id, dataset_id, concept, imported_at, source_line, is_primary FROM entity_dataset_membership WHERE dataset_id = ? AND concept = ?",
                        [dataset_id, concept],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT entity_id, dataset_id, concept, imported_at, source_line, is_primary FROM entity_dataset_membership WHERE dataset_id = ?",
                        [dataset_id],
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "entity_id": r[0], "dataset_id": r[1], "concept": r[2],
                "imported_at": str(r[3]), "source_line": r[4], "is_primary": r[5],
            }
            for r in rows
        ]

    async def remove_entity_from_dataset(self, entity_id: str, dataset_id: str) -> None:
        """Remove an entity from a dataset."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM entity_dataset_membership WHERE entity_id = ? AND dataset_id = ?",
                [entity_id, dataset_id],
            )

    # =========================================================================
    # Phase 1 Enhancement: Dataset Snapshots
    # =========================================================================

    async def create_snapshot(
        self,
        snapshot_id: str,
        dataset_id: str,
        entity_count: int | None = None,
        relation_count: int | None = None,
        description: str | None = None,
    ) -> None:
        """Create a dataset snapshot."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT INTO dataset_snapshots (snapshot_id, dataset_id, entity_count, relation_count, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                [snapshot_id, dataset_id, entity_count, relation_count, description],
            )

    async def get_snapshots(self, dataset_id: str) -> list[dict[str, Any]]:
        """Get snapshots for a dataset."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT snapshot_id, dataset_id, entity_count, relation_count, description, created_at FROM dataset_snapshots WHERE dataset_id = ? ORDER BY created_at",
                    [dataset_id],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "snapshot_id": r[0], "dataset_id": r[1],
                "entity_count": r[2], "relation_count": r[3],
                "description": r[4], "created_at": str(r[5]),
            }
            for r in rows
        ]

    # =========================================================================
    # Phase 1 Enhancement: Dimension Applicability
    # =========================================================================

    async def save_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str,
        required: bool = False,
        auto_categorize: bool = True,
        source_attribute: str | None = None,
    ) -> None:
        """Save dimension applicability mapping."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO dimension_applicability
                    (dimension_id, object_type, required, auto_categorize, source_attribute)
                VALUES (?, ?, ?, ?, ?)
                """,
                [dimension_id, object_type, required, auto_categorize, source_attribute],
            )

    async def get_dimension_applicability(
        self, dimension_id: str, object_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get dimension applicability entries."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if object_type:
                    cursor = self._conn.execute(
                        "SELECT dimension_id, object_type, required, auto_categorize, source_attribute FROM dimension_applicability WHERE dimension_id = ? AND object_type = ?",
                        [dimension_id, object_type],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT dimension_id, object_type, required, auto_categorize, source_attribute FROM dimension_applicability WHERE dimension_id = ?",
                        [dimension_id],
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "dimension_id": r[0], "object_type": r[1],
                "required": r[2], "auto_categorize": r[3],
                "source_attribute": r[4],
            }
            for r in rows
        ]

    async def delete_dimension_applicability(self, dimension_id: str, object_type: str) -> None:
        """Delete a dimension applicability entry."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM dimension_applicability WHERE dimension_id = ? AND object_type = ?",
                [dimension_id, object_type],
            )

    # =========================================================================
    # Phase 1 Enhancement: Category Rule Mapping
    # =========================================================================

    async def save_category_rule_mapping(
        self,
        dimension_id: str,
        dimension_value: str,
        rule_group_id: str,
        mapping_type: str = "applicable",
        override_rule_id: str | None = None,
        override_field: str | None = None,
        override_value: Any = None,
    ) -> None:
        """Save a category-to-rule mapping."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO category_rule_mapping
                    (dimension_id, dimension_value, rule_group_id, mapping_type,
                     override_rule_id, override_field, override_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    dimension_id, dimension_value, rule_group_id, mapping_type,
                    override_rule_id, override_field,
                    json.dumps(override_value) if override_value is not None else None,
                ],
            )

    async def get_category_rule_mappings(
        self,
        dimension_id: str | None = None,
        dimension_value: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get category rule mappings."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                conditions: list[str] = []
                params: list[Any] = []
                if dimension_id:
                    conditions.append("dimension_id = ?")
                    params.append(dimension_id)
                if dimension_value:
                    conditions.append("dimension_value = ?")
                    params.append(dimension_value)
                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                cursor = self._conn.execute(
                    f"SELECT dimension_id, dimension_value, rule_group_id, mapping_type, override_rule_id, override_field, override_value FROM category_rule_mapping {where}",
                    params,
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "dimension_id": r[0], "dimension_value": r[1],
                "rule_group_id": r[2], "mapping_type": r[3],
                "override_rule_id": r[4], "override_field": r[5],
                "override_value": json.loads(r[6]) if r[6] else None,
            }
            for r in rows
        ]

    async def delete_category_rule_mapping(
        self, dimension_id: str, dimension_value: str, rule_group_id: str,
    ) -> None:
        """Delete a category rule mapping."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM category_rule_mapping WHERE dimension_id = ? AND dimension_value = ? AND rule_group_id = ?",
                [dimension_id, dimension_value, rule_group_id],
            )

    # =========================================================================
    # Phase 1 Enhancement: Change Batches
    # =========================================================================

    async def create_change_batch(
        self,
        batch_id: str,
        dataset_id: str | None = None,
        entity_count: int | None = None,
    ) -> None:
        """Create a new change batch."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT INTO change_batches (batch_id, dataset_id, entity_count)
                VALUES (?, ?, ?)
                """,
                [batch_id, dataset_id, entity_count],
            )

    async def update_change_batch(
        self,
        batch_id: str,
        status: str | None = None,
        created_count: int | None = None,
        updated_count: int | None = None,
        deleted_count: int | None = None,
        unchanged_count: int | None = None,
    ) -> None:
        """Update a change batch."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        sets: list[str] = []
        params: list[Any] = []
        if status is not None:
            sets.append("status = ?")
            params.append(status)
        if created_count is not None:
            sets.append("created_count = ?")
            params.append(created_count)
        if updated_count is not None:
            sets.append("updated_count = ?")
            params.append(updated_count)
        if deleted_count is not None:
            sets.append("deleted_count = ?")
            params.append(deleted_count)
        if unchanged_count is not None:
            sets.append("unchanged_count = ?")
            params.append(unchanged_count)
        if not sets:
            return
        params.append(batch_id)
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                f"UPDATE change_batches SET {', '.join(sets)} WHERE batch_id = ?",
                params,
            )

    async def get_change_batch(self, batch_id: str) -> dict[str, Any] | None:
        """Get a change batch by ID."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT batch_id, dataset_id, status, entity_count, created_count, updated_count, deleted_count, unchanged_count, created_at FROM change_batches WHERE batch_id = ?",
                    [batch_id],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "batch_id": row[0], "dataset_id": row[1], "status": row[2],
            "entity_count": row[3], "created_count": row[4], "updated_count": row[5],
            "deleted_count": row[6], "unchanged_count": row[7],
            "created_at": str(row[8]),
        }

    async def list_change_batches(self, dataset_id: str | None = None) -> list[dict[str, Any]]:
        """List change batches."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if dataset_id:
                    cursor = self._conn.execute(
                        "SELECT batch_id, dataset_id, status, entity_count, created_count, updated_count, deleted_count, unchanged_count, created_at FROM change_batches WHERE dataset_id = ? ORDER BY created_at DESC",
                        [dataset_id],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT batch_id, dataset_id, status, entity_count, created_count, updated_count, deleted_count, unchanged_count, created_at FROM change_batches ORDER BY created_at DESC",
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "batch_id": r[0], "dataset_id": r[1], "status": r[2],
                "entity_count": r[3], "created_count": r[4], "updated_count": r[5],
                "deleted_count": r[6], "unchanged_count": r[7],
                "created_at": str(r[8]),
            }
            for r in rows
        ]

    # =========================================================================
    # Phase 1 Enhancement: Entity Changes
    # =========================================================================

    async def save_entity_changes(
        self,
        batch_id: str,
        entity_id: str,
        concept: str,
        change_type: str,
        field_changes: list[dict[str, Any]] | None = None,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
    ) -> None:
        """Save entity changes for a batch."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO entity_changes
                    (batch_id, entity_id, concept, change_type, field_changes, old_data, new_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    batch_id, entity_id, concept, change_type,
                    json.dumps(field_changes or []),
                    json.dumps(old_data) if old_data else None,
                    json.dumps(new_data) if new_data else None,
                ],
            )

    async def get_entity_changes(self, batch_id: str) -> list[dict[str, Any]]:
        """Get entity changes for a batch."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT batch_id, entity_id, concept, change_type, field_changes, old_data, new_data, created_at FROM entity_changes WHERE batch_id = ?",
                    [batch_id],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "batch_id": r[0], "entity_id": r[1], "concept": r[2],
                "change_type": r[3],
                "field_changes": json.loads(r[4]) if r[4] else [],
                "old_data": json.loads(r[5]) if r[5] else None,
                "new_data": json.loads(r[6]) if r[6] else None,
                "created_at": str(r[7]),
            }
            for r in rows
        ]

    # =========================================================================
    # Phase 1 Enhancement: Entity Versions
    # =========================================================================

    async def save_entity_version(
        self,
        entity_id: str,
        concept: str,
        version: int,
        data: dict[str, Any],
        updated_by: str = "system",
    ) -> None:
        """Save an entity version snapshot."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO entity_versions
                    (entity_id, concept, version, data, updated_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                [entity_id, concept, version, json.dumps(data), updated_by],
            )

    async def get_entity_version(
        self, entity_id: str, version: int | None = None,
    ) -> dict[str, Any] | None:
        """Get entity version(s)."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                if version is not None:
                    cursor = self._conn.execute(
                        "SELECT entity_id, concept, version, data, updated_at, updated_by FROM entity_versions WHERE entity_id = ? AND version = ?",
                        [entity_id, version],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT entity_id, concept, version, data, updated_at, updated_by FROM entity_versions WHERE entity_id = ? ORDER BY version DESC LIMIT 1",
                        [entity_id],
                    )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "entity_id": row[0], "concept": row[1], "version": row[2],
            "data": json.loads(row[3]), "updated_at": str(row[4]),
            "updated_by": row[5],
        }

    async def list_entity_versions(self, entity_id: str) -> list[dict[str, Any]]:
        """List all versions for an entity."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT entity_id, concept, version, data, updated_at, updated_by FROM entity_versions WHERE entity_id = ? ORDER BY version",
                    [entity_id],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "entity_id": r[0], "concept": r[1], "version": r[2],
                "data": json.loads(r[3]), "updated_at": str(r[4]),
                "updated_by": r[5],
            }
            for r in rows
        ]

    async def delete_entity_version(self, entity_id: str, version: int) -> None:
        """Delete a specific entity version."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM entity_versions WHERE entity_id = ? AND version = ?",
                [entity_id, version],
            )

    # =========================================================================
    # Phase 2: Rule Orchestration CRUD
    # =========================================================================

    async def save_rule_group(
        self,
        data: dict[str, Any],
        schema_id: str | None = None,
    ) -> None:
        """Save a rule group.

        Args:
            data: Rule group data dict with keys: id (optional, UUID generated if empty),
                  name, description, type, priority, applies_to, preconditions,
                  inputs, outputs, enabled, schema_id
            schema_id: Semantic space ID (required for semantic space isolation).
                      If not provided, uses '__global__' for backward compatibility.
                      The combination (name, schema_id) must be unique.
        """
        import uuid as uuid_module

        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        # Generate UUID if not provided
        rule_group_id = data.get("id") or str(uuid_module.uuid4())
        name = data["name"]
        # Use provided schema_id or default for backward compatibility
        effective_schema_id = schema_id if schema_id is not None else data.get("schema_id")
        if not effective_schema_id:
            effective_schema_id = "__global__"

        params = [
            rule_group_id,
            name,
            data.get("description", ""),
            data.get("type", "decision"),
            data.get("priority", 100),
            json.dumps(data.get("applies_to", {})),
            json.dumps(data.get("preconditions", [])),
            json.dumps(data.get("inputs", [])),
            json.dumps(data.get("outputs", [])),
            data.get("enabled", True),
            effective_schema_id,
        ]
        async with self._lock:
            def _upsert_group() -> None:
                # DuckDB does not support INSERT OR REPLACE with multiple constraints;
                # use DELETE + INSERT to handle both PK(id) and UNIQUE(name, schema_id).
                self._conn.execute(
                    "DELETE FROM rule_groups WHERE id = ? OR (name = ? AND schema_id = ?)",
                    [rule_group_id, name, effective_schema_id],
                )
                self._conn.execute(
                    """
                    INSERT INTO rule_groups
                        (id, name, description, type, priority, applies_to, preconditions,
                         inputs, outputs, enabled, schema_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
                    """,
                    params,
                )
            await asyncio.to_thread(_upsert_group)

    async def get_rule_group(
        self,
        identifier: str,
        schema_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get a rule group by id or (name, schema_id) combination.

        Args:
            identifier: The rule group's UUID (id) or business name
            schema_id: When identifier is a name, this specifies the semantic space
                      for lookup. If not provided and identifier is a name,
                      looks up in '__global__' space for backward compatibility.
        """
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        # Determine if identifier is UUID (id) or name based on hyphen pattern
        # UUIDs have the pattern: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        is_uuid = "-" in identifier and len(identifier) == 36

        async with self._lock:
            def _fetch() -> tuple | None:
                if is_uuid:
                    cursor = self._conn.execute(
                        """
                        SELECT id, name, description, type, priority, applies_to,
                               preconditions, inputs, outputs, enabled, schema_id,
                               created_at, updated_at
                        FROM rule_groups WHERE id = ?
                        """,
                        [identifier],
                    )
                else:
                    # Name-based lookup: use schema_id if provided, otherwise '__global__'
                    effective_schema_id = schema_id if schema_id else "__global__"
                    cursor = self._conn.execute(
                        """
                        SELECT id, name, description, type, priority, applies_to,
                               preconditions, inputs, outputs, enabled, schema_id,
                               created_at, updated_at
                        FROM rule_groups WHERE name = ? AND schema_id = ?
                        """,
                        [identifier, effective_schema_id],
                    )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "type": row[3],
            "priority": row[4],
            "applies_to": json.loads(row[5]) if row[5] else {},
            "preconditions": json.loads(row[6]) if row[6] else [],
            "inputs": json.loads(row[7]) if row[7] else [],
            "outputs": json.loads(row[8]) if row[8] else [],
            "enabled": row[9],
            "schema_id": row[10],
            "created_at": str(row[11]) if row[11] else "",
            "updated_at": str(row[12]) if row[12] else "",
        }

    async def list_rule_groups(
        self,
        schema_id: str | None = None,
        enabled: bool | None = None,
    ) -> list[dict[str, Any]]:
        """List rule groups with optional filters.

        Args:
            schema_id: Filter by semantic space ID. If not provided, lists all spaces.
            enabled: Optional filter by enabled status
        """
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                conditions = []
                params: list[Any] = []
                if schema_id is not None:
                    conditions.append("schema_id = ?")
                    params.append(schema_id)
                if enabled is not None:
                    conditions.append("enabled = ?")
                    params.append(enabled)
                where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                cursor = self._conn.execute(
                    f"""
                    SELECT id, name, description, type, priority, applies_to,
                           preconditions, inputs, outputs, enabled, schema_id,
                           created_at, updated_at
                    FROM rule_groups {where}
                    ORDER BY priority DESC, name
                    """,
                    params,
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "type": r[3],
                "priority": r[4],
                "applies_to": json.loads(r[5]) if r[5] else {},
                "preconditions": json.loads(r[6]) if r[6] else [],
                "inputs": json.loads(r[7]) if r[7] else [],
                "outputs": json.loads(r[8]) if r[8] else [],
                "enabled": r[9],
                "schema_id": r[10],
                "created_at": str(r[11]) if r[11] else "",
                "updated_at": str(r[12]) if r[12] else "",
            }
            for r in rows
        ]

    async def delete_rule_group(
        self,
        identifier: str,
        schema_id: str | None = None,
    ) -> None:
        """Delete a rule group and its steps by id or (name, schema_id).

        Args:
            identifier: The rule group's UUID (id) or business name
            schema_id: When identifier is a name, this specifies the semantic space.
                      If not provided and identifier is a name, uses '__global__'.
        """
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None

        # Determine if identifier is UUID (id) or name
        is_uuid = "-" in identifier and len(identifier) == 36

        async with self._lock:
            # First get the name for deleting steps (steps reference rule_group by name)
            if is_uuid:
                def _get_name() -> str | None:
                    cursor = self._conn.execute(
                        "SELECT name FROM rule_groups WHERE id = ?",
                        [identifier],
                    )
                    row = cursor.fetchone()
                    return row[0] if row else None
                name = await asyncio.to_thread(_get_name)
            else:
                name = identifier

            if name:
                # Delete steps using the exact rule_group name
                await asyncio.to_thread(
                    self._conn.execute,
                    "DELETE FROM rule_steps WHERE rule_group = ?",
                    [name],
                )

            # Delete from rule_groups using appropriate column
            if is_uuid:
                await asyncio.to_thread(
                    self._conn.execute,
                    "DELETE FROM rule_groups WHERE id = ?",
                    [identifier],
                )
            else:
                effective_schema_id = schema_id if schema_id else "__global__"
                await asyncio.to_thread(
                    self._conn.execute,
                    "DELETE FROM rule_groups WHERE name = ? AND schema_id = ?",
                    [name, effective_schema_id],
                )

    async def save_rule_step(self, rule_group: str, data: dict[str, Any]) -> None:
        """Save a rule step.

        Args:
            rule_group: Parent rule group name
            data: Rule step data dict with keys: id, name, step_order, when_clause,
                  then_clause, else_clause, enabled, description, tags
        """
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        step_params = [
            data["id"],
            rule_group,
            data.get("step_order", data.get("order", 0)),
            data.get("name", ""),
            json.dumps(data.get("when", data.get("when_clause", {}))),
            json.dumps(data.get("then", data.get("then_clause", {}))),
            json.dumps(data.get("else", data.get("else_clause"))) if data.get("else") else None,
            data.get("enabled", True),
            data.get("description", ""),
            json.dumps(data.get("tags", [])),
        ]
        async with self._lock:
            def _upsert_step() -> None:
                # DuckDB ON CONFLICT requires explicit target; use DELETE + INSERT.
                self._conn.execute(
                    "DELETE FROM rule_steps WHERE rule_group = ? AND id = ?",
                    [rule_group, data["id"]],
                )
                self._conn.execute(
                    """
                    INSERT INTO rule_steps
                        (id, rule_group, step_order, name, when_clause, then_clause,
                         else_clause, enabled, description, tags, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
                    """,
                    step_params,
                )
            await asyncio.to_thread(_upsert_step)

    async def get_rule_step(self, rule_group: str, step_id: str) -> dict[str, Any] | None:
        """Get a rule step by ID."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    """
                    SELECT id, rule_group, step_order, name, when_clause, then_clause,
                           else_clause, enabled, description, tags, created_at, updated_at
                    FROM rule_steps WHERE rule_group = ? AND id = ?
                    """,
                    [rule_group, step_id],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "id": row[0],
            "rule_group": row[1],
            "step_order": row[2],
            "name": row[3],
            "when": json.loads(row[4]) if row[4] else {},
            "then": json.loads(row[5]) if row[5] else {},
            "else": json.loads(row[6]) if row[6] else None,
            "enabled": row[7],
            "description": row[8],
            "tags": json.loads(row[9]) if row[9] else [],
            "created_at": str(row[10]) if row[10] else "",
            "updated_at": str(row[11]) if row[11] else "",
        }

    async def list_rule_steps(self, rule_group: str) -> list[dict[str, Any]]:
        """List all rule steps for a rule group."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    """
                    SELECT id, rule_group, step_order, name, when_clause, then_clause,
                           else_clause, enabled, description, tags, created_at, updated_at
                    FROM rule_steps WHERE rule_group = ?
                    ORDER BY step_order
                    """,
                    [rule_group],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "id": r[0],
                "rule_group": r[1],
                "step_order": r[2],
                "name": r[3],
                "when": json.loads(r[4]) if r[4] else {},
                "then": json.loads(r[5]) if r[5] else {},
                "else": json.loads(r[6]) if r[6] else None,
                "enabled": r[7],
                "description": r[8],
                "tags": json.loads(r[9]) if r[9] else [],
                "created_at": str(r[10]) if r[10] else "",
                "updated_at": str(r[11]) if r[11] else "",
            }
            for r in rows
        ]

    async def delete_rule_step(self, rule_group: str, step_id: str) -> None:
        """Delete a rule step."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM rule_steps WHERE rule_group = ? AND id = ?",
                [rule_group, step_id],
            )

    async def reorder_rule_steps(self, rule_group: str, step_ids: list[str]) -> None:
        """Reorder rule steps.

        Args:
            rule_group: Rule group name
            step_ids: List of step IDs in new order
        """
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            for order, step_id in enumerate(step_ids):
                await asyncio.to_thread(
                    self._conn.execute,
                    "UPDATE rule_steps SET step_order = ? WHERE rule_group = ? AND id = ?",
                    [order, rule_group, step_id],
                )

    async def save_metric_extension(
        self,
        metric_name: str,
        value_domain: dict[str, Any] | None = None,
        thresholds: dict[str, Any] | None = None,
        color: str | None = None,
        unit: str | None = None,
    ) -> None:
        """Save metric extension data."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO metric_extensions
                    (metric_name, value_domain, thresholds, color, unit, updated_at)
                VALUES (?, ?, ?, ?, ?, NOW())
                """,
                [
                    metric_name,
                    json.dumps(value_domain) if value_domain else None,
                    json.dumps(thresholds) if thresholds else None,
                    color,
                    unit,
                ],
            )

    async def get_metric_extension(
        self, metric_name: str
    ) -> dict[str, Any] | None:
        """Get metric extension data."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    """
                    SELECT metric_name, value_domain, thresholds, color, unit, updated_at
                    FROM metric_extensions WHERE metric_name = ?
                    """,
                    [metric_name],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "metric_name": row[0],
            "value_domain": json.loads(row[1]) if row[1] else None,
            "thresholds": json.loads(row[2]) if row[2] else None,
            "color": row[3],
            "unit": row[4],
            "updated_at": str(row[5]) if row[5] else "",
        }

    async def list_metric_extensions(
        self,
    ) -> list[dict[str, Any]]:
        """List all metric extensions."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    """
                    SELECT metric_name, value_domain, thresholds, color, unit, updated_at
                    FROM metric_extensions
                    """,
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "metric_name": r[0],
                "value_domain": json.loads(r[1]) if r[1] else None,
                "thresholds": json.loads(r[2]) if r[2] else None,
                "color": r[3],
                "unit": r[4],
                "updated_at": str(r[5]) if r[5] else "",
            }
            for r in rows
        ]

    async def delete_metric_extension(self, metric_name: str) -> None:
        """Delete a metric extension."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM metric_extensions WHERE metric_name = ?",
                [metric_name],
            )

    async def save_operator_registry(self, data: dict[str, Any]) -> None:
        """Save operator registry entry."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                """
                INSERT OR REPLACE INTO operator_registry
                    (name, display_name, description, category, param_schema,
                     input_types, output_types, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    data["name"],
                    data.get("display_name", data["name"]),
                    data.get("description", ""),
                    data.get("category", "compute"),
                    json.dumps(data.get("param_schema", {})),
                    json.dumps(data.get("input_types", [])),
                    json.dumps(data.get("output_types", [])),
                    data.get("enabled", True),
                ],
            )

    async def get_operator_registry(self, name: str) -> dict[str, Any] | None:
        """Get operator registry entry."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    """
                    SELECT name, display_name, description, category, param_schema,
                           input_types, output_types, enabled
                    FROM operator_registry WHERE name = ?
                    """,
                    [name],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "name": row[0],
            "display_name": row[1],
            "description": row[2],
            "category": row[3],
            "param_schema": json.loads(row[4]) if row[4] else {},
            "input_types": json.loads(row[5]) if row[5] else [],
            "output_types": json.loads(row[6]) if row[6] else [],
            "enabled": row[7],
        }

    async def list_operator_registry(self) -> list[dict[str, Any]]:
        """List all operator registry entries."""
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    """
                    SELECT name, display_name, description, category, param_schema,
                           input_types, output_types, enabled
                    FROM operator_registry ORDER BY name
                    """,
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "name": r[0],
                "display_name": r[1],
                "description": r[2],
                "category": r[3],
                "param_schema": json.loads(r[4]) if r[4] else {},
                "input_types": json.loads(r[5]) if r[5] else [],
                "output_types": json.loads(r[6]) if r[6] else [],
                "enabled": r[7],
            }
            for r in rows
        ]

    async def close(self) -> None:
        if self._conn is not None:
            if self._lock is not None:
                async with self._lock:
                    await asyncio.to_thread(self._conn.close)
            else:
                await asyncio.to_thread(self._conn.close)
            self._conn = None

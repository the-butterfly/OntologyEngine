# ontology_engine/storage/sqlite/store.py
"""SQLite-based storage backend replacing DuckDB.

Implements the full StorageBackend interface using SQLite with WAL mode
for concurrent read/write support. All JSON columns are stored as TEXT
with json.loads/dumps for serialization.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from typing import Any

from ontology_engine.storage.base import (
    CategoryTag,
    EntityInstance,
    FeedbackRecord,
    KnowledgeFragment,
    RelationInstance,
    StorageBackend,
    StorageError,
)


class SQLiteStorage(StorageBackend):
    """SQLite storage backend with WAL mode.

    Replaces DuckDBStorage with equivalent functionality.
    All tables use TEXT for JSON data with Python-side serialization.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock: asyncio.Lock | None = None

    def _ensure_initialized(self) -> None:
        if self._conn is None:
            raise StorageError("Storage not initialized. Call initialize() first.")

    async def initialize(self) -> None:
        if self._conn is not None:
            return
        self._lock = asyncio.Lock()
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        if self._db_path != ":memory:":
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA cache_size=-64000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables_sync()

    async def _create_tables(self) -> None:
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(self._create_tables_sync)

    def _create_tables_sync(self) -> None:
        assert self._conn is not None
        c = self._conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                concept TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                data TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                confidence REAL DEFAULT 1.0,
                source_pipeline TEXT,
                source_content_hash TEXT,
                feedback_weight REAL DEFAULT 0.5,
                domain_id TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (concept, entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_entities_concept ON entities(concept);

            CREATE TABLE IF NOT EXISTS relations (
                id TEXT,
                relation_type TEXT NOT NULL,
                from_entity_id TEXT NOT NULL,
                to_entity_id TEXT NOT NULL,
                data TEXT,
                edge_text TEXT,
                weight REAL DEFAULT 1.0,
                valid_from TEXT,
                valid_to TEXT,
                confidence REAL DEFAULT 1.0,
                source_pipeline TEXT,
                source_content_hash TEXT,
                PRIMARY KEY (relation_type, from_entity_id, to_entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_relations_from ON relations(from_entity_id);

            CREATE TABLE IF NOT EXISTS computed_metrics (
                entity_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value TEXT NOT NULL,
                computed_at TEXT NOT NULL DEFAULT (datetime('now')),
                valid_from TEXT,
                valid_to TEXT,
                computed_by TEXT,
                computation_snapshot TEXT,
                PRIMARY KEY (entity_id, metric_name)
            );

            CREATE TABLE IF NOT EXISTS category_tags (
                entity_id TEXT NOT NULL,
                dimension_name TEXT NOT NULL,
                value_code TEXT NOT NULL,
                assigned_at TEXT,
                assigned_by TEXT DEFAULT 'rule',
                confidence REAL DEFAULT 1.0,
                PRIMARY KEY (entity_id, dimension_name, value_code)
            );

            CREATE TABLE IF NOT EXISTS rule_execution_log (
                entity_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                result TEXT NOT NULL,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                scope TEXT,
                source_type TEXT,
                version TEXT DEFAULT '1.0.0',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS entity_dataset_membership (
                entity_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                concept TEXT NOT NULL,
                imported_at TEXT NOT NULL DEFAULT (datetime('now')),
                source_line INTEGER,
                is_primary INTEGER DEFAULT 0,
                PRIMARY KEY (entity_id, dataset_id)
            );

            CREATE TABLE IF NOT EXISTS dataset_snapshots (
                snapshot_id TEXT NOT NULL PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                entity_count INTEGER,
                relation_count INTEGER,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS dimension_applicability (
                dimension_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                required INTEGER DEFAULT 0,
                auto_categorize INTEGER DEFAULT 1,
                source_attribute TEXT,
                PRIMARY KEY (dimension_id, object_type)
            );

            CREATE TABLE IF NOT EXISTS category_rule_mapping (
                dimension_id TEXT NOT NULL,
                dimension_value TEXT NOT NULL,
                rule_group_id TEXT NOT NULL,
                mapping_type TEXT NOT NULL DEFAULT 'applicable',
                override_rule_id TEXT,
                override_field TEXT,
                override_value TEXT,
                PRIMARY KEY (dimension_id, dimension_value, rule_group_id)
            );

            CREATE TABLE IF NOT EXISTS change_batches (
                batch_id TEXT NOT NULL PRIMARY KEY,
                dataset_id TEXT,
                status TEXT DEFAULT 'pending',
                entity_count INTEGER,
                created_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                deleted_count INTEGER DEFAULT 0,
                unchanged_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS entity_changes (
                batch_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                concept TEXT NOT NULL,
                change_type TEXT NOT NULL,
                field_changes TEXT,
                old_data TEXT,
                new_data TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (batch_id, entity_id)
            );

            CREATE TABLE IF NOT EXISTS entity_versions (
                entity_id TEXT NOT NULL,
                concept TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                data TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_by TEXT DEFAULT 'system',
                PRIMARY KEY (entity_id, version)
            );

            CREATE TABLE IF NOT EXISTS rule_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                type TEXT NOT NULL,
                priority INTEGER DEFAULT 100,
                applies_to TEXT,
                preconditions TEXT,
                inputs TEXT,
                outputs TEXT,
                enabled INTEGER DEFAULT 1,
                schema_id TEXT,
                source_declaration_id TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (name, schema_id)
            );

            CREATE TABLE IF NOT EXISTS rule_steps (
                id TEXT NOT NULL,
                rule_group TEXT NOT NULL,
                step_order INTEGER NOT NULL,
                name TEXT,
                when_clause TEXT,
                then_clause TEXT,
                else_clause TEXT,
                enabled INTEGER DEFAULT 1,
                description TEXT,
                tags TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (rule_group, id)
            );

            CREATE TABLE IF NOT EXISTS metric_extensions (
                metric_name TEXT PRIMARY KEY,
                value_domain TEXT,
                thresholds TEXT,
                color TEXT,
                unit TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS operator_registry (
                name TEXT PRIMARY KEY,
                display_name TEXT,
                description TEXT,
                category TEXT,
                param_schema TEXT,
                input_types TEXT,
                output_types TEXT,
                enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS feedback_records (
                record_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                metric_name TEXT,
                feedback_type TEXT NOT NULL DEFAULT 'confirm',
                value REAL NOT NULL DEFAULT 1.0,
                previous_weight REAL NOT NULL DEFAULT 1.0,
                updated_weight REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'user',
                text_feedback TEXT,
                applied INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_entity ON feedback_records(entity_id);

            CREATE TABLE IF NOT EXISTS knowledge_fragments (
                id TEXT PRIMARY KEY,
                dataset_id TEXT,
                document_id TEXT,
                chunk_index INTEGER,
                offset_start INTEGER,
                offset_end INTEGER,
                text TEXT NOT NULL,
                vector_id TEXT,
                metadata TEXT,
                extraction_status TEXT NOT NULL DEFAULT 'pending',
                content_hash TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_kf_dataset ON knowledge_fragments(dataset_id);
            CREATE INDEX IF NOT EXISTS idx_kf_status ON knowledge_fragments(extraction_status);
        """)

    async def close(self) -> None:
        if self._conn is not None:
            conn = self._conn
            self._conn = None
            await asyncio.to_thread(conn.close)

    # =========================================================================
    # Entity CRUD
    # =========================================================================

    async def save_entity(self, entity: EntityInstance) -> str:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO entities (concept, entity_id, data, valid_from, valid_to, confidence, source_pipeline, source_content_hash, feedback_weight, domain_id, created_at, updated_at) "
                "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM entities WHERE concept = ? AND entity_id = ?), datetime('now')), datetime('now')",
                [
                    entity._fact_object, entity.entity_id, json.dumps(entity.data),
                    entity.valid_from.isoformat() if entity.valid_from else None,
                    entity.valid_to.isoformat() if entity.valid_to else None,
                    entity.confidence,
                    entity.source_pipeline,
                    entity.source_content_hash,
                    entity.feedback_weight,
                    entity.domain_id,
                    entity._fact_object, entity.entity_id,
                ],
            )
            self._conn.commit()
        return entity.entity_id

    async def get_entity(self, fact_object: str, entity_id: str) -> EntityInstance | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT data, valid_from, valid_to, confidence, source_pipeline, source_content_hash, feedback_weight, domain_id, created_at, updated_at FROM entities WHERE concept = ? AND entity_id = ?",
                    [fact_object, entity_id],
                )
                return cursor.fetchone()
            result = await asyncio.to_thread(_fetch)
        if result is None:
            return None
        from datetime import datetime
        return EntityInstance(
            _fact_object=fact_object, entity_id=entity_id,
            data=json.loads(result[0]),
            valid_from=datetime.fromisoformat(result[1]) if result[1] else None,
            valid_to=datetime.fromisoformat(result[2]) if result[2] else None,
            confidence=result[3] or 1.0,
            source_pipeline=result[4],
            source_content_hash=result[5],
            feedback_weight=result[6] if result[6] is not None else 0.5,
            domain_id=result[7],
            created_at=datetime.fromisoformat(result[8]) if result[8] else None,
            updated_at=datetime.fromisoformat(result[9]) if result[9] else None,
        )

    async def get_entity_by_id(self, entity_id: str) -> EntityInstance | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT concept, data, valid_from, valid_to, confidence, source_pipeline, source_content_hash, feedback_weight, domain_id, created_at, updated_at FROM entities WHERE entity_id = ?",
                    [entity_id],
                )
                return cursor.fetchone()
            result = await asyncio.to_thread(_fetch)
        if result is None:
            return None
        from datetime import datetime
        return EntityInstance(
            _fact_object=result[0], entity_id=entity_id,
            data=json.loads(result[1]),
            valid_from=datetime.fromisoformat(result[2]) if result[2] else None,
            valid_to=datetime.fromisoformat(result[3]) if result[3] else None,
            confidence=result[4] or 1.0,
            source_pipeline=result[5],
            source_content_hash=result[6],
            feedback_weight=result[7] if result[7] is not None else 0.5,
            domain_id=result[8],
            created_at=datetime.fromisoformat(result[9]) if result[9] else None,
            updated_at=datetime.fromisoformat(result[10]) if result[10] else None,
        )

    async def query_entities(
        self,
        fact_object: str | None,
        filters: dict[str, Any] | None = None,
    ) -> list[EntityInstance]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if fact_object:
                    cursor = self._conn.execute(
                        "SELECT concept, entity_id, data, valid_from, valid_to, confidence, source_pipeline, source_content_hash, feedback_weight, domain_id, created_at, updated_at FROM entities WHERE concept = ? ORDER BY entity_id",
                        [fact_object],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT concept, entity_id, data, valid_from, valid_to, confidence, source_pipeline, source_content_hash, feedback_weight, domain_id, created_at, updated_at FROM entities ORDER BY concept, entity_id"
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        from datetime import datetime
        entities = [
            EntityInstance(
                _fact_object=row[0],
                entity_id=row[1],
                data=json.loads(row[2]),
                valid_from=datetime.fromisoformat(row[3]) if row[3] else None,
                valid_to=datetime.fromisoformat(row[4]) if row[4] else None,
                confidence=row[5] or 1.0,
                source_pipeline=row[6],
                source_content_hash=row[7],
                feedback_weight=row[8] if row[8] is not None else 0.5,
                domain_id=row[9],
                created_at=datetime.fromisoformat(row[10]) if row[10] else None,
                updated_at=datetime.fromisoformat(row[11]) if row[11] else None,
            )
            for row in rows
        ]
        if filters:
            entities = [e for e in entities if _matches_filters(e.data, filters)]
        return entities

    async def delete_entity(self, fact_object: str, entity_id: str) -> bool:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            cursor = await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM entities WHERE concept = ? AND entity_id = ?",
                [fact_object, entity_id],
            )
            self._conn.commit()
        return cursor.rowcount > 0

    async def save_category_tag(self, tag: CategoryTag) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO category_tags (entity_id, dimension_name, value_code, assigned_at, assigned_by, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    tag.entity_id,
                    tag.dimension_name,
                    tag.value_code,
                    tag.assigned_at.isoformat() if tag.assigned_at else None,
                    tag.assigned_by,
                    tag.confidence,
                ],
            )
            self._conn.commit()

    async def get_category_tags(
        self, entity_id: str, dimension_name: str | None = None
    ) -> list[CategoryTag]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if dimension_name:
                    cursor = self._conn.execute(
                        "SELECT entity_id, dimension_name, value_code, assigned_at, assigned_by, confidence FROM category_tags WHERE entity_id = ? AND dimension_name = ?",
                        [entity_id, dimension_name],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT entity_id, dimension_name, value_code, assigned_at, assigned_by, confidence FROM category_tags WHERE entity_id = ?",
                        [entity_id],
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        from datetime import datetime
        return [
            CategoryTag(
                entity_id=row[0],
                dimension_name=row[1],
                value_code=row[2],
                assigned_at=datetime.fromisoformat(row[3]) if row[3] else None,
                assigned_by=row[4] or "rule",
                confidence=row[5] if row[5] is not None else 1.0,
            )
            for row in rows
        ]

    async def delete_category_tag(
        self, entity_id: str, dimension_name: str, value_code: str
    ) -> bool:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            cursor = await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM category_tags WHERE entity_id = ? AND dimension_name = ? AND value_code = ?",
                [entity_id, dimension_name, value_code],
            )
            self._conn.commit()
        return cursor.rowcount > 0

    # =========================================================================
    # Relation CRUD
    # =========================================================================

    async def save_relation(self, relation: RelationInstance) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO relations (id, relation_type, from_entity_id, to_entity_id, data, edge_text, weight, valid_from, valid_to, confidence, source_pipeline, source_content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    relation.id,
                    relation.relation_name, relation.from_entity_id, relation.to_entity_id,
                    json.dumps(relation.data),
                    relation.edge_text, relation.weight,
                    relation.valid_from.isoformat() if relation.valid_from else None,
                    relation.valid_to.isoformat() if relation.valid_to else None,
                    relation.confidence, relation.source_pipeline,
                    relation.source_content_hash,
                ],
            )
            self._conn.commit()

    async def get_relations(
        self,
        from_entity_id: str,
        relation_name: str | None = None,
    ) -> list[RelationInstance]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if relation_name:
                    cursor = self._conn.execute(
                        "SELECT relation_type, to_entity_id, data, id, edge_text, weight, valid_from, valid_to, confidence, source_pipeline, source_content_hash FROM relations WHERE from_entity_id = ? AND relation_type = ?",
                        [from_entity_id, relation_name],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT relation_type, to_entity_id, data, id, edge_text, weight, valid_from, valid_to, confidence, source_pipeline, source_content_hash FROM relations WHERE from_entity_id = ?",
                        [from_entity_id],
                    )
                return cursor.fetchall()
            results = await asyncio.to_thread(_fetch)
        from datetime import datetime
        return [
            RelationInstance(
                relation_name=row[0],
                from_entity_id=from_entity_id,
                to_entity_id=row[1],
                data=json.loads(row[2]) if row[2] else {},
                id=row[3],
                edge_text=row[4],
                weight=row[5] or 1.0,
                valid_from=datetime.fromisoformat(row[6]) if row[6] else None,
                valid_to=datetime.fromisoformat(row[7]) if row[7] else None,
                confidence=row[8] or 1.0,
                source_pipeline=row[9],
                source_content_hash=row[10],
            )
            for row in results
        ]

    async def get_neighbors(
        self,
        entity_id: str,
        relation_name: str,
        direction: str = "outgoing",
        as_of: str | None = None,
        include_history: bool = False,
    ) -> list[tuple[EntityInstance, RelationInstance]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple[str, str, str, str, str, str, str | None]]:
                results: list[tuple[str, str, str, str, str, str, str | None]] = []
                temporal_where = ""
                temporal_params: list[str] = []
                if as_of and not include_history:
                    temporal_where = " AND (e.data NOT LIKE '%valid_from%' OR (json_extract(e.data, '$.valid_from') IS NULL OR json_extract(e.data, '$.valid_from') <= ?)) AND (json_extract(e.data, '$.valid_to') IS NULL OR json_extract(e.data, '$.valid_to') > ?)"
                    temporal_params = [as_of, as_of]

                if direction in ("outgoing", "both"):
                    cursor = self._conn.execute(
                        f"""
                        SELECT r.relation_type, r.from_entity_id, r.to_entity_id,
                               e.concept, e.entity_id, e.data, r.data
                        FROM relations r
                        JOIN entities e ON r.to_entity_id = e.entity_id
                        WHERE r.from_entity_id = ? AND r.relation_type = ?{temporal_where}
                        """,
                        [entity_id, relation_name] + temporal_params,
                    )
                    results.extend(cursor.fetchall())
                if direction in ("incoming", "both"):
                    cursor = self._conn.execute(
                        f"""
                        SELECT r.relation_type, r.from_entity_id, r.to_entity_id,
                               e.concept, e.entity_id, e.data, r.data
                        FROM relations r
                        JOIN entities e ON r.from_entity_id = e.entity_id
                        WHERE r.to_entity_id = ? AND r.relation_type = ?{temporal_where}
                        """,
                        [entity_id, relation_name] + temporal_params,
                    )
                    results.extend(cursor.fetchall())
                return results
            rows = await asyncio.to_thread(_fetch)
        neighbors: list[tuple[EntityInstance, RelationInstance]] = []
        for row in rows:
            entity = EntityInstance(
                _fact_object=row[3],
                entity_id=row[4],
                data=json.loads(row[5]),
            )
            relation = RelationInstance(
                relation_name=row[0],
                from_entity_id=row[1],
                to_entity_id=row[2],
                data=json.loads(row[6]) if row[6] else {},
            )
            neighbors.append((entity, relation))
        return neighbors

    # =========================================================================
    # Metrics
    # =========================================================================

    async def save_metric(self, entity_id: str, metric_name: str, value: Any) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO computed_metrics (entity_id, metric_name, value) VALUES (?, ?, ?)",
                [entity_id, metric_name, json.dumps(value)],
            )
            self._conn.commit()

    async def get_metric(self, entity_id: str, metric_name: str) -> Any | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple[str] | None:
                cursor = self._conn.execute(
                    "SELECT value FROM computed_metrics WHERE entity_id = ? AND metric_name = ?",
                    [entity_id, metric_name],
                )
                return cursor.fetchone()
            result = await asyncio.to_thread(_fetch)
        if result is None:
            return None
        return json.loads(result[0])

    # =========================================================================
    # Category Tags (legacy dict-based, delegates to new CategoryTag methods)
    # =========================================================================

    async def save_category_tags(self, entity_id: str, tags: dict[str, str]) -> None:
        from datetime import datetime, timezone
        for dim_name, value_code in tags.items():
            tag = CategoryTag(
                entity_id=entity_id,
                dimension_name=dim_name,
                value_code=value_code,
                assigned_at=datetime.now(timezone.utc),
                assigned_by="rule",
                confidence=1.0,
            )
            await self.save_category_tag(tag)

    async def get_category_tags_dict(self, entity_id: str) -> dict[str, str] | None:
        tags = await self.get_category_tags(entity_id)
        if not tags:
            return None
        return {t.dimension_name: t.value_code for t in tags}

    # =========================================================================
    # Rule Execution Log
    # =========================================================================

    async def log_rule_execution(self, entity_id: str, rule_id: str, result: str) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT INTO rule_execution_log (entity_id, rule_id, result) VALUES (?, ?, ?)",
                [entity_id, rule_id, result],
            )
            self._conn.commit()

    async def get_rule_execution_log(
        self,
        entity_id: str,
        rule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if rule_id:
                    cursor = self._conn.execute(
                        "SELECT entity_id, rule_id, result, executed_at FROM rule_execution_log WHERE entity_id = ? AND rule_id = ? ORDER BY executed_at DESC",
                        [entity_id, rule_id],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT entity_id, rule_id, result, executed_at FROM rule_execution_log WHERE entity_id = ? ORDER BY executed_at DESC",
                        [entity_id],
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {"entity_id": r[0], "rule_id": r[1], "result": r[2], "executed_at": str(r[3])}
            for r in rows
        ]

    # =========================================================================
    # Feedback & Knowledge Fragments
    # =========================================================================

    async def save_feedback(self, feedback: FeedbackRecord) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO feedback_records (record_id, entity_id, metric_name, feedback_type, value, previous_weight, updated_weight, source, text_feedback, applied, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    feedback.record_id, feedback.entity_id, feedback.metric_name,
                    feedback.feedback_type, feedback.value,
                    feedback.previous_weight, feedback.updated_weight,
                    feedback.source, feedback.text_feedback,
                    int(feedback.applied),
                    feedback.created_at.isoformat() if feedback.created_at else None,
                ],
            )
            self._conn.commit()

    async def get_feedback(
        self,
        entity_id: str,
        metric_name: str | None = None,
    ) -> list[FeedbackRecord]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if metric_name:
                    cursor = self._conn.execute(
                        "SELECT record_id, entity_id, metric_name, feedback_type, value, previous_weight, updated_weight, source, text_feedback, applied, created_at FROM feedback_records WHERE entity_id = ? AND metric_name = ? ORDER BY created_at DESC",
                        [entity_id, metric_name],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT record_id, entity_id, metric_name, feedback_type, value, previous_weight, updated_weight, source, text_feedback, applied, created_at FROM feedback_records WHERE entity_id = ? ORDER BY created_at DESC",
                        [entity_id],
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        from datetime import datetime
        return [
            FeedbackRecord(
                record_id=r[0], entity_id=r[1], metric_name=r[2],
                feedback_type=r[3], value=r[4],
                previous_weight=r[5], updated_weight=r[6],
                source=r[7], text_feedback=r[8],
                applied=bool(r[9]),
                created_at=datetime.fromisoformat(r[10]) if r[10] else None,
            )
            for r in rows
        ]

    async def save_knowledge_fragment(self, fragment: KnowledgeFragment) -> str:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        if not fragment.id:
            fragment.id = str(uuid.uuid4())
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        created_at_val = fragment.created_at.isoformat() if fragment.created_at else now_iso
        updated_at_val = fragment.updated_at.isoformat() if fragment.updated_at else now_iso
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO knowledge_fragments (id, dataset_id, document_id, chunk_index, offset_start, offset_end, text, vector_id, metadata, extraction_status, content_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    fragment.id, fragment.dataset_id, fragment.document_id,
                    fragment.chunk_index, fragment.offset_start, fragment.offset_end,
                    fragment.text, fragment.vector_id,
                    json.dumps(fragment.metadata) if fragment.metadata else None,
                    fragment.extraction_status, fragment.content_hash,
                    created_at_val,
                    updated_at_val,
                ],
            )
            self._conn.commit()
        return fragment.id

    async def get_knowledge_fragment(self, fragment_id: str) -> KnowledgeFragment | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT id, dataset_id, document_id, chunk_index, offset_start, offset_end, text, vector_id, metadata, extraction_status, content_hash, created_at, updated_at FROM knowledge_fragments WHERE id = ?",
                    [fragment_id],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        from datetime import datetime
        return KnowledgeFragment(
            id=row[0], dataset_id=row[1], document_id=row[2],
            chunk_index=row[3], offset_start=row[4], offset_end=row[5],
            text=row[6], vector_id=row[7],
            metadata=json.loads(row[8]) if row[8] else {},
            extraction_status=row[9], content_hash=row[10],
            created_at=datetime.fromisoformat(row[11]) if row[11] else None,
            updated_at=datetime.fromisoformat(row[12]) if row[12] else None,
        )

    async def list_knowledge_fragments(
        self,
        dataset_id: str | None = None,
        extraction_status: str | None = None,
    ) -> list[KnowledgeFragment]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                conditions = []
                params: list[Any] = []
                if dataset_id:
                    conditions.append("dataset_id = ?")
                    params.append(dataset_id)
                if extraction_status:
                    conditions.append("extraction_status = ?")
                    params.append(extraction_status)
                where = " WHERE " + " AND ".join(conditions) if conditions else ""
                cursor = self._conn.execute(
                    f"SELECT id, dataset_id, document_id, chunk_index, offset_start, offset_end, text, vector_id, metadata, extraction_status, content_hash, created_at, updated_at FROM knowledge_fragments{where} ORDER BY id",
                    params,
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        from datetime import datetime
        return [
            KnowledgeFragment(
                id=r[0], dataset_id=r[1], document_id=r[2],
                chunk_index=r[3], offset_start=r[4], offset_end=r[5],
                text=r[6], vector_id=r[7],
                metadata=json.loads(r[8]) if r[8] else {},
                extraction_status=r[9], content_hash=r[10],
                created_at=datetime.fromisoformat(r[11]) if r[11] else None,
                updated_at=datetime.fromisoformat(r[12]) if r[12] else None,
            )
            for r in rows
        ]

    # =========================================================================
    # Dataset Management
    # =========================================================================

    async def create_dataset(
        self,
        dataset_id: str,
        name: str,
        scope: dict[str, Any] | None = None,
        source_type: str = "manual",
        description: str | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT INTO datasets (dataset_id, name, description, scope, source_type) VALUES (?, ?, ?, ?, ?)",
                [dataset_id, name, description, json.dumps(scope) if scope else None, source_type],
            )
            self._conn.commit()

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
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
            "dataset_id": row[0], "name": row[1], "description": row[2],
            "scope": json.loads(row[3]) if row[3] else None,
            "source_type": row[4], "version": row[5],
            "created_at": str(row[6]), "updated_at": str(row[7]),
        }

    async def list_datasets(self) -> list[dict[str, Any]]:
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
                "scope": json.loads(r[3]) if r[3] else None,
                "source_type": r[4], "version": r[5],
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
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            sets = []
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
            sets.append("updated_at = datetime('now')")
            params.append(dataset_id)
            await asyncio.to_thread(
                self._conn.execute,
                f"UPDATE datasets SET {', '.join(sets)} WHERE dataset_id = ?",
                params,
            )
            self._conn.commit()
        return True

    async def delete_dataset(self, dataset_id: str) -> bool:
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
            cursor = await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM datasets WHERE dataset_id = ?",
                [dataset_id],
            )
            self._conn.commit()
        return cursor.rowcount > 0

    async def add_entity_to_dataset(
        self,
        entity_id: str,
        dataset_id: str,
        fact_object: str,
        is_primary: bool = False,
        source_line: int | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO entity_dataset_membership (entity_id, dataset_id, concept, is_primary, source_line) VALUES (?, ?, ?, ?, ?)",
                [entity_id, dataset_id, fact_object, int(is_primary), source_line],
            )
            self._conn.commit()

    async def get_dataset_entities(
        self,
        dataset_id: str,
        fact_object: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if fact_object:
                    cursor = self._conn.execute(
                        "SELECT entity_id, dataset_id, concept, imported_at, source_line, is_primary FROM entity_dataset_membership WHERE dataset_id = ? AND concept = ?",
                        [dataset_id, fact_object],
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
                "entity_id": r[0], "dataset_id": r[1], "fact_object": r[2],
                "imported_at": str(r[3]), "source_line": r[4], "is_primary": bool(r[5]),
            }
            for r in rows
        ]

    async def remove_entity_from_dataset(self, entity_id: str, dataset_id: str) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM entity_dataset_membership WHERE entity_id = ? AND dataset_id = ?",
                [entity_id, dataset_id],
            )
            self._conn.commit()

    async def create_snapshot(
        self,
        snapshot_id: str,
        dataset_id: str,
        entity_count: int | None = None,
        relation_count: int | None = None,
        description: str | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT INTO dataset_snapshots (snapshot_id, dataset_id, entity_count, relation_count, description) VALUES (?, ?, ?, ?, ?)",
                [snapshot_id, dataset_id, entity_count, relation_count, description],
            )
            self._conn.commit()

    async def get_snapshots(self, dataset_id: str) -> list[dict[str, Any]]:
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
                "snapshot_id": r[0], "dataset_id": r[1], "entity_count": r[2],
                "relation_count": r[3], "description": r[4], "created_at": str(r[5]),
            }
            for r in rows
        ]

    # =========================================================================
    # Dimension Applicability & Category Rule Mapping
    # =========================================================================

    async def save_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str,
        required: bool = False,
        auto_categorize: bool = True,
        source_attribute: str | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO dimension_applicability (dimension_id, object_type, required, auto_categorize, source_attribute) VALUES (?, ?, ?, ?, ?)",
                [dimension_id, object_type, int(required), int(auto_categorize), source_attribute],
            )
            self._conn.commit()

    async def get_dimension_applicability(
        self,
        dimension_id: str,
        object_type: str | None = None,
    ) -> list[dict[str, Any]]:
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
                "dimension_id": r[0], "object_type": r[1], "required": bool(r[2]),
                "auto_categorize": bool(r[3]), "source_attribute": r[4],
            }
            for r in rows
        ]

    async def delete_dimension_applicability(self, dimension_id: str, object_type: str) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM dimension_applicability WHERE dimension_id = ? AND object_type = ?",
                [dimension_id, object_type],
            )
            self._conn.commit()

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
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO category_rule_mapping (dimension_id, dimension_value, rule_group_id, mapping_type, override_rule_id, override_field, override_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [dimension_id, dimension_value, rule_group_id, mapping_type, override_rule_id, override_field, json.dumps(override_value) if override_value is not None else None],
            )
            self._conn.commit()

    async def get_category_rule_mappings(
        self,
        dimension_id: str | None = None,
        dimension_value: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                if dimension_id and dimension_value:
                    cursor = self._conn.execute(
                        "SELECT dimension_id, dimension_value, rule_group_id, mapping_type, override_rule_id, override_field, override_value FROM category_rule_mapping WHERE dimension_id = ? AND dimension_value = ?",
                        [dimension_id, dimension_value],
                    )
                elif dimension_id:
                    cursor = self._conn.execute(
                        "SELECT dimension_id, dimension_value, rule_group_id, mapping_type, override_rule_id, override_field, override_value FROM category_rule_mapping WHERE dimension_id = ?",
                        [dimension_id],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT dimension_id, dimension_value, rule_group_id, mapping_type, override_rule_id, override_field, override_value FROM category_rule_mapping"
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "dimension_id": r[0], "dimension_value": r[1], "rule_group_id": r[2],
                "mapping_type": r[3], "override_rule_id": r[4], "override_field": r[5],
                "override_value": json.loads(r[6]) if r[6] else None,
            }
            for r in rows
        ]

    async def delete_category_rule_mapping(
        self,
        dimension_id: str,
        dimension_value: str,
        rule_group_id: str,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM category_rule_mapping WHERE dimension_id = ? AND dimension_value = ? AND rule_group_id = ?",
                [dimension_id, dimension_value, rule_group_id],
            )
            self._conn.commit()

    # =========================================================================
    # Incremental Update
    # =========================================================================

    async def create_change_batch(
        self,
        batch_id: str,
        dataset_id: str | None = None,
        entity_count: int | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT INTO change_batches (batch_id, dataset_id, entity_count) VALUES (?, ?, ?)",
                [batch_id, dataset_id, entity_count],
            )
            self._conn.commit()

    async def update_change_batch(
        self,
        batch_id: str,
        status: str | None = None,
        created_count: int | None = None,
        updated_count: int | None = None,
        deleted_count: int | None = None,
        unchanged_count: int | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            sets = []
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
            if sets:
                params.append(batch_id)
                await asyncio.to_thread(
                    self._conn.execute,
                    f"UPDATE change_batches SET {', '.join(sets)} WHERE batch_id = ?",
                    params,
                )
                self._conn.commit()

    async def get_change_batch(self, batch_id: str) -> dict[str, Any] | None:
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
            "deleted_count": row[6], "unchanged_count": row[7], "created_at": str(row[8]),
        }

    async def list_change_batches(
        self,
        dataset_id: str | None = None,
    ) -> list[dict[str, Any]]:
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
                        "SELECT batch_id, dataset_id, status, entity_count, created_count, updated_count, deleted_count, unchanged_count, created_at FROM change_batches ORDER BY created_at DESC"
                    )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "batch_id": r[0], "dataset_id": r[1], "status": r[2],
                "entity_count": r[3], "created_count": r[4], "updated_count": r[5],
                "deleted_count": r[6], "unchanged_count": r[7], "created_at": str(r[8]),
            }
            for r in rows
        ]

    async def save_entity_changes(
        self,
        batch_id: str,
        entity_id: str,
        fact_object: str,
        change_type: str,
        field_changes: list[dict[str, Any]] | None = None,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO entity_changes (batch_id, entity_id, concept, change_type, field_changes, old_data, new_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    batch_id, entity_id, fact_object, change_type,
                    json.dumps(field_changes or []),
                    json.dumps(old_data) if old_data else None,
                    json.dumps(new_data) if new_data else None,
                ],
            )
            self._conn.commit()

    async def get_entity_changes(self, batch_id: str) -> list[dict[str, Any]]:
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
                "batch_id": r[0], "entity_id": r[1], "fact_object": r[2],
                "change_type": r[3],
                "field_changes": json.loads(r[4]) if r[4] else [],
                "old_data": json.loads(r[5]) if r[5] else None,
                "new_data": json.loads(r[6]) if r[6] else None,
                "created_at": str(r[7]),
            }
            for r in rows
        ]

    async def save_entity_version(
        self,
        entity_id: str,
        fact_object: str,
        version: int,
        data: dict[str, Any],
        updated_by: str = "system",
    ) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO entity_versions (entity_id, concept, version, data, updated_by) VALUES (?, ?, ?, ?, ?)",
                [entity_id, fact_object, version, json.dumps(data), updated_by],
            )
            self._conn.commit()

    async def get_entity_version(
        self,
        entity_id: str,
        version: int | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                if version is not None:
                    cursor = self._conn.execute(
                        "SELECT concept, version, data, updated_at, updated_by FROM entity_versions WHERE entity_id = ? AND version = ?",
                        [entity_id, version],
                    )
                else:
                    cursor = self._conn.execute(
                        "SELECT concept, version, data, updated_at, updated_by FROM entity_versions WHERE entity_id = ? ORDER BY version DESC LIMIT 1",
                        [entity_id],
                    )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "concept": row[0], "version": row[1], "data": json.loads(row[2]),
            "updated_at": str(row[3]), "updated_by": row[4],
        }

    async def list_entity_versions(self, entity_id: str) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT concept, version, data, updated_at, updated_by FROM entity_versions WHERE entity_id = ? ORDER BY version",
                    [entity_id],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "concept": r[0], "version": r[1], "data": json.loads(r[2]),
                "updated_at": str(r[3]), "updated_by": r[4],
            }
            for r in rows
        ]

    async def delete_entity_version(self, entity_id: str, version: int) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM entity_versions WHERE entity_id = ? AND version = ?",
                [entity_id, version],
            )
            self._conn.commit()

    async def get_entity_at(
        self,
        entity_id: str,
        as_of: Any,
    ) -> EntityInstance | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        as_of_str = str(as_of)
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT concept, data, valid_from, valid_to FROM entity_versions "
                    "WHERE entity_id = ? AND (valid_from IS NULL OR valid_from <= ?) AND (valid_to IS NULL OR valid_to > ?) "
                    "ORDER BY version DESC LIMIT 1",
                    [entity_id, as_of_str, as_of_str],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        from datetime import datetime
        return EntityInstance(
            _fact_object=row[0],
            entity_id=entity_id,
            data=json.loads(row[1]),
            valid_from=datetime.fromisoformat(row[2]) if row[2] else None,
            valid_to=datetime.fromisoformat(row[3]) if row[3] else None,
        )

    async def get_entity_history(
        self,
        entity_id: str,
    ) -> list[EntityInstance]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT concept, version, data, valid_from, valid_to, updated_at FROM entity_versions WHERE entity_id = ? ORDER BY version",
                    [entity_id],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        from datetime import datetime
        return [
            EntityInstance(
                _fact_object=row[0],
                entity_id=entity_id,
                data=json.loads(row[2]),
                valid_from=datetime.fromisoformat(row[3]) if row[3] else None,
                valid_to=datetime.fromisoformat(row[4]) if row[4] else None,
            )
            for row in rows
        ]

    # =========================================================================
    # Phase 2: Rule Groups & Steps
    # =========================================================================

    async def save_rule_group(self, data: dict, schema_id: str | None = None) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            gid = data.get("id") or str(uuid.uuid4())
            name = data.get("name", "")
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM rule_groups WHERE id = ?",
                [gid],
            )
            await asyncio.to_thread(
                self._conn.execute,
                """INSERT INTO rule_groups (id, name, description, type, priority, applies_to, preconditions, inputs, outputs, enabled, schema_id, source_declaration_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    gid, name, data.get("description"), data.get("type", ""),
                    data.get("priority", 100),
                    json.dumps(data.get("applies_to")) if data.get("applies_to") else None,
                    json.dumps(data.get("preconditions")) if data.get("preconditions") else None,
                    json.dumps(data.get("inputs")) if data.get("inputs") else None,
                    json.dumps(data.get("outputs")) if data.get("outputs") else None,
                    int(data.get("enabled", True)),
                    schema_id, data.get("source_declaration_id"),
                ],
            )
            self._conn.commit()

    async def get_rule_group(self, identifier: str, schema_id: str | None = None) -> dict[str, Any] | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                if len(identifier) == 36 and "-" in identifier:
                    cursor = self._conn.execute(
                        "SELECT id, name, description, type, priority, applies_to, preconditions, inputs, outputs, enabled, schema_id, source_declaration_id, created_at, updated_at FROM rule_groups WHERE id = ?",
                        [identifier],
                    )
                else:
                    if schema_id:
                        cursor = self._conn.execute(
                            "SELECT id, name, description, type, priority, applies_to, preconditions, inputs, outputs, enabled, schema_id, source_declaration_id, created_at, updated_at FROM rule_groups WHERE name = ? AND schema_id = ?",
                            [identifier, schema_id],
                        )
                    else:
                        cursor = self._conn.execute(
                            "SELECT id, name, description, type, priority, applies_to, preconditions, inputs, outputs, enabled, schema_id, source_declaration_id, created_at, updated_at FROM rule_groups WHERE name = ?",
                            [identifier],
                        )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return _row_to_rule_group(row)

    async def list_rule_groups(self, schema_id: str | None = None, enabled: bool | None = None) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                conds = []
                params: list[Any] = []
                if schema_id:
                    conds.append("schema_id = ?")
                    params.append(schema_id)
                if enabled is not None:
                    conds.append("enabled = ?")
                    params.append(int(enabled))
                where = f" WHERE {' AND '.join(conds)}" if conds else ""
                cursor = self._conn.execute(
                    f"SELECT id, name, description, type, priority, applies_to, preconditions, inputs, outputs, enabled, schema_id, source_declaration_id, created_at, updated_at FROM rule_groups{where} ORDER BY priority DESC, name",
                    params,
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [_row_to_rule_group(r) for r in rows]

    async def delete_rule_group(self, identifier: str, schema_id: str | None = None) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            if len(identifier) == 36 and "-" in identifier:
                gid = identifier
            else:
                if schema_id:
                    cursor = self._conn.execute("SELECT id FROM rule_groups WHERE name = ? AND schema_id = ?", [identifier, schema_id])
                else:
                    cursor = self._conn.execute("SELECT id FROM rule_groups WHERE name = ?", [identifier])
                row = cursor.fetchone()
                gid = row[0] if row else identifier
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM rule_steps WHERE rule_group = ?",
                [gid],
            )
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM rule_groups WHERE id = ?",
                [gid],
            )
            self._conn.commit()

    async def save_rule_step(self, rule_group: str, data: dict) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            sid = data.get("id") or str(uuid.uuid4())
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM rule_steps WHERE rule_group = ? AND id = ?",
                [rule_group, sid],
            )
            await asyncio.to_thread(
                self._conn.execute,
                """INSERT INTO rule_steps (id, rule_group, step_order, name, when_clause, then_clause, else_clause, enabled, description, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    sid, rule_group, data.get("step_order", 0), data.get("name"),
                    json.dumps(data.get("when_clause")) if data.get("when_clause") else None,
                    json.dumps(data.get("then_clause")) if data.get("then_clause") else None,
                    json.dumps(data.get("else_clause")) if data.get("else_clause") else None,
                    int(data.get("enabled", True)),
                    data.get("description"),
                    json.dumps(data.get("tags")) if data.get("tags") else None,
                ],
            )
            self._conn.commit()

    async def get_rule_step(self, rule_group: str, step_id: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT id, rule_group, step_order, name, when_clause, then_clause, else_clause, enabled, description, tags, created_at, updated_at FROM rule_steps WHERE rule_group = ? AND id = ?",
                    [rule_group, step_id],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return _row_to_rule_step(row)

    async def list_rule_steps(self, rule_group: str) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT id, rule_group, step_order, name, when_clause, then_clause, else_clause, enabled, description, tags, created_at, updated_at FROM rule_steps WHERE rule_group = ? ORDER BY step_order",
                    [rule_group],
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [_row_to_rule_step(r) for r in rows]

    async def delete_rule_step(self, rule_group: str, step_id: str) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM rule_steps WHERE rule_group = ? AND id = ?",
                [rule_group, step_id],
            )
            self._conn.commit()

    async def reorder_rule_steps(self, rule_group: str, step_ids: list[str]) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            for order, sid in enumerate(step_ids):
                await asyncio.to_thread(
                    self._conn.execute,
                    "UPDATE rule_steps SET step_order = ? WHERE rule_group = ? AND id = ?",
                    [order, rule_group, sid],
                )
            self._conn.commit()

    # =========================================================================
    # Phase 2: Metric Extensions & Operator Registry
    # =========================================================================

    async def save_metric_extension(self, metric_name: str, value_domain: dict | None = None, thresholds: dict | None = None, color: str | None = None, unit: str | None = None) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO metric_extensions (metric_name, value_domain, thresholds, color, unit) VALUES (?, ?, ?, ?, ?)",
                [metric_name, json.dumps(value_domain) if value_domain else None, json.dumps(thresholds) if thresholds else None, color, unit],
            )
            self._conn.commit()

    async def get_metric_extension(self, metric_name: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT metric_name, value_domain, thresholds, color, unit, updated_at FROM metric_extensions WHERE metric_name = ?",
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
            "color": row[3], "unit": row[4], "updated_at": str(row[5]),
        }

    async def list_metric_extensions(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT metric_name, value_domain, thresholds, color, unit, updated_at FROM metric_extensions"
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "metric_name": r[0],
                "value_domain": json.loads(r[1]) if r[1] else None,
                "thresholds": json.loads(r[2]) if r[2] else None,
                "color": r[3], "unit": r[4], "updated_at": str(r[5]),
            }
            for r in rows
        ]

    async def delete_metric_extension(self, metric_name: str) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "DELETE FROM metric_extensions WHERE metric_name = ?",
                [metric_name],
            )
            self._conn.commit()

    async def save_operator_registry(self, data: dict) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            await asyncio.to_thread(
                self._conn.execute,
                "INSERT OR REPLACE INTO operator_registry (name, display_name, description, category, param_schema, input_types, output_types, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    data.get("name"), data.get("display_name"), data.get("description"),
                    data.get("category"),
                    json.dumps(data.get("param_schema")) if data.get("param_schema") else None,
                    json.dumps(data.get("input_types")) if data.get("input_types") else None,
                    json.dumps(data.get("output_types")) if data.get("output_types") else None,
                    int(data.get("enabled", True)),
                ],
            )
            self._conn.commit()

    async def get_operator_registry(self, name: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> tuple | None:
                cursor = self._conn.execute(
                    "SELECT name, display_name, description, category, param_schema, input_types, output_types, enabled FROM operator_registry WHERE name = ?",
                    [name],
                )
                return cursor.fetchone()
            row = await asyncio.to_thread(_fetch)
        if row is None:
            return None
        return {
            "name": row[0], "display_name": row[1], "description": row[2],
            "category": row[3],
            "param_schema": json.loads(row[4]) if row[4] else None,
            "input_types": json.loads(row[5]) if row[5] else None,
            "output_types": json.loads(row[6]) if row[6] else None,
            "enabled": bool(row[7]),
        }

    async def list_operator_registry(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        async with self._lock:
            def _fetch() -> list[tuple]:
                cursor = self._conn.execute(
                    "SELECT name, display_name, description, category, param_schema, input_types, output_types, enabled FROM operator_registry ORDER BY name"
                )
                return cursor.fetchall()
            rows = await asyncio.to_thread(_fetch)
        return [
            {
                "name": r[0], "display_name": r[1], "description": r[2],
                "category": r[3],
                "param_schema": json.loads(r[4]) if r[4] else None,
                "input_types": json.loads(r[5]) if r[5] else None,
                "output_types": json.loads(r[6]) if r[6] else None,
                "enabled": bool(r[7]),
            }
            for r in rows
        ]


def _matches_filters(data: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, expected in filters.items():
        parts = key.split(".")
        actual = _get_nested_value(data, parts)
        if actual is None:
            return False
        if isinstance(expected, dict):
            for op, val in expected.items():
                if op == "$gte" and not (actual >= val):
                    return False
                if op == "$lte" and not (actual <= val):
                    return False
                if op == "$gt" and not (actual > val):
                    return False
                if op == "$lt" and not (actual < val):
                    return False
                if op == "$ne" and actual == val:
                    return False
        elif actual != expected:
            return False
    return True


def _get_nested_value(data: dict[str, Any], path: list[str]) -> Any:
    current = data
    for part in path:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _row_to_rule_group(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0], "name": row[1], "description": row[2],
        "type": row[3], "priority": row[4],
        "applies_to": json.loads(row[5]) if row[5] else None,
        "preconditions": json.loads(row[6]) if row[6] else None,
        "inputs": json.loads(row[7]) if row[7] else None,
        "outputs": json.loads(row[8]) if row[8] else None,
        "enabled": bool(row[9]), "schema_id": row[10],
        "source_declaration_id": row[11],
        "created_at": str(row[12]), "updated_at": str(row[13]),
    }


def _row_to_rule_step(row: tuple) -> dict[str, Any]:
    return {
        "id": row[0], "rule_group": row[1], "step_order": row[2],
        "name": row[3],
        "when_clause": json.loads(row[4]) if row[4] else None,
        "then_clause": json.loads(row[5]) if row[5] else None,
        "else_clause": json.loads(row[6]) if row[6] else None,
        "enabled": bool(row[7]), "description": row[8],
        "tags": json.loads(row[9]) if row[9] else None,
        "created_at": str(row[10]), "updated_at": str(row[11]),
    }

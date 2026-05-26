"""SQLite adapter for CognitiveNode structured data.

P0-2: Implements the StorageInterface for SQLite, handling all
memory_types that route to "sqlite" per StorageRouting.

Manages the cognitive_nodes table with FTS5 full-text search.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
from typing import Any

from ontology_engine.storage.models import CognitiveNode
from ontology_engine.storage.cognitive_interface import (
    SearchQuery,
    SearchResult,
    StorageInterface,
)

logger = logging.getLogger(__name__)

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS cognitive_nodes (
    id              TEXT PRIMARY KEY,
    space_id        TEXT NOT NULL,
    memory_type     TEXT NOT NULL,
    cognitive_layer TEXT NOT NULL,
    content         TEXT NOT NULL,
    entity_name     TEXT,
    entity_type     TEXT,
    schema_ref      TEXT,
    tags            TEXT,
    proof_count     INTEGER DEFAULT 1,
    source_ids      TEXT,
    confidence      REAL DEFAULT 1.0,
    strength        REAL DEFAULT 1.0,
    access_count    INTEGER DEFAULT 0,
    last_accessed_at TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    superseded_by   TEXT,
    version         INTEGER DEFAULT 1,
    belief_status   TEXT DEFAULT 'accepted',
    visibility      TEXT DEFAULT 'shared',
    created_by      TEXT,
    domain_id       TEXT,
    occurred_at     TEXT,
    valid_from      TEXT,
    valid_to        TEXT,
    recorded_at     TEXT,
    attributes      TEXT,
    _store          TEXT DEFAULT 'sqlite',
    content_vector  TEXT,
    source_fragment_ids TEXT,
    ttl_seconds     INTEGER DEFAULT 0,
    history         TEXT,
    consolidated_at TEXT,
    extraction_hint TEXT,
    feedback_weight REAL DEFAULT 0.5,
    confirmation_count INTEGER DEFAULT 0,
    last_confirmed_at TEXT,
    consolidation_reasoning TEXT,
    compiled_at     TEXT,
    source_trust_tier TEXT,
    scope           TEXT,
    source_pipeline TEXT,
    source_content_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_cn_type ON cognitive_nodes(memory_type);
CREATE INDEX IF NOT EXISTS idx_cn_layer ON cognitive_nodes(cognitive_layer);
CREATE INDEX IF NOT EXISTS idx_cn_space ON cognitive_nodes(space_id);
CREATE INDEX IF NOT EXISTS idx_cn_belief ON cognitive_nodes(belief_status);

CREATE VIRTUAL TABLE IF NOT EXISTS cognitive_nodes_fts USING fts5(
    content, entity_name,
    content='cognitive_nodes',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS cn_fts_insert AFTER INSERT ON cognitive_nodes BEGIN
    INSERT INTO cognitive_nodes_fts(rowid, content, entity_name)
    VALUES (new.rowid, new.content, new.entity_name);
END;

CREATE TRIGGER IF NOT EXISTS cn_fts_delete AFTER DELETE ON cognitive_nodes BEGIN
    INSERT INTO cognitive_nodes_fts(cognitive_nodes_fts, rowid, content, entity_name)
    VALUES('delete', old.rowid, old.content, old.entity_name);
END;

CREATE TRIGGER IF NOT EXISTS cn_fts_update AFTER UPDATE ON cognitive_nodes BEGIN
    INSERT INTO cognitive_nodes_fts(cognitive_nodes_fts, rowid, content, entity_name)
    VALUES('delete', old.rowid, old.content, old.entity_name);
    INSERT INTO cognitive_nodes_fts(rowid, content, entity_name)
    VALUES (new.rowid, new.content, new.entity_name);
END;
"""

_FIELDS = [
    "id", "space_id", "memory_type", "cognitive_layer", "content",
    "entity_name", "entity_type", "schema_ref", "tags", "proof_count",
    "source_ids", "confidence", "strength", "access_count",
    "last_accessed_at", "created_at", "updated_at", "superseded_by",
    "version", "belief_status", "visibility", "created_by", "domain_id",
    "occurred_at", "valid_from", "valid_to", "recorded_at", "attributes",
    "_store", "content_vector", "source_fragment_ids", "ttl_seconds",
    "history", "consolidated_at", "extraction_hint", "feedback_weight",
    "confirmation_count", "last_confirmed_at", "consolidation_reasoning",
    "compiled_at", "source_trust_tier", "scope", "source_pipeline",
    "source_content_hash",
]


def _node_to_row(node: CognitiveNode) -> dict[str, Any]:
    d = node.to_dict()
    row: dict[str, Any] = {}
    for f in _FIELDS:
        v = d.get(f)
        if isinstance(v, (dict, list)):
            row[f] = json.dumps(v, ensure_ascii=False)
        else:
            row[f] = v
    row.setdefault("_store", "sqlite")
    return row


def _row_to_node(row: sqlite3.Row | dict[str, Any]) -> CognitiveNode:
    d: dict[str, Any] = {}
    if isinstance(row, sqlite3.Row):
        for k in row.keys():
            d[k] = row[k]
    else:
        d = dict(row)
    for k in ("tags", "attributes", "source_fragment_ids", "source_ids", "history"):
        v = d.get(k)
        if isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                d[k] = {} if k in ("tags", "attributes") else []
    return CognitiveNode.from_dict(d)


class SQLiteAdapter(StorageInterface):
    """SQLite storage adapter for structured CognitiveNode data.

    Handles memory_types routed to "sqlite" per StorageRouting:
    entity, relation, observation, mental_model, episode, procedure,
    rule, opinion, metrics, commitment, constraint, self_experience, task_state.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock: threading.Lock | None = None

    async def initialize(self) -> None:
        if self._conn is not None:
            return
        self._lock = threading.Lock()
        if self._db_path != ":memory:":
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        def _init_conn() -> sqlite3.Connection:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            conn.executescript(_CREATE_TABLES)
            conn.commit()
            return conn

        self._conn = await asyncio.to_thread(_init_conn)
        logger.info("SQLiteAdapter initialized at %s", self._db_path)

    async def close(self) -> None:
        if self._conn is not None:
            conn = self._conn
            self._conn = None
            await asyncio.to_thread(conn.close)

    def _ensure_initialized(self) -> None:
        if self._conn is None:
            raise RuntimeError("SQLiteAdapter not initialized. Call initialize() first.")

    async def save_node(self, node: CognitiveNode) -> str:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        conn = self._conn
        lock = self._lock
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        if node.created_at is None:
            node.created_at = now
        node.updated_at = now
        row = _node_to_row(node)
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        values = list(row.values())

        def _save() -> None:
            lock.acquire()
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO cognitive_nodes ({cols}) VALUES ({placeholders})",
                    values,
                )
                conn.commit()
            finally:
                lock.release()

        await asyncio.to_thread(_save)
        return node.id

    async def get_node(self, node_id: str) -> CognitiveNode | None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        conn = self._conn
        lock = self._lock

        def _get() -> sqlite3.Row | None:
            lock.acquire()
            try:
                cursor = conn.execute(
                    "SELECT * FROM cognitive_nodes WHERE id = ?",
                    [node_id],
                )
                return cursor.fetchone()
            finally:
                lock.release()

        row = await asyncio.to_thread(_get)
        if row is None:
            return None
        return _row_to_node(row)

    async def search(self, query: SearchQuery) -> SearchResult:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        conn = self._conn
        lock = self._lock

        conditions = ["(superseded_by IS NULL OR superseded_by != 'deleted')"]
        params: list[Any] = []

        if query.space_id:
            conditions.append("space_id = ?")
            params.append(query.space_id)
        if query.memory_type:
            conditions.append("memory_type = ?")
            params.append(query.memory_type)
        if query.cognitive_layer:
            conditions.append("cognitive_layer = ?")
            params.append(query.cognitive_layer)
        if query.belief_status:
            conditions.append("belief_status = ?")
            params.append(query.belief_status)
        if query.tags_filter:
            for k, v in query.tags_filter.items():
                conditions.append(f"json_extract(tags, '$.{k}') = ?")
                params.append(json.dumps(v) if isinstance(v, (dict, list)) else v)

        where = " AND ".join(conditions)

        def _search() -> list[sqlite3.Row]:
            lock.acquire()
            try:
                if query.query_text:
                    fts_query = query.query_text.replace("'", "''")
                    cursor = conn.execute(
                        f"""
                        SELECT cn.*, bm25(cognitive_nodes_fts) as fts_score
                        FROM cognitive_nodes cn
                        JOIN cognitive_nodes_fts ON cn.rowid = cognitive_nodes_fts.rowid
                        WHERE cognitive_nodes_fts MATCH ? AND {where}
                        ORDER BY fts_score
                        LIMIT ?
                        """,
                        [fts_query] + params + [query.top_k],
                    )
                else:
                    cursor = conn.execute(
                        f"SELECT * FROM cognitive_nodes WHERE {where} LIMIT ?",
                        params + [query.top_k],
                    )
                return cursor.fetchall()
            finally:
                lock.release()

        rows = await asyncio.to_thread(_search)

        cognitive_nodes = [_row_to_node(row) for row in rows]
        if query.query_text:
            raw_scores: dict[str, float] = {}
            for row in rows:
                if "fts_score" in row.keys():
                    raw_scores[row["id"]] = row["fts_score"]
            if raw_scores:
                min_score = min(raw_scores.values())
                max_score = max(raw_scores.values())
                score_range = max_score - min_score if max_score != min_score else 1.0
                scores = {nid: (max_score - s) / score_range for nid, s in raw_scores.items()}
            else:
                scores = {n.id: 1.0 - (i * 0.05) for i, n in enumerate(cognitive_nodes)}
        else:
            scores = {n.id: 1.0 - (i * 0.05) for i, n in enumerate(cognitive_nodes)}
        return SearchResult(nodes=cognitive_nodes, scores=scores)

    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        conn = self._conn
        lock = self._lock

        def _delete() -> None:
            lock.acquire()
            try:
                if soft:
                    conn.execute(
                        "UPDATE cognitive_nodes SET superseded_by = 'deleted', updated_at = datetime('now') WHERE id = ?",
                        [node_id],
                    )
                else:
                    conn.execute(
                        "DELETE FROM cognitive_nodes WHERE id = ?",
                        [node_id],
                    )
                conn.commit()
            finally:
                lock.release()

        await asyncio.to_thread(_delete)

    async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        conn = self._conn
        lock = self._lock
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        ids = []
        for node in nodes:
            if node.created_at is None:
                node.created_at = now
            node.updated_at = now
            ids.append(node.id)

        def _batch() -> None:
            lock.acquire()
            try:
                for node in nodes:
                    row = _node_to_row(node)
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(["?"] * len(row))
                    values = list(row.values())
                    conn.execute(
                        f"INSERT OR REPLACE INTO cognitive_nodes ({cols}) VALUES ({placeholders})",
                        values,
                    )
                conn.commit()
            finally:
                lock.release()

        await asyncio.to_thread(_batch)
        return ids

    async def count(self, filter: dict[str, Any]) -> int:
        self._ensure_initialized()
        assert self._conn is not None
        assert self._lock is not None
        conn = self._conn
        lock = self._lock
        conditions = []
        params: list[Any] = []
        for k, v in filter.items():
            if k == "tags":
                for tk, tv in v.items():
                    conditions.append(f"json_extract(tags, '$.{tk}') = ?")
                    params.append(json.dumps(tv) if isinstance(tv, (dict, list)) else tv)
            else:
                conditions.append(f"{k} = ?")
                params.append(v)
        where = " AND ".join(conditions) if conditions else "1=1"

        def _count() -> int:
            lock.acquire()
            try:
                cursor = conn.execute(
                    f"SELECT COUNT(*) FROM cognitive_nodes WHERE {where}",
                    params,
                )
                row = cursor.fetchone()
                return row[0] if row else 0
            finally:
                lock.release()

        return await asyncio.to_thread(_count)

"""Agent Activity Log - background writer with independent storage.

Design decisions (2026-05-06):
- D-1: Background thread writes to separate activity_log table
- D-1a: Storage separated from main storage (independent SQLite DB)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ActivityLogEntry:
    """A single agent activity record."""

    space_id: str
    agent_name: str
    activity_type: str
    operation: str
    result: str = ""
    timestamp: str = ""
    node_ids: list[str] = field(default_factory=list)
    duration_ms: int = 0
    success: bool = True
    detail: dict[str, Any] | None = None
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"act:{uuid.uuid4().hex[:12]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_row(self) -> tuple:
        return (
            self.id,
            self.space_id,
            self.agent_name,
            self.activity_type,
            self.operation,
            self.result,
            self.timestamp,
            json.dumps(self.node_ids),
            self.duration_ms,
            1 if self.success else 0,
            json.dumps(self.detail) if self.detail else None,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ActivityLogEntry:
        return cls(
            id=row["id"],
            space_id=row["space_id"],
            agent_name=row["agent_name"],
            activity_type=row["activity_type"],
            operation=row["operation"],
            result=row["result"],
            timestamp=row["timestamp"],
            node_ids=json.loads(row["node_ids"]) if row["node_ids"] else [],
            duration_ms=row["duration_ms"],
            success=bool(row["success"]),
            detail=json.loads(row["detail"]) if row["detail"] else None,
        )


_ACT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS activity_log (
    id TEXT PRIMARY KEY,
    space_id TEXT NOT NULL,
    agent_name TEXT NOT NULL DEFAULT 'system',
    activity_type TEXT NOT NULL,
    operation TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    node_ids TEXT NOT NULL DEFAULT '[]',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 1,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_activity_log_space_id ON activity_log(space_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_type ON activity_log(activity_type);
CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(timestamp);
"""


class ActivityLogWriter:
    """Background thread writer for agent activity logs.

    Uses a daemon thread with a queue. Main thread never blocks on writes.
    Storage is an independent SQLite DB file, separate from the main ontology store.
    """

    def __init__(self, db_path: str | None = None, flush_interval_ms: int = 200):
        if db_path is None:
            project_root = os.environ.get(
                "ONTOLOGY_DATA_DIR",
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data"),
            )
            os.makedirs(project_root, exist_ok=True)
            db_path = os.path.join(project_root, "activity_log.db")

        self._db_path = db_path
        self._queue: queue.Queue[ActivityLogEntry | None] = queue.Queue()
        self._stop_event = threading.Event()
        self._flush_interval = flush_interval_ms / 1000.0
        self._thread: threading.Thread | None = None
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        self._init_db()
        self._thread = threading.Thread(target=self._run, daemon=True, name="activity-log-writer")
        self._thread.start()
        logger.info("ActivityLogWriter started (db=%s)", self._db_path)

    def stop(self, timeout: float = 5.0):
        if not self._started:
            return
        self._stop_event.set()
        self._queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("ActivityLogWriter thread did not stop within timeout")
        self._started = False
        logger.info("ActivityLogWriter stopped")

    def enqueue(self, entry: ActivityLogEntry):
        self._queue.put(entry)

    def query(self, space_id: str, limit: int = 50,
              activity_type: str | None = None) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            sql = "SELECT * FROM activity_log WHERE space_id = ?"
            params: list = [space_id]
            if activity_type:
                sql += " AND activity_type = ?"
                params.append(activity_type)
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            entries = [ActivityLogEntry.from_row(r) for r in rows]
            return [_entry_to_dict(e) for e in entries]
        finally:
            conn.close()

    def _init_db(self):
        conn = sqlite3.connect(self._db_path)
        try:
            conn.executescript(_ACT_LOG_DDL)
            conn.commit()
        finally:
            conn.close()

    def _run(self):
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            batch: list[ActivityLogEntry] = []
            last_flush = time.monotonic()
            while not self._stop_event.is_set():
                try:
                    entry = self._queue.get(timeout=self._flush_interval)
                    if entry is None:
                        break
                    batch.append(entry)
                except queue.Empty:
                    pass

                elapsed = time.monotonic() - last_flush
                if batch and elapsed >= self._flush_interval:
                    self._flush_batch(conn, batch)
                    batch = []
                    last_flush = time.monotonic()

            if batch:
                self._flush_batch(conn, batch)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _flush_batch(conn: sqlite3.Connection, entries: list[ActivityLogEntry]):
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO activity_log VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [e.to_row() for e in entries],
            )
            conn.commit()
        except Exception:
            logger.exception("Failed to flush %d activity log entries", len(entries))


def _entry_to_dict(e: ActivityLogEntry) -> dict[str, Any]:
    return {
        "id": e.id,
        "space_id": e.space_id,
        "agent_name": e.agent_name,
        "activity_type": e.activity_type,
        "timestamp": e.timestamp,
        "operation": e.operation,
        "result": e.result,
        "node_ids": e.node_ids,
        "duration_ms": e.duration_ms,
        "success": e.success,
    }


_global_writer: ActivityLogWriter | None = None
_writer_lock = threading.Lock()


def get_activity_log_writer(db_path: str | None = None) -> ActivityLogWriter:
    """Get or create the global ActivityLogWriter singleton."""
    global _global_writer
    with _writer_lock:
        if _global_writer is None:
            _global_writer = ActivityLogWriter(db_path=db_path)
            _global_writer.start()
        return _global_writer


def log_remember(space_id: str, content: str, node_id: str, memory_type: str,
                 agent_name: str = "system", duration_ms: int = 0,
                 success: bool = True):
    writer = get_activity_log_writer()
    entry = ActivityLogEntry(
        space_id=space_id,
        agent_name=agent_name,
        activity_type="remember",
        operation=f"remember {memory_type}",
        result=f"Created {node_id}",
        node_ids=[node_id],
        duration_ms=duration_ms,
        success=success,
        detail={"content_preview": content[:200], "memory_type": memory_type},
    )
    writer.enqueue(entry)


def log_recall(space_id: str, query: str, result_count: int,
               agent_name: str = "system", duration_ms: int = 0,
               query_type: str = "unknown", success: bool = True):
    writer = get_activity_log_writer()
    entry = ActivityLogEntry(
        space_id=space_id,
        agent_name=agent_name,
        activity_type="recall",
        operation=f"recall {query_type}",
        result=f"Returned {result_count} results",
        duration_ms=duration_ms,
        success=success,
        detail={"query_preview": query[:200], "result_count": result_count},
    )
    writer.enqueue(entry)


def log_reflect(space_id: str, query: str, reflection_id: str,
                iteration_count: int = 0, contradiction_count: int = 0,
                insight_count: int = 0, agent_name: str = "system",
                duration_ms: int = 0, success: bool = True):
    writer = get_activity_log_writer()
    detail = {
        "reflection_id": reflection_id,
        "iterations": iteration_count,
        "contradictions": contradiction_count,
        "insights": insight_count,
    }
    entry = ActivityLogEntry(
        space_id=space_id,
        agent_name=agent_name,
        activity_type="reflect",
        operation=f"reflect on '{query[:100]}'",
        result=f"{iteration_count} iters, {contradiction_count} contradictions, {insight_count} insights",
        node_ids=[reflection_id],
        duration_ms=duration_ms,
        success=success,
        detail=detail,
    )
    writer.enqueue(entry)


def log_correct(space_id: str, node_id: str, new_node_id: str,
                agent_name: str = "system", duration_ms: int = 0,
                success: bool = True):
    writer = get_activity_log_writer()
    entry = ActivityLogEntry(
        space_id=space_id,
        agent_name=agent_name,
        activity_type="correct",
        operation=f"correct {node_id}",
        result=f"Superseded by {new_node_id}",
        node_ids=[node_id, new_node_id],
        duration_ms=duration_ms,
        success=success,
    )
    writer.enqueue(entry)


def log_delete(space_id: str, node_id: str, memory_type: str = "",
               agent_name: str = "system", duration_ms: int = 0,
               success: bool = True):
    writer = get_activity_log_writer()
    entry = ActivityLogEntry(
        space_id=space_id,
        agent_name=agent_name,
        activity_type="delete",
        operation=f"delete {node_id}",
        result="Node deleted",
        node_ids=[node_id],
        duration_ms=duration_ms,
        success=success,
        detail={"memory_type": memory_type},
    )
    writer.enqueue(entry)

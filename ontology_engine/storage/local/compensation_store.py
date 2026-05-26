from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from ontology_engine.storage.base import CompensationStore

logger = logging.getLogger(__name__)


class LocalCompensationStore(CompensationStore):

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS compensation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                retry_count INTEGER DEFAULT 0,
                details TEXT
            )
        """)
        self._conn.commit()

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("LocalCompensationStore is closed")
        return self._conn

    async def save_compensation(self, entry: dict[str, Any]) -> None:
        conn = self._ensure_conn()
        try:
            conn.execute(
                "INSERT INTO compensation_log "
                "(operation, target_type, target_id, timestamp, status, retry_count, details) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.get("operation", ""),
                    entry.get("target_type", ""),
                    entry.get("target_id", ""),
                    entry.get("timestamp", ""),
                    entry.get("status", "pending"),
                    entry.get("retry_count", 0),
                    json.dumps(entry.get("details", {})),
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to persist compensation entry: %s", e)
            raise

    async def get_pending_compensations(self) -> list[dict[str, Any]]:
        conn = self._ensure_conn()
        cursor = conn.execute(
            "SELECT id, operation, target_type, target_id, timestamp, status, retry_count, details "
            "FROM compensation_log WHERE status = 'pending' ORDER BY timestamp"
        )
        rows = cursor.fetchall()
        results = []
        for row_id, operation, target_type, target_id, timestamp, status, retry_count, details in rows:
            results.append({
                "id": row_id,
                "operation": operation,
                "target_type": target_type,
                "target_id": target_id,
                "timestamp": timestamp,
                "status": status,
                "retry_count": retry_count,
                "details": json.loads(details) if details else {},
            })
        return results

    async def mark_compensation_done(self, target_id: str, operation: str) -> None:
        conn = self._ensure_conn()
        try:
            conn.execute(
                "UPDATE compensation_log SET status = 'completed' "
                "WHERE target_id = ? AND operation = ? AND status = 'pending'",
                (target_id, operation),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to mark compensation done: %s", e)
            raise

    async def increment_retry_count(self, target_id: str, operation: str) -> None:
        conn = self._ensure_conn()
        try:
            conn.execute(
                "UPDATE compensation_log SET retry_count = retry_count + 1 "
                "WHERE target_id = ? AND operation = ? AND status = 'pending'",
                (target_id, operation),
            )
            conn.commit()
        except sqlite3.Error as e:
            logger.error("Failed to increment retry count: %s", e)
            raise

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

"""Ladybug-based graph store for production use.

Provides persistent graph storage with native Cypher support.
Requires ``ladybug`` Python binding (``pip install ladybug``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any

from ontology_engine.storage.base import CognitiveStorageBackend, GraphQueryError, GraphStoreBackend

logger = logging.getLogger(__name__)

_LOCK_RETRY_ATTEMPTS = 5
_LOCK_RETRY_BASE_DELAY = 0.5
_LOCK_RETRY_MAX_DELAY = 8.0


class LadybugConnectionPool:
    """Pool of ``ladybug.Connection`` objects sharing one ``ladybug.Database``.

    Ladybug's Python binding is not thread-safe: concurrent ``execute()`` on the
    same ``Connection`` causes data corruption or segfaults.  However, multiple
    ``Connection`` objects attached to the same ``Database`` *are* safe to use
    concurrently as long as each connection is used by at most one coroutine at
    a time.

    The pool enforces this by handing out connections exclusively via the
    ``acquire()`` async context manager.  Callers never hold a raw connection;
    they ``async with pool.acquire() as conn:`` and the pool guarantees no
    two coroutines share the same connection.

    Args:
        db: An already-opened ``ladybug.Database`` instance.
        pool_size: Number of connections in the pool.  Defaults to 3 which
            is sufficient for typical async workloads while keeping resource
            usage modest.
    """

    def __init__(self, db: Any, pool_size: int = 3) -> None:
        self._db = db
        self._pool_size = pool_size
        self._semaphore = asyncio.Semaphore(pool_size)
        self._connections: list[Any] = []
        self._available: asyncio.Queue[Any] = asyncio.Queue(maxsize=pool_size)
        self._closed = False

    async def initialize(self) -> None:
        import ladybug as lb

        for _ in range(self._pool_size):
            conn = lb.Connection(self._db)
            self._connections.append(conn)
            await self._available.put(conn)

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        if self._closed:
            raise GraphQueryError("LadybugConnectionPool is closed")
        await self._semaphore.acquire()
        conn = await self._available.get()
        try:
            yield conn
        finally:
            await self._available.put(conn)
            self._semaphore.release()

    async def close(self) -> None:
        self._closed = True
        for conn in self._connections:
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()
        while not self._available.empty():
            try:
                self._available.get_nowait()
            except asyncio.QueueEmpty:
                break


def _first_row(result: Any) -> dict[str, Any] | None:
    """Get first query result row as dict, or None if empty.

    Avoids ``get_as_df()`` which crashes on JSON columns in ladybug ≤0.17.
    """
    result.rows_as_dict()
    if result.has_next():
        return result.get_next()
    return None


def _all_rows(result: Any) -> list[dict[str, Any]]:
    """Get all query result rows as list of dicts.

    Avoids ``get_as_df()`` which crashes on JSON columns in ladybug ≤0.17.
    """
    result.rows_as_dict()
    return result.get_all()


def _safe_json_loads(value: Any, default: Any = None) -> Any:
    """Parse JSON, falling back to ladybug's non-standard JSON format.

    Ladybug ≤0.17 returns JSON-type column values as non-standard strings
    like ``{key: val, nested: {inner: val}}`` instead of valid JSON.
    This function handles both standard JSON and the ladybug format.
    """
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float)):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default if default is not None else value
        # Standard JSON first
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            return _fix_ladybug_json(value)
        except Exception:
            return default if default is not None else value
    return value


def _fix_ladybug_json(s: str) -> Any:
    """Convert ladybug's non-standard JSON (unquoted keys/values) to Python object.

    Ladybug serializes ``{key: value, nested: {inner: val}}`` where both
    keys and bare string values lack quotes. This function adds quotes and
    delegates to ``json.loads``.
    """
    result: list[str] = []
    i = 0
    expect_key = True  # True after { or , (expect key); False after : (expect value)

    while i < len(s):
        c = s[i]

        if c in '{}[],:':
            result.append(c)
            if c in '{[':
                expect_key = True
            elif c == ',':
                expect_key = True
            elif c == ':':
                expect_key = False
            i += 1
        elif c in ' \t\n\r':
            result.append(c)
            i += 1
        elif c in '"\'':
            # Already quoted — copy verbatim (handles standard JSON mixed in)
            quote = c
            result.append(c)
            i += 1
            while i < len(s) and s[i] != quote:
                if s[i] == '\\':
                    result.append(s[i])
                    i += 1
                result.append(s[i])
                i += 1
            if i < len(s):
                result.append(s[i])
                i += 1
            if expect_key:
                expect_key = False
        else:
            start = i
            if expect_key:
                # Key: single word before delimiter
                while i < len(s) and s[i] not in ': ,}\n\r\t[]':
                    i += 1
            else:
                # Value: may include spaces, extends until , or }/] at depth 0
                vdepth = 0
                while i < len(s):
                    ch = s[i]
                    if ch in ',}]' and vdepth == 0:
                        break
                    if ch in '{[':
                        vdepth += 1
                    if ch in '}]':
                        vdepth -= 1
                    i += 1

            token = s[start:i]
            # Keep JSON literals unquoted
            if token in ('true', 'false', 'null'):
                result.append(token)
            elif re.match(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$', token):
                result.append(token)
            else:
                result.append(f'"{token}"')

            if expect_key:
                expect_key = False

    return json.loads(''.join(result))


class LadybugGraphStore(GraphStoreBackend, CognitiveStorageBackend):
    """Ladybug-based graph store.

    Data model:
    - Nodes: Entity, KnowledgeFragment, ExecutionStepSnapshot, MetricDeclaration,
             CategoryTag, MetricValue
    - Edges: Relation (general), EXTRACTED_FROM, SUPPORTED_BY,
             SUPPORTED_BY_FRAGMENT (KnowledgeFragment→Entity), DEFINED_IN,
             DEFINED_IN_FROM_METRIC, TRACE_TO, CATEGORIZED_AS, HAS_METRIC,
             temporal edges (PRECEDES/SUCCEEDS/…)

    Design note: SUPPORTED_BY covers the Entity→Entity variant (legacy / inline
    annotations), while SUPPORTED_BY_FRAGMENT covers the canonical design-spec
    variant KnowledgeFragment → EntityInstance.  Both are queried by
    ``get_mutual_index_edges`` when edge_type="SUPPORTED_BY".

    Default database path: ``~/.ontology_engine/data/{space_id}/graph.ladybug``

    Concurrency model:
    - A ``LadybugConnectionPool`` manages multiple ``ladybug.Connection`` objects.
    - Each query acquires a connection exclusively via ``pool.acquire()``,
      guaranteeing no two coroutines share the same connection.
    - ``initialize()`` retries with exponential backoff when the database file
      lock is held by another process (e.g. during ``uvicorn --reload``).
    - For multi-worker deployments (gunicorn -w N), each worker process opens
      its own Database + pool; the file lock is handled by retry at init time.
    """

    def __init__(self, pool_size: int = 3) -> None:
        self._db: Any | None = None
        self._pool: LadybugConnectionPool | None = None
        self._initialized = False
        self._fragment_cache: dict[str, bool] = {}
        self._pool_size = pool_size

    # Pre-defined query specs for mutual index relations (class-level constant).
    # Each entry lists ALL rel-tables that carry that logical edge type, so that
    # get_mutual_index_edges() can fan-out to the correct tables based on
    # the actual node types involved.
    _MUTUAL_INDEX_QUERIES: dict[str, list[dict[str, str]]] = {
        "EXTRACTED_FROM": [
            {"rel": "EXTRACTED_FROM", "from_label": "Entity", "from_pk": "entity_id", "to_label": "KnowledgeFragment", "to_pk": "fragment_id"},
        ],
        "SUPPORTED_BY": [
            {"rel": "SUPPORTED_BY_FRAGMENT", "from_label": "KnowledgeFragment", "from_pk": "fragment_id", "to_label": "Entity", "to_pk": "entity_id"},
            {"rel": "SUPPORTED_BY", "from_label": "Entity", "from_pk": "entity_id", "to_label": "Entity", "to_pk": "entity_id"},
        ],
        "DEFINED_IN": [
            {"rel": "DEFINED_IN", "from_label": "Entity", "from_pk": "entity_id", "to_label": "Entity", "to_pk": "entity_id"},
            {"rel": "DEFINED_IN_FROM_METRIC", "from_label": "MetricDeclaration", "from_pk": "id", "to_label": "KnowledgeFragment", "to_pk": "fragment_id"},
            {"rel": "DEFINED_IN_FROM_RULE", "from_label": "RuleDefinitionNode", "from_pk": "id", "to_label": "KnowledgeFragment", "to_pk": "fragment_id"},
        ],
        "TRACE_TO": [
            {"rel": "TRACE_TO", "from_label": "ExecutionStepSnapshot", "from_pk": "id", "to_label": "KnowledgeFragment", "to_pk": "fragment_id"},
        ],
    }

    def _default_path(self) -> str:
        """Return default ladybug database path."""
        base = os.path.expanduser("~/.ontology_engine/data")
        return os.path.join(base, "default", "graph.ladybug")

    async def _execute(self, query: str, parameters: dict[str, Any] | None = None) -> Any:
        """Execute a Cypher query via the connection pool.

        Acquires an exclusive connection from the pool, executes the query,
        and returns the connection.  This guarantees no two coroutines share
        the same ``ladybug.Connection`` which the Ladybug Python binding does not
        support.
        """
        self._ensure_initialized()
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            return conn.execute(query, parameters or {})

    async def initialize(self, db_path: str | None = None) -> None:
        """Initialize ladybug database connection with retry on lock contention.

        When ``uvicorn --reload`` restarts the worker, the old process may
        still hold the database file lock for a brief moment.  This method
        retries with exponential backoff so the new process can acquire the
        lock once the old one releases it.

        If all retries fail due to a stale lock (process crash without cleanup),
        this method attempts to detect and remove the stale lock file and retry
        once before raising.

        Args:
            db_path: Database path. Defaults to
                ``~/.ontology_engine/data/{space_id}/graph.ladybug``.

        Raises:
            GraphQueryError: If already initialized, ladybug not installed, or
                the database lock cannot be acquired after all retries.
        """
        if self._initialized:
            raise GraphQueryError("LadybugGraphStore already initialized")

        try:
            import ladybug as lb
        except ImportError as exc:
            raise GraphQueryError(
                "ladybug is not installed. Install with: pip install ontology-engine[ladybug]"
            ) from exc

        path = db_path or self._default_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        last_error: Exception | None = None
        for attempt in range(1, _LOCK_RETRY_ATTEMPTS + 1):
            try:
                self._db = self._open_database(path)
                break
            except RuntimeError as exc:
                last_error = exc
                msg = str(exc).lower()
                if "lock" not in msg and "could not set" not in msg:
                    # Detect incompatible database format (e.g. old KuzuDB file)
                    if "not a valid" in msg or "invalid" in msg:
                        self._backup_and_recreate(path, exc)
                        try:
                            self._db = self._open_database(path)
                            break
                        except RuntimeError as retry_exc:
                            raise GraphQueryError(
                                f"Failed to open Ladybug at {path} after recreating: {retry_exc}"
                            ) from retry_exc
                    raise GraphQueryError(
                        f"Failed to open Ladybug at {path}: {exc}"
                    ) from exc
                if attempt < _LOCK_RETRY_ATTEMPTS:
                    delay = min(
                        _LOCK_RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                        _LOCK_RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "Ladybug lock contention on %s (attempt %d/%d), "
                        "retrying in %.1fs — another process likely holds the lock",
                        path, attempt, _LOCK_RETRY_ATTEMPTS, delay,
                    )
                    await asyncio.sleep(delay)
        else:
            # All retries exhausted — attempt stale lock recovery
            recovered = await self._recover_stale_lock(path, last_error)
            if recovered:
                try:
                    self._db = lb.Database(path)
                    logger.info("Ladybug lock recovered after stale lock cleanup on %s", path)
                except RuntimeError as exc:
                    raise GraphQueryError(
                        f"Could not acquire Ladybug lock on {path} after "
                        f"{_LOCK_RETRY_ATTEMPTS} retries and stale lock recovery. "
                        f"Another process is actively using the database. "
                        f"Original error: {exc}"
                    ) from exc
            else:
                raise GraphQueryError(
                    f"Could not acquire Ladybug lock on {path} after "
                    f"{_LOCK_RETRY_ATTEMPTS} attempts. Another process is likely "
                    f"using the database. If using uvicorn --reload, the old "
                    f"worker should release the lock shortly. Original error: "
                    f"{last_error}"
                ) from last_error

        self._pool = LadybugConnectionPool(self._db, pool_size=self._pool_size)
        await self._pool.initialize()
        self._initialized = True
        await self._ensure_schema()
        logger.info("Ladybug graph store initialized at %s (pool_size=%d)", path, self._pool_size)

    def _backup_and_recreate(self, path: str, original_error: Exception) -> None:
        """Backup an incompatible database directory and remove it so Ladybug can recreate.

        When upgrading from KuzuDB to Ladybug, the on-disk format is incompatible.
        This method renames the old database directory with a ``.bak`` suffix and
        logs a warning so the user can recover data if needed.
        """
        import shutil
        import time

        if not os.path.exists(path):
            return

        backup = f"{path}.bak.{int(time.time())}"
        logger.warning(
            "Incompatible database at %s (%s). "
            "Backing up to %s and recreating. "
            "Old data will need to be re-ingested.",
            path, original_error, backup,
        )
        try:
            shutil.move(path, backup)
        except OSError as move_exc:
            # If move fails (e.g. cross-device), try copy+remove
            try:
                shutil.copytree(path, backup)
                shutil.rmtree(path)
            except OSError as copy_exc:
                raise GraphQueryError(
                    f"Cannot backup incompatible database at {path}: "
                    f"move failed ({move_exc}), copy+remove also failed ({copy_exc})"
                ) from copy_exc

    @staticmethod
    def _open_database(path: str) -> Any:
        """Open a Ladybug database, falling back to pybind backend if CAPI is unavailable.

        Ladybug 0.17+ supports two backends: ``capi`` (requires shared library) and
        ``pybind`` (bundled in the Python package).  The default ``auto`` tries CAPI
        first, which fails when the native shared library is not installed.  This
        method catches that failure and retries with the pybind backend.
        """
        import ladybug as lb

        try:
            return lb.Database(path)
        except RuntimeError as exc:
            if "c api" in str(exc).lower() or "shared library" in str(exc).lower():
                logger.info("CAPI backend unavailable, falling back to pybind for %s", path)
                return lb.Database(path, backend="pybind")
            raise

    async def _recover_stale_lock(self, path: str, last_error: Exception | None) -> bool:
        """Attempt to detect and remove a stale Ladybug lock file.

        After all retries are exhausted, this method:
        1. Scans the database directory for lock files
        2. Checks if the lock is stale (no other process holds it)
        3. Removes stale lock files and retries

        Returns True if recovery succeeded (lock removed), False otherwise.
        """
        import glob
        import subprocess

        potential_locks: list[str] = []
        if os.path.isdir(path):
            potential_locks.extend(glob.glob(os.path.join(path, "*.lock")))
            potential_locks.extend(glob.glob(os.path.join(path, ".lock")))
        if os.path.isdir(os.path.dirname(path)):
            base = os.path.basename(path)
            potential_locks.extend(glob.glob(os.path.join(os.path.dirname(path), base + "*.lock")))

        if not potential_locks:
            logger.warning("No Ladybug lock files found at %s — cannot recover", path)
            return False

        for lock_path in potential_locks:
            if not os.path.exists(lock_path):
                continue

            try:
                result = subprocess.run(
                    ["lsof", "-F", "p", lock_path],
                    capture_output=True, text=True, timeout=5.0,
                )
                lock_held = result.returncode == 0 and bool(result.stdout.strip())
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                lock_held = True

            if lock_held:
                logger.warning(
                    "Ladybug lock file %s is held by another process — "
                    "cannot remove, another process is actively using the database",
                    lock_path,
                )
                return False

            try:
                os.remove(lock_path)
                logger.warning(
                    "Removed stale Ladybug lock file %s (process crash recovery)",
                    lock_path,
                )
            except OSError as exc:
                logger.warning("Failed to remove stale lock file %s: %s", lock_path, exc)
                return False

        return True

    async def _ensure_schema(self) -> None:
        """Create node/rel tables if they don't exist.

        Schema v2 tables:
        - Entity: core entity node table
        - KnowledgeFragment: Layer-R raw fragment node (canonical SUPPORTED_BY source)
        - ExecutionStepSnapshot: for TRACE_TO source (S-1)
        - MetricDeclaration: for DEFINED_IN source (S-2)
        - CategoryTag: categorization node
        - MetricValue: metric value node
        - Relation: general business relation edge
        - EXTRACTED_FROM: Entity → Entity (mutual-index)
        - SUPPORTED_BY: Entity → Entity (legacy / inline-annotation variant)
        - SUPPORTED_BY_FRAGMENT: KnowledgeFragment → Entity (canonical mutual-index)
        - DEFINED_IN / DEFINED_IN_FROM_METRIC: mutual index edges
        - TRACE_TO: mutual index edge
        - CATEGORIZED_AS / HAS_METRIC: classification edges
        - PRECEDES / SUCCEEDS / LEADS_TO / BECAUSE_OF / ENABLES / PREVENTS / same_entity_as: temporal edges (S-5)
        """
        self._ensure_initialized()

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity(
                entity_id STRING PRIMARY KEY,
                concept STRING,
                space_id STRING,
                properties STRING
            )
        """)

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS KnowledgeFragment(
                fragment_id STRING PRIMARY KEY,
                dataset_id STRING,
                document_id STRING,
                space_id STRING,
                chunk_index INT,
                offset_start INT,
                offset_end INT,
                text STRING,
                vector_id STRING,
                metadata STRING,
                extraction_status STRING,
                content_hash STRING,
                created_at STRING,
                updated_at STRING
            )
        """)

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS ExecutionStepSnapshot(
                id STRING PRIMARY KEY,
                pipeline_run_id STRING,
                step_name STRING,
                step_index INT,
                status STRING,
                started_at STRING,
                finished_at STRING,
                context_snapshot STRING,
                error_message STRING
            )
        """)

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS MetricDeclaration(
                id STRING PRIMARY KEY,
                name STRING,
                metric_type STRING,
                value_type STRING,
                source STRING,
                formula STRING,
                domain_id STRING
            )
        """)

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS RuleDefinitionNode(
                id STRING PRIMARY KEY,
                name STRING,
                description STRING,
                rule_type STRING,
                priority INT64 DEFAULT 100,
                applies_to STRING,
                applicable_categorizations STRING,
                inputs STRING,
                outputs STRING,
                preconditions STRING,
                overrides STRING,
                applicability STRING,
                enabled BOOLEAN DEFAULT true,
                logic_ids STRING,
                domain_id STRING,
                source_pipeline STRING,
                source_content_hash STRING,
                created_at STRING,
                updated_at STRING
            )
        """)

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS CategoryTag(
                id STRING PRIMARY KEY,
                entity_id STRING,
                dimension_name STRING,
                value_code STRING,
                assigned_at STRING,
                assigned_by STRING,
                confidence DOUBLE
            )
        """)

        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS MetricValue(
                id STRING PRIMARY KEY,
                entity_id STRING,
                metric_name STRING,
                value DOUBLE,
                computed_at STRING,
                valid_from STRING,
                valid_to STRING,
                computed_by STRING,
                computation_snapshot STRING
            )
        """)

        # ── Agent Memory: CognitiveNode ──────────────────────────────────
        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS CognitiveNode(
                id STRING PRIMARY KEY,
                memory_type STRING,
                cognitive_layer STRING,
                content STRING,
                content_vector STRING,
                source_fragment_ids STRING,
                belief_status STRING DEFAULT 'accepted',
                ttl_seconds INT64 DEFAULT 0,
                occurred_at STRING,
                created_at STRING,
                updated_at STRING,
                history STRING,
                access_count INT64 DEFAULT 0,
                last_access_at STRING,
                consolidated_at STRING,
                domain_id STRING,
                space_id STRING DEFAULT 'default',
                extraction_hint STRING,
                visibility STRING DEFAULT 'shared',
                created_by STRING,
                feedback_weight DOUBLE DEFAULT 0.5,
                confidence DOUBLE DEFAULT 1.0,
                schema_ref STRING,
                superseded_by STRING,
                proof_count INT64 DEFAULT 1,
                valid_from STRING,
                valid_to STRING,
                recorded_at STRING,
                tags STRING,
                attributes STRING,
                confirmation_count INT64 DEFAULT 0,
                strength DOUBLE DEFAULT 1.0,
                entity_name STRING,
                entity_type STRING,
                version INT64 DEFAULT 1,
                last_confirmed_at STRING,
                consolidation_reasoning STRING,
                compiled_at STRING,
                model_domain STRING,
                source_trust_tier STRING,
                scope STRING,
                source_pipeline STRING,
                source_content_hash STRING
            )
        """)

        # ── Agent Memory: DispositionProfileNode ─────────────────────────
        await self._execute("""
            CREATE NODE TABLE IF NOT EXISTS DispositionProfileNode(
                id STRING PRIMARY KEY,
                skepticism DOUBLE DEFAULT 0.5,
                evidence_demand DOUBLE DEFAULT 0.5,
                abstraction_preference DOUBLE DEFAULT 0.5,
                thoroughness DOUBLE DEFAULT 0.5,
                recency_bias DOUBLE DEFAULT 0.5,
                empathy DOUBLE DEFAULT 0.5,
                risk_tolerance DOUBLE DEFAULT 0.5,
                scene STRING,
                domain_id STRING,
                space_id STRING DEFAULT 'default'
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS Relation(
                FROM Entity TO Entity,
                relation_type STRING,
                relation_id STRING,
                properties STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS EXTRACTED_FROM(
                FROM Entity TO KnowledgeFragment,
                edge_type STRING DEFAULT 'EXTRACTED_FROM',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS SUPPORTED_BY(
                FROM Entity TO Entity,
                edge_type STRING DEFAULT 'SUPPORTED_BY',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS SUPPORTED_BY_FRAGMENT(
                FROM KnowledgeFragment TO Entity,
                edge_type STRING DEFAULT 'SUPPORTED_BY',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS DEFINED_IN(
                FROM Entity TO Entity,
                edge_type STRING DEFAULT 'DEFINED_IN',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS DEFINED_IN_FROM_METRIC(
                FROM MetricDeclaration TO KnowledgeFragment,
                edge_type STRING DEFAULT 'DEFINED_IN',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS DEFINED_IN_FROM_RULE(
                FROM RuleDefinitionNode TO KnowledgeFragment,
                edge_type STRING DEFAULT 'DEFINED_IN',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS TRACE_TO(
                FROM ExecutionStepSnapshot TO KnowledgeFragment,
                edge_type STRING DEFAULT 'TRACE_TO',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS CATEGORIZED_AS(
                FROM Entity TO CategoryTag,
                assigned_at STRING,
                confidence DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_METRIC(
                FROM Entity TO MetricValue,
                computed_at STRING,
                confidence DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS PRECEDES(
                FROM Entity TO Entity,
                time_delta DOUBLE,
                confidence DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS SUCCEEDS(
                FROM Entity TO Entity,
                time_delta DOUBLE,
                confidence DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS LEADS_TO(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS BECAUSE_OF(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS ENABLES(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS PREVENTS(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS same_entity_as(
                FROM Entity TO Entity,
                confidence DOUBLE,
                source_pipeline STRING
            )
        """)

        # ── Agent Memory: Cognitive Edges ────────────────────────────────
        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS PART_OF(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS SUPPORTS(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING,
                evidence_strength DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS CONTRADICTS(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING,
                contradiction_type STRING,
                severity DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS CONSOLIDATED_INTO(
                FROM CognitiveNode TO CognitiveNode,
                consolidated_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS RELATES_TO(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING,
                relation_strength DOUBLE
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS CO_OCCURS_WITH(
                FROM CognitiveNode TO CognitiveNode,
                co_occurrence_count INT64 DEFAULT 1,
                last_seen_at STRING,
                first_seen_at STRING,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS COG_SUPPORTED_BY(
                FROM CognitiveNode TO CognitiveNode,
                evidence_order INT64 DEFAULT 0,
                contribution DOUBLE DEFAULT 0.5,
                edge_confidence DOUBLE DEFAULT 1.0,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS SUPERSEDES(
                FROM CognitiveNode TO CognitiveNode,
                supersede_reason STRING,
                superseded_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS SUMMARIZED_AS(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS LEARNED_INTO(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING
            )
        """)

        await self._execute("""
            CREATE REL TABLE IF NOT EXISTS COGNITIVE_RELATES_TO(
                FROM CognitiveNode TO CognitiveNode,
                created_at STRING,
                relation_strength DOUBLE
            )
        """)

        # ── Agent Memory: Schema Migration ─────────────────────────────
        await self._migrate_cognitive_node_schema()

        # ── Agent Memory: Indexes ────────────────────────────────────────
        # Ladybug auto-creates indexes for PRIMARY KEY columns.
        # Ladybug does not support CREATE INDEX IF NOT EXISTS syntax.
        # As of Ladybug v0.x, CREATE INDEX is not supported at all.
        # When Ladybug adds index support, uncomment the following:
        # for idx_stmt in [
        #     "CREATE INDEX idx_cognitive_type_layer ON CognitiveNode(memory_type)",
        #     "CREATE INDEX idx_cognitive_belief_status ON CognitiveNode(belief_status)",
        #     "CREATE INDEX idx_cognitive_domain ON CognitiveNode(domain_id)",
        #     "CREATE INDEX idx_cognitive_occurred_at ON CognitiveNode(occurred_at)",
        #     "CREATE INDEX idx_disposition_scene ON DispositionProfileNode(scene)",
        #     "CREATE INDEX idx_disposition_domain ON DispositionProfileNode(domain_id)",
        # ]:
        #     try:
        #         await self._execute(idx_stmt)
        #     except RuntimeError as e:
        #         msg = str(e).lower()
        #         if "already exists" not in msg:
        #             logger.warning("Failed to create index: %s — %s", idx_stmt, e)
        pass

    async def _migrate_cognitive_node_schema(self) -> None:
        """Add missing columns to CognitiveNode table for databases created before schema updates.

        CREATE TABLE IF NOT EXISTS does not add new columns to existing tables,
        so we need ALTER TABLE statements to migrate older databases.
        """
        migrations: list[tuple[str, str]] = [
            ("confirmation_count", "INT64 DEFAULT 0"),
            ("strength", "DOUBLE DEFAULT 1.0"),
            ("entity_name", "STRING"),
            ("entity_type", "STRING"),
            ("version", "INT64 DEFAULT 1"),
            ("last_confirmed_at", "STRING"),
            ("consolidation_reasoning", "STRING"),
            ("compiled_at", "STRING"),
            ("model_domain", "STRING"),
            ("source_trust_tier", "STRING"),
            ("scope", "STRING"),
            ("source_pipeline", "STRING"),
            ("source_content_hash", "STRING"),
        ]
        for prop_name, prop_type in migrations:
            try:
                await self._execute(
                    f"ALTER TABLE CognitiveNode ADD {prop_name} {prop_type}"
                )
            except Exception:
                pass

    def _ensure_initialized(self) -> None:
        if not self._initialized or self._pool is None:
            raise GraphQueryError(
                "LadybugGraphStore not initialized. Call initialize() first."
            )

    async def close(self) -> None:
        """Close database connection pool and release resources."""
        if self._pool is not None:
            await self._pool.close()
        if self._db is not None:
            self._db.close()
        self._db = None
        self._pool = None
        self._initialized = False

    # --- Node Management ---

    async def upsert_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> None:
        """Create or update a node.

        Supports both Entity and KnowledgeFragment node types.
        """
        self._ensure_initialized()
        import json

        is_fragment = "KnowledgeFragment" in labels or node_id.startswith("frag:")

        if is_fragment:
            await self._execute(
                "MERGE (n:KnowledgeFragment {fragment_id: $id}) "
                "SET n.dataset_id = $dataset_id, n.document_id = $document_id, "
                "n.space_id = $space_id, n.chunk_index = $chunk_index, "
                "n.offset_start = $offset_start, n.offset_end = $offset_end, "
                "n.text = $text, n.vector_id = $vector_id, "
                "n.metadata = $metadata, n.extraction_status = $extraction_status, "
                "n.content_hash = $content_hash, "
                "n.created_at = $created_at, n.updated_at = $updated_at",
                {
                    "id": node_id,
                    "dataset_id": properties.get("dataset_id", ""),
                    "document_id": properties.get("document_id", ""),
                    "space_id": properties.get("space_id", "default"),
                    "chunk_index": properties.get("chunk_index", 0),
                    "offset_start": properties.get("offset_start", 0),
                    "offset_end": properties.get("offset_end", 0),
                    "text": properties.get("text", ""),
                    "vector_id": properties.get("vector_id", ""),
                    "metadata": json.dumps(properties.get("metadata", {})),
                    "extraction_status": properties.get("extraction_status", "pending"),
                    "content_hash": properties.get("content_hash", ""),
                    "created_at": properties.get("created_at", ""),
                    "updated_at": properties.get("updated_at", ""),
                },
            )
        else:
            concept = labels[0] if labels else "Unknown"
            space_id = properties.get("space_id", "default")
            props_json = json.dumps(properties)

            await self._execute(
                "MERGE (n:Entity {entity_id: $id}) SET n.concept = $concept, "
                "n.space_id = $space_id, n.properties = $props",
                {"id": node_id, "concept": concept, "space_id": space_id, "props": props_json},
            )

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a single node by ID.

        Tries Entity first, then KnowledgeFragment.
        """
        self._ensure_initialized()
        import json

        result = await self._execute(
            "MATCH (n:Entity {entity_id: $id}) RETURN n.entity_id AS id, "
            "n.concept AS concept, n.space_id AS space_id, n.properties AS properties",
            {"id": node_id},
        )
        row = _first_row(result)
        if row is not None:
            return {
                "id": row["id"],
                "fact_object": row["concept"],
                "space_id": row["space_id"],
                "properties": _safe_json_loads(row["properties"]) if row["properties"] else {},
            }

        result = await self._execute(
            "MATCH (n:KnowledgeFragment {fragment_id: $id}) RETURN n.fragment_id AS id, "
            "n.dataset_id AS dataset_id, n.document_id AS document_id, "
            "n.space_id AS space_id, n.chunk_index AS chunk_index, "
            "n.text AS text, n.extraction_status AS extraction_status",
            {"id": node_id},
        )
        row = _first_row(result)
        if row is not None:
            return {
                "id": row["id"],
                "type": "KnowledgeFragment",
                "dataset_id": row["dataset_id"],
                "document_id": row["document_id"],
                "space_id": row["space_id"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
                "extraction_status": row["extraction_status"],
            }

        return None

    async def delete_node(self, node_id: str) -> None:
        """Delete a node and all its edges.

        Tries Entity first, then KnowledgeFragment.
        """
        self._ensure_initialized()
        await self._execute(
            "MATCH (n:Entity {entity_id: $id}) DELETE n",
            {"id": node_id},
        )
        await self._execute(
            "MATCH (n:KnowledgeFragment {fragment_id: $id}) DELETE n",
            {"id": node_id},
        )

    # --- Edge Management ---

    async def upsert_edge(
        self,
        edge_id: str,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create or update an edge (idempotent).

        Note: Ladybug Python binding is not thread-safe, so we keep
        synchronous calls here.  See ADR-008 D3 for details.
        """
        self._ensure_initialized()
        import json

        props_json = json.dumps(properties or {})

        existing = await self._execute(
            "MATCH (a:Entity {entity_id: $from})-[r:Relation {relation_id: $eid}]->(b:Entity {entity_id: $to}) "
            "RETURN r.relation_type",
            {"from": from_node_id, "to": to_node_id, "eid": edge_id},
        )
        row = _first_row(existing)
        if row is not None:
            await self._execute(
                "MATCH (a:Entity {entity_id: $from})-[r:Relation {relation_id: $eid}]->(b:Entity {entity_id: $to}) "
                "SET r.relation_type = $rtype, r.properties = $props",
                {
                    "from": from_node_id,
                    "to": to_node_id,
                    "eid": edge_id,
                    "rtype": edge_type,
                    "props": props_json,
                },
            )
        else:
            await self._execute(
                "MATCH (a:Entity {entity_id: $from}), (b:Entity {entity_id: $to}) "
                "CREATE (a)-[r:Relation {relation_type: $rtype, relation_id: $eid, "
                "properties: $props}]->(b)",
                {
                    "from": from_node_id,
                    "to": to_node_id,
                    "rtype": edge_type,
                    "eid": edge_id,
                    "props": props_json,
                },
            )

    async def get_edges(
        self,
        from_node_id: str | None = None,
        to_node_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query edges."""
        self._ensure_initialized()
        import json

        where_clauses = []
        params: dict[str, Any] = {}

        if from_node_id is not None:
            where_clauses.append("a.entity_id = $from")
            params["from"] = from_node_id
        if to_node_id is not None:
            where_clauses.append("b.entity_id = $to")
            params["to"] = to_node_id
        if edge_type is not None:
            where_clauses.append("r.relation_type = $rtype")
            params["rtype"] = edge_type

        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        query = f"""
            MATCH (a:Entity)-[r:Relation]->(b:Entity)
            {where}
            RETURN a.entity_id AS from_node_id, b.entity_id AS to_node_id,
                   r.relation_type AS edge_type, r.relation_id AS edge_id,
                   r.properties AS properties
        """
        result = await self._execute(query, params)
        rows = _all_rows(result)
        if not rows:
            return []
        return [
            {
                "from_node_id": row["from_node_id"],
                "to_node_id": row["to_node_id"],
                "edge_type": row["edge_type"],
                "edge_id": row["edge_id"],
                "properties": _safe_json_loads(row["properties"]) if row["properties"] else {},
            }
            for row in rows
        ]

    async def delete_edge(self, edge_id: str) -> None:
        """Delete an edge."""
        self._ensure_initialized()
        await self._execute(
            "MATCH (a:Entity)-[r:Relation {relation_id: $eid}]->(b:Entity) DELETE r",
            {"eid": edge_id},
        )

    # --- Graph Queries ---

    async def get_neighbors_basic(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node (generic graph parameters only).

        Pure graph-topology query — no concept or temporal filtering.
        Supports both Entity and KnowledgeFragment nodes.
        """
        self._ensure_initialized()

        arrow_left = ""
        arrow_right = ""
        if direction == "outgoing":
            arrow_left = "-"
            arrow_right = "->"
        elif direction == "incoming":
            arrow_left = "<-"
            arrow_right = "-"
        else:
            arrow_left = "-"
            arrow_right = "-"

        result_rows: list[dict[str, Any]] = []

        # KnowledgeFragment nodes use SUPPORTED_BY_FRAGMENT
        is_fragment = await self._is_knowledge_fragment(node_id)
        if is_fragment:
            result_rows.extend(
                await self._get_fragment_neighbors(
                    node_id, direction=direction, limit=limit
                )
            )
            return result_rows

        # Entity / other node — generic Relation table
        rel_match = (
            f"[r:Relation {{relation_type: '{edge_type}'}}]"
            if edge_type
            else "[r:Relation]"
        )
        where_parts: list[str] = []
        if filter_props:
            for k, v in filter_props.items():
                where_parts.append(f"n.{k} = '{v}'")
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        cypher = f"""
            MATCH (src:Entity {{entity_id: $src_id}}){arrow_left}{rel_match}{arrow_right}(n:Entity)
            {where_clause}
            RETURN n.entity_id AS neighbor_id, r.relation_type AS edge_type,
                   r.relation_id AS edge_id, label(r) AS rel_table,
                   r.properties AS edge_props
            LIMIT {limit}
        """
        ladybug_result = await self._execute(cypher, {"src_id": node_id})
        rows = _all_rows(ladybug_result)
        if rows:
            for row in rows:
                edge_props_raw = row.get("edge_props")
                edge_props = _safe_json_loads(edge_props_raw) if isinstance(edge_props_raw, str) else (edge_props_raw or {})
                result_rows.append({
                    "neighbor_id": row["neighbor_id"],
                    "edge_id": row["edge_id"],
                    "edge_type": row["edge_type"],
                    "direction": direction if direction != "both" else "outgoing",
                    "confidence": edge_props.get("confidence"),
                    "edge_text": edge_props.get("edge_text", ""),
                    "offset_start": edge_props.get("offset_start", 0),
                    "offset_end": edge_props.get("offset_end", 0),
                })

        return result_rows

    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
        node_concept: str | None = None,
        as_of: str | None = None,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node.

        Supports both Entity nodes and KnowledgeFragment nodes.  For
        KnowledgeFragment nodes the method additionally queries the
        ``SUPPORTED_BY_FRAGMENT`` relation table, returning full edge
        attributes (confidence, edge_text, offset_start, offset_end) so that
        ``_expand_via_supported_by`` in MutualIndexCollaborative can read them.

        Returns rows with keys:
            neighbor_id, edge_id, edge_type, direction,
            confidence (optional), edge_text (optional),
            offset_start (optional), offset_end (optional)

        Args:
            node_concept: When provided, ladybug pushes this filter into the WHERE
                clause to avoid returning nodes that don't match the
                fact_object.
            as_of: Optional point-in-time timestamp for temporal filtering.
            include_history: If true, include all historical versions.
        """
        self._ensure_initialized()
        import json

        arrow_left = ""
        arrow_right = ""
        if direction == "outgoing":
            arrow_left = "-"
            arrow_right = "->"
        elif direction == "incoming":
            arrow_left = "<-"
            arrow_right = "-"
        else:
            arrow_left = "-"
            arrow_right = "-"

        result_rows: list[dict[str, Any]] = []

        # ── Branch A: KnowledgeFragment node ─────────────────────────────────
        # These nodes are connected via SUPPORTED_BY_FRAGMENT (outgoing) and have
        # no entries in the generic Relation table.
        is_fragment = await self._is_knowledge_fragment(node_id)
        if is_fragment:
            result_rows.extend(
                await self._get_fragment_neighbors(
                    node_id, direction=direction, limit=limit
                )
            )
            return result_rows

        # ── Branch B: Entity / other node — generic Relation table ───────────
        rel_match = (
            f"[r:Relation {{relation_type: '{edge_type}'}}]"
            if edge_type
            else "[r:Relation]"
        )
        where_parts: list[str] = []
        if node_concept:
            where_parts.append(f"n.concept = '{node_concept}'")
        if filter_props:
            for k, v in filter_props.items():
                where_parts.append(f"n.{k} = '{v}'")
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        cypher = f"""
            MATCH (src:Entity {{entity_id: $src_id}}){arrow_left}{rel_match}{arrow_right}(n:Entity)
            {where_clause}
            RETURN n.entity_id AS neighbor_id, r.relation_type AS edge_type,
                   r.relation_id AS edge_id, label(r) AS rel_table,
                   r.properties AS edge_props, n.properties AS properties
            LIMIT {limit}
        """
        ladybug_result = await self._execute(cypher, {"src_id": node_id})
        rows = _all_rows(ladybug_result)
        if rows:
            for row in rows:
                if as_of and not include_history:
                    props_raw = row.get("properties")
                    props = _safe_json_loads(props_raw) if isinstance(props_raw, str) else (props_raw or {})
                    valid_from = props.get("valid_from")
                    valid_to = props.get("valid_to")
                    if valid_from and valid_from > as_of:
                        continue
                    if valid_to and valid_to <= as_of:
                        continue
                edge_props_raw = row.get("edge_props")
                edge_props = _safe_json_loads(edge_props_raw) if isinstance(edge_props_raw, str) else (edge_props_raw or {})
                result_rows.append({
                    "neighbor_id": row["neighbor_id"],
                    "edge_id": row["edge_id"],
                    "edge_type": row["edge_type"],
                    "direction": direction if direction != "both" else "outgoing",
                    "confidence": edge_props.get("confidence"),
                    "edge_text": edge_props.get("edge_text", ""),
                    "offset_start": edge_props.get("offset_start", 0),
                    "offset_end": edge_props.get("offset_end", 0),
                })

        return result_rows

    async def _is_knowledge_fragment(self, node_id: str) -> bool:
        """Return True if node_id exists in the KnowledgeFragment table."""
        if node_id in self._fragment_cache:
            return self._fragment_cache[node_id]
        self._ensure_initialized()
        try:
            result = await self._execute(
                "MATCH (f:KnowledgeFragment {fragment_id: $fid}) RETURN count(*) AS cnt",
                {"fid": node_id},
            )
            row = _first_row(result)
            is_frag = row is not None and int(row["cnt"]) > 0
        except Exception:
            is_frag = False
        self._fragment_cache[node_id] = is_frag
        return is_frag

    async def get_k_hop_neighbors(
        self,
        node_id: str,
        k: int = 2,
        edge_type: str | None = None,
        direction: str = "both",
        limit_per_hop: int = 100,
    ) -> dict[str, float]:
        """Get all neighbors within k hops using BFS with get_neighbors().

        Args:
            node_id: Starting node ID.
            k: Number of hops (depth). Defaults to 2.
            edge_type: Optional edge type filter.
            direction: Traversal direction ("outgoing", "incoming", "both").
            limit_per_hop: Max neighbors per node per hop.

        Returns:
            Dict mapping neighbor_id → proximity score (1/(1+depth)).
        """
        self._ensure_initialized()
        visited: set[str] = {node_id}
        scores: dict[str, float] = {}
        queue = [node_id]
        depth = 0
        while queue and depth < k:
            next_queue: list[str] = []
            for nid in queue:
                neighbors = await self.get_neighbors(
                    node_id=nid,
                    edge_type=edge_type,
                    direction=direction,
                    limit=limit_per_hop,
                )
                for n in neighbors:
                    neighbor_id = n["neighbor_id"]
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_queue.append(neighbor_id)
                        scores[neighbor_id] = max(
                            scores.get(neighbor_id, 0.0),
                            1.0 / (1.0 + depth),
                        )
            queue = next_queue
            depth += 1
        return scores

    async def _get_fragment_neighbors(
        self,
        fragment_id: str,
        direction: str = "outgoing",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return neighbors of a KnowledgeFragment via SUPPORTED_BY_FRAGMENT.

        Returns rows with full mutual-index edge attributes so that
        MutualIndexCollaborative can read confidence, edge_text and offsets
        without an extra round-trip.
        """
        self._ensure_initialized()
        rows: list[dict[str, Any]] = []
        if direction not in ("outgoing", "both"):
            return rows

        try:
            cypher = f"""
                MATCH (f:KnowledgeFragment {{fragment_id: $fid}})
                      -[r:SUPPORTED_BY_FRAGMENT]->
                      (e:Entity)
                RETURN e.entity_id AS neighbor_id,
                       r.edge_type AS edge_type,
                       r.confidence AS confidence,
                       r.edge_text AS edge_text,
                       r.offset_start AS offset_start,
                       r.offset_end AS offset_end
                LIMIT {limit}
            """
            result = await self._execute(cypher, {"fid": fragment_id})
            rows = _all_rows(result)
            if not rows:
                return rows
            for row in rows:
                rows.append({
                    "neighbor_id": row["neighbor_id"],
                    "edge_id": "",
                    "edge_type": row.get("edge_type") or "SUPPORTED_BY",
                    "direction": "outgoing",
                    "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
                    "edge_text": row.get("edge_text") or "",
                    "offset_start": int(row["offset_start"]) if row.get("offset_start") is not None else 0,
                    "offset_end": int(row["offset_end"]) if row.get("offset_end") is not None else 0,
                })
        except Exception as exc:
            logger.debug("_get_fragment_neighbors failed for %s: %s", fragment_id, exc)
        return rows


    async def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_depth: int = 3,
        edge_types: list[str] | None = None,
    ) -> list[list[dict[str, Any]]]:
        """Find paths between nodes."""
        self._ensure_initialized()

        if target_id:
            cypher = f"""
                MATCH (src:Entity {{entity_id: $src}})-[r*1..{max_depth}]-(tgt:Entity {{entity_id: $tgt}})
                RETURN src.entity_id AS source, tgt.entity_id AS target
                LIMIT 50
            """
            result = await self._execute(cypher, {"src": source_id, "tgt": target_id})
        else:
            cypher = f"""
                MATCH (src:Entity {{entity_id: $src}})-[r*1..{max_depth}]-(n:Entity)
                RETURN src.entity_id AS source, n.entity_id AS target
                LIMIT 50
            """
            result = await self._execute(cypher, {"src": source_id})

        rows = _all_rows(result)
        if not rows:
            return []

        paths: list[list[dict[str, Any]]] = []
        for row in rows:
            paths.append([
                {"node_id": row["source"]},
                {"node_id": row["target"]},
            ])
        return paths

    async def detect_cycles(
        self,
        center_id: str,
        edge_types: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[list[str]]:
        """Detect cycles starting from a node."""
        self._ensure_initialized()
        rel_constraint = ""
        if edge_types:
            types = " | ".join(f"'{et}'" for et in edge_types)
            rel_constraint = f":Relation WHERE r.relation_type IN [{types}]"
        else:
            rel_constraint = ":Relation"

        cypher = f"""
            MATCH cycle = (center:Entity {{entity_id: $cid}})-{rel_constraint}*2..{max_depth}-
            (center)
            RETURN [node IN nodes(cycle) | node.entity_id] AS cycle
            LIMIT 50
        """
        result = await self._execute(cypher, {"cid": center_id})
        rows = _all_rows(result)
        if not rows:
            return []
        return [list(row["cycle"]) for row in rows]

    async def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query (advanced interface).

        This is the primary escape hatch for complex graph patterns that are
        better expressed in Cypher than as a series of ``get_neighbors`` calls.

        Args:
            query: Cypher query string.
            parameters: Query parameters dict.

        Returns:
            List of result rows as dicts.
        """
        self._ensure_initialized()
        import json

        result = await self._execute(query, parameters or {})
        rows = _all_rows(result)
        if not rows:
            return []
        # Convert JSON columns back to dicts
        records = []
        for row in rows:
            record = dict(row)
            for k, v in record.items():
                if isinstance(v, str) and v.startswith("{"):
                    try:
                        record[k] = _safe_json_loads(v)
                    except (json.JSONDecodeError, TypeError):
                        pass
            records.append(record)
        return records

    # --- Graph Algorithms ---

    async def compute_graph_metric(
        self,
        algorithm: str,
        node_id: str | None = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a graph algorithm (centrality, community, etc.).

        Note: Ladybug does not have built-in graph algorithms. This method provides
        a thin wrapper around simple Cypher-based computations. For full
        algorithm support (PageRank, betweenness centrality, etc.), use
        ladybug's Python bindings directly or a dedicated graph processing library.
        """
        self._ensure_initialized()
        config = config or {}
        config.update(kwargs)

        if algorithm == "centrality":
            metric = config.get("metric", "degree")
            if metric == "degree":
                cypher = """
                    MATCH (n:Entity)-[r:Relation]->(m:Entity)
                    WITH n.entity_id AS node, count(r) AS degree
                    RETURN node, degree
                    ORDER BY degree DESC
                    LIMIT 100
                """
            result = await self._execute(cypher)
            rows = _all_rows(result)
            if node_id:
                match = [r for r in rows if r["node"] == node_id]
                return {"algorithm": "centrality", "metric": "degree", "node_id": node_id, "value": int(match[0]["degree"]) if match else 0}
            return {"algorithm": "centrality", "metric": "degree", "values": {r["node"]: int(r["degree"]) for r in rows}}

        elif algorithm == "component":
            # Weakly connected components via label propagation
            cypher = """
                MATCH (n:Entity)
                WITH collect(n.entity_id) AS nodes
                UNWIND nodes AS a
                UNWIND nodes AS b
                WITH a, b WHERE a <> b
                MATCH path = (a:Entity {entity_id: a})-[*0..2]-(b:Entity {entity_id: b})
                WITH a, collect(DISTINCT b) AS reachable
                RETURN a AS node, size(reachable) AS component_size
            """
            result = await self._execute(cypher)
            rows = _all_rows(result)
            max_size = max(r["component_size"] for r in rows) if rows else 0
            return {"algorithm": "component", "component_count": int(max_size)}

        elif algorithm == "community":
            # Simple community detection via connected components
            cypher = """
                MATCH (n:Entity)
                OPTIONAL MATCH (n)-[r]-()
                WITH n.entity_id AS node, count(r) AS degree
                RETURN node, degree
                ORDER BY degree DESC
                LIMIT 100
            """
            result = await self._execute(cypher)
            rows = _all_rows(result)
            return {"algorithm": "community", "community_count": len(rows)}

        else:
            raise GraphQueryError(f"Unknown graph algorithm: {algorithm}")

        return {"algorithm": algorithm}

    # --- Batch Operations ---

    async def batch_upsert(
        self,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Batch write nodes and edges.

        Returns:
            {"nodes_written": N, "edges_written": M}
        """
        self._ensure_initialized()
        nodes_written = 0
        edges_written = 0

        if nodes:
            for node in nodes:
                await self.upsert_node(
                    node_id=node["node_id"],
                    labels=node.get("labels", []),
                    properties=node.get("properties", {}),
                )
                nodes_written += 1

        if edges:
            for edge in edges:
                await self.upsert_edge(
                    edge_id=edge["edge_id"],
                    from_node_id=edge["from_node_id"],
                    to_node_id=edge["to_node_id"],
                    edge_type=edge["edge_type"],
                    properties=edge.get("properties"),
                )
                edges_written += 1

        return {"nodes_written": nodes_written, "edges_written": edges_written}

    # --- Schema v2 Extended Methods ---

    async def get_neighborhood(
        self,
        node_id: str,
        depth: int = 1,
        limit: int = 100,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Get neighborhood subgraph around a node.

        Args:
            node_id: Center node ID.
            depth: Traversal depth (1-3).
            limit: Max nodes to return.
            min_confidence: Minimum confidence filter on edges.

        Returns:
            Dict with "nodes" and "edges" lists.
        """
        self._ensure_initialized()
        import json

        cypher = f"""
            MATCH path = (center:Entity {{entity_id: $id}})-[r*1..{depth}]-(n)
            RETURN DISTINCT n.entity_id AS id, n.concept AS concept,
                   n.space_id AS space_id, n.properties AS properties,
                   [rel IN relationships(path) | {{
                       from_id: startNode(rel).entity_id,
                       to_id: endNode(rel).entity_id,
                       type: type(rel),
                       props: rel.properties
                   }}] AS edges
            LIMIT {limit}
        """
        result = await self._execute(cypher, {"id": node_id})
        rows = _all_rows(result)
        if not rows:
            return {"nodes": [], "edges": []}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = {node_id}
        seen_edges: set[str] = set()

        center_row = _first_row(await self._execute(
            "MATCH (c:Entity {entity_id: $id}) RETURN c.entity_id AS id, "
            "c.concept AS concept, c.space_id AS space_id, c.properties AS properties",
            {"id": node_id},
        ))
        if center_row is not None:
            nodes.append({
                "id": center_row["id"],
                "fact_object": center_row["concept"],
                "space_id": center_row["space_id"],
                "properties": _safe_json_loads(center_row["properties"]) if center_row["properties"] else {},
            })

        for row in rows:
            nid = row["id"]
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({
                    "id": nid,
                    "fact_object": row["concept"],
                    "space_id": row["space_id"],
                    "properties": _safe_json_loads(row["properties"]) if row["properties"] else {},
                })
            for edge_info in row.get("edges", []):
                edge_key = f"{edge_info.get('from_id')}:{edge_info.get('to_id')}:{edge_info.get('type')}"
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    props = edge_info.get("props")
                    if isinstance(props, str):
                        try:
                            props = _safe_json_loads(props)
                        except (json.JSONDecodeError, TypeError):
                            props = {}
                    confidence = (props or {}).get("confidence", 1.0)
                    if confidence >= min_confidence:
                        edges.append({
                            "from_id": edge_info.get("from_id"),
                            "to_id": edge_info.get("to_id"),
                            "type": edge_info.get("type"),
                            "properties": props or {},
                        })

        return {"nodes": nodes, "edges": edges}

    async def get_entity_at(
        self,
        fact_object: str,
        as_of: str,
        domain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Temporal slice query: get entities at a specific point in time.

        Args:
            fact_object: Entity type filter.
            as_of: Timestamp for point-in-time query.
            domain_id: Optional domain filter.

        Returns:
            List of node records valid at the given time.
        """
        self._ensure_initialized()
        import json

        where_parts = ["n.concept = $concept"]
        params: dict[str, Any] = {"concept": fact_object}

        if domain_id:
            where_parts.append("n.space_id = $domain")
            params["domain"] = domain_id

        where = "WHERE " + " AND ".join(where_parts)
        cypher = f"""
            MATCH (n:Entity)
            {where}
            RETURN n.entity_id AS id, n.concept AS concept,
                   n.space_id AS space_id, n.properties AS properties
        """
        result = await self._execute(cypher, params)
        rows = _all_rows(result)
        if not rows:
            return []

        records = []
        for row in rows:
            props = _safe_json_loads(row["properties"]) if row["properties"] else {}
            valid_from = props.get("valid_from")
            valid_to = props.get("valid_to")
            if valid_from and valid_from > as_of:
                continue
            if valid_to and valid_to <= as_of:
                continue
            records.append({
                "id": row["id"],
                "fact_object": row["concept"],
                "space_id": row["space_id"],
                "properties": props,
            })
        return records

    async def get_edge_at(
        self,
        relation_name: str,
        as_of: str,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Temporal slice query: get edges at a specific point in time.

        Args:
            relation_name: Edge type filter.
            as_of: Timestamp for point-in-time query.
            min_confidence: Minimum confidence filter.

        Returns:
            List of edge records valid at the given time.
        """
        self._ensure_initialized()
        import json

        cypher = """
            MATCH (a:Entity)-[r:Relation {relation_type: $rtype}]->(b:Entity)
            RETURN a.entity_id AS from_id, b.entity_id AS to_id,
                   r.relation_type AS edge_type, r.relation_id AS edge_id,
                   r.properties AS properties
        """
        result = await self._execute(cypher, {"rtype": relation_name})
        rows = _all_rows(result)
        if not rows:
            return []

        records = []
        for row in rows:
            props = _safe_json_loads(row["properties"]) if row["properties"] else {}
            valid_from = props.get("valid_from")
            valid_to = props.get("valid_to")
            if valid_from and valid_from > as_of:
                continue
            if valid_to and valid_to <= as_of:
                continue
            confidence = props.get("confidence", 1.0)
            if confidence < min_confidence:
                continue
            records.append({
                "from_id": row["from_id"],
                "to_id": row["to_id"],
                "edge_type": row["edge_type"],
                "edge_id": row["edge_id"],
                "properties": props,
            })
        return records

    async def get_by_source_pipeline(
        self,
        source_pipeline: str,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Traceability query: get entities by source pipeline.

        Args:
            source_pipeline: Source pipeline identifier.
            label: Optional entity type filter.

        Returns:
            List of node records from the given pipeline.
        """
        self._ensure_initialized()
        import json

        where_parts = ["n.properties CONTAINS $pipeline"]
        params: dict[str, Any] = {"pipeline": source_pipeline}

        if label:
            where_parts.append("n.concept = $label")
            params["label"] = label

        where = "WHERE " + " AND ".join(where_parts)
        cypher = f"""
            MATCH (n:Entity)
            {where}
            RETURN n.entity_id AS id, n.concept AS concept,
                   n.space_id AS space_id, n.properties AS properties
        """
        result = await self._execute(cypher, params)
        rows = _all_rows(result)
        if not rows:
            return []

        records = []
        for row in rows:
            props = _safe_json_loads(row["properties"]) if row["properties"] else {}
            if props.get("source_pipeline") != source_pipeline:
                continue
            records.append({
                "id": row["id"],
                "fact_object": row["concept"],
                "space_id": row["space_id"],
                "properties": props,
            })
        return records

    async def create_mutual_index_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a mutual-index edge (EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO).

        Args:
            edge_type: One of EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO.
            from_id: Source node ID.
            to_id: Target node ID.
            properties: Edge properties (confidence, edge_text, source_file, etc.).

        Returns:
            Created edge record.
        """
        self._ensure_initialized()

        valid_types = {"EXTRACTED_FROM", "SUPPORTED_BY", "DEFINED_IN", "TRACE_TO"}
        if edge_type not in valid_types:
            raise GraphQueryError(f"Invalid mutual-index edge type: {edge_type}. Must be one of {valid_types}")

        if edge_type == "TRACE_TO":
            from_label = "ExecutionStepSnapshot"
            from_id_field = "id"
        elif edge_type == "DEFINED_IN" and from_id.startswith("metric:"):
            from_label = "MetricDeclaration"
            from_id_field = "id"
        elif edge_type == "DEFINED_IN" and from_id.startswith("rule:"):
            from_label = "RuleDefinitionNode"
            from_id_field = "id"
        else:
            from_label = "Entity"
            from_id_field = "entity_id"

        if edge_type == "EXTRACTED_FROM":
            to_label = "KnowledgeFragment"
            to_id_field = "fragment_id"
        elif edge_type == "DEFINED_IN" and from_label in ("MetricDeclaration", "RuleDefinitionNode"):
            to_label = "KnowledgeFragment"
            to_id_field = "fragment_id"
        elif edge_type == "TRACE_TO":
            to_label = "KnowledgeFragment"
            to_id_field = "fragment_id"
        else:
            to_label = "Entity"
            to_id_field = "entity_id"

        if edge_type == "DEFINED_IN" and from_label == "MetricDeclaration":
            rel_label = "DEFINED_IN_FROM_METRIC"
        elif edge_type == "DEFINED_IN" and from_label == "RuleDefinitionNode":
            rel_label = "DEFINED_IN_FROM_RULE"
        elif edge_type == "SUPPORTED_BY" and from_label == "KnowledgeFragment":
            rel_label = "SUPPORTED_BY_FRAGMENT"
        else:
            rel_label = edge_type

        props_parts = []
        params: dict[str, Any] = {"from_id": from_id, "to_id": to_id}
        for k, v in properties.items():
            props_parts.append(f"{k}: ${k}")
            params[k] = v

        props_str = ", ".join(props_parts) if props_parts else ""

        cypher = f"""
            MATCH (a:{from_label} {{{from_id_field}: $from_id}}), (b:{to_label} {{{to_id_field}: $to_id}})
            MERGE (a)-[r:{rel_label}]->(b)
            {"SET " + props_str if props_str else ""}
            RETURN label(r) AS edge_type, a.{from_id_field} AS from_id, b.{to_id_field} AS to_id
        """
        await self._execute(cypher, params)
        return {
            "edge_type": edge_type,
            "from_id": from_id,
            "to_id": to_id,
            "properties": properties,
        }

    async def create_cognitive_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an edge between two CognitiveNodes.

        Args:
            edge_type: One of PART_OF, SUPPORTS, CONTRADICTS,
                CONSOLIDATED_INTO, RELATES_TO, CO_OCCURS_WITH, COG_SUPPORTED_BY.
            from_id: Source CognitiveNode ID.
            to_id: Target CognitiveNode ID.
            properties: Optional edge properties. Only properties defined
                in the edge table schema will be set.

        Returns:
            Created edge record.
        """
        self._ensure_initialized()

        valid_types = {"PART_OF", "SUPPORTS", "CONTRADICTS", "CONSOLIDATED_INTO", "RELATES_TO", "CO_OCCURS_WITH", "COG_SUPPORTED_BY", "SUPERSEDES", "SUMMARIZED_AS", "LEARNED_INTO", "COGNITIVE_RELATES_TO"}
        if edge_type not in valid_types:
            raise GraphQueryError(f"Invalid cognitive edge type: {edge_type}. Must be one of {valid_types}")

        edge_schemas = {
            "PART_OF": {"created_at"},
            "SUPPORTS": {"created_at", "evidence_strength"},
            "CONTRADICTS": {"created_at", "contradiction_type", "severity"},
            "CONSOLIDATED_INTO": {"consolidated_at"},
            "RELATES_TO": {"created_at", "relation_strength"},
            "CO_OCCURS_WITH": {"co_occurrence_count", "last_seen_at", "first_seen_at", "created_at"},
            "COG_SUPPORTED_BY": {"evidence_order", "contribution", "edge_confidence", "created_at"},
            "SUPERSEDES": {"supersede_reason", "superseded_at"},
            "SUMMARIZED_AS": {"created_at"},
            "LEARNED_INTO": {"created_at"},
            "COGNITIVE_RELATES_TO": {"created_at", "relation_strength"},
        }

        allowed_props = edge_schemas.get(edge_type, set())
        props = properties or {}
        filtered_props = {k: v for k, v in props.items() if k in allowed_props}

        params: dict[str, Any] = {"from_id": from_id, "to_id": to_id}

        props_parts = []
        for k, v in filtered_props.items():
            props_parts.append(f"r.{k} = ${k}")
            params[k] = v

        set_clause = ", ".join(props_parts) if props_parts else ""

        cypher = f"""
            MATCH (a:CognitiveNode {{id: $from_id}}), (b:CognitiveNode {{id: $to_id}})
            MERGE (a)-[r:{edge_type}]->(b)
            {f"SET {set_clause}" if set_clause else ""}
            RETURN a.id AS from_id, b.id AS to_id
        """
        await self._execute(cypher, params)
        return {
            "edge_type": edge_type,
            "from_id": from_id,
            "to_id": to_id,
            "properties": filtered_props,
        }

    async def query_cognitive_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query cognitive edges with optional filters."""
        self._ensure_initialized()

        edge_table_map = {
            "CONSOLIDATED_INTO": "CONSOLIDATED_INTO",
            "SUMMARIZED_AS": "SUMMARIZED_AS",
            "LEARNED_INTO": "LEARNED_INTO",
            "SUPERSEDES": "SUPERSEDES",
            "CONTRADICTS": "CONTRADICTS",
            "COGNITIVE_RELATES_TO": "COGNITIVE_RELATES_TO",
            "RELATES_TO": "RELATES_TO",
            "CO_OCCURS_WITH": "CO_OCCURS_WITH",
            "PART_OF": "PART_OF",
            "SUPPORTS": "SUPPORTS",
            "COG_SUPPORTED_BY": "COG_SUPPORTED_BY",
        }

        edge_time_fields = {
            "CONSOLIDATED_INTO": "consolidated_at",
            "SUPERSEDES": "superseded_at",
        }

        results: list[dict[str, Any]] = []

        if edge_type and edge_type in edge_table_map:
            tables = [(edge_type, edge_table_map[edge_type])]
        else:
            tables = list(edge_table_map.items())

        for etype, table in tables:
            where_clauses = []
            params: dict[str, Any] = {}

            if from_id:
                where_clauses.append("a.id = $from_id")
                params["from_id"] = from_id
            if to_id:
                where_clauses.append("b.id = $to_id")
                params["to_id"] = to_id

            where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            time_field = edge_time_fields.get(etype, "created_at")

            cypher = f"""
                MATCH (a:CognitiveNode)-[r:{table}]->(b:CognitiveNode)
                {where}
                RETURN a.id AS from_id, b.id AS to_id, r.{time_field} AS time_val
                LIMIT {limit}
            """

            try:
                result_set = await self._execute(cypher, params)
                while result_set.has_next():
                    row = result_set.get_next()
                    results.append({
                        "edge_type": etype,
                        "from_id": row[0],
                        "to_id": row[1],
                        "created_at": row[2] if len(row) > 2 else None,
                    })
            except Exception:
                continue

            if len(results) >= limit:
                break

        return results[:limit]

    async def get_mutual_index_edges(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get mutual-index edges for a node.

        Args:
            node_id: Node ID to query.
            edge_type: Optional specific edge type filter.
            direction: "outgoing", "incoming", or "both".

        Returns:
            List of mutual-index edge records.
        """
        self._ensure_initialized()
        import json

        mutual_types = ["EXTRACTED_FROM", "SUPPORTED_BY", "DEFINED_IN", "TRACE_TO"]
        if edge_type:
            mutual_types = [edge_type]

        results: list[dict[str, Any]] = []
        for mtype in mutual_types:
            query_specs = self._MUTUAL_INDEX_QUERIES.get(mtype, [])
            for spec in query_specs:
                rel_name = spec["rel"]
                fl = spec["from_label"]
                fpk = spec["from_pk"]
                tl = spec["to_label"]
                tpk = spec["to_pk"]

                if direction in ("outgoing", "both"):
                    cypher = f"""
                        MATCH (a:{fl} {{{fpk}: $id}})-[r:{rel_name}]->(b:{tl})
                        RETURN a.{fpk} AS from_id, b.{tpk} AS to_id,
                               label(r) AS edge_type, r AS props
                    """
                    try:
                        result = await self._execute(cypher, {"id": node_id})
                        rows = _all_rows(result)
                        for row in rows:
                            props = row.get("props", {})
                            if isinstance(props, str):
                                try:
                                    props = _safe_json_loads(props)
                                except (json.JSONDecodeError, TypeError):
                                    props = {}
                            results.append({
                                "from_id": row["from_id"],
                                "to_id": row["to_id"],
                                "edge_type": row["edge_type"],
                                "direction": "outgoing",
                                "properties": props if isinstance(props, dict) else {},
                            })
                    except Exception:
                        pass

                if direction in ("incoming", "both"):
                    cypher = f"""
                        MATCH (a:{fl})-[r:{rel_name}]->(b:{tl} {{{tpk}: $id}})
                        RETURN a.{fpk} AS from_id, b.{tpk} AS to_id,
                               label(r) AS edge_type, r AS props
                    """
                    try:
                        result = await self._execute(cypher, {"id": node_id})
                        rows = _all_rows(result)
                        for row in rows:
                            props = row.get("props", {})
                            if isinstance(props, str):
                                try:
                                    props = _safe_json_loads(props)
                                except (json.JSONDecodeError, TypeError):
                                    props = {}
                            results.append({
                                "from_id": row["from_id"],
                                "to_id": row["to_id"],
                                "edge_type": row["edge_type"],
                                "direction": "incoming",
                                "properties": props if isinstance(props, dict) else {},
                            })
                    except Exception:
                        pass

        return results

    async def update_feedback_weight(
        self,
        entity_id: str,
        feedback: float,
        learning_rate: float = 0.1,
    ) -> None:
        """Update feedback weight for an entity (memory reinforcement).

        Uses exponential moving average:
            new_weight = (1 - lr) * old_weight + lr * feedback

        Args:
            entity_id: Entity to update.
            feedback: New feedback value (0.0 to 1.0).
            learning_rate: Learning rate for EMA.
        """
        self._ensure_initialized()
        import json

        cypher = """
            MATCH (n:Entity {entity_id: $id})
            RETURN n.properties AS props
        """
        result = await self._execute(cypher, {"id": entity_id})
        row = _first_row(result)
        if row is None:
            return

        props_str = row["props"]
        props = _safe_json_loads(props_str) if props_str else {}
        old_weight = props.get("feedback_weight", 0.5)
        new_weight = (1 - learning_rate) * old_weight + learning_rate * feedback
        props["feedback_weight"] = new_weight

        await self._execute(
            "MATCH (n:Entity {entity_id: $id}) SET n.properties = $props",
            {"id": entity_id, "props": json.dumps(props)},
        )

    # --- Agent Memory: CognitiveNode Management ---

    async def upsert_cognitive_node(
        self,
        node_id: str,
        memory_type: str,
        cognitive_layer: str,
        content: str,
        content_vector: list[float] | None = None,
        source_fragment_ids: list[str] | None = None,
        belief_status: str = "accepted",
        ttl_seconds: int = 0,
        occurred_at: str | None = None,
        extraction_hint: str | None = None,
        domain_id: str | None = None,
        space_id: str = "default",
        history: list[dict[str, Any]] | None = None,
        visibility: str = "shared",
        created_by: str | None = None,
        feedback_weight: float = 0.5,
        confidence: float = 1.0,
        access_count: int = 0,
        last_access_at: str | None = None,
        consolidated_at: str | None = None,
        schema_ref: str | None = None,
        superseded_by: str | None = None,
        proof_count: int = 1,
        valid_from: str | None = None,
        valid_to: str | None = None,
        recorded_at: str | None = None,
        tags: list[str] | None = None,
        attributes: dict[str, str] | None = None,
        confirmation_count: int = 0,
        strength: float = 1.0,
        entity_name: str | None = None,
        entity_type: str | None = None,
        version: int = 1,
        last_confirmed_at: str | None = None,
        consolidation_reasoning: str | None = None,
        compiled_at: str | None = None,
        model_domain: str | None = None,
        source_trust_tier: str | None = None,
        scope: str | None = None,
        source_pipeline: str | None = None,
        source_content_hash: str | None = None,
    ) -> None:
        self._ensure_initialized()
        import json
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        params: dict[str, Any] = {
            "id": str(node_id),
            "memory_type": str(memory_type),
            "cognitive_layer": str(cognitive_layer),
            "content": str(content),
            "content_vector": json.dumps(content_vector) if content_vector else None,
            "source_fragment_ids": json.dumps(source_fragment_ids) if source_fragment_ids else None,
            "belief_status": str(belief_status),
            "ttl_seconds": int(ttl_seconds),
            "occurred_at": occurred_at,
            "extraction_hint": extraction_hint,
            "domain_id": domain_id,
            "space_id": str(space_id),
            "created_at": now,
            "updated_at": now,
            "history": json.dumps(history) if history else json.dumps([]),
            "visibility": str(visibility),
            "created_by": created_by,
            "feedback_weight": float(feedback_weight),
            "confidence": float(confidence),
            "access_count": int(access_count),
            "last_access_at": last_access_at,
            "consolidated_at": consolidated_at,
            "schema_ref": schema_ref,
            "superseded_by": superseded_by,
            "proof_count": int(proof_count),
            "valid_from": valid_from,
            "valid_to": valid_to,
            "recorded_at": recorded_at,
            "tags": json.dumps(tags) if tags else json.dumps([]),
            "attributes": json.dumps(attributes) if attributes else json.dumps({}),
            "confirmation_count": int(confirmation_count),
            "strength": float(strength),
            "entity_name": entity_name,
            "entity_type": entity_type,
            "version": int(version),
            "last_confirmed_at": last_confirmed_at,
            "consolidation_reasoning": consolidation_reasoning,
            "compiled_at": compiled_at,
            "model_domain": model_domain,
            "source_trust_tier": source_trust_tier,
            "scope": scope,
            "source_pipeline": source_pipeline,
            "source_content_hash": source_content_hash,
        }

        await self._execute("""
            MERGE (n:CognitiveNode {id: $id})
            ON CREATE SET n.created_at = $created_at,
                          n.history = $history
            ON MATCH SET n.updated_at = $updated_at,
                         n.history = $history
            SET n.memory_type = $memory_type,
                n.cognitive_layer = $cognitive_layer,
                n.content = $content,
                n.content_vector = $content_vector,
                n.source_fragment_ids = $source_fragment_ids,
                n.belief_status = $belief_status,
                n.ttl_seconds = $ttl_seconds,
                n.occurred_at = $occurred_at,
                n.extraction_hint = $extraction_hint,
                n.domain_id = $domain_id,
                n.space_id = $space_id,
                n.visibility = $visibility,
                n.created_by = $created_by,
                n.feedback_weight = $feedback_weight,
                n.confidence = $confidence,
                n.access_count = $access_count,
                n.last_access_at = $last_access_at,
                n.consolidated_at = $consolidated_at,
                n.schema_ref = $schema_ref,
                n.superseded_by = $superseded_by,
                n.proof_count = $proof_count,
                n.valid_from = $valid_from,
                n.valid_to = $valid_to,
                n.recorded_at = $recorded_at,
                n.tags = $tags,
                n.attributes = $attributes,
                n.confirmation_count = $confirmation_count,
                n.strength = $strength,
                n.entity_name = $entity_name,
                n.entity_type = $entity_type,
                n.version = $version,
                n.last_confirmed_at = $last_confirmed_at,
                n.consolidation_reasoning = $consolidation_reasoning,
                n.compiled_at = $compiled_at,
                n.model_domain = $model_domain,
                n.source_trust_tier = $source_trust_tier,
                n.scope = $scope,
                n.source_pipeline = $source_pipeline,
                n.source_content_hash = $source_content_hash
        """, params)

    async def get_cognitive_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a CognitiveNode by ID.

        Args:
            node_id: Unique identifier for the cognitive node.

        Returns:
            Dictionary with node properties, or None if not found.
        """
        self._ensure_initialized()
        import json

        result = await self._execute("""
            MATCH (n:CognitiveNode {id: $id})
            RETURN n.id AS id, n.memory_type AS memory_type,
                   n.cognitive_layer AS cognitive_layer, n.content AS content,
                   n.content_vector AS content_vector,
                   n.source_fragment_ids AS source_fragment_ids,
                   n.belief_status AS belief_status, n.ttl_seconds AS ttl_seconds,
                   n.occurred_at AS occurred_at, n.created_at AS created_at,
                   n.updated_at AS updated_at, n.history AS history,
                   n.access_count AS access_count, n.last_access_at AS last_access_at,
                   n.consolidated_at AS consolidated_at, n.domain_id AS domain_id,
                   n.space_id AS space_id, n.extraction_hint AS extraction_hint,
                   n.visibility AS visibility, n.created_by AS created_by,
                   n.feedback_weight AS feedback_weight, n.confidence AS confidence,
                   n.schema_ref AS schema_ref, n.superseded_by AS superseded_by,
                   n.proof_count AS proof_count,
                   n.valid_from AS valid_from, n.valid_to AS valid_to,
                   n.recorded_at AS recorded_at, n.tags AS tags,
                   n.attributes AS attributes,
                   n.confirmation_count AS confirmation_count,
                   n.strength AS strength,
                   n.entity_name AS entity_name,
                   n.entity_type AS entity_type,
                   n.version AS version,
                   n.last_confirmed_at AS last_confirmed_at,
                   n.consolidation_reasoning AS consolidation_reasoning,
                   n.compiled_at AS compiled_at,
                   n.model_domain AS model_domain,
                   n.source_trust_tier AS source_trust_tier,
                   n.scope AS scope,
                   n.source_pipeline AS source_pipeline,
                   n.source_content_hash AS source_content_hash
        """, {"id": node_id})

        row = _first_row(result)
        if row is None:
            return None

        def parse_json_field(value):
            if value is None:
                return None
            if isinstance(value, float) and __import__("math").isnan(value):
                return None
            if hasattr(value, 'item'):
                return value.item()
            if isinstance(value, (list, dict)):
                return value
            if isinstance(value, (int, float)):
                return value
            try:
                return _safe_json_loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

        def safe_val(value, default=None):
            if value is None:
                return default
            if isinstance(value, float) and __import__("math").isnan(value):
                return default
            if hasattr(value, 'item'):
                return value.item()
            return value

        return {
            "id": row["id"],
            "memory_type": row["memory_type"],
            "cognitive_layer": row["cognitive_layer"],
            "content": row["content"],
            "content_vector": parse_json_field(row["content_vector"]),
            "source_fragment_ids": parse_json_field(row["source_fragment_ids"]) or [],
            "belief_status": safe_val(row["belief_status"], "accepted"),
            "ttl_seconds": safe_val(row["ttl_seconds"], 0),
            "occurred_at": safe_val(row["occurred_at"]),
            "created_at": safe_val(row["created_at"]),
            "updated_at": safe_val(row["updated_at"]),
            "history": parse_json_field(row["history"]) or [],
            "access_count": safe_val(row["access_count"], 0),
            "last_access_at": safe_val(row["last_access_at"]),
            "consolidated_at": safe_val(row["consolidated_at"]),
            "domain_id": safe_val(row["domain_id"]),
            "space_id": safe_val(row["space_id"], "default"),
            "extraction_hint": safe_val(row["extraction_hint"]),
            "visibility": safe_val(row["visibility"], "shared"),
            "created_by": safe_val(row["created_by"]),
            "feedback_weight": safe_val(row["feedback_weight"], 0.5),
            "confidence": safe_val(row["confidence"], 1.0),
            "schema_ref": safe_val(row["schema_ref"]),
            "superseded_by": safe_val(row["superseded_by"]),
            "proof_count": safe_val(row["proof_count"], 1),
            "valid_from": safe_val(row["valid_from"]),
            "valid_to": safe_val(row["valid_to"]),
            "recorded_at": safe_val(row["recorded_at"]),
            "tags": _safe_json_loads(safe_val(row["tags"], "[]")),
            "attributes": parse_json_field(row["attributes"]) or {},
            "confirmation_count": safe_val(row.get("confirmation_count"), 0),
            "strength": safe_val(row.get("strength"), 1.0),
            "entity_name": safe_val(row.get("entity_name")),
            "entity_type": safe_val(row.get("entity_type")),
            "version": safe_val(row.get("version"), 1),
            "last_confirmed_at": safe_val(row.get("last_confirmed_at")),
            "consolidation_reasoning": safe_val(row.get("consolidation_reasoning")),
            "compiled_at": safe_val(row.get("compiled_at")),
            "model_domain": safe_val(row.get("model_domain")),
            "source_trust_tier": safe_val(row.get("source_trust_tier")),
            "scope": safe_val(row.get("scope")),
            "source_pipeline": safe_val(row.get("source_pipeline")),
            "source_content_hash": safe_val(row.get("source_content_hash")),
        }

    async def delete_cognitive_node(self, node_id: str) -> None:
        """Delete a CognitiveNode and all its edges.

        Args:
            node_id: Unique identifier for the cognitive node.
        """
        self._ensure_initialized()
        await self._execute("""
            MATCH (n:CognitiveNode {id: $id}) DELETE n
        """, {"id": node_id})

    async def query_cognitive_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query CognitiveNodes with filters.

        Args:
            memory_type: Filter by memory type.
            cognitive_layer: Filter by cognitive layer.
            belief_status: Filter by belief status.
            domain_id: Filter by domain ID.
            space_id: Filter by space ID.
            limit: Maximum number of results.
            as_of: Temporal query — only return nodes valid at this timestamp.

        Returns:
            List of matching CognitiveNode records.
        """
        self._ensure_initialized()

        where_parts = []
        params: dict[str, Any] = {}

        if memory_type:
            where_parts.append("n.memory_type = $memory_type")
            params["memory_type"] = memory_type
        if cognitive_layer:
            where_parts.append("n.cognitive_layer = $cognitive_layer")
            params["cognitive_layer"] = cognitive_layer
        if belief_status:
            where_parts.append("n.belief_status = $belief_status")
            params["belief_status"] = belief_status
        if domain_id:
            where_parts.append("n.domain_id = $domain_id")
            params["domain_id"] = domain_id
        if space_id:
            where_parts.append("n.space_id = $space_id")
            params["space_id"] = space_id
        if as_of:
            where_parts.append(
                "(n.valid_from IS NULL OR n.valid_from <= $as_of) AND "
                "(n.valid_to IS NULL OR n.valid_to > $as_of)"
            )
            params["as_of"] = as_of

        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        cypher = f"""
            MATCH (n:CognitiveNode)
            {where}
            RETURN n.id AS id, n.memory_type AS memory_type,
                   n.cognitive_layer AS cognitive_layer, n.content AS content,
                   n.content_vector AS content_vector,
                   n.source_fragment_ids AS source_fragment_ids,
                   n.belief_status AS belief_status, n.ttl_seconds AS ttl_seconds,
                   n.occurred_at AS occurred_at, n.created_at AS created_at,
                   n.updated_at AS updated_at, n.history AS history,
                   n.access_count AS access_count, n.last_access_at AS last_access_at,
                   n.consolidated_at AS consolidated_at, n.domain_id AS domain_id,
                   n.space_id AS space_id, n.extraction_hint AS extraction_hint,
                   n.visibility AS visibility, n.created_by AS created_by,
                   n.feedback_weight AS feedback_weight, n.confidence AS confidence,
                   n.schema_ref AS schema_ref, n.superseded_by AS superseded_by,
                   n.proof_count AS proof_count,
                   n.valid_from AS valid_from, n.valid_to AS valid_to,
                   n.recorded_at AS recorded_at, n.tags AS tags,
                   n.attributes AS attributes,
                   n.confirmation_count AS confirmation_count,
                   n.strength AS strength,
                   n.entity_name AS entity_name,
                   n.entity_type AS entity_type,
                   n.version AS version,
                   n.last_confirmed_at AS last_confirmed_at,
                   n.consolidation_reasoning AS consolidation_reasoning,
                   n.compiled_at AS compiled_at,
                   n.model_domain AS model_domain,
                   n.source_trust_tier AS source_trust_tier,
                   n.scope AS scope,
                   n.source_pipeline AS source_pipeline,
                   n.source_content_hash AS source_content_hash
            ORDER BY n.created_at DESC
            LIMIT {limit}
        """
        result = await self._execute(cypher, params)
        rows = _all_rows(result)
        if not rows:
            return []

        import json as _json
        import math as _math

        def _parse(val):
            if val is None:
                return None
            if isinstance(val, float) and _math.isnan(val):
                return None
            if hasattr(val, 'item'):
                return val.item()
            if isinstance(val, (list, dict)):
                return val
            if isinstance(val, (int, float)):
                return val
            try:
                return _safe_json_loads(val)
            except (_json.JSONDecodeError, TypeError):
                return val

        def _safe(val, default=None):
            if val is None:
                return default
            if isinstance(val, float) and _math.isnan(val):
                return default
            if hasattr(val, 'item'):
                return val.item()
            return val

        return [
            {
                "id": row["id"],
                "memory_type": row["memory_type"],
                "cognitive_layer": row["cognitive_layer"],
                "content": row["content"],
                "content_vector": _parse(row["content_vector"]),
                "source_fragment_ids": _parse(row["source_fragment_ids"]) or [],
                "belief_status": _safe(row["belief_status"], "accepted"),
                "ttl_seconds": _safe(row["ttl_seconds"], 0),
                "occurred_at": _safe(row["occurred_at"]),
                "created_at": _safe(row["created_at"]),
                "updated_at": _safe(row["updated_at"]),
                "history": _parse(row["history"]) or [],
                "access_count": _safe(row["access_count"], 0),
                "last_access_at": _safe(row["last_access_at"]),
                "consolidated_at": _safe(row["consolidated_at"]),
                "domain_id": _safe(row["domain_id"]),
                "space_id": _safe(row["space_id"], "default"),
                "extraction_hint": _safe(row["extraction_hint"]),
                "visibility": _safe(row["visibility"], "shared"),
                "created_by": _safe(row["created_by"]),
                "feedback_weight": _safe(row["feedback_weight"], 0.5),
                "confidence": _safe(row["confidence"], 1.0),
                "schema_ref": _safe(row["schema_ref"]),
                "superseded_by": _safe(row["superseded_by"]),
                "proof_count": _safe(row["proof_count"], 1),
                "valid_from": _safe(row["valid_from"]),
                "valid_to": _safe(row["valid_to"]),
                "recorded_at": _safe(row["recorded_at"]),
                "tags": _safe_json_loads(_safe(row["tags"], "[]")),
                "confirmation_count": _safe(row["confirmation_count"], 0),
                "attributes": _parse(row["attributes"]) or {},
                "strength": _safe(row["strength"], 1.0),
                "entity_name": _safe(row["entity_name"]),
                "entity_type": _safe(row["entity_type"]),
                "version": _safe(row["version"], 1),
                "last_confirmed_at": _safe(row["last_confirmed_at"]),
                "consolidation_reasoning": _safe(row["consolidation_reasoning"]),
                "compiled_at": _safe(row["compiled_at"]),
                "model_domain": _safe(row["model_domain"]),
                "source_trust_tier": _safe(row["source_trust_tier"]),
                "scope": _safe(row["scope"]),
                "source_pipeline": _safe(row["source_pipeline"]),
                "source_content_hash": _safe(row["source_content_hash"]),
            }
            for row in rows
        ]

    async def update_cognitive_node_history(
        self,
        node_id: str,
        history_entry: dict[str, Any],
    ) -> None:
        """Append a history entry to a CognitiveNode.

        Args:
            node_id: Unique identifier for the cognitive node.
            history_entry: History entry to append.
        """
        self._ensure_initialized()
        import json

        current = await self._execute("""
            MATCH (n:CognitiveNode {id: $id})
            RETURN n.history AS history
        """, {"id": node_id})

        row = _first_row(current)
        if row is None:
            return

        history_str = row["history"]
        history = _safe_json_loads(history_str) if history_str else []
        history.append(history_entry)

        await self._execute("""
            MATCH (n:CognitiveNode {id: $id})
            SET n.history = $history
        """, {"id": node_id, "history": json.dumps(history)})

    async def update_cognitive_node_belief(
        self,
        node_id: str,
        new_belief: str,
        reason: str | None = None,
    ) -> None:
        """Update the belief status of a CognitiveNode.

        Args:
            node_id: Unique identifier for the cognitive node.
            new_belief: New belief status.
            reason: Optional reason for the belief change.
        """
        self._ensure_initialized()
        import json
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        history_entry = {
            "action": "belief_change",
            "old_belief": None,
            "new_belief": new_belief,
            "reason": reason,
            "timestamp": now,
        }

        current = await self._execute("""
            MATCH (n:CognitiveNode {id: $id})
            RETURN n.belief_status AS belief_status, n.history AS history
        """, {"id": node_id})

        row = _first_row(current)
        if row is not None:
            history_entry["old_belief"] = row["belief_status"]
            history_str = row["history"]
            history = _safe_json_loads(history_str) if history_str else []
            history.append(history_entry)
        else:
            history = [history_entry]

        await self._execute("""
            MATCH (n:CognitiveNode {id: $id})
            SET n.belief_status = $new_belief,
                n.history = $history,
                n.updated_at = $updated_at
        """, {
            "id": node_id,
            "new_belief": new_belief,
            "history": json.dumps(history),
            "updated_at": now,
        })

    # --- Agent Memory: DispositionProfile Management ---

    async def upsert_disposition_profile(
        self,
        profile_id: str,
        scene: str,
        skepticism: float = 0.5,
        evidence_demand: float = 0.5,
        abstraction_preference: float = 0.5,
        thoroughness: float = 0.5,
        recency_bias: float = 0.5,
        empathy: float = 0.5,
        risk_tolerance: float = 0.5,
        domain_id: str | None = None,
        space_id: str = "default",
    ) -> None:
        """Create or update a DispositionProfileNode.

        Args:
            profile_id: Unique identifier for the disposition profile.
            scene: Scene/context this profile applies to.
            skepticism: Skepticism dimension (0.3-0.9).
            evidence_demand: Evidence requirement level (0.3-0.9).
            abstraction_preference: Abstraction preference (0.2-0.8).
            thoroughness: Retrieval thoroughness (0.2-0.8).
            recency_bias: Recency bias (0.2-0.8).
            empathy: Empathy level (0.2-0.8).
            risk_tolerance: Risk tolerance (0.2-0.8).
            domain_id: Domain identifier.
            space_id: Space identifier.
        """
        self._ensure_initialized()

        params: dict[str, Any] = {
            "id": profile_id,
            "scene": scene,
            "skepticism": skepticism,
            "evidence_demand": evidence_demand,
            "abstraction_preference": abstraction_preference,
            "thoroughness": thoroughness,
            "recency_bias": recency_bias,
            "empathy": empathy,
            "risk_tolerance": risk_tolerance,
            "domain_id": domain_id,
            "space_id": space_id,
        }

        await self._execute("""
            MERGE (n:DispositionProfileNode {id: $id})
            SET n.scene = $scene,
                n.skepticism = $skepticism,
                n.evidence_demand = $evidence_demand,
                n.abstraction_preference = $abstraction_preference,
                n.thoroughness = $thoroughness,
                n.recency_bias = $recency_bias,
                n.empathy = $empathy,
                n.risk_tolerance = $risk_tolerance,
                n.domain_id = $domain_id,
                n.space_id = $space_id
        """, params)

    async def get_disposition_profile(
        self,
        profile_id: str | None = None,
        scene: str | None = None,
        domain_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get a DispositionProfileNode by ID or scene.

        Args:
            profile_id: Unique identifier for the disposition profile.
            scene: Scene/context to filter by.
            domain_id: Domain identifier to filter by.

        Returns:
            Dictionary with profile properties, or None if not found.
        """
        self._ensure_initialized()

        where_parts = []
        params: dict[str, Any] = {}

        if profile_id:
            where_parts.append("n.id = $id")
            params["id"] = profile_id
        if scene:
            where_parts.append("n.scene = $scene")
            params["scene"] = scene
        if domain_id:
            where_parts.append("n.domain_id = $domain_id")
            params["domain_id"] = domain_id

        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        cypher = f"""
            MATCH (n:DispositionProfileNode)
            {where}
            RETURN n.id AS id, n.skepticism AS skepticism,
                   n.evidence_demand AS evidence_demand,
                   n.abstraction_preference AS abstraction_preference,
                   n.thoroughness AS thoroughness,
                   n.recency_bias AS recency_bias,
                   n.empathy AS empathy,
                   n.risk_tolerance AS risk_tolerance,
                   n.scene AS scene,
                   n.domain_id AS domain_id, n.space_id AS space_id
            LIMIT 1
        """
        result = await self._execute(cypher, params)
        row = _first_row(result)
        if row is None:
            return None

        return {
            "id": row["id"],
            "skepticism": row["skepticism"],
            "evidence_demand": row["evidence_demand"],
            "abstraction_preference": row["abstraction_preference"],
            "thoroughness": row["thoroughness"],
            "recency_bias": row["recency_bias"],
            "empathy": row["empathy"],
            "risk_tolerance": row["risk_tolerance"],
            "scene": row["scene"],
            "domain_id": row["domain_id"],
            "space_id": row["space_id"],
        }

    async def compute_dynamic_weights(self, profile: dict[str, Any]) -> dict[str, float]:
        """Compute dynamic type weights based on a DispositionProfile.

        Args:
            profile: DispositionProfile dictionary.

        Returns:
            Dictionary of memory_type -> weight.
        """
        skepticism = profile.get("skepticism", 0.5)
        empathy = profile.get("empathy", 0.5)
        risk_tolerance = profile.get("risk_tolerance", 0.5)

        base_weights = {
            "mental_model": 3.0,
            "opinion": 2.5,
            "entity": 2.0,
            "rule": 2.0,
            "observation": 1.5,
            "procedure": 1.8,
            "episode": 1.2,
            "fragment": 1.0,
        }

        adjusted = {}
        for memory_type, base_weight in base_weights.items():
            if memory_type in ("mental_model", "opinion", "episode"):
                adjusted[memory_type] = base_weight * (1.0 - (skepticism - 0.5) * 0.6)
            elif memory_type in ("entity", "rule"):
                adjusted[memory_type] = base_weight * (1.0 + (skepticism - 0.5) * 0.4)
            elif memory_type == "observation":
                adjusted[memory_type] = base_weight * (1.0 + (empathy - 0.5) * 0.3)
            elif memory_type == "procedure":
                adjusted[memory_type] = base_weight * (1.0 + (risk_tolerance - 0.5) * 0.2)
            else:
                adjusted[memory_type] = base_weight

        return adjusted

    # --- CognitiveStorageBackend Adapter Methods ---
    # These thin wrappers adapt the CognitiveStorageBackend dict-based interface
    # to the existing LadybugGraphStore method signatures.

    async def save_cognitive_node(self, node_data: dict[str, Any]) -> None:
        """Create or update a CognitiveNode from a dict.

        CognitiveStorageBackend interface adapter — extracts fields from
        node_data and delegates to upsert_cognitive_node().
        """
        await self.upsert_cognitive_node(
            node_id=node_data["id"],
            memory_type=node_data.get("memory_type", "fragment"),
            cognitive_layer=node_data.get("cognitive_layer", "perception"),
            content=node_data.get("content", ""),
            content_vector=node_data.get("content_vector"),
            source_fragment_ids=node_data.get("source_fragment_ids"),
            belief_status=node_data.get("belief_status", "accepted"),
            ttl_seconds=node_data.get("ttl_seconds", 0),
            occurred_at=node_data.get("occurred_at"),
            extraction_hint=node_data.get("extraction_hint"),
            domain_id=node_data.get("domain_id"),
            space_id=node_data.get("space_id", "default"),
            history=node_data.get("history"),
            visibility=node_data.get("visibility", "shared"),
            created_by=node_data.get("created_by"),
            feedback_weight=node_data.get("feedback_weight", 0.5),
            confidence=node_data.get("confidence", 1.0),
            access_count=node_data.get("access_count", 0),
            last_access_at=node_data.get("last_access_at"),
            consolidated_at=node_data.get("consolidated_at"),
            schema_ref=node_data.get("schema_ref"),
            superseded_by=node_data.get("superseded_by"),
            proof_count=node_data.get("proof_count", 1),
            valid_from=node_data.get("valid_from"),
            valid_to=node_data.get("valid_to"),
            recorded_at=node_data.get("recorded_at"),
            tags=node_data.get("tags"),
            attributes=node_data.get("attributes"),
            confirmation_count=node_data.get("confirmation_count", 0),
            strength=node_data.get("strength", 1.0),
            entity_name=node_data.get("entity_name"),
            entity_type=node_data.get("entity_type"),
            version=node_data.get("version", 1),
            last_confirmed_at=node_data.get("last_confirmed_at"),
            consolidation_reasoning=node_data.get("consolidation_reasoning"),
            compiled_at=node_data.get("compiled_at"),
            source_trust_tier=node_data.get("source_trust_tier"),
            scope=node_data.get("scope"),
            source_pipeline=node_data.get("source_pipeline"),
            source_content_hash=node_data.get("source_content_hash"),
        )

    async def list_cognitive_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query CognitiveNodes with filters.

        CognitiveStorageBackend interface adapter — delegates to query_cognitive_nodes().
        """
        return await self.query_cognitive_nodes(
            memory_type=memory_type,
            cognitive_layer=cognitive_layer,
            belief_status=belief_status,
            domain_id=domain_id,
            space_id=space_id,
            limit=limit,
            as_of=as_of,
        )

    async def update_cognitive_node_with_occ(
        self,
        node_id: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a CognitiveNode with optimistic concurrency control.

        Moved from CognitiveStore — the Cypher logic was accessing _execute()
        anyway, so it belongs here in the concrete store implementation.
        """
        current = await self.get_cognitive_node(node_id)
        if current is None:
            return None

        current_version = current.get("version", 1)
        if current_version != expected_version:
            return None

        set_clauses: list[str] = []
        params: dict[str, Any] = {"id": node_id}

        json_fields = {"source_fragment_ids", "tags", "attributes", "content_vector", "history"}
        for key, value in updates.items():
            if key in json_fields:
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = json.dumps(value) if value is not None else None
            else:
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = value

        set_clauses.append("n.version = n.version + 1")
        set_clauses.append("n.updated_at = $updated_at")

        from datetime import datetime, timezone
        params["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_str = ", ".join(set_clauses)
        cypher = f"MATCH (n:CognitiveNode {{id: $id}}) SET {set_str} RETURN n.id AS id"

        try:
            await self._execute(cypher, params)
        except Exception as e:
            logger.error("OCC update failed for %s: %s", node_id, e)
            return None

        return await self.get_cognitive_node(node_id)

    async def save_cognitive_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an edge between two CognitiveNodes.

        CognitiveStorageBackend interface adapter — delegates to create_cognitive_edge().
        """
        return await self.create_cognitive_edge(
            edge_type=edge_type,
            from_id=from_id,
            to_id=to_id,
            properties=properties,
        )

    async def list_cognitive_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query cognitive edges with optional filters.

        CognitiveStorageBackend interface adapter — delegates to query_cognitive_edges().
        """
        return await self.query_cognitive_edges(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            limit=limit,
        )

    async def save_disposition(self, profile_data: dict[str, Any]) -> None:
        """Create or update a DispositionProfile from a dict.

        CognitiveStorageBackend interface adapter — extracts fields from
        profile_data and delegates to upsert_disposition_profile().
        """
        await self.upsert_disposition_profile(
            profile_id=profile_data["id"],
            scene=profile_data.get("scene", "default"),
            skepticism=profile_data.get("skepticism", 0.5),
            evidence_demand=profile_data.get("evidence_demand", 0.5),
            abstraction_preference=profile_data.get("abstraction_preference", 0.5),
            thoroughness=profile_data.get("thoroughness", 0.5),
            recency_bias=profile_data.get("recency_bias", 0.5),
            empathy=profile_data.get("empathy", 0.5),
            risk_tolerance=profile_data.get("risk_tolerance", 0.5),
            domain_id=profile_data.get("domain_id"),
            space_id=profile_data.get("space_id", "default"),
        )

    async def get_disposition(
        self,
        profile_id: str | None = None,
        scene: str | None = None,
        domain_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Get a DispositionProfile by ID or scene.

        CognitiveStorageBackend interface adapter — delegates to get_disposition_profile().
        """
        return await self.get_disposition_profile(
            profile_id=profile_id,
            scene=scene,
            domain_id=domain_id,
        )

    async def save_activity_log(
        self, node_id: str, entry: dict[str, Any]
    ) -> None:
        """Append a history entry to a CognitiveNode.

        CognitiveStorageBackend interface adapter — delegates to update_cognitive_node_history().
        """
        await self.update_cognitive_node_history(node_id, entry)

    async def get_activity_log(
        self, node_id: str
    ) -> list[dict[str, Any]]:
        """Get history entries for a CognitiveNode.

        CognitiveStorageBackend interface adapter — reads from get_cognitive_node().
        """
        node = await self.get_cognitive_node(node_id)
        if node is None:
            return []
        history = node.get("history")
        if isinstance(history, list):
            return history
        if isinstance(history, str):
            try:
                parsed = json.loads(history)
                if isinstance(parsed, list):
                    return parsed
                return []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    async def search_cognitive(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search for cognitive nodes.

        Falls back to text matching against query_cognitive_nodes when no
        vector search backend is available.
        """
        nodes = await self.query_cognitive_nodes(
            domain_id=space_id,
            space_id=space_id,
            memory_type=memory_type,
            limit=top_k,
        )
        results: list[dict[str, Any]] = []
        query_lower = query.lower()
        for node in nodes:
            content = node.get("content", "")
            if query_lower in content.lower():
                node["score"] = 1.0
            else:
                node["score"] = 0.0
            results.append(node)
        results.sort(key=lambda n: n.get("score", 0.0), reverse=True)
        return results

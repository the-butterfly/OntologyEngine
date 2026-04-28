"""Pipeline state management for rule execution.

Manages PipelineRun and ExecutionStepSnapshot lifecycle.
Note: All state is in-memory only. No storage writes are performed to保障数据资产准确性。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PipelineStatus(Enum):
    """Status for pipeline runs."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class StepStatus(Enum):
    """Status for execution steps."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class PipelineRun:
    """Represents a single pipeline execution run."""
    id: str
    rule_logic_name: str
    rule_definition_name: str
    entity_id: str
    dimension: str
    status: PipelineStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    run_config: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    source_pipeline: str = "rule_engine"
    source_user: str | None = None
    source_content_hash: str | None = None
    supersedes: str | None = None


@dataclass
class ExecutionStepSnapshot:
    """Represents a snapshot of an execution step at a point in time."""
    id: str
    pipeline_run_id: str
    step_id: str
    step_name: str
    status: StepStatus
    started_at: str | None = None
    completed_at: str | None = None
    condition_met: bool | None = None
    action_type: str | None = None
    operator_name: str | None = None
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    output_snapshot: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    skip_reason: str | None = None
    dag_layer: int = 0
    depends_on: list[str] = field(default_factory=list)
    trace_to: list[str] | None = None


def _utc_now() -> str:
    """Return current UTC time as ISO format string."""
    return datetime.now(timezone.utc).isoformat()


class PipelineStateManager:
    """Manages pipeline runs and step snapshots in memory.

    Optionally persists state to SQLite for crash recovery.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._runs: dict[str, PipelineRun] = {}
        self._step_snapshots: dict[str, list[ExecutionStepSnapshot]] = {}
        self._db_path = db_path
        self._db_conn: Any = None
        if db_path:
            self._init_db()

    # =============================================================================
    # PipelineRun Management
    # =============================================================================

    async def create_run(
        self,
        rule_logic_name: str,
        rule_definition_name: str,
        entity_id: str,
        dimension: str,
        run_config: dict[str, Any] | None = None,
        source_user: str | None = None,
        source_content_hash: str | None = None,
        supersedes: str | None = None,
    ) -> PipelineRun:
        """Create a new pipeline run in PENDING status.

        Args:
            rule_logic_name: Name of the rule logic
            rule_definition_name: Name of the rule definition
            entity_id: Entity being processed
            dimension: Dimension being analyzed
            run_config: Optional configuration dict
            source_user: Optional source user
            source_content_hash: Optional content hash
            supersedes: Optional ID of run this supersedes

        Returns:
            The created PipelineRun
        """
        run_id = str(uuid.uuid4())
        run = PipelineRun(
            id=run_id,
            rule_logic_name=rule_logic_name,
            rule_definition_name=rule_definition_name,
            entity_id=entity_id,
            dimension=dimension,
            status=PipelineStatus.PENDING,
            created_at=_utc_now(),
            run_config=run_config or {},
            source_user=source_user,
            source_content_hash=source_content_hash,
            supersedes=supersedes,
        )
        self._runs[run_id] = run
        self._step_snapshots[run_id] = []
        self._persist_run(run)
        return run

    async def start_run(self, run_id: str) -> None:
        """Transition a run from PENDING to RUNNING.

        Args:
            run_id: The ID of the run to start

        Raises:
            KeyError: If run_id not found
            ValueError: If run is not in PENDING status
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")
        if run.status != PipelineStatus.PENDING:
            raise ValueError(f"Cannot start run in status {run.status.value}, expected PENDING")
        run.status = PipelineStatus.RUNNING
        run.started_at = _utc_now()
        self._persist_run(run)

    async def complete_run(self, run_id: str) -> None:
        """Mark a run as COMPLETED.

        Args:
            run_id: The ID of the run to complete

        Raises:
            KeyError: If run_id not found
            ValueError: If run is not in RUNNING status
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")
        if run.status != PipelineStatus.RUNNING:
            raise ValueError(f"Cannot complete run in status {run.status.value}, expected RUNNING")
        run.status = PipelineStatus.COMPLETED
        run.completed_at = _utc_now()
        self._persist_run(run)

    async def fail_run(self, run_id: str, error: str) -> None:
        """Mark a run as FAILED with an error message.

        Args:
            run_id: The ID of the run to fail
            error: Error message describing the failure

        Raises:
            KeyError: If run_id not found
            ValueError: If run is not in RUNNING status
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")
        if run.status != PipelineStatus.RUNNING:
            raise ValueError(f"Cannot fail run in status {run.status.value}, expected RUNNING")
        run.status = PipelineStatus.FAILED
        run.completed_at = _utc_now()
        run.error_message = error
        self._persist_run(run)

    async def partial_complete_run(self, run_id: str) -> None:
        """Mark a run as PARTIALLY_COMPLETED (some steps failed/skipped).

        Args:
            run_id: The ID of the run to mark as partially complete

        Raises:
            KeyError: If run_id not found
            ValueError: If run is not in RUNNING status
        """
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")
        if run.status != PipelineStatus.RUNNING:
            raise ValueError(f"Cannot partially complete run in status {run.status.value}, expected RUNNING")
        run.status = PipelineStatus.PARTIALLY_COMPLETED
        run.completed_at = _utc_now()

    # =============================================================================
    # ExecutionStepSnapshot Management
    # =============================================================================

    async def create_step_snapshot(
        self,
        pipeline_run_id: str,
        step_id: str,
        step_name: str,
        dag_layer: int = 0,
        depends_on: list[str] | None = None,
        action_type: str | None = None,
        operator_name: str | None = None,
    ) -> ExecutionStepSnapshot:
        """Create a new step snapshot in PENDING status.

        Args:
            pipeline_run_id: ID of the parent pipeline run
            step_id: ID of the step definition
            step_name: Human-readable name of the step
            dag_layer: DAG layer number for execution ordering
            depends_on: List of step IDs this step depends on
            action_type: Type of action (e.g., "compute", "flag")
            operator_name: Name of the operator to execute

        Returns:
            The created ExecutionStepSnapshot

        Raises:
            KeyError: If pipeline_run_id not found
        """
        if pipeline_run_id not in self._runs:
            raise KeyError(f"Pipeline run {pipeline_run_id} not found")

        snapshot_id = str(uuid.uuid4())
        snapshot = ExecutionStepSnapshot(
            id=snapshot_id,
            pipeline_run_id=pipeline_run_id,
            step_id=step_id,
            step_name=step_name,
            status=StepStatus.PENDING,
            dag_layer=dag_layer,
            depends_on=depends_on or [],
            action_type=action_type,
            operator_name=operator_name,
        )
        self._step_snapshots[pipeline_run_id].append(snapshot)
        return snapshot

    async def start_step(
        self,
        snapshot_id: str,
        input_snapshot: dict[str, Any],
    ) -> None:
        """Transition a step from PENDING to RUNNING.

        Args:
            snapshot_id: The ID of the step snapshot to start
            input_snapshot: Input data at start of execution

        Raises:
            KeyError: If snapshot_id not found
            ValueError: If step is not in PENDING status
        """
        snapshot = self._find_step_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(f"Step snapshot {snapshot_id} not found")
        if snapshot.status != StepStatus.PENDING:
            raise ValueError(f"Cannot start step in status {snapshot.status.value}, expected PENDING")
        snapshot.status = StepStatus.RUNNING
        snapshot.started_at = _utc_now()
        snapshot.input_snapshot = input_snapshot
        self._persist_step(snapshot)

    async def complete_step(
        self,
        snapshot_id: str,
        condition_met: bool,
        output_snapshot: dict[str, Any],
    ) -> None:
        """Mark a step as COMPLETED.

        Args:
            snapshot_id: The ID of the step snapshot to complete
            condition_met: Whether the condition was met
            output_snapshot: Output data from execution

        Raises:
            KeyError: If snapshot_id not found
            ValueError: If step is not in RUNNING status
        """
        snapshot = self._find_step_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(f"Step snapshot {snapshot_id} not found")
        if snapshot.status != StepStatus.RUNNING:
            raise ValueError(f"Cannot complete step in status {snapshot.status.value}, expected RUNNING")
        snapshot.status = StepStatus.COMPLETED
        snapshot.completed_at = _utc_now()
        snapshot.condition_met = condition_met
        snapshot.output_snapshot = output_snapshot
        self._persist_step(snapshot)

    async def skip_step(self, snapshot_id: str, reason: str) -> None:
        """Mark a step as SKIPPED.

        Args:
            snapshot_id: The ID of the step snapshot to skip
            reason: Reason for skipping

        Raises:
            KeyError: If snapshot_id not found
            ValueError: If step is not in PENDING status
        """
        snapshot = self._find_step_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(f"Step snapshot {snapshot_id} not found")
        if snapshot.status != StepStatus.PENDING:
            raise ValueError(f"Cannot skip step in status {snapshot.status.value}, expected PENDING")
        snapshot.status = StepStatus.SKIPPED
        snapshot.completed_at = _utc_now()
        snapshot.skip_reason = reason
        self._persist_step(snapshot)

    async def fail_step(self, snapshot_id: str, error: str) -> None:
        """Mark a step as FAILED with an error message.

        Args:
            snapshot_id: The ID of the step snapshot to fail
            error: Error message describing the failure

        Raises:
            KeyError: If snapshot_id not found
            ValueError: If step is not in RUNNING status
        """
        snapshot = self._find_step_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(f"Step snapshot {snapshot_id} not found")
        if snapshot.status != StepStatus.RUNNING:
            raise ValueError(f"Cannot fail step in status {snapshot.status.value}, expected RUNNING")
        snapshot.status = StepStatus.FAILED
        snapshot.completed_at = _utc_now()
        snapshot.error_message = error
        self._persist_step(snapshot)

    async def rollback_step(self, snapshot_id: str) -> None:
        """Mark a step as ROLLED_BACK.

        Args:
            snapshot_id: The ID of the step snapshot to rollback

        Raises:
            KeyError: If snapshot_id not found
            ValueError: If step is not in COMPLETED or FAILED status
        """
        snapshot = self._find_step_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(f"Step snapshot {snapshot_id} not found")
        if snapshot.status not in (StepStatus.COMPLETED, StepStatus.FAILED):
            raise ValueError(f"Cannot rollback step in status {snapshot.status.value}, expected COMPLETED or FAILED")
        snapshot.status = StepStatus.ROLLED_BACK
        snapshot.completed_at = _utc_now()
        self._persist_step(snapshot)

    # =============================================================================
    # Query Methods
    # =============================================================================

    async def get_run(self, run_id: str) -> PipelineRun | None:
        """Get a pipeline run by ID.

        Args:
            run_id: The ID of the run to retrieve

        Returns:
            The PipelineRun if found, None otherwise
        """
        return self._runs.get(run_id)

    async def get_latest_run(
        self,
        rule_logic_name: str,
        entity_id: str,
    ) -> PipelineRun | None:
        """Get the most recent run for a rule logic and entity.

        Args:
            rule_logic_name: Name of the rule logic
            entity_id: Entity ID to filter by

        Returns:
            The most recent PipelineRun if any exist, None otherwise
        """
        matching = [
            r for r in self._runs.values()
            if r.rule_logic_name == rule_logic_name and r.entity_id == entity_id
        ]
        if not matching:
            return None
        # Sort by created_at descending, return most recent
        return max(matching, key=lambda r: r.created_at)

    async def get_step_snapshots(self, run_id: str) -> list[ExecutionStepSnapshot]:
        """Get all step snapshots for a pipeline run.

        Args:
            run_id: The ID of the pipeline run

        Returns:
            List of ExecutionStepSnapshots for the run, empty list if none
        """
        return list(self._step_snapshots.get(run_id, []))

    async def get_completed_step_ids(self, run_id: str) -> list[str]:
        """Get IDs of all completed steps for a pipeline run.

        Args:
            run_id: The ID of the pipeline run

        Returns:
            List of step snapshot IDs that are COMPLETED
        """
        snapshots = self._step_snapshots.get(run_id, [])
        return [s.id for s in snapshots if s.status == StepStatus.COMPLETED]

    # =============================================================================
    # Internal Helpers
    # =============================================================================

    def _find_step_snapshot(self, snapshot_id: str) -> ExecutionStepSnapshot | None:
        """Find a step snapshot by ID across all runs.

        Args:
            snapshot_id: The snapshot ID to find

        Returns:
            The ExecutionStepSnapshot if found, None otherwise
        """
        for snapshots in self._step_snapshots.values():
            for snapshot in snapshots:
                if snapshot.id == snapshot_id:
                    return snapshot
        return None

    def _init_db(self) -> None:
        import sqlite3

        self._db_conn = sqlite3.connect(self._db_path)
        self._db_conn.execute("""CREATE TABLE IF NOT EXISTS pipeline_runs (
            id TEXT PRIMARY KEY,
            rule_logic_name TEXT,
            rule_definition_name TEXT,
            entity_id TEXT,
            dimension TEXT,
            status TEXT,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT
        )""")
        self._db_conn.execute("""CREATE TABLE IF NOT EXISTS pipeline_steps (
            id TEXT,
            pipeline_run_id TEXT,
            step_id TEXT,
            step_name TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            input_snapshot TEXT,
            output_snapshot TEXT,
            error_message TEXT,
            PRIMARY KEY (id)
        )""")
        self._db_conn.commit()

    def _persist_run(self, run: PipelineRun) -> None:
        if not self._db_conn:
            return
        self._db_conn.execute(
            "INSERT OR REPLACE INTO pipeline_runs (id, rule_logic_name, rule_definition_name, entity_id, dimension, status, created_at, started_at, completed_at, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [run.id, run.rule_logic_name, run.rule_definition_name, run.entity_id, run.dimension, run.status.value, run.created_at, run.started_at, run.completed_at, run.error_message],
        )
        self._db_conn.commit()

    def _persist_step(self, snapshot: ExecutionStepSnapshot) -> None:
        if not self._db_conn:
            return
        import json

        self._db_conn.execute(
            "INSERT OR REPLACE INTO pipeline_steps (id, pipeline_run_id, step_id, step_name, status, started_at, completed_at, input_snapshot, output_snapshot, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                snapshot.id, snapshot.pipeline_run_id, snapshot.step_id, snapshot.step_name,
                snapshot.status.value, snapshot.started_at, snapshot.completed_at,
                json.dumps(snapshot.input_snapshot) if snapshot.input_snapshot else None,
                json.dumps(snapshot.output_snapshot) if snapshot.output_snapshot else None,
                snapshot.error_message,
            ],
        )
        self._db_conn.commit()

    async def recover_runs(self) -> list[PipelineRun]:
        if not self._db_conn:
            return []
        cursor = self._db_conn.execute(
            "SELECT id, rule_logic_name, rule_definition_name, entity_id, dimension, status, created_at, started_at, completed_at, error_message FROM pipeline_runs WHERE status IN ('PENDING', 'RUNNING')"
        )
        rows = cursor.fetchall()
        recovered = []
        for row in rows:
            run = PipelineRun(
                id=row[0], rule_logic_name=row[1], rule_definition_name=row[2],
                entity_id=row[3], dimension=row[4],
                status=PipelineStatus(row[5]),
                created_at=row[6], started_at=row[7], completed_at=row[8],
                error_message=row[9],
            )
            self._runs[run.id] = run
            self._step_snapshots[run.id] = []
            recovered.append(run)
        return recovered
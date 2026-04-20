"""Rule transaction management for snapshot/restore functionality."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ontology_engine.engine.rule.models import Alert, ExecutionContext


@dataclass
class ContextSnapshot:
    """Snapshot of ExecutionContext state at a point in time.

    Captures the computed metrics, flags, alerts, and categories
    to allow rollback on error or commit on success.
    """
    timestamp: str
    computed_metrics: dict[str, Any]
    flags: dict[str, Any]
    alerts: list[Alert]
    categories: dict[str, str]


class RuleTransaction:
    """Transaction manager for rule execution with snapshot/restore.

    Provides snapshot capability to capture ExecutionContext state before
    each DAG layer execution, with support for restore on error or commit
    on success.
    """

    def __init__(self, context: ExecutionContext):
        """Initialize transaction with execution context.

        Args:
            context: The ExecutionContext to manage transactions for.
        """
        self.context = context
        self._snapshots: list[ContextSnapshot] = []

    def snapshot(self) -> ContextSnapshot:
        """Capture current state of context.

        Creates a deep copy of the relevant context fields including
        computed_metrics, flags, alerts, and categories.

        Returns:
            ContextSnapshot containing the current state.
        """
        # Deep copy to ensure independence from original
        computed_metrics = copy.deepcopy(self.context.computed_metrics)
        flags = copy.deepcopy(self.context.flags)
        alerts = copy.deepcopy(self.context.alerts)
        categories = copy.deepcopy(self.context.categories)

        snap = ContextSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            computed_metrics=computed_metrics,
            flags=flags,
            alerts=alerts,
            categories=categories,
        )
        self._snapshots.append(snap)
        return snap

    def restore(self, snapshot: ContextSnapshot) -> None:
        """Restore context to snapshot state.

        Args:
            snapshot: The ContextSnapshot to restore to.

        Raises:
            ValueError: If snapshot is not in the snapshot history.
        """
        if snapshot not in self._snapshots:
            raise ValueError("Snapshot not found in transaction history")

        # Deep copy to ensure context is independent of snapshot
        self.context.computed_metrics = copy.deepcopy(snapshot.computed_metrics)
        self.context.flags = copy.deepcopy(snapshot.flags)
        self.context.alerts = copy.deepcopy(snapshot.alerts)
        self.context.categories = copy.deepcopy(snapshot.categories)

    def commit(self) -> None:
        """Clear snapshots after successful layer execution.

        Removes all snapshots from history after successful execution
        of a DAG layer.
        """
        self._snapshots.clear()

    @property
    def has_snapshots(self) -> bool:
        """Check if there are any snapshots in history.

        Returns:
            True if there are snapshots, False otherwise.
        """
        return len(self._snapshots) > 0

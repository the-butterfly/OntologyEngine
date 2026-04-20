# tests/unit/engine/rule/test_transaction.py
"""Tests for RuleTransaction snapshot/restore functionality."""

import pytest

from ontology_engine.engine.rule.transaction import (
    ContextSnapshot,
    ExecutionContext,
    RuleTransaction,
)
from ontology_engine.engine.rule.models import Alert


class TestContextSnapshot:
    """Test ContextSnapshot dataclass."""

    def test_create_snapshot(self):
        """Test creating a ContextSnapshot."""
        snap = ContextSnapshot(
            timestamp="2026-04-20T00:00:00Z",
            computed_metrics={"score": 100},
            flags={"flag_a": True},
            alerts=[Alert(level="warning", type="test", message="Test alert")],
            categories={"cat1": "value1"},
        )
        assert snap.timestamp == "2026-04-20T00:00:00Z"
        assert snap.computed_metrics == {"score": 100}
        assert snap.flags == {"flag_a": True}
        assert len(snap.alerts) == 1
        assert snap.categories == {"cat1": "value1"}


class TestRuleTransactionSnapshot:
    """Test RuleTransaction snapshot functionality."""

    def test_snapshot_captures_current_state(self):
        """Test that snapshot captures current context state."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
            flags={"approved": True},
            alerts=[Alert(level="warning", type="test", message="Test alert")],
            categories={"risk": "low"},
        )
        tx = RuleTransaction(context)
        snap = tx.snapshot()

        assert snap.computed_metrics == {"score": 100}
        assert snap.flags == {"approved": True}
        assert len(snap.alerts) == 1
        assert snap.categories == {"risk": "low"}
        assert snap.timestamp is not None

    def test_snapshot_after_context_modification(self):
        """Test that snapshot captures state at snapshot time, not modification time."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
            flags={"approved": True},
            alerts=[],
            categories={},
        )
        tx = RuleTransaction(context)

        # Snapshot current state
        snap1 = tx.snapshot()

        # Modify context
        context.computed_metrics["score"] = 200
        context.flags["approved"] = False
        context.flags["new_flag"] = True

        # Take another snapshot
        snap2 = tx.snapshot()

        # First snapshot should have original values
        assert snap1.computed_metrics == {"score": 100}
        assert snap1.flags == {"approved": True}
        # Second snapshot should have modified values
        assert snap2.computed_metrics == {"score": 200}
        assert snap2.flags == {"approved": False, "new_flag": True}


class TestRuleTransactionRestore:
    """Test RuleTransaction restore functionality."""

    def test_restore_to_previous_snapshot(self):
        """Test restoring context to a previous snapshot state."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
            flags={"approved": True},
            alerts=[Alert(level="warning", type="test", message="Test alert")],
            categories={"risk": "low"},
        )
        tx = RuleTransaction(context)

        # Take snapshot
        snap = tx.snapshot()

        # Modify context
        context.computed_metrics["score"] = 200
        context.flags["approved"] = False
        context.alerts.clear()
        context.categories["risk"] = "high"

        # Restore to snapshot
        tx.restore(snap)

        # Context should be restored to snapshot state
        assert context.computed_metrics == {"score": 100}
        assert context.flags == {"approved": True}
        assert len(context.alerts) == 1
        assert context.categories == {"risk": "low"}

    def test_restore_invalid_snapshot_raises_error(self):
        """Test that restoring to invalid snapshot raises ValueError."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
        )
        tx = RuleTransaction(context)

        # Create a snapshot from another transaction
        other_context = ExecutionContext(
            entity_id="entity_2",
            dimension="credit",
            entity_data={},
        )
        other_tx = RuleTransaction(other_context)
        other_snap = other_tx.snapshot()

        # Trying to restore foreign snapshot should raise ValueError
        with pytest.raises(ValueError, match="Snapshot not found"):
            tx.restore(other_snap)


class TestRuleTransactionCommit:
    """Test RuleTransaction commit functionality."""

    def test_commit_clears_snapshots(self):
        """Test that commit clears all snapshots."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
        )
        tx = RuleTransaction(context)

        # Take multiple snapshots
        tx.snapshot()
        tx.snapshot()
        assert tx.has_snapshots is True

        # Commit clears snapshots
        tx.commit()
        assert tx.has_snapshots is False

    def test_commit_does_not_affect_context(self):
        """Test that commit does not modify context state."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
            flags={"approved": True},
        )
        tx = RuleTransaction(context)

        # Snapshot and commit
        tx.snapshot()
        tx.commit()

        # Context should still have original values
        assert context.computed_metrics == {"score": 100}
        assert context.flags == {"approved": True}


class TestRuleTransactionIndependence:
    """Test that snapshots are independent from context."""

    def test_snapshot_independence_from_context_modification(self):
        """Test that modifying context after snapshot doesn't affect snapshot."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
            flags={"approved": True},
            alerts=[],
            categories={},
        )
        tx = RuleTransaction(context)

        # Take snapshot
        snap = tx.snapshot()

        # Deeply modify context (including nested structures)
        context.computed_metrics["score"] = 200
        context.computed_metrics["new_metric"] = 300
        context.flags["approved"] = False
        context.flags["another_flag"] = True

        # Snapshot should be unaffected
        assert snap.computed_metrics == {"score": 100}
        assert snap.flags == {"approved": True}
        assert "new_metric" not in snap.computed_metrics
        assert "another_flag" not in snap.flags

    def test_context_independence_from_snapshot_modification(self):
        """Test that modifying snapshot after creation doesn't affect context."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={"amount": 5000},
            computed_metrics={"score": 100},
            flags={"approved": True},
        )
        tx = RuleTransaction(context)

        # Take snapshot
        snap = tx.snapshot()

        # Modify snapshot
        snap.computed_metrics["score"] = 999
        snap.flags["approved"] = False

        # Context should be unaffected
        assert context.computed_metrics == {"score": 100}
        assert context.flags == {"approved": True}


class TestHasSnapshots:
    """Test has_snapshots property."""

    def test_has_snapshots_false_when_empty(self):
        """Test has_snapshots is False initially."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={},
        )
        tx = RuleTransaction(context)
        assert tx.has_snapshots is False

    def test_has_snapshots_true_after_snapshot(self):
        """Test has_snapshots is True after taking snapshot."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={},
        )
        tx = RuleTransaction(context)
        tx.snapshot()
        assert tx.has_snapshots is True

    def test_has_snapshots_false_after_commit(self):
        """Test has_snapshots is False after commit."""
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="credit",
            entity_data={},
        )
        tx = RuleTransaction(context)
        tx.snapshot()
        tx.commit()
        assert tx.has_snapshots is False

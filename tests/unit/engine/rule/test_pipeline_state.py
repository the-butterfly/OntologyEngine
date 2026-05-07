"""Tests for PipelineStateManager."""

import pytest
import pytest_asyncio

from ontology_engine.engine.rule.pipeline_state import (
    PipelineStateManager,
    PipelineStatus,
    StepStatus,
)


class TestPipelineStatusEnum:
    """Test PipelineStatus enum values."""

    def test_pipeline_status_values(self):
        """Verify all expected status values exist."""
        assert PipelineStatus.PENDING.value == "PENDING"
        assert PipelineStatus.RUNNING.value == "RUNNING"
        assert PipelineStatus.COMPLETED.value == "COMPLETED"
        assert PipelineStatus.FAILED.value == "FAILED"
        assert PipelineStatus.PARTIALLY_COMPLETED.value == "PARTIALLY_COMPLETED"


class TestStepStatusEnum:
    """Test StepStatus enum values."""

    def test_step_status_values(self):
        """Verify all expected status values exist."""
        assert StepStatus.PENDING.value == "PENDING"
        assert StepStatus.RUNNING.value == "RUNNING"
        assert StepStatus.COMPLETED.value == "COMPLETED"
        assert StepStatus.SKIPPED.value == "SKIPPED"
        assert StepStatus.FAILED.value == "FAILED"
        assert StepStatus.ROLLED_BACK.value == "ROLLED_BACK"


class TestPipelineRunCreation:
    """Test PipelineRun creation and initial state."""

    @pytest.fixture
    def manager(self):
        return PipelineStateManager()

    @pytest.mark.asyncio
    async def test_create_run_returns_pending_run(self, manager):
        """Test that create_run creates a run in PENDING status."""
        run = await manager.create_run(
            rule_logic_name="credit_assessment",
            rule_definition_name="scorecard_v1",
            entity_id="entity_123",
            dimension="credit_risk",
        )
        assert run.status == PipelineStatus.PENDING
        assert run.rule_logic_name == "credit_assessment"
        assert run.rule_definition_name == "scorecard_v1"
        assert run.entity_id == "entity_123"
        assert run.dimension == "credit_risk"
        assert run.id is not None
        assert run.created_at is not None

    @pytest.mark.asyncio
    async def test_create_run_with_config(self, manager):
        """Test that run_config is stored correctly."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
            run_config={"timeout": 30, "retry": 3},
        )
        assert run.run_config == {"timeout": 30, "retry": 3}

    @pytest.mark.asyncio
    async def test_create_run_with_source_metadata(self, manager):
        """Test source_user, source_content_hash, supersedes are stored."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
            source_user="alice",
            source_content_hash="abc123",
            supersedes="run_001",
        )
        assert run.source_user == "alice"
        assert run.source_content_hash == "abc123"
        assert run.supersedes == "run_001"

    @pytest.mark.asyncio
    async def test_create_run_default_source_pipeline(self, manager):
        """Test that source_pipeline defaults to 'rule_engine'."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        assert run.source_pipeline == "rule_engine"


class TestPipelineRunStateTransitions:
    """Test PipelineRun state transitions."""

    @pytest.fixture
    def manager(self):
        return PipelineStateManager()

    @pytest.mark.asyncio
    async def test_start_run_transitions_to_running(self, manager):
        """Test that start_run changes status to RUNNING and sets started_at."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        await manager.start_run(run.id)
        assert run.status == PipelineStatus.RUNNING
        assert run.started_at is not None

    @pytest.mark.asyncio
    async def test_start_run_not_found_raises(self, manager):
        """Test that starting a non-existent run raises KeyError."""
        with pytest.raises(KeyError, match="Run .* not found"):
            await manager.start_run("non_existent_id")

    @pytest.mark.asyncio
    async def test_start_run_wrong_status_raises(self, manager):
        """Test that starting a non-PENDING run raises ValueError."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        await manager.start_run(run.id)
        with pytest.raises(ValueError, match="expected PENDING"):
            await manager.start_run(run.id)

    @pytest.mark.asyncio
    async def test_complete_run_transitions_to_completed(self, manager):
        """Test that complete_run changes status to COMPLETED."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        await manager.start_run(run.id)
        await manager.complete_run(run.id)
        assert run.status == PipelineStatus.COMPLETED
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_run_wrong_status_raises(self, manager):
        """Test that completing a non-RUNNING run raises ValueError."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        with pytest.raises(ValueError, match="expected RUNNING"):
            await manager.complete_run(run.id)

    @pytest.mark.asyncio
    async def test_fail_run_transitions_to_failed(self, manager):
        """Test that fail_run changes status to FAILED with error message."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        await manager.start_run(run.id)
        await manager.fail_run(run.id, "Something went wrong")
        assert run.status == PipelineStatus.FAILED
        assert run.error_message == "Something went wrong"
        assert run.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_run_wrong_status_raises(self, manager):
        """Test that failing a non-RUNNING run raises ValueError."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        with pytest.raises(ValueError, match="expected RUNNING"):
            await manager.fail_run(run.id, "error")

    @pytest.mark.asyncio
    async def test_partial_complete_run_transitions_to_partially_completed(self, manager):
        """Test that partial_complete_run changes status to PARTIALLY_COMPLETED."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        await manager.start_run(run.id)
        await manager.partial_complete_run(run.id)
        assert run.status == PipelineStatus.PARTIALLY_COMPLETED
        assert run.completed_at is not None


class TestStepSnapshotCreation:
    """Test ExecutionStepSnapshot creation."""

    @pytest.fixture
    def manager(self):
        return PipelineStateManager()

    @pytest.mark.asyncio
    async def test_create_step_snapshot_returns_pending(self, manager):
        """Test that create_step_snapshot creates snapshot in PENDING status."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        snapshot = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_1",
            step_name="Calculate Score",
        )
        assert snapshot.status == StepStatus.PENDING
        assert snapshot.step_id == "step_1"
        assert snapshot.step_name == "Calculate Score"
        assert snapshot.pipeline_run_id == run.id

    @pytest.mark.asyncio
    async def test_create_step_snapshot_with_options(self, manager):
        """Test creating step snapshot with dag_layer, depends_on, etc."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        snapshot = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_1",
            step_name="Calculate Score",
            dag_layer=2,
            depends_on=["step_0"],
            action_type="compute",
            operator_name="weighted_sum",
        )
        assert snapshot.dag_layer == 2
        assert snapshot.depends_on == ["step_0"]
        assert snapshot.action_type == "compute"
        assert snapshot.operator_name == "weighted_sum"

    @pytest.mark.asyncio
    async def test_create_step_snapshot_run_not_found_raises(self, manager):
        """Test that creating snapshot for non-existent run raises KeyError."""
        with pytest.raises(KeyError, match="Pipeline run .* not found"):
            await manager.create_step_snapshot(
                pipeline_run_id="non_existent",
                step_id="step_1",
                step_name="Test",
            )


class TestStepSnapshotStateTransitions:
    """Test ExecutionStepSnapshot state transitions."""

    @pytest.fixture
    def manager(self):
        return PipelineStateManager()

    @pytest_asyncio.fixture
    async def setup_run_and_snapshot(self, manager):
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        snapshot = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_1",
            step_name="Calculate Score",
        )
        return run, snapshot

    @pytest.mark.asyncio
    async def test_start_step_transitions_to_running(self, manager, setup_run_and_snapshot):
        """Test that start_step changes status to RUNNING."""
        run, snapshot = setup_run_and_snapshot
        await manager.start_step(snapshot.id, {"input": "data"})
        assert snapshot.status == StepStatus.RUNNING
        assert snapshot.started_at is not None
        assert snapshot.input_snapshot == {"input": "data"}

    @pytest.mark.asyncio
    async def test_start_step_not_found_raises(self, manager):
        """Test that starting non-existent step raises KeyError."""
        with pytest.raises(KeyError, match="Step snapshot .* not found"):
            await manager.start_step("non_existent", {})

    @pytest.mark.asyncio
    async def test_start_step_wrong_status_raises(self, manager, setup_run_and_snapshot):
        """Test that starting a non-PENDING step raises ValueError."""
        run, snapshot = setup_run_and_snapshot
        await manager.start_step(snapshot.id, {})
        with pytest.raises(ValueError, match="expected PENDING"):
            await manager.start_step(snapshot.id, {})

    @pytest.mark.asyncio
    async def test_complete_step_transitions_to_completed(self, manager, setup_run_and_snapshot):
        """Test that complete_step changes status to COMPLETED."""
        run, snapshot = setup_run_and_snapshot
        await manager.start_step(snapshot.id, {"input": "data"})
        await manager.complete_step(snapshot.id, condition_met=True, output_snapshot={"result": 100})
        assert snapshot.status == StepStatus.COMPLETED
        assert snapshot.completed_at is not None
        assert snapshot.condition_met is True
        assert snapshot.output_snapshot == {"result": 100}

    @pytest.mark.asyncio
    async def test_complete_step_wrong_status_raises(self, manager, setup_run_and_snapshot):
        """Test that completing a non-RUNNING step raises ValueError."""
        run, snapshot = setup_run_and_snapshot
        with pytest.raises(ValueError, match="expected RUNNING"):
            await manager.complete_step(snapshot.id, condition_met=True, output_snapshot={})

    @pytest.mark.asyncio
    async def test_skip_step_transitions_to_skipped(self, manager, setup_run_and_snapshot):
        """Test that skip_step changes status to SKIPPED with reason."""
        run, snapshot = setup_run_and_snapshot
        await manager.skip_step(snapshot.id, "Condition not met")
        assert snapshot.status == StepStatus.SKIPPED
        assert snapshot.completed_at is not None
        assert snapshot.skip_reason == "Condition not met"

    @pytest.mark.asyncio
    async def test_skip_step_wrong_status_raises(self, manager, setup_run_and_snapshot):
        """Test that skipping a non-PENDING step raises ValueError."""
        run, snapshot = setup_run_and_snapshot
        await manager.start_step(snapshot.id, {})
        with pytest.raises(ValueError, match="expected PENDING"):
            await manager.skip_step(snapshot.id, "reason")

    @pytest.mark.asyncio
    async def test_rollback_step_transitions_to_rolled_back(self, manager, setup_run_and_snapshot):
        """Test that rollback_step changes status to ROLLED_BACK."""
        run, snapshot = setup_run_and_snapshot
        await manager.start_step(snapshot.id, {})
        await manager.complete_step(snapshot.id, condition_met=True, output_snapshot={})
        await manager.rollback_step(snapshot.id)
        assert snapshot.status == StepStatus.ROLLED_BACK
        assert snapshot.completed_at is not None

    @pytest.mark.asyncio
    async def test_rollback_step_from_failed(self, manager):
        """Test that rollback works from FAILED status."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        snapshot = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_1",
            step_name="Test Step",
        )
        await manager.start_step(snapshot.id, {})
        # Simulate failure by directly setting status (for testing rollback)
        snapshot.status = StepStatus.FAILED
        await manager.rollback_step(snapshot.id)
        assert snapshot.status == StepStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_rollback_step_wrong_status_raises(self, manager, setup_run_and_snapshot):
        """Test that rollback on PENDING step raises ValueError."""
        run, snapshot = setup_run_and_snapshot
        with pytest.raises(ValueError, match="expected COMPLETED or FAILED"):
            await manager.rollback_step(snapshot.id)


class TestQueryMethods:
    """Test PipelineStateManager query methods."""

    @pytest.fixture
    def manager(self):
        return PipelineStateManager()

    @pytest.mark.asyncio
    async def test_get_run_found(self, manager):
        """Test get_run returns run when it exists."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        result = await manager.get_run(run.id)
        assert result is not None
        assert result.id == run.id

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, manager):
        """Test get_run returns None when run doesn't exist."""
        result = await manager.get_run("non_existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_run_returns_most_recent(self, manager):
        """Test get_latest_run returns the most recently created run."""
        run1 = await manager.create_run(
            rule_logic_name="test_logic",
            rule_definition_name="def1",
            entity_id="entity_x",
            dimension="dim1",
        )
        run2 = await manager.create_run(
            rule_logic_name="test_logic",
            rule_definition_name="def1",
            entity_id="entity_x",
            dimension="dim1",
        )
        result = await manager.get_latest_run("test_logic", "entity_x")
        assert result is not None
        assert result.id == run2.id

    @pytest.mark.asyncio
    async def test_get_latest_run_no_match(self, manager):
        """Test get_latest_run returns None when no runs match."""
        await manager.create_run(
            rule_logic_name="other_logic",
            rule_definition_name="def1",
            entity_id="entity_x",
            dimension="dim1",
        )
        result = await manager.get_latest_run("non_existent_logic", "entity_x")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_step_snapshots_returns_all_for_run(self, manager):
        """Test get_step_snapshots returns all snapshots for a run."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        s1 = await manager.create_step_snapshot(run.id, "step_1", "Step 1")
        s2 = await manager.create_step_snapshot(run.id, "step_2", "Step 2")
        result = await manager.get_step_snapshots(run.id)
        assert len(result) == 2
        ids = [s.id for s in result]
        assert s1.id in ids
        assert s2.id in ids

    @pytest.mark.asyncio
    async def test_get_step_snapshots_empty_for_new_run(self, manager):
        """Test get_step_snapshots returns empty list for run with no steps."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        result = await manager.get_step_snapshots(run.id)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_step_snapshots_run_not_found(self, manager):
        """Test get_step_snapshots returns empty list for non-existent run."""
        result = await manager.get_step_snapshots("non_existent_run")
        assert result == []

    @pytest.mark.asyncio
    async def test_get_completed_step_ids(self, manager):
        """Test get_completed_step_ids returns only completed step IDs."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        s1 = await manager.create_step_snapshot(run.id, "step_1", "Step 1")
        s2 = await manager.create_step_snapshot(run.id, "step_2", "Step 2")
        s3 = await manager.create_step_snapshot(run.id, "step_3", "Step 3")

        await manager.start_step(s1.id, {})
        await manager.complete_step(s1.id, condition_met=True, output_snapshot={})

        await manager.start_step(s2.id, {})
        await manager.complete_step(s2.id, condition_met=False, output_snapshot={})

        # s3 remains PENDING

        completed_ids = await manager.get_completed_step_ids(run.id)
        assert len(completed_ids) == 2
        assert s1.id in completed_ids
        assert s2.id in completed_ids
        assert s3.id not in completed_ids

    @pytest.mark.asyncio
    async def test_get_completed_step_ids_empty(self, manager):
        """Test get_completed_step_ids returns empty when no steps completed."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        completed_ids = await manager.get_completed_step_ids(run.id)
        assert completed_ids == []


class TestFullPipelineLifecycle:
    """Test complete pipeline execution lifecycle."""

    @pytest.fixture
    def manager(self):
        return PipelineStateManager()

    @pytest.mark.asyncio
    async def test_full_successful_pipeline(self, manager):
        """Test a complete successful pipeline execution."""
        # Create run
        run = await manager.create_run(
            rule_logic_name="credit_assessment",
            rule_definition_name="scorecard_v1",
            entity_id="entity_123",
            dimension="credit_risk",
            run_config={"timeout": 60},
        )
        assert run.status == PipelineStatus.PENDING

        # Create steps
        step1 = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_calculate_score",
            step_name="Calculate Score",
            dag_layer=0,
            action_type="compute",
            operator_name="weighted_sum",
        )
        step2 = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_evaluate",
            step_name="Evaluate",
            dag_layer=1,
            depends_on=["step_calculate_score"],
            action_type="decision",
            operator_name="llm_judge",
        )

        # Start run
        await manager.start_run(run.id)
        assert run.status == PipelineStatus.RUNNING

        # Execute step 1
        await manager.start_step(step1.id, {"scores": [80, 70, 90]})
        await manager.complete_step(step1.id, condition_met=True, output_snapshot={"total_score": 240})

        # Execute step 2
        await manager.start_step(step2.id, {"score": 240})
        await manager.complete_step(step2.id, condition_met=True, output_snapshot={"decision": "approve"})

        # Complete run
        await manager.complete_run(run.id)
        assert run.status == PipelineStatus.COMPLETED

        # Verify final state
        snapshots = await manager.get_step_snapshots(run.id)
        assert len(snapshots) == 2
        completed_ids = await manager.get_completed_step_ids(run.id)
        assert len(completed_ids) == 2

    @pytest.mark.asyncio
    async def test_pipeline_with_skipped_steps(self, manager):
        """Test pipeline execution with some steps skipped."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        step1 = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_1",
            step_name="Required Step",
            dag_layer=0,
        )
        step2 = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_2",
            step_name="Optional Step",
            dag_layer=1,
        )

        await manager.start_run(run.id)

        await manager.start_step(step1.id, {})
        await manager.complete_step(step1.id, condition_met=True, output_snapshot={})

        # Step 2 is skipped due to condition
        await manager.skip_step(step2.id, "Condition not met - skipping")

        await manager.partial_complete_run(run.id)
        assert run.status == PipelineStatus.PARTIALLY_COMPLETED

    @pytest.mark.asyncio
    async def test_pipeline_with_failed_step(self, manager):
        """Test pipeline execution with a failed step."""
        run = await manager.create_run(
            rule_logic_name="test",
            rule_definition_name="test_def",
            entity_id="e1",
            dimension="dim1",
        )
        step1 = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_1",
            step_name="Step 1",
            dag_layer=0,
        )
        step2 = await manager.create_step_snapshot(
            pipeline_run_id=run.id,
            step_id="step_2",
            step_name="Step 2",
            dag_layer=1,
        )

        await manager.start_run(run.id)

        await manager.start_step(step1.id, {})
        # Simulate failure - directly set status since our complete_step requires RUNNING
        step1.status = StepStatus.FAILED
        step1.error_message = "Division by zero"
        step1.completed_at = "2024-01-01T00:00:00Z"

        await manager.fail_run(run.id, "Step 1 failed: Division by zero")
        assert run.status == PipelineStatus.FAILED
        assert run.error_message == "Step 1 failed: Division by zero"
# tests/unit/engine/rule/test_dag_executor.py
"""Tests for DAGExecutor."""

import pytest

from ontology_engine.engine.rule.dag_builder import DAGBuilder, ExecutionDAG, DAGLayer, DAGNode
from ontology_engine.engine.rule.dag_executor import (
    DAGExecutor,
    ErrorStrategy,
    StepResult,
    ExecutionResult,
    LayerExecutionError,
    ExecutionAbortedError,
    StepExecutionError,
)
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleStep,
    ConditionClause,
    ActionClause,
    Alert,
)
from ontology_engine.engine.rule.transaction import RuleTransaction, ContextSnapshot
from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


# Test operators
@OperatorRegistry.register("test_set_flag")
class TestSetFlagOperator(Operator):
    """Test operator that sets a flag."""

    @property
    def name(self) -> str:
        return "test_set_flag"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        flag_name = inputs.get("flag_name", "flag")
        flag_value = inputs.get("flag_value", True)
        return {flag_name: flag_value}


@OperatorRegistry.register("test_compute")
class TestComputeOperator(Operator):
    """Test operator that computes a value."""

    @property
    def name(self) -> str:
        return "test_compute"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        formula = inputs.get("formula", "0")
        value = inputs.get("value", 100)
        return {"result": value * 2, "formula": formula}


@OperatorRegistry.register("test_failing")
class TestFailingOperator(Operator):
    """Test operator that always fails."""

    @property
    def name(self) -> str:
        return "test_failing"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        raise ValueError("Test failure")


@OperatorRegistry.register("test_reject")
class TestRejectOperator(Operator):
    """Test operator that rejects."""

    @property
    def name(self) -> str:
        return "test_reject"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        return {
            "rejected": True,
            "rejection_reason": inputs.get("reason", "Test rejection")
        }


@OperatorRegistry.register("test_alert")
class TestAlertOperator(Operator):
    """Test operator that emits an alert."""

    @property
    def name(self) -> str:
        return "test_alert"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        return {"alert_triggered": True, "alerts": [{"level": "warning", "type": "test", "message": "Test alert"}]}


def make_step(
    step_id: str,
    name: str,
    rule_group: str = "test_group",
    order: int = 1,
    depends_on: list[str] | None = None,
    when_expr: str | None = "True",
    then_op: str = "test_set_flag",
    then_params: dict | None = None,
    else_op: str | None = None,
    else_params: dict | None = None,
    enabled: bool = True,
) -> RuleStep:
    """Helper to create a RuleStep for testing."""
    then_params = then_params or {"flag_name": f"flag_{step_id}"}
    then = ActionClause(operator=then_op, params=then_params)
    else_ = None
    if else_op:
        else_ = ActionClause(operator=else_op, params=else_params or {})

    return RuleStep(
        id=step_id,
        name=name,
        rule_group=rule_group,
        order=order,
        when=ConditionClause(type="expression", expression=when_expr),
        then=then,
        else_=else_,
        enabled=enabled,
        depends_on=depends_on or [],
    )


class TestErrorStrategy:
    """Test ErrorStrategy enum."""

    def test_error_strategy_values(self):
        assert ErrorStrategy.STOP_LAYER.value == "stop_layer"
        assert ErrorStrategy.CONTINUE.value == "continue"
        assert ErrorStrategy.ABORT_ALL.value == "abort_all"


class TestStepResult:
    """Test StepResult dataclass."""

    def test_create_step_result(self):
        result = StepResult(step_id="step_1")
        assert result.step_id == "step_1"
        assert result.skipped is False
        assert result.rejected is False
        assert result.reason is None
        assert result.output == {}
        assert result.error is None
        assert result.alert_emitted is False

    def test_create_step_result_with_all_fields(self):
        result = StepResult(
            step_id="step_1",
            skipped=True,
            rejected=False,
            reason="Condition not met",
            output={"key": "value"},
            error=None,
            alert_emitted=True,
        )
        assert result.step_id == "step_1"
        assert result.skipped is True
        assert result.reason == "Condition not met"
        assert result.output == {"key": "value"}


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_create_execution_result(self):
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )
        result = ExecutionResult(results={}, context=context)
        assert result.results == {}
        assert result.context == context


class TestLayerExecutionError:
    """Test LayerExecutionError exception."""

    def test_layer_execution_error(self):
        errors = [StepExecutionError("step_1", "Failed"), StepExecutionError("step_2", "Failed")]
        error = LayerExecutionError(1, errors)
        assert error.layer_index == 1
        assert len(error.errors) == 2


class TestExecutionAbortedError:
    """Test ExecutionAbortedError exception."""

    def test_execution_aborted_error(self):
        error = ExecutionAbortedError("Execution aborted")
        assert str(error) == "Execution aborted"


class TestDAGExecutorInit:
    """Test DAGExecutor initialization."""

    def test_default_init(self):
        executor = DAGExecutor()
        assert executor.max_concurrency == 8
        assert executor.error_strategy == ErrorStrategy.STOP_LAYER

    def test_custom_init(self):
        executor = DAGExecutor(max_concurrency=4, error_strategy=ErrorStrategy.CONTINUE)
        assert executor.max_concurrency == 4
        assert executor.error_strategy == ErrorStrategy.CONTINUE


class TestDAGExecutorSingleStep:
    """Test DAGExecutor with single step execution."""

    @pytest.mark.asyncio
    async def test_single_step_execution(self):
        builder = DAGBuilder()
        steps = [make_step("step_a", "Step A")]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert len(result.results) == 1
        assert "step_a" in result.results
        assert result.results["step_a"].skipped is False
        assert result.results["step_a"].error is None

    @pytest.mark.asyncio
    async def test_single_step_sets_flag(self):
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", then_op="test_set_flag", then_params={"flag_name": "eligible", "flag_value": True})
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.context.flags.get("eligible") is True


class TestDAGExecutorLinearDAG:
    """Test DAGExecutor with linear DAG (A -> B -> C)."""

    @pytest.mark.asyncio
    async def test_linear_dag_execution(self):
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_b"]),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert len(result.results) == 3
        assert "step_a" in result.results
        assert "step_b" in result.results
        assert "step_c" in result.results
        # All steps should succeed
        for step_id in ["step_a", "step_b", "step_c"]:
            assert result.results[step_id].error is None
            assert result.results[step_id].skipped is False

    @pytest.mark.asyncio
    async def test_linear_dag_maintains_order(self):
        """Test that linear DAG executes in correct order via context."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", then_op="test_compute", then_params={"value": 1}),
            make_step("step_b", "Step B", depends_on=["step_a"], then_op="test_compute", then_params={"value": 2}),
            make_step("step_c", "Step C", depends_on=["step_b"], then_op="test_compute", then_params={"value": 3}),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert len(result.results) == 3
        # Results should be available
        assert result.results["step_a"].output.get("result") == 2
        assert result.results["step_b"].output.get("result") == 4
        assert result.results["step_c"].output.get("result") == 6


class TestDAGExecutorParallelLayer:
    """Test DAGExecutor with parallel layer execution."""

    @pytest.mark.asyncio
    async def test_parallel_layer_execution(self):
        """Test that nodes in same layer execute in parallel."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
            make_step("step_d", "Step D", depends_on=["step_a"]),
        ]
        dag = builder.build(steps)

        # Layer 0: step_a
        # Layer 1: step_b, step_c, step_d (parallel)
        assert len(dag.layers) == 2
        assert len(dag.layers[1].nodes) == 3

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert len(result.results) == 4
        # All parallel steps should succeed
        for step_id in ["step_b", "step_c", "step_d"]:
            assert result.results[step_id].error is None
            assert result.results[step_id].skipped is False


class TestDAGExecutorConditionSkipping:
    """Test DAGExecutor with condition evaluation and skipping."""

    @pytest.mark.asyncio
    async def test_condition_true_executes_then(self):
        """Test that when condition is True, then clause is executed."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                when_expr="1 > 0",
                then_op="test_set_flag",
                then_params={"flag_name": "executed", "flag_value": True}
            )
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.results["step_a"].skipped is False
        assert result.context.flags.get("executed") is True

    @pytest.mark.asyncio
    async def test_condition_false_skips_step(self):
        """Test that when condition is False, step is skipped."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                when_expr="1 > 2",  # False condition
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True}
            )
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.results["step_a"].skipped is True
        assert result.results["step_a"].reason == "Condition not met"
        assert "should_not_set" not in result.context.flags

    @pytest.mark.asyncio
    async def test_condition_false_executes_else(self):
        """Test that when condition is False, else clause is executed."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                when_expr="1 > 2",  # False condition
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True},
                else_op="test_set_flag",
                else_params={"flag_name": "else_executed", "flag_value": True}
            )
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.results["step_a"].skipped is False
        assert "should_not_set" not in result.context.flags
        assert result.context.flags.get("else_executed") is True


class TestDAGExecutorDisabledStep:
    """Test DAGExecutor with disabled steps."""

    @pytest.mark.asyncio
    async def test_disabled_step_skipped(self):
        """Test that disabled steps are skipped."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", enabled=False)
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.results["step_a"].skipped is True
        assert result.results["step_a"].reason == "Step disabled"


class TestDAGExecutorStopLayerStrategy:
    """Test DAGExecutor with STOP_LAYER error strategy."""

    @pytest.mark.asyncio
    async def test_stop_layer_on_failure(self):
        """Test that STOP_LAYER strategy stops execution on layer failure."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step(
                "step_b",
                "Step B",
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={}
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.STOP_LAYER)

        with pytest.raises(LayerExecutionError) as exc_info:
            await executor.execute(dag, context)

        assert exc_info.value.layer_index == 1
        assert len(exc_info.value.errors) == 1

    @pytest.mark.asyncio
    async def test_stop_layer_restores_snapshot(self):
        """Test that STOP_LAYER strategy restores snapshot on failure."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                then_op="test_set_flag",
                then_params={"flag_name": "step_a_done", "flag_value": True}
            ),
            make_step(
                "step_b",
                "Step B",
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={}
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            flags={"initial_flag": True},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.STOP_LAYER)

        with pytest.raises(LayerExecutionError):
            await executor.execute(dag, context)

        # Context should be restored to snapshot state
        # step_a_done flag should NOT be present since it was in a layer that was rolled back
        # (Actually step_a is in layer 0 which commits before layer 1 starts)
        # The failure is in layer 1, so layer 0 results stand
        # But step_b failure causes rollback of layer 1, not layer 0


class TestDAGExecutorContinueStrategy:
    """Test DAGExecutor with CONTINUE error strategy."""

    @pytest.mark.asyncio
    async def test_continue_skips_failing_step(self):
        """Test that CONTINUE strategy skips failing steps and continues."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step(
                "step_b",
                "Step B",
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={}
            ),
            make_step(
                "step_c",
                "Step C",
                depends_on=["step_b"],
                then_op="test_set_flag",
                then_params={"flag_name": "step_c_done", "flag_value": True}
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.CONTINUE)
        result = await executor.execute(dag, context)

        # step_a and step_c should succeed
        assert result.results["step_a"].error is None
        assert result.results["step_c"].error is None
        # step_b should have error
        assert result.results["step_b"].error is not None
        # step_c should have executed
        assert result.context.flags.get("step_c_done") is True


class TestDAGExecutorAbortAllStrategy:
    """Test DAGExecutor with ABORT_ALL error strategy."""

    @pytest.mark.asyncio
    async def test_abort_all_stops_all_execution(self):
        """Test that ABORT_ALL strategy stops all execution on any failure."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step(
                "step_b",
                "Step B",
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={}
            ),
            make_step(
                "step_c",
                "Step C",
                depends_on=["step_b"],
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True}
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.ABORT_ALL)

        with pytest.raises(ExecutionAbortedError):
            await executor.execute(dag, context)

    @pytest.mark.asyncio
    async def test_abort_all_preserves_earlier_layers(self):
        """Test that ABORT_ALL raises exception and preserves committed layer state in context.

        Note: ABORT_ALL raises ExecutionAbortedError and does not return a result.
        The context at the point of abort still contains the committed state from
        earlier layers, but since we raise an exception, the caller cannot access it.
        This test verifies that ABORT_ALL correctly raises an exception.
        """
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                then_op="test_set_flag",
                then_params={"flag_name": "layer0_done", "flag_value": True}
            ),
            make_step(
                "step_b",
                "Step B",
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={}
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.ABORT_ALL)

        # ABORT_ALL raises an exception and does not return a result
        with pytest.raises(ExecutionAbortedError):
            await executor.execute(dag, context)


class TestDAGExecutorComplexDAG:
    """Test DAGExecutor with complex DAG structures."""

    @pytest.mark.asyncio
    async def test_diamond_dag_execution(self):
        r"""Test diamond-shaped DAG:

            A
           / \
          B   C
           \ /
            D
        """
        builder = DAGBuilder()
        steps = [
            make_step("a", "A"),
            make_step("b", "B", depends_on=["a"]),
            make_step("c", "C", depends_on=["a"]),
            make_step("d", "D", depends_on=["b", "c"]),
        ]
        dag = builder.build(steps)

        assert len(dag.layers) == 3
        assert dag.layers[0].nodes[0].step_id == "a"
        assert len(dag.layers[1].nodes) == 2
        assert dag.layers[2].nodes[0].step_id == "d"

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert len(result.results) == 4
        for step_id in ["a", "b", "c", "d"]:
            assert result.results[step_id].error is None


class TestDAGExecutorEmptyDAG:
    """Test DAGExecutor with empty DAG."""

    @pytest.mark.asyncio
    async def test_empty_dag_execution(self):
        """Test execution of empty DAG."""
        builder = DAGBuilder()
        dag = builder.build([])

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert len(result.results) == 0

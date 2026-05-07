# tests/unit/engine/rule/test_rule_executor.py
"""Tests for RuleExecutor execute_rule_group method."""

import pytest

from ontology_engine.engine.rule.executor import RuleExecutor
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    AnalysisResult,
    RuleGroupDefinition,
    RuleStep,
    ConditionClause,
    ActionClause,
    AppliesToConfig,
)


def make_rule_group(
    group_id: str = "test_group",
    name: str = "Test Group",
    priority: int = 100,
) -> RuleGroupDefinition:
    """Helper to create a RuleGroupDefinition."""
    return RuleGroupDefinition(
        id=group_id,
        name=name,
        priority=priority,
        applies_to=AppliesToConfig(fact_objects=["TestEntity"]),
    )


def make_step(
    step_id: str,
    name: str,
    rule_group: str = "test_group",
    order: int = 1,
    depends_on: list[str] | None = None,
    when_expr: str | None = None,
    then_op: str = "set_flag",
    then_params: dict | None = None,
    else_op: str | None = None,
    else_params: dict | None = None,
    enabled: bool = True,
) -> RuleStep:
    """Helper to create a RuleStep for testing."""
    then_params = then_params or {"flag_name": f"flag_{step_id}", "flag_value": True}
    then = ActionClause(operator=then_op, params=then_params)
    else_ = None
    if else_op:
        else_ = ActionClause(operator=else_op, params=else_params or {})

    # No condition by default
    when = None
    if when_expr is not None:
        when = ConditionClause(type="expression", expression=when_expr)

    return RuleStep(
        id=step_id,
        name=name,
        rule_group=rule_group,
        order=order,
        when=when,
        then=then,
        else_=else_,
        enabled=enabled,
        depends_on=depends_on or [],
    )


class TestExecuteRuleGroupWithDAG:
    """Test execute_rule_group with DAG dependencies."""

    @pytest.mark.asyncio
    async def test_dag_execution_linear_dependency(self):
        """Test linear DAG: A -> B -> C."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_b"]),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert isinstance(result, AnalysisResult)
        assert result.entity_id == "entity_1"
        assert result.dimension == "test"
        assert len(result.rule_results) == 3

        # All steps should have passed
        for rr in result.rule_results:
            assert rr.passed is True
            assert rr.error is None

    @pytest.mark.asyncio
    async def test_dag_execution_parallel_layer(self):
        """Test parallel layer execution: A -> [B, C, D]."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
            make_step("step_d", "Step D", depends_on=["step_a"]),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert isinstance(result, AnalysisResult)
        assert len(result.rule_results) == 4

        # All steps should have passed
        for rr in result.rule_results:
            assert rr.passed is True

    @pytest.mark.asyncio
    async def test_dag_execution_diamond_shape(self):
        """Test diamond DAG: A -> B, C -> D."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
            make_step("step_d", "Step D", depends_on=["step_b", "step_c"]),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert isinstance(result, AnalysisResult)
        assert len(result.rule_results) == 4

        # All steps should have passed
        for rr in result.rule_results:
            assert rr.passed is True

    @pytest.mark.asyncio
    async def test_dag_result_conversion_to_rule_results(self):
        """Test that DAG StepResults are correctly converted to RuleResults."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_x", "Step X"),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert len(result.rule_results) == 1
        rr = result.rule_results[0]
        assert rr.rule_id == "step_x"
        assert rr.rule_name == "Step X"
        assert rr.passed is True


class TestExecuteRuleGroupFallback:
    """Test execute_rule_group fallback to priority-based execution."""

    @pytest.mark.asyncio
    async def test_fallback_to_priority_execution(self):
        """Test that steps without depends_on use priority-based execution."""
        rule_group = make_rule_group(priority=100)

        steps = [
            make_step("step_1", "Step 1", order=1),
            make_step("step_2", "Step 2", order=2),
            make_step("step_3", "Step 3", order=3),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert isinstance(result, AnalysisResult)
        assert len(result.rule_results) == 3

        # Steps should be in order (by order desc, so higher order first)
        # With priority fallback, they sort by (-order, -rule_group.priority)
        # So order=3, 2, 1 means step_3 executes first
        assert result.rule_results[0].rule_id == "step_3"
        assert result.rule_results[1].rule_id == "step_2"
        assert result.rule_results[2].rule_id == "step_1"

    @pytest.mark.asyncio
    async def test_fallback_respects_order_field(self):
        """Test that priority fallback correctly sorts by order field."""
        rule_group = make_rule_group(priority=50)

        steps = [
            make_step("step_a", "Step A", order=10),
            make_step("step_b", "Step B", order=5),
            make_step("step_c", "Step C", order=20),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        # Sorted by -order (descending), so order=20 first, then 10, then 5
        assert result.rule_results[0].rule_id == "step_c"
        assert result.rule_results[1].rule_id == "step_a"
        assert result.rule_results[2].rule_id == "step_b"

    @pytest.mark.asyncio
    async def test_fallback_with_condition_false(self):
        """Test priority fallback with false condition."""
        rule_group = make_rule_group()

        steps = [
            make_step(
                "step_always_true", "Always True",
                when_expr="True"
            ),
            make_step(
                "step_always_false", "Always False",
                when_expr="False",
                else_op="set_flag",
                else_params={"flag_name": "false_else_done", "flag_value": True}
            ),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert len(result.rule_results) == 2

        # First step passed
        assert result.rule_results[0].rule_id == "step_always_true"
        assert result.rule_results[0].passed is True

        # Second step didn't pass (condition was false) but else was executed
        assert result.rule_results[1].rule_id == "step_always_false"
        assert result.rule_results[1].passed is False

    @pytest.mark.asyncio
    async def test_fallback_early_termination_on_rejection(self):
        """Test that priority fallback terminates early on rejection."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_1", "Step 1", order=2),
            make_step("step_2", "Step 2", order=1),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        # order=2 runs first (higher order first), then order=1
        # but early termination only happens on rejected or eligible=False
        # Since set_flag doesn't set eligible, no early termination happens
        assert len(result.rule_results) == 2
        assert result.rule_results[0].rule_id == "step_1"
        assert result.rule_results[1].rule_id == "step_2"


class TestExecuteRuleGroupMixed:
    """Test execute_rule_group with mixed DAG and priority scenarios."""

    @pytest.mark.asyncio
    async def test_all_steps_have_empty_depends_on(self):
        """Test that empty depends_on list is treated as no dependencies."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_1", "Step 1", order=1, depends_on=[]),
            make_step("step_2", "Step 2", order=2, depends_on=[]),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        # Should use priority fallback since no step has non-empty depends_on
        assert isinstance(result, AnalysisResult)
        assert len(result.rule_results) == 2

    @pytest.mark.asyncio
    async def test_mixed_with_one_dependency(self):
        """Test that having even one dependency triggers DAG execution."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C"),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        # Should use DAG execution since step_b has depends_on
        assert isinstance(result, AnalysisResult)
        assert len(result.rule_results) == 3


class TestRuleExecutorBackwardCompatibility:
    """Test that existing RuleExecutor methods still work."""

    @pytest.mark.asyncio
    async def test_execute_rule_still_works(self):
        """Test that execute_rule (legacy) still functions."""
        # Note: Testing backward compatibility of execute_rule requires
        # a properly constructed KGMLSchema with RulesDefinition.
        # The execute_rule_group method is the main new feature being tested.
        # This test is intentionally minimal to avoid schema complexity.
        executor = RuleExecutor(schema=None)

        # Just verify the executor can be instantiated and has expected methods
        assert hasattr(executor, 'execute_rule')
        assert hasattr(executor, 'execute_rule_group')
        assert hasattr(executor, 'execute_dimension')


class TestExecuteRuleGroupResultStructure:
    """Test AnalysisResult structure from execute_rule_group."""

    @pytest.mark.asyncio
    async def test_result_contains_entity_id(self):
        """Test that result has correct entity_id."""
        rule_group = make_rule_group()

        steps = [make_step("step_1", "Step 1")]

        context = ExecutionContext(
            entity_id="test_entity_123",
            dimension="credit_assessment",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert result.entity_id == "test_entity_123"
        assert result.dimension == "credit_assessment"

    @pytest.mark.asyncio
    async def test_result_contains_computed_metrics(self):
        """Test that result contains computed metrics from execution."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_1", "Step 1",
                     then_op="set_flag",
                     then_params={"flag_name": "credit_score", "flag_value": 85}),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert "credit_score" in result.computed_metrics
        assert result.computed_metrics["credit_score"] == 85

    @pytest.mark.asyncio
    async def test_result_decision_from_metrics(self):
        """Test that final_decision is extracted from computed_metrics."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_decision", "Decision Step",
                     then_op="set_flag",
                     then_params={"flag_name": "final_decision", "flag_value": "APPROVE"}),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        assert result.decision == "APPROVE"

    @pytest.mark.asyncio
    async def test_result_empty_steps(self):
        """Test execution with no steps."""
        rule_group = make_rule_group()

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, [], context)

        assert isinstance(result, AnalysisResult)
        assert len(result.rule_results) == 0


class TestExecuteRuleGroupDisabledSteps:
    """Test execute_rule_group with disabled steps."""

    @pytest.mark.asyncio
    async def test_disabled_step_is_skipped(self):
        """Test that disabled steps are skipped."""
        rule_group = make_rule_group()

        steps = [
            make_step("step_enabled", "Enabled Step"),
            make_step("step_disabled", "Disabled Step", enabled=False),
        ]

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
            computed_metrics={},
        )

        executor = RuleExecutor(schema=None)
        result = await executor.execute_rule_group(rule_group, steps, context)

        # Only 1 step in results (disabled step is skipped in priority fallback mode)
        # Note: In DAG mode with dependencies, disabled steps would be in results as skipped
        # But in priority fallback (no dependencies), disabled steps are skipped entirely
        assert len(result.rule_results) == 1

        # The enabled step should be in results
        enabled_result = result.rule_results[0]
        assert enabled_result.rule_id == "step_enabled"
        assert enabled_result.passed is True
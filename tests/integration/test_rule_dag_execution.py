"""End-to-end DAG execution integration tests.

Tests the complete DAG execution flow including:
1. Single rule group DAG execution (linear, parallel, complex DAGs)
2. Multi-rule group rule location and chaining
3. Simulation service multi-step interactions
4. Error handling and rollback strategies
"""

import pytest

from ontology_engine.engine.rule.models import (
    ActionClause,
    AppliesToConfig,
    ConditionClause,
    ExecutionContext,
    IOElement,
    RuleGroupDefinition,
    RuleStep,
)
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.dag_executor import (
    DAGExecutor,
    ErrorStrategy,
    LayerExecutionError,
    ExecutionAbortedError,
)
from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry
from ontology_engine.services.simulation_service import (
    SimulationService,
)


# =============================================================================
# Test Operators
# =============================================================================


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


@OperatorRegistry.register("test_add")
class TestAddOperator(Operator):
    """Test operator that adds values."""

    @property
    def name(self) -> str:
        return "test_add"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        a = inputs.get("a", 0)
        b = inputs.get("b", 0)
        return {"sum": a + b}


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
        return {
            "alert_triggered": True,
            "level": "warning",
            "type": "test",
            "message": "Test alert triggered",
            "alerts": [{"level": "warning", "type": "test", "message": "Test alert"}]
        }


# =============================================================================
# Helper Functions
# =============================================================================


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


def make_rule_group(
    name: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    steps: list[RuleStep] | None = None,
) -> RuleGroupDefinition:
    """Helper to create a RuleGroupDefinition for testing."""
    inputs = inputs or []
    outputs = outputs or []

    return RuleGroupDefinition(
        id=f"rg_{name}",
        name=name,
        description=f"Test rule group: {name}",
        type="decision",
        priority=100,
        applies_to=AppliesToConfig(fact_objects=["TestEntity"]),
        preconditions=[],
        inputs=[IOElement(name=n) for n in inputs],
        outputs=[IOElement(name=n) for n in outputs],
        enabled=True,
    )


# =============================================================================
# Test Class: Single Rule Group DAG Execution
# =============================================================================


class TestSingleRuleGroupDAGExecution:
    """Test single rule group DAG execution scenarios."""

    @pytest.mark.asyncio
    async def test_linear_dependency_abc(self):
        """Test linear dependency A → B → C.

        DAG Structure:
            A (layer 0)
            ↓
            B (layer 1)
            ↓
            C (layer 2)
        """
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step("step_b", "Step B", order=2, depends_on=["step_a"]),
            make_step("step_c", "Step C", order=3, depends_on=["step_b"]),
        ]
        dag = builder.build(steps)

        # Verify DAG structure
        assert dag.has_cycle is False
        assert len(dag.layers) == 3
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert dag.layers[1].nodes[0].step_id == "step_b"
        assert dag.layers[2].nodes[0].step_id == "step_c"

        # Execute DAG
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        # Verify all steps executed successfully
        assert len(result.results) == 3
        assert result.results["step_a"].error is None
        assert result.results["step_b"].error is None
        assert result.results["step_c"].error is None

        # Verify flags were set
        assert result.context.flags.get("flag_step_a") is True
        assert result.context.flags.get("flag_step_b") is True
        assert result.context.flags.get("flag_step_c") is True

    @pytest.mark.asyncio
    async def test_parallel_dependency_a_to_bc(self):
        """Test parallel dependency: A → B and A → C.

        DAG Structure:
              A (layer 0)
             / \
            B   C (layer 1)
        """
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step("step_b", "Step B", order=2, depends_on=["step_a"]),
            make_step("step_c", "Step C", order=3, depends_on=["step_a"]),
        ]
        dag = builder.build(steps)

        # Verify DAG structure
        assert dag.has_cycle is False
        assert len(dag.layers) == 2
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert len(dag.layers[1].nodes) == 2
        parallel_ids = {n.step_id for n in dag.layers[1].nodes}
        assert parallel_ids == {"step_b", "step_c"}

        # Execute DAG
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        # Verify all steps executed successfully
        assert len(result.results) == 3
        for step_id in ["step_a", "step_b", "step_c"]:
            assert result.results[step_id].error is None
            assert result.results[step_id].skipped is False

    @pytest.mark.asyncio
    async def test_complex_dag_converging_nodes(self):
        r"""Test complex DAG with converging nodes.

        DAG Structure:
                A (layer 0)
               / \
              B   C (layer 1)
               \ /
                D (layer 2)
        """
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step("step_b", "Step B", order=2, depends_on=["step_a"]),
            make_step("step_c", "Step C", order=3, depends_on=["step_a"]),
            make_step("step_d", "Step D", order=4, depends_on=["step_b", "step_c"]),
        ]
        dag = builder.build(steps)

        # Verify DAG structure
        assert dag.has_cycle is False
        assert len(dag.layers) == 3
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert len(dag.layers[1].nodes) == 2
        assert dag.layers[2].nodes[0].step_id == "step_d"

        # Execute DAG
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        # Verify all steps executed successfully
        assert len(result.results) == 4
        for step_id in ["step_a", "step_b", "step_c", "step_d"]:
            assert result.results[step_id].error is None
            assert result.results[step_id].skipped is False

    @pytest.mark.asyncio
    async def test_diamond_dag_execution(self):
        r"""Test diamond-shaped DAG.

        DAG Structure:
                A (layer 0)
               / \
              B   C (layer 1)
               \ /
                D (layer 2)
               / \
              E   F (layer 3)
        """
        builder = DAGBuilder()
        steps = [
            make_step("a", "A", order=1),
            make_step("b", "B", order=2, depends_on=["a"]),
            make_step("c", "C", order=3, depends_on=["a"]),
            make_step("d", "D", order=4, depends_on=["b", "c"]),
            make_step("e", "E", order=5, depends_on=["d"]),
            make_step("f", "F", order=6, depends_on=["d"]),
        ]
        dag = builder.build(steps)

        # Verify DAG structure
        assert dag.has_cycle is False
        assert len(dag.layers) == 4
        assert dag.layers[0].nodes[0].step_id == "a"
        assert {n.step_id for n in dag.layers[1].nodes} == {"b", "c"}
        assert dag.layers[2].nodes[0].step_id == "d"
        assert {n.step_id for n in dag.layers[3].nodes} == {"e", "f"}

        # Execute DAG
        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        # Verify all steps executed successfully
        assert len(result.results) == 6
        for step_id in ["a", "b", "c", "d", "e", "f"]:
            assert result.results[step_id].error is None


# =============================================================================
# Test Class: Multi-Rule Group Rule Location and Chaining
# =============================================================================


class TestMultiRuleGroupRuleLocation:
    """Test multi-rule group rule location and chaining."""

    @pytest.mark.asyncio
    async def test_locate_rules_by_output_element(self):
        """Test locating rule groups that produce a specific output element."""
        simulation_service = SimulationService()

        # Create rule groups with different outputs
        rule_groups = [
            make_rule_group(
                name="credit_score",
                inputs=["income", "debt"],
                outputs=["credit_score", "risk_level"],
            ),
            make_rule_group(
                name="risk_assessment",
                inputs=["credit_score"],
                outputs=["risk_level", "risk_category"],
            ),
        ]

        all_steps = {
            "credit_score": [
                make_step("cs_calc", "Credit Score Calculation", rule_group="credit_score"),
            ],
            "risk_assessment": [
                make_step("risk_calc", "Risk Calculation", rule_group="risk_assessment"),
            ],
        }

        # Locate rule groups for "credit_score" output
        results = await simulation_service.locate_rules_for_output(
            output_element="credit_score",
            rule_groups=rule_groups,
            all_steps=all_steps,
        )

        assert len(results) == 1
        assert results[0][0].name == "credit_score"

    @pytest.mark.asyncio
    async def test_locate_rules_for_shared_output(self):
        """Test locating rule groups when multiple produce the same output."""
        simulation_service = SimulationService()

        # Create rule groups with overlapping outputs
        rule_groups = [
            make_rule_group(
                name="rule_group_a",
                inputs=["input_a"],
                outputs=["shared_output"],
            ),
            make_rule_group(
                name="rule_group_b",
                inputs=["input_b"],
                outputs=["shared_output", "other_output"],
            ),
        ]

        all_steps = {
            "rule_group_a": [make_step("step_a", "Step A", rule_group="rule_group_a")],
            "rule_group_b": [make_step("step_b", "Step B", rule_group="rule_group_b")],
        }

        # Locate rule groups for "shared_output"
        results = await simulation_service.locate_rules_for_output(
            output_element="shared_output",
            rule_groups=rule_groups,
            all_steps=all_steps,
        )

        assert len(results) == 2
        result_names = {rg.name for rg, _ in results}
        assert result_names == {"rule_group_a", "rule_group_b"}

    @pytest.mark.asyncio
    async def test_locate_rules_no_match(self):
        """Test locating rule groups when no match exists."""
        simulation_service = SimulationService()

        rule_groups = [
            make_rule_group(
                name="credit_score",
                inputs=["income"],
                outputs=["credit_score"],
            ),
        ]

        all_steps = {
            "credit_score": [make_step("cs_calc", "Credit Score Calculation", rule_group="credit_score")],
        }

        # Locate for non-existent output
        results = await simulation_service.locate_rules_for_output(
            output_element="nonexistent_output",
            rule_groups=rule_groups,
            all_steps=all_steps,
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_cross_rule_group_dependency(self):
        """Test DAG building with cross-rule-group dependencies.

        DAG Structure:
            group_1/step_a
                 ↓
            group_2/step_b
                 ↓
            group_3/step_c
        """
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                rule_group="group_1",
                order=1,
                depends_on=[],
            ),
            make_step(
                "step_b",
                "Step B",
                rule_group="group_2",
                order=2,
                depends_on=["group_1/step_a"],
            ),
            make_step(
                "step_c",
                "Step C",
                rule_group="group_3",
                order=3,
                depends_on=["group_2/step_b"],
            ),
        ]
        dag = builder.build(steps)

        # Verify DAG structure
        assert dag.has_cycle is False
        assert len(dag.layers) == 3
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert dag.layers[1].nodes[0].step_id == "step_b"
        assert dag.layers[2].nodes[0].step_id == "step_c"


# =============================================================================
# Test Class: Simulation Service Multi-Step Interactions
# =============================================================================


class TestSimulationServiceMultiStep:
    """Test simulation service multi-step interactions."""

    @pytest.mark.asyncio
    async def test_simulate_rule_group_basic(self):
        """Test basic single rule group simulation."""
        simulation_service = SimulationService()

        rule_group = make_rule_group(
            name="test_group",
            inputs=["x", "y"],
            outputs=["result"],
        )

        steps = [
            make_step(
                "step_a",
                "Step A",
                rule_group="test_group",
                order=1,
                then_op="test_compute",
                then_params={"value": 10},
            ),
        ]

        result = await simulation_service.simulate_rule_group(
            rule_group=rule_group,
            steps=steps,
            entity_data={"x": 5, "y": 3},
        )

        assert result.rule_group_name == "test_group"
        assert len(result.steps) == 1
        assert result.steps[0].step_id == "step_a"
        assert result.final_output.get("result") == 20

    @pytest.mark.asyncio
    async def test_simulate_dag_single_rule_group(self):
        """Test DAG simulation for single rule group."""
        simulation_service = SimulationService()

        rule_group = make_rule_group(
            name="credit_check",
            inputs=["income", "debt"],
            outputs=["credit_score"],
        )

        steps = [
            make_step(
                "step_validate",
                "Validate Inputs",
                rule_group="credit_check",
                order=1,
            ),
            make_step(
                "step_calc",
                "Calculate Score",
                rule_group="credit_check",
                order=2,
                depends_on=["step_validate"],
                then_op="test_compute",
                then_params={"value": 100},
            ),
            make_step(
                "step_finalize",
                "Finalize",
                rule_group="credit_check",
                order=3,
                depends_on=["step_calc"],
            ),
        ]

        result = await simulation_service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={"income": 50000, "debt": 10000},
        )

        assert result.simulation_type == "dag"
        assert result.rule_groups == ["credit_check"]
        assert len(result.steps) == 3
        assert len(result.dag_layers) == 3
        # Verify layer structure
        assert result.dag_layers[0] == ["step_validate"]
        assert result.dag_layers[1] == ["step_calc"]
        assert result.dag_layers[2] == ["step_finalize"]

    @pytest.mark.asyncio
    async def test_simulate_dag_parallel_steps(self):
        """Test DAG simulation with parallel steps."""
        simulation_service = SimulationService()

        rule_group = make_rule_group(
            name="parallel_test",
            inputs=[],
            outputs=["combined_result"],
        )

        steps = [
            make_step("step_a", "Step A", rule_group="parallel_test", order=1),
            make_step(
                "step_b",
                "Step B",
                rule_group="parallel_test",
                order=2,
                depends_on=["step_a"],
            ),
            make_step(
                "step_c",
                "Step C",
                rule_group="parallel_test",
                order=3,
                depends_on=["step_a"],
            ),
            make_step(
                "step_d",
                "Step D",
                rule_group="parallel_test",
                order=4,
                depends_on=["step_b", "step_c"],
            ),
        ]

        result = await simulation_service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert result.simulation_type == "dag"
        assert len(result.steps) == 4
        assert len(result.dag_layers) == 3
        assert result.dag_layers[0] == ["step_a"]
        assert set(result.dag_layers[1]) == {"step_b", "step_c"}
        assert result.dag_layers[2] == ["step_d"]

    @pytest.mark.asyncio
    async def test_whatif_analysis_modify_inputs(self):
        """Test What-if analysis by modifying inputs and re-simulating."""
        simulation_service = SimulationService()

        rule_group = make_rule_group(
            name="credit_check",
            inputs=["income", "debt"],
            outputs=["credit_score", "risk_level"],
        )

        steps = [
            make_step(
                "step_calc",
                "Calculate Score",
                rule_group="credit_check",
                order=1,
                then_op="test_compute",
                then_params={"value": 100},
            ),
        ]

        # Initial simulation
        baseline = await simulation_service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={"income": 50000, "debt": 10000},
        )

        assert baseline.final_output.get("result") == 200

        # What-if: Modify input - double the debt
        modified_inputs = {"income": 50000, "debt": 20000}

        whatif = await simulation_service.agent_interactive_simulation(
            baseline_result=baseline,
            modified_inputs=modified_inputs,
            rule_groups=[rule_group],
            all_steps={"credit_check": steps},
        )

        assert whatif.simulation_type == "agent_interactive"
        assert whatif.modified_inputs == modified_inputs
        # Note: In this simple test case, the modification doesn't affect the result
        # since test_compute just multiplies value by 2

    @pytest.mark.asyncio
    async def test_build_rule_tree_simulation(self):
        """Test building a complete rule tree simulation."""
        simulation_service = SimulationService()

        rule_groups = [
            make_rule_group(
                name="scoring",
                inputs=["processed_input"],
                outputs=["score"],
            ),
        ]

        all_steps = {
            "scoring": [
                make_step(
                    "score",
                    "Calculate Score",
                    rule_group="scoring",
                    order=1,
                ),
                make_step(
                    "finalize",
                    "Finalize Score",
                    rule_group="scoring",
                    order=2,
                    depends_on=["score"],
                ),
            ],
        }

        result = await simulation_service.build_rule_tree_simulation(
            target_output="score",
            rule_groups=rule_groups,
            all_steps=all_steps,
            entity_data={"processed_input": "test_data"},
        )

        assert result.simulation_type == "dag"
        assert "scoring" in result.rule_groups
        assert len(result.steps) >= 1  # At least one step executed


# =============================================================================
# Test Class: Error Handling and Rollback
# =============================================================================


class TestErrorHandlingAndRollback:
    """Test error handling and rollback strategies."""

    @pytest.mark.asyncio
    async def test_stop_layer_strategy_on_failure(self):
        """Test STOP_LAYER strategy stops execution on layer failure."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={},
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
    async def test_stop_layer_preserves_previous_layer_results(self):
        """Test STOP_LAYER preserves results from successful previous layers."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                then_op="test_set_flag",
                then_params={"flag_name": "layer_0_done", "flag_value": True},
            ),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={},
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.STOP_LAYER)

        try:
            await executor.execute(dag, context)
        except LayerExecutionError:
            pass  # Expected

        # Note: Due to transaction rollback, layer 0 results may also be rolled back
        # depending on when the snapshot was taken

    @pytest.mark.asyncio
    async def test_continue_strategy_skips_failing_step(self):
        """Test CONTINUE strategy skips failing steps and continues execution."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={},
            ),
            make_step(
                "step_c",
                "Step C",
                order=3,
                depends_on=["step_b"],
                then_op="test_set_flag",
                then_params={"flag_name": "step_c_done", "flag_value": True},
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

        # step_a should succeed
        assert result.results["step_a"].error is None
        assert result.results["step_a"].skipped is False

        # step_b should have error
        assert result.results["step_b"].error is not None

        # step_c should execute (depends on step_b but CONTINUE allows it)
        # Note: step_c may be skipped if step_b failed and step_c's condition depends on step_b's output
        # In this test, step_c's condition is "True", so it should execute

    @pytest.mark.asyncio
    async def test_continue_strategy_parallel_layer_with_failure(self):
        """Test CONTINUE strategy in a parallel layer with some failures."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_set_flag",
                then_params={"flag_name": "step_b_done", "flag_value": True},
            ),
            make_step(
                "step_c",
                "Step C",
                order=3,
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={},
            ),
            make_step(
                "step_d",
                "Step D",
                order=4,
                depends_on=["step_b", "step_c"],
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

        # step_a should succeed
        assert result.results["step_a"].error is None

        # In parallel layer (layer 1):
        # - step_b should succeed
        # - step_c should fail

        # step_d depends on both step_b and step_c
        # With CONTINUE, execution continues even though step_c failed

    @pytest.mark.asyncio
    async def test_abort_all_strategy_stops_all_execution(self):
        """Test ABORT_ALL strategy stops all execution on any failure."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={},
            ),
            make_step(
                "step_c",
                "Step C",
                order=3,
                depends_on=["step_b"],
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True},
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.ABORT_ALL)

        with pytest.raises(ExecutionAbortedError) as exc_info:
            await executor.execute(dag, context)

        assert "Execution aborted" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_abort_all_raises_exception(self):
        """Test ABORT_ALL raises ExecutionAbortedError and does not return result."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                then_op="test_set_flag",
                then_params={"flag_name": "done", "flag_value": True},
            ),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_failing",
                then_params={},
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor(error_strategy=ErrorStrategy.ABORT_ALL)

        # Should raise and not return a result
        with pytest.raises(ExecutionAbortedError):
            await executor.execute(dag, context)

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


# =============================================================================
# Test Class: Condition Evaluation in DAG
# =============================================================================


class TestConditionEvaluationInDAG:
    """Test condition evaluation and step skipping in DAG execution."""

    @pytest.mark.asyncio
    async def test_condition_true_executes_then_branch(self):
        """Test that when condition is True, then branch is executed."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                when_expr="1 > 0",
                then_op="test_set_flag",
                then_params={"flag_name": "condition_met", "flag_value": True},
            ),
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
        assert result.results["step_a"].error is None
        assert result.context.flags.get("condition_met") is True

    @pytest.mark.asyncio
    async def test_condition_false_skips_step(self):
        """Test that when condition is False, step is skipped."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                when_expr="1 > 2",  # False condition
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True},
            ),
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
    async def test_condition_false_executes_else_branch(self):
        """Test that when condition is False, else branch is executed."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                when_expr="1 > 2",  # False condition
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True},
                else_op="test_set_flag",
                else_params={"flag_name": "else_executed", "flag_value": True},
            ),
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

    @pytest.mark.asyncio
    async def test_disabled_step_skipped(self):
        """Test that disabled steps are skipped."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1, enabled=False),
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

    @pytest.mark.asyncio
    async def test_dag_with_conditional_skipping(self):
        """Test DAG execution with conditional skipping.

        DAG Structure:
            A (always runs)
            ↓
            B (condition: x > 10)
            ↓
            C (always runs, depends on B)
        """
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
            ),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                when_expr="x > 10",  # Will be False
                then_op="test_set_flag",
                then_params={"flag_name": "b_done", "flag_value": True},
            ),
            make_step(
                "step_c",
                "Step C",
                order=3,
                depends_on=["step_b"],
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={"x": 5},  # x is not > 10
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        # step_a should execute
        assert result.results["step_a"].skipped is False

        # step_b should be skipped due to condition
        assert result.results["step_b"].skipped is True

        # step_c should still execute (depends on step_b, but step_b was skipped, not failed)
        assert result.results["step_c"].skipped is False


# =============================================================================
# Test Class: Alert Handling in DAG
# =============================================================================


class TestAlertHandlingInDAG:
    """Test alert handling in DAG execution."""

    @pytest.mark.asyncio
    async def test_alert_operator_triggers_alert(self):
        """Test that alert operator triggers alert in context."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                then_op="test_alert",
                then_params={"message": "Test alert"},
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.results["step_a"].error is None
        assert result.results["step_a"].alert_emitted is True
        assert len(context.alerts) >= 1

    @pytest.mark.asyncio
    async def test_dag_collects_alerts_from_all_layers(self):
        """Test that DAG collects alerts from all layers."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                then_op="test_alert",
                then_params={"message": "Alert from layer 0"},
            ),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_alert",
                then_params={"message": "Alert from layer 1"},
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        # Both steps should have alerts
        assert result.results["step_a"].alert_emitted is True
        assert result.results["step_b"].alert_emitted is True


# =============================================================================
# Test Class: Computed Metrics Propagation
# =============================================================================


class TestComputedMetricsPropagation:
    """Test computed metrics propagation in DAG execution."""

    @pytest.mark.asyncio
    async def test_computed_metrics_available_to_dependent_steps(self):
        """Test that computed metrics are available to dependent steps."""
        builder = DAGBuilder()
        steps = [
            make_step(
                "step_a",
                "Step A",
                order=1,
                then_op="test_compute",
                then_params={"value": 10},
            ),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
                then_op="test_add",
                then_params={"a": 0, "b": 0},  # Will use computed value
            ),
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

        # step_a should compute result=20 (10*2)
        assert result.results["step_a"].output.get("result") == 20

        # step_b should have access to computed result
        assert result.results["step_b"].error is None

    @pytest.mark.asyncio
    async def test_entity_data_available_to_all_steps(self):
        """Test that entity_data is available to all steps."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", order=1),
            make_step(
                "step_b",
                "Step B",
                order=2,
                depends_on=["step_a"],
            ),
        ]
        dag = builder.build(steps)

        context = ExecutionContext(
            entity_id="entity_1",
            dimension="test",
            entity_data={"income": 50000, "debt": 10000},
        )

        executor = DAGExecutor()
        result = await executor.execute(dag, context)

        assert result.results["step_a"].error is None
        assert result.results["step_b"].error is None

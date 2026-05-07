# tests/unit/services/test_simulation_service.py
"""Tests for SimulationService DAG simulation capabilities."""

import pytest

from ontology_engine.services.simulation_service import (
    SimulationService,
    SimulationStep,
    DAGSimulationResult,
)
from ontology_engine.engine.rule.models import (
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
    ConditionClause,
    IOElement,
    AppliesToConfig,
)


# Test operators
from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("test_compute_score")
class TestComputeScoreOperator(Operator):
    """Test operator that computes a score."""

    @property
    def name(self) -> str:
        return "test_compute_score"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        base = inputs.get("base", 0)
        multiplier = inputs.get("multiplier", 1)
        return {"score": base * multiplier, "base": base}


@OperatorRegistry.register("test_apply_grade")
class TestApplyGradeOperator(Operator):
    """Test operator that applies a grade based on score."""

    @property
    def name(self) -> str:
        return "test_apply_grade"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        # Real operators read from context (which contains computed metrics)
        score = context.get("score", 0)
        if score >= 80:
            grade = "A"
        elif score >= 60:
            grade = "B"
        else:
            grade = "C"
        return {"grade": grade, "score": score}


@OperatorRegistry.register("test_decision")
class TestDecisionOperator(Operator):
    """Test operator that makes a decision."""

    @property
    def name(self) -> str:
        return "test_decision"

    async def execute(
        self,
        inputs: dict,
        config: dict,
        context: dict,
    ) -> dict:
        # Real operators read from context
        grade = context.get("grade", "C")
        if grade == "A":
            decision = "APPROVE"
        elif grade == "B":
            decision = "REVIEW"
        else:
            decision = "REJECT"
        return {"final_decision": decision, "decision_reasoning": f"Grade {grade}"}


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


def make_rule_group(
    name: str,
    outputs: list[str] | None = None,
    inputs: list[str] | None = None,
) -> RuleGroupDefinition:
    """Helper to create a RuleGroupDefinition for testing."""
    outputs = outputs or []
    inputs = inputs or []

    return RuleGroupDefinition(
        id=f"rg_{name}",
        name=name,
        outputs=[IOElement(name=o) for o in outputs],
        inputs=[IOElement(name=i) for i in inputs],
        applies_to=AppliesToConfig(fact_objects=["TestEntity"]),
    )


def make_step(
    step_id: str,
    name: str,
    rule_group: str = "test_group",
    order: int = 1,
    depends_on: list[str] | None = None,
    when_expr: str | None = "True",
    then_op: str = "test_set_flag",
    then_params: dict | None = None,
    enabled: bool = True,
) -> RuleStep:
    """Helper to create a RuleStep for testing."""
    then_params = then_params or {"flag_name": f"flag_{step_id}"}
    then = ActionClause(operator=then_op, params=then_params)

    return RuleStep(
        id=step_id,
        name=name,
        rule_group=rule_group,
        order=order,
        when=ConditionClause(type="expression", expression=when_expr),
        then=then,
        enabled=enabled,
        depends_on=depends_on or [],
    )


class TestSimulationStep:
    """Test SimulationStep dataclass."""

    def test_create_simulation_step(self):
        step = SimulationStep(
            step_id="step_1",
            step_name="Test Step",
            layer_index=0,
            execution_order=1,
        )
        assert step.step_id == "step_1"
        assert step.step_name == "Test Step"
        assert step.layer_index == 0
        assert step.execution_order == 1
        assert step.input_values == {}
        assert step.output_values == {}
        assert step.skipped is False

    def test_simulation_step_with_tracking(self):
        step = SimulationStep(
            step_id="step_1",
            step_name="Test Step",
            layer_index=0,
            execution_order=1,
            input_values={"credit_score": 85},
            input_sources={"credit_score": "entity_data"},
            output_values={"grade": "A"},
            output_destinations={"grade": "computed_metrics"},
            depends_on=["step_0"],
        )
        assert step.input_values == {"credit_score": 85}
        assert step.input_sources == {"credit_score": "entity_data"}
        assert step.output_values == {"grade": "A"}
        assert step.depends_on == ["step_0"]


class TestDAGSimulationResult:
    """Test DAGSimulationResult dataclass."""

    def test_create_dag_simulation_result(self):
        result = DAGSimulationResult(
            simulation_id="sim_123",
            simulation_type="dag",
            rule_groups=["credit_assessment"],
            steps=[],
            dag_layers=[["step_a"], ["step_b", "step_c"]],
            final_output={"credit_score": 85, "grade": "A"},
        )
        assert result.simulation_id == "sim_123"
        assert result.simulation_type == "dag"
        assert result.rule_groups == ["credit_assessment"]
        assert len(result.dag_layers) == 2

    def test_dag_simulation_result_with_comparison(self):
        result = DAGSimulationResult(
            simulation_id="sim_456",
            simulation_type="agent_interactive",
            rule_groups=["credit_assessment"],
            baseline_output={"credit_score": 70, "grade": "B"},
            final_output={"credit_score": 85, "grade": "A"},
        )
        # Comparison is built by the service method
        assert result.baseline_output == {"credit_score": 70, "grade": "B"}


class TestSimulationServiceInit:
    """Test SimulationService initialization."""

    def test_init(self):
        service = SimulationService()
        assert service._evaluator is not None


class TestSimulationServiceSimulateDAG:
    """Test SimulationService.simulate_dag()."""

    @pytest.mark.asyncio
    async def test_simulate_dag_single_step(self):
        """Test DAG simulation with single step."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["score"])
        steps = [
            make_step(
                "step_a",
                "Step A",
                then_op="test_compute_score",
                then_params={"base": 100, "multiplier": 1},
            )
        ]

        result = await service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert result.simulation_type == "dag"
        assert result.rule_groups == ["test_rg"]
        assert len(result.steps) == 1
        assert result.steps[0].step_id == "step_a"
        assert result.final_output.get("score") == 100

    @pytest.mark.asyncio
    async def test_simulate_dag_linear_dependencies(self):
        """Test DAG simulation with linear dependencies (A -> B -> C)."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["decision"])
        steps = [
            make_step(
                "step_score",
                "Compute Score",
                then_op="test_compute_score",
                then_params={"base": 50, "multiplier": 2},
            ),
            make_step(
                "step_grade",
                "Apply Grade",
                depends_on=["step_score"],
                then_op="test_apply_grade",
                then_params={},
            ),
            make_step(
                "step_decision",
                "Make Decision",
                depends_on=["step_grade"],
                then_op="test_decision",
                then_params={},
            ),
        ]

        result = await service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert result.simulation_type == "dag"
        assert len(result.steps) == 3

        # Verify execution order
        step_ids = [s.step_id for s in result.steps]
        assert step_ids == ["step_score", "step_grade", "step_decision"]

        # Verify final output
        assert result.final_output.get("score") == 100
        assert result.final_output.get("grade") == "A"
        assert result.final_output.get("final_decision") == "APPROVE"

    @pytest.mark.asyncio
    async def test_simulate_dag_parallel_layer(self):
        """Test DAG simulation with parallel layer execution."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["decision"])
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
        ]

        result = await service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert len(result.steps) == 3

        # Verify DAG layers structure
        assert len(result.dag_layers) == 2
        assert result.dag_layers[0] == ["step_a"]
        assert set(result.dag_layers[1]) == {"step_b", "step_c"}

    @pytest.mark.asyncio
    async def test_simulate_dag_with_condition(self):
        """Test DAG simulation with condition evaluation."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["flag"])
        steps = [
            make_step(
                "step_a",
                "Step A",
                when_expr="1 > 0",
                then_op="test_set_flag",
                then_params={"flag_name": "passed", "flag_value": True},
            )
        ]

        result = await service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert len(result.steps) == 1
        assert result.steps[0].condition_result is True
        assert result.steps[0].skipped is False
        assert result.final_output.get("passed") is True

    @pytest.mark.asyncio
    async def test_simulate_dag_condition_not_met(self):
        """Test DAG simulation when condition is not met."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["flag"])
        steps = [
            make_step(
                "step_a",
                "Step A",
                when_expr="1 > 2",  # False condition
                then_op="test_set_flag",
                then_params={"flag_name": "should_not_set", "flag_value": True},
            )
        ]

        result = await service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert len(result.steps) == 1
        assert result.steps[0].condition_result is False
        assert result.steps[0].skipped is True
        assert "should_not_set" not in result.final_output

    @pytest.mark.asyncio
    async def test_simulate_dag_tracks_input_sources(self):
        """Test that DAG simulation tracks input sources."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["result"])
        steps = [
            make_step(
                "step_a",
                "Step A",
                when_expr="credit_score > 50",
                then_op="test_set_flag",
                then_params={"flag_name": "passed", "flag_value": True},
            )
        ]

        result = await service.simulate_dag(
            rule_group=rule_group,
            steps=steps,
            entity_data={"credit_score": 75},
        )

        assert len(result.steps) == 1
        step = result.steps[0]
        assert step.input_sources.get("credit_score") == "entity_data"
        assert step.condition_result is True


class TestLocateRulesForOutput:
    """Test SimulationService.locate_rules_for_output()."""

    @pytest.mark.asyncio
    async def test_locate_rules_finds_output(self):
        """Test locating rule group by output element."""
        service = SimulationService()

        rule_groups = [
            make_rule_group("credit_assessment", outputs=["credit_score", "grade"]),
            make_rule_group("risk_assessment", outputs=["risk_level"]),
        ]

        all_steps = {
            "credit_assessment": [
                make_step("score_step", "Score Step", rule_group="credit_assessment"),
            ],
            "risk_assessment": [
                make_step("risk_step", "Risk Step", rule_group="risk_assessment"),
            ],
        }

        results = await service.locate_rules_for_output(
            output_element="credit_score",
            rule_groups=rule_groups,
            all_steps=all_steps,
        )

        assert len(results) == 1
        assert results[0][0].name == "credit_assessment"

    @pytest.mark.asyncio
    async def test_locate_rules_not_found(self):
        """Test locating non-existent output element."""
        service = SimulationService()

        rule_groups = [
            make_rule_group("credit_assessment", outputs=["credit_score"]),
        ]

        all_steps = {
            "credit_assessment": [
                make_step("score_step", "Score Step", rule_group="credit_assessment"),
            ],
        }

        results = await service.locate_rules_for_output(
            output_element="nonexistent_output",
            rule_groups=rule_groups,
            all_steps=all_steps,
        )

        assert len(results) == 0


class TestBuildRuleTreeSimulation:
    """Test SimulationService.build_rule_tree_simulation()."""

    @pytest.mark.asyncio
    async def test_build_rule_tree_single_group(self):
        """Test building rule tree with single rule group."""
        service = SimulationService()

        rule_groups = [
            make_rule_group("test_rg", outputs=["score"]),
        ]

        all_steps = {
            "test_rg": [
                make_step(
                    "step_a",
                    "Step A",
                    then_op="test_compute_score",
                    then_params={"base": 100, "multiplier": 1},
                ),
            ],
        }

        result = await service.build_rule_tree_simulation(
            target_output="score",
            rule_groups=rule_groups,
            all_steps=all_steps,
            entity_data={},
        )

        assert result.simulation_type == "dag"
        assert result.rule_groups == ["test_rg"]
        assert len(result.steps) == 1
        assert result.final_output.get("score") == 100

    @pytest.mark.asyncio
    async def test_build_rule_tree_not_found(self):
        """Test building rule tree with non-existent target."""
        service = SimulationService()

        rule_groups = [
            make_rule_group("test_rg", outputs=["score"]),
        ]

        all_steps = {
            "test_rg": [
                make_step("step_a", "Step A"),
            ],
        }

        result = await service.build_rule_tree_simulation(
            target_output="nonexistent",
            rule_groups=rule_groups,
            all_steps=all_steps,
            entity_data={},
        )

        assert len(result.steps) == 0
        assert len(result.errors) == 1
        assert "No rule groups found" in result.errors[0]


class TestAgentInteractiveSimulation:
    """Test SimulationService.agent_interactive_simulation()."""

    @pytest.mark.asyncio
    async def test_agent_interactive_simulation(self):
        """Test agent interactive simulation with modified inputs."""
        service = SimulationService()

        # Create baseline result
        baseline_steps = [
            SimulationStep(
                step_id="step_a",
                step_name="Step A",
                output_values={"score": 50},
            ),
        ]
        baseline_result = DAGSimulationResult(
            simulation_id="baseline_123",
            simulation_type="dag",
            rule_groups=["test_rg"],
            steps=baseline_steps,
            final_output={"score": 50, "grade": "C", "final_decision": "REJECT"},
        )

        rule_groups = [
            make_rule_group("test_rg", outputs=["score", "grade", "decision"]),
        ]

        all_steps = {
            "test_rg": [
                make_step(
                    "step_a",
                    "Step A",
                    then_op="test_compute_score",
                    then_params={"base": 100, "multiplier": 1},
                ),
                make_step(
                    "step_b",
                    "Step B",
                    depends_on=["step_a"],
                    then_op="test_apply_grade",
                    then_params={},
                ),
                make_step(
                    "step_c",
                    "Step C",
                    depends_on=["step_b"],
                    then_op="test_decision",
                    then_params={},
                ),
            ],
        }

        modified_inputs = {"base_input": 80}

        result = await service.agent_interactive_simulation(
            baseline_result=baseline_result,
            modified_inputs=modified_inputs,
            rule_groups=rule_groups,
            all_steps=all_steps,
        )

        assert result.simulation_type == "agent_interactive"
        assert result.modified_inputs == modified_inputs
        assert result.baseline_output == baseline_result.final_output


class TestSimulationServiceTrackInputSources:
    """Test input source tracking."""

    def test_track_input_sources_expression(self):
        """Test tracking sources from expression variables."""
        service = SimulationService()

        condition = ConditionClause(type="expression", expression="credit_score > 50")

        sources = service._track_input_sources(
            condition=condition,
            entity_data={"credit_score": 75},
            computed={"previous_score": 70},
        )

        # Only variables in the expression are tracked
        assert sources.get("credit_score") == "entity_data"
        # previous_score is not in the expression, so it's not tracked
        assert "previous_score" not in sources

    def test_track_input_sources_all_of(self):
        """Test tracking sources from all_of conditions."""
        service = SimulationService()

        condition = ConditionClause(
            type="all_of",
            sub_conditions=["credit_score > 50", "risk_level < 3"],
        )

        sources = service._track_input_sources(
            condition=condition,
            entity_data={"credit_score": 75},
            computed={"risk_level": 2},
        )

        assert sources.get("credit_score") == "entity_data"
        assert sources.get("risk_level") == "computed_metrics"

    def test_track_input_sources_empty_condition(self):
        """Test tracking with no condition."""
        service = SimulationService()

        sources = service._track_input_sources(
            condition=None,
            entity_data={"credit_score": 75},
            computed={},
        )

        assert sources == {}


class TestSimulationServiceLegacyMethods:
    """Test legacy SimulationService methods still work."""

    @pytest.mark.asyncio
    async def test_simulate_rule_group_still_works(self):
        """Test that original simulate_rule_group method still works."""
        service = SimulationService()

        rule_group = make_rule_group("test_rg", outputs=["flag"])
        steps = [
            make_step(
                "step_a",
                "Step A",
                then_op="test_set_flag",
                then_params={"flag_name": "test_flag", "flag_value": True},
            )
        ]

        result = await service.simulate_rule_group(
            rule_group=rule_group,
            steps=steps,
            entity_data={},
        )

        assert result.rule_group_name == "test_rg"
        assert len(result.steps) == 1
        assert result.final_output.get("test_flag") is True

    def test_create_execution_context(self):
        """Test factory method for ExecutionContext."""
        context = SimulationService.create_execution_context(
            entity_id="E001",
            dimension="test",
            entity_data={"name": "Test"},
            computed_metrics={"score": 100},
        )

        assert context.entity_id == "E001"
        assert context.dimension == "test"
        assert context.entity_data == {"name": "Test"}
        assert context.computed_metrics == {"score": 100}

    def test_list_operator_schemas(self):
        """Test listing operator schemas."""
        schemas = SimulationService.list_operator_schemas()
        assert isinstance(schemas, list)

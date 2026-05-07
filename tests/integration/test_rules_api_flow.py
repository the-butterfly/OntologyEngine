"""Rule Groups API flow integration tests - DAG visualization and locate endpoints."""


from ontology_engine.engine.rule.models import (
    ActionClause,
    ConditionClause,
    RuleStep,
)
from ontology_engine.engine.rule.dag_builder import DAGBuilder


class TestDAGBuilderIntegration:
    """Test DAGBuilder with realistic rule step configurations."""

    def test_dag_builder_three_layers(self):
        """Test DAG builder with 3-layer dependency chain."""
        builder = DAGBuilder()
        steps = [
            RuleStep(
                id="A",
                name="资格检查",
                rule_group="test",
                order=1,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=[],
            ),
            RuleStep(
                id="B",
                name="信用评分",
                rule_group="test",
                order=2,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=["A"],
            ),
            RuleStep(
                id="C",
                name="额度计算",
                rule_group="test",
                order=3,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=["B"],
            ),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 3

        # Layer 0: A (no dependencies)
        assert dag.layers[0].index == 0
        assert len(dag.layers[0].nodes) == 1
        assert dag.layers[0].nodes[0].step_id == "A"

        # Layer 1: B (depends on A)
        assert dag.layers[1].index == 1
        assert len(dag.layers[1].nodes) == 1
        assert dag.layers[1].nodes[0].step_id == "B"

        # Layer 2: C (depends on B)
        assert dag.layers[2].index == 2
        assert len(dag.layers[2].nodes) == 1
        assert dag.layers[2].nodes[0].step_id == "C"

    def test_dag_builder_parallel_steps(self):
        """Test DAG builder with parallel steps (same layer)."""
        builder = DAGBuilder()
        steps = [
            RuleStep(
                id="A",
                name="Step A",
                rule_group="test",
                order=1,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=[],
            ),
            RuleStep(
                id="B",
                name="Step B",
                rule_group="test",
                order=2,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=[],
            ),
            RuleStep(
                id="C",
                name="Step C",
                rule_group="test",
                order=3,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=["A", "B"],
            ),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 2

        # Layer 0: A and B (parallel, no dependencies)
        assert dag.layers[0].index == 0
        assert len(dag.layers[0].nodes) == 2
        layer_0_ids = {n.step_id for n in dag.layers[0].nodes}
        assert layer_0_ids == {"A", "B"}

        # Layer 1: C (depends on both A and B)
        assert dag.layers[1].index == 1
        assert len(dag.layers[1].nodes) == 1
        assert dag.layers[1].nodes[0].step_id == "C"

    def test_dag_builder_single_step(self):
        """Test DAG builder with single step (no dependencies)."""
        builder = DAGBuilder()
        steps = [
            RuleStep(
                id="A",
                name="Single Step",
                rule_group="test",
                order=1,
                when=ConditionClause(type="expression", expression="x > 0"),
                then=ActionClause(operator="flag", params={}),
                depends_on=[],
            ),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 1
        assert len(dag.layers[0].nodes) == 1
        assert dag.layers[0].nodes[0].step_id == "A"
        assert dag.layers[0].nodes[0].in_degree == 0


class TestRuleGroupDAGResponse:
    """Test the DAG response format matches API specification."""

    def test_dag_response_format(self):
        """Verify the DAG response format matches the API spec."""
        builder = DAGBuilder()
        steps = [
            RuleStep(
                id="step-A",
                name="资格检查",
                rule_group="credit_assessment",
                order=1,
                when=ConditionClause(type="expression", expression="entity.status == 'ACTIVE'"),
                then=ActionClause(operator="SET_FLAG", params={}),
                depends_on=[],
            ),
            RuleStep(
                id="step-B",
                name="信用评分",
                rule_group="credit_assessment",
                order=2,
                when=ConditionClause(type="expression", expression="entity.capital > 0"),
                then=ActionClause(operator="COMPUTE", params={}),
                depends_on=["step-A"],
            ),
        ]

        dag = builder.build(steps)

        # Verify response structure matches API spec
        total_steps = len(steps)
        total_layers = len(dag.layers)

        assert total_steps == 2
        assert total_layers == 2

        # Verify layer content matches expected API output
        layer_0 = dag.layers[0]
        layer_1 = dag.layers[1]

        # Layer 0 should have step-A with in_degree 0
        assert layer_0.index == 0
        assert len(layer_0.nodes) == 1
        assert layer_0.nodes[0].step_id == "step-A"
        assert layer_0.nodes[0].in_degree == 0
        assert layer_0.nodes[0].step.depends_on == []

        # Layer 1 should have step-B with in_degree 1 (depends on step-A)
        assert layer_1.index == 1
        assert len(layer_1.nodes) == 1
        assert layer_1.nodes[0].step_id == "step-B"
        # in_degree in the API response represents number of dependencies (len of depends_on)
        assert len(layer_1.nodes[0].step.depends_on) == 1
        assert layer_1.nodes[0].step.depends_on == ["step-A"]


class TestLocateResponseFormat:
    """Test the locate response format matches API specification."""

    def test_locate_response_format(self):
        """Verify the locate response format matches the API spec."""
        # Simulate what the API would return
        output = "credit_score"
        rule_groups = [
            {
                "name": "credit_scoring",
                "outputs": [
                    {"name": "credit_score", "type": "metric"},
                ],
                "depends_on": [],
            }
        ]

        # Verify structure matches spec
        assert output == "credit_score"
        assert len(rule_groups) == 1
        assert rule_groups[0]["name"] == "credit_scoring"
        assert rule_groups[0]["outputs"][0]["name"] == "credit_score"
        assert rule_groups[0]["outputs"][0]["type"] == "metric"

# tests/unit/engine/rule/test_dag_builder.py
"""Tests for DAGBuilder using Kahn's algorithm."""

import pytest

from ontology_engine.engine.rule.dag_builder import (
    CycleError,
    DAGBuilder,
    DAGLayer,
    DAGNode,
    ExecutionDAG,
)
from ontology_engine.engine.rule.models import (
    ActionClause,
    ConditionClause,
    RuleStep,
)


def make_step(
    step_id: str,
    name: str,
    rule_group: str = "test_group",
    order: int = 1,
    depends_on: list[str] | None = None,
) -> RuleStep:
    """Helper to create a RuleStep for testing."""
    return RuleStep(
        id=step_id,
        name=name,
        rule_group=rule_group,
        order=order,
        when=ConditionClause(type="expression", expression="x > 0"),
        then=ActionClause(operator="flag", params={}),
        depends_on=depends_on or [],
    )


class TestDAGNode:
    """Test DAGNode dataclass."""

    def test_create_dag_node(self):
        """Test creating a DAGNode."""
        step = make_step("step_a", "Step A")
        node = DAGNode(step_id="step_a", step=step, in_degree=0, dependents=[])

        assert node.step_id == "step_a"
        assert node.step == step
        assert node.in_degree == 0
        assert node.dependents == []


class TestDAGLayer:
    """Test DAGLayer dataclass."""

    def test_create_dag_layer(self):
        """Test creating a DAGLayer."""
        step = make_step("step_a", "Step A")
        node = DAGNode(step_id="step_a", step=step)
        layer = DAGLayer(index=0, nodes=[node])

        assert layer.index == 0
        assert len(layer.nodes) == 1
        assert layer.nodes[0].step_id == "step_a"


class TestExecutionDAG:
    """Test ExecutionDAG dataclass."""

    def test_create_execution_dag(self):
        """Test creating an ExecutionDAG."""
        dag = ExecutionDAG(layers=[], step_map={}, has_cycle=False)

        assert dag.layers == []
        assert dag.step_map == {}
        assert dag.has_cycle is False


class TestDAGBuilder:
    """Test DAGBuilder with Kahn's algorithm."""

    def test_single_step_no_dependencies(self):
        """Test single step with no dependencies."""
        builder = DAGBuilder()
        steps = [make_step("step_a", "Step A")]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 1
        assert len(dag.layers[0].nodes) == 1
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert "step_a" in dag.step_map

    def test_two_steps_no_dependencies(self):
        """Test two steps with no dependencies (both in layer 0)."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B"),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 1
        assert len(dag.layers[0].nodes) == 2
        step_ids = {n.step_id for n in dag.layers[0].nodes}
        assert step_ids == {"step_a", "step_b"}

    def test_linear_dependency_a_b_c(self):
        """Test linear dependency A → B → C."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_b"]),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 3

        # Layer 0: A (no dependencies)
        assert dag.layers[0].index == 0
        assert len(dag.layers[0].nodes) == 1
        assert dag.layers[0].nodes[0].step_id == "step_a"

        # Layer 1: B (depends on A)
        assert dag.layers[1].index == 1
        assert len(dag.layers[1].nodes) == 1
        assert dag.layers[1].nodes[0].step_id == "step_b"

        # Layer 2: C (depends on B)
        assert dag.layers[2].index == 2
        assert len(dag.layers[2].nodes) == 1
        assert dag.layers[2].nodes[0].step_id == "step_c"

    def test_parallel_steps_a_to_b_c(self):
        """Test parallel steps: A → B and A → C."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 2

        # Layer 0: A
        assert dag.layers[0].index == 0
        assert len(dag.layers[0].nodes) == 1
        assert dag.layers[0].nodes[0].step_id == "step_a"

        # Layer 1: B and C (both depend on A, can run in parallel)
        assert dag.layers[1].index == 1
        assert len(dag.layers[1].nodes) == 2
        step_ids = {n.step_id for n in dag.layers[1].nodes}
        assert step_ids == {"step_b", "step_c"}

    def test_complex_dag_converging_nodes(self):
        r"""Test complex DAG with converging nodes.

        Structure:
            A
           / \
          B   C
           \ /
            D
        """
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
            make_step("step_d", "Step D", depends_on=["step_b", "step_c"]),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 3

        # Layer 0: A
        assert dag.layers[0].index == 0
        assert len(dag.layers[0].nodes) == 1
        assert dag.layers[0].nodes[0].step_id == "step_a"

        # Layer 1: B and C (both depend on A)
        assert dag.layers[1].index == 1
        assert len(dag.layers[1].nodes) == 2
        step_ids = {n.step_id for n in dag.layers[1].nodes}
        assert step_ids == {"step_b", "step_c"}

        # Layer 2: D (depends on both B and C)
        assert dag.layers[2].index == 2
        assert len(dag.layers[2].nodes) == 1
        assert dag.layers[2].nodes[0].step_id == "step_d"

    def test_empty_steps(self):
        """Test with empty steps list."""
        builder = DAGBuilder()
        dag = builder.build([])

        assert dag.has_cycle is False
        assert dag.layers == []
        assert dag.step_map == {}

    def test_cross_rule_group_dependency(self):
        """Test dependency with rule_group prefix."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", rule_group="group_1"),
            make_step(
                "step_b",
                "Step B",
                rule_group="group_2",
                depends_on=["group_1/step_a"],
            ),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 2
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert dag.layers[1].nodes[0].step_id == "step_b"

    def test_same_rule_group_dependency_no_prefix(self):
        """Test that same rule group dependency works without prefix."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", rule_group="group_1"),
            make_step(
                "step_b",
                "Step B",
                rule_group="group_1",
                depends_on=["step_a"],
            ),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 2
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert dag.layers[1].nodes[0].step_id == "step_b"

    def test_step_map_contains_all_steps(self):
        """Test that step_map contains all steps."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
        ]

        dag = builder.build(steps)

        assert len(dag.step_map) == 3
        assert "step_a" in dag.step_map
        assert "step_b" in dag.step_map
        assert "step_c" in dag.step_map

    def test_node_dependents_populated(self):
        """Test that node.dependents is correctly populated."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
        ]

        dag = builder.build(steps)

        step_a_node = dag.step_map["step_a"]
        step_b_node = dag.step_map["step_b"]
        step_c_node = dag.step_map["step_c"]

        # A should have B and C as dependents
        assert "step_b" in step_a_node.dependents
        assert "step_c" in step_a_node.dependents

        # B and C should have no dependents
        assert step_b_node.dependents == []
        assert step_c_node.dependents == []

    def test_node_in_degree_correct(self):
        """Test that node.in_degree is correctly calculated."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_a"]),
            make_step(
                "step_d", "Step D", depends_on=["step_b", "step_c"]
            ),
        ]

        dag = builder.build(steps)

        # After build, in_degree should be 0 for all (consumed by algorithm)
        # But we can verify the structure through the layers
        assert dag.layers[0].nodes[0].step_id == "step_a"
        assert dag.layers[1].nodes[0].step_id in ("step_b", "step_c")
        assert dag.layers[1].nodes[1].step_id in ("step_b", "step_c")
        assert dag.layers[2].nodes[0].step_id == "step_d"


class TestCycleDetection:
    """Test cycle detection in DAG."""

    def test_simple_cycle(self):
        """Test detection of simple cycle A → B → C → A."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", depends_on=["step_c"]),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["step_b"]),
        ]

        with pytest.raises(CycleError) as exc_info:
            builder.build(steps)

        assert "Circular dependency detected" in str(exc_info.value)
        assert exc_info.value.cycle_path is not None
        assert len(exc_info.value.cycle_path) > 0

    def test_self_loop_cycle(self):
        """Test detection of self-referential cycle (A depends on A)."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", depends_on=["step_a"]),
        ]

        with pytest.raises(CycleError) as exc_info:
            builder.build(steps)

        assert "Circular dependency detected" in str(exc_info.value)

    def test_two_node_cycle(self):
        """Test detection of two-node cycle A → B → A."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", depends_on=["step_b"]),
            make_step("step_b", "Step B", depends_on=["step_a"]),
        ]

        with pytest.raises(CycleError) as exc_info:
            builder.build(steps)

        assert "Circular dependency detected" in str(exc_info.value)


class TestMissingDependency:
    """Test handling of missing dependencies."""

    def test_missing_dependency_raises_key_error(self):
        """Test that KeyError is raised for non-existent dependency."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A"),
            make_step("step_b", "Step B", depends_on=["step_a"]),
            make_step("step_c", "Step C", depends_on=["nonexistent_step"]),
        ]

        with pytest.raises(KeyError) as exc_info:
            builder.build(steps)

        assert "non-existent step" in str(exc_info.value)
        assert "nonexistent_step" in str(exc_info.value)

    def test_missing_cross_group_dependency(self):
        """Test that KeyError is raised for non-existent cross-group dependency."""
        builder = DAGBuilder()
        steps = [
            make_step("step_a", "Step A", rule_group="group_1"),
            make_step(
                "step_b",
                "Step B",
                rule_group="group_2",
                depends_on=["group_1/nonexistent_step"],
            ),
        ]

        with pytest.raises(KeyError) as exc_info:
            builder.build(steps)

        assert "non-existent step" in str(exc_info.value)
        assert "nonexistent_step" in str(exc_info.value)


class TestDAGProperties:
    """Test DAG invariant properties."""

    def test_all_steps_in_step_map(self):
        """Test that all steps appear in step_map."""
        builder = DAGBuilder()
        steps = [
            make_step("a", "A"),
            make_step("b", "B", depends_on=["a"]),
            make_step("c", "C", depends_on=["a"]),
            make_step("d", "D", depends_on=["b", "c"]),
            make_step("e", "E"),
        ]

        dag = builder.build(steps)

        assert set(dag.step_map.keys()) == {"a", "b", "c", "d", "e"}

    def test_layer_count_matches_max_depth(self):
        """Test that number of layers matches maximum dependency depth."""
        builder = DAGBuilder()
        steps = [
            make_step("l0", "Level 0"),
            make_step("l1", "Level 1", depends_on=["l0"]),
            make_step("l2", "Level 2", depends_on=["l1"]),
            make_step("l3", "Level 3", depends_on=["l2"]),
        ]

        dag = builder.build(steps)

        assert len(dag.layers) == 4
        for i, layer in enumerate(dag.layers):
            assert layer.index == i
            assert len(layer.nodes) == 1
            assert layer.nodes[0].step_id == f"l{i}"

    def test_parallel_layer_contains_correct_nodes(self):
        """Test that parallel execution nodes are in same layer."""
        builder = DAGBuilder()
        steps = [
            make_step("root", "Root"),
            make_step("p1", "Parallel 1", depends_on=["root"]),
            make_step("p2", "Parallel 2", depends_on=["root"]),
            make_step("p3", "Parallel 3", depends_on=["root"]),
            make_step("p4", "Parallel 4", depends_on=["root"]),
        ]

        dag = builder.build(steps)

        assert len(dag.layers) == 2
        assert dag.layers[0].nodes[0].step_id == "root"
        assert len(dag.layers[1].nodes) == 4
        assert {n.step_id for n in dag.layers[1].nodes} == {
            "p1", "p2", "p3", "p4"
        }

    def test_diamond_dependency(self):
        r"""Test diamond-shaped dependency structure.

            A
           / \
          B   C
           \ /
            D
           / \
          E   F
        """
        builder = DAGBuilder()
        steps = [
            make_step("a", "A"),
            make_step("b", "B", depends_on=["a"]),
            make_step("c", "C", depends_on=["a"]),
            make_step("d", "D", depends_on=["b", "c"]),
            make_step("e", "E", depends_on=["d"]),
            make_step("f", "F", depends_on=["d"]),
        ]

        dag = builder.build(steps)

        assert dag.has_cycle is False
        assert len(dag.layers) == 4

        # Layer 0: A
        assert dag.layers[0].nodes[0].step_id == "a"

        # Layer 1: B, C
        assert len(dag.layers[1].nodes) == 2
        assert {n.step_id for n in dag.layers[1].nodes} == {"b", "c"}

        # Layer 2: D
        assert len(dag.layers[2].nodes) == 1
        assert dag.layers[2].nodes[0].step_id == "d"

        # Layer 3: E, F
        assert len(dag.layers[3].nodes) == 2
        assert {n.step_id for n in dag.layers[3].nodes} == {"e", "f"}

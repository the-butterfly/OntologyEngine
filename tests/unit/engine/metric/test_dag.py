# tests/unit/engine/metric/test_dag.py
"""Tests for MetricDAG."""

import pytest
from ontology_engine.core.schema.models import MetricDefinition
from ontology_engine.engine.metric.dag import MetricDAG
from ontology_engine.engine.metric.errors import MetricDAGError


class TestMetricDAG:
    """Test MetricDAG construction and operations."""

    def test_empty_dag(self):
        """Test DAG with no metrics."""
        dag = MetricDAG([])
        assert len(dag.metrics) == 0
        assert len(dag.graph.nodes) == 0

    def test_single_metric_no_deps(self):
        """Test DAG with single metric and no dependencies."""
        metrics = [
            MetricDefinition(name="total_invoice_amount_90d", type="atomic")
        ]
        dag = MetricDAG(metrics)
        assert dag.metrics == {"total_invoice_amount_90d": metrics[0]}
        assert list(dag.graph.nodes) == ["total_invoice_amount_90d"]

    def test_metric_with_dependencies(self):
        """Test DAG with metric dependencies."""
        metrics = [
            MetricDefinition(name="total_invoice_amount_90d", type="atomic"),
            MetricDefinition(name="overdue_invoice_amount", type="atomic"),
            MetricDefinition(
                name="overdue_invoice_ratio",
                type="derived",
                dependencies=["overdue_invoice_amount", "total_invoice_amount_90d"]
            ),
        ]
        dag = MetricDAG(metrics)

        # Check edges: dependency -> dependent
        assert "total_invoice_amount_90d" in dag.graph.nodes
        assert "overdue_invoice_amount" in dag.graph.nodes
        assert "overdue_invoice_ratio" in dag.graph.nodes

        # overdue_invoice_ratio should have edges from its deps
        assert "overdue_invoice_ratio" in dag.graph["total_invoice_amount_90d"]
        assert "overdue_invoice_ratio" in dag.graph["overdue_invoice_amount"]

    def test_circular_dependency_detection(self):
        """Test that circular dependencies raise error."""
        metrics = [
            MetricDefinition(
                name="metric_a",
                dependencies=["metric_b"]
            ),
            MetricDefinition(
                name="metric_b",
                dependencies=["metric_a"]
            ),
        ]
        with pytest.raises(MetricDAGError) as exc_info:
            MetricDAG(metrics)
        assert "cycles" in str(exc_info.value).lower()

    def test_topological_order_no_deps(self):
        """Test topological order with no dependencies."""
        metrics = [
            MetricDefinition(name="a", type="atomic"),
            MetricDefinition(name="b", type="atomic"),
            MetricDefinition(name="c", type="atomic"),
        ]
        dag = MetricDAG(metrics)
        order = dag.topological_order()
        # All should be present
        assert set(order) == {"a", "b", "c"}

    def test_topological_order_with_deps(self):
        """Test topological order respects dependencies."""
        metrics = [
            MetricDefinition(name="total_invoice_amount_90d", type="atomic"),
            MetricDefinition(name="overdue_invoice_amount", type="atomic"),
            MetricDefinition(
                name="overdue_invoice_ratio",
                type="derived",
                dependencies=["overdue_invoice_amount", "total_invoice_amount_90d"]
            ),
        ]
        dag = MetricDAG(metrics)
        order = dag.topological_order(["overdue_invoice_ratio"])

        # Dependencies should come before the dependent
        dep_idx = order.index("overdue_invoice_ratio")
        assert order.index("total_invoice_amount_90d") < dep_idx
        assert order.index("overdue_invoice_amount") < dep_idx

    def test_get_dependencies(self):
        """Test getting direct dependencies."""
        metrics = [
            MetricDefinition(name="a", dependencies=["b", "c"]),
            MetricDefinition(name="b", type="atomic"),
            MetricDefinition(name="c", type="atomic"),
        ]
        dag = MetricDAG(metrics)
        deps = dag.get_dependencies("a")
        assert deps == {"b", "c"}

    def test_get_all_dependencies(self):
        """Test getting transitive dependencies."""
        metrics = [
            MetricDefinition(name="a", dependencies=["b"]),
            MetricDefinition(name="b", dependencies=["c"]),
            MetricDefinition(name="c", type="atomic"),
        ]
        dag = MetricDAG(metrics)
        all_deps = dag.get_all_dependencies("a")
        assert all_deps == {"b", "c"}

    def test_get_dependents(self):
        """Test getting metrics that depend on a given metric."""
        metrics = [
            MetricDefinition(name="a", type="atomic"),
            MetricDefinition(name="b", dependencies=["a"]),
            MetricDefinition(name="c", dependencies=["a"]),
        ]
        dag = MetricDAG(metrics)
        dependents = dag.get_dependents("a")
        assert dependents == {"b", "c"}

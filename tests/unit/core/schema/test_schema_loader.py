"""Tests for SchemaLoader v2 enhancements."""

from ontology_engine.core.schema.loader import SchemaLoader


class TestCompositeDependencyDerivation:
    """Verify composite metrics auto-derive dependencies from components."""

    def test_composite_dependencies_auto_derived(self):
        loader = SchemaLoader()
        schema = loader.load("examples/supply_chain_finance/schema.yaml")
        assert schema.analytical_elements is not None

        credit_score = next(
            (m for m in schema.analytical_elements.metrics if m.id == "credit_score"),
            None,
        )
        assert credit_score is not None
        expected = [
            "business_stability_score",
            "tax_compliance_score",
            "reputation_score",
            "guarantee_chain_depth",
            "core_enterprise_count",
        ]
        assert credit_score.dependencies == expected

    def test_composite_dependencies_consumer_credit(self):
        loader = SchemaLoader()
        schema = loader.load("examples/consumer_credit/schema.yaml")
        assert schema.analytical_elements is not None

        credit_risk_score = next(
            (m for m in schema.analytical_elements.metrics if m.id == "credit_risk_score"),
            None,
        )
        assert credit_risk_score is not None
        expected = [
            "debt_to_income_ratio",
            "credit_bureau_score",
            "repayment_rate_24m",
            "online_behavior_score",
            "network_risk_score",
        ]
        assert credit_risk_score.dependencies == expected


class TestGraphAlgorithmStructuring:
    """Verify graph metrics parse structured algorithm definitions."""

    def test_structured_algorithm_parsed(self):
        loader = SchemaLoader()
        schema = loader.load("examples/supply_chain_finance/schema.yaml")
        assert schema.analytical_elements is not None

        depth_metric = next(
            (m for m in schema.analytical_elements.metrics if m.id == "guarantee_chain_depth"),
            None,
        )
        assert depth_metric is not None
        algo = depth_metric.algorithm
        assert algo is not None
        assert algo.name == "longest_path"
        assert algo.params["direction"] == "both"
        assert algo.params["max_hops"] == 10
        assert algo.params["weighted"] is False

    def test_neighbor_attribute_count_parsed(self):
        loader = SchemaLoader()
        schema = loader.load("examples/consumer_credit/schema.yaml")
        assert schema.analytical_elements is not None

        risk_count = next(
            (m for m in schema.analytical_elements.metrics if m.id == "co_borrower_risk_count"),
            None,
        )
        assert risk_count is not None
        algo = risk_count.algorithm
        assert algo is not None
        assert algo.name == "neighbor_attribute_count"
        assert algo.params["deduplicate_neighbors"] is True
        assert algo.params["max_hops"] == 2

    def test_backward_compatible_string_algorithm(self):
        from ontology_engine.core.schema.models import MetricDefinitionV2

        metric = MetricDefinitionV2(
            id="test_metric",
            type="graph",
            algorithm="longest_path",
        )
        assert metric.algorithm is not None
        assert metric.algorithm.name == "longest_path"
        assert metric.algorithm.params == {}

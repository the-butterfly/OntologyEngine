# tests/unit/services/test_simulation_tree_builder.py
"""Tests for SimulationTreeBuilder - cross-rule-group execution tree builder."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder
from ontology_engine.engine.rule.models import (
    RuleGroupDefinition,
    RuleStep,
    IOElement,
    AppliesToConfig,
    ConditionClause,
    ActionClause,
)


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


class TestRuleTreeBuilder:
    """Test RuleTreeBuilder for cross-rule-group execution tree building."""

    @pytest.fixture
    def tree_builder(self):
        """Create a RuleTreeBuilder instance."""
        return RuleTreeBuilder()

    @pytest.mark.asyncio
    async def test_locate_rule_groups_by_output(self, tree_builder):
        """Test locating rule groups by output name."""
        # Mock the rule service
        mock_rule_service = AsyncMock()
        mock_rule_groups = [
            make_rule_group("decision_maker", outputs=["decision", "reasoning"]),
            make_rule_group("score_calculator", outputs=["score", "grade"]),
        ]
        mock_rule_service.locate_rule_groups = AsyncMock(return_value=mock_rule_groups)
        tree_builder._rule_service = mock_rule_service

        result = await tree_builder._locate_by_output("decision", "schema_001")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].name == "decision_maker"
        mock_rule_service.locate_rule_groups.assert_called_once_with("decision", "schema_001")

    @pytest.mark.asyncio
    async def test_locate_rule_groups_not_found(self, tree_builder):
        """Test locating rule groups when none exist for output."""
        mock_rule_service = AsyncMock()
        mock_rule_service.locate_rule_groups = AsyncMock(return_value=[])
        tree_builder._rule_service = mock_rule_service

        result = await tree_builder._locate_by_output("nonexistent", "schema_001")

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_build_execution_tree_empty(self, tree_builder):
        """Test building execution tree with no matching rule groups."""
        mock_rule_service = AsyncMock()
        mock_rule_service.locate_rule_groups = AsyncMock(return_value=[])
        tree_builder._rule_service = mock_rule_service

        result = await tree_builder.build_tree(
            schema_id="schema_001",
            entity_id="entity_001",
            target_output="decision",
        )

        assert "layers" in result
        assert len(result["layers"]) == 0
        assert result["total_steps"] == 0
        assert result["rule_group_count"] == 0

    @pytest.mark.asyncio
    async def test_build_execution_tree_single_layer(self, tree_builder):
        """Test building execution tree with single rule group."""
        mock_rule_service = AsyncMock()
        mock_rule_groups = [
            make_rule_group("decision_maker", outputs=["decision"]),
        ]
        mock_rule_service.locate_rule_groups = AsyncMock(return_value=mock_rule_groups)
        tree_builder._rule_service = mock_rule_service

        # Mock _filter_steps to return empty for simplicity
        tree_builder._filter_steps = AsyncMock(return_value=[])

        result = await tree_builder.build_tree(
            schema_id="schema_001",
            entity_id="entity_001",
            target_output="decision",
        )

        assert "layers" in result
        assert result["schema_id"] == "schema_001"
        assert result["target_output"] == "decision"
        assert "total_steps" in result
        assert "rule_group_count" in result

    @pytest.mark.asyncio
    async def test_build_execution_tree_returns_dict(self, tree_builder):
        """Test that build_tree returns a proper dict structure."""
        mock_rule_service = AsyncMock()
        mock_rule_service.locate_rule_groups = AsyncMock(return_value=[])
        tree_builder._rule_service = mock_rule_service

        result = await tree_builder.build_tree(
            schema_id="schema_001",
            entity_id="entity_001",
            target_output="decision",
        )

        # Verify structure
        assert isinstance(result, dict)
        assert "schema_id" in result
        assert "target_output" in result
        assert "layers" in result
        assert "total_steps" in result
        assert "rule_group_count" in result


class TestRuleTreeBuilderInit:
    """Test RuleTreeBuilder initialization."""

    def test_init_without_rule_service(self):
        """Test initialization without rule service."""
        builder = RuleTreeBuilder()
        assert builder._rule_service is None

    def test_init_with_rule_service(self):
        """Test initialization with rule service."""
        mock_service = MagicMock()
        builder = RuleTreeBuilder(rule_service=mock_service)
        assert builder._rule_service is mock_service
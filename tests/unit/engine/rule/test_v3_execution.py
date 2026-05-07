# tests/unit/engine/rule/test_v3_execution.py
"""Tests for V3 execution methods (RFC-018 Phase C / RFC-019 Phase C)."""

import pytest

from ontology_engine.core.schema.models import ActionType
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    StructuredActionClause,
    StepDecl,
    RuleDefinitionDecl,
    RuleLogicDecl,
    ConditionClause,
)
from ontology_engine.engine.rule.executor import RuleExecutor
from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata


def _make_context() -> ExecutionContext:
    return ExecutionContext(
        entity_id="SUP_001",
        dimension="credit_assessment",
        entity_data={
            "income": 500000,
            "debt": 100000,
            "registered_capital": {"value": 10000000},
        },
        computed_metrics={},
        rule_results=[],
        alerts=[],
        flags={},
        categories={},
    )


def _make_executor() -> RuleExecutor:
    schema = KGMLSchema(metadata=SchemaMetadata(id="test", name="test"))
    return RuleExecutor(schema=schema)


class TestExecuteV3SetFlag:
    @pytest.mark.asyncio
    async def test_set_flag_true(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Approve",
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="eligible", value=True),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert len(result.rule_results) == 1
        assert result.rule_results[0].passed is True
        assert result.computed_metrics.get("eligible") is True

    @pytest.mark.asyncio
    async def test_set_flag_false(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Reject eligibility",
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="eligible", value=False),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.computed_metrics.get("eligible") is False


class TestExecuteV3Reject:
    @pytest.mark.asyncio
    async def test_reject_with_reason(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Reject",
                    action=StructuredActionClause(type=ActionType.REJECT, reason="Credit score too low"),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.rule_results[0].output.get("_rejected") is True
        assert result.rule_results[0].output.get("reason") == "Credit score too low"
        assert result.computed_metrics.get("rejected") is True

    @pytest.mark.asyncio
    async def test_reject_early_termination(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Reject",
                    action=StructuredActionClause(type=ActionType.REJECT, reason="Fail"),
                ),
                StepDecl(
                    id="S2",
                    name="Should not execute",
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="reached", value=True),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert len(result.rule_results) == 1
        assert "reached" not in result.computed_metrics


class TestExecuteV3EmitAlert:
    @pytest.mark.asyncio
    async def test_emit_alert(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Alert",
                    action=StructuredActionClause(
                        type=ActionType.EMIT_ALERT,
                        severity="CRITICAL",
                        reason="Guarantee chain too deep",
                    ),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert len(result.alerts) == 1
        assert result.alerts[0].level == "CRITICAL"
        assert result.alerts[0].message == "Guarantee chain too deep"


class TestExecuteV3AssignCategory:
    @pytest.mark.asyncio
    async def test_assign_category(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Categorize",
                    action=StructuredActionClause(type=ActionType.ASSIGN_CATEGORY, category="HIGH_RISK"),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.computed_metrics.get("assigned_category") == "HIGH_RISK"


class TestExecuteV3Compute:
    @pytest.mark.asyncio
    async def test_compute_with_formula(self):
        executor = _make_executor()
        context = _make_context()
        context.computed_metrics["income"] = 500000
        context.computed_metrics["debt"] = 100000

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Compute ratio",
                    action=StructuredActionClause(
                        type=ActionType.COMPUTE,
                        output="debt_ratio",
                        formula="debt / income",
                    ),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert "debt_ratio" in result.computed_metrics


class TestExecuteV3Condition:
    @pytest.mark.asyncio
    async def test_condition_true(self):
        executor = _make_executor()
        context = _make_context()
        context.computed_metrics["credit_score"] = 75

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Check score",
                    condition=ConditionClause(type="expression", expression="credit_score >= 60"),
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="eligible", value=True),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.computed_metrics.get("eligible") is True

    @pytest.mark.asyncio
    async def test_condition_false_with_else(self):
        executor = _make_executor()
        context = _make_context()
        context.computed_metrics["credit_score"] = 40

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Check score",
                    condition=ConditionClause(type="expression", expression="credit_score >= 60"),
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="eligible", value=True),
                    else_action=StructuredActionClause(type=ActionType.REJECT, reason="Score too low"),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.rule_results[0].passed is False
        assert result.rule_results[0].output.get("_rejected") is True

    @pytest.mark.asyncio
    async def test_no_condition_always_true(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Always execute",
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="processed", value=True),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.computed_metrics.get("processed") is True


class TestExecuteV3DisabledStep:
    @pytest.mark.asyncio
    async def test_disabled_step_skipped(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Disabled",
                    enabled=False,
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="should_not_set", value=True),
                ),
                StepDecl(
                    id="S2",
                    name="Enabled",
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="should_set", value=True),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert "should_not_set" not in result.computed_metrics
        assert result.computed_metrics.get("should_set") is True


class TestExecuteV3Priority:
    @pytest.mark.asyncio
    async def test_higher_priority_first(self):
        executor = _make_executor()
        context = _make_context()

        definition = RuleDefinitionDecl(name="R001")
        logic = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    name="Low priority",
                    priority=50,
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="low", value=True),
                ),
                StepDecl(
                    id="S2",
                    name="High priority",
                    priority=200,
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="high", value=True),
                ),
            ],
        )

        result = await executor.execute_v3(definition, logic, context)
        assert result.computed_metrics.get("high") is True
        assert result.computed_metrics.get("low") is True

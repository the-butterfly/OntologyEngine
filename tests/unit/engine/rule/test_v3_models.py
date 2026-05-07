# tests/unit/engine/rule/test_v3_models.py
"""Tests for V3 rule models (RFC-018 / RFC-019)."""


from ontology_engine.core.schema.models import (
    ActionType,
    OperatorType,
    StepAction,
    StepCondition,
    AppliesToDecl,
    PreconditionDecl,
    IOElementDecl,
    ApplicabilityDecl,
    StepDeclaration,
    RuleDefinitionDeclaration,
    RuleLogicDeclaration,
    BusinessLogicV3,
)
from ontology_engine.engine.rule.models import (
    StructuredActionClause,
    StepDecl,
    RuleDefinitionDecl,
    RuleLogicDecl,
)


class TestActionType:
    def test_five_action_types(self):
        assert len(ActionType) == 5
        assert ActionType.SET_FLAG.value == "set_flag"
        assert ActionType.COMPUTE.value == "compute"
        assert ActionType.REJECT.value == "reject"
        assert ActionType.EMIT_ALERT.value == "emit_alert"
        assert ActionType.ASSIGN_CATEGORY.value == "assign_category"

    def test_action_type_is_string_enum(self):
        assert isinstance(ActionType.SET_FLAG, str)
        assert ActionType.SET_FLAG == "set_flag"


class TestOperatorType:
    def test_six_operator_types(self):
        assert len(OperatorType) == 6
        assert OperatorType.GRAPH.value == "GRAPH"
        assert OperatorType.BINNING.value == "BINNING"
        assert OperatorType.SWITCH.value == "SWITCH"
        assert OperatorType.SCORECARD.value == "SCORECARD"
        assert OperatorType.WEIGHTED_SUM.value == "WEIGHTED_SUM"
        assert OperatorType.FORMULA.value == "FORMULA"


class TestStepAction:
    def test_set_flag_action(self):
        action = StepAction(type=ActionType.SET_FLAG, flag="eligible", value=True)
        assert action.type == ActionType.SET_FLAG
        assert action.flag == "eligible"
        assert action.value is True

    def test_compute_action(self):
        action = StepAction(
            type=ActionType.COMPUTE,
            output="credit_score",
            operator=OperatorType.FORMULA,
            formula="income / debt",
        )
        assert action.type == ActionType.COMPUTE
        assert action.operator == OperatorType.FORMULA

    def test_reject_action(self):
        action = StepAction(type=ActionType.REJECT, reason="Credit score too low")
        assert action.type == ActionType.REJECT
        assert action.reason == "Credit score too low"

    def test_emit_alert_action(self):
        action = StepAction(
            type=ActionType.EMIT_ALERT,
            severity="WARNING",
            reason="Guarantee chain depth exceeds threshold",
        )
        assert action.type == ActionType.EMIT_ALERT
        assert action.severity == "WARNING"

    def test_assign_category_action(self):
        action = StepAction(type=ActionType.ASSIGN_CATEGORY, category="HIGH_RISK")
        assert action.type == ActionType.ASSIGN_CATEGORY
        assert action.category == "HIGH_RISK"

    def test_compute_with_graph_operator(self):
        action = StepAction(
            type=ActionType.COMPUTE,
            output="guarantee_exposure",
            operator=OperatorType.GRAPH,
            query={"type": "traversal", "relation": "GUARANTEE_FOR", "depth": 3},
            aggregation=[{"type": "sum", "field": "amount", "output": "total"}],
        )
        assert action.operator == OperatorType.GRAPH
        assert action.query is not None
        assert action.aggregation is not None

    def test_compute_with_binning_operator(self):
        action = StepAction(
            type=ActionType.COMPUTE,
            output="risk_grade",
            operator=OperatorType.BINNING,
            bins=[{"range": [0, 40], "result": "D"}, {"range": [40, 60], "result": "C"}],
        )
        assert action.operator == OperatorType.BINNING
        assert len(action.bins) == 2


class TestStepCondition:
    def test_expression_condition(self):
        cond = StepCondition(expression="credit_score >= 60")
        assert cond.expression == "credit_score >= 60"

    def test_and_condition(self):
        cond = StepCondition(**{"and": ["credit_score >= 60", "debt_ratio < 0.5"]})
        assert len(cond.and_) == 2

    def test_or_condition(self):
        cond = StepCondition(**{"or": ["industry == MANUFACTURING", "industry == RETAIL"]})
        assert len(cond.or_) == 2


class TestRuleDefinitionDeclaration:
    def test_minimal_definition(self):
        rd = RuleDefinitionDeclaration(name="R001")
        assert rd.name == "R001"
        assert rd.type == "constraint"
        assert rd.priority == 100
        assert rd.enabled is True

    def test_full_definition(self):
        rd = RuleDefinitionDeclaration(
            name="R001",
            description="Credit eligibility rule",
            type="decision",
            priority=200,
            applies_to=AppliesToDecl(
                fact_objects=["Supplier"],
                categories={"industry": ["MANUFACTURING", "RETAIL"]},
            ),
            preconditions=[PreconditionDecl(expression="credit_score > 0")],
            inputs=[IOElementDecl(name="credit_score", type="integer", metric="credit_score")],
            outputs=[IOElementDecl(name="eligible", type="boolean")],
            overrides="credit_score_formula",
            applicability=ApplicabilityDecl(
                when_text="评估交易对手信用风险时",
                why_text="监管要求定期评级",
            ),
        )
        assert rd.applies_to.fact_objects == ["Supplier"]
        assert rd.applies_to.categories["industry"] == ["MANUFACTURING", "RETAIL"]
        assert len(rd.preconditions) == 1
        assert rd.inputs[0].metric == "credit_score"
        assert rd.applicability.when_text == "评估交易对手信用风险时"


class TestRuleLogicDeclaration:
    def test_minimal_logic(self):
        rl = RuleLogicDeclaration(name="R001_logic", definition_ref="R001")
        assert rl.name == "R001_logic"
        assert rl.definition_ref == "R001"
        assert rl.type == "decision_table"
        assert rl.steps == []

    def test_logic_with_steps(self):
        rl = RuleLogicDeclaration(
            name="R001_logic",
            definition_ref="R001",
            type="decision_table",
            steps=[
                StepDeclaration(
                    id="S1",
                    name="Check credit score",
                    condition=StepCondition(expression="credit_score >= 60"),
                    action=StepAction(type=ActionType.SET_FLAG, flag="eligible", value=True),
                ),
                StepDeclaration(
                    id="S2",
                    name="Reject if low score",
                    depends_on=["S1"],
                    condition=StepCondition(expression="credit_score < 60"),
                    action=StepAction(type=ActionType.REJECT, reason="Credit score too low"),
                ),
            ],
        )
        assert len(rl.steps) == 2
        assert rl.steps[0].action.type == ActionType.SET_FLAG
        assert rl.steps[1].depends_on == ["S1"]


class TestBusinessLogicV3:
    def test_empty_container(self):
        bl = BusinessLogicV3()
        assert bl.rule_definitions == []
        assert bl.rule_logics == []

    def test_full_container(self):
        bl = BusinessLogicV3(
            rule_definitions=[
                RuleDefinitionDeclaration(name="R001", type="decision"),
            ],
            rule_logics=[
                RuleLogicDeclaration(name="R001_logic", definition_ref="R001"),
            ],
        )
        assert len(bl.rule_definitions) == 1
        assert len(bl.rule_logics) == 1
        assert bl.rule_logics[0].definition_ref == "R001"


class TestStructuredActionClause:
    def test_from_legacy_approve(self):
        action = StructuredActionClause.from_legacy("approve_eligibility")
        assert action is not None
        assert action.type == ActionType.SET_FLAG
        assert action.flag == "eligible"
        assert action.value is True

    def test_from_legacy_reject_eligibility(self):
        action = StructuredActionClause.from_legacy(
            "reject_eligibility",
            output={"rejection_reason": "Low score"},
        )
        assert action is not None
        assert action.type == ActionType.SET_FLAG
        assert action.flag == "eligible"
        assert action.value is False
        assert action.reason == "Low score"

    def test_from_legacy_trigger_alert(self):
        action = StructuredActionClause.from_legacy(
            "trigger_alert",
            output={"alert_level": "CRITICAL", "message": "Chain too deep"},
        )
        assert action is not None
        assert action.type == ActionType.EMIT_ALERT
        assert action.severity == "CRITICAL"
        assert action.reason == "Chain too deep"

    def test_from_legacy_compute(self):
        action = StructuredActionClause.from_legacy(
            "calculate_credit_score",
            computation={"formula": "income * 0.3"},
        )
        assert action is not None
        assert action.type == ActionType.COMPUTE

    def test_from_legacy_none(self):
        action = StructuredActionClause.from_legacy(None)
        assert action is None

    def test_to_dict(self):
        action = StructuredActionClause(
            type=ActionType.SET_FLAG,
            flag="eligible",
            value=True,
        )
        d = action.to_dict()
        assert d["type"] == "set_flag"
        assert d["flag"] == "eligible"
        assert d["value"] is True

    def test_to_dict_compute(self):
        action = StructuredActionClause(
            type=ActionType.COMPUTE,
            output="credit_score",
            operator=OperatorType.FORMULA,
            formula="income / debt",
        )
        d = action.to_dict()
        assert d["type"] == "compute"
        assert d["operator"] == "FORMULA"
        assert d["formula"] == "income / debt"


class TestRuleDefinitionDecl:
    def test_minimal(self):
        rd = RuleDefinitionDecl(name="R001")
        assert rd.name == "R001"
        assert rd.type == "constraint"

    def test_to_dict(self):
        rd = RuleDefinitionDecl(name="R001", type="decision", priority=200)
        d = rd.to_dict()
        assert d["name"] == "R001"
        assert d["type"] == "decision"
        assert d["priority"] == 200


class TestRuleLogicDecl:
    def test_minimal(self):
        rl = RuleLogicDecl(name="R001_logic", definition_ref="R001")
        assert rl.name == "R001_logic"
        assert rl.definition_ref == "R001"

    def test_to_dict(self):
        rl = RuleLogicDecl(
            name="R001_logic",
            definition_ref="R001",
            steps=[
                StepDecl(
                    id="S1",
                    action=StructuredActionClause(type=ActionType.SET_FLAG, flag="eligible", value=True),
                ),
            ],
        )
        d = rl.to_dict()
        assert d["name"] == "R001_logic"
        assert d["definition_ref"] == "R001"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["action"]["type"] == "set_flag"

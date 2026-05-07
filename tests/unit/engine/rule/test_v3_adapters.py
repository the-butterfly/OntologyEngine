# tests/unit/engine/rule/test_v3_adapters.py
"""Tests for V3 model adapters (RFC-018 Phase B / RFC-019 Phase B)."""


from ontology_engine.core.schema.models import (
    ActionType,
    OperatorType,
    RuleDefinitionDeclaration,
    RuleLogicDeclaration,
    BusinessLogicV3,
    RuleDefinitionV2,
    RuleLogic,
    RuleWhen,
    RuleStep as SchemaRuleStep,
    BusinessLogic,
    _infer_action_type,
)
from ontology_engine.engine.rule.models import (
    StructuredActionClause,
    RuleDefinitionDecl,
    RuleLogicDecl,
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
    ConditionClause,
    AppliesToConfig,
    IOElement,
)


class TestInferActionType:
    def test_set_flag(self):
        assert _infer_action_type("set_flag") == ActionType.SET_FLAG

    def test_approve_eligibility(self):
        assert _infer_action_type("approve_eligibility") == ActionType.SET_FLAG

    def test_reject_eligibility(self):
        assert _infer_action_type("reject_eligibility") == ActionType.SET_FLAG

    def test_reject(self):
        assert _infer_action_type("reject") == ActionType.REJECT

    def test_trigger_alert(self):
        assert _infer_action_type("trigger_alert") == ActionType.EMIT_ALERT

    def test_alert(self):
        assert _infer_action_type("alert") == ActionType.EMIT_ALERT

    def test_assign_category(self):
        assert _infer_action_type("assign_category") == ActionType.ASSIGN_CATEGORY

    def test_compute_default(self):
        assert _infer_action_type("calculate_credit_score") == ActionType.COMPUTE

    def test_none_defaults_to_compute(self):
        assert _infer_action_type(None) == ActionType.COMPUTE


class TestRuleDefinitionDeclarationFromV2:
    def test_minimal_v2(self):
        v2 = RuleDefinitionV2(id="R001", name="Credit Rule")
        rd = RuleDefinitionDeclaration.from_v2(v2)
        assert rd.name == "Credit Rule"
        assert rd.type == "constraint"
        assert rd.priority == 100

    def test_full_v2(self):
        v2 = RuleDefinitionV2(
            id="R001",
            name="Credit Eligibility",
            description="Check credit eligibility",
            rule_type="decision",
            priority=200,
            applies_to=["Supplier"],
            inputs=[{"name": "credit_score", "type": "integer", "metric": "credit_score"}],
            outputs=[{"name": "eligible", "type": "boolean"}],
            preconditions=[{"expression": "credit_score > 0"}],
            applicability={"when_text": "评估信用风险时"},
            enabled=True,
            logic_ids=["R001_logic"],
        )
        rd = RuleDefinitionDeclaration.from_v2(v2)
        assert rd.name == "Credit Eligibility"
        assert rd.type == "decision"
        assert rd.applies_to.fact_objects == ["Supplier"]
        assert len(rd.inputs) == 1
        assert rd.inputs[0].metric == "credit_score"
        assert len(rd.outputs) == 1
        assert len(rd.preconditions) == 1
        assert rd.applicability is not None
        assert rd.applicability.when_text == "评估信用风险时"

    def test_dict_applies_to(self):
        v2 = RuleDefinitionV2(
            id="R001",
            applies_to=["Supplier"],
            applicable_categorizations=["industry"],
        )
        rd = RuleDefinitionDeclaration.from_v2(v2)
        assert rd.applies_to.fact_objects == ["Supplier"]


class TestRuleLogicDeclarationFromLegacy:
    def test_logic_with_steps(self):
        logic = RuleLogic(
            id="L001",
            name="Credit Logic",
            definition_id="R001",
            type="decision_table",
            steps=[
                SchemaRuleStep(
                    id="S1",
                    name="Check score",
                    action="set_flag",
                    output_field="eligible",
                ),
                SchemaRuleStep(
                    id="S2",
                    name="Compute score",
                    operator="FORMULA",
                    computation={"formula": "income * 0.3"},
                    output_field="credit_score",
                    depends_on=["S1"],
                ),
            ],
        )
        rl = RuleLogicDeclaration.from_legacy_logic(logic)
        assert rl.name == "Credit Logic"
        assert rl.definition_ref == "R001"
        assert len(rl.steps) == 2
        assert rl.steps[0].action is not None
        assert rl.steps[0].action.type == ActionType.SET_FLAG
        assert rl.steps[1].action.type == ActionType.COMPUTE
        assert rl.steps[1].depends_on == ["S1"]

    def test_logic_with_condition(self):
        logic = RuleLogic(
            id="L001",
            name="Conditional Logic",
            definition_id="R001",
            steps=[
                SchemaRuleStep(
                    id="S1",
                    condition=RuleWhen(expression="credit_score >= 60"),
                    action="approve_eligibility",
                ),
            ],
        )
        rl = RuleLogicDeclaration.from_legacy_logic(logic)
        assert rl.steps[0].condition is not None
        assert rl.steps[0].condition.expression == "credit_score >= 60"


class TestBusinessLogicV3FromV2:
    def test_conversion(self):
        bl = BusinessLogic(
            rule_definitions=[
                RuleDefinitionV2(id="R001", name="Rule 1", rule_type="decision"),
                RuleDefinitionV2(id="R002", name="Rule 2", rule_type="constraint"),
            ],
            rule_logics=[
                RuleLogic(id="L001", name="Logic 1", definition_id="R001"),
            ],
        )
        v3 = BusinessLogicV3.from_business_logic(bl)
        assert len(v3.rule_definitions) == 2
        assert len(v3.rule_logics) == 1
        assert v3.rule_definitions[0].name == "Rule 1"
        assert v3.rule_definitions[0].type == "decision"
        assert v3.rule_logics[0].definition_ref == "R001"


class TestRuleDefinitionDeclFromRuleGroup:
    def test_conversion(self):
        rg = RuleGroupDefinition(
            name="R001",
            description="Credit rule",
            type="decision",
            priority=200,
            applies_to=AppliesToConfig(fact_objects=["Supplier"]),
            inputs=[IOElement(name="credit_score", type="integer")],
            outputs=[IOElement(name="eligible", type="boolean")],
        )
        rd = RuleDefinitionDecl.from_rule_group(rg)
        assert rd.name == "R001"
        assert rd.type == "decision"
        assert rd.priority == 200
        assert rd.applies_to.fact_objects == ["Supplier"]
        assert len(rd.inputs) == 1
        assert len(rd.outputs) == 1


class TestRuleLogicDeclFromRuleSteps:
    def test_conversion(self):
        steps = [
            RuleStep(
                id="S1",
                name="Check score",
                rule_group="R001",
                order=1,
                when=ConditionClause(type="expression", expression="credit_score >= 60"),
                then=ActionClause(operator="FORMULA", params={"formula": "income * 0.3"}),
            ),
        ]
        rl = RuleLogicDecl.from_rule_steps(steps, definition_ref="R001")
        assert rl.definition_ref == "R001"
        assert len(rl.steps) == 1
        assert rl.steps[0].id == "S1"
        assert rl.steps[0].action is not None
        assert rl.steps[0].action.type == ActionType.COMPUTE
        assert rl.steps[0].action.operator == OperatorType.FORMULA


class TestStructuredActionClauseFromLegacy:
    def test_from_action_clause(self):
        action = StructuredActionClause.from_legacy(
            "set_flag",
            output={"flag": "eligible", "value": True},
        )
        assert action is not None
        assert action.type == ActionType.SET_FLAG
        assert action.flag == "eligible"
        assert action.value is True

    def test_from_operator_name(self):
        action = StructuredActionClause.from_legacy(
            "calculate_credit_score",
            computation={"formula": "income * 0.3"},
        )
        assert action is not None
        assert action.type == ActionType.COMPUTE

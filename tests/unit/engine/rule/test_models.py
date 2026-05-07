# tests/unit/engine/rule/test_models.py
"""Tests for RuleStep model."""


from ontology_engine.engine.rule.models import (
    ActionClause,
    ConditionClause,
    RuleStep,
)


class TestRuleStepDependsOn:
    """Test RuleStep depends_on field."""

    def test_default_empty_depends_on(self):
        """Test that depends_on defaults to empty list."""
        step = RuleStep(
            id="step_a",
            name="Step A",
            rule_group="test_group",
            order=1,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
        )
        assert step.depends_on == []

    def test_depends_on_with_values(self):
        """Test that depends_on can be set with values."""
        step = RuleStep(
            id="step_b",
            name="Step B",
            rule_group="test_group",
            order=2,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
            depends_on=["step_a", "other_group/step_x"],
        )
        assert step.depends_on == ["step_a", "other_group/step_x"]

    def test_to_dict_includes_depends_on(self):
        """Test that to_dict() includes depends_on field."""
        step = RuleStep(
            id="step_c",
            name="Step C",
            rule_group="test_group",
            order=3,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
            depends_on=["step_a", "other_group/step_x"],
        )
        result = step.to_dict()
        assert "depends_on" in result
        assert result["depends_on"] == ["step_a", "other_group/step_x"]

    def test_to_dict_empty_depends_on(self):
        """Test that to_dict() includes empty depends_on."""
        step = RuleStep(
            id="step_d",
            name="Step D",
            rule_group="test_group",
            order=4,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
        )
        result = step.to_dict()
        assert "depends_on" in result
        assert result["depends_on"] == []

    def test_from_dict_snake_case(self):
        """Test from_dict() with snake_case depends_on."""
        data = {
            "id": "step_e",
            "name": "Step E",
            "rule_group": "test_group",
            "step_order": 5,
            "when": {"type": "expression", "expression": "x > 0"},
            "then": {"operator": "flag", "params": {}},
            "depends_on": ["step_a", "other_group/step_x"],
        }
        step = RuleStep.from_dict(data)
        assert step.depends_on == ["step_a", "other_group/step_x"]

    def test_from_dict_camel_case(self):
        """Test from_dict() with camelCase dependsOn."""
        data = {
            "id": "step_f",
            "name": "Step F",
            "ruleGroup": "test_group",
            "stepOrder": 6,
            "when": {"type": "expression", "expression": "x > 0"},
            "then": {"operator": "flag", "params": {}},
            "dependsOn": ["step_b", "another_group/step_y"],
        }
        step = RuleStep.from_dict(data)
        assert step.depends_on == ["step_b", "another_group/step_y"]

    def test_from_dict_missing_depends_on(self):
        """Test from_dict() when depends_on is missing (defaults to empty list)."""
        data = {
            "id": "step_g",
            "name": "Step G",
            "rule_group": "test_group",
            "step_order": 7,
            "when": {"type": "expression", "expression": "x > 0"},
            "then": {"operator": "flag", "params": {}},
        }
        step = RuleStep.from_dict(data)
        assert step.depends_on == []

    def test_round_trip_snake_case(self):
        """Test that to_dict and from_dict are reversible with snake_case."""
        original = RuleStep(
            id="step_h",
            name="Step H",
            rule_group="test_group",
            order=8,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
            depends_on=["step_a", "other_group/step_x"],
        )
        data = original.to_dict()
        restored = RuleStep.from_dict(data)
        assert restored.depends_on == original.depends_on
        assert restored.id == original.id
        assert restored.name == original.name

    def test_round_trip_camel_case_input(self):
        """Test that from_dict with camelCase and to_dict are reversible."""
        data = {
            "id": "step_i",
            "name": "Step I",
            "ruleGroup": "test_group",
            "stepOrder": 9,
            "when": {"type": "expression", "expression": "x > 0"},
            "then": {"operator": "flag", "params": {}},
            "dependsOn": ["step_b"],
        }
        step = RuleStep.from_dict(data)
        output = step.to_dict()
        assert output["depends_on"] == ["step_b"]


class TestRuleStepBasic:
    """Test basic RuleStep functionality still works."""

    def test_create_rule_step(self):
        """Test creating a RuleStep with all fields."""
        step = RuleStep(
            id="step_1",
            name="Step 1",
            rule_group="group_a",
            order=1,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
            else_=ActionClause(operator="unflag", params={}),
            enabled=True,
            description="Test step",
            tags=["tag1", "tag2"],
        )
        assert step.id == "step_1"
        assert step.name == "Step 1"
        assert step.rule_group == "group_a"
        assert step.order == 1
        assert step.enabled is True
        assert step.description == "Test step"
        assert step.tags == ["tag1", "tag2"]

    def test_to_dict_basic_fields(self):
        """Test to_dict() outputs correct basic fields."""
        step = RuleStep(
            id="step_2",
            name="Step 2",
            rule_group="group_b",
            order=2,
            when=ConditionClause(type="expression", expression="x > 0"),
            then=ActionClause(operator="flag", params={}),
        )
        result = step.to_dict()
        assert result["id"] == "step_2"
        assert result["name"] == "Step 2"
        assert result["rule_group"] == "group_b"
        assert result["step_order"] == 2
        assert result["enabled"] is True
        assert result["description"] == ""
        assert result["tags"] == []

    def test_from_dict_basic_fields(self):
        """Test from_dict() parses basic fields correctly."""
        data = {
            "id": "step_3",
            "name": "Step 3",
            "rule_group": "group_c",
            "step_order": 3,
            "when": {"type": "expression", "expression": "x > 0"},
            "then": {"operator": "flag", "params": {}},
            "enabled": False,
            "description": "A test step",
            "tags": ["test"],
        }
        step = RuleStep.from_dict(data)
        assert step.id == "step_3"
        assert step.name == "Step 3"
        assert step.rule_group == "group_c"
        assert step.order == 3
        assert step.enabled is False
        assert step.description == "A test step"
        assert step.tags == ["test"]

    def test_from_dict_camel_case_rule_group(self):
        """Test from_dict() handles camelCase ruleGroup."""
        data = {
            "id": "step_4",
            "name": "Step 4",
            "ruleGroup": "group_d",  # camelCase
            "step_order": 4,  # Note: to_dict outputs step_order, not stepOrder
            "when": {"type": "expression", "expression": "x > 0"},
            "then": {"operator": "flag", "params": {}},
        }
        step = RuleStep.from_dict(data)
        assert step.rule_group == "group_d"
        assert step.order == 4
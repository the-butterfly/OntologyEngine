"""Tests for safe expression evaluator."""

from __future__ import annotations

import pytest

from ontology_engine.engine.cognitive.models import DEFAULT_BELIEF_REVISION_RULES
from ontology_engine.engine.cognitive.rule_eval import (
    ALLOWED_VARIABLES,
    safe_eval,
)


class TestBasicBooleanExpressions:
    def test_confidence_greater_than(self):
        assert safe_eval("confidence > 0.5", {"confidence": 0.8}) is True

    def test_confidence_not_greater_than(self):
        assert safe_eval("confidence > 0.5", {"confidence": 0.3}) is False

    def test_feedback_weight_less_than(self):
        assert safe_eval("feedback_weight < 0", {"feedback_weight": -0.3}) is True

    def test_feedback_weight_not_less_than(self):
        assert safe_eval("feedback_weight < 0", {"feedback_weight": 0.5}) is False


class TestCompoundExpressions:
    def test_and_both_true(self):
        ctx = {"confidence": 0.8, "feedback_weight": -0.3}
        assert safe_eval("confidence > 0.5 and feedback_weight < 0", ctx) is True

    def test_and_one_false(self):
        ctx = {"confidence": 0.8, "feedback_weight": 0.5}
        assert safe_eval("confidence > 0.5 and feedback_weight < 0", ctx) is False

    def test_and_both_false(self):
        ctx = {"confidence": 0.3, "feedback_weight": 0.5}
        assert safe_eval("confidence > 0.5 and feedback_weight < 0", ctx) is False

    def test_or_one_true(self):
        ctx = {"confidence": 0.9, "evidence_count": 1}
        assert safe_eval("confidence > 0.8 or evidence_count > 3", ctx) is True

    def test_or_both_true(self):
        ctx = {"confidence": 0.9, "evidence_count": 5}
        assert safe_eval("confidence > 0.8 or evidence_count > 3", ctx) is True

    def test_or_both_false(self):
        ctx = {"confidence": 0.5, "evidence_count": 1}
        assert safe_eval("confidence > 0.8 or evidence_count > 3", ctx) is False

    def test_triple_and(self):
        ctx = {"confidence": 0.9, "evidence_count": 5, "feedback_weight": 0.9}
        assert (
            safe_eval(
                "confidence > 0.8 and evidence_count > 3 and feedback_weight > 0.5",
                ctx,
            )
            is True
        )


class TestComparisonOperators:
    @pytest.fixture()
    def ctx(self):
        return {"confidence": 0.5, "evidence_count": 3}

    def test_gt(self, ctx):
        assert safe_eval("confidence > 0.5", ctx) is False

    def test_lt(self, ctx):
        assert safe_eval("confidence < 0.6", ctx) is True

    def test_gte_equal(self, ctx):
        assert safe_eval("confidence >= 0.5", ctx) is True

    def test_gte_greater(self, ctx):
        assert safe_eval("confidence >= 0.4", ctx) is True

    def test_lte_equal(self, ctx):
        assert safe_eval("evidence_count <= 3", ctx) is True

    def test_lte_less(self, ctx):
        assert safe_eval("evidence_count <= 4", ctx) is True

    def test_eq(self, ctx):
        assert safe_eval("evidence_count == 3", ctx) is True

    def test_neq(self, ctx):
        assert safe_eval("evidence_count != 4", ctx) is True

    def test_in_operator(self):
        ctx = {"source": "征信报告"}
        assert safe_eval("source in ('征信报告', '法院判决')", ctx) is True

    def test_not_in_operator(self):
        ctx = {"source": "user_input"}
        assert safe_eval("source not in ('征信报告', '法院判决')", ctx) is True


class TestLogicalOperators:
    def test_not_true(self):
        assert safe_eval("not confidence > 0.5", {"confidence": 0.3}) is True

    def test_not_false(self):
        assert safe_eval("not confidence > 0.5", {"confidence": 0.8}) is False

    def test_not_with_and(self):
        ctx = {"confidence": 0.3, "evidence_count": 1}
        assert safe_eval("not (confidence > 0.5 and evidence_count > 3)", ctx) is True

    def test_not_with_or(self):
        ctx = {"confidence": 0.9, "evidence_count": 5}
        assert safe_eval("not (confidence > 0.8 or evidence_count > 3)", ctx) is False


class TestAllowedVariables:
    @pytest.mark.parametrize(
        "variable,value,expr",
        [
            ("confidence", 0.9, "confidence > 0.5"),
            ("feedback_weight", -0.1, "feedback_weight < 0"),
            ("evidence_count", 5, "evidence_count > 3"),
            ("is_newer", True, "is_newer == True"),
            ("schema_alignment", 0.8, "schema_alignment >= 0.5"),
            ("source", "user_correction", "source == 'user_correction'"),
            ("belief_status", "accepted", "belief_status == 'accepted'"),
        ],
    )
    def test_each_allowed_variable(self, variable, value, expr):
        assert safe_eval(expr, {variable: value}) is True

    def test_disallowed_variable_raises(self):
        with pytest.raises(ValueError, match="not in the allowed set"):
            safe_eval("unknown_var > 0", {"unknown_var": 1})

    def test_context_with_extra_keys_ignored(self):
        ctx = {"confidence": 0.9, "unknown_var": 42}
        assert safe_eval("confidence > 0.5", ctx) is True

    def test_all_variables_in_whitelist_match_model(self):
        expected = {
            "confidence",
            "feedback_weight",
            "evidence_count",
            "is_newer",
            "schema_alignment",
            "source",
            "belief_status",
        }
        assert ALLOWED_VARIABLES == expected


class TestSecurityMaliciousExpressions:
    def test_import_os_system(self):
        with pytest.raises(ValueError):
            safe_eval('__import__("os").system("ls")', {"confidence": 0.5})

    def test_class_bases_subclasses(self):
        with pytest.raises(ValueError):
            safe_eval(
                "().__class__.__bases__[0].__subclasses__()",
                {"confidence": 0.5},
            )

    def test_open_file(self):
        with pytest.raises(ValueError):
            safe_eval('open("/etc/passwd")', {"confidence": 0.5})

    def test_eval_nested(self):
        with pytest.raises(ValueError):
            safe_eval('eval("1+1")', {"confidence": 0.5})

    def test_exec_nested(self):
        with pytest.raises(ValueError):
            safe_eval('exec("print(1)")', {"confidence": 0.5})

    def test_disallowed_variable_name(self):
        with pytest.raises(ValueError, match="not in the allowed set"):
            safe_eval("os_name == 'linux'", {"os_name": "linux"})

    def test_bitwise_and(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("confidence & 1", {"confidence": 1})

    def test_bitwise_or(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("confidence | 1", {"confidence": 1})

    def test_bitwise_xor(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("confidence ^ 1", {"confidence": 1})

    def test_bitwise_shift(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("evidence_count >> 1", {"evidence_count": 4})

    def test_attribute_access(self):
        with pytest.raises(ValueError, match="Disallowed AST node"):
            safe_eval("confidence.__class__", {"confidence": 0.5})

    def test_function_call(self):
        with pytest.raises(ValueError, match="Disallowed AST node"):
            safe_eval("print(1)", {"confidence": 0.5})

    def test_subscript_on_disallowed(self):
        with pytest.raises(ValueError):
            safe_eval("confidence[0]", {"confidence": 0.5})

    def test_lambda_expression(self):
        with pytest.raises(ValueError, match="Disallowed AST node"):
            safe_eval("lambda x: x", {"confidence": 0.5})

    def test_list_comprehension(self):
        with pytest.raises(ValueError, match="Disallowed AST node"):
            safe_eval("[x for x in [1]]", {"confidence": 0.5})

    def test_dict_constant(self):
        with pytest.raises(ValueError, match="Disallowed"):
            safe_eval("{}", {"confidence": 0.5})

    def test_tuple_constant(self):
        result = safe_eval(
            "source in ('a', 'b')",
            {"source": "a"},
        )
        assert result is True


class TestEdgeCases:
    def test_division_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            safe_eval("confidence / 0", {"confidence": 1.0})

    def test_non_bool_result_raises(self):
        with pytest.raises(ValueError, match="did not evaluate to bool"):
            safe_eval("confidence + 0.1", {"confidence": 0.5})

    def test_syntax_error_raises_value_error(self):
        with pytest.raises(ValueError, match="syntax error"):
            safe_eval("confidence >>>", {"confidence": 0.5})

    def test_empty_expression_raises(self):
        with pytest.raises(ValueError):
            safe_eval("", {"confidence": 0.5})

    def test_none_constant(self):
        assert safe_eval("belief_status == None", {"belief_status": None}) is True

    def test_true_false_constants(self):
        assert safe_eval("is_newer == True", {"is_newer": True}) is True
        assert safe_eval("is_newer == False", {"is_newer": False}) is True

    def test_negative_number(self):
        assert safe_eval("feedback_weight < -0.1", {"feedback_weight": -0.5}) is True

    def test_string_equality(self):
        assert (
            safe_eval("source == 'user_correction'", {"source": "user_correction"})
            is True
        )

    def test_string_inequality(self):
        assert (
            safe_eval("source != 'user_correction'", {"source": "other"}) is True
        )

    def test_is_operator(self):
        assert safe_eval("belief_status is None", {"belief_status": None}) is True

    def test_is_not_operator(self):
        assert (
            safe_eval("belief_status is not None", {"belief_status": "accepted"})
            is True
        )


class TestDefaultBeliefRevisionRules:
    RULES_WITH_CONTEXTS = [
        (
            "BR_R001",
            "source == 'user_correction'",
            {"source": "user_correction"},
            True,
        ),
        (
            "BR_R001",
            "source == 'user_correction'",
            {"source": "other"},
            False,
        ),
        (
            "BR_R002",
            "source in ('征信报告', '法院判决', '监管文件')",
            {"source": "征信报告"},
            True,
        ),
        (
            "BR_R002",
            "source in ('征信报告', '法院判决', '监管文件')",
            {"source": "other"},
            False,
        ),
        (
            "BR_R003",
            "confidence >= 0.9 and evidence_count >= 3",
            {"confidence": 0.9, "evidence_count": 3},
            True,
        ),
        (
            "BR_R003",
            "confidence >= 0.9 and evidence_count >= 3",
            {"confidence": 0.8, "evidence_count": 5},
            False,
        ),
        (
            "BR_R004",
            "is_newer and confidence >= 0.7",
            {"is_newer": True, "confidence": 0.7},
            True,
        ),
        (
            "BR_R004",
            "is_newer and confidence >= 0.7",
            {"is_newer": False, "confidence": 0.9},
            False,
        ),
        (
            "BR_R005",
            "feedback_weight > 0.8",
            {"feedback_weight": 0.9},
            True,
        ),
        (
            "BR_R005",
            "feedback_weight > 0.8",
            {"feedback_weight": 0.5},
            False,
        ),
        (
            "BR_R006",
            "schema_alignment < 0.3",
            {"schema_alignment": 0.1},
            True,
        ),
        (
            "BR_R006",
            "schema_alignment < 0.3",
            {"schema_alignment": 0.5},
            False,
        ),
    ]

    @pytest.mark.parametrize(
        "rule_id,condition,context,expected",
        RULES_WITH_CONTEXTS,
        ids=[f"{r[0]}_{i}" for i, r in enumerate(RULES_WITH_CONTEXTS)],
    )
    def test_rule_condition_evaluates(self, rule_id, condition, context, expected):
        assert safe_eval(condition, context) is expected

    def test_br_r007_uses_disallowed_variable(self):
        r007 = next(r for r in DEFAULT_BELIEF_REVISION_RULES if r.rule_id == "BR_R007")
        with pytest.raises(ValueError, match="not in the allowed set"):
            safe_eval(
                r007.condition,
                {"confidence": 0.5, "conflicting_domains": True},
            )

    def test_all_default_rules_present(self):
        rule_ids = {r.rule_id for r in DEFAULT_BELIEF_REVISION_RULES}
        expected_ids = {
            "BR_R001",
            "BR_R002",
            "BR_R003",
            "BR_R004",
            "BR_R005",
            "BR_R006",
            "BR_R007",
        }
        assert rule_ids == expected_ids

# tests/unit/core/types/test_apply_overrides.py
"""Tests for core.types.apply_overrides utility."""

import copy

import pytest

from ontology_engine.core.types import apply_overrides, deep_copy_entity_data


class TestApplyOverrides:
    def test_flat_override(self):
        data = {"industry": "RETAIL", "risk_level": "LOW"}
        apply_overrides(data, {"risk_level": "HIGH"})
        assert data["risk_level"] == "HIGH"
        assert data["industry"] == "RETAIL"

    def test_nested_path_override(self):
        data = {"registered_capital": {"value": 1000000, "currency": "CNY"}}
        apply_overrides(data, {"registered_capital.value": 2000000})
        assert data["registered_capital"]["value"] == 2000000
        assert data["registered_capital"]["currency"] == "CNY"

    def test_nested_path_creates_intermediate(self):
        data: dict = {}
        apply_overrides(data, {"registered_capital.value": 500000})
        assert data == {"registered_capital": {"value": 500000}}

    def test_multiple_overrides(self):
        data = {"industry": "RETAIL", "risk_level": "LOW"}
        apply_overrides(data, {"industry": "MANUFACTURING", "risk_level": "MEDIUM"})
        assert data["industry"] == "MANUFACTURING"
        assert data["risk_level"] == "MEDIUM"

    def test_mixed_flat_and_nested(self):
        data = {"industry": "RETAIL", "capital": {"value": 100}}
        apply_overrides(data, {"industry": "MFG", "capital.value": 200})
        assert data["industry"] == "MFG"
        assert data["capital"]["value"] == 200

    def test_empty_overrides(self):
        data = {"industry": "RETAIL"}
        apply_overrides(data, {})
        assert data == {"industry": "RETAIL"}

    def test_none_overrides(self):
        data = {"industry": "RETAIL"}
        apply_overrides(data, None)
        assert data == {"industry": "RETAIL"}

    def test_new_key_added(self):
        data = {"industry": "RETAIL"}
        apply_overrides(data, {"new_field": "new_value"})
        assert data["new_field"] == "new_value"

    def test_deep_nested_path(self):
        data: dict = {}
        apply_overrides(data, {"a.b.c": 42})
        assert data == {"a": {"b": {"c": 42}}}

    def test_non_dict_intermediate_raises_type_error(self):
        data = {"capital": "string_value"}
        with pytest.raises(TypeError, match="intermediate value"):
            apply_overrides(data, {"capital.value": 100})

    def test_empty_key_segment_raises_value_error(self):
        data: dict = {}
        with pytest.raises(ValueError, match="empty segments"):
            apply_overrides(data, {"a..b": 100})

    def test_leading_dot_raises_value_error(self):
        data: dict = {}
        with pytest.raises(ValueError, match="empty segments"):
            apply_overrides(data, {".foo": 100})

    def test_trailing_dot_raises_value_error(self):
        data: dict = {}
        with pytest.raises(ValueError, match="empty segments"):
            apply_overrides(data, {"foo.": 100})


class TestDeepCopyEntityData:
    def test_deep_copy_isolation(self):
        original = {"a": {"b": 1}, "c": [1, 2, 3]}
        copied = deep_copy_entity_data(original)
        copied["a"]["b"] = 99
        copied["c"].append(4)
        assert original["a"]["b"] == 1
        assert original["c"] == [1, 2, 3]

    def test_deep_copy_with_overrides(self):
        original = {"registered_capital": {"value": 1000000}}
        copied = deep_copy_entity_data(original)
        apply_overrides(copied, {"registered_capital.value": 2000000})
        assert original["registered_capital"]["value"] == 1000000
        assert copied["registered_capital"]["value"] == 2000000

    def test_deep_copy_empty_dict(self):
        original: dict = {}
        copied = deep_copy_entity_data(original)
        assert copied == {}
        assert copied is not original

"""Unit tests for CognitiveNode serialization and storage migrations."""

from __future__ import annotations

import pytest

from ontology_engine.storage.models import (
    CognitiveNode,
    VALID_MEMORY_TYPES,
    VALID_COGNITIVE_LAYERS,
    VALID_BELIEF_STATUSES,
    VALID_VISIBILITIES,
)
from ontology_engine.storage.migrations import (
    _migrate_tags_list_to_dict,
    _migrate_model_domain_to_tags,
    apply_cognitive_node_migrations,
)


def _base_kwargs(**overrides) -> dict:
    defaults = {
        "id": "mem:entity:test1",
        "memory_type": "entity",
        "cognitive_layer": "semantic",
        "content": "test content",
    }
    defaults.update(overrides)
    return defaults


class TestCognitiveNodePostInitValidation:
    def test_valid_node_constructs(self):
        node = CognitiveNode(**_base_kwargs())
        assert node.memory_type == "entity"

    def test_invalid_memory_type_raises(self):
        with pytest.raises(ValueError, match="Invalid memory_type"):
            CognitiveNode(**_base_kwargs(memory_type="invalid_type"))

    def test_invalid_cognitive_layer_raises(self):
        with pytest.raises(ValueError, match="Invalid cognitive_layer"):
            CognitiveNode(**_base_kwargs(cognitive_layer="invalid_layer"))

    def test_invalid_belief_status_raises(self):
        with pytest.raises(ValueError, match="Invalid belief_status"):
            CognitiveNode(**_base_kwargs(belief_status="invalid_status"))

    def test_invalid_visibility_raises(self):
        with pytest.raises(ValueError, match="Invalid visibility"):
            CognitiveNode(**_base_kwargs(visibility="invalid_vis"))

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            CognitiveNode(**_base_kwargs(confidence=1.5))

    def test_negative_confidence_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            CognitiveNode(**_base_kwargs(confidence=-0.1))

    def test_feedback_weight_out_of_range_raises(self):
        with pytest.raises(ValueError, match="feedback_weight"):
            CognitiveNode(**_base_kwargs(feedback_weight=1.5))

    def test_strength_out_of_range_raises(self):
        with pytest.raises(ValueError, match="strength"):
            CognitiveNode(**_base_kwargs(strength=1.5))

    def test_version_zero_raises(self):
        with pytest.raises(ValueError, match="version"):
            CognitiveNode(**_base_kwargs(version=0))

    def test_invalid_source_trust_tier_raises(self):
        with pytest.raises(ValueError, match="source_trust_tier"):
            CognitiveNode(**_base_kwargs(source_trust_tier="invalid"))

    def test_source_trust_tier_none_is_valid(self):
        node = CognitiveNode(**_base_kwargs(source_trust_tier=None))
        assert node.source_trust_tier is None

    def test_all_valid_memory_types(self):
        for mt in VALID_MEMORY_TYPES:
            node = CognitiveNode(**_base_kwargs(memory_type=mt))
            assert node.memory_type == mt

    def test_all_valid_belief_statuses(self):
        for bs in VALID_BELIEF_STATUSES:
            node = CognitiveNode(**_base_kwargs(belief_status=bs))
            assert node.belief_status == bs


class TestCognitiveNodeSerialization:
    def test_to_dict_from_dict_roundtrip(self):
        node = CognitiveNode(**_base_kwargs(
            tags={"domain": "finance"},
            attributes={"key": "value"},
            source_fragment_ids=["f1", "f2"],
            confidence=0.8,
            strength=0.9,
        ))
        d = node.to_dict()
        restored = CognitiveNode.from_dict(d)
        assert restored.id == node.id
        assert restored.memory_type == node.memory_type
        assert restored.content == node.content
        assert restored.tags == node.tags
        assert restored.attributes == node.attributes
        assert restored.source_fragment_ids == node.source_fragment_ids
        assert restored.confidence == node.confidence
        assert restored.strength == node.strength

    def test_to_dict_covers_all_fields(self):
        node = CognitiveNode(**_base_kwargs())
        d = node.to_dict()
        expected_fields = {
            "id", "memory_type", "cognitive_layer", "content",
            "content_vector", "source_fragment_ids", "belief_status",
            "ttl_seconds", "occurred_at", "created_at", "updated_at",
            "history", "access_count", "last_access_at", "consolidated_at",
            "domain_id", "space_id", "extraction_hint", "visibility",
            "created_by", "feedback_weight", "confidence", "schema_ref",
            "superseded_by", "proof_count", "valid_from", "valid_to",
            "recorded_at", "tags", "attributes", "confirmation_count",
            "strength", "entity_name", "entity_type", "version",
            "last_confirmed_at", "consolidation_reasoning", "compiled_at",
            "source_trust_tier", "scope", "source_pipeline",
            "source_content_hash",
        }
        assert set(d.keys()) == expected_fields

    def test_from_dict_filters_unknown_keys(self):
        d = _base_kwargs(extra_field="should_be_removed", another_unknown=42)
        node = CognitiveNode.from_dict(d)
        assert not hasattr(node, "extra_field")
        assert not hasattr(node, "another_unknown")

    def test_can_transition_to_valid(self):
        node = CognitiveNode(**_base_kwargs(belief_status="accepted"))
        assert node.can_transition_to("contradicted") is True
        assert node.can_transition_to("pending_review") is True

    def test_can_transition_to_invalid(self):
        node = CognitiveNode(**_base_kwargs(belief_status="rejected"))
        assert node.can_transition_to("contradicted") is False


class TestMigrations:
    def test_migrate_tags_list_to_dict(self):
        data = {"tags": ["domain:finance", "source:report", "bare_tag"]}
        result = _migrate_tags_list_to_dict(data)
        assert result["tags"] == {"domain": "finance", "source": "report", "_legacy": ["bare_tag"]}

    def test_migrate_tags_list_to_dict_no_tags(self):
        data = {"content": "hello"}
        result = _migrate_tags_list_to_dict(data)
        assert "tags" not in result

    def test_migrate_tags_list_to_dict_already_dict(self):
        data = {"tags": {"domain": "finance"}}
        result = _migrate_tags_list_to_dict(data)
        assert result["tags"] == {"domain": "finance"}

    def test_migrate_model_domain_to_tags(self):
        data = {"model_domain": "User Model"}
        result = _migrate_model_domain_to_tags(data)
        assert result["tags"]["model"] == "User Model"

    def test_migrate_model_domain_to_tags_existing_model_tag(self):
        data = {"model_domain": "User Model", "tags": {"model": "Task Model"}}
        result = _migrate_model_domain_to_tags(data)
        assert result["tags"]["model"] == "Task Model"

    def test_migrate_model_domain_no_model_domain(self):
        data = {"content": "hello"}
        result = _migrate_model_domain_to_tags(data)
        assert "tags" not in result

    def test_apply_migrations_chained(self):
        data = {"model_domain": "World Model", "tags": ["domain:finance"]}
        result = apply_cognitive_node_migrations(data)
        assert result["tags"]["domain"] == "finance"
        assert result["tags"]["model"] == "World Model"

    def test_migrations_do_not_mutate_input(self):
        data = {"tags": ["domain:finance"]}
        original = dict(data)
        _migrate_tags_list_to_dict(data)
        assert data == original

"""Contract tests for CognitiveNode and CognitiveEdge models."""

from __future__ import annotations

import pytest

from ontology_engine.storage.models import (
    BELIEF_TRANSITIONS,
    CognitiveEdge,
    CognitiveNode,
)


def _node_kwargs(**overrides) -> dict:
    defaults = {
        "id": "mem:entity:abc123",
        "memory_type": "entity",
        "cognitive_layer": "semantic",
        "content": "test content",
    }
    defaults.update(overrides)
    return defaults


class TestCognitiveNodeFromDict:
    def test_valid_data(self):
        data = _node_kwargs()
        node = CognitiveNode.from_dict(data)
        assert node.id == "mem:entity:abc123"
        assert node.memory_type == "entity"
        assert node.cognitive_layer == "semantic"
        assert node.content == "test content"

    def test_extra_fields_filtered(self):
        data = _node_kwargs(unknown_field="remove_me", another_extra=42)
        node = CognitiveNode.from_dict(data)
        assert not hasattr(node, "unknown_field")
        assert not hasattr(node, "another_extra")

    def test_missing_optional_fields_use_defaults(self):
        data = {
            "id": "mem:observation:x",
            "memory_type": "observation",
            "cognitive_layer": "perception",
            "content": "observed something",
        }
        node = CognitiveNode.from_dict(data)
        assert node.belief_status == "accepted"
        assert node.visibility == "shared"
        assert node.confidence == 1.0
        assert node.feedback_weight == 0.5
        assert node.version == 1
        assert node.space_id == "default"
        assert node.source_fragment_ids == []
        assert node.history == []
        assert node.tags == {}
        assert node.attributes == {}
        assert node.content_vector is None
        assert node.domain_id is None
        assert node.created_by is None


class TestCognitiveNodeToDict:
    def test_roundtrip_preserves_all_fields(self):
        node = CognitiveNode(
            id="mem:rule:r1",
            memory_type="rule",
            cognitive_layer="procedure",
            content="always validate",
            belief_status="pending_review",
            visibility="private",
            confidence=0.7,
            feedback_weight=0.3,
            version=2,
            space_id="test-space",
            source_fragment_ids=["f1", "f2"],
            tags={"domain": "finance"},
            attributes={"key": "val"},
        )
        d = node.to_dict()
        restored = CognitiveNode.from_dict(d)
        assert restored.id == node.id
        assert restored.memory_type == node.memory_type
        assert restored.cognitive_layer == node.cognitive_layer
        assert restored.content == node.content
        assert restored.belief_status == node.belief_status
        assert restored.visibility == node.visibility
        assert restored.confidence == node.confidence
        assert restored.feedback_weight == node.feedback_weight
        assert restored.version == node.version
        assert restored.space_id == node.space_id
        assert restored.source_fragment_ids == node.source_fragment_ids
        assert restored.tags == node.tags
        assert restored.attributes == node.attributes


class TestCognitiveNodeCanTransitionTo:
    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("accepted", "contradicted"),
            ("accepted", "superseded"),
            ("accepted", "pending_review"),
            ("accepted", "rejected"),
            ("contradicted", "accepted"),
            ("contradicted", "pending_review"),
            ("superseded", "accepted"),
            ("superseded", "rejected"),
            ("pending_review", "accepted"),
            ("pending_review", "contradicted"),
            ("pending_review", "superseded"),
            ("pending_review", "rejected"),
            ("rejected", "accepted"),
            ("rejected", "pending_review"),
        ],
    )
    def test_valid_transitions(self, from_status, to_status):
        node = CognitiveNode(**_node_kwargs(belief_status=from_status))
        assert node.can_transition_to(to_status) is True

    def test_accepted_to_accepted_is_false(self):
        node = CognitiveNode(**_node_kwargs(belief_status="accepted"))
        assert node.can_transition_to("accepted") is False

    def test_rejected_to_contradicted_is_false(self):
        node = CognitiveNode(**_node_kwargs(belief_status="rejected"))
        assert node.can_transition_to("contradicted") is False

    def test_rejected_to_superseded_is_false(self):
        node = CognitiveNode(**_node_kwargs(belief_status="rejected"))
        assert node.can_transition_to("superseded") is False

    def test_unknown_status_returns_false(self):
        node = CognitiveNode(**_node_kwargs(belief_status="accepted"))
        assert node.can_transition_to("nonexistent") is False


class TestCognitiveNodePostInitValidation:
    def test_invalid_memory_type_raises(self):
        with pytest.raises(ValueError, match="Invalid memory_type"):
            CognitiveNode(**_node_kwargs(memory_type="not_a_type"))

    def test_invalid_cognitive_layer_raises(self):
        with pytest.raises(ValueError, match="Invalid cognitive_layer"):
            CognitiveNode(**_node_kwargs(cognitive_layer="not_a_layer"))

    def test_invalid_belief_status_raises(self):
        with pytest.raises(ValueError, match="Invalid belief_status"):
            CognitiveNode(**_node_kwargs(belief_status="not_a_status"))

    def test_invalid_visibility_raises(self):
        with pytest.raises(ValueError, match="Invalid visibility"):
            CognitiveNode(**_node_kwargs(visibility="not_a_visibility"))

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            CognitiveNode(**_node_kwargs(confidence=1.5))

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValueError, match="confidence"):
            CognitiveNode(**_node_kwargs(confidence=-0.1))

    def test_feedback_weight_above_one_raises(self):
        with pytest.raises(ValueError, match="feedback_weight"):
            CognitiveNode(**_node_kwargs(feedback_weight=1.5))

    def test_feedback_weight_below_zero_raises(self):
        with pytest.raises(ValueError, match="feedback_weight"):
            CognitiveNode(**_node_kwargs(feedback_weight=-0.1))

    def test_version_zero_raises(self):
        with pytest.raises(ValueError, match="version"):
            CognitiveNode(**_node_kwargs(version=0))

    def test_version_negative_raises(self):
        with pytest.raises(ValueError, match="version"):
            CognitiveNode(**_node_kwargs(version=-1))


class TestCognitiveEdgeFromDict:
    def test_valid_data(self):
        data = {
            "edge_type": "SUPPORTS",
            "from_id": "mem:entity:a",
            "to_id": "mem:entity:b",
            "properties": {"weight": 0.9},
            "created_at": "2026-01-01T00:00:00Z",
        }
        edge = CognitiveEdge.from_dict(data)
        assert edge.edge_type == "SUPPORTS"
        assert edge.from_id == "mem:entity:a"
        assert edge.to_id == "mem:entity:b"
        assert edge.properties == {"weight": 0.9}
        assert edge.created_at == "2026-01-01T00:00:00Z"

    def test_missing_fields_use_defaults(self):
        data = {"edge_type": "CONTRADICTS", "from_id": "x", "to_id": "y"}
        edge = CognitiveEdge.from_dict(data)
        assert edge.properties == {}
        assert edge.created_at is None

    def test_empty_dict_uses_defaults(self):
        edge = CognitiveEdge.from_dict({})
        assert edge.edge_type == ""
        assert edge.from_id == ""
        assert edge.to_id == ""
        assert edge.properties == {}
        assert edge.created_at is None

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.storage.vector.chromadb_adapter import ChromaDBAdapter


@pytest.fixture
def adapter() -> ChromaDBAdapter:
    return ChromaDBAdapter()


@pytest.fixture
def mock_collection() -> MagicMock:
    collection = MagicMock()
    collection.count.return_value = 42
    collection.get.return_value = {"ids": ["id1", "id2", "id3"]}
    return collection


def _init_adapter(adapter: ChromaDBAdapter, mock_collection: MagicMock) -> None:
    adapter._client = MagicMock()
    adapter._collection = mock_collection


@pytest.mark.asyncio
async def test_count_empty_dict_uses_efficient_path(
    adapter: ChromaDBAdapter, mock_collection: MagicMock
) -> None:
    _init_adapter(adapter, mock_collection)
    result = await adapter.count({})
    assert result == 42
    mock_collection.count.assert_called_once()
    mock_collection.get.assert_not_called()


@pytest.mark.asyncio
async def test_count_with_filter_uses_get_path(
    adapter: ChromaDBAdapter, mock_collection: MagicMock
) -> None:
    _init_adapter(adapter, mock_collection)
    result = await adapter.count({"memory_type": "entity"})
    assert result == 3
    mock_collection.get.assert_called_once_with(where={"memory_type": "entity"})
    mock_collection.count.assert_not_called()


@pytest.mark.asyncio
async def test_count_none_uses_efficient_path(
    adapter: ChromaDBAdapter, mock_collection: MagicMock
) -> None:
    _init_adapter(adapter, mock_collection)
    result = await adapter.count(None)
    assert result == 42
    mock_collection.count.assert_called_once()
    mock_collection.get.assert_not_called()


class TestNodeToMetadataExtendedFields:
    def test_strength_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n1", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default", strength=0.75,
        )
        meta = adapter._node_to_metadata(node)
        assert meta["strength"] == 0.75

    def test_feedback_weight_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n2", memory_type="observation", cognitive_layer="semantic",
            content="test", space_id="default", feedback_weight=0.6,
        )
        meta = adapter._node_to_metadata(node)
        assert meta["feedback_weight"] == 0.6

    def test_confirmation_count_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n3", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default", confirmation_count=5,
        )
        meta = adapter._node_to_metadata(node)
        assert meta["confirmation_count"] == 5

    def test_source_fragment_ids_serialized_as_json(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n4", memory_type="observation", cognitive_layer="semantic",
            content="test", space_id="default",
            source_fragment_ids=["frag-1", "frag-2", "frag-3"],
        )
        meta = adapter._node_to_metadata(node)
        assert meta["source_fragment_ids"] == json.dumps(["frag-1", "frag-2", "frag-3"])

    def test_source_fragment_ids_omitted_when_empty(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n5", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default", source_fragment_ids=[],
        )
        meta = adapter._node_to_metadata(node)
        assert "source_fragment_ids" not in meta

    def test_scope_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n6", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default", scope="global",
        )
        meta = adapter._node_to_metadata(node)
        assert meta["scope"] == "global"

    def test_scope_omitted_when_none(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n7", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default",
        )
        meta = adapter._node_to_metadata(node)
        assert "scope" not in meta

    def test_entity_name_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n8", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default", entity_name="TestEntity",
        )
        meta = adapter._node_to_metadata(node)
        assert meta["entity_name"] == "TestEntity"

    def test_entity_type_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="n9", memory_type="entity", cognitive_layer="semantic",
            content="test", space_id="default", entity_type="Company",
        )
        meta = adapter._node_to_metadata(node)
        assert meta["entity_type"] == "Company"


class TestMetadataToNodeRoundTrip:
    def test_roundtrip_all_extended_fields(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="rt-1", memory_type="entity", cognitive_layer="semantic",
            content="Round trip content", space_id="space-1",
            strength=0.85, feedback_weight=0.65, confirmation_count=7,
            source_fragment_ids=["f1", "f2"], scope="task",
            entity_name="EntityX", entity_type="TypeY",
            belief_status="pending_review", confidence=0.92,
            created_at="2026-01-01T00:00:00Z",
            tags={"source_type": "text", "trust_tier": "high"},
        )
        meta = adapter._node_to_metadata(node)
        reconstructed = adapter._metadata_to_node(meta, node.content, node.id)

        assert reconstructed.id == "rt-1"
        assert reconstructed.memory_type == "entity"
        assert reconstructed.cognitive_layer == "semantic"
        assert reconstructed.content == "Round trip content"
        assert reconstructed.space_id == "space-1"
        assert reconstructed.strength == 0.85
        assert reconstructed.feedback_weight == 0.65
        assert reconstructed.confirmation_count == 7
        assert reconstructed.source_fragment_ids == ["f1", "f2"]
        assert reconstructed.scope == "task"
        assert reconstructed.entity_name == "EntityX"
        assert reconstructed.entity_type == "TypeY"
        assert reconstructed.belief_status == "pending_review"
        assert reconstructed.confidence == 0.92
        assert reconstructed.created_at == "2026-01-01T00:00:00Z"
        assert reconstructed.tags == {"source_type": "text", "trust_tier": "high"}

    def test_roundtrip_defaults_when_missing(self, adapter: ChromaDBAdapter) -> None:
        meta = {
            "memory_type": "fragment",
            "cognitive_layer": "perception",
            "space_id": "default",
            "belief_status": "accepted",
            "confidence": 1.0,
            "created_at": "",
        }
        reconstructed = adapter._metadata_to_node(meta, "doc text", "def-1")

        assert reconstructed.strength == 1.0
        assert reconstructed.feedback_weight == 0.5
        assert reconstructed.confirmation_count == 0
        assert reconstructed.source_fragment_ids == []
        assert reconstructed.scope is None
        assert reconstructed.entity_name is None
        assert reconstructed.entity_type is None

    def test_roundtrip_malformed_source_fragment_ids(self, adapter: ChromaDBAdapter) -> None:
        meta = {
            "memory_type": "fragment",
            "cognitive_layer": "perception",
            "space_id": "default",
            "source_fragment_ids": "not-valid-json{",
        }
        reconstructed = adapter._metadata_to_node(meta, "doc", "mal-1")
        assert reconstructed.source_fragment_ids == []

    def test_missing_fields_not_in_metadata(self, adapter: ChromaDBAdapter) -> None:
        node = CognitiveNode(
            id="full-1", memory_type="entity", cognitive_layer="semantic",
            content="Full node", space_id="default",
            strength=0.8, feedback_weight=0.6, confirmation_count=3,
            source_fragment_ids=["f1"], scope="global",
            entity_name="E1", entity_type="T1",
            ttl_seconds=3600, access_count=10, version=3,
            proof_count=5, visibility="public", created_by="user-1",
            domain_id="finance", schema_ref="finance:Entity",
        )
        meta = adapter._node_to_metadata(node)
        for field_name in ChromaDBAdapter._CHROMADB_MISSING_FIELDS:
            assert field_name not in meta

"""Tests for StorageInterface and StorageRouting."""

from __future__ import annotations

import pytest

from ontology_engine.storage.cognitive_interface import (
    SearchQuery,
    SearchResult,
    StorageInterface,
    StorageRouting,
)


class TestStorageRouting:
    """StorageRouting class tests."""

    def test_get_stores_fragment(self):
        assert StorageRouting.get_stores("fragment") == ["chromadb"]

    def test_get_stores_entity(self):
        assert StorageRouting.get_stores("entity") == ["sqlite", "chromadb"]

    def test_get_stores_relation(self):
        assert StorageRouting.get_stores("relation") == ["sqlite", "chromadb"]

    def test_get_stores_sqlite_only_types(self):
        sqlite_only = [
            "observation", "mental_model", "episode", "procedure",
            "rule", "opinion", "metrics",
        ]
        for mt in sqlite_only:
            assert StorageRouting.get_stores(mt) == ["sqlite"]

    def test_get_stores_oe_extensions(self):
        oe_types = ["commitment", "constraint", "self_experience", "task_state"]
        for mt in oe_types:
            assert StorageRouting.get_stores(mt) == ["sqlite"]

    def test_get_stores_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown memory_type"):
            StorageRouting.get_stores("nonexistent_type")

    def test_supports_store_true(self):
        assert StorageRouting.supports_store("entity", "sqlite") is True
        assert StorageRouting.supports_store("entity", "chromadb") is True
        assert StorageRouting.supports_store("fragment", "chromadb") is True

    def test_supports_store_false(self):
        assert StorageRouting.supports_store("fragment", "sqlite") is False
        assert StorageRouting.supports_store("observation", "chromadb") is False

    def test_supports_store_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown memory_type"):
            StorageRouting.supports_store("bogus", "sqlite")

    def test_all_memory_types_count(self):
        types = StorageRouting.all_memory_types()
        assert len(types) == 14

    def test_all_memory_types_sorted(self):
        types = StorageRouting.all_memory_types()
        assert types == sorted(types)

    def test_all_memory_types_contains_core(self):
        types = StorageRouting.all_memory_types()
        for mt in ["fragment", "entity", "relation", "observation", "mental_model"]:
            assert mt in types

    def test_all_memory_types_contains_oe_extensions(self):
        types = StorageRouting.all_memory_types()
        for mt in ["commitment", "constraint", "self_experience", "task_state"]:
            assert mt in types

    def test_all_stores(self):
        stores = StorageRouting.all_stores()
        assert stores == {"sqlite", "chromadb"}

    def test_routing_table_completeness(self):
        """All VALID_MEMORY_TYPES from models.py should be in ROUTING."""
        from ontology_engine.engine.cognitive.models import VALID_MEMORY_TYPES
        for mt in VALID_MEMORY_TYPES:
            assert mt in StorageRouting.ROUTING, f"{mt} not in StorageRouting.ROUTING"


class TestSearchQuery:
    """SearchQuery dataclass tests."""

    def test_minimal_creation(self):
        q = SearchQuery(query_text="test", space_id="default")
        assert q.query_text == "test"
        assert q.space_id == "default"
        assert q.top_k == 10
        assert q.memory_type is None
        assert q.vector is None

    def test_full_creation(self):
        q = SearchQuery(
            query_text="risk assessment",
            space_id="finance",
            top_k=20,
            memory_type="entity",
            cognitive_layer="semantic",
            tags_filter={"model": "world"},
            belief_status="accepted",
            vector=[0.1, 0.2, 0.3],
        )
        assert q.top_k == 20
        assert q.memory_type == "entity"
        assert q.cognitive_layer == "semantic"
        assert q.tags_filter == {"model": "world"}
        assert q.belief_status == "accepted"
        assert q.vector == [0.1, 0.2, 0.3]


class TestSearchResult:
    """SearchResult dataclass tests."""

    def test_minimal_creation(self):
        r = SearchResult(nodes=[])
        assert r.nodes == []
        assert r.scores == {}
        assert r.semantic_scores == {}
        assert r.keyword_scores == {}
        assert r.fusion_metadata == {}

    def test_with_data(self):
        r = SearchResult(
            nodes=["node1", "node2"],
            scores={"node1": 0.95, "node2": 0.80},
            semantic_scores={"node1": 0.90, "node2": 0.75},
            keyword_scores={"node1": 0.85, "node2": 0.70},
            fusion_metadata={"strategy": "rrf", "k": 60},
        )
        assert len(r.nodes) == 2
        assert r.scores["node1"] == 0.95
        assert r.fusion_metadata["strategy"] == "rrf"


class TestStorageInterface:
    """StorageInterface abstract contract tests."""

    def test_is_abstract(self):
        """StorageInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageInterface()

    def test_has_required_methods(self):
        """StorageInterface defines all required abstract methods."""
        abstract_methods = StorageInterface.__abstractmethods__
        assert "save_node" in abstract_methods
        assert "get_node" in abstract_methods
        assert "search" in abstract_methods
        assert "delete_node" in abstract_methods
        assert "batch_save" in abstract_methods
        assert "count" in abstract_methods

    def test_traverse_has_default_implementation(self):
        """traverse() has a default implementation (not abstract)."""
        assert "traverse" not in StorageInterface.__abstractmethods__

    def test_concrete_implementation_works(self):
        """A minimal concrete implementation can be instantiated."""
        class DummyStorage(StorageInterface):
            async def save_node(self, node): return "id"
            async def get_node(self, node_id): return None
            async def search(self, query): return SearchResult(nodes=[])
            async def delete_node(self, node_id, soft=True): pass
            async def batch_save(self, nodes): return []
            async def count(self, filter): return 0

        storage = DummyStorage()
        assert isinstance(storage, StorageInterface)

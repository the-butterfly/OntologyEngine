"""Tests for CognitiveStorage composite and RRF fusion."""

from __future__ import annotations

import pytest
import pytest_asyncio

from unittest.mock import AsyncMock

from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.storage.cognitive_interface import SearchQuery, SearchResult
from ontology_engine.storage.cognitive_storage import CognitiveStorage, _rrf_fuse
from ontology_engine.storage.sqlite.cognitive_adapter import SQLiteAdapter


def _make_node(node_id: str = "test-001", **kwargs) -> CognitiveNode:
    defaults = dict(
        id=node_id,
        memory_type="observation",
        cognitive_layer="semantic",
        content="Test content",
        space_id="default",
    )
    defaults.update(kwargs)
    return CognitiveNode(**defaults)


@pytest_asyncio.fixture
async def storage():
    sqlite = SQLiteAdapter(db_path=":memory:")
    await sqlite.initialize()
    s = CognitiveStorage(sqlite_adapter=sqlite)
    yield s
    await sqlite.close()


class TestCognitiveStorageRouting:
    @pytest.mark.asyncio
    async def test_save_observation_to_sqlite_only(self, storage):
        node = _make_node("r1", memory_type="observation")
        nid = await storage.save_node(node)
        assert nid == "r1"

        got = await storage.get_node("r1")
        assert got is not None

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, storage):
        got = await storage.get_node("nope")
        assert got is None

    @pytest.mark.asyncio
    async def test_delete_propagates_to_sqlite(self, storage):
        node = _make_node("d1")
        await storage.save_node(node)
        await storage.delete_node("d1", soft=True)

        got = await storage.get_node("d1")
        assert got is not None
        assert got.superseded_by == "deleted"


class TestCognitiveStorageSearch:
    @pytest.mark.asyncio
    async def test_search_sqlite_only(self, storage):
        await storage.batch_save([
            _make_node("s1", content="Apple fruit"),
            _make_node("s2", content="Apple company"),
        ])

        q = SearchQuery(query_text="", space_id="default")
        result = await storage.search(q)
        assert len(result.nodes) == 2


class TestRRFFusion:
    def test_fuse_two_result_sets(self):
        n1 = _make_node("a", content="doc A")
        n2 = _make_node("b", content="doc B")
        n3 = _make_node("c", content="doc C")

        sqlite = SearchResult(
            nodes=[n1, n2],
            scores={"a": 0.9, "b": 0.8},
        )
        chroma = SearchResult(
            nodes=[n2, n3],
            scores={"b": 0.85, "c": 0.7},
        )

        fused = _rrf_fuse(sqlite, chroma, top_k=3)
        assert len(fused.nodes) == 3
        assert "b" in fused.scores
        assert fused.fusion_metadata["strategy"] == "rrf"

    def test_fuse_with_overlap_boosts_shared(self):
        n1 = _make_node("x", content="shared")
        n2 = _make_node("y", content="only sqlite")
        n3 = _make_node("z", content="only chroma")

        sqlite = SearchResult(nodes=[n1, n2], scores={"x": 0.9, "y": 0.5})
        chroma = SearchResult(nodes=[n1, n3], scores={"x": 0.8, "z": 0.4})

        fused = _rrf_fuse(sqlite, chroma, top_k=3)
        shared_score = fused.scores.get("x", 0)
        sqlite_only_score = fused.scores.get("y", 0)
        chroma_only_score = fused.scores.get("z", 0)
        assert shared_score > sqlite_only_score
        assert shared_score > chroma_only_score

    def test_fuse_empty_chroma(self):
        n1 = _make_node("e1")
        sqlite = SearchResult(nodes=[n1], scores={"e1": 0.9})
        chroma = SearchResult(nodes=[])

        fused = _rrf_fuse(sqlite, chroma, top_k=5)
        assert len(fused.nodes) == 1

    def test_fuse_respects_top_k(self):
        nodes = [_make_node(f"tk-{i}") for i in range(20)]
        sqlite = SearchResult(nodes=nodes[:10], scores={n.id: 0.9 for n in nodes[:10]})
        chroma = SearchResult(nodes=nodes[10:], scores={n.id: 0.8 for n in nodes[10:]})

        fused = _rrf_fuse(sqlite, chroma, top_k=5)
        assert len(fused.nodes) == 5


class TestBatchSaveIDPreservation:
    @pytest.mark.asyncio
    async def test_batch_save_maps_ids_across_mixed_stores(self):
        sqlite_mock = AsyncMock()
        chromadb_mock = AsyncMock()
        storage = CognitiveStorage(sqlite_adapter=sqlite_mock, chromadb_adapter=chromadb_mock)

        nodes = [
            _make_node("obs-1", memory_type="observation"),
            _make_node("frag-1", memory_type="fragment"),
            _make_node("ent-1", memory_type="entity"),
            _make_node("mm-1", memory_type="mental_model"),
        ]

        sqlite_mock.batch_save.return_value = ["sqlite-obs-1", "sqlite-ent-1", "sqlite-mm-1"]
        chromadb_mock.batch_save.return_value = None

        result = await storage.batch_save(nodes)

        assert result == ["sqlite-obs-1", "frag-1", "sqlite-ent-1", "sqlite-mm-1"]

        sqlite_args = sqlite_mock.batch_save.call_args[0][0]
        assert [n.id for n in sqlite_args] == ["obs-1", "ent-1", "mm-1"]

        chroma_args = chromadb_mock.batch_save.call_args[0][0]
        assert [n.id for n in chroma_args] == ["frag-1", "ent-1"]

    @pytest.mark.asyncio
    async def test_batch_save_chromadb_only_retains_original_id(self):
        sqlite_mock = AsyncMock()
        chromadb_mock = AsyncMock()
        storage = CognitiveStorage(sqlite_adapter=sqlite_mock, chromadb_adapter=chromadb_mock)

        nodes = [
            _make_node("frag-a", memory_type="fragment"),
            _make_node("frag-b", memory_type="fragment"),
        ]

        sqlite_mock.batch_save.return_value = []
        chromadb_mock.batch_save.return_value = None

        result = await storage.batch_save(nodes)

        assert result == ["frag-a", "frag-b"]
        sqlite_mock.batch_save.assert_not_called()
        chromadb_mock.batch_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_save_entity_gets_sqlite_id_not_original(self):
        sqlite_mock = AsyncMock()
        chromadb_mock = AsyncMock()
        storage = CognitiveStorage(sqlite_adapter=sqlite_mock, chromadb_adapter=chromadb_mock)

        nodes = [
            _make_node("ent-x", memory_type="entity"),
        ]

        sqlite_mock.batch_save.return_value = ["sqlite-ent-x"]
        chromadb_mock.batch_save.return_value = None

        result = await storage.batch_save(nodes)

        assert result == ["sqlite-ent-x"]


class TestGetNodeSQLiteFallback:
    @pytest.mark.asyncio
    async def test_supplement_from_sqlite_when_chromadb_incomplete(self):
        sqlite_mock = AsyncMock()
        chromadb_mock = AsyncMock()
        storage = CognitiveStorage(sqlite_adapter=sqlite_mock, chromadb_adapter=chromadb_mock)

        complete_node = _make_node(
            "sup-1",
            strength=0.9,
            feedback_weight=0.7,
            confirmation_count=10,
            source_fragment_ids=["f1"],
            scope="global",
        )
        incomplete_node = _make_node("sup-1")

        sqlite_mock.get_node.side_effect = [None, complete_node]
        chromadb_mock.get_node.return_value = incomplete_node

        result = await storage.get_node("sup-1")
        assert result is not None
        assert result.strength == 0.9
        assert result.feedback_weight == 0.7
        assert result.confirmation_count == 10
        assert result.source_fragment_ids == ["f1"]
        assert result.scope == "global"

    @pytest.mark.asyncio
    async def test_returns_chromadb_node_when_sqlite_has_no_fallback(self):
        sqlite_mock = AsyncMock()
        chromadb_mock = AsyncMock()
        storage = CognitiveStorage(sqlite_adapter=sqlite_mock, chromadb_adapter=chromadb_mock)

        chroma_node = _make_node("frag-1", memory_type="fragment", strength=0.6)
        sqlite_mock.get_node.return_value = None
        chromadb_mock.get_node.return_value = chroma_node

        result = await storage.get_node("frag-1")
        assert result is not None
        assert result.id == "frag-1"
        assert result.strength == 0.6

    @pytest.mark.asyncio
    async def test_prefers_sqlite_when_both_stores_have_node(self):
        sqlite_mock = AsyncMock()
        chromadb_mock = AsyncMock()
        storage = CognitiveStorage(sqlite_adapter=sqlite_mock, chromadb_adapter=chromadb_mock)

        sqlite_node = _make_node("both-1", strength=0.95, confirmation_count=20)
        sqlite_mock.get_node.return_value = sqlite_node

        result = await storage.get_node("both-1")
        assert result is not None
        assert result.strength == 0.95
        assert result.confirmation_count == 20
        chromadb_mock.get_node.assert_not_called()

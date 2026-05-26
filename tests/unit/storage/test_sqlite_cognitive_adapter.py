"""Tests for SQLiteAdapter and ChromaDBAdapter."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.storage.cognitive_interface import SearchQuery, SearchResult
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
async def adapter():
    a = SQLiteAdapter(db_path=":memory:")
    await a.initialize()
    yield a
    await a.close()


class TestSQLiteAdapterCRUD:
    @pytest.mark.asyncio
    async def test_save_and_get(self, adapter):
        node = _make_node()
        nid = await adapter.save_node(node)
        assert nid == "test-001"

        got = await adapter.get_node("test-001")
        assert got is not None
        assert got.content == "Test content"
        assert got.memory_type == "observation"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, adapter):
        got = await adapter.get_node("nope")
        assert got is None

    @pytest.mark.asyncio
    async def test_update_overwrites(self, adapter):
        node = _make_node()
        await adapter.save_node(node)

        node.content = "Updated content"
        await adapter.save_node(node)

        got = await adapter.get_node("test-001")
        assert got.content == "Updated content"

    @pytest.mark.asyncio
    async def test_delete_soft(self, adapter):
        node = _make_node()
        await adapter.save_node(node)
        await adapter.delete_node("test-001", soft=True)

        got = await adapter.get_node("test-001")
        assert got is not None
        assert got.superseded_by == "deleted"

    @pytest.mark.asyncio
    async def test_delete_hard(self, adapter):
        node = _make_node()
        await adapter.save_node(node)
        await adapter.delete_node("test-001", soft=False)

        got = await adapter.get_node("test-001")
        assert got is None

    @pytest.mark.asyncio
    async def test_batch_save(self, adapter):
        nodes = [
            _make_node(f"b-{i}", content=f"Batch {i}")
            for i in range(5)
        ]
        ids = await adapter.batch_save(nodes)
        assert len(ids) == 5

        got = await adapter.get_node("b-3")
        assert got is not None
        assert got.content == "Batch 3"


class TestSQLiteAdapterSearch:
    @pytest.mark.asyncio
    async def test_search_by_space(self, adapter):
        await adapter.batch_save([
            _make_node("s1", content="Apple fruit", space_id="food"),
            _make_node("s2", content="Apple company", space_id="tech"),
        ])

        q = SearchQuery(query_text="", space_id="food")
        result = await adapter.search(q)
        assert len(result.nodes) == 1
        assert result.nodes[0].id == "s1"

    @pytest.mark.asyncio
    async def test_search_by_memory_type(self, adapter):
        await adapter.batch_save([
            _make_node("t1", content="Observation text", memory_type="observation"),
            _make_node("t2", content="Rule text", memory_type="rule"),
        ])

        q = SearchQuery(query_text="", space_id="default", memory_type="rule")
        result = await adapter.search(q)
        assert len(result.nodes) == 1
        assert result.nodes[0].memory_type == "rule"

    @pytest.mark.asyncio
    async def test_search_returns_scores(self, adapter):
        await adapter.save_node(_make_node("sc1"))

        q = SearchQuery(query_text="", space_id="default")
        result = await adapter.search(q)
        assert "sc1" in result.scores


class TestSQLiteAdapterCount:
    @pytest.mark.asyncio
    async def test_count_all(self, adapter):
        await adapter.batch_save([
            _make_node(f"c-{i}") for i in range(7)
        ])

        count = await adapter.count({})
        assert count == 7

    @pytest.mark.asyncio
    async def test_count_with_filter(self, adapter):
        await adapter.batch_save([
            _make_node("f1", memory_type="observation"),
            _make_node("f2", memory_type="rule"),
            _make_node("f3", memory_type="observation"),
        ])

        count = await adapter.count({"memory_type": "observation"})
        assert count == 2


class TestSQLiteAdapterTags:
    @pytest.mark.asyncio
    async def test_save_and_retrieve_tags(self, adapter):
        node = _make_node(
            "tag-1",
            tags={"model": "world", "domain": ["finance"]},
        )
        await adapter.save_node(node)

        got = await adapter.get_node("tag-1")
        assert got is not None
        assert got.tags["model"] == "world"


class TestSQLiteAdapterFTS5BM25:
    @pytest.mark.asyncio
    async def test_bm25_relevance_ordering_and_score_normalization(self, adapter):
        await adapter.batch_save([
            _make_node("bm25-hi", content="python python python python python"),
            _make_node("bm25-md", content="python programming language"),
            _make_node("bm25-lo", content="the python snake is a large reptile found in tropical regions"),
        ])

        q = SearchQuery(query_text="python", space_id="default")
        result = await adapter.search(q)

        assert len(result.nodes) == 3

        assert result.nodes[0].id == "bm25-hi"

        scores = [result.scores[n.id] for n in result.nodes]
        for s in scores:
            assert 0.0 <= s <= 1.0

        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

        assert scores[0] == 1.0
        assert scores[-1] == 0.0


class TestSQLiteAdapterConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_save_no_data_corruption(self, adapter):
        import asyncio

        async def _save(idx: int) -> str:
            node = _make_node(f"conc-{idx}", content=f"Concurrent {idx}")
            return await adapter.save_node(node)

        ids = await asyncio.gather(*[_save(i) for i in range(10)])

        assert len(ids) == 10
        count = await adapter.count({})
        assert count == 10

        for i in range(10):
            got = await adapter.get_node(f"conc-{i}")
            assert got is not None
            assert got.content == f"Concurrent {i}"

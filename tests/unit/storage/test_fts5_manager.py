from __future__ import annotations

import sqlite3

import pytest
import pytest_asyncio

from ontology_engine.storage.base import SearchResult
from ontology_engine.storage.local.fts5_manager import FTS5Manager


@pytest_asyncio.fixture
async def manager():
    conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
    fts = FTS5Manager(lambda: sqlite3.connect("file::memory:?cache=shared", uri=True))
    fts.ensure_tables()
    conn.close()
    return fts


@pytest.mark.asyncio
async def test_index_document_node(manager: FTS5Manager):
    await manager.index_document("node-1", "machine learning algorithms")
    results = await manager.search("machine learning")
    assert len(results) >= 1
    assert results[0].doc_id == "node-1"
    assert results[0].source_type == "node"


@pytest.mark.asyncio
async def test_index_document_fragment(manager: FTS5Manager):
    await manager.index_document(
        "frag-1",
        "deep learning neural networks",
        metadata={"source_type": "fragment"},
    )
    results = await manager.search("deep learning")
    assert len(results) >= 1
    assert results[0].doc_id == "frag-1"
    assert results[0].source_type == "fragment"


@pytest.mark.asyncio
async def test_search_returns_search_result(manager: FTS5Manager):
    await manager.index_document("doc-a", "quantum computing advances", metadata={"space_id": "physics"})
    await manager.index_document("doc-b", "classical computing history", metadata={"space_id": "physics"})
    results = await manager.search("computing", top_k=5, filters={"space_id": "physics"})
    assert len(results) >= 1
    for r in results:
        assert isinstance(r, SearchResult)
        assert isinstance(r.doc_id, str)
        assert isinstance(r.score, float)
        assert isinstance(r.source_type, str)
    doc_ids = {r.doc_id for r in results}
    assert "doc-a" in doc_ids or "doc-b" in doc_ids


@pytest.mark.asyncio
async def test_delete_document(manager: FTS5Manager):
    await manager.index_document("del-1", "temporary content to delete")
    results_before = await manager.search("temporary")
    assert len(results_before) >= 1
    await manager.delete_document("del-1")
    results_after = await manager.search("temporary")
    assert len(results_after) == 0


@pytest.mark.asyncio
async def test_rebuild_index(manager: FTS5Manager):
    await manager.index_document("rb-1", "content before rebuild")
    count = await manager.rebuild_index()
    assert count == 0
    results = await manager.search("content before rebuild")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_with_space_id_filter(manager: FTS5Manager):
    await manager.index_document("sp-1", "alpha data", metadata={"space_id": "space-alpha"})
    await manager.index_document("sp-2", "alpha data beta", metadata={"space_id": "space-beta"})
    results_alpha = await manager.search("alpha", filters={"space_id": "space-alpha"})
    assert all(r.doc_id == "sp-1" for r in results_alpha)
    results_beta = await manager.search("alpha", filters={"space_id": "space-beta"})
    assert all(r.doc_id == "sp-2" for r in results_beta)

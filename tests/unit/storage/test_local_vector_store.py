"""Tests for LocalVectorStore."""

from __future__ import annotations

import math

import pytest
import pytest_asyncio

from ontology_engine.storage.vector import LocalVectorStore
from ontology_engine.storage.base import StorageError


class TestLocalVectorStore:
    """Exercise LocalVectorStore behavior."""

    @pytest_asyncio.fixture
    async def store(self) -> LocalVectorStore:
        s = LocalVectorStore()
        await s.initialize(dimension=3)
        try:
            yield s
        finally:
            await s.close()

    @pytest.mark.asyncio
    async def test_initialize_and_close(self, store: LocalVectorStore) -> None:
        assert store._dimension == 3
        await store.close()
        assert store._dimension is None

    @pytest.mark.asyncio
    async def test_add_and_search(self, store: LocalVectorStore) -> None:
        await store.add_vectors(
            ids=["v1", "v2"],
            vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            metadata=[{"concept_type": "A"}, {"concept_type": "B"}],
        )

        results = await store.search(query_vector=[1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0].id == "v1"
        # Cosine similarity of identical vectors is 1.0
        assert math.isclose(results[0].score, 1.0, rel_tol=1e-9)

    @pytest.mark.asyncio
    async def test_search_with_metadata_filter(self, store: LocalVectorStore) -> None:
        await store.add_vectors(
            ids=["v1", "v2"],
            vectors=[[1.0, 0.0, 0.0], [0.99, 0.0, 0.0]],
            metadata=[{"concept_type": "A"}, {"concept_type": "B"}],
        )

        results = await store.search(
            query_vector=[1.0, 0.0, 0.0],
            top_k=10,
            filters={"concept_type": "B"},
        )
        assert len(results) == 1
        assert results[0].id == "v2"

    @pytest.mark.asyncio
    async def test_search_empty_store(self, store: LocalVectorStore) -> None:
        results = await store.search(query_vector=[1.0, 0.0, 0.0])
        assert results == []

    @pytest.mark.asyncio
    async def test_delete_vectors(self, store: LocalVectorStore) -> None:
        await store.add_vectors(
            ids=["v1", "v2"],
            vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        )
        await store.delete_vectors(["v1"])
        results = await store.search(query_vector=[1.0, 0.0, 0.0])
        assert len(results) == 1
        assert results[0].id == "v2"

    @pytest.mark.asyncio
    async def test_dimension_mismatch_on_add(self, store: LocalVectorStore) -> None:
        with pytest.raises(ValueError, match="dimension mismatch"):
            await store.add_vectors(ids=["v1"], vectors=[[1.0, 0.0]])

    @pytest.mark.asyncio
    async def test_dimension_mismatch_on_search(self, store: LocalVectorStore) -> None:
        with pytest.raises(ValueError, match="dimension mismatch"):
            await store.search(query_vector=[1.0, 0.0])

    @pytest.mark.asyncio
    async def test_uninitialized_store_raises(self) -> None:
        store = LocalVectorStore()
        with pytest.raises(StorageError, match="not initialized"):
            await store.add_vectors(ids=["v1"], vectors=[[1.0, 0.0, 0.0]])

    @pytest.mark.asyncio
    async def test_add_vectors_length_mismatch(self, store: LocalVectorStore) -> None:
        with pytest.raises(ValueError, match="same length"):
            await store.add_vectors(ids=["v1", "v2"], vectors=[[1.0, 0.0, 0.0]])

    @pytest.mark.asyncio
    async def test_add_vectors_metadata_length_mismatch(self, store: LocalVectorStore) -> None:
        with pytest.raises(ValueError, match="same length"):
            await store.add_vectors(
                ids=["v1", "v2"],
                vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                metadata=[{"concept_type": "A"}],
            )

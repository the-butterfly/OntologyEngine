from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from ontology_engine.engine.cognitive.cognitive_vector_index import (
    CognitiveVectorIndex,
    EmbeddingConfig,
)


class TestEmbeddingDegradation:
    @pytest.mark.asyncio
    async def test_index_node_does_not_raise_when_embedding_returns_none(self):
        config = EmbeddingConfig(provider="bm25")
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._initialized = True
        index._vector_store = None
        index._chroma_collection = None
        index._doc_freq.clear()
        index._total_docs = 0

        with patch.object(index, "_compute_embedding", return_value=None):
            await index.index_node(
                node_id="test-node-1",
                content="test content for BM25 indexing",
                memory_type="observation",
                tags=["test"],
                space_id="test-space",
            )

        assert index._total_docs == 1
        assert len(index._doc_freq) > 0

    @pytest.mark.asyncio
    async def test_index_node_still_indexes_bm25_when_embedding_returns_none(self):
        config = EmbeddingConfig(provider="bm25")
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._initialized = True
        index._vector_store = None
        index._chroma_collection = None
        index._doc_freq.clear()
        index._total_docs = 0

        with patch.object(index, "_compute_embedding", return_value=None):
            await index.index_node(
                node_id="node-bm25",
                content="华为是技术公司",
                memory_type="entity",
                tags=["华为"],
                space_id="test-space",
            )

        assert index._total_docs == 1
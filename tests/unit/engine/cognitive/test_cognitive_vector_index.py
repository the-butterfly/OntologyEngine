from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from ontology_engine.engine.cognitive.cognitive_vector_index import (
    CognitiveVectorIndex,
    EmbeddingConfig,
    DEFAULT_BM25_SEARCH_LIMIT,
    DEFAULT_ST_DIMENSION,
)


class TestEmbeddingConfig:
    """Test EmbeddingConfig dataclass and helpers."""

    def test_with_overrides_returns_new_instance(self):
        cfg = EmbeddingConfig(provider="bm25", dimension=384)
        overridden = cfg.with_overrides(provider="openai_compatible", base_url="http://localhost:9999/v1")
        assert overridden.provider == "openai_compatible"
        assert overridden.base_url == "http://localhost:9999/v1"
        assert overridden.dimension == 384
        assert overridden is not cfg

    def test_with_overrides_only_non_none(self):
        cfg = EmbeddingConfig(provider="bm25")
        overridden = cfg.with_overrides(provider="openai_compatible", base_url=None, dimension=768)
        assert overridden.provider == "openai_compatible"
        assert overridden.base_url is None
        assert overridden.dimension == 768

    def test_with_overrides_preserves_values_when_kwargs_none(self):
        cfg = EmbeddingConfig(provider="bm25", base_url="http://localhost:7852/v1", dimension=2560)
        overridden = cfg.with_overrides(provider=None)
        assert overridden.provider == "bm25"
        assert overridden.base_url == "http://localhost:7852/v1"

    def test_model_signature(self):
        cfg = EmbeddingConfig(provider="openai_compatible", model="text-embedding-3-small", dimension=1536)
        assert cfg.model_signature == "openai_compatible:text-embedding-3-small:1536"

    def test_model_signature_none_model(self):
        cfg = EmbeddingConfig(provider="bm25")
        assert cfg.model_signature == "bm25:none:384"

    def test_default_values(self):
        cfg = EmbeddingConfig()
        assert cfg.provider == "bm25"
        assert cfg.base_url is None
        assert cfg.api_key is None
        assert cfg.model is None
        assert cfg.dimension == DEFAULT_ST_DIMENSION
        assert cfg.persist_dir is None
        assert cfg.llm_api_key is None
        assert cfg.llm_base_url is None
        assert cfg.llm_model is None
        assert cfg.enable_llm_enhancement is False


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
                tags={"model": "observation"},
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
                tags={"model": "entity"},
                space_id="test-space",
            )

        assert index._total_docs == 1


class TestChromaDBInitialization:
    """Test ChromaDB init failure handling."""

    @pytest.fixture(autouse=True)
    def mock_chromadb_mod(self, monkeypatch):
        mock_mod = MagicMock()
        monkeypatch.setitem(sys.modules, "chromadb", mock_mod)
        return mock_mod

    def test_init_chroma_failure_logs_warning(self, mock_chromadb_mod):
        config = EmbeddingConfig(provider="openai_compatible", base_url="http://localhost:9999/v1",
                                  model="test-model", dimension=768)
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        mock_chromadb_mod.PersistentClient.side_effect = RuntimeError("ChromaDB is down")

        result = index._init_chroma("/tmp/fake_persist_dir")
        assert result is False

    def test_init_chroma_oserror_returns_false(self, mock_chromadb_mod):
        config = EmbeddingConfig(provider="openai_compatible", base_url="http://localhost:9999/v1",
                                  model="test-model", dimension=768)
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        mock_chromadb_mod.PersistentClient.side_effect = OSError("Permission denied")

        result = index._init_chroma("/tmp/fake_persist_dir")
        assert result is False

    def test_init_chroma_success(self, mock_chromadb_mod):
        config = EmbeddingConfig(provider="openai_compatible", base_url="http://localhost:9999/v1",
                                  model="test-model", dimension=768)
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        mock_collection = MagicMock()
        mock_chromadb_mod.PersistentClient.return_value.get_or_create_collection.return_value = mock_collection

        result = index._init_chroma("/tmp/fake_persist_dir")
        assert result is True
        assert index._chroma_collection is mock_collection

    def test_init_chroma_import_error_falls_back(self, mock_chromadb_mod):
        config = EmbeddingConfig(provider="openai_compatible", base_url="http://localhost:9999/v1",
                                  model="test-model", dimension=768)
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        mock_chromadb_mod.PersistentClient.side_effect = ImportError("chromadb not installed")

        result = index._init_chroma("/tmp/fake_persist_dir")
        assert result is False


class TestLLMDefaults:
    """Test LLM enhancement defaults are None, not hardcoded values."""

    def test_llm_defaults_are_none(self):
        cfg = EmbeddingConfig()
        assert cfg.llm_api_key is None
        assert cfg.llm_base_url is None
        assert cfg.llm_model is None
        assert cfg.enable_llm_enhancement is False

    def test_init_llm_client_skips_when_disabled(self):
        config = EmbeddingConfig(provider="bm25")
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._init_llm_client()
        assert index._llm_client is None

    def test_init_llm_client_skips_when_no_url_or_model(self):
        config = EmbeddingConfig(provider="bm25", enable_llm_enhancement=True)
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._init_llm_client()
        assert index._llm_client is None

    def test_init_llm_client_uses_config_values(self, monkeypatch):
        mock_httpx = MagicMock()
        monkeypatch.setitem(sys.modules, "httpx", mock_httpx)
        config = EmbeddingConfig(
            provider="bm25",
            enable_llm_enhancement=True,
            llm_base_url="http://llm:8000/v1",
            llm_model="gpt-4",
        )
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._init_llm_client()
        mock_httpx.AsyncClient.assert_called_once()
        assert index._llm_client is not None

    def test_init_llm_client_conditionally_adds_bearer(self, monkeypatch):
        mock_httpx = MagicMock()
        monkeypatch.setitem(sys.modules, "httpx", mock_httpx)
        config = EmbeddingConfig(
            provider="bm25",
            enable_llm_enhancement=True,
            llm_base_url="http://llm:8000/v1",
            llm_model="gpt-4",
            llm_api_key="sk-test-key",
        )
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._init_llm_client()
        call_kwargs = mock_httpx.AsyncClient.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer sk-test-key"

    def test_init_llm_client_no_bearer_when_no_key(self, monkeypatch):
        mock_httpx = MagicMock()
        monkeypatch.setitem(sys.modules, "httpx", mock_httpx)
        config = EmbeddingConfig(
            provider="bm25",
            enable_llm_enhancement=True,
            llm_base_url="http://llm:8000/v1",
            llm_model="gpt-4",
            llm_api_key=None,
        )
        mock_repo = AsyncMock()
        index = CognitiveVectorIndex(repository=mock_repo, config=config)
        index._init_llm_client()
        call_headers = mock_httpx.AsyncClient.call_args.kwargs["headers"]
        assert "Authorization" not in call_headers


class TestBM25SearchLimit:
    """Test BM25 search limit consistency."""

    @pytest.mark.asyncio
    async def test_rebuild_bm25_stats_uses_default_limit(self):
        config = EmbeddingConfig(provider="bm25")
        mock_repo = AsyncMock()
        mock_repo.query_nodes = AsyncMock(return_value=[])
        index = CognitiveVectorIndex(repository=mock_repo, config=config)

        await index._rebuild_bm25_stats("test_space")

        mock_repo.query_nodes.assert_awaited_once()
        assert mock_repo.query_nodes.await_args.kwargs["limit"] == DEFAULT_BM25_SEARCH_LIMIT

    @pytest.mark.asyncio
    async def test_default_bm25_search_limit_value(self):
        assert DEFAULT_BM25_SEARCH_LIMIT == 5000

    @pytest.mark.asyncio
    async def test_rebuild_bm25_stats_counts_tokens(self):
        from ontology_engine.engine.cognitive.models import CognitiveNode

        config = EmbeddingConfig(provider="bm25")
        mock_repo = AsyncMock()
        mock_repo.query_nodes = AsyncMock(return_value=[
            CognitiveNode(id="n1", memory_type="fragment", cognitive_layer="perception",
                          content="Apple is a company", domain_id="ts", space_id="ts"),
            CognitiveNode(id="n2", memory_type="fragment", cognitive_layer="perception",
                          content="Google is also a company", domain_id="ts", space_id="ts"),
        ])
        index = CognitiveVectorIndex(repository=mock_repo, config=config)

        await index._rebuild_bm25_stats("test_space")

        assert index._total_docs == 2
        assert len(index._doc_freq) > 0
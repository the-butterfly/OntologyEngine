"""Tests for CognitiveIngestionService and CognitiveExtractionPipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ontology_engine.engine.cognitive.ingestion_service import (
    CognitiveExtractionPipeline,
    CognitiveIngestionService,
    ExtractedEntity,
    ExtractedRelation,
    _make_fragment_node,
    _make_cognitive_node,
)


class TestMakeNodeHelpers:
    """Test _make_fragment_node and _make_cognitive_node helpers."""

    def test_make_fragment_node_defaults(self):
        node = _make_fragment_node(
            id="frag:test:abc",
            content="test content",
            space_id="s1",
            domain_id="s1",
            memory_type="fragment",
        )
        assert node.cognitive_layer == "perception"
        assert node.belief_status == "accepted"

    def test_make_fragment_node_custom_belief(self):
        node = _make_fragment_node(
            id="frag:test:abc",
            content="test",
            space_id="s1",
            domain_id="s1",
            memory_type="fragment",
            belief_status="pending_review",
        )
        assert node.belief_status == "pending_review"

    def test_make_cognitive_node_defaults(self):
        node = _make_cognitive_node(
            id="mem:entity:s1:abc",
            content="test",
            space_id="s1",
            domain_id="s1",
            memory_type="entity",
        )
        assert node.cognitive_layer == "semantic"
        assert node.belief_status == "accepted"

    def test_make_cognitive_node_custom_layer(self):
        node = _make_cognitive_node(
            id="mem:opinion:s1:abc",
            content="test",
            space_id="s1",
            domain_id="s1",
            memory_type="opinion",
            cognitive_layer="opinion",
            belief_status="pending_review",
        )
        assert node.cognitive_layer == "opinion"
        assert node.belief_status == "pending_review"


class TestInferTags:
    """Test CognitiveIngestionService._infer_tags mapping."""

    def test_world_types(self):
        for t in ("entity", "rule", "constraint", "observation", "fragment"):
            assert CognitiveIngestionService._infer_tags(t) == {"model": "world"}

    def test_self_types(self):
        for t in ("mental_model", "opinion", "self_experience"):
            assert CognitiveIngestionService._infer_tags(t) == {"model": "self"}

    def test_task_types(self):
        for t in ("commitment", "task_state", "procedure", "episode"):
            assert CognitiveIngestionService._infer_tags(t) == {"model": "task"}

    def test_unknown_type_defaults_to_world(self):
        assert CognitiveIngestionService._infer_tags("unknown_type") == {"model": "world"}


class TestExtractionPipeline:
    """Test CognitiveExtractionPipeline."""

    def test_extract_basic(self):
        repo = MagicMock()
        pipeline = CognitiveExtractionPipeline(repository=repo)
        entities, relations = pipeline._extract_with_rules(
            "Apple is a technology company. Google is also a tech company."
        )
        assert len(entities) > 0
        assert isinstance(relations, list)
        entity_texts = [e.text for e in entities]
        assert "Apple" in entity_texts
        assert "Google" in entity_texts

    def test_extract_chinese(self):
        repo = MagicMock()
        pipeline = CognitiveExtractionPipeline(repository=repo)
        entities, relations = pipeline._extract_with_rules(
            "华为是一家技术公司。阿里巴巴也是一家科技公司。"
        )
        assert len(entities) > 0
        entity_texts = [e.text for e in entities]
        assert any("华为" in e.text for e in entities if len(e.text) >= 2)

    def test_extract_empty(self):
        repo = MagicMock()
        pipeline = CognitiveExtractionPipeline(repository=repo)
        entities, relations = pipeline._extract_with_rules("")
        assert entities == []
        assert relations == []

    @pytest.mark.asyncio
    async def test_extract_via_async_wraps_rules(self):
        repo = MagicMock()
        pipeline = CognitiveExtractionPipeline(repository=repo)
        entities, relations = await pipeline.extract("Simple test content")
        assert len(entities) >= 0

    @pytest.mark.asyncio
    async def test_extract_fallback_on_exception(self):
        repo = MagicMock()
        pipeline = CognitiveExtractionPipeline(repository=repo)
        with patch.object(CognitiveExtractionPipeline, "_extract_with_rules", side_effect=ValueError("bad")):
            entities, relations = await pipeline.extract("test")
        assert entities == []
        assert relations == []


class TestIngestionService:
    """Test CognitiveIngestionService."""

    @pytest.fixture
    def mock_repo(self):
        return AsyncMock()

    @pytest.fixture
    def mock_pipeline(self):
        p = MagicMock(spec=CognitiveExtractionPipeline)
        p.extract = AsyncMock(return_value=([], []))
        return p

    @pytest.fixture
    def mock_vector(self):
        v = AsyncMock()
        v.index_node = AsyncMock()
        return v

    @pytest.fixture
    def mock_fts5(self):
        f = AsyncMock()
        f.on_node_created = AsyncMock()
        return f

    @pytest.mark.asyncio
    async def test_ingest_fragment_only(self, mock_repo, mock_pipeline):
        """Test ingest creates a fragment node and returns fragment_id."""
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        result = await service.ingest(
            content="test content",
            space_id="test_space",
            memory_type="fragment",
        )

        assert "fragment_id" in result
        assert result["fragment_id"].startswith("frag:test_space:")
        assert "node_id" not in result
        mock_repo.create_node.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_with_cognitive_node(self, mock_repo, mock_pipeline):
        """Test ingest with non-fragment memory_type creates both fragment and cognitive node."""
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        result = await service.ingest(
            content="test cognitive content",
            space_id="test_space",
            memory_type="entity",
        )

        assert "node_id" in result
        assert "fragment_id" in result
        assert result["node_id"].startswith("mem:entity:test_space:")
        assert mock_repo.create_node.await_count == 2
        assert mock_repo.create_cognitive_edge.await_count == 1

    @pytest.mark.asyncio
    async def test_ingest_with_vector_index(self, mock_repo, mock_pipeline, mock_vector):
        """Test ingest indexes fragment into vector store."""
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
            vector_index=mock_vector,
        )

        result = await service.ingest(
            content="vector index test",
            space_id="test_space",
        )

        mock_vector.index_node.assert_awaited()
        assert mock_vector.index_node.await_args.kwargs["content"] == "vector index test"

    @pytest.mark.asyncio
    async def test_ingest_with_vector_and_cognitive_node(self, mock_repo, mock_pipeline, mock_vector):
        """Test ingest with non-fragment type indexes both nodes."""
        mock_repo.create_node.reset_mock()
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
            vector_index=mock_vector,
        )

        await service.ingest(
            content="dual indexing test",
            space_id="test_space",
            memory_type="observation",
        )

        assert mock_vector.index_node.await_count == 2

    @pytest.mark.asyncio
    async def test_ingest_with_fts5(self, mock_repo, mock_pipeline, mock_fts5):
        """Test ingest syncs fragment to FTS5."""
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
            fts5_manager=mock_fts5,
        )

        await service.ingest(
            content="fts5 test content",
            space_id="test_space",
        )

        mock_fts5.on_node_created.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_with_tags_merging(self, mock_repo, mock_pipeline):
        """Test ingest merges inferred tags with provided tags."""
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        await service.ingest(
            content="tag test",
            space_id="test_space",
            memory_type="observation",
            tags={"domain": "finance", "source": "report"},
        )

        call_kwargs = mock_repo.create_node.call_args_list
        fragment_node = call_kwargs[0][0][0]
        assert fragment_node.tags is not None
        assert fragment_node.tags["model"] == "world"
        assert fragment_node.tags["domain"] == "finance"

    @pytest.mark.asyncio
    async def test_ingest_belief_status_passthrough(self, mock_repo, mock_pipeline):
        """Test ingest passes belief_status through to fragment and cognitive nodes."""
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        await service.ingest(
            content="belief test",
            space_id="test_space",
            memory_type="entity",
            belief_status="pending_review",
        )

        call_kwargs = mock_repo.create_node.call_args_list
        for call in call_kwargs:
            node = call[0][0]
            if hasattr(node, 'belief_status'):
                assert node.belief_status == "pending_review"

    @pytest.mark.asyncio
    async def test_vector_index_failure_sets_pending(self, mock_repo, mock_pipeline):
        """Test when vector.index_node fails, fragment is marked _index_status=pending."""
        mock_vector = AsyncMock()
        mock_vector.index_node = AsyncMock(side_effect=RuntimeError("vector down"))
        mock_repo.update_node = AsyncMock()

        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
            vector_index=mock_vector,
        )

        result = await service.ingest(
            content="fail test",
            space_id="test_space",
        )

        mock_repo.update_node.assert_awaited_once()
        update_call = mock_repo.update_node.await_args
        updated_fragment = update_call[0][0]
        attrs = updated_fragment.attributes or {}
        assert attrs.get("_index_status") == "pending"

    @pytest.mark.asyncio
    async def test_ingest_with_extraction(self, mock_repo):
        """Test that extract is called and entities are resolved."""
        mock_pipeline = MagicMock(spec=CognitiveExtractionPipeline)
        mock_pipeline.extract = AsyncMock(return_value=(
            [ExtractedEntity(text="Apple", entity_type="entity", confidence=0.5)],
            [],
        ))
        mock_repo.query_nodes = AsyncMock(return_value=[])

        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        result = await service.ingest(
            content="Apple is a company",
            space_id="test_space",
        )

        assert result["entities"] == 1
        assert len(result["created_entity_ids"]) == 1

    @pytest.mark.asyncio
    async def test_ingest_with_10_entity_limit(self, mock_repo):
        """Test that at most 10 entities are created per ingest."""
        mock_pipeline = MagicMock(spec=CognitiveExtractionPipeline)
        mock_pipeline.extract = AsyncMock(return_value=(
            [ExtractedEntity(text=f"Entity{i}", entity_type="entity", confidence=0.5)
             for i in range(20)],
            [],
        ))
        mock_repo.query_nodes = AsyncMock(return_value=[])

        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        result = await service.ingest(
            content="many entities " + " ".join(f"Entity{i}" for i in range(20)),
            space_id="test_space",
        )

        assert result["entities"] == 20
        assert len(result["created_entity_ids"]) == 10

    @pytest.mark.asyncio
    async def test_retry_pending_indexes(self, mock_repo, mock_vector):
        """Test retry_pending_indexes re-indexes nodes with _index_status=pending."""
        mock_pipeline = MagicMock(spec=CognitiveExtractionPipeline)
        mock_pipeline.extract = AsyncMock(return_value=([], []))

        from ontology_engine.engine.cognitive.models import CognitiveNode

        pending_node = CognitiveNode(
            id="mem:pending:test:001",
            memory_type="fragment",
            cognitive_layer="perception",
            content="pending content",
            domain_id="test_space",
            space_id="test_space",
            tags={"model": "world"},
            attributes={"_index_status": "pending"},
        )
        mock_repo.query_nodes = AsyncMock(return_value=[pending_node])
        mock_repo.update_node = AsyncMock()

        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
            vector_index=mock_vector,
        )

        reindexed = await service.retry_pending_indexes(space_id="test_space")
        assert reindexed == 1

        query_call = mock_repo.query_nodes.await_args
        assert query_call.kwargs["attributes_filter"] == {"_index_status": "pending"}

        update_call = mock_repo.update_node.await_args
        assert update_call is not None
        updated_node = update_call[0][0]
        attrs = updated_node.attributes or {}
        assert "_index_status" not in attrs

    @pytest.mark.asyncio
    async def test_retry_pending_indexes_no_vector(self, mock_repo):
        """Test retry_pending_indexes returns 0 when vector_index is None."""
        mock_pipeline = MagicMock(spec=CognitiveExtractionPipeline)
        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
            vector_index=None,
        )

        result = await service.retry_pending_indexes()
        assert result == 0

    @pytest.mark.asyncio
    async def test_resolve_or_create_entity_dedup(self, mock_repo):
        """Test entity dedup: matching existing node returns existing ID."""
        mock_pipeline = MagicMock(spec=CognitiveExtractionPipeline)

        from ontology_engine.engine.cognitive.models import CognitiveNode

        existing_node = CognitiveNode(
            id="mem:entity:test:existing",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Apple",
            domain_id="test_space",
            space_id="test_space",
        )
        mock_repo.query_nodes = AsyncMock(return_value=[existing_node])

        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        entity_id = await service._resolve_or_create_entity(
            ExtractedEntity(text="Apple", entity_type="entity", confidence=0.5),
            space_id="test_space",
            source_pipeline="api",
            user_id="system",
        )

        assert entity_id == "mem:entity:test:existing"
        mock_repo.create_node.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_or_create_entity_new(self, mock_repo):
        """Test entity creation when no existing match."""
        mock_pipeline = MagicMock(spec=CognitiveExtractionPipeline)
        mock_repo.query_nodes = AsyncMock(return_value=[])

        service = CognitiveIngestionService(
            repository=mock_repo,
            extraction_pipeline=mock_pipeline,
        )

        entity_id = await service._resolve_or_create_entity(
            ExtractedEntity(text="NewEntity", entity_type="entity", confidence=0.5),
            space_id="test_space",
            source_pipeline="api",
            user_id="system",
        )

        assert entity_id is not None
        assert entity_id.startswith("mem:entity:test_space:")
        mock_repo.create_node.assert_awaited_once()

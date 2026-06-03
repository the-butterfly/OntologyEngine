"""End-to-end storage integration tests.

Tests that verify storage operations work correctly across the full
stack: StorageConfig factory → concrete backends → DualWriteCoordinator
→ DefaultRetrievalBackend → CognitiveNode CRUD.

These tests require real storage backends (SQLite always available;
ladybug/chromadb optional). Tests that depend on optional backends are
skipped automatically when the backend is not installed.

Running:
    pytest tests/integration/test_storage_e2e.py -v
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from ontology_engine.storage.base import (
    EntityInstance,
    GraphStoreBackend,
    HybridSearchResult,
    RelationInstance,
    StorageBackend,
    VectorStoreBackend,
)
from ontology_engine.storage.config import StorageConfig, create_cognitive_store, create_graph_store, create_meta_store, create_vector_store
from ontology_engine.storage.dual_write import DualWriteCoordinator
from ontology_engine.storage.retrieval import DefaultRetrievalBackend

# ---------------------------------------------------------------------------
# Skip flags for optional backends
# ---------------------------------------------------------------------------

_ladybug_available = False
try:
    from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore  # noqa: F401

    _ladybug_available = True
except ImportError:
    pass

_chroma_available = False
try:
    from ontology_engine.storage.vector.chroma_store import ChromaVectorStore  # noqa: F401

    _chroma_available = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def meta_store(tmp_path: Path) -> StorageBackend:
    """Create an in-memory SQLite meta store."""
    store = create_meta_store(StorageConfig(sqlite_db_path=":memory:"))
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest_asyncio.fixture
async def graph_store(tmp_path: Path) -> GraphStoreBackend | None:
    """Create a NetworkX graph store (always available)."""
    config = StorageConfig(
        graph_backend="networkx",
        data_dir=str(tmp_path / "data"),
    )
    store = create_graph_store(config)
    await store.initialize()
    try:
        yield store
    finally:
        await store.close()


@pytest_asyncio.fixture
async def vector_store(tmp_path: Path) -> VectorStoreBackend | None:
    """Create a local vector store (always available)."""
    config = StorageConfig(
        vector_backend="local",
        data_dir=str(tmp_path / "data"),
    )
    store = create_vector_store(config)
    await store.initialize(dimension=128)
    try:
        yield store
    finally:
        await store.close()


@pytest_asyncio.fixture
async def dual_write(
    meta_store: StorageBackend,
    graph_store: GraphStoreBackend | None,
    vector_store: VectorStoreBackend | None,
) -> DualWriteCoordinator:
    """Create a DualWriteCoordinator with all available backends."""
    return DualWriteCoordinator(
        storage=meta_store,
        graph_store=graph_store,
        vector_store=vector_store,
    )


@pytest_asyncio.fixture
async def retrieval(
    meta_store: StorageBackend,
    graph_store: GraphStoreBackend | None,
    vector_store: VectorStoreBackend | None,
) -> DefaultRetrievalBackend:
    """Create a DefaultRetrievalBackend with all available backends."""
    return DefaultRetrievalBackend(
        storage=meta_store,
        graph_store=graph_store,
        vector_store=vector_store,
    )


# ---------------------------------------------------------------------------
# Test: StorageConfig factory functions
# ---------------------------------------------------------------------------


class TestStorageConfigFactory:
    """Test that StorageConfig can create all three backends."""

    @pytest.mark.asyncio
    async def test_create_meta_store_sqlite(self, tmp_path: Path):
        """StorageConfig with meta_backend='sqlite' creates a working SQLiteStorage."""
        config = StorageConfig(
            meta_backend="sqlite",
            sqlite_db_path=str(tmp_path / "test_meta.db"),
        )
        store = create_meta_store(config)
        assert isinstance(store, StorageBackend)
        await store.initialize()
        try:
            entity = EntityInstance(
                _fact_object="Company",
                entity_id="test-company-1",
                data={"name": "TestCorp"},
            )
            eid = await store.save_entity(entity)
            assert eid == "test-company-1"
            retrieved = await store.get_entity("Company", "test-company-1")
            assert retrieved is not None
            assert retrieved.entity_id == "test-company-1"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_create_graph_store_networkx(self, tmp_path: Path):
        """StorageConfig with graph_backend='networkx' creates a working NetworkXGraphStore."""
        config = StorageConfig(
            graph_backend="networkx",
            data_dir=str(tmp_path / "data"),
        )
        store = create_graph_store(config)
        assert isinstance(store, GraphStoreBackend)
        await store.initialize()
        try:
            await store.upsert_node("n1", ["Entity"], {"name": "Node1"})
            node = await store.get_node("n1")
            assert node is not None
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_create_vector_store_local(self, tmp_path: Path):
        """StorageConfig with vector_backend='local' creates a working LocalVectorStore."""
        config = StorageConfig(
            vector_backend="local",
            data_dir=str(tmp_path / "data"),
        )
        store = create_vector_store(config)
        assert isinstance(store, VectorStoreBackend)
        await store.initialize(dimension=128)
        try:
            await store.add_vectors(
                ids=["v1"],
                vectors=[[0.1] * 128],
                metadata=[{"label": "test"}],
            )
            results = await store.search([0.1] * 128, top_k=1)
            assert len(results) >= 1
            assert results[0].id == "v1"
        finally:
            await store.close()

    @pytest.mark.skipif(not _ladybug_available, reason="ladybug not installed")
    @pytest.mark.asyncio
    async def test_create_graph_store_ladybug(self, tmp_path: Path):
        """StorageConfig with graph_backend='ladybug' creates a working LadybugGraphStore."""
        config = StorageConfig(
            graph_backend="ladybug",
            data_dir=str(tmp_path / "data"),
        )
        store = create_graph_store(config)
        assert isinstance(store, GraphStoreBackend)
        await store.initialize()
        try:
            pass  # LadybugGraphStore initialized successfully
        finally:
            await store.close()

    @pytest.mark.skipif(not _chroma_available, reason="chromadb not installed")
    @pytest.mark.asyncio
    async def test_create_vector_store_chroma(self, tmp_path: Path):
        """StorageConfig with vector_backend='chroma' creates a ChromaVectorStore.

        Note: This test only verifies instantiation. ChromaVectorStore.initialize()
        may try to download embedding models, so we skip the full initialization
        in CI/offline environments.
        """
        config = StorageConfig(
            vector_backend="chroma",
            chroma_persist_dir=str(tmp_path / "chroma"),
        )
        store = create_vector_store(config)
        assert isinstance(store, VectorStoreBackend)


# ---------------------------------------------------------------------------
# Test: DualWriteCoordinator
# ---------------------------------------------------------------------------


class TestDualWriteCoordinator:
    """Test that DualWriteCoordinator correctly writes to multiple backends."""

    @pytest.mark.asyncio
    async def test_write_entity_to_meta_store(
        self, dual_write: DualWriteCoordinator, meta_store: StorageBackend
    ):
        """Writing an entity via DualWriteCoordinator persists it in MetaStore."""
        entity = EntityInstance(
            _fact_object="Company",
            entity_id="dw-company-1",
            data={"name": "DualWriteCorp"},
        )
        entity_id = await dual_write.write_entity(entity)
        assert entity_id == "dw-company-1"

        # Verify in MetaStore
        retrieved = await meta_store.get_entity("Company", "dw-company-1")
        assert retrieved is not None
        assert retrieved.entity_id == "dw-company-1"

    @pytest.mark.asyncio
    async def test_write_entity_syncs_to_graph(
        self, dual_write: DualWriteCoordinator, graph_store: GraphStoreBackend | None
    ):
        """Writing an entity via DualWriteCoordinator syncs it to GraphStore."""
        if graph_store is None:
            pytest.skip("GraphStore not available")

        entity = EntityInstance(
            _fact_object="Company",
            entity_id="dw-company-2",
            data={"name": "GraphSyncCorp"},
        )
        await dual_write.write_entity(entity)

        # Verify in GraphStore
        node = await graph_store.get_node("dw-company-2")
        assert node is not None

    @pytest.mark.asyncio
    async def test_write_entity_with_relations(
        self, dual_write: DualWriteCoordinator, meta_store: StorageBackend
    ):
        """Writing entity + relations via DualWriteCoordinator persists both."""
        entity = EntityInstance(
            _fact_object="Company",
            entity_id="dw-company-3",
            data={"name": "RelCorp"},
        )
        rel = RelationInstance(
            relation_name="SUPPLIES",
            from_entity_id="dw-company-3",
            to_entity_id="dw-company-4",
            data={"volume": 1000},
        )
        entity_id = await dual_write.save_entity_with_graph(entity, relations=[rel])
        assert entity_id == "dw-company-3"

        # Verify relation in MetaStore
        rels = await meta_store.get_relations("dw-company-3")
        assert len(rels) >= 1

    @pytest.mark.asyncio
    async def test_graph_failure_does_not_block_meta_write(
        self, meta_store: StorageBackend
    ):
        """If GraphStore fails, MetaStore write still succeeds (eventual consistency)."""
        coordinator = DualWriteCoordinator(
            storage=meta_store,
            graph_store=None,  # Simulate unavailable graph
            vector_store=None,
        )
        entity = EntityInstance(
            _fact_object="Company",
            entity_id="dw-resilient",
            data={"name": "ResilientCorp"},
        )
        entity_id = await coordinator.write_entity(entity)
        assert entity_id == "dw-resilient"

        retrieved = await meta_store.get_entity("Company", "dw-resilient")
        assert retrieved is not None


# ---------------------------------------------------------------------------
# Test: DefaultRetrievalBackend
# ---------------------------------------------------------------------------


class TestDefaultRetrievalBackend:
    """Test that DefaultRetrievalBackend can perform hybrid search."""

    @pytest.mark.asyncio
    async def test_hybrid_search_without_optional_backends(
        self, meta_store: StorageBackend
    ):
        """Hybrid search works even without graph/vector backends (degraded mode)."""
        retrieval = DefaultRetrievalBackend(
            storage=meta_store,
            graph_store=None,
            vector_store=None,
        )
        result = await retrieval.hybrid_search(
            query_text=None,
            query_vector=None,
            top_k=10,
        )
        assert isinstance(result, HybridSearchResult)
        assert result.results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_with_vector(
        self,
        meta_store: StorageBackend,
        vector_store: VectorStoreBackend,
    ):
        """Hybrid search with vector backend returns semantic results."""
        # Index a vector
        await vector_store.add_vectors(
            ids=["entity-1"],
            vectors=[[0.5] * 128],
            metadata=[{"fact_object": "Company"}],
        )

        retrieval = DefaultRetrievalBackend(
            storage=meta_store,
            graph_store=None,
            vector_store=vector_store,
            embedder=lambda text: [0.5] * 128,  # Dummy embedder
        )
        result = await retrieval.hybrid_search(
            query_text="test query",
            top_k=10,
        )
        assert isinstance(result, HybridSearchResult)
        assert len(result.results) >= 1

    @pytest.mark.asyncio
    async def test_semantic_search_requires_embedder(
        self,
        meta_store: StorageBackend,
        vector_store: VectorStoreBackend,
    ):
        """semantic_search raises NotImplementedError when no embedder is configured."""
        retrieval = DefaultRetrievalBackend(
            storage=meta_store,
            graph_store=None,
            vector_store=vector_store,
            embedder=None,
        )
        with pytest.raises(NotImplementedError, match="embedder"):
            await retrieval.semantic_search("test query")

    @pytest.mark.asyncio
    async def test_graph_pattern_match_fallback(
        self, meta_store: StorageBackend
    ):
        """graph_pattern_match falls back to MetaStore when no GraphStore."""
        # Save an entity for pattern matching
        entity = EntityInstance(
            _fact_object="Company",
            entity_id="pattern-company",
            data={"name": "PatternCorp"},
        )
        await meta_store.save_entity(entity)

        retrieval = DefaultRetrievalBackend(
            storage=meta_store,
            graph_store=None,
            vector_store=None,
        )
        # Degenerate case: empty path_pattern just queries start nodes
        results = await retrieval.graph_pattern_match(
            start_concept="Company",
            path_pattern=[],
            limit=10,
        )
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Test: CognitiveNode CRUD through full stack (requires LadybugGraphStore)
# ---------------------------------------------------------------------------


class TestCognitiveNodeFullStack:
    """Test cognitive node CRUD through the full stack.

    These tests require LadybugGraphStore (ladybug package) because
    LadybugGraphStore now directly implements CognitiveStorageBackend.
    NetworkXGraphStore does not implement the cognitive node API.
    """

    @pytest.mark.skipif(not _ladybug_available, reason="ladybug not installed")
    @pytest.mark.asyncio
    async def test_cognitive_node_crud_via_cognitive_storage(
        self, tmp_path: Path
    ):
        """CognitiveNode CRUD works through CognitiveStorageBackend → LadybugGraphStore."""
        config = StorageConfig(
            graph_backend="ladybug",
            data_dir=str(tmp_path / "data"),
        )
        store = create_cognitive_store(config)
        await store.initialize()
        try:
            # Create
            node_data: dict[str, Any] = {
                "id": "cog-node-1",
                "memory_type": "observation",
                "cognitive_layer": "opinion",
                "content": "Test observation content",
                "space_id": "test-space",
                "belief_status": "accepted",
            }
            await store.save_cognitive_node(node_data)

            # Read
            retrieved = await store.get_cognitive_node("cog-node-1")
            assert retrieved is not None
            assert retrieved.get("id") == "cog-node-1"

            # List
            nodes = await store.list_cognitive_nodes(space_id="test-space")
            assert isinstance(nodes, list)

            # Delete
            await store.delete_cognitive_node("cog-node-1")
        finally:
            await store.close()

    @pytest.mark.skipif(not _ladybug_available, reason="ladybug not installed")
    @pytest.mark.asyncio
    async def test_cognitive_edge_crud_via_cognitive_storage(
        self, tmp_path: Path
    ):
        """CognitiveEdge CRUD works through CognitiveStorageBackend."""
        config = StorageConfig(
            graph_backend="ladybug",
            data_dir=str(tmp_path / "data"),
        )
        store = create_cognitive_store(config)
        await store.initialize()
        try:
            # Create two nodes first
            for i in range(2):
                await store.save_cognitive_node({
                    "id": f"cog-node-e{i}",
                    "memory_type": "entity",
                    "cognitive_layer": "semantic",
                    "content": f"Entity {i}",
                    "space_id": "test-space",
                })

            # Create edge
            edge = await store.save_cognitive_edge(
                edge_type="SUPPORTS",
                from_id="cog-node-e0",
                to_id="cog-node-e1",
            )
            assert isinstance(edge, dict)

            # List edges
            edges = await store.list_cognitive_edges(from_id="cog-node-e0")
            assert isinstance(edges, list)
        finally:
            await store.close()

    @pytest.mark.skipif(not _ladybug_available, reason="ladybug not installed")
    @pytest.mark.asyncio
    async def test_disposition_crud_via_cognitive_storage(
        self, tmp_path: Path
    ):
        """DispositionProfile CRUD works through CognitiveStorageBackend."""
        config = StorageConfig(
            graph_backend="ladybug",
            data_dir=str(tmp_path / "data"),
        )
        store = create_cognitive_store(config)
        await store.initialize()
        try:
            # Save disposition
            profile_data: dict[str, Any] = {
                "id": "disp-default",
                "scene": "default",
                "skepticism": 0.5,
                "evidence_demand": 0.5,
                "space_id": "test-space",
            }
            await store.save_disposition(profile_data)

            # Get disposition
            profile = await store.get_disposition(profile_id="disp-default")
            assert profile is not None
        finally:
            await store.close()

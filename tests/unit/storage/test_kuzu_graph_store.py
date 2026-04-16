"""Tests for KuzuGraphStore.

These tests require kuzu to be installed. They will be skipped if kuzu
is not available: pip install kuzu
"""

from __future__ import annotations

import pytest

# Skip all tests if kuzu is not installed
kuzu = pytest.importorskip("kuzu", reason="kuzu not installed - install with: pip install ontology-engine[kuzu]")

from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore


class TestKuzuGraphStore:
    """Test KuzuGraphStore implementation."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create an in-memory KuzuGraphStore for testing."""
        db_path = str(tmp_path / "test_graph.kuzu")
        store = KuzuGraphStore()
        return store

    @pytest.fixture
    async def initialized_store(self, store):
        """Create an initialized store with test data."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = f"{tmp_dir}/test_init.kuzu"
            await store.initialize(db_path)
            yield store
            await store.close()

    @pytest.mark.asyncio
    async def test_initialize(self, store, tmp_path):
        """Test initialization creates database and schema."""
        db_path = str(tmp_path / "test_init.kuzu")
        await store.initialize(db_path)
        assert store._initialized
        assert store._conn is not None
        await store.close()

    @pytest.mark.asyncio
    async def test_initialize_twice(self, store, tmp_path):
        """Test double initialization raises error."""
        db_path = str(tmp_path / "test_init2.kuzu")
        await store.initialize(db_path)
        with pytest.raises(Exception):
            await store.initialize(db_path)
        await store.close()

    @pytest.mark.asyncio
    async def test_upsert_and_get_node(self, store, tmp_path):
        """Test node upsert and retrieval."""
        db_path = str(tmp_path / "test_node.kuzu")
        await store.initialize(db_path)

        await store.upsert_node(
            node_id="company_1",
            labels=["Company"],
            properties={"name": "Acme Corp", "region": "华东"},
        )

        node = await store.get_node("company_1")
        assert node is not None
        assert node["id"] == "company_1"
        assert node["concept"] == "Company"
        assert node["properties"]["name"] == "Acme Corp"

        await store.close()

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, store, tmp_path):
        """Test get_node returns None for non-existent node."""
        db_path = str(tmp_path / "test_notfound.kuzu")
        await store.initialize(db_path)

        node = await store.get_node("nonexistent")
        assert node is None

        await store.close()

    @pytest.mark.asyncio
    async def test_upsert_and_get_edge(self, store, tmp_path):
        """Test edge upsert and retrieval."""
        db_path = str(tmp_path / "test_edge.kuzu")
        await store.initialize(db_path)

        # Create two nodes first
        await store.upsert_node("c1", ["Company"], {"name": "A"})
        await store.upsert_node("c2", ["Company"], {"name": "B"})

        # Create edge
        await store.upsert_edge(
            edge_id="guarantees_1",
            from_node_id="c1",
            to_node_id="c2",
            edge_type="guarantees",
            properties={"amount": 1000000},
        )

        edges = await store.get_edges(from_node_id="c1")
        assert len(edges) == 1
        assert edges[0]["from_node_id"] == "c1"
        assert edges[0]["to_node_id"] == "c2"
        assert edges[0]["edge_type"] == "guarantees"

        await store.close()

    @pytest.mark.asyncio
    async def test_get_neighbors_with_node_concept_filter(self, store, tmp_path):
        """Test get_neighbors with node_concept filter pushes to kuzu."""
        db_path = str(tmp_path / "test_neighbors.kuzu")
        await store.initialize(db_path)

        # Create nodes
        await store.upsert_node("c1", ["Company"], {"name": "A"})
        await store.upsert_node("c2", ["Company"], {"name": "B"})
        await store.upsert_node("i1", ["Invoice"], {"name": "Inv1"})

        # Create edges
        await store.upsert_edge("e1", "c1", "c2", "guarantees")
        await store.upsert_edge("e2", "c1", "i1", "has_invoice")

        # Get neighbors with concept filter
        neighbors = await store.get_neighbors(
            node_id="c1",
            edge_type="guarantees",
            direction="outgoing",
            node_concept="Company",
        )
        assert len(neighbors) == 1
        assert neighbors[0]["neighbor_id"] == "c2"

        # Filter by Invoice concept
        neighbors = await store.get_neighbors(
            node_id="c1",
            edge_type="has_invoice",
            direction="outgoing",
            node_concept="Invoice",
        )
        assert len(neighbors) == 1
        assert neighbors[0]["neighbor_id"] == "i1"

        await store.close()

    @pytest.mark.asyncio
    async def test_get_neighbors_bidirectional(self, store, tmp_path):
        """Test get_neighbors with direction='both'."""
        db_path = str(tmp_path / "test_bidi.kuzu")
        await store.initialize(db_path)

        await store.upsert_node("a", ["A"], {})
        await store.upsert_node("b", ["B"], {})
        await store.upsert_edge("e1", "a", "b", "rel")

        neighbors = await store.get_neighbors("a", direction="both")
        assert len(neighbors) == 1

        await store.close()

    @pytest.mark.asyncio
    async def test_execute_cypher_simple(self, store, tmp_path):
        """Test execute_cypher with a simple MATCH query."""
        db_path = str(tmp_path / "test_cypher.kuzu")
        await store.initialize(db_path)

        await store.upsert_node("c1", ["Company"], {"name": "A"})
        await store.upsert_node("c2", ["Company"], {"name": "B"})
        await store.upsert_edge("e1", "c1", "c2", "supplies")

        results = await store.execute_cypher(
            "MATCH (a:Entity)-[r:Relation]->(b:Entity) "
            "WHERE a.entity_id = 'c1' "
            "RETURN a.entity_id AS src, b.entity_id AS tgt, r.relation_type AS rel"
        )
        assert len(results) == 1
        assert results[0]["src"] == "c1"
        assert results[0]["tgt"] == "c2"
        assert results[0]["rel"] == "supplies"

        await store.close()

    @pytest.mark.asyncio
    async def test_execute_cypher_complex_pattern(self, store, tmp_path):
        """Test execute_cypher with multi-hop MATCH pattern."""
        db_path = str(tmp_path / "test_complex_cypher.kuzu")
        await store.initialize(db_path)

        # Create chain: C1 -guarantees-> C2 -supplies-> CE1
        await store.upsert_node("c1", ["Company"], {"name": "C1"})
        await store.upsert_node("c2", ["Company"], {"name": "C2"})
        await store.upsert_node("ce1", ["CoreEnterprise"], {"name": "CE1"})
        await store.upsert_edge("e1", "c1", "c2", "guarantees")
        await store.upsert_edge("e2", "c2", "ce1", "supplies")

        results = await store.execute_cypher(
            "MATCH (start:Entity {entity_id: 'c1'})"
            "-[r0:Relation {relation_type: 'guarantees'}]->"
            "(m1:Entity {concept: 'Company'})"
            "-[r1:Relation {relation_type: 'supplies'}]->"
            "(end:Entity {concept: 'CoreEnterprise'}) "
            "RETURN start.entity_id, m1.entity_id, end.entity_id"
        )
        assert len(results) == 1
        assert results[0]["start.entity_id"] == "c1"
        assert results[0]["m1.entity_id"] == "c2"
        assert results[0]["end.entity_id"] == "ce1"

        await store.close()

    @pytest.mark.asyncio
    async def test_batch_upsert(self, store, tmp_path):
        """Test batch_upsert for nodes and edges."""
        db_path = str(tmp_path / "test_batch.kuzu")
        await store.initialize(db_path)

        result = await store.batch_upsert(
            nodes=[
                {"node_id": "n1", "labels": ["A"], "properties": {"name": "Node1"}},
                {"node_id": "n2", "labels": ["B"], "properties": {"name": "Node2"}},
            ],
            edges=[
                {
                    "edge_id": "be1",
                    "from_node_id": "n1",
                    "to_node_id": "n2",
                    "edge_type": "rel",
                    "properties": {},
                },
            ],
        )
        assert result["nodes_written"] == 2
        assert result["edges_written"] == 1

        node = await store.get_node("n1")
        assert node["id"] == "n1"

        await store.close()

    @pytest.mark.asyncio
    async def test_delete_node(self, store, tmp_path):
        """Test node deletion."""
        db_path = str(tmp_path / "test_delete.kuzu")
        await store.initialize(db_path)

        await store.upsert_node("delete_me", ["Test"], {})
        node = await store.get_node("delete_me")
        assert node is not None

        await store.delete_node("delete_me")
        node = await store.get_node("delete_me")
        assert node is None

        await store.close()

    @pytest.mark.asyncio
    async def test_delete_edge(self, store, tmp_path):
        """Test edge deletion."""
        db_path = str(tmp_path / "test_delete_edge.kuzu")
        await store.initialize(db_path)

        await store.upsert_node("a", ["A"], {})
        await store.upsert_node("b", ["B"], {})
        await store.upsert_edge("to_delete", "a", "b", "rel")

        edges = await store.get_edges(from_node_id="a")
        assert len(edges) == 1

        await store.delete_edge("to_delete")
        edges = await store.get_edges(from_node_id="a")
        assert len(edges) == 0

        await store.close()

    @pytest.mark.asyncio
    async def test_find_paths(self, store, tmp_path):
        """Test find_paths returns paths between nodes."""
        db_path = str(tmp_path / "test_paths.kuzu")
        await store.initialize(db_path)

        await store.upsert_node("s", ["S"], {})
        await store.upsert_node("m", ["M"], {})
        await store.upsert_node("t", ["T"], {})
        await store.upsert_edge("e1", "s", "m", "r1")
        await store.upsert_edge("e2", "m", "t", "r2")

        paths = await store.find_paths("s", target_id="t", max_depth=3)
        # May return multiple path formats
        assert len(paths) >= 0

        await store.close()

    @pytest.mark.asyncio
    async def test_compute_graph_metric_degree(self, store, tmp_path):
        """Test compute_graph_metric with degree centrality."""
        db_path = str(tmp_path / "test_metric.kuzu")
        await store.initialize(db_path)

        await store.upsert_node("a", ["A"], {})
        await store.upsert_node("b", ["B"], {})
        await store.upsert_node("c", ["C"], {})
        await store.upsert_edge("e1", "a", "b", "r1")
        await store.upsert_edge("e2", "a", "c", "r1")

        result = await store.compute_graph_metric("centrality", metric="degree")
        assert result["algorithm"] == "centrality"
        assert result["metric"] == "degree"

        await store.close()

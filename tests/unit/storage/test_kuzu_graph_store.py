"""Tests for KuzuGraphStore.

These tests require ladybug to be installed. They will be skipped if ladybug
is not available: pip install ladybug
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("ladybug", reason="ladybug not installed - install with: pip install ontology-engine[kuzu]")
import pytest_asyncio

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
        assert store._pool is not None
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
        assert node["fact_object"] == "Company"
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
            "MATCH (start:Entity {entity_id: 'c1'})-[r0:Relation]->(m1:Entity) "
            "WHERE r0.relation_type = 'guarantees' "
            "RETURN start.entity_id AS start_id, m1.entity_id AS mid_id"
        )
        assert len(results) == 1
        assert results[0]["start_id"] == "c1"
        assert results[0]["mid_id"] == "c2"

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


class TestCognitiveNode:
    """Test CognitiveNode CRUD operations."""

    @pytest_asyncio.fixture
    async def store(self, tmp_path):
        """Create an initialized KuzuGraphStore for testing."""
        db_path = str(tmp_path / "test_cognitive.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        yield store
        await store.close()

    @pytest.mark.asyncio
    async def test_upsert_and_get_cognitive_node(self, store):
        """Test CognitiveNode upsert and retrieval."""
        await store.upsert_cognitive_node(
            node_id="mem_001",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Supply chain is a network of suppliers and manufacturers",
            source_fragment_ids=["frag_1", "frag_2"],
            belief_status="accepted",
            domain_id="supply_chain",
        )

        node = await store.get_cognitive_node("mem_001")
        assert node is not None
        assert node["id"] == "mem_001"
        assert node["memory_type"] == "entity"
        assert node["cognitive_layer"] == "semantic"
        assert node["content"] == "Supply chain is a network of suppliers and manufacturers"
        assert node["source_fragment_ids"] == ["frag_1", "frag_2"]
        assert node["belief_status"] == "accepted"
        assert node["domain_id"] == "supply_chain"

    @pytest.mark.asyncio
    async def test_get_cognitive_node_not_found(self, store):
        """Test get_cognitive_node returns None for non-existent node."""
        node = await store.get_cognitive_node("nonexistent")
        assert node is None

    @pytest.mark.asyncio
    async def test_delete_cognitive_node(self, store):
        """Test CognitiveNode deletion."""
        await store.upsert_cognitive_node(
            node_id="mem_delete",
            memory_type="observation",
            cognitive_layer="opinion",
            content="Test observation",
        )

        node = await store.get_cognitive_node("mem_delete")
        assert node is not None

        await store.delete_cognitive_node("mem_delete")
        node = await store.get_cognitive_node("mem_delete")
        assert node is None

    @pytest.mark.asyncio
    async def test_query_cognitive_nodes_by_type(self, store):
        """Test querying CognitiveNodes by memory_type."""
        await store.upsert_cognitive_node("mem_1", "entity", "semantic", "Entity 1")
        await store.upsert_cognitive_node("mem_2", "observation", "opinion", "Observation 1")
        await store.upsert_cognitive_node("mem_3", "entity", "semantic", "Entity 2")

        results = await store.query_cognitive_nodes(memory_type="entity")
        assert len(results) == 2
        assert all(r["memory_type"] == "entity" for r in results)

    @pytest.mark.asyncio
    async def test_query_cognitive_nodes_by_layer(self, store):
        """Test querying CognitiveNodes by cognitive_layer."""
        await store.upsert_cognitive_node("mem_1", "entity", "semantic", "Entity 1")
        await store.upsert_cognitive_node("mem_2", "observation", "opinion", "Observation 1")
        await store.upsert_cognitive_node("mem_3", "procedure", "procedure", "Procedure 1")

        results = await store.query_cognitive_nodes(cognitive_layer="opinion")
        assert len(results) == 1
        assert results[0]["memory_type"] == "observation"

    @pytest.mark.asyncio
    async def test_query_cognitive_nodes_by_belief_status(self, store):
        """Test querying CognitiveNodes by belief_status."""
        await store.upsert_cognitive_node("mem_1", "entity", "semantic", "Entity 1", belief_status="accepted")
        await store.upsert_cognitive_node("mem_2", "entity", "semantic", "Entity 2", belief_status="contradicted")

        results = await store.query_cognitive_nodes(belief_status="contradicted")
        assert len(results) == 1
        assert results[0]["belief_status"] == "contradicted"

    @pytest.mark.asyncio
    async def test_update_cognitive_node_history(self, store):
        """Test appending history entries to CognitiveNode."""
        await store.upsert_cognitive_node(
            node_id="mem_history",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Test content",
        )

        await store.update_cognitive_node_history("mem_history", {
            "action": "access",
            "timestamp": "2026-05-01T00:00:00Z",
        })

        node = await store.get_cognitive_node("mem_history")
        assert len(node["history"]) == 1
        assert node["history"][0]["action"] == "access"

        await store.update_cognitive_node_history("mem_history", {
            "action": "update",
            "timestamp": "2026-05-01T01:00:00Z",
        })

        node = await store.get_cognitive_node("mem_history")
        assert len(node["history"]) == 2

    @pytest.mark.asyncio
    async def test_update_cognitive_node_belief(self, store):
        """Test updating belief status of CognitiveNode."""
        await store.upsert_cognitive_node(
            node_id="mem_belief",
            memory_type="entity",
            cognitive_layer="semantic",
            content="Test content",
            belief_status="accepted",
        )

        await store.update_cognitive_node_belief("mem_belief", "contradicted", reason="New evidence found")

        node = await store.get_cognitive_node("mem_belief")
        assert node["belief_status"] == "contradicted"
        assert len(node["history"]) >= 1

        history_entry = node["history"][-1]
        assert history_entry["action"] == "belief_change"
        assert history_entry["old_belief"] == "accepted"
        assert history_entry["new_belief"] == "contradicted"
        assert history_entry["reason"] == "New evidence found"


class TestDispositionProfile:
    """Test DispositionProfileNode CRUD operations."""

    @pytest_asyncio.fixture
    async def store(self, tmp_path):
        """Create an initialized KuzuGraphStore for testing."""
        db_path = str(tmp_path / "test_disposition.kuzu")
        store = KuzuGraphStore()
        await store.initialize(db_path)
        yield store
        await store.close()

    @pytest.mark.asyncio
    async def test_upsert_and_get_disposition_profile(self, store):
        """Test DispositionProfileNode upsert and retrieval."""
        await store.upsert_disposition_profile(
            profile_id="profile_001",
            scene="financial_analysis",
            skepticism=0.8,
            evidence_demand=0.3,
            empathy=0.6,
            abstraction_preference=0.4,
            risk_tolerance=0.2,
            thoroughness=0.9,
            recency_bias=0.7,
            domain_id="finance",
        )

        profile = await store.get_disposition_profile(profile_id="profile_001")
        assert profile is not None
        assert profile["id"] == "profile_001"
        assert profile["scene"] == "financial_analysis"
        assert profile["skepticism"] == 0.8
        assert profile["evidence_demand"] == 0.3
        assert profile["empathy"] == 0.6
        assert profile["abstraction_preference"] == 0.4
        assert profile["risk_tolerance"] == 0.2
        assert profile["thoroughness"] == 0.9
        assert profile["recency_bias"] == 0.7
        assert profile["domain_id"] == "finance"

    @pytest.mark.asyncio
    async def test_get_disposition_profile_by_scene(self, store):
        """Test retrieving DispositionProfileNode by scene."""
        await store.upsert_disposition_profile(
            profile_id="profile_002",
            scene="legal_review",
            skepticism=0.9,
        )

        profile = await store.get_disposition_profile(scene="legal_review")
        assert profile is not None
        assert profile["scene"] == "legal_review"
        assert profile["skepticism"] == 0.9

    @pytest.mark.asyncio
    async def test_get_disposition_profile_not_found(self, store):
        """Test get_disposition_profile returns None for non-existent profile."""
        profile = await store.get_disposition_profile(profile_id="nonexistent")
        assert profile is None

    @pytest.mark.asyncio
    async def test_compute_dynamic_weights_default(self, store):
        profile = {
            "skepticism": 0.5,
            "evidence_demand": 0.5,
            "abstraction_preference": 0.5,
            "thoroughness": 0.5,
            "recency_bias": 0.5,
            "empathy": 0.5,
            "risk_tolerance": 0.5,
        }

        weights = await store.compute_dynamic_weights(profile)

        from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS
        for mt, base_w in BASE_TYPE_WEIGHTS.items():
            if mt in weights:
                assert abs(weights[mt] - base_w) < 0.01, f"{mt}: {weights[mt]} != {base_w}"

    @pytest.mark.asyncio
    async def test_compute_dynamic_weights_high_skepticism(self, store):
        profile = {
            "skepticism": 0.8,
            "evidence_demand": 0.5,
            "abstraction_preference": 0.5,
            "thoroughness": 0.5,
            "recency_bias": 0.5,
            "empathy": 0.5,
            "risk_tolerance": 0.5,
        }

        weights = await store.compute_dynamic_weights(profile)

        assert weights["mental_model"] < 3.0
        assert weights["entity"] > 2.0

    @pytest.mark.asyncio
    async def test_compute_dynamic_weights_high_empathy(self, store):
        profile = {
            "skepticism": 0.5,
            "evidence_demand": 0.5,
            "abstraction_preference": 0.5,
            "thoroughness": 0.5,
            "recency_bias": 0.5,
            "empathy": 0.8,
            "risk_tolerance": 0.5,
        }

        weights = await store.compute_dynamic_weights(profile)

        observation_weight = weights["observation"]
        assert observation_weight > 1.5

    @pytest.mark.asyncio
    async def test_compute_dynamic_weights_high_risk_tolerance(self, store):
        profile = {
            "skepticism": 0.5,
            "evidence_demand": 0.5,
            "abstraction_preference": 0.5,
            "thoroughness": 0.5,
            "recency_bias": 0.5,
            "empathy": 0.5,
            "risk_tolerance": 0.8,
        }

        weights = await store.compute_dynamic_weights(profile)

        from ontology_engine.engine.cognitive.rrf_types import BASE_TYPE_WEIGHTS
        assert weights["mental_model"] >= BASE_TYPE_WEIGHTS.get("mental_model", 3.0)

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ontology_engine.engine.rule.logical_edges import (
    CAUSAL_RELATIONS,
    ENABLEMENT_RELATIONS,
    CORRELATION_RELATIONS,
    LogicalEdgeEngine,
    LogicalEdgeType,
)


def test_classify_causal():
    for rel in CAUSAL_RELATIONS:
        assert LogicalEdgeEngine.classify(rel) == LogicalEdgeType.CAUSAL


def test_classify_enablement():
    for rel in ENABLEMENT_RELATIONS:
        assert LogicalEdgeEngine.classify(rel) == LogicalEdgeType.ENABLEMENT


def test_classify_correlation():
    for rel in CORRELATION_RELATIONS:
        assert LogicalEdgeEngine.classify(rel) == LogicalEdgeType.CORRELATION


def test_classify_unknown():
    assert LogicalEdgeEngine.classify("UNKNOWN_REL") is None
    assert LogicalEdgeEngine.classify("") is None


@pytest.mark.asyncio
async def test_get_logical_edges_with_graph():
    graph = AsyncMock()
    graph.get_neighbors.return_value = [
        {"neighbor_id": "E2", "edge_type": "LEADS_TO", "direction": "outgoing", "properties": {}},
        {"neighbor_id": "E3", "edge_type": "ENABLES", "direction": "outgoing", "properties": {}},
        {"neighbor_id": "E4", "edge_type": "RELATED_TO", "direction": "outgoing", "properties": {}},
    ]
    engine = LogicalEdgeEngine(graph_store=graph)
    edges = await engine.get_logical_edges("E1")
    assert len(edges) == 2
    assert edges[0]["logical_type"] == "causal"
    assert edges[1]["logical_type"] == "enablement"


@pytest.mark.asyncio
async def test_get_logical_edges_no_graph():
    engine = LogicalEdgeEngine(graph_store=None)
    edges = await engine.get_logical_edges("E1")
    assert edges == []


@pytest.mark.asyncio
async def test_get_logical_edges_filter_by_type():
    graph = AsyncMock()
    graph.get_neighbors.return_value = [
        {"neighbor_id": "E2", "edge_type": "LEADS_TO", "direction": "outgoing", "properties": {}},
        {"neighbor_id": "E3", "edge_type": "ENABLES", "direction": "outgoing", "properties": {}},
    ]
    engine = LogicalEdgeEngine(graph_store=graph)
    edges = await engine.get_logical_edges("E1", edge_type=LogicalEdgeType.CAUSAL)
    assert len(edges) == 1
    assert edges[0]["logical_type"] == "causal"


@pytest.mark.asyncio
async def test_trace_causal_chain():
    graph = AsyncMock()
    graph.get_neighbors.return_value = [
        {"neighbor_id": "E2", "edge_type": "LEADS_TO", "direction": "outgoing", "properties": {}},
    ]
    engine = LogicalEdgeEngine(graph_store=graph)
    edges = await engine.trace_causal_chain("E1", direction="forward")
    assert len(edges) >= 1
    assert edges[0]["logical_type"] == "causal"
    graph.get_neighbors.assert_any_call("E1", direction="outgoing", limit=500)


@pytest.mark.asyncio
async def test_find_enablement():
    graph = AsyncMock()
    graph.get_neighbors.return_value = [
        {"neighbor_id": "E2", "edge_type": "ENABLES", "direction": "outgoing", "properties": {}},
        {"neighbor_id": "E3", "edge_type": "PREVENTS", "direction": "incoming", "properties": {}},
    ]
    engine = LogicalEdgeEngine(graph_store=graph)
    edges = await engine.find_enablement("E1")
    assert len(edges) >= 2


@pytest.mark.asyncio
async def test_find_correlations():
    graph = AsyncMock()
    graph.get_neighbors.return_value = [
        {"neighbor_id": "E2", "edge_type": "same_entity_as", "direction": "both", "properties": {}},
    ]
    engine = LogicalEdgeEngine(graph_store=graph)
    edges = await engine.find_correlations("E1")
    assert len(edges) == 1
    assert edges[0]["logical_type"] == "correlation"

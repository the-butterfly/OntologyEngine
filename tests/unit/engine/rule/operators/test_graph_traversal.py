from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ontology_engine.engine.rule.operators.base import OperatorRegistry


@pytest.fixture
def graph_store():
    gs = AsyncMock()
    gs.get_neighbors.return_value = [
        {"neighbor_id": "E2", "edge_type": "guarantees_for", "direction": "outgoing"},
        {"neighbor_id": "E3", "edge_type": "guarantees_for", "direction": "outgoing"},
    ]
    gs.get_node.return_value = {"id": "E2", "data": {"score": 10.0}}
    return gs


@pytest.fixture
def op():
    return OperatorRegistry.get("graph_traversal")


@pytest.mark.asyncio
async def test_count_aggregation(op, graph_store):
    result = await op.execute(
        {"aggregation": "count"},
        {},
        {"entity_id": "E1", "graph_store": graph_store},
    )
    assert "graph_aggregation" in result
    assert result["graph_aggregation"]["count"] >= 0


@pytest.mark.asyncio
async def test_collect_aggregation(op, graph_store):
    result = await op.execute(
        {"aggregation": "collect"},
        {},
        {"entity_id": "E1", "graph_store": graph_store},
    )
    assert "graph_aggregation" in result
    ga = result["graph_aggregation"]
    assert "count" in ga


@pytest.mark.asyncio
async def test_sum_aggregation(op, graph_store):
    graph_store.get_node.side_effect = [
        {"id": "E2", "score": 10.0},
        {"id": "E3", "score": 20.0},
    ]
    result = await op.execute(
        {"aggregation": "sum", "target_field": "score"},
        {},
        {"entity_id": "E1", "graph_store": graph_store},
    )
    assert "graph_aggregation" in result


@pytest.mark.asyncio
async def test_average_aggregation(op, graph_store):
    graph_store.get_node.side_effect = [
        {"id": "E2", "score": 10.0},
        {"id": "E3", "score": 20.0},
    ]
    result = await op.execute(
        {"aggregation": "average", "target_field": "score"},
        {},
        {"entity_id": "E1", "graph_store": graph_store},
    )
    assert "graph_aggregation" in result


@pytest.mark.asyncio
async def test_no_graph_store(op):
    result = await op.execute(
        {"aggregation": "count"},
        {},
        {"entity_id": "E1"},
    )
    assert "graph_aggregation" in result
    assert "error" in result["graph_aggregation"]


@pytest.mark.asyncio
async def test_no_entity_id(op, graph_store):
    result = await op.execute(
        {"aggregation": "count"},
        {},
        {"graph_store": graph_store},
    )
    assert "graph_aggregation" in result
    assert "error" in result["graph_aggregation"]

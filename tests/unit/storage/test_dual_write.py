from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ontology_engine.storage.base import EntityInstance, RelationInstance
from ontology_engine.storage.dual_write import DualWriteCoordinator


@pytest.fixture
def storage():
    s = AsyncMock()
    s.save_entity = AsyncMock(return_value="SUP_001")
    s.save_relation = AsyncMock()
    s.get_entity_by_id = AsyncMock(return_value=None)
    return s


@pytest.fixture
def graph_store():
    return AsyncMock()


@pytest.fixture
def vector_store():
    return AsyncMock()


@pytest.fixture
def coordinator(storage, graph_store, vector_store):
    return DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        vector_store=vector_store,
    )


@pytest.fixture
def entity():
    return EntityInstance(
        _fact_object="Supplier",
        entity_id="SUP_001",
        data={"name": "Test Supplier"},
    )


@pytest.fixture
def relation():
    return RelationInstance(
        relation_name="guarantees_for",
        from_entity_id="SUP_001",
        to_entity_id="SUP_002",
        data={},
    )


@pytest.mark.asyncio
async def test_write_entity_syncs_to_graph(coordinator, storage, graph_store, entity):
    entity_id = await coordinator.write_entity(entity, space_id="test")
    assert entity_id == "SUP_001"
    storage.save_entity.assert_called_once_with(entity)
    graph_store.upsert_node.assert_called_once()


@pytest.mark.asyncio
async def test_write_entity_graph_failure_compensation(coordinator, storage, graph_store, entity):
    graph_store.upsert_node.side_effect = Exception("Graph error")
    entity_id = await coordinator.write_entity(entity, space_id="test")
    assert entity_id == "SUP_001"
    storage.save_entity.assert_called_once()
    assert len(coordinator._compensation_log) == 1
    assert coordinator._compensation_log[0]["operation"] == "graph_upsert"


@pytest.mark.asyncio
async def test_write_relation_syncs_to_graph(coordinator, storage, graph_store, relation):
    await coordinator.write_relation(relation, space_id="test")
    storage.save_relation.assert_called_once_with(relation)
    graph_store.upsert_edge.assert_called_once()


@pytest.mark.asyncio
async def test_delete_entity_removes_from_all(coordinator, graph_store, vector_store):
    await coordinator.delete_entity("SUP_001")
    graph_store.delete_node.assert_called_once_with(node_id="SUP_001")
    assert vector_store.delete_vectors.call_count == 2


@pytest.mark.asyncio
async def test_sync_to_graph(coordinator, storage, graph_store, entity):
    storage.get_entity_by_id.return_value = entity
    await coordinator.sync_to_graph("SUP_001", space_id="test")
    graph_store.upsert_node.assert_called_once()


@pytest.mark.asyncio
async def test_sync_to_graph_no_graph(storage, entity):
    coord = DualWriteCoordinator(storage=storage, graph_store=None, vector_store=None)
    storage.get_entity_by_id.return_value = entity
    await coord.sync_to_graph("SUP_001")
    storage.get_entity_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_write_entity_no_graph_no_vector(storage, entity):
    coord = DualWriteCoordinator(storage=storage, graph_store=None, vector_store=None)
    entity_id = await coord.write_entity(entity)
    assert entity_id == "SUP_001"
    storage.save_entity.assert_called_once()

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from ontology_engine.storage.base import (
    CompensationStore,
    EntityInstance,
    RelationInstance,
)
from ontology_engine.storage.dual_write import DualWriteCoordinator


@pytest.fixture
def storage():
    s = AsyncMock()
    s.save_entity = AsyncMock(return_value="SUP_001")
    s.save_relation = AsyncMock()
    s.get_entity_by_id = AsyncMock(return_value=None)
    s.get_relations = AsyncMock(return_value=[])
    return s


@pytest.fixture
def graph_store():
    return AsyncMock()


@pytest.fixture
def vector_store():
    return AsyncMock()


@pytest.fixture
def compensation_store():
    return AsyncMock(spec=CompensationStore)


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
async def test_compensation_written_on_graph_failure(
    storage, graph_store, vector_store, entity
):
    graph_store.upsert_node.side_effect = Exception("Graph error")
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        vector_store=vector_store,
    )
    await coordinator.write_entity(entity, space_id="test")
    assert len(coordinator._compensation_log) == 1
    entry = coordinator._compensation_log[0]
    assert entry["operation"] == "graph_upsert"
    assert entry["target_type"] == "entity"
    assert entry["target_id"] == "SUP_001"


@pytest.mark.asyncio
async def test_compensation_written_on_vector_failure(
    storage, graph_store, vector_store, entity
):
    vector_store.sync_entity = AsyncMock(side_effect=Exception("Vector error"))
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        vector_store=vector_store,
    )
    await coordinator.write_entity(entity, space_id="test")
    vector_compensations = [
        e for e in coordinator._compensation_log if e["operation"] == "vector_upsert"
    ]
    assert len(vector_compensations) == 1
    assert vector_compensations[0]["target_type"] == "entity"
    assert vector_compensations[0]["target_id"] == "SUP_001"


@pytest.mark.asyncio
async def test_compensation_persisted_via_store(
    storage, graph_store, vector_store, compensation_store, entity
):
    graph_store.upsert_node.side_effect = Exception("Graph error")
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        vector_store=vector_store,
        compensation_store=compensation_store,
    )
    await coordinator.write_entity(entity, space_id="test")
    compensation_store.save_compensation.assert_called_once()
    call_args = compensation_store.save_compensation.call_args[0][0]
    assert call_args["operation"] == "graph_upsert"
    assert call_args["target_type"] == "entity"
    assert call_args["target_id"] == "SUP_001"
    assert call_args["status"] == "pending"


@pytest.mark.asyncio
async def test_recovery_entity_graph_upsert(
    storage, graph_store, compensation_store, entity
):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "graph_upsert",
                "target_type": "entity",
                "target_id": "SUP_001",
                "status": "pending",
            }
        ]
    )
    storage.get_entity_by_id = AsyncMock(return_value=entity)
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    graph_store.upsert_node.assert_called_once()
    compensation_store.mark_compensation_done.assert_called_once_with(
        "SUP_001", "graph_upsert"
    )


@pytest.mark.asyncio
async def test_recovery_entity_vector_upsert(
    storage, vector_store, compensation_store, entity
):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "vector_upsert",
                "target_type": "entity",
                "target_id": "SUP_001",
                "status": "pending",
            }
        ]
    )
    storage.get_entity_by_id = AsyncMock(return_value=entity)
    coordinator = DualWriteCoordinator(
        storage=storage,
        vector_store=vector_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    storage.get_entity_by_id.assert_called_once()
    compensation_store.mark_compensation_done.assert_called_once_with(
        "SUP_001", "vector_upsert"
    )


@pytest.mark.asyncio
async def test_recovery_relation_graph_upsert(
    storage, graph_store, compensation_store, relation
):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "graph_upsert",
                "target_type": "relation",
                "target_id": "SUP_001:SUP_002:guarantees_for",
                "status": "pending",
            }
        ]
    )
    storage.get_relations = AsyncMock(return_value=[relation])
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    graph_store.upsert_edge.assert_called_once()
    call_kwargs = graph_store.upsert_edge.call_args[1]
    assert call_kwargs["from_node_id"] == "SUP_001"
    assert call_kwargs["to_node_id"] == "SUP_002"
    assert call_kwargs["edge_type"] == "guarantees_for"
    compensation_store.mark_compensation_done.assert_called_once_with(
        "SUP_001:SUP_002:guarantees_for", "graph_upsert"
    )


@pytest.mark.asyncio
async def test_recovery_increments_retry_on_failure(
    storage, graph_store, compensation_store, entity
):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "graph_upsert",
                "target_type": "entity",
                "target_id": "SUP_001",
                "status": "pending",
            }
        ]
    )
    storage.get_entity_by_id = AsyncMock(side_effect=Exception("Storage broken"))
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 0
    compensation_store.increment_retry_count.assert_called_once_with(
        "SUP_001", "graph_upsert"
    )
    compensation_store.mark_compensation_done.assert_not_called()


@pytest.mark.asyncio
async def test_no_recovery_without_compensation_store(storage):
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=None,
        vector_store=None,
        compensation_store=None,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 0


@pytest.mark.asyncio
async def test_recovery_entity_delete_node(graph_store, compensation_store):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "delete_node",
                "target_type": "entity",
                "target_id": "e1",
                "status": "pending",
            }
        ]
    )
    coordinator = DualWriteCoordinator(
        storage=AsyncMock(),
        graph_store=graph_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    graph_store.delete_node.assert_called_once_with(node_id="e1")
    compensation_store.mark_compensation_done.assert_called_once_with(
        "e1", "delete_node"
    )


@pytest.mark.asyncio
async def test_recovery_entity_vector_delete(vector_store, compensation_store):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "vector_delete",
                "target_type": "entity",
                "target_id": "e1",
                "status": "pending",
            }
        ]
    )
    coordinator = DualWriteCoordinator(
        storage=AsyncMock(),
        vector_store=vector_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    vector_store.delete_vectors.assert_called_once_with(["e1"])
    compensation_store.mark_compensation_done.assert_called_once_with(
        "e1", "vector_delete"
    )


@pytest.mark.asyncio
async def test_recovery_relation_delete_relation_graph(
    graph_store, compensation_store
):
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "delete_relation_graph",
                "target_type": "relation",
                "target_id": "from:to:relname",
                "status": "pending",
            }
        ]
    )
    coordinator = DualWriteCoordinator(
        storage=AsyncMock(),
        graph_store=graph_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    graph_store.delete_edge.assert_called_once_with(edge_id="from:to:relname")
    compensation_store.mark_compensation_done.assert_called_once_with(
        "from:to:relname", "delete_relation_graph"
    )


@pytest.mark.asyncio
async def test_recovery_relation_update_relation_graph(
    storage, graph_store, compensation_store
):
    relation = RelationInstance(
        relation_name="relname",
        from_entity_id="from",
        to_entity_id="to",
        data={"key": "val"},
    )
    compensation_store.get_pending_compensations = AsyncMock(
        return_value=[
            {
                "operation": "update_relation_graph",
                "target_type": "relation",
                "target_id": "from:to:relname",
                "status": "pending",
            }
        ]
    )
    storage.get_relations = AsyncMock(return_value=[relation])
    coordinator = DualWriteCoordinator(
        storage=storage,
        graph_store=graph_store,
        compensation_store=compensation_store,
    )
    executed = await coordinator.recover_pending_compensations()
    assert executed == 1
    graph_store.upsert_edge.assert_called_once()
    call_kwargs = graph_store.upsert_edge.call_args[1]
    assert call_kwargs["from_node_id"] == "from"
    assert call_kwargs["to_node_id"] == "to"
    assert call_kwargs["edge_type"] == "relname"
    compensation_store.mark_compensation_done.assert_called_once_with(
        "from:to:relname", "update_relation_graph"
    )


@pytest.mark.asyncio
async def test_compensation_store_closed_raises():
    from ontology_engine.storage.local.compensation_store import LocalCompensationStore

    store = LocalCompensationStore(":memory:")
    store.close()
    with pytest.raises(RuntimeError):
        await store.save_compensation({"operation": "test"})

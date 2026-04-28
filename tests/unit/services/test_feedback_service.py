from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ontology_engine.services.feedback_service import FeedbackService
from ontology_engine.storage.base import EntityInstance, FeedbackRecord


@pytest.fixture
def storage():
    s = AsyncMock()
    s.get_entity_by_id = AsyncMock()
    s.save_feedback = AsyncMock()
    s.get_feedback = AsyncMock(return_value=[])
    s.save_entity = AsyncMock()
    return s


@pytest.fixture
def service(storage):
    return FeedbackService(storage, learning_rate=0.1)


@pytest.fixture
def entity():
    return EntityInstance(
        _fact_object="Supplier",
        entity_id="SUP_001",
        data={"name": "Test Supplier"},
        feedback_weight=0.5,
    )


@pytest.mark.asyncio
async def test_submit_feedback_confirm(service, storage, entity):
    storage.get_entity_by_id.return_value = entity
    record = await service.submit_feedback("SUP_001", "confirm", value=1.0)
    assert record.feedback_type == "confirm"
    assert record.updated_weight > 0.5
    assert record.previous_weight == 0.5
    storage.save_feedback.assert_called_once()


@pytest.mark.asyncio
async def test_submit_feedback_override(service, storage, entity):
    storage.get_entity_by_id.return_value = entity
    record = await service.submit_feedback("SUP_001", "override", value=0.9)
    assert record.feedback_type == "override"
    assert record.updated_weight == 0.9


@pytest.mark.asyncio
async def test_submit_feedback_dispute(service, storage, entity):
    storage.get_entity_by_id.return_value = entity
    record = await service.submit_feedback("SUP_001", "dispute")
    assert record.feedback_type == "dispute"
    assert record.updated_weight < 0.5


@pytest.mark.asyncio
async def test_submit_feedback_invalid_type(service, storage, entity):
    storage.get_entity_by_id.return_value = entity
    with pytest.raises(ValueError, match="Invalid feedback_type"):
        await service.submit_feedback("SUP_001", "invalid_type")


@pytest.mark.asyncio
async def test_submit_feedback_entity_not_found(service, storage):
    storage.get_entity_by_id.return_value = None
    with pytest.raises(ValueError, match="not found"):
        await service.submit_feedback("NONEXISTENT", "confirm")


@pytest.mark.asyncio
async def test_get_feedback(service, storage):
    records = [FeedbackRecord(record_id="r1", entity_id="SUP_001", feedback_type="confirm", created_at=datetime.now(timezone.utc))]
    storage.get_feedback.return_value = records
    result = await service.get_feedback("SUP_001")
    assert len(result) == 1
    assert result[0].record_id == "r1"


@pytest.mark.asyncio
async def test_apply_feedback(service, storage, entity):
    record = FeedbackRecord(
        record_id="r1", entity_id="SUP_001", feedback_type="confirm",
        value=1.0, previous_weight=0.5, updated_weight=0.55,
        applied=False, created_at=datetime.now(timezone.utc),
    )
    storage.get_feedback.return_value = [record]
    storage.get_entity_by_id.return_value = entity

    await service.apply_feedback("SUP_001")

    storage.save_entity.assert_called_once()
    saved_entity = storage.save_entity.call_args[0][0]
    assert saved_entity.feedback_weight == 0.55


@pytest.mark.asyncio
async def test_get_feedback_history(service, storage):
    records = [
        FeedbackRecord(record_id="r1", entity_id="SUP_001", feedback_type="confirm", created_at=datetime.now(timezone.utc)),
        FeedbackRecord(record_id="r2", entity_id="SUP_001", feedback_type="dispute", created_at=datetime.now(timezone.utc)),
    ]
    storage.get_feedback.return_value = records
    result = await service.get_feedback_history("SUP_001")
    assert len(result) == 2

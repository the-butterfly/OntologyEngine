from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ontology_engine.storage.base import FeedbackRecord, StorageBackend


class FeedbackService:
    def __init__(self, storage: StorageBackend, learning_rate: float = 0.1):
        self._storage = storage
        self._learning_rate = learning_rate

    async def submit_feedback(
        self,
        entity_id: str,
        feedback_type: str,
        value: float = 1.0,
        metric_name: str | None = None,
        source: str = "user",
        text_feedback: str | None = None,
    ) -> FeedbackRecord:
        if feedback_type not in ("confirm", "override", "dispute"):
            raise ValueError(f"Invalid feedback_type: {feedback_type}")

        entity = await self._storage.get_entity_by_id(entity_id=entity_id)
        if entity is None:
            raise ValueError(f"Entity {entity_id} not found")

        previous_weight = entity.feedback_weight

        if feedback_type == "confirm":
            updated_weight = previous_weight + self._learning_rate * (1.0 - previous_weight)
        elif feedback_type == "override":
            updated_weight = min(1.0, value)
        else:
            updated_weight = max(0.0, previous_weight - self._learning_rate * previous_weight)

        record = FeedbackRecord(
            record_id=str(uuid4()),
            entity_id=entity_id,
            metric_name=metric_name,
            feedback_type=feedback_type,
            value=value,
            previous_weight=previous_weight,
            updated_weight=updated_weight,
            source=source,
            text_feedback=text_feedback,
            applied=False,
            created_at=datetime.now(timezone.utc),
        )

        await self._storage.save_feedback(record)
        return record

    async def get_feedback(
        self,
        entity_id: str,
        metric_name: str | None = None,
    ) -> list[FeedbackRecord]:
        return await self._storage.get_feedback(entity_id=entity_id, metric_name=metric_name)

    async def apply_feedback(self, entity_id: str, metric_name: str | None = None) -> None:
        records = await self._storage.get_feedback(entity_id=entity_id, metric_name=metric_name)
        unapplied = [r for r in records if not r.applied]
        if not unapplied:
            return

        entity = await self._storage.get_entity_by_id(entity_id=entity_id)
        if entity is None:
            return

        latest = max(unapplied, key=lambda r: r.created_at or datetime.min.replace(tzinfo=timezone.utc))
        entity.feedback_weight = latest.updated_weight
        await self._storage.save_entity(entity)

        for r in unapplied:
            r.applied = True
            await self._storage.save_feedback(r)

    async def get_feedback_history(self, entity_id: str) -> list[FeedbackRecord]:
        return await self._storage.get_feedback(entity_id=entity_id)

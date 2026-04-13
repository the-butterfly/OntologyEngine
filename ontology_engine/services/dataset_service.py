# ontology_engine/services/dataset_service.py
"""Dataset management service.

Provides CRUD operations for datasets, entity membership tracking,
snapshots, and dataset comparison. Persists to DuckDB storage.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ontology_engine.storage.duckdb.store import DuckDBStorage

logger = logging.getLogger(__name__)


class DatasetService:
    """Service for managing datasets.

    Datasets are logical groupings of entities and relations with
    scope definitions, source tracking, and version snapshots.
    """

    def __init__(self, storage: DuckDBStorage):
        self._storage = storage

    async def create_dataset(
        self,
        name: str,
        scope: dict[str, Any] | None = None,
        source_type: str = "manual",
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new dataset."""
        dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
        await self._storage.create_dataset(
            dataset_id=dataset_id,
            name=name,
            scope=scope,
            source_type=source_type,
            description=description,
        )
        dataset = await self._storage.get_dataset(dataset_id)
        return dataset or {"dataset_id": dataset_id, "name": name}

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Get a dataset by ID."""
        return await self._storage.get_dataset(dataset_id)

    async def list_datasets(self) -> list[dict[str, Any]]:
        """List all datasets."""
        return await self._storage.list_datasets()

    async def update_dataset(
        self,
        dataset_id: str,
        name: str | None = None,
        description: str | None = None,
        scope: dict[str, Any] | None = None,
    ) -> bool:
        """Update a dataset."""
        return await self._storage.update_dataset(
            dataset_id=dataset_id,
            name=name,
            description=description,
            scope=scope,
        )

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and its memberships."""
        await self._storage.delete_dataset(dataset_id)
        return True

    async def add_entities(
        self,
        dataset_id: str,
        entities: list[dict[str, Any]],
        concept: str | None = None,
        is_primary: bool = False,
    ) -> int:
        """Add entities to a dataset."""
        dataset = await self._storage.get_dataset(dataset_id)
        if not dataset:
            return 0

        count = 0
        for idx, entity in enumerate(entities):
            eid = entity.get("entity_id", entity.get("id"))
            if eid:
                entity_concept = concept or entity.get("_concept", entity.get("concept", ""))
                await self._storage.add_entity_to_dataset(
                    entity_id=eid,
                    dataset_id=dataset_id,
                    concept=entity_concept,
                    is_primary=is_primary,
                    source_line=entity.get("source_line", idx + 1),
                )
                count += 1

        # Update entity count in dataset
        members = await self._storage.get_dataset_entities(dataset_id)
        await self._storage.update_dataset(dataset_id, scope=dataset.get("scope", {}))
        return count

    async def get_dataset_entities(
        self,
        dataset_id: str,
        concept: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get entities in a dataset."""
        return await self._storage.get_dataset_entities(dataset_id, concept)

    async def get_intersection(
        self,
        dataset_a_id: str,
        dataset_b_id: str,
    ) -> dict[str, Any]:
        """Compute intersection of two datasets."""
        members_a = await self._storage.get_dataset_entities(dataset_a_id)
        members_b = await self._storage.get_dataset_entities(dataset_b_id)

        set_a = {m["entity_id"] for m in members_a}
        set_b = {m["entity_id"] for m in members_b}
        intersection = set_a & set_b

        return {
            "dataset_a": dataset_a_id,
            "dataset_b": dataset_b_id,
            "intersection_count": len(intersection),
            "intersection_entities": list(intersection),
            "dataset_a_only": list(set_a - set_b),
            "dataset_b_only": list(set_b - set_a),
        }

    async def get_diff(
        self,
        dataset_a_id: str,
        dataset_b_id: str,
    ) -> dict[str, Any]:
        """Compute diff between two datasets."""
        members_a = await self._storage.get_dataset_entities(dataset_a_id)
        members_b = await self._storage.get_dataset_entities(dataset_b_id)

        set_a = {m["entity_id"] for m in members_a}
        set_b = {m["entity_id"] for m in members_b}

        return {
            "dataset_a": dataset_a_id,
            "dataset_b": dataset_b_id,
            "only_in_a": list(set_a - set_b),
            "only_in_b": list(set_b - set_a),
            "common": list(set_a & set_b),
            "stats": {
                "dataset_a_count": len(set_a),
                "dataset_b_count": len(set_b),
                "common_count": len(set_a & set_b),
            },
        }

    async def create_snapshot(
        self,
        dataset_id: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a point-in-time snapshot of a dataset."""
        dataset = await self._storage.get_dataset(dataset_id)
        if not dataset:
            return {"error": "Dataset not found"}

        snapshot_id = f"snap_{uuid.uuid4().hex[:10]}"
        members = await self._storage.get_dataset_entities(dataset_id)
        await self._storage.create_snapshot(
            snapshot_id=snapshot_id,
            dataset_id=dataset_id,
            entity_count=len(members),
            description=description,
        )

        snapshots = await self._storage.get_snapshots(dataset_id)
        snap = next((s for s in snapshots if s["snapshot_id"] == snapshot_id), None)
        return snap or {"snapshot_id": snapshot_id, "dataset_id": dataset_id}

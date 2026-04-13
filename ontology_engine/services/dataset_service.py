# ontology_engine/services/dataset_service.py
"""Dataset management service.

Provides CRUD operations for datasets, entity membership tracking,
snapshots, and dataset comparison.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DatasetService:
    """Service for managing datasets.

    Datasets are logical groupings of entities and relations with
    scope definitions, source tracking, and version snapshots.
    """

    def __init__(self):
        self._datasets: dict[str, dict[str, Any]] = {}

    async def create_dataset(
        self,
        name: str,
        scope: dict[str, Any] | None = None,
        source_type: str = "manual",
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new dataset."""
        dataset_id = f"ds_{uuid.uuid4().hex[:10]}"
        dataset = {
            "dataset_id": dataset_id,
            "name": name,
            "description": description,
            "scope": scope or {},
            "source_type": source_type,
            "version": "1.0.0",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "entity_count": 0,
            "relation_count": 0,
        }
        self._datasets[dataset_id] = dataset
        return dataset

    async def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    async def list_datasets(self) -> list[dict[str, Any]]:
        """List all datasets."""
        return list(self._datasets.values())

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset."""
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            return True
        return False

    async def add_entities(
        self,
        dataset_id: str,
        entities: list[dict[str, Any]],
        concept: str | None = None,
        is_primary: bool = False,
    ) -> int:
        """Add entities to a dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return 0

        membership = dataset.setdefault("entity_membership", {})
        count = 0
        for entity in entities:
            eid = entity.get("entity_id", entity.get("id"))
            if eid:
                membership[eid] = {
                    "concept": concept or entity.get("_concept", entity.get("concept", "")),
                    "is_primary": is_primary,
                    "added_at": datetime.utcnow().isoformat(),
                }
                count += 1

        dataset["entity_count"] = len(membership)
        dataset["updated_at"] = datetime.utcnow().isoformat()
        return count

    async def get_dataset_entities(
        self,
        dataset_id: str,
        concept: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get entities in a dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []

        membership = dataset.get("entity_membership", {})
        entities = []
        for eid, info in membership.items():
            if concept and info.get("concept") != concept:
                continue
            entities.append({
                "entity_id": eid,
                **info,
            })
        return entities

    async def get_intersection(
        self,
        dataset_a_id: str,
        dataset_b_id: str,
    ) -> dict[str, Any]:
        """Compute intersection of two datasets."""
        ds_a = self._datasets.get(dataset_a_id)
        ds_b = self._datasets.get(dataset_b_id)
        if not ds_a or not ds_b:
            return {"error": "Dataset not found", "intersection_count": 0}

        membership_a = set(ds_a.get("entity_membership", {}).keys())
        membership_b = set(ds_b.get("entity_membership", {}).keys())
        intersection = membership_a & membership_b

        return {
            "dataset_a": dataset_a_id,
            "dataset_b": dataset_b_id,
            "intersection_count": len(intersection),
            "intersection_entities": list(intersection),
            "dataset_a_only": list(membership_a - membership_b),
            "dataset_b_only": list(membership_b - membership_a),
        }

    async def get_diff(
        self,
        dataset_a_id: str,
        dataset_b_id: str,
    ) -> dict[str, Any]:
        """Compute diff between two datasets."""
        ds_a = self._datasets.get(dataset_a_id)
        ds_b = self._datasets.get(dataset_b_id)
        if not ds_a or not ds_b:
            return {"error": "Dataset not found"}

        members_a = set(ds_a.get("entity_membership", {}).keys())
        members_b = set(ds_b.get("entity_membership", {}).keys())

        return {
            "dataset_a": dataset_a_id,
            "dataset_b": dataset_b_id,
            "only_in_a": list(members_a - members_b),
            "only_in_b": list(members_b - members_a),
            "common": list(members_a & members_b),
            "stats": {
                "dataset_a_count": len(members_a),
                "dataset_b_count": len(members_b),
                "common_count": len(members_a & members_b),
            },
        }

    async def create_snapshot(
        self,
        dataset_id: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a point-in-time snapshot of a dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return {"error": "Dataset not found"}

        snapshot_id = f"snap_{uuid.uuid4().hex[:10]}"
        snapshot = {
            "snapshot_id": snapshot_id,
            "dataset_id": dataset_id,
            "description": description,
            "entity_count": dataset.get("entity_count", 0),
            "relation_count": dataset.get("relation_count", 0),
            "membership_snapshot": dict(dataset.get("entity_membership", {})),
            "created_at": datetime.utcnow().isoformat(),
        }

        snapshots = dataset.setdefault("snapshots", [])
        snapshots.append(snapshot)
        return snapshot

# ontology_engine/services/incremental_update.py
"""Incremental data update service with change detection and diff analysis."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Type of entity change."""
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    UNCHANGED = "UNCHANGED"


@dataclass
class FieldChange:
    """Single field-level change."""
    field_name: str
    old_value: Any = None
    new_value: Any = None


@dataclass
class EntityChange:
    """Change record for a single entity."""
    entity_id: str
    concept: str
    change_type: ChangeType
    field_changes: list[FieldChange] = field(default_factory=list)
    old_data: dict | None = None
    new_data: dict | None = None


@dataclass
class ChangeBatch:
    """Batch of entity changes for a single import operation."""
    batch_id: str
    dataset_id: str | None = None
    created_at: str = ""
    changes: list[EntityChange] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: {
        "total": 0, "created": 0, "updated": 0,
        "deleted": 0, "unchanged": 0,
    })

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()
        self._update_stats()

    def _update_stats(self):
        self.stats["total"] = len(self.changes)
        for change in self.changes:
            ct = change.change_type.value if isinstance(change.change_type, ChangeType) else change.change_type
            self.stats[ct.lower()] = self.stats.get(ct.lower(), 0) + 1


class EntityDiffer:
    """Compute field-level diffs between entity data dicts."""

    @staticmethod
    def diff(old_data: dict[str, Any], new_data: dict[str, Any]) -> list[FieldChange]:
        """Recursively compare two dicts and return field-level changes."""
        field_changes: list[FieldChange] = []
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val == new_val:
                continue

            if key not in old_data:
                field_changes.append(FieldChange(field_name=key, old_value=None, new_value=new_val))
            elif key not in new_data:
                field_changes.append(FieldChange(field_name=key, old_value=old_val, new_value=None))
            elif isinstance(old_val, dict) and isinstance(new_val, dict):
                nested = EntityDiffer.diff(old_val, new_val)
                for nc in nested:
                    field_changes.append(FieldChange(
                        field_name=f"{key}.{nc.field_name}",
                        old_value=nc.old_value,
                        new_value=nc.new_value,
                    ))
            else:
                field_changes.append(FieldChange(field_name=key, old_value=old_val, new_value=new_val))

        return field_changes


class IncrementalUpdateService:
    """Service for incremental entity data updates."""

    def __init__(self):
        self._differ = EntityDiffer()

    def detect_changes(
        self,
        old_entities: dict[str, dict[str, Any]],
        new_entities: dict[str, dict[str, Any]],
    ) -> list[EntityChange]:
        """Detect changes between old and new entity datasets."""
        changes: list[EntityChange] = []

        for entity_id, new_data in new_entities.items():
            concept = new_data.get("_concept", new_data.get("concept", "Unknown"))
            if entity_id not in old_entities:
                changes.append(EntityChange(
                    entity_id=entity_id,
                    concept=concept,
                    change_type=ChangeType.CREATED,
                    new_data=new_data,
                ))
            else:
                old_data = old_entities[entity_id]
                field_changes = self._differ.diff(old_data, new_data)
                if field_changes:
                    changes.append(EntityChange(
                        entity_id=entity_id,
                        concept=concept,
                        change_type=ChangeType.UPDATED,
                        field_changes=field_changes,
                        old_data=old_data,
                        new_data=new_data,
                    ))
                else:
                    changes.append(EntityChange(
                        entity_id=entity_id,
                        concept=concept,
                        change_type=ChangeType.UNCHANGED,
                    ))

        for entity_id, old_data in old_entities.items():
            if entity_id not in new_entities:
                concept = old_data.get("_concept", old_data.get("concept", "Unknown"))
                changes.append(EntityChange(
                    entity_id=entity_id,
                    concept=concept,
                    change_type=ChangeType.DELETED,
                    old_data=old_data,
                ))

        return changes

    def create_change_batch(
        self,
        changes: list[EntityChange],
        dataset_id: str | None = None,
    ) -> ChangeBatch:
        """Create a change batch from detected changes."""
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        return ChangeBatch(
            batch_id=batch_id,
            dataset_id=dataset_id,
            changes=changes,
        )

    def compute_impact(
        self,
        changes: list[EntityChange],
        metric_dependencies: dict[str, list[str]],
        rule_dependencies: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Compute downstream impact of entity changes."""
        affected_entities = set()
        affected_metrics: set[str] = set()
        affected_rules: set[str] = set()
        affected_categories: set[str] = set()

        for change in changes:
            if change.change_type in (ChangeType.CREATED, ChangeType.UPDATED, ChangeType.DELETED):
                eid = change.entity_id
                affected_entities.add(eid)
                for metric_id in metric_dependencies.get(eid, []):
                    affected_metrics.add(metric_id)
                for rule_id in rule_dependencies.get(eid, []):
                    affected_rules.add(rule_id)
                affected_categories.add(eid)

        return {
            "affected_entities": list(affected_entities),
            "affected_metrics": list(affected_metrics),
            "affected_rules": list(affected_rules),
            "affected_categories": list(affected_categories),
            "entity_count": len(affected_entities),
            "metric_count": len(affected_metrics),
            "rule_count": len(affected_rules),
        }

    @staticmethod
    def get_rollback_actions(changes: list[EntityChange]) -> list[dict[str, Any]]:
        """Generate rollback actions from a change batch."""
        actions = []
        for change in changes:
            if change.change_type == ChangeType.CREATED:
                actions.append({
                    "action": "delete",
                    "entity_id": change.entity_id,
                    "concept": change.concept,
                })
            elif change.change_type == ChangeType.DELETED:
                actions.append({
                    "action": "restore",
                    "entity_id": change.entity_id,
                    "concept": change.concept,
                    "data": change.old_data,
                })
            elif change.change_type == ChangeType.UPDATED:
                actions.append({
                    "action": "restore_data",
                    "entity_id": change.entity_id,
                    "concept": change.concept,
                    "data": change.old_data,
                })
        return actions

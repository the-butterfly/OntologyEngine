# ontology_engine/api/routes/incremental.py
"""Incremental update API routes."""
from __future__ import annotations

import warnings
from typing import Any

from fastapi import APIRouter, Query, Depends

from ontology_engine.api.dependencies import get_incremental_update_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.incremental_update import (
    IncrementalUpdateService,
    EntityChange,
    ChangeType,
)

warnings.warn(
    "ontology_engine.api.routes.incremental is deprecated. "
    "Use ontology_engine.api.routes.instances instead.",
    DeprecationWarning,
    stacklevel=2,
)

router = APIRouter(prefix="/v1/incremental", tags=["Incremental Update"])


@router.post("/import")
async def import_with_diff(
    request: dict[str, Any],
    service: IncrementalUpdateService = Depends(get_incremental_update_service),
) -> dict[str, Any]:
    """Import entities with change detection.

    Request body:
        entities: dict of entity_id -> entity_data
        old_entities: dict of entity_id -> existing_data (optional)
        dataset_id: optional dataset association
        dry_run: if True, only detect changes without persisting
    """
    new_entities = request.get("entities", {})
    old_entities = request.get("old_entities")
    dataset_id = request.get("dataset_id")
    dry_run = request.get("dry_run", False)

    if not new_entities:
        return error_response(code="INVALID_REQUEST", message="entities is required")

    try:
        result = await service.import_with_diff(
            new_entities=new_entities,
            old_entities=old_entities,
            dataset_id=dataset_id,
            dry_run=dry_run,
        )
        return success_response(data=result)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/batches")
async def list_change_batches(
    dataset_id: str | None = Query(None),
    service: IncrementalUpdateService = Depends(get_incremental_update_service),
) -> dict[str, Any]:
    """List change batches."""
    try:
        batches = await service.list_change_batches(dataset_id)
        return success_response(data=batches, meta={"total": len(batches)})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/batches/{batch_id}")
async def get_change_batch(
    batch_id: str,
    service: IncrementalUpdateService = Depends(get_incremental_update_service),
) -> dict[str, Any]:
    """Get a change batch with entity changes."""
    try:
        batch = await service.get_change_batch(batch_id)
        if not batch:
            return error_response(
                code="NOT_FOUND",
                message=f"Batch {batch_id} not found",
            )
        return success_response(data=batch)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/batches/{batch_id}/rollback-actions")
async def get_rollback_actions(
    batch_id: str,
    service: IncrementalUpdateService = Depends(get_incremental_update_service),
) -> dict[str, Any]:
    """Get rollback actions for a change batch."""
    try:
        actions = await service.get_rollback_actions(batch_id)
        return success_response(
            data=actions,
            meta={"batch_id": batch_id, "total": len(actions)},
        )
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/impact")
async def compute_impact(
    request: dict[str, Any],
    service: IncrementalUpdateService = Depends(get_incremental_update_service),
) -> dict[str, Any]:
    """Compute downstream impact of changes.

    Request body:
        changes: list of entity change records
        metric_dependencies: dict of entity_id -> [metric_ids]
        rule_dependencies: dict of entity_id -> [rule_ids]
    """
    changes_raw = request.get("changes", [])
    metric_deps = request.get("metric_dependencies", {})
    rule_deps = request.get("rule_dependencies", {})

    try:
        changes = []
        for c in changes_raw:
            changes.append(
                EntityChange(
                    entity_id=c.get("entity_id", ""),
                    concept=c.get("concept", ""),
                    change_type=ChangeType(c.get("change_type", "UPDATED")),
                )
            )

        impact = await service.compute_impact(changes, metric_deps, rule_deps)
        return success_response(data=impact)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))

# ontology_engine/api/routes/incremental.py
"""Incremental update API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ontology_engine.api.dependencies import get_storage

router = APIRouter(prefix="/v1/incremental", tags=["Incremental Update"])


@router.post("/import", response_model=dict)
async def import_with_diff(request: dict[str, Any]):
    """Import entities with change detection.

    Request body:
        entities: dict of entity_id -> entity_data
        old_entities: dict of entity_id -> existing_data (optional, fetched if omitted)
        dataset_id: optional dataset association
        dry_run: if True, only detect changes without persisting
    """
    storage = get_storage()
    from ontology_engine.services.incremental_update import IncrementalUpdateService
    service = IncrementalUpdateService(storage=storage)

    new_entities = request.get("entities", {})
    old_entities = request.get("old_entities")
    dataset_id = request.get("dataset_id")
    dry_run = request.get("dry_run", False)

    if not new_entities:
        raise HTTPException(status_code=400, detail="entities is required")

    result = await service.import_with_diff(
        new_entities=new_entities,
        old_entities=old_entities,
        dataset_id=dataset_id,
        dry_run=dry_run,
    )
    return {"status": "ok", "data": result}


@router.get("/batches", response_model=dict)
async def list_change_batches(dataset_id: str | None = Query(None)):
    """List change batches."""
    storage = get_storage()
    from ontology_engine.services.incremental_update import IncrementalUpdateService
    service = IncrementalUpdateService(storage=storage)

    batches = await service.list_change_batches(dataset_id)
    return {"status": "ok", "data": batches, "total": len(batches)}


@router.get("/batches/{batch_id}", response_model=dict)
async def get_change_batch(batch_id: str):
    """Get a change batch with entity changes."""
    storage = get_storage()
    from ontology_engine.services.incremental_update import IncrementalUpdateService
    service = IncrementalUpdateService(storage=storage)

    batch = await service.get_change_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    return {"status": "ok", "data": batch}


@router.get("/batches/{batch_id}/rollback-actions", response_model=dict)
async def get_rollback_actions(batch_id: str):
    """Get rollback actions for a change batch."""
    storage = get_storage()
    from ontology_engine.services.incremental_update import IncrementalUpdateService
    service = IncrementalUpdateService(storage=storage)

    actions = await service.get_rollback_actions(batch_id)
    return {"status": "ok", "batch_id": batch_id, "data": actions, "total": len(actions)}


@router.post("/impact", response_model=dict)
async def compute_impact(request: dict[str, Any]):
    """Compute downstream impact of changes.

    Request body:
        changes: list of entity change records
        metric_dependencies: dict of entity_id -> [metric_ids]
        rule_dependencies: dict of entity_id -> [rule_ids]
    """
    storage = get_storage()
    from ontology_engine.services.incremental_update import IncrementalUpdateService, EntityChange, ChangeType

    service = IncrementalUpdateService(storage=storage)
    changes_raw = request.get("changes", [])
    metric_deps = request.get("metric_dependencies", {})
    rule_deps = request.get("rule_dependencies", {})

    changes = []
    for c in changes_raw:
        changes.append(EntityChange(
            entity_id=c.get("entity_id", ""),
            concept=c.get("concept", ""),
            change_type=ChangeType(c.get("change_type", "UPDATED")),
        ))

    impact = await service.compute_impact(changes, metric_deps, rule_deps)
    return {"status": "ok", "data": impact}

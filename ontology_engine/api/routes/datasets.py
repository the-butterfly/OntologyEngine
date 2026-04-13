# ontology_engine/api/routes/datasets.py
"""Dataset management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ontology_engine.api.dependencies import get_storage

router = APIRouter(prefix="/v1/datasets", tags=["Datasets"])


@router.post("", response_model=dict)
async def create_dataset(request: dict[str, Any]):
    """Create a new dataset."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    name = request.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Dataset name is required")

    dataset = await service.create_dataset(
        name=name,
        scope=request.get("scope"),
        source_type=request.get("source_type", "manual"),
        description=request.get("description"),
    )
    return {"status": "ok", "data": dataset}


@router.get("", response_model=dict)
async def list_datasets():
    """List all datasets."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    datasets = await service.list_datasets()
    return {"status": "ok", "data": datasets, "total": len(datasets)}


@router.get("/{dataset_id}", response_model=dict)
async def get_dataset(dataset_id: str):
    """Get a dataset by ID."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    dataset = await service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return {"status": "ok", "data": dataset}


@router.put("/{dataset_id}", response_model=dict)
async def update_dataset(dataset_id: str, request: dict[str, Any]):
    """Update a dataset."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    ok = await service.update_dataset(
        dataset_id=dataset_id,
        name=request.get("name"),
        description=request.get("description"),
        scope=request.get("scope"),
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found or no changes")
    dataset = await service.get_dataset(dataset_id)
    return {"status": "ok", "data": dataset}


@router.delete("/{dataset_id}", response_model=dict)
async def delete_dataset(dataset_id: str):
    """Delete a dataset."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    await service.delete_dataset(dataset_id)
    return {"status": "ok", "deleted": dataset_id}


@router.post("/{dataset_id}/entities", response_model=dict)
async def add_entities_to_dataset(dataset_id: str, request: dict[str, Any]):
    """Add entities to a dataset."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    entities = request.get("entities", [])
    concept = request.get("concept")
    is_primary = request.get("is_primary", False)
    count = await service.add_entities(
        dataset_id=dataset_id,
        entities=entities,
        concept=concept,
        is_primary=is_primary,
    )
    return {"status": "ok", "added_count": count}


@router.get("/{dataset_id}/entities", response_model=dict)
async def get_dataset_entities(dataset_id: str, concept: str | None = None):
    """Get entities in a dataset."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    entities = await service.get_dataset_entities(dataset_id, concept)
    return {"status": "ok", "data": entities, "total": len(entities)}


@router.post("/{dataset_id}/snapshots", response_model=dict)
async def create_snapshot(dataset_id: str, request: dict[str, Any] | None = None):
    """Create a dataset snapshot."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    description = request.get("description") if request else None
    snapshot = await service.create_snapshot(dataset_id=dataset_id, description=description)
    return {"status": "ok", "data": snapshot}


@router.get("/{dataset_id}/snapshots", response_model=dict)
async def get_dataset_snapshots(dataset_id: str):
    """Get snapshots for a dataset."""
    storage = get_storage()
    snapshots = await storage.get_snapshots(dataset_id)
    return {"status": "ok", "data": snapshots}


@router.post("/compare", response_model=dict)
async def compare_datasets(request: dict[str, Any]):
    """Compare two datasets (intersection or diff)."""
    storage = get_storage()
    from ontology_engine.services.dataset_service import DatasetService
    service = DatasetService(storage=storage)

    ds_a = request.get("dataset_a")
    ds_b = request.get("dataset_b")
    mode = request.get("mode", "diff")

    if not ds_a or not ds_b:
        raise HTTPException(status_code=400, detail="dataset_a and dataset_b are required")

    if mode == "intersection":
        result = await service.get_intersection(ds_a, ds_b)
    else:
        result = await service.get_diff(ds_a, ds_b)

    return {"status": "ok", "mode": mode, "data": result}

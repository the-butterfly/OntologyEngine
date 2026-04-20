# ontology_engine/api/routes/datasets.py
"""Dataset management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ontology_engine.api.dependencies import get_dataset_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.services.dataset_service import DatasetService

router = APIRouter(prefix="/v1/datasets", tags=["Datasets"])


@router.post("")
async def create_dataset(
    request: dict[str, Any],
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Create a new dataset."""
    name = request.get("name")
    if not name:
        return error_response(code="INVALID_REQUEST", message="Dataset name is required")

    try:
        dataset = await service.create_dataset(
            name=name,
            scope=request.get("scope"),
            source_type=request.get("source_type", "manual"),
            description=request.get("description"),
        )
        return success_response(data=dataset)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("")
async def list_datasets(
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """List all datasets."""
    try:
        datasets = await service.list_datasets()
        return success_response(data=datasets, meta={"total": len(datasets)})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Get a dataset by ID."""
    try:
        dataset = await service.get_dataset(dataset_id)
        if not dataset:
            return error_response(
                code="NOT_FOUND",
                message=f"Dataset {dataset_id} not found",
            )
        return success_response(data=dataset)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.put("/{dataset_id}")
async def update_dataset(
    dataset_id: str,
    request: dict[str, Any],
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Update a dataset."""
    try:
        ok = await service.update_dataset(
            dataset_id=dataset_id,
            name=request.get("name"),
            description=request.get("description"),
            scope=request.get("scope"),
        )
        if not ok:
            return error_response(
                code="NOT_FOUND",
                message=f"Dataset {dataset_id} not found or no changes",
            )
        dataset = await service.get_dataset(dataset_id)
        return success_response(data=dataset)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Delete a dataset."""
    try:
        await service.delete_dataset(dataset_id)
        return success_response(data={"deleted": dataset_id})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/{dataset_id}/entities")
async def add_entities_to_dataset(
    dataset_id: str,
    request: dict[str, Any],
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Add entities to a dataset."""
    try:
        count = await service.add_entities(
            dataset_id=dataset_id,
            entities=request.get("entities", []),
            concept=request.get("concept"),
            is_primary=request.get("is_primary", False),
        )
        return success_response(data={"added_count": count})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/{dataset_id}/entities")
async def get_dataset_entities(
    dataset_id: str,
    concept: str | None = None,
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Get entities in a dataset."""
    try:
        entities = await service.get_dataset_entities(dataset_id, concept)
        return success_response(data=entities, meta={"total": len(entities)})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/{dataset_id}/snapshots")
async def create_snapshot(
    dataset_id: str,
    request: dict[str, Any] | None = None,
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Create a dataset snapshot."""
    try:
        description = request.get("description") if request else None
        snapshot = await service.create_snapshot(
            dataset_id=dataset_id, description=description
        )
        if "error" in snapshot:
            return error_response(code="NOT_FOUND", message=snapshot["error"])
        return success_response(data=snapshot)
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/{dataset_id}/snapshots")
async def get_dataset_snapshots(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Get snapshots for a dataset."""
    try:
        snapshots = await service.get_snapshots(dataset_id)
        return success_response(data=snapshots, meta={"total": len(snapshots)})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.post("/compare")
async def compare_datasets(
    request: dict[str, Any],
    service: DatasetService = Depends(get_dataset_service),
) -> dict[str, Any]:
    """Compare two datasets (intersection or diff)."""
    ds_a = request.get("dataset_a")
    ds_b = request.get("dataset_b")
    mode = request.get("mode", "diff")

    if not ds_a or not ds_b:
        return error_response(
            code="INVALID_REQUEST",
            message="dataset_a and dataset_b are required",
        )

    if mode not in ("diff", "intersection"):
        return error_response(
            code="INVALID_REQUEST",
            message="mode must be 'diff' or 'intersection'",
        )

    try:
        if mode == "intersection":
            result = await service.get_intersection(ds_a, ds_b)
        else:
            result = await service.get_diff(ds_a, ds_b)
        return success_response(data=result, meta={"mode": mode})
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))

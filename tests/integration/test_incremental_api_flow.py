"""Incremental update API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_import_with_diff_dry_run(client):
    """POST /v1/incremental/import with dry_run=true."""
    resp = await client.post(
        "/v1/incremental/import",
        json={
            "dataset_id": "test_ds",
            "dry_run": True,
            "entities": {
                "E001": {"entity_id": "E001", "_fact_object": "Supplier", "name": "Supplier A"},
            },
        },
    )
    body = resp.json()
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    assert body["success"] is True


@pytest.mark.asyncio
async def test_import_with_diff_missing_entities(client):
    """POST /v1/incremental/import without entities returns error."""
    resp = await client.post(
        "/v1/incremental/import",
        json={"dataset_id": "test_ds", "dry_run": True},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["success"] is False
    assert "INVALID_REQUEST" in body["error"]["code"]


@pytest.mark.asyncio
async def test_list_change_batches(client):
    """GET /v1/incremental/batches returns batch list."""
    resp = await client.get("/v1/incremental/batches")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["success"] is True
    assert "data" in body


@pytest.mark.asyncio
async def test_impact_analysis(client):
    """POST /v1/incremental/impact."""
    resp = await client.post(
        "/v1/incremental/impact",
        json={
            "changes": [
                {"entity_id": "E001", "concept": "Supplier", "change_type": "UPDATED"},
                {"entity_id": "E002", "concept": "Invoice", "change_type": "DELETED"},
            ],
        },
    )
    body = resp.json()
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    assert body["success"] is True

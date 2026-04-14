"""Incremental update API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_import_with_diff_dry_run(client):
    """POST /v1/incremental/import with dry_run=true."""
    resp = await client.post(
        "/v1/incremental/import",
        json={
            "dataset_id": "any_id",
            "dry_run": True,
            "changes": [
                {
                    "entity_id": "E001",
                    "change_type": "upsert",
                    "concept": "Supplier",
                    "properties": {"name": "Supplier A"},
                }
            ],
        },
    )
    # Accept 200 (success) or 400 (dataset not found in test env) but not 500
    assert resp.status_code in (200, 400), f"Got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_list_change_batches(client):
    """GET /v1/incremental/batches returns batch list."""
    resp = await client.get("/v1/incremental/batches")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    assert "data" in resp.json()


@pytest.mark.asyncio
async def test_impact_analysis(client):
    """POST /v1/incremental/impact."""
    resp = await client.post(
        "/v1/incremental/impact",
        json={"entity_ids": ["E001", "E002"], "change_type": "delete"},
    )
    assert resp.status_code in (200, 400), f"Got {resp.status_code}: {resp.text}"

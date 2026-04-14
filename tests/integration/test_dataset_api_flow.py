"""Dataset API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_create_and_retrieve_dataset(client):
    """POST /v1/datasets → GET /v1/datasets/{dataset_id}"""
    create_resp = await client.post(
        "/v1/datasets",
        json={"name": "Test Dataset", "description": "Integration test dataset"},
    )
    assert create_resp.status_code == 200, f"Got {create_resp.status_code}: {create_resp.text}"
    data = create_resp.json()
    assert data["success"] is True
    dataset_id = data["data"]["dataset_id"]

    get_resp = await client.get(f"/v1/datasets/{dataset_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "Test Dataset"


@pytest.mark.asyncio
async def test_list_datasets(client):
    """GET /v1/datasets returns dataset list."""
    for name in ["DS A", "DS B"]:
        await client.post("/v1/datasets", json={"name": name})
    resp = await client.get("/v1/datasets")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_delete_dataset(client):
    """DELETE /v1/datasets/{dataset_id}."""
    create_resp = await client.post("/v1/datasets", json={"name": "To Delete"})
    dataset_id = create_resp.json()["data"]["dataset_id"]
    del_resp = await client.delete(f"/v1/datasets/{dataset_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

# tests/integration/test_dataset_api_flow.py
"""Dataset API flow integration tests.

Covers:
- POST /v1/datasets (create)
- GET  /v1/datasets (list)
- GET  /v1/datasets/{dataset_id} (get)
- PUT  /v1/datasets/{dataset_id} (update)
- DELETE /v1/datasets/{dataset_id} (delete)
- POST /v1/datasets/{dataset_id}/entities (add entities)
- GET  /v1/datasets/{dataset_id}/entities (get entities)
- POST /v1/datasets/{dataset_id}/snapshots (create snapshot)
- GET  /v1/datasets/{dataset_id}/snapshots (list snapshots)
- POST /v1/datasets/compare (compare datasets)
- Error paths: nonexistent dataset, invalid compare params
"""

import pytest


@pytest.mark.asyncio
async def test_create_and_retrieve_dataset(client):
    """POST /v1/datasets -> GET /v1/datasets/{dataset_id}"""
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
    assert get_resp.json()["data"]["description"] == "Integration test dataset"


@pytest.mark.asyncio
async def test_list_datasets(client):
    """GET /v1/datasets returns dataset list."""
    for name in ["DS A", "DS B"]:
        await client.post("/v1/datasets", json={"name": name})
    resp = await client.get("/v1/datasets")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_update_dataset(client):
    """PUT /v1/datasets/{dataset_id}."""
    create_resp = await client.post("/v1/datasets", json={"name": "Original"})
    dataset_id = create_resp.json()["data"]["dataset_id"]

    update_resp = await client.put(
        f"/v1/datasets/{dataset_id}",
        json={"name": "Updated", "description": "Updated desc"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_dataset(client):
    """DELETE /v1/datasets/{dataset_id}."""
    create_resp = await client.post("/v1/datasets", json={"name": "To Delete"})
    dataset_id = create_resp.json()["data"]["dataset_id"]
    del_resp = await client.delete(f"/v1/datasets/{dataset_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    get_resp = await client.get(f"/v1/datasets/{dataset_id}")
    assert get_resp.json()["success"] is False


@pytest.mark.asyncio
async def test_add_and_get_entities(client):
    """POST /v1/datasets/{dataset_id}/entities -> GET."""
    create_resp = await client.post("/v1/datasets", json={"name": "Entity DS"})
    dataset_id = create_resp.json()["data"]["dataset_id"]

    add_resp = await client.post(
        f"/v1/datasets/{dataset_id}/entities",
        json={"entities": [{"entity_id": "E001"}, {"entity_id": "E002"}]},
    )
    assert add_resp.status_code == 200
    assert add_resp.json()["success"] is True

    get_resp = await client.get(f"/v1/datasets/{dataset_id}/entities")
    assert get_resp.status_code == 200
    entities = get_resp.json()["data"]
    entity_ids = [e.get("entity_id") for e in entities]
    assert "E001" in entity_ids
    assert "E002" in entity_ids


@pytest.mark.asyncio
async def test_create_and_list_snapshots(client):
    """POST /v1/datasets/{dataset_id}/snapshots -> GET."""
    create_resp = await client.post("/v1/datasets", json={"name": "Snapshot DS"})
    dataset_id = create_resp.json()["data"]["dataset_id"]

    snapshot_resp = await client.post(
        f"/v1/datasets/{dataset_id}/snapshots",
        json={"description": "v1 snapshot"},
    )
    assert snapshot_resp.status_code == 200
    assert snapshot_resp.json()["success"] is True
    snapshot_data = snapshot_resp.json()["data"]
    assert "snapshot_id" in snapshot_data

    list_resp = await client.get(f"/v1/datasets/{dataset_id}/snapshots")
    assert list_resp.status_code == 200
    snapshots = list_resp.json()["data"]
    assert len(snapshots) == 1
    assert snapshots[0]["description"] == "v1 snapshot"


@pytest.mark.asyncio
async def test_compare_datasets(client):
    """POST /v1/datasets/compare."""
    resp_a = await client.post("/v1/datasets", json={"name": "DS A"})
    resp_b = await client.post("/v1/datasets", json={"name": "DS B"})
    ds_a = resp_a.json()["data"]["dataset_id"]
    ds_b = resp_b.json()["data"]["dataset_id"]

    compare_resp = await client.post(
        "/v1/datasets/compare",
        json={"dataset_a": ds_a, "dataset_b": ds_b, "mode": "diff"},
    )
    assert compare_resp.status_code == 200
    assert compare_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_compare_datasets_intersection(client):
    """POST /v1/datasets/compare with mode=intersection."""
    resp_a = await client.post("/v1/datasets", json={"name": "DS A2"})
    resp_b = await client.post("/v1/datasets", json={"name": "DS B2"})
    ds_a = resp_a.json()["data"]["dataset_id"]
    ds_b = resp_b.json()["data"]["dataset_id"]

    compare_resp = await client.post(
        "/v1/datasets/compare",
        json={"dataset_a": ds_a, "dataset_b": ds_b, "mode": "intersection"},
    )
    assert compare_resp.status_code == 200
    assert compare_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_compare_datasets_invalid_mode(client):
    """POST /v1/datasets/compare with invalid mode."""
    resp_a = await client.post("/v1/datasets", json={"name": "DS A3"})
    resp_b = await client.post("/v1/datasets", json={"name": "DS B3"})
    ds_a = resp_a.json()["data"]["dataset_id"]
    ds_b = resp_b.json()["data"]["dataset_id"]

    compare_resp = await client.post(
        "/v1/datasets/compare",
        json={"dataset_a": ds_a, "dataset_b": ds_b, "mode": "invalid"},
    )
    assert compare_resp.status_code == 200
    body = compare_resp.json()
    assert body["success"] is False
    assert "INVALID_REQUEST" in body["error"]["code"]


@pytest.mark.asyncio
async def test_compare_datasets_missing_params(client):
    """POST /v1/datasets/compare with missing params."""
    compare_resp = await client.post(
        "/v1/datasets/compare",
        json={"dataset_a": "only_one"},
    )
    assert compare_resp.status_code == 200
    body = compare_resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_get_nonexistent_dataset(client):
    """GET /v1/datasets/{nonexistent} returns error."""
    resp = await client.get("/v1/datasets/nonexistent_id")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False


@pytest.mark.asyncio
async def test_snapshot_nonexistent_dataset(client):
    """POST /v1/datasets/{nonexistent}/snapshots returns error."""
    resp = await client.post(
        "/v1/datasets/nonexistent_id/snapshots",
        json={"description": "test"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False

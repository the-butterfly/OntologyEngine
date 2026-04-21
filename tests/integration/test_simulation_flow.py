"""Integration tests for Simulation API flow."""

import pytest


@pytest.mark.asyncio
async def test_simulation_flow(client):
    """Test complete simulation flow: create -> get -> update -> delete."""
    # 1. Create session
    response = await client.post("/v1/simulation/tree", json={
        "schema_id": "test_schema",
        "target_output": "decision",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    session_id = data["data"]["session_id"]

    # 2. Get session
    response = await client.get(f"/v1/simulation/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["session_id"] == session_id

    # 3. Update inputs
    response = await client.patch(f"/v1/simulation/{session_id}", json={
        "input_values": {"credit_score": 80},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated_inputs" in data["data"]

    # 4. Delete session
    response = await client.delete(f"/v1/simulation/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["deleted"] is True

    # Verify it's gone
    response = await client.get(f"/v1/simulation/{session_id}")
    assert response.status_code == 404
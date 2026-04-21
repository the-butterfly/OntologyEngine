"""Integration tests for Simulation API endpoints."""

import pytest


@pytest.mark.asyncio
async def test_create_simulation_session(client):
    """Test POST /v1/simulation/tree creates a simulation session."""
    response = await client.post("/v1/simulation/tree", json={
        "schema_id": "schema_001",
        "target_output": "decision",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data["data"]
    assert "execution_tree" in data["data"]


@pytest.mark.asyncio
async def test_get_simulation_session(client):
    """Test GET /v1/simulation/{session_id} retrieves a session."""
    # Create first
    create_resp = await client.post("/v1/simulation/tree", json={
        "schema_id": "schema_001",
        "target_output": "decision",
    })
    session_id = create_resp.json()["data"]["session_id"]

    # Get
    response = await client.get(f"/v1/simulation/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["session_id"] == session_id


@pytest.mark.asyncio
async def test_update_simulation_inputs(client):
    """Test PATCH /v1/simulation/{session_id} updates inputs."""
    # Create first
    create_resp = await client.post("/v1/simulation/tree", json={
        "schema_id": "schema_001",
        "target_output": "decision",
    })
    session_id = create_resp.json()["data"]["session_id"]

    # Update inputs
    response = await client.patch(f"/v1/simulation/{session_id}", json={
        "input_values": {"credit_score": 80},
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated_inputs" in data["data"]


@pytest.mark.asyncio
async def test_delete_simulation_session(client):
    """Test DELETE /v1/simulation/{session_id} deletes a session."""
    # Create first
    create_resp = await client.post("/v1/simulation/tree", json={
        "schema_id": "schema_001",
        "target_output": "decision",
    })
    session_id = create_resp.json()["data"]["session_id"]

    # Delete
    response = await client.delete(f"/v1/simulation/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["deleted"] is True

    # Verify it's gone
    get_resp = await client.get(f"/v1/simulation/{session_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_simulation_session_not_found(client):
    """Test GET /v1/simulation/{session_id} returns 404 for unknown session."""
    response = await client.get("/v1/simulation/nonexistent-session-id")
    assert response.status_code == 404
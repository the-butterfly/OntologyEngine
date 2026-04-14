"""Category API flow integration tests."""

import pytest


@pytest.mark.asyncio
async def test_create_rule_mapping(client):
    """POST /v1/categories/rule-mappings creates a category-rule mapping."""
    resp = await client.post(
        "/v1/categories/rule-mappings",
        json={
            "dimension_id": "risk_level",
            "dimension_value": "HIGH",
            "rule_group_id": "RG001",
            "mapping_type": "applicable",
        },
    )
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_list_rule_mappings(client):
    """GET /v1/categories/rule-mappings returns mappings."""
    await client.post(
        "/v1/categories/rule-mappings",
        json={
            "dimension_id": "credit_score",
            "dimension_value": "LOW",
            "rule_group_id": "RG002",
        },
    )
    resp = await client.get("/v1/categories/rule-mappings")
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    assert len(resp.json()["data"]) >= 1

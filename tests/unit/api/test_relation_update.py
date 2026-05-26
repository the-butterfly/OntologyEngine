from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


class FakeMetadata:
    def __init__(self, id, name, status=None):
        self.id = id
        self.name = name
        self.description = "test description"
        self.domain = "test_domain"
        self.status = status or MagicMock(value="DRAFT")
        self.created_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
        self.updated_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")


class FakeInstances:
    def __init__(self, relations=None):
        self.entities = []
        self.relations = relations or []


class FakeSpace:
    def __init__(self, space_id="space_test", relations=None):
        self.metadata = FakeMetadata(id=space_id, name="Test Space")
        self.instances = FakeInstances(relations=relations)
        self.layers = MagicMock()
        self.active_version = 1
        self.versions = []


class FakeSpaceService:
    def __init__(self, spaces=None):
        self._spaces = spaces or {}

    async def get_space(self, space_id):
        return self._spaces.get(space_id)

    async def save_space(self, space):
        self._spaces[space.metadata.id] = space

    async def update_relation_in_space(
        self, space_id, relation_id, attributes, reason=""
    ):
        space = self._spaces.get(space_id)
        if not space:
            return None
        for rel in space.instances.relations:
            if rel.get("id") == relation_id:
                rel.update(attributes)
                return {
                    "space_id": space_id,
                    "relation_id": relation_id,
                    "updated_attributes": attributes,
                    "cognitive_node_updated": False,
                }
        return {"space_id": space_id, "error": "Relation not found", "not_found": True}


class TestUpdateRelation:
    @pytest.mark.asyncio
    async def test_update_relation_success(self):
        from ontology_engine.api.routes.semantic_spaces import update_relation

        space = FakeSpace(
            space_id="test-space",
            relations=[
                {
                    "id": "rel-1",
                    "relation_name": "contains",
                    "from_entity_id": "e1",
                    "to_entity_id": "e2",
                    "data": {"weight": 1.0},
                }
            ],
        )
        service = FakeSpaceService(spaces={"test-space": space})

        with patch(
            "ontology_engine.api.routes.semantic_spaces.get_space_service",
            return_value=service,
        ):
            result = await update_relation(
                space_id="test-space",
                relation_id="rel-1",
                request={"attributes": {"weight": 2.0}, "reason": "update weight"},
            )

        assert result["success"] is True
        assert result["data"]["updated_attributes"] == {"weight": 2.0}

    @pytest.mark.asyncio
    async def test_update_relation_not_found(self):
        from ontology_engine.api.routes.semantic_spaces import update_relation

        space = FakeSpace(space_id="test-space", relations=[])
        service = FakeSpaceService(spaces={"test-space": space})

        with patch(
            "ontology_engine.api.routes.semantic_spaces.get_space_service",
            return_value=service,
        ):
            result = await update_relation(
                space_id="test-space",
                relation_id="nonexistent",
                request={"attributes": {"weight": 2.0}},
            )

        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_update_relation_space_not_found(self):
        from ontology_engine.api.routes.semantic_spaces import update_relation

        service = FakeSpaceService(spaces={})

        with patch(
            "ontology_engine.api.routes.semantic_spaces.get_space_service",
            return_value=service,
        ):
            result = await update_relation(
                space_id="nonexistent",
                relation_id="rel-1",
                request={"attributes": {"weight": 2.0}},
            )

        assert result.status_code == 404

from __future__ import annotations

import pytest

from ontology_engine.mcp import init_mcp_dependencies


class FakeInstances:
    def __init__(self, relations=None):
        self.entities = []
        self.relations = relations or []


class FakeSpace:
    def __init__(self, space_id="space_test", relations=None):
        self.metadata = type("M", (), {"id": space_id, "name": "Test"})()
        self.instances = FakeInstances(relations=relations)
        self.layers = type("L", (), {})()
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


class FakeMemoryService:
    def __init__(self):
        self.correct_node_called = False

    async def correct_node(
        self, space_id, node_id, corrected_text, reason="", user_id="system"
    ):
        self.correct_node_called = True
        return {"node_id": node_id, "status": "corrected"}


def _init_fake_service(spaces=None, memory=None):
    service = FakeSpaceService(spaces=spaces)
    services = {"space": service}
    if memory is not None:
        services["memory"] = memory
    init_mcp_dependencies(services=services)
    return service


class TestOEUpdateRelation:
    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_update_relation_via_space_service(self):
        from ontology_engine.mcp.tools.management import oe_update_relation

        space = FakeSpace(
            space_id="test-space",
            relations=[{"id": "rel-1", "relation_name": "contains"}],
        )
        _init_fake_service(spaces={"test-space": space})

        result = await oe_update_relation(
            space_id="test-space",
            relation_id="rel-1",
            attributes={"weight": 2.0},
        )

        assert result["success"] is True
        assert result["data"]["relation_id"] == "rel-1"
        assert result["data"]["cognitive_node_updated"] is False

    @pytest.mark.asyncio
    async def test_update_relation_not_found(self):
        from ontology_engine.mcp.tools.management import oe_update_relation

        space = FakeSpace(space_id="test-space", relations=[])
        _init_fake_service(spaces={"test-space": space})

        result = await oe_update_relation(
            space_id="test-space",
            relation_id="nonexistent",
            attributes={"weight": 2.0},
        )

        assert result["success"] is False
        assert result["error"]["code"] == "RELATION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_relation_space_not_found(self):
        from ontology_engine.mcp.tools.management import oe_update_relation

        _init_fake_service(spaces={})

        result = await oe_update_relation(
            space_id="nonexistent",
            relation_id="rel-1",
            attributes={"weight": 2.0},
        )

        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_relation_with_cognitive_node(self):
        from ontology_engine.mcp.tools.management import oe_update_relation

        space = FakeSpace(
            space_id="test-space",
            relations=[
                {
                    "id": "rel-cog",
                    "relation_name": "contains",
                    "_cognitive_node_id": "cog-node-1",
                }
            ],
        )
        memory = FakeMemoryService()
        _init_fake_service(spaces={"test-space": space}, memory=memory)

        result = await oe_update_relation(
            space_id="test-space",
            relation_id="rel-cog",
            attributes={"weight": 2.0},
            reason="update weight",
        )

        assert result["success"] is True
        assert result["data"]["cognitive_node_updated"] is True
        assert memory.correct_node_called is True

    @pytest.mark.asyncio
    async def test_update_relation_without_deps(self):
        from ontology_engine.mcp.tools.management import oe_update_relation

        result = await oe_update_relation(
            space_id="test-space",
            relation_id="rel-1",
            attributes={"weight": 2.0},
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"

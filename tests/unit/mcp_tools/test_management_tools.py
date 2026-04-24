"""Unit tests for P2 MCP management tools — oe_create_entity, oe_define_rule, oe_activate_space."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.mcp import init_mcp_dependencies


class FakeSpaceService:
    def __init__(self):
        self._spaces = {}
        self._entities = {}
        self._rules = {}

    def add_space(self, space_id, name="Test", status="DRAFT", has_rules=False):
        self._spaces[space_id] = {
            "space_id": space_id,
            "name": name,
            "status": status,
            "has_rules": has_rules,
        }

    async def get_space(self, space_id):
        return self._spaces.get(space_id)

    async def add_entity(self, space_id, entity_id, fact_object, attributes=None):
        if space_id not in self._spaces:
            return None
        if entity_id in self._entities.get(space_id, {}):
            return None
        if space_id not in self._entities:
            self._entities[space_id] = {}
        self._entities[space_id][entity_id] = True
        return {"entity_id": entity_id, "fact_object": fact_object, "space_id": space_id}

    async def define_rule(self, space_id, rule_id, name, dimension="credit_assessment", applies_to=None, description=None):
        if space_id not in self._spaces:
            return None
        if rule_id in self._rules.get(space_id, {}):
            return None
        if space_id not in self._rules:
            self._rules[space_id] = {}
        self._rules[space_id][rule_id] = True
        self._spaces[space_id]["has_rules"] = True
        return {
            "rule_id": rule_id,
            "name": name,
            "dimension": dimension,
            "applies_to": applies_to or [],
            "space_id": space_id,
        }

    async def activate_space(self, space_id):
        if space_id not in self._spaces:
            return None
        space = self._spaces[space_id]
        if space["status"] == "ACTIVE":
            return {"space_id": space_id, "status": "ACTIVE", "active_version": 1, "already_active": True}
        if not space.get("has_rules"):
            return {"space_id": space_id, "no_rules": True}
        space["status"] = "ACTIVE"
        return {"space_id": space_id, "status": "ACTIVE", "active_version": 2}


def _init_fake_service():
    service = FakeSpaceService()
    service.add_space("space_mgmt_test", name="Management Test", has_rules=False)
    init_mcp_dependencies(services={"space": service})
    return service


class TestOECreateEntity:
    """Test oe_create_entity MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_create_entity_success(self):
        from ontology_engine.mcp.tools.management import oe_create_entity

        _init_fake_service()
        result = await oe_create_entity(
            space_id="space_mgmt_test",
            entity_id="SUP_C1",
            fact_object="Supplier",
            attributes={"revenue": 5000000},
        )

        assert result["success"] is True
        assert result["data"]["entity_id"] == "SUP_C1"
        assert result["data"]["fact_object"] == "Supplier"
        assert result["data"]["space_id"] == "space_mgmt_test"

    @pytest.mark.asyncio
    async def test_create_entity_without_attributes(self):
        from ontology_engine.mcp.tools.management import oe_create_entity

        _init_fake_service()
        result = await oe_create_entity(
            space_id="space_mgmt_test",
            entity_id="SUP_C2",
            fact_object="Guarantor",
        )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_entity_space_not_found(self):
        from ontology_engine.mcp.tools.management import oe_create_entity

        _init_fake_service()
        result = await oe_create_entity(
            space_id="space_nonexistent",
            entity_id="SUP_C1",
            fact_object="Supplier",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_create_entity_without_deps(self):
        from ontology_engine.mcp.tools.management import oe_create_entity

        result = await oe_create_entity(
            space_id="space_test",
            entity_id="SUP_C1",
            fact_object="Supplier",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"


class TestOEDefineRule:
    """Test oe_define_rule MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_define_rule_success(self):
        from ontology_engine.mcp.tools.management import oe_define_rule

        _init_fake_service()
        result = await oe_define_rule(
            space_id="space_mgmt_test",
            rule_id="rule_credit_score",
            name="Credit Score Check",
            dimension="credit_assessment",
            applies_to=["Supplier"],
        )

        assert result["success"] is True
        assert result["data"]["rule_id"] == "rule_credit_score"
        assert result["data"]["name"] == "Credit Score Check"
        assert result["data"]["dimension"] == "credit_assessment"
        assert result["data"]["applies_to"] == ["Supplier"]

    @pytest.mark.asyncio
    async def test_define_rule_minimal(self):
        from ontology_engine.mcp.tools.management import oe_define_rule

        _init_fake_service()
        result = await oe_define_rule(
            space_id="space_mgmt_test",
            rule_id="rule_minimal",
            name="Minimal Rule",
        )

        assert result["success"] is True
        assert result["data"]["applies_to"] == []
        assert result["data"]["dimension"] == "credit_assessment"

    @pytest.mark.asyncio
    async def test_define_rule_duplicate_id(self):
        from ontology_engine.mcp.tools.management import oe_define_rule

        service = _init_fake_service()
        await service.define_rule("space_mgmt_test", "rule_existing", "Existing")
        result = await oe_define_rule(
            space_id="space_mgmt_test",
            rule_id="rule_existing",
            name="Duplicate Rule",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DUPLICATE_RULE_ID"

    @pytest.mark.asyncio
    async def test_define_rule_space_not_found(self):
        from ontology_engine.mcp.tools.management import oe_define_rule

        _init_fake_service()
        result = await oe_define_rule(
            space_id="space_nonexistent",
            rule_id="rule_test",
            name="Test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DUPLICATE_RULE_ID"


class TestOEActivateSpace:
    """Test oe_activate_space MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_activate_space_success(self):
        from ontology_engine.mcp.tools.management import oe_activate_space

        service = _init_fake_service()
        service.add_space("space_active_test", name="Active Test", has_rules=True)
        result = await oe_activate_space(space_id="space_active_test")

        assert result["success"] is True
        assert result["data"]["status"] == "ACTIVE"

    @pytest.mark.asyncio
    async def test_activate_space_already_active(self):
        from ontology_engine.mcp.tools.management import oe_activate_space

        service = _init_fake_service()
        service.add_space("space_already_active", name="Already Active", status="ACTIVE", has_rules=True)
        result = await oe_activate_space(space_id="space_already_active")

        assert result["success"] is True
        assert result["data"]["note"] == "Space was already active"

    @pytest.mark.asyncio
    async def test_activate_space_no_schema(self):
        from ontology_engine.mcp.tools.management import oe_activate_space

        _init_fake_service()
        result = await oe_activate_space(space_id="space_mgmt_test")

        assert result["success"] is False
        assert result["error"]["code"] == "SCHEMA_NOT_LOADED"

    @pytest.mark.asyncio
    async def test_activate_space_not_found(self):
        from ontology_engine.mcp.tools.management import oe_activate_space

        _init_fake_service()
        result = await oe_activate_space(space_id="space_nonexistent")

        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"

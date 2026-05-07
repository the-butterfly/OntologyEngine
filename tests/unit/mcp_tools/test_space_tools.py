"""Unit tests for MCP space tools — oe_create_space, oe_list_spaces, oe_load_schema."""

import pytest

from ontology_engine.mcp import init_mcp_dependencies


class FakeSpaceService:
    def __init__(self, spaces=None):
        self._spaces = spaces or {}
        self._next_id = 0

    async def create_space(self, name, description=None, domain=None):
        self._next_id += 1
        space_id = f"space_{self._next_id:08d}"
        self._spaces[space_id] = {
            "space_id": space_id,
            "name": name,
            "description": description,
            "domain": domain,
            "status": "draft",
        }
        return self._spaces[space_id]

    async def get_space(self, space_id):
        from ontology_engine.core.semantic_space import SemanticSpace
        entry = self._spaces.get(space_id)
        if entry and isinstance(entry, SemanticSpace):
            return entry
        return None

    async def list_spaces(self):
        result = []
        for sid, entry in self._spaces.items():
            if isinstance(entry, dict):
                result.append({
                    "space_id": sid,
                    "name": entry.get("name"),
                    "status": entry.get("status", "DRAFT"),
                    "domain": entry.get("domain"),
                    "entity_count": 0,
                })
        return result

    async def get_schema_overview(self, space_id):
        entry = self._spaces.get(space_id)
        if not entry:
            return None
        if isinstance(entry, dict):
            return {
                "space_id": space_id,
                "name": entry.get("name"),
                "active_version": 1,
                "layers": {"L1": {"fact_objects": 0}, "L2": {"categorizations": 0}, "L3": {"analytical_elements": 0}, "L4": {"rule_definitions": 0, "rule_logics": 0}},
            }
        return None


def _init_fake_service(spaces=None):
    service = FakeSpaceService(spaces)
    init_mcp_dependencies(services={"space": service})
    return service


class TestOECreateSpace:
    """Test oe_create_space MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_create_space_success(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        _init_fake_service()
        result = await oe_create_space(name="Test Space", description="desc", domain="finance")

        assert result["success"] is True
        assert result["data"]["name"] == "Test Space"
        assert result["data"]["description"] == "desc"
        assert result["data"]["domain"] == "finance"
        assert result["data"]["status"].lower() == "draft"
        assert result["data"]["space_id"].startswith("space_")

    @pytest.mark.asyncio
    async def test_create_space_minimal_args(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        _init_fake_service()
        result = await oe_create_space(name="Minimal Space")

        assert result["success"] is True
        assert result["data"]["name"] == "Minimal Space"
        assert result["data"]["description"] is None
        assert result["data"]["domain"] is None

    @pytest.mark.asyncio
    async def test_create_space_returns_mcp_format(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        _init_fake_service()
        result = await oe_create_space(name="Format Test")

        assert "success" in result
        assert "data" in result
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_space_without_deps_returns_error(self):
        from ontology_engine.mcp.tools.space import oe_create_space

        result = await oe_create_space(name="No Deps")
        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"


class TestOEListSpaces:
    """Test oe_list_spaces MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_list_spaces_empty(self):
        from ontology_engine.mcp.tools.space import oe_list_spaces

        _init_fake_service()
        result = await oe_list_spaces()

        assert result["success"] is True
        assert result["data"]["spaces"] == []
        assert result["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_spaces_with_existing_spaces(self):
        from ontology_engine.mcp.tools.space import oe_list_spaces, oe_create_space

        _init_fake_service()
        await oe_create_space(name="Space A", domain="finance")
        await oe_create_space(name="Space B", domain="compliance")

        result = await oe_list_spaces()

        assert result["success"] is True
        assert result["data"]["total"] == 2
        names = [s["name"] for s in result["data"]["spaces"]]
        assert "Space A" in names
        assert "Space B" in names

    @pytest.mark.asyncio
    async def test_list_spaces_without_deps_returns_error(self):
        from ontology_engine.mcp.tools.space import oe_list_spaces

        result = await oe_list_spaces()
        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"


class TestOELoadSchema:
    """Test oe_load_schema MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_load_schema_existing_space(self):
        from ontology_engine.mcp.tools.space import oe_load_schema

        _init_fake_service({"space_schema_test": {"name": "Schema Test", "status": "DRAFT"}})
        result = await oe_load_schema(space_id="space_schema_test")

        assert result["success"] is True
        assert result["data"]["space_id"] == "space_schema_test"
        assert result["data"]["name"] == "Schema Test"

    @pytest.mark.asyncio
    async def test_load_schema_nonexistent_space(self):
        from ontology_engine.mcp.tools.space import oe_load_schema

        _init_fake_service()
        result = await oe_load_schema(space_id="space_nonexistent")

        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"
        assert result["error"]["suggestion"] == "Use oe_list_spaces to find available spaces"

    @pytest.mark.asyncio
    async def test_load_schema_without_deps_returns_error(self):
        from ontology_engine.mcp.tools.space import oe_load_schema

        result = await oe_load_schema(space_id="any")
        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"

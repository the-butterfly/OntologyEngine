"""Unit tests for MCP execution tools — oe_execute_rule, oe_simulate."""

import pytest
from unittest.mock import MagicMock

from ontology_engine.mcp import init_mcp_dependencies


class FakeMetadata:
    def __init__(self, id, name, status=None):
        self.id = id
        self.name = name
        self.status = status or MagicMock(value="ACTIVE")


class FakeInstances:
    def __init__(self, entities=None):
        self.entities = entities or []


class FakeL4:
    def __init__(self):
        self.rule_definitions = []
        self.rule_logics = []


class FakeLayers:
    def __init__(self):
        self.L1_fact_objects = []
        self.L2_categorizations = []
        self.L3_analytical_elements = []
        self.L4_business_logic = FakeL4()


class FakeSpace:
    def __init__(self, space_id="space_test01", name="Test", entities=None):
        self.metadata = FakeMetadata(id=space_id, name=name)
        self.instances = FakeInstances(entities=entities or [])
        self.layers = FakeLayers()
        self.active_version = 1


class FakeSpaceService:
    def __init__(self, spaces=None):
        self._spaces = spaces or {}

    async def get_space(self, space_id):
        return self._spaces.get(space_id)


class FakeAnalysisResult:
    def __init__(self, entity_id="E1", dimension="credit_assessment"):
        self.entity_id = entity_id
        self.fact_object = "Supplier"
        self.dimension = dimension
        self.decision = "approved"
        self.decision_reasoning = "All checks passed"
        self.computed_metrics = {"score": 85.0}
        self.category_tags = ["low_risk"]
        self.rule_results = []
        self.alerts = []


class FakeAnalysisService:
    def __init__(self):
        pass

    async def execute_analysis(self, entity_id, dimension, context):
        return FakeAnalysisResult(entity_id=entity_id, dimension=dimension)

    async def execute_dry_run(self, entity_id, dimension, context):
        return FakeAnalysisResult(entity_id=entity_id, dimension=dimension)


def _init_fake_deps(entities=None):
    space = FakeSpace(
        space_id="space_test",
        name="Test Space",
        entities=entities or [{"entity_id": "SUP_C1", "_fact_object": "Supplier"}],
    )
    space_svc = FakeSpaceService({"space_test": space})
    analysis_svc = FakeAnalysisService()
    init_mcp_dependencies(services={"space": space_svc, "analysis": analysis_svc})
    return space_svc, analysis_svc


class TestOEExecuteRule:
    """Test oe_execute_rule MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_execute_rule_success(self):
        from ontology_engine.mcp.tools.execution import oe_execute_rule

        _init_fake_deps()
        result = await oe_execute_rule(
            entity_id="SUP_C1",
            view_id="space_test",
            dimension="credit_assessment",
        )

        assert result["success"] is True
        assert result["data"]["entity_id"] == "SUP_C1"
        assert result["data"]["dimension"] == "credit_assessment"
        assert result["data"]["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_execute_rule_dry_run(self):
        from ontology_engine.mcp.tools.execution import oe_execute_rule

        _init_fake_deps()
        result = await oe_execute_rule(
            entity_id="SUP_C1",
            view_id="space_test",
            dry_run=True,
        )

        assert result["success"] is True
        assert result["data"]["dry_run"] is True

    @pytest.mark.asyncio
    async def test_execute_rule_space_not_found(self):
        from ontology_engine.mcp.tools.execution import oe_execute_rule

        _init_fake_deps()
        result = await oe_execute_rule(
            entity_id="SUP_C1",
            view_id="space_nonexistent",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_execute_rule_entity_not_found(self):
        from ontology_engine.mcp.tools.execution import oe_execute_rule

        _init_fake_deps()
        result = await oe_execute_rule(
            entity_id="SUP_NONEXISTENT",
            view_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_execute_rule_without_deps(self):
        from ontology_engine.mcp.tools.execution import oe_execute_rule

        result = await oe_execute_rule(
            entity_id="SUP_C1",
            view_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"


class TestOESimulate:
    """Test oe_simulate MCP tool."""

    def setup_method(self):
        import ontology_engine.mcp as mcp_mod
        mcp_mod._services = None

    @pytest.mark.asyncio
    async def test_simulate_success(self):
        from ontology_engine.mcp.tools.execution import oe_simulate

        _init_fake_deps()
        result = await oe_simulate(
            entity_id="SUP_C1",
            view_id="space_test",
            dimension="credit_assessment",
            overrides={"revenue": 5000000},
        )

        assert result["success"] is True
        assert "baseline" in result["data"]
        assert "simulated" in result["data"]
        assert result["data"]["overrides_applied"] == {"revenue": 5000000}

    @pytest.mark.asyncio
    async def test_simulate_no_overrides(self):
        from ontology_engine.mcp.tools.execution import oe_simulate

        _init_fake_deps()
        result = await oe_simulate(
            entity_id="SUP_C1",
            view_id="space_test",
        )

        assert result["success"] is True
        assert result["data"]["overrides_applied"] == {}

    @pytest.mark.asyncio
    async def test_simulate_space_not_found(self):
        from ontology_engine.mcp.tools.execution import oe_simulate

        _init_fake_deps()
        result = await oe_simulate(
            entity_id="SUP_C1",
            view_id="space_nonexistent",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "SPACE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_simulate_entity_not_found(self):
        from ontology_engine.mcp.tools.execution import oe_simulate

        _init_fake_deps()
        result = await oe_simulate(
            entity_id="SUP_NONEXISTENT",
            view_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "ENTITY_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_simulate_without_deps(self):
        from ontology_engine.mcp.tools.execution import oe_simulate

        result = await oe_simulate(
            entity_id="SUP_C1",
            view_id="space_test",
        )

        assert result["success"] is False
        assert result["error"]["code"] == "DEPS_NOT_INITIALIZED"

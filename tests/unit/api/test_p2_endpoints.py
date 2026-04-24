"""Unit tests for P2 API endpoints — impact analysis, entity/rule versions, ETag."""

import pytest
from unittest.mock import patch, MagicMock

from ontology_engine.api.dto.responses import error_response


class FakeMetadata:
    def __init__(self, id, name, status=None):
        self.id = id
        self.name = name
        self.description = "test description"
        self.domain = "test_domain"
        self.status = status or MagicMock(value="ACTIVE")
        self.created_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
        self.updated_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")


class FakeVersion:
    def __init__(self, version, space_id, description=""):
        self.version = version
        self.space_id = space_id
        self.created_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
        self.change_description = description
        self.snapshot_path = None
        self.is_stable = True


class FakeInstances:
    def __init__(self, entities=None):
        self.entities = entities or []
        self.relations = []


class FakeL4:
    def __init__(self):
        self.rule_definitions = [
            {"id": "rule_credit", "name": "Credit Check", "dimension": "credit_assessment", "applies_to": ["Supplier"]},
        ]
        self.rule_logics = [
            {"id": "logic_1", "definition_id": "rule_credit"},
        ]


class FakeLayers:
    def __init__(self):
        self.L1_fact_objects = []
        self.L2_categorizations = []
        self.L3_analytical_elements = []
        self.L4_business_logic = FakeL4()


class FakeSpace:
    def __init__(self, space_id="space_p2_test", name="P2 Test"):
        self.metadata = FakeMetadata(id=space_id, name=name)
        self.instances = FakeInstances(entities=[
            {"entity_id": "SUP_C1", "_fact_object": "Supplier", "revenue": 5000000},
        ])
        self.layers = FakeLayers()
        self.active_version = 1
        self.versions = []


class FakeStorage:
    def __init__(self, spaces=None):
        self._spaces = spaces or {}
        self._version_snapshots = {}

    async def load(self, space_id):
        return self._spaces.get(space_id)

    async def load_version(self, space_id, version, *, space=None):
        return self._version_snapshots.get((space_id, version))

    async def save(self, space):
        self._spaces[space.metadata.id] = space


@pytest.fixture
def fake_storage():
    space = FakeSpace()
    storage = FakeStorage({"space_p2_test": space})
    v1_space = FakeSpace()
    v1_space.metadata = FakeMetadata(id="space_p2_test", name="P2 Test v1")
    v1_space.instances = FakeInstances(entities=[
        {"entity_id": "SUP_C1", "_fact_object": "Supplier", "revenue": 3000000},
    ])
    v1_space.layers = FakeLayers()
    v1_space.active_version = 1
    v1_space.versions = []
    storage._version_snapshots[("space_p2_test", 1)] = v1_space

    space.versions = [FakeVersion(version=1, space_id="space_p2_test", description="Initial")]
    space.versions[0].snapshot_path = "fake_path"

    return storage


class TestSchemaImpactAnalysis:
    """Test POST /v1/spaces/{space_id}/schema/impact-analysis."""

    @pytest.mark.asyncio
    async def test_impact_analysis_rule_change(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import analyze_schema_impact, SchemaImpactAnalysisRequest

            result = await analyze_schema_impact(
                space_id="space_p2_test",
                request=SchemaImpactAnalysisRequest(change_type="rule_definition", target="rule_credit"),
            )

        assert result["success"] is True
        assert result["data"]["affected_rules_count"] >= 1
        assert result["data"]["affected_dimensions"] == ["credit_assessment"]

    @pytest.mark.asyncio
    async def test_impact_analysis_entity_type_change(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import analyze_schema_impact, SchemaImpactAnalysisRequest

            result = await analyze_schema_impact(
                space_id="space_p2_test",
                request=SchemaImpactAnalysisRequest(change_type="fact_object", target="Supplier"),
            )

        assert result["success"] is True
        assert result["data"]["affected_entities_count"] == 1
        assert result["data"]["affected_entities"][0]["entity_id"] == "SUP_C1"

    @pytest.mark.asyncio
    async def test_impact_analysis_space_not_found(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import analyze_schema_impact, SchemaImpactAnalysisRequest

            result = await analyze_schema_impact(
                space_id="space_nonexistent",
                request=SchemaImpactAnalysisRequest(change_type="rule_definition", target="rule_1"),
            )

        assert result.status_code == 404


class TestEntityVersions:
    """Test GET /v1/spaces/{space_id}/instances/entities/{entity_id}/versions."""

    @pytest.mark.asyncio
    async def test_list_entity_versions(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import list_entity_versions

            result = await list_entity_versions(
                space_id="space_p2_test",
                entity_id="SUP_C1",
            )

        assert result["success"] is True
        assert result["data"]["entity_id"] == "SUP_C1"
        assert result["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_entity_versions_not_found(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import list_entity_versions

            result = await list_entity_versions(
                space_id="space_p2_test",
                entity_id="NONEXISTENT",
            )

        assert result.status_code == 404


class TestRuleVersions:
    """Test GET /v1/spaces/{space_id}/rules/definitions/{rule_id}/versions."""

    @pytest.mark.asyncio
    async def test_list_rule_versions(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import list_rule_versions

            result = await list_rule_versions(
                space_id="space_p2_test",
                rule_id="rule_credit",
            )

        assert result["success"] is True
        assert result["data"]["rule_id"] == "rule_credit"
        assert result["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_rule_versions_not_found(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import list_rule_versions

            result = await list_rule_versions(
                space_id="space_p2_test",
                rule_id="rule_nonexistent",
            )

        assert result.status_code == 404


class TestETag:
    """Test GET /v1/spaces/{space_id}/etag and PUT with If-Match."""

    @pytest.mark.asyncio
    async def test_get_space_etag(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import get_space_etag

            result = await get_space_etag(space_id="space_p2_test")

        assert result["success"] is True
        assert "etag" in result["data"]
        assert len(result["data"]["etag"]) == 16

    @pytest.mark.asyncio
    async def test_etag_consistency(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import get_space_etag

            result1 = await get_space_etag(space_id="space_p2_test")
            result2 = await get_space_etag(space_id="space_p2_test")

        assert result1["data"]["etag"] == result2["data"]["etag"]

    @pytest.mark.asyncio
    async def test_etag_changes_with_metadata(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import get_space_etag, update_space_metadata
            from ontology_engine.api.routes.semantic_spaces import UpdateSpaceMetadataRequest

            etag_before = await get_space_etag(space_id="space_p2_test")
            etag1 = etag_before["data"]["etag"]

            await update_space_metadata(
                space_id="space_p2_test",
                request=UpdateSpaceMetadataRequest(name="Changed Name"),
                if_match=None,
            )

            etag_after = await get_space_etag(space_id="space_p2_test")
            etag2 = etag_after["data"]["etag"]

        assert etag1 != etag2, "ETag should change when metadata is updated"

    @pytest.mark.asyncio
    async def test_update_with_valid_etag(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import get_space_etag, update_space_metadata
            from ontology_engine.api.routes.semantic_spaces import UpdateSpaceMetadataRequest

            etag_result = await get_space_etag(space_id="space_p2_test")
            etag = etag_result["data"]["etag"]

            result = await update_space_metadata(
                space_id="space_p2_test",
                request=UpdateSpaceMetadataRequest(name="Updated Name"),
                if_match=etag,
            )

        assert result["success"] is True
        data = result["data"]
        name = data.name if hasattr(data, "name") else data.get("name")
        assert name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_with_invalid_etag_returns_412(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import update_space_metadata
            from ontology_engine.api.routes.semantic_spaces import UpdateSpaceMetadataRequest

            result = await update_space_metadata(
                space_id="space_p2_test",
                request=UpdateSpaceMetadataRequest(name="Should Fail"),
                if_match="invalid_etag_value",
            )

        assert result.status_code == 412
        import json
        body = json.loads(result.body)
        assert body["error"]["code"] == "PRECONDITION_FAILED"
        assert "suggestion" in body["error"]
        assert "current_etag" in body["error"]["details"]

    @pytest.mark.asyncio
    async def test_update_without_etag_succeeds(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import update_space_metadata
            from ontology_engine.api.routes.semantic_spaces import UpdateSpaceMetadataRequest

            result = await update_space_metadata(
                space_id="space_p2_test",
                request=UpdateSpaceMetadataRequest(name="No ETag Update"),
                if_match=None,
            )

        assert result["success"] is True


class TestUpdateRuleDefinitionDryRun:
    """Test PUT /v1/spaces/{space_id}/rules/definitions/{rule_id} with dry_run."""

    @pytest.mark.asyncio
    async def test_update_rule_definition_dry_run(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import update_rule_definition
            from ontology_engine.api.routes.semantic_spaces import CreateRuleDefinitionRequest

            result = await update_rule_definition(
                space_id="space_p2_test",
                rule_id="rule_credit",
                request=CreateRuleDefinitionRequest(
                    id="rule_credit",
                    name="Updated Credit Check",
                    rule_type="constraint",
                ),
                dry_run=True,
            )

        assert result["success"] is True
        assert result["data"]["dry_run"] is True
        assert "current_definition" in result["data"]
        assert "proposed_definition" in result["data"]
        assert result["data"]["current_definition"]["name"] == "Credit Check"
        assert result["data"]["proposed_definition"]["name"] == "Updated Credit Check"

    @pytest.mark.asyncio
    async def test_update_rule_definition_actual(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import update_rule_definition
            from ontology_engine.api.routes.semantic_spaces import CreateRuleDefinitionRequest

            result = await update_rule_definition(
                space_id="space_p2_test",
                rule_id="rule_credit",
                request=CreateRuleDefinitionRequest(
                    id="rule_credit",
                    name="Updated Credit Check",
                    rule_type="constraint",
                ),
                dry_run=False,
            )

        assert result["success"] is True
        assert result["data"]["name"] == "Updated Credit Check"


class TestComputeEtag:
    """Test _compute_etag helper function."""

    def test_etag_includes_metadata(self):
        from ontology_engine.api.routes.semantic_spaces import _compute_etag

        space1 = FakeSpace(name="Space A")
        space2 = FakeSpace(name="Space B")

        etag1 = _compute_etag(space1)
        etag2 = _compute_etag(space2)

        assert etag1 != etag2, "ETag should differ when metadata name differs"

    def test_etag_includes_status(self):
        from ontology_engine.api.routes.semantic_spaces import _compute_etag

        space1 = FakeSpace()
        space1.metadata.status = MagicMock(value="DRAFT")

        space2 = FakeSpace()
        space2.metadata.status = MagicMock(value="ACTIVE")

        etag1 = _compute_etag(space1)
        etag2 = _compute_etag(space2)

        assert etag1 != etag2, "ETag should differ when status differs"

    def test_etag_includes_domain(self):
        from ontology_engine.api.routes.semantic_spaces import _compute_etag

        space1 = FakeSpace()
        space1.metadata.domain = "finance"

        space2 = FakeSpace()
        space2.metadata.domain = "compliance"

        etag1 = _compute_etag(space1)
        etag2 = _compute_etag(space2)

        assert etag1 != etag2, "ETag should differ when domain differs"


class TestExtractAppliesToFactObjects:
    """Test _extract_applies_to_fact_objects helper function."""

    def test_list_str_format(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {"applies_to": ["Supplier", "Buyer"]}
        result = _extract_applies_to_fact_objects(rule)
        assert result == ["Supplier", "Buyer"]

    def test_dict_format(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {"applies_to": {"fact_objects": ["Supplier"], "categories": {"risk": ["high"]}}}
        result = _extract_applies_to_fact_objects(rule)
        assert result == ["Supplier"]

    def test_list_dict_format(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {"applies_to": [{"id": "Supplier"}, {"name": "Buyer"}]}
        result = _extract_applies_to_fact_objects(rule)
        assert "Supplier" in result
        assert "Buyer" in result

    def test_empty_applies_to(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {"applies_to": []}
        result = _extract_applies_to_fact_objects(rule)
        assert result == []

    def test_missing_applies_to(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {}
        result = _extract_applies_to_fact_objects(rule)
        assert result == []

    def test_legacy_target_objects_key(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {"target_objects": ["Supplier"]}
        result = _extract_applies_to_fact_objects(rule)
        assert result == ["Supplier"]

    def test_dict_format_empty_fact_objects(self):
        from ontology_engine.api.routes.semantic_spaces import _extract_applies_to_fact_objects

        rule = {"applies_to": {"fact_objects": [], "categories": {"risk": ["high"]}}}
        result = _extract_applies_to_fact_objects(rule)
        assert result == []


class TestImpactAnalysisAppliesToCompat:
    """Test impact analysis with different applies_to formats."""

    @pytest.mark.asyncio
    async def test_impact_analysis_with_dict_applies_to(self):
        from ontology_engine.api.routes.semantic_spaces import analyze_schema_impact, SchemaImpactAnalysisRequest

        space = FakeSpace()
        space.layers.L4_business_logic.rule_definitions = [
            {
                "id": "rule_supplier",
                "name": "Supplier Check",
                "dimension": "credit_assessment",
                "applies_to": {"fact_objects": ["Supplier"], "categories": {}},
            },
        ]

        storage = FakeStorage({"space_p2_test": space})

        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=storage,
        ):
            result = await analyze_schema_impact(
                space_id="space_p2_test",
                request=SchemaImpactAnalysisRequest(change_type="fact_object", target="Supplier"),
            )

        assert result["success"] is True
        assert result["data"]["affected_rules_count"] >= 1
        assert any(r.get("impact") == "applies_to_match" for r in result["data"]["affected_rules"])

    @pytest.mark.asyncio
    async def test_impact_analysis_with_list_str_applies_to(self):
        from ontology_engine.api.routes.semantic_spaces import analyze_schema_impact, SchemaImpactAnalysisRequest

        space = FakeSpace()
        space.layers.L4_business_logic.rule_definitions = [
            {
                "id": "rule_supplier",
                "name": "Supplier Check",
                "dimension": "credit_assessment",
                "applies_to": ["Supplier"],
            },
        ]

        storage = FakeStorage({"space_p2_test": space})

        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=storage,
        ):
            result = await analyze_schema_impact(
                space_id="space_p2_test",
                request=SchemaImpactAnalysisRequest(change_type="fact_object", target="Supplier"),
            )

        assert result["success"] is True
        assert result["data"]["affected_rules_count"] >= 1


class TestSchemaImpactAnalysisRequestValidation:
    """Test SchemaImpactAnalysisRequest Literal constraint."""

    def test_valid_change_types(self):
        from ontology_engine.api.routes.semantic_spaces import SchemaImpactAnalysisRequest

        for ct in ["rule_definition", "rule_logic", "fact_object", "entity_type"]:
            req = SchemaImpactAnalysisRequest(change_type=ct, target="test")
            assert req.change_type == ct

    def test_invalid_change_type_raises(self):
        from ontology_engine.api.routes.semantic_spaces import SchemaImpactAnalysisRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SchemaImpactAnalysisRequest(change_type="invalid_type", target="test")

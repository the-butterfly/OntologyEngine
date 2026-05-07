"""Unit tests for API dry-run support — DELETE space, DELETE rule definition, rollback."""

import pytest
from unittest.mock import MagicMock, patch



class FakeMetadata:
    def __init__(self, id, name, status=None, domain=None, description=None):
        self.id = id
        self.name = name
        self.description = description
        self.domain = domain
        self.status = status or MagicMock(value="ACTIVE")
        self.created_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")
        self.updated_at = MagicMock(isoformat=lambda: "2026-01-01T00:00:00")


class FakeInstances:
    def __init__(self, entities=None, relations=None):
        self.entities = entities or [{"entity_id": "E1"}, {"entity_id": "E2"}]
        self.relations = relations or []


class FakeL4:
    def __init__(self):
        self.rule_definitions = [
            {"id": "rule_1", "name": "Credit Rule", "applies_to": []},
        ]
        self.rule_logics = [
            {"id": "logic_1", "definition_id": "rule_1", "when": {}, "then_action": {}},
        ]


class FakeLayers:
    def __init__(self):
        self.L1_fact_objects = [{"id": "fo_1"}]
        self.L2_categorizations = [{"id": "cat_1"}]
        self.L3_analytical_elements = [{"id": "ae_1"}]
        self.L4_business_logic = FakeL4()


class FakeSpace:
    def __init__(self, space_id="space_test01", name="Test Space"):
        self.metadata = FakeMetadata(id=space_id, name=name)
        self.instances = FakeInstances()
        self.layers = FakeLayers()
        self.active_version = 1


class FakeStorage:
    def __init__(self, spaces=None):
        self._spaces = spaces or {}
        self._versions = {}

    async def load(self, space_id):
        return self._spaces.get(space_id)

    async def load_version(self, space_id, version, *, space=None):
        return self._versions.get((space_id, version))

    async def save(self, space):
        self._spaces[space.metadata.id] = space

    async def delete(self, space_id):
        return self._spaces.pop(space_id, None) is not None

    async def list(self):
        return [s.metadata for s in self._spaces.values()]

    async def create_snapshot(self, space, description=None):
        version = space.active_version + 1
        self._versions[(space.metadata.id, version)] = space
        return version

    async def rollback_to_version(self, space_id, version):
        target = self._versions.get((space_id, version))
        if target:
            self._spaces[space_id] = target
            return target
        return None


@pytest.fixture
def fake_storage():
    space = FakeSpace(space_id="space_dry_run_test", name="Dry Run Test")
    storage = FakeStorage({"space_dry_run_test": space})
    storage._versions[("space_dry_run_test", 1)] = space
    return storage


class TestDeleteSpaceDryRun:
    """Test DELETE /v1/spaces/{space_id}?dry_run=true."""

    @pytest.mark.asyncio
    async def test_delete_space_dry_run_returns_preview(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_space

            result = await delete_space(
                space_id="space_dry_run_test",
                dry_run=True,
            )

        assert result["success"] is True
        assert result["data"]["dry_run"] is True
        assert result["data"]["would_delete"]["space_id"] == "space_dry_run_test"
        assert result["data"]["would_delete"]["space_name"] == "Dry Run Test"
        assert result["data"]["would_delete"]["entities"] == 2
        assert result["data"]["would_delete"]["rule_definitions"] == 1

    @pytest.mark.asyncio
    async def test_delete_space_dry_run_does_not_delete(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_space

            await delete_space(space_id="space_dry_run_test", dry_run=True)

        space = await fake_storage.load("space_dry_run_test")
        assert space is not None, "Space should still exist after dry_run"

    @pytest.mark.asyncio
    async def test_delete_space_actual_delete(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_space

            result = await delete_space(
                space_id="space_dry_run_test",
                dry_run=False,
            )

        assert result["success"] is True
        assert result["data"]["deleted"] is True
        assert result["data"]["space_id"] == "space_dry_run_test"
        space = await fake_storage.load("space_dry_run_test")
        assert space is None, "Space should be deleted after actual delete"

    @pytest.mark.asyncio
    async def test_delete_space_nonexistent_dry_run(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_space

            result = await delete_space(space_id="space_nonexistent", dry_run=True)

        assert result.status_code == 404


class TestDeleteRuleDefinitionDryRun:
    """Test DELETE /v1/spaces/{space_id}/rules/definitions/{rule_id}?dry_run=true."""

    @pytest.mark.asyncio
    async def test_delete_rule_dry_run_shows_dependent_logics(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_rule_definition

            result = await delete_rule_definition(
                space_id="space_dry_run_test",
                rule_id="rule_1",
                dry_run=True,
            )

        assert result["success"] is True
        assert result["data"]["dry_run"] is True
        assert result["data"]["would_delete"]["rule_definition"]["id"] == "rule_1"
        assert result["data"]["would_delete"]["dependent_rule_logics"] == 1
        assert "logic_1" in result["data"]["would_delete"]["dependent_logic_ids"]

    @pytest.mark.asyncio
    async def test_delete_rule_dry_run_does_not_delete(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_rule_definition

            await delete_rule_definition(
                space_id="space_dry_run_test",
                rule_id="rule_1",
                dry_run=True,
            )

        space = await fake_storage.load("space_dry_run_test")
        assert len(space.layers.L4_business_logic.rule_definitions) == 1
        assert len(space.layers.L4_business_logic.rule_logics) == 1

    @pytest.mark.asyncio
    async def test_delete_rule_actual_delete_cascades_logics(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_rule_definition

            result = await delete_rule_definition(
                space_id="space_dry_run_test",
                rule_id="rule_1",
                dry_run=False,
            )

        assert result["success"] is True
        assert result["data"]["deleted"] is True
        assert result["data"]["cascaded_logics"] == 1
        space = await fake_storage.load("space_dry_run_test")
        assert len(space.layers.L4_business_logic.rule_definitions) == 0
        assert len(space.layers.L4_business_logic.rule_logics) == 0

    @pytest.mark.asyncio
    async def test_delete_rule_nonexistent_dry_run(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import delete_rule_definition

            result = await delete_rule_definition(
                space_id="space_dry_run_test",
                rule_id="rule_nonexistent",
                dry_run=True,
            )

        assert result.status_code == 404


class TestRollbackDryRun:
    """Test POST /v1/spaces/{space_id}/versions/{version}/rollback?dry_run=true."""

    @pytest.mark.asyncio
    async def test_rollback_dry_run_shows_diff(self, fake_storage):
        v1_space = FakeSpace(space_id="space_dry_run_test", name="V1 Space")
        v1_space.instances = FakeInstances(entities=[{"entity_id": "E1"}])
        v1_space.active_version = 1
        fake_storage._versions[("space_dry_run_test", 1)] = v1_space

        current_space = fake_storage._spaces["space_dry_run_test"]
        current_space.instances = FakeInstances(entities=[{"entity_id": "E1"}, {"entity_id": "E2"}])
        current_space.active_version = 2

        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import rollback_to_version

            result = await rollback_to_version(
                space_id="space_dry_run_test",
                version=1,
                dry_run=True,
            )

        assert result["success"] is True
        assert result["data"]["dry_run"] is True
        assert result["data"]["current_version"] == 2
        assert result["data"]["target_version"] == 1
        assert result["data"]["current_entity_count"] == 2
        assert result["data"]["target_entity_count"] == 1

    @pytest.mark.asyncio
    async def test_rollback_dry_run_does_not_rollback(self, fake_storage):
        fake_storage._spaces["space_dry_run_test"].active_version = 2

        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import rollback_to_version

            await rollback_to_version(
                space_id="space_dry_run_test",
                version=1,
                dry_run=True,
            )

        space = await fake_storage.load("space_dry_run_test")
        assert space.active_version == 2, "Version should not change after dry_run"

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version_dry_run(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import rollback_to_version

            result = await rollback_to_version(
                space_id="space_dry_run_test",
                version=999,
                dry_run=True,
            )

        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_space_dry_run(self, fake_storage):
        with patch(
            "ontology_engine.api.routes.semantic_spaces._get_storage",
            return_value=fake_storage,
        ):
            from ontology_engine.api.routes.semantic_spaces import rollback_to_version

            result = await rollback_to_version(
                space_id="space_nonexistent",
                version=1,
                dry_run=True,
            )

        assert result.status_code == 404

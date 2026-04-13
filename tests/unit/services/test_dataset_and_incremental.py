# tests/unit/services/test_dataset_and_incremental.py
"""Tests for DatasetService and IncrementalUpdateService with DuckDB persistence."""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.storage.duckdb.store import DuckDBStorage
from ontology_engine.services.dataset_service import DatasetService
from ontology_engine.services.incremental_update import (
    IncrementalUpdateService,
    ChangeType,
)


class BaseServiceTest:
    """Base class with shared async storage fixture."""

    @pytest_asyncio.fixture
    async def storage(self) -> DuckDBStorage:
        """Create an in-memory DuckDB storage for testing."""
        s = DuckDBStorage(db_path=":memory:")
        await s.initialize()
        try:
            yield s
        finally:
            await s.close()


# =========================================================================
# DatasetService Tests
# =========================================================================

class TestDatasetService(BaseServiceTest):

    @pytest.mark.asyncio
    async def test_create_and_get_dataset(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        ds = await service.create_dataset(name="Test DS", description="desc")
        assert ds["name"] == "Test DS"
        assert "dataset_id" in ds

        fetched = await service.get_dataset(ds["dataset_id"])
        assert fetched is not None
        assert fetched["name"] == "Test DS"

    @pytest.mark.asyncio
    async def test_list_datasets(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        await service.create_dataset(name="DS 1")
        await service.create_dataset(name="DS 2")
        datasets = await service.list_datasets()
        assert len(datasets) == 2

    @pytest.mark.asyncio
    async def test_add_entities(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        ds = await service.create_dataset(name="With Entities")
        count = await service.add_entities(
            dataset_id=ds["dataset_id"],
            entities=[
                {"entity_id": "ent_1", "_concept": "Enterprise", "name": "Co A"},
                {"entity_id": "ent_2", "_concept": "Enterprise", "name": "Co B"},
            ],
            concept="Enterprise",
        )
        assert count == 2

        members = await service.get_dataset_entities(ds["dataset_id"])
        assert len(members) == 2

    @pytest.mark.asyncio
    async def test_intersection(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        ds_a = await service.create_dataset(name="A")
        ds_b = await service.create_dataset(name="B")

        await service.add_entities(ds_a["dataset_id"], [{"entity_id": "e1"}, {"entity_id": "e2"}])
        await service.add_entities(ds_b["dataset_id"], [{"entity_id": "e2"}, {"entity_id": "e3"}])

        result = await service.get_intersection(ds_a["dataset_id"], ds_b["dataset_id"])
        assert result["intersection_count"] == 1
        assert "e2" in result["intersection_entities"]

    @pytest.mark.asyncio
    async def test_diff(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        ds_a = await service.create_dataset(name="A")
        ds_b = await service.create_dataset(name="B")

        await service.add_entities(ds_a["dataset_id"], [{"entity_id": "e1"}, {"entity_id": "e2"}])
        await service.add_entities(ds_b["dataset_id"], [{"entity_id": "e2"}, {"entity_id": "e3"}])

        result = await service.get_diff(ds_a["dataset_id"], ds_b["dataset_id"])
        assert "e1" in result["only_in_a"]
        assert "e3" in result["only_in_b"]
        assert "e2" in result["common"]

    @pytest.mark.asyncio
    async def test_snapshot(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        ds = await service.create_dataset(name="Snap Test")
        await service.add_entities(
            ds["dataset_id"],
            [{"entity_id": "e1"}, {"entity_id": "e2"}, {"entity_id": "e3"}],
        )
        snap = await service.create_snapshot(ds["dataset_id"], description="baseline")
        assert snap["entity_count"] == 3
        assert snap["description"] == "baseline"

    @pytest.mark.asyncio
    async def test_delete_dataset(self, storage: DuckDBStorage):
        service = DatasetService(storage=storage)
        ds = await service.create_dataset(name="To Delete")
        await service.delete_dataset(ds["dataset_id"])
        assert await service.get_dataset(ds["dataset_id"]) is None


# =========================================================================
# IncrementalUpdateService Tests
# =========================================================================

class TestIncrementalUpdateService(BaseServiceTest):

    @pytest.mark.asyncio
    async def test_detect_changes(self, storage: DuckDBStorage):
        service = IncrementalUpdateService(storage=storage)
        old = {
            "e1": {"_concept": "Enterprise", "name": "Co A", "revenue": 100},
            "e2": {"_concept": "Enterprise", "name": "Co B", "revenue": 200},
        }
        new = {
            "e1": {"_concept": "Enterprise", "name": "Co A Updated", "revenue": 100},
            "e2": {"_concept": "Enterprise", "name": "Co B", "revenue": 200},
            "e3": {"_concept": "Enterprise", "name": "Co C", "revenue": 300},
        }
        changes = service.detect_changes(old, new)
        types = {c.change_type for c in changes}
        assert ChangeType.UPDATED in types
        assert ChangeType.CREATED in types
        assert ChangeType.UNCHANGED in types

    @pytest.mark.asyncio
    async def test_import_with_diff_dry_run(self, storage: DuckDBStorage):
        service = IncrementalUpdateService(storage=storage)
        new_entities = {
            "e1": {"_concept": "Enterprise", "name": "New Co"},
            "e2": {"_concept": "Enterprise", "name": "Another Co"},
        }
        result = await service.import_with_diff(
            new_entities=new_entities,
            dry_run=True,
        )
        assert result["dry_run"] is True
        assert result["stats"]["created"] == 2

    @pytest.mark.asyncio
    async def test_import_with_diff_persist(self, storage: DuckDBStorage):
        service = IncrementalUpdateService(storage=storage)
        new_entities = {
            "e1": {"_concept": "Enterprise", "name": "Co A"},
            "e2": {"_concept": "Enterprise", "name": "Co B"},
        }
        result = await service.import_with_diff(
            new_entities=new_entities,
            dry_run=False,
        )
        assert result["dry_run"] is False
        assert result["status"] == "applied"
        assert result["stats"]["created"] == 2

        # Verify batch is persisted
        batch = await service.get_change_batch(result["batch_id"])
        assert batch is not None
        assert batch["status"] == "applied"

    @pytest.mark.asyncio
    async def test_entity_version_persisted(self, storage: DuckDBStorage):
        service = IncrementalUpdateService(storage=storage)
        new_entities = {
            "e_ver": {"_concept": "Enterprise", "name": "Versioned Co", "revenue": 500},
        }
        result = await service.import_with_diff(new_entities=new_entities)
        versions = await storage.list_entity_versions("e_ver")
        assert len(versions) == 1
        assert versions[0]["data"]["name"] == "Versioned Co"

    @pytest.mark.asyncio
    async def test_rollback_actions(self, storage: DuckDBStorage):
        service = IncrementalUpdateService(storage=storage)
        new_entities = {
            "e_new": {"_concept": "Enterprise", "name": "New Co"},
        }
        old_entities = {
            "e_del": {"_concept": "Enterprise", "name": "Deleted Co"},
        }

        # Import new
        result = await service.import_with_diff(new_entities=new_entities, old_entities=old_entities)
        actions = await service.get_rollback_actions(result["batch_id"])
        action_types = {a["action"] for a in actions}
        assert "delete" in action_types  # e_new was created
        assert "restore" in action_types  # e_del was deleted

    @pytest.mark.asyncio
    async def test_impact_analysis(self, storage: DuckDBStorage):
        service = IncrementalUpdateService(storage=storage)
        from ontology_engine.services.incremental_update import EntityChange
        changes = [
            EntityChange(entity_id="e1", concept="Enterprise", change_type=ChangeType.UPDATED),
        ]
        impact = await service.compute_impact(
            changes=changes,
            metric_dependencies={"e1": ["credit_score", "debt_ratio"]},
            rule_dependencies={"e1": ["rule_1"]},
        )
        assert impact["entity_count"] == 1
        assert "credit_score" in impact["affected_metrics"]
        assert "rule_1" in impact["affected_rules"]

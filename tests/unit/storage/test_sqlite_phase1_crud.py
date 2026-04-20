# tests/unit/storage/test_sqlite_phase1_crud.py
"""Tests for Phase 1 SQLite CRUD methods (datasets, memberships, snapshots,
dimension_applicability, category_rule_mapping, change_batches, entity_changes,
entity_versions).
"""

from __future__ import annotations

import pytest
import pytest_asyncio

from ontology_engine.storage.sqlite.store import SQLiteStorage


class BaseStorageTest:
    """Base class with shared async storage fixture."""

    @pytest_asyncio.fixture
    async def storage(self) -> SQLiteStorage:
        """Create an in-memory SQLite storage for testing."""
        s = SQLiteStorage(db_path=":memory:")
        await s.initialize()
        try:
            yield s
        finally:
            await s.close()


# =========================================================================
# Dataset CRUD
# =========================================================================

class TestDatasetCRUD(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_create_and_get_dataset(self, storage: SQLiteStorage):
        await storage.create_dataset(
            dataset_id="ds_test1",
            name="Test Dataset",
            description="A test dataset",
            scope={"concept": "Enterprise"},
        )
        ds = await storage.get_dataset("ds_test1")
        assert ds is not None
        assert ds["name"] == "Test Dataset"
        assert ds["description"] == "A test dataset"
        assert ds["scope"]["concept"] == "Enterprise"
        assert ds["source_type"] == "manual"

    @pytest.mark.asyncio
    async def test_list_datasets(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_1", "Dataset 1")
        await storage.create_dataset("ds_2", "Dataset 2")
        datasets = await storage.list_datasets()
        assert len(datasets) == 2

    @pytest.mark.asyncio
    async def test_update_dataset(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_up", "Original Name")
        await storage.update_dataset("ds_up", name="Updated Name")
        ds = await storage.get_dataset("ds_up")
        assert ds["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_dataset(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_del", "To Delete")
        await storage.add_entity_to_dataset("ent_1", "ds_del", "Enterprise")
        ok = await storage.delete_dataset("ds_del")
        assert ok
        assert await storage.get_dataset("ds_del") is None
        members = await storage.get_dataset_entities("ds_del")
        assert len(members) == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_dataset(self, storage: SQLiteStorage):
        ds = await storage.get_dataset("ds_nonexistent")
        assert ds is None


# =========================================================================
# Entity Dataset Membership
# =========================================================================

class TestEntityDatasetMembership(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_add_and_get_entities(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_m1", "Membership Test")
        await storage.add_entity_to_dataset("ent_1", "ds_m1", "Enterprise", is_primary=True)
        await storage.add_entity_to_dataset("ent_2", "ds_m1", "Enterprise")

        members = await storage.get_dataset_entities("ds_m1")
        assert len(members) == 2
        assert members[0]["entity_id"] == "ent_1"
        assert members[0]["is_primary"] is True

    @pytest.mark.asyncio
    async def test_filter_by_concept(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_m2", "Concept Filter")
        await storage.add_entity_to_dataset("ent_a", "ds_m2", "Enterprise")
        await storage.add_entity_to_dataset("ent_b", "ds_m2", "Person")

        enterprise = await storage.get_dataset_entities("ds_m2", fact_object="Enterprise")
        assert len(enterprise) == 1
        assert enterprise[0]["entity_id"] == "ent_a"

    @pytest.mark.asyncio
    async def test_remove_entity(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_m3", "Remove Test")
        await storage.add_entity_to_dataset("ent_1", "ds_m3", "Enterprise")
        await storage.remove_entity_from_dataset("ent_1", "ds_m3")
        members = await storage.get_dataset_entities("ds_m3")
        assert len(members) == 0


# =========================================================================
# Dataset Snapshots
# =========================================================================

class TestDatasetSnapshots(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_create_and_get_snapshots(self, storage: SQLiteStorage):
        await storage.create_dataset("ds_snap", "Snapshot Test")
        await storage.create_snapshot("snap_1", "ds_snap", entity_count=10, description="v1")
        await storage.create_snapshot("snap_2", "ds_snap", entity_count=15, description="v2")

        snapshots = await storage.get_snapshots("ds_snap")
        assert len(snapshots) == 2
        assert snapshots[0]["snapshot_id"] == "snap_1"
        assert snapshots[0]["entity_count"] == 10


# =========================================================================
# Dimension Applicability
# =========================================================================

class TestDimensionApplicability(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_save_and_get(self, storage: SQLiteStorage):
        await storage.save_dimension_applicability(
            dimension_id="industry",
            object_type="Enterprise",
            required=True,
            auto_categorize=True,
            source_attribute="industry_code",
        )
        entries = await storage.get_dimension_applicability("industry")
        assert len(entries) == 1
        assert entries[0]["required"] is True
        assert entries[0]["source_attribute"] == "industry_code"

    @pytest.mark.asyncio
    async def test_filter_by_object_type(self, storage: SQLiteStorage):
        await storage.save_dimension_applicability("dim1", "Enterprise")
        await storage.save_dimension_applicability("dim1", "Person")

        entries = await storage.get_dimension_applicability("dim1", "Enterprise")
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_delete(self, storage: SQLiteStorage):
        await storage.save_dimension_applicability("dim2", "Enterprise")
        await storage.delete_dimension_applicability("dim2", "Enterprise")
        entries = await storage.get_dimension_applicability("dim2")
        assert len(entries) == 0


# =========================================================================
# Category Rule Mapping
# =========================================================================

class TestCategoryRuleMapping(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_save_and_get(self, storage: SQLiteStorage):
        await storage.save_category_rule_mapping(
            dimension_id="industry",
            dimension_value="manufacturing",
            rule_group_id="rg_1",
            mapping_type="applicable",
        )
        mappings = await storage.get_category_rule_mappings()
        assert len(mappings) == 1
        assert mappings[0]["rule_group_id"] == "rg_1"

    @pytest.mark.asyncio
    async def test_filter_by_dimension(self, storage: SQLiteStorage):
        await storage.save_category_rule_mapping("dim_a", "val_1", "rg_1")
        await storage.save_category_rule_mapping("dim_b", "val_2", "rg_2")

        mappings = await storage.get_category_rule_mappings(dimension_id="dim_a")
        assert len(mappings) == 1

    @pytest.mark.asyncio
    async def test_delete(self, storage: SQLiteStorage):
        await storage.save_category_rule_mapping("dim_x", "val_y", "rg_z")
        await storage.delete_category_rule_mapping("dim_x", "val_y", "rg_z")
        mappings = await storage.get_category_rule_mappings()
        assert len(mappings) == 0


# =========================================================================
# Change Batches
# =========================================================================

class TestChangeBatches(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_create_and_get(self, storage: SQLiteStorage):
        await storage.create_change_batch("batch_1", dataset_id="ds_1", entity_count=5)
        batch = await storage.get_change_batch("batch_1")
        assert batch is not None
        assert batch["dataset_id"] == "ds_1"
        assert batch["status"] == "pending"

    @pytest.mark.asyncio
    async def test_update_batch(self, storage: SQLiteStorage):
        await storage.create_change_batch("batch_2")
        await storage.update_change_batch(
            "batch_2", status="applied", created_count=3, updated_count=2,
        )
        batch = await storage.get_change_batch("batch_2")
        assert batch["status"] == "applied"
        assert batch["created_count"] == 3

    @pytest.mark.asyncio
    async def test_list_batches(self, storage: SQLiteStorage):
        await storage.create_change_batch("batch_a", dataset_id="ds_x")
        await storage.create_change_batch("batch_b", dataset_id="ds_y")

        all_batches = await storage.list_change_batches()
        assert len(all_batches) == 2

        ds_x_batches = await storage.list_change_batches(dataset_id="ds_x")
        assert len(ds_x_batches) == 1


# =========================================================================
# Entity Changes
# =========================================================================

class TestEntityChanges(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_save_and_get(self, storage: SQLiteStorage):
        await storage.create_change_batch("batch_ec1")
        await storage.save_entity_changes(
            batch_id="batch_ec1",
            entity_id="ent_1",
            fact_object="Enterprise",
            change_type="UPDATED",
            field_changes=[{"field_name": "name", "old_value": "Old", "new_value": "New"}],
        )
        changes = await storage.get_entity_changes("batch_ec1")
        assert len(changes) == 1
        assert changes[0]["change_type"] == "UPDATED"
        assert len(changes[0]["field_changes"]) == 1


# =========================================================================
# Entity Versions
# =========================================================================

class TestEntityVersions(BaseStorageTest):

    @pytest.mark.asyncio
    async def test_save_and_get(self, storage: SQLiteStorage):
        await storage.save_entity_version("ent_v1", "Enterprise", 1, {"name": "v1"})
        await storage.save_entity_version("ent_v1", "Enterprise", 2, {"name": "v2"})

        v = await storage.get_entity_version("ent_v1")
        assert v is not None
        assert v["version"] == 2

        v1 = await storage.get_entity_version("ent_v1", version=1)
        assert v1["data"]["name"] == "v1"

    @pytest.mark.asyncio
    async def test_list_versions(self, storage: SQLiteStorage):
        await storage.save_entity_version("ent_v2", "Person", 1, {"name": "v1"})
        await storage.save_entity_version("ent_v2", "Person", 2, {"name": "v2"})
        versions = await storage.list_entity_versions("ent_v2")
        assert len(versions) == 2
        assert versions[0]["version"] == 1

    @pytest.mark.asyncio
    async def test_delete_version(self, storage: SQLiteStorage):
        await storage.save_entity_version("ent_v3", "Enterprise", 1, {"name": "v1"})
        await storage.delete_entity_version("ent_v3", 1)
        v = await storage.get_entity_version("ent_v3", 1)
        assert v is None

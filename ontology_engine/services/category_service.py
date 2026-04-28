# ontology_engine/services/category_service.py
"""Category management service — mediates between API and storage."""

from __future__ import annotations

from typing import Any

from ontology_engine.storage.base import StorageBackend


class CategoryService:
    """Thin service wrapper for category / dimension / version operations."""

    def __init__(self, storage: StorageBackend) -> None:
        self._storage = storage

    async def save_dimension_applicability(self, **kwargs: Any) -> None:
        await self._storage.save_dimension_applicability(**kwargs)

    async def get_dimension_applicability(
        self, dimension_id: str, object_type: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._storage.get_dimension_applicability(dimension_id, object_type)

    async def delete_dimension_applicability(
        self, dimension_id: str, object_type: str
    ) -> None:
        await self._storage.delete_dimension_applicability(dimension_id, object_type)

    async def save_category_rule_mapping(self, **kwargs: Any) -> None:
        await self._storage.save_category_rule_mapping(**kwargs)

    async def get_category_rule_mappings(
        self,
        dimension_id: str | None = None,
        dimension_value: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._storage.get_category_rule_mappings(dimension_id, dimension_value)

    async def delete_category_rule_mapping(
        self, dimension_id: str, dimension_value: str, rule_group_id: str
    ) -> None:
        await self._storage.delete_category_rule_mapping(dimension_id, dimension_value, rule_group_id)

    async def list_entity_versions(self, entity_id: str) -> list[dict[str, Any]]:
        return await self._storage.list_entity_versions(entity_id)

    async def get_entity_version(
        self, entity_id: str, version: int
    ) -> dict[str, Any] | None:
        return await self._storage.get_entity_version(entity_id, version)

"""SpaceService — semantic space lifecycle management.

Encapsulates all space-level operations so that MCP tools and API routes
do not need to directly depend on core/ or storage/ layers.
"""

import uuid
from typing import Any

from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SemanticSpaceLayers,
    SpaceInstances,
    L4BusinessLogic,
    SpaceMetadata,
    SpaceStatus,
)
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage


class SpaceService:
    """Service for semantic space CRUD, activation, and version management."""

    def __init__(self, storage: SemanticSpaceStorage | None = None) -> None:
        self._storage = storage or SemanticSpaceStorage()

    async def create_space(
        self,
        name: str,
        description: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Create a new semantic space in DRAFT status.

        Returns:
            Dict with space_id, name, description, domain, status.
        """
        space_id = f"space_{uuid.uuid4().hex[:8]}"
        metadata = SpaceMetadata(
            id=space_id,
            name=name,
            description=description,
            domain=domain,
            status=SpaceStatus.DRAFT,
        )
        space = SemanticSpace(
            metadata=metadata,
            layers=SemanticSpaceLayers(L4_business_logic=L4BusinessLogic()),
            instances=SpaceInstances(),
        )
        await self._storage.save(space)
        return {
            "space_id": space_id,
            "name": name,
            "description": description,
            "domain": domain,
            "status": SpaceStatus.DRAFT.value,
        }

    async def get_space(self, space_id: str) -> SemanticSpace | None:
        """Load a semantic space by ID."""
        return await self._storage.load(space_id)

    async def list_spaces(self) -> list[dict[str, Any]]:
        """List all spaces with summary information."""
        all_metadata = await self._storage.list()
        result = []
        for meta in all_metadata:
            space = await self._storage.load(meta.id)
            entity_count = len(space.instances.entities) if space else 0
            result.append({
                "space_id": meta.id,
                "name": meta.name,
                "status": meta.status.value if hasattr(meta.status, "value") else str(meta.status),
                "domain": meta.domain,
                "entity_count": entity_count,
            })
        return result

    async def get_schema_overview(self, space_id: str) -> dict[str, Any] | None:
        """Get schema layer overview for a space.

        Returns:
            Dict with space_id, name, active_version, layers summary, or None if not found.
        """
        space = await self._storage.load(space_id)
        if not space:
            return None

        return {
            "space_id": space.metadata.id,
            "name": space.metadata.name,
            "active_version": space.active_version,
            "layers": {
                "L1": {
                    "fact_objects": len(space.layers.L1_fact_objects) if space.layers.L1_fact_objects else 0,
                },
                "L2": {
                    "categorizations": len(space.layers.L2_categorizations) if space.layers.L2_categorizations else 0,
                },
                "L3": {
                    "analytical_elements": len(space.layers.L3_analytical_elements) if space.layers.L3_analytical_elements else 0,
                },
                "L4": {
                    "rule_definitions": len(space.layers.L4_business_logic.rule_definitions),
                    "rule_logics": len(space.layers.L4_business_logic.rule_logics),
                },
            },
        }

    async def add_entity(
        self,
        space_id: str,
        entity_id: str,
        fact_object: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Add an entity instance to a space.

        Returns:
            Dict with entity_id, fact_object, space_id, or None if space not found.
        """
        space = await self._storage.load(space_id)
        if not space:
            return None

        existing = next(
            (e for e in space.instances.entities if e.get("entity_id") == entity_id),
            None,
        )
        if existing:
            return None

        entity = attributes.copy() if attributes else {}
        entity["entity_id"] = entity_id
        entity["_fact_object"] = fact_object
        space.instances.entities.append(entity)
        await self._storage.save(space)

        return {
            "entity_id": entity_id,
            "fact_object": fact_object,
            "space_id": space_id,
        }

    async def define_rule(
        self,
        space_id: str,
        rule_id: str,
        name: str,
        dimension: str = "credit_assessment",
        applies_to: list[str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        """Add a rule definition to a space's L4 layer.

        Returns:
            Dict with rule details, or None if space not found / duplicate.
        """
        space = await self._storage.load(space_id)
        if not space:
            return None

        existing_ids = [rd.get("id") for rd in space.layers.L4_business_logic.rule_definitions]
        if rule_id in existing_ids:
            return None

        rule_def = {
            "id": rule_id,
            "name": name,
            "dimension": dimension,
            "applies_to": applies_to or [],
            "description": description or "",
        }
        space.layers.L4_business_logic.rule_definitions.append(rule_def)
        await self._storage.save(space)

        return {
            "rule_id": rule_id,
            "name": name,
            "dimension": dimension,
            "applies_to": applies_to or [],
            "space_id": space_id,
        }

    async def activate_space(self, space_id: str) -> dict[str, Any] | None:
        """Transition a space from DRAFT to ACTIVE.

        Returns:
            Dict with space_id, status, active_version, or None if space not found.
            Dict with 'already_active' key if space was already active.
            Dict with 'no_rules' key if space has no rule definitions.
        """
        space = await self._storage.load(space_id)
        if not space:
            return None

        if space.metadata.status == SpaceStatus.ACTIVE:
            return {
                "space_id": space_id,
                "status": "ACTIVE",
                "active_version": space.active_version,
                "already_active": True,
            }

        has_l4 = len(space.layers.L4_business_logic.rule_definitions) > 0
        if not has_l4:
            return {"space_id": space_id, "no_rules": True}

        space.metadata.status = SpaceStatus.ACTIVE
        space.active_version = space.active_version + 1 if space.active_version else 1
        await self._storage.save(space)

        return {
            "space_id": space_id,
            "status": "ACTIVE",
            "active_version": space.active_version,
        }

    async def create_snapshot(
        self,
        space_id: str,
        description: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any] | None:
        """Create a versioned snapshot of a space.

        Returns:
            Dict with version info, or None if space not found.
        """
        space = await self._storage.load(space_id)
        if not space:
            return None

        version = await self._storage.create_snapshot(
            space, description=description, created_by=created_by
        )

        return {
            "space_id": space_id,
            "version": version.version,
            "description": version.change_description,
            "is_stable": version.is_stable,
        }

    async def rollback_space(
        self,
        space_id: str,
        target_version: int,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any] | None:
        """Rollback a space to a previous version.

        Returns:
            Dict with rollback info, or None if space/version not found.
        """
        space = await self._storage.load(space_id)
        if not space:
            return None

        if dry_run:
            target = await self._storage.load_version(space_id, target_version, space=space)
            if not target:
                return None
            return {
                "dry_run": True,
                "current_version": space.active_version,
                "target_version": target_version,
                "current_entity_count": len(space.instances.entities),
                "target_entity_count": len(target.instances.entities),
                "current_rule_def_count": len(space.layers.L4_business_logic.rule_definitions),
                "target_rule_def_count": len(target.layers.L4_business_logic.rule_definitions),
            }

        restored = await self._storage.rollback_to_version(space_id, target_version, space=space)
        if not restored:
            return None

        return {
            "space_id": space_id,
            "active_version": restored.active_version,
            "status": restored.metadata.status.value,
        }

    async def delete_space(self, space_id: str) -> bool:
        return await self._storage.delete(space_id)

    async def save_space(self, space: SemanticSpace) -> None:
        await self._storage.save(space)

    async def list_metadata(self) -> list[Any]:
        return await self._storage.list()

    async def load_version(
        self, space_id: str, version: int, space: SemanticSpace
    ) -> SemanticSpace | None:
        return await self._storage.load_version(space_id, version, space=space)

    async def rollback_to_version(
        self, space_id: str, version: int, space: SemanticSpace
    ) -> SemanticSpace | None:
        return await self._storage.rollback_to_version(
            space_id, version, space=space
        )

    async def create_snapshot_with_space(
        self,
        space: SemanticSpace,
        description: str | None = None,
    ) -> Any:
        return await self._storage.create_snapshot(space, description=description)

    def load_space_from_file(self, path: str) -> SemanticSpace:
        from ontology_engine.core.semantic_space import SpaceLoader
        loader = SpaceLoader()
        return loader.load(path)

    def load_schema_from_file(self, path: str) -> Any:
        from ontology_engine.core.schema import SchemaLoader
        loader = SchemaLoader()
        return loader.load(path)

    def load_instances_from_file(
        self, path: str
    ) -> tuple[list[Any], list[Any]]:
        from ontology_engine.core.instances import InstanceLoader
        loader = InstanceLoader()
        return loader.load(path)

    async def list_entity_versions(
        self, entity_key: str
    ) -> list[dict[str, Any]]:
        return await self._storage._meta_store.list_entity_versions(
            entity_key
        )

    async def get_entity_version(
        self, entity_key: str, version: int
    ) -> dict[str, Any] | None:
        return await self._storage._meta_store.get_entity_version(
            entity_key, version
        )

    async def save_entity_version(
        self,
        entity_key: str,
        entity_type: str,
        version: int,
        data: dict[str, Any],
        updated_by: str = "api",
    ) -> None:
        await self._storage._meta_store.save_entity_version(
            entity_key, entity_type, version, data, updated_by=updated_by
        )

# ontology_engine/services/schema_service.py
"""Schema management service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ontology_engine.core.schema import SchemaLoader
from ontology_engine.services.dto import (
    SchemaInfo,
    SchemaValidationError,
)
from ontology_engine.storage.base import StorageBackend

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema


class SchemaService:
    """Schema management service.

    Handles schema loading, validation, versioning, and hot-reload.
    """

    def __init__(
        self,
        storage: DuckDBStorage,
    ):
        """Initialize SchemaService.

        Args:
            storage: DuckDBStorage instance
        """
        self.storage = storage
        self._loader = SchemaLoader()
        self._current_schema: KGMLSchema | None = None
        self._schema_versions: list[dict] = []
        self._version_counter = 0

    async def load_schema(self, schema_path: str) -> SchemaInfo:
        """Load schema from path.

        Args:
            schema_path: Path to schema YAML file

        Returns:
            SchemaInfo with loaded schema details

        Raises:
            SchemaValidationError: If schema validation fails
        """
        # 1. Parse schema
        schema = self._loader.load(schema_path)

        # 2. Validate
        issues = self._loader.validate(schema)
        errors = [i for i in issues if getattr(i, 'level', None) == 'error']
        if errors:
            raise SchemaValidationError([str(e) for e in errors])

        # 3. Commit version
        self._version_counter += 1
        version_info = {
            "version": f"v{self._version_counter}",
            "schema_id": schema.metadata.id if hasattr(schema, 'metadata') else 'unknown',
            "description": f"Loaded from {schema_path}"
        }
        self._schema_versions.append(version_info)

        # 4. Activate
        self._current_schema = schema

        # Get counts
        entity_count = len(getattr(schema, 'concepts', []))
        metric_count = len(getattr(schema, 'metrics', []))
        rules_def = getattr(schema, 'rules', None)
        rule_count = len(rules_def.ruleset) if rules_def else 0

        warnings = [str(i) for i in issues if getattr(i, 'level', None) == 'warning']

        return SchemaInfo(
            schema_id=schema.metadata.id if hasattr(schema, 'metadata') else 'unknown',
            version=version_info["version"],
            entity_count=entity_count,
            metric_count=metric_count,
            rule_count=rule_count,
            warnings=warnings
        )

    async def get_schema(self) -> KGMLSchema | None:
        """Get current active schema.

        Returns:
            Current KGMLSchema or None if not loaded
        """
        return self._current_schema

    async def reload_schema(self, schema_path: str) -> SchemaInfo:
        """Hot-reload schema from path.

        Args:
            schema_path: Path to schema YAML file

        Returns:
            SchemaInfo with reloaded schema details
        """
        return await self.load_schema(schema_path)

    async def get_schema_versions(self) -> list[dict]:
        """Get schema version history.

        Returns:
            List of version info dicts
        """
        return self._schema_versions

    async def rollback_schema(self, target_version: int) -> SchemaInfo:
        """Rollback to a specific schema version.

        Note: This is a simplified implementation. Full versioning
        would require storing schema snapshots.

        Args:
            target_version: Version number to rollback to

        Returns:
            SchemaInfo (Note: full rollback not implemented in Phase 1)
        """
        if target_version < 1 or target_version > len(self._schema_versions):
            raise ValueError(f"Invalid version: {target_version}")

        # In Phase 1, we just return info about the target version
        target_info = self._schema_versions[target_version - 1]

        return SchemaInfo(
            schema_id=target_info["schema_id"],
            version=target_info["version"],
            warnings=["Rollback is informational in Phase 1"]
        )

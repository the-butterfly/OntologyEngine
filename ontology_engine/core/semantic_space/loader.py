# ontology_engine/core/semantic_space/loader.py
"""Loader for semantic spaces from JSON and YAML files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
)


class SpaceLoaderError(Exception):
    """Space loader error."""
    pass


class SpaceLoader:
    """Loader for semantic spaces from JSON/YAML files.

    Supports loading full semantic space configurations including:
    - L1-L4 schema layers
    - Instance data (entities, relations)
    - Metadata and versions
    """

    def load(self, path: str | Path) -> SemanticSpace:
        """Load a semantic space from a JSON or YAML file.

        Args:
            path: Path to the space file (.json, .yaml, .yml)

        Returns:
            SemanticSpace object

        Raises:
            FileNotFoundError: If file doesn't exist
            SpaceLoaderError: If file format is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Space file not found: {path}")

        suffix = path.suffix.lower()

        if suffix == ".json":
            return self._load_json(path)
        elif suffix in (".yaml", ".yml"):
            return self._load_yaml(path)
        else:
            raise SpaceLoaderError(f"Unsupported file format: {suffix}. Use .json or .yaml")

    def _load_json(self, path: Path) -> SemanticSpace:
        """Load semantic space from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._parse(data)
        except json.JSONDecodeError as e:
            raise SpaceLoaderError(f"Invalid JSON in {path}: {e}") from e

    def _load_yaml(self, path: Path) -> SemanticSpace:
        """Load semantic space from YAML file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return self._parse(data)
        except yaml.YAMLError as e:
            raise SpaceLoaderError(f"Invalid YAML in {path}: {e}") from e

    def _parse(self, data: dict[str, Any]) -> SemanticSpace:
        """Parse raw dict into SemanticSpace.

        Handles both direct SemanticSpace format and nested format
        where layers/instances may be under different keys.
        """
        if not data:
            raise SpaceLoaderError("Space data is empty")

        # Check if this is a SemanticSpace-compatible format
        # demo_space.json uses "metadata", "layers", "instances", "versions"
        if "metadata" in data:
            return self._parse_full_format(data)
        else:
            raise SpaceLoaderError(
                "Unrecognized space format. Expected 'metadata' key. "
                f"Available keys: {list(data.keys())}"
            )

    def _parse_full_format(self, data: dict[str, Any]) -> SemanticSpace:
        """Parse full semantic space format."""
        try:
            # Parse metadata
            metadata_data = data.get("metadata", {})
            metadata = SpaceMetadata(
                id=metadata_data.get("id", ""),
                name=metadata_data.get("name", ""),
                space_type=metadata_data.get("space_type", "management"),
                description=metadata_data.get("description"),
                domain=metadata_data.get("domain"),
                status=metadata_data.get("status", "draft"),
                created_at=metadata_data.get("created_at"),
                updated_at=metadata_data.get("updated_at"),
                created_by=metadata_data.get("created_by"),
                view_id=metadata_data.get("view_id"),
            )

            # Parse layers
            layers_data = data.get("layers", {})
            layers = self._parse_layers(layers_data)

            # Parse instances
            instances_data = data.get("instances", {})
            instances = SpaceInstances(
                entities=instances_data.get("entities", []),
                relations=instances_data.get("relations", []),
                category_tags=instances_data.get("category_tags", []),
                metric_values=instances_data.get("metric_values", []),
            )

            # Parse versions
            versions_data = data.get("versions", [])
            from ontology_engine.core.semantic_space import SpaceVersion
            versions = [
                SpaceVersion(
                    version=v.get("version", 1),
                    space_id=v.get("space_id", metadata.id),
                    snapshot_path=v.get("snapshot_path"),
                    created_at=v.get("created_at"),
                    created_by=v.get("created_by"),
                    change_description=v.get("change_description"),
                    is_stable=v.get("is_stable", False),
                )
                for v in versions_data
            ]

            return SemanticSpace(
                metadata=metadata,
                layers=layers,
                instances=instances,
                versions=versions,
                active_version=data.get("active_version", 1),
            )

        except Exception as e:
            raise SpaceLoaderError(f"Failed to parse space data: {e}") from e

    def _parse_layers(self, layers_data: dict[str, Any]) -> SemanticSpaceLayers:
        """Parse L1-L4 layers from dict."""
        # L4 Business Logic
        l4_data = layers_data.get("L4_business_logic", {})
        if isinstance(l4_data, dict):
            l4_business_logic = L4BusinessLogic(
                rule_definitions=l4_data.get("rule_definitions", []),
                rule_logics=l4_data.get("rule_logics", []),
            )
        else:
            l4_business_logic = L4BusinessLogic(
                rule_definitions=[],
                rule_logics=[],
            )

        return SemanticSpaceLayers(
            L1_fact_objects=layers_data.get("L1_fact_objects", []),
            L2_categorizations=layers_data.get("L2_categorizations", []),
            L3_analytical_elements=layers_data.get("L3_analytical_elements", []),
            L4_business_logic=l4_business_logic,
        )

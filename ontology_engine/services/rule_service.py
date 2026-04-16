# ontology_engine/services/rule_service.py
"""Rule orchestration service - CRUD and YAML import/export."""
from __future__ import annotations

import uuid
from typing import Any

import yaml

from ontology_engine.engine.rule.models import (
    AppliesToConfig,
    RuleGroupDefinition,
    RuleStep,
)
from ontology_engine.storage.base import StorageBackend


class RuleServiceError(Exception):
    """Rule service error."""
    pass


class RuleService:
    """Service for managing rule groups and rule steps.

    Provides CRUD operations and YAML import/export functionality.
    """

    def __init__(self, storage: StorageBackend):
        """Initialize RuleService.

        Args:
            storage: StorageBackend instance for persistence
        """
        self._storage = storage

    # =========================================================================
    # Rule Group CRUD
    # =========================================================================

    async def create_rule_group(
        self,
        data: dict[str, Any],
        schema_id: str | None = None,
    ) -> RuleGroupDefinition:
        """Create a new rule group.

        Args:
            data: Rule group data
            schema_id: Semantic space ID (required for semantic space isolation).
                      The combination (name, schema_id) must be unique.

        Returns:
            Created RuleGroupDefinition

        Raises:
            RuleServiceError: If rule group already exists or schema_id is missing
        """
        name = data.get("name")
        if not name:
            raise RuleServiceError("Rule group name is required")

        # schema_id is required for semantic space isolation
        if not schema_id:
            schema_id = data.get("schema_id")
        if not schema_id:
            raise RuleServiceError("schema_id is required for semantic space isolation")

        # Generate UUID if not provided
        if not data.get("id"):
            data["id"] = str(uuid.uuid4())

        # Check for existing rule group in the same semantic space
        existing = await self._storage.get_rule_group(name, schema_id=schema_id)
        if existing:
            raise RuleServiceError(
                f"Rule group '{name}' already exists in semantic space '{schema_id}'"
            )

        # Ensure schema_id is in the data
        data["schema_id"] = schema_id

        # Save to storage
        await self._storage.save_rule_group(data, schema_id=schema_id)

        return RuleGroupDefinition.from_dict(data)

    async def get_rule_group(
        self,
        identifier: str,
        schema_id: str | None = None,
    ) -> RuleGroupDefinition | None:
        """Get a rule group by id or (name, schema_id).

        Args:
            identifier: Rule group UUID (id) or name
            schema_id: Semantic space ID for name-based lookup.
                      Required when identifier is a name.

        Returns:
            RuleGroupDefinition or None if not found
        """
        data = await self._storage.get_rule_group(identifier, schema_id=schema_id)
        if data is None:
            return None
        return RuleGroupDefinition.from_dict(data)

    async def list_rule_groups(
        self,
        schema_id: str,
        enabled: bool | None = None,
    ) -> list[RuleGroupDefinition]:
        """List rule groups in a semantic space.

        Args:
            schema_id: Semantic space ID (required for isolation)
            enabled: Optional filter by enabled status

        Returns:
            List of RuleGroupDefinition in the specified semantic space
        """
        rows = await self._storage.list_rule_groups(schema_id=schema_id, enabled=enabled)
        return [RuleGroupDefinition.from_dict(r) for r in rows]

    async def update_rule_group(
        self,
        identifier: str,
        data: dict[str, Any],
        schema_id: str | None = None,
    ) -> RuleGroupDefinition | None:
        """Update a rule group.

        Args:
            identifier: Rule group UUID (id) or name
            data: Updated rule group data
            schema_id: Semantic space ID for name-based lookup

        Returns:
            Updated RuleGroupDefinition or None if not found
        """
        existing = await self._storage.get_rule_group(identifier, schema_id=schema_id)
        if existing is None:
            return None

        # Merge with existing data - preserve existing name and schema_id
        merged = dict(existing)
        merged.update(data)
        # Ensure name is preserved from existing data
        merged["name"] = existing["name"]
        # Ensure schema_id is preserved
        merged["schema_id"] = existing.get("schema_id")
        # If id was provided in data, keep the existing id
        if "id" not in data and existing.get("id"):
            merged["id"] = existing["id"]

        await self._storage.save_rule_group(merged, schema_id=merged["schema_id"])
        return RuleGroupDefinition.from_dict(merged)

    async def delete_rule_group(
        self,
        identifier: str,
        schema_id: str | None = None,
    ) -> bool:
        """Delete a rule group and its steps.

        Args:
            identifier: Rule group UUID (id) or name
            schema_id: Semantic space ID for name-based lookup

        Returns:
            True if deleted, False if not found
        """
        existing = await self._storage.get_rule_group(identifier, schema_id=schema_id)
        if existing is None:
            return False

        await self._storage.delete_rule_group(identifier, schema_id=schema_id)
        return True

    # =========================================================================
    # Rule Step CRUD
    # =========================================================================

    async def create_rule_step(
        self,
        rule_group: str,
        data: dict[str, Any],
        schema_id: str | None = None,
    ) -> RuleStep:
        """Create a new rule step.

        Args:
            rule_group: Parent rule group name
            data: Rule step data
            schema_id: Semantic space ID for rule group lookup

        Returns:
            Created RuleStep

        Raises:
            RuleServiceError: If rule step already exists or rule group not found
        """
        step_id = data.get("id")
        if not step_id:
            raise RuleServiceError("Rule step ID is required")

        # Verify rule group exists
        rg = await self._storage.get_rule_group(rule_group, schema_id=schema_id)
        if rg is None:
            raise RuleServiceError(f"Rule group '{rule_group}' not found in semantic space")

        # Use the rule group's actual name (in case of case mismatch)
        actual_rule_group = rg["name"]

        # Save to storage
        await self._storage.save_rule_step(actual_rule_group, data)

        return RuleStep.from_dict({**data, "rule_group": actual_rule_group})

    async def get_rule_step(
        self,
        rule_group: str,
        step_id: str,
        schema_id: str | None = None,
    ) -> RuleStep | None:
        """Get a rule step by ID.

        Args:
            rule_group: Parent rule group name
            step_id: Rule step ID
            schema_id: Semantic space ID for rule group lookup

        Returns:
            RuleStep or None if not found
        """
        # First resolve the rule group to get its actual name
        rg = await self._storage.get_rule_group(rule_group, schema_id=schema_id)
        if rg is None:
            return None

        data = await self._storage.get_rule_step(rg["name"], step_id)
        if data is None:
            return None
        return RuleStep.from_dict(data)

    async def list_rule_steps(
        self,
        rule_group: str,
        schema_id: str | None = None,
    ) -> list[RuleStep]:
        """List all rule steps for a rule group.

        Args:
            rule_group: Rule group name
            schema_id: Semantic space ID for rule group lookup

        Returns:
            List of RuleStep ordered by step_order
        """
        # First resolve the rule group to get its actual name
        rg = await self._storage.get_rule_group(rule_group, schema_id=schema_id)
        if rg is None:
            return []

        rows = await self._storage.list_rule_steps(rg["name"])
        return [RuleStep.from_dict(r) for r in rows]

    async def update_rule_step(
        self,
        rule_group: str,
        step_id: str,
        data: dict[str, Any],
        schema_id: str | None = None,
    ) -> RuleStep | None:
        """Update a rule step.

        Args:
            rule_group: Parent rule group name
            step_id: Rule step ID
            data: Updated rule step data
            schema_id: Semantic space ID for rule group lookup

        Returns:
            Updated RuleStep or None if not found
        """
        # First resolve the rule group to get its actual name
        rg = await self._storage.get_rule_group(rule_group, schema_id=schema_id)
        if rg is None:
            return None

        existing = await self._storage.get_rule_step(rg["name"], step_id)
        if existing is None:
            return None

        # Merge with existing data
        merged = {
            "id": step_id,
            "rule_group": rg["name"],
            "step_order": data.get("step_order", existing.order),
            "name": data.get("name", existing.name),
            "when": data.get("when", existing.when.to_dict()),
            "then": data.get("then", existing.then.to_dict()),
            "else": data.get("else", existing.else_.to_dict() if existing.else_ else None),
            "enabled": data.get("enabled", existing.enabled),
            "description": data.get("description", existing.description),
            "tags": data.get("tags", existing.tags),
        }

        await self._storage.save_rule_step(rg["name"], merged)
        return RuleStep.from_dict(merged)

    async def delete_rule_step(
        self,
        rule_group: str,
        step_id: str,
        schema_id: str | None = None,
    ) -> bool:
        """Delete a rule step.

        Args:
            rule_group: Parent rule group name
            step_id: Rule step ID
            schema_id: Semantic space ID for rule group lookup

        Returns:
            True if deleted, False if not found
        """
        # First resolve the rule group to get its actual name
        rg = await self._storage.get_rule_group(rule_group, schema_id=schema_id)
        if rg is None:
            return False

        existing = await self._storage.get_rule_step(rg["name"], step_id)
        if existing is None:
            return False

        await self._storage.delete_rule_step(rg["name"], step_id)
        return True

    async def reorder_rule_steps(
        self,
        rule_group: str,
        step_ids: list[str],
        schema_id: str | None = None,
    ) -> None:
        """Reorder rule steps.

        Args:
            rule_group: Rule group name
            step_ids: List of step IDs in new order
            schema_id: Semantic space ID for rule group lookup
        """
        # First resolve the rule group to get its actual name
        rg = await self._storage.get_rule_group(rule_group, schema_id=schema_id)
        if rg is None:
            raise RuleServiceError(f"Rule group '{rule_group}' not found")

        await self._storage.reorder_rule_steps(rg["name"], step_ids)

    # =========================================================================
    # YAML Import/Export
    # =========================================================================

    async def export_rule_group_to_yaml(
        self,
        rule_group_name: str,
        schema_id: str | None = None,
    ) -> str:
        """Export a rule group to YAML format.

        Args:
            rule_group_name: Rule group name
            schema_id: Semantic space ID for rule group lookup

        Returns:
            YAML string

        Raises:
            RuleServiceError: If rule group not found
        """
        rg_data = await self._storage.get_rule_group(rule_group_name, schema_id=schema_id)
        if rg_data is None:
            raise RuleServiceError(f"Rule group '{rule_group_name}' not found")

        steps_data = await self._storage.list_rule_steps(rg_data["name"])

        # Build YAML structure conforming to Schema v2
        yaml_data = {
            "rule_definitions": [
                {
                    "name": rg_data["name"],
                    "description": rg_data.get("description", ""),
                    "type": rg_data.get("type", "decision"),
                    "priority": rg_data.get("priority", 100),
                    "applies_to": rg_data.get("applies_to", {}),
                    "preconditions": rg_data.get("preconditions", []),
                    "inputs": rg_data.get("inputs", []),
                    "outputs": rg_data.get("outputs", []),
                }
            ],
            "rule_logics": [
                {
                    "name": f"{rule_group_name}_logic",
                    "rule_definition": rule_group_name,
                    "steps": [
                        {
                            "id": s["id"],
                            "name": s.get("name", ""),
                            "when": s.get("when", {}),
                            "then": s.get("then", {}),
                            "else": s.get("else"),
                        }
                        for s in steps_data
                    ],
                }
            ],
        }

        return yaml.dump(yaml_data, allow_unicode=True, sort_keys=False)

    async def import_from_yaml(
        self,
        yaml_content: str,
        schema_id: str | None = None,
    ) -> RuleGroupDefinition:
        """Import a rule group from YAML.

        Supports two formats:
        - Phase 2: rule_group + rule_steps structure (RFC-017 Section 2.1)
        - Legacy: rule_definitions + rule_logics structure (backward compatible)

        Args:
            yaml_content: YAML content string
            schema_id: Semantic space ID for the imported rule group (required)

        Returns:
            Imported RuleGroupDefinition

        Raises:
            RuleServiceError: If YAML is invalid, validation fails, or schema_id is missing
        """
        # schema_id is required for semantic space isolation
        if not schema_id:
            raise RuleServiceError("schema_id is required for semantic space isolation")

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise RuleServiceError(f"Invalid YAML: {e}")

        # Detect format: Phase 2 uses rule_group, legacy uses rule_definitions
        if "rule_group" in data:
            return await self._import_phase2_format(data, schema_id)
        elif "rule_definitions" in data:
            return await self._import_legacy_format(data, schema_id)
        else:
            raise RuleServiceError(
                "No valid rule format found. Expected 'rule_group' (Phase 2) or 'rule_definitions' (legacy)"
            )

    async def _import_phase2_format(
        self,
        data: dict[str, Any],
        schema_id: str,
    ) -> RuleGroupDefinition:
        """Import Phase 2 YAML format (rule_group + rule_steps).

        Args:
            data: Parsed YAML data
            schema_id: Semantic space ID

        Returns:
            Imported RuleGroupDefinition
        """
        rg_raw = data["rule_group"]
        steps_raw = data.get("rule_steps", [])

        name = rg_raw.get("name")
        if not name:
            raise RuleServiceError("Rule group must have a name")

        # Check if rule group already exists
        existing = await self._storage.get_rule_group(name, schema_id=schema_id)
        if existing:
            raise RuleServiceError(
                f"Rule group '{name}' already exists in semantic space '{schema_id}'"
            )

        # Normalize AppliesToConfig: fact_objects must be list, categories must be dict
        applies_to = self._normalize_applies_to(rg_raw.get("applies_to", {}))

        # Build rule group data
        rg_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": rg_raw.get("description", ""),
            "type": rg_raw.get("type", "decision"),
            "priority": rg_raw.get("priority", 100),
            "enabled": rg_raw.get("enabled", True),
            "applies_to": {
                "fact_objects": applies_to.fact_objects,
                "categories": applies_to.categories,
            },
            "preconditions": rg_raw.get("preconditions", []),
            "inputs": self._normalize_io_elements(rg_raw.get("inputs", [])),
            "outputs": self._normalize_io_elements(rg_raw.get("outputs", [])),
            "schema_id": schema_id,
        }

        # Save rule group
        await self._storage.save_rule_group(rg_data, schema_id=schema_id)

        # Process rule steps
        for step_raw in steps_raw:
            when_normalized = self._normalize_when(step_raw.get("when", {}))
            then_normalized = self._normalize_action(step_raw.get("then", {}))

            step_data = {
                "id": step_raw.get("id"),
                "name": step_raw.get("name", ""),
                "step_order": step_raw.get("order", 0),
                "enabled": step_raw.get("enabled", True),
                "description": step_raw.get("description", ""),
                "tags": step_raw.get("tags", []),
                "when": when_normalized,
                "then": then_normalized,
            }
            await self._storage.save_rule_step(name, step_data)

        return RuleGroupDefinition.from_dict(
            await self._storage.get_rule_group(name, schema_id=schema_id)
        )

    async def _import_legacy_format(
        self,
        data: dict[str, Any],
        schema_id: str,
    ) -> RuleGroupDefinition:
        """Import legacy YAML format (rule_definitions + rule_logics).

        Args:
            data: Parsed YAML data
            schema_id: Semantic space ID

        Returns:
            Imported RuleGroupDefinition
        """
        # Extract rule definition (legacy format)
        rule_defs = data.get("rule_definitions", [])
        if not rule_defs:
            raise RuleServiceError("No rule_definitions found in YAML")

        rule_def = rule_defs[0]
        name = rule_def.get("name")
        if not name:
            raise RuleServiceError("Rule definition must have a name")

        # Check if rule group already exists
        existing = await self._storage.get_rule_group(name, schema_id=schema_id)
        if existing:
            raise RuleServiceError(
                f"Rule group '{name}' already exists in semantic space '{schema_id}'"
            )

        # Prepare rule group data (legacy format)
        rg_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": rule_def.get("description", ""),
            "type": rule_def.get("type", "decision"),
            "priority": rule_def.get("priority", 100),
            "applies_to": rule_def.get("applies_to", {}),
            "preconditions": rule_def.get("preconditions", []),
            "inputs": rule_def.get("inputs", []),
            "outputs": rule_def.get("outputs", []),
            "enabled": True,
            "schema_id": schema_id,
        }

        # Save rule group
        await self._storage.save_rule_group(rg_data, schema_id=schema_id)

        # Extract and save rule steps from rule_logics
        rule_logics = data.get("rule_logics", [])
        for logic in rule_logics:
            if logic.get("rule_definition") == name:
                steps = logic.get("steps", [])
                for order, step in enumerate(steps):
                    step_data = {
                        "id": step.get("id"),
                        "name": step.get("name", ""),
                        "step_order": order,
                        "when": step.get("when", {}),
                        "then": step.get("then", {}),
                        "else": step.get("else"),
                        "enabled": True,
                    }
                    await self._storage.save_rule_step(name, step_data)

        return RuleGroupDefinition.from_dict(
            await self._storage.get_rule_group(name, schema_id=schema_id)
        )

    # =========================================================================
    # Helper methods for Phase 2 YAML normalization
    # =========================================================================

    def _normalize_applies_to(self, raw: dict[str, Any]) -> "AppliesToConfig":
        """Normalize AppliesToConfig: fact_objects must be list, categories must be dict.

        Args:
            raw: Raw applies_to dict from YAML

        Returns:
            AppliesToConfig with normalized fields
        """
        fact_objects = raw.get("fact_objects", [])
        if isinstance(fact_objects, str):
            fact_objects = [fact_objects]

        categories = raw.get("categories", {})
        # Legacy format may have categories as list, normalize to dict
        if isinstance(categories, list):
            categories = {}

        return AppliesToConfig(
            fact_objects=fact_objects,
            categories=categories,
        )

    def _normalize_io_elements(
        self,
        elements: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Normalize IO elements (inputs/outputs).

        Args:
            elements: List of IO element dicts

        Returns:
            Normalized list of IO element dicts
        """
        normalized = []
        for elem in elements:
            normalized.append({
                "name": elem.get("name", ""),
                "type": elem.get("type"),
                "metric": elem.get("metric"),
                "attribute": elem.get("attribute"),
            })
        return normalized

    def _normalize_when(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize when clause.

        Phase 2 format: when.type determines structure
        - expression: uses when.expression
        - all_of/any_of: uses when.sub_conditions

        Args:
            raw: Raw when clause dict

        Returns:
            Normalized when clause
        """
        if not raw:
            return {"type": "expression", "expression": None, "sub_conditions": []}

        when_type = raw.get("type", "expression")
        if when_type == "expression":
            return {
                "type": "expression",
                "expression": raw.get("expression"),
                "sub_conditions": [],
            }
        elif when_type in ("all_of", "any_of"):
            return {
                "type": when_type,
                "expression": None,
                "sub_conditions": raw.get("sub_conditions", []),
            }
        else:
            # Preserve original structure for unknown types
            return {
                "type": when_type,
                "expression": raw.get("expression"),
                "sub_conditions": raw.get("sub_conditions", []),
            }

    def _normalize_action(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize action/then clause.

        Phase 2 format uses then.operator directly from params,
        legacy format may have then as the operator itself.

        Args:
            raw: Raw action dict

        Returns:
            Normalized action clause
        """
        if not raw:
            return {"operator": "", "params": {}, "output_mapping": {}}

        return {
            "operator": raw.get("operator", ""),
            "params": raw.get("params", {}),
            "output_mapping": raw.get("output_mapping", {}),
        }

    async def validate_yaml(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate YAML without importing.

        Supports both Phase 2 (rule_group + rule_steps) and legacy (rule_definitions + rule_logics) formats.

        Args:
            yaml_content: YAML content string

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []

        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            return False, [f"Invalid YAML syntax: {e}"]

        # Detect format
        if "rule_group" in data:
            errors.extend(self._validate_phase2_format(data))
        elif "rule_definitions" in data:
            errors.extend(self._validate_legacy_format(data))
        else:
            errors.append("No valid rule format found. Expected 'rule_group' (Phase 2) or 'rule_definitions' (legacy)")

        return len(errors) == 0, errors

    def _validate_phase2_format(self, data: dict[str, Any]) -> list[str]:
        """Validate Phase 2 YAML format.

        Args:
            data: Parsed YAML data

        Returns:
            List of error messages
        """
        errors: list[str] = []

        # Validate rule_group
        rg = data.get("rule_group", {})
        if not rg.get("name"):
            errors.append("rule_group must have a name")

        # Validate rule_steps if present
        steps = data.get("rule_steps", [])
        if not isinstance(steps, list):
            errors.append("rule_steps must be a list")
        else:
            for i, step in enumerate(steps):
                if not step.get("id"):
                    errors.append(f"rule_steps[{i}] must have id")
                if not step.get("when"):
                    errors.append(f"rule_steps[{i}] must have when clause")

        return errors

    def _validate_legacy_format(self, data: dict[str, Any]) -> list[str]:
        """Validate legacy YAML format.

        Args:
            data: Parsed YAML data

        Returns:
            List of error messages
        """
        errors: list[str] = []

        # Check rule_definitions
        if "rule_definitions" not in data:
            errors.append("Missing required key: rule_definitions")
        elif not isinstance(data["rule_definitions"], list):
            errors.append("rule_definitions must be a list")
        elif len(data["rule_definitions"]) == 0:
            errors.append("rule_definitions cannot be empty")
        else:
            rd = data["rule_definitions"][0]
            if not rd.get("name"):
                errors.append("rule_definition[0] must have a name")

        # Check rule_logics if present
        if "rule_logics" in data:
            if not isinstance(data["rule_logics"], list):
                errors.append("rule_logics must be a list")
            else:
                for i, logic in enumerate(data["rule_logics"]):
                    if not logic.get("rule_definition"):
                        errors.append(f"rule_logics[{i}] must have rule_definition")
                    if "steps" in logic:
                        if not isinstance(logic["steps"], list):
                            errors.append(f"rule_logics[{i}].steps must be a list")
                        else:
                            for j, step in enumerate(logic["steps"]):
                                if not step.get("id"):
                                    errors.append(f"rule_logics[{i}].steps[{j}] must have id")

        return errors

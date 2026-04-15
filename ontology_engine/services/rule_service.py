# ontology_engine/services/rule_service.py
"""Rule orchestration service - CRUD and YAML import/export."""
from __future__ import annotations

from typing import Any

import yaml

from ontology_engine.engine.rule.models import (
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

    async def create_rule_group(self, data: dict[str, Any]) -> RuleGroupDefinition:
        """Create a new rule group.

        Args:
            data: Rule group data

        Returns:
            Created RuleGroupDefinition

        Raises:
            RuleServiceError: If rule group already exists
        """
        name = data.get("name")
        if not name:
            raise RuleServiceError("Rule group name is required")

        existing = await self._storage.get_rule_group(name)
        if existing:
            raise RuleServiceError(f"Rule group '{name}' already exists")

        # Save to storage
        await self._storage.save_rule_group(data)

        return RuleGroupDefinition.from_dict(data)

    async def get_rule_group(self, name: str) -> RuleGroupDefinition | None:
        """Get a rule group by name.

        Args:
            name: Rule group name

        Returns:
            RuleGroupDefinition or None if not found
        """
        data = await self._storage.get_rule_group(name)
        if data is None:
            return None
        return RuleGroupDefinition.from_dict(data)

    async def list_rule_groups(
        self,
        enabled: bool | None = None,
    ) -> list[RuleGroupDefinition]:
        """List rule groups with optional filter.

        Args:
            enabled: Optional filter by enabled status

        Returns:
            List of RuleGroupDefinition
        """
        rows = await self._storage.list_rule_groups(enabled=enabled)
        return [RuleGroupDefinition.from_dict(r) for r in rows]

    async def update_rule_group(
        self,
        name: str,
        data: dict[str, Any],
    ) -> RuleGroupDefinition | None:
        """Update a rule group.

        Args:
            name: Rule group name
            data: Updated rule group data

        Returns:
            Updated RuleGroupDefinition or None if not found
        """
        existing = await self._storage.get_rule_group(name)
        if existing is None:
            return None

        # Merge with existing data
        merged = dict(existing)
        merged.update(data)
        merged["name"] = name

        await self._storage.save_rule_group(merged)
        return RuleGroupDefinition.from_dict(merged)

    async def delete_rule_group(self, name: str) -> bool:
        """Delete a rule group and its steps.

        Args:
            name: Rule group name

        Returns:
            True if deleted, False if not found
        """
        existing = await self._storage.get_rule_group(name)
        if existing is None:
            return False

        await self._storage.delete_rule_group(name)
        return True

    # =========================================================================
    # Rule Step CRUD
    # =========================================================================

    async def create_rule_step(
        self,
        rule_group: str,
        data: dict[str, Any],
    ) -> RuleStep:
        """Create a new rule step.

        Args:
            rule_group: Parent rule group name
            data: Rule step data

        Returns:
            Created RuleStep

        Raises:
            RuleServiceError: If rule step already exists
        """
        step_id = data.get("id")
        if not step_id:
            raise RuleServiceError("Rule step ID is required")

        # Verify rule group exists
        rg = await self._storage.get_rule_group(rule_group)
        if rg is None:
            raise RuleServiceError(f"Rule group '{rule_group}' not found")

        # Save to storage
        await self._storage.save_rule_step(rule_group, data)

        return RuleStep.from_dict({**data, "rule_group": rule_group})

    async def get_rule_step(
        self,
        rule_group: str,
        step_id: str,
    ) -> RuleStep | None:
        """Get a rule step by ID.

        Args:
            rule_group: Parent rule group name
            step_id: Rule step ID

        Returns:
            RuleStep or None if not found
        """
        data = await self._storage.get_rule_step(rule_group, step_id)
        if data is None:
            return None
        return RuleStep.from_dict(data)

    async def list_rule_steps(self, rule_group: str) -> list[RuleStep]:
        """List all rule steps for a rule group.

        Args:
            rule_group: Rule group name

        Returns:
            List of RuleStep ordered by step_order
        """
        rows = await self._storage.list_rule_steps(rule_group)
        return [RuleStep.from_dict(r) for r in rows]

    async def update_rule_step(
        self,
        rule_group: str,
        step_id: str,
        data: dict[str, Any],
    ) -> RuleStep | None:
        """Update a rule step.

        Args:
            rule_group: Parent rule group name
            step_id: Rule step ID
            data: Updated rule step data

        Returns:
            Updated RuleStep or None if not found
        """
        existing = await self._storage.get_rule_step(rule_group, step_id)
        if existing is None:
            return None

        # Merge with existing data
        merged = {
            "id": step_id,
            "rule_group": rule_group,
            "step_order": data.get("step_order", existing.order),
            "name": data.get("name", existing.name),
            "when": data.get("when", existing.when.to_dict()),
            "then": data.get("then", existing.then.to_dict()),
            "else": data.get("else", existing.else_.to_dict() if existing.else_ else None),
            "enabled": data.get("enabled", existing.enabled),
            "description": data.get("description", existing.description),
            "tags": data.get("tags", existing.tags),
        }

        await self._storage.save_rule_step(rule_group, merged)
        return RuleStep.from_dict(merged)

    async def delete_rule_step(self, rule_group: str, step_id: str) -> bool:
        """Delete a rule step.

        Args:
            rule_group: Parent rule group name
            step_id: Rule step ID

        Returns:
            True if deleted, False if not found
        """
        existing = await self._storage.get_rule_step(rule_group, step_id)
        if existing is None:
            return False

        await self._storage.delete_rule_step(rule_group, step_id)
        return True

    async def reorder_rule_steps(
        self,
        rule_group: str,
        step_ids: list[str],
    ) -> None:
        """Reorder rule steps.

        Args:
            rule_group: Rule group name
            step_ids: List of step IDs in new order
        """
        await self._storage.reorder_rule_steps(rule_group, step_ids)

    # =========================================================================
    # YAML Import/Export
    # =========================================================================

    async def export_rule_group_to_yaml(self, rule_group_name: str) -> str:
        """Export a rule group to YAML format.

        Args:
            rule_group_name: Rule group name

        Returns:
            YAML string

        Raises:
            RuleServiceError: If rule group not found
        """
        rg_data = await self._storage.get_rule_group(rule_group_name)
        if rg_data is None:
            raise RuleServiceError(f"Rule group '{rule_group_name}' not found")

        steps_data = await self._storage.list_rule_steps(rule_group_name)

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

    async def import_from_yaml(self, yaml_content: str) -> RuleGroupDefinition:
        """Import a rule group from YAML.

        Args:
            yaml_content: YAML content string

        Returns:
            Imported RuleGroupDefinition

        Raises:
            RuleServiceError: If YAML is invalid or validation fails
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise RuleServiceError(f"Invalid YAML: {e}")

        # Extract rule definition
        rule_defs = data.get("rule_definitions", [])
        if not rule_defs:
            raise RuleServiceError("No rule_definitions found in YAML")

        rule_def = rule_defs[0]
        name = rule_def.get("name")
        if not name:
            raise RuleServiceError("Rule definition must have a name")

        # Validate and save rule group
        await self._storage.save_rule_group({
            "name": name,
            "description": rule_def.get("description", ""),
            "type": rule_def.get("type", "decision"),
            "priority": rule_def.get("priority", 100),
            "applies_to": rule_def.get("applies_to", {}),
            "preconditions": rule_def.get("preconditions", []),
            "inputs": rule_def.get("inputs", []),
            "outputs": rule_def.get("outputs", []),
            "enabled": True,
        })

        # Extract and save rule steps
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

        return RuleGroupDefinition.from_dict(await self._storage.get_rule_group(name))

    async def validate_yaml(self, yaml_content: str) -> tuple[bool, list[str]]:
        """Validate YAML without importing.

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

        return len(errors) == 0, errors

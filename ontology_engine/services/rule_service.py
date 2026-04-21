# ontology_engine/services/rule_service.py
"""Rule orchestration service - CRUD and YAML import/export."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import yaml

from ontology_engine.engine.rule.models import (
    AppliesToConfig,
    RuleGroupDefinition,
    RuleStep,
)
from ontology_engine.storage.base import StorageBackend

# L4 action_type -> Phase 2 operator mapping
ACTION_TYPE_MAP = {
    "set_flag": "SET_FLAG",
    "compute": "COMPUTE",
    "alert": "ALERT",
    "approve": "APPROVE",
    "reject": "REJECT",
    "set_value": "SET_VALUE",
}


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

    async def locate_rule_groups(
        self,
        output_name: str,
        schema_id: str | None = None,
    ) -> list[RuleGroupDefinition]:
        """Locate rule groups that produce a specific output element.

        Searches across all rule groups (optionally filtered by semantic space)
        to find those that define the specified output element.

        Args:
            output_name: Output element name to search for
            schema_id: Semantic space ID (optional, searches all if not provided)

        Returns:
            List of RuleGroupDefinition that produce the specified output
        """
        # Get all rule groups
        rule_groups = await self.list_rule_groups(schema_id=schema_id)

        # Find rule groups that have this output
        matching_groups = []
        for rg in rule_groups:
            for out in rg.outputs:
                if out.name == output_name:
                    matching_groups.append(rg)
                    break  # Only list each rule group once

        return matching_groups

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
        """Export a rule group to YAML format (Phase 2).

        Args:
            rule_group_name: Rule group name
            schema_id: Semantic space ID for rule group lookup

        Returns:
            YAML string in Phase 2 format (rule_group + rule_steps)

        Raises:
            RuleServiceError: If rule group not found
        """
        rg_data = await self._storage.get_rule_group(rule_group_name, schema_id=schema_id)
        if rg_data is None:
            raise RuleServiceError(f"Rule group '{rule_group_name}' not found")

        steps_data = await self._storage.list_rule_steps(rg_data["name"])

        # Build Phase 2 YAML structure (RFC-017 Section 2.1)
        yaml_data = {
            "rule_group": {
                "name": rg_data["name"],
                "description": rg_data.get("description", ""),
                "type": rg_data.get("type", "decision"),
                "priority": rg_data.get("priority", 100),
                "enabled": rg_data.get("enabled", True),
                "applies_to": rg_data.get("applies_to", {}),
                "preconditions": rg_data.get("preconditions", []),
                "inputs": rg_data.get("inputs", []),
                "outputs": rg_data.get("outputs", []),
            },
            "rule_steps": [
                {
                    "id": s["id"],
                    "name": s.get("name", ""),
                    "order": s.get("step_order", s.get("order", 0)),
                    "enabled": s.get("enabled", True),
                    "description": s.get("description", ""),
                    "tags": s.get("tags", []),
                    "when": s.get("when", {}),
                    "then": s.get("then", {}),
                    "else": s.get("else"),
                }
                for s in steps_data
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

        # Process rule steps in parallel
        async def save_step(step_raw: dict[str, Any]) -> None:
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

        await asyncio.gather(*[save_step(s) for s in steps_raw])

        return RuleGroupDefinition.from_dict(rg_data)

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

        # Extract and save rule steps from rule_logics in parallel
        async def save_legacy_step(step: dict[str, Any], order: int) -> None:
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

        rule_logics = data.get("rule_logics", [])
        save_tasks = []
        for logic in rule_logics:
            if logic.get("rule_definition") == name:
                steps = logic.get("steps", [])
                for order, step in enumerate(steps):
                    save_tasks.append(save_legacy_step(step, order))

        if save_tasks:
            await asyncio.gather(*save_tasks)

        return RuleGroupDefinition.from_dict(rg_data)

    # L4 Schema YAML Import (Legacy Compatibility)
    # =========================================================================

    async def import_from_l4_schema_yaml(
        self,
        yaml_content: str,
        schema_id: str | None = None,
    ) -> list[RuleGroupDefinition]:
        """Import rules from old L4 schema.yaml format (nested in semantic_space.business_logic).

        Single-direction only: converts L4 format to Phase 2 format.
        Does NOT export back to L4 format.

        L4 Format Structure:
            semantic_space:
              business_logic:
                rule_definitions:
                  - id: RD001_basic_eligibility
                    name: "基础准入检查"
                    rule_type: constraint
                    applies_to: [Supplier]
                    applicable_categorizations: [credit_assessment]
                    inputs:
                      - { id: status, name: "经营状态", type: attribute }
                    outputs:
                      - { id: is_eligible, name: "是否准入", type: flag }
                    logic_ids: [RL001_eligibility_standard]
                    enabled: true
                rule_logics:
                  - id: RL001_eligibility_standard
                    definition_id: RD001_basic_eligibility
                    when:
                      expression: "status == 'ACTIVE'"
                    then_action:
                      action_type: set_flag
                      output:
                        is_eligible: true
                    else_action:
                      action_type: set_flag
                      output:
                        is_eligible: false

        Field Mapping:
            L4 Old                     -> Phase 2 New
            id (rule_definition)       -> name
            rule_type                  -> type
            applies_to: [Supplier]     -> applies_to.fact_objects: ["Supplier"]
            applicable_categorizations -> applies_to.categories: {} (empty for now)
            inputs[].id                -> inputs[].name
            outputs[].id               -> outputs[].name
            logic_ids: [RL001]         -> Multiple rule_steps from each matching logic
            action_type: set_flag      -> operator: SET_FLAG
            output: {is_eligible: true} -> params: {flag_name: "is_eligible", flag_value: true}
            when.expression (string)  -> when.type: "expression", when.expression

        Args:
            yaml_content: YAML content string in L4 format
            schema_id: Semantic space ID (required for isolation)

        Returns:
            List of imported RuleGroupDefinition

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

        # Extract business_logic from semantic_space
        semantic_space = data.get("semantic_space", {})
        business_logic = semantic_space.get("business_logic", {})
        rule_definitions = business_logic.get("rule_definitions", [])
        rule_logics = business_logic.get("rule_logics", [])

        if not rule_definitions:
            raise RuleServiceError("No rule_definitions found in L4 schema YAML")

        # Pre-build lookup dict: definition_id -> list of matching logics
        # Also index by logic id for logic_ids references
        definition_logics: dict[str, list[dict[str, Any]]] = {}
        logic_by_id: dict[str, dict[str, Any]] = {}
        for logic in rule_logics:
            def_id = logic.get("definition_id", "")
            if def_id:
                if def_id not in definition_logics:
                    definition_logics[def_id] = []
                definition_logics[def_id].append(logic)
            logic_id = logic.get("id", "")
            if logic_id:
                logic_by_id[logic_id] = logic

        imported_rule_groups: list[RuleGroupDefinition] = []

        # Process each rule_definition
        for rule_def in rule_definitions:
            rule_def_id = rule_def.get("id")
            name = rule_def.get("name")
            if not name:
                raise RuleServiceError("Rule definition must have a name")

            # Check if rule group already exists
            existing = await self._storage.get_rule_group(name, schema_id=schema_id)
            if existing:
                raise RuleServiceError(
                    f"Rule group '{name}' already exists in semantic space '{schema_id}'"
                )

            # Map rule_type -> type
            rule_type = rule_def.get("rule_type", "decision")

            # Map applies_to: [Supplier] -> applies_to.fact_objects: ["Supplier"]
            applies_to_list = rule_def.get("applies_to", [])
            if isinstance(applies_to_list, str):
                applies_to_list = [applies_to_list]

            # Map applicable_categorizations -> categories (empty dict for now)
            # Note: applicable_categorizations not yet mapped, reserved for future use

            # Normalize inputs: id -> name
            inputs_raw = rule_def.get("inputs", [])
            inputs_normalized = []
            for inp in inputs_raw:
                inputs_normalized.append({
                    "name": inp.get("id", inp.get("name", "")),
                    "type": inp.get("type"),
                    "metric": inp.get("metric"),
                    "attribute": inp.get("attribute"),
                })

            # Normalize outputs: id -> name
            outputs_raw = rule_def.get("outputs", [])
            outputs_normalized = []
            for out in outputs_raw:
                outputs_normalized.append({
                    "name": out.get("id", out.get("name", "")),
                    "type": out.get("type"),
                })

            # Build rule group data
            rg_data = {
                "id": str(uuid.uuid4()),
                "name": name,
                "description": rule_def.get("description", ""),
                "type": rule_type,
                "priority": rule_def.get("priority", 100),
                "enabled": rule_def.get("enabled", True),
                "applies_to": {
                    "fact_objects": applies_to_list,
                    "categories": {},  # applicable_categorizations not mapped yet
                },
                "preconditions": [],
                "inputs": inputs_normalized,
                "outputs": outputs_normalized,
                "schema_id": schema_id,
            }

            # Find all rule_logics that reference this rule_definition
            logic_ids = rule_def.get("logic_ids", [])
            matching_logics = list(definition_logics.get(rule_def_id, []))
            for lid in logic_ids:
                if lid in logic_by_id and lid not in [lg.get("id") for lg in matching_logics]:
                    matching_logics.append(logic_by_id[lid])

            # Save rule group and create rule_steps in parallel
            await self._storage.save_rule_group(rg_data, schema_id=schema_id)

            async def save_l4_step(logic: dict[str, Any], order: int) -> None:
                step_data = self._convert_l4_logic_to_step(logic, name, order)
                await self._storage.save_rule_step(name, step_data)

            save_tasks = [save_l4_step(logic, order) for order, logic in enumerate(matching_logics)]
            if save_tasks:
                await asyncio.gather(*save_tasks)

            imported_rule_groups.append(RuleGroupDefinition.from_dict(rg_data))

        return imported_rule_groups

    def _convert_l4_logic_to_step(
        self,
        logic: dict[str, Any],
        rule_group_name: str,
        order: int,
    ) -> dict[str, Any]:
        """Convert an L4 rule_logic to a Phase 2 rule_step.

        Args:
            logic: L4 rule_logic dict
            rule_group_name: Name of the parent rule group
            order: Step order

        Returns:
            Phase 2 rule_step dict
        """
        logic_id = logic.get("id", "")
        logic_name = logic.get("name", logic_id)

        # Convert when clause
        when_raw = logic.get("when", {})
        when_normalized = self._normalize_l4_when(when_raw)

        # Convert then_action
        then_action = logic.get("then_action", {})
        then_normalized = self._normalize_l4_action(then_action)

        # Convert else_action
        else_action = logic.get("else_action")
        else_normalized = self._normalize_l4_action(else_action) if else_action else None

        return {
            "id": logic_id,
            "name": logic_name,
            "step_order": order,
            "enabled": True,
            "description": logic.get("description", ""),
            "tags": [],
            "when": when_normalized,
            "then": then_normalized,
            "else": else_normalized,
        }

    def _normalize_l4_when(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize L4 when clause to Phase 2 format.

        L4 when can have:
        - expression: "string expression"
        - allOf/anyOf: [list of conditions]

        Phase 2 when has:
        - type: "expression" | "all_of" | "any_of"
        - expression: string (for type=expression)
        - sub_conditions: [] (for type=all_of/any_of)

        Args:
            raw: L4 when clause dict

        Returns:
            Phase 2 when clause
        """
        if not raw:
            return {"type": "expression", "expression": None, "sub_conditions": []}

        # Handle expression string
        if "expression" in raw:
            expression = raw["expression"]
            if isinstance(expression, str):
                return {
                    "type": "expression",
                    "expression": expression,
                    "sub_conditions": [],
                }
            # If expression is already parsed (not a string), treat as expression
            return {
                "type": "expression",
                "expression": str(expression) if expression else None,
                "sub_conditions": [],
            }

        # Handle allOf/anyOf
        if "allOf" in raw or "anyOf" in raw:
            cond_type = "all_of" if "allOf" in raw else "any_of"
            conditions = raw.get("allOf") or raw.get("anyOf") or []
            return {
                "type": cond_type,
                "expression": None,
                "sub_conditions": conditions,
            }

        # Fallback: treat entire raw as expression
        return {
            "type": "expression",
            "expression": str(raw) if raw else None,
            "sub_conditions": [],
        }

    def _normalize_l4_action(self, raw: dict[str, Any] | None) -> dict[str, Any]:
        """Normalize L4 action (then_action/else_action) to Phase 2 format.

        L4 action structure:
            then_action:
              action_type: set_flag
              output:
                is_eligible: true
                rejection_reason: "..."

        Phase 2 action structure:
            then:
              operator: SET_FLAG
              params:
                flag_name: "is_eligible"
                flag_value: true
              output_mapping: {}

        Args:
            raw: L4 action dict

        Returns:
            Phase 2 action clause
        """
        if not raw:
            return {"operator": "", "params": {}, "output_mapping": {}}

        action_type = raw.get("action_type", "")
        output = raw.get("output", {})

        # Map L4 action_type to Phase 2 operator
        operator = self._map_l4_action_type(action_type)

        # Convert L4 output to params and output_mapping
        params, output_mapping = self._convert_l4_output(output, action_type)

        return {
            "operator": operator,
            "params": params,
            "output_mapping": output_mapping,
        }

    def _map_l4_action_type(self, action_type: str) -> str:
        """Map L4 action_type to Phase 2 operator.

        Args:
            action_type: L4 action type string

        Returns:
            Phase 2 operator string
        """
        return ACTION_TYPE_MAP.get(action_type.lower(), action_type.upper())

    def _convert_l4_output(
        self,
        output: dict[str, Any],
        action_type: str,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Convert L4 output to Phase 2 params and output_mapping.

        For set_flag action:
            L4: output: {is_eligible: true, rejection_reason: "..."}
            Phase 2: params: {flag_name: "is_eligible", flag_value: true}
                     output_mapping: {rejection_reason: "rejection_reason"}

        For compute action:
            L4: output: {credit_score: "$metric:credit_score", ...}
            Phase 2: params: {computations: {credit_score: "$metric:credit_score", ...}}
                     output_mapping: {}

        Args:
            output: L4 output dict
            action_type: L4 action type

        Returns:
            Tuple of (params, output_mapping)
        """
        if action_type == "set_flag":
            # Extract flag_name and flag_value from output
            flag_name = None
            flag_value = None
            output_mapping = {}

            for key, value in output.items():
                if flag_name is None and isinstance(value, bool):
                    # First boolean value is the flag
                    flag_name = key
                    flag_value = value
                else:
                    # Other values go to output_mapping
                    output_mapping[key] = key

            params = {}
            if flag_name is not None:
                params["flag_name"] = flag_name
                params["flag_value"] = flag_value

            return params, output_mapping

        elif action_type == "compute":
            # For compute, put all outputs in params.computations
            return {"computations": output}, {}

        elif action_type == "alert":
            # For alert, put output in params
            return {"alert_data": output}, {}

        else:
            # Default: pass through output as params
            return {"raw_output": output}, {}

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
                "expression": raw.get("expression", ""),
                "sub_conditions": [],
            }
        elif when_type in ("all_of", "any_of"):
            return {
                "type": when_type,
                "expression": "",
                "sub_conditions": raw.get("sub_conditions", []),
            }
        else:
            # Preserve original structure for unknown types
            return {
                "type": when_type,
                "expression": raw.get("expression", ""),
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

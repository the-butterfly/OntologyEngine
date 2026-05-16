# ontology_engine/services/rule_locator.py
"""RuleLocator service - locate rule definitions by input/output elements."""

from __future__ import annotations

from ontology_engine.services.space_service import SpaceService

# Key constants for rule definition dicts
_KEY_INPUTS = "inputs"
_KEY_OUTPUTS = "outputs"
_KEY_ID = "id"


class RuleLocator:
    """Service to locate rule definitions by their input/output elements."""

    def __init__(self, service: SpaceService):
        self._service = service

    async def locate_by_output(self, output_name: str, schema_id: str) -> list[dict]:
        """Find rule definitions that produce a specific output element.

        Args:
            output_name: The name of the output element to search for
            schema_id: The schema (space) ID to search within

        Returns:
            List of rule definition dicts that have the specified output
        """
        return await self._find_rules(output_name, _KEY_OUTPUTS, schema_id)

    async def locate_by_input(self, input_name: str, schema_id: str) -> list[dict]:
        """Find rule definitions that consume a specific input element.

        Args:
            input_name: The name of the input element to search for
            schema_id: The schema (space) ID to search within

        Returns:
            List of rule definition dicts that have the specified input
        """
        return await self._find_rules(input_name, _KEY_INPUTS, schema_id)

    async def _find_rules(
        self, element_name: str, element_list_key: str, schema_id: str
    ) -> list[dict]:
        """Find rules containing a specific element in their input/output list.

        Args:
            element_name: The name of the element to search for
            element_list_key: The key for the list to search in ("inputs" or "outputs")
            schema_id: The schema (space) ID to search within

        Returns:
            List of rule definition dicts that contain the specified element
        """
        space = await self._service.get_space(schema_id)
        if not space:
            return []

        if not space.layers.L4_business_logic:
            return []

        rule_definitions = space.layers.L4_business_logic.rule_definitions
        if not rule_definitions:
            return []

        matching_rules = []
        for rule in rule_definitions:
            elements = rule.get(element_list_key, [])
            for elem in elements:
                if elem.get(_KEY_ID) == element_name:
                    matching_rules.append(rule)
                    break

        return matching_rules
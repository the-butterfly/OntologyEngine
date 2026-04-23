# ontology_engine/api/routes/simulation.py
"""Simulation API endpoints for cross-rule-group execution."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from ontology_engine.services.simulation_session import SessionManager, SimulationSession
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage

router = APIRouter(prefix="/v1/simulation", tags=["Simulation"])

# Global session manager and tree builder
_session_manager = SessionManager()
_semantic_space_storage = SemanticSpaceStorage()
_tree_builder = RuleTreeBuilder(semantic_space_storage=_semantic_space_storage)


class CreateSimulationRequest(BaseModel):
    """Request body for creating a simulation tree."""
    schema_id: str
    entity_id: str | None = None
    target_output: str
    input_values: dict[str, Any] | None = None


class UpdateSimulationRequest(BaseModel):
    """Request body for updating simulation inputs."""
    input_values: dict[str, Any]
    full_override: bool = False


@router.post("/tree")
async def create_simulation_tree(body: CreateSimulationRequest):
    """Create a new simulation session and build execution tree.

    Args:
        body: CreateSimulationRequest with schema_id, target_output, etc.

    Returns:
        Success response with session_id and execution_tree
    """
    try:
        # Build execution tree
        tree = await _tree_builder.build_tree(
            schema_id=body.schema_id,
            entity_id=body.entity_id,
            target_output=body.target_output,
        )

        # Create session
        session = _session_manager.create_session(
            schema_id=body.schema_id,
            entity_id=body.entity_id or "",
            target_output=body.target_output,
            execution_tree=tree,
        )

        # Auto-fill inputs from entity attributes if entity_id is provided
        if body.entity_id:
            auto_filled = await _auto_fill_inputs_from_entity(
                schema_id=body.schema_id,
                entity_id=body.entity_id,
                tree=tree,
            )
            if auto_filled:
                _session_manager.update_inputs(
                    session.session_id,
                    auto_filled,
                    partial=False,
                )

        # Pre-fill inputs if provided (after auto-fill)
        if body.input_values:
            _session_manager.update_inputs(
                session.session_id,
                body.input_values,
                partial=False,
            )

        return success_response(data={
            "session_id": session.session_id,
            "execution_tree": tree,
            "required_inputs": _extract_required_inputs(tree),
            "current_inputs": session.current_inputs,
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/{session_id}")
async def get_simulation_session(session_id: str):
    """Get current simulation session state.

    Args:
        session_id: The simulation session ID

    Returns:
        Success response with session data or error if not found
    """
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return success_response(data={
        "session_id": session.session_id,
        "execution_tree": session.execution_tree,
        "current_inputs": session.current_inputs,
        "result": session.current_result,
    })


@router.patch("/{session_id}")
async def update_simulation_inputs(session_id: str, body: UpdateSimulationRequest):
    """Update simulation inputs (partial or full override).

    Args:
        session_id: The simulation session ID
        body: UpdateSimulationRequest with input_values and full_override flag

    Returns:
        Success response with updated inputs and missing inputs list
    """
    session = _session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    _session_manager.update_inputs(
        session_id,
        body.input_values,
        partial=not body.full_override,
    )

    # Check if all required inputs are filled
    missing = _get_missing_inputs(session)
    result = None
    if not missing and session.execution_tree.get("total_steps", 0) > 0:
        result = await _run_simulation(session)

    return success_response(data={
        "session_id": session_id,
        "updated_inputs": session.current_inputs,
        "result": result,
        "missing_inputs": missing,
    })


@router.delete("/{session_id}")
async def delete_simulation_session(session_id: str):
    """Delete a simulation session.

    Args:
        session_id: The simulation session ID to delete

    Returns:
        Success response confirming deletion or error if not found
    """
    deleted = _session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return success_response(data={"deleted": True})


def _extract_required_inputs(tree: dict) -> list[str]:
    """Extract required input elements from execution tree.

    Args:
        tree: Execution tree dictionary

    Returns:
        List of required input attribute names
    """
    inputs = []
    for layer in tree.get("layers", []):
        for step in layer.get("steps", []):
            for inp in step.get("inputs", []):
                if inp.get("type") == "attribute" and inp.get("name") not in inputs:
                    inputs.append(inp["name"])
    return inputs


def _get_missing_inputs(session: SimulationSession) -> list[str]:
    """Get list of missing required inputs.

    Args:
        session: SimulationSession instance

    Returns:
        List of required input names that are not yet provided
    """
    required = _extract_required_inputs(session.execution_tree)
    return [inp for inp in required if inp not in session.current_inputs]


async def _auto_fill_inputs_from_entity(
    schema_id: str,
    entity_id: str,
    tree: dict[str, Any],
) -> dict[str, Any]:
    """Auto-fill input values from entity attributes.

    This function:
    1. Loads the semantic space
    2. Finds the entity by entity_id
    3. Extracts L3 analytical element values based on source.attribute mapping
    4. Returns a dict of input_name -> value

    Args:
        schema_id: The space ID to load
        entity_id: The entity ID to look up
        tree: The execution tree (used to get required input names)

    Returns:
        Dict of input_name -> value for auto-filled inputs
    """
    try:
        space = await _semantic_space_storage.load(schema_id)
        if not space:
            return {}

        # Find entity in instances
        entity = None
        for ent in space.instances.entities:
            if ent.get("entity_id") == entity_id or ent.get("id") == entity_id:
                entity = ent
                break

        if not entity:
            return {}

        # Build mapping: L3 element id -> source.attribute
        # We need to find all L3 elements that can be sourced from entity attributes
        # regardless of the input type in the tree (attribute, metric, etc.)
        l3_attribute_mapping: dict[str, str] = {}
        for l3_element in space.layers.L3_analytical_elements:
            element_id = l3_element.get("id", "")
            source = l3_element.get("source", {})
            attr_path = source.get("attribute")
            if attr_path:
                l3_attribute_mapping[element_id] = attr_path

        # Now find which of these L3 elements are actually needed as inputs in the tree
        # We use the element id (not name) to match
        required_input_ids = set()
        for layer in tree.get("layers", []):
            for step in layer.get("steps", []):
                for inp in step.get("inputs", []):
                    inp_id = inp.get("id", "")
                    if inp_id:
                        required_input_ids.add(inp_id)

        # Auto-fill values for L3 elements that have source.attribute and are in required inputs
        input_values = {}
        for element_id, attr_path in l3_attribute_mapping.items():
            if element_id in required_input_ids:
                value = _get_nested_value(entity, attr_path)
                if value is not None:
                    input_values[element_id] = value

        return input_values

    except Exception:
        # Don't fail the request if auto-fill fails, just return empty
        return {}


def _get_nested_value(data: dict, path: str) -> Any:
    """Get nested value from dict using dot notation path.

    Args:
        data: Dictionary to search
        path: Dot-notation path (e.g., "credit_score" or "attributes.credit_score")

    Returns:
        Value at path or None if not found
    """
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


async def _run_simulation(session: SimulationSession) -> dict[str, Any]:
    """Run simulation with current inputs.

    Args:
        session: SimulationSession with all required inputs filled

    Returns:
        Simulation result dictionary
    """
    raise NotImplementedError("Simulation execution requires DAGExecutor integration")
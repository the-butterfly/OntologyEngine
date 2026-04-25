# ontology_engine/api/routes/simulation.py
"""Simulation API endpoints for cross-rule-group execution."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from ontology_engine.services.simulation_session import SessionManager, SimulationSession
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder
from ontology_engine.services.dag_executor import DAGExecutor
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

    missing = _get_missing_inputs(session)
    result = None
    simulation_error = None
    if not missing and session.execution_tree.get("total_steps", 0) > 0:
        try:
            result = await _run_simulation(session)
        except ValueError as e:
            simulation_error = str(e)
        except Exception as e:
            simulation_error = f"Simulation execution failed: {type(e).__name__}: {e}"

    return success_response(data={
        "session_id": session_id,
        "updated_inputs": session.current_inputs,
        "result": result,
        "missing_inputs": missing,
        "simulation_error": simulation_error,
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
        List of required input IDs (using 'id' field for consistency)
    """
    inputs = []
    for layer in tree.get("layers", []):
        for step in layer.get("steps", []):
            for inp in step.get("inputs", []):
                inp_id = inp.get("id") if isinstance(inp, dict) else inp
                inp_type = inp.get("type", "attribute") if isinstance(inp, dict) else "attribute"
                if inp_type == "attribute" and inp_id and inp_id not in inputs:
                    inputs.append(inp_id)
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

        # Build L3 mapping by name -> attribute path
        l3_name_to_attr_path: dict[str, str] = {}
        for l3_element in space.layers.L3_analytical_elements:
            element_name = l3_element.get("name", "")
            source = l3_element.get("source", {})
            attr_path = source.get("attribute")
            if attr_path and element_name:
                l3_name_to_attr_path[element_name] = attr_path

        # Now find which inputs are actually required based on input_requirements
        # input_requirements uses 'name' field (not 'id')
        required_input_names = set()
        for layer in tree.get("layers", []):
            for req in layer.get("input_requirements", []):
                req_name = req.get("name", "")
                if req_name:
                    required_input_names.add(req_name)

        # Auto-fill values using input name as key (matching input_requirements.name)
        # Strategy 1: Try L3 analytical element source.attribute mapping
        # Strategy 2: Fallback to direct entity attribute lookup
        input_values = {}
        for input_name in required_input_names:
            # Strategy 1: L3 mapping
            if input_name in l3_name_to_attr_path:
                attr_path = l3_name_to_attr_path[input_name]
                value = _get_nested_value(entity, attr_path)
                if value is not None:
                    input_values[input_name] = value
                    continue

            # Strategy 2: Direct entity attribute lookup
            # Handle nested objects with .value (e.g., registered_capital: {value: 50000000, currency: "CNY"})
            if input_name in entity:
                raw_value = entity[input_name]
                if raw_value is not None:
                    if isinstance(raw_value, dict) and 'value' in raw_value:
                        input_values[input_name] = raw_value['value']
                    else:
                        input_values[input_name] = raw_value

        return input_values

    except Exception as e:
        # Don't fail the request if auto-fill fails, just return empty
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Auto-fill failed: {e}")
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
        Simulation result dictionary matching frontend SimulationResult type
    """
    import time

    start_time = time.time()

    space = await _semantic_space_storage.load(session.schema_id)
    if not space:
        raise ValueError(f"Space {session.schema_id} not found")

    # Find entity in the space
    entity = None
    for e in space.instances.entities:
        if e.get("entity_id") == session.entity_id or e.get("id") == session.entity_id:
            entity = dict(e)
            break

    if not entity:
        raise ValueError(f"Entity {session.entity_id} not found")

    # Execute the rule tree using DAGExecutor
    executor = DAGExecutor(space)
    raw_result = await executor.execute(
        execution_tree=session.execution_tree,
        entity_data=entity,
        input_overrides=session.current_inputs,
    )

    execution_time_ms = int((time.time() - start_time) * 1000)

    # Convert to frontend SimulationResult format
    # Flatten step_results from layer structure to flat steps list
    steps = []
    for layer_result in raw_result.get("step_results", []):
        layer_index = layer_result.get("layer_index", 0)
        for step_result in layer_result.get("step_results", []):
            step_result["layer_index"] = layer_index
            steps.append(step_result)

    # Build alerts from step results
    alerts = []
    for step in steps:
        if step.get("action_taken") == "alert":
            alerts.append({
                "level": "warning",
                "type": "rule_alert",
                "message": f"Alert from {step['step_name']}: {step.get('output', {})}",
                "source_step": step["step_id"],
            })

    # Build errors list
    errors = raw_result.get("errors") or []
    if not isinstance(errors, list):
        errors = [errors] if errors else []

    result = {
        "session_id": session.session_id,
        "final_output": raw_result.get("final_outputs", {}),
        "steps": steps,
        "alerts": alerts,
        "errors": errors,
        "execution_time_ms": execution_time_ms,
    }

    # Store result in session
    session.current_result = result

    return result
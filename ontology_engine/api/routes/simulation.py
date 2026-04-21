# ontology_engine/api/routes/simulation.py
"""Simulation API endpoints for cross-rule-group execution."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from pydantic import BaseModel

from ontology_engine.services.simulation_session import SessionManager
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder
from ontology_engine.api.dto.responses import success_response, error_response

router = APIRouter(prefix="/v1/simulation", tags=["Simulation"])

# Global session manager and tree builder
_session_manager = SessionManager()
_tree_builder = RuleTreeBuilder()


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

        # Pre-fill inputs if provided
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
        return error_response(code="NOT_FOUND", message=f"Session {session_id} not found")

    return success_response(data={
        "session_id": session.session_id,
        "execution_tree": session.execution_tree,
        "current_inputs": session.current_inputs,
        "current_result": session.current_result,
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
        return error_response(code="NOT_FOUND", message=f"Session {session_id} not found")

    _session_manager.update_inputs(
        session_id,
        body.input_values,
        partial=not body.full_override,
    )

    # Check if all required inputs are filled
    missing = _get_missing_inputs(session)
    result = None
    if not missing:
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
        return error_response(code="NOT_FOUND", message=f"Session {session_id} not found")
    return success_response(data={"deleted": True})


def _extract_required_inputs(tree: dict) -> list:
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


def _get_missing_inputs(session) -> list:
    """Get list of missing required inputs.

    Args:
        session: SimulationSession instance

    Returns:
        List of required input names that are not yet provided
    """
    required = _extract_required_inputs(session.execution_tree)
    return [inp for inp in required if inp not in session.current_inputs]


async def _run_simulation(session):
    """Run simulation with current inputs.

    Args:
        session: SimulationSession with all required inputs filled

    Returns:
        Simulation result dictionary
    """
    # TODO: Integrate with DAGExecutor for actual rule execution
    return {"final_output": {}, "steps": [], "errors": []}
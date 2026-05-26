# ontology_engine/api/routes/semantic_spaces.py
"""Semantic Spaces API routes - management surface for semantic spaces."""
from __future__ import annotations

import warnings
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, AliasChoices, Field

from ontology_engine.api.dependencies import get_space_service
from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.services.types import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SpaceType,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    SemanticSpaceStorageError,
)

warnings.warn(
    "ontology_engine.api.routes.semantic_spaces is deprecated. "
    "Use ontology_engine.api.routes.spaces instead.",
    DeprecationWarning,
    stacklevel=2,
)

router = APIRouter(prefix="/v1/spaces", tags=["SemanticSpaces"])


# Request/Response Models
class CreateSpaceRequest(BaseModel):
    name: str = Field(description="Space name, must be unique (e.g., 'Supply Chain Finance')")
    description: str | None = Field(default=None, description="Space description")
    domain: str | None = Field(default=None, description="Business domain (e.g., 'finance', 'compliance')")


class UpdateSpaceMetadataRequest(BaseModel):
    name: str | None = Field(default=None, description="New space name")
    description: str | None = Field(default=None, description="New space description")
    domain: str | None = Field(default=None, description="New business domain")
    status: SpaceStatus | None = Field(default=None, description="New space status")


# ============================================================================
# Canonical Field Helpers (support both legacy and canonical names)
# ============================================================================

def _rule_inputs(rule: dict) -> list[dict]:
    """Get rule inputs, supporting both canonical and legacy field names."""
    return rule.get("inputs") or rule.get("input_elements") or []


def _rule_outputs(rule: dict) -> list[dict]:
    """Get rule outputs, supporting both canonical and legacy field names."""
    return rule.get("outputs") or rule.get("output_elements") or []


def _extract_applies_to_fact_objects(rule: dict) -> list[str]:
    """Extract fact_object names from applies_to, handling both formats.

    L4 format: applies_to: ["Supplier"]  (list[str])
    Phase 2 format: applies_to: {"fact_objects": ["Supplier"], "categories": {}}  (dict)
    """
    applies_to = rule.get("applies_to") or rule.get("target_objects") or []
    if isinstance(applies_to, dict):
        return applies_to.get("fact_objects") or []
    if isinstance(applies_to, list):
        if applies_to and isinstance(applies_to[0], str):
            return applies_to
        if applies_to and isinstance(applies_to[0], dict):
            return [item.get("id") or item.get("name", "") for item in applies_to if item.get("id") or item.get("name")]
    return []


class CreateRuleDefinitionRequest(BaseModel):
    """Request to create a rule definition.

    Canonical field names: applies_to, inputs/outputs.
    Accepts both canonical and legacy field names for backward compatibility.
    """
    id: str
    name: str | None = None
    description: str | None = None
    rule_type: str = "constraint"
    priority: int = 100
    applicable_scope: dict | None = None
    applies_to: list[str | dict] = Field(
        default_factory=list,
        description="Fact object types this rule applies to (e.g., ['Supplier']). Accepts strings or structured dicts.",
        validation_alias=AliasChoices("applies_to", "target_objects"),
    )
    inputs: list[dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("inputs", "input_elements"),
    )
    outputs: list[dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("outputs", "output_elements"),
    )
    enabled: bool = True
    logic_ids: list[str] | None = None
    # Backward compatibility fields
    when: dict | None = None
    then_action: dict | None = None
    else_action: dict | None = None


class CreateRuleLogicRequest(BaseModel):
    id: str
    name: str | None = None
    definition_id: str
    applicable_conditions: list[dict] | None = None
    when: dict | None = None
    then_action: dict | None = None
    else_action: dict | None = None
    version: int = 1
    environment: str = "default"


class CreateVersionRequest(BaseModel):
    description: str | None = None


class SchemaImpactAnalysisRequest(BaseModel):
    """Request for schema change impact analysis."""
    change_type: Literal["rule_definition", "rule_logic", "fact_object", "entity_type"] = Field(
        description="Type of change: rule_definition, rule_logic, fact_object, entity_type"
    )
    target: str = Field(description="ID or name of the target being changed")


class AddFactObjectRequest(BaseModel):
    id: str
    name: str
    description: str | None = None
    properties: list[dict] | None = None
    relations: list[dict] | None = None


class AddCategorizationRequest(BaseModel):
    id: str
    name: str
    type: str = "flat"
    description: str | None = None
    dimensions: list[dict] | None = None
    values: list[dict] | None = None


class AddAnalyticalElementRequest(BaseModel):
    id: str
    name: str
    type: str = Field(
        default="derived",
        validation_alias=AliasChoices("type", "element_type"),
    )
    description: str | None = None
    source: dict | None = None
    dependencies: list[str] | None = None
    overridable: bool = True


class AddRuleDefinitionRequest(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    rule_type: str = "constraint"
    priority: int = 100
    applies_to: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("applies_to", "target_objects"),
    )
    inputs: list[dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("inputs", "input_elements"),
    )
    outputs: list[dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("outputs", "output_elements"),
    )
    preconditions: list[dict] = Field(default_factory=list)
    enabled: bool = True
    logic_ids: list[str] | None = None


class AddRuleLogicRequest(BaseModel):
    id: str
    definition_id: str
    name: str | None = None
    description: str | None = None
    applicable_conditions: list[dict] | None = None
    when: dict | None = None
    then_action: dict | None = None
    else_action: dict | None = None
    priority: int = 100
    version: int = 1
    environment: str = "default"


class LoadFromYamlRequest(BaseModel):
    yaml_path: str
    overwrite: bool = False


class LoadInstancesFromYamlRequest(BaseModel):
    yaml_path: str
    overwrite: bool = False


class LoadSpaceFromJsonRequest(BaseModel):
    json_path: str
    space_id: str | None = None
    overwrite: bool = False


def _resolve_safe_path(path_str: str) -> Path | None:
    """Resolve a file path and validate no path traversal outside CWD or ~/.ontology_engine."""
    resolved = Path(path_str).resolve()
    cwd = Path.cwd().resolve()

    try:
        resolved.relative_to(cwd)
    except ValueError:
        data_dir = (Path.home() / ".ontology_engine").resolve()
        try:
            resolved.relative_to(data_dir)
        except ValueError:
            raise PermissionError(
                f"Access denied: {path_str} resolves to {resolved}, "
                f"which is outside allowed directories ({cwd}, {data_dir})"
            )

    if not resolved.exists():
        return None
    return resolved


class SpaceResponse(BaseModel):
    id: str
    name: str
    description: str | None
    domain: str | None
    status: str
    version: int
    created_at: str
    updated_at: str
    entity_count: int
    relation_count: int
    rule_definition_count: int
    rule_logic_count: int


def _space_to_response(space: SemanticSpace) -> SpaceResponse:
    """Convert SemanticSpace to response model."""
    return SpaceResponse(
        id=space.metadata.id,
        name=space.metadata.name,
        description=space.metadata.description,
        domain=space.metadata.domain,
        status=space.metadata.status.value,
        version=space.active_version,
        created_at=space.metadata.created_at.isoformat(),
        updated_at=space.metadata.updated_at.isoformat(),
        entity_count=len(space.instances.entities),
        relation_count=len(space.instances.relations),
        rule_definition_count=len(space.layers.L4_business_logic.rule_definitions),
        rule_logic_count=len(space.layers.L4_business_logic.rule_logics),
    )


def _compute_etag(space: SemanticSpace) -> str:
    """Compute ETag for a space, including metadata and content state."""
    import hashlib
    import json

    etag_source = json.dumps(
        {
            "active_version": space.active_version,
            "name": space.metadata.name,
            "description": space.metadata.description,
            "domain": space.metadata.domain,
            "status": space.metadata.status.value,
            "entity_count": len(space.instances.entities),
            "relation_count": len(space.instances.relations),
            "rule_def_count": len(space.layers.L4_business_logic.rule_definitions),
            "rule_logic_count": len(space.layers.L4_business_logic.rule_logics),
        },
        sort_keys=True,
    )
    return hashlib.sha256(etag_source.encode()).hexdigest()[:16]


def _topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    from collections import defaultdict, deque

    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        if src in in_degree and tgt in in_degree:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
    priority_map = {n["id"]: n.get("priority", 100) for n in nodes}
    sorted_queue = sorted(queue, key=lambda nid: -priority_map.get(nid, 100))
    queue = deque(sorted_queue)

    order: list[str] = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in sorted(adj[nid], key=lambda x: -priority_map.get(x, 100)):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    remaining = [n["id"] for n in nodes if n["id"] not in set(order)]
    return order + remaining


# ============================================================================
# Space CRUD
# ============================================================================

@router.post("/", response_model=dict, summary="Create semantic space", description="Create a new semantic space in DRAFT status. After creation, load schema via /schema/load-yaml and activate via /{space_id}/activate before running analysis.")
async def create_space(request: CreateSpaceRequest):
    """Create a new semantic space."""
    service = get_space_service()

    space_id = f"space_{uuid.uuid4().hex[:8]}"

    metadata = SpaceMetadata(
        id=space_id,
        name=request.name,
        description=request.description,
        domain=request.domain,
        status=SpaceStatus.DRAFT,
    )

    space = SemanticSpace(
        metadata=metadata,
        layers=SemanticSpaceLayers(
            L4_business_logic=L4BusinessLogic()
        ),
        instances=SpaceInstances(),
    )

    await service.save_space(space)

    return success_response(data=_space_to_response(space))


@router.get("/", response_model=dict, summary="List semantic spaces", description="List all semantic spaces with their IDs, names, statuses, and entity counts.")
async def list_spaces():
    """List all semantic spaces."""
    service = get_space_service()
    spaces = await service.list_metadata()

    # Load full space for counts
    responses = []
    for metadata in spaces:
        space = await service.get_space(metadata.id)
        if space:
            responses.append(_space_to_response(space))

    return success_response(data=responses)


@router.get("/{space_id}", response_model=dict, summary="Get semantic space", description="Get detailed information about a specific semantic space.")
async def get_space(space_id: str):
    """Get a semantic space by ID."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=_space_to_response(space))


@router.put("/{space_id}", response_model=dict, summary="Update space metadata", description="Update space name, description, domain, or status. Supports If-Match header for optimistic concurrency control.")
async def update_space_metadata(
    space_id: str,
    request: UpdateSpaceMetadataRequest,
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    """Update space metadata with optional ETag-based concurrency control."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    if if_match:
        current_etag = _compute_etag(space)

        if if_match != current_etag:
            return error_response(
                code="PRECONDITION_FAILED",
                message="ETag mismatch — the space has been modified by another client",
                suggestion="Re-fetch the space, merge changes, and retry with the new ETag",
                details={"current_etag": current_etag, "provided_etag": if_match},
            )

    if request.name is not None:
        space.metadata.name = request.name
    if request.description is not None:
        space.metadata.description = request.description
    if request.domain is not None:
        space.metadata.domain = request.domain
    if request.status is not None and request.status != space.metadata.status:
        return error_response(
            code="INVALID_TRANSITION",
            message="Status changes must go through state machine endpoints (activate/deactivate/archive)",
        )

    await service.save_space(space)

    return success_response(data=_space_to_response(space))


@router.delete("/{space_id}", response_model=dict, summary="Delete semantic space", description="Delete a semantic space and all its associated data. Supports ?dry_run=true to preview impact. Only DRAFT or ARCHIVED spaces can be deleted.")
async def delete_space(space_id: str, dry_run: bool = Query(default=False, description="If true, preview what would be deleted without actually deleting")):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    if space.metadata.status not in (SpaceStatus.DRAFT, SpaceStatus.ARCHIVED):
        return error_response(
            code="INVALID_TRANSITION",
            message=f"Cannot delete space in {space.metadata.status.value} status. Only DRAFT or ARCHIVED spaces can be deleted.",
        )

    if dry_run:
        entity_count = len(space.instances.entities)
        relation_count = len(space.instances.relations)
        rule_def_count = len(space.layers.L4_business_logic.rule_definitions)
        rule_logic_count = len(space.layers.L4_business_logic.rule_logics)
        return success_response(data={
            "dry_run": True,
            "would_delete": {
                "space_id": space_id,
                "space_name": space.metadata.name,
                "entities": entity_count,
                "relations": relation_count,
                "rule_definitions": rule_def_count,
                "rule_logics": rule_logic_count,
            },
        })

    deleted = await service.delete_space(space_id)

    if not deleted:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data={"deleted": True, "space_id": space_id})


# ============================================================================
# Rule Definitions CRUD
# ============================================================================

@router.get("/{space_id}/rules/definitions", response_model=dict, summary="List rule definitions", description="List all rule definitions (L4) in the space.")
async def list_rule_definitions(space_id: str):
    """List all rule definitions in a space."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=space.layers.L4_business_logic.rule_definitions)


@router.post("/{space_id}/rules/definitions", response_model=dict, summary="Create rule definition", description="Add a new rule definition to the space schema L4 layer.")
async def create_rule_definition(space_id: str, request: CreateRuleDefinitionRequest):
    """Create a new rule definition."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Check if ID already exists
    existing_ids = [rd["id"] for rd in space.layers.L4_business_logic.rule_definitions]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Rule definition {request.id} already exists")

    # Build rule definition
    definition = {
        "id": request.id,
        "name": request.name,
        "description": request.description,
        "rule_type": request.rule_type,
        "priority": request.priority,
        "applicable_scope": request.applicable_scope or {"scope_type": "global"},
        "applies_to": request.applies_to,
        "inputs": request.inputs,
        "outputs": request.outputs,
        "enabled": request.enabled,
        "logic_ids": request.logic_ids or [],
        # Backward compatibility
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
    }

    space.layers.L4_business_logic.rule_definitions.append(definition)
    await service.save_space(space)

    return success_response(data=definition)


@router.get("/{space_id}/rules/definitions/{rule_id}", response_model=dict, summary="Get rule definition", description="Get a specific rule definition by ID.")
async def get_rule_definition(space_id: str, rule_id: str):
    """Get a rule definition by ID."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    definition = next(
        (rd for rd in space.layers.L4_business_logic.rule_definitions if rd["id"] == rule_id),
        None,
    )

    if not definition:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    return success_response(data=definition)


@router.put("/{space_id}/rules/definitions/{rule_id}", response_model=dict, summary="Update rule definition", description="Update an existing rule definition. Supports ?dry_run=true to preview impact.")
async def update_rule_definition(space_id: str, rule_id: str, request: CreateRuleDefinitionRequest, dry_run: bool = Query(default=False, description="If true, preview what would change without actually updating")):
    """Update a rule definition."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    index = next(
        (i for i, rd in enumerate(space.layers.L4_business_logic.rule_definitions) if rd["id"] == rule_id),
        None,
    )

    if index is None:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    definition = {
        "id": rule_id,
        "name": request.name,
        "description": request.description,
        "rule_type": request.rule_type,
        "priority": request.priority,
        "applicable_scope": request.applicable_scope or {"scope_type": "global"},
        "applies_to": request.applies_to,
        "inputs": request.inputs,
        "outputs": request.outputs,
        "enabled": request.enabled,
        "logic_ids": request.logic_ids or [],
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
    }

    if dry_run:
        current = space.layers.L4_business_logic.rule_definitions[index]
        dependent_logics = [
            rl for rl in space.layers.L4_business_logic.rule_logics
            if rl.get("definition_id") == rule_id
        ]
        return success_response(data={
            "dry_run": True,
            "current_definition": current,
            "proposed_definition": definition,
            "dependent_rule_logics": len(dependent_logics),
            "dependent_logic_ids": [rl.get("id") for rl in dependent_logics],
        })

    space.layers.L4_business_logic.rule_definitions[index] = definition
    await service.save_space(space)

    return success_response(data=definition)


@router.delete("/{space_id}/rules/definitions/{rule_id}", response_model=dict, summary="Delete rule definition", description="Delete a rule definition. Supports ?dry_run=true to preview impact.")
async def delete_rule_definition(space_id: str, rule_id: str, dry_run: bool = Query(default=False, description="If true, preview what would be deleted without actually deleting")):
    """Delete a rule definition."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    rule_def = next(
        (rd for rd in space.layers.L4_business_logic.rule_definitions if rd["id"] == rule_id),
        None,
    )
    if not rule_def:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    dependent_logics = [
        rl for rl in space.layers.L4_business_logic.rule_logics
        if rl.get("definition_id") == rule_id
    ]

    if dry_run:
        return success_response(data={
            "dry_run": True,
            "would_delete": {
                "rule_definition": rule_def,
                "dependent_rule_logics": len(dependent_logics),
                "dependent_logic_ids": [rl.get("id") for rl in dependent_logics],
            },
        })

    space.layers.L4_business_logic.rule_definitions = [
        rd for rd in space.layers.L4_business_logic.rule_definitions if rd["id"] != rule_id
    ]
    space.layers.L4_business_logic.rule_logics = [
        rl for rl in space.layers.L4_business_logic.rule_logics
        if rl.get("definition_id") != rule_id
    ]

    await service.save_space(space)

    return success_response(data={"deleted": True, "rule_id": rule_id, "cascaded_logics": len(dependent_logics)})


# ============================================================================
# Rule Logics CRUD
# ============================================================================

@router.get("/{space_id}/rules/logics", response_model=dict, summary="List rule logics", description="List all rule logics (L4) in the space.")
async def list_rule_logics(space_id: str):
    """List all rule logics in a space."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=space.layers.L4_business_logic.rule_logics)


@router.post("/{space_id}/rules/logics", response_model=dict, summary="Create rule logic", description="Add a new rule logic to the space schema L4 layer.")
async def create_rule_logic(space_id: str, request: CreateRuleLogicRequest):
    """Create a new rule logic."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Check if ID already exists
    existing_ids = [rl["id"] for rl in space.layers.L4_business_logic.rule_logics]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Rule logic {request.id} already exists")

    # Verify definition exists
    def_ids = [rd["id"] for rd in space.layers.L4_business_logic.rule_definitions]
    if request.definition_id not in def_ids:
        return error_response(code="NOT_FOUND", message=f"Rule definition {request.definition_id} not found")

    logic = {
        "id": request.id,
        "name": request.name,
        "definition_id": request.definition_id,
        "applicable_conditions": request.applicable_conditions or [],
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
        "version": request.version,
        "environment": request.environment,
    }

    space.layers.L4_business_logic.rule_logics.append(logic)
    await service.save_space(space)

    return success_response(data=logic)


@router.get("/{space_id}/rules/logics/{logic_id}", response_model=dict, summary="Get rule logic", description="Get a specific rule logic by ID.")
async def get_rule_logic(space_id: str, logic_id: str):
    """Get a rule logic by ID."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    logic = next(
        (rl for rl in space.layers.L4_business_logic.rule_logics if rl["id"] == logic_id),
        None,
    )

    if not logic:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    return success_response(data=logic)


@router.put("/{space_id}/rules/logics/{logic_id}", response_model=dict, summary="Update rule logic", description="Update an existing rule logic.")
async def update_rule_logic(space_id: str, logic_id: str, request: CreateRuleLogicRequest):
    """Update a rule logic."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    index = next(
        (i for i, rl in enumerate(space.layers.L4_business_logic.rule_logics) if rl["id"] == logic_id),
        None,
    )

    if index is None:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    logic = {
        "id": logic_id,
        "name": request.name,
        "definition_id": request.definition_id,
        "applicable_conditions": request.applicable_conditions or [],
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
        "version": request.version,
        "environment": request.environment,
    }

    space.layers.L4_business_logic.rule_logics[index] = logic
    await service.save_space(space)

    return success_response(data=logic)


@router.delete("/{space_id}/rules/logics/{logic_id}", response_model=dict, summary="Delete rule logic", description="Delete a rule logic.")
async def delete_rule_logic(space_id: str, logic_id: str):
    """Delete a rule logic."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    original_count = len(space.layers.L4_business_logic.rule_logics)
    space.layers.L4_business_logic.rule_logics = [
        rl for rl in space.layers.L4_business_logic.rule_logics if rl["id"] != logic_id
    ]

    if len(space.layers.L4_business_logic.rule_logics) == original_count:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    await service.save_space(space)

    return success_response(data={"deleted": True})


# ============================================================================
# Version Management
# ============================================================================

@router.get("/{space_id}/versions", response_model=dict, summary="List versions", description="List all version snapshots for the space.")
async def list_versions(space_id: str):
    """List all versions of a space."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    versions = [
        {
            "version": v.version,
            "space_id": v.space_id,
            "snapshot_path": v.snapshot_path,
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "change_description": v.change_description,
            "is_stable": v.is_stable,
        }
        for v in space.versions
    ]

    return success_response(data=versions)


@router.post("/{space_id}/versions", response_model=dict, summary="Create version snapshot", description="Create a new version snapshot of the space.")
async def create_version(space_id: str, request: CreateVersionRequest):
    """Create a new version snapshot."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    try:
        version = await service.create_snapshot_with_space(
            space,
            description=request.description,
        )

        return success_response(data={
            "version": version.version,
            "space_id": version.space_id,
            "snapshot_path": version.snapshot_path,
            "created_at": version.created_at.isoformat(),
            "created_by": version.created_by,
            "change_description": version.change_description,
            "is_stable": version.is_stable,
        })
    except Exception as e:
        return error_response(code="SNAPSHOT_ERROR", message=str(e))


@router.post("/{space_id}/versions/{version}/rollback", response_model=dict, summary="Rollback to version", description="Rollback the space to a specific version. Supports ?dry_run=true to preview changes.")
async def rollback_to_version(space_id: str, version: int, dry_run: bool = Query(default=False, description="If true, preview rollback diff without actually rolling back")):
    """Rollback to a previous version."""
    service = get_space_service()

    try:
        current = await service.get_space(space_id)
        if not current:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

        if dry_run:
            target = await service.load_version(space_id, version, space=current)
            if not target:
                return error_response(code="NOT_FOUND", message=f"Version {version} not found for space {space_id}", suggestion=f"Use GET /v1/spaces/{space_id}/versions to list available versions")
            return success_response(data={
                "dry_run": True,
                "current_version": current.active_version,
                "target_version": version,
                "current_entity_count": len(current.instances.entities),
                "target_entity_count": len(target.instances.entities),
                "current_rule_def_count": len(current.layers.L4_business_logic.rule_definitions),
                "target_rule_def_count": len(target.layers.L4_business_logic.rule_definitions),
            })

        restored = await service.rollback_to_version(space_id, version, space=current)

        if not restored:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

        return success_response(data=_space_to_response(restored))
    except SemanticSpaceStorageError as e:
        return error_response(code="ROLLBACK_ERROR", message=str(e))


# ============================================================================
# Metric Card Version Management
# ============================================================================

@router.get("/{space_id}/metrics/{metric_id}/versions", response_model=dict, summary="List metric card versions", description="List all versions of a specific metric card.")
async def list_metric_versions(space_id: str, metric_id: str):
    """List all versions of a metric card."""
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    versions = await service.list_entity_versions(f"metric.{metric_id}")
    return success_response(data={
        "space_id": space_id,
        "metric_id": metric_id,
        "versions": versions,
    })


@router.get("/{space_id}/metrics/{metric_id}/versions/{version}", response_model=dict, summary="Get metric card version", description="Get a specific version of a metric card.")
async def get_metric_version(space_id: str, metric_id: str, version: int):
    """Get a specific version of a metric card."""
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    ver_data = await service.get_entity_version(f"metric.{metric_id}", version)
    if not ver_data:
        return error_response(code="NOT_FOUND", message=f"Version {version} not found for metric {metric_id}")

    return success_response(data={
        "space_id": space_id,
        "metric_id": metric_id,
        **ver_data,
    })


@router.post("/{space_id}/metrics/{metric_id}/versions", response_model=dict, summary="Create metric card version", description="Create a new version of a metric card with updated formula or thresholds.")
async def create_metric_version(
    space_id: str,
    metric_id: str,
    body: dict,
):
    """Create a new version of a metric card."""
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_versions = await service.list_entity_versions(f"metric.{metric_id}")
    next_version = max((v["version"] for v in existing_versions), default=0) + 1

    formula = body.get("formula")
    thresholds = body.get("thresholds")
    change_reason = body.get("change_reason", "")
    updated_by = body.get("updated_by", "api")

    version_data = {
        "metric_id": metric_id,
        "formula": formula,
        "thresholds": thresholds,
        "change_reason": change_reason,
    }

    await service.save_entity_version(
        f"metric.{metric_id}",
        "MetricCard",
        next_version,
        version_data,
        updated_by=updated_by,
    )

    return success_response(data={
        "space_id": space_id,
        "metric_id": metric_id,
        "version": next_version,
        **version_data,
    })


@router.get("/{space_id}/metrics/{metric_id}/diff", response_model=dict, summary="Diff metric card versions", description="Compare two versions of a metric card.")
async def diff_metric_versions(
    space_id: str,
    metric_id: str,
    from_version: int = Query(..., description="Source version"),
    to_version: int = Query(..., description="Target version"),
):
    """Compare two versions of a metric card."""
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    from_data = await service.get_entity_version(f"metric.{metric_id}", from_version)
    to_data = await service.get_entity_version(f"metric.{metric_id}", to_version)

    if not from_data:
        return error_response(code="NOT_FOUND", message=f"Version {from_version} not found for metric {metric_id}")
    if not to_data:
        return error_response(code="NOT_FOUND", message=f"Version {to_version} not found for metric {metric_id}")

    from_formula = from_data.get("data", {}).get("formula", "")
    to_formula = to_data.get("data", {}).get("formula", "")
    from_thresholds = from_data.get("data", {}).get("thresholds", {})
    to_thresholds = to_data.get("data", {}).get("thresholds", {})

    diff = {
        "metric_id": metric_id,
        "from_version": from_version,
        "to_version": to_version,
        "formula_changed": from_formula != to_formula,
        "formula_diff": {
            "from": from_formula,
            "to": to_formula,
        } if from_formula != to_formula else None,
        "thresholds_changed": from_thresholds != to_thresholds,
        "thresholds_diff": {
            "from": from_thresholds,
            "to": to_thresholds,
        } if from_thresholds != to_thresholds else None,
        "change_reason": to_data.get("data", {}).get("change_reason", ""),
    }

    return success_response(data=diff)

@router.get("/{space_id}/instances/entities", response_model=dict, summary="List entities", description="List all entities in the space.")
async def list_entities(
    space_id: str,
    concept: str | None = Query(default=None, description="Filter by concept"),
):
    """List entities in a space."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    entities = space.instances.entities
    if concept:
        entities = [e for e in entities if e.get("_fact_object") == concept or e.get("_concept") == concept]

    return success_response(data=entities)


@router.post("/{space_id}/instances/entities", response_model=dict, summary="Create entity", description="Add a new entity to the space.")
async def create_entity(space_id: str, entity: dict):
    """Create a new entity."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Check required fields
    if "entity_id" not in entity or ("_concept" not in entity and "_fact_object" not in entity):
        return error_response(code="VALIDATION_ERROR", message="entity_id and _fact_object (or _concept) are required")

    space.instances.entities.append(entity)
    await service.save_space(space)

    return success_response(data=entity)


@router.get("/{space_id}/instances/relations", response_model=dict, summary="List relations", description="List all relations in the space.")
async def list_relations(space_id: str):
    """List relations in a space."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=space.instances.relations)


@router.post("/{space_id}/instances/relations", response_model=dict, summary="Create relation", description="Add a new relation to the space.")
async def create_relation(space_id: str, relation: dict):
    """Create a new relation."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Check required fields
    if "relation_name" not in relation or "from_entity_id" not in relation or "to_entity_id" not in relation:
        if "relation_type" in relation and "relation_name" not in relation:
            relation["relation_name"] = relation.pop("relation_type")
        else:
            return error_response(code="VALIDATION_ERROR", message="relation_name (or relation_type), from_entity_id, and to_entity_id are required")

    space.instances.relations.append(relation)
    await service.save_space(space)

    return success_response(data=relation)


@router.patch("/{space_id}/instances/relations/{relation_id}", response_model=dict, summary="Update relation", description="Update a relation's attributes in the space.")
async def update_relation(space_id: str, relation_id: str, request: dict[str, Any]):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    attributes = request.get("attributes", {})
    reason = request.get("reason", "")
    result = await service.update_relation_in_space(space_id, relation_id, attributes, reason=reason)

    if not result:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")
    if result.get("not_found"):
        return error_response(code="NOT_FOUND", message=f"Relation {relation_id} not found in space {space_id}")

    return success_response(data=result)


# ============================================================================
# Execution Endpoints (Consumption Surface)
# ============================================================================


class ExecuteAnalyzeRequest(BaseModel):
    """Request for analyze endpoint."""
    entity_id: str
    dimension: str = "default"
    include_trace: bool = True


class ExecuteSimulateRequest(BaseModel):
    """Request for simulate endpoint."""
    entity_id: str
    dimension: str = "default"
    overrides: dict[str, Any] | None = None
    include_trace: bool = True


@router.get("/{space_id}/execute/schema-graph", response_model=dict, summary="Get schema graph", description="Get the schema dependency graph for the space.")
async def get_schema_graph(
    space_id: str,
    graph_type: str = Query(default="entity_relation", description="Graph type: entity_relation, metric_dependency, full, rule_overview"),
    layer_filter: str | None = Query(default=None, description="Comma-separated layers: L1,L2,L3,L4"),
):
    """Get schema visualization graph data for a semantic space."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Build graph nodes and edges from semantic space layers
    nodes = []
    edges = []

    # L1: Fact Objects (Entity types)
    for entity in space.layers.L1_fact_objects:
        entity_id = entity.get("id", entity.get("name", "unknown"))
        nodes.append({
            "id": entity_id,
            "type": "entity",
            "data": {
                "label": entity.get("display_name") or entity.get("name", entity_id),
                "category": "entity",
                "properties": entity.get("properties", {}),
            }
        })
        # Add relation edges
        for rel in entity.get("relations", []):
            rel_id = f"{entity_id}__{rel.get('target')}__{rel.get('name')}"
            edges.append({
                "id": rel_id,
                "source": entity_id,
                "target": rel.get("target", ""),
                "type": "relation",
                "data": {
                    "label": rel.get("display_name") or rel.get("name", ""),
                    "relation_name": rel.get("relation_name", "") or rel.get("relation_type", ""),
                }
            })

    # L2: Categorizations
    for cat in space.layers.L2_categorizations:
        cat_id = cat.get("id", cat.get("name", "unknown"))
        nodes.append({
            "id": cat_id,
            "type": "category",
            "data": {
                "label": cat.get("display_name") or cat.get("name", cat_id),
                "category": "categorization",
                "values": cat.get("values", []),
            }
        })

    # L3: Analytical Elements (Metrics)
    for element in space.layers.L3_analytical_elements:
        elem_id = element.get("id", element.get("name", "unknown"))
        nodes.append({
            "id": elem_id,
            "type": "metric",
            "data": {
                "label": element.get("display_name") or element.get("name", elem_id),
                "category": "element",
                "type": element.get("type") or element.get("element_type") or "metric",
                "formula": element.get("formula"),
            }
        })
        # Add dependency edges
        for dep in element.get("dependencies", []):
            dep_id = f"{dep}__{elem_id}"
            edges.append({
                "id": dep_id,
                "source": dep,
                "target": elem_id,
                "type": "metric_dep",
                "data": {}
            })

    # L4: Business Logic (Rules)
    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule.get("id", "unknown")
        nodes.append({
            "id": rule_id,
            "type": "rule",
            "data": {
                "label": rule.get("name", rule_id),
                "category": "rule_definition",
                "rule_type": rule.get("rule_type", "constraint"),
                "applies_to": rule.get("applies_to") or rule.get("target_objects") or [],
                "inputs": _rule_inputs(rule),
                "outputs": _rule_outputs(rule),
            }
        })

    # Add rule → output element edges
    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule.get("id", "unknown")
        for output in _rule_outputs(rule):
            output_name = output.get("name", output) if isinstance(output, dict) else output
            edge_id = f"{rule_id}__{output_name}"
            edges.append({
                "id": edge_id,
                "source": rule_id,
                "target": output_name,
                "type": "rule_output",
                "data": {}
            })

    # Parse layer filter
    layers = None
    if layer_filter:
        layers = [layer.strip() for layer in layer_filter.split(",")]

    # Filter nodes by layer if specified
    if layers:
        layer_type_map = {
            "L1": "entity",
            "L2": "category",
            "L3": "metric",
            "L4": "rule",
        }
        allowed_types = {layer_type_map[layer] for layer in layers if layer in layer_type_map}
        nodes = [n for n in nodes if n["type"] in allowed_types]

    # Build response
    graph_data = {
        "schema_id": space_id,
        "graph_type": graph_type,
        "nodes": nodes,
        "edges": edges,
        "layout_config": {
            "type": "dagre",
            "rankdir": "LR",
            "nodesep": 50,
            "ranksep": 80,
        },
        "metadata": {
            "entity_count": len([n for n in nodes if n["type"] == "entity"]),
            "relation_count": len([e for e in edges if e["type"] == "relation"]),
            "metric_count": len([n for n in nodes if n["type"] == "metric"]),
            "rule_count": len([n for n in nodes if n["type"] == "rule"]),
        }
    }

    return success_response(data=graph_data)


@router.get("/{space_id}/execute/rule-chain/{dimension}", response_model=dict, summary="Get rule chain", description="Get the rule execution chain for a specific analysis dimension.")
async def get_rule_chain_graph(space_id: str, dimension: str):
    """Get rule chain visualization DAG for a specific dimension."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Build rule chain DAG from rule definitions and logics
    nodes = []
    edges = []

    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule["id"]
        associated_logics = [
            logic for logic in space.layers.L4_business_logic.rule_logics
            if logic.get("definition_id") == rule_id
        ]

        nodes.append({
            "id": rule_id,
            "data": {
                "label": rule.get("name", rule_id),
                "rule_type": rule.get("rule_type", "constraint"),
                "priority": rule.get("priority", 100),
                "applicable_scope": rule.get("applicable_scope", {}),
                "logic_count": len(associated_logics),
                "logic_ids": [logic["id"] for logic in associated_logics],
            }
        })

        # Create edges: rule → logic if logic has condition details
        for logic in associated_logics:
            logic_id = logic["id"]
            when = logic.get("when", {})
            if when.get("expression") or when.get("allOf") or when.get("anyOf"):
                edges.append({
                    "id": f"{rule_id}__{logic_id}",
                    "source": rule_id,
                    "target": logic_id,
                    "data": {"type": "rule_to_logic"}
                })

    # Create nodes for logics
    for logic in space.layers.L4_business_logic.rule_logics:
        logic_id = logic["id"]
        when = logic.get("when", {})
        then_action = logic.get("then_action", {})

        nodes.append({
            "id": logic_id,
            "data": {
                "label": logic.get("name", logic_id),
                "type": "logic",
                "condition_expression": when.get("expression", "") if when else "",
                "action_type": then_action.get("action_type", "") if then_action else "",
                "applicable_conditions": logic.get("applicable_conditions", []),
            }
        })

    # Rule execution order based on priority (simple linear chain for now)
    sorted_rules = sorted(
        space.layers.L4_business_logic.rule_definitions,
        key=lambda r: r.get("priority", 100)
    )
    for i in range(len(sorted_rules) - 1):
        current_rule = sorted_rules[i]
        next_rule = sorted_rules[i + 1]
        edges.append({
            "id": f"{current_rule['id']}__{next_rule['id']}",
            "source": current_rule["id"],
            "target": next_rule["id"],
            "data": {"type": "execution_flow", "label": "执行"}
        })

    return success_response(data={
        "dimension": dimension,
        "nodes": nodes,
        "edges": edges,
        "dimension_info": {
            "name": dimension,
            "description": f"规则链图 - {dimension}",
            "applicable_entities": [],
            "rule_count": len(nodes),
        }
    })


@router.post("/{space_id}/execute/analyze", response_model=dict, summary="Execute analysis", description="Execute rule analysis on an entity. Runs L2 categorization, L3 metric computation, and L4 rule execution.")
async def execute_analyze(space_id: str, request: ExecuteAnalyzeRequest):
    """Execute rules on an entity and return analysis results."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Find the entity
    entity = None
    for e in space.instances.entities:
        if e.get("entity_id") == request.entity_id:
            entity = e
            break

    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")

    # Execute rules
    steps = []
    final_outputs = {}
    entity_data = dict(entity)
    entity_data["_fact_object"] = entity.get("_fact_object") or entity.get("_concept", "Unknown")

    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule["id"]
        rule_name = rule.get("name", rule_id)
        rule_type = rule.get("rule_type", "constraint")

        # Check if rule is enabled
        if not rule.get("enabled", True):
            steps.append({
                "step": len(steps) + 1,
                "rule_id": rule_id,
                "rule_name": rule_name,
                "rule_type": rule_type,
                "status": "skipped",
                "explanation": "规则已禁用",
            })
            continue

        # Get applicable scope
        scope = rule.get("applicable_scope", {})
        scope_type = scope.get("scope_type", "global")

        # Check scope applicability (simplified)
        if scope_type == "by_classification":
            # Check if entity matches the classification
            classification_path = scope.get("classification_path", "")
            classification_values = scope.get("classification_values", [])
            entity_class = entity_data.get(classification_path, "")
            if classification_values and entity_class not in classification_values:
                steps.append({
                    "step": len(steps) + 1,
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "rule_type": rule_type,
                    "status": "skipped",
                    "explanation": f"实体分类 '{entity_class}' 不在适用范围内",
                })
                continue

        # Get rule logic
        logic_ids = rule.get("logic_ids", [])
        when_expr = rule.get("when", {}).get("expression") if rule.get("when") else None
        then_action = rule.get("then_action")

        # Try to find matching logic
        for logic_id in logic_ids:
            for logic in space.layers.L4_business_logic.rule_logics:
                if logic["id"] == logic_id:
                    when_expr = logic.get("when", {}).get("expression") if logic.get("when") else None
                    then_action = logic.get("then_action")
                    break

        # Evaluate condition (simplified - just check if expression exists)
        condition_result = False
        if when_expr:
            # Simple evaluation - in real implementation, this would use the expression engine
            try:
                # Mock evaluation for demonstration
                condition_result = True
                explanation = f"条件表达式: {when_expr}"
            except Exception as e:
                condition_result = False
                explanation = f"条件评估错误: {str(e)}"
        else:
            condition_result = True
            explanation = "无触发条件，规则直接执行"

        # Execute action
        context_before = dict(entity_data)
        if condition_result and then_action:
            action_type = then_action.get("action_type", "")
            if action_type == "set_flag":
                output_name = then_action.get("output", {}).get("eligible") or then_action.get("output_name", "result")
                entity_data[output_name] = then_action.get("output", {}).get("value", True)
                final_outputs[output_name] = entity_data[output_name]
            elif action_type == "compute":
                formula = then_action.get("formula")
                if formula:
                    # Mock computation
                    final_outputs[rule_id] = {"formula": formula, "result": True}
            explanation = f"执行动作: {action_type}"
        elif condition_result:
            explanation = "规则执行完成"
        else:
            explanation = "条件不满足，规则跳过"

        steps.append({
            "step": len(steps) + 1,
            "rule_id": rule_id,
            "rule_name": rule_name,
            "rule_type": rule_type,
            "condition_expression": when_expr or "",
            "condition_result": condition_result,
            "context_before": context_before if request.include_trace else {},
            "context_after": entity_data if request.include_trace else {},
            "inputs": _rule_inputs(rule),
            "outputs": _rule_outputs(rule),
            "status": "passed" if condition_result else "skipped",
            "duration_ms": 0.0,
            "explanation": explanation,
            "affected_metrics": [],
        })

    return success_response(data={
        "entity_id": request.entity_id,
        "dimension": request.dimension,
        "steps": steps,
        "execution_path": [s["rule_id"] for s in steps if s["status"] == "passed"],
        "skipped_rules": [s["rule_id"] for s in steps if s["status"] == "skipped"],
        "final_outputs": final_outputs,
    })


# ============================================================================
# Instance Graph Visualization Endpoints
# ============================================================================


class InstanceGraphRequest(BaseModel):
    """Request for instance graph endpoint."""
    seed_entity_id: str | None = Query(default=None, description="Seed entity ID for hop-based layout")
    max_hops: int = Query(default=3, description="Maximum hop depth from seed")
    concept_filter: str | None = Query(default=None, description="Comma-separated concept types to include")
    group_by: str | None = Query(default="concept", description="Grouping: concept, component, hops, result")


@router.get("/{space_id}/instances/graph", response_model=dict, summary="Get instance graph", description="Get the instance-level graph data (entities + relations) for visualization. Supports seed-based hop expansion, concept filtering, and grouping modes.")
async def get_instance_graph(
    space_id: str,
    seed_entity_id: str | None = Query(default=None, description="Seed entity ID for hop-based layout"),
    max_hops: int = Query(default=3, description="Maximum hop depth from seed"),
    concept_filter: str | None = Query(default=None, description="Comma-separated concept types to include"),
    group_by: str | None = Query(default="concept", description="Grouping mode: concept, component, hops, result"),
):
    """Get instance-level graph data for visualization."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    entities = space.instances.entities
    relations = list(space.instances.relations)

    guarantee_entities = [e for e in entities if e.get("_fact_object") == "GuaranteeRelation"]
    existing_guarantee_keys = set()
    for rel in relations:
        if rel.get("relation_name") == "guarantees" or rel.get("relation_type") == "guarantees":
            key = (rel.get("from_entity_id"), rel.get("to_entity_id"))
            existing_guarantee_keys.add(key)

    for ge in guarantee_entities:
        guarantor = ge.get("guarantor_id") or ge.get("guarantor")
        guarantee_target = ge.get("guaranteed_id") or ge.get("target_id") or ge.get("guarantee_target")
        if guarantor and guarantee_target and (guarantor, guarantee_target) not in existing_guarantee_keys:
            amt = ge.get("guaranteed_amount")
            if isinstance(amt, dict):
                amt_display = f"{amt.get('value', '')} {amt.get('currency', '')}"
            else:
                amt_display = amt
            relations.append({
                "from_entity_id": guarantor,
                "to_entity_id": guarantee_target,
                "relation_name": "guarantees",
                "relation_type": "guarantees",
                "amount": amt_display,
                "type": ge.get("guarantee_type"),
                "status": ge.get("status"),
                "guarantee_id": ge.get("entity_id"),
            })

    concept_filters = [c.strip() for c in concept_filter.split(",")] if concept_filter else None

    if concept_filters:
        entities = [e for e in entities if e.get("_fact_object") or e.get("_concept") in concept_filters]
        entity_ids = {e.get("entity_id") for e in entities}
        relations = [r for r in relations if r.get("from_entity_id") in entity_ids and r.get("to_entity_id") in entity_ids]

    entity_map = {e.get("entity_id"): e for e in entities}

    if seed_entity_id and seed_entity_id in entity_map:
        reachable_ids = _compute_hop_reachability(seed_entity_id, relations, max_hops)
        if concept_filters:
            reachable_ids &= entity_ids
        entities = [entity_map[eid] for eid in reachable_ids if eid in entity_map]
        reachable_ids_final = {e.get("entity_id") for e in entities}
        relations = [r for r in relations if r.get("from_entity_id") in reachable_ids_final and r.get("to_entity_id") in reachable_ids_final]
    elif concept_filters:
        pass
    else:
        pass

    hop_layers = {}
    if seed_entity_id and seed_entity_id in entity_map:
        hop_layers = _compute_hop_layers(seed_entity_id, relations, max_hops)
        if concept_filters:
            entity_ids_set = {e.get("entity_id") for e in entities}
            hop_layers = {k: (v & entity_ids_set) for k, v in hop_layers.items()}

    node_id_to_hop = {}
    for hop, ids in hop_layers.items():
        for eid in ids:
            node_id_to_hop[eid] = hop

    CONCEPT_COLORS = {
        "Supplier": "#1890ff",
        "CoreEnterprise": "#52c41a",
        "Invoice": "#faad14",
        "Contract": "#722ed1",
        "GuaranteeRelation": "#ff4d4f",
        "Borrower": "#13c2c2",
        "LoanApplication": "#eb2f96",
        "RepaymentRecord": "#8c8c8c",
    }

    RELATION_STYLES = {
        "supplies_to": {"stroke": "#1890ff", "label": "供应"},
        "has_invoice": {"stroke": "#faad14", "label": "发票"},
        "has_contract": {"stroke": "#722ed1", "label": "合同"},
        "guarantees": {"stroke": "#ff4d4f", "label": "担保"},
        "issued_to": {"stroke": "#52c41a", "label": "开具给"},
        "co_borrows_with": {"stroke": "#13c2c2", "label": "共借"},
        "has_applications": {"stroke": "#eb2f96", "label": "申请"},
        "has_repayments": {"stroke": "#8c8c8c", "label": "还款"},
    }

    components = _find_connected_components(entities, relations)

    entity_analysis = {}
    for entity in entities:
        eid = entity.get("entity_id", "")
        fact_obj = entity.get("_fact_object") or entity.get("_concept", "Unknown")
        properties = {k: v for k, v in entity.items() if k not in ("entity_id", "_fact_object", "_concept", "layer", "valid_from", "valid_to")}
        name = properties.get("name") or properties.get("company_name") or properties.get("borrower_name") or eid
        credit_score = properties.get("credit_score") or properties.get("score")
        status = properties.get("status") or properties.get("credit_decision") or properties.get("decision")

        result_group = "unknown"
        if status:
            status_upper = str(status).upper()
            if any(kw in status_upper for kw in ("APPROVE", "PASS", "ACCEPT", "ELIGIB", "GREEN")):
                result_group = "approved"
            elif any(kw in status_upper for kw in ("REJECT", "FAIL", "DENY", "RED", "INELIGIB")):
                result_group = "rejected"
            elif any(kw in status_upper for kw in ("PENDING", "REVIEW", "CONDITIONAL")):
                result_group = "pending"

        component_id = -1
        for ci, comp_entities in enumerate(components):
            if eid in comp_entities:
                component_id = ci
                break

        node_hop = node_id_to_hop.get(eid, 0) if seed_entity_id else 0

        entity_analysis[eid] = {
            "name": name,
            "fact_object": fact_obj,
            "color": CONCEPT_COLORS.get(fact_obj, "#999"),
            "credit_score": credit_score,
            "status": status,
            "result_group": result_group,
            "component_id": component_id,
            "hop": node_hop,
            "properties": properties,
        }

    nodes = []
    for entity in entities:
        eid = entity.get("entity_id", "")
        analysis = entity_analysis.get(eid, {})
        fact_obj = analysis.get("fact_object", "Unknown")
        name = analysis.get("name", eid)
        credit_score = analysis.get("credit_score")

        size = 40
        if credit_score is not None:
            try:
                score_val = float(credit_score)
                size = 20 + int((score_val / 100.0) * 40)
            except (ValueError, TypeError):
                pass

        node = {
            "id": eid,
            "type": "entity_instance",
            "data": {
                "label": name,
                "concept": fact_obj,
                "entity_id": eid,
                "credit_score": credit_score,
                "status": analysis.get("status"),
                "result_group": analysis.get("result_group"),
                "component_id": analysis.get("component_id"),
                "hop": analysis.get("hop", 0),
                "properties": analysis.get("properties", {}),
            },
            "style": {
                "fill": analysis.get("color", "#999"),
                "size": size,
            }
        }
        nodes.append(node)

    edges = []
    for rel in relations:
        from_id = rel.get("from_entity_id", "")
        to_id = rel.get("to_entity_id", "")
        rel_type = rel.get("relation_name") or rel.get("relation_type", "unknown")
        rel_props = {k: v for k, v in rel.items() if k not in ("from_entity_id", "to_entity_id", "relation_name", "relation_type")}

        style = RELATION_STYLES.get(rel_type, {"stroke": "#d9d9d9", "label": rel_type})
        edge_label = style.get("label", rel_type)
        if rel_props.get("amount"):
            edge_label = f"{edge_label}\n{rel_props['amount']}"

        is_guarantee = rel_type in ("guarantees", "guarantee", "GuaranteeRelation")
        is_cycle_edge = False
        if is_guarantee:
            cycle_paths = _detect_cycle_edges(from_id, to_id, relations)
            is_cycle_edge = len(cycle_paths) > 0

        edge = {
            "id": f"{from_id}__{to_id}__{rel_type}",
            "source": from_id,
            "target": to_id,
            "type": rel_type,
            "data": {
                "label": edge_label,
                "relation_type": rel_type,
                "is_guarantee": is_guarantee,
                "is_cycle_edge": is_cycle_edge,
                "properties": rel_props,
            },
            "style": {
                "stroke": style.get("stroke", "#d9d9d9"),
                "line_width": 3 if is_cycle_edge else 1.5,
            }
        }
        edges.append(edge)

    node_count = len(nodes)
    edge_count = len(edges)
    cycle_count = len([e for e in edges if e.get("data", {}).get("is_cycle_edge")])
    concept_counts = {}
    for node in nodes:
        concept = node.get("data", {}).get("concept", "Unknown")
        concept_counts[concept] = concept_counts.get(concept, 0) + 1

    return success_response(data={
        "space_id": space_id,
        "graph_type": "instance_graph",
        "nodes": nodes,
        "edges": edges,
        "grouping": {
            "concept_groups": _build_concept_groups(nodes),
            "component_groups": _build_component_groups(nodes, components),
            "hop_groups": hop_layers if hop_layers else {},
            "result_groups": _build_result_groups(nodes),
        },
        "layout_config": {
            "type": "hybrid",
            "primary": "dagre",
            "secondary": "force",
            "seed_entity_id": seed_entity_id,
        },
        "metadata": {
            "entity_count": node_count,
            "relation_count": edge_count,
            "cycle_count": cycle_count,
            "concept_counts": concept_counts,
            "component_count": len(components),
        }
    })


def _compute_hop_reachability(seed_id: str, relations: list[dict], max_hops: int) -> set[str]:
    """BFS from seed entity to find all reachable entities within max_hops."""
    from collections import deque

    adj: dict[str, list[str]] = {}
    for rel in relations:
        from_id = rel.get("from_entity_id", "")
        to_id = rel.get("to_entity_id", "")
        adj.setdefault(from_id, []).append(to_id)
        adj.setdefault(to_id, []).append(from_id)

    visited = {seed_id}
    queue = deque([(seed_id, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return visited


def _compute_hop_layers(seed_id: str, relations: list[dict], max_hops: int) -> dict[int, set[str]]:
    """BFS from seed entity to compute hop layer assignments."""
    from collections import deque

    adj: dict[str, list[str]] = {}
    for rel in relations:
        from_id = rel.get("from_entity_id", "")
        to_id = rel.get("to_entity_id", "")
        adj.setdefault(from_id, []).append(to_id)
        adj.setdefault(to_id, []).append(from_id)

    layers: dict[int, set[str]] = {0: {seed_id}}
    visited = {seed_id}
    queue = deque([(seed_id, 0)])

    while queue:
        current, depth = queue.popleft()
        if depth >= max_hops:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                layers.setdefault(depth + 1, set()).add(neighbor)
                queue.append((neighbor, depth + 1))

    return layers


def _find_connected_components(entities: list[dict], relations: list[dict]) -> list[set[str]]:
    """Find connected components in the graph."""
    entity_ids = {e.get("entity_id") for e in entities}
    adj: dict[str, set[str]] = {eid: set() for eid in entity_ids}

    for rel in relations:
        from_id = rel.get("from_entity_id", "")
        to_id = rel.get("to_entity_id", "")
        if from_id in adj and to_id in adj:
            adj[from_id].add(to_id)
            adj[to_id].add(from_id)

    visited = set()
    components = []

    for eid in entity_ids:
        if eid not in visited:
            component = set()
            stack = [eid]
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    component.add(node)
                    for neighbor in adj.get(node, []):
                        if neighbor not in visited:
                            stack.append(neighbor)
            components.append(component)

    return components


def _detect_cycle_edges(from_id: str, to_id: str, relations: list[dict]) -> list[list[str]]:
    """Detect if there's a cycle path from from_id to to_id via guarantee relations."""
    adj: dict[str, list[str]] = {}
    for rel in relations:
        rel_type = rel.get("relation_name") or rel.get("relation_type", "")
        if rel_type in ("guarantees", "guarantee"):
            f = rel.get("from_entity_id", "")
            t = rel.get("to_entity_id", "")
            adj.setdefault(f, []).append(t)

    paths = []
    visited = {from_id}

    def dfs(current: str, path: list[str]):
        if current == to_id and len(path) > 1:
            paths.append(list(path))
            return
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                path.append(neighbor)
                dfs(neighbor, path)
                path.pop()
                visited.remove(neighbor)

    dfs(from_id, [from_id])
    return paths


def _build_concept_groups(nodes: list[dict]) -> dict[str, list[str]]:
    """Group node IDs by concept type."""
    groups: dict[str, list[str]] = {}
    for node in nodes:
        concept = node.get("data", {}).get("concept", "Unknown")
        groups.setdefault(concept, []).append(node["id"])
    return groups


def _build_component_groups(nodes: list[dict], components: list[set[str]]) -> list[list[str]]:
    """Group node IDs by connected component."""
    return [list(comp) for comp in components]


def _build_result_groups(nodes: list[dict]) -> dict[str, list[str]]:
    """Group node IDs by business result (approved/rejected/pending)."""
    groups: dict[str, list[str]] = {}
    for node in nodes:
        result = node.get("data", {}).get("result_group", "unknown")
        groups.setdefault(result, []).append(node["id"])
    return groups


@router.post("/{space_id}/execute/simulate", response_model=dict, summary="Simulate analysis", description="Simulate rule execution with hypothetical data overrides. Returns baseline vs simulated comparison.")
async def execute_simulate(space_id: str, request: ExecuteSimulateRequest):
    """Execute what-if simulation with variable overrides."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Find the entity
    entity = None
    for e in space.instances.entities:
        if e.get("entity_id") == request.entity_id:
            entity = e
            break

    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")

    # Execute baseline analysis first
    baseline_steps = []
    baseline_outputs = {}
    entity_data = dict(entity)
    entity_data["_fact_object"] = entity.get("_fact_object") or entity.get("_concept", "Unknown")

    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule["id"]
        when_expr = rule.get("when", {}).get("expression") if rule.get("when") else None
        then_action = rule.get("then_action")

        # Get logic if available
        for logic_id in rule.get("logic_ids", []):
            for logic in space.layers.L4_business_logic.rule_logics:
                if logic["id"] == logic_id:
                    when_expr = logic.get("when", {}).get("expression") if logic.get("when") else None
                    then_action = logic.get("then_action")
                    break

        condition_result = bool(when_expr)  # Simplified
        baseline_steps.append({
            "step": len(baseline_steps) + 1,
            "rule_id": rule_id,
            "rule_name": rule.get("name", rule_id),
            "rule_type": rule.get("rule_type", "constraint"),
            "status": "passed" if condition_result else "skipped",
        })

        if condition_result and then_action:
            action_type = then_action.get("action_type", "")
            if action_type == "set_flag":
                output_name = then_action.get("output", {}).get("eligible") or "result"
                baseline_outputs[output_name] = then_action.get("output", {}).get("value", True)

    # Apply overrides and execute simulated analysis
    simulated_data = dict(entity)
    simulated_data["_fact_object"] = entity.get("_fact_object") or entity.get("_concept", "Unknown")
    if request.overrides:
        simulated_data.update(request.overrides)

    simulated_steps = []
    simulated_outputs = {}

    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule["id"]
        when_expr = rule.get("when", {}).get("expression") if rule.get("when") else None
        then_action = rule.get("then_action")

        # Get logic if available
        for logic_id in rule.get("logic_ids", []):
            for logic in space.layers.L4_business_logic.rule_logics:
                if logic["id"] == logic_id:
                    when_expr = logic.get("when", {}).get("expression") if logic.get("when") else None
                    then_action = logic.get("then_action")
                    break

        condition_result = bool(when_expr)  # Simplified
        simulated_steps.append({
            "step": len(simulated_steps) + 1,
            "rule_id": rule_id,
            "rule_name": rule.get("name", rule_id),
            "rule_type": rule.get("rule_type", "constraint"),
            "status": "passed" if condition_result else "skipped",
        })

        if condition_result and then_action:
            action_type = then_action.get("action_type", "")
            if action_type == "set_flag":
                output_name = then_action.get("output", {}).get("eligible") or "result"
                simulated_outputs[output_name] = then_action.get("output", {}).get("value", True)

    # Build diffs
    diffs = []
    all_keys = set(baseline_outputs.keys()) | set(simulated_outputs.keys())
    for key in all_keys:
        baseline_val = baseline_outputs.get(key)
        simulated_val = simulated_outputs.get(key)
        if baseline_val != simulated_val:
            change_type = "changed"
            if key not in baseline_outputs:
                change_type = "new"
            elif key not in simulated_outputs:
                change_type = "removed"
            diffs.append({
                "field": key,
                "baseline_value": baseline_val,
                "simulated_value": simulated_val,
                "change_type": change_type,
                "impact": f"{baseline_val} → {simulated_val}",
            })

    return success_response(data={
        "entity_id": request.entity_id,
        "dimension": request.dimension,
        "simulation_type": "what_if",
        "steps": simulated_steps,
        "execution_path": [s["rule_id"] for s in simulated_steps if s["status"] == "passed"],
        "skipped_rules": [s["rule_id"] for s in simulated_steps if s["status"] == "skipped"],
        "final_outputs": simulated_outputs,
        "comparison": {
            "baseline": baseline_outputs,
            "simulated": simulated_outputs,
            "diffs": diffs,
            "impact_chains": [],
        },
        "final_context": simulated_data,
    })


@router.post(
    "/{space_id}/schema/impact-analysis",
    response_model=dict,
    summary="Analyze schema change impact",
    description="Analyze the downstream impact of a proposed schema change on rules, entities, and analysis results. Returns affected rules, entities, and dimensions.",
)
async def analyze_schema_impact(
    space_id: str,
    request: SchemaImpactAnalysisRequest,
):
    """Analyze the downstream impact of a proposed schema change."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(
            code="SPACE_NOT_FOUND",
            message=f"Space '{space_id}' not found",
            suggestion="Use GET /v1/spaces to list available spaces",
        )

    change_type = request.change_type
    change_target = request.target
    affected_rules = []
    affected_entities = []
    affected_dimensions = set()

    if change_type in ("rule_definition", "rule_logic"):
        for rd in space.layers.L4_business_logic.rule_definitions:
            if change_target in (rd.get("id", ""), rd.get("name", "")):
                affected_rules.append({
                    "rule_id": rd.get("id"),
                    "rule_name": rd.get("name"),
                    "dimension": rd.get("dimension", ""),
                    "impact": "direct",
                })
                affected_dimensions.add(rd.get("dimension", ""))

        for rl in space.layers.L4_business_logic.rule_logics:
            if rl.get("definition_id") == change_target:
                affected_rules.append({
                    "logic_id": rl.get("id"),
                    "definition_id": rl.get("definition_id"),
                    "impact": "cascaded",
                })

    if change_type in ("fact_object", "entity_type"):
        for entity in space.instances.entities:
            if entity.get("_fact_object") == change_target:
                affected_entities.append({
                    "entity_id": entity.get("entity_id"),
                    "fact_object": entity.get("_fact_object"),
                    "impact": "direct",
                })

        for rd in space.layers.L4_business_logic.rule_definitions:
            applies_to_names = _extract_applies_to_fact_objects(rd)
            if change_target in applies_to_names:
                affected_rules.append({
                    "rule_id": rd.get("id"),
                    "rule_name": rd.get("name"),
                    "impact": "applies_to_match",
                })
                affected_dimensions.add(rd.get("dimension", ""))

    return success_response(data={
        "space_id": space_id,
        "change_type": change_type,
        "change_target": change_target,
        "affected_rules": affected_rules,
        "affected_rules_count": len(affected_rules),
        "affected_entities": affected_entities[:50],
        "affected_entities_count": len(affected_entities),
        "affected_dimensions": list(affected_dimensions),
    })


@router.get(
    "/{space_id}/instances/entities/{entity_id}/versions",
    response_model=dict,
    summary="List entity version history",
    description="List the version history of a specific entity, showing all changes made over time.",
)
async def list_entity_versions(
    space_id: str,
    entity_id: str,
):
    """List version history for a specific entity."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(
            code="SPACE_NOT_FOUND",
            message=f"Space '{space_id}' not found",
            suggestion="Use GET /v1/spaces to list available spaces",
        )

    entity = next(
        (e for e in space.instances.entities if e.get("entity_id") == entity_id),
        None,
    )
    if not entity:
        return error_response(
            code="ENTITY_NOT_FOUND",
            message=f"Entity '{entity_id}' not found in space '{space_id}'",
            suggestion="Use GET /v1/spaces/{space_id}/instances/entities to list entities",
        )

    entity_versions = []
    for v in space.versions:
        v_space = await service.load_version(space_id, v.version, space=space)
        if v_space:
            v_entity = next(
                (e for e in v_space.instances.entities if e.get("entity_id") == entity_id),
                None,
            )
            if v_entity:
                entity_versions.append({
                    "version": v.version,
                    "timestamp": v.created_at.isoformat(),
                    "description": v.change_description or "",
                    "entity_snapshot": v_entity,
                })

    return success_response(data={
        "space_id": space_id,
        "entity_id": entity_id,
        "versions": entity_versions,
        "total": len(entity_versions),
    })


@router.get(
    "/{space_id}/rules/definitions/{rule_id}/versions",
    response_model=dict,
    summary="List rule version history",
    description="List the version history of a specific rule definition, showing all changes made over time.",
)
async def list_rule_versions(
    space_id: str,
    rule_id: str,
):
    """List version history for a specific rule definition."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(
            code="SPACE_NOT_FOUND",
            message=f"Space '{space_id}' not found",
            suggestion="Use GET /v1/spaces to list available spaces",
        )

    current_rule = next(
        (rd for rd in space.layers.L4_business_logic.rule_definitions if rd.get("id") == rule_id),
        None,
    )
    if not current_rule:
        return error_response(
            code="NOT_FOUND",
            message=f"Rule definition '{rule_id}' not found",
        )

    versions = space.versions
    rule_versions = []
    for v in versions:
        v_space = await service.load_version(space_id, v.version, space=space)
        if v_space:
            v_rule = next(
                (rd for rd in v_space.layers.L4_business_logic.rule_definitions if rd.get("id") == rule_id),
                None,
            )
            if v_rule:
                rule_versions.append({
                    "version": v.version,
                    "timestamp": v.created_at.isoformat(),
                    "description": v.change_description or "",
                    "rule_snapshot": v_rule,
                })

    return success_response(data={
        "space_id": space_id,
        "rule_id": rule_id,
        "versions": rule_versions,
        "total": len(rule_versions),
    })


@router.get(
    "/{space_id}/etag",
    response_model=dict,
    summary="Get space ETag",
    description="Get the current ETag (entity tag) for a space. Used for optimistic concurrency control — include the ETag in If-Match header when updating.",
)
async def get_space_etag(space_id: str):
    """Get ETag for optimistic concurrency control."""
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(
            code="SPACE_NOT_FOUND",
            message=f"Space '{space_id}' not found",
            suggestion="Use GET /v1/spaces to list available spaces",
        )

    etag = _compute_etag(space)

    return success_response(data={
        "space_id": space_id,
        "etag": etag,
        "active_version": space.active_version,
    })


# ============================================================================
# Space Lifecycle
# ============================================================================

@router.post("/{space_id}/activate", response_model=dict)
async def activate_space(space_id: str):
    service = get_space_service()
    result = await service.activate_space(space_id)

    if not result:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if result.get("invalid_transition"):
        return error_response(code="INVALID_TRANSITION", message=result["error"])

    if result.get("already_active"):
        return success_response(data=result)

    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    view_id = space.metadata.view_id
    if view_id:
        view = await service.get_space(view_id)
        if not view:
            view_id = f"view_{uuid.uuid4().hex[:8]}"
            space.metadata.view_id = view_id
            await service.save_space(space)

            view_metadata = SpaceMetadata(
                id=view_id,
                name=f"{space.metadata.name} (消费视图)",
                space_type=SpaceType.CONSUMPTION,
                description=f"自动创建的消费视图，授权自 {space_id}",
                status=SpaceStatus.ACTIVE,
            )
            view = SemanticSpace(
                metadata=view_metadata,
                layers=SemanticSpaceLayers(),
                instances=SpaceInstances(),
                versions=[],
            )
            await service.save_space(view)

        view.layers = SemanticSpaceLayers(
            L1_fact_objects=list(space.layers.L1_fact_objects),
            L2_categorizations=list(space.layers.L2_categorizations),
            L3_analytical_elements=list(space.layers.L3_analytical_elements),
            L4_business_logic=L4BusinessLogic(
                rule_definitions=list(space.layers.L4_business_logic.rule_definitions),
                rule_logics=list(space.layers.L4_business_logic.rule_logics),
            ),
        )
        view.instances = SpaceInstances(
            entities=list(space.instances.entities),
            relations=list(space.instances.relations),
            category_tags=list(space.instances.category_tags),
            metric_values=list(space.instances.metric_values),
        )
        view.metadata.status = SpaceStatus.ACTIVE
        await service.save_space(view)

    return success_response(data={"id": space_id, "status": result.get("status"), "view_id": view_id})


@router.post("/{space_id}/deactivate", response_model=dict)
async def deactivate_space(space_id: str):
    service = get_space_service()
    result = await service.deactivate_space(space_id)

    if not result:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if result.get("invalid_transition"):
        return error_response(code="INVALID_TRANSITION", message=result["error"])

    space = await service.get_space(space_id)
    view_id = space.metadata.view_id if space else None
    if view_id:
        view = await service.get_space(view_id)
        if view:
            view.metadata.status = SpaceStatus.DRAFT
            await service.save_space(view)

    return success_response(data={"id": space_id, "status": result.get("status"), "view_id": view_id})


@router.post("/{space_id}/archive", response_model=dict)
async def archive_space(space_id: str):
    service = get_space_service()
    result = await service.archive_space(space_id)

    if not result:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if result.get("invalid_transition"):
        return error_response(code="INVALID_TRANSITION", message=result["error"])

    space = await service.get_space(space_id)
    view_id = space.metadata.view_id if space else None
    if view_id:
        view = await service.get_space(view_id)
        if view:
            view.metadata.status = SpaceStatus.ARCHIVED
            await service.save_space(view)

    return success_response(data={"id": space_id, "status": result.get("status")})


@router.post("/load-from-json", response_model=dict)
async def load_space_from_json(request: LoadSpaceFromJsonRequest):
    json_path = request.json_path

    try:
        resolved = _resolve_safe_path(json_path)
    except PermissionError as e:
        return error_response(code="FORBIDDEN", message=str(e))

    if resolved is None:
        return error_response(code="FILE_NOT_FOUND", message=f"Space file not found: {json_path}")

    try:
        service = get_space_service()
        space = service.load_space_from_file(str(resolved))
    except Exception as e:
        return error_response(code="SPACE_LOAD_ERROR", message=f"Failed to load space: {str(e)}")

    if request.space_id:
        space.metadata.id = request.space_id

    space.metadata.space_type = SpaceType.MANAGEMENT

    existing = await service.get_space(space.metadata.id)
    if existing and not request.overwrite:
        return error_response(
            code="CONFLICT",
            message=f"Space {space.metadata.id} already exists. Use overwrite or a different space_id."
        )

    await service.save_space(space)

    view_id = space.metadata.view_id
    if not view_id:
        view_id = f"view_{uuid.uuid4().hex[:8]}"
        space.metadata.view_id = view_id
        await service.save_space(space)

        view_metadata = SpaceMetadata(
            id=view_id,
            name=f"{space.metadata.name} (消费视图)",
            space_type=SpaceType.CONSUMPTION,
            description=f"自动创建的消费视图，授权自 {space.metadata.id}",
            status=SpaceStatus.ACTIVE,
        )
        view_space = SemanticSpace(
            metadata=view_metadata,
            layers=SemanticSpaceLayers(),
            instances=SpaceInstances(),
            versions=[],
        )
        await service.save_space(view_space)

    return success_response(data={
        "id": space.metadata.id,
        "name": space.metadata.name,
        "status": space.metadata.status.value,
        "view_id": view_id,
        "loaded": {
            "L1_fact_objects": len(space.layers.L1_fact_objects),
            "L2_categorizations": len(space.layers.L2_categorizations),
            "L3_analytical_elements": len(space.layers.L3_analytical_elements),
            "L4_rule_definitions": len(space.layers.L4_business_logic.rule_definitions),
            "L4_rule_logics": len(space.layers.L4_business_logic.rule_logics),
            "entities": len(space.instances.entities),
            "relations": len(space.instances.relations),
        },
    })


# ============================================================================
# Schema Layer Routes
# ============================================================================

@router.get("/{space_id}/schema/L1/fact-objects", response_model=dict)
async def list_fact_objects(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L1_fact_objects)


@router.post("/{space_id}/schema/L1/fact-objects", response_model=dict)
async def add_fact_object(space_id: str, request: AddFactObjectRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_ids = [fo.get("id") for fo in space.layers.L1_fact_objects]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Fact object {request.id} already exists")

    fact_object = {
        "id": request.id,
        "name": request.name,
        "description": request.description,
        "properties": request.properties or [],
        "relations": request.relations or [],
    }

    space.layers.L1_fact_objects.append(fact_object)
    await service.save_space(space)

    return success_response(data=fact_object)


@router.get("/{space_id}/schema/L2/categorizations", response_model=dict)
async def list_categorizations(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L2_categorizations)


@router.post("/{space_id}/schema/L2/categorizations", response_model=dict)
async def add_categorization(space_id: str, request: AddCategorizationRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_ids = [c.get("id") for c in space.layers.L2_categorizations]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Categorization {request.id} already exists")

    categorization = {
        "id": request.id,
        "name": request.name,
        "type": request.type,
        "description": request.description,
        "dimensions": request.dimensions or [],
        "values": request.values or [],
    }

    space.layers.L2_categorizations.append(categorization)
    await service.save_space(space)

    return success_response(data=categorization)


@router.get("/{space_id}/schema/L3/analytical-elements", response_model=dict)
async def list_analytical_elements(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L3_analytical_elements)


@router.post("/{space_id}/schema/L3/analytical-elements", response_model=dict)
async def add_analytical_element(space_id: str, request: AddAnalyticalElementRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_ids = [e.get("id") for e in space.layers.L3_analytical_elements]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Analytical element {request.id} already exists")

    element = {
        "id": request.id,
        "name": request.name,
        "type": request.type,
        "description": request.description,
        "source": request.source,
        "dependencies": request.dependencies or [],
        "overridable": request.overridable,
    }

    space.layers.L3_analytical_elements.append(element)
    await service.save_space(space)

    return success_response(data=element)


@router.delete("/{space_id}/schema/L2/categorizations/{categorization_id}", response_model=dict)
async def schema_l2_delete_categorization(space_id: str, categorization_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")
    original_count = len(space.layers.L2_categorizations)
    space.layers.L2_categorizations = [
        c for c in space.layers.L2_categorizations if c.get("id") != categorization_id
    ]
    if len(space.layers.L2_categorizations) == original_count:
        return error_response(code="NOT_FOUND", message=f"Categorization {categorization_id} not found")
    await service.save_space(space)
    return success_response(data={"deleted": True})


@router.delete("/{space_id}/schema/L3/analytical-elements/{element_id}", response_model=dict)
async def schema_l3_delete_analytical_element(space_id: str, element_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")
    original_count = len(space.layers.L3_analytical_elements)
    space.layers.L3_analytical_elements = [
        e for e in space.layers.L3_analytical_elements if e.get("id") != element_id
    ]
    if len(space.layers.L3_analytical_elements) == original_count:
        return error_response(code="NOT_FOUND", message=f"Analytical element {element_id} not found")
    await service.save_space(space)
    return success_response(data={"deleted": True})


@router.get("/{space_id}/schema", response_model=dict)
async def get_schema_overview(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data={
        "space_id": space_id,
        "L1": {
            "count": len(space.layers.L1_fact_objects),
            "items": space.layers.L1_fact_objects,
        },
        "L2": {
            "count": len(space.layers.L2_categorizations),
            "items": space.layers.L2_categorizations,
        },
        "L3": {
            "count": len(space.layers.L3_analytical_elements),
            "items": space.layers.L3_analytical_elements,
        },
        "L4": {
            "rule_definitions_count": len(space.layers.L4_business_logic.rule_definitions),
            "rule_logics_count": len(space.layers.L4_business_logic.rule_logics),
            "rule_definitions": space.layers.L4_business_logic.rule_definitions,
            "rule_logics": space.layers.L4_business_logic.rule_logics,
        },
    })


# ============================================================================
# Schema L4 Rules CRUD (direct layer access)
# ============================================================================

@router.get("/{space_id}/schema/L4/rules/definitions", response_model=dict)
async def schema_l4_list_rule_definitions(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_definitions)


@router.post("/{space_id}/schema/L4/rules/definitions", response_model=dict)
async def schema_l4_add_rule_definition(space_id: str, request: AddRuleDefinitionRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_ids = [rd.get("id") for rd in space.layers.L4_business_logic.rule_definitions]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Rule definition {request.id} already exists")

    definition = {
        "id": request.id,
        "name": request.name,
        "description": request.description,
        "rule_type": request.rule_type,
        "priority": request.priority,
        "applies_to": request.applies_to,
        "inputs": request.inputs,
        "outputs": request.outputs,
        "preconditions": request.preconditions,
        "enabled": request.enabled,
        "logic_ids": request.logic_ids or [],
    }

    space.layers.L4_business_logic.rule_definitions.append(definition)
    await service.save_space(space)

    return success_response(data=definition)


@router.get("/{space_id}/schema/L4/rules/definitions/{rule_id}", response_model=dict)
async def schema_l4_get_rule_definition(space_id: str, rule_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    definition = next(
        (rd for rd in space.layers.L4_business_logic.rule_definitions if rd.get("id") == rule_id),
        None,
    )

    if not definition:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    return success_response(data=definition)


@router.put("/{space_id}/schema/L4/rules/definitions/{rule_id}", response_model=dict)
async def schema_l4_update_rule_definition(space_id: str, rule_id: str, request: AddRuleDefinitionRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    index = next(
        (i for i, rd in enumerate(space.layers.L4_business_logic.rule_definitions) if rd.get("id") == rule_id),
        None,
    )

    if index is None:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    definition = {
        "id": rule_id,
        "name": request.name,
        "description": request.description,
        "rule_type": request.rule_type,
        "priority": request.priority,
        "applies_to": request.applies_to,
        "inputs": request.inputs,
        "outputs": request.outputs,
        "preconditions": request.preconditions,
        "enabled": request.enabled,
        "logic_ids": request.logic_ids or [],
    }

    space.layers.L4_business_logic.rule_definitions[index] = definition
    await service.save_space(space)

    return success_response(data=definition)


@router.delete("/{space_id}/schema/L4/rules/definitions/{rule_id}", response_model=dict)
async def schema_l4_delete_rule_definition(space_id: str, rule_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    original_count = len(space.layers.L4_business_logic.rule_definitions)
    space.layers.L4_business_logic.rule_definitions = [
        rd for rd in space.layers.L4_business_logic.rule_definitions if rd.get("id") != rule_id
    ]

    if len(space.layers.L4_business_logic.rule_definitions) == original_count:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    await service.save_space(space)

    return success_response(data={"deleted": True})


@router.get("/{space_id}/schema/L4/rules/logics", response_model=dict)
async def schema_l4_list_rule_logics(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_logics)


@router.post("/{space_id}/schema/L4/rules/logics", response_model=dict)
async def schema_l4_add_rule_logic(space_id: str, request: AddRuleLogicRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    def_ids = [rd.get("id") for rd in space.layers.L4_business_logic.rule_definitions]
    if request.definition_id not in def_ids:
        return error_response(code="NOT_FOUND", message=f"Rule definition {request.definition_id} not found")

    existing_ids = [rl.get("id") for rl in space.layers.L4_business_logic.rule_logics]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Rule logic {request.id} already exists")

    logic = {
        "id": request.id,
        "definition_id": request.definition_id,
        "name": request.name,
        "description": request.description,
        "applicable_conditions": request.applicable_conditions or [],
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
        "priority": request.priority,
        "version": request.version,
        "environment": request.environment,
    }

    space.layers.L4_business_logic.rule_logics.append(logic)
    await service.save_space(space)

    return success_response(data=logic)


@router.get("/{space_id}/schema/L4/rules/logics/{logic_id}", response_model=dict)
async def schema_l4_get_rule_logic(space_id: str, logic_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    logic = next(
        (rl for rl in space.layers.L4_business_logic.rule_logics if rl.get("id") == logic_id),
        None,
    )

    if not logic:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    return success_response(data=logic)


@router.put("/{space_id}/schema/L4/rules/logics/{logic_id}", response_model=dict)
async def schema_l4_update_rule_logic(space_id: str, logic_id: str, request: AddRuleLogicRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    index = next(
        (i for i, rl in enumerate(space.layers.L4_business_logic.rule_logics) if rl.get("id") == logic_id),
        None,
    )

    if index is None:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    logic = {
        "id": logic_id,
        "definition_id": request.definition_id,
        "name": request.name,
        "description": request.description,
        "applicable_conditions": request.applicable_conditions or [],
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
        "priority": request.priority,
        "version": request.version,
        "environment": request.environment,
    }

    space.layers.L4_business_logic.rule_logics[index] = logic
    await service.save_space(space)

    return success_response(data=logic)


@router.delete("/{space_id}/schema/L4/rules/logics/{logic_id}", response_model=dict)
async def schema_l4_delete_rule_logic(space_id: str, logic_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    original_count = len(space.layers.L4_business_logic.rule_logics)
    space.layers.L4_business_logic.rule_logics = [
        rl for rl in space.layers.L4_business_logic.rule_logics if rl.get("id") != logic_id
    ]

    if len(space.layers.L4_business_logic.rule_logics) == original_count:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    await service.save_space(space)

    return success_response(data={"deleted": True})


# ============================================================================
# Schema L4 Rule Dependency Graph
# ============================================================================

@router.get("/{space_id}/schema/L4/rules/dependency-graph", response_model=dict)
async def get_rule_dependency_graph(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    rules = space.layers.L4_business_logic.rule_definitions

    nodes = []
    for rule in rules:
        logic_ids = rule.get("logic_ids", [])
        logics = [
            rl for rl in space.layers.L4_business_logic.rule_logics
            if rl.get("id") in logic_ids
        ]

        nodes.append({
            "id": rule["id"],
            "label": rule.get("name") or rule["id"],
            "rule_type": rule.get("rule_type", "constraint"),
            "priority": rule.get("priority", 100),
            "enabled": rule.get("enabled", True),
            "applies_to": _extract_applies_to_fact_objects(rule),
            "applicable_categorizations": rule.get("applicable_categorizations", []),
            "inputs": _rule_inputs(rule),
            "outputs": _rule_outputs(rule),
            "logic_count": len(logics),
        })

    edges = []
    output_map: dict[str, list[str]] = {}
    for rule in rules:
        for out_elem in _rule_outputs(rule):
            elem_name = out_elem.get("name") or out_elem.get("id", "")
            if elem_name:
                output_map.setdefault(elem_name, []).append(rule["id"])

    for rule in rules:
        for in_elem in _rule_inputs(rule):
            elem_name = in_elem.get("name") or in_elem.get("id", "")
            producers = output_map.get(elem_name, [])
            for producer_id in producers:
                if producer_id != rule["id"]:
                    edges.append({
                        "id": f"{producer_id}__{rule['id']}__{elem_name}",
                        "source": producer_id,
                        "target": rule["id"],
                        "element": elem_name,
                        "type": "data_dependency",
                        "label": elem_name,
                    })

    exclusion_pairs = []
    for i, rule_a in enumerate(rules):
        for rule_b in rules[i + 1:]:
            targets_a = set(_extract_applies_to_fact_objects(rule_a))
            targets_b = set(_extract_applies_to_fact_objects(rule_b))
            if not (targets_a & targets_b) and targets_a and targets_b:
                continue
            cats_a = set(rule_a.get("applicable_categorizations", []))
            cats_b = set(rule_b.get("applicable_categorizations", []))
            if cats_a and cats_b and not (cats_a & cats_b):
                exclusion_pairs.append({
                    "rule_a": rule_a["id"],
                    "rule_b": rule_b["id"],
                    "reason": f"适用分类不同: {list(cats_a)} vs {list(cats_b)}",
                    "type": "categorization_exclusive",
                })
            outputs_a = {(e.get("name") or e.get("id", "")) for e in _rule_outputs(rule_a)}
            outputs_b = {(e.get("name") or e.get("id", "")) for e in _rule_outputs(rule_b)}
            shared_outputs = outputs_a & outputs_b - {""}
            if shared_outputs:
                exclusion_pairs.append({
                    "rule_a": rule_a["id"],
                    "rule_b": rule_b["id"],
                    "reason": f"共同输出元素: {list(shared_outputs)}",
                    "type": "output_conflict",
                })

    execution_order = _topological_sort(nodes, edges)

    return success_response(data={
        "space_id": space_id,
        "nodes": nodes,
        "edges": edges,
        "mutual_exclusions": exclusion_pairs,
        "execution_order": execution_order,
        "stats": {
            "total_rules": len(nodes),
            "dependency_edges": len(edges),
            "exclusion_pairs": len(exclusion_pairs),
        },
    })


# ============================================================================
# Schema & Instance YAML Loading
# ============================================================================

@router.post("/{space_id}/schema/load-yaml", response_model=dict)
async def load_schema_from_yaml(space_id: str, request: LoadFromYamlRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    try:
        resolved = _resolve_safe_path(request.yaml_path)
    except PermissionError as e:
        return error_response(code="FORBIDDEN", message=str(e))

    if resolved is None:
        return error_response(code="FILE_NOT_FOUND", message=f"Schema file not found: {request.yaml_path}")

    try:
        schema = service.load_schema_from_file(str(resolved))
    except Exception as e:
        return error_response(code="SCHEMA_LOAD_ERROR", message=f"Failed to load schema: {str(e)}")

    try:
        layers_dict = schema.to_space_layers_dict()
    except Exception as e:
        return error_response(code="SCHEMA_CONVERT_ERROR", message=f"Failed to convert schema: {str(e)}")

    if request.overwrite:
        space.layers = SemanticSpaceLayers(
            L1_fact_objects=layers_dict["L1_fact_objects"],
            L2_categorizations=layers_dict["L2_categorizations"],
            L3_analytical_elements=layers_dict["L3_analytical_elements"],
            L4_business_logic=L4BusinessLogic(
                rule_definitions=layers_dict["L4_business_logic"]["rule_definitions"],
                rule_logics=layers_dict["L4_business_logic"]["rule_logics"],
            ),
        )
    else:
        existing_l1_ids = {fo.get("id") for fo in space.layers.L1_fact_objects}
        for fo in layers_dict["L1_fact_objects"]:
            if fo.get("id") not in existing_l1_ids:
                space.layers.L1_fact_objects.append(fo)

        existing_l2_ids = {c.get("id") for c in space.layers.L2_categorizations}
        for cat in layers_dict["L2_categorizations"]:
            if cat.get("id") not in existing_l2_ids:
                space.layers.L2_categorizations.append(cat)

        existing_l3_ids = {e.get("id") for e in space.layers.L3_analytical_elements}
        for elem in layers_dict["L3_analytical_elements"]:
            if elem.get("id") not in existing_l3_ids:
                space.layers.L3_analytical_elements.append(elem)

        existing_rd_ids = {rd.get("id") for rd in space.layers.L4_business_logic.rule_definitions}
        for rd in layers_dict["L4_business_logic"]["rule_definitions"]:
            if rd.get("id") not in existing_rd_ids:
                space.layers.L4_business_logic.rule_definitions.append(rd)

        existing_rl_ids = {rl.get("id") for rl in space.layers.L4_business_logic.rule_logics}
        for rl in layers_dict["L4_business_logic"]["rule_logics"]:
            if rl.get("id") not in existing_rl_ids:
                space.layers.L4_business_logic.rule_logics.append(rl)

    if schema.metadata.domain and not space.metadata.domain:
        space.metadata.domain = schema.metadata.domain

    await service.save_space(space)

    return success_response(data={
        "space_id": space_id,
        "schema_id": schema.metadata.id,
        "schema_name": schema.metadata.name,
        "loaded": {
            "L1_fact_objects": len(layers_dict["L1_fact_objects"]),
            "L2_categorizations": len(layers_dict["L2_categorizations"]),
            "L3_analytical_elements": len(layers_dict["L3_analytical_elements"]),
            "L4_rule_definitions": len(layers_dict["L4_business_logic"]["rule_definitions"]),
            "L4_rule_logics": len(layers_dict["L4_business_logic"]["rule_logics"]),
        },
        "total_after": {
            "L1_fact_objects": len(space.layers.L1_fact_objects),
            "L2_categorizations": len(space.layers.L2_categorizations),
            "L3_analytical_elements": len(space.layers.L3_analytical_elements),
            "L4_rule_definitions": len(space.layers.L4_business_logic.rule_definitions),
            "L4_rule_logics": len(space.layers.L4_business_logic.rule_logics),
        },
    })


@router.post("/{space_id}/instances/load-yaml", response_model=dict)
async def load_instances_from_yaml(space_id: str, request: LoadInstancesFromYamlRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    yaml_path = request.yaml_path

    try:
        resolved = _resolve_safe_path(yaml_path)
    except PermissionError as e:
        return error_response(code="FORBIDDEN", message=str(e))

    if resolved is None:
        return error_response(code="FILE_NOT_FOUND", message=f"Instances file not found: {yaml_path}")

    try:
        entities, relations = service.load_instances_from_file(str(resolved))
    except Exception as e:
        return error_response(code="INSTANCE_LOAD_ERROR", message=f"Failed to load instances: {str(e)}")

    if request.overwrite:
        space.instances.entities = []
        space.instances.relations = []

    existing_entity_ids = {e.get("entity_id") for e in space.instances.entities}
    added_entities = 0
    for entity in entities:
        eid = entity.entity_id
        entity_dict: dict[str, object] = {
            "entity_id": eid,
            "_fact_object": entity._fact_object,
            "_concept": entity._fact_object,
        }
        if hasattr(entity, 'data') and entity.data:
            entity_dict.update(entity.data)

        if eid not in existing_entity_ids:
            space.instances.entities.append(entity_dict)
            existing_entity_ids.add(eid)
            added_entities += 1

    added_relations = 0
    for relation in relations:
        rel_dict: dict[str, object] = {
            "from_entity_id": relation.from_entity_id,
            "to_entity_id": relation.to_entity_id,
            "relation_type": relation.relation_name,
            "relation_name": relation.relation_name,
        }
        if hasattr(relation, 'data') and relation.data:
            rel_dict.update(relation.data)
        space.instances.relations.append(rel_dict)
        added_relations += 1

    await service.save_space(space)

    return success_response(data={
        "space_id": space_id,
        "added_entities": added_entities,
        "added_relations": added_relations,
        "total_entities": len(space.instances.entities),
        "total_relations": len(space.instances.relations),
    })

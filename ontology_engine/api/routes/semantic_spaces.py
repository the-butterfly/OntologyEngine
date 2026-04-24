# ontology_engine/api/routes/semantic_spaces.py
"""Semantic Spaces API routes - management surface for semantic spaces."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel, AliasChoices, Field

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    SemanticSpaceStorage,
    SemanticSpaceStorageError,
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


def _get_storage() -> SemanticSpaceStorage:
    """Get or create storage instance."""
    return SemanticSpaceStorage()


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


# ============================================================================
# Space CRUD
# ============================================================================

@router.post("/", response_model=dict, summary="Create semantic space", description="Create a new semantic space in DRAFT status. After creation, load schema via /schema/load-yaml and activate via /{space_id}/activate before running analysis.")
async def create_space(request: CreateSpaceRequest):
    """Create a new semantic space."""
    storage = _get_storage()

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

    await storage.save(space)

    return success_response(data=_space_to_response(space))


@router.get("/", response_model=dict, summary="List semantic spaces", description="List all semantic spaces with their IDs, names, statuses, and entity counts.")
async def list_spaces():
    """List all semantic spaces."""
    storage = _get_storage()
    spaces = await storage.list()

    # Load full space for counts
    responses = []
    for metadata in spaces:
        space = await storage.load(metadata.id)
        if space:
            responses.append(_space_to_response(space))

    return success_response(data=responses)


@router.get("/{space_id}", response_model=dict, summary="Get semantic space", description="Get detailed information about a specific semantic space.")
async def get_space(space_id: str):
    """Get a semantic space by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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
    if request.status is not None:
        space.metadata.status = request.status

    await storage.save(space)

    return success_response(data=_space_to_response(space))


@router.delete("/{space_id}", response_model=dict, summary="Delete semantic space", description="Delete a semantic space and all its associated data. Supports ?dry_run=true to preview impact.")
async def delete_space(space_id: str, dry_run: bool = Query(default=False, description="If true, preview what would be deleted without actually deleting")):
    """Delete (archive) a semantic space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

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

    deleted = await storage.delete(space_id)

    if not deleted:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data={"deleted": True, "space_id": space_id})


# ============================================================================
# Rule Definitions CRUD
# ============================================================================

@router.get("/{space_id}/rules/definitions", response_model=dict, summary="List rule definitions", description="List all rule definitions (L4) in the space.")
async def list_rule_definitions(space_id: str):
    """List all rule definitions in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=space.layers.L4_business_logic.rule_definitions)


@router.post("/{space_id}/rules/definitions", response_model=dict, summary="Create rule definition", description="Add a new rule definition to the space schema L4 layer.")
async def create_rule_definition(space_id: str, request: CreateRuleDefinitionRequest):
    """Create a new rule definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    await storage.save(space)

    return success_response(data=definition)


@router.get("/{space_id}/rules/definitions/{rule_id}", response_model=dict, summary="Get rule definition", description="Get a specific rule definition by ID.")
async def get_rule_definition(space_id: str, rule_id: str):
    """Get a rule definition by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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
    await storage.save(space)

    return success_response(data=definition)


@router.delete("/{space_id}/rules/definitions/{rule_id}", response_model=dict, summary="Delete rule definition", description="Delete a rule definition. Supports ?dry_run=true to preview impact.")
async def delete_rule_definition(space_id: str, rule_id: str, dry_run: bool = Query(default=False, description="If true, preview what would be deleted without actually deleting")):
    """Delete a rule definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

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

    await storage.save(space)

    return success_response(data={"deleted": True, "rule_id": rule_id, "cascaded_logics": len(dependent_logics)})


# ============================================================================
# Rule Logics CRUD
# ============================================================================

@router.get("/{space_id}/rules/logics", response_model=dict, summary="List rule logics", description="List all rule logics (L4) in the space.")
async def list_rule_logics(space_id: str):
    """List all rule logics in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=space.layers.L4_business_logic.rule_logics)


@router.post("/{space_id}/rules/logics", response_model=dict, summary="Create rule logic", description="Add a new rule logic to the space schema L4 layer.")
async def create_rule_logic(space_id: str, request: CreateRuleLogicRequest):
    """Create a new rule logic."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    await storage.save(space)

    return success_response(data=logic)


@router.get("/{space_id}/rules/logics/{logic_id}", response_model=dict, summary="Get rule logic", description="Get a specific rule logic by ID.")
async def get_rule_logic(space_id: str, logic_id: str):
    """Get a rule logic by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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
    await storage.save(space)

    return success_response(data=logic)


@router.delete("/{space_id}/rules/logics/{logic_id}", response_model=dict, summary="Delete rule logic", description="Delete a rule logic.")
async def delete_rule_logic(space_id: str, logic_id: str):
    """Delete a rule logic."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    original_count = len(space.layers.L4_business_logic.rule_logics)
    space.layers.L4_business_logic.rule_logics = [
        rl for rl in space.layers.L4_business_logic.rule_logics if rl["id"] != logic_id
    ]

    if len(space.layers.L4_business_logic.rule_logics) == original_count:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    await storage.save(space)

    return success_response(data={"deleted": True})


# ============================================================================
# Version Management
# ============================================================================

@router.get("/{space_id}/versions", response_model=dict, summary="List versions", description="List all version snapshots for the space.")
async def list_versions(space_id: str):
    """List all versions of a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    try:
        version = await storage.create_snapshot(
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
    storage = _get_storage()

    try:
        current = await storage.load(space_id)
        if not current:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

        if dry_run:
            target = await storage.load_version(space_id, version, space=current)
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

        restored = await storage.rollback_to_version(space_id, version, space=current)

        if not restored:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

        return success_response(data=_space_to_response(restored))
    except SemanticSpaceStorageError as e:
        return error_response(code="ROLLBACK_ERROR", message=str(e))


# ============================================================================
# Instance Data Management
# ============================================================================

@router.get("/{space_id}/instances/entities", response_model=dict, summary="List entities", description="List all entities in the space.")
async def list_entities(
    space_id: str,
    concept: str | None = Query(default=None, description="Filter by concept"),
):
    """List entities in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    entities = space.instances.entities
    if concept:
        entities = [e for e in entities if e.get("_fact_object") == concept or e.get("_concept") == concept]

    return success_response(data=entities)


@router.post("/{space_id}/instances/entities", response_model=dict, summary="Create entity", description="Add a new entity to the space.")
async def create_entity(space_id: str, entity: dict):
    """Create a new entity."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Check required fields
    if "entity_id" not in entity or ("_concept" not in entity and "_fact_object" not in entity):
        return error_response(code="VALIDATION_ERROR", message="entity_id and _fact_object (or _concept) are required")

    space.instances.entities.append(entity)
    await storage.save(space)

    return success_response(data=entity)


@router.get("/{space_id}/instances/relations", response_model=dict, summary="List relations", description="List all relations in the space.")
async def list_relations(space_id: str):
    """List relations in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    return success_response(data=space.instances.relations)


@router.post("/{space_id}/instances/relations", response_model=dict, summary="Create relation", description="Add a new relation to the space.")
async def create_relation(space_id: str, relation: dict):
    """Create a new relation."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found", suggestion="Use GET /v1/spaces to list available spaces")

    # Check required fields
    if "relation_name" not in relation or "from_entity_id" not in relation or "to_entity_id" not in relation:
        if "relation_type" in relation and "relation_name" not in relation:
            relation["relation_name"] = relation.pop("relation_type")
        else:
            return error_response(code="VALIDATION_ERROR", message="relation_name (or relation_type), from_entity_id, and to_entity_id are required")

    space.instances.relations.append(relation)
    await storage.save(space)

    return success_response(data=relation)


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
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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


@router.post("/{space_id}/execute/simulate", response_model=dict, summary="Simulate analysis", description="Simulate rule execution with hypothetical data overrides. Returns baseline vs simulated comparison.")
async def execute_simulate(space_id: str, request: ExecuteSimulateRequest):
    """Execute what-if simulation with variable overrides."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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
    storage = _get_storage()
    space = await storage.load(space_id)

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
        v_space = await storage.load_version(space_id, v.version, space=space)
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
    storage = _get_storage()
    space = await storage.load(space_id)

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
        v_space = await storage.load_version(space_id, v.version, space=space)
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
    storage = _get_storage()
    space = await storage.load(space_id)

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

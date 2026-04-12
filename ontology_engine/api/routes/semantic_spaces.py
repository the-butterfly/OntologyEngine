# ontology_engine/api/routes/semantic_spaces.py
"""Semantic Spaces API routes - management surface for semantic spaces."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    SpaceVersion,
    SemanticSpaceStorage,
    SemanticSpaceStorageError,
    RuleDefinition,
    RuleLogic,
    ApplicableScope,
    TargetObject,
    InputElement,
    OutputElement,
    RuleWhen,
    RuleAction,
    ApplicableCondition,
)

router = APIRouter(prefix="/v1/spaces", tags=["SemanticSpaces"])


# Request/Response Models
class CreateSpaceRequest(BaseModel):
    name: str
    description: str | None = None
    domain: str | None = None


class UpdateSpaceMetadataRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    status: SpaceStatus | None = None


class CreateRuleDefinitionRequest(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    rule_type: str = "constraint"
    priority: int = 100
    applicable_scope: dict | None = None
    target_objects: list[dict] | None = None
    input_elements: list[dict] | None = None
    output_elements: list[dict] | None = None
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


# ============================================================================
# Space CRUD
# ============================================================================

@router.post("/", response_model=dict)
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


@router.get("/", response_model=dict)
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


@router.get("/{space_id}", response_model=dict)
async def get_space(space_id: str):
    """Get a semantic space by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=_space_to_response(space))


@router.put("/{space_id}", response_model=dict)
async def update_space_metadata(space_id: str, request: UpdateSpaceMetadataRequest):
    """Update space metadata."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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


@router.delete("/{space_id}", response_model=dict)
async def delete_space(space_id: str):
    """Delete (archive) a semantic space."""
    storage = _get_storage()
    deleted = await storage.delete(space_id)

    if not deleted:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data={"deleted": True})


# ============================================================================
# Rule Definitions CRUD
# ============================================================================

@router.get("/{space_id}/rules/definitions", response_model=dict)
async def list_rule_definitions(space_id: str):
    """List all rule definitions in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_definitions)


@router.post("/{space_id}/rules/definitions", response_model=dict)
async def create_rule_definition(space_id: str, request: CreateRuleDefinitionRequest):
    """Create a new rule definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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
        "target_objects": request.target_objects or [],
        "input_elements": request.input_elements or [],
        "output_elements": request.output_elements or [],
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


@router.get("/{space_id}/rules/definitions/{rule_id}", response_model=dict)
async def get_rule_definition(space_id: str, rule_id: str):
    """Get a rule definition by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    definition = next(
        (rd for rd in space.layers.L4_business_logic.rule_definitions if rd["id"] == rule_id),
        None,
    )

    if not definition:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    return success_response(data=definition)


@router.put("/{space_id}/rules/definitions/{rule_id}", response_model=dict)
async def update_rule_definition(space_id: str, rule_id: str, request: CreateRuleDefinitionRequest):
    """Update a rule definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    index = next(
        (i for i, rd in enumerate(space.layers.L4_business_logic.rule_definitions) if rd["id"] == rule_id),
        None,
    )

    if index is None:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    # Update definition
    definition = {
        "id": rule_id,  # ID cannot be changed
        "name": request.name,
        "description": request.description,
        "rule_type": request.rule_type,
        "priority": request.priority,
        "applicable_scope": request.applicable_scope or {"scope_type": "global"},
        "target_objects": request.target_objects or [],
        "input_elements": request.input_elements or [],
        "output_elements": request.output_elements or [],
        "enabled": request.enabled,
        "logic_ids": request.logic_ids or [],
        "when": request.when,
        "then_action": request.then_action,
        "else_action": request.else_action,
    }

    space.layers.L4_business_logic.rule_definitions[index] = definition
    await storage.save(space)

    return success_response(data=definition)


@router.delete("/{space_id}/rules/definitions/{rule_id}", response_model=dict)
async def delete_rule_definition(space_id: str, rule_id: str):
    """Delete a rule definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    original_count = len(space.layers.L4_business_logic.rule_definitions)
    space.layers.L4_business_logic.rule_definitions = [
        rd for rd in space.layers.L4_business_logic.rule_definitions if rd["id"] != rule_id
    ]

    if len(space.layers.L4_business_logic.rule_definitions) == original_count:
        return error_response(code="NOT_FOUND", message=f"Rule definition {rule_id} not found")

    await storage.save(space)

    return success_response(data={"deleted": True})


# ============================================================================
# Rule Logics CRUD
# ============================================================================

@router.get("/{space_id}/rules/logics", response_model=dict)
async def list_rule_logics(space_id: str):
    """List all rule logics in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_logics)


@router.post("/{space_id}/rules/logics", response_model=dict)
async def create_rule_logic(space_id: str, request: CreateRuleLogicRequest):
    """Create a new rule logic."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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


@router.get("/{space_id}/rules/logics/{logic_id}", response_model=dict)
async def get_rule_logic(space_id: str, logic_id: str):
    """Get a rule logic by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    logic = next(
        (rl for rl in space.layers.L4_business_logic.rule_logics if rl["id"] == logic_id),
        None,
    )

    if not logic:
        return error_response(code="NOT_FOUND", message=f"Rule logic {logic_id} not found")

    return success_response(data=logic)


@router.put("/{space_id}/rules/logics/{logic_id}", response_model=dict)
async def update_rule_logic(space_id: str, logic_id: str, request: CreateRuleLogicRequest):
    """Update a rule logic."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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


@router.delete("/{space_id}/rules/logics/{logic_id}", response_model=dict)
async def delete_rule_logic(space_id: str, logic_id: str):
    """Delete a rule logic."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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

@router.get("/{space_id}/versions", response_model=dict)
async def list_versions(space_id: str):
    """List all versions of a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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


@router.post("/{space_id}/versions", response_model=dict)
async def create_version(space_id: str, request: CreateVersionRequest):
    """Create a new version snapshot."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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


@router.post("/{space_id}/versions/{version}/rollback", response_model=dict)
async def rollback_to_version(space_id: str, version: int):
    """Rollback to a previous version."""
    storage = _get_storage()

    try:
        restored = await storage.rollback_to_version(space_id, version)

        if not restored:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

        return success_response(data=_space_to_response(restored))
    except SemanticSpaceStorageError as e:
        return error_response(code="ROLLBACK_ERROR", message=str(e))


# ============================================================================
# Instance Data Management
# ============================================================================

@router.get("/{space_id}/instances/entities", response_model=dict)
async def list_entities(
    space_id: str,
    concept: str | None = Query(default=None, description="Filter by concept"),
):
    """List entities in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    entities = space.instances.entities
    if concept:
        entities = [e for e in entities if e.get("_concept") == concept]

    return success_response(data=entities)


@router.post("/{space_id}/instances/entities", response_model=dict)
async def create_entity(space_id: str, entity: dict):
    """Create a new entity."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Check required fields
    if "entity_id" not in entity or "_concept" not in entity:
        return error_response(code="VALIDATION_ERROR", message="entity_id and _concept are required")

    space.instances.entities.append(entity)
    await storage.save(space)

    return success_response(data=entity)


@router.get("/{space_id}/instances/relations", response_model=dict)
async def list_relations(space_id: str):
    """List relations in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.instances.relations)


@router.post("/{space_id}/instances/relations", response_model=dict)
async def create_relation(space_id: str, relation: dict):
    """Create a new relation."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Check required fields
    if "relation_type" not in relation or "from_entity_id" not in relation or "to_entity_id" not in relation:
        return error_response(code="VALIDATION_ERROR", message="relation_type, from_entity_id, and to_entity_id are required")

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


@router.get("/{space_id}/execute/schema-graph", response_model=dict)
async def get_schema_graph(
    space_id: str,
    graph_type: str = Query(default="entity_relation", description="Graph type: entity_relation, metric_dependency, full, rule_overview"),
    layer_filter: str | None = Query(default=None, description="Comma-separated layers: L1,L2,L3,L4"),
):
    """Get schema visualization graph data for a semantic space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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
                    "relation_type": rel.get("relation_type", ""),
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
                "element_type": element.get("element_type", "metric"),
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
                "target_objects": rule.get("target_objects", []),
                "input_elements": rule.get("input_elements", []),
                "output_elements": rule.get("output_elements", []),
            }
        })

    # Add rule → output element edges
    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule.get("id", "unknown")
        for output in rule.get("output_elements", []):
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
        layers = [l.strip() for l in layer_filter.split(",")]

    # Filter nodes by layer if specified
    if layers:
        layer_type_map = {
            "L1": "entity",
            "L2": "category",
            "L3": "metric",
            "L4": "rule",
        }
        allowed_types = {layer_type_map[l] for l in layers if l in layer_type_map}
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


@router.get("/{space_id}/execute/rule-chain/{dimension}", response_model=dict)
async def get_rule_chain_graph(space_id: str, dimension: str):
    """Get rule chain visualization DAG for a specific dimension."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Build rule chain DAG from rule definitions and logics
    nodes = []
    edges = []
    rule_map = {r["id"]: r for r in space.layers.L4_business_logic.rule_definitions}
    logic_map = {l["id"]: l for l in space.layers.L4_business_logic.rule_logics}

    # Create nodes for each rule definition
    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule["id"]
        # Find associated logics
        associated_logics = [
            l for l in space.layers.L4_business_logic.rule_logics
            if l.get("definition_id") == rule_id
        ]

        nodes.append({
            "id": rule_id,
            "data": {
                "label": rule.get("name", rule_id),
                "rule_type": rule.get("rule_type", "constraint"),
                "priority": rule.get("priority", 100),
                "applicable_scope": rule.get("applicable_scope", {}),
                "logic_count": len(associated_logics),
                "logic_ids": [l["id"] for l in associated_logics],
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


@router.post("/{space_id}/execute/analyze", response_model=dict)
async def execute_analyze(space_id: str, request: ExecuteAnalyzeRequest):
    """Execute rules on an entity and return analysis results."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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
    entity_data["_concept"] = entity.get("_concept", "Unknown")

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
        matching_logic = None
        for logic_id in logic_ids:
            for logic in space.layers.L4_business_logic.rule_logics:
                if logic["id"] == logic_id:
                    matching_logic = logic
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
            "inputs": rule.get("input_elements", []),
            "outputs": rule.get("output_elements", []),
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


@router.post("/{space_id}/execute/simulate", response_model=dict)
async def execute_simulate(space_id: str, request: ExecuteSimulateRequest):
    """Execute what-if simulation with variable overrides."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

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
    entity_data["_concept"] = entity.get("_concept", "Unknown")

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
    simulated_data["_concept"] = entity.get("_concept", "Unknown")
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

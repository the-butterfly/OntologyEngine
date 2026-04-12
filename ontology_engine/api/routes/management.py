# ontology_engine/api/routes/management.py
"""Management API routes for semantic spaces.

Prefix: /v1/management/{spaceId}/
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SpaceType,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    SpaceVersion,
    Authorization,
    SemanticSpaceStorage,
    SemanticSpaceStorageError,
)
from ontology_engine.core.dataset import (
    DatasetDeclaration,
    DatasetType,
    SyncMode,
    MappingRule,
    SyncHistory,
    SourceConnection,
    FieldSchema,
    SyncConfig,
    IncrementalConfig,
)

router = APIRouter(prefix="/v1/management", tags=["Management"])


# ============================================================================
# Storage Helper
# ============================================================================

def _get_storage() -> SemanticSpaceStorage:
    return SemanticSpaceStorage()


def _get_space(storage: SemanticSpaceStorage, space_id: str) -> SemanticSpace:
    """Get space or raise 404."""
    space = storage
    return space


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateManagementSpaceRequest(BaseModel):
    name: str
    description: str | None = None
    domain: str | None = None
    create_default_view: bool = True


class UpdateSpaceRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    status: SpaceStatus | None = None


class CreateConsumptionViewRequest(BaseModel):
    name: str
    description: str | None = None
    source_spaces: list[str] | None = None


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
    element_type: str = "derived"
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
    target_objects: list[str] | None = None
    input_elements: list[dict] | None = None
    output_elements: list[dict] | None = None
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


class CreateVersionSnapshotRequest(BaseModel):
    description: str | None = None


class CreateAuthorizationRequest(BaseModel):
    target_view_id: str
    enabled: bool = True
    granted_layers: dict[str, Any] | None = None


class CreateEntityInstanceRequest(BaseModel):
    entity_id: str
    concept: str
    properties: dict | None = None
    relations: list[dict] | None = None


# ============================================================================
# Space Management
# ============================================================================

@router.post("/spaces", response_model=dict)
async def create_space(request: CreateManagementSpaceRequest):
    """Create a new management space."""
    storage = _get_storage()

    space_id = f"space_{uuid.uuid4().hex[:8]}"

    metadata = SpaceMetadata(
        id=space_id,
        name=request.name,
        space_type=SpaceType.MANAGEMENT,
        description=request.description,
        domain=request.domain,
        status=SpaceStatus.DRAFT,
    )

    space = SemanticSpace(
        metadata=metadata,
        layers=SemanticSpaceLayers(
            L1_fact_objects=[],
            L2_categorizations=[],
            L3_analytical_elements=[],
            L4_business_logic=L4BusinessLogic(
                rule_definitions=[],
                rule_logics=[],
            ),
        ),
        instances=SpaceInstances(
            entities=[],
            relations=[],
            category_tags=[],
            metric_values=[],
        ),
        versions=[],
    )

    await storage.save(space)

    # Optionally create default consumption view
    view_id = None
    if request.create_default_view:
        view_id = f"view_{uuid.uuid4().hex[:8]}"
        view_metadata = SpaceMetadata(
            id=view_id,
            name=f"{request.name} (消费视图)",
            space_type=SpaceType.CONSUMPTION,
            description=f"自动创建的消费视图，授权自 {space_id}",
            status=SpaceStatus.DRAFT,
        )
        view_space = SemanticSpace(
            metadata=view_metadata,
            layers=SemanticSpaceLayers(),
            instances=SpaceInstances(),
            versions=[],
        )
        # Create authorization
        auth = Authorization(
            id=f"auth_{uuid.uuid4().hex[:8]}",
            target_view_id=view_id,
            enabled=True,
            granted_layers={
                "L1_fact_objects": {"all": True},
                "L2_categorizations": {"all": True},
                "L3_analytical_elements": {"all": True},
                "L4_business_logic": {"all": True},
            },
        )
        await storage.save(view_space)
        # Update space with view_id
        space.metadata.view_id = view_id
        await storage.save(space)

    return success_response(data={
        "id": space_id,
        "name": request.name,
        "status": SpaceStatus.DRAFT.value,
        "view_id": view_id if request.create_default_view else None,
    })


@router.get("/spaces", response_model=dict)
async def list_spaces():
    """List all management spaces with their associated views."""
    storage = _get_storage()
    all_metadata = await storage.list()

    # Filter only management spaces
    management_spaces = [
        m for m in all_metadata if m.space_type == SpaceType.MANAGEMENT
    ]

    spaces = []
    for metadata in management_spaces:
        space = await storage.load(metadata.id)
        if space:
            # Get view info if exists
            view_info = None
            if space.metadata.view_id:
                view = await storage.load(space.metadata.view_id)
                if view:
                    view_info = {
                        "id": view.metadata.id,
                        "name": view.metadata.name,
                        "status": view.metadata.status.value,
                    }

            spaces.append({
                "id": space.metadata.id,
                "name": space.metadata.name,
                "description": space.metadata.description,
                "status": space.metadata.status.value,
                "version": space.active_version,
                "entity_count": len(space.instances.entities),
                "rule_count": len(space.layers.L4_business_logic.rule_definitions),
                "created_at": space.metadata.created_at.isoformat(),
                "updated_at": space.metadata.updated_at.isoformat(),
                "view_id": space.metadata.view_id,
                "view": view_info,
            })

    return success_response(data=spaces)


@router.get("/spaces/{space_id}", response_model=dict)
async def get_space(space_id: str):
    """Get a management space by ID."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if space.metadata.space_type != SpaceType.MANAGEMENT:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} is not a management space")

    # Get view info if exists
    view_info = None
    if space.metadata.view_id:
        view = await storage.load(space.metadata.view_id)
        if view:
            view_info = {
                "id": view.metadata.id,
                "name": view.metadata.name,
                "status": view.metadata.status.value,
            }

    return success_response(data={
        "id": space.metadata.id,
        "name": space.metadata.name,
        "description": space.metadata.description,
        "domain": space.metadata.domain,
        "status": space.metadata.status.value,
        "space_type": space.metadata.space_type.value,
        "version": space.active_version,
        "entity_count": len(space.instances.entities),
        "relation_count": len(space.instances.relations),
        "rule_definition_count": len(space.layers.L4_business_logic.rule_definitions),
        "rule_logic_count": len(space.layers.L4_business_logic.rule_logics),
        "created_at": space.metadata.created_at.isoformat(),
        "updated_at": space.metadata.updated_at.isoformat(),
        "view_id": space.metadata.view_id,
        "view": view_info,
    })


@router.put("/spaces/{space_id}", response_model=dict)
async def update_space(space_id: str, request: UpdateSpaceRequest):
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

    return success_response(data={
        "id": space.metadata.id,
        "name": space.metadata.name,
        "status": space.metadata.status.value,
    })


@router.post("/spaces/{space_id}/activate", response_model=dict)
async def activate_space(space_id: str):
    """Activate a management space and sync data to consumption view."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if space.metadata.status == SpaceStatus.DRAFT:
        space.metadata.status = SpaceStatus.ACTIVE
    elif space.metadata.status == SpaceStatus.ARCHIVED:
        # Can reactivate from archived
        space.metadata.status = SpaceStatus.ACTIVE

    await storage.save(space)

    # Sync data to consumption view
    view_id = space.metadata.view_id
    if view_id:
        view = await storage.load(view_id)
        if not view:
            # View was deleted, recreate it
            view_id = f"view_{uuid.uuid4().hex[:8]}"
            space.metadata.view_id = view_id
            await storage.save(space)

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
            await storage.save(view)

        # Copy layers from management space to consumption view
        view.layers = SemanticSpaceLayers(
            L1_fact_objects=list(space.layers.L1_fact_objects),
            L2_categorizations=list(space.layers.L2_categorizations),
            L3_analytical_elements=list(space.layers.L3_analytical_elements),
            L4_business_logic=L4BusinessLogic(
                rule_definitions=list(space.layers.L4_business_logic.rule_definitions),
                rule_logics=list(space.layers.L4_business_logic.rule_logics),
            ),
        )
        # Copy instances
        view.instances = SpaceInstances(
            entities=list(space.instances.entities),
            relations=list(space.instances.relations),
            category_tags=list(space.instances.category_tags),
            metric_values=list(space.instances.metric_values),
        )
        # Activate the view as well
        view.metadata.status = SpaceStatus.ACTIVE
        await storage.save(view)

    return success_response(data={"id": space_id, "status": space.metadata.status.value, "view_id": view_id})


@router.post("/spaces/{space_id}/deactivate", response_model=dict)
async def deactivate_space(space_id: str):
    """Deactivate a management space (set to DRAFT) and deactivate its view."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    space.metadata.status = SpaceStatus.DRAFT
    await storage.save(space)

    # Deactivate consumption view if exists
    view_id = space.metadata.view_id
    if view_id:
        view = await storage.load(view_id)
        if view:
            view.metadata.status = SpaceStatus.DRAFT
            await storage.save(view)

    return success_response(data={"id": space_id, "status": space.metadata.status.value, "view_id": view_id})


@router.delete("/spaces/{space_id}", response_model=dict)
async def delete_space(space_id: str):
    """Delete a management space and its associated consumption view."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Delete associated consumption view if exists
    view_id = space.metadata.view_id
    if view_id:
        await storage.delete(view_id)

    # Delete the management space
    await storage.delete(space_id)

    return success_response(data={"deleted": True, "space_id": space_id, "view_id": view_id})


@router.post("/spaces/{space_id}/archive", response_model=dict)
async def archive_space(space_id: str):
    """Archive a management space and deactivate its consumption view."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    space.metadata.status = SpaceStatus.ARCHIVED
    await storage.save(space)

    # Deactivate consumption view if exists
    view_id = space.metadata.view_id
    if view_id:
        view = await storage.load(view_id)
        if view:
            view.metadata.status = SpaceStatus.ARCHIVED
            await storage.save(view)

    return success_response(data={"id": space_id, "status": space.metadata.status.value})


# ============================================================================
# Schema Management - L1 Fact Objects
# ============================================================================

@router.get("/{space_id}/schema/L1/fact-objects", response_model=dict)
async def list_fact_objects(space_id: str):
    """List all fact objects in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L1_fact_objects)


@router.post("/{space_id}/schema/L1/fact-objects", response_model=dict)
async def add_fact_object(space_id: str, request: AddFactObjectRequest):
    """Add a fact object definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Check if already exists
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
    await storage.save(space)

    return success_response(data=fact_object)


# ============================================================================
# Schema Management - L2 Categorizations
# ============================================================================

@router.get("/{space_id}/schema/L2/categorizations", response_model=dict)
async def list_categorizations(space_id: str):
    """List all categorizations in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L2_categorizations)


@router.post("/{space_id}/schema/L2/categorizations", response_model=dict)
async def add_categorization(space_id: str, request: AddCategorizationRequest):
    """Add a categorization definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
    await storage.save(space)

    return success_response(data=categorization)


# ============================================================================
# Schema Management - L3 Analytical Elements
# ============================================================================

@router.get("/{space_id}/schema/L3/analytical-elements", response_model=dict)
async def list_analytical_elements(space_id: str):
    """List all analytical elements in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L3_analytical_elements)


@router.post("/{space_id}/schema/L3/analytical-elements", response_model=dict)
async def add_analytical_element(space_id: str, request: AddAnalyticalElementRequest):
    """Add an analytical element definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_ids = [e.get("id") for e in space.layers.L3_analytical_elements]
    if request.id in existing_ids:
        return error_response(code="CONFLICT", message=f"Analytical element {request.id} already exists")

    element = {
        "id": request.id,
        "name": request.name,
        "element_type": request.element_type,
        "description": request.description,
        "source": request.source,
        "dependencies": request.dependencies or [],
        "overridable": request.overridable,
    }

    space.layers.L3_analytical_elements.append(element)
    await storage.save(space)

    return success_response(data=element)


# ============================================================================
# Schema Management - L4 Rule Definitions
# ============================================================================

@router.get("/{space_id}/schema/L4/rules/definitions", response_model=dict)
async def list_rule_definitions(space_id: str):
    """List all rule definitions in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_definitions)


@router.post("/{space_id}/schema/L4/rules/definitions", response_model=dict)
async def add_rule_definition(space_id: str, request: AddRuleDefinitionRequest):
    """Add a rule definition."""
    storage = _get_storage()
    space = await storage.load(space_id)

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
        "target_objects": request.target_objects or [],
        "input_elements": request.input_elements or [],
        "output_elements": request.output_elements or [],
        "enabled": request.enabled,
        "logic_ids": request.logic_ids or [],
    }

    space.layers.L4_business_logic.rule_definitions.append(definition)
    await storage.save(space)

    return success_response(data=definition)


# ============================================================================
# Schema Management - L4 Rule Logics
# ============================================================================

@router.get("/{space_id}/schema/L4/rules/logics", response_model=dict)
async def list_rule_logics(space_id: str):
    """List all rule logics in a space."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_logics)


@router.post("/{space_id}/schema/L4/rules/logics", response_model=dict)
async def add_rule_logic(space_id: str, request: AddRuleLogicRequest):
    """Add a rule logic."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Verify definition exists
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
    await storage.save(space)

    return success_response(data=logic)


# ============================================================================
# Instance Management
# ============================================================================

@router.get("/{space_id}/instances/entities", response_model=dict)
async def list_entities(
    space_id: str,
    concept: str | None = Query(default=None),
):
    """List all entity instances."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    entities = space.instances.entities
    if concept:
        entities = [e for e in entities if e.get("_concept") == concept]

    return success_response(data=entities)


@router.post("/{space_id}/instances/entities", response_model=dict)
async def add_entity(space_id: str, request: CreateEntityInstanceRequest):
    """Add an entity instance."""
    storage = _get_storage()
    space = await storage.load(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    # Check if already exists
    existing_ids = [e.get("entity_id") for e in space.instances.entities]
    if request.entity_id in existing_ids:
        return error_response(code="CONFLICT", message=f"Entity {request.entity_id} already exists")

    entity = {
        "entity_id": request.entity_id,
        "_concept": request.concept,
        **({"properties": request.properties} if request.properties else {}),
        **({"relations": request.relations} if request.relations else {}),
    }

    space.instances.entities.append(entity)
    await storage.save(space)

    return success_response(data=entity)


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
            "created_at": v.created_at.isoformat(),
            "created_by": v.created_by,
            "change_description": v.change_description,
            "is_stable": v.is_stable,
        }
        for v in space.versions
    ]

    return success_response(data=versions)


@router.post("/{space_id}/versions", response_model=dict)
async def create_snapshot(space_id: str, request: CreateVersionSnapshotRequest):
    """Create a version snapshot."""
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
            "created_at": version.created_at.isoformat(),
        })
    except SemanticSpaceStorageError as e:
        return error_response(code="SNAPSHOT_ERROR", message=str(e))


# ============================================================================
# Authorization Management
# ============================================================================

@router.get("/{space_id}/authorizations", response_model=dict)
async def list_authorizations(space_id: str):
    """List all authorizations for a space."""
    # Placeholder - authorizations stored in space metadata for now
    return success_response(data=[])


@router.post("/{space_id}/authorizations", response_model=dict)
async def create_authorization(space_id: str, request: CreateAuthorizationRequest):
    """Create an authorization."""
    # Placeholder implementation
    return success_response(data={
        "id": f"auth_{uuid.uuid4().hex[:8]}",
        "space_id": space_id,
        "target_view_id": request.target_view_id,
        "enabled": request.enabled,
    })


# ============================================================================
# Dataset Management
# ============================================================================

class CreateDatasetRequest(BaseModel):
    id: str
    name: str
    description: str | None = None
    source_type: DatasetType
    connection: dict | None = None
    schema_fields: list[dict] | None = None
    sync_mode: SyncMode = SyncMode.FULL


class CreateMappingRuleRequest(BaseModel):
    id: str
    target_entity_type: str
    field_mappings: list[dict] | None = None
    filters: list[dict] | None = None


class TriggerSyncRequest(BaseModel):
    mode: SyncMode = SyncMode.FULL
    override_last_sync: str | None = None


# In-memory dataset storage (for demo purposes - replace with proper storage)
_DATASETS: dict[str, DatasetDeclaration] = {}
_SYNC_HISTORY: list[SyncHistory] = []


@router.get("/{space_id}/datasets", response_model=dict)
async def list_datasets(space_id: str):
    """List all datasets for a space."""
    datasets = [d.model_dump() for d in _DATASETS.values() if d.id.startswith(space_id.split("_")[0] + "_") or not space_id]
    return success_response(data=datasets)


@router.post("/{space_id}/datasets", response_model=dict)
async def create_dataset(space_id: str, request: CreateDatasetRequest):
    """Create a new dataset."""
    dataset_id = f"{space_id}_{request.id}"

    source = SourceConnection(type=request.source_type)
    if request.connection:
        for key, value in request.connection.items():
            if hasattr(source, key):
                setattr(source, key, value)

    fields = []
    if request.schema_fields:
        for f in request.schema_fields:
            fields.append(FieldSchema(**f))

    dataset = DatasetDeclaration(
        id=dataset_id,
        name=request.name,
        description=request.description,
        source=source,
        schema_fields=fields,
        sync_config=SyncConfig(mode=request.sync_mode),
    )

    _DATASETS[dataset_id] = dataset

    return success_response(data=dataset.model_dump())


@router.get("/{space_id}/datasets/{dataset_id}", response_model=dict)
async def get_dataset(space_id: str, dataset_id: str):
    """Get a dataset by ID."""
    full_id = f"{space_id}_{dataset_id}" if not dataset_id.startswith(space_id) else dataset_id
    dataset = _DATASETS.get(full_id)

    if not dataset:
        return error_response(code="NOT_FOUND", message=f"Dataset {dataset_id} not found")

    return success_response(data=dataset.model_dump())


@router.delete("/{space_id}/datasets/{dataset_id}", response_model=dict)
async def delete_dataset(space_id: str, dataset_id: str):
    """Delete a dataset."""
    full_id = f"{space_id}_{dataset_id}" if not dataset_id.startswith(space_id) else dataset_id

    if full_id in _DATASETS:
        del _DATASETS[full_id]
        return success_response(data={"deleted": True})

    return error_response(code="NOT_FOUND", message=f"Dataset {dataset_id} not found")


# ============================================================================
# Mapping Rules
# ============================================================================

@router.get("/{space_id}/datasets/{dataset_id}/mappings", response_model=dict)
async def list_mapping_rules(space_id: str, dataset_id: str):
    """List mapping rules for a dataset."""
    full_id = f"{space_id}_{dataset_id}" if not dataset_id.startswith(space_id) else dataset_id
    dataset = _DATASETS.get(full_id)

    if not dataset:
        return error_response(code="NOT_FOUND", message=f"Dataset {dataset_id} not found")

    return success_response(data=[r.model_dump() for r in dataset.mapping_rules])


@router.post("/{space_id}/datasets/{dataset_id}/mappings", response_model=dict)
async def add_mapping_rule(space_id: str, dataset_id: str, request: CreateMappingRuleRequest):
    """Add a mapping rule to a dataset."""
    full_id = f"{space_id}_{dataset_id}" if not dataset_id.startswith(space_id) else dataset_id
    dataset = _DATASETS.get(full_id)

    if not dataset:
        return error_response(code="NOT_FOUND", message=f"Dataset {dataset_id} not found")

    mappings = []
    if request.field_mappings:
        for fm in request.field_mappings:
            mappings.append(FieldMapping(**fm))

    rule = MappingRule(
        id=request.id,
        target_entity_type=request.target_entity_type,
        field_mappings=mappings,
        filters=request.filters or [],
    )

    dataset.mapping_rules.append(rule)

    return success_response(data=rule.model_dump())


# ============================================================================
# Sync
# ============================================================================

@router.post("/{space_id}/datasets/{dataset_id}/sync", response_model=dict)
async def trigger_sync(space_id: str, dataset_id: str, request: TriggerSyncRequest):
    """Trigger a dataset sync."""
    full_id = f"{space_id}_{dataset_id}" if not dataset_id.startswith(space_id) else dataset_id
    dataset = _DATASETS.get(full_id)

    if not dataset:
        return error_response(code="NOT_FOUND", message=f"Dataset {dataset_id} not found")

    # Create sync record
    sync_id = f"sync_{uuid.uuid4().hex[:8]}"
    sync_record = SyncHistory(
        id=sync_id,
        dataset_id=full_id,
        triggered_by="manual",
        started_at=datetime.utcnow(),
        mode=request.mode,
        parameters={"override_last_sync": request.override_last_sync} if request.override_last_sync else None,
        stats={
            "records_read": 0,
            "records_created": 0,
            "records_updated": 0,
            "records_skipped": 0,
        },
        status="running",
    )

    _SYNC_HISTORY.append(sync_record)

    # For demo: simulate completion
    sync_record.completed_at = datetime.utcnow()
    sync_record.status = "success"
    sync_record.stats = {
        "records_read": 100,
        "records_created": 50,
        "records_updated": 30,
        "records_skipped": 20,
    }

    return success_response(data={
        "sync_id": sync_id,
        "status": sync_record.status,
        "started_at": sync_record.started_at.isoformat(),
        "completed_at": sync_record.completed_at.isoformat() if sync_record.completed_at else None,
        "stats": sync_record.stats,
    })


@router.get("/{space_id}/datasets/{dataset_id}/sync/history", response_model=dict)
async def get_sync_history(space_id: str, dataset_id: str):
    """Get sync history for a dataset."""
    full_id = f"{space_id}_{dataset_id}" if not dataset_id.startswith(space_id) else dataset_id

    history = [s.model_dump() for s in _SYNC_HISTORY if s.dataset_id == full_id]

    # Convert datetime to string for JSON serialization
    for h in history:
        if h.get("started_at"):
            h["started_at"] = h["started_at"].isoformat()
        if h.get("completed_at") and h["completed_at"]:
            h["completed_at"] = h["completed_at"].isoformat()

    return success_response(data=history)

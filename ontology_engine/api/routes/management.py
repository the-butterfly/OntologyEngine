# ontology_engine/api/routes/management.py
from __future__ import annotations

import warnings
import uuid
from pathlib import Path
import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, AliasChoices

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.api.dependencies import get_space_service
from ontology_engine.services.types import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SpaceType,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    Authorization,
    SemanticSpaceStorageError,
)

warnings.warn(
    "ontology_engine.api.routes.management is deprecated. "
    "Use ontology_engine.api.routes.spaces instead.",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Management"])


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


class CreateVersionSnapshotRequest(BaseModel):
    description: str | None = None


class CreateEntityInstanceRequest(BaseModel):
    entity_id: str
    fact_object: str = Field(validation_alias=AliasChoices("fact_object", "concept"))
    properties: dict | None = None
    relations: list[dict] | None = None


class LoadFromYamlRequest(BaseModel):
    yaml_path: str
    overwrite: bool = False


class LoadInstancesFromYamlRequest(BaseModel):
    yaml_path: str
    overwrite: bool = False


class LoadSpaceFromJsonRequest(BaseModel):
    json_path: str
    space_id: str | None = None


@router.post("/spaces", response_model=dict)
async def create_space(request: CreateManagementSpaceRequest):
    service = get_space_service()

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

    await service.save_space(space)

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
        _authorization = Authorization(
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
        await service.save_space(view_space)
        space.metadata.view_id = view_id
        await service.save_space(space)

    return success_response(data={
        "id": space_id,
        "name": request.name,
        "status": SpaceStatus.DRAFT.value,
        "view_id": view_id if request.create_default_view else None,
    })


@router.get("/spaces", response_model=dict)
async def list_spaces():
    service = get_space_service()
    all_metadata = await service.list_metadata()

    management_spaces = [
        m for m in all_metadata if m.space_type == SpaceType.MANAGEMENT
    ]

    spaces = []
    for metadata in management_spaces:
        space = await service.get_space(metadata.id)
        if space:
            view_info = None
            if space.metadata.view_id:
                view = await service.get_space(space.metadata.view_id)
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
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if space.metadata.space_type != SpaceType.MANAGEMENT:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} is not a management space")

    view_info = None
    if space.metadata.view_id:
        view = await service.get_space(space.metadata.view_id)
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
    service = get_space_service()
    space = await service.get_space(space_id)

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

    await service.save_space(space)

    return success_response(data={
        "id": space.metadata.id,
        "name": space.metadata.name,
        "status": space.metadata.status.value,
    })


@router.post("/spaces/{space_id}/activate", response_model=dict)
async def activate_space(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    if space.metadata.status == SpaceStatus.DRAFT:
        space.metadata.status = SpaceStatus.ACTIVE
    elif space.metadata.status == SpaceStatus.ARCHIVED:
        space.metadata.status = SpaceStatus.ACTIVE

    await service.save_space(space)

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

    return success_response(data={"id": space_id, "status": space.metadata.status.value, "view_id": view_id})


@router.post("/spaces/{space_id}/deactivate", response_model=dict)
async def deactivate_space(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    space.metadata.status = SpaceStatus.DRAFT
    await service.save_space(space)

    view_id = space.metadata.view_id
    if view_id:
        view = await service.get_space(view_id)
        if view:
            view.metadata.status = SpaceStatus.DRAFT
            await service.save_space(view)

    return success_response(data={"id": space_id, "status": space.metadata.status.value, "view_id": view_id})


@router.delete("/spaces/{space_id}", response_model=dict)
async def delete_space(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    view_id = space.metadata.view_id
    if view_id:
        await service.delete_space(view_id)

    await service.delete_space(space_id)

    return success_response(data={"deleted": True, "space_id": space_id, "view_id": view_id})


@router.post("/spaces/{space_id}/archive", response_model=dict)
async def archive_space(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    space.metadata.status = SpaceStatus.ARCHIVED
    await service.save_space(space)

    view_id = space.metadata.view_id
    if view_id:
        view = await service.get_space(view_id)
        if view:
            view.metadata.status = SpaceStatus.ARCHIVED
            await service.save_space(view)

    return success_response(data={"id": space_id, "status": space.metadata.status.value})


@router.post("/spaces/load-from-json", response_model=dict)
async def load_space_from_json(request: LoadSpaceFromJsonRequest):
    json_path = request.json_path
    full_path = Path(json_path)

    if not full_path.is_absolute():
        if not full_path.exists():
            return error_response(code="FILE_NOT_FOUND", message=f"Space file not found: {json_path}")
    else:
        if not full_path.exists():
            return error_response(code="FILE_NOT_FOUND", message=f"Space file not found: {json_path}")

    try:
        service = get_space_service()
        space = service.load_space_from_file(str(full_path))
    except Exception as e:
        return error_response(code="SPACE_LOAD_ERROR", message=f"Failed to load space: {str(e)}")

    if request.space_id:
        space.metadata.id = request.space_id

    space.metadata.space_type = SpaceType.MANAGEMENT

    existing = await service.get_space(space.metadata.id)
    if existing:
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


@router.get("/spaces/{space_id}/schema/L1/fact-objects", response_model=dict)
async def list_fact_objects(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L1_fact_objects)


@router.post("/spaces/{space_id}/schema/L1/fact-objects", response_model=dict)
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


@router.get("/spaces/{space_id}/schema/L2/categorizations", response_model=dict)
async def list_categorizations(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L2_categorizations)


@router.post("/spaces/{space_id}/schema/L2/categorizations", response_model=dict)
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


@router.get("/spaces/{space_id}/schema/L3/analytical-elements", response_model=dict)
async def list_analytical_elements(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L3_analytical_elements)


@router.post("/spaces/{space_id}/schema/L3/analytical-elements", response_model=dict)
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


@router.get("/spaces/{space_id}/schema/L4/rules/definitions", response_model=dict)
async def list_rule_definitions(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_definitions)


@router.post("/spaces/{space_id}/schema/L4/rules/definitions", response_model=dict)
async def add_rule_definition(space_id: str, request: AddRuleDefinitionRequest):
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


@router.get("/spaces/{space_id}/schema/L4/rules/definitions/{rule_id}", response_model=dict)
async def get_rule_definition(space_id: str, rule_id: str):
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


@router.put("/spaces/{space_id}/schema/L4/rules/definitions/{rule_id}", response_model=dict)
async def update_rule_definition(space_id: str, rule_id: str, request: AddRuleDefinitionRequest):
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


@router.delete("/spaces/{space_id}/schema/L4/rules/definitions/{rule_id}", response_model=dict)
async def delete_rule_definition(space_id: str, rule_id: str):
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


@router.get("/spaces/{space_id}/schema/L4/rules/logics", response_model=dict)
async def list_rule_logics(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.layers.L4_business_logic.rule_logics)


@router.post("/spaces/{space_id}/schema/L4/rules/logics", response_model=dict)
async def add_rule_logic(space_id: str, request: AddRuleLogicRequest):
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


@router.get("/spaces/{space_id}/schema/L4/rules/logics/{logic_id}", response_model=dict)
async def get_rule_logic(space_id: str, logic_id: str):
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


@router.put("/spaces/{space_id}/schema/L4/rules/logics/{logic_id}", response_model=dict)
async def update_rule_logic(space_id: str, logic_id: str, request: AddRuleLogicRequest):
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


@router.delete("/spaces/{space_id}/schema/L4/rules/logics/{logic_id}", response_model=dict)
async def delete_rule_logic(space_id: str, logic_id: str):
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


@router.get("/spaces/{space_id}/instances/entities", response_model=dict)
async def list_entities(
    space_id: str,
    concept: str | None = Query(default=None),
):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    entities = space.instances.entities
    if concept:
        entities = [e for e in entities if e.get("_fact_object") == concept or e.get("_concept") == concept]

    return success_response(data=entities)


@router.post("/spaces/{space_id}/instances/entities", response_model=dict)
async def add_entity(space_id: str, request: CreateEntityInstanceRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    existing_ids = [e.get("entity_id") for e in space.instances.entities]
    if request.entity_id in existing_ids:
        return error_response(code="CONFLICT", message=f"Entity {request.entity_id} already exists")

    entity = {
        "entity_id": request.entity_id,
        "_fact_object": request.fact_object,
        **({"properties": request.properties} if request.properties else {}),
        **({"relations": request.relations} if request.relations else {}),
    }

    space.instances.entities.append(entity)
    await service.save_space(space)

    return success_response(data=entity)


@router.get("/spaces/{space_id}/versions", response_model=dict)
async def list_versions(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

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


@router.post("/spaces/{space_id}/versions", response_model=dict)
async def create_snapshot(space_id: str, request: CreateVersionSnapshotRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    try:
        version = await service.create_snapshot_with_space(
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


@router.post("/spaces/{space_id}/versions/{version}/rollback", response_model=dict)
async def rollback_to_version(space_id: str, version: int):
    service = get_space_service()

    try:
        space = await service.get_space(space_id)
        if not space:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

        restored = await service.rollback_to_version(space_id, version, space)

        if not restored:
            return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

        return success_response(data={"status": "restored", "version": version})
    except SemanticSpaceStorageError as e:
        return error_response(code="ROLLBACK_ERROR", message=str(e))


@router.post("/spaces/{space_id}/schema/load-yaml", response_model=dict)
async def load_schema_from_yaml(space_id: str, request: LoadFromYamlRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    yaml_path = request.yaml_path
    if not Path(yaml_path).is_absolute():
        full_path = Path(yaml_path)
        if not full_path.exists():
            return error_response(code="FILE_NOT_FOUND", message=f"Schema file not found: {yaml_path}")
    else:
        full_path = Path(yaml_path)
        if not full_path.exists():
            return error_response(code="FILE_NOT_FOUND", message=f"Schema file not found: {yaml_path}")

    try:
        schema = service.load_schema_from_file(str(full_path))
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


@router.post("/spaces/{space_id}/instances/load-yaml", response_model=dict)
async def load_instances_from_yaml(space_id: str, request: LoadInstancesFromYamlRequest):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    yaml_path = request.yaml_path
    full_path = Path(yaml_path)
    if not full_path.exists():
        return error_response(code="FILE_NOT_FOUND", message=f"Instances file not found: {yaml_path}")

    try:
        entities, relations = service.load_instances_from_file(str(full_path))
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


@router.get("/spaces/{space_id}/instances/relations", response_model=dict)
async def list_relations(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    return success_response(data=space.instances.relations)


@router.post("/spaces/{space_id}/instances/relations", response_model=dict)
async def add_relation(space_id: str, relation: dict):
    service = get_space_service()
    space = await service.get_space(space_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")

    space.instances.relations.append(relation)
    await service.save_space(space)

    return success_response(data=relation)


@router.get("/spaces/{space_id}/schema", response_model=dict)
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


@router.get("/spaces/{space_id}/schema/L2/categorizations", response_model=dict)
async def list_categorizations_v2(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")
    return success_response(data=space.layers.L2_categorizations)


@router.get("/spaces/{space_id}/schema/L3/analytical-elements", response_model=dict)
async def list_analytical_elements_v2(space_id: str):
    service = get_space_service()
    space = await service.get_space(space_id)
    if not space:
        return error_response(code="NOT_FOUND", message=f"Space {space_id} not found")
    return success_response(data=space.layers.L3_analytical_elements)


def _rule_inputs(rule: dict) -> list[dict]:
    return rule.get("inputs") or rule.get("input_elements") or []


def _rule_outputs(rule: dict) -> list[dict]:
    return rule.get("outputs") or rule.get("output_elements") or []


def _rule_applies_to(rule: dict) -> list[str]:
    return rule.get("applies_to") or rule.get("target_objects") or []


@router.get("/spaces/{space_id}/schema/L4/rules/dependency-graph", response_model=dict)
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
            "applies_to": _rule_applies_to(rule),
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
            targets_a = set(_rule_applies_to(rule_a))
            targets_b = set(_rule_applies_to(rule_b))
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

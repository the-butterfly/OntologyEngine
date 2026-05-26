"""P2 MCP tools — oe_define_rule, oe_create_entity, oe_activate_space, oe_update_relation."""

from typing import Any

from ontology_engine.mcp import mcp_response, get_service


async def oe_create_entity(
    space_id: str,
    entity_id: str,
    fact_object: str,
    attributes: dict | None = None,
) -> dict:
    """Create a new entity in a semantic space.

    Adds an entity instance to the space. The entity must reference a valid
    fact_object type defined in the space's L1 schema layer.

    Parameters:
        space_id: Space ID (e.g., "space_supply_chain_finance")
        entity_id: Unique entity ID (e.g., "SUP_C1")
        fact_object: Fact object type from L1 schema (e.g., "Supplier")
        attributes: Optional entity attributes as key-value pairs

    Returns:
        MCP unified format: {success, data, error}
        data contains: entity_id, fact_object, space_id
    """
    try:
        space_service = get_service("space")
        result = await space_service.add_entity(
            space_id=space_id,
            entity_id=entity_id,
            fact_object=fact_object,
            attributes=attributes,
        )
        if not result:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{space_id}' not found or entity '{entity_id}' already exists",
                    "suggestion": "Use oe_list_spaces to find available spaces",
                },
            )
        return mcp_response(success=True, data=result)
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


async def oe_update_relation(
    space_id: str,
    relation_id: str,
    attributes: dict[str, Any] | None = None,
    reason: str = "",
) -> dict:
    try:
        space_service = get_service("space")
        space = await space_service.get_space(space_id)
        if not space:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{space_id}' not found",
                },
            )
        target_rel: dict[str, Any] | None = None
        for rel in space.instances.relations:
            if rel.get("id") == relation_id:
                target_rel = rel
                break
        if not target_rel:
            return mcp_response(
                success=False,
                error={
                    "code": "RELATION_NOT_FOUND",
                    "message": f"Relation '{relation_id}' not found in space '{space_id}'",
                },
            )
        if target_rel.get("_cognitive_node_id"):
            try:
                memory_service = get_service("memory")
            except (RuntimeError, KeyError):
                memory_service = None
            if memory_service:
                result = await memory_service.correct_node(
                    space_id=space_id,
                    node_id=target_rel["_cognitive_node_id"],
                    corrected_text=str(attributes or ""),
                    reason=reason or "MCP oe_update_relation",
                )
                return mcp_response(
                    success=True,
                    data={
                        "relation_id": relation_id,
                        "cognitive_node_updated": True,
                        "result": result,
                    },
                )
        attrs = attributes or {}
        result = await space_service.update_relation_in_space(
            space_id, relation_id, attrs, reason=reason
        )
        if not result or result.get("not_found"):
            return mcp_response(
                success=False,
                error={
                    "code": "UPDATE_FAILED",
                    "message": f"Failed to update relation '{relation_id}'",
                },
            )
        return mcp_response(success=True, data=result)
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


async def oe_define_rule(
    space_id: str,
    rule_id: str,
    name: str,
    dimension: str = "credit_assessment",
    applies_to: list[str] | None = None,
    description: str | None = None,
) -> dict:
    """Define a new rule declaration in the space's L4 schema layer.

    Creates a rule definition that can later have rule logic attached via
    oe_attach_rule_logic. Rules are organized by analysis dimension.

    Parameters:
        space_id: Space ID (e.g., "space_supply_chain_finance")
        rule_id: Unique rule ID (e.g., "rule_credit_score")
        name: Human-readable rule name (e.g., "Credit Score Check")
        dimension: Analysis dimension this rule belongs to (e.g., "credit_assessment")
        applies_to: List of fact_object types this rule applies to (e.g., ["Supplier"])
        description: Rule description

    Returns:
        MCP unified format: {success, data, error}
        data contains: rule_id, name, dimension, applies_to, space_id
    """
    try:
        space_service = get_service("space")
        result = await space_service.define_rule(
            space_id=space_id,
            rule_id=rule_id,
            name=name,
            dimension=dimension,
            applies_to=applies_to,
            description=description,
        )
        if not result:
            return mcp_response(
                success=False,
                error={
                    "code": "DUPLICATE_RULE_ID",
                    "message": f"Rule definition '{rule_id}' already exists or space '{space_id}' not found",
                    "suggestion": "Use a different rule_id or update the existing rule",
                },
            )
        return mcp_response(success=True, data=result)
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


async def oe_activate_space(
    space_id: str,
) -> dict:
    """Activate a semantic space, transitioning it from DRAFT to ACTIVE.

    An active space creates a consumption view that can be used for
    analysis and simulation. The space must have a schema loaded before
    activation.

    Parameters:
        space_id: Space ID to activate (e.g., "space_supply_chain_finance")

    Returns:
        MCP unified format: {success, data, error}
        data contains: space_id, status, active_version
    """
    try:
        space_service = get_service("space")
        result = await space_service.activate_space(space_id)
        if not result:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{space_id}' not found",
                    "suggestion": "Use oe_list_spaces to find available spaces",
                },
            )
        if result.get("no_rules"):
            return mcp_response(
                success=False,
                error={
                    "code": "SCHEMA_NOT_LOADED",
                    "message": f"Space '{space_id}' has no rule definitions. Load schema first.",
                    "suggestion": "Use oe_load_schema to check schema status, then load via API POST /v1/spaces/{id}/schema/load-yaml",
                },
            )
        if result.get("already_active"):
            return mcp_response(
                success=True,
                data={
                    "space_id": space_id,
                    "status": "ACTIVE",
                    "active_version": result["active_version"],
                    "note": "Space was already active",
                },
            )
        return mcp_response(success=True, data=result)
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )

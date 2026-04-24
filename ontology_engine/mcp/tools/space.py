"""Space management MCP tools."""

from ontology_engine.mcp import mcp_response, get_service


async def oe_create_space(
    name: str,
    description: str | None = None,
    domain: str | None = None,
) -> dict:
    """Create a new semantic space.

    Creates a semantic space in DRAFT status. After creation, load a schema
    via oe_load_schema and activate via oe_activate_space before running analysis.

    Parameters:
        name: Space name (e.g., "Supply Chain Finance")
        description: Space description
        domain: Business domain (e.g., "finance", "compliance")

    Returns:
        MCP unified format: {success, data, error}
        data contains: space_id, name, description, domain, status
    """
    try:
        space_service = get_service("space")
        result = await space_service.create_space(
            name=name, description=description, domain=domain,
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


async def oe_list_spaces() -> dict:
    """List all semantic spaces.

    Returns a summary of all spaces including their IDs, names, statuses,
    and entity counts. Use this to discover available spaces before
    calling other tools.

    Returns:
        MCP unified format: {success, data, error}
        data contains: spaces (list of {space_id, name, status, domain})
    """
    try:
        space_service = get_service("space")
        spaces = await space_service.list_spaces()
        return mcp_response(success=True, data={"spaces": spaces, "total": len(spaces)})
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


async def oe_load_schema(space_id: str) -> dict:
    """Load schema overview for a semantic space.

    Returns a summary of all four schema layers (L1-L4) including
    fact object counts, categorization dimensions, analytical metrics,
    and rule definitions.

    Parameters:
        space_id: Space ID (e.g., "space_supply_chain_finance")

    Returns:
        MCP unified format: {success, data, error}
        data contains: space_id, name, active_version, layers (L1-L4 summaries)
    """
    try:
        space_service = get_service("space")
        result = await space_service.get_schema_overview(space_id)
        if not result:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{space_id}' not found",
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

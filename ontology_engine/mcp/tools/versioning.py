"""Versioning MCP tools — oe_snapshot and oe_rollback."""

from ontology_engine.mcp import mcp_response, get_service


async def oe_snapshot(
    space_id: str,
    description: str | None = None,
) -> dict:
    """Create a versioned snapshot of a semantic space.

    Snapshots enable rollback to previous states. Use oe_rollback to
    restore a previous snapshot. Create snapshots before making risky
    changes to rules or entities.

    Parameters:
        space_id: Space ID to snapshot (e.g., "space_supply_chain_finance")
        description: Snapshot description (e.g., "Before rule change")

    Returns:
        MCP unified format: {success, data, error}
        data contains: space_id, version, description, is_stable
    """
    try:
        space_service = get_service("space")
        result = await space_service.create_snapshot(
            space_id=space_id, description=description,
        )
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
            error={"code": "SNAPSHOT_ERROR", "message": str(e)},
        )


async def oe_rollback(
    space_id: str,
    target_version: int,
    dry_run: bool = False,
) -> dict:
    """Rollback a semantic space to a previous version.

    Set dry_run=true to preview the rollback impact without applying changes.
    Use oe_snapshot to create version checkpoints before risky changes.

    Parameters:
        space_id: Space ID to rollback (e.g., "space_supply_chain_finance")
        target_version: Target version number to rollback to
        dry_run: If true, preview rollback impact without applying

    Returns:
        MCP unified format: {success, data, error}
        data contains: space_id, active_version, status (or dry_run preview)
    """
    try:
        space_service = get_service("space")
        result = await space_service.rollback_space(
            space_id=space_id, target_version=target_version, dry_run=dry_run,
        )
        if not result:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{space_id}' not found or version {target_version} does not exist",
                    "suggestion": "Use oe_load_schema to check available versions",
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
            error={"code": "ROLLBACK_ERROR", "message": str(e)},
        )

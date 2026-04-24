"""Dataset MCP tools."""

from ontology_engine.mcp import mcp_response, get_service

_VALID_SOURCE_TYPES = {"manual", "csv", "api", "database"}
_VALID_SYNC_MODES = {"full", "incremental"}


async def oe_register_dataset(
    space_id: str,
    name: str,
    source_type: str = "manual",
    description: str | None = None,
) -> dict:
    """Register a dataset within a semantic space.

    Creates a new dataset in the specified space. After registration,
    use oe_trigger_sync to synchronize entities from the dataset into the space.

    Parameters:
        space_id: Space ID to register the dataset under (e.g., "space_supply_chain_finance")
        name: Dataset name (e.g., "Q1 Financial Data")
        source_type: Data source type. Options: "manual", "csv", "api", "database"
        description: Dataset description

    Returns:
        MCP unified format: {success, data, error}
        data contains: dataset_id, name, scope, source_type
    """
    if source_type not in _VALID_SOURCE_TYPES:
        return mcp_response(
            success=False,
            error={
                "code": "INVALID_SOURCE_TYPE",
                "message": f"Invalid source_type: '{source_type}'",
                "suggestion": f"Use one of: {', '.join(sorted(_VALID_SOURCE_TYPES))}",
            },
        )

    try:
        service = get_service("dataset")
        result = await service.create_dataset(
            name=name,
            scope={"space_id": space_id},
            source_type=source_type,
            description=description,
        )
        return mcp_response(success=True, data=result)
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except KeyError as e:
        return mcp_response(
            success=False,
            error={"code": "SERVICE_NOT_FOUND", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )


async def oe_trigger_sync(
    dataset_id: str,
    space_id: str,
    mode: str = "full",
) -> dict:
    """Trigger entity synchronization from a dataset to a space.

    Synchronizes entities from the specified dataset into the semantic space.
    Use mode="incremental" for partial syncs or mode="full" for complete syncs.

    Parameters:
        dataset_id: Dataset ID to sync from (e.g., "ds_abc123")
        space_id: Target space ID (e.g., "space_supply_chain_finance")
        mode: Sync mode. Options: "full" (replace all), "incremental" (add only new)

    Returns:
        MCP unified format: {success, data, error}
        data contains: dataset_id, space_id, synced_count, mode
    """
    if mode not in _VALID_SYNC_MODES:
        return mcp_response(
            success=False,
            error={
                "code": "INVALID_SYNC_MODE",
                "message": f"Invalid sync mode: '{mode}'",
                "suggestion": f"Use one of: {', '.join(sorted(_VALID_SYNC_MODES))}",
            },
        )

    try:
        service = get_service("dataset")

        dataset = await service.get_dataset(dataset_id)
        if not dataset:
            return mcp_response(
                success=False,
                error={
                    "code": "DATASET_NOT_FOUND",
                    "message": f"Dataset '{dataset_id}' not found",
                    "suggestion": "Use oe_register_dataset to create a dataset first",
                },
            )

        entities = await service.get_dataset_entities(dataset_id)
        count = await service.add_entities(
            dataset_id=dataset_id,
            entities=entities,
        )

        return mcp_response(
            success=True,
            data={
                "dataset_id": dataset_id,
                "space_id": space_id,
                "synced_count": count,
                "mode": mode,
            },
        )
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except KeyError as e:
        return mcp_response(
            success=False,
            error={"code": "SERVICE_NOT_FOUND", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": str(e)},
        )

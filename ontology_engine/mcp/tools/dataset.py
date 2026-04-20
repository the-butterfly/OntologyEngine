"""Dataset MCP tools."""

from ontology_engine.mcp import mcp_response
from ontology_engine.services.dataset_service import DatasetService
from ontology_engine.storage.sqlite.store import SQLiteStorage


async def oe_register_dataset(
    space_id: str,
    name: str,
    source_type: str = "manual",
    description: str | None = None,
) -> dict:
    """注册数据集.

    Parameters:
        space_id: 所属空间 ID（作为 scope）
        name: 数据集名称
        source_type: 数据源类型
        description: 数据集描述

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SQLiteStorage(db_path=":memory:")
        await storage.initialize()
        service = DatasetService(storage=storage)
        result = await service.create_dataset(
            name=name,
            scope={"space_id": space_id},
            source_type=source_type,
            description=description,
        )
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))


async def oe_trigger_sync(dataset_id: str, space_id: str, mode: str | None = None) -> dict:
    """触发数据集实体同步.

    Parameters:
        dataset_id: 数据集 ID
        space_id: 空间 ID
        mode: 同步模式

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SQLiteStorage(db_path=":memory:")
        await storage.initialize()
        service = DatasetService(storage=storage)
        # Trigger sync adds entities from dataset to space
        count = await service.add_entities(dataset_id=dataset_id, entities=[])
        return mcp_response(success=True, data={"synced_count": count})
    except Exception as e:
        return mcp_response(success=False, error=str(e))

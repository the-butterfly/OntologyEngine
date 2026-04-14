"""Space management MCP tools."""

import uuid

from ontology_engine.mcp import mcp_response
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SemanticSpaceLayers,
    SpaceInstances,
    L4BusinessLogic,
    SpaceMetadata,
    SpaceStatus,
    SemanticSpaceStorage,
)


async def oe_create_space(
    name: str,
    description: str | None = None,
    domain: str | None = None,
) -> dict:
    """创建语义空间（Semantic Space）.

    Parameters:
        name: 空间名称
        description: 空间描述
        domain: 业务领域

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SemanticSpaceStorage()
        space_id = f"space_{uuid.uuid4().hex[:8]}"

        metadata = SpaceMetadata(
            id=space_id,
            name=name,
            description=description,
            domain=domain,
            status=SpaceStatus.DRAFT,
        )

        space = SemanticSpace(
            metadata=metadata,
            layers=SemanticSpaceLayers(L4_business_logic=L4BusinessLogic()),
            instances=SpaceInstances(),
        )

        await storage.save(space)
        loaded = await storage.load(space_id)
        if not loaded:
            return mcp_response(success=False, error="Failed to load created space")

        return mcp_response(
            success=True,
            data={
                "space_id": loaded.metadata.id,
                "name": loaded.metadata.name,
                "description": loaded.metadata.description,
                "domain": loaded.metadata.domain,
                "status": loaded.metadata.status.value,
            },
        )
    except Exception as e:
        return mcp_response(success=False, error=str(e))


async def oe_load_schema(space_id: str) -> dict:
    """加载语义空间的 Schema.

    Parameters:
        space_id: 空间 ID

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SemanticSpaceStorage()
        space = await storage.load(space_id)
        if not space:
            return mcp_response(success=False, error=f"Space {space_id} not found")

        return mcp_response(
            success=True,
            data={
                "space_id": space.metadata.id,
                "name": space.metadata.name,
                "active_version": space.active_version,
                "layers": {
                    "L4": {
                        "rule_definitions": len(space.layers.L4_business_logic.rule_definitions),
                        "rule_logics": len(space.layers.L4_business_logic.rule_logics),
                    }
                },
            },
        )
    except Exception as e:
        return mcp_response(success=False, error=str(e))

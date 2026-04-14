"""Execution MCP tools — oe_execute_rule and oe_simulate."""

import asyncio

from ontology_engine.mcp import mcp_response
from ontology_engine.core.semantic_space import SemanticSpaceStorage


async def oe_execute_rule(
    entity_id: str,
    view_id: str,
    dimension: str | None = None,
    explain_level: str = "brief",
) -> dict[str, object]:
    """对实体执行规则分析.

    Parameters:
        entity_id: 实体 ID
        view_id: 视图/空间 ID
        dimension: 分析维度（如 "credit_assessment"）
        explain_level: 解释级别 (full|detailed|brief)

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SemanticSpaceStorage()
        space = await storage.load(view_id)
        if not space:
            return mcp_response(success=False, error=f"Space {view_id} not found")

        entity = next(
            (e for e in space.instances.entities if e.get("entity_id") == entity_id),
            None,
        )
        if not entity:
            return mcp_response(success=False, error=f"Entity {entity_id} not found in space {view_id}")

        # Import the analysis function from consumption routes
        from ontology_engine.api.routes.consumption import _run_full_analysis

        result = await _run_full_analysis(
            space=space,
            entity=entity,
            dimension=dimension or "credit_assessment",
            overrides={},
            include_trace=(explain_level != "brief"),
        )
        return mcp_response(success=True, data=result)
    except Exception as e:
        return mcp_response(success=False, error=str(e))


async def oe_simulate(
    entity_id: str,
    view_id: str,
    dimension: str | None = None,
    overrides: dict | None = None,
) -> dict:
    """模拟规则执行（假设数据覆盖）.

    Parameters:
        entity_id: 实体 ID
        view_id: 视图/空间 ID
        dimension: 分析维度
        overrides: 字段覆盖值

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SemanticSpaceStorage()
        space = await storage.load(view_id)
        if not space:
            return mcp_response(success=False, error=f"Space {view_id} not found")

        entity = next(
            (e for e in space.instances.entities if e.get("entity_id") == entity_id),
            None,
        )
        if not entity:
            return mcp_response(success=False, error=f"Entity {entity_id} not found in space {view_id}")

        from ontology_engine.api.routes.consumption import _run_full_analysis

        dim = dimension or "credit_assessment"
        # Run baseline and simulated concurrently
        baseline, simulated = await asyncio.gather(
            _run_full_analysis(space=space, entity=entity, dimension=dim, overrides={}, include_trace=False),
            _run_full_analysis(space=space, entity=entity, dimension=dim, overrides=overrides or {}, include_trace=False),
        )

        return mcp_response(
            success=True,
            data={
                "baseline": baseline,
                "simulated": simulated,
                "overrides_applied": overrides or {},
            },
        )
    except Exception as e:
        return mcp_response(success=False, error=str(e))

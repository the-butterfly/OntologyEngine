"""Query MCP tools — oe_query."""

from ontology_engine.mcp import mcp_response
from ontology_engine.services.query_service import QueryService
from ontology_engine.storage.sqlite.store import SQLiteStorage


async def oe_query(
    query: str,
    match_mode: str,
    top_k: int = 10,
) -> dict:
    """知识检索查询.

    Parameters:
        query: 查询文本
        match_mode: 匹配模式 (vector|keyword|hybrid|graph|pattern)
        top_k: 返回结果数量

    Returns:
        MCP 统一格式: {success, data, error}
    """
    try:
        storage = SQLiteStorage(db_path=":memory:")
        await storage.initialize()
        service = QueryService(storage=storage)

        if match_mode == "graph":
            # graph mode needs entity_id as start node - not yet supported
            results = []
        elif match_mode in ("vector", "keyword", "hybrid", "pattern"):
            results = await service.pattern_match(concept="", patterns={"text": query})
        else:
            return mcp_response(success=False, error=f"Unknown match_mode: {match_mode}")

        return mcp_response(
            success=True,
            data={
                "results": [
                    {
                        "entity_id": r.entity_id,
                        "fact_object": r.fact_object,
                        "score": r.score,
                        "attributes": r.attributes,
                    }
                    for r in results[:top_k]
                ],
                "match_mode": match_mode,
                "query": query,
            },
        )
    except Exception as e:
        return mcp_response(success=False, error=str(e))

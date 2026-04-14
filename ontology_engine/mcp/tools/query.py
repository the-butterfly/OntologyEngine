"""Query MCP tools — oe_query."""

from ontology_engine.mcp import mcp_response
from ontology_engine.services.query_service import QueryService
from ontology_engine.storage.duckdb.store import DuckDBStorage


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
        storage = DuckDBStorage(db_path=":memory:")
        await storage.initialize()
        service = QueryService(storage=storage)

        if match_mode == "vector":
            results = await service.pattern_match(concept="", patterns={"text": query})
        elif match_mode == "keyword":
            results = await service.pattern_match(concept="", patterns={"text": query})
        elif match_mode == "hybrid":
            results = await service.pattern_match(concept="", patterns={"text": query})
        elif match_mode == "graph":
            # graph mode needs entity_id as start node
            results = []
        elif match_mode == "pattern":
            results = await service.pattern_match(concept="", patterns={"text": query})
        else:
            return mcp_response(success=False, error=f"Unknown match_mode: {match_mode}")

        return mcp_response(
            success=True,
            data={
                "results": [
                    {
                        "entity_id": r.entity_id,
                        "concept_type": r.concept_type,
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

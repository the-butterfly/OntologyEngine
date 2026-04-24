"""Query MCP tools — oe_query."""

from ontology_engine.mcp import mcp_response, get_service


async def oe_query(
    query: str,
    match_mode: str = "hybrid",
    top_k: int = 10,
) -> dict:
    """Knowledge retrieval query across semantic spaces.

    Searches for entities and relations using the specified match mode.
    Use "hybrid" for best results combining vector similarity and keyword matching.

    Parameters:
        query: Search text (e.g., "high risk suppliers with guarantee chains")
        match_mode: Search strategy. Options: "vector" (semantic similarity),
                    "keyword" (exact text match), "hybrid" (combined, recommended),
                    "pattern" (attribute pattern match)
        top_k: Maximum number of results to return

    Returns:
        MCP unified format: {success, data, error}
        data contains: results (list of {entity_id, fact_object, score, attributes}),
                       match_mode, query, total_count
    """
    try:
        service = get_service("query")

        if match_mode == "pattern":
            results = await service.pattern_match(
                concept="",
                patterns={"text": query},
            )
        elif match_mode in ("vector", "keyword", "hybrid"):
            try:
                if match_mode == "vector":
                    search_results = await service.semantic_search(
                        query_text=query,
                        top_k=top_k,
                    )
                elif match_mode == "hybrid":
                    search_results = await service.hybrid_search(
                        query_text=query,
                        top_k=top_k,
                    )
                else:
                    results = await service.pattern_match(
                        concept="",
                        patterns={"text": query},
                    )
                    search_results = None

                if search_results is not None:
                    if hasattr(search_results, "results"):
                        results = search_results.results
                    elif isinstance(search_results, list):
                        results = search_results
                    else:
                        results = []
            except NotImplementedError:
                results = await service.pattern_match(
                    concept="",
                    patterns={"text": query},
                )
        else:
            return mcp_response(
                success=False,
                error={
                    "code": "INVALID_MATCH_MODE",
                    "message": f"Unknown match_mode: '{match_mode}'",
                    "suggestion": "Use one of: vector, keyword, hybrid, pattern",
                },
            )

        serialized = []
        for r in results[:top_k]:
            if hasattr(r, "to_dict") and callable(r.to_dict):
                serialized.append(r.to_dict())
            elif hasattr(r, "entity_id"):
                serialized.append({
                    "entity_id": r.entity_id,
                    "fact_object": getattr(r, "fact_object", ""),
                    "score": getattr(r, "score", 0.0),
                    "attributes": getattr(r, "attributes", {}),
                })
            elif isinstance(r, dict):
                serialized.append(r)

        return mcp_response(
            success=True,
            data={
                "results": serialized,
                "match_mode": match_mode,
                "query": query,
                "total_count": len(serialized),
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
            error={"code": "QUERY_ERROR", "message": str(e)},
        )

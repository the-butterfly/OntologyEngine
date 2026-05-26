# ontology_engine/api/routes/query.py
"""Query endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ontology_engine.api.dependencies import get_query_service
from ontology_engine.api.dto.responses import success_response, error_response
from ontology_engine.api.dto.requests import VectorSearchRequest, HybridSearchRequest, GraphQueryRequest
from ontology_engine.services.query_service import QueryService

router = APIRouter(prefix="/v1/query", tags=["Query"])


class SearchRequest(BaseModel):
    """Request body for semantic search."""
    text: str
    fact_object: str | None = None
    top_k: int = 10
    filters: dict[str, Any] | None = None


class PatternMatchRequest(BaseModel):
    """Request body for pattern match."""
    concept: str
    patterns: dict[str, Any] | None = None


class TraverseRequest(BaseModel):
    """Request body for graph traverse."""
    relation_name: str = ""
    direction: str = "outgoing"
    depth: int = 1
    as_of: datetime | None = None
    include_history: bool = False


class PathQueryRequest(BaseModel):
    """Request body for path finding."""
    from_entity_id: str
    to_entity_id: str
    max_depth: int = 3


@router.post("/search")
async def semantic_search(
    body: SearchRequest,
    service: QueryService = Depends(get_query_service)
):
    """Semantic search for entities.

    Uses vector similarity to find entities matching the query text.
    Requires a configured vector store (ChromaDB or LocalVectorStore).

    Args:
        body: Search request with text query, optional filters and top_k

    Returns:
        Search results with relevance scores
    """
    try:
        results = await service.semantic_search(
            query_text=body.text,
            top_k=body.top_k,
            fact_object=body.fact_object,
        )
        formatted = [
            {
                "entity_id": r.id,
                "concept_type": r.metadata.get("_fact_object", r.metadata.get("concept", "")),
                "relevance_score": r.score,
                "attributes": r.metadata,
            }
            for r in results
        ]
        return success_response(data={
            "results": formatted,
            "total": len(formatted),
            "query_type": "semantic",
        })
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/vector", deprecated=True)
async def vector_search(
    body: VectorSearchRequest,
    service: QueryService = Depends(get_query_service)
):
    """Vector search for entities.

    Args:
        body: Vector search request with text query

    Returns:
        List of matching SearchResultResponse
    """
    try:
        results = await service.pattern_match(
            concept=body.fact_object or "",
            patterns={"text": body.text}
        )
        return success_response(data={"results": results})
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/hybrid")
async def hybrid_search(
    body: HybridSearchRequest,
    service: QueryService = Depends(get_query_service)
):
    """Hybrid search combining text and filters.

    Args:
        body: Hybrid search request

    Returns:
        List of matching SearchResultResponse
    """
    try:
        filters = body.filters or {}
        if body.query:
            filters["text"] = body.query
        results = await service.pattern_match(
            concept=body.fact_object or "",
            patterns=filters
        )
        return success_response(data={"results": results})
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/graph")
async def graph_query(
    body: GraphQueryRequest,
    service: QueryService = Depends(get_query_service)
):
    """Graph traversal query.

    Args:
        body: Graph query request with start node and traversal spec

    Returns:
        List of traversed entities
    """
    try:
        # Extract start entity from body.start
        start_entity = body.start.get("entity_id")
        if not start_entity:
            return error_response(
                code="INVALID_REQUEST",
                message="start.entity_id is required"
            )

        # Extract traversal params
        traverse = body.traverse[0] if body.traverse else {}
        relation_name = traverse.get("relation_name") or traverse.get("relation_type", "")
        direction = traverse.get("direction", "outgoing")
        depth = traverse.get("max_hops", 1)

        results = await service.graph_traverse(
            entity_id=start_entity,
            relation_type=relation_name,
            direction=direction,
            depth=depth,
            as_of=body.as_of,
            include_history=body.include_history,
        )
        return success_response(data={"results": results})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


# Keep GET endpoints for backward compatibility
@router.get("/pattern-match/{concept}", deprecated=True)
async def pattern_match_get(
    concept: str,
    patterns: dict[str, Any] | None = None,
    service: QueryService = Depends(get_query_service)
):
    """Pattern match entities by concept and attribute patterns.

    Args:
        concept: Concept type to match
        patterns: Optional attribute patterns to match

    Returns:
        List of matching SearchResultResponse
    """
    try:
        results = await service.pattern_match(concept=concept, patterns=patterns)
        return success_response(data={"results": results})
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/pattern-match/{concept}")
async def pattern_match_post(
    concept: str,
    body: PatternMatchRequest,
    service: QueryService = Depends(get_query_service)
):
    """Pattern match entities by concept and attribute patterns.

    Args:
        concept: Concept type to match
        body: Pattern match request

    Returns:
        List of matching SearchResultResponse
    """
    try:
        results = await service.pattern_match(concept=concept, patterns=body.patterns)
        return success_response(data={"results": results})
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.get("/traverse/{entity_id}", deprecated=True)
async def graph_traverse_get(
    entity_id: str,
    relation_name: str = Query(default="", alias="relation_type"),
    direction: str = "outgoing",
    depth: int = 1,
    as_of: datetime | None = None,
    include_history: bool = False,
    service: QueryService = Depends(get_query_service)
):
    """Traverse graph from entity via relations.

    Args:
        entity_id: Starting entity ID
        relation_name: Relation name to traverse (alias: relation_type)
        direction: "outgoing" or "incoming"
        depth: Traversal depth (max 2 in Phase 1)
        as_of: Point-in-time query for temporal entities
        include_history: If true, include all historical versions

    Returns:
        List of traversed entities
    """
    try:
        results = await service.graph_traverse(
            entity_id=entity_id,
            relation_type=relation_name,
            direction=direction,
            depth=depth,
            as_of=as_of,
            include_history=include_history,
        )
        return success_response(data={"results": results})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/traverse/{entity_id}")
async def graph_traverse_post(
    entity_id: str,
    body: TraverseRequest,
    service: QueryService = Depends(get_query_service)
):
    """Traverse graph from entity via relations.

    Args:
        entity_id: Starting entity ID
        body: Traverse request with relation_name, direction, depth

    Returns:
        List of traversed entities
    """
    try:
        results = await service.graph_traverse(
            entity_id=entity_id,
            relation_type=body.relation_name,
            direction=body.direction,
            depth=body.depth,
            as_of=body.as_of,
            include_history=body.include_history,
        )
        return success_response(data={"results": results})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.get("/trace/{entity_id}")
async def trace_rule(
    entity_id: str,
    rule_id: str | None = None,
    service: QueryService = Depends(get_query_service)
):
    """Trace rule execution history for an entity.

    Args:
        entity_id: Entity to trace
        rule_id: Optional specific rule to trace

    Returns:
        List of rule execution records
    """
    try:
        results = await service.trace_rule(entity_id=entity_id, rule_id=rule_id)
        return success_response(data={"traces": results})
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.get("/path/{from_entity_id}/{to_entity_id}", deprecated=True)
async def find_path(
    from_entity_id: str,
    to_entity_id: str,
    max_depth: int = 3,
    service: QueryService = Depends(get_query_service)
):
    """Find paths between two entities.

    Args:
        from_entity_id: Start entity
        to_entity_id: Target entity
        max_depth: Maximum path depth (max 3 in Phase 1)

    Returns:
        List of paths, each path is a list of entity IDs
    """
    try:
        results = await service.find_path(
            from_entity_id=from_entity_id,
            to_entity_id=to_entity_id,
            max_depth=max_depth
        )
        return success_response(data={"paths": results})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))


@router.post("/path")
async def find_path_post(
    body: PathQueryRequest,
    service: QueryService = Depends(get_query_service)
):
    """Find paths between two entities.

    Args:
        body: Path query request

    Returns:
        List of paths, each path is a list of entity IDs
    """
    try:
        results = await service.find_path(
            from_entity_id=body.from_entity_id,
            to_entity_id=body.to_entity_id,
            max_depth=body.max_depth
        )
        return success_response(data={"paths": results})
    except ValueError as e:
        return error_response(code="INVALID_REQUEST", message=str(e))
    except Exception as e:
        return error_response(code="QUERY_ERROR", message=str(e))

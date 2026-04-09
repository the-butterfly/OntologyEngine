# ontology_engine/api/routes/query.py
"""Query endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Depends

from ontology_engine.api.server import get_query_service
from ontology_engine.services.query_service import QueryService

router = APIRouter()


@router.get("/pattern-match/{concept}")
async def pattern_match(
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
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traverse/{entity_id}")
async def graph_traverse(
    entity_id: str,
    relation_type: str = "has_invoice",
    direction: str = "outgoing",
    depth: int = 1,
    service: QueryService = Depends(get_query_service)
):
    """Traverse graph from entity via relations.

    Args:
        entity_id: Starting entity ID
        relation_type: Relation type to traverse
        direction: "outgoing" or "incoming"
        depth: Traversal depth (max 2 in Phase 1)

    Returns:
        List of traversed entities
    """
    try:
        results = await service.graph_traverse(
            entity_id=entity_id,
            relation_type=relation_type,
            direction=direction,
            depth=depth
        )
        return {"results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        return {"traces": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/path/{from_entity_id}/{to_entity_id}")
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
        return {"paths": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

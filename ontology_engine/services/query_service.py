# ontology_engine/services/query_service.py
"""Query service for pattern matching, graph traversal, and semantic retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from ontology_engine.services.dto import SearchResultResponse
from ontology_engine.storage.base import (
    GraphStoreBackend,
    HybridSearchResult,
    RetrievalBackend,
    StorageBackend,
    VectorStoreBackend,
    VectorSearchResult,
)

if TYPE_CHECKING:
    from ontology_engine.engine.rule import RuleExecutor


class QueryService:
    """Query service.

    Handles pattern matching, graph traversal, rule tracing, and
    Phase 2 semantic / hybrid retrieval.
    """

    def __init__(
        self,
        storage: StorageBackend,
        rule_executor: RuleExecutor | None = None,
        retrieval: RetrievalBackend | None = None,
        graph_store: GraphStoreBackend | None = None,
        vector_store: VectorStoreBackend | None = None,
    ):
        """Initialize QueryService.

        Args:
            storage: StorageBackend instance
            rule_executor: Optional RuleExecutor for rule tracing
            retrieval: Optional unified retrieval backend
            graph_store: Optional graph store for native graph queries
            vector_store: Optional vector store for semantic search
        """
        self.storage = storage
        self.rule_executor = rule_executor
        self.retrieval = retrieval
        self.graph_store = graph_store
        self.vector_store = vector_store

    async def pattern_match(
        self,
        concept: str,
        patterns: dict[str, Any] | None = None,
    ) -> list[SearchResultResponse]:
        """Pattern match entities by concept and attribute patterns.

        Args:
            concept: Concept type to match
            patterns: Attribute patterns to match (supports exact match)

        Returns:
            List of matching SearchResultResponse
        """
        entities = await self.storage.query_entities(
            fact_object=concept,
            filters=patterns,
        )

        return [
            SearchResultResponse(
                entity_id=e.entity_id,
                fact_object=e._fact_object,
                score=1.0,
                attributes=e.data,
            )
            for e in entities
        ]

    async def graph_traverse(
        self,
        entity_id: str,
        relation_type: str,
        direction: str = "outgoing",
        depth: int = 1,
        as_of: datetime | None = None,
        include_history: bool = False,
    ) -> list[SearchResultResponse]:
        """Traverse graph from entity via relations.

        Args:
            entity_id: Starting entity ID
            relation_type: Relation type to traverse
            direction: "outgoing" or "incoming"
            depth: Traversal depth (max 2 in Phase 1)
            as_of: Optional point-in-time timestamp for temporal filtering
            include_history: If true, include all historical versions

        Returns:
            List of traversed entities with relations
        """
        if depth > 2:
            raise ValueError("Phase 1 maximum depth is 2")

        as_of_str = as_of.isoformat() if as_of else None

        results = []
        visited = set()
        current_level = [(entity_id, None)]

        for _ in range(depth):
            next_level = []
            for current_id, _rel_data in current_level:
                neighbors = await self.storage.get_neighbors(
                    entity_id=current_id,
                    relation_name=relation_type,
                    direction=direction,
                    as_of=as_of_str,
                    include_history=include_history,
                )

                for entity, relation in neighbors:
                    if entity.entity_id not in visited:
                        visited.add(entity.entity_id)
                        results.append(
                            SearchResultResponse(
                                entity_id=entity.entity_id,
                                fact_object=entity._fact_object,
                                score=1.0,
                                attributes={
                                    **entity.data,
                                    "_relation_name": relation.relation_name,
                                    "_related_from": current_id,
                                },
                            )
                        )
                        next_level.append((entity.entity_id, relation.data))

            current_level = next_level

        return results

    async def trace_rule(
        self,
        entity_id: str,
        rule_id: str | None = None,
    ) -> list[dict]:
        """Trace rule execution history for an entity.

        Args:
            entity_id: Entity to trace
            rule_id: Optional specific rule to trace

        Returns:
            List of rule execution records
        """
        return await self.storage.get_rule_execution_log(entity_id, rule_id)

    async def find_path(
        self,
        from_entity_id: str,
        to_entity_id: str,
        max_depth: int = 3,
        relation_name: str | None = None,
    ) -> list[list[str]]:
        """Find paths between two entities.

        Args:
            from_entity_id: Start entity
            to_entity_id: Target entity
            max_depth: Maximum path depth
            relation_name: Relation type to traverse. If None, tries all relations.

        Returns:
            List of paths, each path is a list of entity IDs
        """
        if max_depth > 3:
            raise ValueError("Phase 1 maximum path depth is 3")

        rel_name = relation_name

        paths: list[list[str]] = []
        visited = set()

        async def dfs(current: str, target: str, path: list[str]) -> None:
            if current == target:
                paths.append(path.copy())
                return
            if len(path) >= max_depth:
                return

            visited.add(current)

            if rel_name:
                neighbors = await self.storage.get_neighbors(
                    entity_id=current,
                    relation_name=rel_name,
                    direction="outgoing",
                )
                for entity, _ in neighbors:
                    if entity.entity_id not in visited:
                        path.append(entity.entity_id)
                        await dfs(entity.entity_id, target, path)
                        path.pop()
            else:
                all_neighbors = await self.storage.get_neighbors(
                    entity_id=current,
                    relation_name="",
                    direction="outgoing",
                )
                for entity, _ in all_neighbors:
                    if entity.entity_id not in visited:
                        path.append(entity.entity_id)
                        await dfs(entity.entity_id, target, path)
                        path.pop()

            visited.remove(current)

        await dfs(from_entity_id, to_entity_id, [from_entity_id])
        return paths

    # -------------------------------------------------------------------------
    # Phase 2 retrieval interfaces (placeholders until Faiss/ladybug integration)
    # -------------------------------------------------------------------------

    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
        fact_object: str | None = None,
    ) -> list[VectorSearchResult]:
        """Pure semantic (vector) search.

        Args:
            query_text: Raw text query
            top_k: Maximum number of results
            fact_object: Optional fact object type filter

        Returns:
            Vector search results

        Raises:
            NotImplementedError: If no retrieval backend or embedder is configured.
        """
        if self.retrieval is not None:
            return await self.retrieval.semantic_search(
                query_text=query_text,
                top_k=top_k,
                fact_object=fact_object,
            )
        raise NotImplementedError(
            "semantic_search requires a RetrievalBackend with an embedder. "
            "Pass retrieval=DefaultRetrievalBackend(...) to QueryService."
        )

    async def hybrid_search(
        self,
        query_text: str | None = None,
        query_vector: list[float] | None = None,
        graph_seed_id: str | None = None,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        graph_weight: float = 0.4,
        fusion_strategy: str = "independent_then_fuse",
        path_pattern: list[tuple[str, str]] | None = None,
        path_weight: float = 0.2,
    ) -> HybridSearchResult:
        """Hybrid retrieval combining semantic, graph, and optional path signals.

        Args:
            query_text: Optional raw text query
            query_vector: Optional pre-computed query embedding
            graph_seed_id: Optional seed entity for graph expansion
            top_k: Maximum number of results
            semantic_weight: Weight for vector scores
            graph_weight: Weight for graph proximity scores
            fusion_strategy: One of ``filter_then_fuse``, ``independent_then_fuse``,
                            ``fuse_then_filter``
            path_pattern: Optional sequence of (relation_type, target_concept) tuples
            path_weight: Weight for path match scores

        Returns:
            HybridSearchResult with fused results and intermediate scores
        """
        if self.retrieval is not None:
            return await self.retrieval.hybrid_search(
                query_text=query_text,
                query_vector=query_vector,
                graph_seed_id=graph_seed_id,
                top_k=top_k,
                semantic_weight=semantic_weight,
                graph_weight=graph_weight,
                fusion_strategy=fusion_strategy,
                path_pattern=path_pattern,
                path_weight=path_weight,
            )
        raise NotImplementedError(
            "hybrid_search requires a RetrievalBackend. "
            "Pass retrieval=DefaultRetrievalBackend(...) to QueryService."
        )

    async def graph_pattern_match(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Graph DSL pattern match.

        Args:
            start_concept: Starting node concept type
            path_pattern: Sequence of (relation_type, target_concept) tuples
            start_filters: Optional attribute filters on the start node
            limit: Maximum result count

        Returns:
            Matched paths with node details
        """
        if self.retrieval is not None:
            return await self.retrieval.graph_pattern_match(
                start_concept=start_concept,
                path_pattern=path_pattern,
                start_filters=start_filters,
                limit=limit,
            )
        # Fallback: use MetaStore traversal
        from ontology_engine.storage.retrieval import DefaultRetrievalBackend

        fallback = DefaultRetrievalBackend(
            storage=self.storage,
            graph_store=self.graph_store,
            vector_store=self.vector_store,
        )
        return await fallback.graph_pattern_match(
            start_concept=start_concept,
            path_pattern=path_pattern,
            start_filters=start_filters,
            limit=limit,
        )

    async def query_raw(
        self,
        query_text: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        results = await self.semantic_search(query_text, top_k)
        return [
            {"id": r.id, "score": r.score, "metadata": r.metadata}
            for r in results
        ]

    async def query_structured(
        self,
        filters: dict[str, Any],
        sort: str | None = None,
        pagination: dict[str, int] | None = None,
    ) -> list[SearchResultResponse]:
        fact_object = filters.get("_fact_object") if filters else None
        query_filters = {k: v for k, v in filters.items() if k != "_fact_object"} if filters else None
        entities = await self.storage.query_entities(fact_object, query_filters)
        offset = (pagination or {}).get("offset", 0)
        limit = (pagination or {}).get("limit", 100)
        entities = entities[offset:offset + limit]
        return [
            SearchResultResponse(
                entity_id=e.entity_id,
                fact_object=e._fact_object,
                score=1.0,
                attributes=e.data,
            )
            for e in entities
        ]

    async def query_hybrid(
        self,
        query_text: str,
        filters: dict[str, Any] | None = None,
        fusion_strategy: str = "independent_then_fuse",
    ) -> dict[str, Any]:
        semantic_results = await self.semantic_search(query_text, top_k=20)
        semantic_ids = {r.id for r in semantic_results}
        semantic_meta = {r.id: r.metadata for r in semantic_results}

        structured_results = []
        structured_meta: dict[str, dict[str, Any]] = {}
        if filters:
            fact_object = filters.get("_fact_object") if filters else None
            query_filters = {k: v for k, v in filters.items() if k != "_fact_object"} if filters else None
            entities = await self.storage.query_entities(fact_object, query_filters)
            structured_results = [
                {"entity_id": e.entity_id, "fact_object": e._fact_object, "data": e.data}
                for e in entities
            ]
            for e in entities:
                structured_meta[e.entity_id] = {
                    "entity_id": e.entity_id,
                    "fact_object": e._fact_object,
                    "attributes": e.data,
                }

        if filters and structured_results:
            structured_ids = {r["entity_id"] for r in structured_results}
            if fusion_strategy == "filter_then_fuse":
                filtered_semantic = [r for r in semantic_results if r.id in structured_ids]
                return {
                    "results": [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in filtered_semantic],
                    "strategy": fusion_strategy,
                    "semantic_count": len(semantic_results),
                    "structured_count": len(structured_results),
                }
            else:
                all_ids = semantic_ids | structured_ids
                results = []
                for eid in all_ids:
                    meta = semantic_meta.get(eid) or structured_meta.get(eid, {})
                    score = next((r.score for r in semantic_results if r.id == eid), 0.0)
                    results.append({"id": eid, "score": score, "metadata": meta})
                return {
                    "results": results,
                    "strategy": fusion_strategy,
                    "semantic_count": len(semantic_results),
                    "structured_count": len(structured_results),
                }

        return {
            "results": [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in semantic_results],
            "strategy": "semantic_only",
            "semantic_count": len(semantic_results),
            "structured_count": 0,
        }

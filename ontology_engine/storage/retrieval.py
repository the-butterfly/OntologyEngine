"""Default retrieval backend that coordinates storage layers."""

from __future__ import annotations

from typing import Any, Callable

from ontology_engine.storage.base import (
    GraphStoreBackend,
    HybridSearchResult,
    RetrievalBackend,
    StorageBackend,
    VectorSearchResult,
    VectorStoreBackend,
)


class DefaultRetrievalBackend(RetrievalBackend):
    """Coordinates MetaStore + GraphStore + VectorStore for unified retrieval.

    This is the concrete implementation of the "统一 Repository 接口"
    described in ``docs/05-schema-v2/query-engine-target.md``.

    Write flow:
        1. Attributes -> StorageBackend (MetaStore)
        2. Topology  -> GraphStoreBackend (NetworkX / kuzu)
        3. Vectors   -> VectorStoreBackend (ChromaDB / LocalVectorStore)

    Read flow:
        1. Structured queries -> StorageBackend
        2. Graph queries      -> GraphStoreBackend
        3. Semantic queries   -> VectorStoreBackend
        4. Hybrid queries     -> Fusion across backends
    """

    def __init__(
        self,
        storage: StorageBackend,
        graph_store: GraphStoreBackend | None = None,
        vector_store: VectorStoreBackend | None = None,
        embedder: Callable[[str], list[float]] | None = None,
    ):
        self.storage = storage
        self.graph = graph_store
        self.vector = vector_store
        self._embedder = embedder

    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
        fact_object: str | None = None,
    ) -> list[VectorSearchResult]:
        """Pure vector search.

        Raises:
            NotImplementedError: If no embedder is configured.
        """
        if self.vector is None:
            return []
        if self._embedder is None:
            raise NotImplementedError(
                "semantic_search requires an embedder. "
                "Install sentence-transformers and pass an embedder, "
                "or provide a pre-computed query_vector via hybrid_search."
            )
        query_vector = self._embedder(query_text)
        results = await self.vector.search(query_vector, top_k=top_k)
        if fact_object:
            results = [
                r for r in results if r.metadata.get("fact_object") == fact_object
            ]
        return results

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
        """Hybrid retrieval combining semantic, graph expansion, and optional path pattern.

        Args:
            query_text: Optional raw text query (used to derive embedding).
            query_vector: Optional pre-computed query embedding.
            graph_seed_id: Optional seed entity for graph expansion.
            top_k: Maximum number of results.
            semantic_weight: Weight for vector scores.
            graph_weight: Weight for graph proximity scores.
            fusion_strategy: One of ``filter_then_fuse``, ``independent_then_fuse``,
                            ``fuse_then_filter``.
            path_pattern: Optional sequence of (relation_type, target_concept) tuples
                         for path-based filtering/scoring.
            path_weight: Weight for path match scores.

        Returns:
            HybridSearchResult with final results and intermediate scores for
            observability and tuning.
        """
        valid_strategies = ("filter_then_fuse", "independent_then_fuse", "fuse_then_filter")
        if fusion_strategy not in valid_strategies:
            raise ValueError(f"Unknown fusion strategy: {fusion_strategy}. Must be one of {valid_strategies}")

        # Resolve query vector
        if query_vector is None and query_text is not None:
            if self._embedder is None:
                raise NotImplementedError(
                    "hybrid_search requires either query_vector or an embedder."
                )
            query_vector = self._embedder(query_text)

        # --- Semantic leg ---
        semantic_scores: dict[str, float] = {}
        semantic_results: list[VectorSearchResult] = []
        if self.vector is not None and query_vector is not None:
            semantic_results = await self.vector.search(query_vector, top_k=top_k * 2)
            for r in semantic_results:
                semantic_scores[r.id] = r.score

        # --- Graph leg ---
        graph_scores: dict[str, float] = {}
        if self.graph is not None and graph_seed_id is not None:
            visited = {graph_seed_id}
            queue = [graph_seed_id]
            depth = 0
            max_depth = 2
            while queue and depth <= max_depth:
                next_queue = []
                for node_id in queue:
                    neighbors = await self.graph.get_neighbors(
                        node_id,
                        edge_type=None,
                        direction="both",
                        limit=100,
                    )
                    for n in neighbors:
                        nid = n["neighbor_id"]
                        if nid not in visited:
                            visited.add(nid)
                            next_queue.append(nid)
                            graph_scores[nid] = max(
                                graph_scores.get(nid, 0.0),
                                1.0 / (1.0 + depth),
                            )
                queue = next_queue
                depth += 1

        # --- Path pattern leg ---
        path_match_scores: dict[str, float] = {}
        if path_pattern and self.graph is not None and graph_seed_id is not None:
            path_length = len(path_pattern)
            if path_length <= 2:
                # Short path: use get_neighbors multi-hop for path scoring
                path_match_scores = await self._score_short_path_pattern(
                    graph_seed_id, path_pattern
                )
            else:
                # Long path: use Cypher native MATCH
                path_match_scores = await self._score_long_path_pattern(
                    graph_seed_id, path_pattern
                )

        # --- Fusion ---
        if fusion_strategy == "filter_then_fuse":
            final_ids, used_path_ids = self._fuse_filter_then_fuse(
                semantic_scores, graph_scores, path_match_scores,
                semantic_weight, graph_weight, path_weight, top_k,
            )
        elif fusion_strategy == "fuse_then_filter":
            final_ids = self._fuse_then_filter(
                semantic_scores, graph_scores, path_match_scores,
                semantic_weight, graph_weight, path_weight, top_k, path_pattern,
            )
            used_path_ids = set(path_match_scores.keys())
        else:  # independent_then_fuse
            final_ids, used_path_ids = self._fuse_independent_then_fuse(
                semantic_scores, graph_scores, path_match_scores,
                semantic_weight, graph_weight, path_weight, top_k,
            )

        # Build results
        semantic_meta: dict[str, dict[str, Any]] = {
            r.id: r.metadata for r in semantic_results
        }

        non_semantic_ids = [vid for vid in final_ids if vid not in semantic_meta]
        if non_semantic_ids and self.storage is not None:
            for vid in non_semantic_ids:
                try:
                    entity = await self.storage.get_entity_by_id(vid)
                    if entity is not None:
                        semantic_meta[vid] = {
                            "entity_id": entity.entity_id,
                            "fact_object": entity.concept,
                            "attributes": entity.data if hasattr(entity, 'data') else {},
                        }
                except Exception:
                    semantic_meta[vid] = {}

        fused_scores: dict[str, float] = {}
        for vid in final_ids:
            s = semantic_scores.get(vid, 0.0) * semantic_weight
            g = graph_scores.get(vid, 0.0) * graph_weight
            p = path_match_scores.get(vid, 0.0) * path_weight
            fused_scores[vid] = s + g + p

        results: list[VectorSearchResult] = []
        for vid in final_ids:
            meta = semantic_meta.get(vid, {})
            results.append(VectorSearchResult(id=vid, score=fused_scores.get(vid, 0.0), metadata=meta))

        fusion_metadata = {
            "strategy": fusion_strategy,
            "weights": {
                "semantic": semantic_weight,
                "graph": graph_weight,
                "path": path_weight,
            },
            "candidate_count": len(set(semantic_scores) | set(graph_scores) | set(path_match_scores)),
            "semantic_candidates": len(semantic_scores),
            "graph_candidates": len(graph_scores),
            "path_candidates": len(path_match_scores),
        }

        return HybridSearchResult(
            results=results,
            semantic_scores=semantic_scores,
            graph_scores=graph_scores,
            path_match_scores=path_match_scores,
            fusion_metadata=fusion_metadata,
        )

    async def _score_short_path_pattern(
        self,
        seed_id: str,
        path_pattern: list[tuple[str, str]],
    ) -> dict[str, float]:
        """Score entities based on short path pattern (<=2 hops) using get_neighbors."""
        if self.graph is None:
            return {}
        visited_paths: dict[str, float] = {seed_id: 1.0}

        for rel_type, target_concept in path_pattern:
            next_visited: dict[str, float] = {}
            for current_id, current_score in visited_paths.items():
                neighbors = await self.graph.get_neighbors(
                    node_id=current_id,
                    edge_type=rel_type,
                    direction="outgoing",
                    limit=100,
                    node_concept=target_concept,
                )
                for neighbor_info in neighbors:
                    nid = neighbor_info["neighbor_id"]
                    edge_weight = 1.0
                    edge_confidence = neighbor_info.get("confidence")
                    if edge_confidence is not None:
                        try:
                            edge_weight = float(edge_confidence)
                        except (ValueError, TypeError):
                            pass
                    edge_props = neighbor_info.get("properties", {})
                    if edge_props and "weight" in edge_props:
                        edge_weight = float(edge_props["weight"])
                    # Score = path_score * edge_weight
                    new_score = current_score * edge_weight
                    next_visited[nid] = max(next_visited.get(nid, 0.0), new_score)
            visited_paths = next_visited
            if not visited_paths:
                break

        return visited_paths

    async def _score_long_path_pattern(
        self,
        seed_id: str,
        path_pattern: list[tuple[str, str]],
    ) -> dict[str, float]:
        if self.graph is None:
            return {}

        segments = [f"(start:Entity {{entity_id: $seed_id}})"]
        params: dict[str, Any] = {"seed_id": seed_id}
        for i, (rel_type, target_concept) in enumerate(path_pattern):
            params[f"rel_type_{i}"] = rel_type
            params[f"concept_{i+1}"] = target_concept
            segments.append(f"-[r{i}:Relation {{relation_type: $rel_type_{i}}}]->")
            segments.append(f"(n{i+1}:Entity {{concept: $concept_{i+1}}})")

        cypher = "MATCH " + "".join(segments)
        return_cols = [f"n{i+1}.entity_id" for i in range(len(path_pattern))]
        cypher += f" RETURN {', '.join(return_cols)}"

        try:
            result = await self.graph.execute_cypher(cypher, params)
            scores: dict[str, float] = {}
            for row in result:
                last_col = f"n{len(path_pattern)}.entity_id"
                if last_col in row:
                    entity_id = row[last_col]
                    scores[entity_id] = 1.0
            return scores
        except Exception:
            return {}

    def _fuse_filter_then_fuse(
        self,
        semantic_scores: dict[str, float],
        graph_scores: dict[str, float],
        path_match_scores: dict[str, float],
        semantic_weight: float,
        graph_weight: float,
        path_weight: float,
        top_k: int,
    ) -> tuple[list[str], set[str]]:
        """Filter by path first, then fuse with other signals."""
        # Filter candidates to those matching the path pattern
        if path_match_scores:
            candidates = set(path_match_scores.keys())
        else:
            candidates = set(semantic_scores) | set(graph_scores)

        used_path_ids = set(path_match_scores.keys())
        fused_scores: dict[str, float] = {}
        for vid in candidates:
            sem = semantic_scores.get(vid, 0.0)
            gra = graph_scores.get(vid, 0.0)
            pat = path_match_scores.get(vid, 0.0)
            total_weight = semantic_weight + graph_weight + path_weight
            norm_sem = semantic_weight / total_weight if total_weight > 0 else 0
            norm_gra = graph_weight / total_weight if total_weight > 0 else 0
            norm_pat = path_weight / total_weight if total_weight > 0 else 0
            fused_scores[vid] = norm_sem * sem + norm_gra * gra + norm_pat * pat

        sorted_ids = sorted(fused_scores, key=lambda k: fused_scores[k], reverse=True)
        return sorted_ids[:top_k], used_path_ids

    def _fuse_independent_then_fuse(
        self,
        semantic_scores: dict[str, float],
        graph_scores: dict[str, float],
        path_match_scores: dict[str, float],
        semantic_weight: float,
        graph_weight: float,
        path_weight: float,
        top_k: int,
    ) -> tuple[list[str], set[str]]:
        """Score each leg independently, then fuse with weights."""
        all_ids = set(semantic_scores) | set(graph_scores) | set(path_match_scores)
        fused_scores: dict[str, float] = {}

        for vid in all_ids:
            sem = semantic_scores.get(vid, 0.0)
            gra = graph_scores.get(vid, 0.0)
            pat = path_match_scores.get(vid, 0.0)
            total_weight = semantic_weight + graph_weight + path_weight
            norm_sem = semantic_weight / total_weight if total_weight > 0 else 0
            norm_gra = graph_weight / total_weight if total_weight > 0 else 0
            norm_pat = path_weight / total_weight if total_weight > 0 else 0
            fused_scores[vid] = norm_sem * sem + norm_gra * gra + norm_pat * pat

        sorted_ids = sorted(fused_scores, key=lambda k: fused_scores[k], reverse=True)
        used_path_ids = set(path_match_scores.keys())
        return sorted_ids[:top_k], used_path_ids

    def _fuse_then_filter(
        self,
        semantic_scores: dict[str, float],
        graph_scores: dict[str, float],
        path_match_scores: dict[str, float],
        semantic_weight: float,
        graph_weight: float,
        path_weight: float,
        top_k: int,
        path_pattern: list[tuple[str, str]] | None,
    ) -> list[str]:
        """Fuse all signals first, then apply path pattern as final filter."""
        all_ids = set(semantic_scores) | set(graph_scores)
        fused_scores: dict[str, float] = {}

        for vid in all_ids:
            sem = semantic_scores.get(vid, 0.0)
            gra = graph_scores.get(vid, 0.0)
            total_weight = semantic_weight + graph_weight
            norm_sem = semantic_weight / total_weight if total_weight > 0 else 0
            norm_gra = graph_weight / total_weight if total_weight > 0 else 0
            fused_scores[vid] = norm_sem * sem + norm_gra * gra

        sorted_ids = sorted(fused_scores, key=lambda k: fused_scores[k], reverse=True)

        # Filter by path pattern if provided
        if path_pattern:
            filtered: list[str] = []
            for vid in sorted_ids:
                if vid in path_match_scores and path_match_scores[vid] > 0:
                    filtered.append(vid)
                if len(filtered) >= top_k:
                    break
            return filtered
        return sorted_ids[:top_k]

    async def graph_pattern_match(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Graph DSL pattern match using available backends.

        Strategy:
        - Short paths (<=2 hops): get_neighbors multi-hop (lower latency)
        - Long paths (>2 hops): Cypher native MATCH (kuzu optimizer global optimization)
        - No graph store: MetaStore fallback
        """
        if not path_pattern:
            # Degenerate case: just query start nodes
            entities = await self.storage.query_entities(
                fact_object=start_concept,
                filters=start_filters,
            )
            return [
                {"nodes": [{"entity_id": e.entity_id, "fact_object": e._fact_object}]}
                for e in entities[:limit]
            ]

        path_length = len(path_pattern)

        if self.graph is None:
            # MetaStore fallback
            return await self._graph_pattern_match_storage(
                start_concept, path_pattern, start_filters, limit
            )

        if path_length <= 2:
            # Short path: get_neighbors multi-hop
            return await self._graph_pattern_match_short(
                start_concept, path_pattern, start_filters, limit
            )
        else:
            # Long path: Cypher native MATCH
            return await self._execute_cypher_pattern(
                start_concept, path_pattern, start_filters, limit
            )

    async def _graph_pattern_match_storage(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fallback pattern match using MetaStore."""
        candidates = await self.storage.query_entities(
            fact_object=start_concept,
            filters=start_filters,
        )

        results: list[dict[str, Any]] = []
        for entity in candidates:
            if len(results) >= limit:
                break
            path = await self._traverse_pattern_storage(
                entity.entity_id, path_pattern
            )
            if path:
                results.append(path)
        return results

    async def _graph_pattern_match_short(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Short path pattern match using get_neighbors with node_concept."""
        # Find candidate start nodes
        candidates = await self.storage.query_entities(
            fact_object=start_concept,
            filters=start_filters,
        )

        results: list[dict[str, Any]] = []
        for entity in candidates:
            if len(results) >= limit:
                break
            path = await self._traverse_pattern_with_concept(
                entity.entity_id, path_pattern
            )
            if path:
                results.append(path)
        return results

    async def _traverse_pattern_with_concept(
        self,
        start_id: str,
        path_pattern: list[tuple[str, str]],
    ) -> dict[str, Any] | None:
        """Traverse using get_neighbors with node_concept filter (no MetaStore lookup needed)."""
        if self.graph is None:
            return None
        nodes: list[dict[str, Any]] = [{"entity_id": start_id}]
        edges: list[dict[str, Any]] = []
        current_id = start_id

        for rel_type, target_concept in path_pattern:
            # Use node_concept filter - kuzu will filter at storage layer
            graph_neighbors = await self.graph.get_neighbors(
                node_id=current_id,
                edge_type=rel_type,
                direction="outgoing",
                limit=100,
                node_concept=target_concept,
            )
            found = False
            for neighbor_info in graph_neighbors:
                neighbor_id: str = neighbor_info["neighbor_id"]
                # Concept is already verified by node_concept filter
                nodes.append({"entity_id": neighbor_id, "concept": target_concept})
                edges.append({"relation_type": rel_type})
                current_id = neighbor_id
                found = True
                break
            if not found:
                return None

        return {"nodes": nodes, "edges": edges}

    async def _traverse_pattern_storage(
        self,
        start_id: str,
        path_pattern: list[tuple[str, str]],
    ) -> dict[str, Any] | None:
        """Traverse using StorageBackend get_neighbors (fallback when no graph store)."""
        nodes: list[dict[str, Any]] = [{"entity_id": start_id}]
        edges: list[dict[str, Any]] = []
        current_id = start_id

        for rel_type, target_concept in path_pattern:
            db_neighbors = await self.storage.get_neighbors(
                entity_id=current_id,
                relation_name=rel_type,
                direction="outgoing",
            )
            found = False
            for db_ent, db_rel in db_neighbors:
                if db_ent._fact_object == target_concept:
                    nodes.append({"entity_id": db_ent.entity_id, "fact_object": db_ent._fact_object})
                    edges.append({"relation_name": db_rel.relation_name})
                    current_id = db_ent.entity_id
                    found = True
                    break
            if not found:
                return None

        return {"nodes": nodes, "edges": edges}

    async def _execute_cypher_pattern(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        if self.graph is None:
            return []
        segments = [f"(start:Entity {{concept: $start_concept}})"]
        params: dict[str, Any] = {"start_concept": start_concept}
        for i, (rel_type, target_concept) in enumerate(path_pattern):
            params[f"rel_type_{i}"] = rel_type
            params[f"concept_{i+1}"] = target_concept
            segments.append(f"-[r{i}:Relation {{relation_type: $rel_type_{i}}}]->")
            segments.append(f"(n{i+1}:Entity {{concept: $concept_{i+1}}})")

        cypher = "MATCH " + "".join(segments)

        if start_filters:
            where_parts = []
            for k, v in start_filters.items():
                param_name = f"sf_{k}"
                where_parts.append(f"start.{k} = ${param_name}")
                params[param_name] = v
            cypher += " WHERE " + " AND ".join(where_parts)

        return_cols = ["start.entity_id"] + [f"n{i+1}.entity_id" for i in range(len(path_pattern))]
        cypher += f" RETURN {', '.join(return_cols)} LIMIT {limit}"

        result = await self.graph.execute_cypher(cypher, params)
        return [self._format_pattern_result(row, start_concept, path_pattern) for row in result]

    def _format_pattern_result(
        self,
        row: dict[str, Any],
        start_concept: str,
        path_pattern: list[tuple[str, str]],
    ) -> dict[str, Any]:
        """Format a Cypher result row into a pattern result dict."""
        nodes = [{"entity_id": row["start.entity_id"], "concept": start_concept}]
        edges = []
        for i in range(len(path_pattern)):
            nodes.append({
                "entity_id": row[f"n{i+1}.entity_id"],
                "concept": path_pattern[i][1],
            })
            edges.append({"relation_type": path_pattern[i][0]})
        return {"nodes": nodes, "edges": edges}

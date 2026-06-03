"""Layer-S graph traversal retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ontology_engine.storage.base import GraphStoreBackend, StorageBackend


@dataclass
class EntityResult:
    entity_id: str
    name: str
    fact_object: str
    attributes: dict[str, str]
    valid_from: str | None
    valid_to: str | None
    domain_id: str
    confidence: float
    feedback_weight: float


@dataclass
class EdgeResult:
    edge_id: str
    from_id: str
    to_id: str
    relation_name: str
    edge_text: str
    weight: float
    confidence: float
    valid_from: str | None
    valid_to: str | None


@dataclass
class PathResult:
    nodes: list[str]
    edges: list[str]
    path_score: float
    path_type: str


@dataclass
class StructuredResult:
    entities: list[EntityResult] = field(default_factory=list)
    edges: list[EdgeResult] = field(default_factory=list)
    paths: list[PathResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


QUERY_TYPE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "factual": {"TEMPORAL": 1.0, "CAUSAL": 1.0, "ENTITY": 1.0},
    "multi_hop": {"TEMPORAL": 1.0, "CAUSAL": 2.0, "ENTITY": 1.5},
    "temporal": {"TEMPORAL": 3.0, "CAUSAL": 1.0, "ENTITY": 1.0},
    "mixed": {"TEMPORAL": 2.0, "CAUSAL": 1.5, "ENTITY": 1.2},
}


class LayerSRetriever:
    """Layer-S: Graph traversal retrieval via Ladybug."""

    def __init__(self, graph_store: GraphStoreBackend, meta_store: StorageBackend) -> None:
        self._graph_store = graph_store
        self._meta_store = meta_store

    async def retrieve_neighbors(
        self,
        entity_id: str,
        query_type: str = "factual",
        max_depth: int = 2,
        min_confidence: float = 0.3,
        as_of: str | None = None,
    ) -> StructuredResult:
        multipliers = QUERY_TYPE_MULTIPLIERS.get(query_type, QUERY_TYPE_MULTIPLIERS["factual"])

        entities: list[EntityResult] = []
        edges: list[EdgeResult] = []
        paths: list[PathResult] = []
        visited: set[str] = {entity_id}
        current_level = [entity_id]

        # Build extra keyword args that the graph store accepts
        _get_neighbors_kwargs: dict[str, Any] = {"direction": "both", "limit": 50}
        if as_of is not None:
            _get_neighbors_kwargs["as_of"] = as_of

        for _depth in range(max_depth):
            next_level: list[str] = []
            for nid in current_level:
                try:
                    neighbors = await self._graph_store.get_neighbors(
                        node_id=nid,
                        **_get_neighbors_kwargs,
                    )
                except TypeError:
                    # Fallback: backend may not support as_of yet
                    neighbors = await self._graph_store.get_neighbors(
                        node_id=nid,
                        direction="both",
                        limit=50,
                    )
                for nb in neighbors:
                    nb_id = nb.get("neighbor_id", "")
                    if nb_id in visited:
                        continue

                    edge_type = nb.get("edge_type", "")
                    confidence = float(nb.get("confidence", 0.5))
                    if confidence < min_confidence:
                        continue

                    visited.add(nb_id)
                    next_level.append(nb_id)

                    edge_weight = self._compute_edge_weight(edge_type, multipliers)
                    entity = await self._fetch_entity(nb_id)
                    if entity:
                        entities.append(entity)

                    edges.append(EdgeResult(
                        edge_id=nb.get("edge_id", ""),
                        from_id=nid,
                        to_id=nb_id,
                        relation_name=edge_type,
                        edge_text=nb.get("edge_text", ""),
                        weight=edge_weight,
                        confidence=confidence,
                        valid_from=nb.get("valid_from"),
                        valid_to=nb.get("valid_to"),
                    ))

            current_level = next_level

        return StructuredResult(entities=entities, edges=edges, paths=paths)

    async def score_edge_text(
        self,
        query_embedding: list[float],
        edge_texts: list[str],
    ) -> list[float]:
        if not edge_texts:
            return []
        return [1.0 / (1.0 + len(t)) for t in edge_texts]

    async def _fetch_entity(self, entity_id: str) -> EntityResult | None:
        try:
            entity = await self._meta_store.get_entity_by_id(entity_id)
            if entity is None:
                return None
            data = entity.data if hasattr(entity, "data") else {}
            return EntityResult(
                entity_id=entity.entity_id,
                name=data.get("name", ""),
                fact_object=entity.concept,
                attributes={k: str(v) for k, v in data.items() if k != "name"},
                valid_from=data.get("valid_from"),
                valid_to=data.get("valid_to"),
                domain_id=data.get("domain_id", ""),
                confidence=data.get("confidence", 0.5),
                feedback_weight=data.get("feedback_weight", 0.5),
            )
        except Exception:
            return None

    @staticmethod
    def _compute_edge_weight(edge_type: str, multipliers: dict[str, float]) -> float:
        base_weight = 1.0
        category = "ENTITY"
        temporal_types = {"PRECEDES", "SUCCEEDS", "LEADS_TO", "BECAUSE_OF", "ENABLES", "PREVENTS", "same_entity_as"}
        causal_types = {"LEADS_TO", "BECAUSE_OF", "ENABLES", "PREVENTS"}
        if edge_type in temporal_types:
            category = "TEMPORAL"
        if edge_type in causal_types:
            category = "CAUSAL"
        return base_weight * multipliers.get(category, 1.0)

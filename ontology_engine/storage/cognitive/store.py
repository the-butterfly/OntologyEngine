from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.storage.base import CognitiveStorageBackend, GraphQueryError
from ontology_engine.storage.cognitive_interface import SearchQuery, StorageInterface

if TYPE_CHECKING:
    from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore

logger = logging.getLogger(__name__)


class CognitiveStore(CognitiveStorageBackend):
    """Cognitive storage backend backed by KuzuGraphStore.

    Delegates all cognitive-specific persistence operations to the
    underlying KuzuGraphStore, translating between the dict-based
    CognitiveStorageBackend interface and KuzuGraphStore's method
    signatures.
    """

    def __init__(
        self,
        graph_store: KuzuGraphStore,
        storage: StorageInterface | None = None,
    ) -> None:
        self._store = graph_store
        self._storage = storage

    async def initialize(self, db_path: str | None = None) -> None:
        await self._store.initialize(db_path)

    async def close(self) -> None:
        await self._store.close()

    async def save_cognitive_node(self, node_data: dict[str, Any]) -> None:
        await self._store.upsert_cognitive_node(
            node_id=node_data["id"],
            memory_type=node_data.get("memory_type", "fragment"),
            cognitive_layer=node_data.get("cognitive_layer", "perception"),
            content=node_data.get("content", ""),
            content_vector=node_data.get("content_vector"),
            source_fragment_ids=node_data.get("source_fragment_ids"),
            belief_status=node_data.get("belief_status", "accepted"),
            ttl_seconds=node_data.get("ttl_seconds", 0),
            occurred_at=node_data.get("occurred_at"),
            extraction_hint=node_data.get("extraction_hint"),
            domain_id=node_data.get("domain_id"),
            space_id=node_data.get("space_id", "default"),
            history=node_data.get("history"),
            visibility=node_data.get("visibility", "shared"),
            created_by=node_data.get("created_by"),
            feedback_weight=node_data.get("feedback_weight", 0.5),
            confidence=node_data.get("confidence", 1.0),
            access_count=node_data.get("access_count", 0),
            last_access_at=node_data.get("last_access_at"),
            consolidated_at=node_data.get("consolidated_at"),
            schema_ref=node_data.get("schema_ref"),
            superseded_by=node_data.get("superseded_by"),
            proof_count=node_data.get("proof_count", 1),
            valid_from=node_data.get("valid_from"),
            valid_to=node_data.get("valid_to"),
            recorded_at=node_data.get("recorded_at"),
            tags=node_data.get("tags"),
            attributes=node_data.get("attributes"),
            confirmation_count=node_data.get("confirmation_count", 0),
            strength=node_data.get("strength", 1.0),
            entity_name=node_data.get("entity_name"),
            entity_type=node_data.get("entity_type"),
            version=node_data.get("version", 1),
            last_confirmed_at=node_data.get("last_confirmed_at"),
            consolidation_reasoning=node_data.get("consolidation_reasoning"),
            compiled_at=node_data.get("compiled_at"),
            source_trust_tier=node_data.get("source_trust_tier"),
            scope=node_data.get("scope"),
            source_pipeline=node_data.get("source_pipeline"),
            source_content_hash=node_data.get("source_content_hash"),
        )

    async def get_cognitive_node(self, node_id: str) -> dict[str, Any] | None:
        return await self._store.get_cognitive_node(node_id)

    async def list_cognitive_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._store.query_cognitive_nodes(
            memory_type=memory_type,
            cognitive_layer=cognitive_layer,
            belief_status=belief_status,
            domain_id=domain_id,
            space_id=space_id,
            limit=limit,
            as_of=as_of,
        )

    async def delete_cognitive_node(self, node_id: str) -> None:
        await self._store.delete_cognitive_node(node_id)

    async def update_cognitive_node_belief(
        self,
        node_id: str,
        new_belief: str,
        reason: str | None = None,
    ) -> None:
        await self._store.update_cognitive_node_belief(node_id, new_belief, reason)

    async def update_cognitive_node_with_occ(
        self,
        node_id: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        current = await self._store.get_cognitive_node(node_id)
        if current is None:
            return None

        current_version = current.get("version", 1)
        if current_version != expected_version:
            return None

        set_clauses: list[str] = []
        params: dict[str, Any] = {"id": node_id}

        json_fields = {"source_fragment_ids", "tags", "attributes", "content_vector", "history"}
        for key, value in updates.items():
            if key in json_fields:
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = json.dumps(value) if value is not None else None
            else:
                set_clauses.append(f"n.{key} = ${key}")
                params[key] = value

        set_clauses.append("n.version = n.version + 1")
        set_clauses.append("n.updated_at = $updated_at")

        from datetime import datetime, timezone
        params["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_str = ", ".join(set_clauses)
        cypher = f"MATCH (n:CognitiveNode {{id: $id}}) SET {set_str} RETURN n.id AS id"

        try:
            await self._store._execute(cypher, params)
        except Exception as e:
            logger.error("OCC update failed for %s: %s", node_id, e)
            return None

        return await self._store.get_cognitive_node(node_id)

    async def save_cognitive_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._store.create_cognitive_edge(
            edge_type=edge_type,
            from_id=from_id,
            to_id=to_id,
            properties=properties,
        )

    async def list_cognitive_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._store.query_cognitive_edges(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            limit=limit,
        )

    async def save_disposition(self, profile_data: dict[str, Any]) -> None:
        await self._store.upsert_disposition_profile(
            profile_id=profile_data["id"],
            scene=profile_data.get("scene", "default"),
            skepticism=profile_data.get("skepticism", 0.5),
            evidence_demand=profile_data.get("evidence_demand", 0.5),
            abstraction_preference=profile_data.get("abstraction_preference", 0.5),
            thoroughness=profile_data.get("thoroughness", 0.5),
            recency_bias=profile_data.get("recency_bias", 0.5),
            empathy=profile_data.get("empathy", 0.5),
            risk_tolerance=profile_data.get("risk_tolerance", 0.5),
            domain_id=profile_data.get("domain_id"),
            space_id=profile_data.get("space_id", "default"),
        )

    async def get_disposition(
        self,
        profile_id: str | None = None,
        scene: str | None = None,
        domain_id: str | None = None,
    ) -> dict[str, Any] | None:
        return await self._store.get_disposition_profile(
            profile_id=profile_id,
            scene=scene,
            domain_id=domain_id,
        )

    async def compute_dynamic_weights(
        self, profile: dict[str, Any]
    ) -> dict[str, float]:
        return await self._store.compute_dynamic_weights(profile)

    async def save_activity_log(
        self, node_id: str, entry: dict[str, Any]
    ) -> None:
        await self._store.update_cognitive_node_history(node_id, entry)

    async def get_activity_log(
        self, node_id: str
    ) -> list[dict[str, Any]]:
        node = await self._store.get_cognitive_node(node_id)
        if node is None:
            return []
        history = node.get("history")
        if isinstance(history, list):
            return history
        if isinstance(history, str):
            try:
                parsed = json.loads(history)
                if isinstance(parsed, list):
                    return parsed
                return []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    async def search_cognitive(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._storage is None:
            nodes = await self._store.query_cognitive_nodes(
                domain_id=space_id,
                space_id=space_id,
                memory_type=memory_type,
                limit=top_k,
            )
            results: list[dict[str, Any]] = []
            query_lower = query.lower()
            for node in nodes:
                content = node.get("content", "")
                if query_lower in content.lower():
                    node["score"] = 1.0
                else:
                    node["score"] = 0.0
                results.append(node)
            results.sort(key=lambda n: n.get("score", 0.0), reverse=True)
            return results

        search_query = SearchQuery(
            query_text=query,
            space_id=space_id,
            top_k=top_k,
            memory_type=memory_type,
        )
        search_result = await self._storage.search(search_query)
        results = []
        for node in search_result.nodes:
            row = node.to_dict() if hasattr(node, "to_dict") else dict(node)
            row["score"] = search_result.scores.get(node.id, 0.0)
            if search_result.semantic_scores:
                row["semantic_score"] = search_result.semantic_scores.get(node.id, 0.0)
            if search_result.keyword_scores:
                row["keyword_score"] = search_result.keyword_scores.get(node.id, 0.0)
            if search_result.fusion_metadata:
                row["fusion_metadata"] = search_result.fusion_metadata
            results.append(row)
        return results

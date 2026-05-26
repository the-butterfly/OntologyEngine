from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.memory_utils import (
    compute_strength,
    make_response,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class QueryService:

    def __init__(self, repository: "CognitiveRepository"):
        self._repo = repository

    async def get_node(self, space_id: str, node_id: str) -> dict[str, Any]:
        node = await self._repo.get_node(node_id)
        return {
            k: getattr(node, k)
            for k in (
                "id", "memory_type", "cognitive_layer", "content", "belief_status",
                "confidence", "visibility", "created_by", "space_id", "tags",
                "attributes", "schema_ref", "occurred_at", "recorded_at", "valid_from",
                "valid_to", "superseded_by", "source_fragment_ids", "confirmation_count",
                "strength", "entity_name", "entity_type", "version", "last_confirmed_at",
                "consolidation_reasoning", "compiled_at", "source_trust_tier", "scope",
                "source_pipeline", "source_content_hash", "access_count", "last_access_at",
                "consolidated_at", "domain_id", "feedback_weight", "proof_count", "ttl_seconds",
            )
        }

    async def list_nodes(
        self,
        space_id: str,
        memory_type: str | None = None,
        belief_status: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        nodes = await self._repo.query_nodes(
            domain_id=space_id, memory_type=memory_type, belief_status=belief_status, limit=limit,
        )
        results = []
        for n in nodes:
            strength_info = compute_strength(n)
            results.append({
                "id": n.id, "memory_type": n.memory_type, "text": n.content,
                "cognitive_layer": n.cognitive_layer, "belief_status": n.belief_status,
                "proof_count": len(n.source_fragment_ids), "visibility": n.visibility,
                "created_by": n.created_by, "confidence": n.confidence,
                "strength": strength_info["value"], "strength_breakdown": strength_info["breakdown"],
            })
        return {"nodes": results, "total": len(results), "space_id": space_id}

    async def list_my_memories(
        self,
        space_id: str,
        user_id: str,
        scope_type: str | None = None,
        memory_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id, memory_type=memory_type, limit=10000,
            )
            filtered = []
            for n in nodes:
                if n.created_by == user_id:
                    filtered.append(n)
                elif n.visibility in ("public", "shared"):
                    filtered.append(n)
                elif n.created_by is None and n.belief_status == "accepted":
                    filtered.append(n)
            if scope_type:
                filtered = [n for n in filtered if getattr(n, "scope", None) == scope_type]
            filtered = filtered[:limit]
            results = []
            for n in filtered:
                strength_info = compute_strength(n)
                results.append({
                    "id": n.id, "memory_type": n.memory_type, "text": n.content,
                    "cognitive_layer": n.cognitive_layer, "belief_status": n.belief_status,
                    "proof_count": len(n.source_fragment_ids), "visibility": n.visibility,
                    "created_by": n.created_by, "confidence": n.confidence,
                    "strength": strength_info["value"], "strength_breakdown": strength_info["breakdown"],
                })
            return make_response(
                data={"nodes": results, "total": len(results), "space_id": space_id},
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("list_my_memories failed: %s", e)
            return make_response(
                data={"nodes": [], "total": 0, "space_id": space_id}, space_id=space_id,
            )

    async def get_stats(self, space_id: str) -> dict[str, Any]:
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=10000)
        total = len(nodes)
        by_type: dict[str, int] = {}
        by_belief: dict[str, int] = {}
        by_layer: dict[str, int] = {}
        for n in nodes:
            by_type[n.memory_type] = by_type.get(n.memory_type, 0) + 1
            by_belief[n.belief_status] = by_belief.get(n.belief_status, 0) + 1
            by_layer[n.cognitive_layer] = by_layer.get(n.cognitive_layer, 0) + 1
        return {
            "total": total,
            "by_type": by_type,
            "by_belief": by_belief,
            "by_layer": by_layer,
            "space_id": space_id,
        }

    async def get_types(self, space_id: str) -> dict[str, Any]:
        nodes = await self._repo.query_nodes(domain_id=space_id, limit=10000)
        by_type: dict[str, int] = {}
        for n in nodes:
            by_type[n.memory_type] = by_type.get(n.memory_type, 0) + 1
        return {"types": by_type, "space_id": space_id}

    async def get_audit_trail(self, space_id: str, limit: int = 50) -> dict[str, Any]:
        superseded = await self._repo.query_nodes(
            domain_id=space_id, belief_status="superseded", limit=limit,
        )
        rejected = await self._repo.query_nodes(
            domain_id=space_id, belief_status="rejected", limit=limit,
        )
        pending = await self._repo.query_nodes(
            domain_id=space_id, belief_status="pending_review", limit=limit,
        )
        entries = []
        for n in superseded + rejected + pending:
            entries.append({
                "id": n.id,
                "memory_type": n.memory_type,
                "content": n.content[:200],
                "belief_status": n.belief_status,
                "superseded_by": n.superseded_by,
                "updated_at": n.updated_at,
            })
        return {"entries": entries[:limit], "space_id": space_id}

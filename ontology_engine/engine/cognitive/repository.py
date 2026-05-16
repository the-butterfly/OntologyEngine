"""Cognitive engine repository.

Provides high-level operations for CognitiveNode and DispositionProfile
management, wrapping the CognitiveStorageBackend abstraction layer.

Boundary: engine/cognitive/ -> storage/base.py (CognitiveStorageBackend)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveNodeConflictError,
    CognitiveNodeNotFoundError,
    DispositionProfileNotFoundError,
    InvalidBeliefTransitionError,
)
from ontology_engine.engine.cognitive.models import (
    VALID_BELIEF_STATUSES,
    VALID_COGNITIVE_LAYERS,
    VALID_MEMORY_TYPES,
    VALID_VISIBILITIES,
    CognitiveEdge,
    CognitiveNode,
    DispositionProfile,
)

if TYPE_CHECKING:
    from ontology_engine.storage.base import CognitiveStorageBackend

logger = logging.getLogger(__name__)


class CognitiveRepository:
    """Repository for CognitiveNode and DispositionProfile operations.

    Wraps CognitiveStorageBackend to provide domain-specific operations
    with validation, optimistic concurrency control, and history tracking.
    """

    def __init__(self, storage: CognitiveStorageBackend) -> None:
        self._storage = storage

    # --- CognitiveNode Operations ---

    async def create_node(self, node: CognitiveNode) -> CognitiveNode:
        self._validate_node(node)

        now = datetime.now(timezone.utc).isoformat()
        node.created_at = now
        node.updated_at = now

        await self._storage.save_cognitive_node(node.to_dict())

        logger.info("Created cognitive node %s (type=%s, layer=%s)", node.id, node.memory_type, node.cognitive_layer)
        return node

    async def get_node(self, node_id: str) -> CognitiveNode:
        data = await self._storage.get_cognitive_node(node_id)
        if data is None:
            raise CognitiveNodeNotFoundError(f"CognitiveNode '{node_id}' not found")
        return CognitiveNode.from_dict(data)

    async def update_node(
        self,
        node: CognitiveNode,
        reason: str | None = None,
        expected_version: int | None = None,
        action: str = "update",
    ) -> CognitiveNode:
        existing = await self._storage.get_cognitive_node(node.id)
        if existing is None:
            raise CognitiveNodeNotFoundError(f"CognitiveNode '{node.id}' not found")

        if expected_version is not None:
            if isinstance(existing, dict):
                current_version = existing.get("version", len(existing.get("history", [])))
            else:
                current_version = getattr(existing, "version", None) or len(getattr(existing, "history", []) or [])
            if current_version != expected_version:
                raise CognitiveNodeConflictError(
                    f"Version mismatch for '{node.id}': "
                    f"expected {expected_version}, current {current_version}"
                )

        now = datetime.now(timezone.utc).isoformat()

        history_entry = {
            "action": action,
            "timestamp": now,
            "reason": reason,
        }

        if node.history:
            merged_history = node.history + [history_entry]
        else:
            existing_history = existing.get("history", []) if isinstance(existing, dict) else []
            merged_history = existing_history + [history_entry]

        node.history = merged_history

        await self._storage.save_cognitive_node(node.to_dict())

        node.updated_at = now
        logger.info("Updated cognitive node %s", node.id)
        return node

    async def update_node_with_occ(
        self,
        node: CognitiveNode,
        expected_version: int,
    ) -> CognitiveNode:
        from ontology_engine.engine.cognitive.errors import OCCVersionConflict

        updates = {
            "content": node.content,
            "strength": node.strength,
            "feedback_weight": node.feedback_weight,
            "belief_status": node.belief_status,
            "attributes": node.attributes or {},
            "memory_type": node.memory_type,
            "entity_name": node.entity_name,
            "entity_type": node.entity_type,
            "scope": node.scope,
            "source_trust_tier": node.source_trust_tier,
            "last_confirmed_at": node.last_confirmed_at,
            "consolidation_reasoning": node.consolidation_reasoning,
            "valid_to": node.valid_to,
            "superseded_by": node.superseded_by,
            "confidence": node.confidence,
            "schema_ref": node.schema_ref,
            "extraction_hint": node.extraction_hint,
            "source_fragment_ids": node.source_fragment_ids or [],
            "tags": node.tags or {},
            "proof_count": node.proof_count,
            "confirmation_count": node.confirmation_count,
        }

        result = await self._storage.update_cognitive_node_with_occ(
            node.id, expected_version, updates
        )
        if result is None:
            current = await self._storage.get_cognitive_node(node.id)
            actual_version = current.get("version", 1) if current else expected_version
            raise OCCVersionConflict(node.id, expected_version, actual_version)

        return await self.get_node(node.id)

    async def delete_node(self, node_id: str) -> None:
        existing = await self._storage.get_cognitive_node(node_id)
        if existing is None:
            raise CognitiveNodeNotFoundError(f"CognitiveNode '{node_id}' not found")

        await self._storage.delete_cognitive_node(node_id)
        logger.info("Deleted cognitive node %s", node_id)

    async def query_nodes(
        self,
        memory_type: str | None = None,
        cognitive_layer: str | None = None,
        belief_status: str | None = None,
        domain_id: str | None = None,
        space_id: str | None = None,
        limit: int = 100,
        as_of: str | None = None,
        attributes_filter: dict[str, str] | None = None,
    ) -> list[CognitiveNode]:
        data_list = await self._storage.list_cognitive_nodes(
            memory_type=memory_type,
            cognitive_layer=cognitive_layer,
            belief_status=belief_status,
            domain_id=domain_id,
            space_id=space_id,
            limit=limit,
            as_of=as_of,
        )
        nodes = [CognitiveNode.from_dict(d) for d in data_list]
        if attributes_filter:
            filtered = []
            for n in nodes:
                attrs = n.attributes or {}
                if all(str(attrs.get(k)) == str(v) for k, v in attributes_filter.items()):
                    filtered.append(n)
            return filtered
        return nodes

    async def transition_belief(
        self,
        node_id: str,
        new_belief: str,
        reason: str | None = None,
    ) -> CognitiveNode:
        if new_belief not in VALID_BELIEF_STATUSES:
            raise CognitiveError(f"Invalid belief status: {new_belief}")

        node = await self.get_node(node_id)
        if not node.can_transition_to(new_belief):
            raise InvalidBeliefTransitionError(
                f"Cannot transition from '{node.belief_status}' to '{new_belief}'"
            )

        await self._storage.update_cognitive_node_belief(node_id, new_belief, reason)
        node.belief_status = new_belief
        node.updated_at = datetime.now(timezone.utc).isoformat()
        return node

    async def record_access(self, node_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        node = await self.get_node(node_id)
        node.access_count += 1
        node.last_access_at = now
        await self.update_node(node, reason="access", action="access")

    # --- DispositionProfile Operations ---

    async def create_profile(self, profile: DispositionProfile) -> DispositionProfile:
        await self._storage.save_disposition(profile.to_dict())
        return profile

    async def get_profile(self, profile_id: str) -> DispositionProfile:
        data = await self._storage.get_disposition(profile_id=profile_id)
        if data is None:
            raise DispositionProfileNotFoundError(f"DispositionProfile '{profile_id}' not found")
        return DispositionProfile.from_dict(data)

    async def get_profile_by_scene(self, scene: str, domain_id: str | None = None) -> DispositionProfile:
        data = await self._storage.get_disposition(scene=scene, domain_id=domain_id)
        if data is None:
            raise DispositionProfileNotFoundError(f"DispositionProfile for scene '{scene}' not found")
        return DispositionProfile.from_dict(data)

    async def compute_weights(self, profile: DispositionProfile) -> dict[str, float]:
        return await self._storage.compute_dynamic_weights(profile.to_dict())

    # --- Edge Operations ---

    async def create_cognitive_edge(self, edge: CognitiveEdge) -> None:
        now = datetime.now(timezone.utc).isoformat()

        if edge.edge_type == "CONSOLIDATED_INTO":
            props = {**edge.properties, "consolidated_at": now}
        else:
            if edge.created_at is None:
                edge.created_at = now
            props = {**edge.properties, "created_at": edge.created_at}

        await self._storage.save_cognitive_edge(
            edge_type=edge.edge_type,
            from_id=edge.from_id,
            to_id=edge.to_id,
            properties=props,
        )

    async def query_cognitive_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[CognitiveEdge]:
        data_list = await self._storage.list_cognitive_edges(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            limit=limit,
        )
        return [CognitiveEdge.from_dict(d) for d in data_list]

    # --- Validation ---

    def _validate_node(self, node: CognitiveNode) -> None:
        if node.memory_type not in VALID_MEMORY_TYPES:
            raise CognitiveError(f"Invalid memory_type: {node.memory_type}. Must be one of {VALID_MEMORY_TYPES}")
        if node.cognitive_layer not in VALID_COGNITIVE_LAYERS:
            raise CognitiveError(f"Invalid cognitive_layer: {node.cognitive_layer}. Must be one of {VALID_COGNITIVE_LAYERS}")
        if node.belief_status not in VALID_BELIEF_STATUSES:
            raise CognitiveError(f"Invalid belief_status: {node.belief_status}. Must be one of {VALID_BELIEF_STATUSES}")
        if node.visibility not in VALID_VISIBILITIES:
            raise CognitiveError(f"Invalid visibility: {node.visibility}. Must be one of {VALID_VISIBILITIES}")
        if not node.content:
            raise CognitiveError("CognitiveNode content cannot be empty")

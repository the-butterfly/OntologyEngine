"""Cognitive engine repository.

Provides high-level operations for CognitiveNode and DispositionProfile
management, wrapping the storage layer (KuzuGraphStore).

Boundary: engine/cognitive/ -> storage/graph/kuzu_store.py (via base.py interfaces)
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
    from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore

logger = logging.getLogger(__name__)


class CognitiveRepository:
    """Repository for CognitiveNode and DispositionProfile operations.

    Wraps KuzuGraphStore to provide domain-specific operations
    with validation, optimistic concurrency control, and history tracking.
    """

    def __init__(self, graph_store: "KuzuGraphStore"):
        """Initialize CognitiveRepository.

        Args:
            graph_store: Initialized KuzuGraphStore instance.
        """
        self._store = graph_store

    # --- CognitiveNode Operations ---

    async def create_node(self, node: CognitiveNode) -> CognitiveNode:
        """Create a new CognitiveNode.

        Args:
            node: CognitiveNode to create.

        Returns:
            Created CognitiveNode with timestamps populated.

        Raises:
            CognitiveError: If validation fails.
        """
        self._validate_node(node)

        now = datetime.now(timezone.utc).isoformat()
        node.created_at = now
        node.updated_at = now

        await self._store.upsert_cognitive_node(
            node_id=node.id,
            memory_type=node.memory_type,
            cognitive_layer=node.cognitive_layer,
            content=node.content,
            content_vector=node.content_vector,
            source_fragment_ids=node.source_fragment_ids,
            belief_status=node.belief_status,
            ttl_seconds=node.ttl_seconds,
            occurred_at=node.occurred_at,
            extraction_hint=node.extraction_hint,
            domain_id=node.domain_id,
            space_id=node.space_id,
            history=node.history,
            visibility=node.visibility,
            created_by=node.created_by,
            feedback_weight=node.feedback_weight,
            confidence=node.confidence,
            access_count=node.access_count,
            last_access_at=node.last_access_at,
            consolidated_at=node.consolidated_at,
            schema_ref=node.schema_ref,
            superseded_by=node.superseded_by,
            proof_count=node.proof_count,
            valid_from=node.valid_from,
            valid_to=node.valid_to,
            recorded_at=node.recorded_at,
            tags=node.tags,
            attributes=node.attributes,
            confirmation_count=node.confirmation_count,
        )

        logger.info("Created cognitive node %s (type=%s, layer=%s)", node.id, node.memory_type, node.cognitive_layer)
        return node

    async def get_node(self, node_id: str) -> CognitiveNode:
        """Get a CognitiveNode by ID.

        Args:
            node_id: Node ID.

        Returns:
            CognitiveNode instance.

        Raises:
            CognitiveNodeNotFoundError: If node doesn't exist.
        """
        data = await self._store.get_cognitive_node(node_id)
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
        """Update an existing CognitiveNode with optimistic concurrency control.

        Args:
            node: Updated CognitiveNode.
            reason: Optional reason for the update.
            expected_version: Optional version number for OCC. If provided,
                must match the current history length; otherwise raises
                CognitiveNodeConflictError.
            action: History action label (default "update").

        Returns:
            Updated CognitiveNode.

        Raises:
            CognitiveNodeNotFoundError: If node doesn't exist.
            CognitiveNodeConflictError: If concurrent modification detected.
        """
        existing = await self._store.get_cognitive_node(node.id)
        if existing is None:
            raise CognitiveNodeNotFoundError(f"CognitiveNode '{node.id}' not found")

        if expected_version is not None:
            existing_history = existing.get("history", []) if isinstance(existing, dict) else []
            current_version = int(len(existing_history))
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

        await self._store.upsert_cognitive_node(
            node_id=node.id,
            memory_type=node.memory_type,
            cognitive_layer=node.cognitive_layer,
            content=node.content,
            content_vector=node.content_vector,
            source_fragment_ids=node.source_fragment_ids,
            belief_status=node.belief_status,
            ttl_seconds=node.ttl_seconds,
            occurred_at=node.occurred_at,
            extraction_hint=node.extraction_hint,
            domain_id=node.domain_id,
            space_id=node.space_id,
            history=node.history,
            visibility=node.visibility,
            created_by=node.created_by,
            feedback_weight=node.feedback_weight,
            confidence=node.confidence,
            access_count=node.access_count,
            last_access_at=node.last_access_at,
            consolidated_at=node.consolidated_at,
            schema_ref=node.schema_ref,
            superseded_by=node.superseded_by,
            proof_count=node.proof_count,
            valid_from=node.valid_from,
            valid_to=node.valid_to,
            recorded_at=node.recorded_at,
            tags=node.tags,
            attributes=node.attributes,
        )

        node.updated_at = now
        logger.info("Updated cognitive node %s", node.id)
        return node

    async def delete_node(self, node_id: str) -> None:
        """Delete a CognitiveNode.

        Args:
            node_id: Node ID.

        Raises:
            CognitiveNodeNotFoundError: If node doesn't exist.
        """
        existing = await self._store.get_cognitive_node(node_id)
        if existing is None:
            raise CognitiveNodeNotFoundError(f"CognitiveNode '{node_id}' not found")

        await self._store.delete_cognitive_node(node_id)
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
    ) -> list[CognitiveNode]:
        """Query CognitiveNodes with filters.

        Args:
            memory_type: Filter by memory type.
            cognitive_layer: Filter by cognitive layer.
            belief_status: Filter by belief status.
            domain_id: Filter by domain ID.
            space_id: Filter by space ID.
            limit: Maximum results.
            as_of: ISO 8601 timestamp for temporal query.

        Returns:
            List of matching CognitiveNode instances.
        """
        data_list = await self._store.query_cognitive_nodes(
            memory_type=memory_type,
            cognitive_layer=cognitive_layer,
            belief_status=belief_status,
            domain_id=domain_id,
            space_id=space_id,
            limit=limit,
            as_of=as_of,
        )
        nodes = [CognitiveNode.from_dict(d) for d in data_list]
        return nodes

    async def transition_belief(
        self,
        node_id: str,
        new_belief: str,
        reason: str | None = None,
    ) -> CognitiveNode:
        """Transition a node's belief status.

        Args:
            node_id: Node ID.
            new_belief: New belief status.
            reason: Optional reason for transition.

        Returns:
            Updated CognitiveNode.

        Raises:
            CognitiveNodeNotFoundError: If node doesn't exist.
            InvalidBeliefTransitionError: If transition is invalid.
        """
        if new_belief not in VALID_BELIEF_STATUSES:
            raise CognitiveError(f"Invalid belief status: {new_belief}")

        node = await self.get_node(node_id)
        if not node.can_transition_to(new_belief):
            raise InvalidBeliefTransitionError(
                f"Cannot transition from '{node.belief_status}' to '{new_belief}'"
            )

        await self._store.update_cognitive_node_belief(node_id, new_belief, reason)
        node.belief_status = new_belief
        node.updated_at = datetime.now(timezone.utc).isoformat()
        return node

    async def record_access(self, node_id: str) -> None:
        """Record a node access for memory strength tracking.

        Increments access_count and updates last_access_at.

        Args:
            node_id: Node ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        node = await self.get_node(node_id)
        node.access_count += 1
        node.last_access_at = now
        await self.update_node(node, reason="access", action="access")

    # --- DispositionProfile Operations ---

    async def create_profile(self, profile: DispositionProfile) -> DispositionProfile:
        """Create or update a DispositionProfile (delegates to store)."""
        await self._store.upsert_disposition_profile(
            profile_id=profile.id,
            scene=profile.scene,
            skepticism=profile.skepticism,
            evidence_demand=profile.evidence_demand,
            abstraction_preference=profile.abstraction_preference,
            thoroughness=profile.thoroughness,
            recency_bias=profile.recency_bias,
            empathy=profile.empathy,
            risk_tolerance=profile.risk_tolerance,
            domain_id=profile.domain_id,
            space_id=profile.space_id,
        )
        return profile

    async def get_profile(self, profile_id: str) -> DispositionProfile:
        """Get a DispositionProfile by ID.

        Args:
            profile_id: Profile ID.

        Returns:
            DispositionProfile instance.

        Raises:
            DispositionProfileNotFoundError: If profile doesn't exist.
        """
        data = await self._store.get_disposition_profile(profile_id=profile_id)
        if data is None:
            raise DispositionProfileNotFoundError(f"DispositionProfile '{profile_id}' not found")
        return DispositionProfile.from_dict(data)

    async def get_profile_by_scene(self, scene: str, domain_id: str | None = None) -> DispositionProfile:
        """Get a DispositionProfile by scene.

        Args:
            scene: Scene/context.
            domain_id: Optional domain filter.

        Returns:
            DispositionProfile instance.

        Raises:
            DispositionProfileNotFoundError: If profile doesn't exist.
        """
        data = await self._store.get_disposition_profile(scene=scene, domain_id=domain_id)
        if data is None:
            raise DispositionProfileNotFoundError(f"DispositionProfile for scene '{scene}' not found")
        return DispositionProfile.from_dict(data)

    async def compute_weights(self, profile: DispositionProfile) -> dict[str, float]:
        """Compute dynamic type weights based on a DispositionProfile.

        Args:
            profile: DispositionProfile.

        Returns:
            Dictionary of memory_type -> weight.
        """
        return await self._store.compute_dynamic_weights(profile.to_dict())

    # --- Edge Operations ---

    async def create_cognitive_edge(self, edge: CognitiveEdge) -> None:
        """Create an edge between two CognitiveNodes.

        Args:
            edge: CognitiveEdge instance.
        """
        now = datetime.now(timezone.utc).isoformat()

        if edge.edge_type == "CONSOLIDATED_INTO":
            props = {**edge.properties, "consolidated_at": now}
        else:
            if edge.created_at is None:
                edge.created_at = now
            props = {**edge.properties, "created_at": edge.created_at}

        await self._store.create_cognitive_edge(
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
        """Query cognitive edges with optional filters.

        Args:
            from_id: Filter by source node ID.
            to_id: Filter by target node ID.
            edge_type: Filter by edge type (e.g. SUPERSEDES, CONTRADICTS).
            limit: Maximum number of edges to return.

        Returns:
            List of matching CognitiveEdge instances.
        """
        data_list = await self._store.query_cognitive_edges(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            limit=limit,
        )
        return [CognitiveEdge.from_dict(d) for d in data_list]

    async def delete_cognitive_edge(self, edge_id: str) -> None:
        """Delete a cognitive edge by its ID.

        Args:
            edge_id: The edge ID to delete.
        """
        await self._store.delete_edge(edge_id)

    # --- Validation ---

    def _validate_node(self, node: CognitiveNode) -> None:
        """Validate a CognitiveNode before creation.

        Args:
            node: CognitiveNode to validate.

        Raises:
            CognitiveError: If validation fails.
        """
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

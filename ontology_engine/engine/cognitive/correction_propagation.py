"""Correction propagation engine.

Propagates belief changes along cognitive edges. When a source node's
belief changes to contradicted or superseded, dependent nodes are
flagged as pending_review.

Design decisions:
- Minimal BFS propagation along SUMMARIZED_AS, CONSOLIDATED_INTO, COGNITIVE_RELATES_TO edges
- Cascade depth controlled by caller (default 3)
- Only accepted nodes are transitioned to pending_review
- Propagation stops on errors (best-effort per node)
- Uses query_cognitive_edges for proper cognitive edge traversal
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)

PROPAGATION_EDGE_TYPES = {"SUMMARIZED_AS", "CONSOLIDATED_INTO", "COGNITIVE_RELATES_TO"}
TRIGGER_BELIEFS = {"contradicted", "superseded", "rejected"}
MAX_CASCADE_NODES = 100


@dataclass
class PropagationResult:
    """Result of a correction propagation run.

    Attributes:
        reviewed_node_ids: IDs of nodes transitioned to pending_review.
        propagated_count: Number of nodes affected.
        depth_reached: Maximum depth reached during propagation.
        errors: Non-fatal errors encountered.
        needs_approval: Whether human approval is needed (≥ MAX_CASCADE_NODES).
        pending_node_ids: Nodes awaiting approval before processing.
    """
    reviewed_node_ids: list[str] = field(default_factory=list)
    propagated_count: int = 0
    depth_reached: int = 0
    errors: list[str] = field(default_factory=list)
    needs_approval: bool = False
    pending_node_ids: list[str] = field(default_factory=list)
    signal: str = ""


class CorrectionPropagation:
    """Minimal correction propagation engine.

    Propagates belief changes along SUMMARIZED_AS, CONSOLIDATED_INTO,
    and COGNITIVE_RELATES_TO edges. When a source node's belief changes
    to contradicted or superseded, dependent nodes are flagged
    as pending_review.
    """

    def __init__(self, repository: "CognitiveRepository"):
        self._repo = repository

    async def propagate(
        self,
        source_node_id: str,
        cascade_depth: int = 3,
        signal: str = "",
    ) -> PropagationResult:
        """Propagate belief change from a source node.

        Args:
            source_node_id: Node whose belief changed.
            cascade_depth: Maximum propagation depth.

        Returns:
            PropagationResult with affected nodes.
        """
        try:
            source = await self._repo.get_node(source_node_id)
        except Exception:
            return PropagationResult(signal=signal)

        if source.belief_status not in TRIGGER_BELIEFS:
            return PropagationResult(signal=signal)

        if signal:
            logger.info("Propagation signal: %s", signal)

        visited: set[str] = {source_node_id}
        reviewed_ids: list[str] = []
        errors: list[str] = []
        current_frontier = [source_node_id]
        depth = 0
        needs_approval = False
        pending_ids: list[str] = []

        while current_frontier and depth < cascade_depth:
            next_frontier = []
            for node_id in current_frontier:
                try:
                    neighbors = await self._get_propagation_neighbors(node_id)
                    for neighbor_id in neighbors:
                        if neighbor_id in visited:
                            continue
                        visited.add(neighbor_id)

                        if len(visited) > MAX_CASCADE_NODES:
                            pending_ids.append(neighbor_id)
                            continue

                        next_frontier.append(neighbor_id)
                        try:
                            target = await self._repo.get_node(neighbor_id)
                            if target.belief_status == "accepted":
                                target.attributes = dict(target.attributes or {})
                                memory_type = target.memory_type
                                if memory_type == "mental_model":
                                    target.attributes["is_stale"] = True
                                elif memory_type == "entity":
                                    target.attributes["needs_attribute_update"] = True
                                elif memory_type == "observation":
                                    target.attributes["needs_reinduction"] = True
                                elif memory_type == "rule":
                                    target.attributes["needs_revalidation"] = True
                                elif memory_type == "commitment":
                                    target.attributes["needs_reassessment"] = True
                                elif memory_type == "procedure":
                                    target.attributes["needs_reverification"] = True
                                target.attributes["stale_reason"] = f"upstream_{source.belief_status}"
                                target.attributes["stale_from"] = source_node_id
                                await self._repo.update_node(target)
                                await self._repo.transition_belief(
                                    neighbor_id,
                                    "pending_review",
                                    reason=f"Propagated from {node_id} (depth={depth + 1})",
                                )
                                reviewed_ids.append(neighbor_id)
                        except Exception as e:
                            errors.append(f"Failed to review {neighbor_id}: {e}")
                except Exception as e:
                    errors.append(f"Failed to get neighbors of {node_id}: {e}")
            current_frontier = next_frontier
            depth += 1

        if pending_ids or len(visited) > MAX_CASCADE_NODES:
            needs_approval = True
            pending_ids.extend([n for n in current_frontier if n not in pending_ids])

        return PropagationResult(
            reviewed_node_ids=reviewed_ids,
            propagated_count=len(reviewed_ids),
            depth_reached=depth,
            errors=errors,
            needs_approval=needs_approval,
            pending_node_ids=pending_ids,
            signal=signal,
        )

    async def _get_propagation_neighbors(self, node_id: str) -> list[str]:
        """Get neighbor node IDs along propagation edge types.

        Propagation direction semantics:
        - CONSOLIDATED_INTO (fragment → observation): only forward (out edges).
          When a fragment is corrected, its consolidated observation needs review.
          When an observation is corrected, its source fragments should NOT change.
        - SUMMARIZED_AS (observation → mental_model): only forward (out edges).
          When an observation is corrected, its summarized mental_model needs refresh.
        - COGNITIVE_RELATES_TO (bidirectional): both directions.
          Related entities should be notified regardless of direction.

        Args:
            node_id: Node to find neighbors for.

        Returns:
            List of neighbor node IDs.
        """
        neighbors: list[str] = []
        seen: set[str] = set()

        bidirectional_types = {"COGNITIVE_RELATES_TO"}

        for edge_type in PROPAGATION_EDGE_TYPES:
            try:
                out_edges = await self._repo.query_cognitive_edges(
                    from_id=node_id, edge_type=edge_type, limit=50,
                )
                for edge in out_edges:
                    nid = edge.to_id
                    if nid and nid != node_id and nid not in seen:
                        neighbors.append(nid)
                        seen.add(nid)

                if edge_type in bidirectional_types:
                    in_edges = await self._repo.query_cognitive_edges(
                        to_id=node_id, edge_type=edge_type, limit=50,
                    )
                    for edge in in_edges:
                        nid = edge.from_id
                        if nid and nid != node_id and nid not in seen:
                            neighbors.append(nid)
                            seen.add(nid)
            except Exception:
                continue
        return neighbors

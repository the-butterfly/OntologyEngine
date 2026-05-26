"""Evidence expansion deep module.

Encapsulates the 4-strategy serial fallback for expanding evidence
chains behind a CognitiveNode.  Strategies are independently testable;
the expander decides when to fallback.

Strategies (serial fallback order):
1. COG_SUPPORTED_BY edges — direct evidence links
2. source_fragment_ids — Layer-R fragments referenced by the node
3. CONSOLIDATED_INTO — consolidated node's source fragments
4. depth-2 recursive — expand each evidence node's own sources
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ontology_engine.engine.cognitive.errors import (
    CognitiveNodeNotFoundError,
    EvidenceExpansionError,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


@dataclass
class EvidenceItem:
    """A single evidence node with provenance metadata.

    Attributes:
        doc_id: Source node ID.
        content: Content text of the evidence.
        source: Expansion strategy that found this evidence.
        memory_type: Memory type of the source node.
        cognitive_layer: Cognitive layer of the source node.
        edge_type: Edge type connecting evidence to target.
        confidence: Confidence score (0-1).
        contribution: Contribution weight of this evidence.
    """
    doc_id: str
    content: str
    source: str = "unknown"
    memory_type: str = "fragment"
    cognitive_layer: str = "perception"
    edge_type: str = "SUPPORTS"
    confidence: float = 1.0
    contribution: float = 0.5


class EvidenceExpander:
    """Deep module: expand evidence chain for a cognitive node.

    Uses serial fallback — if a higher-priority strategy yields results,
    lower-priority strategies are skipped.  This matches the recall
    semantics where COG_SUPPORTED_BY is the most direct evidence path.
    """

    def __init__(self, repository: CognitiveRepository) -> None:
        self._repo = repository

    async def expand(
        self,
        node_id: str,
        space_id: str,
        depth: int = 1,
    ) -> list[EvidenceItem]:
        """Expand evidence using serial fallback strategy.

        Args:
            node_id: Target node to find evidence for.
            space_id: Space identifier (for future filtering).
            depth: Expansion depth (1 = direct, 2 = recursive).

        Returns:
            List of evidence items, possibly empty.

        Raises:
            CognitiveNodeNotFoundError: If the target node does not exist.
            EvidenceExpansionError: If a strategy encounters an unexpected error.
        """
        node = await self._repo.get_node(node_id)
        if node is None:
            raise CognitiveNodeNotFoundError(node_id)

        # Strategy 1: COG_SUPPORTED_BY edges
        evidence = await self._expand_supported_by(node_id)
        if evidence:
            return await self._maybe_expand_depth2(evidence, depth)

        # Strategy 2: source_fragment_ids
        evidence = await self._expand_source_fragments(node)
        if evidence:
            return await self._maybe_expand_depth2(evidence, depth)

        # Strategy 3: CONSOLIDATED_INTO → source_fragment_ids
        evidence = await self._expand_consolidated_into(node_id)
        return evidence

    async def _expand_supported_by(self, node_id: str) -> list[EvidenceItem]:
        """Strategy 1: Find nodes connected via COG_SUPPORTED_BY edges."""
        try:
            edges = await self._repo.query_cognitive_edges(
                to_id=node_id, edge_type="COG_SUPPORTED_BY", limit=10,
            )
        except Exception as exc:
            raise EvidenceExpansionError(
                node_id, "cog_supported_by", str(exc),
            ) from exc

        items: list[EvidenceItem] = []
        for edge in edges:
            try:
                source_node = await self._repo.get_node(edge.from_id)
            except Exception as exc:
                raise EvidenceExpansionError(
                    node_id, f"cog_supported_by.get_node({edge.from_id})", str(exc),
                ) from exc
            if source_node is None:
                logger.debug("COG_SUPPORTED_BY source node %s not found, skipping", edge.from_id)
                continue
            items.append(EvidenceItem(
                doc_id=source_node.id,
                content=source_node.content,
                source="cog_supported_by",
                memory_type=source_node.memory_type,
                cognitive_layer=source_node.cognitive_layer,
                edge_type="COG_SUPPORTED_BY",
                confidence=edge.properties.get("edge_confidence", 1.0),
                contribution=edge.properties.get("contribution", 0.5),
            ))
        return items

    async def _expand_source_fragments(self, node: Any) -> list[EvidenceItem]:
        """Strategy 2: Expand via node.source_fragment_ids."""
        if not node.source_fragment_ids:
            return []

        frag_count = len(node.source_fragment_ids)
        items: list[EvidenceItem] = []
        for idx, frag_id in enumerate(node.source_fragment_ids):
            try:
                frag = await self._repo.get_node(frag_id)
            except Exception as exc:
                raise EvidenceExpansionError(
                    node.id, f"source_fragment_ids.get_node({frag_id})", str(exc),
                ) from exc
            if frag is None:
                logger.debug("Fragment %s not found, skipping", frag_id)
                continue
            items.append(EvidenceItem(
                doc_id=frag.id,
                content=frag.content,
                source="source_fragment",
                memory_type=frag.memory_type,
                cognitive_layer=frag.cognitive_layer,
                edge_type="SUPPORTS",
                confidence=frag.confidence,
                contribution=round(1.0 / frag_count, 3) if idx < frag_count else 0.0,
            ))
        return items

    async def _expand_consolidated_into(self, node_id: str) -> list[EvidenceItem]:
        """Strategy 3: Find CONSOLIDATED_INTO edges, then expand their fragments."""
        try:
            edges = await self._repo.query_cognitive_edges(
                from_id=node_id, edge_type="CONSOLIDATED_INTO", limit=5,
            )
        except Exception as exc:
            raise EvidenceExpansionError(
                node_id, "consolidated_into", str(exc),
            ) from exc

        for edge in edges:
            try:
                consolidated = await self._repo.get_node(edge.to_id)
            except Exception as exc:
                raise EvidenceExpansionError(
                    node_id, f"consolidated_into.get_node({edge.to_id})", str(exc),
                ) from exc
            if consolidated is not None and consolidated.source_fragment_ids:
                return await self._expand_source_fragments(consolidated)
        return []

    async def _maybe_expand_depth2(
        self, evidence: list[EvidenceItem], depth: int,
    ) -> list[EvidenceItem]:
        """Recursively expand each evidence node's own sources at depth=2."""
        if depth < 2:
            return evidence

        depth2_items: list[EvidenceItem] = []
        for ev in list(evidence):
            try:
                ev_node = await self._repo.get_node(ev.doc_id)
            except Exception as exc:
                raise EvidenceExpansionError(
                    ev.doc_id, "depth2.get_node", str(exc),
                ) from exc
            if ev_node is None:
                continue
            if not ev_node.source_fragment_ids:
                continue
            for deeper_id in ev_node.source_fragment_ids:
                try:
                    deeper = await self._repo.get_node(deeper_id)
                except Exception as exc:
                    raise EvidenceExpansionError(
                        ev.doc_id, f"depth2.get_node({deeper_id})", str(exc),
                    ) from exc
                if deeper is None:
                    continue
                depth2_items.append(EvidenceItem(
                    doc_id=deeper.id,
                    content=deeper.content,
                    source="evidence_depth_2",
                    memory_type=deeper.memory_type,
                    cognitive_layer=deeper.cognitive_layer,
                    edge_type="SUPPORTS",
                    confidence=deeper.confidence,
                    contribution=0.1,
                ))
        return evidence + depth2_items

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


class CompilationService:

    def __init__(self, repository: "CognitiveRepository"):
        self._repo = repository

    async def compile_entity_page(
        self,
        entity_id: str,
        space_id: str,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                limit=5000,
            )
            entity_nodes = [
                n for n in nodes
                if n.entity_name == entity_id or entity_id in n.id
            ]
            entity_node_ids = {en.id for en in entity_nodes}
            entity_names: set[str] = set()
            src_fragment_ids: set[str] = set()
            for en in entity_nodes:
                if en.entity_name:
                    entity_names.add(en.entity_name)
                for fid in (en.source_fragment_ids or []):
                    src_fragment_ids.add(fid)
            related_nodes = [
                n for n in nodes
                if n.id not in entity_node_ids and (
                    n.id in src_fragment_ids or (
                        n.entity_name and n.entity_name in entity_names
                    )
                )
            ]
            page_nodes = entity_nodes + related_nodes[:20]
            node_list = []
            for n in page_nodes:
                strength_info = compute_strength(n)
                node_list.append({
                    "id": n.id,
                    "memory_type": n.memory_type,
                    "text": n.content,
                    "entity_name": n.entity_name,
                    "entity_type": n.entity_type,
                    "belief_status": n.belief_status,
                    "confidence": n.confidence,
                    "strength": strength_info["value"],
                    "created_by": n.created_by,
                    "created_at": n.created_at,
                    "tags": n.tags,
                    "attributes": n.attributes,
                })

            summary_sections = []
            primary = [n for n in entity_nodes if n.memory_type in ("entity", "observation")]
            if primary:
                overview_text = primary[0].content or ""
                if overview_text:
                    summary_sections.append(f"[Overview] {overview_text[:300]}")
            supporting = [n for n in related_nodes[:5] if n.content]
            if supporting:
                facts = "; ".join(n.content[:100] for n in supporting)
                summary_sections.append(f"[Related Facts] {facts}")
            if not summary_sections and entity_nodes:
                fallback = entity_nodes[0].content or ""
                if fallback:
                    summary_sections.append(f"[Info] {fallback[:300]}")
            summary = "\n".join(summary_sections)

            return make_response(
                data={
                    "entity_id": entity_id,
                    "summary": summary,
                    "nodes": node_list,
                    "total_nodes": len(node_list),
                    "entity_node_count": len(entity_nodes),
                    "related_node_count": len(related_nodes[:20]),
                    "space_id": space_id,
                },
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("compile_entity_page failed: %s", e)
            return make_response(
                data={"entity_id": entity_id, "summary": "", "nodes": [], "total_nodes": 0, "space_id": space_id},
                space_id=space_id,
            )

    async def compile_topic_page(
        self,
        topic: str,
        entity_ids: list[str],
        space_id: str,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                limit=5000,
            )
            entity_set = set(entity_ids)
            topic_lower = topic.lower()
            topic_nodes: list[Any] = []
            for n in nodes:
                matches = False
                if n.entity_name and n.entity_name in entity_set:
                    matches = True
                elif topic_lower in (n.content or "").lower():
                    matches = True
                elif any(topic_lower in str(v).lower() for v in (n.tags or {}).values()):
                    matches = True
                if matches:
                    topic_nodes.append(n)

            topic_nodes = topic_nodes[:100]
            node_list = []
            for n in topic_nodes:
                strength_info = compute_strength(n)
                node_list.append({
                    "id": n.id,
                    "memory_type": n.memory_type,
                    "text": n.content,
                    "entity_name": n.entity_name,
                    "entity_type": n.entity_type,
                    "belief_status": n.belief_status,
                    "confidence": n.confidence,
                    "strength": strength_info["value"],
                    "created_by": n.created_by,
                    "created_at": n.created_at,
                    "tags": n.tags,
                    "attributes": n.attributes,
                })
            return make_response(
                data={
                    "topic": topic,
                    "entity_ids": entity_ids,
                    "nodes": node_list,
                    "total_nodes": len(node_list),
                    "space_id": space_id,
                },
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("compile_topic_page failed: %s", e)
            return make_response(
                data={"topic": topic, "entity_ids": entity_ids, "nodes": [], "total_nodes": 0, "space_id": space_id},
                space_id=space_id,
            )

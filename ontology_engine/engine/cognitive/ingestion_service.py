from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    text: str
    entity_type: str = "unknown"
    identity_fields: dict[str, str] | None = None
    confidence: float = 0.3


@dataclass
class ExtractedRelation:
    subject: str
    predicate: str
    object_: str
    confidence: float = 0.3


class CognitiveExtractionPipeline:

    def __init__(self, repository: CognitiveRepository, llm_call: Any | None = None) -> None:
        self._repo = repository
        self._llm_call = llm_call

    async def extract(
        self,
        content: str,
        schema_ref: str | None = None,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        try:
            return self._extract_with_rules(content)
        except Exception as e:
            logger.warning("Rule extraction failed: %s", e)
            return [], []

    def _extract_with_rules(self, content: str) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        entities: list[ExtractedEntity] = []
        relations: list[ExtractedRelation] = []

        import re
        sentences = [s.strip() for s in re.split(r'[。！？.!?\n]', content) if s.strip()][:5]

        for sentence in sentences[:3]:
            words = sentence.split()
            for w in words[:200]:
                if len(w) >= 2 and (w[0].isupper() or any('\u4e00' <= c <= '\u9fff' for c in w)):
                    entity_type = "observation"
                    if any('\u4e00' <= c <= '\u9fff' for c in w):
                        entity_type = "entity"
                    entities.append(ExtractedEntity(text=w, entity_type=entity_type, confidence=0.5))

            chinese_segments = re.findall(r'[\u4e00-\u9fff]{2,8}', sentence)
            for seg in chinese_segments[:5]:
                if seg not in [e.text for e in entities]:
                    entities.append(ExtractedEntity(text=seg, entity_type="entity", confidence=0.3))

        return entities, relations


class CognitiveIngestionService:

    @staticmethod
    def _infer_tags(memory_type: str) -> dict[str, str]:
        mapping = {
            "entity": "world", "rule": "world", "constraint": "world",
            "observation": "world",
            "mental_model": "self", "opinion": "self",
            "commitment": "task", "task_state": "task", "procedure": "task", "episode": "task",
            "self_experience": "self", "fragment": "world",
        }
        return {"model": mapping.get(memory_type, "world")}

    def __init__(
        self,
        repository: CognitiveRepository,
        extraction_pipeline: CognitiveExtractionPipeline,
        vector_index: Any | None = None,
        fts5_manager: Any | None = None,
    ) -> None:
        self._repo = repository
        self._pipeline = extraction_pipeline
        self._vector = vector_index
        self._fts5 = fts5_manager

    async def ingest(
        self,
        content: str,
        space_id: str,
        memory_type: str = "fragment",
        tags: dict[str, str | list[str]] | None = None,
        metadata: dict[str, str] | None = None,
        source_trust_tier: str = "normal",
        scope: str = "",
        source_pipeline: str = "api",
        user_id: str = "system",
        visibility: str = "shared",
        confidence: float = 1.0,
        belief_status: str = "accepted",
    ) -> dict[str, Any]:
        source_content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        initial_tags = self._infer_tags(memory_type)
        merged_tags = {**initial_tags, **(tags or {})}

        from ontology_engine.engine.extraction.chunker import chunk_text
        chunk_result = chunk_text(content)
        if len(chunk_result.chunks) <= 1:
            fragment_ids = [await self._ingest_single_chunk(
                content, space_id, merged_tags, source_content_hash,
                source_trust_tier, source_pipeline, user_id, visibility, confidence, belief_status,
            )]
        else:
            fragment_ids = []
            for ci, chunk in enumerate(chunk_result.chunks):
                chunk_tags = {**merged_tags, "chunk_index": str(ci)}
                fid = await self._ingest_single_chunk(
                    chunk.content, space_id, chunk_tags, source_content_hash,
                    source_trust_tier, source_pipeline, user_id, visibility, confidence, belief_status,
                )
                fragment_ids.append(fid)

        entities, relations = await self._pipeline.extract(content)

        created_entity_ids: list[str] = []
        for entity in entities[:10]:
            try:
                entity_id = await self._resolve_or_create_entity(
                    entity, space_id, source_pipeline, user_id, visibility, confidence,
                )
                if entity_id:
                    created_entity_ids.append(entity_id)
            except Exception as e:
                logger.debug("Entity creation skipped for '%s': %s", entity.text, e)

        for relation in relations[:5]:
            try:
                from ontology_engine.engine.cognitive.models import CognitiveEdge as _CE
                await self._repo.create_cognitive_edge(_CE(
                    edge_type="COGNITIVE_RELATES_TO",
                    from_id=relation.subject,
                    to_id=relation.object_,
                ))
            except Exception as e:
                logger.debug("Relation edge creation skipped: %s", e)

        if memory_type != "fragment":
            node_id = f"mem:{memory_type}:{space_id}:{uuid.uuid4().hex[:12]}"
            node = _make_cognitive_node(
                id=node_id,
                content=content,
                space_id=space_id,
                domain_id=space_id,
                memory_type=memory_type,
                source_fragment_ids=fragment_ids,
                source_content_hash=source_content_hash,
                source_trust_tier=source_trust_tier,
                scope=scope,
                source_pipeline=source_pipeline,
                tags=merged_tags,
                created_by=user_id,
                visibility=visibility,
                confidence=confidence,
                belief_status=belief_status,
            )
            await self._repo.create_node(node)

            from ontology_engine.engine.cognitive.models import CognitiveEdge
            for fid in fragment_ids:
                await self._repo.create_cognitive_edge(CognitiveEdge(
                    edge_type="COG_SUPPORTED_BY",
                    from_id=fid,
                    to_id=node_id,
                ))

            if self._fts5:
                try:
                    await self._fts5.on_node_created(node)
                except Exception as e:
                    logger.warning("FTS5 sync failed for node %s: %s", node_id, e)

            if self._vector:
                try:
                    await self._vector.index_node(
                        node_id=node.id,
                        content=node.content,
                        memory_type=node.memory_type,
                        tags=node.tags,
                        space_id=node.space_id,
                    )
                except Exception as e:
                    logger.warning("Vector indexing failed for %s: %s", node_id, e)
                    attrs = dict(node.attributes or {})
                    attrs["_index_status"] = "pending"
                    node.attributes = attrs
                    try:
                        await self._repo.update_node(node)
                    except Exception:
                        logger.warning("Failed to mark node %s as pending for vector indexing", node_id)

            return {"node_id": node_id, "fragment_ids": fragment_ids, "entities": len(entities), "relations": len(relations), "created_entity_ids": created_entity_ids}

        return {"fragment_ids": fragment_ids, "entities": len(entities), "relations": len(relations), "created_entity_ids": created_entity_ids}

    async def _ingest_single_chunk(
        self,
        content: str,
        space_id: str,
        merged_tags: dict[str, str | list[str]],
        source_content_hash: str,
        source_trust_tier: str,
        source_pipeline: str,
        user_id: str,
        visibility: str,
        confidence: float,
        belief_status: str,
    ) -> str:
        fragment_id = f"frag:{space_id}:{uuid.uuid4().hex[:12]}"
        fragment = _make_fragment_node(
            id=fragment_id,
            content=content,
            space_id=space_id,
            domain_id=space_id,
            memory_type="fragment",
            tags=merged_tags,
            source_content_hash=source_content_hash,
            source_trust_tier=source_trust_tier,
            source_pipeline=source_pipeline,
            created_by=user_id,
            visibility=visibility,
            confidence=confidence,
            belief_status=belief_status,
        )
        await self._repo.create_node(fragment)

        if self._fts5:
            try:
                await self._fts5.on_node_created(fragment)
            except Exception as e:
                logger.warning("FTS5 sync failed for fragment %s: %s", fragment_id, e)

        if self._vector:
            try:
                await self._vector.index_node(
                    node_id=fragment_id,
                    content=content,
                    memory_type="fragment",
                    tags=merged_tags,
                    space_id=space_id,
                )
            except Exception as e:
                logger.warning("Vector indexing failed for fragment %s: %s", fragment_id, e)
                fragment.attributes = dict(fragment.attributes or {})
                fragment.attributes["_index_status"] = "pending"
                try:
                    await self._repo.update_node(fragment)
                except Exception:
                    pass

        return fragment_id

    async def retry_pending_indexes(self, space_id: str = "default", batch_size: int = 50) -> int:
        """Retry vector indexing for nodes marked as _index_status=pending.

        Returns the number of successfully re-indexed nodes.
        """
        if not self._vector:
            return 0

        re_indexed = 0
        try:
            nodes = await self._repo.query_nodes(
                space_id=space_id,
                limit=batch_size,
                attributes_filter={"_index_status": "pending"},
            )
            for node in nodes:
                try:
                    await self._vector.index_node(
                        node_id=node.id,
                        content=node.content,
                        memory_type=node.memory_type,
                        tags=node.tags or {},
                        space_id=node.space_id,
                    )
                    attrs = dict(node.attributes or {})
                    attrs.pop("_index_status", None)
                    node.attributes = attrs
                    await self._repo.update_node(node)
                    re_indexed += 1
                except Exception as e:
                    logger.warning("Retry index failed for %s: %s", node.id, e)
        except Exception as e:
            logger.warning("retry_pending_indexes failed: %s", e)

        return re_indexed

    async def _resolve_or_create_entity(
        self,
        entity: ExtractedEntity,
        space_id: str,
        source_pipeline: str,
        user_id: str,
        visibility: str = "shared",
        confidence: float = 1.0,
    ) -> str | None:
        """Resolve an extracted entity to an existing node or create a new one.

        Uses content-based dedup: if an entity node with matching content
        already exists in the space, reuse it.  Otherwise create a new node.
        """
        from ontology_engine.engine.cognitive.models import CognitiveNode

        existing = await self._repo.query_nodes(
            domain_id=space_id,
            memory_type="entity",
            limit=100,
        )
        for n in existing:
            if n.content and n.content.strip().lower() == entity.text.strip().lower():
                return n.id

        entity_id = f"mem:entity:{space_id}:{uuid.uuid4().hex[:12]}"
        node = CognitiveNode(
            id=entity_id,
            memory_type="entity",
            cognitive_layer="semantic",
            content=entity.text,
            domain_id=space_id,
            space_id=space_id,
            entity_name=entity.text,
            entity_type=entity.entity_type,
            confidence=confidence,
            visibility=visibility,
            tags={"model": "world"},
            source_pipeline=source_pipeline,
            created_by=user_id,
        )
        await self._repo.create_node(node)
        return entity_id


def _make_fragment_node(**kwargs: Any) -> Any:
    from ontology_engine.engine.cognitive.models import CognitiveNode
    kwargs.setdefault("cognitive_layer", "perception")
    kwargs.setdefault("belief_status", "accepted")
    return CognitiveNode(**kwargs)


def _make_cognitive_node(**kwargs: Any) -> Any:
    from ontology_engine.engine.cognitive.models import CognitiveNode
    kwargs.setdefault("cognitive_layer", "semantic")
    kwargs.setdefault("belief_status", "accepted")
    return CognitiveNode(**kwargs)

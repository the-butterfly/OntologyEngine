from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.deduplication_gate import WriteDecision
from ontology_engine.engine.cognitive.errors import (
    CognitiveError,
    CognitiveErrorCode,
    CognitiveNodeNotFoundError,
    InvalidMemoryTypeError,
    InvalidVisibilityError,
)
from ontology_engine.engine.cognitive.memory_utils import (
    RememberRequest,
    determine_visibility,
    extract_attributes,
    generate_memory_id,
    infer_cognitive_layer,
    infer_tags,
    make_response,
)
from ontology_engine.engine.cognitive.models import (
    VALID_MEMORY_TYPES,
    VALID_VISIBILITIES,
    CognitiveEdge,
    CognitiveNode,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
    from ontology_engine.engine.cognitive.cognitive_vector_index import CognitiveVectorIndex
    from ontology_engine.engine.cognitive.deduplication_gate import DeduplicationGate
    from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class RememberService:

    def __init__(
        self,
        repository: "CognitiveRepository",
        consolidation_engine: "ConsolidationEngine",
        entity_resolver: "EntityResolver",
        dedup_gate: "DeduplicationGate",
        vector_index: "CognitiveVectorIndex | None" = None,
        ingestion_service: Any | None = None,
    ):
        self._repo = repository
        self._consolidation = consolidation_engine
        self._resolver = entity_resolver
        self._dedup_gate = dedup_gate
        self._vector_index = vector_index
        self._ingestion = ingestion_service

    async def remember(self, req: RememberRequest) -> dict[str, Any]:
        if not req.content or not req.content.strip():
            raise CognitiveError("Content cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if not req.space_id or not req.space_id.strip():
            raise CognitiveError("Space ID cannot be empty", CognitiveErrorCode.EMPTY_INPUT)

        if req.memory_type not in VALID_MEMORY_TYPES:
            raise InvalidMemoryTypeError(req.memory_type, VALID_MEMORY_TYPES)

        if req.visibility is None:
            source = req.metadata.get("source") if req.metadata else None
            req.visibility = determine_visibility(req.content, req.memory_type, source)
        elif req.visibility not in VALID_VISIBILITIES:
            raise InvalidVisibilityError(req.visibility, VALID_VISIBILITIES)

        gate_result = await self._dedup_gate.check(
            content=req.content,
            space_id=req.space_id,
            memory_type=req.memory_type,
            tags=req.tags,
            confidence=req.confidence,
        )

        if gate_result.decision == WriteDecision.DUPLICATE:
            if gate_result.duplicate_of:
                try:
                    await self._repo.record_access(gate_result.duplicate_of)
                except Exception:
                    pass
            return make_response(
                data={
                    "memory_id": gate_result.duplicate_of,
                    "decision": "duplicate",
                    "reason": gate_result.reason,
                    "space_id": req.space_id,
                },
                space_id=req.space_id,
            )

        if gate_result.decision == WriteDecision.CONTRADICTION_CANDIDATE:
            req.belief_status = "pending_review"

        if gate_result.decision == WriteDecision.DELAYED:
            return make_response(
                data={
                    "memory_id": None,
                    "decision": "delayed",
                    "reason": gate_result.reason,
                    "marginal_value": gate_result.marginal_value,
                    "space_id": req.space_id,
                },
                space_id=req.space_id,
            )

        node_id = generate_memory_id(req.content, req.space_id, req.memory_type)
        cognitive_layer = infer_cognitive_layer(req.memory_type)
        initial_tags = infer_tags(req.memory_type)
        merged_tags = {**initial_tags, **(req.tags or {})}

        if self._ingestion is not None:
            try:
                ingest_result = await self._ingestion.ingest(
                    content=req.content,
                    space_id=req.space_id,
                    memory_type=req.memory_type,
                    tags=merged_tags,
                    metadata=req.metadata,
                    source_trust_tier="normal",
                    scope=merged_tags.get("model", "world"),
                    source_pipeline="api",
                    user_id=req.created_by or "system",
                    visibility=req.visibility,
                    confidence=req.confidence,
                    belief_status=req.belief_status,
                )
                node_id = ingest_result.get("node_id", node_id)
                return make_response(
                    data={
                        "memory_id": node_id,
                        "node_id": node_id,
                        "fragment_id": ingest_result.get("fragment_id"),
                        "decision": "contradiction_candidate" if req.belief_status == "pending_review" else "accepted",
                        "space_id": req.space_id,
                    },
                    space_id=req.space_id,
                )
            except Exception as e:
                logger.warning("IngestionService failed, falling back to direct create: %s", e)

        node = CognitiveNode(
            id=node_id,
            memory_type=req.memory_type,
            cognitive_layer=cognitive_layer,
            content=req.content,
            domain_id=req.space_id,
            space_id=req.space_id,
            visibility=req.visibility,
            created_by=req.created_by,
            confidence=req.confidence,
            belief_status=req.belief_status,
            occurred_at=req.occurred_at,
            schema_ref=req.schema_ref,
            valid_from=req.valid_from,
            valid_to=req.valid_to,
            recorded_at=req.recorded_at,
            tags=merged_tags,
            attributes=extract_attributes(req.memory_type, req.metadata),
            source_fragment_ids=req.source_fragment_ids or [],
            proof_count=len(req.source_fragment_ids) if req.source_fragment_ids else 0,
        )
        await self._repo.create_node(node)

        if self._vector_index is not None:
            try:
                await self._vector_index.index_node(
                    node_id=node.id,
                    content=node.content,
                    memory_type=node.memory_type,
                    tags=node.tags,
                    space_id=node.space_id,
                )
            except Exception as e:
                logger.debug("Vector indexing skipped for %s: %s", node.id, e)

        schema_extracted_nodes = await self._extract_schema_nodes(req, node_id)
        extracted_entities = await self._extract_entities(req)
        consolidation_triggered = await self._trigger_consolidation(req)
        superseded_node_id = await self._handle_supersede(req, node_id)

        return make_response(
            data={
                "memory_id": node_id,
                "memory_type": req.memory_type,
                "visibility": req.visibility,
                "extracted_entities": extracted_entities,
                "schema_extracted_nodes": schema_extracted_nodes,
                "consolidation_triggered": consolidation_triggered,
                "superseded_node_id": superseded_node_id,
            },
            space_id=req.space_id,
        )

    async def _extract_schema_nodes(self, req: RememberRequest, node_id: str) -> list[str]:
        if not req.schema_ref:
            return []
        try:
            schema_node_id = generate_memory_id(
                f"schema:{req.schema_ref}:{req.content[:60]}",
                req.space_id,
                "observation",
            )
            schema_node = CognitiveNode(
                id=schema_node_id,
                memory_type="observation",
                cognitive_layer="semantic",
                content=req.content,
                domain_id=req.space_id,
                space_id=req.space_id,
                visibility=req.visibility,
                created_by=req.created_by,
                confidence=req.confidence,
                schema_ref=req.schema_ref,
                source_fragment_ids=[node_id],
                extraction_hint="schema_guided",
            )
            await self._repo.create_node(schema_node)
            await self._repo.create_cognitive_edge(CognitiveEdge(
                edge_type="CONSOLIDATED_INTO",
                from_id=node_id,
                to_id=schema_node_id,
                properties={"consolidated_at": datetime.now(timezone.utc).isoformat()},
            ))
            return [schema_node_id]
        except Exception as e:
            logger.warning("Schema-guided extraction failed: %s", e)
            return []

    async def _extract_entities(self, req: RememberRequest) -> list[str]:
        try:
            entity_id = await self._resolver.resolve_and_create_or_reuse(
                entity_text=req.content[:50],
                entity_type="auto_extracted",
                space_id=req.space_id,
            )
            return [entity_id]
        except Exception as e:
            logger.debug("Entity extraction skipped: %s", e)
            return []

    async def _trigger_consolidation(self, req: RememberRequest) -> bool:
        if self._consolidation is None:
            return False
        try:
            async def _trigger():
                try:
                    return await self._consolidation.maybe_trigger_consolidation(
                        req.space_id, trigger="post_write"
                    )
                except Exception as e:
                    logger.warning("Consolidation post-write hook failed: %s", e)
                    return False

            asyncio.create_task(_trigger())
            return True
        except Exception as e:
            logger.warning("Consolidation post-write hook scheduling failed: %s", e)
            return False

    async def _handle_supersede(self, req: RememberRequest, node_id: str) -> str | None:
        if not req.supersede_target:
            return None
        try:
            target = await self._repo.get_node(req.supersede_target)
            target.superseded_by = node_id
            target.belief_status = "superseded"
            target.confidence = 0.0
            reason = req.supersede_reason or "correction"
            await self._repo.update_node(target, reason=reason, action="superseded")
            edge = CognitiveEdge(
                edge_type="SUPERSEDES",
                from_id=node_id,
                to_id=target.id,
            )
            await self._repo.create_cognitive_edge(edge)
            return target.id
        except CognitiveNodeNotFoundError:
            logger.warning("Supersede target '%s' not found", req.supersede_target)
        except Exception as e:
            logger.warning("Supersede failed for '%s': %s", req.supersede_target, e)
        return None

from __future__ import annotations

from typing import Any

from ontology_engine.engine.cognitive.factory import MemoryAPISingleton
from ontology_engine.engine.cognitive.errors import CognitiveNodeNotFoundError


class MemoryService:

    def __init__(self, embedding_config: dict[str, Any] | None = None):
        self._embedding_config = embedding_config

    async def get_api(self) -> Any:
        return await MemoryAPISingleton.get_or_create(embedding_config=self._embedding_config)

    async def close(self) -> None:
        await MemoryAPISingleton.close()

    async def remember(
        self,
        space_id: str,
        content: str = "",
        tags: dict[str, str | list[str]] | list[str] | None = None,
        memory_type: str = "fragment",
        visibility: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_by: str | None = None,
        confidence: float = 1.0,
        schema_ref: str | None = None,
        supersede_target: str | None = None,
        supersede_reason: str | None = None,
        belief_status: str = "accepted",
        valid_from: str | None = None,
        valid_to: str | None = None,
        recorded_at: str | None = None,
        occurred_at: str | None = None,
        source_pipeline: str | None = None,
        auto_consolidate: bool = False,
        source_trust_tier: str | None = None,
    ) -> dict[str, Any]:
        api = await self.get_api()
        # Normalize list[str] tags to dict[str, str] for MemoryAPI
        normalized_tags: dict[str, str | list[str]] | None = None
        if isinstance(tags, list):
            normalized_tags = {t: t for t in tags}
        elif isinstance(tags, dict):
            normalized_tags = tags
        result = await api.remember(
            content=content,
            space_id=space_id,
            tags=normalized_tags,
            memory_type=memory_type,
            visibility=visibility,
            metadata=metadata,
            created_by=created_by,
            confidence=confidence,
            schema_ref=schema_ref,
            supersede_target=supersede_target,
            supersede_reason=supersede_reason,
            belief_status=belief_status,
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at,
            occurred_at=occurred_at,
            source_pipeline=source_pipeline,
            auto_consolidate=auto_consolidate,
            source_trust_tier=source_trust_tier,
        )
        return result

    async def recall(
        self,
        space_id: str,
        query: str = "",
        memory_type: str | None = None,
        max_results: int = 10,
        include_evidence: bool = True,
        evidence_depth: int = 1,
        as_of: str | None = None,
        token_budget: int | None = None,
        belief_status_filter: str | None = None,
        audit_trail: bool = False,
        user_id: str | None = None,
        min_confidence: float = 0.5,
        disposition_override: str | None = None,
        cognitive_layer: str | None = None,
        include_superseded: bool = False,
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.recall(
            query=query,
            space_id=space_id,
            memory_type=memory_type,
            max_results=max_results,
            include_evidence=include_evidence,
            evidence_depth=evidence_depth,
            as_of=as_of,
            token_budget=token_budget,
            belief_status_filter=belief_status_filter,
            audit_trail=audit_trail,
            user_id=user_id,
            min_confidence=min_confidence,
            disposition_override=disposition_override,
            cognitive_layer=cognitive_layer,
            include_superseded=include_superseded,
        )
        return result

    async def reflect(
        self,
        space_id: str,
        query: str = "",
        max_iterations: int = 10,
        focus_types: list[str] | None = None,
        async_mode: bool = True,
        skip_consolidation: bool = False,
        skip_forgetting: bool = False,
        cascade_depth: int = 3,
        skip_correction_propagation: bool = False,
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.reflect(
            query=query,
            space_id=space_id,
            max_iterations=max_iterations,
            focus_types=focus_types,
            async_mode=async_mode,
            skip_consolidation=skip_consolidation,
            skip_forgetting=skip_forgetting,
            cascade_depth=cascade_depth,
            skip_correction_propagation=skip_correction_propagation,
        )
        return result

    async def approve_memory(
        self,
        node_id: str = "",
        action: str = "approve",
        modifier_id: str = "user",
        comment: str = "",
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.approve_memory(
            node_id=node_id,
            action=action,
            modifier_id=modifier_id,
            comment=comment,
        )
        return result

    async def run_consolidation(self, space_id: str) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.run_consolidation(space_id)
        return result

    async def run_forgetting(
        self, space_id: str, days_elapsed: int = 1
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.run_forgetting(space_id, days_elapsed=days_elapsed)
        return result

    async def dream(self, space_id: str) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.dream(space_id)
        return result

    async def get_stats(self, space_id: str) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_stats(space_id)
        return result

    async def get_types(self, space_id: str) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_types(space_id)
        return result

    async def get_audit_trail(
        self, space_id: str, limit: int = 50
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_audit_trail(space_id, limit=limit)
        return result

    async def list_nodes(
        self,
        space_id: str,
        memory_type: str | None = None,
        belief_status: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.list_nodes(
            space_id,
            memory_type=memory_type,
            belief_status=belief_status,
            limit=limit,
        )
        return result

    async def list_edges(
        self,
        space_id: str,
        edge_type: str | None = None,
        from_id: str | None = None,
        to_id: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.list_edges(
            space_id,
            edge_type=edge_type,
            from_id=from_id,
            to_id=to_id,
            limit=limit,
        )
        return result

    async def get_memory_graph(
        self,
        space_id: str,
        memory_type: str | None = None,
        belief_status: str | None = None,
        edge_type: str | None = None,
        node_limit: int = 500,
        edge_limit: int = 500,
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_memory_graph(
            space_id,
            memory_type=memory_type,
            belief_status=belief_status,
            edge_type=edge_type,
            node_limit=node_limit,
            edge_limit=edge_limit,
        )
        return result

    async def get_node(
        self, space_id: str, node_id: str
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_node(space_id, node_id)
        return result

    async def get_evidence(
        self, space_id: str, node_id: str, depth: int = 1
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_evidence(space_id, node_id, depth=depth)
        return result

    async def correct_node(
        self,
        space_id: str,
        node_id: str,
        corrected_text: str,
        reason: str = "",
        user_id: str = "system",
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.correct_memory(
            node_id=node_id,
            corrected_text=corrected_text,
            reason=reason,
            user_id=user_id,
        )
        return result

    async def get_reflection_status(
        self, reflection_id: str
    ) -> dict[str, Any]:
        api = await self.get_api()
        result = await api.get_reflection_status(reflection_id)
        return result

    def is_node_not_found_error(self, exc: Exception) -> bool:
        return isinstance(exc, CognitiveNodeNotFoundError)

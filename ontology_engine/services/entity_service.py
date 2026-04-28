# ontology_engine/services/entity_service.py
"""Entity management service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ontology_engine.services.dto import (
    EntityCreateRequest,
    EntityResponse,
    RelationResponse,
    NeighborResponse,
    BatchOperationResult,
    ConceptNotDefinedError,
)
from ontology_engine.storage.base import StorageBackend, EntityInstance, RelationInstance

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema


class EntityService:
    """Entity management service.

    Handles entity CRUD, batch operations, and relations.
    """

    def __init__(
        self,
        storage: StorageBackend,
        schema: KGMLSchema | None = None,
    ):
        """Initialize EntityService.

        Args:
            storage: StorageBackend instance
            schema: Optional KGMLSchema for validation
        """
        self.storage = storage
        self.schema = schema

    async def create_entity(
        self,
        fact_object: str,
        entity_id: str,
        attributes: dict[str, Any] | None = None,
        *,
        concept_type: str | None = None,
        atomic: bool = False,
    ) -> EntityResponse:
        fo = concept_type or fact_object

        if self.schema:
            concept_names = [c.name for c in self.schema.concepts]
            if fo not in concept_names:
                raise ConceptNotDefinedError(fo)

        entity = EntityInstance(
            _fact_object=fo,
            entity_id=entity_id,
            data=attributes if attributes else {}
        )

        if atomic:
            try:
                await self.storage.save_entity(entity)
            except Exception:
                raise
        else:
            await self.storage.save_entity(entity)

        return EntityResponse.from_domain(entity)

    async def batch_create(
        self,
        entities: list[EntityCreateRequest]
    ) -> BatchOperationResult:
        """Batch create entities.

        Args:
            entities: List of entity creation requests

        Returns:
            BatchOperationResult with success/error counts
        """
        results = []
        errors = []

        for req in entities:
            try:
                entity = await self.create_entity(
                    fact_object=req.fact_object,
                    entity_id=req.entity_id,
                    attributes=req.attributes
                )
                results.append(entity)
            except Exception as e:
                errors.append({
                    "entity_id": req.entity_id,
                    "error": str(e)
                })

        return BatchOperationResult(
            success_count=len(results),
            error_count=len(errors),
            entities=results,
            errors=errors
        )

    async def get_entity(
        self,
        fact_object: str,
        entity_id: str
    ) -> EntityResponse | None:
        """Get an entity by fact object type and ID."""
        entity = await self.storage.get_entity(fact_object, entity_id)
        if entity is None:
            return None
        return EntityResponse.from_domain(entity)

    async def query_entities(
        self,
        fact_object: str | None = None,
        filters: dict[str, Any] | None = None,
        *,
        concept_type: str | None = None,
    ) -> list[EntityResponse]:
        """Query entities with optional filters.

        Args:
            fact_object: Filter by fact object type
            filters: Attribute filters
            concept_type: Backward-compatible alias for fact_object
        """
        fo = concept_type or fact_object
        entities = await self.storage.query_entities(
            fact_object=fo or "",
            filters=filters
        )

        return [EntityResponse.from_domain(e) for e in entities]

    async def create_relation(
        self,
        relation_name: str,
        from_id: str,
        to_id: str,
        attributes: dict[str, Any] | None = None,
        *,
        relation_type: str | None = None,
    ) -> RelationResponse:
        """Create a relation between entities.

        Args:
            relation_name: Name of relation
            from_id: Source entity ID
            to_id: Target entity ID
            attributes: Relation attributes
            relation_type: Backward-compatible alias for relation_name
        """
        rn = relation_type or relation_name

        relation = RelationInstance(
            relation_name=rn,
            from_entity_id=from_id,
            to_entity_id=to_id,
            data=attributes if attributes else {}
        )

        await self.storage.save_relation(relation)

        return RelationResponse(
            relation_name=rn,
            from_id=from_id,
            to_id=to_id,
            attributes=attributes
        )

    async def get_neighbors(
        self,
        entity_id: str,
        relation_name: str | None = None,
        depth: int = 1,
        *,
        relation_type: str | None = None,
    ) -> list[NeighborResponse]:
        """Get neighboring entities.

        Args:
            entity_id: Source entity ID
            relation_name: Filter by relation name
            depth: Traversal depth (max 2 in Phase 1)
            relation_type: Backward-compatible alias for relation_name
        """
        if depth > 2:
            raise ValueError("Phase 1 maximum depth is 2")

        rn = relation_type or relation_name
        if rn is None and self.schema:
            rn = self.schema.get_first_relation_name()
        neighbors = await self.storage.get_neighbors(
            entity_id=entity_id,
            relation_name=rn or "",
            direction="outgoing"
        )

        results = []
        for entity, rel in neighbors:
            entity_resp = EntityResponse.from_domain(entity)
            rel_resp = RelationResponse(
                relation_name=rel.relation_name if hasattr(rel, 'relation_name') else rn or "",
                from_id=entity_id,
                to_id=entity.entity_id,
                attributes=rel.data if hasattr(rel, 'data') else {}
            )
            results.append(NeighborResponse(
                entity=entity_resp,
                relation=rel_resp
            ))

        return results

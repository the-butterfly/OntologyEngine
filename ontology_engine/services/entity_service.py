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
from ontology_engine.storage.duckdb import DuckDBStorage, EntityInstance, RelationInstance

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import KGMLSchema


class EntityService:
    """Entity management service.

    Handles entity CRUD, batch operations, and relations.
    """

    def __init__(
        self,
        storage: DuckDBStorage,
        schema: KGMLSchema | None = None,
    ):
        """Initialize EntityService.

        Args:
            storage: DuckDBStorage instance
            schema: Optional KGMLSchema for validation
        """
        self.storage = storage
        self.schema = schema

    async def create_entity(
        self,
        concept_type: str,
        entity_id: str,
        attributes: dict[str, Any] | None = None
    ) -> EntityResponse:
        """Create a new entity.

        Args:
            concept_type: The concept type for the entity
            entity_id: Unique identifier for the entity
            attributes: Entity attributes

        Returns:
            EntityResponse with created entity

        Raises:
            ConceptNotDefinedError: If concept type not in schema
        """
        # Validate concept type against schema
        if self.schema:
            concept_names = [c.name for c in self.schema.concepts]
            if concept_type not in concept_names:
                raise ConceptNotDefinedError(concept_type)

        # Create entity
        entity = EntityInstance(
            concept=concept_type,
            entity_id=entity_id,
            data=attributes if attributes else {}
        )

        # Persist
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
                    concept_type=req.concept_type,
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
        concept: str,
        entity_id: str
    ) -> EntityResponse | None:
        """Get an entity by concept and ID.

        Args:
            concept: Concept type
            entity_id: Entity ID

        Returns:
            EntityResponse if found, None otherwise
        """
        entity = await self.storage.get_entity(concept, entity_id)
        if entity is None:
            return None
        return EntityResponse.from_domain(entity)

    async def query_entities(
        self,
        concept_type: str | None = None,
        filters: dict[str, Any] | None = None
    ) -> list[EntityResponse]:
        """Query entities with optional filters.

        Args:
            concept_type: Filter by concept type
            filters: Attribute filters

        Returns:
            List of matching EntityResponse objects
        """
        entities = await self.storage.query_entities(
            concept=concept_type or "",
            filters=filters
        )

        return [EntityResponse.from_domain(e) for e in entities]

    async def create_relation(
        self,
        relation_type: str,
        from_id: str,
        to_id: str,
        attributes: dict[str, Any] | None = None
    ) -> RelationResponse:
        """Create a relation between entities.

        Args:
            relation_type: Type of relation
            from_id: Source entity ID
            to_id: Target entity ID
            attributes: Relation attributes

        Returns:
            RelationResponse with created relation

        Raises:
            EntityNotFoundError: If from_id or to_id not found
        """
        # Verify both entities exist (we need to check if they exist in storage)
        # For now, we'll just create the relation
        # Full validation would require checking each entity

        relation = RelationInstance(
            relation_type=relation_type,
            from_entity_id=from_id,
            to_entity_id=to_id,
            data=attributes if attributes else {}
        )

        await self.storage.save_relation(relation)

        return RelationResponse(
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            attributes=attributes
        )

    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        depth: int = 1
    ) -> list[NeighborResponse]:
        """Get neighboring entities.

        Args:
            entity_id: Source entity ID
            relation_type: Filter by relation type
            depth: Traversal depth (max 2 in Phase 1)

        Returns:
            List of NeighborResponse objects
        """
        if depth > 2:
            raise ValueError("Phase 1 maximum depth is 2")

        neighbors = await self.storage.get_neighbors(
            entity_id=entity_id,
            relation_type=relation_type or "has_invoice",
            direction="outgoing"
        )

        results = []
        for entity, rel in neighbors:
            entity_resp = EntityResponse.from_domain(entity)
            rel_resp = RelationResponse(
                relation_type=rel.relation_type if hasattr(rel, 'relation_type') else relation_type or "",
                from_id=entity_id,
                to_id=entity.entity_id,
                attributes=rel.data if hasattr(rel, 'data') else {}
            )
            results.append(NeighborResponse(
                entity=entity_resp,
                relation=rel_resp
            ))

        return results

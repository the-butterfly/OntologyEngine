# ontology_engine/services/ingestion_service.py
"""Ingestion service for importing entities and relations."""

from __future__ import annotations

from typing import Any

from ontology_engine.services.dto import (
    IngestionRequest,
    IngestionResult,
    EntityCreateRequest,
)
from ontology_engine.services.entity_service import EntityService
from ontology_engine.storage.duckdb import DuckDBStorage, EntityInstance, RelationInstance


class IngestionService:
    """Ingestion service.

    Handles bulk import of entities and relations from various sources.
    """

    def __init__(
        self,
        storage: DuckDBStorage,
        entity_service: EntityService,
    ):
        """Initialize IngestionService.

        Args:
            storage: StorageBackend instance
            entity_service: EntityService for entity creation
        """
        self.storage = storage
        self.entity_service = entity_service

    async def import_instances(
        self,
        request: IngestionRequest
    ) -> IngestionResult:
        """Import entities and relations in bulk.

        Args:
            request: IngestionRequest with entities and relations

        Returns:
            IngestionResult with counts and any errors
        """
        errors = []
        entity_count = 0
        relation_count = 0

        # Import entities
        for entity_data in request.entities:
            try:
                entity = EntityInstance(
                    concept=entity_data.concept_type,
                    entity_id=entity_data.entity_id,
                    data=entity_data.attributes if entity_data.attributes else {}
                )
                await self.storage.save_entity(entity)
                entity_count += 1
            except Exception as e:
                errors.append({
                    "entity_id": entity_data.entity_id,
                    "error": str(e)
                })

        # Import relations
        for rel_data in request.relations:
            try:
                relation = RelationInstance(
                    relation_type=rel_data.relation_type,
                    from_entity_id=rel_data.from_id,
                    to_entity_id=rel_data.to_id,
                    data=rel_data.attributes if rel_data.attributes else {}
                )
                await self.storage.save_relation(relation)
                relation_count += 1
            except Exception as e:
                errors.append({
                    "from_id": rel_data.from_id,
                    "to_id": rel_data.to_id,
                    "relation_type": rel_data.relation_type,
                    "error": str(e)
                })

        return IngestionResult(
            entity_count=entity_count,
            relation_count=relation_count,
            error_count=len(errors),
            errors=errors
        )

    async def import_from_dict(
        self,
        data: dict[str, Any]
    ) -> IngestionResult:
        """Import from a dictionary format.

        Expected format:
        {
            "entities": [
                {"concept_type": "Supplier", "entity_id": "S001", "attributes": {...}}
            ],
            "relations": [
                {"relation_type": "has_invoice", "from_id": "S001", "to_id": "INV001", ...}
            ]
        }

        Args:
            data: Dictionary with entities and relations

        Returns:
            IngestionResult with counts
        """
        entities = [
            EntityCreateRequest(
                concept_type=e.get("concept_type", ""),
                entity_id=e.get("entity_id", ""),
                attributes=e.get("attributes", {})
            )
            for e in data.get("entities", [])
        ]

        from ontology_engine.services.dto import RelationCreateRequest
        relations = [
            RelationCreateRequest(
                relation_type=r.get("relation_type", ""),
                from_id=r.get("from_id", ""),
                to_id=r.get("to_id", ""),
                attributes=r.get("attributes", {})
            )
            for r in data.get("relations", [])
        ]

        request = IngestionRequest(
            entities=entities,
            relations=relations
        )

        return await self.import_instances(request)

    async def validate_import(
        self,
        request: IngestionRequest
    ) -> tuple[list[dict], list[dict]]:
        """Validate import data without persisting.

        Args:
            request: IngestionRequest to validate

        Returns:
            Tuple of (valid_entity_ids, invalid_reasons)
        """
        valid_entities = []
        invalid_reasons = []

        # Validate entities
        for entity_data in request.entities:
            if not entity_data.entity_id:
                invalid_reasons.append({
                    "type": "entity",
                    "error": "entity_id is required"
                })
                continue
            if not entity_data.concept_type:
                invalid_reasons.append({
                    "entity_id": entity_data.entity_id,
                    "type": "entity",
                    "error": "concept_type is required"
                })
                continue
            valid_entities.append(entity_data.entity_id)

        # Validate relations
        for rel_data in request.relations:
            if not rel_data.from_id or not rel_data.to_id:
                invalid_reasons.append({
                    "type": "relation",
                    "error": "from_id and to_id are required"
                })
                continue
            if rel_data.from_id not in valid_entities:
                invalid_reasons.append({
                    "from_id": rel_data.from_id,
                    "type": "relation",
                    "error": "from_id not in entity list"
                })
            if rel_data.to_id not in valid_entities:
                invalid_reasons.append({
                    "to_id": rel_data.to_id,
                    "type": "relation",
                    "error": "to_id not in entity list"
                })

        return valid_entities, invalid_reasons

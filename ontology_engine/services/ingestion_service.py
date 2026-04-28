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
from ontology_engine.storage.base import StorageBackend, EntityInstance, RelationInstance


class IngestionService:
    """Ingestion service.

    Handles bulk import of entities and relations from various sources.
    """

    def __init__(
        self,
        storage: StorageBackend,
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
                    _fact_object=entity_data.fact_object,
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
                    relation_name=rel_data.relation_name,
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
                    "relation_name": rel_data.relation_name,
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
        data: dict[str, Any],
        space_id: str | None = None
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
            space_id: Space ID to associate with imported entities

        Returns:
            IngestionResult with counts
        """
        entities = [
            EntityCreateRequest(
                fact_object=e.get("fact_object", "") or e.get("concept_type", ""),
                entity_id=e.get("entity_id", ""),
                attributes=e.get("attributes", {})
            )
            for e in data.get("entities", [])
        ]

        from ontology_engine.services.dto import RelationCreateRequest
        relations = [
            RelationCreateRequest(
                relation_name=r.get("relation_name", "") or r.get("relation_type", ""),
                from_id=r.get("from_id", ""),
                to_id=r.get("to_id", ""),
                attributes=r.get("attributes", {})
            )
            for r in data.get("relations", [])
        ]

        request = IngestionRequest(
            entities=entities,
            relations=relations,
            space_id=space_id
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
            if not entity_data.fact_object:
                invalid_reasons.append({
                    "entity_id": entity_data.entity_id,
                    "type": "entity",
                    "error": "fact_object is required"
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

    async def ingest_structured(
        self,
        space_id: str,
        data: dict[str, Any],
        format_type: str = "yaml",
    ) -> dict[str, Any]:
        result = await self.import_from_dict(data, space_id=space_id)
        return {
            "entity_count": result.entity_count,
            "relation_count": result.relation_count,
            "error_count": result.error_count,
            "errors": result.errors,
            "channel": "fast",
        }

    async def ingest_unstructured(
        self,
        space_id: str,
        documents: list[dict[str, Any]],
        pipeline_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from ontology_engine.engine.extraction.pipeline import ExtractionPipeline
        from ontology_engine.storage.base import KnowledgeFragment

        fragments_created = 0
        entities_created = 0
        relations_created = 0

        for doc in documents:
            text = doc.get("text", "")
            document_id = doc.get("document_id", "")
            dataset_id = doc.get("dataset_id", space_id)

            chunk_size = (pipeline_config or {}).get("chunk_size", 1000)
            chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

            for idx, chunk in enumerate(chunks):
                fragment = KnowledgeFragment(
                    dataset_id=dataset_id,
                    document_id=document_id,
                    chunk_index=idx,
                    text=chunk,
                    extraction_status="pending",
                )
                await self.storage.save_knowledge_fragment(fragment)
                fragments_created += 1

        pipeline = ExtractionPipeline()
        all_fragments = await self.storage.list_knowledge_fragments(
            dataset_id=space_id, extraction_status="pending"
        )

        for fragment in all_fragments:
            try:
                extraction_result = await pipeline.extract(fragment.text)
                for entity_data in extraction_result.get("entities", []):
                    entity = EntityInstance(
                        _fact_object=entity_data.get("_fact_object", "Unknown"),
                        entity_id=entity_data.get("entity_id", ""),
                        data=entity_data.get("data", {}),
                        source_pipeline="extraction",
                    )
                    await self.storage.save_entity(entity)
                    entities_created += 1

                for rel_data in extraction_result.get("relations", []):
                    relation = RelationInstance(
                        relation_name=rel_data.get("relation_name", ""),
                        from_entity_id=rel_data.get("from_entity_id", ""),
                        to_entity_id=rel_data.get("to_entity_id", ""),
                        data=rel_data.get("data", {}),
                        source_pipeline="extraction",
                    )
                    await self.storage.save_relation(relation)
                    relations_created += 1

                fragment.extraction_status = "completed"
                await self.storage.save_knowledge_fragment(fragment)
            except Exception:
                fragment.extraction_status = "failed"
                await self.storage.save_knowledge_fragment(fragment)

        return {
            "fragments_created": fragments_created,
            "entities_created": entities_created,
            "relations_created": relations_created,
            "channel": "slow",
        }

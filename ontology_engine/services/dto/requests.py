# ontology_engine/services/dto/requests.py
"""Request DTOs for service layer."""

from __future__ import annotations

from typing import Any


class EntityCreateRequest:
    """Request to create an entity."""

    def __init__(
        self,
        concept_type: str,
        entity_id: str,
        attributes: dict[str, Any] | None = None
    ):
        self.concept_type = concept_type
        self.entity_id = entity_id
        self.attributes = attributes if attributes else {}


class RelationCreateRequest:
    """Request to create a relation."""

    def __init__(
        self,
        relation_type: str,
        from_id: str,
        to_id: str,
        attributes: dict[str, Any] | None = None
    ):
        self.relation_type = relation_type
        self.from_id = from_id
        self.to_id = to_id
        self.attributes = attributes if attributes else {}


class AnalysisRequest:
    """Request to execute an analysis."""

    def __init__(
        self,
        entity_id: str,
        dimension: str,
        context: dict[str, Any] | None = None
    ):
        self.entity_id = entity_id
        self.dimension = dimension
        self.context = context if context else {}


class QueryRequest:
    """Request to execute a knowledge query."""

    def __init__(
        self,
        query: str,
        match_mode: str = "hybrid",
        concept_type: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 10
    ):
        self.query = query
        self.match_mode = match_mode
        self.concept_type = concept_type
        self.filters = filters if filters else {}
        self.top_k = top_k


class IngestionRequest:
    """Request to ingest data."""

    def __init__(
        self,
        instances_path: str | None = None,
        entities: list[dict] | None = None,
        relations: list[dict] | None = None
    ):
        self.instances_path = instances_path
        self.entities = entities if entities else []
        self.relations = relations if relations else []

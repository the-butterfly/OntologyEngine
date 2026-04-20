# ontology_engine/services/dto/requests.py
"""Request DTOs for service layer."""

from __future__ import annotations

from typing import Any


class EntityCreateRequest:
    """Request to create an entity."""

    def __init__(
        self,
        fact_object: str,
        entity_id: str,
        attributes: dict[str, Any] | None = None,
        *,
        concept_type: str | None = None,
    ):
        self._fact_object = concept_type or fact_object
        self.entity_id = entity_id
        self.attributes = attributes if attributes else {}

    @property
    def fact_object(self) -> str:
        return self._fact_object

    @property
    def concept_type(self) -> str:
        return self._fact_object


class RelationCreateRequest:
    """Request to create a relation."""

    def __init__(
        self,
        relation_name: str,
        from_id: str,
        to_id: str,
        attributes: dict[str, Any] | None = None,
        *,
        relation_type: str | None = None,
    ):
        self._relation_name = relation_type or relation_name
        self.from_id = from_id
        self.to_id = to_id
        self.attributes = attributes if attributes else {}

    @property
    def relation_name(self) -> str:
        return self._relation_name

    @property
    def relation_type(self) -> str:
        return self._relation_name


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
        fact_object: str | None = None,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
        *,
        concept_type: str | None = None,
    ):
        self.query = query
        self.match_mode = match_mode
        self._fact_object = concept_type or fact_object
        self.filters = filters if filters else {}
        self.top_k = top_k

    @property
    def fact_object(self) -> str | None:
        return self._fact_object

    @property
    def concept_type(self) -> str | None:
        return self._fact_object


class IngestionRequest:
    """Request to ingest data."""

    def __init__(
        self,
        instances_path: str | None = None,
        entities: list[dict] | None = None,
        relations: list[dict] | None = None,
        space_id: str | None = None
    ):
        self.instances_path = instances_path
        self.entities = entities if entities else []
        self.relations = relations if relations else []
        self.space_id = space_id

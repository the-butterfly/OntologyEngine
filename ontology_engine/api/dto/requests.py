# ontology_engine/api/dto/requests.py
"""API request models."""

from typing import Any
from pydantic import BaseModel, Field


class SchemaLoadRequest(BaseModel):
    """Request to load a schema."""

    schema_path: str


class EntityCreateRequest(BaseModel):
    """Request to create an entity."""

    concept_type: str
    entity_id: str
    attributes: dict[str, Any] | None = None


class EntityBatchCreateRequest(BaseModel):
    """Request to batch create entities."""

    entities: list[EntityCreateRequest]


class EntityQueryRequest(BaseModel):
    """Request to query entities."""

    concept_type: str | None = None
    filter: dict[str, Any] | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class RelationCreateRequest(BaseModel):
    """Request to create a relation."""

    relation_type: str
    from_id: str
    to_id: str
    attributes: dict[str, Any] | None = None


class RuleExecuteRequest(BaseModel):
    """Request to execute rules."""

    entity_id: str
    dimension: str
    rules: list[str] | None = None
    dry_run: bool = False
    context_overrides: dict[str, Any] | None = None


class VectorSearchRequest(BaseModel):
    """Request for vector search."""

    text: str
    concept_type: str | None = None
    top_k: int = Field(default=10, ge=1, le=100)


class HybridSearchRequest(BaseModel):
    """Request for hybrid search."""

    query: str
    match_mode: str = "hybrid"
    concept_type: str | None = None
    filters: dict[str, Any] | None = None
    top_k: int = Field(default=10, ge=1, le=100)


class GraphQueryRequest(BaseModel):
    """Request for graph traversal query."""

    start: dict[str, Any]
    traverse: list[dict[str, Any]]
    return_: dict[str, Any] | None = Field(None, alias="return")
    limit: int = Field(default=50, ge=1, le=1000)

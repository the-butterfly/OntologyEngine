# ontology_engine/api/dto/requests.py
"""API request models."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class SchemaLoadRequest(BaseModel):
    """Request to load a schema."""

    schema_path: str


class EntityCreateRequest(BaseModel):
    """Request to create an entity."""

    fact_object: str = Field(alias="concept_type")
    entity_id: str
    attributes: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class EntityBatchCreateRequest(BaseModel):
    """Request to batch create entities."""

    entities: list[EntityCreateRequest]


class EntityQueryRequest(BaseModel):
    """Request to query entities."""

    fact_object: str | None = Field(default=None, alias="concept_type")
    filter: dict[str, Any] | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    as_of: datetime | None = Field(default=None, description="Point-in-time query: return entity state as of this timestamp")
    include_history: bool = Field(default=False, description="If true, include all historical versions")

    model_config = {"populate_by_name": True}


class RelationCreateRequest(BaseModel):
    """Request to create a relation."""

    relation_name: str = Field(alias="relation_type")
    from_id: str
    to_id: str
    attributes: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class RelationUpdateRequest(BaseModel):
    """Request to update a relation's attributes."""

    attributes: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


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
    fact_object: str | None = Field(default=None, alias="concept_type")
    top_k: int = Field(default=10, ge=1, le=100)

    model_config = {"populate_by_name": True}


class HybridSearchRequest(BaseModel):
    """Request for hybrid search."""

    query: str
    match_mode: str = "hybrid"
    fact_object: str | None = Field(default=None, alias="concept_type")
    filters: dict[str, Any] | None = None
    top_k: int = Field(default=10, ge=1, le=100)
    as_of: datetime | None = Field(default=None, description="Point-in-time query for temporal entities")

    model_config = {"populate_by_name": True}


class GraphQueryRequest(BaseModel):
    """Request for graph traversal query."""

    start: dict[str, Any]
    traverse: list[dict[str, Any]]
    return_: dict[str, Any] | None = Field(None, alias="return")
    limit: int = Field(default=50, ge=1, le=1000)
    as_of: datetime | None = Field(default=None, description="Point-in-time query for temporal entities")
    include_history: bool = Field(default=False, description="If true, include all historical versions")

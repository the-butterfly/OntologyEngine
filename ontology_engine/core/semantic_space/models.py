# ontology_engine/core/semantic_space/models.py
"""Core models for semantic space management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class SpaceType(str, Enum):
    """Type of semantic space."""
    MANAGEMENT = "management"
    CONSUMPTION = "consumption"


class SpaceStatus(str, Enum):
    """Status of a semantic space."""
    DRAFT = "draft"
    ACTIVE = "active"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SpaceMetadata(BaseModel):
    """Metadata for a semantic space."""
    id: str
    name: str
    space_type: SpaceType = SpaceType.MANAGEMENT
    description: str | None = None
    domain: str | None = None
    status: SpaceStatus = SpaceStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None
    view_id: str | None = None  # Associated consumption view ID


class SpaceVersion(BaseModel):
    """A version snapshot of a semantic space."""
    version: int
    space_id: str
    snapshot_path: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None
    change_description: str | None = None
    is_stable: bool = False


class SemanticSpace(BaseModel):
    """
    Root semantic space container that holds:
    - L1: Fact objects (entity definitions)
    - L2: Categorizations (classification definitions)
    - L3: Analytical elements (metric definitions)
    - L4: Business logic (rule definitions + rule logics)
    - Instances (entity and relation instances)
    - Versions (snapshot history)
    """
    metadata: SpaceMetadata
    layers: SemanticSpaceLayers = Field(default_factory=lambda: SemanticSpaceLayers())
    instances: SpaceInstances = Field(default_factory=lambda: SpaceInstances())
    versions: list[SpaceVersion] = Field(default_factory=list)
    active_version: int = 1


class SemanticSpaceLayers(BaseModel):
    """Container for the four layers of a semantic space."""
    L1_fact_objects: list[dict] = Field(default_factory=list)
    L2_categorizations: list[dict] = Field(default_factory=list)
    L3_analytical_elements: list[dict] = Field(default_factory=list)
    L4_business_logic: L4BusinessLogic = Field(default_factory=lambda: L4BusinessLogic())


class L4BusinessLogic(BaseModel):
    """L4 Business Logic layer containing rule definitions and logics."""
    rule_definitions: list[dict] = Field(default_factory=list)
    rule_logics: list[dict] = Field(default_factory=list)


class SpaceInstances(BaseModel):
    """Container for entity and relation instances."""
    entities: list[dict] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)
    category_tags: list[dict] = Field(default_factory=list)
    metric_values: list[dict] = Field(default_factory=list)


class Authorization(BaseModel):
    """Authorization from management space to consumption view."""
    id: str
    target_view_id: str
    enabled: bool = True
    granted_layers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None


class ConsumptionView(BaseModel):
    """
    Consumption view that aggregates authorized content from management spaces.
    """
    metadata: SpaceMetadata
    source_authorizations: list[str] = Field(default_factory=list)
    merged_schema: SemanticSpaceLayers | None = None
    instances: SpaceInstances | None = None


# Re-export for convenience
__all__ = [
    "SemanticSpace",
    "SpaceMetadata",
    "SpaceVersion",
    "SpaceStatus",
    "SpaceType",
    "SemanticSpaceLayers",
    "L4BusinessLogic",
    "SpaceInstances",
    "Authorization",
    "ConsumptionView",
]

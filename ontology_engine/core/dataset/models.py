# ontology_engine/core/dataset/models.py
"""Dataset models for external data source management."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class DatasetType(str, Enum):
    """Supported dataset source types."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    FILE = "file"
    API = "api"
    S3 = "s3"


class SyncMode(str, Enum):
    """Sync mode for dataset synchronization."""
    FULL = "full"
    INCREMENTAL = "incremental"


class IncrementalType(str, Enum):
    """Incremental sync type."""
    TIMESTAMP = "timestamp"
    CONDITIONS = "conditions"


class DatasetStatus(str, Enum):
    """Dataset status."""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class FieldMapping(BaseModel):
    """Field-level mapping from source to target."""
    source_field: str
    target_field: str


class MappingRule(BaseModel):
    """Mapping rule for transforming source data to entity instances."""
    id: str
    target_entity_type: str
    field_mappings: list[FieldMapping] = Field(default_factory=list)
    filters: list[dict] = Field(default_factory=list)
    enabled: bool = True


class SourceConnection(BaseModel):
    """Data source connection configuration."""
    type: DatasetType
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    url: str | None = None  # For file or API sources


class FieldSchema(BaseModel):
    """Schema definition for a dataset field."""
    name: str
    type: str  # string, integer, float, boolean, timestamp
    description: str | None = None


class IncrementalConfig(BaseModel):
    """Configuration for incremental sync."""
    type: IncrementalType = IncrementalType.TIMESTAMP
    timestamp_field: str | None = None
    conditions: list[dict] | None = None
    last_sync: datetime | None = None


class SyncConfig(BaseModel):
    """Sync configuration for dataset."""
    mode: SyncMode = SyncMode.FULL
    incremental: IncrementalConfig | None = None
    schedule_enabled: bool = False
    schedule_cron: str | None = None
    schedule_timezone: str = "UTC"
    max_records: int = 100000
    on_exceed: str = "truncate"  # truncate, skip, error


class DatasetDeclaration(BaseModel):
    """
    Dataset declaration - external data source abstraction.

    A dataset represents an external data source that can synchronize
    entity instances into a semantic space.
    """
    id: str
    name: str
    description: str | None = None

    # Source configuration
    source: SourceConnection

    # Schema definition
    schema_fields: list[FieldSchema] = Field(default_factory=list)

    # Mapping rules
    mapping_rules: list[MappingRule] = Field(default_factory=list)

    # Sync configuration
    sync_config: SyncConfig = Field(default_factory=SyncConfig)

    # Status
    status: DatasetStatus = DatasetStatus.ACTIVE

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = None


class SyncHistory(BaseModel):
    """Record of a sync operation."""
    id: str
    dataset_id: str
    triggered_by: str  # manual, scheduled, api
    started_at: datetime
    completed_at: datetime | None = None

    mode: SyncMode
    parameters: dict | None = None

    stats: dict = Field(default_factory=dict)
    # Example: {
    #   "records_read": 1500,
    #   "records_created": 120,
    #   "records_updated": 350,
    #   "records_skipped": 30,
    #   "records_truncated": 0
    # }

    status: str = "running"  # running, success, partial, failed
    error: str | None = None

# ontology_engine/api/server.py
"""FastAPI server for OntologyEngine API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ontology_engine.services import (
    SchemaService,
    EntityService,
    AnalysisService,
    QueryService,
    IngestionService,
)
from ontology_engine.storage.duckdb import DuckDBStorage
from ontology_engine.core.schema import SchemaLoader
from ontology_engine.engine.metric.engine import MetricEngine, MetricCache
from ontology_engine.engine.categorization.engine import CategorizationEngine
from ontology_engine.engine.rule.executor import RuleExecutor


# Global storage and services (initialized on startup)
_storage: DuckDBStorage | None = None
_services: dict[str, Any] = {}


def get_storage() -> DuckDBStorage:
    """Get storage instance."""
    if _storage is None:
        raise HTTPException(status_code=500, detail="Storage not initialized")
    return _storage


def get_schema_service() -> SchemaService:
    """Get schema service."""
    if "schema" not in _services:
        raise HTTPException(status_code=500, detail="Schema service not initialized")
    return _services["schema"]


def get_entity_service() -> EntityService:
    """Get entity service."""
    if "entity" not in _services:
        raise HTTPException(status_code=500, detail="Entity service not initialized")
    return _services["entity"]


def get_analysis_service() -> AnalysisService:
    """Get analysis service."""
    if "analysis" not in _services:
        raise HTTPException(status_code=500, detail="Analysis service not initialized")
    return _services["analysis"]


def get_query_service() -> QueryService:
    """Get query service."""
    if "query" not in _services:
        raise HTTPException(status_code=500, detail="Query service not initialized")
    return _services["query"]


def get_ingestion_service() -> IngestionService:
    """Get ingestion service."""
    if "ingestion" not in _services:
        raise HTTPException(status_code=500, detail="Ingestion service not initialized")
    return _services["ingestion"]


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan handler."""
    global _storage, _services

    # Initialize storage
    _storage = DuckDBStorage(db_path=":memory:")
    await _storage.initialize()

    # Initialize schema loader
    schema_loader = SchemaLoader()
    schema = None
    try:
        schema = schema_loader.load("examples/supply_chain_finance/schema.yaml")
    except FileNotFoundError:
        pass  # Schema file optional at startup

    # Initialize engines
    metric_cache = MetricCache() if schema else None
    metric_engine = MetricEngine(schema=schema, storage=_storage, cache=metric_cache) if schema else None
    rule_executor = RuleExecutor(schema=schema) if schema else None
    categorization_engine = CategorizationEngine(
        schema=schema, storage=_storage, rule_executor=rule_executor
    ) if schema and rule_executor else None

    # Initialize services with engines
    _services["schema"] = SchemaService(storage=_storage)
    _services["entity"] = EntityService(storage=_storage, schema=schema)
    _services["analysis"] = AnalysisService(
        categorization_engine=categorization_engine,
        metric_engine=metric_engine,
        rule_executor=rule_executor,
        storage=_storage,
        schema=schema
    )
    _services["query"] = QueryService(storage=_storage, rule_executor=rule_executor)
    _services["ingestion"] = IngestionService(
        storage=_storage,
        entity_service=_services["entity"]
    )

    yield

    # Cleanup
    if _storage:
        await _storage.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OntologyEngine API",
        description="Credit Assessment Knowledge Graph Engine API",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routes
    from ontology_engine.api.routes import schema, entities, analysis, query, ingestion

    app.include_router(schema.router, prefix="/v1/schema", tags=["Schema"])
    app.include_router(entities.router, prefix="/v1/entities", tags=["Entities"])
    app.include_router(analysis.router, prefix="/v1/analysis", tags=["Analysis"])
    app.include_router(query.router, prefix="/v1/query", tags=["Query"])
    app.include_router(ingestion.router, prefix="/v1/ingestion", tags=["Ingestion"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "OntologyEngine API",
            "version": "1.0.0",
            "docs": "/docs"
        }

    return app


app = create_app()

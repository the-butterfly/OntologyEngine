# ontology_engine/api/server.py
"""FastAPI server for OntologyEngine API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ontology_engine.services import (
    SchemaService,
    EntityService,
    AnalysisService,
    QueryService,
    IngestionService,
)
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.storage.duckdb import DuckDBStorage
from ontology_engine.core.schema import SchemaLoader
from ontology_engine.engine.metric.engine import MetricEngine, MetricCache
from ontology_engine.engine.categorization.engine import CategorizationEngine
from ontology_engine.engine.rule.executor import RuleExecutor
from ontology_engine.api import dependencies


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan handler."""
    # Initialize storage
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    # Initialize schema loader
    schema_loader = SchemaLoader()
    schema = None
    try:
        schema = schema_loader.load("examples/supply_chain_finance/schema.yaml")
    except FileNotFoundError:
        pass  # Schema file optional at startup

    # Initialize engines
    metric_cache = MetricCache() if schema else None
    metric_engine = MetricEngine(schema=schema, storage=storage, cache=metric_cache) if schema else None
    rule_executor = RuleExecutor(schema=schema) if schema else None
    categorization_engine = CategorizationEngine(
        schema=schema, storage=storage, rule_executor=rule_executor
    ) if schema and rule_executor else None

    # Initialize services with engines
    services: dict[str, Any] = {}
    services["schema"] = SchemaService(storage=storage)
    services["entity"] = EntityService(storage=storage, schema=schema)
    services["analysis"] = AnalysisService(
        categorization_engine=categorization_engine,
        metric_engine=metric_engine,
        rule_executor=rule_executor,
        storage=storage,
        schema=schema
    )
    services["query"] = QueryService(storage=storage, rule_executor=rule_executor)
    services["ingestion"] = IngestionService(
        storage=storage,
        entity_service=services["entity"]
    )
    services["visualization"] = VisualizationService(
        schema_service=services["schema"],
        analysis_service=services["analysis"],
        storage=storage,
        schema=schema,
    )

    # Initialize dependencies
    dependencies.init_dependencies(storage, services)

    yield

    # Cleanup
    if storage:
        await storage.close()


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

    # Import and include routes (routers already have their prefixes defined)
    from ontology_engine.api.routes import schema, entities, analysis, query, ingestion, visualization, relations, rules
    from ontology_engine.api.dto.responses import APIResponse

    app.include_router(schema.router, tags=["Schema"])
    app.include_router(entities.router, tags=["Entities"])
    app.include_router(analysis.router, tags=["Analysis"])
    app.include_router(query.router, tags=["Query"])
    app.include_router(ingestion.router, tags=["Ingestion"])
    app.include_router(visualization.router, tags=["Visualization"])
    app.include_router(relations.router, tags=["Relations"])
    app.include_router(rules.router, tags=["Rules"])

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


# Module-level app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ontology_engine.api.server:app", host="0.0.0.0", port=8000, reload=True)

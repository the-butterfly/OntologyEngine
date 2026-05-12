# ontology_engine/api/server.py
"""FastAPI server for OntologyEngine API."""

from __future__ import annotations

import logging
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
    DatasetService,
    IncrementalUpdateService,
    RuleService,
)
from ontology_engine.services.visualization_service import VisualizationService
from ontology_engine.services.dag_service import DAGService
from ontology_engine.services.simulation_service import SimulationService
from ontology_engine.services.category_service import CategoryService
from ontology_engine.storage.config import create_meta_store
from ontology_engine.core.schema import SchemaLoader
from ontology_engine.core.instances import InstanceLoader
from ontology_engine.api import dependencies
from ontology_engine.core.semantic_space import SemanticSpaceStorage

logger = logging.getLogger(__name__)


# ============================================================================
# Application Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan handler.

    The engine starts clean — no example data is pre-loaded.
    Business scripts (e.g. examples/setup_all_spaces.py) construct
    graph space assets via the API after the server is running.
    """
    storage = create_meta_store()
    await storage.initialize()

    schema_loader = SchemaLoader()
    instance_loader = InstanceLoader()

    # ---- Legacy engine initialization (for backward-compatible routes) ----
    schema = None
    try:
        schema = schema_loader.load("examples/supply_chain_finance/schema.yaml")
    except FileNotFoundError:
        pass

    try:
        instances_path = "examples/supply_chain_finance/instances.yaml"
        entities, relations = instance_loader.load(instances_path)
        for entity in entities:
            await storage.save_entity(entity)
        for relation in relations:
            await storage.save_relation(relation)
        logger.info(
            f"Loaded {len(entities)} entities and {len(relations)} relations into storage"
        )
    except Exception as exc:
        import traceback
        logger.error(f"Failed to load instances into storage: {exc}")
        logger.error(traceback.format_exc())

    # Initialize services
    services: dict[str, Any] = {}
    services["schema"] = SchemaService(storage=storage)
    services["entity"] = EntityService(storage=storage, schema=schema)
    services["analysis"] = AnalysisService(
        storage=storage,
        schema=schema,
    )
    services["query"] = QueryService(storage=storage, rule_executor=services["analysis"].rule_executor)
    services["ingestion"] = IngestionService(
        storage=storage,
        entity_service=services["entity"],
    )
    services["visualization"] = VisualizationService(
        schema_service=services["schema"],
        analysis_service=services["analysis"],
        storage=storage,
        schema=schema,
    )
    services["dataset"] = DatasetService(storage=storage)
    services["incremental"] = IncrementalUpdateService(storage=storage)
    services["rule"] = RuleService(storage=storage)
    services["dag"] = DAGService(storage=storage, schema=schema)
    services["simulation"] = SimulationService()
    services["category"] = CategoryService(storage=storage)

    dependencies.init_dependencies(storage, services)

    yield

    from ontology_engine.engine.cognitive.factory import MemoryAPISingleton
    await MemoryAPISingleton.close()

    if storage:
        await storage.close()


# ============================================================================
# App Factory
# ============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="OntologyEngine API",
        description="Credit Assessment Knowledge Graph Engine API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from ontology_engine.api.middleware import DeprecationMiddleware
    app.add_middleware(DeprecationMiddleware, mode="header")

    from ontology_engine.api.routes import (
        schema,
        entities,
        analysis,
        query,
        ingestion,
        visualization,
        relations,
        rules,
        management,
        consumption,
        datasets,
        incremental,
        categories,
        simulation,
    )
    from ontology_engine.api.routes.actions import router as actions_router
    from ontology_engine.api.routes.ontology import router as ontology_router

    app.include_router(schema.router, tags=["Schema"])
    app.include_router(entities.router, tags=["Entities"])
    app.include_router(analysis.router, tags=["Analysis"])
    app.include_router(query.router, tags=["Query"])
    app.include_router(ingestion.router, tags=["Ingestion"])
    app.include_router(visualization.router, tags=["Visualization"])
    app.include_router(relations.router, tags=["Relations"])
    app.include_router(rules.router, tags=["Rules"])
    app.include_router(management.router, tags=["Management"])
    app.include_router(consumption.router, tags=["Consumption"])
    app.include_router(datasets.router, tags=["Datasets"])
    app.include_router(incremental.router, tags=["Incremental Update"])
    app.include_router(categories.router, tags=["Categories"])
    app.include_router(simulation.router, tags=["Simulation"])
    app.include_router(actions_router, tags=["Actions"])
    app.include_router(ontology_router, tags=["Ontology"])

    from ontology_engine.api.routes.memory import router as memory_router
    app.include_router(memory_router, tags=["Memory"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        space_storage = SemanticSpaceStorage()
        try:
            all_metadata = await space_storage.list()
            from ontology_engine.core.semantic_space import SpaceType
            mgmt_count = sum(1 for m in all_metadata if m.space_type == SpaceType.MANAGEMENT)
            view_count = sum(1 for m in all_metadata if m.space_type == SpaceType.CONSUMPTION)
            return {
                "status": "healthy",
                "spaces": {
                    "management": mgmt_count,
                    "consumption": view_count,
                },
            }
        except Exception:
            return {"status": "healthy"}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "OntologyEngine API",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ontology_engine.api.server:app", host="0.0.0.0", port=8000, reload=True)

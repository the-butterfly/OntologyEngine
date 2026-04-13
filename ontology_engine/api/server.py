# ontology_engine/api/server.py
"""FastAPI server for OntologyEngine API."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

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
from ontology_engine.core.instances import InstanceLoader
from ontology_engine.engine.metric.engine import MetricEngine, MetricCache
from ontology_engine.engine.categorization.engine import CategorizationEngine
from ontology_engine.engine.rule.executor import RuleExecutor
from ontology_engine.api import dependencies
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceStatus,
    SpaceType,
    SemanticSpaceLayers,
    L4BusinessLogic,
    SpaceInstances,
    SemanticSpaceStorage,
)


# ============================================================================
# Example case definitions: auto-import at startup
# ============================================================================

EXAMPLE_CASES = [
    {
        "name": "供应链金融授信",
        "description": "供应链金融核心企业授信场景，含担保链图指标和规则分离设计",
        "domain": "supply_chain_finance",
        "schema_path": "examples/supply_chain_finance/schema.yaml",
        "instances_path": "examples/supply_chain_finance/instances.yaml",
    },
    {
        "name": "个人消费信贷",
        "description": "个人消费信贷评分场景，含L3指标、产品分流和一票否决逻辑",
        "domain": "consumer_credit",
        "schema_path": "examples/consumer_credit/schema.yaml",
        "instances_path": "examples/consumer_credit/instances.yaml",
    },
]


async def _load_example_case_as_space(
    case: dict[str, Any],
    space_storage: SemanticSpaceStorage,
    schema_loader: SchemaLoader,
    instance_loader: InstanceLoader,
) -> str | None:
    """Load a YAML example case into a semantic space. Returns space_id or None."""
    schema_path = Path(case["schema_path"])
    instances_path = Path(case["instances_path"])

    if not schema_path.exists():
        logger.warning(f"Schema file not found, skipping: {schema_path}")
        return None

    # Load schema
    try:
        schema = schema_loader.load(str(schema_path))
    except Exception as exc:
        logger.error(f"Failed to load schema {schema_path}: {exc}")
        return None

    # Convert to space layers
    try:
        layers_dict = schema.to_space_layers_dict()
    except Exception as exc:
        logger.error(f"Failed to convert schema to layers: {exc}")
        return None

    # Create management space
    space_id = f"space_{case['domain']}"
    view_id = f"view_{case['domain']}"

    # Check if already exists (with instances loaded)
    existing = await space_storage.load(space_id)
    if existing and len(existing.instances.entities) > 0:
        logger.info(f"Space {space_id} already exists with {len(existing.instances.entities)} entities, skipping.")
        return space_id

    if existing:
        # Space exists but has no instances — reload instances into existing space
        logger.info(f"Space {space_id} exists but has no instances, reloading instances.")
        space = existing
    else:
        # Create fresh management space
        metadata = SpaceMetadata(
            id=space_id,
            name=case["name"],
            space_type=SpaceType.MANAGEMENT,
            description=case["description"],
            domain=case["domain"],
            status=SpaceStatus.ACTIVE,
            view_id=view_id,
        )
        space = SemanticSpace(
            metadata=metadata,
            layers=SemanticSpaceLayers(
                L1_fact_objects=layers_dict["L1_fact_objects"],
                L2_categorizations=layers_dict["L2_categorizations"],
                L3_analytical_elements=layers_dict["L3_analytical_elements"],
                L4_business_logic=L4BusinessLogic(
                    rule_definitions=layers_dict["L4_business_logic"]["rule_definitions"],
                    rule_logics=layers_dict["L4_business_logic"]["rule_logics"],
                ),
            ),
            instances=SpaceInstances(
                entities=[],
                relations=[],
                category_tags=[],
                metric_values=[],
            ),
            versions=[],
        )

    # Load instances if available
    if instances_path.exists():
        try:
            entities, relations = instance_loader.load(str(instances_path))
            for entity in entities:
                entity_dict: dict[str, Any] = {
                    "entity_id": entity.entity_id,
                    "_concept": entity.concept,
                }
                # Flatten entity data attributes
                if hasattr(entity, "data") and isinstance(entity.data, dict):
                    for k, v in entity.data.items():
                        if k not in ("_concept",):
                            entity_dict[k] = v
                space.instances.entities.append(entity_dict)

            for relation in relations:
                rel_dict: dict[str, Any] = {
                    "from_entity_id": relation.from_entity_id,
                    "to_entity_id": relation.to_entity_id,
                    "relation_type": relation.relation_type,
                }
                if hasattr(relation, "data") and isinstance(relation.data, dict):
                    rel_dict.update(relation.data)
                space.instances.relations.append(rel_dict)

            logger.info(
                f"Loaded {len(space.instances.entities)} entities, "
                f"{len(space.instances.relations)} relations for {case['name']}"
            )
        except Exception as exc:
            logger.error(f"Failed to load instances for {case['name']}: {exc}")

    await space_storage.save(space)

    # Create consumption view (always refresh from management space)
    view_metadata = SpaceMetadata(
        id=view_id,
        name=f"{case['name']} (消费视图)",
        space_type=SpaceType.CONSUMPTION,
        description=f"自动创建的消费视图，来自 {case['name']}",
        domain=case["domain"],
        status=SpaceStatus.ACTIVE,
    )
    view = SemanticSpace(
        metadata=view_metadata,
        layers=SemanticSpaceLayers(
            L1_fact_objects=list(space.layers.L1_fact_objects),
            L2_categorizations=list(space.layers.L2_categorizations),
            L3_analytical_elements=list(space.layers.L3_analytical_elements),
            L4_business_logic=L4BusinessLogic(
                rule_definitions=list(space.layers.L4_business_logic.rule_definitions),
                rule_logics=list(space.layers.L4_business_logic.rule_logics),
            ),
        ),
        instances=SpaceInstances(
            entities=list(space.instances.entities),
            relations=list(space.instances.relations),
            category_tags=[],
            metric_values=[],
        ),
        versions=[],
    )
    await space_storage.save(view)

    logger.info(
        f"✅ Loaded example case '{case['name']}' as space={space_id} / view={view_id}"
    )
    return space_id


# ============================================================================
# Application Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Application lifespan handler."""
    # Initialize storage
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    # Initialize schema/instance loaders
    schema_loader = SchemaLoader()
    instance_loader = InstanceLoader()

    # Initialize semantic space storage (in-memory singleton)
    space_storage = SemanticSpaceStorage()

    # Auto-load example cases as semantic spaces
    for case in EXAMPLE_CASES:
        try:
            await _load_example_case_as_space(case, space_storage, schema_loader, instance_loader)
        except Exception as exc:
            import traceback
            logger.error(f"Failed to load example case {case['name']}: {exc}")
            logger.error(traceback.format_exc())

    # Sync management space instances to corresponding consumption views
    # (handles cases where management space was loaded before instance sync was implemented)
    try:
        all_metadata = await space_storage.list()
        from ontology_engine.core.semantic_space import SpaceType as ST
        mgmt_spaces = {m.id: m for m in all_metadata if m.space_type == ST.MANAGEMENT}
        for meta in all_metadata:
            if meta.space_type == ST.MANAGEMENT and meta.view_id:
                view = await space_storage.load(meta.view_id)
                space = await space_storage.load(meta.id)
                if view and space and len(view.instances.entities) < len(space.instances.entities):
                    view.instances.entities = list(space.instances.entities)
                    view.instances.relations = list(space.instances.relations)
                    await space_storage.save(view)
                    logger.info(
                        f"Synced {len(space.instances.entities)} entities from {meta.id} to {meta.view_id}"
                    )
    except Exception as exc:
        logger.warning(f"Failed to sync management instances to views: {exc}")

    # ---- Legacy engine initialization (for backward-compatible routes) ----
    schema = None
    try:
        schema = schema_loader.load("examples/supply_chain_finance/schema.yaml")
    except FileNotFoundError:
        pass

    # Load instance data into DuckDB storage (for legacy routes)
    try:
        instances_path = "examples/supply_chain_finance/instances.yaml"
        entities, relations = instance_loader.load(instances_path)
        for entity in entities:
            await storage.save_entity(entity)
        for relation in relations:
            await storage.save_relation(relation)
        logger.info(
            f"Loaded {len(entities)} entities and {len(relations)} relations into DuckDB storage"
        )
    except Exception as exc:
        import traceback
        logger.error(f"Failed to load instances into DuckDB: {exc}")
        logger.error(traceback.format_exc())

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
        schema=schema,
    )
    services["query"] = QueryService(storage=storage, rule_executor=rule_executor)
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

    # Initialize dependencies
    dependencies.init_dependencies(storage, services)

    yield

    # Cleanup
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

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include routes
    from ontology_engine.api.routes import (
        schema,
        entities,
        analysis,
        query,
        ingestion,
        visualization,
        relations,
        rules,
        semantic_spaces,
        management,
        consumption,
        datasets,
        incremental,
        categories,
    )

    app.include_router(schema.router, tags=["Schema"])
    app.include_router(entities.router, tags=["Entities"])
    app.include_router(analysis.router, tags=["Analysis"])
    app.include_router(query.router, tags=["Query"])
    app.include_router(ingestion.router, tags=["Ingestion"])
    app.include_router(visualization.router, tags=["Visualization"])
    app.include_router(relations.router, tags=["Relations"])
    app.include_router(rules.router, tags=["Rules"])
    # New management and consumption routes
    app.include_router(management.router, tags=["Management"])
    app.include_router(consumption.router, tags=["Consumption"])
    # Phase 1 Enhancement routes
    app.include_router(datasets.router, tags=["Datasets"])
    app.include_router(incremental.router, tags=["Incremental Update"])
    app.include_router(categories.router, tags=["Categories"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        # Also return loaded space count
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
            "examples": [c["name"] for c in EXAMPLE_CASES],
        }

    return app


# Module-level app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ontology_engine.api.server:app", host="0.0.0.0", port=8000, reload=True)

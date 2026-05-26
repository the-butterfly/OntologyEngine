from __future__ import annotations

from fastapi import APIRouter

from ontology_engine.api.routes.entities import router as entities_router
from ontology_engine.api.routes.relations import router as relations_router
from ontology_engine.api.routes.datasets import router as datasets_router
from ontology_engine.api.routes.incremental import router as incremental_router
from ontology_engine.api.routes.ingestion import router as ingestion_router

router = APIRouter(tags=["Instances"])

router.include_router(entities_router)
router.include_router(relations_router)
router.include_router(datasets_router)
router.include_router(incremental_router)
router.include_router(ingestion_router)

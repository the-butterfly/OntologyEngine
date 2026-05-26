from __future__ import annotations

from fastapi import APIRouter

from ontology_engine.api.routes.consumption import router as consumption_router
from ontology_engine.api.routes.visualization import router as visualization_router
from ontology_engine.api.routes.analysis import router as analysis_router

router = APIRouter(prefix="/v1", tags=["Views"])

router.include_router(consumption_router)
router.include_router(visualization_router)
router.include_router(analysis_router)

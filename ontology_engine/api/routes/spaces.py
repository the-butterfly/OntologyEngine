from __future__ import annotations

from fastapi import APIRouter

from ontology_engine.api.routes.semantic_spaces import router as semantic_spaces_router

router = APIRouter(tags=["Spaces"])

router.include_router(semantic_spaces_router)

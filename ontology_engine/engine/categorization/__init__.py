# ontology_engine/engine/categorization/__init__.py
"""L2 CategorizationEngine module."""

from ontology_engine.engine.categorization.models import CategoryTags
from ontology_engine.engine.categorization.engine import CategorizationEngine

__all__ = [
    "CategoryTags",
    "CategorizationEngine",
]

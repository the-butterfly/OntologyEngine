"""Query engine for KGML queries — Phase 7B implementation."""

from ontology_engine.engine.query.router import (
    QueryType,
    RetrievalParams,
    detect_query_type,
    build_retrieval_params,
)
from ontology_engine.engine.query.layer_r import LayerRRetriever, FragmentResult
from ontology_engine.engine.query.layer_s import LayerSRetriever, StructuredResult, EntityResult, EdgeResult
from ontology_engine.engine.query.bundle_search import BundleSearchEngine, BundleResult
from ontology_engine.engine.query.rrf_fusion import RRFFusion, RRFDocument
from ontology_engine.engine.query.mutual_index import (
    MutualIndexCollaborative,
    CollaborativeResult,
    RetrieverRegistry,
)

__all__ = [
    "QueryType",
    "RetrievalParams",
    "detect_query_type",
    "build_retrieval_params",
    "LayerRRetriever",
    "FragmentResult",
    "LayerSRetriever",
    "StructuredResult",
    "EntityResult",
    "EdgeResult",
    "BundleSearchEngine",
    "BundleResult",
    "RRFFusion",
    "RRFDocument",
    "MutualIndexCollaborative",
    "CollaborativeResult",
    "RetrieverRegistry",
]

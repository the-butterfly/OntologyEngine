"""Extraction pipeline — three-pass architecture for knowledge extraction."""

from ontology_engine.engine.extraction.ast_extractor import ASTExtractor, ASTExtractionResult
from ontology_engine.engine.extraction.llm_extractor import LLMExtractor, LLMExtractionResult
from ontology_engine.engine.extraction.cache import IncrementalCache
from ontology_engine.engine.extraction.dedup import DedupStrategy, DedupResult
from ontology_engine.engine.extraction.pipeline import ExtractionPipeline

__all__ = [
    "ASTExtractor",
    "ASTExtractionResult",
    "LLMExtractor",
    "LLMExtractionResult",
    "IncrementalCache",
    "DedupStrategy",
    "DedupResult",
    "ExtractionPipeline",
]

"""Extraction pipeline orchestrator — three-pass architecture."""

from __future__ import annotations

from typing import Any

from ontology_engine.engine.extraction.ast_extractor import ASTExtractor, ASTExtractionResult
from ontology_engine.engine.extraction.llm_extractor import LLMExtractor
from ontology_engine.engine.extraction.cache import IncrementalCache
from ontology_engine.engine.extraction.dedup import DedupStrategy, DedupResult


class ExtractionPipeline:
    """Three-pass extraction pipeline: AST → LLM → Dedup."""

    def __init__(
        self,
        cache_dir: str = ".ontology/cache",
    ) -> None:
        self._ast_extractor = ASTExtractor()
        self._llm_extractor = LLMExtractor()
        self._cache = IncrementalCache(cache_dir)
        self._dedup = DedupStrategy()

    def ingest(self, source_files: list[str], root: str = ".") -> DedupResult:
        all_ast_results: list[ASTExtractionResult] = []
        uncached_fragments: list[dict[str, Any]] = []

        for source_file in source_files:
            cached = self._cache.load_ast_cache(
                __import__("pathlib").Path(source_file),
                __import__("pathlib").Path(root),
            )
            if cached is not None:
                all_ast_results.append(ASTExtractionResult(
                    entities=cached.get("entities", []),
                    edges=cached.get("edges", []),
                    extracted_from_edges=cached.get("extracted_from_edges", []),
                ))
            else:
                result = self._ast_extractor.extract(source_file)
                all_ast_results.append(result)
                self._cache.save_ast_cache(
                    __import__("pathlib").Path(source_file),
                    {
                        "entities": result.entities,
                        "edges": result.edges,
                        "extracted_from_edges": result.extracted_from_edges,
                    },
                    __import__("pathlib").Path(root),
                )
                uncached_fragments.append({
                    "id": source_file,
                    "text": __import__("pathlib").Path(source_file).read_text(encoding="utf-8") if __import__("pathlib").Path(source_file).exists() else "",
                })

        llm_result = self._llm_extractor.extract(uncached_fragments)

        merged_ast = self._merge_ast_results(all_ast_results)
        return self._dedup.dedup_and_index(merged_ast, llm_result, uncached_fragments)

    def _merge_ast_results(self, results: list[ASTExtractionResult]) -> ASTExtractionResult:
        merged = ASTExtractionResult()
        for r in results:
            merged.entities.extend(r.entities)
            merged.edges.extend(r.edges)
            merged.extracted_from_edges.extend(r.extracted_from_edges)
        return merged

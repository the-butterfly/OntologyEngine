"""Extraction pipeline orchestrator — three-pass architecture.

Pass 1 — AST extraction  (structural, high confidence)
Pass 2 — LLM extraction  (semantic, configurable via LLMClientProtocol)
Pass 3 — Dedup + mutual-index edge unification
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ontology_engine.engine.extraction.ast_extractor import ASTExtractor, ASTExtractionResult
from ontology_engine.engine.extraction.llm_extractor import LLMExtractor
from ontology_engine.engine.extraction.llm_protocol import LLMClientProtocol
from ontology_engine.engine.extraction.cache import IncrementalCache
from ontology_engine.engine.extraction.dedup import DedupStrategy, DedupResult


class ExtractionPipeline:
    """Three-pass extraction pipeline: AST → LLM → Dedup.

    Args:
        cache_dir: Directory used by IncrementalCache for AST + semantic
            result caching.
        llm_client: Optional pre-built LLM client.  When supplied, it is
            injected into LLMExtractor directly.  When omitted, LLMExtractor
            falls back to ``config.yaml`` / env-var configuration.
        llm_config_path: Path to ``config.yaml`` used for LLM configuration
            when ``llm_client`` is not provided.
        schema_loader: Optional SchemaLoader instance.  When provided,
            ``ingest()`` calls ``schema_loader.get_fact_object_descriptions()``
            and passes the result to LLMExtractor so extracted entity types
            align with the project's type system.
    """

    def __init__(
        self,
        cache_dir: str = ".ontology/cache",
        llm_client: LLMClientProtocol | None = None,
        llm_config_path: str | Path | None = None,
        schema_loader: Any | None = None,
    ) -> None:
        self._ast_extractor = ASTExtractor()
        self._llm_extractor = LLMExtractor(
            llm_client=llm_client,
            config_path=llm_config_path,
        )
        self._cache = IncrementalCache(cache_dir)
        self._dedup = DedupStrategy()
        self._schema_loader = schema_loader

    def ingest(self, source_files: list[str], root: str = ".") -> DedupResult:
        """Ingest a list of source files through the three-pass pipeline.

        Args:
            source_files: Absolute or relative paths to source files.
            root: Project root used for relative-path hashing in the cache.

        Returns:
            DedupResult containing deduplicated entities, edges and
            mutual-index edges.
        """
        root_path = Path(root)
        all_ast_results: list[ASTExtractionResult] = []
        uncached_fragments: list[dict[str, Any]] = []

        for source_file in source_files:
            file_path = Path(source_file)
            cached = self._cache.load_ast_cache(file_path, root_path)
            if cached is not None:
                all_ast_results.append(
                    ASTExtractionResult(
                        entities=cached.get("entities", []),
                        edges=cached.get("edges", []),
                        extracted_from_edges=cached.get("extracted_from_edges", []),
                    )
                )
            else:
                result = self._ast_extractor.extract(source_file)
                all_ast_results.append(result)
                self._cache.save_ast_cache(
                    file_path,
                    {
                        "entities": result.entities,
                        "edges": result.edges,
                        "extracted_from_edges": result.extracted_from_edges,
                    },
                    root_path,
                )
                text = ""
                if file_path.exists():
                    try:
                        text = file_path.read_text(encoding="utf-8")
                    except OSError:
                        pass
                uncached_fragments.append({"id": source_file, "text": text})

        # Resolve schema context from optional SchemaLoader injection.
        # get_fact_object_descriptions() is expected to return a dict mapping
        # fact_object name → description string (or None).  If the method is
        # unavailable or raises, we degrade gracefully to no schema context.
        schema_context: dict[str, Any] | None = None
        if self._schema_loader is not None:
            try:
                schema_context = self._schema_loader.get_fact_object_descriptions()
            except Exception:
                schema_context = None

        llm_result = self._llm_extractor.extract(
            uncached_fragments,
            schema_context=schema_context,
        )
        merged_ast = self._merge_ast_results(all_ast_results)
        return self._dedup.dedup_and_index(merged_ast, llm_result, uncached_fragments)

    def _merge_ast_results(self, results: list[ASTExtractionResult]) -> ASTExtractionResult:
        merged = ASTExtractionResult()
        for r in results:
            merged.entities.extend(r.entities)
            merged.edges.extend(r.edges)
            merged.extracted_from_edges.extend(r.extracted_from_edges)
        return merged


"""RRF fusion engine.

Implements four-path RRF (Reciprocal Rank Fusion) for combining
retrieval results from Layer-R, Layer-S, BM25, and Temporal paths.

Design decisions (from rrf-fusion.md):
- D-RRF-1: RRF k=60 (industry standard)
- D-RRF-2: Four-path fusion (adding Temporal)
- D-RRF-3: BM25 extended to CognitiveNode
- D-RRF-4: Query routing drives weights
- D-RRF-5: Cognitive layer weights stacked on RRF
- D-RRF-6: Disposition dynamic weights
- D-RRF-7: BM25 based on SQLite FTS5
- D-RRF-8: Cross-encoder optional
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.rrf_types import (
    BASE_TYPE_WEIGHTS,
    COGNITIVE_LAYER_PRIORITY,
    QUERY_TYPE_WEIGHTS,
    RRF_K,
    DecisionConstraint,
    RetrievalResult,
    TemporalConstraint,
    UserPreferenceConstraint,
)

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


TEMPORAL_PATTERNS = [
    (r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b", "range"),
    (r"\b(since|from|after)\s+(20\d{2})\b", "since"),
    (r"\b(before|until|by)\s+(20\d{2})\b", "before"),
    (r"\b(last|recent)\s+(year|month|quarter)\b", "relative"),
    (r"\b(20\d{2})\b", "year"),
    (r"(过去|最近|近)\s*(一|两|三|几|半)?\s*(天|周|月|年|季度)", "relative_zh"),
    (r"(自从|自|从)\s*(\d{4})", "since_zh"),
    (r"(之前|以前|截至|到)\s*(\d{4})", "before_zh"),
    (r"(\d{4})\s*[-—到至]\s*(\d{4})", "range_zh"),
    (r"(今年|去年|前年|本年|上年)", "relative_zh_year"),
    (r"(本月|上月|上个月|这个月)", "relative_zh_month"),
]


def extract_temporal_constraint(query: str) -> TemporalConstraint | None:
    """Extract temporal constraint from a query string.

    Args:
        query: Query text.

    Returns:
        TemporalConstraint if found, None otherwise.
    """
    for pattern, kind in TEMPORAL_PATTERNS:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return TemporalConstraint(kind=kind, groups=match.groups())
    return None


USER_PREFERENCE_PATTERNS = [
    (r"保守.{0,4}(投资|策略|型)", "risk_averse"),
    (r"(风险厌恶|厌恶风险|低风险偏好)", "risk_averse"),
    (r"偏好.{0,6}(保守|低风险|稳健|安全)", "risk_averse"),
    (r"(激进|进取|高风险).{0,4}(投资|策略|型)", "aggressive"),
    (r"偏好.{0,6}(高收益|高回报|高风险|增长)", "aggressive"),
    (r"(稳健|平衡|居中).{0,4}(投资|策略|型)", "balanced"),
    (r"偏好.{0,6}(稳健|平衡|适中|中等风险)", "balanced"),
    (r"用户偏好\S*", "user_preference_generic"),
    (r"我\S*偏好\S*", "user_preference_generic"),
    (r"倾向.{0,4}(于|选择)", "user_preference_generic"),
    (r"个人.{0,4}(偏好|倾向|风格)", "user_preference_generic"),
]


def extract_user_preference_constraint(query: str) -> UserPreferenceConstraint | None:
    """Extract user preference constraint from a query string.

    Args:
        query: Query text.

    Returns:
        UserPreferenceConstraint if found, None otherwise.
    """
    for pattern, pref_type in USER_PREFERENCE_PATTERNS:
        match = re.search(pattern, query)
        if match:
            return UserPreferenceConstraint(preference_type=pref_type, keyword=match.group())
    return None


DECISION_PATTERNS = [
    (r"(是否|能不能|该不该|要不要).{0,6}(应该|可以|需要)", "yes_no"),
    (r"是否应该", "yes_no"),
    (r"(推荐|建议|介绍).{0,4}(哪些|什么|哪|哪种)", "recommendation"),
    (r"(有什么|有哪些).{0,4}(推荐|建议)", "recommendation"),
    (r"(选择|选).{0,4}(哪个|哪种|什么)", "comparison"),
    (r"(哪个|哪种).{0,2}(更|比较).{0,2}(好|优|合适|适合)", "comparison"),
    (r"怎么.{0,2}(选择|决策|判断)", "suggestion"),
    (r"(如何|怎样).{0,2}(决策|选择|判断|评估)", "suggestion"),
    (r"(应该|可以).{0,4}(还是|或者)", "comparison"),
]


def extract_decision_constraint(query: str) -> DecisionConstraint | None:
    """Extract decision-type constraint from a query string.

    Args:
        query: Query text.

    Returns:
        DecisionConstraint if found, None otherwise.
    """
    for pattern, dec_type in DECISION_PATTERNS:
        match = re.search(pattern, query)
        if match:
            return DecisionConstraint(decision_type=dec_type, keyword=match.group())
    return None


class RerankerConfig:
    """Configuration for optional Cross-Encoder reranker (D-RRF-8)."""

    def __init__(
        self,
        enabled: bool = False,
        strategy: str = "none",
        model_path: str | None = None,
        top_k_for_rerank: int = 20,
        top_k_after_rerank: int = 10,
    ):
        self.enabled = enabled
        self.strategy = strategy
        self.model_path = model_path
        self.top_k_for_rerank = top_k_for_rerank
        self.top_k_after_rerank = top_k_after_rerank


class RRFFusionEngine:
    """Four-path RRF fusion engine.

    Combines retrieval results from Layer-R (vector), Layer-S (graph),
    BM25 (keyword), and Temporal paths using weighted RRF scoring.
    """

    def __init__(
        self,
        repository: "CognitiveRepository",
        bm25_search_fn: Any | None = None,
        vector_search_fn: Any | None = None,
        reranker_config: RerankerConfig | None = None,
    ):
        """Initialize RRFFusionEngine.

        Args:
            repository: CognitiveRepository for node operations.
            bm25_search_fn: Optional async BM25 search function.
            vector_search_fn: Optional async vector search function.
            reranker_config: Optional reranker configuration.
        """
        self._repo = repository
        self._bm25_search = bm25_search_fn
        self._vector_search = vector_search_fn
        self._reranker_config = reranker_config or RerankerConfig()

    async def fuse(
        self,
        query: str,
        query_type: str = "mixed",
        space_id: str = "default",
        top_k: int = 10,
        disposition_weights: dict[str, float] | None = None,
    ) -> list[RetrievalResult]:
        """Execute four-path retrieval and RRF fusion.

        Args:
            query: Query text.
            query_type: Type of query (factual, multi_hop, temporal, analytical, mixed).
            space_id: Space to search within.
            top_k: Maximum number of results.
            disposition_weights: Optional disposition-adjusted type weights.

        Returns:
            Fused and ranked retrieval results.
        """
        if query_type == "analytical":
            return await self._search_analytical(query, space_id, top_k, disposition_weights)

        weights = QUERY_TYPE_WEIGHTS.get(query_type, QUERY_TYPE_WEIGHTS["mixed"])

        layer_r_results = await self._search_layer_r(query, space_id, top_k)
        layer_s_results = await self._search_layer_s(query, space_id, top_k)
        bm25_results = await self._search_bm25(query, space_id, top_k)
        temporal_results = await self._search_temporal(query, space_id, top_k)

        all_results = {
            "layer_r": layer_r_results,
            "layer_s": layer_s_results,
            "bm25": bm25_results,
            "temporal": temporal_results,
        }

        fused = self._compute_rrf(
            all_results,
            weights,
            disposition_weights or BASE_TYPE_WEIGHTS,
        )

        fused.sort(key=lambda r: (
            r.score,
            COGNITIVE_LAYER_PRIORITY.get(r.cognitive_layer, 0),
            _temporal_proximity_score(r),
        ), reverse=True)

        if self._reranker_config.enabled:
            fused = await self._rerank(query, fused)

        return fused[:top_k]

    def _compute_rrf(
        self,
        all_results: dict[str, list[RetrievalResult]],
        weights: dict[str, float],
        type_weights: dict[str, float],
    ) -> list[RetrievalResult]:
        """Compute weighted RRF scores for all results.

        Args:
            all_results: Results from each retrieval path.
            weights: Path weights (w_layer_r, w_layer_s, w_bm25, w_temporal).
            type_weights: Memory type weights.

        Returns:
            Deduplicated and scored results.
        """
        doc_scores: dict[str, float] = {}
        doc_data: dict[str, RetrievalResult] = {}

        path_mapping = {
            "layer_r": "w_layer_r",
            "layer_s": "w_layer_s",
            "bm25": "w_bm25",
            "temporal": "w_temporal",
        }

        for path_name, results in all_results.items():
            w_key = path_mapping.get(path_name, "w_layer_r")
            w = weights.get(w_key, 0.0)

            for rank, result in enumerate(results, start=1):
                rrf_contribution = w / (RRF_K + rank)

                if result.doc_id not in doc_scores:
                    doc_scores[result.doc_id] = 0.0
                    doc_data[result.doc_id] = result

                doc_scores[result.doc_id] += rrf_contribution

        for doc_id, base_score in doc_scores.items():
            result = doc_data[doc_id]
            type_weight = type_weights.get(result.memory_type, 1.0)
            doc_scores[doc_id] = base_score * type_weight

        fused_results = []
        for doc_id, score in doc_scores.items():
            result = doc_data[doc_id]
            result.score = score
            fused_results.append(result)

        return fused_results

    async def _rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Apply Cross-Encoder reranking (D-RRF-8).

        Strategy dispatch:
        - "none": passthrough (no reranking)
        - "local_gguf": load GGUF reranker model from model_path
        - "api": call external reranker API

        Args:
            query: Original query text.
            candidates: RRF-fused candidate results.

        Returns:
            Reranked results (truncated to top_k_after_rerank).
        """
        cfg = self._reranker_config
        if not cfg.enabled or cfg.strategy == "none":
            return candidates

        candidates = candidates[:cfg.top_k_for_rerank]

        if cfg.strategy == "local_gguf" and cfg.model_path:
            try:
                reranked = await self._rerank_local_gguf(query, candidates, cfg)
                return reranked[:cfg.top_k_after_rerank]
            except Exception as e:
                logger.warning("Local GGUF reranker failed, falling back: %s", e)
                return candidates[:cfg.top_k_after_rerank]

        if cfg.strategy == "api":
            try:
                reranked = await self._rerank_api(query, candidates, cfg)
                return reranked[:cfg.top_k_after_rerank]
            except Exception as e:
                logger.warning("API reranker failed, falling back: %s", e)
                return candidates[:cfg.top_k_after_rerank]

        return candidates[:cfg.top_k_after_rerank]

    async def _rerank_local_gguf(
        self,
        query: str,
        candidates: list[RetrievalResult],
        cfg: RerankerConfig,
    ) -> list[RetrievalResult]:
        """Rerank using local GGUF Cross-Encoder model.

        Placeholder: requires llama-cpp-python or similar runtime.
        When model_path is valid and runtime available, loads the model
        and computes cross-encoder scores for (query, doc) pairs.
        """
        from pathlib import Path
        model_file = Path(cfg.model_path) if cfg.model_path else None
        if model_file and model_file.exists():
            try:
                from llama_cpp import Llama
                model = Llama(model_path=str(model_file))
                scored = []
                for c in candidates:
                    score = model.score(query, c.content)
                    c.score = float(score) if score is not None else c.score
                    scored.append(c)
                scored.sort(key=lambda r: r.score, reverse=True)
                return scored
            except ImportError:
                logger.warning("llama-cpp-python not installed, skipping GGUF reranker")
        return candidates

    async def _rerank_api(
        self,
        query: str,
        candidates: list[RetrievalResult],
        cfg: RerankerConfig,
    ) -> list[RetrievalResult]:
        """Rerank using external API Cross-Encoder.

        Placeholder: requires API endpoint configuration.
        """
        logger.info("API reranker not yet configured, returning candidates as-is")
        return candidates

    async def _search_layer_r(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Search Layer-R (vector retrieval).

        Falls back to repository query if no vector search function.
        """
        if self._vector_search is not None:
            try:
                return await self._vector_search(query, space_id, top_k)
            except Exception as e:
                logger.warning("Layer-R search failed: %s", e)

        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            limit=top_k,
        )
        return [
            RetrievalResult(
                doc_id=n.id,
                content=n.content,
                source="layer_r",
                memory_type=n.memory_type,
                cognitive_layer=n.cognitive_layer,
                occurred_at=n.occurred_at,
                created_at=n.created_at,
            )
            for n in nodes
        ]

    async def _search_layer_s(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Search Layer-S (graph traversal).

        Returns entity, observation, and mental_model nodes as graph results.
        """
        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            limit=top_k,
        )
        return [
            RetrievalResult(
                doc_id=n.id,
                content=n.content,
                source="layer_s",
                memory_type=n.memory_type,
                cognitive_layer=n.cognitive_layer,
                occurred_at=n.occurred_at,
                created_at=n.created_at,
            )
            for n in nodes
            if n.memory_type in ("entity", "observation", "mental_model")
        ]

    async def _search_bm25(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Search BM25 (keyword retrieval).

        Uses Chinese tokenizer for CJK queries, falls back to substring matching.
        """
        if self._bm25_search is not None:
            try:
                return await self._bm25_search(query, space_id, top_k)
            except Exception as e:
                logger.warning("BM25 search failed: %s", e)

        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            limit=200,
        )

        from ontology_engine.engine.cognitive.bm25_tokenizer import (
            ChineseTokenizer,
        )
        tokenizer = ChineseTokenizer()
        query_tokens = tokenizer.tokenize_query(query)
        query_lower = query.lower()

        scored: list[tuple[RetrievalResult, int]] = []
        for n in nodes:
            content_lower = n.content.lower()
            if query_lower in content_lower:
                matches = len(query_tokens) if query_tokens else 1
                scored.append((
                    RetrievalResult(
                        doc_id=n.id,
                        content=n.content,
                        source="bm25",
                        memory_type=n.memory_type,
                        cognitive_layer=n.cognitive_layer,
                        occurred_at=n.occurred_at,
                        created_at=n.created_at,
                    ),
                    matches,
                ))
            elif query_tokens:
                token_hits = sum(1 for t in query_tokens if t.lower() in content_lower)
                if token_hits >= max(1, len(query_tokens) // 2):
                    scored.append((
                        RetrievalResult(
                            doc_id=n.id,
                            content=n.content,
                            source="bm25",
                            memory_type=n.memory_type,
                            cognitive_layer=n.cognitive_layer,
                            occurred_at=n.occurred_at,
                            created_at=n.created_at,
                        ),
                        token_hits,
                    ))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]

    async def _search_analytical(
        self,
        query: str,
        space_id: str,
        top_k: int,
        disposition_weights: dict[str, float] | None = None,
    ) -> list[RetrievalResult]:
        """Search for analytical queries.

        Analytical queries require cross-entity synthesis. Strategy:
        1. Broad retrieval across all memory types (not just entity)
        2. Weighted RRF with emphasis on Layer-S (graph structure)
        3. Boost mental_model and observation types for synthesis
        """
        weights = QUERY_TYPE_WEIGHTS["analytical"]

        layer_r_results = await self._search_layer_r(query, space_id, top_k * 2)
        layer_s_results = await self._search_layer_s_broad(query, space_id, top_k * 2)
        bm25_results = await self._search_bm25(query, space_id, top_k * 2)
        temporal_results = await self._search_temporal(query, space_id, top_k)

        all_results = {
            "layer_r": layer_r_results,
            "layer_s": layer_s_results,
            "bm25": bm25_results,
            "temporal": temporal_results,
        }

        analytical_type_weights = {
            "mental_model": 4.0,
            "opinion": 3.0,
            "entity": 2.5,
            "observation": 2.0,
            "constraint": 2.0,
            "rule": 2.0,
            "commitment": 1.5,
            "procedure": 1.5,
            "task_state": 1.3,
            "episode": 1.2,
            "self_experience": 1.1,
            "fragment": 0.8,
        }

        fused = self._compute_rrf(
            all_results,
            weights,
            disposition_weights or analytical_type_weights,
        )

        fused.sort(key=lambda r: (
            r.score,
            COGNITIVE_LAYER_PRIORITY.get(r.cognitive_layer, 0),
            _temporal_proximity_score(r),
        ), reverse=True)

        return fused[:top_k]

    async def _search_layer_s_broad(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Search Layer-S across all memory types (not just entity).

        Used by analytical queries that need cross-type synthesis.
        """
        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            limit=top_k,
        )
        return [
            RetrievalResult(
                doc_id=n.id,
                content=n.content,
                source="layer_s",
                memory_type=n.memory_type,
                cognitive_layer=n.cognitive_layer,
                occurred_at=n.occurred_at,
                created_at=n.created_at,
            )
            for n in nodes
            if n.memory_type in ("entity", "observation", "mental_model", "opinion", "constraint")
        ]

    async def _search_temporal(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """Search temporal path.

        Extracts temporal constraints from query and searches
        CognitiveNode temporal fields.
        """
        constraint = extract_temporal_constraint(query)
        if constraint is None:
            return []

        nodes = await self._repo.query_nodes(
            domain_id=space_id,
            limit=100,
        )

        results = []
        for n in nodes:
            if n.occurred_at and constraint.period_start and constraint.period_end:
                if constraint.period_start <= n.occurred_at <= constraint.period_end:
                    results.append(RetrievalResult(
                        doc_id=n.id,
                        content=n.content,
                        source="temporal",
                        memory_type=n.memory_type,
                        cognitive_layer=n.cognitive_layer,
                        occurred_at=n.occurred_at,
                        created_at=n.created_at,
                    ))

        return results[:top_k]


def _temporal_proximity_score(result: RetrievalResult) -> float:
    """Compute temporal proximity score for a retrieval result.

    Design §5: newer nodes get higher scores. Uses occurred_at or created_at.

    Formula: score = exp(-0.05 * days_since_occurrence)
    """
    from datetime import datetime, timezone
    import math

    timestamp = result.occurred_at or result.created_at
    if not timestamp:
        return 0.0
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0.0
    now = datetime.now(timezone.utc)
    days = max(0, (now - dt).total_seconds() / 86400.0)
    return math.exp(-0.05 * days)

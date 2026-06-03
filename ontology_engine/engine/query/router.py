"""Query type enumeration and routing configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QueryType(str, Enum):
    FACTUAL = "factual"
    MULTI_HOP = "multi_hop"
    TEMPORAL = "temporal"
    ANALYTICAL = "analytical"
    MIXED = "mixed"


FACTUAL_PATTERNS: dict[str, list[str]] = {
    "zh": ["谁", "什么", "哪个", "哪里", "多少", "是否", "有没有"],
    "en": ["who", "what", "which", "where", "how many", "how much", "is there", "does"],
}

MULTI_HOP_PATTERNS: dict[str, list[str]] = {
    "zh": ["为什么", "如何", "关系", "导致", "影响", "原因", "结果", "因果", "之间"],
    "en": ["why", "how", "relationship between", "leads to", "causes", "affects", "because", "therefore"],
}

TEMPORAL_PATTERNS: dict[str, list[str]] = {
    "zh": ["什么时候", "何时", "持续多久", "历史", "变化", "趋势", "之前", "之后", "期间", "时间线"],
    "en": ["when", "how long", "history", "change over", "trend", "before", "after", "during", "timeline"],
}

ANALYTICAL_PATTERNS: dict[str, list[str]] = {
    "zh": ["计算", "分析", "占比", "评估", "评分", "评级", "风险等级", "合规"],
    "en": ["calculate", "analyze", "ratio", "evaluate", "score", "rate", "grade", "compliance"],
}


@dataclass
class RetrievalParams:
    query_type: QueryType
    chroma_top_k: int = 10
    ladybug_max_depth: int = 2
    edge_weights: dict[str, float] = field(default_factory=dict)
    temporal_filter: bool = False
    extracted_from_expansion: bool = True
    trace_to_backtrack: bool = False
    bundle_search_enabled: bool = False
    rrf_weights: dict[str, float] = field(default_factory=lambda: {
        "layer_r": 0.6,
        "layer_s": 0.2,
        "bm25": 0.2,
    })
    confidence_threshold: float = 0.3


RRF_WEIGHT_MAP: dict[QueryType, dict[str, float]] = {
    QueryType.FACTUAL: {"layer_r": 0.6, "layer_s": 0.2, "bm25": 0.2},
    QueryType.MULTI_HOP: {"layer_r": 0.3, "layer_s": 0.5, "bm25": 0.2},
    QueryType.TEMPORAL: {"layer_r": 0.3, "layer_s": 0.5, "bm25": 0.2},
    QueryType.ANALYTICAL: {"layer_r": 0.0, "layer_s": 0.0, "bm25": 0.0},
    QueryType.MIXED: {"layer_r": 0.4, "layer_s": 0.4, "bm25": 0.2},
}


def detect_query_type(query: str) -> QueryType:
    query_lower = query.lower()
    hits: set[QueryType] = set()

    for patterns in FACTUAL_PATTERNS.values():
        if any(p in query_lower for p in patterns):
            hits.add(QueryType.FACTUAL)

    for patterns in MULTI_HOP_PATTERNS.values():
        if any(p in query_lower for p in patterns):
            hits.add(QueryType.MULTI_HOP)

    for patterns in TEMPORAL_PATTERNS.values():
        if any(p in query_lower for p in patterns):
            hits.add(QueryType.TEMPORAL)

    for patterns in ANALYTICAL_PATTERNS.values():
        if any(p in query_lower for p in patterns):
            hits.add(QueryType.ANALYTICAL)

    if len(hits) >= 2:
        return QueryType.MIXED
    if len(hits) == 1:
        return hits.pop()
    return QueryType.FACTUAL


def build_retrieval_params(query_type: QueryType) -> RetrievalParams:
    params = RetrievalParams(query_type=query_type)
    params.rrf_weights = RRF_WEIGHT_MAP.get(query_type, RRF_WEIGHT_MAP[QueryType.FACTUAL]).copy()

    if query_type == QueryType.MULTI_HOP:
        params.ladybug_max_depth = 3
        params.bundle_search_enabled = True
        params.extracted_from_expansion = True
    elif query_type == QueryType.TEMPORAL:
        params.temporal_filter = True
        params.ladybug_max_depth = 2
    elif query_type == QueryType.ANALYTICAL:
        params.trace_to_backtrack = True
    elif query_type == QueryType.MIXED:
        params.bundle_search_enabled = True
        params.extracted_from_expansion = True
        params.trace_to_backtrack = True
        params.ladybug_max_depth = 3

    return params

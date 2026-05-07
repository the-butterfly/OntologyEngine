"""Query router types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievalParams:
    """Parameters for a retrieval operation.

    Attributes:
        query_type: Detected query type.
        cognitive_layers: Ordered list of cognitive layers to search.
        memory_types: Memory types to include.
        chroma_top_k: Top-K for vector retrieval.
        kuzu_max_depth: Max graph traversal depth.
        edge_weights: Edge type weights.
        temporal_filter: Whether to apply temporal filtering.
        cog_extracted_from_expansion: Whether to expand via COG_EXTRACTED_FROM.
        cog_supported_by_backtrack: Whether to backtrack via COG_SUPPORTED_BY.
        bundle_search_enabled: Whether to enable bundle search.
        rrf_weights: RRF path weights.
        confidence_threshold: Minimum confidence threshold.
        belief_status_filter: Belief status filter.
        allow_short_circuit: Whether to allow short-circuit in funnel.
    """
    query_type: str = "factual"
    cognitive_layers: list[str] = field(default_factory=lambda: ["opinion", "semantic", "procedure", "perception"])
    memory_types: list[str] = field(default_factory=lambda: ["mental_model", "entity", "observation", "fragment"])
    chroma_top_k: int = 10
    kuzu_max_depth: int = 1
    edge_weights: dict[str, float] = field(default_factory=dict)
    temporal_filter: bool = False
    cog_extracted_from_expansion: bool = True
    cog_supported_by_backtrack: bool = False
    bundle_search_enabled: bool = False
    rrf_weights: dict[str, float] = field(default_factory=lambda: {
        "w_layer_r": 0.5, "w_layer_s": 0.2, "w_bm25": 0.2, "w_temporal": 0.1,
    })
    confidence_threshold: float = 0.5
    belief_status_filter: str = "accepted"
    allow_short_circuit: bool = True


QUERY_TYPE_PATTERNS = {
    "temporal": {
        "zh": ["什么时候", "何时", "持续多久", "历史", "变化", "趋势", "之前", "之后", "期间", "时间线"],
        "en": ["when", "how long", "history", "change over", "trend", "before", "after", "during", "timeline"],
    },
    "decision": {
        "zh": ["推荐", "建议", "是否应该", "选择哪个", "怎么选", "应该还是", "如何决策", "要不要", "该不该"],
        "en": ["recommend", "suggest", "should i", "which one", "better choice", "decide"],
    },
    "analytical": {
        "zh": ["计算", "分析", "占比", "评估", "评分", "评级", "风险等级", "合规"],
        "en": ["calculate", "analyze", "ratio", "evaluate", "score", "rate", "grade", "compliance"],
    },
    "user_preference": {
        "zh": ["偏好", "倾向", "喜欢", "习惯", "我的风格", "个人偏好", "用户偏好", "保守型", "激进型", "稳健型"],
        "en": ["prefer", "preference", "tendency", "like", "my style", "habit"],
    },
    "multi_hop": {
        "zh": ["为什么", "如何", "关系", "导致", "影响", "原因", "结果", "因果", "之间"],
        "en": ["why", "how", "relationship between", "leads to", "causes", "affects", "because", "therefore"],
    },
    "factual": {
        "zh": ["谁", "什么", "哪个", "哪里", "多少", "是否", "有没有"],
        "en": ["who", "what", "which", "where", "how many", "how much", "is there", "does"],
    },
}

PARAM_PRESETS = {
    "factual": RetrievalParams(
        query_type="factual",
        chroma_top_k=10,
        kuzu_max_depth=1,
        edge_weights={"TEMPORAL": 1.0, "CAUSAL": 1.0, "COGNITIVE_RELATES_TO": 1.0},
        temporal_filter=False,
        cog_extracted_from_expansion=True,
        cog_supported_by_backtrack=False,
        bundle_search_enabled=False,
        rrf_weights={"w_layer_r": 0.5, "w_layer_s": 0.2, "w_bm25": 0.2, "w_temporal": 0.1},
        confidence_threshold=0.5,
    ),
    "multi_hop": RetrievalParams(
        query_type="multi_hop",
        chroma_top_k=5,
        kuzu_max_depth=3,
        edge_weights={"TEMPORAL": 1.0, "CAUSAL": 2.0, "COGNITIVE_RELATES_TO": 1.5},
        temporal_filter=False,
        cog_extracted_from_expansion=False,
        cog_supported_by_backtrack=False,
        bundle_search_enabled=True,
        rrf_weights={"w_layer_r": 0.2, "w_layer_s": 0.5, "w_bm25": 0.1, "w_temporal": 0.2},
        confidence_threshold=0.4,
    ),
    "temporal": RetrievalParams(
        query_type="temporal",
        chroma_top_k=5,
        kuzu_max_depth=2,
        edge_weights={"TEMPORAL": 3.0, "CAUSAL": 1.0, "COGNITIVE_RELATES_TO": 1.0},
        temporal_filter=True,
        cog_extracted_from_expansion=True,
        cog_supported_by_backtrack=False,
        bundle_search_enabled=True,
        rrf_weights={"w_layer_r": 0.1, "w_layer_s": 0.2, "w_bm25": 0.1, "w_temporal": 0.6},
        confidence_threshold=0.4,
    ),
    "analytical": RetrievalParams(
        query_type="analytical",
        chroma_top_k=0,
        kuzu_max_depth=0,
        edge_weights={},
        temporal_filter=False,
        cog_supported_by_backtrack=True,
        bundle_search_enabled=False,
        rrf_weights={"w_layer_r": 0.0, "w_layer_s": 0.0, "w_bm25": 0.0, "w_temporal": 0.0},
        confidence_threshold=0.0,
    ),
    "mixed": RetrievalParams(
        query_type="mixed",
        chroma_top_k=10,
        kuzu_max_depth=3,
        edge_weights={"TEMPORAL": 2.0, "CAUSAL": 1.5, "COGNITIVE_RELATES_TO": 1.2},
        temporal_filter=False,
        cog_extracted_from_expansion=True,
        cog_supported_by_backtrack=True,
        bundle_search_enabled=True,
        rrf_weights={"w_layer_r": 0.3, "w_layer_s": 0.3, "w_bm25": 0.2, "w_temporal": 0.2},
        confidence_threshold=0.4,
    ),
    "user_preference": RetrievalParams(
        query_type="user_preference",
        chroma_top_k=5,
        kuzu_max_depth=3,
        edge_weights={"COGNITIVE_RELATES_TO": 2.0, "COG_EXTRACTED_FROM": 1.5},
        temporal_filter=False,
        cog_extracted_from_expansion=True,
        cog_supported_by_backtrack=True,
        bundle_search_enabled=False,
        rrf_weights={"w_layer_r": 0.2, "w_layer_s": 0.5, "w_bm25": 0.1, "w_temporal": 0.2},
        confidence_threshold=0.5,
        memory_types=["mental_model", "opinion", "self_experience", "entity", "observation", "fragment"],
    ),
    "decision": RetrievalParams(
        query_type="decision",
        chroma_top_k=5,
        kuzu_max_depth=3,
        edge_weights={"TEMPORAL": 1.0, "CAUSAL": 2.0, "COGNITIVE_RELATES_TO": 1.5},
        temporal_filter=False,
        cog_extracted_from_expansion=True,
        cog_supported_by_backtrack=True,
        bundle_search_enabled=True,
        rrf_weights={"w_layer_r": 0.2, "w_layer_s": 0.4, "w_bm25": 0.2, "w_temporal": 0.2},
        confidence_threshold=0.4,
        memory_types=["mental_model", "rule", "procedure", "constraint", "entity", "observation"],
    ),
}

DEGRADATION_CHAINS = {
    "factual": ["layer_r", "bm25", "layer_s"],
    "multi_hop": ["layer_s", "bundle", "layer_r"],
    "temporal": ["layer_s_temporal", "widen_window", "layer_r"],
    "analytical": ["rule_engine", "layer_s", "layer_r"],
    "mixed": ["collaborative", "best_single"],
    "user_preference": ["layer_s", "layer_r", "bm25"],
    "decision": ["layer_s", "bundle", "layer_r"],
}

MIN_RESULTS_THRESHOLD = 3
MIN_CONFIDENCE_THRESHOLD = 0.3

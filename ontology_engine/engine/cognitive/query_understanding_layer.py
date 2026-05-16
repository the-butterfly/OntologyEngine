from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAX_TOTAL_BOOST = 3.0


@dataclass
class QueryConstraint:
    constraint_type: str
    value: str | float | bool
    confidence: float = 1.0
    source: str = "rule"
    raw_match: str = ""


@dataclass
class StrategyAdjustment:
    boost_factor: float = 1.0
    boost_model_tag: str | None = None
    boost_memory_types: list[str] = field(default_factory=list)
    boost_entity_names: list[str] = field(default_factory=list)
    temporal_window_days: int | None = None
    min_proof_count: int = 0
    min_belief_status: str = ""
    require_evidence: bool = False
    boost_weights: dict[str, float] = field(default_factory=dict)

    def matches(self, result: dict) -> bool:
        if self.boost_model_tag:
            result_tags = result.get("tags", {}) or {}
            if result_tags.get("model") != self.boost_model_tag:
                return False
        if self.boost_memory_types and result.get("memory_type") not in self.boost_memory_types:
            return False
        if self.boost_entity_names and result.get("entity_name") not in self.boost_entity_names:
            return False
        return True


@dataclass
class RetrievalStrategyAdjustment:
    adjustments: list[StrategyAdjustment] = field(default_factory=list)

    def apply(self, adjustment: StrategyAdjustment, constraint: QueryConstraint | None = None) -> None:
        self.adjustments.append(adjustment)


@dataclass
class RecallContext:
    space_id: str = ""
    active_task_id: str = ""
    user_id: str = ""
    conversation_history: list[str] = field(default_factory=list)
    user_preferences: dict[str, str] = field(default_factory=dict)
    pending_commitments: list[str] = field(default_factory=list)
    disposition: Any = None


CONSTRAINT_TO_RETRIEVAL_STRATEGY = {
    "temporal_scope": StrategyAdjustment(boost_factor=1.3, boost_weights={"temporal": 0.6}, temporal_window_days=30),
    "user_preference": StrategyAdjustment(boost_factor=1.5, boost_model_tag="self", boost_memory_types=["opinion", "mental_model", "self_experience"]),
    "decision_type": StrategyAdjustment(boost_factor=1.4, boost_model_tag="task", boost_memory_types=["rule", "constraint"], require_evidence=True),
    "task_history": StrategyAdjustment(boost_factor=1.3, boost_model_tag="task", boost_memory_types=["commitment", "task_state", "episode"]),
    "environmental": StrategyAdjustment(boost_factor=1.3, boost_model_tag="world", boost_memory_types=["constraint", "rule"]),
    "self_reference": StrategyAdjustment(boost_factor=1.2, boost_model_tag="self", boost_memory_types=["self_experience", "procedure"]),
    "entity_targets": StrategyAdjustment(boost_factor=2.0, boost_entity_names=[]),
    "confidence_demand": StrategyAdjustment(boost_factor=1.0, min_proof_count=2, min_belief_status="accepted"),
}


TEMPORAL_PATTERNS = [
    (r"最近|今天|昨天|前天|本周|上周|本月|上月|刚刚|刚才", "recent"),
    (r"以前|过去|之前|曾经|历史上|往期", "past"),
    (r"未来|将来|接下来|即将|计划|预计", "future"),
]

USER_PREFERENCE_PATTERNS = [
    (r"我喜欢|我偏好|我习惯|我想要|我希望|根据我的|按我的", "explicit"),
    (r"推荐|建议|适合我|合我意", "implicit"),
]

DECISION_PATTERNS = [
    (r"应该|不该|值得|不值得|选择|决定|判断|权衡|利弊|优缺点", "deliberative"),
    (r"对比|比较|vs|versus|哪个好|哪个更好|区别", "comparative"),
]


class RuleExtractor:

    def extract(self, query: str) -> list[QueryConstraint]:
        return []


class TemporalConstraintExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        import re
        constraints = []
        for pattern, scope in TEMPORAL_PATTERNS:
            if re.search(pattern, query):
                constraints.append(QueryConstraint(
                    constraint_type="temporal_scope",
                    value=scope,
                    confidence=0.9,
                    source="rule",
                ))
                break
        return constraints


class UserPreferenceExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        import re
        constraints = []
        for pattern, pref_type in USER_PREFERENCE_PATTERNS:
            if re.search(pattern, query):
                constraints.append(QueryConstraint(
                    constraint_type="user_preference",
                    value=pref_type,
                    confidence=0.85,
                    source="rule",
                ))
                break
        return constraints


class DecisionTypeExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        import re
        constraints = []
        for pattern, dec_type in DECISION_PATTERNS:
            if re.search(pattern, query):
                constraints.append(QueryConstraint(
                    constraint_type="decision_type",
                    value=dec_type,
                    confidence=0.8,
                    source="rule",
                ))
                break
        return constraints


class TaskHistoryExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        keywords = ["之前", "上次", "历史", "曾经", "否决过", "拒绝过", "回顾", "复盘", "总结", "以前", "过往", "早前", "先前", "过去", "旧版", "原方案", "上一个", "前一次", "讨论过"]
        for kw in keywords:
            if kw in query:
                return [QueryConstraint(constraint_type="task_history", value=kw, confidence=0.7, source="rule", raw_match=kw)]
        return []


class EnvironmentalExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        keywords = ["限制", "条件", "前提", "约束", "环境", "上下文", "平台", "系统要求", "兼容", "限制因素", "资源限制", "技术栈", "框架", "运行环境", "部署约束", "基础设施", "硬件限制", "网络限制"]
        for kw in keywords:
            if kw in query:
                return [QueryConstraint(constraint_type="environmental", value=kw, confidence=0.6, source="rule", raw_match=kw)]
        return []


class SelfReferenceExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        patterns = ["我的经验", "我之前", "我们决定", "我自己", "我们", "我的工具", "自己", "本人", "亲身", "亲自", "试过", "我觉得", "我认为", "我判断", "我们的方案", "我们的决策", "我方"]
        for p in patterns:
            if p in query:
                return [QueryConstraint(constraint_type="self_reference", value=p, confidence=0.8, source="rule", raw_match=p)]
        return []


class EntityTargetExtractor(RuleExtractor):

    def extract(self, query: str) -> list[QueryConstraint]:
        import re
        constraints = []
        quoted = re.findall(r'["""]([^"""]+)["""]', query)
        book_titles = re.findall(r'《([^》]+)》', query)
        bracketed = re.findall(r'【([^】]+)】', query)
        all_entities = quoted + book_titles + bracketed
        for entity_name in all_entities:
            constraints.append(QueryConstraint(
                constraint_type="entity_targets",
                value=entity_name,
                source="rule",
                confidence=0.9,
                raw_match=entity_name,
            ))
        return constraints


class ConfidenceDemandExtractor(RuleExtractor):

    KEYWORD_MAP = {
        "务必": 0.95, "一定": 0.95, "必须": 0.95, "零误差": 0.95,
        "精确": 0.85, "准确": 0.85, "严格": 0.85, "不容有误": 0.85,
        "确定": 0.75, "确认": 0.75, "可靠": 0.75, "权威": 0.75,
        "大概": 0.3, "可能": 0.3, "也许": 0.3, "似乎": 0.3,
    }

    def extract(self, query: str) -> list[QueryConstraint]:
        for kw, val in self.KEYWORD_MAP.items():
            if kw in query:
                return [QueryConstraint(constraint_type="confidence_demand", value=val, confidence=0.8, source="rule", raw_match=kw)]
        return []


QUERY_TYPE_FROM_CONSTRAINTS = {
    "temporal_scope": "temporal",
    "user_preference": "user_preference",
    "decision_type": "analytical",
    "task_history": "mixed",
    "environmental": "mixed",
    "self_reference": "mixed",
    "entity_targets": "factual",
    "confidence_demand": "analytical",
}


class QueryUnderstandingLayer:

    def __init__(self, repository: Any | None = None, llm_call: Callable | None = None) -> None:
        self._repo = repository
        self._llm_call = llm_call
        self._llm_available = llm_call is not None
        self._extractors: list[RuleExtractor] = [
            TemporalConstraintExtractor(),
            UserPreferenceExtractor(),
            DecisionTypeExtractor(),
            TaskHistoryExtractor(),
            EnvironmentalExtractor(),
            SelfReferenceExtractor(),
            EntityTargetExtractor(),
            ConfidenceDemandExtractor(),
        ]

    async def extract_constraints(self, query: str, context: RecallContext | None = None) -> list[QueryConstraint]:
        constraints: list[QueryConstraint] = []
        for extractor in self._extractors:
            try:
                extracted = extractor.extract(query)
                constraints.extend(extracted)
            except Exception as e:
                logger.warning("Extractor %s failed: %s", type(extractor).__name__, e)
        if self._llm_available and len(constraints) < 2:
            try:
                import asyncio
                llm_constraints = await asyncio.wait_for(
                    self._extract_with_llm(query, context), timeout=0.5,
                )
                for c in llm_constraints:
                    c.source = "llm"
                constraints.extend(llm_constraints)
            except asyncio.TimeoutError:
                logger.warning("LLM constraint extraction timed out, using rule-only results")
            except Exception as e:
                logger.warning("LLM constraint extraction failed: %s", e)
        return constraints

    async def _extract_with_llm(self, query: str, context: RecallContext | None = None) -> list[QueryConstraint]:
        if not self._llm_call:
            return []
        return []

    def map_to_retrieval_strategy(self, constraints: list[QueryConstraint]) -> RetrievalStrategyAdjustment:
        import dataclasses
        adjustment = RetrievalStrategyAdjustment()
        for c in constraints:
            strategy = CONSTRAINT_TO_RETRIEVAL_STRATEGY.get(c.constraint_type)
            if strategy:
                adj = dataclasses.replace(strategy)
                if c.constraint_type == "entity_targets" and isinstance(c.value, str):
                    adj = dataclasses.replace(adj, boost_entity_names=[c.value])
                if c.constraint_type == "confidence_demand" and isinstance(c.value, (int, float)):
                    if c.value >= 0.9:
                        adj = dataclasses.replace(adj, min_proof_count=3, min_belief_status="accepted", require_evidence=True)
                    elif c.value >= 0.7:
                        adj = dataclasses.replace(adj, min_proof_count=2, min_belief_status="accepted")
                    elif c.value >= 0.5:
                        adj = dataclasses.replace(adj, min_proof_count=1)
                adjustment.apply(adj, c)
        return adjustment

    def apply_constraint_boost(self, results: list[dict], constraints: list[QueryConstraint]) -> list[dict]:
        strategy = self.map_to_retrieval_strategy(constraints)
        for r in results:
            total_boost = 1.0
            for adj in strategy.adjustments:
                if adj.matches(r):
                    total_boost *= adj.boost_factor
            r["constraint_boost"] = min(total_boost, MAX_TOTAL_BOOST)
            r["rank_score"] = r.get("rank_score", 0) * r["constraint_boost"]
        results = sorted(results, key=lambda x: x["rank_score"], reverse=True)

        for adj in strategy.adjustments:
            if adj.min_proof_count > 0:
                results = [r for r in results if r.get("proof_count", 0) >= adj.min_proof_count]
            if adj.min_belief_status:
                status_order = {"accepted": 3, "pending_review": 2, "contradicted": 1, "superseded": 0, "rejected": 0}
                min_level = status_order.get(adj.min_belief_status, 0)
                results = [r for r in results if status_order.get(r.get("belief_status", ""), 0) >= min_level]
            if adj.require_evidence:
                results = [r for r in results if r.get("source_fragment_ids") or r.get("proof_count", 0) > 0]

        return results

    def infer_query_type(self, constraints: list[QueryConstraint]) -> str:
        if not constraints:
            return "mixed"
        for c in constraints:
            qt = QUERY_TYPE_FROM_CONSTRAINTS.get(c.constraint_type)
            if qt:
                return qt
        return "mixed"

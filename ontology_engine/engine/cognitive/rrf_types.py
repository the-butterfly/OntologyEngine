"""RRF fusion types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalResult:
    """A single retrieval result from any retrieval path.

    Attributes:
        doc_id: Document/node ID.
        content: Content text.
        score: Raw retrieval score.
        source: Retrieval source (layer_r, layer_s, bm25, temporal).
        memory_type: Memory type of the result.
        cognitive_layer: Cognitive layer of the result.
        metadata: Additional metadata.
        edge_type: Edge type for evidence chain (SUPPORTS, CONSOLIDATED_INTO).
        confidence: Confidence score from source node (0-1).
        contribution: Contribution weight of this evidence.
    """
    doc_id: str
    content: str
    score: float = 0.0
    source: str = "unknown"
    memory_type: str = "fragment"
    cognitive_layer: str = "perception"
    metadata: dict[str, Any] = field(default_factory=dict)
    edge_type: str = "SUPPORTS"
    confidence: float = 1.0
    contribution: float = 0.5
    occurred_at: str | None = None
    created_at: str | None = None


@dataclass
class TemporalConstraint:
    """Temporal constraint extracted from a query.

    Attributes:
        kind: Type of temporal constraint (year, range, since, before, relative).
        groups: Match groups from the regex pattern.
    """
    kind: str
    groups: tuple[str, ...] = ()

    @property
    def period_start(self) -> str | None:
        """Get the start of the time period."""
        if self.kind == "year" and self.groups:
            return f"{self.groups[0]}-01-01"
        if self.kind == "range" and len(self.groups) >= 2:
            return f"{self.groups[0]}-01-01"
        if self.kind == "since" and len(self.groups) >= 2:
            return f"{self.groups[1]}-01-01"
        if self.kind == "range_zh" and len(self.groups) >= 2:
            return f"{self.groups[0]}-01-01"
        if self.kind == "since_zh" and len(self.groups) >= 2:
            return f"{self.groups[1]}-01-01"
        if self.kind in ("relative_zh", "relative_zh_year", "relative_zh_month"):
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            if self.kind == "relative_zh_year":
                year_map = {"今年": 0, "本年": 0, "去年": -1, "上年": -1, "前年": -2}
                offset = year_map.get(self.groups[0] if self.groups else "", 0)
                return f"{now.year + offset}-01-01"
            if self.kind == "relative_zh_month":
                month_map = {"本月": 0, "这个月": 0, "上月": -1, "上个月": -1}
                offset = month_map.get(self.groups[0] if self.groups else "", 0)
                target_month = now.month + offset
                target_year = now.year
                while target_month < 1:
                    target_month += 12
                    target_year -= 1
                while target_month > 12:
                    target_month -= 12
                    target_year += 1
                return f"{target_year}-{target_month:02d}-01"
            if self.kind == "relative_zh" and self.groups:
                text = "".join(self.groups)
                delta_map = {"天": 1, "周": 7, "月": 30, "年": 365, "季度": 90}
                count_map = {"一": 1, "两": 2, "三": 3, "几": 3, "半": 0.5}
                count: int | float = 1
                unit_days = 30
                for ch in text:
                    if ch in count_map:
                        count = count_map[ch]
                    if ch in delta_map:
                        unit_days = delta_map[ch]
                total_days = int(count * unit_days)
                start = now - timedelta(days=total_days)
                return start.strftime("%Y-%m-%d")
        return None

    @property
    def period_end(self) -> str | None:
        """Get the end of the time period."""
        if self.kind == "year" and self.groups:
            return f"{self.groups[0]}-12-31"
        if self.kind == "range" and len(self.groups) >= 2:
            return f"{self.groups[1]}-12-31"
        if self.kind == "before" and len(self.groups) >= 2:
            return f"{self.groups[1]}-12-31"
        if self.kind == "range_zh" and len(self.groups) >= 2:
            return f"{self.groups[1]}-12-31"
        if self.kind == "before_zh" and len(self.groups) >= 2:
            return f"{self.groups[1]}-12-31"
        if self.kind in ("relative_zh", "relative_zh_year", "relative_zh_month"):
            from datetime import datetime, timezone
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return None


@dataclass
class UserPreferenceConstraint:
    """User preference constraint extracted from a query.

    Attributes:
        preference_type: Category of preference (risk_averse, growth_oriented,
                        conservative, aggressive, balanced).
        keyword: The matched keyword phrase.
    """
    preference_type: str
    keyword: str = ""


@dataclass
class DecisionConstraint:
    """Decision-type constraint extracted from a query.

    Attributes:
        decision_type: Category (recommendation, comparison, yes_no, suggestion).
        keyword: The matched keyword phrase.
    """
    decision_type: str
    keyword: str = ""


RRF_K = 60

QUERY_TYPE_WEIGHTS = {
    "factual": {"w_layer_r": 0.5, "w_layer_s": 0.2, "w_bm25": 0.2, "w_temporal": 0.1},
    "multi_hop": {"w_layer_r": 0.2, "w_layer_s": 0.5, "w_bm25": 0.1, "w_temporal": 0.2},
    "temporal": {"w_layer_r": 0.1, "w_layer_s": 0.2, "w_bm25": 0.1, "w_temporal": 0.6},
    "analytical": {"w_layer_r": 0.2, "w_layer_s": 0.4, "w_bm25": 0.2, "w_temporal": 0.2},
    "mixed": {"w_layer_r": 0.3, "w_layer_s": 0.3, "w_bm25": 0.2, "w_temporal": 0.2},
    "user_preference": {"w_layer_r": 0.2, "w_layer_s": 0.5, "w_bm25": 0.1, "w_temporal": 0.2},
    "decision": {"w_layer_r": 0.2, "w_layer_s": 0.4, "w_bm25": 0.2, "w_temporal": 0.2},
}

BASE_TYPE_WEIGHTS = {
    "mental_model": 3.0,
    "opinion": 2.5,
    "commitment": 1.9,
    "entity": 2.0,
    "rule": 2.0,
    "constraint": 1.8,
    "observation": 1.5,
    "procedure": 1.8,
    "task_state": 1.6,
    "episode": 1.2,
    "self_experience": 1.1,
    "fragment": 1.0,
}

COGNITIVE_LAYER_PRIORITY = {
    "opinion": 4,
    "semantic": 3,
    "procedure": 2,
    "perception": 1,
}

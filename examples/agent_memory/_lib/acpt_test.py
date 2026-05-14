"""Acceptance test infrastructure for Agent Memory evaluation.

Replaces the old EvalResult/EvalReport with a score-only model.
Each scenario produces a continuous score [0.0, 1.0] rather than
binary pass/fail. The global acceptance threshold is configurable.

Key differences from old _ok()/EvalReport:
- No `passed` field — continuous score only
- F1 / rank-weighted / chain-adjacency for retrieval tests
- Weighted assertion banks for management tests
- Per-category summary with sub-scores
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AcptResult:
    """Single acceptance test result. score in [0.0, 1.0]."""

    name: str
    score: float = 0.0
    details: str = ""
    latency_ms: float = 0.0
    sub_scores: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        self.score = max(0.0, min(1.0, self.score))


@dataclass
class AcptReport:
    """Score-only acceptance report with category-aware summary."""

    case_name: str = ""
    total: int = 0
    results: list[AcptResult] = field(default_factory=list)
    threshold: float = 0.70

    def add(self, r: AcptResult) -> None:
        self.total += 1
        self.results.append(r)

    @property
    def mean_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def min_score(self) -> float:
        if not self.results:
            return 0.0
        return min(r.score for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.score >= self.threshold)

    def category_mean(self, prefix: str) -> float:
        subset = [r for r in self.results if r.name.startswith(prefix)]
        if not subset:
            return 0.0
        return sum(r.score for r in subset) / len(subset)

    def summary(self) -> str:
        lines = [
            "=" * 70,
            f"ACPT Report: {self.case_name}",
            f"  Scenarios: {self.total}",
            f"  Mean Score: {self.mean_score:.3f}  Min Score: {self.min_score:.3f}",
            f"  >= {self.threshold}: {self.passed_count}/{self.total}",
            "=" * 70,
        ]
        for r in self.results:
            bar = _score_bar(r.score)
            lines.append(
                f"  [{r.score:.2f}] {bar} {r.name}  ({r.latency_ms:.0f}ms)"
            )
            if r.details:
                for d in r.details.split("\n")[:5]:
                    lines.append(f"         {d}")
            if r.sub_scores:
                sub = ", ".join(f"{k}={v:.2f}" for k, v in r.sub_scores.items())
                lines.append(f"         sub: {sub}")
        lines.append("=" * 70)
        return "\n".join(lines)

    def save(self, case_dir: Path) -> Path:
        results_dir = case_dir / "results"
        results_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = results_dir / f"acpt_{ts}.json"
        payload: dict[str, Any] = {
            "timestamp": ts,
            "case": self.case_name,
            "total": self.total,
            "mean_score": round(self.mean_score, 4),
            "min_score": round(self.min_score, 4),
            "passed_count": self.passed_count,
            "threshold": self.threshold,
            "results": [
                {
                    "name": r.name,
                    "score": round(r.score, 4),
                    "details": r.details,
                    "latency_ms": round(r.latency_ms, 1),
                    "sub_scores": {k: round(v, 4) for k, v in r.sub_scores.items()},
                }
                for r in self.results
            ],
        }
        out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        return out_file


def _score_bar(score: float, width: int = 10) -> str:
    filled = int(round(score * width))
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Scoring Helpers
# ---------------------------------------------------------------------------


def f1_score(results: list[dict[str, Any]], expected_keywords: list[str]) -> dict[str, float]:
    """Precision / Recall / F1 based on keyword presence in result text.

    Args:
        results: recall() result dicts, each must have a "text" key.
        expected_keywords: keywords that SHOULD appear.

    Returns:
        dict with precision, recall, f1 keys.
    """
    texts = [r.get("text", "") for r in results]
    hits = sum(1 for kw in expected_keywords if any(kw in t for t in texts))
    precision = hits / max(len(results), 1)
    recall = hits / max(len(expected_keywords), 1)
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def rank_weighted_score(
    results: list[dict[str, Any]], relevant_keywords: list[str]
) -> float:
    """Rank-weighted relevance: Σ(1 / rank_i) for each relevant result.

    A result is "relevant" if its text contains any of the relevant_keywords.
    Higher-ranked results contribute more.

    Maximum possible score = Σ(1/k) for k=1..n where n = len(relevant_keywords),
    normalized to [0, 1].
    """
    texts = [r.get("text", "") for r in results]
    scored = 0.0
    for rank, text in enumerate(texts, start=1):
        if any(kw in text for kw in relevant_keywords):
            scored += 1.0 / rank
    max_possible = sum(1.0 / k for k in range(1, len(relevant_keywords) + 1))
    if max_possible == 0:
        return 0.0
    return round(scored / max_possible, 4)


def check_recall_chain_adjacency(
    results: list[dict[str, Any]], chain_keywords: list[tuple[str, str]]
) -> dict[str, float]:
    """Verify multi-hop recall chain: adjacent keywords should appear in
    nearby result positions, indicating the system traversed an inference chain.

    Args:
        results: recall() result dicts.
        chain_keywords: ordered pairs [(step1_kw, step2_kw), ...] where
                        each pair represents adjacent nodes in the reasoning chain.

    Returns:
        dict with adjacency_score (0-1) and pair_scores per pair.
    """
    texts = [r.get("text", "") for r in results]
    pair_scores: dict[str, float] = {}
    for a_kw, b_kw in chain_keywords:
        a_positions = [i for i, t in enumerate(texts) if a_kw in t]
        b_positions = [i for i, t in enumerate(texts) if b_kw in t]
        if not a_positions or not b_positions:
            pair_scores[f"{a_kw}<->{b_kw}"] = 0.0
            continue
        min_dist = min(abs(a - b) for a in a_positions for b in b_positions)
        max_rank = max(len(texts) - 1, 1)
        pair_scores[f"{a_kw}<->{b_kw}"] = round(1.0 - min_dist / max_rank, 4)

    adj_score = sum(pair_scores.values()) / max(len(pair_scores), 1)
    return {"adjacency_score": round(adj_score, 4), **pair_scores}


def score_behavior(checks: list[tuple[bool, float]], label: str = "") -> dict[str, float]:
    """Weighted assertion bank for management-style tests.

    Each check is (passed: bool, weight: float).
    Total score = Σ(passed * weight) / Σ(weight).

    Returns:
        dict with score and per-check results.
    """
    total_weight = sum(w for _, w in checks)
    if total_weight == 0:
        return {"score": 0.0}
    earned = sum(w for passed, w in checks if passed)
    result: dict[str, float] = {"score": round(earned / total_weight, 4)}
    for i, (passed, w) in enumerate(checks):
        key = f"{label}_check_{i}" if label else f"check_{i}"
        result[key] = 1.0 if passed else 0.0
    return result


# ---------------------------------------------------------------------------
# Convenience result builder
# ---------------------------------------------------------------------------


def r(
    name: str,
    score: float,
    details: str = "",
    latency_ms: float = 0.0,
    sub_scores: dict[str, float] | None = None,
) -> AcptResult:
    return AcptResult(
        name=name,
        score=score,
        details=details,
        latency_ms=latency_ms,
        sub_scores=sub_scores or {},
    )
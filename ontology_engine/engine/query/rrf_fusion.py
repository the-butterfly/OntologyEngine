"""RRF (Reciprocal Rank Fusion) for multi-path result merging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RRF_K = 60


@dataclass
class RRFDocument:
    doc_id: str
    doc_type: str
    score: float
    source: str
    data: dict[str, Any] | None = None


class RRFFusion:
    """Reciprocal Rank Fusion for combining Layer-R, Layer-S, and BM25 results."""

    def __init__(self, k: int = RRF_K) -> None:
        self._k = k

    def fuse(
        self,
        layer_r_results: list[RRFDocument],
        layer_s_results: list[RRFDocument],
        bm25_results: list[RRFDocument] | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[RRFDocument]:
        w = weights or {"layer_r": 0.6, "layer_s": 0.2, "bm25": 0.2}
        scores: dict[str, float] = {}
        doc_map: dict[str, RRFDocument] = {}

        self._add_rank_scores(layer_r_results, "layer_r", w.get("layer_r", 0.6), scores, doc_map)
        self._add_rank_scores(layer_s_results, "layer_s", w.get("layer_s", 0.2), scores, doc_map)
        if bm25_results:
            self._add_rank_scores(bm25_results, "bm25", w.get("bm25", 0.2), scores, doc_map)

        fused = []
        for doc_id, total_score in scores.items():
            doc = doc_map[doc_id]
            fused.append(RRFDocument(
                doc_id=doc_id,
                doc_type=doc.doc_type,
                score=total_score,
                source=doc.source,
                data=doc.data,
            ))

        return sorted(fused, key=lambda d: d.score, reverse=True)

    def _add_rank_scores(
        self,
        results: list[RRFDocument],
        source: str,
        weight: float,
        scores: dict[str, float],
        doc_map: dict[str, RRFDocument],
    ) -> None:
        for rank, doc in enumerate(results, start=1):
            rrf_score = weight / (self._k + rank)
            if doc.doc_id not in scores:
                scores[doc.doc_id] = 0.0
            scores[doc.doc_id] += rrf_score
            if doc.doc_id not in doc_map:
                doc_map[doc.doc_id] = doc

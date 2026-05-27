"""LOCOMO benchmark metrics.

Mirrors the computation logic from memory-benchmarks/benchmarks/locomo/run.py
so that OE and Mem0 results are directly comparable.
"""

from __future__ import annotations

import statistics
from collections import defaultdict


def cutoff_label(c: int) -> str:
    return f"top_{c}"


def compute_locomo_metrics(evaluations: list[dict], cutoffs: list[int]) -> dict:
    """Compute per-category and overall metrics at each cutoff."""
    metrics_by_cutoff = {}
    for c in cutoffs:
        label = cutoff_label(c)
        total = len(evaluations)
        scores = [
            e.get("cutoff_results", {}).get(label, {}).get("score", 0.0)
            for e in evaluations
        ]
        correct = sum(1 for s in scores if s >= 0.5)

        by_category: dict[str, list] = defaultdict(list)
        for e in evaluations:
            cat_name = e.get("category_name", "unknown")
            by_category[cat_name].append(
                e.get("cutoff_results", {}).get(label, {}).get("score", 0.0)
            )

        cat_metrics = {}
        for cat_name in sorted(by_category):
            cat_scores = by_category[cat_name]
            cat_correct = sum(1 for s in cat_scores if s >= 0.5)
            cat_metrics[cat_name] = {
                "total": len(cat_scores),
                "correct": cat_correct,
                "accuracy": cat_correct / len(cat_scores) * 100 if cat_scores else 0.0,
                "avg_score": statistics.mean(cat_scores) * 100 if cat_scores else 0.0,
            }

        metrics_by_cutoff[label] = {
            "overall": {
                "total": total,
                "correct": correct,
                "accuracy": correct / total * 100 if total else 0.0,
                "avg_score": statistics.mean(scores) * 100 if scores else 0.0,
            },
            "by_category": cat_metrics,
        }
    return metrics_by_cutoff


def display_results(metrics_by_cutoff: dict, cutoffs: list[int]) -> None:
    """Print metrics to console in a compact table."""
    for c in cutoffs:
        label = cutoff_label(c)
        m = metrics_by_cutoff.get(label, {})
        overall = m.get("overall", {})
        print(f"\n--- {label} ---")
        print(
            f"  Overall: {overall.get('correct', 0)}/{overall.get('total', 0)} "
            f"({overall.get('accuracy', 0):.1f}%) avg={overall.get('avg_score', 0):.1f}%"
        )
        for cat_name, cm in sorted(m.get("by_category", {}).items()):
            print(f"  {cat_name}: {cm['correct']}/{cm['total']} ({cm['accuracy']:.1f}%)")


def build_comparison_table(
    oe_metrics: dict,
    mem0_metrics: dict,
    cutoffs: list[int],
) -> str:
    """Build a Markdown comparison table between OE and Mem0."""
    lines = [
        "# LOCOMO Benchmark: OE vs Mem0 Comparison",
        "",
        "| Cutoff | Backend | Overall Acc | short-term | medium-term | long-term | cross-dialogue |",
        "|--------|---------|-------------|------------|-------------|-----------|----------------|",
    ]
    for c in cutoffs:
        label = cutoff_label(c)
        for backend, metrics in [("OE", oe_metrics), ("Mem0", mem0_metrics)]:
            if not metrics:
                continue
            m = metrics.get(label, {})
            overall = m.get("overall", {})
            by_cat = m.get("by_category", {})
            acc = overall.get("accuracy", 0.0)
            st = by_cat.get("short-term", {}).get("accuracy", 0.0)
            mt = by_cat.get("medium-term", {}).get("accuracy", 0.0)
            lt = by_cat.get("long-term", {}).get("accuracy", 0.0)
            cd = by_cat.get("cross-dialogue", {}).get("accuracy", 0.0)
            lines.append(
                f"| {label} | {backend} | {acc:.1f}% | {st:.1f}% | {mt:.1f}% | {lt:.1f}% | {cd:.1f}% |"
            )
    lines.append("")
    return "\n".join(lines)

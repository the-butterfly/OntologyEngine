"""Shared CLI Runner for Agent Memory evaluation cases.

Each method maps 1:1 to a CLI command, calling MemoryAPI
through the standard public interface. No internal module imports.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from ontology_engine.engine.cognitive.factory import create_memory_api
from ontology_engine.engine.cognitive.memory_api import MemoryAPI


@dataclass
class EvalResult:
    name: str
    passed: bool = False
    score: float = 0.0
    details: str = ""
    latency_ms: float = 0.0


@dataclass
class EvalReport:
    total: int = 0
    passed: int = 0
    results: list[EvalResult] = field(default_factory=list)

    def add(self, r: EvalResult):
        self.total += 1
        if r.passed:
            self.passed += 1
        self.results.append(r)

    def summary(self) -> str:
        lines = [
            "=" * 70,
            f"Eval Report: {self.passed}/{self.total} passed "
            f"({self.passed / max(self.total, 1) * 100:.1f}%)",
            "=" * 70,
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"[{status}] {r.name} (score={r.score:.2f}, {r.latency_ms:.0f}ms)")
            if r.details:
                for d in r.details.split("\n")[:3]:
                    lines.append(f"       {d}")
        lines.append("=" * 70)
        return "\n".join(lines)


def _ok(name: str, passed: bool, score: float, details: str, latency_ms: float) -> EvalResult:
    return EvalResult(name=name, passed=passed, score=score, details=details, latency_ms=latency_ms)


class CLIRunner:
    """CLI-equivalent runner for Agent Memory operations."""

    def __init__(self, api: MemoryAPI, space_id: str = "default"):
        self._api = api
        self._space = space_id

    @property
    def api(self) -> MemoryAPI:
        return self._api

    @property
    def space(self) -> str:
        return self._space

    def set_space(self, space_id: str) -> None:
        self._space = space_id

    async def remember(self, content: str, *, memory_type: str = "fragment",
                       tags: list[str] | None = None, confidence: float = 1.0,
                       visibility: str = "shared", created_by: str | None = None,
                       source_pipeline: str | None = None, model_domain: str | None = None,
                       source_trust_tier: str | None = None, belief_status: str = "accepted",
                       auto_consolidate: bool = False, supersede_target: str | None = None,
                       supersede_reason: str | None = None, scope: dict | None = None) -> dict:
        r = await self._api.remember(
            content=content, space_id=self._space, memory_type=memory_type,
            tags=tags or [], confidence=confidence, visibility=visibility,
            created_by=created_by, source_pipeline=source_pipeline,
            belief_status=belief_status, auto_consolidate=auto_consolidate,
            supersede_target=supersede_target, supersede_reason=supersede_reason)
        data = r.get("data", r)
        if "memory_id" in data and "node_id" not in data:
            data["node_id"] = data["memory_id"]
        return data

    async def recall(self, query: str, *, memory_type: str | None = None,
                     max_results: int = 10, include_evidence: bool = True,
                     evidence_depth: int = 1, min_confidence: float = 0.5,
                     cognitive_layer: str | None = None, include_superseded: bool = False,
                     user_id: str | None = None) -> dict:
        r = await self._api.recall(
            query=query, space_id=self._space, memory_type=memory_type,
            max_results=max_results, include_evidence=include_evidence,
            evidence_depth=evidence_depth, min_confidence=min_confidence,
            cognitive_layer=cognitive_layer, include_superseded=include_superseded, user_id=user_id)
        return r.get("data", r)

    async def reflect(self, query: str, *, max_iterations: int = 5,
                      focus_types: list[str] | None = None, async_mode: bool = False,
                      skip_consolidation: bool = False, skip_forgetting: bool = True,
                      cascade_depth: int = 3) -> dict:
        r = await self._api.reflect(
            query=query, space_id=self._space, max_iterations=max_iterations,
            focus_types=focus_types, async_mode=async_mode,
            skip_consolidation=skip_consolidation, skip_forgetting=skip_forgetting,
            cascade_depth=cascade_depth)
        return r.get("data", r)

    async def approve(self, node_id: str, *, action: str = "approve",
                      comment: str = "") -> dict:
        r = await self._api.approve_memory(
            node_id=node_id, action=action, comment=comment)
        return r.get("data", r)

    async def consolidate(self) -> dict:
        r = await self._api.run_consolidation(self._space)
        return r.get("data", r)

    async def forget(self, days_elapsed: int = 1) -> dict:
        r = await self._api.run_forgetting(self._space, days_elapsed=days_elapsed)
        return r.get("data", r)

    async def stats(self) -> dict:
        r = await self._api.get_stats(self._space)
        return r.get("data", r)

    async def types(self) -> dict:
        r = await self._api.get_types(self._space)
        return r.get("data", r)

    async def audit(self, limit: int = 50) -> dict:
        r = await self._api.get_audit_trail(self._space, limit=limit)
        return r.get("data", r)

    async def correct(self, node_id: str, corrected_text: str, *,
                      reason: str = "", user_id: str = "cli_user") -> dict:
        r = await self._api.correct_memory(
            node_id=node_id, corrected_text=corrected_text, reason=reason, user_id=user_id)
        return r.get("data", r)

    async def delete(self, node_id: str, *, cascade: bool = False,
                     user_id: str = "cli_user") -> dict:
        r = await self._api.delete_memory(
            node_id=node_id, space_id=self._space, cascade=cascade, user_id=user_id)
        return r.get("data", r)

    async def list_my(self, user_id: str, *, scope_type: str | None = None,
                      memory_type: str | None = None, limit: int = 50) -> dict:
        r = await self._api.list_my_memories(
            space_id=self._space, user_id=user_id, scope_type=scope_type,
            memory_type=memory_type, limit=limit)
        return r.get("data", r)

    async def record_commitment(self, content: str, *, deadline: str | None = None,
                                task_id: str | None = None, created_by: str | None = None) -> dict:
        r = await self._api.record_commitment(
            content=content, space_id=self._space, deadline=deadline,
            task_id=task_id, created_by=created_by)
        return r.get("data", r)

    async def check_commitments(self, *, status: str | None = None,
                                overdue: bool = False) -> dict:
        r = await self._api.check_commitments(
            space_id=self._space, status=status, overdue=overdue)
        return r.get("data", r)

    async def compile_entity(self, entity_id: str) -> dict:
        r = await self._api.compile_entity_page(
            entity_id=entity_id, space_id=self._space)
        return r.get("data", r)

    async def compile_topic(self, topic: str, entity_ids: list[str]) -> dict:
        r = await self._api.compile_topic_page(
            topic=topic, entity_ids=entity_ids, space_id=self._space)
        return r.get("data", r)

    async def dream(self) -> dict:
        r = await self._api.run_dream_cycle(space_id=self._space)
        return r.get("data", r)

    @staticmethod
    def extract_constraints(query: str) -> dict:
        from ontology_engine.engine.cognitive.rrf_fusion import (
            extract_temporal_constraint,
            extract_user_preference_constraint,
            extract_decision_constraint,
        )
        tc = extract_temporal_constraint(query)
        upc = extract_user_preference_constraint(query)
        dc = extract_decision_constraint(query)
        result: dict = {
            "query": query,
            "has_temporal": tc is not None,
            "has_user_preference": upc is not None,
            "has_decision": dc is not None,
        }
        if tc is not None:
            result["temporal_constraint"] = tc
        if upc is not None:
            result["user_preference_constraint"] = upc
        if dc is not None:
            result["decision_constraint"] = dc
        return result


async def create_runner(space_id: str, tmp_dir: Path | None = None) -> tuple[CLIRunner, Path]:
    if tmp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="mem_eval_"))
    api, _ = await create_memory_api(db_path=str(tmp_dir / "cognitive"))
    return CLIRunner(api, space_id=space_id), tmp_dir


def save_report(report: EvalReport, case_dir: Path, case_name: str):
    results_dir = case_dir / "results"
    results_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = results_dir / f"eval_{ts}.json"
    out_file.write_text(json.dumps({
        "timestamp": ts, "case": case_name,
        "total": report.total, "passed": report.passed,
        "pass_rate": report.passed / max(report.total, 1),
        "results": [{"name": r.name, "passed": bool(r.passed), "score": float(r.score),
                     "details": r.details, "latency_ms": float(r.latency_ms)} for r in report.results],
    }, indent=2, ensure_ascii=False))
    return out_file

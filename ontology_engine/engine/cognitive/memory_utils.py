from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.engine.cognitive.reflect_types import (
    ReflectionJob,
    ReflectionPhase,
    ReflectionProgress,
    ReflectionStatus,
)

_MEMORY_TYPE_PATTERNS: list[tuple[str, list[str]]] = [
    ("entity", [
        r"\b(is|are|was|were)\s+(a|an|the)?\s*\w+\s+(who|which|that|where)",
        r"\b(company|person|organization|product|place|city|country)\b",
        r"(公司|企业|机构|组织|人物|产品|地点|城市|国家)",
    ]),
    ("relation", [
        r"\b(works?\s+at|owns?|located\s+in|based\s+in|founded|manages?|reports?\s+to)",
        r"\b(partner|subsidiary|parent\s+company|supplier|customer)\b",
        r"(任职|拥有|位于|总部|创办|管理|汇报|合作|子公司|母公司|供应商|客户)",
    ]),
    ("rule", [
        r"\b(should|must|shall|cannot|must\s+not|if.*then|when.*then|rule|policy)",
        r"(应该|必须|不得|禁止|如果.*则|规则|政策|规定)",
    ]),
    ("episode", [
        r"\b(on\s+\w+\s+\d{1,2}(\w{2})?,?\s+\d{4}|in\s+\w+\s+\d{4}|yesterday|today|last\s+\w+)",
        r"\b(happened|occurred|took\s+place|event|incident)\b",
        r"(昨天|今天|上周|上月|发生|出现|事件|事故)",
    ]),
    ("procedure", [
        r"\b(first|then|next|finally|step\s*\d|procedure|process|how\s+to|instructions)",
        r"(首先|然后|接着|最后|步骤|流程|操作|方法)",
    ]),
    ("opinion", [
        r"\b(i\s+(think|believe|feel|suspect|hope)|in\s+my\s+opinion|probably|likely|seems)",
        r"(我认为|我觉得|相信|希望|可能|大概|似乎)",
    ]),
    ("observation", [
        r"\b(observed|noticed|detected|found|measured|recorded|data\s+shows)",
        r"(观察到|发现|检测到|测量|记录|数据显示)",
    ]),
]


def infer_memory_type(content: str) -> str:
    text = content.lower()
    for mem_type, patterns in _MEMORY_TYPE_PATTERNS:
        for pat in patterns:
            if re.search(pat, text):
                return mem_type
    return "fragment"


def generate_memory_id(content: str, space_id: str, memory_type: str) -> str:
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"mem:{memory_type}:{space_id}:{content_hash}"


def infer_cognitive_layer(memory_type: str) -> str:
    layer_mapping = {
        "mental_model": "opinion",
        "opinion": "opinion",
        "observation": "opinion",
        "commitment": "opinion",
        "entity": "semantic",
        "rule": "semantic",
        "constraint": "semantic",
        "task_state": "semantic",
        "metrics": "semantic",
        "relation": "semantic",
        "procedure": "procedure",
        "episode": "procedure",
        "self_experience": "perception",
        "fragment": "perception",
    }
    return layer_mapping.get(memory_type, "perception")


def infer_tags(memory_type: str) -> dict[str, str]:
    domain_mapping: dict[str, str] = {
        "entity": "world", "rule": "world", "constraint": "world",
        "observation": "world", "fragment": "world",
        "mental_model": "self", "opinion": "self", "self_experience": "self",
        "commitment": "task", "task_state": "task", "procedure": "task", "episode": "task",
        "metrics": "world", "relation": "world",
    }
    return {"model": domain_mapping.get(memory_type, "world")}


def compute_temporal_proximity(result: dict[str, Any]) -> float:
    import math

    timestamp = result.get("occurred_at") or result.get("created_at")
    if not timestamp:
        return 0.5
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days = max(0, (now - dt).total_seconds() / 86400.0)
        return math.exp(-0.05 * days)
    except (ValueError, TypeError):
        return 0.5


def extract_attributes(memory_type: str, metadata: dict[str, Any] | None) -> dict[str, str]:
    type_specific_keys: dict[str, list[str]] = {
        "observation": ["fact_type", "observed_at", "observer", "certainty"],
        "opinion": ["opinion_type", "sentiment", "holder", "topic", "confidence_basis", "review_required"],
        "mental_model": ["model_type", "scope", "abstraction_level"],
        "episode": ["event_type", "location", "participants", "duration"],
        "procedure": ["step_count", "domain", "difficulty", "prerequisites"],
        "entity": ["entity_name", "entity_type", "aliases"],
        "rule": ["rule_type", "scope", "priority"],
        "metrics": ["metric_name", "value", "unit", "computed_at", "computed_by"],
        "relation": ["relation_type", "source_entity", "target_entity", "weight"],
        "commitment": ["deadline", "status", "task_id", "fulfilled_by"],
        "constraint": ["constraint_type", "enforceable", "violation_action"],
        "self_experience": ["tool_name", "call_result", "latency_ms"],
        "task_state": ["task_id", "current_phase", "decision_log"],
    }
    if not metadata:
        return {}
    allowed = type_specific_keys.get(memory_type, [])
    return {k: str(v) for k, v in metadata.items() if k in allowed}


def determine_visibility(content: str, memory_type: str, source: str | None = None) -> str:
    if contains_personal_info(content):
        return "private"
    if memory_type in ("entity", "rule", "mental_model"):
        return "shared"
    if source == "user_input" and memory_type == "episode":
        return "private"
    return "shared"


def contains_personal_info(content: str) -> bool:
    patterns = [
        r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
        r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        r"\b\d{3}-\d{2}-\d{4}\b",
        r"\b(?:passport\s*(?:no|number|#)|ssn|social\s*security)\b",
    ]
    return any(re.search(p, content, re.IGNORECASE) for p in patterns)


def compute_strength(node: CognitiveNode) -> dict[str, Any]:
    recency = 0.5
    last_access = node.last_access_at or node.updated_at or node.created_at
    if last_access:
        try:
            accessed = datetime.fromisoformat(str(last_access).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age_hours = max(0, (now - accessed).total_seconds() / 3600)
            recency = max(0.0, 1.0 - (age_hours / (30 * 24)))
        except (ValueError, TypeError):
            pass

    evidence = min(1.0, len(node.source_fragment_ids) / 5.0) if isinstance(node.source_fragment_ids, list) and node.source_fragment_ids else 0.1

    feedback = node.feedback_weight

    frequency = min(1.0, node.access_count / 10.0) if node.access_count else 0.1

    confirmation = 0.1
    if hasattr(node, "proof_count") and node.proof_count:
        confirmation = min(1.0, node.proof_count / 5.0)

    strength = recency * 0.25 + confirmation * 0.15 + evidence * 0.25 + feedback * 0.2 + frequency * 0.15

    return {
        "value": round(strength, 3),
        "breakdown": {
            "recency": round(recency, 3),
            "confirmation": round(confirmation, 3),
            "evidence": round(evidence, 3),
            "feedback": round(feedback, 3),
            "access_frequency": round(frequency, 3),
        },
    }


def make_response(
    data: dict[str, Any] | None = None,
    space_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    return {
        "success": True,
        "data": data or {},
        "error": None,
        "meta": {
            "request_id": request_id or str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "space_id": space_id,
            "memory_version": "v2",
        },
    }


@dataclass
class RememberRequest:
    content: str
    space_id: str
    tags: dict[str, str | list[str]] | None = None
    memory_type: str = "fragment"
    metadata: dict[str, Any] | None = None
    visibility: str | None = None
    created_by: str | None = None
    confidence: float = 1.0
    supersede_target: str | None = None
    supersede_reason: str | None = None
    belief_status: str = "accepted"
    valid_from: str | None = None
    valid_to: str | None = None
    recorded_at: str | None = None
    occurred_at: str | None = None
    source_pipeline: str | None = None
    schema_ref: str | None = None
    source_fragment_ids: list[str] | None = None
    source_trust_tier: str | None = None
    auto_consolidate: bool = False


@dataclass
class RecallRequest:
    query: str
    space_id: str
    memory_type: str | None = None
    max_results: int = 10
    include_evidence: bool = True
    evidence_depth: int = 1
    user_id: str | None = None
    as_of: str | None = None
    allow_short_circuit: bool = True
    min_confidence: float = 0.5
    token_budget: int | None = None
    belief_status_filter: str | None = None
    reflection_id: str | None = None
    cognitive_layer: str | None = None
    expansion_rules: str | None = None
    disposition_override: dict[str, Any] | str | None = None


@dataclass
class ReflectRequest:
    query: str
    space_id: str
    max_iterations: int = 10
    focus_types: list[str] | None = None
    skip_consolidation: bool = False
    skip_forgetting: bool = False
    cascade_depth: int = 3
    skip_correction_propagation: bool = False


class ReflectionJobStore:

    def __init__(self):
        self._jobs: dict[str, ReflectionJob] = {}
        self._lock = asyncio.Lock()

    async def create_job(
        self,
        query: str,
        space_id: str,
        max_iterations: int = 10,
        focus_types: list[str] | None = None,
        skip_consolidation: bool = False,
        skip_forgetting: bool = False,
        cascade_depth: int = 3,
        skip_correction_propagation: bool = False,
    ) -> ReflectionJob:
        async with self._lock:
            reflection_id = f"refl:{uuid.uuid4().hex[:12]}"
            progress = ReflectionProgress(
                reflection_id=reflection_id,
                status=ReflectionStatus.PENDING,
                progress={phase.value: "pending" for phase in ReflectionPhase},
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            job = ReflectionJob(
                reflection_id=reflection_id,
                query=query,
                space_id=space_id,
                max_iterations=max_iterations,
                focus_types=focus_types,
                skip_consolidation=skip_consolidation,
                skip_forgetting=skip_forgetting,
                cascade_depth=cascade_depth,
                skip_correction_propagation=skip_correction_propagation,
                progress=progress,
            )
            self._jobs[reflection_id] = job
            return job

    async def get_job(self, reflection_id: str) -> ReflectionJob | None:
        async with self._lock:
            return self._jobs.get(reflection_id)

    async def update_progress(self, reflection_id: str, phase: str, phase_status: str) -> None:
        async with self._lock:
            job = self._jobs.get(reflection_id)
            if job and job.progress:
                job.progress.progress[phase] = phase_status
                if all(s == "completed" for s in job.progress.progress.values()):
                    job.progress.status = ReflectionStatus.COMPLETED
                    job.progress.completed_at = datetime.now(timezone.utc).isoformat()
                elif any(s == "in_progress" for s in job.progress.progress.values()):
                    job.progress.status = ReflectionStatus.IN_PROGRESS

    async def set_partial_results(self, reflection_id: str, key: str, results: Any) -> None:
        async with self._lock:
            job = self._jobs.get(reflection_id)
            if job and job.progress:
                job.progress.partial_results[key] = results

    async def set_error(self, reflection_id: str, error: str) -> None:
        async with self._lock:
            job = self._jobs.get(reflection_id)
            if job and job.progress:
                job.progress.status = ReflectionStatus.FAILED
            job.progress.error = error

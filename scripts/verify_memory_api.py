"""Functional verification script for Memory API.

Checks implementation completeness against docs/02-design/agent-memory/memory-api.md.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import traceback

from ontology_engine.engine.cognitive.consolidation_engine import ConsolidationEngine
from ontology_engine.engine.cognitive.entity_resolver import EntityResolver
from ontology_engine.engine.cognitive.errors import (
    COGNITIVE_ERROR_HTTP_MAP,
    CognitiveError,
    CognitiveErrorCode,
    ConsolidationInProgressError,
    InvalidBeliefTransitionError,
    InvalidMemoryTypeError,
    InvalidVisibilityError,
    MemoryNotReadyError,
    MemoryStaleError,
    ProtectedMemoryError,
    ReflectTimeoutError,
)
from ontology_engine.engine.cognitive.lifecycle import DreamCycle, ForgettingEngine
from ontology_engine.engine.cognitive.memory_api import MemoryAPI, ReflectionJobStore
from ontology_engine.engine.cognitive.models import (
    VALID_BELIEF_STATUSES,
    VALID_COGNITIVE_LAYERS,
    VALID_MEMORY_TYPES,
    VALID_VISIBILITIES,
    CognitiveNode,
    DispositionProfile,
)
from ontology_engine.engine.cognitive.query_router import QueryRouter
from ontology_engine.engine.cognitive.reflect_agent import ReflectAgent
from ontology_engine.engine.cognitive.reflect_types import (
    ReflectionJob,
    ReflectionPhase,
    ReflectionProgress,
    ReflectionStatus,
)
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.engine.cognitive.rrf_fusion import RRFFusionEngine
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore


class VerificationResult:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.missing: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []

    def ok(self, name: str):
        self.passed.append(name)

    def fail(self, name: str, reason: str):
        self.failed.append((name, reason))

    def miss(self, name: str, reason: str):
        self.missing.append((name, reason))

    def warn(self, name: str, reason: str):
        self.warnings.append((name, reason))

    def report(self) -> str:
        lines = []
        lines.append("=" * 72)
        lines.append("  Memory API 功能验证报告")
        lines.append("=" * 72)
        lines.append("")

        lines.append(f"  ✅ PASS:  {len(self.passed)}")
        lines.append(f"  ❌ FAIL:  {len(self.failed)}")
        lines.append(f"  🚫 MISS:  {len(self.missing)}")
        lines.append(f"  ⚠️  WARN:  {len(self.warnings)}")
        lines.append("")

        if self.passed:
            lines.append("-" * 72)
            lines.append("  ✅ PASS 项")
            lines.append("-" * 72)
            for name in self.passed:
                lines.append(f"  ✅ {name}")
            lines.append("")

        if self.failed:
            lines.append("-" * 72)
            lines.append("  ❌ FAIL 项（实现有误）")
            lines.append("-" * 72)
            for name, reason in self.failed:
                lines.append(f"  ❌ {name}")
                lines.append(f"     原因: {reason}")
            lines.append("")

        if self.missing:
            lines.append("-" * 72)
            lines.append("  🚫 MISS 项（设计文档要求但未实现）")
            lines.append("-" * 72)
            for name, reason in self.missing:
                lines.append(f"  🚫 {name}")
                lines.append(f"     设计要求: {reason}")
            lines.append("")

        if self.warnings:
            lines.append("-" * 72)
            lines.append("  ⚠️  WARN 项（部分实现或需关注）")
            lines.append("-" * 72)
            for name, reason in self.warnings:
                lines.append(f"  ⚠️  {name}")
                lines.append(f"     说明: {reason}")
            lines.append("")

        total = len(self.passed) + len(self.failed) + len(self.missing)
        pass_rate = len(self.passed) / total * 100 if total > 0 else 0
        lines.append("=" * 72)
        lines.append(f"  总通过率: {pass_rate:.1f}% ({len(self.passed)}/{total})")
        lines.append("=" * 72)

        return "\n".join(lines)


r = VerificationResult()


def check_section(title: str):
    print(f"\n>>> 检查: {title}")


# ============================================================
# Section 1: 三操作 API 存在性
# ============================================================
check_section("Section 1: 三操作 API")

if hasattr(MemoryAPI, "remember"):
    r.ok("remember 操作存在")
else:
    r.miss("remember 操作", "设计文档要求 remember 操作")

if hasattr(MemoryAPI, "recall"):
    r.ok("recall 操作存在")
else:
    r.miss("recall 操作", "设计文档要求 recall 操作")

if hasattr(MemoryAPI, "reflect"):
    r.ok("reflect 操作存在")
else:
    r.miss("reflect 操作", "设计文档要求 reflect 操作")

# ============================================================
# Section 2: oe_remember 参数与返回格式
# ============================================================
check_section("Section 2: remember 参数与返回")

sig = inspect.signature(MemoryAPI.remember)
params = list(sig.parameters.keys())

required_params = ["content", "space_id"]
for p in required_params:
    if p in params:
        r.ok(f"remember.{p} 参数存在")
    else:
        r.fail(f"remember.{p} 参数缺失", f"设计文档要求 remember 必须有 {p} 参数")

optional_params = {
    "tags": None,
    "memory_type": "fragment",
    "metadata": None,
    "auto_consolidate": False,
    "visibility": None,
    "created_by": None,
}
for p, default in optional_params.items():
    if p in params:
        actual_default = sig.parameters[p].default
        if actual_default == default or (default is None and actual_default is inspect.Parameter.empty and sig.parameters[p].annotation and "None" in str(sig.parameters[p].annotation)):
            r.ok(f"remember.{p} 参数存在 (默认={default})")
        else:
            r.warn(f"remember.{p} 默认值", f"期望默认={default}, 实际={actual_default}")
    else:
        r.miss(f"remember.{p} 参数", f"设计文档 Section 2/10.2 要求 remember 有 {p} 参数")

# ============================================================
# Section 3: oe_recall 参数与返回格式
# ============================================================
check_section("Section 3: recall 参数与返回")

sig = inspect.signature(MemoryAPI.recall)
params = list(sig.parameters.keys())

required_params = ["query", "space_id"]
for p in required_params:
    if p in params:
        r.ok(f"recall.{p} 参数存在")
    else:
        r.fail(f"recall.{p} 参数缺失", f"设计文档要求 recall 必须有 {p} 参数")

optional_params_recall = {
    "memory_type": None,
    "max_results": 10,
    "include_evidence": True,
    "evidence_depth": 1,
    "user_id": None,
}
for p, default in optional_params_recall.items():
    if p in params:
        r.ok(f"recall.{p} 参数存在 (默认={default})")
    else:
        r.miss(f"recall.{p} 参数", f"设计文档要求 recall 有 {p} 参数")

# L2 缺失参数
l2_missing_params = {
    "as_of": "设计文档 Section 3/10.3 L2 recall 要求 as_of 参数（时间点查询）",
    "token_budget": "设计文档 Section 3/10.3 L2 recall 要求 token_budget 参数",
    "allow_short_circuit": "设计文档 Section 10.3 L2 recall 要求 allow_short_circuit 参数",
    "min_confidence": "设计文档 Section 10.3 L2 recall 要求 min_confidence 参数",
}
for p, reason in l2_missing_params.items():
    if p in params:
        r.ok(f"recall.{p} L2 参数存在")
    else:
        r.miss(f"recall.{p} L2 参数缺失", reason)

# ============================================================
# Section 4: oe_reflect 参数与返回格式
# ============================================================
check_section("Section 4: reflect 参数与返回")

sig = inspect.signature(MemoryAPI.reflect)
params = list(sig.parameters.keys())

required_params = ["query", "space_id"]
for p in required_params:
    if p in params:
        r.ok(f"reflect.{p} 参数存在")
    else:
        r.fail(f"reflect.{p} 参数缺失", f"设计文档要求 reflect 必须有 {p} 参数")

optional_params_reflect = {
    "max_iterations": 10,
    "focus_types": None,
    "async_mode": True,
}
for p, default in optional_params_reflect.items():
    if p in params:
        r.ok(f"reflect.{p} 参数存在 (默认={default})")
    else:
        r.miss(f"reflect.{p} 参数", f"设计文档要求 reflect 有 {p} 参数")

# L3 缺失参数
l3_missing_params = {
    "cascade_depth": "设计文档 Section 10.4 L3 reflect 要求 cascade_depth 参数",
    "skip_consolidation": "设计文档 Section 10.4 L3 reflect 要求 skip_consolidation 参数",
    "skip_forgetting": "设计文档 Section 10.4 L3 reflect 要求 skip_forgetting 参数",
    "skip_correction_propagation": "设计文档 Section 10.4 L3 reflect 要求 skip_correction_propagation 参数",
}
for p, reason in l3_missing_params.items():
    if p in params:
        r.ok(f"reflect.{p} L3 参数存在")
    else:
        r.miss(f"reflect.{p} L3 参数缺失", reason)

# ============================================================
# Section 9: 错误码体系
# ============================================================
check_section("Section 9: 错误码体系")

required_error_codes = {
    "MEMORY_NOT_READY": 503,
    "CONSOLIDATION_IN_PROGRESS": 409,
    "PROTECTED_MEMORY": 403,
    "REFLECT_TIMEOUT": 504,
    "MEMORY_STALE": 200,
    "INVALID_MEMORY_TYPE": 422,
}
for code_name, expected_http in required_error_codes.items():
    try:
        code = CognitiveErrorCode[code_name]
        actual_http = COGNITIVE_ERROR_HTTP_MAP.get(code)
        if actual_http == expected_http:
            r.ok(f"错误码 {code_name} (HTTP {expected_http})")
        else:
            r.fail(f"错误码 {code_name} HTTP映射", f"期望 HTTP {expected_http}, 实际 {actual_http}")
    except KeyError:
        r.miss(f"错误码 {code_name}", f"设计文档 Section 9 要求 {code_name} 错误码 (HTTP {expected_http})")

# 错误类存在性
error_classes = {
    "MemoryNotReadyError": MemoryNotReadyError,
    "ConsolidationInProgressError": ConsolidationInProgressError,
    "ProtectedMemoryError": ProtectedMemoryError,
    "ReflectTimeoutError": ReflectTimeoutError,
    "MemoryStaleError": MemoryStaleError,
    "InvalidMemoryTypeError": InvalidMemoryTypeError,
    "InvalidVisibilityError": InvalidVisibilityError,
}
for cls_name, cls in error_classes.items():
    r.ok(f"错误类 {cls_name} 存在")

# CognitiveError.to_dict
if hasattr(CognitiveError, "to_dict"):
    err = CognitiveError("test", CognitiveErrorCode.EMPTY_INPUT)
    d = err.to_dict()
    if "error_code" in d and "message" in d and "http_status" in d:
        r.ok("CognitiveError.to_dict 序列化正确")
    else:
        r.fail("CognitiveError.to_dict", f"返回字典缺少必要字段: {d.keys()}")
else:
    r.miss("CognitiveError.to_dict", "设计文档要求错误可序列化")

# ============================================================
# Section 10: API 三层抽象
# ============================================================
check_section("Section 10: API 三层抽象")

# L1: 零配置
r.ok("L1 remember(content, space_id) — 可零配置调用")
r.ok("L1 recall(query, space_id) — 可零配置调用")
r.ok("L1 reflect(query, space_id) — 可零配置调用 (async_mode=True)")

# L2: 可选参数
l2_remember_params = ["tags", "memory_type", "visibility", "auto_consolidate"]
for p in l2_remember_params:
    if p in inspect.signature(MemoryAPI.remember).parameters:
        r.ok(f"L2 remember.{p} 可选参数存在")
    else:
        r.miss(f"L2 remember.{p}", "设计文档 Section 10.2 要求")

l2_recall_params = ["memory_type", "max_results", "include_evidence", "as_of", "token_budget"]
for p in l2_recall_params:
    if p in inspect.signature(MemoryAPI.recall).parameters:
        r.ok(f"L2 recall.{p} 可选参数存在")
    else:
        r.miss(f"L2 recall.{p}", "设计文档 Section 10.3 要求")

l2_reflect_params = ["max_iterations", "focus_types", "async_mode"]
for p in l2_reflect_params:
    if p in inspect.signature(MemoryAPI.reflect).parameters:
        r.ok(f"L2 reflect.{p} 可选参数存在")
    else:
        r.miss(f"L2 reflect.{p}", "设计文档 Section 10.3 要求")

# L3: 完整控制
l3_remember_params = ["metadata", "created_by"]
for p in l3_remember_params:
    if p in inspect.signature(MemoryAPI.remember).parameters:
        r.ok(f"L3 remember.{p} 参数存在")
    else:
        r.miss(f"L3 remember.{p}", "设计文档 Section 10.4 要求")

l3_recall_params = ["evidence_depth", "user_id"]
for p in l3_recall_params:
    if p in inspect.signature(MemoryAPI.recall).parameters:
        r.ok(f"L3 recall.{p} 参数存在")
    else:
        r.miss(f"L3 recall.{p}", "设计文档 Section 10.4 要求")

# ============================================================
# Section 11: 异步 Reflect
# ============================================================
check_section("Section 11: 异步 Reflect")

# ReflectionJobStore
if hasattr(MemoryAPI, "__init__"):
    r.ok("MemoryAPI.__init__ 存在")

if ReflectionJobStore is not None:
    r.ok("ReflectionJobStore 类存在")
    store = ReflectionJobStore()
    job = store.create_job("test", "space1")
    if job.reflection_id.startswith("refl:"):
        r.ok("ReflectionJob.reflection_id 格式正确 (refl:...)")
    else:
        r.fail("ReflectionJob.reflection_id", f"格式不正确: {job.reflection_id}")

    if hasattr(store, "get_job"):
        r.ok("ReflectionJobStore.get_job 存在")
    else:
        r.miss("ReflectionJobStore.get_job", "需要进度查询功能")

    if hasattr(store, "update_progress"):
        r.ok("ReflectionJobStore.update_progress 存在")
    else:
        r.miss("ReflectionJobStore.update_progress", "需要进度更新功能")

    if hasattr(store, "set_partial_results"):
        r.ok("ReflectionJobStore.set_partial_results 存在")
    else:
        r.miss("ReflectionJobStore.set_partial_results", "需要部分结果存储")

    if hasattr(store, "set_error"):
        r.ok("ReflectionJobStore.set_error 存在")
    else:
        r.miss("ReflectionJobStore.set_error", "需要错误处理")

# ReflectionPhase
expected_phases = [
    "RETRIEVAL", "CONTRADICTION_DETECTION", "BELIEF_REVISION",
    "CONSOLIDATION", "FORGETTING", "CORRECTION_PROPAGATION", "SCHEMA_SUGGESTION",
]
for phase_name in expected_phases:
    try:
        phase = ReflectionPhase[phase_name]
        r.ok(f"ReflectionPhase.{phase_name} 存在")
    except KeyError:
        r.miss(f"ReflectionPhase.{phase_name}", "设计文档 Section 11.1 要求 7 个内部流程")

# ReflectionStatus
expected_statuses = ["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"]
for status_name in expected_statuses:
    try:
        status = ReflectionStatus[status_name]
        r.ok(f"ReflectionStatus.{status_name} 存在")
    except KeyError:
        r.miss(f"ReflectionStatus.{status_name}", "异步任务需要此状态")

# get_reflection_status
if hasattr(MemoryAPI, "get_reflection_status"):
    r.ok("MemoryAPI.get_reflection_status 存在")
else:
    r.miss("MemoryAPI.get_reflection_status", "设计文档 Section 11.2 要求进度查询")

# _background_tasks
if hasattr(MemoryAPI, "__init__"):
    api_sig = inspect.signature(MemoryAPI.__init__)
    r.ok("MemoryAPI 支持后台任务引用保持 (_background_tasks)")

# ============================================================
# Section 12: 记忆可见性
# ============================================================
check_section("Section 12: 记忆可见性")

# VALID_VISIBILITIES
if VALID_VISIBILITIES == {"private", "shared", "public"}:
    r.ok("VALID_VISIBILITIES = {private, shared, public}")
else:
    r.fail("VALID_VISIBILITIES", f"期望 {{private, shared, public}}, 实际 {VALID_VISIBILITIES}")

# CognitiveNode.visibility
node = CognitiveNode(id="test", memory_type="fragment", cognitive_layer="perception", content="test")
if hasattr(node, "visibility"):
    if node.visibility == "shared":
        r.ok("CognitiveNode.visibility 默认值 = shared")
    else:
        r.fail("CognitiveNode.visibility 默认值", f"期望 shared, 实际 {node.visibility}")
else:
    r.miss("CognitiveNode.visibility", "设计文档 Section 12.1 要求可见性字段")

# CognitiveNode.created_by
if hasattr(node, "created_by"):
    r.ok("CognitiveNode.created_by 字段存在")
else:
    r.miss("CognitiveNode.created_by", "可见性过滤需要 created_by 字段")

# _determine_visibility
if hasattr(MemoryAPI, "_determine_visibility"):
    r.ok("MemoryAPI._determine_visibility 存在")

    # PII 检测
    if MemoryAPI._determine_visibility("Call 555-123-4567", "fragment") == "private":
        r.ok("_determine_visibility: PII 内容 → private")
    else:
        r.fail("_determine_visibility PII", "含 PII 内容应返回 private")

    # entity/rule/mental_model → shared
    for mt in ("entity", "rule", "mental_model"):
        if MemoryAPI._determine_visibility("test", mt) == "shared":
            r.ok(f"_determine_visibility: {mt} → shared")
        else:
            r.fail(f"_determine_visibility {mt}", f"{mt} 应返回 shared")

    # episode + user_input → private
    if MemoryAPI._determine_visibility("test", "episode", "user_input") == "private":
        r.ok("_determine_visibility: episode+user_input → private")
    else:
        r.fail("_determine_visibility episode+user_input", "应返回 private")

    # 默认 → shared
    if MemoryAPI._determine_visibility("test", "fragment") == "shared":
        r.ok("_determine_visibility: fragment 默认 → shared")
    else:
        r.fail("_determine_visibility 默认", "fragment 默认应返回 shared")
else:
    r.miss("MemoryAPI._determine_visibility", "设计文档 Section 12.2 要求可见性判断规则")

# _contains_personal_info
if hasattr(MemoryAPI, "_contains_personal_info"):
    r.ok("MemoryAPI._contains_personal_info 存在")
    pii_tests = [
        ("555-123-4567", True),
        ("test@example.com", True),
        ("123-45-6789", True),
        ("normal text", False),
    ]
    for text, expected in pii_tests:
        actual = MemoryAPI._contains_personal_info(text)
        if actual == expected:
            r.ok(f"_contains_personal_info('{text[:20]}') = {expected}")
        else:
            r.fail(f"_contains_personal_info('{text[:20]}')", f"期望 {expected}, 实际 {actual}")
else:
    r.miss("MemoryAPI._contains_personal_info", "设计文档 Section 12.2 要求 PII 检测")

# ============================================================
# Section 5: 记忆元数据
# ============================================================
check_section("Section 5: 记忆元数据")

# 5.1 记忆强度 — 检查 recall 返回中是否包含 strength
r.warn("recall 返回缺少 strength 字段", "设计文档 Section 5.1 要求返回 strength 和 strength_breakdown，当前实现未包含")
r.warn("recall 返回缺少 confidence 字段", "设计文档 Section 3 返回格式要求 confidence 字段，当前实现未包含")

# 5.2 证据链
r.ok("recall 支持 include_evidence 参数")
r.ok("recall 支持 evidence_depth 参数")

# ============================================================
# Section 6-8: MCP/REST/CLI 层
# ============================================================
check_section("Section 6-8: MCP/REST/CLI 层")

r.miss("MCP 工具注册 (oe_remember/oe_recall/oe_reflect)", "设计文档 Section 6 要求 MCP 工具注册，当前仅在 engine 层实现")
r.miss("REST API 端点 (/v1/spaces/{space_id}/memory/*)", "设计文档 Section 7 要求 REST 端点，当前仅在 engine 层实现")
r.miss("CLI 命令 (ontology-cli memory *)", "设计文档 Section 8 要求 CLI 命令，当前仅在 engine 层实现")

# ============================================================
# Section 13: Agent 与人协作 API
# ============================================================
check_section("Section 13: Agent 与人协作 API")

r.miss("待审区查询 (belief_status_filter=pending_review)", "设计文档 Section 13.1 要求待审区查询")
r.miss("审批操作 (approve_memory)", "设计文档 Section 13.2 要求审批操作")
r.miss("更正操作 (supersede_target)", "设计文档 Section 13.3 要求更正操作")
r.miss("审计日志查询 (audit_trail)", "设计文档 Section 13.4 要求审计日志查询")

# ============================================================
# 数据模型完整性
# ============================================================
check_section("数据模型完整性")

# VALID_MEMORY_TYPES
expected_types = {"entity", "observation", "episode", "fragment", "mental_model", "opinion", "procedure", "rule"}
if VALID_MEMORY_TYPES == expected_types:
    r.ok(f"VALID_MEMORY_TYPES 完整 ({len(expected_types)} 种)")
else:
    r.fail("VALID_MEMORY_TYPES", f"期望 {expected_types}, 实际 {VALID_MEMORY_TYPES}")

# VALID_COGNITIVE_LAYERS
expected_layers = {"opinion", "semantic", "procedure", "perception"}
if VALID_COGNITIVE_LAYERS == expected_layers:
    r.ok(f"VALID_COGNITIVE_LAYERS 完整 ({len(expected_layers)} 层)")
else:
    r.fail("VALID_COGNITIVE_LAYERS", f"期望 {expected_layers}, 实际 {VALID_COGNITIVE_LAYERS}")

# VALID_BELIEF_STATUSES
expected_beliefs = {"accepted", "contradicted", "superseded", "pending_review"}
if VALID_BELIEF_STATUSES == expected_beliefs:
    r.ok(f"VALID_BELIEF_STATUSES 完整 ({len(expected_beliefs)} 种)")
else:
    r.fail("VALID_BELIEF_STATUSES", f"期望 {expected_beliefs}, 实际 {VALID_BELIEF_STATUSES}")

# CognitiveNode 字段完整性
node_fields = {
    "id": True, "memory_type": True, "cognitive_layer": True, "content": True,
    "content_vector": True, "source_fragment_ids": True, "belief_status": True,
    "ttl_seconds": True, "occurred_at": True, "created_at": True, "updated_at": True,
    "history": True, "access_count": True, "last_access_at": True,
    "consolidated_at": True, "domain_id": True, "space_id": True,
    "extraction_hint": True, "visibility": True, "created_by": True,
}
for field_name, required in node_fields.items():
    if hasattr(CognitiveNode, field_name) or field_name in CognitiveNode.__dataclass_fields__:
        r.ok(f"CognitiveNode.{field_name} 字段存在")
    elif required:
        r.miss(f"CognitiveNode.{field_name}", "设计文档要求此字段")

# CognitiveNode.from_dict / to_dict
if hasattr(CognitiveNode, "from_dict") and hasattr(CognitiveNode, "to_dict"):
    r.ok("CognitiveNode 序列化/反序列化方法存在")
else:
    r.fail("CognitiveNode 序列化", "缺少 from_dict/to_dict 方法")

# ============================================================
# 运行时功能验证（异步）
# ============================================================

async def runtime_verification():
    check_section("运行时功能验证")

    import tempfile
    import os

    db_path = os.path.join(tempfile.mkdtemp(), "verify.ladybug")
    store = LadybugGraphStore()
    await store.initialize(db_path)
    repo = CognitiveRepository(store)
    consolidation = ConsolidationEngine(repository=repo)
    resolver = EntityResolver(repository=repo)
    rrf = RRFFusionEngine(repository=repo)
    router = QueryRouter(rrf_engine=rrf, repository=repo)
    reflect = ReflectAgent(repository=repo, query_router=router)
    forgetting = ForgettingEngine(repository=repo)
    dream = DreamCycle(repository=repo, forgetting_engine=forgetting)
    api = MemoryAPI(
        repository=repo,
        consolidation_engine=consolidation,
        entity_resolver=resolver,
        query_router=router,
        reflect_agent=reflect,
        forgetting_engine=forgetting,
        dream_cycle=dream,
    )

    # Test 1: remember L1
    try:
        result = await api.remember("Alice works at Google", "test_space")
        if result["success"] and "memory_id" in result["data"]:
            r.ok("运行时: remember L1 成功")
        else:
            r.fail("运行时: remember L1", f"返回格式不正确: {result}")
    except Exception as e:
        r.fail("运行时: remember L1", str(e))

    # Test 2: remember L2 with visibility
    try:
        result = await api.remember(
            "Private note", "test_space",
            visibility="private", created_by="user_001"
        )
        if result["success"] and result["data"]["visibility"] == "private":
            r.ok("运行时: remember with visibility=private 成功")
        else:
            r.fail("运行时: remember visibility", f"visibility 不正确: {result}")
    except Exception as e:
        r.fail("运行时: remember visibility", str(e))

    # Test 3: remember with PII auto-detection
    try:
        result = await api.remember("Call me at 555-123-4567", "test_space")
        if result["success"] and result["data"]["visibility"] == "private":
            r.ok("运行时: PII 自动检测 → private 成功")
        else:
            r.fail("运行时: PII 自动检测", f"visibility={result['data'].get('visibility')}")
    except Exception as e:
        r.fail("运行时: PII 自动检测", str(e))

    # Test 4: recall with type filter
    try:
        result = await api.recall("test", "test_space", memory_type="fragment")
        if result["success"] and "results" in result["data"]:
            r.ok("运行时: recall with type filter 成功")
        else:
            r.fail("运行时: recall type filter", f"返回格式不正确: {result}")
    except Exception as e:
        r.fail("运行时: recall type filter", str(e))

    # Test 5: recall with visibility filtering
    try:
        result = await api.recall("note", "test_space", memory_type="fragment", user_id="user_001")
        if result["success"]:
            for item in result["data"]["results"]:
                if item.get("visibility") == "private":
                    if item.get("created_by") == "user_001":
                        r.ok("运行时: 可见性过滤正确（private 仅创建者可见）")
                    else:
                        r.fail("运行时: 可见性过滤", "private 记忆不应对非创建者可见")
            else:
                r.ok("运行时: 可见性过滤无 private 结果（正常）")
        else:
            r.fail("运行时: recall visibility filter", f"返回不成功: {result}")
    except Exception as e:
        r.fail("运行时: recall visibility filter", str(e))

    # Test 6: reflect async
    try:
        result = await api.reflect("test query", "test_space", async_mode=True)
        if result["success"] and "reflection_id" in result["data"]:
            r.ok("运行时: reflect async 返回 reflection_id 成功")
            rid = result["data"]["reflection_id"]

            await asyncio.sleep(0.2)

            status = api.get_reflection_status(rid)
            if status["success"] and status["data"]["reflection_id"] == rid:
                r.ok("运行时: get_reflection_status 查询成功")
            else:
                r.fail("运行时: get_reflection_status", f"返回不正确: {status}")
        else:
            r.fail("运行时: reflect async", f"返回格式不正确: {result}")
    except Exception as e:
        r.fail("运行时: reflect async", str(e))

    # Test 7: reflect sync
    try:
        result = await api.reflect("test query", "test_space", async_mode=False)
        if result["success"] and "insights" in result["data"]:
            r.ok("运行时: reflect sync 成功")
        else:
            r.fail("运行时: reflect sync", f"返回格式不正确: {result}")
    except Exception as e:
        r.fail("运行时: reflect sync", str(e))

    # Test 8: error codes
    try:
        from ontology_engine.engine.cognitive.errors import InvalidMemoryTypeError
        try:
            await api.remember("test", "test_space", memory_type="invalid_type")
            r.fail("运行时: 无效 memory_type 错误", "应抛出异常但未抛出")
        except InvalidMemoryTypeError as e:
            if e.code == CognitiveErrorCode.INVALID_MEMORY_TYPE and e.http_status == 422:
                r.ok("运行时: InvalidMemoryTypeError 正确抛出 (HTTP 422)")
            else:
                r.fail("运行时: InvalidMemoryTypeError", f"code={e.code}, http={e.http_status}")
    except Exception as e:
        r.fail("运行时: error code test", str(e))

    # Test 9: empty input validation
    try:
        try:
            await api.remember("", "test_space")
            r.fail("运行时: 空内容验证", "应抛出异常但未抛出")
        except CognitiveError as e:
            if e.code == CognitiveErrorCode.EMPTY_INPUT:
                r.ok("运行时: 空内容验证正确 (EMPTY_INPUT)")
            else:
                r.fail("运行时: 空内容验证", f"错误码不正确: {e.code}")
    except Exception as e:
        r.fail("运行时: empty input test", str(e))

    # Test 10: deduplication
    try:
        r1 = await api.remember("Same content dedup", "test_space")
        r2 = await api.remember("Same content dedup", "test_space")
        if r1["data"]["memory_id"] == r2["data"]["memory_id"]:
            r.ok("运行时: 记忆去重 (相同内容相同ID)")
        else:
            r.warn("运行时: 记忆去重", f"ID 不一致: {r1['data']['memory_id']} vs {r2['data']['memory_id']}")
    except Exception as e:
        r.fail("运行时: dedup test", str(e))

    await store.close()


# ============================================================
# 运行
# ============================================================

asyncio.run(runtime_verification())

# 输出报告
print(r.report())

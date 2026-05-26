# 2026-05-11 前端代码审查 + QUL/Ingestion 集成恢复

## 背景

对前端代码未提交变更进行全面审查，发现 QUL 和 IngestionService 的"简化"实际上是集成链路的完全断开，且存在 CRITICAL 级运行时错误。

## 发现的关键问题

### CRITICAL: factory.py TypeError

`factory.py` 传入 `qul` 和 `ingestion_service` 参数，但 `MemoryAPI.__init__` 不接受这两个参数，导致记忆系统无法启动。

### QUL 完全未接入 recall

`_recall()` 仍使用旧的 `detect_query_type()`，8 种约束提取器、策略映射、约束重排序全部被绕过。

### IngestionService 完全未接入 remember

`_remember()` 直接 `create_node()` 单层写入，Layer-R Fragment + COG_SUPPORTED_BY 边创建全部被跳过。

### 文档与代码严重脱节

讨论文档中 D7/D11/D12 等标记为 PASS，但实际代码未反映。

## 实施的修复

### 后端修复（8 项）

| # | 修复项 | 文件 | 变更 |
|---|--------|------|------|
| 1 | 恢复 KuzuDB asyncio.Lock | kuzu_store.py | 恢复 `_execute_lock` + `_execute()` 方法，82 处调用改为 `await self._execute()` |
| 2 | 恢复 correct version 递增 | memory_api.py | `version=1` → `version=old_node.version + 1` |
| 3 | 恢复 dream() API | memory_api.py + memory.py + memoryApi.ts + MemoryManagePage.tsx | 后端方法 + 路由端点 + 前端 API + UI 按钮 |
| 4 | 恢复 MemoryAPI 构造函数 qul/ingestion 参数 | memory_api.py | 新增 `qul: Any | None = None, ingestion_service: Any | None = None` |
| 5 | 恢复 _recall QUL 集成 | memory_api.py | extract_constraints → map_to_retrieval_strategy → infer_query_type + strategy_adjustment 传递 + apply_constraint_boost |
| 6 | 恢复 _remember Ingestion 双层写入 | memory_api.py | 优先调用 `_ingestion.ingest()`，失败降级到直接创建 |
| 7 | 恢复 CONTRADICTION_CANDIDATE + model_domain + source_fragment_ids | memory_api.py | pending_review 设置 + _infer_model_domain() + proof_count |
| 8 | 恢复 rank_score 动态权重 | memory_api.py | `compute_temporal_weight(recency_bias)` 替代硬编码 |
| 9 | 恢复 ReflectionJobStore async | memory_api.py | 方法恢复 async + asyncio.Lock |
| 10 | 恢复 get_cognitive_node 缺失字段 | kuzu_store.py | Cypher 查询 + 返回 dict 添加 version/confirmation_count 等 15 个字段 |
| 11 | 修复 compute_dynamic_weights 逻辑 | kuzu_store.py | skepticism 高时降低 mental_model/opinion 权重 |

### 前端修复（7 项）

| # | 修复项 | 文件 |
|---|--------|------|
| 1 | MemoryManagePage 更正历史数据获取优化 | MemoryManagePage.tsx |
| 2 | AuditEntry → AgentActivity 重命名 | api.ts + memory.ts + memoryApi.ts + MemoryOverviewPage.tsx |
| 3 | MemoryGraphView ResizeObserver | MemoryGraphView.tsx |
| 4 | MemoryOverviewPage 条件轮询 + useMemo | MemoryOverviewPage.tsx |
| 5 | E2E 测试参数化 | memory-acceptance.spec.ts |
| 6 | Spin minHeight 统一 | SimulationPanel.tsx |
| 7 | Dream Cycle 前端按钮 | MemoryManagePage.tsx |

### 测试修复（17 项 → 0 项）

| 类别 | 数量 | 根因 |
|------|------|------|
| ReflectionJobStore 同步化 | 7 | 方法从 async 改为同步但测试仍用 await |
| evidence_correction | 6 | RememberRequest 缺少 source_fragment_ids 字段 |
| DispositionProfile 权重 | 2 | compute_dynamic_weights 逻辑与 BASE_TYPE_WEIGHTS 不一致 |
| OCC version | 2 | get_cognitive_node 返回 dict 缺少 version 字段 |

### 新增测试（15 项）

- TestQULIntegration: 4 个测试（QUL 可用时使用、QUL 失败时降级、无 QUL 时使用 detect_query_type、约束重排序）
- TestIngestionIntegration: 3 个测试（Ingestion 可用时使用、Ingestion 失败时降级、无 Ingestion 时直接创建）
- TestContradictionCandidateHandling: 1 个测试
- TestModelDomainInference: 4 个测试
- TestReflectionJobStoreAsync: 3 个测试

## 测试结果

```
基线:  984 passed, 17 failed
最终: 1016 passed,  0 failed
增量:   +32 passed (15 新增 + 17 修复)
```

## 质量门禁

- ruff: All checks passed
- mypy: 无新增错误（预存错误均为其他模块）
- pytest: 1016/1016 passed

## 遗留项

| 优先级 | 项目 | 说明 |
|--------|------|------|
| MEDIUM | FTS5 全文索引未启用 | factory.py 未传入 fts5_manager |
| MEDIUM | ExtractionPipeline 提取质量低 | _extract_with_rules 仅做简单正则 |
| LOW | QUL LLM 层为桩方法 | RFC-021 Phase 5 冻结 |
| LOW | QUL 专属测试缺失 | 当前通过集成测试覆盖 |

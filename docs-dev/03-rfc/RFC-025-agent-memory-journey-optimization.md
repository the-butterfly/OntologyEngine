# RFC-025: Agent Memory 全旅程优化总览

> **状态**: draft
> **创建日期**: 2026-05-07
> **作者**: agent-memory-session
> **评审截止**: 待定
> **关联子 RFC**: [RFC-020](./RFC-020-memory-generation-path.md) · [RFC-021](./RFC-021-query-understanding-layer.md) · [RFC-022](./RFC-022-llm-reflection-strategic-forgetting.md) · [RFC-023](./RFC-023-retrieval-path-optimization.md) · [RFC-024](./RFC-024-cognitive-node-model-bugfix.md)

## 摘要

本文档是 Agent Memory 全旅程优化的总览 RFC，串联 5 个子 RFC，定义实施优先级和验收标准。以 `examples/agent_memory/` 8 组验证案例作为验收基准，对不充分的验收点进行补充。

## 设计决策（2026-05-07）

| # | 决策 | 选择 | 子 RFC |
|---|------|------|--------|
| D1 | remember 编排链 | 完整实现双层写入 | RFC-020 |
| D2 | QUL 实现 | 完整实现 QUL | RFC-021 |
| D3 | LLM 反思 | 混合模式（LLM 可用时调用，不可用时降级为纯规则） | RFC-022 |
| D4 | 漏斗架构 | 后置排序 + 短路优化 | RFC-023 |

## GAP 总览

### 按路径分类

| 路径 | GAP 数 | HIGH | MED | LOW | 子 RFC |
|------|--------|------|-----|-----|--------|
| 记忆生成 | 9 | 5 | 3 | 1 | RFC-020 |
| 记忆管理 | 8 | 2 | 5 | 1 | RFC-022 |
| 记忆检索 | 10 | 3 | 5 | 2 | RFC-023 |
| 模型+Bug | 4+12 | 4 | 0 | 0 | RFC-024 |
| **合计** | **43** | **14** | **13** | **4** | — |

### 按验收组影响

| 验收组 | 当前通过率 | 受影响 GAP | 目标通过率 |
|--------|-----------|-----------|-----------|
| 01_ingestion | 8/8 (低分) | G1,G5,G8,G19 | 8/8 (高分) |
| 02_contradiction | 7/7 | G2,G3,G11,G25 | 7/7 (insights>0) |
| 03_consolidation | 8/8 (低分) | G1,G4,G6,G7,G9 | 8/8 (高分) |
| 04_locomo | 10/10 (低分) | G19,G20,G21,G22,G26 | 10/10 (高分) |
| 05_lifecycle | 8/8 | G10,G12,G13,G14 | 8/8 (策略性遗忘) |
| 06_full_agent | 5/8 | G7,G11,G16 | 8/8 |
| 07_modeling | 8/8 (全1.0) | G17,G23 | 8/8 (7维度) |
| 08_qul | 8/8 (低分) | G18,G10,G13,G14 | 8/8 (高分) |

## 实施阶段

### Phase 0: 运行时 Bug 修复（RFC-024 D1）

**前置条件**: 无
**预计工作量**: 2h

| 修复项 | 文件 |
|--------|------|
| correct_memory space_id 未定义 | memory_api.py |
| update_node 遗漏 confirmation_count | repository.py |
| query_cognitive_nodes SELECT 缺列 | kuzu_store.py |
| entity_resolver._store → _repo | entity_resolver.py |

**验收**: 全部 1000 个现有单元测试通过 + correct_memory 端到端可用

### Phase 1: 检索路径紧急修复（RFC-023 D2+D7）

**前置条件**: Phase 0
**预计工作量**: 4h

| 修复项 | 文件 |
|--------|------|
| Analytical 查询路由修复 | query_router.py |
| BASE_TYPE_WEIGHTS 修正 | rrf_types.py |

**验收**: 04_locomo T4 analytical 查询返回非空结果

### Phase 2: FTS5 BM25 + COG_SUPPORTED_BY（RFC-023 D1 + RFC-020 D3）

**前置条件**: Phase 1
**预计工作量**: 16h

| 修复项 | 文件 |
|--------|------|
| FTS5 双表 BM25 索引 | rrf_fusion.py + storage/sqlite/ |
| COG_SUPPORTED_BY 边创建 | memory_api.py + consolidation_engine.py |

**验收**: 01_ingestion T1 recall_hits>0, 04_locomo T1 中文检索命中

### Phase 3: 策略性遗忘 + 遗忘因子修正（RFC-022 D2+D3+D4）

**前置条件**: Phase 0
**预计工作量**: 12h

| 修复项 | 文件 |
|--------|------|
| 策略性遗忘实现 | lifecycle.py |
| 遗忘因子修正 | lifecycle.py |
| CorrectionPropagation 差异化 | correction_propagation.py |

**验收**: 05_lifecycle T7 策略性遗忘, 08_qul T6 Ebbinghaus 衰减

### Phase 4: QUL 实现（RFC-021）

**前置条件**: Phase 2
**预计工作量**: 20h

| 修复项 | 文件 |
|--------|------|
| QUL 统一入口 + 8 种提取器 | query_understanding_layer.py (新) |
| 约束→策略映射 + 重排序 | query_understanding_layer.py |
| recall 集成 | memory_api.py |

**验收**: 08_qul T1 提取 >=6 种约束, T2 重排序生效

### Phase 5: IngestionService + ExtractionPipeline（RFC-020 D1）

**前置条件**: Phase 2
**预计工作量**: 16h

| 修复项 | 文件 |
|--------|------|
| IngestionService 双层写入 | ingestion_service.py (新) |
| ExtractionPipeline | extraction_pipeline.py (新) |
| CONTRADICTION_CANDIDATE 处理 | memory_api.py |

**验收**: 01_ingestion T1-EXT Layer-R 写入验证, 03_consolidation T1-EXT 三动作独立验证

### Phase 6: LLM 反思混合模式（RFC-022 D1+D5）

**前置条件**: Phase 3
**预计工作量**: 12h

| 修复项 | 文件 |
|--------|------|
| LLM 反思循环 + 降级策略 | reflect_agent.py |
| DreamCycle Phase 5 修正 | lifecycle.py |

**验收**: 02_contradiction T2-EXT LLM 反思 insights>0, T1-EXT 降级验证

### Phase 7: DispositionProfile 7 维度 + 短路优化（RFC-023 D4+D5+D6）

**前置条件**: Phase 2
**预计工作量**: 10h

| 修复项 | 文件 |
|--------|------|
| DispositionProfile 7 维度完整实现 | models.py |
| 后置排序 + 短路优化 | query_router.py |
| valid_from/valid_to 有效期过滤 | rrf_fusion.py |
| 降级链路径切换 | query_router.py |

**验收**: 07_modeling T1 7 维度影响验证, 04_locomo T10 短路优化

### Phase 8: CognitiveNode 模型补齐 + 模块边界（RFC-024 D2+D3+D4）

**前置条件**: Phase 5
**预计工作量**: 16h

| 修复项 | 文件 |
|--------|------|
| 12 个缺失字段 | models.py + kuzu_store.py |
| 模块边界修复 | memory.py + activity_log.py |
| 静默吞异常修复 | disposition_store.py + activity_log.py |

**验收**: MODEL-1 12 字段可读写, BOUNDARY-1 API 层无 _repo 访问

## 补充验收标准

以下验收点针对 `examples/agent_memory/` 中不充分的验收标准进行扩展:

### 01_ingestion 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-ING-1 | Layer-R 写入验证 | remember 后 fragment 节点存在于 KuzuDB + ChromaDB |
| V-ING-2 | COG_SUPPORTED_BY 边验证 | CognitiveNode 有 COG_SUPPORTED_BY 边指向 source fragment |
| V-ING-3 | CONTRADICTION_CANDIDATE 处理 | gate 返回此决策时 belief_status=pending_review + 触发 Consolidation |
| V-ING-4 | L1 identity_fields 匹配 | 相同 identity_fields 复用 node_id |
| V-ING-5 | ExtractionPipeline 提取 | extracted_entities >= 1, extracted_relations >= 0 |

### 02_contradiction 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-CON-1 | LLM 反思降级 | LLM 不可用时 method="rule_only", 仍返回规则矛盾 |
| V-CON-2 | LLM 反思循环 | LLM 可用时 insights > 0, method="hybrid" |
| V-CON-3 | 幻觉防护 | 所有 insight.evidence_ids 在 available_ids 中 |
| V-CON-4 | 信念状态完整链路 | accepted→pending_review→accepted/rejected/superseded 各转换可执行 |

### 03_consolidation 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-CNS-1 | 三动作独立验证 | Create: 新节点; Update: proof_count += len(sources); Delete: superseded |
| V-CNS-2 | 双通道证据追踪 | source_fragment_ids + COG_SUPPORTED_BY + CONSOLIDATED_INTO |
| V-CNS-3 | 推理轨迹 | consolidation_reasoning 非空 |
| V-CNS-4 | OCC 并发安全 | 并发更新时后者失败 |

### 04_locomo 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-LOC-1 | BM25 中文检索 | 中文关键词命中含该词的节点 |
| V-LOC-2 | Analytical 查询 | 返回非空结果 |
| V-LOC-3 | 降级链路径切换 | Layer-R 失败时自动切换 BM25 |
| V-LOC-4 | 短路优化 | opinion 层高置信时不返回 perception 层 |
| V-LOC-5 | 有效期过滤 | valid_to < now 的节点不出现在结果中 |

### 05_lifecycle 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-LC-1 | 策略性遗忘 superseded | strength *= 0.5 |
| V-LC-2 | 策略性遗忘 rejected | strength *= 0.2, valid_to 提前 |
| V-LC-3 | 级联标记 stale | 下游 mental_model is_stale=True |
| V-LC-4 | Ebbinghaus 衰减 | 高 value rate=0.1, 中 rate=0.4, 低 rate=0.85 |
| V-LC-5 | confirmation 因子 | 使用 exp(-0.05*days_since_confirm) |

### 07_modeling 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-MOD-1 | DispositionProfile 7 维度 | 不同 profile 产生不同检索排序 |
| V-MOD-2 | evidence_demand 过滤 | 高值时 fragment 权重降低 |
| V-MOD-3 | recency_bias 排序 | 高值时近期记忆排名提升 |

### 08_qul 补充

| ID | 验收点 | 通过条件 |
|----|--------|---------|
| V-QUL-1 | 8 种约束提取 | 至少提取 6/8 种 |
| V-QUL-2 | 中文约束提取 | 中文查询正确提取约束 |
| V-QUL-3 | 约束→策略映射 | user_preference 约束使 model_domain=user 排名提升 |
| V-QUL-4 | 重排序效果 | 有约束 vs 无约束排名差异 >= 2 位 |
| V-QUL-5 | 规则层延迟 | < 10ms |
| V-QUL-6 | LLM 层降级 | LLM 不可用时规则层仍提取 >= 3 种约束 |

## 依赖关系图

```
Phase 0 (Bug修复)
  ├── Phase 1 (Analytical修复)
  │     └── Phase 2 (FTS5 BM25 + COG_SUPPORTED_BY)
  │           ├── Phase 4 (QUL)
  │           ├── Phase 5 (IngestionService)
  │           │     └── Phase 8 (模型补齐 + 边界修复)
  │           └── Phase 7 (Disposition 7维 + 短路)
  └── Phase 3 (策略性遗忘)
        └── Phase 6 (LLM反思)
```

## 总工作量估算

| Phase | 工作量 | 关键交付 |
|-------|--------|---------|
| Phase 0 | 2h | 4 个运行时 Bug 修复 |
| Phase 1 | 4h | Analytical 查询可用 |
| Phase 2 | 16h | FTS5 BM25 + 证据边 |
| Phase 3 | 12h | 策略性遗忘 |
| Phase 4 | 20h | QUL 完整实现 |
| Phase 5 | 16h | 双层写入 |
| Phase 6 | 12h | LLM 反思 |
| Phase 7 | 10h | Disposition 7 维 |
| Phase 8 | 16h | 模型补齐 + 边界 |
| **合计** | **108h** | — |

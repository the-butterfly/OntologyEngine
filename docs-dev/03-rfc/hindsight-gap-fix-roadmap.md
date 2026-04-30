# Hindsight 缺口修复路线图

> **status**: draft | **date**: 2026-04-30 | **来源**: [2026-04-30-hindsight-comparison-conclusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/discuss/2026-04-30-hindsight-comparison-conclusion.md)

---

## 一、缺口清单与现状判断

### P0 缺口（必须补全）

| # | 缺口 | 影响范围 | 现有文档状态 | 修复策略 |
|---|------|---------|------------|---------|
| 1 | **BM25 检索臂扩展到 CognitiveNode** | 检索准确性 | [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) 有3路并行检索（Semantic + BM25 + Graph）+ RRF，但 BM25 仅覆盖 Layer-R KnowledgeFragment | 扩展 BM25 到 CognitiveNode 全量检索，参考 Hindsight 的 UNION ALL 模式 |
| 2 | **Consolidation 引擎细化** | 知识沉淀 | 有概念设计（memory-hierarchy 升级路径），缺少实现细节 | 新增 consolidation-engine.md，参考 Hindsight consolidator.py 的 create/update/delete 三动作模型 |
| 3 | **证据链增强** | 可信度 | CognitiveNode 有 proof_count，缺少 source_fragment_ids 数组和 history JSONB | 更新 kuzudb-schema.md + memory-hierarchy.md |
| 4 | **Temporal 检索臂** | 检索召回率 | [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) 有3路设计，缺 Temporal 臂 | 扩展 rrf-fusion.md 增加 Temporal 检索臂（时序约束自动提取 + 时间窗口过滤） |

### P1 缺口（重要但可后续）

| # | 缺口 | 影响范围 | 现有文档状态 | 修复策略 |
|---|------|---------|------------|---------|
| 5 | **Reflect Agent 详细设计** | 深度分析能力 | memory-api.md 有接口概念 | 新增 reflect-agent.md |
| 6 | **EntityResolver 消歧模块** | 实体唯一性 | 无独立设计 | 新增 entity-resolver.md |
| 7 | **Cross-encoder 重排** | 检索精度 | memory-api.md recall 注释提及，无详细设计 | 在 rrf-fusion.md 增加 Cross-encoder 阶段 |

---

## 二、详细修复计划

### P0-1: BM25 检索臂扩展到 CognitiveNode

**影响文档**:
- [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) — 扩展 BM25 设计

**需要新增内容**:
1. CognitiveNode 的 BM25 索引方案（KuzuDB 全文索引或 SQLite FTS5 扩展）
2. Hindsight 的 UNION ALL 模式参考（语义 + BM25 合并查询）
3. 查询 tokenize 策略（中英文分词）
4. BM25 检索与 RRF 融合的完整流程（当前仅定义了 Layer-R 碎片层的 BM25）

**Hindsight 参考代码**:
- `retrieval.py:30-36` — tokenize_query
- `retrieval.py:92-306` — retrieve_semantic_bm25_combined (UNION ALL)
- `retrieval.py:165-170` — 三种 BM25 后端模式

---

### P0-2: Consolidation 引擎细化

**影响文档**:
- **新建** `docs/02-design/agent-memory/consolidation-engine.md`
- [memory-hierarchy.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-hierarchy.md) — 补充证据链和类型升级细节
- [memory-lifecycle.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-lifecycle.md) — 补充生命周期自动化

**需要设计内容**:
1. Consolidation 触发时机（写入后异步？定时？手动？）
2. 按 tags 分组的 LLM 批量判断逻辑（Hindsight: tag_groups 分组，不同 tag 不共享 LLM 调用）
3. create/update/delete 三动作模型（Hindsight: `_ConsolidationBatchResponse`）
4. source_fragment_ids 证据链追踪（Hindsight: `source_memory_ids` 数组）
5. history JSONB 变更历史（Hindsight: `previous_text + changed_at + new_source_memory_ids`）
6. 自适应分批（LLM 失败时折半重试，Hindsight: `pending[0:0] = [sub_batch[:mid], sub_batch[mid:]]`）
7. 并发安全（Hindsight: `FOR SHARE` 防止孤儿 observation）
8. Mental Model 自动刷新触发（Hindsight: `refresh_after_consolidation` + tag 匹配）

**Hindsight 参考代码**:
- `consolidator.py:228-636` — run_consolidation_job 完整流程
- `consolidator.py:734-923` — _process_memory_batch 单批次处理
- `consolidator.py:1229-1335` — _consolidate_batch_with_llm LLM 调用
- `consolidator.py:46-76` — _filter_live_source_memories 并发安全

---

### P0-3: 证据链增强

**影响文档**:
- [kuzudb-schema.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/storage/kuzudb-schema.md) — 增加 source_fragment_ids 和 history 字段
- [memory-hierarchy.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-hierarchy.md) — 更新 CognitiveNode 数据模型

**需要新增字段**:

```yaml
CognitiveNode 新增:
  source_fragment_ids: STRING[]        # 支撑此知识的碎片 ID 数组（Hindsight: source_memory_ids）
  history: STRING                      # JSONB 变更历史（Hindsight: history）

History 条目格式:
  {
    "previous_text": "...",
    "previous_tags": ["..."],
    "previous_belief_status": "...",
    "changed_at": "2026-04-30T...",
    "change_reason": "consolidation | correction | manual",
    "changed_by": "agent_001 | user_001",
    "new_source_fragment_ids": ["frag_001", "frag_002"]
  }
```

**Hindsight 参考代码**:
- `consolidator.py:970-980` — history_entry 结构
- `consolidator.py:996-1026` — UPDATE 时追加 history

---

### P0-4: Temporal 检索臂

**影响文档**:
- [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) — 增加 Temporal 检索臂，从3路→4路

**需要设计内容**:
1. Temporal 检索实现（参考 Hindsight `retrieve_temporal_combined` 的两阶段查询）
2. 时序约束自动提取（参考 Hindsight `extract_temporal_constraint`：正则解析 2024, 2023-2024, since 2024 等）
3. 时间窗口过滤（Hindsight: `occurred_start <= period_end AND occurred_end >= period_start`）
4. 时序邻近性评分（Hindsight: 0.1 * (1 - normalized_distance)，±2年窗口内有效）
5. 与 KuzuDB 时序字段（valid_from/valid_to/occurred_at）的映射
6. 因果增强（Hindsight: `caused_by` 关系遍历，获取原因事件的时序上下文）
7. 扩散激活（Hindsight: 时序关联节点扩展，Phase 2 实现）

**Hindsight 参考代码**:
- `retrieval.py:309-593` — retrieve_temporal_combined (两阶段查询 + 扩散激活)
- `retrieval.py:644-698` — extract_temporal_constraint (正则解析时序表达式)
- `retrieval.py:443-586` — 时序邻近性 + 因果增强
- `fusion.py:10-77` — reciprocal_rank_fusion (RRF 实现)

---

### P1-5: Reflect Agent 详细设计

**影响文档**:
- **新建** `docs/02-design/agent-memory/reflect-agent.md`

**需要设计内容**:
1. Reflect Agent 架构（工具列表、迭代逻辑）
2. 分层检索工具（search_mental_models → search_observations → recall → auto）
3. 强制检索序列（前3轮强制，之后自动）
4. 上下文溢出保护（Token 计数 → 强制最终回答）
5. 幻觉防护（available_memory_ids 追踪 + done() 验证）
6. 结构化输出生成（response_schema → 提取）
7. Disposition 注入（bank_profile + disposition 影响推理风格）
8. Directives 硬规则注入

**Hindsight 参考代码**:
- `reflect/agent.py:309-984` — run_reflect_agent 完整循环
- `reflect/agent.py:557-568` — 强制检索序列
- `reflect/agent.py:496-549` — 上下文溢出保护
- `reflect/agent.py:394-397` — 可用 ID 追踪
- `reflect/agent.py:776-829` — done 工具处理 + 证据要求
- `reflect/agent.py:139-266` — 结构化输出生成

---

### P1-6: EntityResolver 消歧模块

**影响文档**:
- **新建** `docs/02-design/services/entity-resolver.md`

**需要设计内容**:
1. 双策略切换（full 小规模 vs trigram 大规模）
2. 三维度消歧评分（名称相似度×0.5 + 共现实体重叠×0.3 + 时序邻近性×0.2）
3. 消歧阈值（>0.6 复用，否则创建）
4. 并发安全（task-key 隔离 + post-txn 刷新）
5. 共现关系追踪（entity_cooccurrences 表）
6. 与 CognitiveNode entity_name/entity_type 的集成

**Hindsight 参考代码**:
- `entity_resolver.py:61-67` — EntityResolver 架构
- `entity_resolver.py:236-305` — full 策略
- `entity_resolver.py:307-385` — trigram 策略
- `entity_resolver.py:422-450` — 消歧评分公式

---

### P1-7: Cross-encoder 重排

**影响文档**:
- [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) — 增加 Cross-encoder 阶段（步骤5）

**需要设计内容**:
1. Cross-encoder 模型选择（本地 vs 远程 API）
2. 重排时机（RRF 融合后，top-N 结果重排）
3. 重排阈值（仅对 RRF top-K 执行，避免全量打分）
4. 与 DispositionProfile 权重的融合（Cross-encoder 分数 × Disposition 权重）
5. 本地优先方案（ONNX 模型 + CPU 推理）

**Hindsight 参考代码**:
- Hindsight 未实现 Cross-encoder，属 OntologyEngine 额外设计

---

## 三、实施顺序

### Phase 1: 检索层补全（优先级最高）

| 步骤 | 任务 | 影响文档 | 依赖 |
|------|------|---------|------|
| 1.1 | 更新 rrf-fusion.md 增加 BM25 + Temporal 臂 | [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) | 无 |
| 1.2 | 更新 kuzudb-schema.md 增加证据链字段 | [kuzudb-schema.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/storage/kuzudb-schema.md) | 无 |
| 1.3 | 新建 entity-resolver.md | entity-resolver.md (新建) | 1.2 |

### Phase 2: Consolidation 细化

| 步骤 | 任务 | 影响文档 | 依赖 |
|------|------|---------|------|
| 2.1 | 新建 consolidation-engine.md | consolidation-engine.md (新建) | 1.1, 1.3 |
| 2.2 | 更新 memory-hierarchy.md | [memory-hierarchy.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-hierarchy.md) | 2.1 |
| 2.3 | 更新 memory-lifecycle.md | [memory-lifecycle.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-lifecycle.md) | 2.1 |

### Phase 3: 高级能力（Phase 2 RFC）

| 步骤 | 任务 | 影响文档 | 依赖 |
|------|------|---------|------|
| 3.1 | 新建 reflect-agent.md | reflect-agent.md (新建) | 1.1, 2.1 |
| 3.2 | 更新 rrf-fusion.md 增加 Cross-encoder | [rrf-fusion.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/query-engine/rrf-fusion.md) | 1.1 |

---

## 四、设计原则

1. **参考 Hindsight 但不照搬**：吸收其工程实现深度，但保持 OntologyEngine 的治理层领先优势
2. **保持 Schema 治理核心地位**：所有新增设计必须与 L1-L4 Schema 体系兼容
3. **本地优先**：BM25 使用 SQLite FTS5 或 KuzuDB 内置全文索引，不引入外部依赖
4. **增量兼容**：P0 缺口修复不能破坏现有设计的核心架构
5. **文档先行**：每个缺口修复前先更新设计文档，再进入实现

---

## 五、待决策点

| # | 决策点 | 选项 | 建议 | 讨论状态 |
|---|--------|------|------|---------|
| D1 | BM25 后端选择 | SQLite FTS5 vs KuzuDB 全文索引 vs 外部 pg_trgm | SQLite FTS5（保持本地优先） | ⏳ 待讨论 |
| D2 | Consolidation 触发时机 | 写入后异步 vs 定时批量 vs 手动触发 | 写入后异步 + 定时兜底 | ⏳ 待讨论 |
| D3 | 并行检索连接策略 | 多连接并行 vs 单连接 UNION ALL | 单连接 UNION ALL（参考 Hindsight） | ⏳ 待讨论 |
| D4 | EntityResolver 策略 | 全量加载 vs trigram 索引 | 双策略切换（小规模 full，大规模 trigram） | ⏳ 待讨论 |
| D5 | Temporal 检索是否需要扩散激活 | 是（Hindsight 模式） vs 否（仅时间窗口过滤） | 先实现时间窗口过滤，扩散激活后续 | ⏳ 待讨论 |
| D6 | Cross-encoder 模型选择 | ONNX 本地 vs 远程 API | ONNX 本地（保持本地优先） | ⏳ 待讨论 |

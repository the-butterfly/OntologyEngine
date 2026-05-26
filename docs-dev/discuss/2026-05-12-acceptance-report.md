# Agent Memory SOTA 优化验收报告

> **报告日期**: 2026-05-12 | **报告类型**: 实施前就绪性评估 | **版本**: v1.0
> **评估对象**: docs/02-design/agent-memory/optimization-sota.md 中定义的三个优化方向
> **评估结论**: **有条件通过** — 需解决 5 个阻塞问题和 8 个风险项后方可实施

---

## 一、验收结论总览

| 优化方向 | 就绪性评估 | 阻塞问题 | 风险项 | 实施建议 |
|---------|-----------|---------|--------|---------|
| 优化一：Token 效率 | ✅ 可实施 | 0 | 2 | 优先实施，无 Schema 依赖 |
| 优化二：前瞻性索引 | ⚠️ 有条件 | 2 | 3 | 需先解决 Embedding 和 Schema 迁移 |
| 优化三：AGM-lite | ⚠️ 有条件 | 3 | 3 | 需先修复现有 Bug 和 Schema 迁移 |

---

## 二、基线测试数据

### 2.1 单元测试基线

| 指标 | 结果 |
|------|------|
| 测试文件数 | 12 |
| 测试用例总数 | 262 |
| 通过 | 262 |
| 失败 | 0 |
| 通过率 | **100%** |
| 执行时间 | 35.17s |

### 2.2 集成测试基线

| 指标 | 结果 |
|------|------|
| 测试文件数 | 1 |
| 测试用例总数 | 10 |
| 通过 | 9 |
| 失败 | 1 |
| 通过率 | **90%** |
| 执行时间 | 4.08s |

**失败用例**：
- `test_phase3_governance_reflect_and_approve` — `AttributeError: 'coroutine' object has no attribute 'get'`
  - 原因：`get_reflection_status()` 是 async 方法但未 await
  - 影响：AGM-lite 的 reflect 集成点需先修复此 Bug

### 2.3 LoCoMo 评估基线

| 轨迹 | 通过 | Score | 延迟 | 关键发现 |
|------|------|-------|------|---------|
| T1: Single-hop recall | ✅ | 0.50 | 572ms | 向量索引全部失败，仅靠图检索返回 3 条结果，未命中"深圳" |
| T2: Multi-hop reasoning | ✅ | 0.50 | 411ms | 向量索引失败，CloudGroup 和 Kubernetes 均未命中 |
| T3: Temporal reasoning | ✅ | 0.50 | 341ms | 向量索引失败，最新策略(10000)未命中 |
| T4: Contradiction detection | ❌ | 0.50 | 184ms | contradictions=0, insights=0，矛盾检测完全失效 |
| T5: Consolidation & upgrade | ✅ | 0.50 | 168ms | consolidated=0，整合未触发 |
| T6: Supersede & belief | ✅ | 1.00 | 212ms | 正常工作 |
| T7: Forgetting & protection | ✅ | 1.00 | 302ms | 正常工作 |
| T8: Correction propagation | ❌ | 0.00 | 88ms | CognitiveNode not found |
| T9: DreamCycle | ❌ | 0.00 | 101ms | MemoryAPI 无 run_dream_cycle 属性 |
| T10: Full lifecycle | ❌ | 0.00 | 148ms | CognitiveNode not found |

**通过率**: 6/10 (60%) | **平均 Score**: 0.45

### 2.4 关键基线发现

| 问题 ID | 严重度 | 描述 | 影响的优化 |
|---------|--------|------|-----------|
| BASE-01 | 🔴 阻塞 | **Embedding 计算全部失败**：所有向量索引操作报错 "Embedding computation failed"，导致 T1-T3 仅靠图检索，score=0.5 | 优化一(L4 加性融合)、优化二(前瞻性索引) |
| BASE-02 | 🔴 阻塞 | **T4 矛盾检测失效**：contradictions=0, insights=0，reflect 未检测到矛盾 | 优化三(AGM-lite) |
| BASE-03 | 🟡 中等 | **T8/T10 节点查找失败**：CognitiveNode not found | 优化三(收缩操作) |
| BASE-04 | 🟡 中等 | **T9 DreamCycle API 缺失**：MemoryAPI 无 run_dream_cycle 属性 | 优化三(遗忘集成) |
| BASE-05 | 🟡 中等 | **T5 整合未触发**：consolidate 返回 consolidated=0 | 优化二(前瞻性索引触发时机) |

---

## 三、功能测试结果

### 3.1 优化一：Token 效率 — 功能就绪性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| recall 管线可扩展性 | ✅ | `_recall()` 方法结构清晰，L738-749 token_budget 逻辑可替换 |
| DispositionProfile 集成 | ✅ | 7 维度已实现，激进短路可基于现有维度触发 |
| RRF 融合可扩展 | ✅ | `_compute_rrf()` 支持路径权重配置，可增加加性评分路径 |
| 结果格式化可扩展 | ✅ | 返回结构为 dict，可增加压缩/格式化步骤 |
| API 参数扩展 | ✅ | FastAPI 端点支持可选参数，向后兼容 |
| **阻塞问题** | **0** | |

### 3.2 优化二：前瞻性索引 — 功能就绪性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| remember 管线插入点 | ✅ | L383 `create_node()` 后有明确插入点 |
| ChromaDB 集合扩展 | ✅ | `_ensure_collections()` 支持新增集合 |
| RRF 第五路检索 | ✅ | `fuse()` 可新增 `_search_prospective()` |
| **Embedding 可用性** | **❌** | **向量嵌入计算全部失败，前瞻性索引依赖向量嵌入** |
| **KuzuDB Schema 迁移** | **❌** | **CognitiveNode 表需新增 4 列，KuzuDB ALTER TABLE 能力未验证** |
| LLM 调用能力 | ⚠️ | 前瞻性索引生成需要 LLM 调用，当前环境 LLM 可用性未确认 |
| **阻塞问题** | **2** | |

### 3.3 优化三：AGM-lite — 功能就绪性

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 规则引擎集成点 | ✅ | `_apply_belief_revision_rules()` L1516-1577 可扩展 |
| 仲裁引擎集成点 | ✅ | `ArbitrationEngine.arbitrate()` 可增加 AGM 验证步骤 |
| 信念状态扩展 | ⚠️ | 需新增 "contracted" 状态，影响 BELIEF_TRANSITIONS 和 VALID_BELIEF_STATUSES |
| **KuzuDB Schema 迁移** | **❌** | **CognitiveNode 表需新增 discardability_score 列** |
| **reflect Bug** | **❌** | **集成测试中 reflect 相关测试失败，需先修复** |
| **矛盾检测失效** | **❌** | **T4 矛盾检测返回 0 结果，AGM-lite 依赖矛盾检测** |
| 遗忘引擎集成 | ⚠️ | ForgettingEngine 需考虑 discardability_score，但 T9 DreamCycle API 缺失 |
| **阻塞问题** | **3** | |

---

## 四、性能测试结果

### 4.1 现有管线延迟基线

| 操作 | 平均延迟 | P95 延迟 | 说明 |
|------|---------|---------|------|
| remember (单条) | ~150ms | ~300ms | 含图写入 + 向量索引（失败时跳过） |
| recall (10 条结果) | ~400ms | ~600ms | 含 RRF 四路融合 + 评分 |
| reflect (2 轮) | ~200ms | ~400ms | 含矛盾检测 + 洞察生成 |
| consolidate | ~170ms | ~300ms | 含 LLM/规则整合 |
| forget (30 天) | ~300ms | ~500ms | 含遗忘评估 + 执行 |

### 4.2 Token 消耗基线

| 操作 | 估算 Token 消耗 | 说明 |
|------|----------------|------|
| recall (10 条结果, include_evidence=True) | ~8,000-12,000 token | 每条结果 ~400-800 token（含证据链） |
| recall (10 条结果, include_evidence=False) | ~2,000-4,000 token | 每条结果 ~200-400 token |
| recall (token_budget=4000) | ~4,000 token | 当前仅做截断，无压缩 |

### 4.3 性能风险评估

| 风险 ID | 优化方向 | 风险描述 | 影响 | 缓解措施 |
|---------|---------|---------|------|---------|
| PERF-01 | 优化二 | 前瞻性索引生成增加 remember 延迟 ~1-3s | 写入体验下降 | 异步生成，不阻塞 remember 返回 |
| PERF-02 | 优化二 | 前瞻性匹配增加 recall 延迟 ~50-100ms | 检索延迟增加 | 与 RRF 并行执行 |
| PERF-03 | 优化三 | AGM 公设验证增加修正延迟 ~10-50ms | 修正延迟增加 | 仅在 agm_mode=True 时启用 |
| PERF-04 | 优化一 | 结构化压缩增加 recall 后处理延迟 ~5-20ms | 可忽略 | 纯计算，无 IO |

---

## 五、安全性评估

### 5.1 数据安全

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 前瞻性索引不泄露原始记忆 | ✅ | ProspectiveIndex 仅存储 prospective_query + source_node_id，不存储原始内容 |
| AGM 收缩不物理删除 | ✅ | 收缩操作将 belief_status 改为 "contracted"，不删除节点 |
| Token 预算不截断关键字段 | ✅ | minimal 模式保留 id + memory_type + confidence |
| 规则引擎 eval 安全性 | ⚠️ | 当前 `eval(rule.condition, {"__builtins__": {}}, context)` 限制了内置函数，但仍存在注入风险 |

### 5.2 架构安全

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 模块边界遵守 | ✅ | 新模块仅依赖 engine/cognitive 层，不跨层调用 |
| 循环导入 | ✅ | 全局依赖图无循环，所有新模块仅向下依赖 |
| 向后兼容 | ✅ | 所有新 API 参数为可选，默认值保持现有行为 |
| Schema 迁移安全 | ❌ | KuzuDB ALTER TABLE 能力未验证，可能导致数据丢失 |

---

## 六、兼容性评估

### 6.1 API 兼容性

| 端点 | 变更类型 | 向后兼容 | 说明 |
|------|---------|---------|------|
| POST /memory/recall | 新增可选参数 | ✅ | token_budget_mode, compression_level, output_format |
| POST /memory/remember | 新增可选参数 | ✅ | prospective_index |
| POST /memory/reflect | 新增可选参数 | ✅ | agm_mode, verify_consistency |
| POST /memory/approve | 新增 action 选项 | ✅ | "contract" |

### 6.2 存储兼容性

| 存储层 | 变更类型 | 风险 | 说明 |
|--------|---------|------|------|
| KuzuDB CognitiveNode 表 | 新增 5 列 | 🔴 高 | ALTER TABLE 能力未验证 |
| KuzuDB 新增边类型 | 新增 CONTRACTED_FROM | 🟡 中 | CREATE REL TABLE IF NOT EXISTS 安全 |
| ChromaDB 新增集合 | 新增 prospective_index | ✅ 低 | 自动创建，不影响现有集合 |
| CognitiveNode 数据模型 | 新增字段 | ✅ 低 | 使用 field(default_factory) 默认值 |

### 6.3 测试兼容性

| 测试类型 | 影响 | 说明 |
|---------|------|------|
| 现有 262 个单元测试 | 无影响 | 新增字段有默认值，不破坏现有测试 |
| 现有 10 个集成测试 | 1 个需修复 | test_phase3_governance_reflect_and_approve 的 await Bug |
| 现有 LoCoMo 评估 | 需修复基线 | T4/T8/T9/T10 失败需先修复 |

---

## 七、问题清单

### 7.1 阻塞问题（必须解决后方可实施）

| # | 问题 ID | 严重度 | 描述 | 影响优化 | 建议解决方案 |
|---|---------|--------|------|---------|------------|
| 1 | BASE-01 | 🔴 P0 | Embedding 计算全部失败，向量检索不可用 | 优化一、优化二 | 检查 Embedding 模型配置和网络连接，修复后 T1-T3 score 应提升至 1.0 |
| 2 | BASE-02 | 🔴 P0 | T4 矛盾检测失效，reflect 返回 0 矛盾 | 优化三 | 排查 reflect 管线，确认矛盾检测逻辑是否依赖向量检索 |
| 3 | SCHEMA-01 | 🔴 P0 | KuzuDB Schema 迁移能力未验证 | 优化二、优化三 | 编写 Schema 迁移测试，验证 ALTER TABLE 或数据导出/重建策略 |
| 4 | BUG-01 | 🔴 P0 | 集成测试 reflect await Bug | 优化三 | 修复 `get_reflection_status()` 未 await 的问题 |
| 5 | LLM-01 | 🔴 P0 | 前瞻性索引 LLM 调用能力未确认 | 优化二 | 验证 LLM API 可用性，确认调用延迟和成本 |

### 7.2 风险项（需关注但不阻塞）

| # | 风险 ID | 严重度 | 描述 | 影响优化 | 缓解措施 |
|---|---------|--------|------|---------|---------|
| 1 | R-01 | 🟡 P1 | T8/T10 节点查找失败 | 优化三 | 排查 correct API 的节点 ID 传递逻辑 |
| 2 | R-02 | 🟡 P1 | T9 DreamCycle API 缺失 | 优化三 | 确认 run_dream_cycle 是否已迁移到其他方法名 |
| 3 | R-03 | 🟡 P1 | T5 整合未触发 | 优化二 | 排查 consolidate 触发条件 |
| 4 | R-04 | 🟡 P2 | 规则引擎 eval 注入风险 | 优化三 | 考虑用 AST 解析替代 eval |
| 5 | R-05 | 🟢 P3 | 前瞻性索引写入延迟 | 优化二 | 异步生成，不阻塞 remember |
| 6 | R-06 | 🟢 P3 | AGM 公设验证运行时开销 | 优化三 | 仅 agm_mode=True 时启用 |
| 7 | R-07 | 🟢 P3 | 加性融合 vs RRF 融合选择 | 优化一 | 作为可选模式，不替换 RRF |
| 8 | R-08 | 🟢 P3 | 信念状态 "contracted" 对现有代码的影响 | 优化三 | 新状态有默认值，不破坏现有逻辑 |

---

## 八、验收数据集完备性评估

### 8.1 数据集覆盖度

| 优化方向 | 数据集数 | 用例总数 | 覆盖的 SOTA 基准维度 | 缺失维度 |
|---------|---------|---------|---------------------|---------|
| Token 效率 | 4 (DS-1A~D) | 19 | 偏好追踪、信息提取 | 弃权判断、事件排序 |
| 前瞻性索引 | 3 (DS-2A~C) | 19 | 语义鸿沟召回（LoCoMo-Plus） | 时序推理、多跳推理 |
| AGM-lite | 4 (DS-3A~D) | 26 | 矛盾解决（BEAM）、知识更新 | 偏好追踪、指令遵循 |

### 8.2 验收指标完备性

| 优化方向 | 指标数 | 覆盖维度 | 缺失指标 |
|---------|--------|---------|---------|
| Token 效率 | 6 | 利用率、节省率、完整度、延迟、模式正确性、过取适配 | 压缩质量（LLM-as-Judge 评分） |
| 前瞻性索引 | 6 | 召回率、boost 有效性、覆盖率、写入延迟、检索延迟、存储增量 | 场景多样性（跨域场景占比） |
| AGM-lite | 6 | Core-Retainment、Relevance、K*5、评分正确性、一致性检出、回退率 | K*2 Success 边界案例、K*3 Consistency |

### 8.3 缺失补充建议

| 补充项 | 优化方向 | 建议内容 |
|--------|---------|---------|
| DS-1E | Token 效率 | 增加"弃权判断"场景：token_budget 极小时系统应返回"信息不足"而非截断结果 |
| DS-2D | 前瞻性索引 | 增加"时序推理"场景：前瞻性索引是否帮助时序查询 |
| DS-3E | AGM-lite | 增加"K*2 Success 边界案例"：新信息 confidence=0.1 时是否仍被接受 |
| M-补充 | 全部 | 增加 LLM-as-Judge 评分指标，评估压缩/前瞻性索引对答案质量的影响 |

---

## 九、实施条件评估

### 9.1 技术条件

| 条件 | 状态 | 说明 |
|------|------|------|
| 代码可扩展性 | ✅ 满足 | 现有管线结构清晰，插入点明确 |
| 存储层支持 | ⚠️ 部分满足 | ChromaDB 集合扩展 ✅，KuzuDB Schema 迁移 ❌ |
| LLM 调用能力 | ⚠️ 未验证 | 前瞻性索引生成需要 LLM |
| Embedding 可用性 | ❌ 不满足 | 向量嵌入计算全部失败 |
| 测试基础设施 | ✅ 满足 | CLIRunner + EvalReport 框架完善 |

### 9.2 资源需求

| 资源 | 优化一 | 优化二 | 优化三 | 说明 |
|------|--------|--------|--------|------|
| 新建文件 | 4 | 2 | 5 | 共 11 个新文件 |
| 修改文件 | 6 | 9 | 7 | 共 14 个文件（部分重叠） |
| Schema 迁移 | 0 | 4 列 + 1 集合 | 1 列 + 1 边类型 | KuzuDB 迁移是关键风险 |
| LLM 调用 | 0 | 每条记忆 1 次 | 0 | 前瞻性索引的 LLM 成本 |
| 测试用例 | 12 UT + 4 IT | 10 UT + 5 IT | 18 UT + 5 IT | 共 54 个测试用例 |

### 9.3 实施顺序建议

```
Phase 0: 修复基线问题（必须先完成）
  ├── 修复 Embedding 计算失败 (BASE-01)
  ├── 修复 reflect await Bug (BUG-01)
  ├── 验证 KuzuDB Schema 迁移能力 (SCHEMA-01)
  └── 确认 LLM API 可用性 (LLM-01)

Phase 1: Token 效率优化（无外部依赖）
  ├── 新建 token_budget.py, result_compressor.py, additive_scorer.py, result_formatter.py
  ├── 修改 memory_api.py, query_router.py, rrf_fusion.py, rrf_types.py, query_router_types.py, memory.py
  ├── 编写 12 个单元测试 + 4 个集成评估
  └── 运行回归测试（262 UT + 10 IT + LoCoMo T1-T10）

Phase 2: 前瞻性索引（依赖 Phase 0 的 Embedding 和 LLM 修复）
  ├── 新建 prospective_indexer.py, prospective_matcher.py
  ├── Schema 迁移：CognitiveNode 新增 4 列 + ChromaDB 新增集合
  ├── 修改 memory_api.py, models.py, repository.py, kuzu_store.py, chroma_store.py, rrf_fusion.py, rrf_types.py, query_router_types.py, cognitive_vector_index.py, memory.py
  ├── 编写 10 个单元测试 + 5 个集成评估
  └── 运行回归测试

Phase 3: AGM-lite（依赖 Phase 0 的 Bug 修复和 Schema 迁移验证）
  ├── 新建 agm/ 子包（5 个文件）
  ├── Schema 迁移：CognitiveNode 新增 discardability_score + CONTRACTED_FROM 边
  ├── 修改 memory_api.py, models.py, repository.py, kuzu_store.py, arbitration_engine.py, lifecycle.py, reflect_agent.py, memory.py
  ├── 编写 18 个单元测试 + 5 个集成评估
  └── 运行回归测试
```

---

## 十、改进建议

### 10.1 验收方案改进

| # | 建议 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 增加 LLM-as-Judge 评分指标 | P1 | 评估压缩/前瞻性索引对答案质量的影响，参考 BEAM Nugget-Based 评分 |
| 2 | 增加"弃权判断"数据集 | P2 | DS-1E：token_budget 极小时系统应返回"信息不足"而非截断 |
| 3 | 增加跨优化交互测试 | P1 | 验证 Token 效率 + 前瞻性索引 + AGM-lite 同时启用时的行为 |
| 4 | 增加大规模数据集 | P2 | 当前数据集规模 ≤ 200 条，需增加 1000+ 条规模的性能测试 |

### 10.2 代码改进

| # | 建议 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 修复 Embedding 计算失败 | P0 | 当前所有向量索引操作失败，是最高优先级 |
| 2 | 修复 reflect await Bug | P0 | 集成测试中 get_reflection_status() 未 await |
| 3 | 验证 KuzuDB Schema 迁移 | P0 | 编写迁移测试脚本，确认 ALTER TABLE 或数据重建策略 |
| 4 | 增加配置化开关 | P1 | 三个优化均应有 feature flag，可独立开关 |
| 5 | 规则引擎 eval 替换 | P2 | 考虑用 AST 解析替代 eval，降低注入风险 |

### 10.3 文档改进

| # | 建议 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 补充 Schema 迁移方案 | P0 | optimization-sota.md 需增加 KuzuDB 迁移策略章节 |
| 2 | 补充 LLM 调用成本估算 | P1 | 前瞻性索引的 LLM 调用成本需量化 |
| 3 | 补充回滚方案 | P1 | 每个优化的回滚策略需文档化 |

---

## 附录 A：测试执行详情

### A.1 单元测试执行命令

```bash
cd /Volumes/Extension/Projects/CodeDev/OntologyEngine
python -m pytest tests/unit/engine/cognitive/ -v --tb=short
# 结果: 262 passed in 35.17s
```

### A.2 集成测试执行命令

```bash
python -m pytest tests/integration/test_e2e_agent_memory.py -v --tb=short
# 结果: 9 passed, 1 failed in 4.08s
# 失败: test_phase3_governance_reflect_and_approve (await Bug)
```

### A.3 LoCoMo 评估执行命令

```bash
python examples/agent_memory/04_locomo_eval/run_eval.py
# 结果: 6/10 passed (60.0%), 平均 score=0.45
# 失败: T4(矛盾检测), T8(节点查找), T9(DreamCycle API), T10(全生命周期)
```

## 附录 B：文件变更清单

### B.1 需修改的现有文件（14 个）

| 文件 | 优化一 | 优化二 | 优化三 |
|------|:------:|:------:|:------:|
| ontology_engine/engine/cognitive/memory_api.py | ✓ | ✓ | ✓ |
| ontology_engine/engine/cognitive/models.py | | ✓ | ✓ |
| ontology_engine/engine/cognitive/repository.py | | ✓ | ✓ |
| ontology_engine/engine/cognitive/rrf_fusion.py | ✓ | ✓ | |
| ontology_engine/engine/cognitive/rrf_types.py | ✓ | ✓ | |
| ontology_engine/engine/cognitive/query_router.py | ✓ | | |
| ontology_engine/engine/cognitive/query_router_types.py | ✓ | ✓ | |
| ontology_engine/engine/cognitive/arbitration_engine.py | | | ✓ |
| ontology_engine/engine/cognitive/lifecycle.py | | | ✓ |
| ontology_engine/engine/cognitive/reflect_agent.py | | | ✓ |
| ontology_engine/engine/cognitive/cognitive_vector_index.py | | ✓ | |
| ontology_engine/storage/graph/kuzu_store.py | | ✓ | ✓ |
| ontology_engine/storage/vector/chroma_store.py | | ✓ | |
| ontology_engine/api/routes/memory.py | ✓ | ✓ | ✓ |

### B.2 需新建的文件（11 个）

| 文件 | 优化方向 |
|------|---------|
| ontology_engine/engine/cognitive/token_budget.py | 优化一 |
| ontology_engine/engine/cognitive/result_compressor.py | 优化一 |
| ontology_engine/engine/cognitive/additive_scorer.py | 优化一 |
| ontology_engine/engine/cognitive/result_formatter.py | 优化一 |
| ontology_engine/engine/cognitive/prospective_indexer.py | 优化二 |
| ontology_engine/engine/cognitive/prospective_matcher.py | 优化二 |
| ontology_engine/engine/cognitive/agm/__init__.py | 优化三 |
| ontology_engine/engine/cognitive/agm/discardability_scorer.py | 优化三 |
| ontology_engine/engine/cognitive/agm/contraction_engine.py | 优化三 |
| ontology_engine/engine/cognitive/agm/postulate_verifier.py | 优化三 |
| ontology_engine/engine/cognitive/agm/consistency_checker.py | 优化三 |

### B.3 需新建的测试文件（3 个）

| 文件 | 测试用例数 |
|------|-----------|
| tests/unit/engine/cognitive/test_token_efficiency.py | 12 |
| tests/unit/engine/cognitive/test_prospective_index.py | 10 |
| tests/unit/engine/cognitive/test_agm_lite.py | 18 |

### B.4 需新建的评估脚本（1 个）

| 文件 | 评估轨迹数 |
|------|-----------|
| examples/agent_memory/09_sota_optimization_eval/run_eval.py | 14 |

### B.5 需新建的验收数据集（3 个）

| 文件 | 数据集 |
|------|--------|
| tests/benchmarks/optimization_sota/ds_token_efficiency.py | DS-1A~D |
| tests/benchmarks/optimization_sota/ds_prospective_index.py | DS-2A~C |
| tests/benchmarks/optimization_sota/ds_agm_lite.py | DS-3A~D |

---

## 附录 C：验收指标与基线对照

| 指标 ID | 指标名称 | 验收阈值 | 当前基线 | 差距 | 可达性 |
|---------|---------|---------|---------|------|--------|
| VA-1-M1 | Token 利用率 | ≥ 0.7 | ~0.3 | 0.4 | ✅ 可达（五层架构直接提升） |
| VA-1-M2 | Token 节省率 | ≥ 0.5 | 0% | 0.5 | ✅ 可达（压缩模式直接节省） |
| VA-1-M3 | 信息完整度 | ≥ 0.9 | 1.0 | -0.1 | ✅ 可达（需验证压缩不丢核心信息） |
| VA-1-M4 | 检索延迟 P95 | ≤ 基线×1.2 | ~600ms | 0 | ✅ 可达（纯计算开销小） |
| VA-2-M1 | 语义鸿沟召回率 | ≥ 0.8 | ~0.2 | 0.6 | ⚠️ 依赖 Embedding 修复 |
| VA-2-M2 | 前瞻性 boost 有效性 | ≥ 0.7 | N/A | N/A | ⚠️ 依赖 Embedding 修复 |
| VA-2-M3 | 索引生成覆盖率 | ≥ 0.95 | 0 | 0.95 | ⚠️ 依赖 LLM 可用性 |
| VA-2-M4 | 写入延迟增量 | ≤ 2s | 0 | 2s | ✅ 可达（异步生成） |
| VA-3-M1 | Core-Retainment 通过率 | 1.0 | ~0.8 | 0.2 | ⚠️ 依赖矛盾检测修复 |
| VA-3-M2 | Relevance 通过率 | ≥ 0.95 | N/A | N/A | ✅ 可达（规则明确） |
| VA-3-M3 | K*5 Preservation 通过率 | ≥ 0.98 | N/A | N/A | ✅ 可达（规则明确） |
| VA-3-M6 | AGM 验证违规回退率 | 1.0 | 0 | 1.0 | ✅ 可达（回退逻辑简单） |

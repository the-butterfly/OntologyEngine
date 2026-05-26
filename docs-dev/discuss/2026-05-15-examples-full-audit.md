# Examples 全量运行审查报告

**日期**: 2026-05-15
**审查范围**: `examples/agent_memory/` 全部 12 个 eval 脚本 + 4 个辅助脚本
**LLM 端点**: `http://localhost:9528/v1`, 模型 `sensenova/sensenova-6.7-flash-lite`
**环境变量**: `OE_LLM_BASE_URL`, `OE_LLM_API_KEY`, `OE_LLM_MODEL`

---

## 一、总体通过率

| # | 脚本 | 架构 | 通过/总数 | 通过率 | LLM 调用 | 关键问题 |
|---|------|------|-----------|--------|----------|----------|
| 01 | ingestion_pipeline | EvalReport | **8/8** | 100% | 否 | T2 dedup=False |
| 02 | contradiction_belief | EvalReport | **6/7** | 85.7% | ✅ 是 | T5 approve_memory; LLM consolidation 序列化错 |
| 03 | consolidation_compilation | EvalReport | **8/8** | 100% | ✅ 是 | 全部 LLM 序列化失败; 多场景 score=0.50 |
| 04 | locomo_eval | EvalReport | **10/10** | 100% | ✅ 是 | T4 31s LLM 矛盾检测; LLM consolidation 失败 |
| 05 | lifecycle_governance | EvalReport | **8/8** | 100% | ✅ 是 | LLM consolidation 失败 |
| 06 | full_agent_eval | EvalReport | **3/8** | 37.5% | ✅ 是 | record_commitment/compile/list_my 方法缺失 |
| 07 | modeling_objects | EvalReport | **3/8** | 37.5% | 否 | record_commitment/list_my 方法缺失 |
| 08 | qul_lifecycle | EvalReport | **7/8** | 87.5% | ✅ 是 | T3 record_commitment 缺失; LLM consolidation 失败 |
| 09 | sota_optimization_eval | EvalReport | **12/12** | 100% | ✅ 是 | IT-2-01 语义 gap 0/5 hits; LLM consolidation 失败 |
| 10 | contradiction_fix_eval | EvalReport | **14/17** | 82.4% | ✅ 是 | R-03/R-04/P-01 失败; B-02 429 限流; 长时间运行(5min+) |
| 11 | acpt_retrieval | **AcptReport** | **5/9** ≥0.7 | 55.6% | 否(A-07) | Mean=0.767; A-01/A-06/A-07/A-08 低分 |
| 12 | acpt_management | **AcptReport** | **8/8** ≥0.7 | 100% | 否 | Mean=0.963; B-06 pending_review 被 normalise |

**总计: 92/111 通过 (82.9%)**

---

## 二、LLM 调用真实性审查

### ✅ 确认使用真实 LLM 调用的路径

| 操作 | 调用链 | 证据 |
|------|--------|------|
| `reflect()` | CLIRunner → MemoryAPI.reflect() → ReflectAgent._execute_reflect() → llm_call_fn() | 01-T1 34s、02-T2 20s、04-T4 31s |
| `consolidate()` | CLIRunner → MemoryAPI.run_consolidation() → ConsolidationEngine → llm_consolidate_fn() | 返回错误日志 "LLM consolidation failed" |
| `extract_constraints()` | CLIRunner.extract_constraints() → RRF 工具函数 | 规则匹配，非 LLM |
| `compile_entity_page()` | (未亲自调用，但引擎链支持) | — |

### ⚠️ LLM 调用但失败的操作

| 操作 | 错误 | 影响 |
|------|------|------|
| **LLM Consolidation** | `Object of type Fragment/CognitiveNode is not JSON serializable` | 所有 scenario 的 consolidate 步骤均失败。ConsolidationEngine 在构建 prompt 时将 Fragment/CognitiveNode 对象直接传给 json.dumps()，未先转换为 dict |
| **10-B-02** | `429 Too Many Requests` | LLM API 限流，偶发性，非代码问题 |

### ✅ 确认无 mock 绕过

- 全量 Grep 结果: **0 个 mock/patch/MagicMock/unittest.mock** 出现在任何 `run_eval*.py` 中
- 所有 eval 通过 `CLIRunner` → `MemoryAPI` 真实链路调用
- 无硬编码的假数据、无 skip 标记绕过

---

## 三、按场景的详细发现

### 01_ingestion_pipeline — 摄入流水线
- **T2 DeduplicationGate**: `dedup=False` — 两次相同内容的 remember 返回不同 node_id
  - 第一次: `mem:entity:ingestion_eval:1b5ce857f859`
  - 第二次: `mem:entity:ingestion_eval:f18f7ab53678`
  - 第三次: `mem:entity:ingestion_eval:f2413fe906f0`
  - **结论**: Deduplication gate 未生效，需排查 `DeduplicationGate.check()` 逻辑
- T1/T3-T8 均正常

### 02_contradiction_belief — 矛盾检测
- **T1 规则矛盾**: ✅ 检测到 2 个矛盾
- **T2 LLM 语义矛盾**: ✅ 检测到 3 个矛盾（LLM 真实调用）
- **T5 Approve**: ❌ 同 B-06 问题 — `approve_memory` 要求 pending_review 状态
- **LLM Consolidation 序列化**: 4 处失败

### 03_consolidation_compilation — 整合编译
- **全部 LLM Consolidation 失败**: 序列化问题导致所有 consolidate 操作无效果
- T1-T4/T7 score=0.50 均因 consolidation 失败
- T5 EntityPage: summary_len=0（无 LLM 生成）
- T6 TopicPage: synthesis_len=0

### 04_locomo_eval — 综合评估
- **T4 矛盾检测**: ✅ 检测到 5 个矛盾 + 2 个洞察（31s LLM）
- **T9 DreamCycle**: ✅ phases=5
- **T10 全生命周期**: ✅ 所有操作通过
- LLM Consolidation 全部失败（序列化问题）

### 06_full_agent_eval — 全栈评估
- **方法缺失**: `record_commitment`, `compile_entity_page`, `list_my_memories` 在 MemoryAPI 上不存在
  - CLIRunner 定义了这些方法但没有对应的 MemoryAPI 实现
  - T2/T4/T6/T7 因此失败
- T8 全生命周期 ✅

### 07_modeling_objects — 对象建模
- 同样的问题: `record_commitment`, `list_my_memories` 缺失
- T4 Self Model: recall_hits=0（模型未正确创建）

### 08_qul_lifecycle — QUL 生命周期
- **T1 约束提取**: 1/4 extracted（提取率低，可能是 QUL 未充分启用）
- **T4 全生命周期**: ✅ 26s LLM reflect
- **T8 E2E**: ✅ 23s LLM reflect, 1 insight

### 09_sota_optimization_eval — SOTA 优化
- **IT-2-01 语义 gap**: 0/5 hits — "推荐什么晚餐"、"批量查征信可行吗" 等问题全部 MISS
  - 这是真正的语义检索差距，证明了优化方向的必要性
- **IT-3-01 核心信念保护**: contradictions=0, insights=0（LLM reflect 可能因限流失败）
- **IT-3-04 AGM postulate**: 1/5 supported — 大部分形式化 belief revision 规则未实现

### 10_contradiction_fix_eval — 矛盾修复验证
- **R-01 否定冲突**: ✅ 16 contradictions
- **R-02 值冲突**: ✅ 5 contradictions
- **R-03 信念冲突**: ❌ contradictions=0
- **R-04 实体名分组**: ❌ `entity_name` 参数不存在于 CLIRunner.remember()
- **P-01 50+节点压力**: ❌ timeout-like (48s, 0 contradictions)
- **LLM 频繁调用**: 总计 ~5min 运行时间，多场景 30-60s LLM 处理

### 11_acpt_retrieval — 检索验收
- **A-01**: precision=0.25 — 返回 4 条结果仅 1 条相关
- **A-06**: low_conf_excluded=False — 置信过滤未实施
- **A-07**: evidence_non_empty=False — 证据链未展开
- **A-08**: alice_leak=True — 私有隔离未生效

### 12_acpt_management — 管理验收
- 全部 8 场景 ≥0.7
- B-06 `has_pending=False`: pending_review 在 stats 中被归一化

---

## 四、系统级问题汇总

### P0 — 阻塞性问题

| # | 问题 | 影响范围 | 修复建议 |
|---|------|----------|----------|
| 1 | **LLM Consolidation 序列化错误** | 03/04/05/08/09/10/11 共 7 个脚本 | `ConsolidationEngine` prompt 构建时 Fragment/CognitiveNode 需先 `.to_dict()` |
| 2 | **DeduplicationGate 不生效** | 01-T2 | 排查 `DeduplicationGate.check()` 的相似度阈值和决策逻辑 |
| 3 | **MemoryAPI 方法缺失** | 06/07/08 | `record_commitment`/`list_my_memories`/`compile_entity_page` 未在 MemoryAPI 注册 |
| 4 | **approve_memory 状态限制** | 02-T5 | 应支持从 accepted 状态 approve 或在 eval 中使用 pending_review 状态 |
| 5 | **置信过滤/私有隔离/证据链未实施** | 11-A06/A07/A08 | recall 管道需补充 min_confidence/user_id/evidence 过滤逻辑 |

### P1 — 功能性问题

| # | 问题 | 影响 |
|---|------|------|
| 6 | **IT-2-01 语义检索全 MISS** | 跨领域语义匹配能力严重不足 |
| 7 | **A-01 精度 25%** | 召回结果过多无关项，缺 post-recall relevance filtering |
| 8 | **B-06 pending_review 被 stats 归一化** | belief_status 追踪不准确 |
| 9 | **R-04 entity_name 参数缺失** | CLIRunner.remember() 缺少 entity_name 参数 |
| 10 | **QUL 约束提取率低 (1/4)** | QueryUnderstandingLayer 未充分启用 |
| 11 | **`run_eval_llm.py` 检测 `ONTOLOGY_LLM_API_KEY` 而非 `OE_LLM_API_KEY`** | LLM 检测逻辑与实际 env var 不一致 |

### P2 — 运维问题

| # | 问题 |
|---|------|
| 12 | 10-B-02 LLM API 429 限流 — 大批量运行时需加 rate limiting 或重试 |
| 13 | 旧 eval 脚本中存在 8 条"永恒真"断言（tags 是 list、node_id 非空等） |
| 14 | 部分场景 score=0.50 掩盖了实际失败（API 不崩=pass 的残留模式） |

---

## 五、LLM 使用统计

| 操作 | 场景数 | 总调用估算 | 单次耗时 |
|------|--------|-----------|----------|
| `reflect()` 矛盾检测 | 8 | ~16 | 15-40s |
| `reflect()` 洞察生成 | 5 | ~8 | 10-30s |
| `consolidate()` | 11 | ~30 | 失败 |
| `dream()` | 3 | 3 | <1s |
| **总计** | — | **~57 次 LLM 调用** | — |

---

## 六、建议优先级

1. **立即修复**: LLM Consolidation 序列化错误 → 可解锁 7 个脚本的 consolidate 步骤
2. **短期修复**: DeduplicationGate 不生效 + MemoryAPI 方法缺失 → 提高 06/07 通过率
3. **中期改善**: 置信过滤/私有隔离/证据链 → 提升 11 验收评分
4. **持续关注**: 语义检索 gap + 精度问题 → 需要检索管道整体优化
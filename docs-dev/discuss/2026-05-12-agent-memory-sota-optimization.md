# Agent Memory SOTA 优化设计决策记录

> **日期**: 2026-05-12 | **状态**: 已完成设计 | **文档**: docs/02-design/agent-memory/optimization-sota.md

---

## 背景

基于对 mem0 代码库（/Volumes/Extension/Projects/AgentKB-Memory/mem0）和 Kumiho 论文（arXiv:2603.17244）的深度分析，识别出 OntologyEngine Agent 记忆系统在三个方向上的差距，并完成优化设计。

## 关键决策

### D-OPT-1: Token 效率 — 五层架构而非单一截断

**决策**：采用五层 Token 效率架构（预算感知检索 → 结构化压缩 → 激进短路 → 加性融合 → 结果格式化），而非仅在最终阶段截断。

**依据**：
- mem0 开源版实际无显式 token budget 机制，仅用 top_k + 字符截断
- mem0 的核心效率来自：4x 过取 + 三信号融合 + 自适应除数 + 语义前置门控
- OntologyEngine 当前 token_budget 仅做逐条截断，浪费了检索管线的优化空间

**权衡**：
- 五层架构增加了管线复杂度，但每层可独立开关
- Layer 3（激进短路）可能与现有分层漏斗冲突，需要 DispositionProfile 维度交互规则

### D-OPT-2: 前瞻性索引 — 独立 ProspectiveIndex 集合而非嵌入主记忆

**决策**：前瞻性索引存储在独立的 ChromaDB 集合 `prospective_queries` 和 KuzuDB `ProspectiveIndex` 表中，不污染主记忆库。

**依据**：
- Kumiho 的 Prospective Indexing 在写入时让 LLM 生成假设性未来查询场景并索引
- LoCoMo-Plus 基准中，cue-trigger semantic disconnect 是所有基线系统的共同弱项
- Kumiho 通过前瞻性索引达到 98.5% 召回率

**权衡**：
- 写入时 LLM 成本：每条 observation/opinion/constraint/commitment 增加 3-5 个场景的 LLM 调用
- 存储成本：独立集合增加存储，但不影响主记忆检索性能
- 检索时延迟：前瞻性匹配与 RRF 融合并行执行，不增加串行延迟

### D-OPT-3: AGM-lite 验证层而非替换规则引擎

**决策**：AGM-lite 作为验证层叠加在现有规则引擎之上，不替换规则引擎。

**依据**：
- 完整 AGM 需要逻辑推理引擎，工程成本过高
- Kumiho 证明了 AGM K*2-K*6 + Relevance/Core-Retainment 公设可以在实际系统中实现
- 当前规则引擎的 7 条默认规则存在冲突可能（如 BR_R001 vs BR_R005）

**权衡**：
- AGM-lite 不提供完整形式化证明，但提供运行时公设验证
- 违反 Core-Retainment 或 Relevance 时回退规则动作 + 升级人工审查
- 一致性检查器在规则初始化时运行，不增加运行时开销

## 与 SOTA 方案的对齐状态

| 维度 | 优化前 | 优化后 | SOTA 参考 |
|------|--------|--------|-----------|
| Token 效率 | token_budget 逐条截断 | 五层架构 + 压缩模式 | mem0 ~6,950 token/查询 |
| 语义鸿沟召回 | QUL 反应式约束提取 | 前瞻性索引写入时预索引 | Kumiho 98.5% 召回 |
| 信念修正 | 7 条规则 + eval | AGM-lite 验证层 + 收缩操作 | Kumiho AGM K*2-K*6 |
| 实体链接 | EntityResolver 写入时消歧 | [未优化] 需增加检索时实体 boost | mem0 Entity Store + 95% 合并 |
| 加性融合 | RRF 四路融合 | [新增] 语义前置门控 + 自适应除数 | mem0 三信号加性融合 |

## 验收标准决策

### D-VA-1: Nugget-Based 评分而非 Token-level F1

**决策**：采用 BEAM 基准的 Nugget-Based 评分（0/0.5/1.0），而非 LoCoMo 的 Token-level F1。

**依据**：
- Token-level F1 无法区分"部分记住"和"完全忘记"
- Nugget-Based 能捕捉部分记忆失败的细微情况
- 与项目现有 CLIRunner 的 EvalReport 评分体系（0/0.5/1.0）天然对齐

### D-VA-2: 验收数据集覆盖 LoCoMo-Plus 场景

**决策**：DS-2A 数据集专门设计 10 个 Cue-Trigger Semantic Disconnect 场景，对齐 LoCoMo-Plus 基准。

**依据**：
- LoCoMo-Plus 是当前唯一专门测试隐性约束记忆的基准
- Kumiho 在 LoCoMo-Plus 上达到 93.3%，验证了前瞻性索引的有效性
- 10 个场景覆盖 observation/constraint/commitment/opinion/entity 五种类型

### D-VA-3: AGM 验收阈值 — Core-Retainment 必须为 1.0

**决策**：VA-3-M1（Core-Retainment 通过率）的验收阈值为 1.0，不允许任何核心信念被错误移除。

**依据**：
- 核心信念被错误移除的后果是不可逆的（数据丢失）
- Kumiho 的 Core-Retainment 公设要求核心信念在收缩操作中不被移除
- 当前 BR_R001（用户更正 priority=100）可覆盖 BR_R005（反馈保护 priority=60），导致核心信念被移除

### D-VA-4: 回归保护 — 现有 T1-T10 不得退化

**决策**：优化实施后，现有 LoCoMo 评估轨迹 T1-T10 的通过率不得降低。

**依据**：
- 优化是增量式的，不应破坏已有功能
- T1-T3 当前 score=0.5（向量检索降级），优化后应 ≥ 0.5
- T4-T10 当前 score=1.0，优化后必须保持 1.0

## 待讨论

1. **前瞻性索引的 LLM 成本**：是否需要为所有 observation 生成，还是仅高价值记忆？
2. **AGM-lite 与 BR_R001 的冲突**：用户更正 vs 核心信念保护，哪个优先级更高？
3. **加性融合 vs RRF 融合**：是否完全替换 RRF，还是作为可选模式并存？

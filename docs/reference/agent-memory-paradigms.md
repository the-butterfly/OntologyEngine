# Agent 记忆范式深度参考

> **作用**: 存放 2025-2026 年 Agent 记忆系统关键方案（Mem0、Zep/Graphiti、Hindsight、BYTEROVER、Kumiho）的设计展开与对比分析
> **来源**: `docs-dev/research/knowledge-base-agent-memory-comparison-20260428.md`, `docs-dev/research/hindsight-deep-analysis.md`, `docs-dev/research/mem0-report/report.md`
> **最后更新**: 2026-05-15
> **交叉比对基准**: `ontology_engine/engine/cognitive/` 实际代码 + AgentKB-Memory 外部方案源码

---

## 目录

1. [评估基准：LoCoMo / LongMemEval / BEAM / LoCoMo-Plus](#1-评估基准)
2. [memo Token-Efficient Memory Algorithm](#2-mem0)
3. [Zep/Graphiti 时序知识图谱](#3-zepgraphiti)
4. [Hindsight Retain→Recall→Reflect 架构](#4-hindsight)
5. [新兴范式：BYTEROVER / Memory-R1 / Kumiho](#5-新兴范式)
6. [方案总对比表](#6-方案总对比表)
7. [OntologyEngine 交叉比对与争议标记](#7-oe-交叉比对)

---

## 1. 评估基准

### 1.1 LoCoMo（ACL 2024）

| 属性 | 值 |
|------|-----|
| 类型 | 长对话记忆基准 |
| 规模 | 10 个对话，平均 ~600 轮 / ~16K token |
| 问题数 | 1,982 |
| 测试维度 | 单跳回忆、多跳推理、时序推理、开放域知识 |
| 评分 | Token-level F1 |

**典型成绩**：Mem0 91.6% | Hindsight 89.6% | BYTEROVER 92.2%

### 1.2 LongMemEval（ICLR 2025）

| 属性 | 值 |
|------|-----|
| 规模 | 平均 100K-1.5M token |
| 问题数 | 500 |
| 测试维度 | 信息提取、多会话推理、时序推理、知识更新、偏好回忆 |
| 评分 | LLM-as-a-Judge |

**典型成绩**：Mem0 93.4% | Hindsight 91.4%

### 1.3 BEAM（ICLR 2026）

| 属性 | 值 |
|------|-----|
| 规模 | 100K / 500K / 1M / **10M** token 四级 |
| 测试维度 | 10 项能力（偏好追踪、矛盾解决、事件排序等） |
| 评分 | Nugget-based（0/0.5/1.0） |

**关键发现**：
- 百万 token 上下文窗口的模型也无法仅靠扩大窗口解决长时记忆问题
- 所有系统在 10M 规模均显著衰减
- Mem0 1M: 64.1% → 10M: 48.6%
- Hindsight 1M: 73.9% → 10M: 64.1%

### 1.4 LoCoMo-Plus（2026.02）

| 属性 | 值 |
|------|-----|
| 定位 | 认知记忆评估（隐性约束回忆） |
| 测试场景 | cue-trigger semantic disconnect |
| 基线成绩 | 23%-46%（含百万窗口顶级模型） |
| Kumiho 成绩 | **93.3%**（使用 GPT-4o-mini，总成本 ~$14） |

---

## 2. Mem0

> 来源: `docs-dev/research/mem0-report/report.md` §2 | 代码: AgentKB-Memory/mem0/

### 2.1 核心算法：Token-Efficient Memory（2026.04）

**关键创新**：Single-Pass ADD-only 提取 + Multi-Signal 检索

```
传统两阶段: 事实识别 → 记忆协调(ADD/UPDATE/DELETE/NOOP) → 持久化
新算法:     单次 LLM 调用(提取) → 去重 → 实体链接 → 持久化(仅 ADD)
```

**新算法改动的三个核心决策**：

| 决策 | 旧算法 | 新算法 |
|------|--------|--------|
| 提取流程 | 两阶段（识别 + 协调） | 单次端到端 |
| 更新语义 | ADD/UPDATE/DELETE/NOOP | **仅 ADD** |
| Agent 记忆 | 忽略 Agent 自身发言 | Agent 事实一等公民 |

**基准跃升**：
- LoCoMo: 71.4% → **91.6%**（+20.2）
- LongMemEval: 67.8% → **93.4%**（+25.6）
- 平均检索 token: ~6,950（全上下文基线的 1/4）

### 2.2 四大技术组件

**Single-Pass ADD-only**：
- 放弃协调步骤 → 提取延迟减半
- 保留完整变更历史 → 自然支持时序查询（"+29.6 LoCoMo Temporal"）
- Agent 事实提升为一等公民 → Single-Session Assistant 从 46.4% → 100.0%

**实体链接层**：
- 每次提取识别实体（专有名词、引用文本、复合名词短语）
- 实体单独嵌入 + 独立查找层
- 效果：多跳推理 +23.1，时序查询 +29.6

**多信号并行检索**：
- Semantic Similarity（向量）
- Keyword Matching（BM25）
- Entity Matching（实体层）
- 三者 RRF 融合

**动词形态归一化**：
- 将查询中的动词还原为基本形式 → 提高 BM25 通道召回率

### 2.3 代码验证（AgentKB-Memory 源码）

| 组件 | 路径 | 验证结果 |
|------|------|----------|
| 核心存储 | `mem0/memory/main.py` | 已确认，三层存储（向量/图/结构化） |
| 实体链接 | `mem0/memory/utils.py` | 实体提取逻辑存在 |
| 检索融合 | 无独立 fusion 模块 | 检索集成在 memory 模块内 |

### 2.4 争议记录

> ⚠️ **争议 2.4.1**: Mem0 官方报告 LoCoMo **91.6%** vs BYTEROVER 独立评估 **66.9%**。差异源于评估配置（裁判模型、提示模板、问题子集）不统一。Mem0 已开源评估框架。
>
> ⚠️ **争议 2.4.2**: ADD-only 策略在 BEAM 矛盾解决类别仅 **35.7%**。保留所有历史也保留了所有矛盾，需要更复杂的矛盾检测机制。

---

## 3. Zep/Graphiti

> 来源: `docs-dev/research/mem0-report/report.md` §3 | 代码: AgentKB-Memory/graphiti/

### 3.1 核心架构：时序知识图谱

**论文**: [arXiv:2501.13956](https://arxiv.org/abs/2501.13956)

三层图结构：

```
Community Subgraph（动态标签传播聚类）
        ↑
Semantic Entity Subgraph（LLM 实体/关系提取 + 1024d 嵌入）
        ↑
Episodes（带时间戳的原始数据，ground truth）
```

### 3.2 双时序模型（Bitemporal）

| 时间线 | 含义 | 作用 |
|--------|------|------|
| **T**（事件时间） | 事实实际发生时间 | 锚定事实时间线 |
| **T'**（摄取时间） | 信息被系统观察/添加的时间 | 事务谱系追溯 |

**边有效性区间**：每条边带有 `t_valid` / `t_invalid` 属性。新事实冲突时 → 旧边设 `t_invalid` + 新边建 `t_valid`。

### 3.3 三元混合检索

| 信号 | 实现 | 搜索对象 |
|------|------|----------|
| φ_cos | 余弦语义相似度 | fact / entity name |
| φ_bm25 | Okapi BM25 | 全文搜索 |
| φ_bfs | BFS 图遍历 | n 跳邻域发现 |

**融合**：RRF → Cross-encoder reranking
**P95 延迟**：~300ms（Neo4j native 索引，检索阶段零 LLM 调用）

### 3.4 代码验证（AgentKB-Memory 源码）

| 组件 | 路径 | 验证结果 |
|------|------|----------|
| 核心图引擎 | `graphiti/graphiti_core/graphiti.py` | 确认：Graphiti 类 |
| 节点定义 | `graphiti/graphiti_core/nodes.py` | 确认：EntityNode, EpisodeNode 等 |
| 边定义 | `graphiti/graphiti_core/edges.py` | 确认：带 t_valid/t_invalid 属性 |
| 搜索 | `graphiti/graphiti_core/search/search.py` | 确认：多模式搜索实现 |
| Neo4j 驱动 | `graphiti/graphiti_core/driver/neo4j/` | 确认 |
| 跨编码器 | `graphiti/graphiti_core/cross_encoder/` | 确认 |

### 3.5 争议记录

> ⚠️ **争议 3.5.1**: 官方报告 LongMemEval 改进 18.5% vs 独立评估 ~63.8%。差异类似 Mem0 的评估配置问题。

> ⚠️ **争议 3.5.2**: 图构建需数小时后台处理，摄入后立即检索经常失败。适合延迟敏感度低的场景。

---

## 4. Hindsight

> 来源: `docs-dev/research/hindsight-deep-analysis.md` | 代码: AgentKB-Memory/hindsight/

### 4.1 核心定位

> "Hindsight is focused on making agents that learn, not just remember."
> —— Vectorize.io

LongMemEval SOTA（2026.01），Virginia Tech / Washington Post 独立复现。

### 4.2 四层记忆类型

```
Mental Model    │ 用户策划摘要     │ 最高优先级 │ reflect 使用
Observation     │ 自动归纳知识     │ 中优先级   │ 证据追踪
World Fact      │ 客观世界事实     │ 低优先级   │ retain 提取
Experience Fact │ Agent 自身经历    │ 低优先级   │ retain 提取
```

**Observation 关键结构**（带证据追踪）：
```python
{
    "text": "Alice works at Google",
    "proof_count": 3,                     # 证据数量
    "source_memory_ids": ["uuid1", ...],  # 来源记忆
    "history": [...],                      # 变更历史
    "occurred_start": datetime,           # MIN(来源)
    "occurred_end": datetime,             # MAX(来源)
}
```

### 4.3 TEMPR 四路并行检索

| 检索路 | 实现 | 关键参数 |
|--------|------|----------|
| **Semantic** | HNSW 向量索引 | 5x Overfetch, ef_search=200, 阈值 0.3 |
| **BM25** | PostgreSQL ts_rank / pg_textsearch / vchord | 三种模式可选 |
| **Graph** | 链路扩展 + 扩散激活 | causal_boost=2.0 |
| **Temporal** | 两阶段 date_ranked → sim_ranked | 窗口 50, 阈值 0.1 |

**RRF 融合**：k=60，四路加权合并 → Cross-encoder reranking

### 4.4 实体解析

**双策略切换**：

| 策略 | 规模 | 方法 |
|------|------|------|
| `full` | 小规模 | 全量实体加载到内存 O(N) |
| `trigram` | 大规模 | pg_trgm 索引 O(1) |

**消歧评分**：
```
score = name_similarity × 0.5
      + cooccurrence_overlap × 0.3
      + temporal_proximity × 0.2
```
阈值 0.6 → 复用 | 0.3-0.6 → 人工审核 | < 0.3 → 新建

### 4.5 事实提取（Fact Extraction）

**四模式**：

| 模式 | 说明 | 场景 |
|------|------|------|
| `concise` | 选择性提取，仅保留长期有价值信息 | **默认** |
| `verbose` | 极度详细提取 | 复杂对话分析 |
| `verbatim` | 保留原文，仅提取元数据 | 精确原文检索 |
| `chunks` | 无 LLM，直接分块存储 | 高速批量摄入 |

**因果关系提取**：`target_fact_index` + `relation_type`（仅 `caused_by`）+ `strength`

### 4.6 Consolidation 机制

```
1. 获取未归类记忆（consolidated_at IS NULL）
2. 按标签分组（严格隔离，防止跨租户泄露）
3. 每组调用 LLM → 返回 create/update/delete 操作
4. 执行操作 + 记录 history
5. 触发 Mental Model 刷新
```

**自适应分批**：LLM 输出太长时折半重试（类似 OE ConsolidationEngine 的 adaptive_batch）

### 4.7 Reflect Agent

**强制搜索序列**：
1. `search_mental_models` → 2. `search_observations` → 3. `recall` → 4-10. LLM 自主选择

**幻觉防护**：`available_memory_ids` 追踪，`done()` 时验证引用 ID 是否真实存在

**上下文的溢出保护**：`estimated_tokens >= max_context_tokens` → 强制最终回答

### 4.8 代码验证（AgentKB-Memory 源码）

| 组件 | 路径 | 验证结果 |
|------|------|----------|
| MemoryEngine | `hindsight-api-slim/.../memory_engine.py` | 确认 |
| 检索 | `.../search/retrieval.py` | 确认：四路检索 |
| RRF Fusion | `.../search/fusion.py` | 确认：RRF 实现 |
| Graph 检索 | `.../search/graph_retrieval.py` | 确认 |
| 链路扩展 | `.../search/link_expansion_retrieval.py` | 确认 |
| 事实提取 | `.../retain/fact_extraction.py` | 确认：四模式 |
| 实体解析 | `.../entity_resolver.py` | 确认：双策略切换 |
| Consolidation | `.../consolidation/consolidator.py` | 确认 |
| Reflect Agent | `.../reflect/agent.py` | 确认：分层工具调用 |
| 跨编码器 | `.../cross_encoder.py` | 确认 |

### 4.9 争议记录

> ⚠️ **争议 4.9.1**: Mental Model 需要用户策划，自动化程度低。Hindsight 对此无原生自动化方案。
>
> ⚠️ **争议 4.9.2**: 矛盾处理依赖证据数量（proof_count），无规则引擎。与 OE 的 BeliefRevisionRule 规则引擎形成对比。

---

## 5. 新兴范式

### 5.1 BYTEROVER Context Tree

| 项目 | 值 |
|------|-----|
| LoCoMo Overall | **92.2%** |
| LongMemEval-S | **92.8%** |
| Temporal | **94.4%**（行业最高） |

**核心创新**：
- LLM 在构建阶段主动组织层级（domain → topic → subtopic）
- Agent Layer 理解意图 → Execution Layer 沿树导航
- 自适应知识生命周期（根据访问频率调整位置）

> ⚠️ **争议**: BYTEROVER 代码未开源，结果无法独立复现。

### 5.2 Memory-R1（强化学习驱动）

| 项目 | 值 |
|------|-----|
| 核心方法 | PPO + GRPO 训练 Memory Manager |
| 训练数据 | 仅 **152 个 QA 对** |
| 扩展性 | 3B → 14B 一致单调提升 |

**创新**：outcome-based RL 替代监督学习 → 通过试错发现最优记忆操作策略

### 5.3 Kumiho（AGM 信念修正）

| 项目 | 值 |
|------|-----|
| LoCoMo-Plus | **93.3%**（基线 45.7%） |
| 总成本 | ~$14（全部 401 条评估） |
| 基础模型 | GPT-4o-mini |

**三大架构创新**：
1. **前瞻性索引（Prospective Indexing）**：写入时让 LLM 生成假设性未来场景并索引
2. **事件提取（Event Extraction）**：保留叙事压缩丢弃的因果细节
3. **客户端 LLM 重排序**：由消费 Agent 的 LLM 从结构化元数据中选择最相关版本

---

## 6. 方案总对比表

| 维度 | Mem0（新算法） | Zep/Graphiti | Hindsight | BYTEROVER | Kumiho |
|------|---------------|-------------|-----------|-----------|--------|
| **核心表示** | 原子事实 + 实体链接 | 时序知识图谱 | 四网络分离 | Context Tree | AGM 信念基 |
| **提取方式** | Single-pass ADD-only | Episode→Entity→Graph | Retain（LLM 抽取） | LLM 策划层级 | 前瞻索引 |
| **时序支持** | ADD-only 保留历史 | 双时序 T/T' | 四路 + 时序过滤 | 内嵌时间戳 | 事件 + 趋势 |
| **矛盾处理** | 无（35.7% BEAM） | 边失效 | 证据计数 | 层级更新 | **AGM 公设** |
| **LoCoMo** | **91.6%** | 75.1% | 89.6% | **92.2%** | 未报告 |
| **LongMemEval** | **93.4%** | ~63.8% | 91.4% | 92.8% | 未报告 |
| **BEAM-1M** | 64.1% | 未报告 | **73.9%** | 未报告 | 未报告 |
| **BEAM-10M** | 48.6% | 未报告 | **64.1%** | 未报告 | 未报告 |
| **Token/查询** | ~6,950 | ~12,000 | ~15,000 | 未公开 | 极低 |
| **开源** | Apache 2.0 | Graphiti 开源 | MIT | 未开源 | 未开源 |

---

## 7. OE 交叉比对与争议标记

### 7.1 研究文档中关于 OE 的表述 — 代码验证

以下验证基于 `ontology_engine/engine/cognitive/` 实际代码（2026-05-15 最新）：

| 研究中的表述 | 来源文档 | 验证结果 | 说明 |
|-------------|----------|----------|------|
| "OE 目前主要是三元组存储 + 概念层" | knowledge-base-agent-memory-comparison.md | ❌ **已过时/不正确** | OE 已实现完整的认知层：12 内存类型 + 4 认知层 + 信念状态机 |
| "缺少自动归纳层（Observation）" | hindsight-deep-analysis.md §8.1 | ❌ **已过时/不正确** | `CognitiveNode.memory_type` 已包含 `"observation"` |
| "主要依赖向量相似度，缺少 BM25、时序、图遍历" | hindsight-deep-analysis.md §8.2 | ❌ **已过时/不正确** | `RRFFusionEngine` 已实现四路并行（向量/BM25/时序/图遍历） |
| "缺少实体解析" | hindsight-deep-analysis.md §8.3 | ❌ **已过时/不正确** | `EntityResolver` 已实现三维评分 + 双策略 + L1/L2/L3 |
| "缺少 Consolidation" | hindsight-deep-analysis.md §8.4 | ❌ **已过时/不正确** | `ConsolidationEngine` 已实现（Fragment→Knowledge） |
| "缺少 Reflect" | hindsight-deep-analysis.md §8.5 | ❌ **已过时/不正确** | `ReflectAgent` 已实现（多轮工具调用 + 防幻觉） |
| "缺少证据追踪" | hindsight-deep-analysis.md §8.6 | ❌ **已过时/不正确** | `CognitiveNode.proof_count` + `source_fragment_ids` 已实现 |

> **结论**: `docs-dev/research/` 中关于 OE 现状的调研在撰写时（2026-04-20 ~ 2026-04-28）处于准确状态，但 OE 认知层在 2026-05 期间已实现。研究文档中的"当前差距"部分应标记为 **「已实现」**。保留这些文档作为设计动机的参考。

### 7.2 OE Cognitive 模块与外部的设计异同

| 设计点 | OE 实现 | Hindsight | 差异说明 |
|--------|---------|-----------|----------|
| 记忆层次 | 12 类型 × 4 层 | 4 层（Mental/Obs/Wld/Exp） | OE 更多层次（opinion/procedure/commitment 等） |
| 检索融合 | 四路 RRF + 查询类型路由 | 四路 RRF + 跨编码器 | OE 多了查询类型加权 |
| 实体消歧 | 三维（名称 0.5/共现 0.3/时序 0.2）+ L3 LLM | 三维（名称 0.5/共现 0.3/时序 0.2）+ L3 | 评分公式几乎一致 |
| 信念修正 | BeliefRevisionRule 规则引擎 | proof_count 证据驱动 | **OE 独特**: 规则引擎分级处理 |
| consolidate | Fragment→Observation/Entity | Fact→Observation | OE 双向迁移（fragment→knowledge + 回退） |
| 失效机制 | valid_from/valid_to + superseded_by | history 字段 | **OE 独特**: 双时序（类似 Zep） |
| 遗忘机制 | ForgettingEngine + DreamCycle | 无 | **OE 独特**: 主动记忆巩固 |
| Disposition | 7 维（含 risk_tolerance） | 3 维（skepticism/empathy/literalism） | OE 更细粒度 |
| 编译 | CompilationScheduler（Entity/Topic） | Mental Model 手动刷新 | **OE 独特**: 自动编译 |

### 7.3 参考指南

- 查看 OE 设计决策：`docs/02-design/agent-memory/`（各模块 *.md）
- 查看 OE 认知层代码：`ontology_engine/engine/cognitive/`
- 外部方案对照（7 大参考系统）：`docs/reference/external-reference-systems.md`
- 本文件：Agent 记忆范式对照（3 大记忆系统 + 新兴范式）

---

## 参考来源

| 系统 | 原始来源 | OE 代码验证对照 |
|------|---------|----------------|
| Mem0 | `docs-dev/research/mem0-report/` + AgentKB-Memory/mem0/ | `ontology_engine/engine/cognitive/memory_api.py` |
| Zep/Graphiti | `docs-dev/research/mem0-report/report.md` §3 + AgentKB-Memory/graphiti/ | `ontology_engine/engine/cognitive/rrf_fusion.py` |
| Hindsight | `docs-dev/research/hindsight-deep-analysis.md` + AgentKB-Memory/hindsight/ | `ontology_engine/engine/cognitive/` |
| BYTEROVER | `docs-dev/research/mem0-report/report.md` §5.2 | 无代码可验证 |
| Memory-R1 | `docs-dev/research/mem0-report/report.md` §5.3 | 无代码可验证 |
| Kumiho | `docs-dev/research/mem0-report/report.md` §5.4 | 无代码可验证 |

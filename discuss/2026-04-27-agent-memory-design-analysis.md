# OntologyEngine Agent 记忆架构深度审视报告

> **日期**: 2026-04-27 | **分析视角**: Agent记忆库 | **范围**: docs/01-overview/09-agent-memory.md + docs/02-design/ + docs-dev/research/ + Web前沿
> **[关键设计点]**: 本报告基于 Hindsight/Mem0/MAGMA/Zep/Kumiho 等 SOTA 系统的前沿成果，对当前设计进行系统性审视

---

## 一、执行摘要

OntologyEngine 当前从「知识管理系统」向「Agent 记忆系统」演进的设计（`09-agent-memory.md` 及 `docs/02-design/agent-memory/`）在概念框架上已具备良好基础，但在**存储分层语义、时序建模深度、Schema 的认知作用、细粒度检索策略、以及 L1-L4 与记忆类型的融合方式**上，与 2025-2026 年 SOTA Agent 记忆系统存在显著差距。

本报告识别出 **7 个关键不足** 和 **5 个演进方向**，重点参考了 Hindsight 的四网络分离、MAGMA 的正交多图、Mem0 的 ADD-only 时序演化、Zep/Graphiti 的双时序模型、以及 Kumiho 的信念修正框架。

---

## 二、当前设计概览

### 2.1 核心架构（现状）

```
┌─────────────────────────────────────────────┐
│  Agent 认知操作: remember / recall / reflect │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┴──────────────┐
    ▼                             ▼
┌──────────┐              ┌──────────────────┐
│ Layer-R  │              │ Layer-S          │
│ 碎片层   │◄──互索引边──►│ 结构化层         │
│ ChromaDB │  (4种边)     │ KuzuDB + 向量    │
│ 向量优先 │              │ memory_type 标签  │
└──────────┘              └──────────────────┘
                          │ entity/observation│
                          │ mental_model/...  │
                          └──────────────────┘
```

### 2.2 Schema v2 四层（L1-L4）

| 层级 | 内容 | 作用 |
|------|------|------|
| L1 | Fact Objects (entities/relations) | 领域模型定义 |
| L2 | Categorizations (dimensions) | 分类体系 |
| L3 | Analytical Elements (metrics) | 分析计算单元 |
| L4 | Business Logic (rules) | 业务规则与决策 |

### 2.3 Agent 记忆扩展（新增）

- **memory_type 标签**: fragment → observation → entity → mental_model（巩固升级路径）
- **三大认知操作**: Consolidation / Forgetting / Reflection
- **三操作 API**: remember / recall / reflect

---

## 三、关键不足与可改进点

### 不足 1: 存储分层的语义模糊 —— Layer-R/Layer-S 与记忆类型的正交性未充分发挥

**问题描述**:

当前设计将 Layer-R 和 Layer-S 定义为**存储范式差异**（向量优先 vs 图优先），然后在 Layer-S 内通过 `memory_type` 标签区分记忆类型。这一设计的出发点是简化 Agent 认知负担，但导致了两个深层问题：

1. **存储范式与认知层次的混淆**: Layer-R（碎片）本质上是**感知记忆（Sensory Memory）**的等价物——原始、未加工、高保真但不可推理。Layer-S 内的 `fragment` 类型标签却试图在同一存储层内模拟这一过程，造成认知层次与存储层的错位。

2. **时序实体与记忆单元的混存**: `EntityNode`（Schema 驱动的结构化实例）与 `MemoryUnitNode(type=entity)`（记忆视角的实体）通过 `MAPPED_TO` 边关联，形成了**影子节点模式**。这在小规模下可行，但随着实体数量增长，影子节点的维护成本（一致性、更新传播、索引同步）将指数级上升。

**SOTA 对比**:

| 系统 | 分层策略 | 关键洞察 |
|------|---------|---------|
| **Hindsight** | 四网络分离（World/Experience/Opinion/Observation） | 按**认知功能**分离，而非存储范式 |
| **MAGMA** | 四正交图（语义/时序/因果/实体） | 按**关系维度**分离，支持策略引导遍历 |
| **Zep/Graphiti** | 三层子图（Episodic/Semantic/Community） | 按**抽象层次**分离，对应情景→语义→概念记忆 |
| **Letta** | OS 三层（Core/Recall/Archival） | 按**访问时效**分离，Agent 自主管理 |

**深度分析**:

OntologyEngine 当前的分层是**一维的**（存储范式 × 记忆类型标签），而 SOTA 系统趋向**多维正交分离**：

```
当前（OntologyEngine）:          SOTA（理想方向）:
Layer-R (向量)                  Sensory/Episodic Layer（感知/情景）
  └─ fragment                    ├─ 原始交互记录（高保真）
Layer-S (图+向量)                Semantic Layer（语义）
  ├─ fragment                    ├─ 事实网络（World Facts）
  ├─ observation                 ├─ 经验网络（Experience Facts）
  ├─ entity                      ├─ 观察摘要（Observations）
  ├─ mental_model                Opinion Layer（观点）
  ├─ episode                     ├─ 信念网络（带置信度）
  └─ procedure                   Procedural Layer（程序）
                                  └─ 操作模式/技能记忆
```

**改进建议**: 考虑引入**认知功能分层**作为第一维度，存储范式作为第二维度，形成矩阵式架构：

| 认知层次 | 存储范式 A | 存储范式 B | 代表内容 |
|---------|-----------|-----------|---------|
| 感知/情景 | 向量优先（原文保留） | 文档存储 | 原始文档、对话记录 |
| 语义 | 图优先（KuzuDB） | 向量索引 | 实体、关系、观察 |
| 观点 | 图 + 置信度传播 | 时序索引 | 信念、评估、偏好 |
| 程序 | 结构化规则 | 版本控制 | 操作模式、技能 |

---

### 不足 2: 时序建模的浅层性 —— 缺乏双时序模型与事件结构

**问题描述**:

当前时序建模基于 MemPalace 的 `valid_from/valid_to` 模式，本质上是**有效性窗口（Validity Window）**。这在企业数据场景下足够（如"注册资本在 2025-06-01 至 2026-01-01 间有效"），但对 Agent 记忆系统而言严重不足：

1. **无摄取时间（Transaction Time）**: 无法区分"事件何时发生"与"系统何时知晓"。当用户说"实际上，我上周说的日期是错的"时，当前设计只能更新 `valid_to`，丢失了"系统何时被纠正"的元信息。

2. **无事件结构**: 当前时序是**实体属性级**的（`EntityInstance.valid_from`），而非**事件级**的。Agent 记忆需要的事件结构是："用户失业 → 导致付不起房租 → 导致搬到小公寓"，这是一个因果链，当前设计缺乏原生的事件节点和因果边类型。

3. **时序邻近性评分的简单性**: `temporal_proximity()` 函数是线性衰减的，但人类记忆的时间感知是非线性的——近期事件细节清晰，远期事件只记得概要，特定里程碑事件（如签约、上市）长期保持高分辨率。

**SOTA 对比**:

| 系统 | 时序模型 | 关键优势 |
|------|---------|---------|
| **Zep/Graphiti** | 双时序（Event Time T + Ingestion Time T'） | 支持追溯更正、审计追踪、精确时序查询 |
| **Hindsight TEMPR** | 时序过滤作为第四路检索 | 时序窗口 + 向量相似度融合 |
| **MAGMA** | 独立时序图（Temporal Graph） | 时序关系与语义/因果关系正交分离 |
| **Mem0 (新算法)** | ADD-only 保留完整历史 | 天然支持"用户之前如何想"的时序推理 |

**深度分析**:

OntologyEngine 的时序设计是**快照导向的**（Snapshot-oriented），适合企业数据审计，但不适合 Agent 的**叙事记忆（Narrative Memory）**。叙事记忆需要：

- **事件节点（Event Node）**: 独立的记忆单元，携带 `occurred_at`、`mentioned_at`、`event_type`
- **因果边（Causal Edge）**: `LEADS_TO`、`BECAUSE_OF`、`ENABLES`、`PREVENTS`，携带 `strength` 和 `confidence`
- **双时序属性**: `t_valid`（事实有效期）+ `t_transaction`（系统记录期）
- **叙事聚合（Narrative Clustering）**: MAMGA 的 `NARRATIVE` 节点——时间窗口内 ≥3 个相关事件时自动生成叙事摘要

**改进建议**: 引入 **EventNode** 和 **双时序边** 到 KuzuDB Schema：

```cypher
CREATE NODE TABLE EventNode (
    id STRING PRIMARY KEY,
    event_type STRING,           -- interaction / state_change / decision
    description STRING,
    occurred_at TIMESTAMP,       -- 事件实际发生时间 (T)
    recorded_at TIMESTAMP,       -- 系统记录时间 (T')
    participants STRING[],       -- 参与的实体/Agent
    space_id STRING,
    source_fragment_ids STRING[]
);

CREATE REL TABLE CAUSES (
    FROM EventNode TO EventNode,
    causal_type STRING,          -- leads_to / because_of / enables / prevents
    strength DOUBLE,
    confidence DOUBLE
);

CREATE REL TABLE PART_OF_NARRATIVE (
    FROM EventNode TO MemoryUnitNode,  -- 连接到 mental_model/observation
    narrative_id STRING
);
```

---

### 不足 3: Schema 的认知作用被低估 —— 从「约束定义」到「检索路由」的跃迁未完成

**问题描述**:

当前 Schema v2（L1-L4）的核心作用是**数据约束和推理规则定义**：
- L1: 实体/关系的结构约束
- L2: 分类维度定义
- L3: 指标计算逻辑
- L4: 业务规则执行

但在 Agent 记忆系统中，Schema 应该发挥更深层的**认知组织作用**：

1. **Schema 作为检索的语义骨架**: 当前检索是**查询词驱动的**（特征词匹配 → 查询路由），而非**Schema 驱动的**。当 Agent 查询"企业A的风险等级"时，Schema 知道 `risk_grade` 是 L3 指标，由 L4 规则 `R001_risk_grade` 计算，依赖 L1 实体 `Counterparty` 的属性。这一知识路径应该**主动引导检索**，而非被动等待查询路由识别。

2. **Schema 作为记忆巩固的模板**: Consolidation 将 fragment → observation → entity 的升级过程中，当前设计依赖 LLM 判断"是否匹配 Schema entity pattern"。但 Schema 本身可以提供更精确的**提取模板**——L1 EntityDeclaration 的 `attributes` 定义就是提取的目标结构。

3. **L1-L4 与 memory_type 的映射未显式化**: `entity` 类型记忆对应 L1 实例，`rule` 类型对应 L4 定义，但 `mental_model` 应该对应什么？`episode` 和 `procedure` 在 L1-L4 中缺乏明确归属。这导致 Agent 在使用 `oe_remember` 时，无法利用 Schema 结构指导记忆类型的自动分配。

**SOTA 对比**:

| 系统 | Schema/结构作用 | 关键洞察 |
|------|----------------|---------|
| **Kumiho** | Schema-aware 规划引导检索 | 先理解图 Schema，再制定验证计划 |
| **MAGMA** | 策略引导的 Schema 遍历 | 查询意图 → 策略 → 图选择 → 遍历 |
| **SHARP** | Schema-Hybrid Agent | Schema 约束 + 外部证据交叉验证 |
| **Cognee** | 14 种检索模式按 Schema 类型路由 | 不同数据类型触发不同检索策略 |

**深度分析**:

当前设计中的 `query-routing.md` 使用**特征词匹配**进行查询分类（factual/multi-hop/temporal/analytical/mixed），这是 O(1) 的确定性方法，但缺点是：
- 无法利用 Schema 结构优化检索路径
- 对复合查询的识别精度有限
- 不能根据数据的 Schema 类型动态调整检索深度

**改进建议**: 引入 **Schema-Aware Retrieval Router**：

```python
class SchemaAwareRouter:
    def route(self, query, space_id):
        # 1. 查询意图解析（保留特征词匹配）
        intent = detect_query_type(query)
        
        # 2. Schema 结构解析（新增）
        schema_hints = self.schema_parser.extract_referenced_schema(query)
        # 例如: query="企业A的风险等级" → schema_hints=[L3_metric:"risk_grade", L1_entity:"Counterparty"]
        
        # 3. 记忆类型映射（新增）
        memory_type_preference = self.map_schema_to_memory_types(schema_hints)
        # 例如: L3_metric → 优先检索 entity + mental_model
        #       L4_rule → 优先检索 rule + observation
        
        # 4. 联合路由决策
        return RetrievalPlan(
            primary_path=...,
            schema_guided_expansion=True,  # 沿 Schema 依赖链扩展
            memory_type_weights=memory_type_preference
        )
```

---

### 不足 4: 细粒度检索的策略单一 —— 缺乏多信号融合与实体链接层

**问题描述**:

当前检索架构（`query-engine/`）设计了：
- Layer-R: 向量检索 + EXTRACTED_FROM 扩展
- Layer-S: 图遍历 + 边权重偏好 + 时序过滤
- RRF 融合: 三路（Layer-R + Layer-S + BM25）

但与 SOTA 相比存在显著差距：

1. **无实体链接层（Entity Linking Layer）**: Mem0 新算法的核心创新之一是实体链接层——将查询中的实体与记忆库中的实体节点匹配，即使语义相似度不高，只要包含同一实体就提升排名。当前设计缺乏这一层。

2. **无多信号并行检索**: Hindsight TEMPR 的四路并行（语义+BM25+图遍历+时序）是当前设计的超集。OntologyEngine 的 RRF 仅融合 3 路，且时序仅在 temporal 查询类型时启用，而非作为常驻信号。

3. **无自适应检索策略**: MAGMA 的策略引导遍历根据查询意图动态决定遍历路径（语义图→时序图→因果图→实体图）。当前设计的边权重偏好是静态映射表，缺乏动态调整能力。

4. **BM25 的实现局限**: 当前使用 SQLite FTS5 的 `unicode61` 分词器，对中文支持有限。且缺乏 Mem0 的**动词形态归一化**等关键优化。

**SOTA 对比**:

| 系统 | 检索信号 | 融合策略 | 特色机制 |
|------|---------|---------|---------|
| **Hindsight TEMPR** | 语义+BM25+图遍历+时序 | RRF + Cross-Encoder | 四路并行，token 预算感知 |
| **Mem0 (新)** | 语义+关键词+实体匹配 | 三信号融合 | 实体链接层解决指代消解 |
| **MAGMA** | 语义/时序/因果/实体四图 | 策略引导遍历 | 查询自适应路径选择 |
| **Zep** | 语义+BM25+BFS 图遍历 | RRF + Reranking | Neo4j 原生索引，P95=300ms |
| **OntologyEngine** | 语义+BM25+图遍历 | RRF（3路） | 查询路由+静态边权重 |

**深度分析**:

当前设计的检索是**漏斗式**的：先路由到某一路/某几路，再融合。SOTA 趋向**并行信号+动态剪枝**：

```
当前: 查询 → 路由(1路/3路) → 检索 → RRF → 结果

SOTA: 查询 → 并行4路检索 → 候选池 → 动态剪枝 → RRF → Rerank → 结果
              ↑
         每路独立 top-k，
         不依赖路由决策
```

**改进建议**:

1. **引入实体链接层**:
```python
class EntityLinkingLayer:
    async def link_entities(self, query, space_id):
        # 从查询中提取实体指称
        mentions = await extract_mentions(query)
        # 与记忆库中的实体节点匹配
        linked = await self.entity_resolver.resolve(mentions, space_id)
        # 返回实体ID列表，用于检索时提升包含这些实体的记忆
        return linked
```

2. **将时序检索提升为常驻信号**: 即使非 temporal 查询，也启用时序过滤（如优先返回近期记忆），而非仅在 temporal 类型时启用。

3. **引入自适应边权重**: 参考 MAGMA，根据查询的实体密度、时间表达密度、关系词密度动态调整边权重，而非静态映射表。

---

### 不足 5: 巩固与遗忘机制的形式化不足 —— 缺乏信念修正语义

**问题描述**:

当前设计的 Consolidation 和 Forgetting 存在形式化漏洞：

1. **Consolidation 的 LLM 依赖**: `consolidate_batch_with_llm()` 让 LLM 决定 create/update/delete，但缺乏**约束条件**：
   - 当新事实与旧 observation 矛盾时，是删除旧的还是创建新的？
   - 证据链（`source_ids`）在 update 时如何继承？
   - 多条 fragment 合并为一条 observation 时，时序范围如何聚合？

2. **Forgetting 的粗暴性**: 当前遗忘公式 `strength = recency×0.3 + evidence×0.3 + feedback×0.2 + access_freq×0.2` 是启发式的，缺乏**认知科学基础**。Ebbinghaus 衰减的应用过于简化——人类遗忘是非单调的（被巩固的长期记忆几乎不遗忘），且受**睡眠/离线巩固**影响。

3. **无矛盾消解机制**: 当 `mental_model` 与新 `observation` 矛盾时，当前设计生成 `contradiction_report` 并等待人工处理。但 SOTA 系统（Kumiho/Hindsight）已实现**自动信念修正**：Kumiho 基于 AGM 框架，在矛盾时以最少改动维持一致性；Hindsight 的 Opinion Network 通过置信度更新实现信念演化。

**SOTA 对比**:

| 系统 | 巩固机制 | 遗忘机制 | 矛盾处理 |
|------|---------|---------|---------|
| **Hindsight** | LLM 提取 + 实体解析 + 图链接构建 | 无显式遗忘（依赖规模限制） | Opinion Network 置信度更新 |
| **Mem0 (新)** | Single-pass ADD-only（无 update/delete） | 无（保留全部历史） | 检索时由 LLM 判断 |
| **Kumiho** | 前瞻性索引 + 事件提取 | 无显式遗忘 | **AGM 信念修正**：Supersedes 边 + 最小改动原则 |
| **Letta** | Agent 自主决定（工具调用） | 无自动机制 | 无 |
| **OntologyEngine** | LLM 判断 CUD | Ebbinghaus 启发式 | 人工确认的矛盾报告 |

**深度分析**:

当前设计的核心矛盾在于：**试图让企业知识管理系统（确定性、人工审核）和 Agent 记忆系统（自治、自动演化）共享同一套矛盾处理机制**。在企业场景下，"CRM 和 ERP 的客户地址不一致"确实需要人工确认；但在 Agent 记忆场景下，"用户先说喜欢 A 后来喜欢 B"应该自动处理为**偏好演化**而非矛盾。

**改进建议**: 引入 **双轨矛盾处理机制**：

```
企业知识矛盾（Schema 约束）:
  检测 → 生成矛盾报告 → 人工确认 → 标记 deprecated/rejected
  
Agent 记忆矛盾（信念演化）:
  检测 → 置信度比较 → 自动信念修正 → Supersedes 边链接 → 下游影响分析
```

信念修正的具体实现可参考 Kumiho：
- 新记忆到达时，检查与现有记忆的逻辑一致性
- 若矛盾，创建新修订版本，通过 `SUPERSEDES` 边链接旧版本
- `AnalyzeImpact` 遍历 `Depends_On` 边，识别所有下游结论需重新评估
- 旧版本不删除，仅通过标签指针标记为 `stale`，显式 opt-in 可检索

---

### 不足 6: L1-L4 与 Agent 记忆类型的融合断层

**问题描述**:

当前设计的 `memory_type` 类型体系（fragment/observation/entity/mental_model/episode/procedure/rule）与 Schema v2 的 L1-L4 是**并行但弱关联**的：

| memory_type | 对应 Schema 层 | 关联强度 |
|-------------|---------------|---------|
| entity | L1 EntityInstance | 强（影子节点） |
| rule | L4 RuleDefinition | 强（影子节点） |
| observation | 无直接对应 | 弱 |
| mental_model | 无直接对应 | 弱 |
| episode | 无直接对应 | 弱 |
| procedure | 无直接对应 | 弱 |
| fragment | Layer-R KnowledgeFragment | 中 |

这导致 Agent 在调用 `oe_remember(content="...")` 时，系统难以自动判断：
- 这条内容应该成为 L1 entity 还是 L3 metric？
- 这个 episode 是否应该触发 L4 rule 的更新？
- 这个 mental_model 是否应该映射为 L2 derived dimension？

**SOTA 对比**:

| 系统 | 记忆-知识融合方式 | 关键洞察 |
|------|------------------|---------|
| **Hindsight** | Observation 网络自动合成 World/Experience | 记忆网络之间自动转化 |
| **Mem0** | 事实提取后直接存入统一表，无 Schema 约束 | 扁平但灵活 |
| **BYTEROVER** | Context Tree 层级（domain→topic→subtopic）自动组织 | 层级结构天然映射到知识分类 |
| **Cognee** | `cognify` 管道自动提取→图构建→互链接 | 管道式融合 |

**深度分析**:

当前设计遵循**知识管理系统**的思维——Schema 先定义，数据后填入。但 Agent 记忆系统需要**数据驱动 Schema 演化**的能力：
- Agent 交互中自动发现的新实体类型 → 提示人类补充 L1 定义
- 频繁出现的 observation 模式 → 自动生成 L3 metric 建议
- 反复成功的 procedure → 升级为 L4 rule_logic

**改进建议**: 设计 **Schema-Memory 双向反馈环**：

```
Agent 交互数据
    ↓
[自动提取] → observation / episode / procedure
    ↓
[模式检测] → 高频模式识别（如"每3次提到X就触发Y"）
    ↓
[Schema 建议] → 向知识管理员建议新增 L1/L3/L4 定义
    ↓
[人工确认] → Schema v2 更新
    ↓
[Schema 增强记忆] → 新提取使用更新后的 Schema 结构
    ↓
[循环]
```

具体实现：
- `memory_type=observation` 的 `attributes` 中增加 `schema_alignment_score`: 0-1，表示与现有 Schema 的匹配度
- 当某类 observation 的 `schema_alignment_score` 持续高于 0.8 且数量超过阈值时，触发 Schema 建议事件
- `procedure` 类型的 `success_rate` 和 `invocation_count` 作为升级为 L4 rule_logic 的量化依据

---

### 不足 7: 反思（Reflection）的能力边界过窄

**问题描述**:

当前 `ReflectAgent` 的设计：
```python
for memory_type in ["mental_model", "entity", "observation", "fragment"]:
    type_results = await recall(query, space_id, memory_type=memory_type)
    # LLM 生成洞察、检测矛盾
```

这一设计的局限：

1. **无跨类型关联推理**: 仅按类型权重递减检索，未利用图结构进行**跨类型关联**。例如，mental_model "企业A风险高" 应与 observation "企业A负债率连续3季度上升" 和 entity "企业A(risk_grade=D)" 形成三角关联，当前设计依赖 LLM 在生成阶段发现这种关联，而非在检索阶段主动构建。

2. **无 Opinions 网络**: Hindsight 的 CARA 组件维护**观点网络（Opinion Network）**，每个观点带置信度，新证据到达时自动强化/弱化。当前设计缺乏显式的观点/信念存储层，所有"洞察"都是临时生成的文本，不持久化。

3. **无 Disposition/性格参数**: CARA 的 `skepticism/literalism/empathy` 参数使 Agent 能形成稳定的行为风格。当前设计的 Reflect 是"中性"的，缺乏**个性一致性**。

4. **反思触发被动**: 仅通过 `oe_reflect` 显式调用触发。SOTA 系统（Letta sleep-time compute、Hindsight background merging）支持**后台异步反思**。

**SOTA 对比**:

| 系统 | 反思机制 | 特色功能 |
|------|---------|---------|
| **Hindsight CARA** | Preference-conditioned generation + Opinion formation | Disposition 参数 + 观点置信度演化 |
| **Letta** | Sleep-time compute（后台异步） | Agent 自主决定何时反思 |
| **Mem0** | 无显式反思，检索时由 LLM 推理 | 依赖 ADD-only 历史保留 |
| **Kumiho** | Client-side LLM reranking | 消费 Agent 自身的 LLM 进行重排序 |
| **OntologyEngine** | 显式 oe_reflect，按类型权重检索 | 无观点持久化，无性格参数 |

**改进建议**:

1. **引入 OpinionNode** 到图 Schema：
```cypher
CREATE NODE TABLE OpinionNode (
    id STRING PRIMARY KEY,
    space_id STRING,
    opinion_text STRING,
    confidence DOUBLE,           -- 信念强度 [0,1]
    belief_type STRING,          -- preference / assessment / prediction
    supporting_evidence STRING[], -- evidence memory IDs
    contradicted_by STRING[],    -- 矛盾观点 IDs
    created_at TIMESTAMP,
    last_reinforced_at TIMESTAMP,
    reinforcement_count INT64
);
```

2. **引入 Agent Profile / Disposition**：
```yaml
agent_profile:
  disposition:
    skepticism: 3      # 1-5: 对证据的怀疑程度
    literalism: 2      # 1-5: 字面理解 vs 推断偏好
    empathy: 4         # 1-5: 共情倾向
  bias_strength: 0.5   # 0-1: 性格参数的影响强度
```

3. **后台反思调度器**：
```python
class BackgroundReflectScheduler:
    async def schedule(self, space_id):
        # 触发条件：
        # - 新记忆数 > threshold（事件触发）
        # - 定时触发（每 N 小时）
        # - 记忆库熵增检测（新记忆与现有知识冲突率高）
        if await self.should_reflect(space_id):
            await reflect_agent.reflect(space_id, mode="background")
```

---

## 四、融合演进范式探索

### 范式 A: 认知功能分层 × 存储范式矩阵（推荐探索方向）

将当前的一维分层扩展为**认知功能 × 存储范式**的矩阵架构：

```
                    向量优先      图优先        时序索引      规则引擎
感知/情景层      [Layer-R]     [EventGraph]  [Timeline]    —
                原始碎片        事件节点       时间线        
                
语义/事实层      [向量索引]     [Layer-S]     [ValidWindow] [Schema约束]
                实体嵌入        知识图谱       有效性窗口     L1-L4定义
                
观点/信念层      —             [OpinionNet]  [BeliefRev]   —
                —             置信度传播      AGM修正       
                
程序/技能层      —             [ProcedureG]  —             [RuleExec]
                —             操作模式图      —             L4执行引擎
```

**优势**: 
- 每层的存储选择最适范式，而非强行统一
- 认知功能分离使 Agent 能"选择用什么记忆回答问题"
- 与 Hindsight 四网络、MAGMA 多图正交对齐

**挑战**: 跨层一致性维护、检索路由复杂度

---

### 范式 B: Schema 作为动态认知骨架（推荐优先实施）

将 Schema v2 L1-L4 从**静态约束**提升为**动态认知组织器**：

```
用户查询: "评估企业A的信用风险"
    ↓
Schema 解析:
  L1: Counterparty 实体类型
  L2: risk_assessment 维度
  L3: credit_score (derived metric)
  L4: R001_risk_grade (rule logic)
    ↓
记忆检索路径（Schema 引导）:
  1. 实体层: 检索 Counterparty[企业A] 的当前属性
  2. 指标层: 计算/检索 credit_score 依赖的 atomic metrics
  3. 规则层: 加载 R001_risk_grade 的 execution snapshot
  4. 观察层: 检索与企业A信用相关的 observations
  5. 情景层: 检索涉及企业A的近期 episodes
    ↓
证据融合:
  Schema 依赖 DAG → 自动构建 evidence chain
  规则执行结果 + 观察摘要 + 原始碎片 → 综合回答
```

**实施要点**:
- 扩展 `SchemaLoader` 增加 `get_retrieval_plan(query)` 接口
- 在 `memory-hierarchy.md` 中显式定义 memory_type ↔ L1-L4 的映射表
- 引入 `SchemaGuidedRetriever` 作为 `QueryRouter` 的增强版

---

### 范式 C: 事件驱动的记忆生命周期（推荐中长期演进）

将当前"类型升级"（fragment→observation→entity→mental_model）的线性路径，扩展为**事件驱动的网状生命周期**：

```
                    ┌─────────────────────────────────────────┐
                    │         Event-Driven Lifecycle          │
                    └─────────────────────────────────────────┘
    
    原始输入 → [提取事件] → EventNode(occurred_at, recorded_at, participants)
                    ↓
        ┌──────────┼──────────┐
        ▼          ▼          ▼
    [观察归纳]   [实体对齐]   [因果链接]
        ↓          ↓          ↓
    Observation  Entity      CausalEdge
    (聚合事件)   (提取属性)   (事件关联)
        ↓          ↓          ↓
        └──────────┼──────────┘
                   ▼
            [反思触发]
                   ↓
        ┌──────────┼──────────┐
        ▼          ▼          ▼
    MentalModel  Opinion     Procedure
    (主题摘要)   (信念评估)   (模式提取)
        ↓          ↓          ↓
        └──────────┴──────────┘
                   ↓
            [Schema 建议]
                   ↓
            L1/L3/L4 更新建议
```

**关键创新**:
- `EventNode` 作为记忆生命周期的枢纽
- 事件不仅驱动记忆创建，还驱动**记忆更新传播**（Kumiho 的 AnalyzeImpact）
- `CausalEdge` 使 Agent 能回答"为什么"和"如何导致"

---

## 五、具体改进路线图

### Phase 2.1（近期）: 检索增强

| 改进项 | 优先级 | 参考 | 工作量 |
|--------|--------|------|--------|
| 引入实体链接层 | 高 | Mem0 | 中 |
| Schema-Aware Retrieval Router | 高 | SHARP/Kumiho | 中 |
| 时序检索提升为常驻信号 | 中 | Hindsight | 低 |
| BM25 中文分词优化 | 中 | Mem0 | 低 |
| Cross-Encoder Reranker 实现 | 中 | Hindsight/QMD | 中 |

### Phase 2.2（中期）: 时序与事件

| 改进项 | 优先级 | 参考 | 工作量 |
|--------|--------|------|--------|
| EventNode + 双时序边 | 高 | Zep/Graphiti | 大 |
| 因果边类型（CAUSES/ENABLES） | 高 | MAGMA/MAMGA | 中 |
| 叙事聚合（NARRATIVE 节点） | 中 | MAMGA | 中 |
| 后台反思调度器 | 中 | Letta/Hindsight | 中 |

### Phase 2.3（长期）: 认知架构

| 改进项 | 优先级 | 参考 | 工作量 |
|--------|--------|------|--------|
| OpinionNode + 置信度传播 | 高 | Hindsight | 大 |
| Agent Profile / Disposition | 中 | Hindsight CARA | 中 |
| 信念修正机制（AGM-lite） | 中 | Kumiho | 大 |
| Schema-Memory 双向反馈环 | 低 | 原创 | 大 |
| 四正交图实验（语义/时序/因果/实体） | 低 | MAGMA | 极大 |

---

## 六、总结

OntologyEngine 的 Agent 记忆设计在**概念框架**上迈出了关键一步（双层+标签、三操作 API、记忆生命周期），但在**实现深度**上距离 SOTA 存在结构性差距：

1. **存储分层需要认知化**: 从"存储范式差异"升级到"认知功能分离"
2. **时序建模需要事件化**: 从"有效性窗口"升级到"双时序事件网络"
3. **Schema 需要主动化**: 从"约束定义"升级到"检索引导+记忆组织"
4. **检索需要多信号化**: 从"3路静态融合"升级到"4路+实体链接+自适应"
5. **巩固需要形式化**: 从"LLM 启发式"升级到"信念修正+下游传播"
6. **反思需要人格化**: 从"中性洞察生成"升级到"观点持久化+性格参数"

**最核心的建议**: 当前设计不应追求"一个 MemoryUnit 表+标签"的极简统一，而应在**保持 Agent 认知接口简洁（remember/recall/reflect）的前提下，内部实现向多维认知架构演进**。Agent 的接口简单与内部的认知丰富并不矛盾——正如人类对外表达"我记得/我回忆/我想想"，但大脑内部的海马体-皮层系统远比这三个动词复杂。

---

## 参考文档索引

| 文档 | 位置 | 作用 |
|------|------|------|
| Agent 记忆概念框架 | `docs/01-overview/09-agent-memory.md` | 当前设计入口 |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` | MemoryUnit 模型 |
| 记忆生命周期 | `docs/02-design/agent-memory/memory-lifecycle.md` | Consolidation/Forgetting/Reflection |
| 认知操作 API | `docs/02-design/agent-memory/memory-api.md` | remember/recall/reflect |
| Schema v2 规范 | `docs/02-design/schema/01-schema-spec.md` | L1-L4 语法 |
| L1-L4 声明层 | `docs/02-design/schema/L1-L4-declarations.md` | 层间交互 |
| 查询路由 | `docs/02-design/query-engine/query-routing.md` | 查询类型识别 |
| RRF 融合 | `docs/02-design/query-engine/rrf-fusion.md` | 多路结果融合 |
| Hindsight 调研 | `docs-dev/research/hindsight-deep-analysis.md` | SOTA 参考 #1 |
| Mem0 调研 | `docs-dev/research/mem0-report/report.md` | SOTA 参考 #2 |

## Web 参考

| 来源 | 主题 | 关键洞察 |
|------|------|---------|
| Hindsight (arXiv:2512.12818) | 四网络+TEMPR+CARA | 认知功能分离、观点置信度演化 |
| Mem0 Token-Efficient Algorithm | ADD-only + 实体链接 | 单次提取、历史保留、3-4倍 token 节省 |
| Zep/Graphiti (arXiv:2501.13956) | 时序知识图谱 | 双时序模型、三元混合检索、P95=300ms |
| MAGMA (arXiv:2601.03236) | 四正交图 | 语义/时序/因果/实体分离、策略引导遍历 |
| Kumiho (arXiv:2603.17244) | AGM 信念修正 | Supersedes 边、AnalyzeImpact、LoCoMo-Plus 93.3% |
| CLAG (arXiv:2603.15421) | Agent 驱动聚类 | 两阶段检索（聚类→细粒度）、局部演化 |
| Memory Survey (arXiv:2603.07670) | 全面综述 | write-manage-read 循环、5 机制家族 |
| BYTEROVER | Context Tree | 层级检索、时序 94.4%、多跳 85.1% |

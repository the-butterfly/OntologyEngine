# 互索引边 Grammar

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/05-concepts.md` + `docs/01-overview/08-knowledge-retrieval.md` | **last_verified**: 2026-04-19

## 目的

定义 Layer-R 与 Layer-S 之间的四种互索引边类型，建立结构化知识与原始知识碎片之间的双向可追溯链接。互索引边是 OntologyEngine 双层协同架构的核心纽带——它使 Layer-S 的推理结果可以追溯到 Layer-R 的原始证据，也使 Layer-R 的碎片可以导航到 Layer-S 的结构化实体。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | canonical spec 无互索引边语法 | Layer-R 与 Layer-S 在数据层面完全断连，无法协同检索 |
| 2 | 推理结果不可解释 | 无法回答"这个结论来自哪个文档的哪个段落" |
| 3 | 文档碎片无法导航到业务实体 | 向量检索返回碎片后，无法自动扩展到关联的结构化知识 |
| 4 | 规则/指标的定义来源不可追溯 | 规则变更时无法定位原始定义文档，影响合规审计 |
| 5 | 边缺乏语义表达 | 互索引边只是简单链接，无法参与向量检索和成本传播 |

---

## 四种互索引边类型

### 总览

| 边类型 | 方向 | 语义 | 场景示例 |
|--------|------|------|----------|
| EXTRACTED_FROM | EntityInstance → KnowledgeFragment | "这个实体来自哪个文档的哪个段落" | 授信规则 R001 定义在《授信管理办法》第 3.2 节 |
| SUPPORTED_BY | KnowledgeFragment → EntityInstance | "这个文档片段支撑了哪个业务判断" | 审查意见（个人笔记）支撑了高风险归类 |
| DEFINED_IN | RuleDefinition / MetricDeclaration → KnowledgeFragment | "这条规则/公式的定义来源" | 信用分公式定义在《风险评分模型 v2.1》 |
| TRACE_TO | ExecutionStepSnapshot → KnowledgeFragment | "这个决策可追溯到哪些原始材料" | 授信额度 500 万 → 企业财报 + 评分卡文档 + 审批记录 |

### 方向语义图

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer-S（结构化知识层）                                          │
│                                                                  │
│  EntityInstance ◀──── SUPPORTED_BY ────┐                        │
│       │                                │                        │
│       │ EXTRACTED_FROM                 │                        │
│       ▼                                │                        │
│  KnowledgeFragment ──── SUPPORTED_BY ──┘                        │
│       ▲                                │                        │
│       │ DEFINED_IN                     │                        │
│       │                                │                        │
│  RuleDefinition                        │                        │
│  MetricDeclaration                     │                        │
│       ▲                                │                        │
│       │ TRACE_TO                       │                        │
│       │                                │                        │
│  ExecutionStepSnapshot                 │                        │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Layer-R（原始知识层）                                            │
│                                                                  │
│  KnowledgeFragment ← 所有互索引边的 Layer-R 端点                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 公共边字段

### 目的

定义四种互索引边共享的字段结构，确保统一的溯源粒度、置信度表达和语义检索能力。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 溯源粒度不一致 | source_file + offset_start + offset_end 实现段落级精确定位 |
| 2 | 置信度缺乏统一标签 | confidence + 标签体系（EXTRACTED / INFERRED / AMBIGUOUS） |
| 3 | 边无法参与向量检索 | edge_text 向量化后存入 ChromaDB，参与 Bundle Search |

### 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string | 是 | — | 唯一标识 |
| `from_id` | string | 是 | — | 源端节点 ID |
| `to_id` | string | 是 | — | 目标端节点 ID |
| `edge_type` | enum | 是 | — | EXTRACTED_FROM \| SUPPORTED_BY \| DEFINED_IN \| TRACE_TO |
| `source_file` | string | 是 | — | 来源文件路径 |
| `offset_start` | integer | 是 | — | 字符偏移起始 |
| `offset_end` | integer | 是 | — | 字符偏移终止 |
| `confidence` | float | 是 | — | 置信度，配合标签体系解读 |
| `edge_text` | string? | 否 | null | 边语义文本，向量化后参与 Bundle Search |
| `created_at` | datetime | 是 | — | 边创建时间 |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-MI-1 | `from_id` 和 `to_id` 必须引用已存在的节点 | 引用完整性 |
| V-MI-2 | `edge_type` ∈ {EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO} | 类型枚举约束 |
| V-MI-3 | `offset_end` > `offset_start` | 偏移区间语义正确 |
| V-MI-4 | `confidence` ∈ [0, 1] | 置信度范围约束 |
| V-MI-5 | `source_file` 不能为空字符串 | 溯源必须有文件来源 |
| V-MI-6 | `from_id` ≠ `to_id` | 禁止自环 |

---

## EXTRACTED_FROM

### 目的

记录 EntityInstance 是从哪个 KnowledgeFragment 提取而来。这是 Layer-R → Layer-S 的主要桥接边，回答"这个实体来自哪个文档的哪个段落"。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 实体来源不可追溯 | EXTRACTED_FROM 边指向原始碎片，精确定位到段落级偏移 |
| 2 | 向量检索结果无法扩展到结构化知识 | 通过 EXTRACTED_FROM 反向导航（SUPPORTED_BY），实现碎片→实体的扩展 |

### 类型约束

| 约束 | 值 |
|------|-----|
| from_id 类型 | EntityInstance.id |
| to_id 类型 | KnowledgeFragment.id |
| 方向 | Layer-S → Layer-R |

### 场景示例

```
EntityInstance[id="ent_001", _fact_object="finance:Counterparty"]
  ──[EXTRACTED_FROM]──▶
KnowledgeFragment[id="frag_042", document_id="授信管理办法.pdf", offset_start=3200, offset_end=3580]
  edge_text: "交易对手基本信息从授信管理办法第3.2节提取"
  confidence: 1.0 (AST 确定性提取)
```

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-EF-1 | `from_id` 必须引用 EntityInstance | 源端类型约束 |
| V-EF-2 | `to_id` 必须引用 KnowledgeFragment | 目标端类型约束 |
| V-EF-3 | `to_id` 对应的 KnowledgeFragment.extraction_status 必须为 "extracted" | 只能关联已提取的碎片 |

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| m_flow `includes_chunk` | m_flow 的 Episode → ContentFragment 关联边，OntologyEngine 将其泛化为 EntityInstance → KnowledgeFragment |
| KAG ExternalGraphLoader | KAG 的外部图加载器通过 MatchConfig 将 Chunk 中的实体链接到 KnowledgeUnit，OntologyEngine 的 EXTRACTED_FROM 是显式边而非隐式链接 |
| Cognee source_pipeline | Cognee 的 DataPoint 溯源链模式，OntologyEngine 在边级别复用，增加 offset 信息实现段落级溯源 |

---

## SUPPORTED_BY

### 目的

记录 KnowledgeFragment 支撑了哪个 EntityInstance 的业务判断。这是 EXTRACTED_FROM 的反向导航边，回答"这个文档片段支撑了哪个业务判断"。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 文档碎片的业务价值不明确 | SUPPORTED_BY 边将碎片与业务实体关联，明确碎片的业务上下文 |
| 2 | 证据链单向不可逆 | EXTRACTED_FROM 只能从实体找碎片，SUPPORTED_BY 补充从碎片找实体的反向导航 |

### 类型约束

| 约束 | 值 |
|------|-----|
| from_id 类型 | KnowledgeFragment.id |
| to_id 类型 | EntityInstance.id |
| 方向 | Layer-R → Layer-S |

### 场景示例

```
KnowledgeFragment[id="frag_078", document_id="审查意见_2024Q4.docx", offset_start=150, offset_end=420]
  ──[SUPPORTED_BY]──▶
EntityInstance[id="ent_023", _fact_object="finance:Counterparty"]
  edge_text: "审查意见指出该客户存在关联交易风险，支撑高风险归类"
  confidence: 0.85 (LLM 语义推断)
```

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-SB-1 | `from_id` 必须引用 KnowledgeFragment | 源端类型约束 |
| V-SB-2 | `to_id` 必须引用 EntityInstance | 目标端类型约束 |

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| m_flow `supported_by` | m_flow 的 ContentFragment → Facet 关联边，OntologyEngine 扩展为双向可导航（m_flow 是单向的） |
| m_flow edge_text | m_flow 的边语义文本模式，OntologyEngine 增加 weight + attributes，使边语义更丰富 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-SB-1 | SUPPORTED_BY 与 EXTRACTED_FROM 是独立边而非同一条边的双向属性 | 语义不同：EXTRACTED_FROM 表示提取来源（确定性），SUPPORTED_BY 表示支撑关系（可能为推断）；置信度可能不同 |
| D-SB-2 | SUPPORTED_BY 的 confidence 通常低于 EXTRACTED_FROM | 提取是确定性操作（AST），支撑关系可能是 LLM 推断的语义关联 |

---

## DEFINED_IN

### 目的

记录 RuleDefinition 或 MetricDeclaration 的定义来源——即规则/指标定义在哪个文档的哪个段落。这是 L4/L3 声明层到 Layer-R 的桥接边，回答"这条规则/公式的定义来源"。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 规则定义来源不可追溯 | DEFINED_IN 边指向原始文档碎片，支持合规审计 |
| 2 | 规则变更时无法定位原始定义文档 | 通过 DEFINED_IN 边快速定位定义来源，评估变更影响 |
| 3 | 指标公式缺乏权威来源 | DEFINED_IN 边关联公式定义文档，增强指标可信度 |

### 类型约束

| 约束 | 值 |
|------|-----|
| from_id 类型 | RuleDefinition.id 或 MetricDeclaration.id |
| to_id 类型 | KnowledgeFragment.id |
| 方向 | Layer-S（声明层）→ Layer-R |

### 场景示例

```
RuleDefinition[id="rule_001", name="风险等级评定"]
  ──[DEFINED_IN]──▶
KnowledgeFragment[id="frag_015", document_id="风险评分模型v2.1.pdf", offset_start=8900, offset_end=9350]
  edge_text: "风险等级评定规则定义在风险评分模型v2.1第4.1节"
  confidence: 1.0 (确定性引用)
```

```
MetricDeclaration[id="metric_credit_score", name="credit_score"]
  ──[DEFINED_IN]──▶
KnowledgeFragment[id="frag_022", document_id="信用评分方法论.pdf", offset_start=1200, offset_end=1800]
  edge_text: "信用评分公式定义在信用评分方法论第2章"
  confidence: 1.0 (确定性引用)
```

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-DI-1 | `from_id` 必须引用 RuleDefinition 或 MetricDeclaration | 源端类型约束 |
| V-DI-2 | `to_id` 必须引用 KnowledgeFragment | 目标端类型约束 |
| V-DI-3 | confidence 通常为 1.0 | 规则/指标的定义来源通常是确定性引用 |

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| m_flow `derived_procedure` | m_flow 的 FacetPoint → Procedure 关联边，OntologyEngine 将其泛化为声明→碎片的溯源 |
| Cognee source_pipeline | Cognee DataPoint 的溯源链模式，OntologyEngine 在边级别实现，增加 offset 实现段落级定位 |

---

## TRACE_TO

### 目的

记录 ExecutionStepSnapshot 可追溯到哪些原始 KnowledgeFragment。这是推理链到原始证据的桥接边，回答"这个决策可追溯到哪些原始材料"。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 推理结果不可解释 | TRACE_TO 边将推理步骤关联到原始碎片，构建完整证据链 |
| 2 | 审计缺乏证据支撑 | 通过 TRACE_TO 边追溯每个决策步骤的原始依据 |
| 3 | 推理链与原始数据断裂 | TRACE_TO 边连接 Layer-S 的推理层与 Layer-R 的数据层 |

### 类型约束

| 约束 | 值 |
|------|-----|
| from_id 类型 | ExecutionStepSnapshot.id |
| to_id 类型 | KnowledgeFragment.id |
| 方向 | Layer-S（推理层）→ Layer-R |

### 场景示例

```
ExecutionStepSnapshot[id="snap_001", rule_id="R001_risk_grade", step_index=3]
  ──[TRACE_TO]──▶
KnowledgeFragment[id="frag_001", document_id="企业A_2024年报.pdf", offset_start=4500, offset_end=4900]
  edge_text: "授信额度决策基于企业A 2024年报财务数据"
  confidence: 0.9 (推断关联)

ExecutionStepSnapshot[id="snap_001"]
  ──[TRACE_TO]──▶
KnowledgeFragment[id="frag_002", document_id="评分卡文档v3.pdf", offset_start=200, offset_end=580]
  edge_text: "评分卡文档定义了信用评分计算方法"
  confidence: 0.95 (确定性关联)

ExecutionStepSnapshot[id="snap_001"]
  ──[TRACE_TO]──▶
KnowledgeFragment[id="frag_003", document_id="审批记录_2024Q4.pdf", offset_start=100, offset_end=350]
  edge_text: "审批记录确认了最终授信额度"
  confidence: 1.0 (确定性引用)
```

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-TT-1 | `from_id` 必须引用 ExecutionStepSnapshot | 源端类型约束 |
| V-TT-2 | `to_id` 必须引用 KnowledgeFragment | 目标端类型约束 |
| V-TT-3 | 一个 ExecutionStepSnapshot 可以有多条 TRACE_TO 边 | 推理步骤可能依赖多个原始材料 |

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| m_flow `derived_procedure` | m_flow 的 Procedure 执行追溯模式，OntologyEngine 扩展为步骤级（而非过程级）的碎片关联 |
| KAG AtomicQuery | KAG 的 AtomicQuery 同时桥接 query→KU→chunk，OntologyEngine 将追溯拆分为独立的 TRACE_TO 边，粒度更细 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-TT-1 | TRACE_TO 的源端是 ExecutionStepSnapshot 而非 RuleDefinition | 规则定义是静态的（用 DEFINED_IN），推理步骤是动态的（用 TRACE_TO）；同一规则在不同实体上执行可能追溯到不同碎片 |
| D-TT-2 | 允许一个步骤关联多个碎片 | 推理步骤可能综合多个来源做出判断，每个来源都需要被记录 |

---

## 置信度标签体系

### 目的

为互索引边的 confidence 字段提供统一的语义解读框架，区分确定性提取、语义推断和模糊匹配。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | confidence 数值缺乏语义解读 | 标签体系将数值范围映射到语义类别 |
| 2 | 不同来源的边置信度不可比 | 统一标签体系确保跨来源可比性 |
| 3 | 低置信度边缺乏处理策略 | AMBIGUOUS 标签触发人工审查流程 |

### 标签定义

| 标签 | confidence 范围 | 语义 | 典型场景 | 后续动作 |
|------|----------------|------|----------|----------|
| EXTRACTED | 1.0 | AST 确定性提取 | 结构化数据直接映射、规则定义引用 | 无需审查 |
| INFERRED | 0.4-0.9 | LLM 语义推断 | LLM 提取的实体关系、支撑关系推断 | 可选审查 |
| AMBIGUOUS | 0.1-0.3 | 模糊匹配 | 低置信度实体链接、跨域对齐 | 必须人工审查 |

### 标签与边类型的典型组合

| 边类型 | EXTRACTED | INFERRED | AMBIGUOUS |
|--------|-----------|----------|-----------|
| EXTRACTED_FROM | ✅ 典型 | ⚠️ 少见（LLM 提取时） | ❌ 不应出现 |
| SUPPORTED_BY | ⚠️ 少见 | ✅ 典型 | ⚠️ 可能 |
| DEFINED_IN | ✅ 典型 | ⚠️ 少见 | ❌ 不应出现 |
| TRACE_TO | ⚠️ 少见 | ✅ 典型 | ⚠️ 可能 |

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| Graphify | Graphify validate_extraction() 要求每条边携带 confidence，AMBIGUOUS 边标记为需人工审查 |
| Cognee | Cognee 的 feedback_weight 机制可调整边的置信度，OntologyEngine 将置信度标签化 |

---

## Bundle Search 集成

### 目的

定义互索引边如何参与 Bundle Search 的向量检索和成本传播，使边语义成为检索评分的一等公民。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 互索引边不参与检索评分 | edge_text 向量化后存入 ChromaDB，参与 Bundle Search |
| 2 | 边类型不影响路径成本 | 不同边类型在成本传播中赋予不同权重 |
| 3 | Layer-R/Layer-S 协同检索缺乏成本模型 | 互索引边作为跨层跳转边，纳入统一成本传播 |

### edge_text 向量化

```
互索引边创建时：
  1. edge_text 非空 → 调用 embedding 模型生成向量
  2. 向量存入 ChromaDB，collection = "edge_text"
  3. metadata 包含：edge_type, from_id, to_id, confidence
  4. vector_id 回写到边的存储记录

Bundle Search Phase 1（宽网撒播）：
  查询嵌入同时搜索：
  [entity_name, entity_summary, facet_search_text, edge_text, knowledge_fragment, rule_definition]
  每个集合返回最多 100 个候选

Bundle Search Phase 2（投影到图）：
  命中的互索引边作为跨层跳转入口
  EXTRACTED_FROM 命中 → 从 Layer-R 跳转到 Layer-S
  SUPPORTED_BY 命中 → 从 Layer-S 跳转到 Layer-R
```

### 路径成本计算

```
路径成本 = 起始节点向量距离
         + Σ(边向量距离 + 跳数惩罚 + 边类型权重调整)
         + miss_penalty（边未被向量检索命中的惩罚）

互索引边的跳数惩罚：
  同层内跳转：hop_penalty = 0.05
  跨层跳转（经互索引边）：hop_penalty = 0.15  ← 跨层跳转成本更高

互索引边的 miss_penalty：
  EXTRACTED_FROM：0.5  ← 实体通常有明确来源
  SUPPORTED_BY：0.7    ← 支撑关系可能不唯一
  DEFINED_IN：0.3      ← 规则定义来源通常明确
  TRACE_TO：0.6        ← 推理追溯可能多路径
```

### 五种路径类型映射

Bundle Search 的五种路径类型在 OntologyEngine 中的映射：

| m_flow 路径类型 | OntologyEngine 映射 | 涉及的互索引边 |
|-----------------|---------------------|---------------|
| direct_episode | 直接命中 EntityInstance | 无 |
| facet | Categorization → EntityInstance | 无 |
| point | AnalyticalElement → Categorization → EntityInstance | 无 |
| entity | EntityInstance 直接命中 | 无 |
| facet_entity | EntityInstance → Categorization → EntityInstance | 无 |
| **跨层路径（新增）** | **KnowledgeFragment → EXTRACTED_FROM → EntityInstance** | EXTRACTED_FROM |
| **跨层路径（新增）** | **EntityInstance → SUPPORTED_BY → KnowledgeFragment** | SUPPORTED_BY |
| **跨层路径（新增）** | **RuleDefinition → DEFINED_IN → KnowledgeFragment** | DEFINED_IN |
| **跨层路径（新增）** | **ExecutionStepSnapshot → TRACE_TO → KnowledgeFragment** | TRACE_TO |

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| m_flow Bundle Search | m_flow 的四阶段算法（宽网撒播→投影到图→代价传播→排序组装），OntologyEngine 增加互索引边作为跨层跳转边 |
| m_flow edge_text | m_flow 的边语义向量化模式，OntologyEngine 将其扩展到互索引边 |
| KAG DPR+PPR+RRF | KAG 的五步混合检索，OntologyEngine 的互索引边参与 PPR 概率传播 |

---

## 协同检索流程

### 目的

展示互索引边如何驱动 Layer-R 与 Layer-S 的协同检索，实现"检索→推理→回溯"的完整闭环。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 双层检索缺乏桥接机制 | 互索引边作为跨层导航的显式链接 |
| 2 | 检索结果缺乏证据链 | TRACE_TO 边构建从推理结果到原始碎片的证据链 |

### 典型流程：客户风险分析

```
查询：explain_risk(customer_id="A")

Step 1 — Layer-R 检索：
  query_raw("企业A 财务 风险")
  → frag_001: "2024年报：营收3.2亿，资产负债率65%..."
  → frag_002: "征信报告：逾期2次，最高90天..."

Step 2 — SUPPORTED_BY 扩展（Layer-R → Layer-S）：
  frag_001 ──[SUPPORTED_BY]──▶ ent_A_financial
  frag_002 ──[SUPPORTED_BY]──▶ ent_A_credit

Step 3 — Layer-S 推理：
  MetricEngine 计算：debt_ratio=0.65, credit_score=0.55
  RuleEngine 执行：IF compliance_score < 40 → risk_level = "D"
  产出 ExecutionStepSnapshot

Step 4 — TRACE_TO 回溯（Layer-S → Layer-R）：
  ExecutionStepSnapshot ──[TRACE_TO]──▶ frag_001
  ExecutionStepSnapshot ──[TRACE_TO]──▶ frag_002

Step 5 — 输出：
  risk_level: D
  evidence: [frag_001, frag_002]
  execution_snapshot: {...}
  trace_chain: [snap → frag_001, snap → frag_002]
```

### 查询路由与互索引边

| 查询类型 | 使用的互索引边 | 检索路径 |
|----------|---------------|----------|
| factual | EXTRACTED_FROM | Layer-R 向量检索 → EXTRACTED_FROM 扩展到 EntityInstance |
| multi-hop | 无直接使用 | Layer-S 图遍历，互索引边参与 Bundle Search |
| temporal | EXTRACTED_FROM | valid_from/to 过滤 → EXTRACTED_FROM 扩展 |
| analytical | TRACE_TO | L4 RuleEngine 执行 → TRACE_TO 回溯碎片证据 |
| mixed | 全部四种 | Layer-R → SUPPORTED_BY → Layer-S → TRACE_TO → Layer-R |

---

## 存储实现

### 目的

定义互索引边在 KuzuDB 和 ChromaDB 中的存储方式。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 互索引边缺乏存储模型 | KuzuDB 关系表 + ChromaDB 向量集合的双存储 |
| 2 | 边语义无法被向量检索 | edge_text 向量化存入 ChromaDB |

### KuzuDB 存储

```
关系类型：EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO

每条边属性：
  id: STRING (PK)
  from_id: STRING
  to_id: STRING
  source_file: STRING
  offset_start: INT64
  offset_end: INT64
  confidence: DOUBLE
  edge_text: STRING
  created_at: DATETIME

索引：
  - (from_id, edge_type) 组合索引：支持从源端查找所有出边
  - (to_id, edge_type) 组合索引：支持从目标端查找所有入边
  - confidence 索引：支持按置信度过滤
```

### ChromaDB 存储

```
Collection: "edge_text"

每条记录：
  id: 边的 vector_id
  embedding: edge_text 的向量嵌入
  metadata: {
    edge_type: "EXTRACTED_FROM" | "SUPPORTED_BY" | "DEFINED_IN" | "TRACE_TO",
    from_id: string,
    to_id: string,
    confidence: float,
    source_file: string
  }

查询：
  向量检索 + metadata 过滤（edge_type, confidence 阈值）
```

### 参考项目对齐

| 参考项目 | 对齐说明 |
|----------|----------|
| KAG KnowledgeUnit | KAG 的 Chunk → KnowledgeUnit 桥接存储，OntologyEngine 使用 KuzuDB 关系表替代 |
| m_flow Episode/Facet | m_flow 的 Episode → ContentFragment 关联存储，OntologyEngine 增加向量索引 |
| Cognee DataPoint | Cognee 的 source_pipeline 溯源链存储模式 |

---

## 与 Instance 层的关系

互索引边的端点是 Instance 层的数据结构。完整 Instance 层定义见 `docs/02-design/schema/instance-layer.md`。

| 互索引边类型 | 源端（Instance 层） | 目标端（Instance 层） |
|-------------|--------------------|-----------------------|
| EXTRACTED_FROM | EntityInstance | KnowledgeFragment |
| SUPPORTED_BY | KnowledgeFragment | EntityInstance |
| DEFINED_IN | RuleDefinition / MetricDeclaration | KnowledgeFragment |
| TRACE_TO | ExecutionStepSnapshot | KnowledgeFragment |

### 引用完整性

```
互索引边写入时：
  1. 验证 from_id 和 to_id 引用的节点存在
  2. 验证节点类型匹配边类型的约束
  3. 验证 confidence 在合法范围内
  4. edge_text 非空时触发向量化流程

节点删除时：
  1. 级联删除所有引用该节点的互索引边
  2. 级联删除 ChromaDB 中对应的向量记录
```

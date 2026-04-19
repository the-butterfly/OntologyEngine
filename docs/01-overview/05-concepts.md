# 核心概念

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档（术语定义） | **last_verified**: 2026-04-19
> **[关键设计点]**: 本文档基于 Schema v2 四层架构定义核心术语，作为项目唯一术语规范入口
> **[单一事实源]**: 术语定义与 Schema v2 规范保持一致，详见 `docs/05-schema-v2/09-canonical-schema-spec.md`

## 术语对照表

| 旧术语（MVP） | 新术语（Schema v2） | 说明 |
|--------------|-------------------|------|
| Concept | **Fact Object** | 领域模型的核心抽象，定义业务实体的结构和关系 |
| Entity | **Entity Instance** | Fact Object 的具体数据实例 |
| Metric | **Analytical Element** | 分析要素（细分：Metric / Indicator / Scorecard） |
| Dimension（分析维度）| **Categorization** | 分类体系，用于组织和筛选分析视角 |
| ~~Concept（独立层）~~ | **L2 tag_based** | **[废弃] SemanticConcept 不作为独立层，tag_based 承担标签功能** |
| Rule / RuleGroup | **Rule Definition + Rule Logic** | 规则定义与规则逻辑分离 |
| Ruleset | **Business Logic** | 逐步淡出，统一使用业务逻辑层术语 |
| Attribute | **Attribute** | 保持不变，Fact Object 的属性定义 |
| Relation | **Relation** | 保持不变，Fact Object 之间的关系定义 |

### SemanticConcept 决策（2026-04-19）

**采用方案 A1**：废弃独立 Concept 层，L2 `tag_based` + L3 `indicator` 承担标签功能。

**原因**：
- 本地知识库场景够用
- 未来需要跨域泛化时，做多 Space 知识融合即可

**参考**：LLM-Wiki 的 `concepts/` 目录本质上是主题标签，与 L2 `tag_based` 等效。

---

## Layer-R 与 Layer-S：知识的两层认知分工

### 为什么需要两层

企业知识以两种形态并存：

| 形态 | 内容 | 特征 | 适用场景 |
|------|------|------|---------|
| **原始形态** | 制度文件、财务报表、API 响应 | 丰富、非结构化、来源多样 | 探索性查询、原文证据 |
| **结构化形态** | Entity 实例、Rule 定义、Indicator 值 | 精确、可推理、可执行 | 确定性计算、合规审计 |

传统系统二选一：**只做知识图谱**（丢失碎片上下文）**或只做文档检索**（无法结构化推理）。OntologyEngine 的选择：**双层共存，认知分工，协同推理**。

### Layer-R：原始知识层（Raw Knowledge Layer）

**存储单元**：`KnowledgeFragment`（知识碎片）—— 原文块 + 向量嵌入 + 元数据

**核心启示来自 MemPalace**：原文块存储 + 向量检索在垂直领域可达 96.6% R@5 基线，无需强制 LLM 提取。Layer-R 支持"原文优先"模式，对特定领域可选择不做提取，直接对碎片建向量索引。

### Layer-S：结构化知识层（Structured Knowledge Layer）

**存储单元**：`EntityInstance / RelationInstance / RuleDefinition` —— Schema 驱动的结构化数据

**核心启示来自 KAG + m_flow**：Layer-S 是 Schema 约束的结构化知识，推理结果可解释、可审计。规则引擎执行 DAG，ExecutionStepSnapshot 实现全链路追溯。

### 两层协同

```
查询"分析企业A的税务风险"
     ↓
Layer-R 检索：向量 + 关键词 → 相关碎片（年报 PDF、申报记录）
     ↓
extracted_from 边：碎片 → 对应 EntityInstance（税务指标实体）
     ↓
Layer-S 推理：EntityInstance → Indicator 计算 → RuleEngine 执行
     ↓
trace_to 边：推理步骤 → 来源碎片（提供证据）
     ↓
输出：税务风险结论 + 证据链 + 可信度评分
```

### 业界对齐

| 系统 | Layer-R 对应 | Layer-S 对应 |
|------|------------|------------|
| MemPalace | Drawer（原文块 + ChromaDB）| SQLite KG（实体三元组）|
| MAMGA | EventNode（原始内容）| EpisodeNode + SessionNode |
| LLM-Wiki | wiki/pages/（原始 md）| entity/concept pages |
| m_flow | ContentFragment | Episode/Facet/FacetPoint/Entity |
| KAG | Chunk | KnowledgeUnit + AtomicQuery |
| OntologyEngine | KnowledgeFragment | L1-L4 四层结构 |

---

## Dataset（数据集元数据声明）

**Dataset 是对外部原始数据源的元数据声明，不是数据副本**。它告诉 OntologyEngine "数据在哪里、如何访问"，而非"数据本身"。

### 设计原则

- **数据主权**：原始数据保留在源系统，不复制
- **新鲜度**：始终访问最新数据，无需同步
- **权限**：沿用源系统权限

### Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `source_type` | enum | table / api / file / stream |
| `source_uri` | string | 访问 URI |
| `linkage_targets` | list[schema_id] | 链接到的 Schema 定义 |
| `metadata` | object | owner、tags、sensitivity_level 等 |

### 与存储的关系

```
Dataset（声明）
  └── linkage_targets → Schema ID
       ↓
  实际数据（外部系统：MySQL/API/File）
       ↓ IngestionService
  KnowledgeFragment（Layer-R 存储）
       ↓ extracted_from 边
  EntityInstance（Layer-S 实体）
```

---

## KnowledgeFragment（知识碎片）

Layer-R 的存储单元，从 Dataset 或非结构化文档中提取的最小可检索单元。

### Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `dataset_id` | string | 所属 Dataset |
| `document_id` | string | 来源文档 ID |
| `chunk_index` | int | 文档内块序号 |
| `offset_start` | int | 块在文档中的字符偏移（起点）|
| `offset_end` | int | 块在文档中的字符偏移（终点）|
| `text` | string | **原文内容**（Layer-R 核心）|
| `vector_id` | string | ChromaDB/FAISS 向量 ID（按规模选择） |
| `metadata` | object | author、date、tags 等 |
| `extraction_status` | enum | pending / extracted / failed |

### 块切分策略

```
文档：默认 800 字符块，100 字符 overlap，优先段落边界切分
表格式数据：每行作为一个 Fragment
API 响应：每个字段值作为一个 Fragment
```

---

## 互索引（Mutual Indexing）

结构化知识与知识碎片之间的**双向可追溯链接**。

### 四种互索引关系

| 关系类型 | 方向 | 含义 | 场景示例 |
|----------|------|------|----------|
| `extracted_from` | 实体 → 碎片 | "这个实体来自哪个文档的哪个段落" | 授信规则 R001 定义在《授信管理办法》第 3.2 节 |
| `supported_by` | 碎片 → 实体 | "这个文档片段支撑了哪个业务判断" | 审查意见（个人笔记）支撑了高风险归类 |
| `defined_in` | 规则/指标 → 碎片 | "这条规则/公式的定义来源" | 信用分公式定义在《风险评分模型 v2.1》 |
| `trace_to` | 推理步骤 → 碎片 | "这个决策可追溯到哪些原始材料" | 授信额度 500 万 → 企业财报 + 评分卡文档 + 审批记录 |

### 与 KAG AtomicQuery 的对比

| 维度 | KAG | OntologyEngine |
|------|-----|----------------|
| **桥接结构** | AtomicQuery 同时桥接 query→KU→chunk | 四种专门关系分立 |
| **溯源粒度** | chunk 级别 | **块 + 段落偏移**（offset_start/end）|
| **设计目的** | 检索效率优先 | **推理可解释性优先** |

### 与 m_flow `supported_by` 的对比

| 维度 | m_flow | OntologyEngine |
|------|--------|----------------|
| **方向** | 单向（碎片 → Facet） | **双向可导航** |
| **语义丰富度** | edge_text | edge_text + weight + attributes |
| **推理参与** | 无语义权重 | **边语义参与推理成本传播** |

### 技术实现框架

```
互索引存储实现（参考 KAG KnowledgeUnit + m_flow Episode/Facet）：

KuzuDB 存储：
  - 互索引边作为独立关系类型存储（EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO）
  - 每条边携带：source_file, offset_start, offset_end, confidence, edge_text
  - 边文本向量化后存入 ChromaDB，参与 Bundle Search 评分

KAG 五层图结构对比：
  Chunk → KnowledgeUnit → AtomicQuery → Entity → SemanticConcept
  OntologyEngine 对应：
  KnowledgeFragment → EntityInstance → (互索引边) → RuleDefinition

Cognee DataPoint 溯源模式：
  source_pipeline: 来源管道
  source_task: 来源任务
  source_user: 来源用户
  source_content_hash: 内容哈希
  → OntologyEngine 互索引边可复用此模式，增加 source_document_id + offset 信息
```

---

## 矛盾检测（Contradiction Detection）

同一业务实体从不同来源获取时可能产生矛盾（如 CRM 与 ERP 的客户地址不一致）。

### 检测机制

**Ingestion 时（阻止写入）**：
```
新知识 → 与已有知识比对 → 发现矛盾
  → 阻止写入，生成 contradiction_report
  → 通知知识管理员
  → 人工确认：
     ① 接受新，废弃旧（标记 deprecated）
     ② 保留旧，丢弃新（标记 rejected）
     ③ 修改后接受（手动编辑解决矛盾）
```

**后台异步扫描（定期）**：夜间批次检测，发现矛盾通知管理员，不阻塞日常查询。

### Query 结果展示

Query 结果忠实展示，不主动过滤矛盾。可选返回 `contradiction_warnings`：

```json
{
  "result": {...},
  "contradiction_warnings": [
    {
      "type": "value_conflict",
      "entity_id": "ent_001",
      "field": "address",
      "sources": {
        "ds_crm": "北京市朝阳区建国路88号",
        "ds_erp": "北京市海淀区中关村大街1号"
      }
    }
  ]
}
```

### 技术实现框架

```
矛盾检测实现（参考 LLM-Wiki-Agent + Graphify）：

Ingest 时检测（参考 LLM-Wiki-Agent ingest.py）：
  - LLM 编译时同时对比现有 Wiki 内容，输出 contradictions 数组
  - 矛盾在摄入时就被标记，而非查询时才发现
  - 源页面模板中有专门的 ## Contradictions 区块

Lint 时检测（参考 LLM-Wiki-Agent lint.py）：
  - 采样 ≤20 页面，截断到 1500 字符
  - LLM 语义检查：跨页面矛盾、过时内容、数据缺口、概念深度不足
  - 同时包含确定性检查：孤儿页面、断裂链接、缺失实体页面

Graph-Aware 检测（参考 LLM-Wiki-Agent lint.py）：
  - Hub Stub 检测：度数 > μ+2σ 但内容 < 500 字符的节点
  - 脆弱桥检测：社区间仅靠 1 条边连接
  - 孤立社区检测：零外部连接的知识孤岛

Graphify 验证模式（参考 validate.py）：
  - validate_extraction() 强制执行 schema
  - 确保每个节点有 {id, label, file_type, source_file}
  - 确保每条边有 {source, target, relation, confidence, source_file}
  - AMBIGUOUS 边标记为需人工审查

OntologyEngine 矛盾检测策略：
  - Ingest 时：LLM 编译 + SHA256 哈希比对
  - Lint 时：采样语义检查 + 确定性检查
  - Graph-Aware：Hub Stub + 脆弱桥 + 孤立社区
  - 矛盾报告存储：SQLite contradiction_reports 表
  - 矛盾解决：人工确认后标记 deprecated/rejected/modified
```

---

## 时序建模（Temporal Modeling）

### 两种实体

| 类型 | 时序标注 | 示例 |
|------|---------|------|
| **静态实体**（static） | 无需时序 | 法人姓名、营业执照号 |
| **时序实体**（temporal） | valid_from / valid_to | 注册资本、营收数据、担保敞口 |

### 时序字段

```yaml
# FactObjectDefinition 中声明
fact_object:
  id: "finance:Company"
  temporal: true

# EntityInstance 中记录
entity_instance:
  id: "ent_001"
  _fact_object: "finance:Company"
  registered_capital: 50000000
  valid_from: "2025-06-01"   # null = 从创建起生效
  valid_to: null              # null = 当前有效
```

### 查询语义

| 查询 | 语义 | 实现 |
|------|------|------|
| `query_entity(id)` | 返回当前版本 | `WHERE valid_to IS NULL` |
| `query_entity(id, as_of=date)` | 返回指定时点 | 时序过滤 |
| `query_entity(id, include_history=true)` | 返回所有历史版本 | 全量返回 |

**默认行为**：返回当前版本。若结果为空，调用方显式查询历史版本。

### 技术实现框架

```
时序存储实现（参考 MAMGA + MemPalace）：

MAMGA 时序共振图模式：
  - EVENT 节点通过 PRECEDES/SUCCEEDS 链接形成时序链，携带 time_delta 属性
  - TEMPORALLY_CLOSE 链接携带 time_diff_hours 和 weight（反比衰减）
  - NARRATIVE 节点：时间窗口内 ≥3 个事件时自动生成叙事聚合
  - 查询时通过 get_temporal_chain() 沿时序链前向/后向遍历

MemPalace Validity Window 模式：
  - 每个 triple 携带 valid_from 和 valid_to 时间戳
  - invalidate() 方法设置 valid_to，标记事实不再为真
  - 查询时通过 as_of 参数获取特定时间点的事实
  - 时间线查询：mempalace_kg_timeline 工具

OntologyEngine 时序实现策略：
  - 静态实体：无时序字段，直接存储
  - 时序实体：valid_from/valid_to 字段，SQLite 存储 + KuzuDB 索引
  - 时序链接边：PRECEDES/SUCCEEDS 类型，携带 time_delta
  - 因果链接边：LEADS_TO/BECAUSE_OF/ENABLES/PREVENTS（参考 MAMGA）
  - 查询路由：temporal 类型查询自动调整边权重偏好（TEMPORAL×3.0）
  - 时间增强（参考 m_flow）：查询时间解析 + 时间匹配奖励 + 时间不匹配惩罚 + 候选池扩展
```

---

## 关系语义（Relational Semantics）

图中的边不仅是类型标签，而是**可被独立检索、评分、参与推理的语义载体**。

### 核心启示来自 m_flow

> *"In virtually every knowledge graph system, edges are just type labels. M-flow breaks this: every edge carries a natural language description, and these edge texts are vectorized and searched alongside nodes."*

### 边语义维度

| 语义维度 | 定义 | OntologyEngine 实现 |
|----------|------|-------------------|
| **边文本** | 关系的自然语言描述 | `Relation.edge_text`，参与向量检索 |
| **边权重** | 关系的数值重要性 | `Relation.weight`，支持多维度 |
| **边属性** | 关系的业务属性 | `Relation.attributes`（如担保金额、期限）|
| **语义参与推理** | 边作为推理链的中间步骤 | RuleEngine 执行路径中的关系遍历 |

### 边成本传播（Bundle Search 机制）

```
路径成本 = 起始节点向量距离 + Σ(边向量距离 + 跳数惩罚) + miss_penalty
Episode 最终得分 = min(所有路径成本)  ← 一条强证据链即可证明相关性
```

### 关系类型分类

| 类别 | 示例 | 语义特征 |
|------|------|---------|
| **业务关系** | guarantees, supplies, employs | 携带业务属性（金额、期限、比例）|
| **规则关系** | triggers, depends_on, overrides | 携带执行语义（条件、动作）|
| **溯源关系** | extracted_from, defined_in, trace_to | 携带来源信息（文档ID、段落号）|

---

## 查询路由分类（Query Routing）

OntologyEngine 的 QueryEngine 根据查询类型自动选择检索路径。

| 查询类型 | 特征词 | 检索路径 | 边权重偏好 |
|----------|--------|---------|-----------|
| **factual** | 谁/什么/哪个 | Layer-R 向量检索 → extracted_from 扩展 | 无 |
| **multi-hop** | 为什么/如何/...和...的关系 | Layer-S 图遍历 + ENTITY 边优先 | ENTITY×1.0, TEMPORAL×1.0, CAUSAL×2.0 |
| **temporal** | 什么时候/持续多久/历史变化 | valid_from/to 过滤 + 时序边 | TEMPORAL×3.0 |
| **analytical** | 计算/分析/占比/趋势 | → L4 RuleEngine 执行 | 无 |
| **mixed** | 复合查询 | Layer-R → Layer-S → trace_to 回溯 | 自适应 |

核心启示来自 **MAMGA**：同一架构对不同查询类型使用完全不同的检索参数（遍历深度、边权重、评分系数）。

---

## 语义推理（Semantic Reasoning）

基于关系边的传递推导和语义权重，在图结构上执行多跳推理，无需每次调用 LLM。

### 两种模式

**确定推理（规则引擎执行）**：有明确业务规则的场景，推理逻辑 100% 复现：

```
输入: 企业A的财务数据
  ↓
L2 归类: 行业=制造业, 规模=中型 (归类规则)
  ↓
L3 分析: credit_score = f(负债率, 流动比, ...) (指标计算)
  ↓
L4 决策: IF credit_score >= 700 THEN 授信额度=500万 (规则执行)
  ↓
输出: 授信决策 + ExecutionStepSnapshot
```

**传递推理（图遍历 + 语义权重）**：关系传递和语义扩散场景：

```
企业A ──[guarantees, 金额=500万, weight=0.8]──▶ 企业B
企业B ──[guarantees, 金额=300万, weight=0.6]──▶ 企业C

风险传导: risk(A→C) = risk(A) × 0.8 × 0.6
```

### 传递推理规则

1. **权重衰减**：每跳乘以边的语义权重
2. **类型约束**：只在特定关系类型上传递（如 `guarantees` 传递风险）
3. **阈值截止**：累积权重低于阈值时停止传播
4. **环路检测**：避免循环传播

---

## Schema v2 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│  L4: Business Logic（业务逻辑层）                              │
│  - Rule Definition + Rule Logic + Computation Graph         │
├─────────────────────────────────────────────────────────────┤
│  L3: Analytical Elements（分析要素层）                         │
│  - Metric / Indicator / Scorecard                           │
├─────────────────────────────────────────────────────────────┤
│  L2: Categorizations（分类层）                                 │
│  - Category + View                                          │
├─────────────────────────────────────────────────────────────┤
│  L1: Fact Objects（事实对象层）                                │
│  - Fact Object Definition → Entity Instance + Edge Instance │
└─────────────────────────────────────────────────────────────┘
```

### L1: Fact Objects

领域模型的核心抽象，定义业务对象的结构、属性和关系。资产归属：IT 资产（数据实例）+ 组织资产（定义规范）。

```yaml
fact_object:
  id: "finance:Counterparty"
  name: "交易对手"
  attributes:
    - name: "entity_id"
      type: "string"
    - name: "risk_grade"
      type: "enum"
      enum_type: "RiskGrade"
  relations:
    - name: "guarantees"
      target: "finance:Counterparty"
```

### L2: Categorizations

对 Fact Objects 进行分组和筛选的分类体系。资产归属：个人知识（专家分类视角）→ 组织资产（共识化分类标准）。

**tag_based 类型**：用于主题标签、跨域概念标记（如"制造业"、"上市公司"），与 SemanticConcept 功能等效。

```yaml
categorization:
  id: "risk_assessment"
  applicable_to: ["finance:Counterparty"]

categorization:
  id: "industry_tags"
  type: "tag_based"  # 承担 SemanticConcept 功能
  values:
    - "manufacturing"  # 制造业
    - "listed"         # 上市公司
```

### L3: Analytical Elements

用于分析和评估的业务计算单元，三种类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| **Metric** | 可量化度量 | 负债率、流动比 |
| **Indicator** | 二元/多元状态标识 | is_high_risk: true/false |
| **Scorecard** | 加权综合评分 | credit_scorecard: 0.645 |

### L4: Business Logic

规则定义与规则逻辑的分离，规则依赖 DAG 自动拓扑排序执行。

```yaml
rule_logic:
  rule_id: "R001_risk_grade"
  computation:
    operator: "SWITCH"
    cases:
      - condition: "value >= 85"
        output: { "risk_grade": "A" }
      - condition: "value >= 70"
        output: { "risk_grade": "B" }
      - condition: "value >= 60"
        output: { "risk_grade": "C" }
      - default:
        output: { "risk_grade": "D" }
```

---

## 知识点管理（Knowledge Point Management）

对图中每个原子知识单元的全生命周期管理。

### 生命周期

```
创建 → 关联 → 版本化 → 演进 → 溯源 → 归档
  │      │      │       │      │      │
  ↓      ↓      ↓       ↓      ↓      ↓
导入   互索引  快照    沉淀   Provenance  历史
定义   关系   diff    转化   Link       标记
交互   权重   审批    反馈   证据链     保留
```

### 质量维度

| 维度 | 定义 | 影响范围 |
|------|------|---------|
| **新鲜度** | 数据的时效性 | IT 资产实例 |
| **置信度** | 知识的可靠程度 | 个人资产规则/指标 |
| **权威性** | 知识的来源等级 | 三类资产 |
| **一致性** | 知识间的逻辑一致性 | 组织资产规则 |

---

## 上下文就绪知识（Context-Ready Knowledge）

经过溯源标注、互索引关联、质量评估后的知识，可被 Agent 直接可靠使用。

### 三个条件

| 条件 | 要求 | 实现 |
|------|------|------|
| **可溯源** | 任何知识都能追溯到原始来源 | Provenance Link |
| **可关联** | 知识之间有显式的语义连接 | 关系语义 |
| **可评估** | 知识有质量标签供 Agent 判断可信度 | 质量维度 |

Agent 在作业前通过 QueryService 检索，返回数据/规则/指标时附带溯源证据和质量标签。

---

## 语义空间隔离（Semantic Space Isolation）

多域知识通过混合隔离策略管理，域间实体对齐实现跨域协同。

### 隔离策略

| 策略 | 适用场景 | 实现方式 | 参考系统 |
|------|---------|---------|---------|
| **逻辑隔离**（默认） | 大多数场景，域间有协同需求 | domain_id 元数据过滤 | MemPalace Wing/Room |
| **物理隔离**（可选） | 安全要求高的场景，域间完全独立 | 独立 DB 实例 | m_flow DatasetStore |
| **混合模式** | 按需切换 | 配置驱动，ContextVar 请求级切换 | m_flow ENABLE_BACKEND_ACCESS_CONTROL |

### 域模型

```yaml
domain:
  id: "risk_control"
  name: "风控域"
  sub_domains:
    - id: "credit_risk"
      name: "信用风险"
    - id: "market_risk"
      name: "市场风险"
  isolation: logical  # logical | physical
  parent_domain: null  # 支持域的层次化组织
```

### 跨域实体对齐

不同域中相同实体通过 canonical_name + same_entity_as 边互连：

```
风控域: Company[canonical_name="华为技术有限公司"]
  ──[same_entity_as, confidence=1.0]──▶
供应链域: Company[canonical_name="华为技术有限公司"]
```

查询时自动扩展：在风控域查询"华为"时，通过 same_entity_as 边自动关联供应链域的知识。

### 技术实现框架

```
参考 m_flow DatasetStoreHandlerInterface + ContextVar 模式：

逻辑隔离实现：
  - 每个节点/边携带 domain_id 字段
  - ChromaDB where 过滤：{"domain_id": "risk_control"}
  - KuzuDB 属性过滤：WHERE n.domain_id = 'risk_control'

物理隔离实现：
  - DatasetStoreHandlerInterface 适配器模式
  - create_dataset() / delete_dataset() 生命周期钩子
  - KuzuDatasetStoreHandler：每个域独立的 .kuzu 文件
  - LanceDBDatasetStoreHandler：每个域独立的向量库

ContextVar 请求级切换：
  - _domain_id: ContextVar = ContextVar("_domain_id", default=None)
  - set_domain_context(domain, user_id)：为当前异步上下文设置域配置
  - 下游代码通过 get_domain_config() 自动获取，无需显式传参
  - 协程安全：不同请求并行执行，各自连接到不同的域配置
```

---

## 知识全链路可管理性（Knowledge Manageability）

自动化只是第一层，知识加工-存储-消费全链路需要可读、可见、可管理、可调整。

### 四层人工介入机制

| 机制 | 人工角色 | 触发条件 | 参考系统 |
|------|---------|---------|---------|
| **声明式规则编辑** | 领域专家定义业务规则 | 规则创建/修改时 | KAG Expert Rules DSL（简化版） |
| **反馈闭环** | 对检索结果评分 | 每次检索后 | Cognee feedback_weight + alpha |
| **质量检测+自愈** | 审阅检测结果，确认/否决修复 | 定期扫描 + ingest 时 | LLM-Wiki-Agent lint+heal |
| **知识时效管理** | 标记知识失效 | 知识过时时 | MemPalace invalidate() |

### 规则表达式设计

**设计原则**：结构化配置参数+合理表达式，不使用严格 DSL，降低领域专家使用门槛。

```yaml
rule_definition:
  id: "R001_risk_grade"
  name: "风险等级评定"
  scope:
    dimensions: ["risk_assessment"]
    entity_types: ["finance:Counterparty"]
  when:
    expression: "credit_score != null AND debt_ratio != null"
  then:
    operator: "SWITCH"
    cases:
      - condition: "credit_score >= 85 AND debt_ratio < 0.3"
        output: { "risk_grade": "A" }
      - condition: "credit_score >= 70"
        output: { "risk_grade": "B" }
  applicability:
    when_text: "评估交易对手信用风险时"
    why_text: "监管要求对所有交易对手定期评级"
    boundary_text: "不适用于同业拆借对手"
    outcome_text: "产出风险等级 A/B/C/D"
    prereq_text: "需要信用评分和负债率数据"
    exception_text: "新客户无历史数据时使用默认评级 C"
```

### 反馈闭环实现

```
参考 Cognee apply_feedback_weights.py：

反馈流程：
  1. 用户对检索结果评分（1-5 分 + 文字反馈）
  2. 分数归一化：normalize(score) = (score - 1) / 4 → [0, 1]
  3. 流式更新权重：updated = previous + alpha × (normalized - previous)
     alpha = 0.1（学习率，可配置）
  4. 只更新被检索使用过的图元素（used_graph_element_ids）
  5. 已处理反馈标记，避免重复应用

权重影响：
  - feedback_weight 参与检索评分：final = λ × semantic + (1-λ) × feedback_weight
  - 高权重节点/边在检索时获得更高排名
  - 低权重节点/边逐渐被降级
```

### 质量检测+自愈循环

```
参考 LLM-Wiki-Agent lint.py + heal.py + Graphify suggest_questions()：

Lint 检测（定期扫描）：
  确定性检测：孤儿页面、断裂链接、缺失实体页面
  图感知检测：Hub Stub（度数 > μ+2σ 且内容 < 500 字符）、脆弱桥、孤立社区
  语义检测：跨页面矛盾、过时内容、数据缺口

Heal 修复（自动+人工确认）：
  自动修复：缺失实体页面生成（LLM + 人工校验）
  引导修复：AMBIGUOUS 边 → "X 和 Y 的确切关系是什么？"
  建议问题：桥接节点、低内聚社区、孤立节点

闭环：lint → heal → lint → ... 持续改进
```

---

## 业务逻辑资产化（Business Logic as Knowledge Asset）

风险评估、指标计算、图分析逻辑等业务逻辑是一等知识资产，双层表达。

### 双层表达模型

| 层次 | 表达方式 | 特点 | 参考系统 |
|------|---------|------|---------|
| **Schema 内嵌** | 规则定义嵌入 FactObjectDefinition | 逻辑边按需计算，不可编辑 | KAG Expert Rules DSL |
| **图节点存储** | 规则作为独立图节点 | 可编辑、可版本化、可溯源 | m_flow Procedure + Cognee Rule DataPoint |

### 规则图节点模型

```yaml
rule_node:
  id: "rule_001"
  type: "RuleDefinition"
  name: "风险等级评定"
  version: 2
  status: "active"  # active | deprecated | superseded
  confidence: "high"  # high | low
  
  # 规则适用性六维度（参考 m_flow ContextPack）
  applicability:
    when_text: "评估交易对手信用风险时"
    why_text: "监管要求对所有交易对手定期评级"
    boundary_text: "不适用于同业拆借对手"
    outcome_text: "产出风险等级 A/B/C/D"
    prereq_text: "需要信用评分和负债率数据"
    exception_text: "新客户无历史数据时使用默认评级 C"
  
  # 规则表达式（结构化配置+表达式，非严格 DSL）
  expression:
    operator: "SWITCH"
    cases:
      - condition: "credit_score >= 85 AND debt_ratio < 0.3"
        output: { "risk_grade": "A" }
  
  # 溯源（参考 Cognee DataPoint）
  source_pipeline: "rule_editor"
  source_user: "expert_001"
  source_content_hash: "sha256:abc123"
  
  # 版本链（参考 m_flow supersedes）
  supersedes: ["rule_001_v1"]
  evidence_refs: ["doc_003", "doc_007"]
```

### 规则生命周期

```
创建 → 验证 → 发布 → 执行 → 反馈 → 演化 → 废弃
  │      │      │      │      │      │      │
  ↓      ↓      ↓      ↓      ↓      ↓      ↓
编辑器  Schema  审批   推理引擎  feedback  版本   标记
配置   验证    流程   逻辑边   权重更新  管理   deprecated
```

### 规则与图节点的关联

```
RuleDefinition[rule_001] ──[defines]──▶ FactObjectDefinition[finance:Counterparty]
RuleDefinition[rule_001] ──[computes]──▶ AnalyticalElement[credit_score]
RuleDefinition[rule_001] ──[triggers]──▶ RuleLogic[R001_risk_grade]
RuleDefinition[rule_001] ──[supersedes]──▶ RuleDefinition[rule_001_v1]
RuleDefinition[rule_001] ──[evidence_from]──▶ KnowledgeFragment[doc_003]
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Schema完整规范 | `docs/02-design/schema/01-canonical-schema-spec.md` |
| 四层架构设计 | `docs/02-design/schema/L1-L4-declarations.md` |
| 规则引擎设计 | `docs/02-design/rule-engine/README.md` |
| 存储设计 | `docs/storage/README.md` |
| 知识检索设计 | `docs/01-overview/08-knowledge-retrieval.md` |
| 上下文栈参考 | [AI Memory vs RAG vs Knowledge Graph (Atlan 2026)](https://atlan.com/know/ai-memory-vs-rag-vs-knowledge-graph/) |
| Agent Memory 架构 | [The Agent Memory Race of 2026 (OSSInsight)](https://ossinsight.io/blog/agent-memory-race-2026) |

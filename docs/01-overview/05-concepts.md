# 核心概念

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档（术语定义） | **last_verified**: 2026-04-17
> **[关键设计点]**: 本文档基于 Schema v2 四层架构定义核心术语，作为项目唯一术语规范入口
> **[单一事实源]**: 术语定义与 Schema v2 规范保持一致，详见 `docs/05-schema-v2/09-canonical-schema-spec.md`

## 术语对照表

| 旧术语（MVP） | 新术语（Schema v2） | 说明 |
|--------------|-------------------|------|
| Concept | **Fact Object** | 领域模型的核心抽象，定义业务实体的结构和关系 |
| Entity | **Entity Instance** | Fact Object 的具体数据实例 |
| Metric | **Analytical Element** | 分析要素（细分：Metric / Indicator / Scorecard） |
| Dimension（分析维度）| **Categorization** | 分类体系，用于组织和筛选分析视角 |
| Rule / RuleGroup | **Rule Definition + Rule Logic** | 规则定义与规则逻辑分离 |
| Ruleset | **Business Logic** | 逐步淡出，统一使用业务逻辑层术语 |
| Attribute | **Attribute** | 保持不变，Fact Object 的属性定义 |
| Relation | **Relation** | 保持不变，Fact Object 之间的关系定义 |

---

## 新增核心概念（2026-04-17）

### 上下文栈 (Context Stack)

AI Agent 的完整上下文由三层构成，每层解决不同的问题：

```
┌─────────────────────────────────────────────┐
│  Memory (连续性层)                           │
│  ── 跨会话状态、用户偏好、学习到的事实        │
├─────────────────────────────────────────────┤
│  RAG (广度层)                               │
│  ── 文档检索、向量相似度、知识密集型问答      │
├─────────────────────────────────────────────┤
│  Knowledge Graph (深度层)                    │
│  ── 实体关系、多跳推理、规则执行              │
└─────────────────────────────────────────────┘
```

| 层 | 解决的问题 | OntologyEngine 角色 |
|----|-----------|---------------------|
| Memory | Agent 行为连续性 | 提供知识接口，不实现 Memory |
| RAG | 信息覆盖广度 | 提供向量索引，可与外部 RAG 协同 |
| Knowledge Graph | 推理深度和可解释性 | **核心能力层**，三层资产链接载体 |

> **关键洞察**：三层不是替代关系，而是组合关系。生产级 Agent 系统需要三者协同。参考 [AI Memory vs RAG vs Knowledge Graph](https://atlan.com/know/ai-memory-vs-rag-vs-knowledge-graph/)

### 知识资产 (Knowledge Assets)

企业知识资产分为三层，OntologyEngine 负责链接而非替代：

| 资产层 | 内容 | 特征 | OntologyEngine 对应 |
|--------|------|------|---------------------|
| IT 资产 | 数据源、API 接口、系统配置 | 结构化、可自动化、实时变化 | L1 Fact Objects（实例化） |
| 个人知识沉淀 | 专家经验、隐性知识、领域直觉 | 主观性、经验性、难显性化 | L2/L3（归类+分析，经验→规则） |
| 组织级资产 | 业务规则、合规策略、行业标准 | 共识性、权威性、版本化管理 | L4 Business Logic（规则执行） |

### 资产链接 (Asset Linking)

三层知识资产之间的可推理关联：

| 链接类型 | 方向 | 机制 | 示例 |
|----------|------|------|------|
| 数据→规则 | IT → 组织 | Schema 驱动：数据结构驱动规则定义 | 实体属性变更 → 规则输入更新 |
| 规则→数据 | 组织 → IT | 执行输出：规则结果写回实例 | 授信额度计算 → 实体属性更新 |
| 经验→规则 | 个人 → 组织 | 声明式编码：YAML 将经验转化为可执行逻辑 | 风控直觉 → 担保圈检测规则 |
| 规则→经验 | 组织 → 个人 | 可解释性：执行快照帮助专家理解系统行为 | 条件拆解 → 专家审查判断 |
| 全链路追溯 | 三层联合 | ExecutionStepSnapshot + 影响链分析 | 任何决策可追溯到数据源+规则版本+专家依据 |

### 上下文就绪数据 (Context-Ready Data)

生产级 AI 系统对知识资产的数据质量要求（参考 Atlan 2026）：

| 属性 | 说明 | OntologyEngine 实现 |
|------|------|---------------------|
| 新鲜度评分 | 每个数据资产有时间戳和过时分数 | 增量更新 + 变更检测 |
| 血缘追踪 | 从源头到索引资产的路径可追溯 | ExecutionStepSnapshot |
| 语义标签 | 实体定义、领域分类、业务术语表 | KGML Schema + Categorization |
| 所有权元数据 | 每个资产有明确负责人 | Schema 元数据（Phase 3） |

### Agent 记忆架构 (Agent Memory Architectures)

业界 2026 年的四种主流 Agent 记忆架构对比（参考 [OSSInsight](https://ossinsight.io/blog/agent-memory-race-2026)）：

| 架构 | 本体论 | 代表 | OntologyEngine 对齐 |
|------|--------|------|---------------------|
| 逐字原文存储 | 记忆 = 可语义检索的原始经验 | MemPalace | 不采用，OntologyEngine 侧重结构化 |
| 文件系统上下文 | 记忆 = 可按需加载的层级资源 | OpenViking | 部分对齐（L0/L1 分层加载） |
| 代码知识图谱 | 记忆 = 实体间的关系结构 | code-review-graph | **核心对齐**（图+规则+推理） |
| 扁平全文索引 | 记忆 = 可全文搜索的文本痕迹 | engram | 不采用，OntologyEngine 侧重深度推理 |

> **OntologyEngine 定位**：代码知识图谱架构的业务领域扩展 —— 从"代码依赖图"泛化为"业务规则推理图"。

---

## 新增核心概念（2026-04-17 第二轮深化）

> **背景**：OntologyEngine 不仅要管理结构化的知识图谱（实体/关系/规则），还必须与原始的知识碎片（文档/文本/图片）**共存、互索引、可溯源**。以下概念借鉴 KAG 互索引、m-flow 关系语义、GraphRAG 双存储架构，定义了知识碎片与结构化知识之间的管理机制。

### 知识碎片 (Knowledge Fragment)

**定义**：未经结构化处理或仅做了轻量分块的原始知识载体，包括文档段落、文本片段、表格、图片、PDF 页面等。

**特征**：
- **非结构化/半结构化**：没有 Schema 约束，内容自由度高
- **海量且异构**：来源多样（内部文档、外部网页、用户上传），格式不统一
- **时效性差异大**：政策文件可能长期有效，新闻资讯数日过期
- **语义密度不均**：一段文字可能包含多个实体/关系，也可能只有一句话

**与 OntologyEngine 的关系**：
```
知识碎片 ──Extractor──▶ 结构化知识（实体/关系/指标）
    ↑                        │
    │                        ↓
    └──── Provenance ────── 溯源链接
```

**对标业界**：
| 系统 | 知识碎片的称谓 | 管理方式 |
|------|--------------|----------|
| KAG | Chunk / ContentFragment | ChunkIndexManager，通过 AtomicQuery 桥接到 KG |
| m-flow | ContentFragment | 通过 `supported_by` 和 `includes_chunk` 边挂载到 Facet/Episode |
| GraphRAG (SAP) | Chunk | 双存储：Milvus(向量) + iGraph(图)，实体-文本块关系双向链接 |
| OntologyEngine | **KnowledgeFragment** | 三类资产均可关联碎片，通过 Provenance Link 双向可达 |

**OntologyEngine 碎片分类**：

| 碎片类型 | 来源 | 示例 | 关联资产层 |
|----------|------|------|-----------|
| 制度文件 | 组织内部 | 《授信管理办法 v3.2》PDF | 组织资产 |
| 操作手册 | 组织内部 | 审批流程操作指南 | 组织资产 |
| 业务数据文档 | IT 资产系统 | 数据字典、表结构说明 | IT 资产 |
| 个人笔记 | 用户上传 | 专家的审查意见、分析笔记 | 个人资产 |
| 外部信息 | 公开来源 | 行业报告、法规解读 | IT 资产 |

### 互索引 (Mutual Indexing)

**定义**：结构化知识（实体/关系/规则）与知识碎片（文本块/文档）之间的**双向可追溯链接**，支持从任一端导航到另一端。

**设计借鉴**：

| 系统 | 互索引方案 | 桥接机制 | 优势 | 局限 |
|------|-----------|----------|------|------|
| **KAG** | AtomicQuery 桥接层 | `AtomicQuery.relatedTo → KnowledgeUnit` + `AtomicQuery.sourceChunk → Chunk` | 三路独立检索（KG自由文本/KG结构化/向量文本块） | Hybrid 模式 LLM 消耗极高（460万 tokens/100k字符） |
| **m-flow** | 语义边挂载 | `Facet.supported_by → ContentFragment` + `Episode.includes_chunk → ContentFragment` | 边参与向量检索（语义过滤），支持证据追踪 | 仅单向（碎片→结构化），无结构化→碎片的主动导航 |
| **GraphRAG (SAP)** | 双存储双向关系 | 实体-文本块关系（63,681条）存储在图数据库，Milvus 存向量嵌入 | 检索时同时返回关系三元组+源文本块，混合排序 | 无规则层，不含业务逻辑的互索引 |

**OntologyEngine 互索引架构**：

```
┌─────────────────────────────────────────────────────────────┐
│                   互索引双向链接架构                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    provenance_link    ┌──────────────┐   │
│  │ 知识碎片层    │ ◄══════════════════► │ 结构化知识层  │   │
│  │              │                       │              │   │
│  │ KnowledgeFrag│  ┌─ 碎片→实体        │ Entity       │   │
│  │ (文档/文本)   │  │  extracted_from   │ Instance     │   │
│  │              │  │                    │              │   │
│  │              │  ├─ 实体→碎片        │ Relation     │   │
│  │              │  │  supported_by     │ Instance     │   │
│  │              │  │                    │              │   │
│  │              │  ├─ 规则→碎片        │ Rule         │   │
│  │              │  │  defined_in       │ Definition   │   │
│  │              │  │                    │              │   │
│  │              │  ├─ 指标→碎片        │ Metric       │   │
│  │              │  │  documented_in    │ Definition   │   │
│  │              │  │                    │              │   │
│  │              │  └─ 推理→碎片        │ Execution    │   │
│  │              │     trace_to         │ StepSnapshot │   │
│  └──────────────┘                       └──────────────┘   │
│                                                             │
│  检索路径：                                                  │
│    碎片侧入口 → 提取实体 → 图推理 → 返回结果+证据碎片        │
│    结构化侧入口 → 推理执行 → 溯源 → 返回结果+来源碎片        │
│    混合入口 → 向量+图联合检索 → 融合排序+证据链              │
└─────────────────────────────────────────────────────────────┘
```

**四种互索引关系类型**：

| 关系类型 | 方向 | 含义 | 场景示例 |
|----------|------|------|----------|
| `extracted_from` | 实体 → 碎片 | 实体是从哪个碎片中提取的 | 授信规则 R001 定义在《授信管理办法》第 3.2 节 |
| `supported_by` | 碎片 → 实体 | 碎片支撑了哪个实体/判断 | 审查意见（个人笔记）支撑了高风险归类 |
| `defined_in` | 规则/指标 → 碎片 | 规则/指标的定义来源 | 信用分计算公式定义在《风险评分模型 v2.1》 |
| `trace_to` | 推理步骤 → 碎片 | 推理执行链可追溯到来源 | 授信额度 500 万的决策可追溯到企业财报 + 评分卡文档 |

> **关键洞察**：OntologyEngine 的互索引比 KAG 更深一层 —— KAG 只做实体↔文本的桥接，OntologyEngine 还要做**规则/指标/推理链↔碎片**的溯源，因为业务场景要求每个决策都能追溯到来源文档。

### 关系语义 (Relational Semantics)

**定义**：图中的边（关系）不仅是两个节点之间的类型标签，而是**可被独立检索、评分、参与推理的语义载体**。

**设计借鉴 m-flow**：

m-flow 的核心创新是 **"边有语义"**（Design Break #1: Edges Have Semantics）：

> *"In virtually every knowledge graph system, edges are just type labels. M-flow breaks this: every edge carries a natural language description, and these edge texts are vectorized and searched alongside nodes."*

**m-flow 边语义的实现机制**：

| 组件 | 实现 | 作用 |
|------|------|------|
| `Edge.edge_text` | 自然语言描述（如"公司A向B提供500万担保"） | 被向量化，参与检索 |
| `Edge.weight` / `Edge.weights` | 数值权重（支持多维度） | 图遍历时的路径成本 |
| `Edge.relationship_type` | 关系类型标签（如"guarantees"） | 图结构查询、边分类 |
| `edge_text_generators.py` | 为每种关系类型生成精简的 edge_text | 统一格式，减少语义干扰 |

**Bundle Search 中的边成本传播**：
```
路径成本 = 起始节点向量距离 + Σ(边向量距离 + 跳数惩罚)
         + miss_penalty（边未被向量检索命中的惩罚）

Episode 最终得分 = min(所有路径成本)  ← 一条强证据链即可证明相关性
```

**OntologyEngine 关系语义规范**：

| 语义维度 | 定义 | OntologyEngine 实现 | 对齐 m-flow |
|----------|------|-------------------|-------------|
| **边文本** | 关系的自然语言描述 | `Relation.edge_text`，参与向量检索 | 对齐 `Edge.edge_text` |
| **边权重** | 关系的数值重要性 | `Relation.weight`，支持多维度（`weights: dict`） | 对齐 `Edge.weights` |
| **边类型** | 关系的类型标签 | `Relation.relationship_type`（Schema 定义） | 对齐 `Edge.relationship_type` |
| **边属性** | 关系的业务属性 | `Relation.attributes`（如担保金额、担保类型） | 对齐 `Edge.properties` |
| **语义参与检索** | 边被向量化并参与检索打分 | `edge_hit_map` 中的向量距离 | 对齐 m-flow 的 Bundle Search |
| **语义参与推理** | 边作为推理链的中间步骤 | RuleEngine 执行路径中的关系遍历 | 超越 m-flow（m-flow 仅检索，不执行业务规则） |

**关系类型分类规范**：

| 类别 | 关系类型 | 示例 | 语义特征 |
|------|----------|------|----------|
| **业务关系** | guarantees, supplies, employs, invests_in | "A向B提供担保" | 携带业务属性（金额、期限、比例） |
| **归类关系** | belongs_to_category, classified_as | "企业A归类为制造业" | 单向、权威性（组织规则定义） |
| **分析关系** | computed_from, derived_from | "信用分由5个指标加权计算" | 携带计算逻辑（公式、权重） |
| **规则关系** | triggers, depends_on, overrides | "风险分>80 触发预警" | 携带执行语义（条件、动作） |
| **溯源关系** | extracted_from, defined_in, trace_to | "实体A来自文档D第3节" | 携带来源信息（文档ID、段落号、时间戳） |
| **资产关系** | owned_by, shared_to, promoted_to | "规则R001由user_123创建" | 携带权限和生命周期信息 |

### 语义推理 (Semantic Reasoning)

**定义**：基于关系边的**传递推导**和**语义权重**，在图结构上执行多跳推理，无需每次都调用 LLM。

**设计借鉴**：

| 系统 | 推理方式 | 特点 | 局限 |
|------|----------|------|------|
| **m-flow Bundle Search** | 成本传播（tip→base） | 模拟多跳推理链，用算术替代 LLM 调用 | 仅做检索排序，不生成新的知识 |
| **KAG Solver** | Logical Form Planner + Executor | op_deduce（演绎）+ op_retrieval（检索） | 依赖 LLM 做推理规划 |
| **OntologyEngine** | **DAG 规则执行 + 图遍历推理** | 规则引擎执行确定逻辑，图遍历做传递推导 | — |

**OntologyEngine 语义推理的两种模式**：

**模式 1：确定推理（规则引擎执行）**

适用于有明确业务规则的场景，推理逻辑可 100% 复现：

```
输入: 企业A的财务数据
  ↓
L2 归类: 行业=制造业, 规模=中型 (归类规则)
  ↓
L3 分析: credit_score = f(负债率, 流动比, ...) (指标计算)
  ↓
L4 决策: IF credit_score >= 700 THEN 授信额度=500万 (规则执行)
  ↓
输出: 授信决策 + ExecutionStepSnapshot (全链路可追溯)
```

**模式 2：传递推理（图遍历 + 语义权重）**

适用于关系传递和语义扩散场景，类似 m-flow 的成本传播但用于业务推理：

```
示例：担保链风险传导

企业A ──[guarantees, 金额=500万, weight=0.8]──▶ 企业B
企业B ──[guarantees, 金额=300万, weight=0.6]──▶ 企业C
企业C ──[guarantees, 金额=100万, weight=0.3]──▶ 企业D

风险传导: risk(A→D) = risk(A) × 0.8 × 0.6 × 0.3
                        = risk(A) × 0.144  ← 3跳后风险显著衰减
```

**传递推理规则**：
1. **权重衰减**：每跳乘以边的语义权重，模拟风险/影响力的递减
2. **类型约束**：只在特定关系类型上传递（如 `guarantees` 传递风险，`belongs_to_category` 不传递）
3. **阈值截止**：累积权重低于阈值时停止传播
4. **环路检测**：检测并避免循环传播（NetworkX 实现）

> **与 m-flow 的关键差异**：m-flow 的成本传播是**检索时的排序机制**（越低越好），OntologyEngine 的传递推理是**业务计算**（如风险传导值）。前者服务于"找到最相关的知识"，后者服务于"计算出业务结果"。

### 知识点管理 (Knowledge Point Management)

**定义**：对图中每个**原子知识单元**（实体实例、关系实例、规则、指标、碎片）进行**全生命周期管理**，包括版本化、溯源、关联和质量追踪。

**设计借鉴**：

| 系统 | 知识点管理方式 | 特点 |
|------|---------------|------|
| **m-flow FacetPoint** | 独立向量化、独立评分、独立证据链接 | "一个信息点可以独立检索、独立解释、独立关联证据" |
| **KAG KnowledgeUnit** | 结构化内容 + 本体类型 + 描述，通过 AtomicQuery 桥接到文本 | 三路独立检索 |
| **GraphRAG (SAP)** | 实体 + 实体-文本块关系，双向可追溯 | 双存储（Milvus + iGraph） |

**OntologyEngine 知识点生命周期**：

```
┌────────────────────────────────────────────────────────────────┐
│ 知识点生命周期                                                  │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. 创建 (Create)                                              │
│     ├─ IT 资产：从数据源自动导入 (IngestionService)              │
│     ├─ 组织资产：Schema 定义 + 审核 (SchemaService)             │
│     ├─ 个人资产：Agent 交互自动生成 / 用户手动创建               │
│     └─ 知识碎片：文档上传 + 自动分块 + 向量化                   │
│                                                                │
│  2. 关联 (Link)                                                │
│     ├─ 实体↔碎片：extracted_from / supported_by                 │
│     ├─ 规则↔碎片：defined_in                                    │
│     ├─ 推理↔碎片：trace_to                                      │
│     ├─ 实体↔实体：业务关系 (guarantees, supplies, ...)          │
│     └─ 规则↔规则：depends_on, overrides                         │
│                                                                │
│  3. 版本化 (Version)                                           │
│     ├─ Schema 版本：全量快照策略                                │
│     ├─ 实例版本：DuckDB diff 表（version_id + diff_json）        │
│     ├─ 规则版本：v2.1, v2.2, ... + 审批记录                     │
│     └─ 碎片版本：文档级版本（不可变）+ 分块级哈希                │
│                                                                │
│  4. 演进 (Evolve)                                              │
│     ├─ 个人资产 → 候选 → 组织资产（沉淀转化）                   │
│     ├─ 规则反馈 → 置信度更新 → 自动优化                         │
│     └─ 实体属性 → 增量更新 → 影响分析                           │
│                                                                │
│  5. 溯源 (Trace)                                               │
│     ├─ 任意知识点 → 来源碎片（document_id + chunk_id + offset）  │
│     ├─ 任意决策 → ExecutionStepSnapshot → 推理链 → 数据源       │
│     └─ 任意规则 → 创建者 + 审批记录 + 变更历史                  │
│                                                                │
│  6. 归档 (Archive)                                             │
│     ├─ 过期规则：标记 deprecated，保留历史版本                   │
│     ├─ 过期数据：按保留策略清理                                  │
│     └─ 失效碎片：标记 stale，保留索引引用                       │
└────────────────────────────────────────────────────────────────┘
```

**知识点质量维度**：

| 质量维度 | 定义 | 度量方式 | 影响范围 |
|----------|------|----------|----------|
| **新鲜度** | 数据的时效性 | 时间戳 + 过时分数 | IT 资产实例 |
| **置信度** | 知识的可靠程度 | 使用次数 + 正面反馈比 | 个人资产规则/指标 |
| **权威性** | 知识的来源等级 | 组织审核 → 高；个人创建 → 低 | 三类资产 |
| **覆盖率** | 知识的完整程度 | 属性填充率 + 关系密度 | 实体实例 |
| **一致性** | 知识间的逻辑一致性 | 规则冲突检测 + 值域校验 | 组织资产规则 |

### 上下文就绪知识 (Context-Ready Knowledge)

**定义**：经过溯源标注、互索引关联、质量评估后的知识，可以被 Agent 在作业过程中**直接、可靠地使用**，无需额外的人工整理。

**与"上下文就绪数据"的区别**：
- 上下文就绪数据（上一轮定义）：侧重**数据质量**（新鲜度、血缘、语义标签）
- 上下文就绪知识（本轮新增）：侧重**知识可用性**（溯源、互索引、质量评估、生命周期管理）

**上下文就绪知识的三个条件**：

| 条件 | 要求 | OntologyEngine 实现 |
|------|------|---------------------|
| **可溯源** | 任何知识都能追溯到原始来源 | Provenance Link（碎片↔结构化） |
| **可关联** | 知识之间有显式的语义连接 | 关系语义（edge_text + weight + type） |
| **可评估** | 知识有质量标签供 Agent 判断可信度 | 质量维度（新鲜度/置信度/权威性/覆盖率/一致性） |

> **Agent 使用模式**：Agent 在作业前通过 QueryService 检索上下文就绪知识，系统返回的不仅是数据/规则/指标，还附带**溯源证据**（来自哪些文档的哪些段落）和**质量标签**（置信度 0.85、数据截至 2026-04-15），让 Agent 可以判断知识的可靠程度并决定是否采用。

---

## Schema v2 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│  L4: Business Logic（业务逻辑层）                              │
│  - Rule Definition（规则定义）                                │
│  - Rule Logic（规则逻辑）                                     │
├─────────────────────────────────────────────────────────────┤
│  L3: Analytical Elements（分析要素层）                         │
│  - Metric（指标）                                             │
│  - Indicator（指示器）                                        │
│  - Scorecard（评分卡）                                        │
├─────────────────────────────────────────────────────────────┤
│  L2: Categorizations（分类层）                                 │
│  - Category（分类）                                           │
│  - View（视图）                                               │
├─────────────────────────────────────────────────────────────┤
│  L1: Fact Objects（事实对象层）                                │
│  - Fact Object Definition（定义）                             │
│  - Entity Instance（实例）                                    │
│  - Edge Instance（关系实例）                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## L1: Fact Objects（事实对象层）

### 是什么

Fact Object 是领域模型的核心抽象，代表业务世界中的**事实实体**。它定义了业务对象的结构、属性和关系，是数据建模的基础单元。

**资产归属**: IT 资产（数据实例）+ 组织资产（定义规范）

### 包含什么

**Fact Object Definition（定义）**
```yaml
fact_object:
  id: "finance:Counterparty"
  name: "交易对手"
  attributes:
    - name: "entity_id"
      type: "string"
      required: true
    - name: "risk_grade"
      type: "enum"
      enum_type: "RiskGrade"
  relations:
    - name: "guarantees"
      target: "finance:Counterparty"
```

**属性类型（Attribute）**

| 类型 | 说明 | 示例 |
|------|------|------|
| Basic | 基础属性，直接存储 | `registered_capital`, `status` |
| Derived | 派生属性，通过规则计算 | `credit_limit` |
| Aggregated | 聚合属性，跨实体关联计算 | `total_guarantee_amount` |

**关系（Relation）**

两个 Fact Object 之间的连接定义，可携带属性：
- `from`: 源 Fact Object
- `to`: 目标 Fact Object  
- `attributes`: 关系属性

### 与其他层的关系

- **向上**: L2 Categorizations 引用 L1 Fact Objects 进行分组和分类
- **向上**: L3 Analytical Elements 基于 L1 的属性计算指标
- **向上**: L4 Business Logic 操作 L1 的实例数据

### 旧术语映射

| 旧术语 | 对应新术语 | 关系 |
|--------|-----------|------|
| Concept | Fact Object | 完全对应，改名 |
| Concept.attributes | Fact Object.attributes | 完全一致 |
| Concept.relations | Fact Object.relations | 完全一致 |

---

## L2: Categorizations（分类层）

### 是什么

Categorization（分类体系）替代了原有的 Dimension（分析维度）概念，提供了一种更通用的组织机制，用于对 Fact Objects 进行分组、筛选和分析视角定义。

**资产归属**: 个人知识（专家分类视角）→ 组织资产（共识化分类标准）

**重要澄清**: Categorization 不同于存储属性，它定义的是**分析视角和分组规则**。

### 包含什么

**Category（分类）**
```yaml
categorization:
  id: "risk_assessment"
  name: "风险评估分类"
  applicable_to: ["finance:Counterparty", "finance:Enterprise"]
  dimensions:
    - id: "credit_assessment"
      name: "融资授信视角"
      filters:
        - attribute: "status"
          operator: "EQ"
          value: "active"
    - id: "transaction_monitoring"
      name: "交易监控视角"
```

**View（视图）**

基于 Categorization 定义的动态数据视图，决定哪些 Entity Instances 在特定分析场景下可见。

### 与其他层的关系

- **向下**: 引用 L1 Fact Objects，定义适用的对象类型
- **向上**: L3 Analytical Elements 在特定 Categorization 下计算
- **向上**: L4 Business Logic 可限定在特定 Categorization 范围内执行

### 旧术语映射

| 旧术语 | 对应新术语 | 关系 |
|--------|-----------|------|
| Dimension | Categorization | 概念扩展，Dimension 成为 Categorization 的一种具体类型 |
| dimension_attributes | 移除 | 原误称，派生属性应通过 L4 Business Logic 定义 |

**迁移示例**

```yaml
# 旧理解（已废弃）
concepts:
  - name: "Supplier"
    dimension_attributes:
      credit_assessment:
        - name: "credit_limit"  # ❌ 这不是存储属性

# 新理解
fact_objects:
  - id: "finance:Supplier"
    attributes:  # ← 存储的属性
      - name: "registered_capital"
      - name: "status"

categorizations:
  - id: "credit_assessment"
    applicable_to: ["finance:Supplier"]
    # 分类定义，不包含派生属性

business_logic:
  rules:
    - id: "R004_credit_limit"
      scope:
        categorization: "credit_assessment"
      computation:
        formula: "registered_capital * 0.5"
```

---

## L3: Analytical Elements（分析要素层）

### 是什么

Analytical Element 是用于分析和评估的业务计算单元，替代了原有的 Metric 概念，并扩展为三种具体类型。

**资产归属**: 个人知识（专家经验量化）→ 组织资产（共识化指标）

### 包含什么

**Metric（指标）**

可量化的业务度量，支持原子指标、派生指标和复合指标：

```yaml
analytical_element:
  id: "guarantee_ratio"
  type: "metric"
  metric_type: "derived"  # atomic | derived | composite
  calculation:
    type: "formula"
    expression: "total_guarantee_out / net_asset"
  categorization_scope: ["risk_assessment"]
```

**Indicator（指示器）**

二元或多元状态标识，通常用于标记特定业务状态：

```yaml
analytical_element:
  id: "is_high_risk"
  type: "indicator"
  indicator_type: "boolean"
  calculation:
    type: "threshold"
    condition: "risk_score > 80"
```

**Scorecard（评分卡）**

综合评估模型，组合多个 Metrics/Indicators 进行加权评分：

```yaml
analytical_element:
  id: "credit_scorecard"
  type: "scorecard"
  components:
    - metric: "guarantee_ratio"
      weight: 0.4
    - metric: "cash_flow_stability"
      weight: 0.6
```

### 与其他层的关系

- **向下**: 基于 L1 Fact Objects 的属性进行计算
- **向下**: 在 L2 Categorizations 定义的范围内应用
- **向上**: L4 Business Logic 引用 Analytical Elements 作为规则输入/输出

### 旧术语映射

| 旧术语 | 对应新术语 | 关系 |
|--------|-----------|------|
| Metric | Analytical Element (type=metric) | 概念扩展，Metric 成为子类型 |
| - | Indicator | 新增类型 |
| - | Scorecard | 新增类型 |

---

## L4: Business Logic（业务逻辑层）

### 是什么

Business Logic 层统一封装业务规则和计算逻辑，替代了原有的 Rule / RuleGroup / Ruleset 体系，实现了**规则定义**与**规则逻辑**的分离。

**资产归属**: 组织级资产（核心业务规则库），可追溯至个人知识（专家经验来源）

### 包含什么

**Rule Definition（规则定义）**

描述规则的元数据：ID、名称、适用范围、输入输出声明：

```yaml
rule_definition:
  id: "R001_risk_grade"
  name: "风险等级评估规则"
  scope:
    fact_objects: ["finance:Counterparty"]
    categorizations: ["risk_assessment"]
  inputs:
    - name: "comprehensive_risk_score"
      type: "analytical_element"
      ref: "risk_score"
  outputs:
    - name: "risk_grade"
      type: "attribute"
      target: "finance:Counterparty.risk_grade"
```

**Rule Logic（规则逻辑）**

具体的计算逻辑，通过算子组合实现：

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

**Operator（算子）**

| 类别 | 算子 | 说明 |
|------|------|------|
| Math | ADD, SUB, MUL, DIV, SUM, AVG | 数学运算 |
| Logic | IF, SWITCH, AND, OR | 逻辑控制 |
| Comparison | EQ, GT, LT, GTE, LTE | 比较运算 |
| Binning | BINNING | 分箱（含 inclusive_max） |
| Scorecard | SCORECARD | 评分卡（WOE + grade） |
| Decision | DECISION_TABLE | 决策表 |
| Graph | TRAVERSE, CENTRALITY, NEIGHBORS | 图计算 |
| External | LLM_INFERENCE, API_CALL | 外部调用 |

**Computation Graph（计算图）**

规则依赖的 DAG，系统根据输入输出关系自动拓扑排序执行。

### 与其他层的关系

- **向下**: 操作 L1 Entity Instances 的数据
- **向下**: 读取 L2 Categorizations 确定执行范围
- **向下**: 引用 L3 Analytical Elements 作为计算依据
- **内部**: Rule Definition 与 Rule Logic 解耦，支持逻辑复用和版本管理

### 旧术语映射

| 旧术语 | 对应新术语 | 关系 |
|--------|-----------|------|
| Rule | Rule Definition + Rule Logic | 拆分，元数据与逻辑分离 |
| RuleGroup | Rule Definition.scope | 通过 scope 字段分组 |
| Ruleset | Business Logic | 统一命名，Ruleset 逐步淡出 |
| Operator | Operator | 保持一致，扩展算子库 |

---

## 数据层：实例化

### 是什么

数据层是 L1 Fact Objects 的**运行时实例化**，包含具体的业务数据和关系。

**资产归属**: IT 资产（运行时数据）

### 包含什么

**Entity Instance（实体实例）**

Fact Object 的具体数据实例，JSON 表示：

```json
{
  "_id": "ent_12345",
  "_fact_object": "finance:Counterparty",
  "entity_id": "C-2024-001",
  "name": "某供应链企业",
  "registered_capital": 50000000,
  "status": "active",
  "risk_grade": "B"
}
```

**Edge Instance（边实例）**

Relation 的具体关系实例：

```json
{
  "_id": "edge_67890",
  "_relation": "guarantees",
  "from": "ent_12345",
  "to": "ent_12346",
  "guarantee_amount": 10000000,
  "guarantee_type": "financial"
}
```

**Instance（完整实例）**

特定 Categorization 下的 Schema + Data 完整填充，包含：
- 该分类适用的所有 Entity Instances
- 所有相关的 Edge Instances
- 计算得到的 Analytical Element 值

### 与 L1 的关系

```
Fact Object Definition ──实例化──▶ Entity Instance
         │                              │
    attributes ─────────────────────▶ 属性值
    relations ──────────────────────▶ Edge Instances
```

> **[关键设计点]**: 数据层不是独立的架构层，而是 L1 在运行时的具体表现。Schema v2 的四层架构指的是**模型定义层**，数据层是这些定义的实例化结果。

---

## 总结：概念映射全景

```
Schema v2 四层架构 × 三层知识资产:
┌─────────────────────────────────────────────────────────────┐
│ L4 Business Logic                                           │
│   Rule Definition → Rule Logic → Computation Graph         │
│   [组织级资产: 业务规则库]                                    │
├─────────────────────────────────────────────────────────────┤
│ L3 Analytical Elements                                      │
│   Metric / Indicator / Scorecard                           │
│   [个人知识→组织资产: 专家经验量化]                           │
├─────────────────────────────────────────────────────────────┤
│ L2 Categorizations                                          │
│   Category / View (替代旧 Dimension)                        │
│   [个人知识: 专家分类视角]                                    │
├─────────────────────────────────────────────────────────────┤
│ L1 Fact Objects                                             │
│   Definition ──▶ Entity Instance + Edge Instance           │
│   [IT资产: 数据实例 + 组织资产: 定义规范]                     │
└─────────────────────────────────────────────────────────────┘

上下文栈定位:
  Memory (连续性层) ← Agent 框架提供
  RAG (广度层)      ← 外部检索系统 / OntologyEngine 向量索引
  KG (深度层)       ← OntologyEngine 核心

MVP 旧概念映射:
  Concept ───────────────▶ Fact Object (L1)
  Entity ────────────────▶ Entity Instance (L1 运行时)
  Metric ────────────────▶ Analytical Element (L3)
  Dimension ─────────────▶ Categorization (L2)
  Rule / Ruleset ────────▶ Business Logic (L4)
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Schema v2 完整规范 | `docs/05-schema-v2/09-canonical-schema-spec.md` |
| 四层架构设计 | `docs/05-schema-v2/README.md` |
| 规则引擎设计 | `docs/06-module-detailed-design/rule-engine.md` |
| 存储设计 | `docs/06-module-detailed-design/storage.md` |
| 上下文栈参考 | [AI Memory vs RAG vs Knowledge Graph (Atlan 2026)](https://atlan.com/know/ai-memory-vs-rag-vs-knowledge-graph/) |
| Agent Memory 架构 | [The Agent Memory Race of 2026 (OSSInsight)](https://ossinsight.io/blog/agent-memory-race-2026) |
| AI Memory 综述 | [Awesome-AI-Memory (GitHub)](https://github.com/IAAR-Shanghai/Awesome-AI-Memory) |

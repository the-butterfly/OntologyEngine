# 参考项目对齐分析

> **status**: draft | **phase**: rewrite | **last_verified**: 2026-04-19

## 目的

记录 OntologyEngine Schema 设计与四个参考项目（KAG、m_flow、Cognee、MemPalace）的对齐关系，确保每个设计决策都有成熟项目的实践依据。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 设计决策缺乏外部依据，难以评估合理性 | 新特性引入时无法判断是创新还是重复造轮子 |
| 2 | 借鉴与偏离的边界不清晰 | 开发者不确定哪些设计必须遵循参考项目、哪些可以自由发挥 |
| 3 | 参考项目的优势未被系统化吸收 | 各参考项目的亮点散落在不同讨论中，缺乏统一视图 |

---

## 1. KAG (OpenSPG) 对齐分析

### 目的

分析 OntologyEngine 与 KAG（基于 OpenSPG 的知识增强生成框架）的对齐关系，明确借鉴与偏离。

### 解决的问题

KAG 是最接近 OntologyEngine 定位的开源项目，其 EntityType/ConceptType 体系、逻辑推导机制和强/弱 Schema 双模式对 OE 有直接参考价值，需要显式记录哪些是借鉴、哪些是偏离。

### 借鉴

| # | KAG 特性 | OE 对应 | 说明 |
|---|---------|---------|------|
| 1 | EntityType / ConceptType / EventType / DocumentType 四类型体系 | OE L1 EntityDeclaration + L2 DimensionDeclaration | KAG 的四类型体系启发 OE 将实体声明与分类维度分离为 L1/L2 两层 |
| 2 | IND# 逻辑推导前缀 | OE L4 逻辑边按需计算 | KAG 通过 `IND#` 前缀标记逻辑推导关系，OE 将此机制纳入 L4 逻辑边，按需计算而非预存储 |
| 3 | 属性/关系二分法 | OE AttributeDef + RelationDeclaration | KAG 明确区分属性（EntityType.property）和关系（EntityType.relation），OE 沿用此二分法 |
| 4 | 强/弱 Schema 双模式 | OE ExtractionPipeline AST+LLM 双通道 | KAG 支持 strict schema 和 fuzzy schema 两种提取模式，OE 通过 AST 通道（强 Schema）和 LLM 通道（弱 Schema）实现 |

### 偏离

| # | KAG 特性 | OE 偏离 | 原因 |
|---|---------|---------|------|
| 1 | 无 Instance 层 grammar | OE 新增完整 Instance 层 | KAG 的 Instance 由运行时动态生成，无显式 grammar。OE 需要支持版本化、溯源、质量评估，必须对 Instance 建模 |
| 2 | 无互索引边 | OE 新增四种互索引边 | KAG 通过 AtomicQuery 桥接 query→KU→chunk，但桥接结构单一。OE 需要双向可导航的互索引（extracted_from / supported_by / defined_in / trace_to）以支持推理可解释性 |

---

## 2. m_flow 对齐分析

### 目的

分析 OntologyEngine 与 m_flow（知识图谱驱动的多源信息融合框架）的对齐关系。

### 解决的问题

m_flow 在边语义、跨域实体对齐、检索字段分离等方面有成熟实践，OE 需要系统化吸收这些模式。

### 借鉴

| # | m_flow 特性 | OE 对应 | 说明 |
|---|------------|---------|------|
| 1 | Episode-Facet-FacetPoint 三层锚点 | OE KnowledgeFragment-EntityInstance-MetricValue 三层 | m_flow 的三层锚点结构将知识从原始碎片到结构化实体再到量化指标逐层精炼，OE 沿用此分层逻辑 |
| 2 | tuple\[Edge, Target\] + edge_text | OE EdgeInstance.edge_text | m_flow 的每条边携带自然语言描述（edge_text），OE 将此作为边语义的核心维度 |
| 3 | metadata.index_fields | OE ChromaDB 集合设计 | m_flow 通过 index_fields 声明哪些字段参与向量索引，OE 在 ChromaDB 集合设计中复用此模式 |
| 4 | canonical_name + same_entity_as | OE 跨域实体对齐 | m_flow 通过 canonical_name 标准化实体名称，same_entity_as 边连接不同域中的同一实体，OE 直接采用 |
| 5 | display_only 字段 | OE 检索字段与展示字段分离 | m_flow 区分参与检索的字段和仅用于展示的字段，OE 在 AttributeDef 中引入角色标记实现分离 |

### 偏离

| # | m_flow 特性 | OE 偏离 | 原因 |
|---|------------|---------|------|
| 1 | 无声明层 grammar | OE 有完整 L1-L4 声明 | m_flow 的 Schema 由 Python dataclass 隐式定义，无独立声明层。OE 需要支持领域专家声明式定义业务模型，必须有显式 grammar |

---

## 3. Cognee 对齐分析

### 目的

分析 OntologyEngine 与 Cognee（认知记忆图谱框架）的对齐关系。

### 解决的问题

Cognee 在确定性 ID 生成、溯源五维模型、反馈闭环等方面有创新设计，OE 需要明确吸收哪些模式。

### 借鉴

| # | Cognee 特性 | OE 对应 | 说明 |
|---|------------|---------|------|
| 1 | DataPoint 基类 + source_* 五维溯源 | OE Instance 层 source_pipeline/content_hash | Cognee 的 DataPoint 携带 source_pipeline、source_task、source_user、source_content_hash、source_timestamp 五维溯源信息，OE 在 Instance 层复用此模式 |
| 2 | identity_fields + UUID5 确定性 ID | OE EntityInstance.id 生成策略 | Cognee 通过 identity_fields 声明确定性字段，使用 UUID5 基于字段值生成稳定 ID，实现幂等写入。OE 在 EntityDeclaration.identity_fields 中采用此模式 |
| 3 | Annotated 字段角色标记 | OE AttributeDef 扩展角色 | Cognee 使用 Python Annotated 类型为字段标记角色（如检索字段、展示字段、索引字段），OE 在 AttributeDef 中扩展角色属性 |
| 4 | feedback_weight + importance_weight | OE 反馈闭环 | Cognee 的 feedback_weight 通过用户反馈流式更新（alpha=0.1），importance_weight 通过 topological_rank 计算，OE 在反馈闭环机制中复用此双权重模式 |
| 5 | topological_rank | OE MetricEngine DAG 排序 | Cognee 通过 PageRank 变体计算节点在知识图谱中的拓扑重要性，OE 在 MetricEngine 中使用 DAG 拓扑排序确定指标计算顺序 |

### 偏离

| # | Cognee 特性 | OE 偏离 | 原因 |
|---|------------|---------|------|
| 1 | 无四层架构 | OE L1-L4 分层更清晰 | Cognee 的 DataPoint 是扁平结构，所有类型共享同一基类。OE 需要区分声明层（L1-L4）与实例层，支持不同粒度的知识管理 |

---

## 4. MemPalace 对齐分析

### 目的

分析 OntologyEngine 与 MemPalace（轻量级记忆宫殿知识图谱系统）的对齐关系。

### 解决的问题

MemPalace 在时态窗口、软删除、分层记忆和轻量级存储架构方面有简洁有效的实现，OE 需要吸收其核心模式。

### 借鉴

| # | MemPalace 特性 | OE 对应 | 说明 |
|---|---------------|---------|------|
| 1 | valid_from / valid_to 时态窗口 | OE 时序建模 | MemPalace 每个 triple 携带 valid_from 和 valid_to 时间戳，OE 在时序实体 Instance 中直接采用此模式 |
| 2 | invalidate 软删除 | OE valid_to 设置 | MemPalace 的 invalidate() 方法设置 valid_to 标记事实不再为真，OE 在知识时效管理中复用此模式 |
| 3 | 四层记忆栈 L0-L3 | OE Layer-R/S 分层检索 | MemPalace 的 L0（工作记忆）→ L1（短期）→ L2（长期）→ L3（归档）分层记忆栈，启发 OE 的 Layer-R（原始层）与 Layer-S（结构层）分层检索策略 |
| 4 | 轻量级 SQLite + ChromaDB | OE 存储架构 | MemPalace 使用 SQLite 存储结构化知识、ChromaDB 存储向量嵌入，OE 沿用此轻量级本地优先存储架构 |

### 偏离

| # | MemPalace 特性 | OE 偏离 | 原因 |
|---|---------------|---------|------|
| 1 | 无显式 Schema | OE 有完整声明层 | MemPalace 的 Schema 由 triple 的 subject/predicate/object 隐式定义，无独立声明层。OE 需要支持领域专家声明式定义业务模型 |

---

## 5. 综合借鉴矩阵

### 目的

以 OE 特性为维度，汇总四个参考项目的贡献，形成一目了然的借鉴全景图。

### 解决的问题

单个参考项目的对齐分析分散在各自章节，难以快速判断某个 OE 特性受哪些项目影响。

### 矩阵

| OE 特性 | KAG | m_flow | Cognee | MemPalace |
|---------|-----|--------|--------|-----------|
| L1 EntityDeclaration | ✅ 四类型体系 | - | - | - |
| L2 DimensionDeclaration | ✅ 四类型体系 | - | - | - |
| L3 Analytical Elements | - | ✅ FacetPoint | ✅ importance_weight | - |
| L4 逻辑边按需计算 | ✅ IND# 前缀 | - | - | - |
| AttributeDef + RelationDeclaration | ✅ 属性/关系二分法 | - | ✅ Annotated 角色 | - |
| ExtractionPipeline 双通道 | ✅ 强/弱 Schema | - | - | - |
| Instance 层 grammar | ❌ 无（OE 独有） | - | - | - |
| 四种互索引边 | ❌ 无（OE 独有） | ✅ edge_text | - | - |
| EdgeInstance.edge_text | - | ✅ tuple[Edge,Target] | - | - |
| ChromaDB 集合设计 | - | ✅ index_fields | - | - |
| 跨域实体对齐 | - | ✅ canonical_name + same_entity_as | - | - |
| 检索/展示字段分离 | - | ✅ display_only | ✅ Annotated 角色 | - |
| Instance 溯源 | - | - | ✅ source_* 五维 | - |
| 确定性 ID 生成 | - | - | ✅ identity_fields + UUID5 | - |
| 反馈闭环 | - | - | ✅ feedback_weight | - |
| DAG 拓扑排序 | - | - | ✅ topological_rank | - |
| valid_from / valid_to | - | - | - | ✅ 时态窗口 |
| 软删除 | - | - | - | ✅ invalidate() |
| Layer-R/S 分层 | - | - | - | ✅ 四层记忆栈 |
| SQLite + ChromaDB | - | - | - | ✅ 轻量级架构 |
| 时序边（PRECEDES/SUCCEEDS） | - | - | - | - |
| 因果边（LEADS_TO 等） | - | - | - | - |
| 语义空间隔离 | - | ✅ DatasetStore | - | ✅ Wing/Room |
| 消费视图授权 | - | ✅ ENABLE_BACKEND_ACCESS_CONTROL | - | - |

**图例**：✅ = 借鉴 | ❌ = 偏离（OE 独有） | - = 无直接关联

---

## 6. OE 独有创新

### 目的

明确 OntologyEngine 在参考项目基础上做出的原创设计贡献。

### 解决的问题

避免将 OE 的创新点误认为借鉴，确保开发者理解这些设计没有外部参考可依赖，需要更审慎地验证。

### 创新清单

| # | 创新点 | 说明 | 解决的核心问题 |
|---|--------|------|---------------|
| 1 | L1-L4 四层声明 + Instance 层的完整 grammar | 四个参考项目均无完整的声明层 grammar，OE 将声明层分为 L1（事实对象）→ L2（分类）→ L3（分析要素）→ L4（业务逻辑），加上 Instance 层形成五层完整模型 | 领域专家无法声明式定义业务模型；Instance 无版本化、溯源、质量评估能力 |
| 2 | 四种互索引边 + Bundle Search 协同检索 | KAG 只有 AtomicQuery 单一桥接，m_flow 只有单向 supported_by。OE 设计四种双向互索引边（extracted_from / supported_by / defined_in / trace_to），配合 Bundle Search 路径成本传播实现协同检索 | 结构化知识与原始碎片之间缺乏双向可追溯链接；检索结果缺乏推理可解释性 |
| 3 | 语义空间隔离 + 消费视图授权 | 融合 m_flow DatasetStore 物理隔离和 MemPalace Wing/Room 逻辑隔离，增加消费视图授权机制 | 多域知识管理缺乏灵活的隔离策略；数据消费缺乏权限控制 |
| 4 | 三层资产（IT/个人/组织）统一描述 | 将知识资产按 IT 资产（数据实例）、个人知识（专家分类视角）、组织资产（共识化标准）三层统一建模，明确每层资产的归属、权限和演进路径 | 知识资产的权属和演进路径不清晰，个人知识与组织共识之间缺乏转化机制 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 核心概念（单一事实源） | [01-overview/05-concepts.md](../../01-overview/05-concepts.md) |
| 时序建模 Grammar | [02-design/schema/temporal-modeling.md](./temporal-modeling.md) |
| Schema v2 完整规范 | `docs/02-design/schema/01-schema-spec.md` |
| 当前态 Schema 规范 | [02-design/schema/01-schema-spec.md](./01-schema-spec.md) |

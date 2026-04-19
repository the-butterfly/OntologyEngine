# Schema 设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [01-overview/05-concepts.md](../../01-overview/05-concepts.md) | **last_verified**: 2026-04-19

---

## 目的

Schema 是 OntologyEngine 所有其他模块的基石。存储层（KuzuDB/ChromaDB/SQLite）的 schema、引擎层（RuleEngine/MetricEngine/QueryEngine）的执行语义、服务层的 CRUD 接口、API 层的路由结构——全部从 Schema grammar 派生。Schema 设计的质量直接决定了整个系统的可推理性、可追溯性和可扩展性。

本文档作为 Schema 设计的导航入口，回答以下问题：
- Schema 设计解决什么问题？
- 整体架构如何分层？
- 各子文档的职责是什么？
- 关键设计决策有哪些？
- 与 baseline（docs-baseline/05-schema-v2/）相比发生了什么变化？

## 解决的问题

| # | 问题 | 表现 | Schema 设计如何解决 |
|---|------|------|-------------------|
| 1 | **多版本混乱** | v1 MVP 的 `concepts/metrics/rules` 扁平结构与 v2 L1-L4 四层架构并存，术语不一致 | 统一为 Schema v2 L1-L4 四层声明，v1 术语仅保留在迁移映射表中 |
| 2 | **术语不一致** | `properties` vs `attributes`、`source/target` vs `from/to`、`element_type` vs `type` | 以 [09-canonical-schema-spec.md](../../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md) 冻结的术语为准，所有文档统一 |
| 3 | **缺少 Instance 层 grammar** | baseline 只定义了声明层，实例层（EntityInstance、CategoryTagInstance、MetricValueInstance）无统一 grammar | 新增 Instance 层子文档，定义实例与声明的映射关系 |
| 4 | **缺少互索引边 grammar** | 05-concepts.md 定义了四种互索引关系（extracted_from/supported_by/defined_in/trace_to），但 baseline 无 grammar | 新增互索引边子文档，定义边类型、属性、与 Layer-R/S 的关联 |
| 5 | **缺少时序建模 grammar** | 05-concepts.md 定义了 valid_from/valid_to 时序字段和 PRECEDES/SUCCEEDS 边，但 baseline 无 grammar | 新增时序建模子文档，定义时序实体标注、查询语义、因果链接边 |
| 6 | **声明层与参考项目洞察未融合** | KAG 的 IND# 逻辑边、m_flow 的 index_fields/display_only、Cognee 的 identity_fields/Annotated/source_* 等洞察未反映到 grammar | 在 L1-L4 声明层 grammar 中增强对应字段，并在 reference-alignment.md 中记录对齐关系 |

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│  Schema v2                                                      │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  声明层 (Declarations)                                     │  │
│  │                                                           │  │
│  │  L1: fact_objects         ── 实体 + 关系 + 属性            │  │
│  │  L2: categorizations      ── 维度 + 分类值 + 打标规则       │  │
│  │  L3: analytical_elements  ── 指标 + 阈值 + 覆盖机制         │  │
│  │  L4: business_logic       ── 规则定义 + 规则逻辑 + DAG 步骤  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  实例层 (Instances)                                        │  │
│  │  EntityInstance / EdgeInstance / CategoryTagInstance        │  │
│  │  MetricValueInstance / RuleExecutionSnapshot                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  边层 (Edge Layer)                                         │  │
│  │  互索引边: extracted_from / supported_by / defined_in /     │  │
│  │           trace_to                                         │  │
│  │  时序边: PRECEDES / SUCCEEDS / LEADS_TO / BECAUSE_OF       │  │
│  │  业务边: guarantees / supplies / employs ...                │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  时序层 (Temporal Layer)                                    │  │
│  │  valid_from / valid_to / temporal 标注 / as_of 查询语义     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  semantic_space: 元数据容器（id / name / type / status / version）│
└─────────────────────────────────────────────────────────────────┘
```

### 层间数据流

```
L1 fact_objects
  │
  ├── 属性 ──────────────► L3 atomic metrics（source/formula）
  │                           │
  │                           ├── dependencies ──► L3 derived metrics
  │                           │
  │                           └── components ────► L3 composite metrics
  │
  ├── 属性 ──────────────► L4 inputs（via attribute 引用）
  │
  └── 关系 ──────────────► L3 graph metrics（via 图数据库）
                              │
                              ▼
                          L4 graph_op 算子

L2 categorizations
  │
  ├── hierarchical ──► L4 applicable_conditions 过滤
  │
  └── derived (rule_logic) ──► L4 rule_logic 复用

L3 metrics
  │
  ├── overridable ──► L4 rule_definitions.overrides
  │
  └── dependencies ──► L4 inputs（via metric 引用）

L4 rule_logics.steps
  │
  ├── condition 引用：L1 属性 / L3 指标 / L2 维度 / 其他 step 输出
  │
  └── action 输出 ──► L4 rule_outputs / 触发 L2 derived 维度值
```

---

## 文档地图

| 文档 | 职责 | 状态 |
|------|------|------|
| [README.md](./README.md) | Schema 设计导航入口（本文档） | draft |
| [L1-L4-declarations.md](./L1-L4-declarations.md) | L1-L4 声明层完整 grammar 定义 | draft |
| [instance-layer.md](./instance-layer.md) | 实例层 grammar：EntityInstance、EdgeInstance、CategoryTagInstance、MetricValueInstance | planned |
| [mutual-index-edges.md](./mutual-index-edges.md) | 互索引边 grammar：四种关系类型、属性、与 Layer-R/S 关联 | planned |
| [temporal-modeling.md](./temporal-modeling.md) | 时序建模 grammar：valid_from/to、时序边、因果链接、查询语义 | planned |
| [reference-alignment.md](./reference-alignment.md) | 参考项目对齐：KAG/m_flow/Cognee/MemPalace 洞察与 grammar 增强映射 | planned |

**规范层级关系**：

```
01-overview/05-concepts.md          ← 术语与概念唯一事实源
         │
         ▼
02-design/schema/L1-L4-declarations.md  ← 声明层 grammar 唯一事实源
         │
         ├── instance-layer.md
         ├── mutual-index-edges.md
         ├── temporal-modeling.md
         └── reference-alignment.md
```

---

## 关键设计决策

| # | 决策 | 选择 | 备选 | 理由 |
|---|------|------|------|------|
| 1 | **四层分离** | L1 事实 / L2 分类 / L3 分析 / L4 逻辑 | 扁平结构（v1） | v1 的 concepts/metrics/rules 混杂导致属性与分析结果不分、规则与数据绑定 |
| 2 | **声明与实例分离** | 声明层定义类型，实例层承载数据 | 声明实例混合 | 一个声明可关联多个实例（如不同行业的信用检查规则），提升复用性 |
| 3 | **SemanticConcept 废弃** | L2 `tag_based` 承担标签功能 | 独立 Concept 层 | 本地知识库场景够用；跨域泛化通过多 Space 知识融合实现（方案 A1） |
| 4 | **L2 derived 复用 L4** | derived 维度通过 `rule_logic` 引用 L4 规则逻辑 | L2 自带计算逻辑 | 避免重复定义，统一执行引擎，分类计算与业务规则复用同一执行器 |
| 5 | **L3 overridable 机制** | 指标声明 `overridable=true`，L4 通过 `overrides` 覆盖 | 指标计算逻辑固定 | 不同业务场景需要不同的计算逻辑（如授信额度按行业差异化），但需声明式控制 |
| 6 | **L4 规则定义 + 规则逻辑分离** | `rule_definitions` 定义作用域/IO，`rule_logics` 定义执行步骤 | 规则定义与逻辑一体 | 一个定义可关联多个逻辑（如制造业/批发零售不同条件分支），提升场景适配性 |
| 7 | **属性增强字段** | 新增 `identity_fields`、`index_fields`、`display_only`、`source_*` | 仅保留 name/type/required | 参考 Cognee（identity_fields/source_* 溯源）、m_flow（index_fields/display_only 元数据） |
| 8 | **互索引边独立建模** | 四种专门关系类型分立，边携带 offset/confidence/edge_text | KAG 式 AtomicQuery 统一桥接 | 推理可解释性优先，四种关系语义不同需分立管理 |
| 9 | **时序字段声明式** | EntityDeclaration 中 `temporal: true` 标注，实例层 `valid_from/valid_to` | 所有实体强制时序 | 静态实体（法人姓名、营业执照号）无需时序开销，显式标注更精确 |
| 10 | **枚举隐式声明** | 枚举值在 Instance 层定义，声明层仅通过 `enum_type` 引用 | 枚举独立声明节 | 枚举值随业务变化频繁，与实例数据同层管理更灵活 |

---

## 与 baseline 的偏差

| 主题 | baseline（docs-baseline/05-schema-v2/） | 当前设计 | 变更原因 |
|------|---------------------------------------|---------|---------|
| **L1 属性增强** | AttributeDef 仅含 name/type/required/unique/description + 类型特定字段 | 新增 `identity_fields`（实体级）、`index_fields`（属性级）、`display_only`、`source_*` 溯源字段 | Cognee 的 identity_fields 提供实体唯一性约束；m_flow 的 index_fields 提供存储索引提示；display_only 区分展示与计算属性 |
| **L1 关系增强** | RelationDeclaration 含 from/to/cardinality/attributes | 新增 `logical_type`（IND# 逻辑边类型标注，参考 KAG） | KAG 的 IND# 逻辑边区分业务关系与推理关系，支持规则引擎的关系类型过滤 |
| **L3 指标增强** | MetricDeclaration 含 type/value_type/source/formula/dependencies/overridable | 新增 `identity_fields`（指标级）、`source_pipeline`/`source_task`（溯源，参考 Cognee DataPoint） | Cognee 的 source_* 模式提供指标计算的可追溯性 |
| **L4 规则增强** | RuleDefinitionDeclaration 含 applies_to/preconditions/inputs/outputs/overrides | 新增 `applicability` 六维度模型（when/why/boundary/outcome/prereq/exception，参考 m_flow ContextPack） | m_flow 的 ContextPack 六维度是规则适用性边界的最佳实践，提升规则可解释性 |
| **Instance 层** | baseline 各子文档分散描述实例结构 | 统一为独立 instance-layer.md | 实例层有统一的元数据模式（_created_at/_updated_at/_version）和与声明层的映射关系，需集中定义 |
| **互索引边** | baseline 无 grammar | 新增 mutual-index-edges.md | 05-concepts.md 定义了四种互索引关系，需 grammar 化 |
| **时序建模** | baseline 无 grammar | 新增 temporal-modeling.md | 05-concepts.md 定义了时序字段和时序边，需 grammar 化 |
| **文档结构** | baseline 01-04 分层文档 + 09 canonical spec | L1-L4-declarations.md 统一声明层 + 子文档分主题 | baseline 的 01-04 文档存在 grammar 重复定义（与 09 冲突），统一后消除歧义 |

---

## 与其他模块的依赖关系

```
Schema grammar（本文档）
    │
    ├──► 存储层 schema（KuzuDB/ChromaDB/SQLite 的 DDL 从 grammar 派生）
    │
    ├──► 规则引擎（DAG 执行语义从 L4 rule_logics.steps 派生）
    │
    ├──► 指标引擎（计算依赖图从 L3 dependencies/components 派生）
    │
    ├──► 查询引擎（查询路由从 L1-L4 层间引用关系派生）
    │
    ├──► 服务层（CRUD 接口从声明/实例分离模式派生）
    │
    └──► API 层（路由结构从 semantic_space + 四层容器派生）
```

Schema 设计必须最先完成（ROADMAP Phase 1），是所有后续 Phase 的基础。

---

## 参考文档

| 主题 | 文档 |
|------|------|
| 术语与概念 | [01-overview/05-concepts.md](../../01-overview/05-concepts.md) |
| Schema 最新规范 | [02-design/schema/01-schema-spec.md](../schema/01-schema-spec.md) |
| 冻结的 canonical grammar | [docs-baseline/05-schema-v2/09-canonical-schema-spec.md](../../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md) |
| baseline L1 详情 | [docs-baseline/05-schema-v2/01-fact-objects.md](../../../docs-baseline/05-schema-v2/01-fact-objects.md) |
| baseline L2 详情 | [docs-baseline/05-schema-v2/02-categorization.md](../../../docs-baseline/05-schema-v2/02-categorization.md) |
| baseline L3 详情 | [docs-baseline/05-schema-v2/03-analytical-elements.md](../../../docs-baseline/05-schema-v2/03-analytical-elements.md) |
| baseline L4 详情 | [docs-baseline/05-schema-v2/04-business-logic.md](../../../docs-baseline/05-schema-v2/04-business-logic.md) |
| baseline 概览 | [docs-baseline/05-schema-v2/00-overview.md](../../../docs-baseline/05-schema-v2/00-overview.md) |
| 技术实现框架决策 | [discuss/2026-04-19-tech-impl-framework-decisions.md](../../../discuss/2026-04-19-tech-impl-framework-decisions.md) |

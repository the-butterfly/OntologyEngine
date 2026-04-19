# Instance 层 Grammar

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/05-concepts.md` | **last_verified**: 2026-04-19

## 目的

定义 L1-L4 声明的实例层数据结构——即填充知识图谱的实际数据。Instance 层是 Schema 声明的运行时体现：L1 的 EntityDeclaration 和 RelationDeclaration 产出 EntityInstance 与 EdgeInstance，L2 的 DimensionDeclaration 产出 CategoryTag，L3 的 MetricDeclaration 产出 MetricValue，Layer-R 的 Dataset 产出 KnowledgeFragment。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 冻结的 canonical spec（`01-schema-spec.md`）只定义了声明层（Declaration），没有 Instance 层语法 | 实例数据结构隐含在代码中，无法跨模块对齐 |
| 2 | 实例与声明的关系未形式化 | 无法验证实例是否合规于其声明 |
| 3 | 时序、溯源、置信度等横切关注点在实例层缺乏统一字段定义 | 各模块各自实现，字段名和语义不一致 |
| 4 | Layer-R 的 KnowledgeFragment 与 Layer-S 的 EntityInstance 缺乏统一实例模型 | 互索引边无法在统一类型系统上定义 |

---

## 数据结构总览

```
┌──────────────────────────────────────────────────────────────────┐
│  Instance 层                                                     │
│                                                                  │
│  EntityInstance        ← L1 EntityDeclaration 的运行时实例        │
│  EdgeInstance          ← L1 RelationDeclaration 的运行时实例      │
│  CategoryTag           ← L2 DimensionDeclaration 的运行时实例     │
│  MetricValue           ← L3 MetricDeclaration 的运行时实例       │
│  KnowledgeFragment     ← Layer-R 原始知识碎片                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## EntityInstance

### 目的

表示 L1 EntityDeclaration 的具体数据实例，是知识图谱中的核心节点。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 实例身份标识不稳定 | UUID5 基于 identity_fields 确定性生成，同一业务实体始终产出相同 ID |
| 2 | 时序实体无版本管理 | valid_from/valid_to 字段支持时间切片查询 |
| 3 | 数据来源不可追溯 | source_pipeline + source_content_hash 构成溯源链 |
| 4 | 反馈无法影响检索排序 | feedback_weight 参与检索评分公式 |

### 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string | 是 | — | UUID5，基于 identity_fields 确定性生成 |
| `_fact_object` | string | 是 | — | 引用 L1 EntityDeclaration.name，声明此实例归属的 Fact Object |
| `attributes` | dict | 是 | — | 键值对，键为 AttributeDef.name，值为实际值 |
| `valid_from` | datetime? | 条件 | null | 当 EntityDeclaration.temporal=true 时必填 |
| `valid_to` | datetime? | 否 | null | null 表示当前有效 |
| `created_at` | datetime | 是 | — | 实例创建时间 |
| `updated_at` | datetime | 是 | — | 实例最后更新时间 |
| `domain_id` | string? | 否 | null | 语义空间域 ID，支持逻辑隔离 |
| `confidence` | float | 否 | 1.0 | 置信度，范围 [0, 1] |
| `source_pipeline` | string? | 否 | null | 来源管道标识（如 "ingest_pdf"、"rule_editor"） |
| `source_content_hash` | string? | 否 | null | 来源内容 SHA256 哈希，用于增量缓存和矛盾检测 |
| `feedback_weight` | float | 否 | 0.5 | 反馈权重，参与检索评分：final = λ × semantic + (1-λ) × feedback_weight |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-EI-1 | `id` 必须为合法 UUID5 格式 | 确定性 ID 保证幂等写入 |
| V-EI-2 | `_fact_object` 必须引用已存在的 EntityDeclaration.name | 实例必须合规于声明 |
| V-EI-3 | `attributes` 的键集合必须是 EntityDeclaration.attributes 的子集 | 不允许未声明的属性 |
| V-EI-4 | `attributes` 中必填属性（required=true）的值不能为 null | 声明约束在实例层强制执行 |
| V-EI-5 | 当 EntityDeclaration.temporal=true 时，`valid_from` 不能为 null | 时序实体必须有生效时间 |
| V-EI-6 | `valid_to` 为 null 或 `valid_to > valid_from` | 时间区间语义正确 |
| V-EI-7 | `confidence` ∈ [0, 1] | 置信度范围约束 |
| V-EI-8 | `feedback_weight` ∈ [0, 1] | 反馈权重范围约束 |
| V-EI-9 | 同一 `_fact_object` + identity_fields 组合的 `id` 必须唯一 | UUID5 确定性保证 |
| V-EI-10 | 同一实体在相同时段内（valid_from/valid_to 区间重叠）只能有一个有效版本 | 时序唯一性约束 |

### 参考项目对齐

| 字段 | 参考项目 | 对齐说明 |
|------|----------|----------|
| `id` (UUID5) | Cognee | Cognee 使用 UUID5 基于 identity 字段确定性生成 DataPoint ID，保证同一业务实体跨管道幂等 |
| `confidence` | MemPalace | MemPalace 的 triple 级置信度评分，OntologyEngine 将其提升为实例级字段 |
| `source_pipeline` | Cognee | Cognee DataPoint.source_pipeline，标识数据产出管道 |
| `source_content_hash` | Cognee | Cognee DataPoint.source_content_hash，SHA256 哈希用于增量缓存和去重 |
| `feedback_weight` | Cognee | Cognee apply_feedback_weights.py 的流式更新机制：updated = previous + α × (normalized - previous) |
| `domain_id` | MemPalace | MemPalace Wing/Room 逻辑隔离模式，通过元数据过滤实现域隔离 |
| `valid_from/valid_to` | MemPalace | MemPalace Validity Window 模式，invalidate() 设置 valid_to 标记事实失效 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-EI-1 | 使用 UUID5 而非 UUID4 | 确定性 ID 支持幂等写入：同一业务实体从不同管道摄入时产出相同 ID，避免重复实例 |
| D-EI-2 | `_fact_object` 使用下划线前缀 | 区分元数据字段与业务属性字段，避免与 attributes 中的键名冲突 |
| D-EI-3 | 时序字段放在实例层而非声明层 | 声明层只标记 temporal=true，具体的时间区间由实例携带，一个声明可有多个时间版本 |
| D-EI-4 | `feedback_weight` 默认 0.5 | 中性初始值，既不偏向也不偏离，随反馈逐步调整 |
| D-EI-5 | `attributes` 使用扁平 dict 而非嵌套结构 | 与 canonical spec 的 AttributeDef 定义对齐，键为 name 字符串，值为标量或简单类型 |

---

## EdgeInstance

### 目的

表示 L1 RelationDeclaration 的具体数据实例，是知识图谱中的边。边不仅是类型标签，而是可被独立检索、评分、参与推理的语义载体（核心启示来自 m_flow）。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 边缺乏语义表达 | edge_text 携带自然语言描述，向量化后参与 Bundle Search |
| 2 | 边权重缺失 | weight 字段支持多维度权重，参与推理成本传播 |
| 3 | 关系属性无结构 | attributes dict 承载业务属性（如担保金额、期限） |
| 4 | 时序关系无版本管理 | valid_from/valid_to 支持关系的时间有效性 |

### 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string | 是 | — | 唯一标识 |
| `from_id` | string | 是 | — | 源 EntityInstance.id |
| `to_id` | string | 是 | — | 目标 EntityInstance.id |
| `relation_name` | string | 是 | — | 引用 L1 RelationDeclaration.name |
| `attributes` | dict? | 否 | null | 关系属性，键为 RelationDeclaration 中定义的属性名 |
| `edge_text` | string? | 否 | null | 关系语义文本（借鉴 m_flow），向量化后参与 Bundle Search |
| `weight` | float? | 否 | null | 关系权重，参与推理成本传播和风险传导计算 |
| `valid_from` | datetime? | 否 | null | 关系生效时间 |
| `valid_to` | datetime? | 否 | null | null 表示当前有效 |
| `confidence` | float | 否 | 1.0 | 置信度 |
| `source_pipeline` | string? | 否 | null | 来源管道 |
| `source_content_hash` | string? | 否 | null | 来源内容哈希 |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-ED-1 | `from_id` 和 `to_id` 必须引用已存在的 EntityInstance.id | 引用完整性 |
| V-ED-2 | `from_id` ≠ `to_id` | 禁止自环（业务关系语义下无意义） |
| V-EI-3 | `relation_name` 必须引用已存在的 RelationDeclaration.name | 实例必须合规于声明 |
| V-ED-4 | `from_id` 对应的 EntityInstance._fact_object 必须匹配 RelationDeclaration.source | 源类型约束 |
| V-ED-5 | `to_id` 对应的 EntityInstance._fact_object 必须匹配 RelationDeclaration.target | 目标类型约束 |
| V-ED-6 | `attributes` 的键集合必须是 RelationDeclaration.attributes 的子集 | 不允许未声明的属性 |
| V-ED-7 | `valid_to` 为 null 或 `valid_to > valid_from` | 时间区间语义正确 |
| V-ED-8 | `confidence` ∈ [0, 1] | 置信度范围约束 |
| V-ED-9 | `weight` 为 null 或 `weight` ∈ (0, 1] | 权重范围约束 |

### 参考项目对齐

| 字段 | 参考项目 | 对齐说明 |
|------|----------|----------|
| `edge_text` | m_flow | m_flow 的每条边携带自然语言描述，向量化后与节点一同参与检索，打破"边只是类型标签"的传统 |
| `weight` | m_flow | m_flow Bundle Search 的边代价传播：路径成本 = Σ(边向量距离 + 跳数惩罚) |
| `attributes` | m_flow | m_flow FacetPoint 的属性字典，承载业务语义（金额、期限、比例） |
| `confidence` | Graphify | Graphify validate_extraction() 要求每条边携带 confidence，AMBIGUOUS 边标记为需人工审查 |
| `source_pipeline` / `source_content_hash` | Cognee | Cognee DataPoint 溯源链模式 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-ED-1 | `edge_text` 可选而非必填 | 结构化关系（如外键关联）可能无自然语言描述；LLM 提取或人工标注的关系才有语义文本 |
| D-ED-2 | `weight` 可选而非必填 | 简单关系无需权重；只有参与推理成本传播的关系（如 guarantees 传递风险）才需要 |
| D-ED-3 | 边不携带 `feedback_weight` | 边的反馈通过 `weight` 间接体现；避免字段冗余 |
| D-ED-4 | `attributes` 与 `edge_text` 分离 | attributes 承载结构化业务属性，edge_text 承载非结构化语义描述，职责不同 |

---

## CategoryTag

### 目的

表示 L2 DimensionDeclaration 对 EntityInstance 的分类标注结果。CategoryTag 是 L2 声明的运行时实例，将实体归入分类体系的某个值。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | L2 分类结果无独立数据结构 | 分类标注隐含在实体属性中，无法独立查询和追溯 |
| 2 | 分类来源不明确 | assigned_by 字段区分规则自动归类、人工标注、LLM 推断 |
| 3 | 分类置信度缺失 | confidence 字段支持 LLM 推断场景下的不确定性表达 |

### 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `entity_id` | string | 是 | — | 引用 EntityInstance.id |
| `dimension_name` | string | 是 | — | 引用 L2 DimensionDeclaration.name |
| `value_code` | string | 是 | — | 引用 ValueDefinition.code |
| `assigned_at` | datetime | 是 | — | 标注时间 |
| `assigned_by` | string? | 否 | null | 标注来源："rule" \| "manual" \| "llm" |
| `confidence` | float | 否 | 1.0 | 置信度 |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-CT-1 | `entity_id` 必须引用已存在的 EntityInstance.id | 引用完整性 |
| V-CT-2 | `dimension_name` 必须引用已存在的 DimensionDeclaration.name | 声明合规 |
| V-CT-3 | `value_code` 必须在 DimensionDeclaration 的 ValueDefinition 中存在 | 值域约束 |
| V-CT-4 | `dimension_name` 对应的 DimensionDeclaration.applicable_to 必须包含 `entity_id` 对应的 EntityInstance._fact_object | 适用性约束 |
| V-CT-5 | 同一 `entity_id` + `dimension_name` 组合唯一 | 一个实体在一个维度下只能有一个值 |
| V-CT-6 | `assigned_by` 为 null 或 ∈ {"rule", "manual", "llm"} | 来源枚举约束 |
| V-CT-7 | `confidence` ∈ [0, 1] | 置信度范围约束 |
| V-CT-8 | 当 `assigned_by` = "rule" 时，`confidence` 必须为 1.0 | 规则归类是确定性的 |

### 参考项目对齐

| 字段 | 参考项目 | 对齐说明 |
|------|----------|----------|
| `dimension_name` + `value_code` | KAG | KAG 的 MatchConfig 实体链接模式：通过维度+值码将实体归入分类体系 |
| `assigned_by` | LLM-Wiki | LLM-Wiki-Agent 的 lint/heal 区分确定性检查与 LLM 语义检查 |
| `confidence` | Graphify | Graphify 的 AMBIGUOUS 边标记模式：LLM 推断结果携带低置信度，需人工审查 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-CT-1 | CategoryTag 不设独立 `id` | 以 (entity_id, dimension_name) 作为复合主键，天然唯一且查询友好 |
| D-CT-2 | `assigned_by` 使用枚举字符串而非整数编码 | 可读性优先，分类来源种类有限，无需编码映射 |
| D-CT-3 | 规则归类的 confidence 强制为 1.0 | 规则执行是确定性的，不存在不确定性；只有 LLM 推断才引入置信度 |

---

## MetricValue

### 目的

表示 L3 MetricDeclaration 的计算结果实例。MetricValue 记录指标在特定时间点对特定实体的计算值，以及计算的来源和上下文。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 指标计算结果无独立存储 | 计算结果隐含在实体属性中，无法追溯计算过程 |
| 2 | 计算来源不明确 | computed_by 区分引擎计算、规则覆盖、人工录入 |
| 3 | 计算快照无法关联 | computation_snapshot 引用 ExecutionStepSnapshot，支持全链路追溯 |

### 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `entity_id` | string | 是 | — | 引用 EntityInstance.id |
| `metric_name` | string | 是 | — | 引用 L3 MetricDeclaration.name |
| `value` | any | 是 | — | 计算结果值，类型由 MetricDeclaration.result_type 决定 |
| `computed_at` | datetime | 是 | — | 计算时间 |
| `valid_from` | datetime? | 否 | null | 值的生效时间 |
| `valid_to` | datetime? | 否 | null | null 表示当前有效 |
| `computed_by` | string? | 否 | null | 计算来源："engine" \| "rule_override" \| "manual" |
| `computation_snapshot` | dict? | 否 | null | ExecutionStepSnapshot 引用，记录完整计算上下文 |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-MV-1 | `entity_id` 必须引用已存在的 EntityInstance.id | 引用完整性 |
| V-MV-2 | `metric_name` 必须引用已存在的 MetricDeclaration.name | 声明合规 |
| V-MV-3 | `metric_name` 对应的 MetricDeclaration.scope 必须匹配 `entity_id` 对应的 EntityInstance._fact_object | 适用性约束 |
| V-MV-4 | `value` 的类型必须匹配 MetricDeclaration.result_type | 类型合规 |
| V-MV-5 | 同一 `entity_id` + `metric_name` + `valid_from` 组合唯一 | 时序唯一性 |
| V-MV-6 | `valid_to` 为 null 或 `valid_to > valid_from` | 时间区间语义正确 |
| V-MV-7 | `computed_by` 为 null 或 ∈ {"engine", "rule_override", "manual"} | 来源枚举约束 |
| V-MV-8 | 当 `computed_by` = "engine" 时，`computation_snapshot` 不能为 null | 引擎计算必须记录快照 |

### 参考项目对齐

| 字段 | 参考项目 | 对齐说明 |
|------|----------|----------|
| `computation_snapshot` | m_flow | m_flow Procedure 的执行快照模式，记录完整计算上下文用于追溯 |
| `computed_by` | Cognee | Cognee DataPoint 的 source_pipeline 模式，区分数据产出路径 |
| `valid_from/valid_to` | MemPalace | MemPalace Validity Window 模式，支持指标值的时序查询 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-MV-1 | MetricValue 不设独立 `id` | 以 (entity_id, metric_name, valid_from) 作为复合主键 |
| D-MV-2 | `value` 类型为 any | 指标值类型多样（float、int、bool、enum），由 MetricDeclaration.result_type 约束而非字段类型 |
| D-MV-3 | `computation_snapshot` 为 dict 而非 string | 快照是结构化数据，dict 便于查询和序列化；具体结构由 ExecutionStepSnapshot 定义 |
| D-MV-4 | 引擎计算强制关联快照 | 确保每个自动计算结果都可追溯到完整的计算过程，支持审计和调试 |

---

## KnowledgeFragment

### 目的

表示 Layer-R 的原始知识碎片——从 Dataset 或非结构化文档中提取的最小可检索单元。KnowledgeFragment 是 Layer-R 的核心存储单元，保留原文内容及其向量嵌入。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 原始文档无法被语义检索 | text + vector_id 实现原文内容与向量嵌入的双存储 |
| 2 | 碎片来源不可追溯 | dataset_id + document_id + offset 定位到原始文档的精确位置 |
| 3 | 提取状态不可追踪 | extraction_status 枚举标记碎片在提取管线中的阶段 |
| 4 | 增量处理缺乏依据 | content_hash 支持 SHA256 比对，避免重复处理 |

### 字段定义

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | string | 是 | — | 唯一标识 |
| `dataset_id` | string | 是 | — | 引用 Dataset.id |
| `document_id` | string | 是 | — | 文档标识 |
| `chunk_index` | integer | 是 | — | 文档内分片序号 |
| `offset_start` | integer | 是 | — | 字符偏移起始 |
| `offset_end` | integer | 是 | — | 字符偏移终止 |
| `text` | string | 是 | — | 原文内容（Layer-R 核心） |
| `vector_id` | string? | 否 | null | ChromaDB 向量 ID |
| `metadata` | dict? | 否 | null | 扩展元数据（author、date、tags 等） |
| `extraction_status` | enum | 是 | — | pending \| extracted \| failed |
| `content_hash` | string? | 否 | null | SHA256 内容哈希，用于增量缓存 |
| `created_at` | datetime | 是 | — | 创建时间 |
| `updated_at` | datetime | 是 | — | 最后更新时间 |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-KF-1 | `dataset_id` 必须引用已存在的 Dataset.id | 引用完整性 |
| V-KF-2 | `offset_end` > `offset_start` | 偏移区间语义正确 |
| V-KF-3 | `chunk_index` ≥ 0 | 序号非负 |
| V-KF-4 | `text` 不能为空字符串 | 空碎片无意义 |
| V-KF-5 | `extraction_status` ∈ {"pending", "extracted", "failed"} | 状态枚举约束 |
| V-KF-6 | 同一 `dataset_id` + `document_id` + `chunk_index` 组合唯一 | 分片唯一性 |
| V-KF-7 | 当 `extraction_status` = "extracted" 时，`vector_id` 不能为 null | 已提取碎片必须有向量索引 |
| V-KF-8 | `content_hash` 若非 null，必须为合法 SHA256 十六进制字符串（64 字符） | 哈希格式约束 |

### 参考项目对齐

| 字段 | 参考项目 | 对齐说明 |
|------|----------|----------|
| `text` + `vector_id` | MemPalace | MemPalace Drawer 模式：原文块存储 + ChromaDB 向量检索，垂直领域可达 96.6% R@5 基线 |
| `dataset_id` + `document_id` + `offset_*` | KAG | KAG Chunk 的精确定位模式，OntologyEngine 增加字符级偏移实现段落级溯源 |
| `extraction_status` | KAG | KAG 的提取管线状态追踪 |
| `content_hash` | Cognee | Cognee DataPoint.source_content_hash，SHA256 哈希用于增量缓存和去重 |
| `metadata` | m_flow | m_flow ContentFragment 的扩展元数据模式 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-KF-1 | `vector_id` 可选 | 碎片创建时可能尚未向量化（extraction_status=pending）；向量化是异步步骤 |
| D-KF-2 | 使用字符偏移而非段落/页码 | 字符偏移是文档无关的通用定位方式，段落/页码依赖文档格式 |
| D-KF-3 | `content_hash` 可选 | 向后兼容旧数据；新数据应强制填充 |
| D-KF-4 | `extraction_status` 区分 pending/extracted/failed | 三态覆盖碎片生命周期：创建→提取成功/提取失败 |

---

## 实例层与声明层的映射关系

### 目的

明确每个实例类型与其声明层的引用关系，确保实例数据始终合规于声明约束。

### 映射表

| 实例类型 | 引用的声明 | 引用字段 | 约束语义 |
|----------|-----------|----------|----------|
| EntityInstance | EntityDeclaration | `_fact_object` → `.name` | 实例的属性键集合 ⊆ 声明的属性定义 |
| EdgeInstance | RelationDeclaration | `relation_name` → `.name` | 实例的 from/to 类型必须匹配声明的 source/target |
| CategoryTag | DimensionDeclaration | `dimension_name` → `.name` | value_code 必须在声明的 ValueDefinition 中存在 |
| MetricValue | MetricDeclaration | `metric_name` → `.name` | value 类型必须匹配声明的 result_type |
| KnowledgeFragment | Dataset | `dataset_id` → `.id` | 碎片归属的数据集必须存在 |

### 引用完整性策略

```
写入时：验证引用字段指向的声明是否存在，不存在则拒绝写入
删除时：级联检查——删除声明前检查是否有实例引用它
更新时：声明变更时检查是否破坏已有实例的合规性
```

---

## 横切关注点

### 时序建模

仅 EntityInstance 和 EdgeInstance 携带 valid_from/valid_to 字段。查询语义：

| 查询模式 | 语义 | SQL 等价 |
|----------|------|----------|
| 当前版本 | 返回 valid_to IS NULL 的记录 | `WHERE valid_to IS NULL` |
| 指定时点 | 返回 valid_from ≤ as_of < valid_to 的记录 | `WHERE valid_from <= :as_of AND (valid_to IS NULL OR valid_to > :as_of)` |
| 全量历史 | 返回所有版本 | 无过滤 |

### 溯源链

EntityInstance、EdgeInstance 共享 source_pipeline + source_content_hash 溯源模式（借鉴 Cognee DataPoint）：

```
source_pipeline: 标识数据产出管道（如 "ingest_pdf"、"rule_editor"、"manual"）
source_content_hash: SHA256 哈希，用于增量缓存和矛盾检测
```

### 置信度体系

| 场景 | confidence 值 | 说明 |
|------|--------------|------|
| 确定性提取（AST 解析） | 1.0 | 结构化数据直接映射，无不确定性 |
| LLM 语义推断 | 0.4-0.9 | LLM 提取的实体/关系，置信度由模型输出 |
| 模糊匹配 | 0.1-0.3 | 低置信度结果标记为需人工审查 |

### 反馈闭环

feedback_weight 参与检索评分公式（借鉴 Cognee apply_feedback_weights.py）：

```
final_score = λ × semantic_score + (1 - λ) × feedback_weight

更新规则：
  updated = previous + α × (normalized_feedback - previous)
  α = 0.1（学习率，可配置）
```

---

## 与互索引边的关系

Instance 层的数据结构是互索引边的端点。互索引边连接 Layer-S 实例（EntityInstance、RuleDefinition 等）与 Layer-R 碎片（KnowledgeFragment），实现双层协同检索。互索引边的完整语法见 `docs/02-design/schema/mutual-index-edges.md`。

| 互索引边类型 | 源端实例 | 目标端实例 |
|-------------|---------|-----------|
| EXTRACTED_FROM | EntityInstance | KnowledgeFragment |
| SUPPORTED_BY | KnowledgeFragment | EntityInstance |
| DEFINED_IN | RuleDefinition / MetricDeclaration | KnowledgeFragment |
| TRACE_TO | ExecutionStepSnapshot | KnowledgeFragment |

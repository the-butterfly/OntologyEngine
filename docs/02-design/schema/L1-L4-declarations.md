# L1-L4 声明层 Grammar

> **status**: draft | **phase**: rewrite | **source_of_truth**: [01-overview/05-concepts.md](../../01-overview/05-concepts.md) + [docs-baseline/05-schema-v2/09-canonical-schema-spec.md](../../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md) | **last_verified**: 2026-04-19

---

## 目的

本文档定义 Schema v2 L1-L4 声明层的完整 grammar，作为类型定义的唯一事实源。存储层的 DDL、SchemaLoader 的解析规则、引擎层的执行语义，均以本文档为准。

## 解决的问题

| # | 问题 | 表现 | 本文如何解决 |
|---|------|------|-------------|
| 1 | **v1 概念混杂** | `concepts` 同时包含实体、关系、指标，`attributes` 既存事实又存分析结果 | L1-L4 四层分离，每层有明确职责边界 |
| 2 | **扁平规则结构** | v1 的 `ruleset` 是扁平的 when/then，无步骤依赖、无算子类型 | L4 `rule_logics.steps` 支持 DAG 依赖 + 6 种算子类型 |
| 3 | **缺少分类层** | v1 无独立分类层，分类逻辑散落在规则中 | L2 `categorizations` 独立声明，三种类型（hierarchical/derived/tag_based） |
| 4 | **术语不一致** | baseline 01-04 子文档与 09 canonical spec 存在 grammar 重复定义 | 本文以 09 canonical spec 为基础增强，消除重复定义 |
| 5 | **参考项目洞察未融合** | KAG/m_flow/Cognee 的字段设计洞察未反映到 grammar | 在各层 grammar 中增强对应字段，并标注来源 |

---

## 根级结构

```yaml
schema_version: "2.0"

semantic_space:
  id: string
  name: string
  type: enum                     # management | consumption
  status: enum                   # DRAFT | ACTIVE | ARCHIVED | PUBLISHED
  version: string                # SemVer X.Y.Z
  description: string?
  created_at: string?            # ISO 8601
  updated_at: string?            # ISO 8601

fact_objects:                    # L1
  entities: [EntityDeclaration]
  relations: [RelationDeclaration]

categorizations:                 # L2
  dimensions: [DimensionDeclaration]

analytical_elements:             # L3
  metrics: [MetricDeclaration]

business_logic:                  # L4
  rule_definitions: [RuleDefinitionDeclaration]
  rule_logics: [RuleLogicDeclaration]
```

### 目的

根级结构定义 Schema 的顶层容器和四层声明入口。`semantic_space` 提供元数据与版本管理，四层声明按职责分离。

### 解决的问题

- v1 无顶层容器，Schema 和 Instance 分散
- `semantic_space.type` 区分管理空间（可编辑）与消费视图（只读），解决多租户数据隔离需求

---

## L1: fact_objects

### 目的

L1 定义领域模型的核心抽象——实体类型和关系类型。只包含可观测、可验证的事实，不包含分析结果或业务逻辑。

### 解决的问题

- v1 的 `concepts` 混杂实体和关系，`attributes` 既存事实又存分析结果
- 缺少实体唯一性约束和存储索引提示
- 缺少属性来源溯源

### entities: [EntityDeclaration]

```yaml
- name: string                    # 实体类型名称，全局唯一
  description: string?
  attributes: [AttributeDef]      # 属性定义列表
  key_attributes: [string]?       # 关键属性名列表，用于快速识别
  identity_fields: [string]?      # 实体唯一性字段组合（参考 Cognee）
  temporal: boolean = false       # 是否为时序实体（参考 MemPalace validity window）
```

**`identity_fields` 说明**（参考 Cognee）：
- 声明实体的业务唯一性约束，如 `["unified_social_code"]` 或 `["company_name", "registered_address"]`
- 用于 Ingestion 时实体去重和矛盾检测
- 与 `key_attributes` 的区别：`key_attributes` 用于快速识别（展示），`identity_fields` 用于唯一性判定（逻辑）

**`temporal` 说明**（参考 MemPalace）：
- `temporal: true` 的实体在实例层自动携带 `valid_from` / `valid_to` 字段
- 静态实体（法人姓名、营业执照号）无需时序开销

### AttributeDef

```yaml
- name: string                    # 属性名
  type: enum                      # string | integer | decimal | boolean | date | datetime | enum | Money | JSON
  required: boolean = false       # 是否必填
  unique: boolean = false         # 是否唯一
  description: string?
  enum_type: string?              # 当 type=enum 时，引用枚举类型名
  currency: string?               # 当 type=Money 时，货币代码（ISO 4217，如 CNY）
  default: any?                   # 默认值
  pattern: string?                # 当 type=string 时，Regex 校验
  min: number?                    # 数值类属性下界
  max: number?                    # 数值类属性上界
  extraction_hint: string?        # 提取提示词（如"资产负债率|debt ratio|负债率"），指导 LLM 从非结构化文本提取该属性
  index_fields: boolean = false   # 是否建立存储索引（参考 m_flow）
  display_only: boolean = false   # 仅展示不参与计算（参考 m_flow）
  source_field: string?           # 来源字段映射（参考 Cognee Annotated）
  source_pipeline: string?        # 来源管道（参考 Cognee DataPoint）
  source_task: string?            # 来源任务（参考 Cognee DataPoint）
  source_content_hash: string?    # 内容哈希（参考 Cognee DataPoint）
```

**增强字段说明**：

| 字段 | 来源 | 目的 |
|------|------|------|
| `extraction_hint` | 10-kb-process.md 2.3 | 指导 LLM 从非结构化文本中提取该属性值，如"资产负债率\|debt ratio\|负债率"提供多语言同义提示 |
| `index_fields` | m_flow | 提示存储层为该属性建立索引，优化查询性能。如 `unified_social_code` 需要索引以支持快速查找 |
| `display_only` | m_flow | 区分展示属性与计算属性。如 `company_short_name` 仅用于 UI 展示，不参与指标计算和规则推理 |
| `source_field` | Cognee Annotated | 标注属性值来自外部系统的哪个字段，支持数据溯源 |
| `source_pipeline` | Cognee DataPoint | 记录数据来源管道（如 `erp_sync`、`manual_input`），用于溯源和影响分析 |
| `source_task` | Cognee DataPoint | 记录数据来源任务（如 `daily_batch`、`realtime_webhook`），用于溯源 |
| `source_content_hash` | Cognee DataPoint | 记录数据内容的 SHA256 哈希，用于变更检测和矛盾检测 |

### relations: [RelationDeclaration]

```yaml
- name: string                    # 关系类型名，全局唯一
  from: string                    # 源实体类型（Entity.name）
  to: string                      # 目标实体类型
  description: string?
  attributes: [AttributeDef]?     # 可选关系属性
  cardinality: enum?              # one_to_one | one_to_many | many_to_many
  logical_type: enum?             # business | inference | traceability（参考 KAG IND#）
```

**`logical_type` 说明**（参考 KAG IND# 逻辑边）：

| 值 | 含义 | 示例 |
|------|------|------|
| `business` | 业务关系，携带业务属性 | guarantees（担保）、supplies（供应） |
| `inference` | 推理关系，由规则引擎产出 | triggers（触发）、depends_on（依赖） |
| `traceability` | 溯源关系，连接知识碎片 | extracted_from、defined_in、trace_to |

KAG 的 IND#（Independent Number）逻辑边设计区分了业务关系和推理关系，使得规则引擎可以按 `logical_type` 过滤关系类型，避免推理关系参与业务指标计算。

### 枚举类型（隐式声明）

枚举类型无需独立声明节，直接在 `AttributeDef.type=enum` 时通过 `enum_type` 引用，枚举值在 Instance 层定义。

### L1 设计决策

| # | 决策 | 选择 | 备选 | 理由 |
|---|------|------|------|------|
| 1 | 实体与关系分离 | `entities[]` + `relations[]` 独立列表 | v1 的 `concepts` 混合 | 关系有 from/to/cardinality 等独有字段，混合导致结构混乱 |
| 2 | `identity_fields` 实体级声明 | 在 EntityDeclaration 上声明 | 在 AttributeDef 上标记 | 实体唯一性通常是字段组合（如 company_name+address），需实体级声明 |
| 3 | `temporal` 声明式标注 | `temporal: true` 标注时序实体 | 所有实体强制时序 | 静态实体无需时序开销，显式标注更精确 |
| 4 | 枚举隐式声明 | `enum_type` 引用，值在 Instance 层 | 枚举独立声明节 | 枚举值随业务变化频繁，与实例数据同层管理更灵活 |
| 5 | `logical_type` 关系分类 | 区分 business/inference/traceability | 关系无逻辑类型标注 | KAG IND# 证明逻辑边分类对规则引擎过滤至关重要 |

---

## L2: categorizations

### 目的

L2 定义对 Fact Objects 的分类体系，用于组织和筛选分析视角。分类结果是实体与维度值的映射，独立于实体属性存储。

### 解决的问题

- v1 无独立分类层，分类逻辑散落在规则中
- 无法多维度叠加分类
- 分类结果混在 entity.attributes 中

### dimensions: [DimensionDeclaration]

```yaml
- name: string                    # 维度名，全局唯一
  description: string?
  type: enum                      # hierarchical | derived | tag_based
  values: [ValueDefinition]?      # 当 type=hierarchical 或 tag_based 时
  rule_logic: string?             # 当 type=derived 时，引用 RuleLogicDeclaration.name
  color: string?                  # 可选，hex 色值（如 "#FF4D4F"）
  applicable_to: [string]?        # 适用的实体类型名列表
```

**`applicable_to` 说明**：
- 声明该维度适用于哪些实体类型
- 未指定时默认适用于所有实体类型
- 用于分类引擎的维度选择和 UI 的维度过滤

### ValueDefinition

```yaml
- code: string | integer          # 分类编码
  name: string                    # 人类可读名称
  description: string?
  color: string?                  # 可选色值
  children: [ValueDefinition]?    # 层级子节点（仅 hierarchical 类型）
```

### 三种维度类型

| 类型 | 说明 | 值来源 | 示例 |
|------|------|--------|------|
| `hierarchical` | 层级分类 | `values` 静态声明（支持 children 嵌套） | 行业分类（门类→大类→中类→小类） |
| `derived` | 派生分类 | L4 `rule_logic` 计算产出 | 企业规模（大型/中型/小型/微型） |
| `tag_based` | 多值标签 | `values` 静态声明 + 手动/规则打标 | 业务标签（核心企业/白名单/重点供应商） |

### L2 → L4 复用语义

`type=derived` 的维度复用 L4 `rule_logics`：规则逻辑的 `steps` 输出即为维度值。维度声明本身仅引用已有的 `rule_logic` name，不重复定义计算逻辑。

```yaml
dimensions:
  - name: company_scale
    type: derived
    rule_logic: determine_scale
    values:
      - code: LARGE
        name: "大型企业"
      - code: MEDIUM
        name: "中型企业"
      - code: SMALL
        name: "小型企业"
      - code: MICRO
        name: "微型企业"
```

### tag_based 与 SemanticConcept 的关系

**[关键设计点]** L2 `tag_based` 承担了原 SemanticConcept 的功能（方案 A1，见 05-concepts.md）。本地知识库场景下 `tag_based` 足够；未来跨域泛化需求通过多 Space 知识融合实现。

### L2 设计决策

| # | 决策 | 选择 | 备选 | 理由 |
|---|------|------|------|------|
| 1 | derived 复用 L4 | `rule_logic` 引用 L4 规则逻辑 | L2 自带计算逻辑 | 避免重复定义，统一执行引擎 |
| 2 | SemanticConcept 废弃 | `tag_based` 承担标签功能 | 独立 Concept 层 | 本地场景够用，跨域通过 Space 融合 |
| 3 | hierarchical 支持 children | ValueDefinition 递归嵌套 | 扁平编码 + parent 引用 | 递归嵌套更直观，YAML 可读性更好 |
| 4 | `applicable_to` 显式声明 | 维度声明适用的实体类型 | 隐式推断 | 显式声明避免歧义，支持 UI 过滤 |

---

## L3: analytical_elements

### 目的

L3 定义用于分析和评估的业务计算单元。指标声明只定义"是什么"（名称、类型、依赖），计算逻辑由 L3 自身的 formula 或 L4 的 overrides 提供。

### 解决的问题

- v1 的 `metrics` 只有 atomic/derived/composite 三种类型，缺少 graph 和 variable
- 指标值混在 entity.attributes 中
- 无 overridable 机制，不同场景无法差异化计算
- 无指标溯源

### metrics: [MetricDeclaration]

```yaml
- name: string                    # 指标名，全局唯一
  description: string?
  type: enum                      # atomic | derived | graph | composite | variable
  value_type: enum                # integer | decimal | percentage | currency | score | flag

  source: string?                 # atomic 专用：属性路径（如 "registered_capital.value"）
  formula: string?                # atomic/derived 专用：简单表达式
  dependencies: [string]?         # derived/graph/composite 专用：依赖指标名列表
  components: [ComponentDef]?     # composite 专用：聚合分量定义
  overridable: boolean = false    # 是否允许 L4 规则实例覆盖计算逻辑
  overridable_by: string?         # 当 overridable=true 时，引用的 rule_definition.name

  color: string?                  # 可选，hex 色值
  unit: string?                   # 可选，单位（如 "%", "万"）
  thresholds: [ThresholdDef]?     # 可选，阈值定义（traffic-light 可视化）

  identity_fields: [string]?      # 指标唯一性字段（参考 Cognee）
  source_pipeline: string?        # 来源管道（参考 Cognee DataPoint）
  source_task: string?            # 来源任务（参考 Cognee DataPoint）
  source_content_hash: string?    # 内容哈希（参考 Cognee DataPoint）
```

### 五种指标类型

| 类型 | 说明 | 来源 | 典型场景 |
|------|------|------|---------|
| `atomic` | 从 L1 事实直接获取或简单转换 | `source` 属性路径或 `formula` 简单表达式 | 年营业收入、注册资本 |
| `derived` | 依赖 L1 属性或 L3 原子指标 | `dependencies` + `formula` | 资产负债率、流动比 |
| `graph` | 依赖图计算 | `dependencies` + L4 `graph_op` 算子 | 担保敞口评分、关联方数量 |
| `composite` | 多维度加权聚合 | `components` + `dependencies` | 综合信用评分 |
| `variable` | 外部可注入的变量 | 全局常量或配置值 | 行业平均营收、地区风险系数 |

### ComponentDef（composite 指标分量）

```yaml
- metric: string                  # 依赖的指标名（L3 指标名）
  weight: decimal?                # 加权系数
  aggregation: enum?              # sum | avg | max | min（当依赖为列表时）
```

### ThresholdDef（可视化阈值）

```yaml
- label: string                   # 阈值标签（如 "高"、"中"、"低"）
  operator: enum                  # gt | gte | lt | lte | eq | between
  value: any                      # 阈值
  color: string                   # 该区间色值
```

### overridable 与 L4 overrides 机制

当 `overridable=true` 时，在 `business_logic.rule_definitions` 中通过 `overrides` 字段声明覆盖：

```yaml
metrics:
  - name: credit_limit
    type: derived
    overridable: true
    dependencies:
      - credit_score
      - guarantee_exposure

rule_definitions:
  - name: credit_limit_override
    overrides: credit_limit
    inputs:
      - metric: credit_score
      - metric: guarantee_exposure
    outputs:
      - name: credit_limit
        type: Money
```

**覆盖优先级**：
1. 存在 `overrides: X` 的 rule_definition → 使用覆盖逻辑
2. 不存在覆盖规则 → 使用 L3 声明的标准计算逻辑
3. `overridable=false` → 禁止任何覆盖

### L3 设计决策

| # | 决策 | 选择 | 备选 | 理由 |
|---|------|------|------|------|
| 1 | 五种指标类型 | atomic/derived/graph/composite/variable | v1 三种（atomic/derived/composite） | graph 指标需要图数据库支持；variable 支持外部注入 |
| 2 | overridable 机制 | 声明式控制 + L4 覆盖 | 指标计算逻辑固定 | 不同业务场景需要差异化计算（如授信额度按行业） |
| 3 | 指标溯源字段 | `source_pipeline`/`source_task`/`source_content_hash` | 无溯源 | Cognee DataPoint 模式提供指标计算的可追溯性 |
| 4 | formula 位置 | L3 声明简单 formula，L4 提供复杂计算 | 所有 formula 在 L4 | 简单公式（如 `source * 1.0`）放在 L3 更直观，复杂逻辑在 L4 |
| 5 | thresholds 声明式 | 在指标声明中定义阈值 | 阈值在规则中定义 | 阈值主要用于可视化（traffic-light），与指标定义同层更自然 |

---

## L4: business_logic

### 目的

L4 定义业务规则，包括规则的作用域（rule_definitions）和执行步骤（rule_logics）。规则定义声明"对谁、输入什么、输出什么"，规则逻辑定义"怎么算"。

### 解决的问题

- v1 规则硬编码 `entity_types`，复用性差
- 扁平 when/then 结构，无步骤依赖
- 无算子类型，所有计算都是 formula
- 无规则适用性边界描述

### rule_definitions: [RuleDefinitionDeclaration]

```yaml
- name: string                    # 规则定义名，全局唯一
  description: string?
  type: enum                      # constraint | inference | alert | decision
  priority: integer?              # 执行优先级，数字越大越先执行，默认 100

  applies_to:                     # 规则适用对象
    fact_objects: [string]?       # 实体类型名列表；空数组 [] 表示 GLOBAL
    categories: dict?             # 分类过滤，格式: {dimension_name: [value_codes]}

  preconditions: [Precondition]?  # 前置条件
  inputs: [IOElement]?            # 输入要素
  outputs: [IOElement]?           # 输出要素

  overrides: string?              # 可选，覆盖 L3 overridable 指标

  applicability:                  # 规则适用性六维度（参考 m_flow ContextPack）
    when_text: string?            # 何时使用
    why_text: string?             # 为什么使用
    boundary_text: string?        # 边界条件
    outcome_text: string?         # 预期产出
    prereq_text: string?          # 前置条件描述
    exception_text: string?       # 异常处理描述
```

**`applicability` 六维度说明**（参考 m_flow ContextPack）：

m_flow 的 ContextPack 六维度模型是规则适用性边界的最佳实践。它让规则不仅是"可执行"的，还是"可解释"的——Agent 和人类都能理解规则的适用场景。

| 维度 | 含义 | 示例 |
|------|------|------|
| `when_text` | 何时使用此规则 | "评估交易对手信用风险时" |
| `why_text` | 为什么需要此规则 | "监管要求对所有交易对手定期评级" |
| `boundary_text` | 规则的适用边界 | "不适用于同业拆借对手" |
| `outcome_text` | 规则的预期产出 | "产出风险等级 A/B/C/D" |
| `prereq_text` | 前置条件 | "需要信用评分和负债率数据" |
| `exception_text` | 异常处理 | "新客户无历史数据时使用默认评级 C" |

### Precondition

```yaml
- expression: string              # 布尔表达式
  fail:                           # 不满足时的动作
    reject: boolean?              # 是否拒绝
    reason: string?               # 拒绝原因
    action: string?               # 其他动作
```

### IOElement（输入/输出要素）

```yaml
- metric: string?                 # 引用 L3 指标名
  attribute: string?              # 引用 L1 属性路径
  rule_output: string?            # 引用其他规则的输出名
  name: string?                   # 要素名称
  type: enum                      # boolean | integer | decimal | Money | string | flag
```

**引用优先级**：`metric` > `attribute` > `rule_output`。当 `metric` 和 `attribute` 同时指定时，`metric` 优先。

### rule_logics: [RuleLogicDeclaration]

```yaml
- name: string                    # 规则逻辑名，全局唯一
  description: string?
  type: enum                      # decision_table | scorecard | switch | binning | graph_op | custom
  steps: [Step]                   # 步骤序列，支持 DAG 依赖
```

### Step（步骤定义）

```yaml
- id: string                      # 步骤 ID，唯一
  name: string                    # 步骤名称
  description: string?
  priority: integer?              # 执行优先级，默认 100
  depends_on: [string]?           # 依赖的前置步骤 ID 列表（形成 DAG）

  condition:                      # 触发条件
    expression: string?           # 布尔表达式
    and: [string]?                # 复合 AND 条件
    or: [string]?                 # 复合 OR 条件
    not: string?                  # 取反条件

  action:                         # 触发动作
    type: enum                    # set_flag | compute | reject | emit_alert | assign_category
    flag: string?                 # type=set_flag 时：flag 名称
    value: any?                   # type=set_flag 时：flag 值
    output: string?               # type=compute 时：输出变量名
    operator: enum?               # type=compute 时：算子类型
    query: object?                # operator=GRAPH 时：图遍历查询定义
    aggregation: [AggDef]?        # operator=GRAPH 时：聚合定义
    bins: [BinDef]?               # operator=BINNING 时：分箱定义
    branches: [BranchDef]?        # operator=SWITCH 时：分支定义
    variables: [VariableDef]?     # operator=SCORECARD 时：变量评分卡
    formula: string?              # 通用计算公式
    category: string?             # type=assign_category 时：分类维度值
    reason: string?               # type=reject/emit_alert 时：原因
    severity: enum?               # type=emit_alert 时：INFO | WARNING | CRITICAL

  else:                           # 条件不满足时的备选动作（同 action 结构）
```

**条件表达式可用变量**：
- L1 属性：`attribute_name`（如 `status`, `registered_capital.value`）
- L3 指标：`metric_name`（如 `credit_score`, `guarantee_exposure`）
- 规则输出：`step_id.output`（如 `R001.eligible`）
- L2 维度：`dimension_name`（如 `company_scale`, `risk_level`）

### 算子类型

| 算子 | 说明 | 使用场景 | 对应子结构 |
|------|------|----------|-----------|
| `GRAPH` | 图遍历算子 | 遍历关系网络计算担保敞口 | `query` + `aggregation` |
| `BINNING` | 分箱算子 | 将连续值分段映射 | `bins` |
| `SWITCH` | 分支算子 | 根据值匹配不同计算分支 | `branches` |
| `SCORECARD` | 评分卡算子 | 加权打分模型 | `variables` |
| `WEIGHTED_SUM` | 加权求和算子 | 多因素加权求和 | `variables` + `formula` |
| `FORMULA` | 通用公式 | 任意表达式计算 | `formula` |

### GraphOp（operator=GRAPH）

```yaml
query:
  type: enum                      # traversal | neighbors | path | cycle_detection
  relation: string?               # 关系类型名
  from: string?                   # 起点实体 ID
  depth: integer?                 # 遍历深度
  direction: enum?                # outgoing | incoming | undirected
aggregation:
  - type: enum                    # sum | avg | max | min | count
    field: string                 # 聚合字段
    output: string                # 输出变量名
post_process:
  formula: string                 # 后处理公式
```

### BinDef（operator=BINNING）

```yaml
- range: [any, any]              # 左闭右闭区间
  result: any                     # 该区间对应值
```

### BranchDef（operator=SWITCH）

```yaml
- condition: string               # 分支条件
  formula: string?                # 该分支的计算公式
```

### VariableDef（operator=SCORECARD / WEIGHTED_SUM）

```yaml
- name: string                    # 变量名
  points:                         # 评分点列表
    - condition: string           # 条件表达式
      score: decimal              # 得分
  baseline: decimal?              # 基准分
post_formula: string?             # 后处理公式
```

### L4 设计决策

| # | 决策 | 选择 | 备选 | 理由 |
|---|------|------|------|------|
| 1 | 规则定义与规则逻辑分离 | `rule_definitions` + `rule_logics` | 规则定义与逻辑一体 | 一个定义可关联多个逻辑（不同行业/场景），提升复用性 |
| 2 | `applies_to` 结构化 | `fact_objects` + `categories` 过滤 | v1 硬编码 `entity_types` | 结构化定义支持多维度过滤（实体类型 + 分类维度） |
| 3 | `applicability` 六维度 | when/why/boundary/outcome/prereq/exception | 无适用性描述 | m_flow ContextPack 是规则可解释性的最佳实践 |
| 4 | steps DAG 依赖 | `depends_on` 形成执行 DAG | 扁平 when/then | DAG 支持步骤间依赖、并行执行、拓扑排序 |
| 5 | 6 种算子类型 | GRAPH/BINNING/SWITCH/SCORECARD/WEIGHTED_SUM/FORMULA | 仅 formula | 不同算子有不同的参数结构和执行语义，显式分类更清晰 |
| 6 | overrides 机制 | L4 可覆盖 L3 overridable 指标 | 指标计算不可覆盖 | 不同场景需要差异化计算逻辑 |
| 7 | action.type 分类 | set_flag/compute/reject/emit_alert/assign_category | 仅 then/else | 显式分类让执行引擎可以针对不同动作类型优化处理 |

---

## 层间交互图

```
                    ┌─────────────────────────────────────────────────┐
                    │              semantic_space                      │
                    │   (id / name / type / status / version)         │
                    └─────────────────────┬───────────────────────────┘
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            │                             │                             │
            ▼                             ▼                             ▼
   ┌────────────────┐          ┌──────────────────┐          ┌──────────────────┐
   │  L1 fact_objects│          │ L2 categorizations│          │ L3 analytical    │
   │                │          │                  │          │    elements      │
   │  entities[]    │          │  dimensions[]    │          │  metrics[]       │
   │  relations[]   │          │                  │          │                  │
   └───────┬────────┘          └────────┬─────────┘          └────────┬─────────┘
           │                            │                             │
           │ 属性引用                    │ derived 引用                 │ dependencies
           │ (attribute)                │ (rule_logic)                │ (metric)
           │                            │                             │
           ▼                            ▼                             ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                        L4 business_logic                                 │
   │                                                                          │
   │  rule_definitions[]          rule_logics[]                               │
   │  ├─ applies_to.fact_objects  ├─ steps[].condition                        │
   │  ├─ applies_to.categories    │   ├─ expression (引用 L1/L3/L2)            │
   │  ├─ inputs (metric/attr)     │   └─ and/or/not                           │
   │  ├─ outputs                  ├─ steps[].action                           │
   │  ├─ overrides (→ L3)        │   ├─ compute (operator: GRAPH/BINNING/...) │
   │  └─ applicability            │   ├─ set_flag / reject / emit_alert       │
   │                              │   └─ assign_category (→ L2 derived)       │
   │                              └─ steps[].else                             │
   └──────────────────────────────────────────────────────────────────────────┘
```

### 数据流说明

| 流向 | 机制 | 示例 |
|------|------|------|
| L1 → L3 | `source` 属性路径 | `registered_capital.value` → atomic metric `annual_revenue` |
| L1 → L3 | `dependencies` + 图数据库 | `Guarantee` 关系 → graph metric `guarantee_exposure` |
| L1 → L4 | `inputs.attribute` | `registered_capital.value` → rule input |
| L2 → L4 | `applies_to.categories` | `{industry_category: ["C"]}` → 规则仅对制造业生效 |
| L2 → L4 | `rule_logic` 引用 | derived 维度 `company_scale` → 复用 `determine_scale` 逻辑 |
| L3 → L3 | `dependencies` | `total_assets` + `total_liabilities` → `asset_liability_ratio` |
| L3 → L3 | `components` | `financial_health` + `business_stability` → `credit_score` |
| L3 → L4 | `inputs.metric` | `credit_score` → rule input |
| L3 → L4 | `overridable` + `overrides` | `credit_limit` overridable → `credit_limit_override` 覆盖 |
| L4 → L2 | `assign_category` action | 规则步骤输出 → derived 维度值 |
| L4 → L4 | `depends_on` DAG | `check_eligible` → `assess_risk`（依赖前者输出） |

---

## 全局数据类型

### Money

```yaml
value: decimal                    # 金额
currency: string                  # ISO 4217 货币代码（CNY, USD, EUR）
```

### Percentage

```yaml
value: decimal                    # 0-100（约定使用百分制）
```

---

## v1 → v2 迁移映射

| v1 写法 | v2 写法 | 说明 |
|---------|---------|------|
| `concepts` (混合) | `fact_objects.entities[]` + `fact_objects.relations[]` | 实体与关系分离 |
| `properties` | `attributes` | 实体属性定义 |
| `source` / `target` | `from` / `to` | 关系端点 |
| `element_type` | `type` | 指标类型 |
| `input_elements` / `output_elements` | `inputs` / `outputs` | 规则 I/O |
| `ruleset` | `rule_logic` (type=derived) | L2 derived 维度引用 |
| Flat `when/then_action` | `steps[].condition/action` | L4 规则逻辑 |
| `rule_group` | `rule_definitions[].name` + `rule_logics[].name` | 规则分组 |
| `categorization` | `categorizations`（复数容器） | L2 容器 |
| `fact_object_declaration` | `fact_objects.entities[]` | L1 实体声明 |
| `category: entity` | 顶层 `entities[]` | 实体类型标记 |
| `category: relation` | 顶层 `relations[]` | 关系类型标记 |
| `ruleset[].scope.entity_types` | `applies_to.fact_objects` | 规则适用对象 |
| `ruleset[].scope.dimensions` | `applies_to.categories` | 规则分类过滤 |
| `then.action` (字符串) | `action.type` + 具体字段 | 动作结构化 |
| `metadata.id` | `semantic_space.id` | Schema 标识 |
| `types` | 全局数据类型 (Money/Percentage) + `enum_type` | 类型系统 |
| `enums` | `enum_type` 引用 + Instance 层值 | 枚举定义 |

---

## 参考文档

| 主题 | 文档 |
|------|------|
| 冻结的 canonical grammar | [docs-baseline/05-schema-v2/09-canonical-schema-spec.md](../../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md) |
| 术语与概念 | [01-overview/05-concepts.md](../../01-overview/05-concepts.md) |
| Schema 设计导航 | [02-design/schema/README.md](./README.md) |
| baseline L1 详情 | [docs-baseline/05-schema-v2/01-fact-objects.md](../../../docs-baseline/05-schema-v2/01-fact-objects.md) |
| baseline L2 详情 | [docs-baseline/05-schema-v2/02-categorization.md](../../../docs-baseline/05-schema-v2/02-categorization.md) |
| baseline L3 详情 | [docs-baseline/05-schema-v2/03-analytical-elements.md](../../../docs-baseline/05-schema-v2/03-analytical-elements.md) |
| baseline L4 详情 | [docs-baseline/05-schema-v2/04-business-logic.md](../../../docs-baseline/05-schema-v2/04-business-logic.md) |
| 技术实现框架决策 | [discuss/2026-04-19-tech-impl-framework-decisions.md](../../../discuss/2026-04-19-tech-impl-framework-decisions.md) |

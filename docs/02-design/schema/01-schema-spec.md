# Schema v2 规范

> **status**: draft
> **phase**: phase1
> **source_of_truth**: [docs-baseline/05-schema-v2/09-canonical-schema-spec.md](../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md)
> **verified_against**: [01-overview/05-concepts.md](../../01-overview/05-concepts.md)
> **last_verified**: 2026-04-19

本文档是 Schema v2 的核心规范入口，定义 OntologyEngine 知识表示的完整 YAML grammar。与 05-concepts.md 中的术语和愿景保持一致，是四层架构（L1-L4）的正式语法绑定。

---

## 术语对照表

| 旧术语（MVP） | 新术语（Schema v2） | 说明 |
|--------------|-------------------|------|
| `metadata` | `semantic_space` | 语义空间元数据容器 |
| `types` | `attributes` (inline) | 复合类型内联到属性定义 |
| `enums` | 隐式声明 | 枚举通过 `enum_type` 引用，无需独立节 |
| `concepts` (category: entity) | `fact_objects.entities` | L1 实体声明 |
| `concepts` (category: relation) | `fact_objects.relations` | L1 关系声明 |
| `properties` | `attributes` | 实体/关系的属性定义 |
| `source` / `target` | `from` / `to` | 关系端点 |
| `metrics` | `analytical_elements.metrics` | L3 分析要素 |
| `rules` / `ruleset` | `business_logic` | L4 业务逻辑层 |
| `rule_group` | `rule_definitions[].name` + `rule_logics[].name` | 规则分组 |

---

## Canonical 根级结构

```yaml
schema_version: "2.0"

semantic_space:           # Schema 元数据与版本信息
  id: string             # 唯一标识，格式: space.{name}
  name: string           # 人类可读名称
  type: enum             # management | consumption
  status: enum           # DRAFT | ACTIVE | ARCHIVED | PUBLISHED
  version: string        # 语义版本（SemVer），格式: X.Y.Z
  description: string?   # 可选描述
  created_at: string?    # ISO 8601 时间戳
  updated_at: string?    # ISO 8601 时间戳

fact_objects:            # L1: 事实对象声明
  entities: [EntityDeclaration]
  relations: [RelationDeclaration]

categorizations:         # L2: 分类声明
  dimensions: [DimensionDeclaration]

analytical_elements:     # L3: 分析要素声明
  metrics: [MetricDeclaration]

business_logic:          # L4: 业务逻辑声明
  rule_definitions: [RuleDefinitionDeclaration]
  rule_logics: [RuleLogicDeclaration]
```

---

## L1: fact_objects

### entities: [EntityDeclaration]

```yaml
entities:
  - name: string                    # 实体类型名称，全局唯一
    description: string?
    temporal: boolean = false       # 是否为时序实体
    attributes: [AttributeDef]      # 属性定义列表
    key_attributes: [string]?      # 关键属性名列表，用于快速识别
```

### AttributeDef

```yaml
attributes:
  - name: string                    # 属性名
    type: enum                      # string | integer | decimal | boolean | date | datetime | enum | Money | JSON
    required: boolean = false       # 是否必填
    unique: boolean = false        # 是否唯一
    description: string?
    # 以下为可选字段，按 type 启用
    enum_type: string?              # 当 type=enum 时，引用枚举类型名
    currency: string?               # 当 type=Money 时，货币代码（如 CNY）
    default: any?                   # 默认值
    pattern: string?                # 当 type=string 时，Regex 校验
    min: number?                    # 数值类属性下界
    max: number?                    # 数值类属性上界
```

### relations: [RelationDeclaration]

```yaml
relations:
  - name: string                    # 关系类型名，全局唯一
    from: string                    # 源实体类型（Entity.name）
    to: string                      # 目标实体类型
    description: string?
    attributes: [AttributeDef]?      # 可选关系属性
    cardinality: enum?              # one_to_one | one_to_many | many_to_many
    logical_type: string?           # 可选，IND# 逻辑边类型（参考 KAG）
```

### 枚举类型（隐式声明）

枚举类型无需独立声明节，直接在 `AttributeDef.type=enum` 时通过 `enum_type` 引用：

```yaml
# 在 entities 中引用
- name: status
  type: enum
  enum_type: CompanyStatus
```

---

## L2: categorizations

### dimensions: [DimensionDeclaration]

```yaml
dimensions:
  - name: string                    # 维度名，全局唯一
    description: string?
    type: enum                      # hierarchical | derived | tag_based
    values: [ValueDefinition]?      # 当 type=hierarchical 或 tag_based 时
    rule_logic: string?             # 当 type=derived 时，引用 RuleLogicDeclaration.name
    color: string?                  # 可选，hex 色值，用于可视化（如 "#FF4D4F"）
```

### ValueDefinition

```yaml
values:
  - code: string | integer          # 分类编码
    name: string                    # 人类可读名称
    description: string?
    color: string?                  # 可选色值
```

### L2 → L4 关系语义

`type=derived` 的维度**复用 L4 rule_logics**：规则逻辑（`steps` 中的 `condition/result`）输出即为维度值。维度声明本身仅引用已有的 rule_logic name，不重复定义计算逻辑。

```yaml
# 示例：company_scale 维度引用 determine_scale 规则逻辑
dimensions:
  - name: company_scale
    type: derived
    rule_logic: determine_scale    # 引用 business_logic.rule_logics[].name
    values: [LARGE, MEDIUM, SMALL, MICRO]
```

---

## L3: analytical_elements

### metrics: [MetricDeclaration]

```yaml
metrics:
  - name: string                    # 指标名，全局唯一
    description: string?
    type: enum                      # atomic | derived | graph | composite | variable
    value_type: enum                # integer | decimal | percentage | currency | score | flag

    # atomic: 从 L1 事实直接获取或简单转换
    # derived: 依赖 L1 属性或 L3 原子指标
    # graph: 依赖图计算（通过图数据库）
    # composite: 多维度加权聚合
    # variable: 外部可注入的变量

    source: string?                 # atomic 专用：属性路径（如 "registered_capital.value"）
    formula: string?                # atomic 专用：简单表达式（当 source 不够时）
    dependencies: [string]?         # derived/graph/composite 专用：依赖指标名列表
    components: [ComponentDef]?     # composite 专用：聚合分量定义
    overridable: boolean = false    # 是否允许 L4 规则实例覆盖计算逻辑
    overridable_by: string?         # 当 overridable=true 时，引用的 rule_definition.name

    color: string?                  # 可选，hex 色值，用于可视化
    unit: string?                   # 可选，单位（如 "%", "万"）
    thresholds: [ThresholdDef]?     # 可选，阈值定义（用于 traffic-light 可视化）
```

### ComponentDef（composite 指标分量）

```yaml
components:
  - metric: string                  # 依赖的指标名（L3 指标名）
    weight: decimal?                # 加权系数
    aggregation: enum?              # sum | avg | max | min（当依赖为列表时）
```

### ThresholdDef（可视化阈值）

```yaml
thresholds:
  - label: string                   # 阈值标签（如 "高"、"中"、"低"）
    operator: enum                  # gt | gte | lt | lte | eq | between
    value: any                      # 阈值
    color: string                   # 该区间色值
```

### L3 → L4 override 语义

当 `overridable=true` 时，在 `business_logic.rule_definitions` 中通过 `overrides` 字段声明覆盖：

```yaml
# 示例：credit_limit 指标声明为 overridable
metrics:
  - name: credit_limit
    type: derived
    overridable: true

# 在 L4 规则声明中覆盖
rule_definitions:
  - name: credit_limit_override
    overrides: credit_limit
    inputs: [{metric: credit_score}, {metric: guarantee_exposure}]
    outputs: [{name: credit_limit, type: Money}]
```

---

## L4: business_logic

### rule_definitions: [RuleDefinitionDeclaration]

```yaml
rule_definitions:
  - name: string                    # 规则定义名，全局唯一
    description: string?
    type: enum                      # constraint | inference | alert | decision
    priority: integer?              # 执行优先级，数字越大越先执行，默认 100

    applies_to:                     # 规则适用对象
      fact_objects: [string]?       # 实体类型名列表；空数组 [] 表示 GLOBAL（所有实体）
      categories: dict?              # 分类过滤，格式: {dimension_name: [value_codes]}

    preconditions: [Precondition]? # 前置条件，不满足则跳过整个规则组
    inputs: [IOElement]?            # 输入要素
    outputs: [IOElement]?           # 输出要素

    overrides: string?              # 可选，覆盖 L3 overridable 指标（引用 metric.name）
```

### Precondition

```yaml
preconditions:
  - expression: string              # 布尔表达式
    fail:                           # 不满足时的动作
      reject: boolean?               # 是否拒绝
      reason: string?                # 拒绝原因
      action: string?                # 其他动作
```

### IOElement（输入/输出要素）

```yaml
inputs:                            # 或 outputs:
  - metric: string?                 # 引用 L3 指标名
    attribute: string?               # 引用 L1 属性路径
    rule_output: string?             # 引用其他规则的输出名
    name: string?                   # 要素名称
    type: enum                       # boolean | integer | decimal | Money | string | flag
```

> **设计原则**：优先使用 `metric` 引用 L3 指标；`attribute` 直接引用 L1 属性；两者都指定时，`metric` 优先。

### rule_logics: [RuleLogicDeclaration]

```yaml
rule_logics:
  - name: string                    # 规则逻辑名，全局唯一
    description: string?
    type: enum                      # decision_table | scorecard | switch | binning | graph_op | custom
    steps: [Step]                   # 步骤序列，支持 DAG 依赖
```

### Step（步骤定义）

```yaml
steps:
  - id: string                      # 步骤 ID，唯一
    name: string                    # 步骤名称
    description: string?
    priority: integer?              # 执行优先级，默认 100
    depends_on: [string]?           # 依赖的前置步骤 ID 列表（形成 DAG）

    condition:                      # 触发条件（支持复杂表达式）
      expression: string?            # 布尔表达式（当 type!=graph_op 时）
      and: [string]?                 # 复合 AND 条件
      or: [string]?                 # 复合 OR 条件
      not: string?                  # 取反条件
      # 条件表达式中可用变量：
      #   - L1 属性：attribute_name（如 status, registered_capital.value）
      #   - L3 指标：metric_name（如 credit_score, guarantee_exposure）
      #   - 规则输出：step_id.output（如 R001.eligible）
      #   - L2 维度：dimension_name（如 company_scale, risk_level）

    action:                         # 触发动作
      type: enum                    # set_flag | compute | reject | emit_alert | assign_category
      flag: string?                 # type=set_flag 时：flag 名称
      value: any?                   # type=set_flag 时：flag 值
      output: string?               # type=compute 时：输出变量名
      operator: enum?                # type=compute 时：算子类型
      # 算子类型（operator）：
      #   - GRAPH: 图遍历算子
      #   - BINNING: 分箱算子
      #   - SWITCH: 分支算子
      #   - SCORECARD: 评分卡算子
      #   - WEIGHTED_SUM: 加权求和算子
      #   - FORMULA: 通用公式算子，执行 ExpressionEngine 表达式，支持 L0/L1 两级执行模型
      query: object?                # operator=GRAPH 时：图遍历查询定义
      aggregation: [AggDef]?        # operator=GRAPH 时：聚合定义
      bins: [BinDef]?               # operator=BINNING 时：分箱定义
      branches: [BranchDef]?        # operator=SWITCH 时：分支定义
      variables: [VariableDef]?     # operator=SCORECARD 时：变量评分卡
      formula: string?               # 通用计算公式
      category: string?              # type=assign_category 时：分类维度值
      reason: string?               # type=reject/emit_alert 时：原因
      severity: enum?                # type=emit_alert 时：INFO | WARNING | CRITICAL

    else:                           # 条件不满足时的备选动作（同 action 结构）
```

### GraphOp（operator=GRAPH 时）

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
post_process:                     # 后处理公式
  formula: string
```

### BinDef（operator=BINNING 时）

```yaml
bins:
  - range: [any, any]              # 左闭右闭区间
    result: any                     # 该区间对应值
```

### BranchDef（operator=SWITCH 时）

```yaml
branches:
  - condition: string               # 分支条件（精确匹配或表达式）
    formula: string?                # 该分支的计算公式
```

### VariableDef（operator=SCORECARD 时）

```yaml
variables:
  - name: string                    # 变量名
    points:                         # 评分点列表
      - condition: string           # 条件表达式
        score: decimal              # 得分
    baseline: decimal?              # 基准分
    post_formula: string?             # 后处理公式
```

---

## 全局数据类型约定

### Money

```yaml
value: decimal
currency: string   # ISO 4217 货币代码（如 CNY, USD, EUR）
```

### Percentage

```yaml
value: decimal   # 0-100 或 0-1，约定 0-100
```

---

## 层间数据流

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

## 完整示例

参见 [docs-baseline/05-schema-v2/05-complete-example.md](../../docs-baseline/05-schema-v2/05-complete-example.md)

---

## 与历史写法的迁移对照

| 历史 / 示例写法 | Canonical 写法 | 说明 |
|----------------|---------------|------|
| `metadata` | `semantic_space` | Schema 元数据容器 |
| `properties` | `attributes` | 实体属性定义 |
| `source` / `target` | `from` / `to` | 关系端点 |
| `element_type` | `type` | 指标类型 |
| `input_elements` / `output_elements` | `inputs` / `outputs` | 规则 I/O |
| `ruleset` | `rule_logic` (type=derived) | L2 derived 维度引用 |
| Flat `when/then_action` | `steps[].condition/action` | L4 规则逻辑 |
| `rule_group` | `rule_definitions[].name` + `rule_logics[].name` | 规则分组 |
| `categorization` | `categorizations`（复数容器） | L2 容器 |
| `fact_object_declaration` | `fact_objects.entities[]` | L1 实体声明 |

---

## 使用规则

1. **唯一事实源**：Schema v2 所有 grammar 定义以 [09-canonical-schema-spec.md](../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md) 为准
2. **禁止重复定义**：本文档只解释设计意图，不重新定义字段名或结构
3. **完整示例**：[docs-baseline/05-schema-v2/05-complete-example.md](../../docs-baseline/05-schema-v2/05-complete-example.md) 是 grammar 的完整可执行示例
4. **变更新规则**：任何 grammar 变更必须先更新 canonical spec，再同步完整示例，最后更新 STATUS.md
5. **代码核验**：实现 Schema Loader 时，以 canonical spec 作为解析器 schema 的规范

---

## 相关文档

| 文档 | 位置 | 职责 |
|------|------|------|
| 核心概念与术语 | [01-overview/05-concepts.md](../../01-overview/05-concepts.md) | 术语定义、Layer-R/S 架构、愿景 |
| Canonical Grammar | [docs-baseline/05-schema-v2/09-canonical-schema-spec.md](../../docs-baseline/05-schema-v2/09-canonical-schema-spec.md) | Schema v2 根级 grammar 唯一事实源 |
| L1-L4 声明层 | [L1-L4-declarations.md](./L1-L4-declarations.md) | L1-L4 声明层 grammar 详解 |
| 实例层 | [instance-layer.md](./instance-layer.md) | EntityInstance、EdgeInstance 等实例 grammar |
| 互索引边 | [mutual-index-edges.md](./mutual-index-edges.md) | extracted_from/supported_by/defined_in/trace_to |
| 时序建模 | [temporal-modeling.md](./temporal-modeling.md) | valid_from/to、时序边、因果链接 |
| 参考对齐 | [reference-alignment.md](./reference-alignment.md) | KAG/m_flow/Cognee 等系统洞察与 grammar 映射 |

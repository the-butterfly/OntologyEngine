# 核心概念

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
Schema v2 四层架构:
┌─────────────────────────────────────────────────────────────┐
│ L4 Business Logic                                           │
│   Rule Definition → Rule Logic → Computation Graph         │
├─────────────────────────────────────────────────────────────┤
│ L3 Analytical Elements                                      │
│   Metric / Indicator / Scorecard                           │
├─────────────────────────────────────────────────────────────┤
│ L2 Categorizations                                          │
│   Category / View (替代旧 Dimension)                        │
├─────────────────────────────────────────────────────────────┤
│ L1 Fact Objects                                             │
│   Definition ──▶ Entity Instance + Edge Instance           │
└─────────────────────────────────────────────────────────────┘

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

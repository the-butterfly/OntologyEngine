# 核心概念

> **[待扩展]**: 本文仍混用 `Concept / Metric / Rule` 等旧术语，后续需与 Schema v2 的 `Fact Object / Analytical Element / Business Logic` 体系继续统一
> **[关键设计点]**: 当概念解释与目标态设计冲突时，请优先参考 `docs/05-schema-v2/README.md` 与 `docs/05-schema-v2/09-canonical-schema-spec.md`

## Schema 层

### Concept (概念)
```yaml
concept:
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

### Relation (关系)
两个 Concept 之间的连接，带属性。

### Attribute (属性)
| 类型 | 说明 |
|------|------|
| Basic | 基础属性，直接存储 |
| Derived | 派生属性，规则计算 |
| Aggregated | 聚合属性，关联计算 |

### Metric (指标)
```yaml
metric:
  id: "guarantee_ratio"
  metric_type: "derived"  # atomic | derived | composite
  calculation:
    type: "formula"
    expression: "total_guarantee_out / net_asset"
```

## 分析维度

### Dimension (维度)
分析维度定义不同视角，如 `credit_assessment`（融资授信）、`transaction_monitoring`（交易监控）。

同一实体在不同维度下有相同的核心属性，但派生出不同的分析结果。

**重要澄清：dimension_attributes 不是存储属性**

`schema.yaml` 中的 `dimension_attributes` 是一个**误称**。实际上：

- **Concept 的 attributes** = 实体的核心数据，**存储**在数据库中
- **dimension_attributes** = 该维度下的**派生规则/指标**，**按需计算**

```yaml
# 错误理解（不要这样做）
concepts:
  - name: "Supplier"
    dimension_attributes:
      credit_assessment:
        - name: "credit_limit"  # ❌ 这不是存储属性

# 正确理解
concepts:
  - name: "Supplier"
    attributes:  # ← 存储的属性
      - name: "registered_capital"
      - name: "status"

rules:  # ← 派生属性在规则中定义
  ruleset:
    - id: "R004_credit_limit"
      scope:
        dimensions: ["credit_assessment"]
      computation:
        formula: "registered_capital * 0.5"
```

## 计算层

### Rule (规则)
```yaml
rule:
  id: "R001_risk_grade"
  inputs:
    - name: "comprehensive_risk_score"
  compute:
    operator: "SWITCH"
    cases:
      - condition: "value >= 85"
        output: { "risk_grade": "A" }
  outputs:
    - name: "risk_grade"
```

### Operator (算子)
- Math: ADD, SUB, MUL, DIV, SUM, AVG
- Logic: IF, SWITCH, AND, OR
- Comparison: EQ, GT, LT
- Graph: TRAVERSE, CENTRALITY
- External: LLM_INFERENCE, API_CALL

### Computation Graph
规则依赖的 DAG，自动拓扑排序执行。

## 数据层

### Entity (实体)
Concept 的实例，JSON 表示。

### Edge (边)
Relation 的实例，有 from/to 节点。

### Instance
Schema + Data 的完整填充。

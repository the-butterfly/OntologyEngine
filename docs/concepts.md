# 核心概念

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

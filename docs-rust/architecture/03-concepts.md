# 核心概念

> **状态**: 设计中  
> **级别**: L0 - 架构层  
> **目标读者**: 架构师、开发者

## 概念总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            知识表示层 (Knowledge)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │   Concept    │ │  Relation    │ │  Attribute   │ │   Metric     │        │
│  │   (概念)     │ │   (关系)     │ │   (属性)     │ │   (指标)     │        │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            数据层 (Data)                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │    Entity    │ │     Edge     │ │    Value     │ │   Instance   │        │
│  │   (实体)     │ │   (边)       │ │   (值)       │ │   (实例)     │        │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            计算层 (Computation)                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │     Rule     │ │  Operator    │ │  Inference   │ │   Query      │        │
│  │   (规则)     │ │   (算子)     │ │   (推理)     │ │   (查询)     │        │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心概念详解

### 1. Schema 层概念

#### 1.1 Concept（概念/类型）

概念是对现实世界实体的抽象定义，类似于编程语言中的类。

```yaml
concept:
  id: "finance:Counterparty"
  name: "交易对手"
  description: "金融交易中的对手方机构"
  
  # 概念层级
  parent: "finance:FinancialEntity"  # 继承
  category: "entity"                  # entity | relation | event
  
  # 属性定义
  attributes:
    - name: "entity_id"
      type: "string"
      required: true
      unique: true
      
    - name: "legal_name"
      type: "string"
      required: true
      vector_config:
        enabled: true                 # 支持语义检索
        
    - name: "risk_grade"
      type: "enum"
      enum_type: "RiskGrade"
      
  # 关系定义
  relations:
    - name: "guarantees"
      target: "finance:Counterparty"
      cardinality: "0..*"
      inverse: "guaranteed_by"
      
    - name: "trades_with"
      target: "finance:Counterparty"
```

#### 1.2 Relation（关系）

关系定义概念之间的连接方式。

```yaml
relation:
  id: "finance:GuaranteeRelation"
  name: "担保关系"
  
  # 参与方
  participants:
    - role: "guarantor"               # 担保方
      concept: "finance:Counterparty"
      cardinality: "1"
      
    - role: "guaranteed"              # 被担保方
      concept: "finance:Counterparty"
      cardinality: "1"
      
  # 关系属性
  attributes:
    - name: "amount"
      type: "Money"
      
    - name: "start_date"
      type: "date"
    
    - name: "end_date"
      type: "date"
      
  # 语义角色（用于推理）
  semantic_roles:
    - "financial_obligation"
    - "credit_support"
```

#### 1.3 Attribute（属性）

属性是概念的特征描述。

| 属性类型 | 说明 | 示例 |
|----------|------|------|
| Basic | 基础属性，直接存储 | `name`, `age` |
| Derived | 派生属性，计算得出 | `account_risk_score` |
| Aggregated | 聚合属性，关联聚合 | `total_transaction_amount` |
| Virtual | 虚拟属性，查询时计算 | `current_balance` |

```yaml
attribute:
  name: "account_risk_score"
  type: "integer"
  
  # 属性类型
  attribute_type: "derived"
  
  # 计算配置
  calculation:
    type: "multi_strategy"
    strategies:
      - priority: 1
        type: "formula"
        expression: "if balance > 1000000: return 90"
      - priority: 2
        type: "graph"
        query: "MATCH (a:Account)..."
      - priority: 3
        type: "llm"
        prompt: "分析账户风险..."
        
  # 缓存配置
  cache:
    enabled: true
    ttl_seconds: 3600
```

#### 1.4 Metric（指标）

指标是可量化的计算目标。

```yaml
metric:
  id: "guarantee_ratio"
  name: "对外担保比例"
  
  # 指标类型
  metric_type: "derived"              # atomic | derived | composite
  
  # 数据类型
  value_type: "decimal"
  unit: "ratio"                       # 百分比、金额等
  
  # 计算配置
  calculation:
    type: "formula"
    expression: "total_guarantee_out / net_asset"
    
  # 阈值配置
  thresholds:
    warning: 0.5
    critical: 0.8
```

### 2. 数据层概念

#### 2.1 Entity（实体）

实体是概念的具体实例。

```json
{
  "_id": "entity://finance/Counterparty/CP_001",
  "_concept": "finance:Counterparty",
  "entity_id": "CP_001",
  "legal_name": "某证券有限责任公司",
  "risk_grade": "B",
  "_metadata": {
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-03-20T14:22:00Z",
    "version": 3
  }
}
```

#### 2.2 Edge（边）

边表示实体之间的关系实例。

```json
{
  "_id": "edge://finance/GuaranteeRelation/E_001",
  "_relation": "finance:GuaranteeRelation",
  "_from": "entity://finance/Counterparty/CP_001",
  "_to": "entity://finance/Counterparty/CP_002",
  "amount": {
    "value": 50000000,
    "currency": "CNY"
  },
  "start_date": "2024-01-01",
  "end_date": "2025-01-01"
}
```

#### 2.3 Instance（实例）

实例是 Schema 的具体数据填充。

### 3. 计算层概念

#### 3.1 Rule（规则）

规则定义业务逻辑和计算流程。

```yaml
rule:
  id: "R001_risk_grade_assignment"
  name: "风险等级评定"
  
  # 输入声明
  inputs:
    - name: "comprehensive_risk_score"
      type: "decimal"
      required: true
      
  # 计算逻辑
  compute:
    operator: "SWITCH"
    parameters:
      value: "${comprehensive_risk_score}"
      cases:
        - condition: "value >= 85"
          output: { "risk_grade": "A" }
        - condition: "value >= 70"
          output: { "risk_grade": "B" }
        - condition: "value >= 55"
          output: { "risk_grade": "C" }
      default:
        output: { "risk_grade": "D" }
        
  # 输出声明
  outputs:
    - name: "risk_grade"
      type: "enum"
```

#### 3.2 Operator（算子）

算子是可复用的计算单元。

| 类别 | 算子 | 说明 |
|------|------|------|
| Math | ADD, SUB, MUL, DIV, SUM, AVG, MAX, MIN | 数学运算 |
| Logic | IF, SWITCH, AND, OR, NOT | 逻辑判断 |
| Comparison | EQ, GT, GTE, LT, LTE, IN | 比较运算 |
| Scoring | SCORECARD, BINNING, WOE | 评分卡 |
| Graph | TRAVERSE, PATH, CENTRALITY | 图计算 |
| External | ML_MODEL, LLM_INFERENCE, API_CALL | 外部调用 |

#### 3.3 Computation Graph（计算图）

计算图表示规则和指标之间的依赖关系。

```
┌─────────────────────────────────────────────────────────────────┐
│                        计算图示例                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐                                               │
│   │  net_asset  │                                               │
│   └──────┬──────┘                                               │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│   │total_guaran-│     │   R001:     │     │guarantee_   │      │
│   │tee_out      │────▶│guarantee_   │────▶│ratio        │      │
│   └─────────────┘     │ratio        │     └──────┬──────┘      │
│                       └─────────────┘            │             │
│                                                  ▼             │
│                       ┌─────────────┐     ┌─────────────┐      │
│   ┌─────────────┐     │   R002:     │◀────│   R003:     │      │
│   │capital_ade- │────▶│capital_     │     │guarantee_   │      │
│   │quacy_ratio  │     │score        │     │score        │      │
│   └─────────────┘     └──────┬──────┘     └─────────────┘      │
│                              │                                  │
│                              ▼                                  │
│                       ┌─────────────┐                          │
│                       │   R006:     │                          │
│                       │comprehen-   │                          │
│                       │sive_score   │                          │
│                       └──────┬──────┘                          │
│                              │                                  │
│                              ▼                                  │
│                       ┌─────────────┐                          │
│                       │   R007:     │                          │
│                       │risk_grade   │                          │
│                       └─────────────┘                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4. 维度概念（Domain Dimensions）

同一实体在不同业务维度下有不同的派生属性。

```yaml
concept:
  id: "finance:Customer"
  name: "客户"
  
  # 基础属性（所有维度共有）
  attributes:
    - name: "customer_id"
      type: "string"
    - name: "name"
      type: "string"
      
  # 维度特定属性
  dimension_attributes:
    loan_approval:                    # 贷款审批维度
      - name: "debt_to_income_ratio"
        type: "Percentage"
        derived: true
        
      - name: "loan_approval_eligibility"
        type: "string"
        derived: true
        
    aml_monitoring:                   # AML监控维度
      - name: "transaction_velocity_1h"
        type: "integer"
        derived: true
        
      - name: "cross_border_ratio"
        type: "Percentage"
        derived: true
```

## 概念关系图

```
┌─────────────┐       defines        ┌─────────────┐
│   Schema    │──────────────────────▶│   Concept   │
└─────────────┘                       └──────┬──────┘
       │                                     │
       │ contains                            │ has
       ▼                                     ▼
┌─────────────┐                       ┌─────────────┐
│   Metric    │                       │  Attribute  │
└──────┬──────┘                       └──────┬──────┘
       │                                     │
       │ uses                                │ has type
       ▼                                     ▼
┌─────────────┐                       ┌─────────────┐
│   Rule      │                       │    Type     │
└──────┬──────┘                       └─────────────┘
       │
       │ calls
       ▼
┌─────────────┐
│  Operator   │
└─────────────┘
```

## 💬 待讨论问题

1. **概念继承**: 是否支持多重继承？如何平衡灵活性和复杂性？
2. **属性派生**: 派生属性的计算触发策略（实时/定时/事件）如何设计？
3. **维度属性**: 维度属性的作用域和可见性如何控制？
4. **算子扩展**: 用户自定义算子的安全性和性能如何保证？

## 术语表

参见 [术语表](../reference/glossary.md)

## 下一步

- [分层架构](./04-layers.md) - 系统分层设计
- [Schema 设计](../design/schema/) - 详细 Schema 设计

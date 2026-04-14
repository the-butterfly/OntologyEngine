# L3: 分析要素 (Analytical Elements)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-14
verified_against: docs/05-schema-v2/09-canonical-schema-spec.md
related_docs:
  - 00-overview.md
  - 00b-semantic-space-architecture.md
  - 01-fact-objects.md
  - 02-categorization.md
  - 04-business-logic.md
  - 09-canonical-schema-spec.md
related_adrs:
  - architecture/decisions/007-l3-l4-computation-boundary.md
---

> **Status**: v2.0 (aligned with Canonical Grammar)
> **Last Verified**: 2026-04-14
> **verified_against**: docs/05-schema-v2/09-canonical-schema-spec.md

## 核心概念

L3 分析要素包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Declaration)** | 指标定义 | 名称、类型、数据来源、计算依赖 |
| **实例 (Instance)** | 指标值 | entity_id + metric_id → computed value |

---

## 1. 声明：指标定义

### 1.1 结构

在 Schema v2 中，指标通过 `analytical_elements.metrics[]` 声明：

```yaml
analytical_elements:
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

### 1.2 指标类型

| 类型 | 说明 | 来源 |
|------|------|------|
| `atomic` | 基础指标 | 事实属性或外部 API |
| `derived` | 派生指标 | 基于其他指标计算 |
| `composite` | 复合指标 | 多指标加权聚合 |
| `graph` | 图指标 | 基于关系网络计算 |
| `variable` | 变量 | 全局常量或配置值 |

### 1.3 示例

```yaml
analytical_elements:
  metrics:
    # 原子指标 - 直接取事实属性
    - name: annual_revenue
      description: 年营业收入
      type: atomic
      value_type: currency
      source: annual_revenue.value
      unit: CNY

    # 原子指标 - 外部 API
    - name: external_credit_score
      description: 外部征信评分
      type: atomic
      value_type: score
      source: external_api.pbccrc.credit_score
      thresholds:
        - label: "高风险"
          operator: lt
          value: 600
          color: "#FF4D4F"
        - label: "中等"
          operator: between
          value: [600, 750]
          color: "#FAAD14"
        - label: "优良"
          operator: gte
          value: 750
          color: "#52C41A"

    # 派生指标 - 只声明依赖，formula 在 L4 定义
    - name: asset_liability_ratio
      description: 资产负债率
      type: derived
      value_type: percentage
      dependencies:
        - total_assets
        - total_liabilities
      overridable: true
      unit: "%"
      range: [0, 100]

    # 复合指标 - 声明组件，权重在 L4 计算
    - name: credit_score
      description: 综合信用评分
      type: composite
      value_type: score
      dependencies:
        - financial_health_score
        - business_stability_score
        - external_credit_score
      overridable: true
      range: [0, 100]

    # 图指标
    - name: guarantee_exposure_score
      description: 担保敞口评分
      type: graph
      value_type: score
      dependencies:
        - guarantee_exposure
      overridable: true
      range: [0, 100]
```

### 1.4 不可覆盖指标示例

```yaml
    - name: revenue_growth_rate
      description: 营收增长率
      type: derived
      overridable: false          # 不允许覆盖，使用标准公式
      formula: "(current - previous) / previous * 100"
      parameters:
        - name: period
          type: string
          default: "1Y"
```

---

## 2. overridable 与 L4 overrides 关系

### 2.1 机制说明

L3 指标可以声明 `overridable=true`（默认为 false），允许 L4 规则定义中通过 `overrides` 字段声明覆盖其计算逻辑。

```
L3 指标声明
    │
    ├── overridable: true
    │       │
    │       └── L4 rule_definition
    │               │
    │               └── overrides: <metric_name>
    │                       │
    │                       └── 提供自定义计算逻辑
    │
    └── overridable: false (默认)
            │
            └── 使用标准计算，不允许覆盖
```

### 2.2 完整示例：credit_limit 指标覆盖

```yaml
# L3: 定义 credit_limit 指标，声明为 overridable
analytical_elements:
  metrics:
    - name: credit_limit
      description: 授信额度
      type: derived
      value_type: currency
      dependencies:
        - credit_score
        - guarantee_exposure
      overridable: true              # ← 允许 L4 覆盖

# L4: 定义规则，覆盖 credit_limit 的计算逻辑
business_logic:
  rule_definitions:
    - name: credit_limit_override
      description: 自定义授信额度计算规则
      type: decision
      overrides: credit_limit        # ← 覆盖 L3 的 credit_limit 指标
      inputs:
        - metric: credit_score
          type: score
        - metric: guarantee_exposure
          type: currency
        - attribute: registered_capital.value
          type: decimal
      outputs:
        - name: credit_limit
          type: currency

  rule_logics:
    - name: credit_limit_custom_logic
      type: formula
      steps:
        - id: calculate
          action:
            type: compute
            output: credit_limit
            operator: WEIGHTED_SUM
            variables:
              - name: base_score_factor
                points:
                  - condition: "credit_score >= 800"
                    score: 0.5
                  - condition: "credit_score >= 600"
                    score: 0.3
                  - condition: "credit_score >= 400"
                    score: 0.2
                baseline: 0.1
              - name: exposure_factor
                points:
                  - condition: "guarantee_exposure == 0"
                    score: 1.0
                  - condition: "guarantee_exposure < 10000000"
                    score: 0.8
                  - condition: "guarantee_exposure < 50000000"
                    score: 0.5
                  - condition: "guarantee_exposure >= 50000000"
                    score: 0.2
                baseline: 0.0
            formula: "registered_capital.value * base_score_factor * exposure_factor"
```

### 2.3 覆盖规则优先级

1. 如果存在 `overrides: X` 的 rule_definition，选中该规则提供计算逻辑
2. 如果不存在覆盖规则，使用 L3 声明的标准计算逻辑
3. `overridable=false` 的指标禁止任何覆盖

---

## 3. 实例：指标值

### 3.1 结构

```yaml
metric_value_instance:
  entity_id: string             # 实体 ID
  metric_id: string             # 指标 ID (声明中的 name)
  value: any                   # 指标值
  timestamp: string            # 计算时间
  source: computed | cached | manual
  version: integer             # 版本号
  metadata:
    computation_time_ms: float
    cache_hit: boolean
```

### 3.2 存储策略

指标值可以选择**存储**或**实时计算**：

| 策略 | 适用场景 | 说明 |
|------|----------|------|
| **缓存** | 频繁访问的历史快照 | 存储在 Space 内，按 TTL 失效 |
| **实时计算** | 需要最新值 | 不存储，执行时计算 |

```yaml
# 声明中指定缓存策略
    - name: annual_revenue
      type: atomic
      value_type: currency
      cache:
        enabled: true
        ttl: 86400               # 24 小时
        invalidate_on:
          - fact_change          # 事实属性变更时失效
```

### 3.3 示例

```yaml
# 存储的指标值
metric_value_instances:
  - entity_id: SUP_001
    metric_id: credit_limit
    value:
      value: 5000000
      currency: CNY
    timestamp: "2026-04-14T10:00:00Z"
    source: computed
    version: 3

  - entity_id: SUP_001
    metric_id: asset_liability_ratio
    value: 65.2
    timestamp: "2026-04-14T10:00:00Z"
    source: cached            # 从缓存读取
    version: 1
```

---

## 4. 指标依赖图

声明中定义的依赖关系自动构建 DAG：

```
L1 事实属性
    │
    ▼
┌─────────────────────────────────────────┐
│         L3 指标声明 (dependencies)         │
└─────────────────────────────────────────┘
    │
    │ depends on
    ▼
┌─────────────────────────────────────────┐
│  annual_revenue ──────┐                 │
│  total_assets ────────┼──▶ asset_liability_ratio │
│  total_liabilities ───┘                 │
│                        │                │
│  current_assets ───────┼──▶ current_ratio       │
│  current_liabilities ──┘                │
│                        │                │
│  revenue_growth ───────┼──▶ revenue_growth_rate │
└─────────────────────────────────────────┘
    │
    │ components
    ▼
┌─────────────────────────────────────────┐
│  financial_health_score ──┐             │
│  business_stability ─────┼──▶ credit_score │
│  external_credit ────────┤             │
│  guarantee_exposure ──────┘             │
└─────────────────────────────────────────┘
    │
    ▼
L4 业务逻辑
```

---

## 5. 变量定义

变量是一种特殊的分析要素，用于存储全局常量或计算结果：

```yaml
    - name: industry_avg_revenue
      description: 行业平均营收
      type: variable
      value_type: currency
      scope: industry_category    # 按维度聚合
      aggregation: avg
      source_metric: annual_revenue

    - name: region_risk_coefficient
      description: 地区风险系数
      type: variable
      value_type: decimal
      scope: registered_address.province
      source:
        type: lookup_table
        table: region_risk_config
```

---

## 6. 运行时行为

### 6.1 按需计算

指标值在规则执行时按需计算：

```python
class MetricEngine:
    def compute(self, metric_name: str, entity_id: str) -> MetricValue:
        declaration = self.get_declaration(metric_name)

        # 1. 检查是否被 L4 覆盖
        if declaration.overridable:
            override_def = self.get_override_definition(metric_name)
            if override_def:
                return self.execute_override(override_def, entity_id)

        # 2. 检查缓存
        if cached := self.cache.get(entity_id, metric_name):
            return cached

        # 3. 按类型计算
        if declaration.type == "atomic":
            value = self.load_atomic(declaration, entity_id)
        elif declaration.type == "derived":
            deps = self.compute_dependencies(declaration.dependencies, entity_id)
            value = self.evaluate_formula(declaration.formula, deps)
        elif declaration.type == "composite":
            value = self.aggregate_components(declaration, entity_id)
        elif declaration.type == "graph":
            value = self.run_graph_algorithm(declaration.dependencies, entity_id)

        # 4. 缓存结果
        if declaration.cache.enabled:
            self.cache.set(entity_id, metric_name, value, declaration.cache.ttl)

        return value
```

### 6.2 缓存失效

| 触发条件 | 说明 |
|----------|------|
| `fact_change` | 实体的 L1 属性变更 |
| `relation_change` | 关系变更 |
| `rule_execution` | 规则执行后 |
| `manual` | 手动清除 |

---

## 7. API 设计

### 7.1 声明 CRUD

```
GET    /v1/management/{spaceId}/schema/L3/analytical-elements
POST   /v1/management/{spaceId}/schema/L3/analytical-elements
GET    /v1/management/{spaceId}/schema/L3/analytical-elements/{id}
PUT    /v1/management/{spaceId}/schema/L3/analytical-elements/{id}
DELETE /v1/management/{spaceId}/schema/L3/analytical-elements/{id}
```

### 7.2 实例管理

```
GET    /v1/management/{spaceId}/instances/metrics/{entityId}
POST   /v1/management/{spaceId}/instances/metrics/compute
DELETE /v1/management/{spaceId}/instances/metrics/{entityId}/{metricId}
```

### 7.3 缓存管理

```
POST /v1/management/{spaceId}/instances/metrics/invalidate
# Body: { entity_id: "SUP_001", metric_id: "credit_score" }
```

---

## 8. 与 v1 的区别

| v1 | v2 (Canonical) |
|-----|----------------|
| `element_type` | `type` |
| formula 占位符 | 真实可执行的 formula |
| 无类型区分 | 明确 atomic/derived/composite/graph/variable |
| 无缓存定义 | 支持缓存策略配置 |
| 无依赖声明 | 自动推导依赖 DAG |
| 指标值混在 attributes | 指标值独立存储 |
| 无 overridable 机制 | 支持 L4 overrides 覆盖 |

---

## 9. 完整结构参考

完整 Schema v2 语法结构参见 [09-canonical-schema-spec.md](./09-canonical-schema-spec.md) 的 **L3: analytical_elements** 节。

*文档结束*

# L3: 分析要素 (Analytical Elements)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-12
verified_against: docs-only
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

> **Status**: v2.0 (with Declaration/Instance separation)
> **Date**: 2026-04-12

## 核心概念

L3 分析要素包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Declaration)** | 指标定义 | 名称、类型、数据来源、计算依赖 |
| **实例 (Instance)** | 指标值 | entity_id + metric_id → computed value |

---

## 1. 声明：指标定义

### 1.1 结构

```yaml
analytical_element_declaration:
  id: string                    # 全局唯一标识
  name: string                  # 显示名称
  description: string | null    # 描述
  element_type: atomic | derived | composite | graph | variable

  # 数据来源
  source:
    type: fact_attribute | external_api | constant
    entity: string             # 实体类型
    attribute: string           # 属性路径
    provider: string           # 外部 API 时使用

  # 依赖声明
  dependencies: list[string]    # 依赖的其他指标 ID

  # 计算参数
  parameters:
    - name: string
      type: string
      default: any

  # 可覆盖性
  overridable: boolean         # 是否允许 L4 覆盖计算逻辑

  # 元数据
  unit: string | null          # 单位
  range: [min, max] | null     # 取值范围
  ttl: integer | null         # 缓存 TTL (秒)
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
# 原子指标 - 直接取事实属性
analytical_element_declaration:
  id: annual_revenue
  name: 年营业收入
  element_type: atomic
  source:
    type: fact_attribute
    entity: Company
    attribute: annual_revenue.value
  unit: CNY

---
# 原子指标 - 外部 API
analytical_element_declaration:
  id: external_credit_score
  name: 外部征信评分
  element_type: atomic
  source:
    type: external_api
    provider: pbccrc
    field: credit_score
  range: [300, 900]

---
# 派生指标 - 只声明依赖，formula 在 L4 定义
analytical_element_declaration:
  id: asset_liability_ratio
  name: 资产负债率
  element_type: derived
  dependencies:
    - total_assets
    - total_liabilities
  overridable: true
  unit: percentage
  range: [0, 100]

---
# 复合指标 - 声明组件，权重在 L4 计算
analytical_element_declaration:
  id: credit_score
  name: 综合信用评分
  element_type: composite
  dependencies:
    - financial_health_score
    - business_stability_score
    - external_credit_score
  overridable: true
  range: [0, 100]

---
# 图指标
analytical_element_declaration:
  id: guarantee_exposure_score
  name: 担保敞口评分
  element_type: graph
  algorithm:
    type: weighted_sum
    traversal:
      - relation: Guarantee
        depth: 2
        aggregation: sum
        field: guarantee_amount.value
  overridable: true
  range: [0, 100]
```

### 1.4 可覆盖机制

L3 指标可声明 `overridable`：

| 值 | 说明 |
|-----|------|
| `true` (默认) | L4 可提供覆盖的 formula |
| `false` | 不允许 L4 覆盖，使用标准计算 |

```yaml
# L3: 定义标准计算逻辑
analytical_element_declaration:
  id: revenue_growth_rate
  name: 营收增长率
  element_type: derived
  overridable: false          # 不允许覆盖
  formula: "(current - previous) / previous * 100"
  parameters:
    - name: period
      type: string
      default: "1Y"
```

---

## 2. 实例：指标值

### 2.1 结构

```yaml
metric_value_instance:
  entity_id: string             # 实体 ID
  metric_id: string             # 指标 ID (声明中的 id)
  value: any                   # 指标值
  timestamp: string            # 计算时间
  source: computed | cached | manual
  version: integer             # 版本号
  metadata:
    computation_time_ms: float
    cache_hit: boolean
```

### 2.2 存储策略

指标值可以选择**存储**或**实时计算**：

| 策略 | 适用场景 | 说明 |
|------|----------|------|
| **缓存** | 频繁访问的历史快照 | 存储在 Space 内，按 TTL 失效 |
| **实时计算** | 需要最新值 | 不存储，执行时计算 |

```yaml
# 声明中指定缓存策略
analytical_element_declaration:
  id: annual_revenue
  name: 年营业收入
  element_type: atomic
  cache:
    enabled: true
    ttl: 86400               # 24 小时
    invalidate_on:
      - fact_change          # 事实属性变更时失效
```

### 2.3 示例

```yaml
# 存储的指标值
metric_value_instances:
  - entity_id: SUP_001
    metric_id: credit_score
    value: 78.5
    timestamp: "2026-04-12T10:00:00Z"
    source: computed
    version: 3

  - entity_id: SUP_001
    metric_id: asset_liability_ratio
    value: 65.2
    timestamp: "2026-04-12T10:00:00Z"
    source: cached            # 从缓存读取
    version: 1
```

---

## 3. 指标依赖图

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

## 4. 变量定义

变量是一种特殊的分析要素，用于存储全局常量或计算结果：

```yaml
variable_declaration:
  id: industry_avg_revenue
  name: 行业平均营收
  element_type: variable
  scope: industry_category    # 按维度聚合
  aggregation: avg
  source_metric: annual_revenue

  - id: region_risk_coefficient
    name: 地区风险系数
    element_type: variable
    scope: registered_address.province
    source:
      type: lookup_table
      table: region_risk_config
```

---

## 5. 运行时行为

### 5.1 按需计算

指标值在规则执行时按需计算：

```python
class MetricEngine:
    def compute(self, metric_id: str, entity_id: str) -> MetricValue:
        declaration = self.get_declaration(metric_id)

        # 1. 检查缓存
        if cached := self.cache.get(entity_id, metric_id):
            return cached

        # 2. 按类型计算
        if declaration.element_type == "atomic":
            value = self.load_atomic(declaration, entity_id)
        elif declaration.element_type == "derived":
            # 先计算依赖
            deps = self.compute_dependencies(declaration.dependencies, entity_id)
            # 再计算本身
            value = self.evaluate_formula(declaration.formula, deps)
        elif declaration.element_type == "composite":
            value = self.aggregate_components(declaration, entity_id)
        elif declaration.element_type == "graph":
            value = self.run_graph_algorithm(declaration.algorithm, entity_id)

        # 3. 缓存结果
        if declaration.cache.enabled:
            self.cache.set(entity_id, metric_id, value, declaration.cache.ttl)

        return value
```

### 5.2 缓存失效

| 触发条件 | 说明 |
|----------|------|
| `fact_change` | 实体的 L1 属性变更 |
| `relation_change` | 关系变更 |
| `rule_execution` | 规则执行后 |
| `manual` | 手动清除 |

---

## 6. API 设计

### 6.1 声明 CRUD

```
GET    /v1/management/{spaceId}/schema/L3/analytical-elements
POST   /v1/management/{spaceId}/schema/L3/analytical-elements
GET    /v1/management/{spaceId}/schema/L3/analytical-elements/{id}
PUT    /v1/management/{spaceId}/schema/L3/analytical-elements/{id}
DELETE /v1/management/{spaceId}/schema/L3/analytical-elements/{id}
```

### 6.2 实例管理

```
GET    /v1/management/{spaceId}/instances/metrics/{entityId}
POST   /v1/management/{spaceId}/instances/metrics/compute
DELETE /v1/management/{spaceId}/instances/metrics/{entityId}/{metricId}
```

### 6.3 缓存管理

```
POST /v1/management/{spaceId}/instances/metrics/invalidate
# Body: { entity_id: "SUP_001", metric_id: "credit_score" }
```

---

## 7. 与 v1 的区别

| v1 | v2 |
|-----|-----|
| formula 占位符 | 真实可执行的 formula |
| 无类型区分 | 明确 atomic/derived/composite/graph |
| 无缓存定义 | 支持缓存策略配置 |
| 无依赖声明 | 自动推导依赖 DAG |
| 指标值混在 attributes | 指标值独立存储 |

---

*文档结束*

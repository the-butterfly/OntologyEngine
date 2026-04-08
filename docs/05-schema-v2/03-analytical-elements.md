# L3: 分析要素 (Analytical Elements)

> 基于事实对象提炼的分析指标

## 核心概念

```yaml
analytical_elements:
  metrics:           # 指标定义
  variables:         # 变量定义
  functions:         # 可复用函数
```

## 指标类型

### 基础指标 (Atomic)

直接从事实对象获取或外部输入。

```yaml
analytical_elements:
  metrics:
    - name: annual_revenue
      type: atomic
      description: "年营业收入"
      source:
        type: fact_attribute
        entity: Company
        attribute: annual_revenue.value

    - name: total_assets
      type: atomic
      description: "总资产"
      source:
        type: fact_attribute
        entity: Company
        attribute: total_assets.value

    - name: external_credit_score
      type: atomic
      description: "外部征信评分"
      source:
        type: external_api
        provider: pbccrc
        field: credit_score
```

### 派生指标 (Derived)

基于基础指标计算。

**⚠️ 注意**: L3 指标 **不包含 formula 计算逻辑**。formula 统一在 L4 Business Logic 中声明。

L3 仅定义：
- 指标名称和类型
- 数据来源（属性或外部 API）
- 依赖的其他指标

计算逻辑在 L4 通过算子或 formula 实现，实现「指标定义」与「计算逻辑」分离。

```yaml
# L3: 仅定义指标存在及其依赖
analytical_elements:
  metrics:
    - name: credit_score
      type: derived
      description: "信用评分"
      dependencies:
        - financial_health_score
        - guarantee_exposure_score
      # formula 在 L4 声明
```

```yaml
    # derived 类型仅声明指标，计算逻辑在 L4 定义
    - name: asset_liability_ratio
      type: derived
      description: "资产负债率"
      dependencies:
        - total_assets
        - total_liabilities
      unit: percentage
      range: [0, 100]

    - name: current_ratio
      type: derived
      description: "流动比率"
      dependencies:
        - current_assets
        - current_liabilities
      unit: ratio

    - name: revenue_growth_rate
      type: derived
      description: "营收增长率"
      dependencies:
        - current_revenue
        - previous_revenue
      unit: percentage
      parameters:
        - name: period
          type: string
          default: "1Y"
      # formula 在 L4 通过 FORMULA 或 SCORECARD 算子声明
```

### 复合指标 (Composite)

多维度加权聚合。组件和权重在 L4 计算时指定。

```yaml
    - name: financial_health_score
      type: composite
      description: "财务健康度"
      components:
        - asset_liability_ratio
        - current_ratio
        - revenue_growth_rate
        - profit_margin
      # 权重和方向在 L4 SCORECARD 或 FORMULA 算子中声明

    - name: credit_score
      type: composite
      description: "综合信用评分"
      components:
        - financial_health_score
        - business_stability_score
        - external_credit_score
        - graph_centrality_score
```

### 图指标 (Graph)

基于关系网络的指标。

```yaml
    - name: guarantee_chain_length
      type: graph
      description: "担保链长度"
      algorithm:
        type: path_length
        relation: Guarantee
        direction: outgoing
        max_depth: 10

    - name: network_centrality
      type: graph
      description: "网络中心性"
      algorithm:
        type: betweenness_centrality
        relation: [Transaction, Guarantee]
        scope: global

    - name: related_risk_exposure
      type: graph
      description: "关联风险敞口"
      algorithm:
        type: aggregation
        traversal:
          - relation: Guarantee
            depth: 2
            aggregation: sum
            field: guarantee_amount.value
```

## 变量定义

```yaml
  variables:
    - name: industry_avg_revenue
      description: "行业平均营收"
      scope: industry_category
      aggregation: avg
      source_metric: annual_revenue

    - name: region_risk_coefficient
      description: "地区风险系数"
      scope: registered_address.province
      source:
        type: lookup_table
        table: region_risk_config
```

## 可复用函数

```yaml
  functions:
    - name: normalize
      description: "归一化到 [0, 1]"
      parameters:
        - name: value
          type: decimal
        - name: min
          type: decimal
        - name: max
          type: decimal
      body: "(value - min) / (max - min)"

    - name: percentile_rank
      description: "计算百分位排名"
      parameters:
        - name: value
          type: decimal
        - name: distribution
          type: array
      body: "..."

    - name: days_since
      description: "计算距今天数"
      parameters:
        - name: date
          type: date
      body: "today() - date"
```

## 缓存策略

```yaml
cache:
  - metric: "*.score"
    ttl: 3600              # 评分类缓存1小时
    invalidate_on:
      - fact_change

  - metric: "graph.*"
    ttl: 86400             # 图指标缓存24小时
    invalidate_on:
      - relation_change
```

## 指标依赖图

```
annual_revenue ──────┐
total_assets ────┐   │
total_liabilities─┼──┼──▶ asset_liability_ratio ──┐
                 │   │                              │
current_assets ──┤   │                              ├─▶ financial_health_score ──┐
current_liabilities▶ current_ratio ─────────────────┤                              │
                                                    │                              ├─▶ credit_score
revenue_growth ─────────────────────────────────────┤                              │
                                                    │                              │
business_years ───────▶ stability_score ────────────┘                              │
                                                                                  │
external_credit ──────────────────────────────────────────────────────────────────┤
                                                                                  │
graph_centrality ─────────────────────────────────────────────────────────────────┘
```

## 与 v1 metrics 的区别

| v1 | v2 |
|-----|-----|
| formula 占位符 | 真实可执行的 formula |
| 无类型区分 | 明确 atomic/derived/composite/graph |
| 无缓存定义 | 支持缓存策略配置 |
| 无依赖声明 | 自动推导依赖DAG |

## 运行时行为

```python
class MetricEngine:
    def compute(self, metric_name: str, entity: Entity) -> MetricValue:
        metric = self.get_metric(metric_name)

        # 检查缓存
        if cached := self.cache.get(entity.id, metric_name):
            return cached

        # 计算
        if metric.type == "atomic":
            value = self.load_atomic(metric, entity)
        elif metric.type == "derived":
            value = self.evaluate_formula(metric.formula, entity)
        elif metric.type == "composite":
            value = self.aggregate_components(metric, entity)
        elif metric.type == "graph":
            value = self.run_graph_algorithm(metric.algorithm, entity)

        # 缓存
        self.cache.set(entity.id, metric_name, value, metric.ttl)

        return value
```

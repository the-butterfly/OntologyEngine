# 模块 04: 指标引擎 (MetricEngine)

> **位置**: `ontology_engine/engine/metric/`
> **依赖**: SchemaLoader, DuckDBStorage, NetworkXGraphStore, ExpressionEngine
> **被依赖**: AnalysisService, RuleEngine

> ⚠️ **L3/L4 公式归属说明**：L3 的 `formula` 是**默认计算公式**，代表指标的客观定义（如比率计算方式），任何规则组应保持一致。L4 action 中的 `computation.formula` 用于**业务决策逻辑**（如授信额度乘数），可覆盖 L3 默认值。这**不是重复定义**，而是**默认 + 可覆盖**机制——避免同一指标在不同规则组中出现不一致的计算结果。

## 1. 职责

1. **四类指标计算** — atomic / derived / composite / graph
2. **DAG 依赖解析** — 自动构建指标依赖图，拓扑排序
3. **增量更新** — 利用缓存和过期策略避免重复计算
4. **批量预计算** — 为规则引擎一次性准备好所有 L3 输入

## 2. 核心接口

```python
# engine/metric/engine.py

class MetricEngine:
    """指标计算引擎"""
    
    def __init__(
        self,
        schema: KGMLSchema,
        storage: DuckDBStorage,
        graph_store: NetworkXGraphStore,
        expr_engine: ExpressionEngine,
        cache: MetricCache
    ):
        self.schema = schema
        self.storage = storage
        self.graph_store = graph_store
        self.expr_engine = expr_engine
        self.cache = cache
        
        # 预构建指标 DAG
        self._metric_defs = {m.name: m for m in schema.metrics}
        self._dag = self._build_dag()
    
    async def compute(
        self,
        metric_name: str,
        entity: Entity,
        context: dict | None = None
    ) -> Any:
        """计算单个指标
        
        自动处理依赖: 如果依赖指标未计算，递归计算
        """
        metric_def = self._metric_defs.get(metric_name)
        if not metric_def:
            raise MetricNotFoundError(metric_name)
        
        # 检查缓存
        cached = self.cache.get(entity.id, metric_name)
        if cached is not None:
            return cached
        
        # 确保依赖已计算
        dep_values = {}
        for dep in metric_def.dependencies:
            dep_values[dep] = await self.compute(dep, entity, context)
        
        # 按类型计算
        if metric_def.metric_type == "atomic":
            value = await self._compute_atomic(metric_def, entity, context)
        elif metric_def.metric_type == "derived":
            value = await self._compute_derived(metric_def, entity, dep_values, context)
        elif metric_def.metric_type == "composite":
            value = await self._compute_composite(metric_def, entity, dep_values, context)
        elif metric_def.metric_type == "graph":
            value = await self._compute_graph(metric_def, entity, context)
        else:
            raise MetricError(f"未知指标类型: {metric_def.metric_type}")
        
        # 缓存
        self.cache.set(entity.id, metric_name, value)
        
        # 持久化
        await self.storage.save_metric(entity.id, metric_name, value)
        
        return value
    
    async def compute_batch(
        self,
        metric_names: list[str],
        entity: Entity,
        context: dict | None = None
    ) -> dict[str, Any]:
        """批量计算指标
        
        按拓扑排序优化计算顺序，确保依赖先算
        """
        # 收集所有需要的指标 (包括传递依赖)
        required = self._collect_dependencies(metric_names)
        
        # 按拓扑排序计算
        sorted_metrics = self._topological_sort(required)
        
        results = {}
        for metric_name in sorted_metrics:
            # 跳过已有缓存
            if metric_name in results:
                continue
            results[metric_name] = await self.compute(metric_name, entity, context)
        
        return {name: results[name] for name in metric_names}
```

## 3. 四类指标计算

### 3.1 原子指标 (Atomic)

```python
async def _compute_atomic(
    self,
    metric_def: MetricDefinition,
    entity: Entity,
    context: dict | None
) -> Any:
    """原子指标: 直接从实体属性或存储查询获取
    
    供应链金融场景示例:
    - total_invoice_amount_90d: 聚合关联发票
    - overdue_invoice_amount: 聚合逾期发票
    - negative_news_count_90d: 直接属性或外部数据
    """
    # 优先: 从 entity 属性获取
    if metric_def.name in entity.attributes:
        return entity.attributes[metric_def.name]
    
    # 次选: 从 computed_metrics 获取 (之前计算过的)
    cached = await self.storage.get_metric(entity.id, metric_def.name)
    if cached is not None:
        return cached
    
    # 最后: 执行数据源查询
    if metric_def.graph_query:
        # 图查询获取 (Phase 1: 从 DuckDB 关系查询模拟)
        return await self._query_from_relations(metric_def, entity)
    
    # 无法计算 — 返回默认值
    if metric_def.default is not None:
        return metric_def.default
    
    raise MetricNotComputableError(
        f"原子指标 {metric_def.name} 无法从实体 {entity.id} 获取"
    )


async def _query_from_relations(
    self,
    metric_def: MetricDefinition,
    entity: Entity
) -> Any:
    """从关联实体聚合计算原子指标
    
    示例: total_invoice_amount_90d
    1. 查询 Supplier 的 has_invoice 关系
    2. 获取所有关联 Invoice
    3. 过滤 90 天内
    4. 聚合 sum(amount.value)
    """
    # 供应链金融场景的硬编码聚合逻辑
    # Phase 2 改为解析 graph_query DSL
    
    if metric_def.name == "total_invoice_amount_90d":
        neighbors = await self.storage.get_neighbors(
            entity.id, relation_type="has_invoice", direction="outgoing"
        )
        total = 0
        cutoff = date.today() - timedelta(days=90)
        for inv_entity, rel in neighbors:
            amount = inv_entity.attributes.get("amount", {})
            if isinstance(amount, dict):
                val = amount.get("value", 0)
            else:
                val = amount
            issue_date_str = inv_entity.attributes.get("issue_date", "")
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                if issue_date >= cutoff:
                    total += val
            except (ValueError, TypeError):
                pass
        return {"value": total, "currency": "CNY"}
    
    elif metric_def.name == "overdue_invoice_amount":
        neighbors = await self.storage.get_neighbors(
            entity.id, relation_type="has_invoice", direction="outgoing"
        )
        total = 0
        for inv_entity, rel in neighbors:
            if inv_entity.attributes.get("status") == "OVERDUE":
                amount = inv_entity.attributes.get("amount", {})
                val = amount.get("value", 0) if isinstance(amount, dict) else amount
                total += val
        return {"value": total, "currency": "CNY"}
    
    elif metric_def.name == "invoice_count_90d":
        neighbors = await self.storage.get_neighbors(
            entity.id, relation_type="has_invoice", direction="outgoing"
        )
        cutoff = date.today() - timedelta(days=90)
        count = 0
        for inv_entity, rel in neighbors:
            issue_date_str = inv_entity.attributes.get("issue_date", "")
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                if issue_date >= cutoff:
                    count += 1
            except (ValueError, TypeError):
                pass
        return count
    
    elif metric_def.name == "total_contract_amount":
        neighbors = await self.storage.get_neighbors(
            entity.id, relation_type="has_contract", direction="outgoing"
        )
        total = 0
        for ctr_entity, rel in neighbors:
            amount = ctr_entity.attributes.get("contract_amount", {})
            val = amount.get("value", 0) if isinstance(amount, dict) else amount
            total += val
        return {"value": total, "currency": "CNY"}
    
    elif metric_def.name == "core_enterprise_count":
        neighbors = await self.storage.get_neighbors(
            entity.id, relation_type="supplies_to", direction="outgoing"
        )
        return len(neighbors)
    
    else:
        return 0  # 默认值
```

### 3.2 派生指标 (Derived)

```python
async def _compute_derived(
    self,
    metric_def: MetricDefinition,
    entity: Entity,
    dep_values: dict[str, Any],
    context: dict | None
) -> Any:
    """派生指标: 基于 formula 表达式计算
    
    供应链金融场景示例:
    - overdue_invoice_ratio = overdue_invoice_amount / total_invoice_amount_90d * 100
    - avg_invoice_amount = total_invoice_amount_90d / invoice_count_90d
    - contract_utilization_rate = total_invoice_amount_90d / total_contract_amount * 100
    """
    if not metric_def.formula:
        raise MetricError(f"派生指标 {metric_def.name} 缺少 formula")
    
    # 构建求值上下文
    eval_context = self._build_eval_context(entity, dep_values, context)
    
    # 执行表达式
    result = self.expr_engine.evaluate(metric_def.formula, eval_context)
    
    # 类型适配
    if metric_def.type == "Percentage" and isinstance(result, (int, float)):
        result = round(result, 2)
    elif metric_def.type == "Money" and isinstance(result, (int, float)):
        result = {"value": result, "currency": "CNY"}
    
    return result


def _build_eval_context(
    self,
    entity: Entity,
    dep_values: dict[str, Any],
    context: dict | None
) -> dict:
    """构建表达式求值上下文
    
    合并: entity 属性 + 依赖指标值 + 外部上下文
    """
    eval_ctx = {}
    
    # 实体属性 (展平嵌套)
    for key, value in entity.attributes.items():
        if isinstance(value, dict) and "value" in value:
            eval_ctx[key] = value  # 保留原始结构，表达式可以用 key.value
        else:
            eval_ctx[key] = value
    
    # 依赖指标值
    for dep_name, dep_value in dep_values.items():
        eval_ctx[dep_name] = dep_value
    
    # 外部上下文 (覆盖)
    if context:
        eval_ctx.update(context)
    
    return eval_ctx
```

### 3.3 复合指标 (Composite)

```python
async def _compute_composite(
    self,
    metric_def: MetricDefinition,
    entity: Entity,
    dep_values: dict[str, Any],
    context: dict | None
) -> Any:
    """复合指标: 多维度加权聚合
    
    供应链金融场景示例:
    - credit_score = SUM(component_score * weight) * 100
      components: business_stability_score(0.30), tax_compliance_score(0.25), ...
    """
    if not metric_def.components:
        # 如果有 formula，用 formula 计算
        if metric_def.formula:
            eval_context = self._build_eval_context(entity, dep_values, context)
            return self.expr_engine.evaluate(metric_def.formula, eval_context)
        raise MetricError(f"复合指标 {metric_def.name} 缺少 components 和 formula")
    
    # 计算每个组件
    weighted_sum = 0.0
    total_weight = 0.0
    
    for comp in metric_def.components:
        # 获取组件值
        comp_value = dep_values.get(comp.metric)
        if comp_value is None:
            # 尝试从缓存/计算获取
            comp_value = await self.compute(comp.metric, entity, context)
        
        # 转换
        if comp.transform:
            eval_ctx = {comp.metric: comp_value, "value": comp_value}
            comp_value = self.expr_engine.evaluate(comp.transform, eval_ctx)
        
        # 提取数值
        numeric_value = self._to_numeric(comp_value)
        
        weighted_sum += numeric_value * comp.weight
        total_weight += comp.weight
    
    result = weighted_sum if total_weight == 0 else weighted_sum / total_weight * sum(c.weight for c in metric_def.components)
    
    # 输出范围裁剪
    if metric_def.output_range:
        result = max(metric_def.output_range[0], min(metric_def.output_range[1], result))
    
    return round(result, 2)


def _to_numeric(self, value: Any) -> float:
    """将指标值转为数值"""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and "value" in value:
        return float(value["value"])
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0
```

### 3.4 图指标 (Graph)

```python
async def _compute_graph(
    self,
    metric_def: MetricDefinition,
    entity: Entity,
    context: dict | None
) -> Any:
    """图指标: 基于 NetworkX 图算法计算
    
    供应链金融场景示例:
    - guarantee_chain_depth: 担保链深度 (longest_path)
    - network_centrality_score: 网络中心性 (page_rank)
    """
    if metric_def.algorithm == "longest_path":
        depth = self.graph_store.find_longest_path(
            source=entity.id,
            relation_type="guarantees_for",
            max_depth=10
        )
        return depth
    
    elif metric_def.algorithm == "page_rank":
        score = self.graph_store.calculate_centrality(
            node_id=entity.id,
            method="pagerank"
        )
        return round(score, 4)
    
    elif metric_def.algorithm == "cycle_detection":
        cycles = self.graph_store.detect_cycles(
            center_id=entity.id,
            max_depth=10
        )
        return len(cycles) > 0
    
    elif metric_def.algorithm == "betweenness":
        score = self.graph_store.calculate_centrality(
            node_id=entity.id,
            method="betweenness"
        )
        return round(score, 4)
    
    else:
        raise MetricError(f"未知图算法: {metric_def.algorithm}")
```

## 4. DAG 依赖管理

```python
# engine/metric/dag.py

class MetricDAG:
    """指标依赖 DAG"""
    
    def __init__(self, metrics: list[MetricDefinition]):
        self.metrics = {m.name: m for m in metrics}
        self.graph = self._build()
        self._validate()
    
    def _build(self) -> nx.DiGraph:
        """构建依赖图"""
        G = nx.DiGraph()
        
        for metric in self.metrics.values():
            G.add_node(metric.name, metric=metric)
            for dep in metric.dependencies:
                G.add_edge(dep, metric.name)
        
        return G
    
    def _validate(self):
        """校验 DAG 无环"""
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise MetricDAGError(f"指标依赖存在循环: {cycles}")
    
    def topological_order(self, target_metrics: list[str] | None = None) -> list[str]:
        """拓扑排序
        
        Args:
            target_metrics: 目标指标列表。如果指定，只返回这些指标及其传递依赖的排序
        """
        if target_metrics is None:
            return list(nx.topological_sort(self.graph))
        
        # 收集传递依赖
        required = set()
        for target in target_metrics:
            required.add(target)
            if target in self.graph:
                for pred in nx.ancestors(self.graph, target):
                    required.add(pred)
        
        # 过滤子图并排序
        subgraph = self.graph.subgraph(required & set(self.graph.nodes))
        return list(nx.topological_sort(subgraph))
    
    def get_dependencies(self, metric_name: str) -> set[str]:
        """获取直接依赖"""
        return set(self.graph.predecessors(metric_name)) if metric_name in self.graph else set()
    
    def get_all_dependencies(self, metric_name: str) -> set[str]:
        """获取传递依赖"""
        return nx.ancestors(self.graph, metric_name) if metric_name in self.graph else set()
```

## 5. 供应链金融场景计算流

以"信用评分"为例的完整计算链路:

```
输入: Supplier (SUP_2024_001)
      ↓
[atomic]  total_invoice_amount_90d   ← 从 Invoice 关系聚合
[atomic]  invoice_count_90d          ← 从 Invoice 关系计数
[atomic]  overdue_invoice_amount     ← 从 Invoice (OVERDUE) 聚合
[atomic]  total_contract_amount      ← 从 Contract 关系聚合
[atomic]  core_enterprise_count      ← 从 supplies_to 关系计数
[atomic]  tax_compliance_score       ← 实体属性
[atomic]  negative_news_count_90d    ← 实体属性
      ↓
[derived] overdue_invoice_ratio      = overdue_invoice_amount / total_invoice_amount_90d * 100
[derived] avg_invoice_amount         = total_invoice_amount_90d / invoice_count_90d
[derived] contract_utilization_rate  = total_invoice_amount_90d / total_contract_amount * 100
[derived] business_stability_score   = formula(基于 contract_utilization_rate, ...)
      ↓
[graph]   guarantee_chain_depth      = longest_path(SUP_2024_001, "guarantees_for")
[graph]   network_centrality_score   = pagerank(SUP_2024_001)
      ↓
[derived] reputation_score           = formula(基于 negative_news_count_90d, overdue_invoice_ratio)
[derived] guarantee_risk_score       = formula(基于 guarantee_chain_depth)
      ↓
[composite] credit_score             = Σ(component * weight)
            = business_stability_score*0.30
            + tax_compliance_score*0.25
            + network_centrality_score*0.15
            + reputation_score*0.15
            + guarantee_risk_adjustment*0.15
      ↓
[derived] credit_grade               = SWITCH(credit_score)
            >= 90 → AAA, >= 85 → AA, ...
```

## 6. 错误处理

```python
class MetricError(Exception):
    """指标计算错误基类"""

class MetricNotFoundError(MetricError):
    """指标定义不存在"""

class MetricNotComputableError(MetricError):
    """指标无法计算 (缺少输入)"""

class MetricDAGError(MetricError):
    """指标依赖图错误 (循环依赖)"""

class MetricTimeoutError(MetricError):
    """指标计算超时"""
```

## 7. 文件结构

```
ontology_engine/engine/metric/
├── __init__.py           # 导出 MetricEngine
├── engine.py             # MetricEngine 主类
├── dag.py                # MetricDAG 依赖图
├── atomic.py             # 原子指标计算 (聚合查询)
├── derived.py            # 派生指标计算 (表达式)
├── composite.py          # 复合指标计算 (加权聚合)
├── graph_metrics.py      # 图指标计算 (委托 NetworkX)
└── errors.py             # 异常定义
```

# 后端模块详细设计 - builders.py

> **文件**: `ontology_engine/visualization/builders.py`
> **职责**: 将 KGML Schema 数据转换为 G6/X6 兼容的图数据

## 一、SchemaGraphBuilder

### 1.1 职责

将 `KGMLSchema` 转换为 `SchemaGraphData`（G6兼容格式），支持4种视图：

| graph_type | 展示内容 | 布局 | 重点 |
|-----------|---------|------|------|
| entity_relation | L1实体+关系边 | force/dagre LR | 实体关系概览 |
| metric_dependency | L3指标+依赖边(带权重) | dagre TB | **勾稽逻辑**核心视图 |
| full | L1+L3+L4全量 | dagre LR | 全景图 |
| rule_overview | L4规则+输入依赖 | dagre TB | 规则概览 |

### 1.2 构建逻辑

```python
class SchemaGraphBuilder:
    """KGML Schema → G6 图数据"""

    def __init__(self, schema: KGMLSchema):
        self.schema = schema
        # 建立指标名→MetricDefinition的快速索引
        self._metric_index: dict[str, MetricDefinition] = {
            m.name: m for m in schema.metrics
        }
        # 建立规则ID→RuleDefinition的快速索引
        self._rule_index: dict[str, RuleDefinition] = {}
        if schema.rules:
            for r in schema.rules.ruleset:
                self._rule_index[r.id] = r

    def build(
        self,
        graph_type: str,
        layer_filter: list[str] | None = None,
    ) -> SchemaGraphData:
        """构建图数据"""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # 根据 graph_type 决定包含哪些层
        layers = self._resolve_layers(graph_type, layer_filter)

        # L1: 事实对象 → 实体节点 + 关系边
        if "L1" in layers:
            for concept in self.schema.concepts:
                if concept.category == "entity":
                    nodes.append(self._build_entity_node(concept))
                    for rel in concept.relations:
                        edges.append(self._build_relation_edge(concept.name, rel))

        # L3: 分析指标 → 指标节点 + 依赖边(带权重)
        if "L3" in layers:
            for metric in self.schema.metrics:
                nodes.append(self._build_metric_node(metric))
                for dep in metric.dependencies:
                    edges.append(self._build_metric_dep_edge(dep, metric))

        # L4: 业务规则 → 规则节点 + 输入边
        if "L4" in layers:
            if self.schema.rules:
                for rule in self.schema.rules.ruleset:
                    nodes.append(self._build_rule_node(rule))

        # 跨层依赖边（指标→规则的数据流）
        if "L3" in layers or "L4" in layers:
            edges.extend(self._build_cross_layer_edges())

        return SchemaGraphData(
            schema_id=self.schema.metadata.id,
            graph_type=graph_type,
            nodes=nodes,
            edges=edges,
            layout_config=self._get_layout_config(graph_type),
            metadata=self._build_metadata(nodes, edges),
        )
```

### 1.3 节点构建方法

#### _build_entity_node(concept)

```python
def _build_entity_node(self, concept: ConceptDefinition) -> GraphNode:
    """构建实体节点"""
    key_attrs = [a.name for a in concept.attributes if a.required or a.unique][:4]
    return GraphNode(
        id=concept.name,
        type="entity",
        data={
            "label": self._translate_concept_name(concept.name),
            "layer": "L1",
            "attribute_count": len(concept.attributes),
            "key_attributes": key_attrs,
            "description": concept.description or "",
        },
    )
```

**概念名翻译映射** (硬编码中文映射，后续可抽取)：
- Supplier → 供应商
- CoreEnterprise → 核心企业
- Invoice → 发票
- Contract → 合同
- LogisticsRecord → 物流记录
- GuaranteeRelation → 担保关系

#### _build_metric_node(metric)

```python
def _build_metric_node(self, metric: MetricDefinition) -> GraphNode:
    """构建指标节点 - 勾稽逻辑的关键展示"""
    # 从 composite 的 components 提取权重
    weight_map = self._extract_weights(metric)

    return GraphNode(
        id=metric.name,
        type="metric",
        data={
            "label": self._translate_metric_name(metric.name),
            "layer": "L3",
            "metric_type": metric.type or "atomic",  # atomic|derived|composite|graph
            "formula": metric.formula or "",
            "dependencies": metric.dependencies,
            "weight_map": weight_map,  # { dep_name: weight } - 勾稽逻辑核心
            "description": metric.description or "",
        },
    )
```

**权重提取** - 从信用评分的 components 中提取：

```python
def _extract_weights(self, metric: MetricDefinition) -> dict[str, float]:
    """从 composite metric 的 schema 定义中提取权重"""
    # credit_score 的勾稽关系：
    # business_stability_score: 0.30
    # tax_compliance_score: 0.25
    # network_centrality_score: 0.15
    # reputation_score: 0.15
    # guarantee_risk_adjustment: 0.15
    
    # 硬编码映射（从 schema.yaml 的 components 提取）
    WEIGHT_MAPS = {
        "credit_score": {
            "business_stability_score": 0.30,
            "tax_compliance_score": 0.25,
            "network_centrality_score": 0.15,
            "reputation_score": 0.15,
            "guarantee_chain_depth": 0.15,  # guarantee_risk_adjustment 的实际依赖
        },
    }
    return WEIGHT_MAPS.get(metric.name, {})
```

#### _build_rule_node(rule)

```python
def _build_rule_node(self, rule: RuleDefinition) -> GraphNode:
    """构建规则节点"""
    # 条件预览（截断长表达式）
    condition_preview = self._preview_condition(rule.when)
    # 动作预览
    action_preview = rule.then.action if rule.then else ""

    return GraphNode(
        id=rule.id,
        type="rule",
        data={
            "label": rule.name or rule.id,
            "layer": "L4",
            "rule_type": rule.type,  # constraint|inference|alert|decision
            "priority": rule.priority,
            "condition_preview": condition_preview,
            "action_preview": action_preview,
            "enabled": rule.enabled,
        },
    )
```

### 1.4 边构建方法

#### _build_metric_dep_edge(dep, metric) — 勾稽逻辑边

```python
def _build_metric_dep_edge(self, dep: str, metric: MetricDefinition) -> GraphEdge:
    """构建指标依赖边 - 勾稽逻辑的核心"""
    # 边方向：dep → metric（依赖指向被依赖的下游）
    weight = self._extract_weights(metric).get(dep)
    return GraphEdge(
        id=f"dep_{dep}_{metric.name}",
        source=dep,
        target=metric.name,
        type="metric_dep",
        data={
            "weight": weight,  # None表示非权重依赖
        },
    )
```

#### _build_cross_layer_edges() — 指标→规则数据流

```python
def _build_cross_layer_edges(self) -> list[GraphEdge]:
    """构建跨层依赖边：指标→规则"""
    edges = []
    if not self.schema.rules:
        return edges
    
    for rule in self.schema.rules.ruleset:
        # 从规则条件中提取引用的指标名
        referenced_metrics = self._extract_referenced_metrics(rule)
        for metric_name in referenced_metrics:
            if metric_name in self._metric_index:
                edges.append(GraphEdge(
                    id=f"flow_{metric_name}_{rule.id}",
                    source=metric_name,
                    target=rule.id,
                    type="rule_input",
                    data={},
                ))
    return edges
```

### 1.5 布局配置

```python
def _get_layout_config(self, graph_type: str) -> LayoutConfig:
    """根据图类型返回布局配置"""
    configs = {
        "entity_relation": LayoutConfig(type="force", rankdir="LR", nodesep=50, ranksep=80),
        "metric_dependency": LayoutConfig(type="dagre", rankdir="TB", nodesep=40, ranksep=60),
        "full": LayoutConfig(type="dagre", rankdir="LR", nodesep=50, ranksep=80),
        "rule_overview": LayoutConfig(type="dagre", rankdir="TB", nodesep=50, ranksep=80),
    }
    return configs.get(graph_type, LayoutConfig())
```

## 二、RuleChainGraphBuilder

### 2.1 职责

将指定维度的规则列表转换为 `RuleChainGraphData`（X6兼容格式），展示规则执行顺序和数据流。

### 2.2 构建逻辑

```python
class RuleChainGraphBuilder:
    """Rules → X6 规则链 DAG"""

    def __init__(self, schema: KGMLSchema):
        self.schema = schema

    def build(self, dimension: str) -> RuleChainGraphData:
        """构建规则链 DAG"""
        rules = self.schema.get_rules_for_dimension(dimension)
        rules = sorted(rules, key=lambda r: -r.priority)  # 优先级降序

        nodes = [self._build_rule_node(rule, idx) for idx, rule in enumerate(rules)]
        edges = self._build_data_flow_edges(rules)

        dim_info = self._get_dimension_info(dimension)

        return RuleChainGraphData(
            dimension=dimension,
            nodes=nodes,
            edges=edges,
            dimension_info=dim_info,
        )
```

### 2.3 规则链节点位置

```python
def _build_rule_node(self, rule: RuleDefinition, index: int) -> RuleChainNode:
    """构建规则链节点，自动排列位置"""
    # 从上到下排列，每行一个规则
    y = index * 120 + 100
    x = 300  # 居中

    return RuleChainNode(
        id=rule.id,
        position={"x": x, "y": y},
        data={
            "ruleId": rule.id,
            "ruleName": rule.name or "",
            "ruleType": rule.type,
            "priority": rule.priority,
            "condition": self._serialize_condition(rule.when),
            "action": rule.then.action if rule.then else "",
            "enabled": rule.enabled,
            "dimension": rule.scope.get("dimensions", []) if rule.scope else [],
        },
    )
```

### 2.4 规则间数据流边

规则间边表示"前一条规则的输出是后一条规则的输入"：

```python
def _build_data_flow_edges(self, rules: list[RuleDefinition]) -> list[RuleChainEdge]:
    """构建规则间数据流边"""
    edges = []
    
    # 规则链的依赖关系（硬编码，来自 schema.yaml 的逻辑顺序）
    # R001 → R002: R001通过后→执行信用评分
    # R002 → R003: 信用评分后→检查担保圈
    # R002 → R004: 信用评分后→计算额度
    # R003 → R007: 担保圈影响决策
    # R004 → R006: 额度计算后→利率定价
    # R004 → R007: 额度计算后→综合决策
    
    # 通用方法：从规则条件中提取依赖
    rule_ids = [r.id for r in rules]
    
    for i, rule in enumerate(rules):
        # 后续规则如果条件中引用了前面规则的输出字段，
        # 则存在数据流依赖
        for j in range(i + 1, len(rules)):
            later_rule = rules[j]
            if self._has_data_dependency(rule, later_rule):
                edges.append(RuleChainEdge(
                    id=f"{rule.id}-{later_rule.id}",
                    source=rule.id,
                    target=later_rule.id,
                    data={
                        "dependency_type": "data_flow",
                        "description": f"{rule.id} 输出 → {later_rule.id} 输入",
                    },
                ))
    
    return edges
```

**数据流依赖检测**：检查后规则的 when 条件是否引用了前规则的 then 输出字段。

## 三、辅助方法

### 概念名/指标名中文映射

```python
# 概念名中文映射
CONCEPT_LABELS = {
    "Supplier": "供应商",
    "CoreEnterprise": "核心企业",
    "Invoice": "发票",
    "Contract": "合同",
    "LogisticsRecord": "物流记录",
    "GuaranteeRelation": "担保关系",
}

# 指标名中文映射
METRIC_LABELS = {
    "total_invoice_amount_90d": "近90天发票总额",
    "invoice_count_90d": "近90天发票数",
    "overdue_invoice_amount": "逾期发票金额",
    "total_contract_amount": "合同总金额",
    "avg_monthly_tax_revenue": "月均纳税额",
    "tax_compliance_score": "税务合规评分",
    "negative_news_count_90d": "近90天负面新闻数",
    "core_enterprise_count": "合作核心企业数",
    "overdue_invoice_ratio": "逾期发票占比",
    "avg_invoice_amount": "平均发票金额",
    "contract_utilization_rate": "合同执行率",
    "business_stability_score": "业务稳定性评分",
    "guarantee_chain_depth": "担保链深度",
    "network_centrality_score": "网络中心性得分",
    "credit_score": "综合信用评分",
    "reputation_score": "声誉风险评分",
    "guarantee_risk_score": "担保风险评分",
    "credit_grade": "信用等级",
}
```

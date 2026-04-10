# 测试设计 + 验收场景

> **目录**: `tests/unit/visualization/`
> **覆盖率目标**: ≥ 80%

## 一、后端测试

### 1.1 test_models.py

```python
"""测试可视化数据模型"""
import pytest
from ontology_engine.visualization.models import (
    GraphNode, GraphEdge, SchemaGraphData, LayoutConfig, GraphMetadata,
    RuleChainNode, RuleChainEdge, RuleChainGraphData, DimensionInfo,
    ConditionDetail, ExecutionStepSnapshot,
    SimulationResult, DiffEntry, ImpactChain, ComparisonResult,
)


class TestGraphNode:
    def test_entity_node_creation(self):
        node = GraphNode(id="Supplier", type="entity", data={"label": "供应商"})
        assert node.id == "Supplier"
        assert node.type == "entity"

    def test_metric_node_with_weight_map(self):
        node = GraphNode(
            id="credit_score",
            type="metric",
            data={"metric_type": "composite", "weight_map": {"business_stability_score": 0.30}},
        )
        assert node.data["weight_map"]["business_stability_score"] == 0.30


class TestSchemaGraphData:
    def test_full_graph_data(self):
        data = SchemaGraphData(
            schema_id="test",
            graph_type="entity_relation",
            nodes=[GraphNode(id="n1", type="entity", data={})],
            edges=[GraphEdge(id="e1", source="n1", target="n2", type="relation", data={})],
            layout_config=LayoutConfig(),
            metadata=GraphMetadata(entity_count=1),
        )
        assert len(data.nodes) == 1
        assert len(data.edges) == 1
```

### 1.2 test_schema_graph_builder.py

```python
"""测试 SchemaGraphBuilder"""
import pytest
from ontology_engine.visualization.builders import SchemaGraphBuilder
from ontology_engine.core.schema.models import (
    KGMLSchema, SchemaMetadata, ConceptDefinition, AttributeDefinition,
    RelationDefinition, MetricDefinition, RulesDefinition, RuleDefinition,
)


@pytest.fixture
def supply_chain_schema() -> KGMLSchema:
    """构建供应链金融 Schema (简化版)"""
    return KGMLSchema(
        metadata=SchemaMetadata(id="kg://test/1.0", name="测试"),
        concepts=[
            ConceptDefinition(
                name="Supplier",
                description="供应商",
                category="entity",
                attributes=[
                    AttributeDefinition(name="supplier_id", type="string", required=True),
                    AttributeDefinition(name="status", type="string", required=True),
                    AttributeDefinition(name="registered_capital", type="Money", required=True),
                ],
                relations=[
                    RelationDefinition(name="has_invoice", target="Invoice", cardinality="0..*"),
                ],
            ),
            ConceptDefinition(
                name="Invoice",
                description="发票",
                category="entity",
                attributes=[
                    AttributeDefinition(name="invoice_no", type="string", required=True),
                    AttributeDefinition(name="amount", type="Money", required=True),
                ],
            ),
        ],
        metrics=[
            MetricDefinition(
                name="total_invoice_amount_90d",
                description="近90天发票总额",
                type="atomic",
                scope="Supplier",
                dependencies=[],
            ),
            MetricDefinition(
                name="overdue_invoice_amount",
                description="逾期发票金额",
                type="atomic",
                scope="Supplier",
                dependencies=[],
            ),
            MetricDefinition(
                name="overdue_invoice_ratio",
                description="逾期发票占比",
                type="derived",
                scope="Supplier",
                formula="overdue_invoice_amount / total_invoice_amount_90d * 100",
                dependencies=["overdue_invoice_amount", "total_invoice_amount_90d"],
            ),
            MetricDefinition(
                name="credit_score",
                description="综合信用评分",
                type="composite",
                scope="Supplier",
                dependencies=[
                    "business_stability_score", "tax_compliance_score",
                    "network_centrality_score", "reputation_score",
                    "guarantee_chain_depth",
                ],
            ),
        ],
        rules=RulesDefinition(
            ruleset=[
                RuleDefinition(
                    id="R001",
                    name="基础准入检查",
                    type="constraint",
                    priority=100,
                    scope={"dimensions": ["credit_assessment"]},
                ),
            ],
        ),
    )


class TestSchemaGraphBuilder:
    def test_entity_relation_graph(self, supply_chain_schema):
        builder = SchemaGraphBuilder(supply_chain_schema)
        result = builder.build("entity_relation")

        assert result.graph_type == "entity_relation"
        # 应包含 Supplier 和 Invoice 两个实体节点
        entity_nodes = [n for n in result.nodes if n.type == "entity"]
        assert len(entity_nodes) == 2

        # 应包含 has_invoice 关系边
        relation_edges = [e for e in result.edges if e.type == "relation"]
        assert len(relation_edges) >= 1

    def test_metric_dependency_graph(self, supply_chain_schema):
        builder = SchemaGraphBuilder(supply_chain_schema)
        result = builder.build("metric_dependency")

        assert result.graph_type == "metric_dependency"
        # 应包含所有4个指标节点
        metric_nodes = [n for n in result.nodes if n.type == "metric"]
        assert len(metric_nodes) == 4

        # 应包含依赖边
        dep_edges = [e for e in result.edges if e.type == "metric_dep"]
        assert len(dep_edges) >= 3  # overdue→ratio, total→ratio, 5→credit_score

        # credit_score 的权重边应标注 weight
        credit_score_deps = [e for e in dep_edges if e.target == "credit_score"]
        weights = [e.data.get("weight") for e in credit_score_deps]
        assert any(w is not None for w in weights)  # 至少一条有权重

    def test_layer_filter(self, supply_chain_schema):
        builder = SchemaGraphBuilder(supply_chain_schema)
        result = builder.build("full", layer_filter=["L1"])

        # 只包含 L1 层节点
        assert all(n.type == "entity" for n in result.nodes)

    def test_full_graph(self, supply_chain_schema):
        builder = SchemaGraphBuilder(supply_chain_schema)
        result = builder.build("full")

        # 应包含 entity + metric + rule 节点
        types = {n.type for n in result.nodes}
        assert "entity" in types
        assert "metric" in types
        assert "rule" in types

    def test_layout_config(self, supply_chain_schema):
        builder = SchemaGraphBuilder(supply_chain_schema)

        er = builder.build("entity_relation")
        assert er.layout_config.type == "force"

        md = builder.build("metric_dependency")
        assert md.layout_config.type == "dagre"
        assert md.layout_config.rankdir == "TB"
```

### 1.3 test_rule_chain_builder.py

```python
"""测试 RuleChainGraphBuilder"""


class TestRuleChainGraphBuilder:
    def test_credit_assessment_chain(self, supply_chain_schema):
        builder = RuleChainGraphBuilder(supply_chain_schema)
        result = builder.build("credit_assessment")

        assert result.dimension == "credit_assessment"
        # R001 应在链中
        assert any(n.id == "R001" for n in result.nodes)
        # 规则按优先级降序
        priorities = [n.data["priority"] for n in result.nodes]
        assert priorities == sorted(priorities, reverse=True)

    def test_empty_dimension(self, supply_chain_schema):
        builder = RuleChainGraphBuilder(supply_chain_schema)
        result = builder.build("nonexistent_dimension")

        assert len(result.nodes) == 0
        assert len(result.edges) == 0
```

### 1.4 test_condition_explainer.py

```python
"""测试 ConditionExplainer"""
from ontology_engine.visualization.explainers import ConditionExplainer
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator
from ontology_engine.core.schema.models import RuleWhen


class TestConditionExplainer:
    def test_simple_expression(self):
        explainer = ConditionExplainer(ExpressionEvaluator())
        when = RuleWhen(expression="status == 'ACTIVE'")
        context = {"status": "ACTIVE"}

        details = explainer.explain(when, context)
        assert len(details) == 1
        assert details[0].result is True
        assert "ACTIVE" in details[0].resolved

    def test_and_expression(self):
        explainer = ConditionExplainer(ExpressionEvaluator())
        when = RuleWhen(expression="status == 'ACTIVE' AND credit_score >= 80")
        context = {"status": "ACTIVE", "credit_score": 92}

        details = explainer.explain(when, context)
        assert len(details) == 2
        assert all(d.result for d in details)

    def test_allof_expression(self):
        explainer = ConditionExplainer(ExpressionEvaluator())
        when = RuleWhen(
            allOf=[
                {"expression": "status == 'ACTIVE'"},
                {"expression": "registered_capital.value >= 1000000"},
            ]
        )
        context = {"status": "ACTIVE", "registered_capital": {"value": 100000000}}

        details = explainer.explain(when, context)
        assert len(details) == 2
        assert all(d.result for d in details)

    def test_failed_condition(self):
        explainer = ConditionExplainer(ExpressionEvaluator())
        when = RuleWhen(expression="credit_score >= 80")
        context = {"credit_score": 45}

        details = explainer.explain(when, context)
        assert len(details) == 1
        assert details[0].result is False
        assert "不满足" in details[0].explanation or "条件不满足" in details[0].explanation

    def test_none_when(self):
        explainer = ConditionExplainer(ExpressionEvaluator())
        details = explainer.explain(None, {})
        assert details == []
```

### 1.5 test_simulator.py

```python
"""测试 RuleChainSimulator - 5个验收场景"""
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestRuleChainSimulator:
    """5个验收场景的模拟测试"""

    @pytest.mark.asyncio
    async def test_scenario1_schema_graph(self, supply_chain_schema):
        """场景一：Schema 实体关系图 - 验证 nodes 和 edges 数量"""
        builder = SchemaGraphBuilder(supply_chain_schema)
        result = builder.build("entity_relation")

        entity_nodes = [n for n in result.nodes if n.type == "entity"]
        relation_edges = [e for e in result.edges if e.type == "relation"]
        # 供应链 Schema 应有 Supplier + Invoice = 2 实体
        # 有 has_invoice = 1 关系
        assert len(entity_nodes) >= 2
        assert len(relation_edges) >= 1

    @pytest.mark.asyncio
    async def test_scenario2_metric_dependency(self, supply_chain_schema):
        """场景二：指标依赖图 - 验证分层和依赖"""
        builder = SchemaGraphBuilder(supply_chain_schema)
        result = builder.build("metric_dependency")

        # 验证指标类型分层
        metric_types = {n.data.get("metric_type") for n in result.nodes if n.type == "metric"}
        assert "atomic" in metric_types
        assert "derived" in metric_types or "composite" in metric_types

        # 验证依赖边存在
        dep_edges = [e for e in result.edges if e.type == "metric_dep"]
        assert len(dep_edges) > 0

    @pytest.mark.asyncio
    async def test_scenario5_what_if(self, supply_chain_schema):
        """场景五：What-if 担保圈模拟 - 验证对比结果"""
        # 需要 mock storage 和 executor
        # 验证 overrides 导致的 diffs
        pass
```

## 二、前端测试 (Vitest)

### 2.1 g6Transformers.test.ts

```typescript
import { transformToG6 } from '../utils/g6Transformers';
import type { SchemaGraphData, GraphNode, GraphEdge } from '../types/visualization';

describe('g6Transformers', () => {
  it('should transform entity nodes correctly', () => {
    const data: SchemaGraphData = {
      schema_id: 'test',
      graph_type: 'entity_relation',
      nodes: [{ id: 'Supplier', type: 'entity', data: { label: '供应商' } }],
      edges: [],
      layout_config: { type: 'force', rankdir: 'LR', nodesep: 50, ranksep: 80 },
      metadata: { entity_count: 1 },
    };
    const g6Data = transformToG6(data);
    expect(g6Data.nodes).toHaveLength(1);
    expect(g6Data.nodes[0].data.style.fill).toBe('#E8F4FD');
    expect(g6Data.nodes[0].data.style.stroke).toBe('#1890FF');
  });

  it('should apply metric type colors', () => {
    const data: SchemaGraphData = {
      schema_id: 'test',
      graph_type: 'metric_dependency',
      nodes: [
        { id: 'm1', type: 'metric', data: { label: 'test', metric_type: 'atomic' } },
        { id: 'm2', type: 'metric', data: { label: 'test', metric_type: 'composite' } },
      ],
      edges: [],
      layout_config: { type: 'dagre', rankdir: 'TB', nodesep: 40, ranksep: 60 },
      metadata: {},
    };
    const g6Data = transformToG6(data);
    expect(g6Data.nodes[0].data.style.fill).toBe('#F6FFED');  // atomic = green
    expect(g6Data.nodes[1].data.style.fill).toBe('#F9F0FF');  // composite = purple
  });
});
```

## 三、验收场景验收标准

| 场景 | 验收命令/操作 | 通过标准 |
|------|--------------|----------|
| **场景1** | `GET /v1/visualize/schema/graph?graph_type=entity_relation` | nodes≥5(完整Schema), edges≥4, 前端G6渲染无重叠 |
| **场景2** | `GET /v1/visualize/schema/graph?graph_type=metric_dependency` | 4类指标分层清晰, 依赖边带权重, credit_score有5条入边 |
| **场景3** | `POST /v1/visualize/simulate {entity_id:"SUP_2024_EXC",dimension:"credit_assessment"}` | execution_path含R001-R007, decision=APPROVE, 评分卡显示92分 |
| **场景4** | `POST /v1/visualize/simulate {entity_id:"SUP_2024_003",dimension:"credit_assessment"}` | R001条件failed, decision=REJECT, condition_details显示具体失败条件 |
| **场景5** | `POST /v1/visualize/simulate {entity_id:"SUP_2024_EXC",overrides:{credit_score:50,guarantee_chain_depth:5}}` | credit_limit↓≥70%, 新增alert, impact_chains非空 |

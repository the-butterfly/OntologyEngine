# 可视化系统详细设计文档

> **模块**: Schema Visualization & Rule Execution Explainability
> **版本**: v3.0（精简版）
> **设计时间**: 2026-04-10 → 2026-04-14（精简重构）
> **代码实现**: [`ontology_engine/visualization/`](../ontology_engine/visualization/)

---

## 0. 代码实现状态

> **[已核对代码]** 以下模块已实现并与代码核验（2026-04-14）。

| 模块 | 文件 | 类 / 方法 | 状态 |
|------|------|-----------|------|
| 可视化服务 | `ontology_engine/services/visualization_service.py` | `VisualizationService` | ✅ |
| Schema 图构建 | `ontology_engine/visualization/builders.py` | `SchemaGraphBuilder` | ✅ |
| 规则链图构建 | `ontology_engine/visualization/builders.py` | `RuleChainGraphBuilder` | ✅ |
| 模拟执行器 | `ontology_engine/visualization/simulator.py` | `RuleChainSimulator` | ✅ |
| 条件解释器 | `ontology_engine/visualization/explainers.py` | `ConditionExplainer` | ✅ |
| 影响分析器 | `ontology_engine/visualization/explainers.py` | `ImpactAnalyzer` | ✅ |
| 数据模型 | `ontology_engine/visualization/models.py` | `SchemaGraphData`, `ExecutionStepSnapshot`, `SimulationResult` 等 | ✅ |
| API 路由 | `ontology_engine/api/routes/visualization.py` | 6 个端点 | ✅ |
| **前端 UI** | `ontology-engine-ui/` | 组件待实现 | ⏳ 进行中 |

---

## 1. 设计目标与原则

| # | 目标 | 度量 |
|---|------|------|
| G1 | **Schema 结构成图**：将 Schema 可视化为可交互的知识图谱 | 加载 ≤ 500ms，100 节点内流畅 |
| G2 | **规则链可视化**：展示规则依赖 DAG、执行路径、输入输出 | 单规则链 ≤ 200ms 渲染 |
| G3 | **执行可解释性**：逐步回放规则执行过程，展示每步的上下文快照 | 步骤间切换 ≤ 50ms |
| G4 | **What-if 模拟**：修改输入变量值，实时观察执行路径和结果变化 | 响应 ≤ 1s |
| G5 | **验收可驱动**：所有可视化场景可通过 examples/ 数据验证 | 覆盖 5 个验收场景 |

**设计原则**：
1. **前后端分离**：后端提供结构化 JSON 图数据，前端负责渲染与交互
2. **数据驱动渲染**：后端不生成 Mermaid/Plotly 字符串，仅输出 G6 兼容的图数据模型
3. **可解释优先**：规则执行的每一步必须有明确的上下文快照
4. **技术栈收敛**：AntV 全家桶（G6 + X6），不引入 graphviz/plotly

---

## 2. 核心数据模型

> 完整定义见 [`ontology_engine/visualization/models.py`](../ontology_engine/visualization/models.py)

### 2.1 SchemaGraphData（Schema 图数据）

```python
@dataclass
class SchemaGraphData:
    schema_id: str
    graph_type: str                       # entity_relation | metric_dependency | full | rule_overview
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    layout_config: LayoutConfig
    metadata: GraphMetadata

@dataclass
class GraphNode:
    id: str
    type: str                              # entity | metric | rule
    data: dict                            # label, layer, metric_type, rule_type, priority

@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    type: str                              # relation | metric_dep | rule_input
    data: dict                            # label, cardinality, weight
```

### 2.2 ExecutionStepSnapshot（执行步骤快照）

```python
@dataclass
class ExecutionStepSnapshot:
    step: int                              # 执行步骤序号
    rule_id: str
    rule_name: str
    rule_type: str                         # constraint | inference | alert | decision

    # 条件求值
    condition_expression: str
    condition_result: bool | None
    condition_details: list[ConditionDetail]  # 子条件逐一求值

    # 上下文快照
    context_before: dict[str, Any]         # 执行前上下文（entity_data + computed_metrics）
    context_after: dict[str, Any]         # 执行后上下文（含本步输出）

    # 输入输出
    inputs: dict[str, Any]
    outputs: dict[str, Any]

    # 状态
    status: Literal["pending", "executing", "passed", "failed", "skipped"]
    duration_ms: float

    # 解释
    explanation: str
    affected_metrics: list[str]

@dataclass
class ConditionDetail:
    expression: str
    resolved: str                          # 变量替换后表达式
    result: bool
    explanation: str
```

### 2.3 SimulationResult（模拟执行结果）

```python
@dataclass
class SimulationResult:
    entity_id: str
    dimension: str
    simulation_type: Literal["dry_run", "what_if"]

    steps: list[ExecutionStepSnapshot]
    execution_path: list[str]             # 实际执行的规则 ID 序列
    skipped_rules: list[str]
    final_outputs: dict[str, Any]

    decision: str | None
    decision_reasoning: str | None
    alerts: list[dict[str, Any]]

    comparison: ComparisonResult | None    # What-if 时对比原始结果

@dataclass
class ComparisonResult:
    baseline: dict[str, Any]               # 原始执行结果
    simulated: dict[str, Any]             # 模拟执行结果
    diffs: list[DiffEntry]                # 差异列表

@dataclass
class DiffEntry:
    field: str
    baseline_value: Any
    simulated_value: Any
    impact: str
```

### 2.4 G6 节点样式映射

```typescript
// 详见 ontology_engine/visualization/builders.py 的 NODE_STYLE_MAP

const NODE_STYLE_MAP = {
  entity:   { type: 'rect',      fill: '#E8F4FD', stroke: '#1890FF' },
  metric:   { type: 'diamond',   fill: (d) => typeColors[d.data.metric_type] },
  rule:     { type: 'rect',      fill: (d) => typeColors[d.data.rule_type] },
};
// 颜色映射：atomic=绿, derived=橙, composite=紫, graph=红
// 规则类型：constraint=红, inference=蓝, alert=橙, decision=绿
```

---

## 3. API 端点

> 完整实现见 [`ontology_engine/api/routes/visualization.py`](../ontology_engine/api/routes/visualization.py)

| 方法 | 端点 | 功能 | 输出 |
|------|------|------|------|
| `GET` | `/v1/visualize/schema/graph` | Schema 图数据（G6 格式） | `SchemaGraphData` |
| `GET` | `/v1/visualize/entities` | 实体列表（用于可视化选择） | `VisualizationEntityOption[]` |
| `GET` | `/v1/visualize/metrics/{entity_id}` | 实体指标快照 | `MetricSnapshot` |
| `GET` | `/v1/visualize/rule-chain/{dimension}` | 规则链 DAG（X6 格式） | `RuleChainGraphData` |
| `POST` | `/v1/visualize/simulate` | 模拟执行（dry_run / what_if） | `SimulationResult` |
| `GET` | `/v1/visualize/execution/{entity_id}/{dimension}` | 历史执行轨迹 | `ExecutionStepSnapshot[]` |

### 请求/响应示例

**GET /v1/visualize/schema/graph?graph_type=entity_relation**

```json
{
  "schema_id": "kg://scf/v2.0",
  "graph_type": "entity_relation",
  "nodes": [
    {"id": "Company", "type": "entity", "data": {"label": "企业", "layer": "L1"}},
    {"id": "credit_score", "type": "metric", "data": {"label": "信用评分", "layer": "L3"}},
    {"id": "R001", "type": "rule", "data": {"label": "基础准入检查", "layer": "L4"}}
  ],
  "edges": [
    {"id": "e1", "source": "credit_score", "target": "R001", "type": "rule_input"}
  ],
  "layout_config": {"type": "dagre", "rankdir": "LR"},
  "metadata": {"entity_count": 5, "relation_count": 4, "metric_count": 10, "rule_count": 7}
}
```

**POST /v1/visualize/simulate**

```json
{
  "entity_id": "COMP001",
  "dimension": "credit_assessment",
  "overrides": {"credit_score": 50},
  "dry_run": false
}
```

---

## 4. 后端模块边界

```
ontology_engine/
├── visualization/
│   ├── builders.py        ✅  SchemaGraphBuilder, RuleChainGraphBuilder
│   ├── simulator.py        ✅  RuleChainSimulator
│   ├── explainers.py       ✅  ConditionExplainer, ImpactAnalyzer
│   └── models.py          ✅  核心数据模型
├── services/
│   └── visualization_service.py  ✅  VisualizationService（聚合层）
└── api/routes/
    └── visualization.py   ✅  6 个端点

不依赖：neo4j / redis / psycopg / graphviz / mermaid
```

**关键约束**：
- `simulator.py` 调用 `RuleExecutor` 但不写入存储（dry_run 模式）
- `builders.py` 只读 Schema 数据，不修改
- API 层只调用 `VisualizationService`，不直接调 engine

---

## 5. 验收场景

基于 `examples/supply_chain_finance/` 数据：

### 场景一：Schema 实体关系图

| 项 | 值 |
|----|-----|
| **输入** | `GET /v1/visualize/schema/graph?graph_type=entity_relation` |
| **预期 nodes** | Company, Invoice, Contract, GuaranteeRelation, CoreEnterprise (5个) |
| **预期 edges** | has_invoice, has_contract, guaranteed_by, supplies_to (4条) |
| **前端验证** | G6 渲染后节点数 = 5，边数 = 4，力导布局无重叠 |

### 场景二：指标依赖图

| 项 | 值 |
|----|-----|
| **输入** | `GET /v1/visualize/schema/graph?graph_type=metric_dependency` |
| **预期节点分层** | L3-atomic → L3-derived → L3-composite → L3-graph |
| **前端验证** | dagre TB 布局，依赖边无环，4 层分层清晰 |

### 场景三：规则链模拟-通过

| 项 | 值 |
|----|-----|
| **输入** | `POST /v1/visualize/simulate { entity_id: "COMP001", dimension: "credit_assessment" }` |
| **预期路径** | R001 → R002 → R003 → R004 → R005 |
| **预期决策** | APPROVE |
| **前端验证** | 回放器全步骤全绿，eligible=true, credit_score≥60 |

### 场景四：规则链模拟-拒绝

| 项 | 值 |
|----|-----|
| **输入** | `POST /v1/visualize/simulate { entity_id: "COMP003", dimension: "credit_assessment" }` |
| **预期** | R001 条件失败 → REJECT |
| **前端验证** | R001 节点红色高亮，解释面板显示具体失败条件 |

### 场景五：What-if 担保圈模拟

| 项 | 值 |
|----|-----|
| **输入** | `POST /v1/visualize/simulate { entity_id: "COMP001", dimension: "credit_assessment", overrides: {"credit_score": 50, "guarantee_chain_depth": 5} }` |
| **预期** | R003 触发预警，额度显著降低 |
| **前端验证** | 对比视图显示 credit_limit 下降 ≥ 70%，新增 alert |

---

## 6. 实施计划

| 阶段 | 目标 | 状态 |
|------|------|------|
| **Phase 1**：基础可视化 | 后端 SchemaGraphBuilder + API，前端 G6 SchemaGraph | ✅ 后端完成 |
| **Phase 2**：规则链 DAG + 回放 | 后端 RuleChainGraphBuilder + RuleChainSimulator，前端 X6 | ✅ 后端完成 |
| **Phase 3**：What-if 模拟 + 对比 | What-if overrides + ComparisonResult，前端 SimulationPanel | ✅ 后端完成 |
| **Phase 4**：前端 UI + 增强 | Playwright 验证，历史轨迹回放，导出功能 | ⏳ 进行中 |

---

## 7. 质量门禁

```bash
# 后端
mypy ontology_engine/visualization/ --strict
ruff check ontology_engine/visualization/
pytest tests/unit/visualization/ -v --cov=ontology_engine.visualization

# 前端
cd ontology-engine-ui
npm run type-check && npm run lint && npm run build
```

---

## 8. 相关文档

| 文档 | 关系 |
|------|------|
| [`09-frontend-architecture.md`](./09-frontend-architecture.md) | 前端架构与页面路由 |
| [`ontology_engine/visualization/models.py`](../ontology_engine/visualization/models.py) | 完整数据模型 |
| [`ontology_engine/visualization/builders.py`](../ontology_engine/visualization/builders.py) | 图构建器实现 |
| [`ontology_engine/visualization/simulator.py`](../ontology_engine/visualization/simulator.py) | 模拟执行器实现 |
| [`ontology_engine/api/routes/visualization.py`](../ontology_engine/api/routes/visualization.py) | API 路由实现 |

# 可视化系统详细设计文档

> **模块**: Schema Visualization & Rule Execution Explainability
> **版本**: v2.0 (重写)
> **设计时间**: 2026-04-10
> **前置文档**: 01-overview, 02-design, 05-schema-v2, alignment/01-02-05-alignment.md

## 一、设计目标与原则

### 1.1 核心目标

| # | 目标 | 度量 |
|---|------|------|
| G1 | **Schema 结构成图**：将 KGML Schema 可视化为可交互的知识图谱 | 加载 ≤ 500ms，100 节点内流畅 |
| G2 | **规则链可视化**：展示规则依赖 DAG、执行路径、输入输出 | 单规则链 ≤ 200ms 渲染 |
| G3 | **执行可解释性**：逐步回放规则执行过程，展示每步的上下文快照 | 步骤间切换 ≤ 50ms |
| G4 | **What-if 模拟**：修改输入变量值，实时观察执行路径和结果变化 | 响应 ≤ 1s |
| G5 | **验收可驱动**：所有可视化场景可通过 examples/ 数据验证 | 覆盖 5 个验收场景 |

### 1.2 设计原则

1. **前后端分离**：后端提供结构化 JSON 图数据，前端负责渲染与交互
2. **数据驱动渲染**：后端不生成 Mermaid/Plotly 字符串，仅输出 G6 兼容的图数据模型
3. **增量交互**：首次加载概览图，按需展开详情（lazy-load）
4. **可解释优先**：规则执行的每一步必须有明确的上下文快照
5. **技术栈收敛**：AntV 全家桶（G6 + X6），不引入 graphviz/plotly

---

## 二、前端技术栈

### 2.1 技术选型

| 层次 | 技术 | 用途 | 版本 |
|------|------|------|------|
| **框架** | React 18+ | UI 框架 | 18.x |
| **构建** | Vite | 开发/构建工具 | 5.x |
| **图可视化** | @antv/g6 | Schema 实体关系图、指标依赖图、担保圈图 | 5.x |
| **DAG 编辑** | @antv/x6 | 规则链 DAG 图（需编辑能力时使用） | 2.x |
| **图表** | @antv/g2 | 指标雷达图、对比柱状图 | 5.x |
| **UI 组件** | Ant Design | 布局、表单、表格、弹窗 | 5.x |
| **状态管理** | Zustand | 全局状态（schema/execution/simulation） | 4.x |
| **请求** | axios / fetch | API 调用 | - |
| **语言** | TypeScript | 全量 TS | 5.x |

### 2.2 选型理由

**G6 vs X6 分工**：

| 场景 | 引擎 | 理由 |
|------|------|------|
| Schema 实体关系图 | G6 | 大规模节点，力导/层次布局，只读分析 |
| 指标依赖图 | G6 | DAG 拓扑，highlight 依赖链 |
| 担保圈/关系网 | G6 | 图算法可视化（cycle detection） |
| 规则链 DAG | X6 | 需要拖拽/编辑节点位置，自定义节点丰富 |
| 执行流程回放 | X6 | 逐步高亮 + 自定义节点内部组件（输入/输出面板） |

### 2.3 前端项目结构

```
ontology-engine-ui/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/                     # API 客户端
│   │   ├── client.ts
│   │   ├── schema.ts
│   │   ├── analysis.ts
│   │   └── visualization.ts
│   ├── stores/                  # Zustand 状态
│   │   ├── schemaStore.ts
│   │   ├── executionStore.ts
│   │   └── simulationStore.ts
│   ├── components/
│   │   ├── layout/              # 页面布局
│   │   │   ├── AppLayout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx
│   │   ├── schema/              # Schema 可视化组件
│   │   │   ├── SchemaGraph.tsx       # G6 实体关系图
│   │   │   ├── MetricDepGraph.tsx    # G6 指标依赖图
│   │   │   ├── SchemaOverview.tsx    # Schema 概览面板
│   │   │   └── EntityDetail.tsx      # 实体详情侧栏
│   │   ├── rule/                # 规则链可视化组件
│   │   │   ├── RuleChainDAG.tsx      # X6 规则 DAG 图
│   │   │   ├── ExecutionReplay.tsx   # 执行回放控制器
│   │   │   ├── StepSnapshot.tsx      # 单步上下文快照
│   │   │   ├── ExecutionTimeline.tsx # 执行时间线
│   │   │   └── AlertPanel.tsx        # 预警面板
│   │   ├── simulation/          # What-if 模拟组件
│   │   │   ├── SimulationPanel.tsx   # 模拟输入面板
│   │   │   ├── VariableOverride.tsx  # 变量覆盖编辑器
│   │   │   ├── ComparisonView.tsx    # 原始 vs 模拟对比
│   │   │   └── ImpactAnalysis.tsx    # 影响分析图
│   │   └── common/              # 通用组件
│   │       ├── G6Container.tsx
│   │       ├── X6Container.tsx
│   │       ├── JsonViewer.tsx
│   │       └── StatusBadge.tsx
│   ├── pages/
│   │   ├── SchemaPage.tsx
│   │   ├── RuleChainPage.tsx
│   │   └── SimulationPage.tsx
│   ├── utils/
│   │   ├── g6Transformers.ts    # KGML → G6 数据转换
│   │   ├── x6Transformers.ts    # Rule → X6 数据转换
│   │   └── formatters.ts
│   └── types/
│       ├── schema.ts            # Schema 相关类型
│       ├── rule.ts              # Rule 相关类型
│       └── visualization.ts     # 可视化 API 响应类型
```

---

## 三、Schema 可视化详细设计

### 3.1 数据模型（后端 API → 前端 G6）

#### 3.1.1 后端 API 响应格式

**GET /v1/visualize/schema/graph**

```json
{
  "code": 0,
  "data": {
    "schema_id": "kg://supply-chain/finance/credit-assessment/1.0",
    "graph_type": "entity_relation",
    "nodes": [
      {
        "id": "Company",
        "type": "entity",
        "data": {
          "label": "企业",
          "layer": "L1",
          "attribute_count": 12,
          "key_attributes": ["uscc", "name", "registered_capital", "status"],
          "description": "供应链企业实体"
        }
      },
      {
        "id": "Invoice",
        "type": "entity",
        "data": {
          "label": "发票",
          "layer": "L1",
          "attribute_count": 7,
          "key_attributes": ["invoice_no", "amount", "status"]
        }
      },
      {
        "id": "credit_score",
        "type": "metric",
        "data": {
          "label": "信用评分",
          "layer": "L3",
          "metric_type": "composite",
          "formula": "business_stability_score*0.30 + ...",
          "dependencies": ["business_stability_score", "reputation_score"]
        }
      },
      {
        "id": "R001",
        "type": "rule",
        "data": {
          "label": "基础准入检查",
          "layer": "L4",
          "rule_type": "constraint",
          "priority": 100
        }
      }
    ],
    "edges": [
      {
        "id": "e1",
        "source": "Company",
        "target": "Invoice",
        "type": "relation",
        "data": {
          "label": "has_invoice",
          "cardinality": "0..*"
        }
      },
      {
        "id": "e2",
        "source": "business_stability_score",
        "target": "credit_score",
        "type": "metric_dep",
        "data": {
          "weight": 0.30
        }
      },
      {
        "id": "e3",
        "source": "credit_score",
        "target": "R001",
        "type": "rule_input",
        "data": {}
      }
    ],
    "layout_config": {
      "type": "dagre",
      "rankdir": "LR",
      "nodesep": 50,
      "ranksep": 80
    },
    "metadata": {
      "entity_count": 5,
      "relation_count": 4,
      "metric_count": 10,
      "rule_count": 7
    }
  }
}
```

#### 3.1.2 前端 G6 节点样式映射

```typescript
// g6Transformers.ts - KGML → G6 数据转换

const NODE_STYLE_MAP: Record<string, G6NodeStyle> = {
  entity: {
    type: 'rect',
    style: {
      size: [120, 50],
      fill: '#E8F4FD',
      stroke: '#1890FF',
      radius: 8,
      labelText: (d) => d.data.label,
      labelFill: '#333',
      iconSrc: '/icons/entity.svg',
    },
    state: {
      hover: { stroke: '#40A9FF', lineWidth: 2 },
      selected: { stroke: '#096DD9', lineWidth: 3, shadowColor: '#1890FF', shadowBlur: 10 },
    },
  },
  metric: {
    type: 'diamond',
    style: {
      size: 40,
      fill: (d) => {
        const typeColors: Record<string, string> = {
          atomic: '#F6FFED',   // 绿色 - 原子指标
          derived: '#FFF7E6',  // 橙色 - 派生指标
          composite: '#F9F0FF', // 紫色 - 复合指标
          graph: '#FFF1F0',    // 红色 - 图指标
        };
        return typeColors[d.data.metric_type] || '#F0F0F0';
      },
      stroke: (d) => {
        const typeColors: Record<string, string> = {
          atomic: '#52C41A', derived: '#FA8C16', composite: '#722ED1', graph: '#F5222D',
        };
        return typeColors[d.data.metric_type] || '#D9D9D9';
      },
      labelText: (d) => d.data.label,
    },
  },
  rule: {
    type: 'rect',
    style: {
      size: [140, 60],
      fill: (d) => {
        const typeColors: Record<string, string> = {
          constraint: '#FFF1F0',  // 红色 - 约束
          inference: '#E6F7FF',  // 蓝色 - 推理
          alert: '#FFF7E6',     // 橙色 - 预警
          decision: '#F6FFED',  // 绿色 - 决策
        };
        return typeColors[d.data.rule_type] || '#F0F0F0';
      },
      stroke: (d) => {
        const typeColors: Record<string, string> = {
          constraint: '#F5222D', inference: '#1890FF', alert: '#FA8C16', decision: '#52C41A',
        };
        return typeColors[d.data.rule_type] || '#D9D9D9';
      },
      radius: 4,
      labelText: (d) => `${d.id}: ${d.data.label}`,
    },
  },
};

const EDGE_STYLE_MAP: Record<string, G6EdgeStyle> = {
  relation: {
    type: 'quadratic',
    style: { stroke: '#A0A0A0', lineWidth: 1.5, endArrow: true, labelText: (d) => d.data.label },
  },
  metric_dep: {
    type: 'line',
    style: { stroke: '#722ED1', lineWidth: 1, lineDash: [4, 4], endArrow: true },
  },
  rule_input: {
    type: 'line',
    style: { stroke: '#1890FF', lineWidth: 1, lineDash: [2, 2], endArrow: true },
  },
};
```

### 3.2 Schema 可视化交互设计

#### 3.2.1 视图切换

| 视图 | 布局 | 展示内容 | 触发方式 |
|------|------|----------|----------|
| **实体关系图** | force / dagre LR | L1 实体 + 关系边 | 默认视图 |
| **指标依赖图** | dagre TB | L3 指标 + 依赖边（按层级分层） | 切换 Tab |
| **四层全图** | dagre LR | L1-L4 全部节点 | 切换 Tab |
| **规则概览** | dagre TB | L4 规则 + 依赖 + 类型着色 | 切换 Tab |

#### 3.2.2 交互行为

| 交互 | 行为 | 实现方式 |
|------|------|----------|
| **节点点击** | 右侧面板展示详情（属性列表/公式/条件） | G6 `node:click` 事件 → 更新 Zustand store |
| **节点悬停** | 高亮该节点及其直接依赖/被依赖 | G6 `node:mouseenter` → `setState('hover')` |
| **边悬停** | 展示边标签 tooltip（基数/权重/条件） | G6 `edge:mouseenter` → Tooltip 插件 |
| **框选** | 多选节点，批量高亮依赖链 | G6 BrushSelect 插件 |
| **缩放/平移** | 常规图操作 | G6 Zoom/Scroll 插件 |
| **搜索** | 输入节点名 → 定位并高亮 | 自定义搜索框 → `graph.focusElement(id)` |
| **分层过滤** | 勾选 L1/L2/L3/L4 显隐 | 过滤 nodes 数组 → `graph.setData()` |
| **导出** | 导出 PNG/SVG | G6 `graph.toDataURL()` / `graph.toFullDataURL()` |

### 3.3 后端 API 实现

#### 3.3.1 新增模块：VisualizationService

```python
# ontology_engine/services/visualization_service.py

class VisualizationService:
    """可视化数据服务 - 将 KGML Schema 转换为图数据模型"""

    def __init__(
        self,
        schema_service: SchemaService,
        analysis_service: AnalysisService,
    ):
        self.schema_service = schema_service
        self.analysis_service = analysis_service

    async def get_schema_graph(
        self,
        graph_type: Literal["entity_relation", "metric_dependency", "full", "rule_overview"],
        layer_filter: list[str] | None = None,
    ) -> SchemaGraphData:
        """
        生成 Schema 图数据（G6 兼容格式）

        不渲染图形，仅输出结构化数据供前端消费。
        """
        schema = await self.schema_service.get_schema()
        if not schema:
            raise SchemaNotLoadedError()

        builder = SchemaGraphBuilder(schema)
        return builder.build(graph_type, layer_filter)

    async def get_rule_chain_graph(
        self,
        dimension: str,
    ) -> RuleChainGraphData:
        """
        生成规则链 DAG 图数据（X6 兼容格式）

        展示规则依赖、优先级、类型。
        """
        schema = await self.schema_service.get_schema()
        if not schema:
            raise SchemaNotLoadedError()

        builder = RuleChainGraphBuilder(schema)
        return builder.build(dimension)

    async def simulate_execution(
        self,
        entity_id: str,
        dimension: str,
        overrides: dict[str, Any] | None = None,
        dry_run: bool = True,
    ) -> SimulationResult:
        """
        模拟执行规则链，返回逐步执行快照

        每步包含：
        - 规则 ID / 名称
        - 条件表达式及求值结果
        - 输入上下文快照
        - 输出结果
        - 执行状态
        - 执行耗时
        """
        ...
```

#### 3.3.2 图数据构建器

```python
# ontology_engine/visualization/builders.py

class SchemaGraphBuilder:
    """KGML Schema → G6 图数据"""

    def __init__(self, schema: KGMLSchema):
        self.schema = schema

    def build(
        self,
        graph_type: str,
        layer_filter: list[str] | None = None,
    ) -> SchemaGraphData:
        nodes = []
        edges = []

        # L1: 事实对象 → 实体节点
        if not layer_filter or "L1" in layer_filter:
            for concept in self.schema.concepts:
                nodes.append(self._build_entity_node(concept))
                for rel in concept.relations:
                    edges.append(self._build_relation_edge(concept.name, rel))

        # L3: 分析指标 → 指标节点
        if not layer_filter or "L3" in layer_filter:
            for metric in self.schema.metrics:
                nodes.append(self._build_metric_node(metric))
                for dep in metric.dependencies:
                    edges.append(self._build_metric_dep_edge(dep, metric.name))

        # L4: 业务规则 → 规则节点
        if not layer_filter or "L4" in layer_filter:
            if self.schema.rules:
                for rule in self.schema.rules.ruleset:
                    nodes.append(self._build_rule_node(rule))

        # 跨层依赖边（指标→规则）
        if layer_filter is None or "L3" in layer_filter or "L4" in layer_filter:
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

---

## 四、规则链可视化与执行可解释性

### 4.1 规则链 DAG 图（X6）

#### 4.1.1 X6 自定义节点设计

```typescript
// RuleNode - 规则节点自定义组件

interface RuleNodeData {
  ruleId: string;
  ruleName: string;
  ruleType: 'constraint' | 'inference' | 'alert' | 'decision';
  priority: number;
  condition: string;       // when 表达式
  action: string;          // then action 类型
  enabled: boolean;
  // 执行状态（模拟/回放时填充）
  executionStatus?: 'pending' | 'executing' | 'passed' | 'failed' | 'skipped';
  executionDuration?: number;
  conditionResult?: boolean;
  inputs?: Record<string, any>;
  outputs?: Record<string, any>;
}
```

**X6 自定义节点视觉设计**：

```
┌──────────────────────────────────────────┐
│  ⬤ R001: 基础准入检查          [constraint] │  ← 标题栏（类型着色）
├──────────────────────────────────────────┤
│  Priority: 100  |  Status: ✓ PASSED       │  ← 状态栏
├──────────────────────────────────────────┤
│  WHEN: status == 'ACTIVE' AND            │  ← 条件预览
│        registered_capital >= 1000000      │
├──────────────────────────────────────────┤
│  THEN: approve_eligibility               │  ← 动作预览
│  → eligible: true                        │
├──────────────────────────────────────────┤
│  ⏱ 2.3ms                                │  ← 耗时
└──────────────────────────────────────────┘
```

#### 4.1.2 后端规则链图数据

**GET /v1/visualize/rule-chain/{dimension}**

```json
{
  "code": 0,
  "data": {
    "dimension": "credit_assessment",
    "nodes": [
      {
        "id": "R001",
        "position": { "x": 100, "y": 100 },
        "data": {
          "ruleId": "R001",
          "ruleName": "基础准入检查",
          "ruleType": "constraint",
          "priority": 100,
          "condition": "status == 'ACTIVE' AND registered_capital.value >= 1000000 AND establishment_date IS NOT NULL",
          "action": "approve_eligibility",
          "enabled": true
        }
      }
    ],
    "edges": [
      {
        "id": "R001-R002",
        "source": "R001",
        "target": "R002",
        "data": {
          "dependency_type": "data_flow",
          "description": "R001 通过后 → 执行信用评分计算"
        }
      }
    ],
    "dimension_info": {
      "name": "credit_assessment",
      "description": "供应商信用评估维度",
      "applicable_entities": ["Supplier"],
      "rule_count": 7
    }
  }
}
```

### 4.2 执行可解释性设计

#### 4.2.1 执行快照模型

```python
# ontology_engine/visualization/models.py

@dataclass
class ExecutionStepSnapshot:
    """规则执行的完整快照 - 可解释性核心数据结构"""

    step: int                              # 执行步骤序号
    rule_id: str                           # 规则 ID
    rule_name: str                         # 规则名称
    rule_type: str                         # constraint/inference/alert/decision

    # 条件求值
    condition_expression: str              # 原始条件表达式
    condition_result: bool | None          # 条件求值结果
    condition_details: list[ConditionDetail]  # 子条件逐一求值结果

    # 上下文快照
    context_before: dict[str, Any]         # 执行前的上下文（entity_data + computed_metrics）
    context_after: dict[str, Any]          # 执行后的上下文（含本步输出）

    # 输入输出
    inputs: dict[str, Any]                 # 本步实际输入
    outputs: dict[str, Any]                # 本步实际输出

    # 状态
    status: Literal["pending", "executing", "passed", "failed", "skipped"]
    duration_ms: float                     # 执行耗时

    # 解释
    explanation: str                       # 自然语言解释
    affected_metrics: list[str]            # 本步影响的指标名


@dataclass
class ConditionDetail:
    """子条件求值详情"""
    expression: str                        # 子条件表达式
    resolved: str                          # 变量替换后的表达式
    result: bool                           # 求值结果
    explanation: str                       # 解释文本


@dataclass
class SimulationResult:
    """模拟执行结果"""
    entity_id: str
    dimension: str
    simulation_type: Literal["dry_run", "what_if"]

    steps: list[ExecutionStepSnapshot]     # 逐步快照
    execution_path: list[str]              # 实际执行的规则 ID 序列
    skipped_rules: list[str]               # 跳过的规则 ID
    final_outputs: dict[str, Any]          # 最终输出

    # 决策结果
    decision: str | None
    decision_reasoning: str | None
    alerts: list[dict[str, Any]]

    # 对比（What-if 时使用）
    comparison: ComparisonResult | None


@dataclass
class ComparisonResult:
    """原始 vs 模拟 对比"""
    baseline: dict[str, Any]               # 原始执行结果
    simulated: dict[str, Any]              # 模拟执行结果
    diffs: list[DiffEntry]                 # 差异列表


@dataclass
class DiffEntry:
    """单项差异"""
    field: str                             # 字段名
    baseline_value: Any                    # 原始值
    simulated_value: Any                   # 模拟值
    impact: str                            # 影响描述
```

#### 4.2.2 模拟执行引擎

```python
# ontology_engine/visualization/simulator.py

class RuleChainSimulator:
    """规则链模拟执行器

    核心能力：
    1. dry_run 模式：不写存储，仅追踪执行路径
    2. what_if 模式：覆盖变量值，对比执行差异
    3. 逐步快照：记录每步的完整上下文
    4. 可解释性：生成自然语言解释
    """

    def __init__(
        self,
        rule_executor: RuleExecutor,
        metric_engine: MetricEngine,
        storage: DuckDBStorage,
    ):
        self.rule_executor = rule_executor
        self.metric_engine = metric_engine
        self.storage = storage

    async def simulate(
        self,
        entity_id: str,
        dimension: str,
        overrides: dict[str, Any] | None = None,
        dry_run: bool = True,
    ) -> SimulationResult:
        """
        执行模拟

        实现方式：
        1. 获取实体数据
        2. 如有 overrides，合并到 entity_data
        3. 如需基线对比，先执行一次原始模拟
        4. 逐步执行规则，每步记录 ExecutionStepSnapshot
        5. 不写入存储（dry_run 模式）
        """
        # 1. 获取实体
        entity = await self._find_entity(entity_id)
        entity_data = dict(entity.data)
        entity_data["_concept"] = entity.concept

        # 2. 基线执行（用于 What-if 对比）
        baseline_result = None
        if overrides:
            baseline_result = await self._execute_with_snapshots(
                entity_id, dimension, dict(entity_data)
            )

        # 3. 应用覆盖值
        if overrides:
            self._apply_overrides(entity_data, overrides)

        # 4. 带快照的执行
        simulation = await self._execute_with_snapshots(
            entity_id, dimension, entity_data
        )

        # 5. 构建对比
        comparison = None
        if baseline_result and overrides:
            comparison = self._build_comparison(baseline_result, simulation)

        simulation.comparison = comparison
        simulation.simulation_type = "what_if" if overrides else "dry_run"

        return simulation

    async def _execute_with_snapshots(
        self,
        entity_id: str,
        dimension: str,
        entity_data: dict[str, Any],
    ) -> SimulationResult:
        """带逐步快照的规则执行"""

        schema = self.rule_executor.schema
        rules = schema.get_rules_for_dimension(dimension) if schema.rules else []
        rules = sorted(rules, key=lambda r: -r.priority)

        snapshots: list[ExecutionStepSnapshot] = []
        execution_path: list[str] = []
        skipped: list[str] = []

        # 初始化执行上下文
        context = ExecutionContext(
            entity_id=entity_id,
            dimension=dimension,
            entity_data=entity_data,
        )

        for step_idx, rule in enumerate(rules):
            if not rule.enabled:
                skipped.append(rule.id)
                continue

            step_snapshot = await self._execute_rule_with_snapshot(
                step_idx + 1, rule, context
            )
            snapshots.append(step_snapshot)

            if step_snapshot.status in ("passed", "failed"):
                execution_path.append(rule.id)
            elif step_snapshot.status == "skipped":
                skipped.append(rule.id)

        return SimulationResult(
            entity_id=entity_id,
            dimension=dimension,
            simulation_type="dry_run",
            steps=snapshots,
            execution_path=execution_path,
            skipped_rules=skipped,
            final_outputs=dict(context.computed_metrics),
            decision=self._determine_decision(context),
            decision_reasoning=self._generate_reasoning(context),
            alerts=[{"level": a.level, "type": a.type, "message": a.message} for a in context.alerts],
            comparison=None,
        )

    async def _execute_rule_with_snapshot(
        self,
        step: int,
        rule: RuleDefinition,
        context: ExecutionContext,
    ) -> ExecutionStepSnapshot:
        """执行单条规则并记录快照"""

        context_before = self._snapshot_context(context)

        # 求值条件
        condition_result = None
        condition_details = []
        if rule.when:
            eval_context = self.rule_executor._get_eval_context(context)
            condition_result = self.rule_executor.evaluator.evaluate(
                rule.when, eval_context
            )
            condition_details = self._explain_condition(rule.when, eval_context)

        # 执行规则
        start_time = time.monotonic()
        rule_result = await self.rule_executor.execute_rule(rule, context)
        duration_ms = (time.monotonic() - start_time) * 1000

        context_after = self._snapshot_context(context)

        # 生成解释
        explanation = self._generate_step_explanation(
            rule, condition_result, rule_result
        )

        return ExecutionStepSnapshot(
            step=step,
            rule_id=rule.id,
            rule_name=rule.name or "",
            rule_type=rule.type,
            condition_expression=self._serialize_condition(rule.when),
            condition_result=condition_result,
            condition_details=condition_details,
            context_before=context_before,
            context_after=context_after,
            inputs=self._extract_inputs(rule, context_before),
            outputs=rule_result.output,
            status="passed" if rule_result.passed else "failed",
            duration_ms=duration_ms,
            explanation=explanation,
            affected_metrics=list(rule_result.output.keys()),
        )

    def _explain_condition(
        self,
        when: RuleWhen,
        eval_context: dict,
    ) -> list[ConditionDetail]:
        """
        将条件表达式拆解为子条件并逐一解释

        例：status == 'ACTIVE' AND capital >= 1000000
        → [
            { expression: "status == 'ACTIVE'", resolved: "'ACTIVE' == 'ACTIVE'", result: true, explanation: "企业状态为活跃" },
            { expression: "capital >= 1000000", resolved: "100000000 >= 1000000", result: true, explanation: "注册资本满足最低要求" }
          ]
        """
        ...
```

### 4.3 执行回放交互设计

#### 4.3.1 回放控制器

```
┌─────────────────────────────────────────────────────────────────┐
│  执行回放    ◀◀  ◀  ▶  ▶▶  ⏸   Step 3/7   2.3ms              │
│  ───────────●─────────────────────────────────────              │
│  1    2    3    4    5    6    7                                 │
│  ✓    ✓   ▶●    ○    ○    ○    ○                                │
│  R001 R002 R003 R004 R005 R006 R007                            │
└─────────────────────────────────────────────────────────────────┘
```

| 操作 | 行为 |
|------|------|
| ▶ Play | 自动逐步执行，每步停留 800ms |
| ⏸ Pause | 暂停自动播放 |
| ◀ Step Back | 回退一步，恢复上一快照 |
| ▶ Step Forward | 前进一步 |
| ◀◀ Reset | 回到初始状态 |
| ▶▶ Skip to End | 直接跳到最终结果 |
| 点击时间线节点 | 跳转到指定步骤 |

#### 4.3.2 步骤快照面板

当用户选择某个步骤时，右侧面板展示：

```
┌─────────────────────────────────────┐
│  Step 3: R003 担保圈检测            │
│  Type: alert  |  Priority: 95       │
├─────────────────────────────────────┤
│  📋 条件求值                         │
│  ┌─────────────────────────────────┐│
│  │ guarantee_chain_depth >= 3      ││
│  │ → 1 >= 3  → false              ││
│  │ ✗ 未触发担保圈预警              ││
│  └─────────────────────────────────┘│
├─────────────────────────────────────┤
│  📥 输入                            │
│  guarantee_chain_depth: 1           │
│  has_guarantee_circle: false        │
├─────────────────────────────────────┤
│  📤 输出                            │
│  guarantee_chain_depth: 1           │
│  (无变更)                           │
├─────────────────────────────────────┤
│  💡 解释                            │
│  该供应商担保链深度为 1，             │
│  未达到预警阈值 3，不触发担保圈预警。 │
├─────────────────────────────────────┤
│  ⏱ 1.2ms                           │
└─────────────────────────────────────┘
```

### 4.4 What-if 模拟交互设计

#### 4.4.1 变量覆盖编辑器

```
┌─────────────────────────────────────────────┐
│  What-if 模拟                               │
├─────────────────────────────────────────────┤
│  实体: SUP_2024_EXC                         │
│  维度: credit_assessment                     │
├─────────────────────────────────────────────┤
│  变量覆盖:                                   │
│  ┌───────────────────┬─────────────────────┐│
│  │ credit_score      │ [50        ]  ✏️     ││
│  │ (原始值: 92)      │                     ││
│  ├───────────────────┼─────────────────────┤│
│  │ guarantee_chain_  │ [5         ]  ✏️     ││
│  │ depth (原始值: 1) │                     ││
│  ├───────────────────┼─────────────────────┤│
│  │ + 添加变量         │                     ││
│  └───────────────────┴─────────────────────┘│
│                                              │
│  [▶ 运行模拟]  [↺ 重置]                     │
└─────────────────────────────────────────────┘
```

#### 4.4.2 对比视图

```
┌──────────────────────────────────────────────────────┐
│  对比分析: 原始 vs 模拟                               │
├────────────────┬──────────┬──────────┬───────────────┤
│  指标           │ 原始值    │ 模拟值    │ 变化          │
├────────────────┼──────────┼──────────┼───────────────┤
│  credit_score  │ 92       │ 50       │ ↓ 45.7% 🔴    │
│  credit_grade  │ AA       │ B        │ ↓ 3级 🔴      │
│  credit_limit  │ 1.8亿    │ 4000万   │ ↓ 77.8% 🔴    │
│  decision      │ APPROVE  │ APPROVE_ │ ↓ 降级 🟡     │
│                │          │ RESTRICT │               │
│  alerts        │ 无       │ 担保圈预警 │ 🔴 新增      │
├────────────────┴──────────┴──────────┴───────────────┤
│  影响路径:                                            │
│  credit_score ↓ → credit_grade ↓ → credit_limit ↓    │
│  guarantee_chain_depth ↑ → alert 触发                 │
└──────────────────────────────────────────────────────┘
```

---

## 五、API 端点设计

### 5.1 新增端点

```python
# ontology_engine/api/routes/visualization.py

router = APIRouter(prefix="/v1/visualize", tags=["visualization"])


# ========== Schema 可视化 ==========

@router.get("/schema/graph")
async def get_schema_graph(
    graph_type: str = "entity_relation",   # entity_relation | metric_dependency | full | rule_overview
    layer_filter: str | None = None,        # 逗号分隔: "L1,L3"
    service: VisualizationService = Depends(get_visualization_service),
):
    """
    获取 Schema 图数据（G6 格式）

    返回 nodes + edges 结构化数据，前端负责渲染。
    """


# ========== 规则链可视化 ==========

@router.get("/rule-chain/{dimension}")
async def get_rule_chain_graph(
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """
    获取规则链 DAG 图数据（X6 格式）

    包含规则节点、依赖边、优先级信息。
    """


# ========== 模拟执行 ==========

class SimulationRequest(BaseModel):
    entity_id: str
    dimension: str
    overrides: dict[str, Any] | None = None
    dry_run: bool = True


@router.post("/simulate")
async def simulate_execution(
    request: SimulationRequest,
    service: VisualizationService = Depends(get_visualization_service),
):
    """
    模拟执行规则链

    返回逐步 ExecutionStepSnapshot，支持：
    - dry_run: 不写存储
    - overrides: What-if 变量覆盖
    """


# ========== 执行回放 ==========

@router.get("/execution/{entity_id}/{dimension}")
async def get_execution_trace(
    entity_id: str,
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """
    获取历史执行轨迹

    从 rule_execution_log 表读取历史执行记录，
    重建 ExecutionStepSnapshot 序列。
    """
```

### 5.2 API 端点汇总

| 方法 | 端点 | 功能 | 输出格式 |
|------|------|------|----------|
| GET | /v1/visualize/schema/graph | Schema 图数据 | G6 nodes/edges |
| GET | /v1/visualize/rule-chain/{dim} | 规则链 DAG | X6 nodes/edges |
| POST | /v1/visualize/simulate | 模拟执行 | ExecutionStepSnapshot[] |
| GET | /v1/visualize/execution/{eid}/{dim} | 历史执行轨迹 | ExecutionStepSnapshot[] |

---

## 六、后端模块设计

### 6.1 目录结构

```
ontology_engine/
├── visualization/                    # 新增模块
│   ├── __init__.py
│   ├── builders.py                   # 图数据构建器
│   │   ├── SchemaGraphBuilder        # KGML → G6 格式
│   │   └── RuleChainGraphBuilder     # Rules → X6 格式
│   ├── simulator.py                  # 模拟执行引擎
│   │   └── RuleChainSimulator
│   ├── explainers.py                 # 可解释性引擎
│   │   ├── ConditionExplainer        # 条件表达式拆解
│   │   └── ImpactAnalyzer            # 影响链分析
│   └── models.py                     # 可视化数据模型
│       ├── SchemaGraphData
│       ├── RuleChainGraphData
│       ├── ExecutionStepSnapshot
│       ├── SimulationResult
│       └── ComparisonResult
├── services/
│   └── visualization_service.py      # 新增服务
└── api/routes/
    └── visualization.py              # 新增路由
```

### 6.2 边界与依赖

```
┌────────────────────────────────────────────────────────────┐
│                   Visualization Module                      │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    依赖 (下游)     ┌───────────────┐     │
│  │ builders.py  │ ←──────────────── │ SchemaService │     │
│  │ simulator.py │ ←──────────────── │ RuleExecutor  │     │
│  │ explainers.py│ ←──────────────── │ MetricEngine  │     │
│  └──────────────┘                   │ DuckDBStorage │     │
│       │                              └───────────────┘     │
│       ▼                                                     │
│  ┌─────────────────────┐                                   │
│  │ VisualizationService│ ←── api/routes/visualization.py  │
│  └─────────────────────┘                                   │
│                                                             │
│  不依赖:                                                    │
│  - neo4j / redis / psycopg                                 │
│  - networkx (仅 MetricDAG 内部使用，不直接依赖)              │
│  - graphviz / plotly / mermaid                             │
│                                                             │
│  关键约束:                                                  │
│  - simulator.py 调用 RuleExecutor 但不写入存储               │
│  - builders.py 只读 Schema 数据，不修改                      │
│  - API 层只调用 VisualizationService，不直接调 engine        │
└────────────────────────────────────────────────────────────┘
```

### 6.3 与存量模块的交互方式

| 交互 | 方式 | 说明 |
|------|------|------|
| 获取 Schema | `SchemaService.get_schema()` | 只读 |
| 执行规则 | `RuleExecutor.execute_rule()` | 直接调用，但在模拟上下文中 |
| 计算指标 | `MetricEngine.compute_batch()` | What-if 时需要重算 |
| 获取实体 | `DuckDBStorage.get_entity()` | 通过 AnalysisService._find_entity |
| 记录日志 | `DuckDBStorage.log_rule_execution()` | 仅非 dry_run 时 |

---

## 七、验收场景设计

基于 `examples/supply_chain_finance/` 数据：

### 7.1 场景一：Schema 实体关系图

| 项 | 值 |
|----|-----|
| **输入** | GET /v1/visualize/schema/graph?graph_type=entity_relation |
| **预期 nodes** | Company, Invoice, Contract, GuaranteeRelation, CoreEnterprise (5个) |
| **预期 edges** | has_invoice, has_contract, guaranteed_by, supplies_to (4条) |
| **前端验证** | G6 渲染后节点数 = 5，边数 = 4，力导布局无重叠 |

### 7.2 场景二：指标依赖图

| 项 | 值 |
|----|-----|
| **输入** | GET /v1/visualize/schema/graph?graph_type=metric_dependency |
| **预期节点分层** | L3-atomic: total_invoice_amount_90d, overdue_invoice_amount... |
| | L3-derived: overdue_invoice_ratio, avg_invoice_amount... |
| | L3-composite: business_stability_score, credit_score... |
| | L3-graph: guarantee_chain_depth |
| **前端验证** | dagre TB 布局，4 层分层清晰，依赖边无环 |

### 7.3 场景三：规则链模拟-通过

| 项 | 值 |
|----|-----|
| **输入** | POST /v1/visualize/simulate { entity_id: "SUP_2024_EXC", dimension: "credit_assessment" } |
| **预期路径** | R001 → R002 → R003 → R004 → R005 → R007 |
| **预期决策** | APPROVE |
| **前端验证** | 回放器 7 步全绿，最终输出 eligible=true, credit_score≥80 |

### 7.4 场景四：规则链模拟-拒绝

| 项 | 值 |
|----|-----|
| **输入** | POST /v1/visualize/simulate { entity_id: "SUP_2024_003", dimension: "credit_assessment" } |
| **预期** | R001 条件失败 → REJECT |
| **前端验证** | R001 节点红色高亮，解释面板显示具体失败条件 |

### 7.5 场景五：What-if 担保圈模拟

| 项 | 值 |
|----|-----|
| **输入** | POST /v1/visualize/simulate { entity_id: "SUP_2024_EXC", dimension: "credit_assessment", overrides: {"credit_score": 50, "guarantee_chain_depth": 5} } |
| **预期** | R003 触发预警，额度显著降低 |
| **前端验证** | 对比视图显示 credit_limit 下降 ≥ 70%，新增 alert |

---

## 八、实施计划

### Phase 1：基础可视化（2 周）

- [ ] 后端：SchemaGraphBuilder + API
- [ ] 前端：React 项目搭建 + G6 SchemaGraph 组件
- [ ] 验收：场景一、场景二

### Phase 2：规则链 DAG + 回放（2 周）

- [ ] 后端：RuleChainGraphBuilder + RuleChainSimulator（dry_run）
- [ ] 前端：X6 RuleChainDAG + ExecutionReplay
- [ ] 验收：场景三、场景四

### Phase 3：What-if 模拟 + 对比（2 周）

- [ ] 后端：What-if overrides + ComparisonResult
- [ ] 前端：SimulationPanel + ComparisonView
- [ ] 验收：场景五

### Phase 4：增强功能（1 周）

- [ ] 历史执行轨迹回放
- [ ] 导出功能（PNG/SVG/PDF）
- [ ] 搜索与过滤增强
- [ ] 性能优化（大图虚拟滚动）

---

## 九、质量门禁

### 9.1 后端

```bash
mypy ontology_engine/visualization/ --strict
ruff check ontology_engine/visualization/
pytest tests/unit/visualization/ -v --cov=ontology_engine.visualization
```

### 9.2 前端

```bash
cd ontology-engine-ui
npm run type-check     # TypeScript 类型检查
npm run lint           # ESLint
npm run test           # Vitest 单元测试
npm run build          # 生产构建验证
```

### 9.3 测试覆盖

| 模块 | 测试文件 | 覆盖目标 |
|------|----------|----------|
| SchemaGraphBuilder | test_schema_graph_builder.py | 4 种 graph_type 输出 |
| RuleChainGraphBuilder | test_rule_chain_builder.py | DAG 结构 + 依赖边 |
| RuleChainSimulator | test_simulator.py | 5 个验收场景 |
| ConditionExplainer | test_explainer.py | 条件拆解 + 解释生成 |
| VisualizationService | test_visualization_service.py | 端到端集成 |

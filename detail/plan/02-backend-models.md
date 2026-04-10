# 后端模块详细设计 - models.py

> **文件**: `ontology_engine/visualization/models.py`
> **职责**: 可视化数据模型定义，所有可视化API的输入输出数据结构

## 一、数据模型总览

```
SchemaGraphData          # Schema图数据 (G6格式)
  ├── GraphNode[]        # 节点列表
  ├── GraphEdge[]        # 边列表
  ├── LayoutConfig       # 布局配置
  └── GraphMetadata      # 图元数据

RuleChainGraphData       # 规则链DAG数据 (X6格式)
  ├── RuleChainNode[]    # 规则节点
  ├── RuleChainEdge[]    # 依赖边
  └── DimensionInfo      # 维度信息

ExecutionStepSnapshot    # 执行步骤快照 (可解释性核心)
  ├── ConditionDetail[]  # 条件拆解
  ├── context_before     # 执行前上下文
  ├── context_after      # 执行后上下文
  └── explanation        # 自然语言解释

SimulationResult         # 模拟执行结果
  ├── ExecutionStepSnapshot[]
  ├── execution_path     # 实际执行路径
  ├── skipped_rules      # 跳过的规则
  ├── ComparisonResult?  # What-if对比
  └── decision/alerts

ComparisonResult         # 原始vs模拟对比
  ├── baseline
  ├── simulated
  ├── DiffEntry[]        # 差异条目
  └── impact_chains      # 影响路径
```

## 二、模型定义

### 2.1 Schema 图数据模型

```python
@dataclass
class GraphNode:
    """G6 兼容的图节点"""
    id: str                              # 节点ID (概念名/指标名/规则ID)
    type: str                            # 节点类型: entity | metric | rule
    data: dict[str, Any]                 # 节点数据
    # data 内容根据 type 不同:
    # entity: { label, layer="L1", attribute_count, key_attributes, description }
    # metric: { label, layer="L3", metric_type, formula, dependencies, weight? }
    # rule: { label, layer="L4", rule_type, priority, condition_preview, action_preview }

@dataclass
class GraphEdge:
    """G6 兼容的图边"""
    id: str                              # 边ID
    source: str                          # 源节点ID
    target: str                          # 目标节点ID
    type: str                            # 边类型: relation | metric_dep | rule_input
    data: dict[str, Any]                 # 边数据
    # data 内容:
    # relation: { label, cardinality }
    # metric_dep: { weight }
    # rule_input: { }

@dataclass
class LayoutConfig:
    """布局配置"""
    type: str = "dagre"                  # dagre | force | concentric
    rankdir: str = "LR"                  # LR | TB | RL | BT
    nodesep: int = 50
    ranksep: int = 80

@dataclass
class GraphMetadata:
    """图元数据"""
    entity_count: int = 0
    relation_count: int = 0
    metric_count: int = 0
    rule_count: int = 0

@dataclass
class SchemaGraphData:
    """Schema 完整图数据 (后端 API 响应体)"""
    schema_id: str
    graph_type: str                      # entity_relation | metric_dependency | full | rule_overview
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    layout_config: LayoutConfig
    metadata: GraphMetadata
```

### 2.2 规则链 DAG 数据模型

```python
@dataclass
class RuleChainNode:
    """X6 兼容的规则链节点"""
    id: str                              # 规则ID (如 "R001_basic_eligibility")
    position: dict[str, float]           # { x, y } 初始位置(自动布局可覆盖)
    data: dict[str, Any]
    # data: {
    #   ruleId, ruleName, ruleType (constraint|inference|alert|decision),
    #   priority, condition (原始条件表达式), action (then action类型),
    #   enabled, dimension
    # }

@dataclass
class RuleChainEdge:
    """X6 兼容的规则链边"""
    id: str                              # 边ID (如 "R001-R002")
    source: str                          # 源规则ID
    target: str                          # 目标规则ID
    data: dict[str, Any]
    # data: { dependency_type: data_flow|condition_dep, description }

@dataclass
class DimensionInfo:
    """维度信息"""
    name: str
    description: str | None
    applicable_entities: list[str]
    rule_count: int

@dataclass
class RuleChainGraphData:
    """规则链 DAG 完整图数据"""
    dimension: str
    nodes: list[RuleChainNode]
    edges: list[RuleChainEdge]
    dimension_info: DimensionInfo
```

### 2.3 执行可解释性数据模型

```python
@dataclass
class ConditionDetail:
    """子条件求值详情"""
    expression: str                      # 子条件原始表达式
    resolved: str                        # 变量替换后的表达式 (如 "100000000 >= 1000000")
    result: bool                         # 求值结果
    explanation: str                     # 自然语言解释 (如 "注册资本100000000元满足最低100万要求")

@dataclass
class ExecutionStepSnapshot:
    """规则执行的完整快照 - 可解释性核心数据结构"""
    step: int                            # 执行步骤序号 (1-based)
    rule_id: str                         # 规则ID
    rule_name: str                       # 规则名称
    rule_type: str                       # constraint | inference | alert | decision

    # 条件求值
    condition_expression: str            # 原始条件表达式
    condition_result: bool | None        # 条件求值结果 (None=无条件)
    condition_details: list[ConditionDetail]  # 子条件逐一求值

    # 上下文快照
    context_before: dict[str, Any]       # 执行前的上下文 (entity_data + computed_metrics)
    context_after: dict[str, Any]        # 执行后的上下文 (含本步输出)

    # 输入输出
    inputs: dict[str, Any]               # 本步实际输入 (从条件中引用的字段)
    outputs: dict[str, Any]              # 本步实际输出

    # 状态
    status: str                          # pending | executing | passed | failed | skipped
    duration_ms: float                   # 执行耗时

    # 解释
    explanation: str                     # 自然语言解释
    affected_metrics: list[str]          # 本步影响的指标名
```

### 2.4 模拟执行数据模型

```python
@dataclass
class SimulationResult:
    """模拟执行结果"""
    entity_id: str
    dimension: str
    simulation_type: str                 # dry_run | what_if

    steps: list[ExecutionStepSnapshot]   # 逐步快照
    execution_path: list[str]            # 实际执行的规则ID序列
    skipped_rules: list[str]             # 跳过的规则ID
    final_outputs: dict[str, Any]        # 最终输出 (computed_metrics最终状态)

    # 决策结果
    decision: str | None                 # APPROVE | REJECT | ...
    decision_reasoning: str | None
    alerts: list[dict[str, Any]]

    # 对比 (What-if 时使用)
    comparison: ComparisonResult | None = None

@dataclass
class DiffEntry:
    """单项差异"""
    field: str                           # 字段名
    baseline_value: Any                  # 原始值
    simulated_value: Any                 # 模拟值
    change_type: str                     # increased | decreased | new | removed | unchanged
    change_magnitude: float | None       # 变化幅度 (百分比)
    impact: str                          # 影响描述

@dataclass
class ImpactChain:
    """影响路径"""
    source_field: str                    # 变更源头
    affected_fields: list[str]           # 受影响字段链
    description: str                     # 影响路径描述

@dataclass
class ComparisonResult:
    """原始 vs 模拟 对比"""
    baseline: dict[str, Any]             # 原始执行结果
    simulated: dict[str, Any]            # 模拟执行结果
    diffs: list[DiffEntry]              # 差异列表
    impact_chains: list[ImpactChain]     # 影响路径
```

## 三、序列化策略

所有 dataclass 通过 `dataclasses.asdict()` 转为 dict，再由 FastAPI 的 `jsonable_encoder` 序列化。

关键点：
- `Any` 类型中的 `datetime`/`date` 需要转为 ISO 格式字符串
- `dict` 中的 `None` 值保留（前端需要区分"未设置"和"无值"）
- `float` 的 `NaN`/`Infinity` 需要替换为 `null`

## 四、与现有模型的关系

| 可视化模型 | 数据来源 | 现有模型 |
|-----------|---------|---------|
| GraphNode (entity) | ConceptDefinition | core/schema/models.py |
| GraphNode (metric) | MetricDefinition | core/schema/models.py |
| GraphNode (rule) | RuleDefinition | core/schema/models.py |
| GraphEdge (relation) | RelationDefinition | core/schema/models.py |
| GraphEdge (metric_dep) | MetricDefinition.dependencies | core/schema/models.py |
| ConditionDetail | RuleWhen + ExpressionEvaluator | engine/rule/evaluator.py |
| ExecutionStepSnapshot | ExecutionContext + RuleResult | engine/rule/models.py |
| SimulationResult | AnalysisResult + 扩展 | engine/rule/models.py |

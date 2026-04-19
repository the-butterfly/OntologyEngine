# AnalysisService 跨引擎协调设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

---

## 目的

定义 AnalysisService 的跨引擎协调架构，将当前 CategorizationEngine → MetricEngine → RuleExecutor 的简单顺序调用重写为支持 L3 并行预计算、指标缓存、ExecutionStepSnapshot 全链路追溯的完整分析编排服务。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **无执行快照** | 规则执行结果无全链路追溯 | ExecutionStepSnapshot 记录每步计算上下文，支持审计和调试 |
| 2 | **L3 指标无并行预计算** | `compute_batch` 顺序计算所有指标 | 按依赖关系分组，无依赖指标 asyncio.gather 并行计算 |
| 3 | **无指标缓存** | 每次分析都重新计算所有指标 | SQLite 缓存已计算指标，相同实体+指标名直接命中 |
| 4 | **无外部注入** | 不支持 context.overrides 跳过计算 | context.overrides 检查，已存在则跳过计算 |
| 5 | **_find_entity 硬编码** | 遍历固定 concept_types 列表查找实体 | 通过 KuzuDB 全局 ID 索引直接查找 |
| 6 | **applies_to 检查缺失** | 不验证规则是否适用于当前实体 | RuleGroup.applies_to 匹配 entity_type + categories |

---

## 执行序列

```
AnalysisService.execute_analysis(entity_id, dimension)
    │
    ├─▶ 1. 获取 Entity (KuzuDB 全局 ID 索引)
    │      └─▶ 不存在 → EntityNotFoundError
    │
    ├─▶ 2. 获取适用 RuleGroup (RuleEngine)
    │      ├─▶ applies_to.fact_objects 匹配
    │      └─▶ applies_to.categories 匹配
    │      └─▶ 不匹配 → NotApplicableError
    │
    ├─▶ 3. L2 归类 (CategorizationEngine)
    │      └─▶ 产出 CategoryTag[]
    │
    ├─▶ 4. L3 指标预计算 (MetricEngine, 并行)
    │      ├─▶ 检查 context.overrides → 跳过
    │      ├─▶ 检查缓存 → 命中则跳过
    │      ├─▶ 按依赖分组 → 无依赖并行计算
    │      └─▶ 写入缓存 + 记录 ExecutionStepSnapshot
    │
    ├─▶ 5. L4 规则执行 (RuleEngine DAG)
    │      ├─▶ DAGBuilder 构建依赖图
    │      ├─▶ DAGExecutor 拓扑分层执行
    │      ├─▶ RuleTransaction 快照回滚
    │      └─▶ 记录 ExecutionStepSnapshot
    │
    └─▶ 6. 结果组装
           ├─▶ computed_metrics: dict[str, Any]
           ├─▶ rule_results: list[RuleResult]
           ├─▶ execution_snapshot: ExecutionSnapshot
           └─▶ 返回 AnalysisResult
```

---

## L3 指标预计算

### 目的

按需计算 L3 指标，优化并行性和缓存命中率。

### 并行计算策略

```
RuleGroup.inputs = [debt_ratio, credit_score, guarantee_exposure]

依赖分析：
  debt_ratio: 依赖 Entity.attributes.debt, Entity.attributes.assets → 无外部依赖
  credit_score: 依赖 debt_ratio → 依赖 debt_ratio
  guarantee_exposure: 依赖 Entity 关联的 guarantees 边 → 无外部依赖

分组：
  Layer 0: [debt_ratio, guarantee_exposure]  ← 无依赖，并行计算
  Layer 1: [credit_score]                     ← 依赖 debt_ratio

执行：
  Layer 0: asyncio.gather(debt_ratio, guarantee_exposure)
  Layer 1: credit_score(debt_ratio_result)
```

### 缓存策略

| 缓存键 | 格式 | 过期策略 |
|--------|------|---------|
| `metric:{entity_id}:{metric_name}` | MetricValue JSON | 实体属性变更时失效 |
| `metric:{entity_id}:{metric_name}:{valid_from}` | 时序指标值 | valid_to 设置时失效 |

### 外部注入

```python
@dataclass
class AnalysisContext:
    overrides: dict[str, Any]
    skip_categorization: bool = False
    dry_run: bool = False
```

当 `context.overrides` 中包含指标名时，直接使用注入值，跳过计算和缓存。

---

## ExecutionStepSnapshot

### 目的

记录分析执行的每一步，实现全链路追溯。对齐 m_flow Procedure 执行快照和 Cognee DataPoint 溯源模式。

### 模型

```python
@dataclass
class ExecutionStepSnapshot:
    snapshot_id: str
    analysis_id: str
    step_type: str
    step_name: str
    entity_id: str
    dimension: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    computed_at: datetime
    computed_by: str
    computation_duration_ms: float
    trace_to_fragment_ids: list[str]
```

### step_type 枚举

| step_type | 说明 | 产出 |
|-----------|------|------|
| `categorization` | L2 归类 | CategoryTag[] |
| `metric_computation` | L3 指标计算 | MetricValue |
| `rule_execution` | L4 规则执行 | RuleResult |
| `metric_cache_hit` | 缓存命中 | MetricValue（来自缓存） |

### 与 MetricValue 的关联

MetricValue.computation_snapshot 引用 ExecutionStepSnapshot.snapshot_id，确保每个自动计算结果都可追溯到完整的计算过程。

### 与互索引边的关系

ExecutionStepSnapshot 通过 TRACE_TO 边关联到 KnowledgeFragment，实现推理步骤 → 来源碎片的证据链：

```
ExecutionStepSnapshot[snap_001] ──[TRACE_TO]──▶ KnowledgeFragment[frag_042]
                                               "授信管理办法第3.2节"
```

---

## 完整接口清单

| 方法 | 说明 |
|------|------|
| `execute_analysis(entity_id, dimension, context)` | 完整维度分析 |
| `execute_dry_run(entity_id, dimension, context)` | 预览分析（不持久化） |
| `get_analysis_history(entity_id, dimension, limit)` | 查询分析历史 |
| `get_execution_snapshot(snapshot_id)` | 获取执行快照详情 |
| `invalidate_metric_cache(entity_id, metric_names)` | 失效指标缓存 |

---

## 返回模型

```python
@dataclass
class AnalysisResult:
    entity_id: str
    fact_object: str
    dimension: str
    category_tags: dict[str, str]
    computed_metrics: dict[str, Any]
    rule_results: list[RuleResult]
    alerts: list[Alert]
    decision: str | None
    decision_reasoning: str | None
    execution_snapshot: ExecutionSnapshot

@dataclass
class ExecutionSnapshot:
    analysis_id: str
    steps: list[ExecutionStepSnapshot]
    total_duration_ms: float
    cache_hit_count: int
    parallelism_used: bool
```

---

## 与 Cognee ECL Pipeline 对齐

| Cognee 概念 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| Pipeline（Task 链式执行） | AnalysisService 执行序列 | Cognee 的 run_pipeline 将 BoundTasks 链式执行 |
| Task（底层执行单元） | ExecutionStepSnapshot | Cognee 的 Task 对应 OntologyEngine 的执行步骤 |
| PipelineContext（上下文注入） | AnalysisContext.overrides | Cognee 的 PipelineContext 传递 user/dataset/extras |
| batch_size（并发控制） | Semaphore(max_concurrency) | Cognee 的 batch_size 对应 OntologyEngine 的并发信号量 |
| DataPoint.source_pipeline | ExecutionStepSnapshot.computed_by | 溯源链：标识数据产出管道 |
| DataPoint.source_content_hash | EntityInstance.source_content_hash | SHA256 哈希用于增量缓存 |

---

## 与 DAG 执行设计的对齐

| DAG 执行概念 | AnalysisService 编排 | 说明 |
|-------------|---------------------|------|
| DAGBuilder.build() | 步骤 2：获取 RuleGroup 后构建 DAG | 从 Step.depends_on 构建依赖图 |
| DAGExecutor.execute() | 步骤 5：L4 规则执行 | 拓扑分层执行，同层并行 |
| RuleTransaction.snapshot() | 每层执行前快照 | 失败时回滚到上一层 |
| ErrorStrategy | 默认 STOP_LAYER | 关键业务场景使用 ABORT_ALL |
| ExecutionDAG.layers | L3 指标也按依赖分层 | 与 L4 DAG 执行使用相同的并行策略 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-AS-1 | L3 指标按依赖分组并行计算 | 无依赖指标并行计算可显著减少总延迟 |
| D-AS-2 | 指标缓存使用 SQLite 而非内存 | 持久化缓存跨会话有效，重启不丢失 |
| D-AS-3 | ExecutionStepSnapshot 独立存储 | 快照数据量大，独立存储避免污染主数据 |
| D-AS-4 | _find_entity 使用 KuzuDB 全局 ID 索引 | 避免硬编码 concept_types 列表 |
| D-AS-5 | applies_to 检查在服务层执行 | 规则适用性是业务逻辑，应在编排层验证 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| DAG 执行设计 | `docs/02-design/rule-engine/dag-execution.md` |
| Instance 层 MetricValue | `docs/02-design/schema/instance-layer.md` |
| Schema v2 四层架构 | `docs/01-overview/05-concepts.md` |
| Cognee Pipeline | `cognee/modules/pipelines/operations/run_pipeline.py` |

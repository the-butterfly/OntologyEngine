# DAG 执行设计

> **status**: accepted | **phase**: implemented | **source_of_truth**: 本文档（DAG 执行机制） | **last_verified**: 2026-04-20

---

## 目的

定义规则引擎从优先级排序执行到 DAG 拓扑执行的完整机制，包括依赖图构建、并行执行策略、快照回滚机制和错误处理。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **步骤间依赖靠优先级隐式保证** | `sorted(rules, key=lambda r: -r.priority)` 降序排序，步骤执行顺序依赖开发者手动设置优先级 | `DAGBuilder` 从 `Step.depends_on` 构建显式依赖图，拓扑排序确定执行顺序 |
| 2 | **无并行执行** | 所有规则顺序执行，即使无依赖关系 | 拓扑分层后，同一层无依赖步骤 `asyncio.gather` 并行执行 |
| 3 | **无环检测** | 循环依赖导致无限循环或静默错误 | `DAGBuilder.build()` 检测环并抛出 `CycleError` |
| 4 | **无回滚** | 规则执行失败仅记录错误，context 已被部分修改 | `RuleTransaction` 提供 snapshot/restore，失败时回滚到一致状态 |
| 5 | **并发无限制** | 无并发控制，大量规则同时执行可能压垮存储层 | `asyncio.Semaphore` 限制并发度 |

---

## DAGBuilder

### 职责

从 L4 `RuleLogicDeclaration.steps` 的 `depends_on` 字段构建有向无环图，检测循环依赖，输出拓扑排序结果。

### 输入

```yaml
rule_logic:
  name: risk_assessment
  type: switch
  steps:
    - id: check_eligible
      name: "资格检查"
      action:
        type: set_flag
        flag: eligible
        value: true
    - id: calc_score
      name: "信用评分"
      depends_on: [check_eligible]
      condition:
        expression: "eligible == true"
      action:
        type: compute
        operator: SCORECARD
        output: credit_score
    - id: assess_risk
      name: "风险评估"
      depends_on: [calc_score]
      action:
        type: compute
        operator: SWITCH
        output: risk_grade
    - id: check_guarantee
      name: "担保链检查"
      depends_on: [check_eligible]
      action:
        type: compute
        operator: GRAPH
        output: guarantee_chain_depth
    - id: final_decision
      name: "最终决策"
      depends_on: [assess_risk, check_guarantee]
      action:
        type: compute
        operator: FORMULA
        output: decision
```

### 输出

```
拓扑分层:

Layer 0: [check_eligible]          ← 无依赖，可立即执行
Layer 1: [calc_score, check_guarantee]  ← 依赖 Layer 0，可并行
Layer 2: [assess_risk]             ← 依赖 calc_score
Layer 3: [final_decision]          ← 依赖 assess_risk + check_guarantee
```

### 模型

```python
class DAGNode:
    step_id: str
    step: Step
    in_degree: int
    dependents: list[str]

class DAGLayer:
    index: int
    nodes: list[DAGNode]

class ExecutionDAG:
    layers: list[DAGLayer]
    step_map: dict[str, DAGNode]
    has_cycle: bool
```

### 构建算法

```
1. 遍历 steps，为每个 step 创建 DAGNode
2. 遍历 steps，解析 depends_on，建立边：
   - 源 step → 目标 step
   - 目标 step.in_degree += 1
   - 源 step.dependents.append(目标 step_id)
3. 环检测：Kahn 算法（BFS 拓扑排序）
   - 初始化队列：in_degree == 0 的节点
   - 逐层出队，减少后继 in_degree
   - 若出队节点数 < 总节点数 → 存在环 → 抛出 CycleError
4. 拓扑分层：
   - Layer 0: in_degree == 0
   - Layer N: 前一层执行完后 in_degree 降为 0 的节点
```

### 环检测错误信息

```
CycleError:
  message: "规则逻辑 'risk_assessment' 存在循环依赖"
  cycle_path: ["calc_score", "assess_risk", "calc_score"]
  suggestion: "请检查步骤 depends_on 声明，消除循环引用"
```

---

## DAGExecutor

### 职责

按拓扑分层执行规则步骤，同一层内并行执行无依赖步骤，支持快照回滚和错误处理。

### 执行流程

```
DAGBuilder.build(rule_logic)
  ↓
ExecutionDAG (拓扑分层)
  ↓
for layer in dag.layers:
  ↓
  RuleTransaction.snapshot(context)
  ↓
  asyncio.gather(*[execute_step(node, context) for node in layer.nodes])
  ↓ (全部成功)
  RuleTransaction.commit()
  ↓ (任一失败)
  RuleTransaction.rollback()
```

### 并行执行策略

**对齐 Cognee Pipeline**：Cognee 的 `run_tasks_parallel` 使用 `asyncio.gather` 并行执行无依赖任务。OntologyEngine 采用相同策略，增加 `Semaphore` 限制并发度。

```python
class DAGExecutor:
    def __init__(
        self,
        operator_registry: OperatorRegistry,
        expression_engine: ExpressionEngine,
        max_concurrency: int = 8,
    ):
        self.operators = operator_registry
        self.expr_engine = expression_engine
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(
        self,
        dag: ExecutionDAG,
        context: ExecutionContext,
        error_strategy: ErrorStrategy = ErrorStrategy.STOP_LAYER,
    ) -> ExecutionResult:
        results = {}

        for layer in dag.layers:
            layer_snapshot = context.snapshot()

            tasks = [
                self._execute_with_semaphore(node, context)
                for node in layer.nodes
            ]
            layer_results = await asyncio.gather(*tasks, return_exceptions=True)

            failed = [r for r in layer_results if isinstance(r, Exception)]
            if failed:
                if error_strategy == ErrorStrategy.STOP_LAYER:
                    context.restore(layer_snapshot)
                    raise LayerExecutionError(layer.index, failed)
                elif error_strategy == ErrorStrategy.CONTINUE:
                    for exc in failed:
                        logger.warning(f"Step failed: {exc}")

            for step_id, result in zip(
                [n.step_id for n in layer.nodes],
                layer_results,
            ):
                if not isinstance(result, Exception):
                    results[step_id] = result
                    context.update(step_id, result)

        return ExecutionResult(results=results, context=context)

    async def _execute_with_semaphore(
        self, node: DAGNode, context: ExecutionContext
    ) -> StepResult:
        async with self.semaphore:
            return await self._execute_step(node, context)

    async def _execute_step(
        self, node: DAGNode, context: ExecutionContext
    ) -> StepResult:
        step = node.step

        condition_met = True
        if step.condition:
            condition_met = self.expr_engine.evaluate(
                step.condition, context.to_eval_dict()
            )

        if not condition_met:
            if step.else_action:
                return await self._execute_action(step.else_action, context, step.id)
            return StepResult(step_id=step.id, skipped=True)

        return await self._execute_action(step.action, context, step.id)

    async def _execute_action(
        self, action: Action, context: ExecutionContext, step_id: str
    ) -> StepResult:
        if action.type == "set_flag":
            context.set_flag(action.flag, action.value)
            return StepResult(step_id=step_id, output={action.flag: action.value})

        if action.type == "compute":
            operator = self.operators.get(action.operator)
            result = await operator.execute(
                inputs=self._resolve_inputs(action, context),
                config=self._build_config(action),
                context=context.to_operator_context(),
            )
            context.set_computed(action.output, result)
            return StepResult(step_id=step_id, output=result)

        if action.type == "reject":
            return StepResult(
                step_id=step_id, rejected=True, reason=action.reason
            )

        if action.type == "emit_alert":
            context.add_alert(Alert(
                severity=action.severity,
                message=action.reason,
            ))
            return StepResult(step_id=step_id, alert_emitted=True)

        if action.type == "assign_category":
            context.set_category(action.category)
            return StepResult(
                step_id=step_id, output={"category": action.category}
            )

        raise UnknownActionTypeError(action.type)
```

### 实现状态

> **2026-04-20 更新**: DAGExecutor 已实现，支持：
> - Kahn 算法拓扑分层
> - 层内并行执行（asyncio.gather + Semaphore）
> - 三种错误策略：STOP_LAYER / CONTINUE / ABORT_ALL
> - RuleTransaction 按层快照/回滚

### 与 Cognee Pipeline Task 对齐

| Cognee 概念 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| `Task` (底层执行) | `DAGNode` + `_execute_step()` | 原子执行单元 |
| `TaskSpec` (装饰器包装) | `Step` 模型 | 声明式步骤定义 |
| `BoundTask` (绑定参数) | `ExecutionContext` 绑定 | 运行时参数注入 |
| `batch_size` | `Semaphore(max_concurrency)` | 并发控制 |
| `enriches` | `ErrorStrategy.CONTINUE` | 失败时继续而非中断 |
| `Drop` 信号 | `StepResult(skipped=True)` | 跳过下游传递 |
| `accepts_ctx` | `context.to_operator_context()` | 自动检测并注入上下文 |

---

## RuleTransaction（快照回滚）

### 职责

在 DAG 执行的每个拓扑层前后提供 context 快照，失败时回滚到上一层执行前的状态。

### 模型

```python
class ContextSnapshot:
    timestamp: str
    computed_metrics: dict[str, Any]
    flags: dict[str, Any]
    alerts: list[Alert]
    categories: dict[str, str]

class RuleTransaction:
    def __init__(self, context: ExecutionContext):
        self.context = context
        self._snapshots: list[ContextSnapshot] = []

    def snapshot(self) -> ContextSnapshot:
        snap = ContextSnapshot(
            timestamp=iso_now(),
            computed_metrics=deepcopy(self.context.computed_metrics),
            flags=deepcopy(self.context.flags),
            alerts=list(self.context.alerts),
            categories=deepcopy(self.context.categories),
        )
        self._snapshots.append(snap)
        return snap

    def restore(self, snapshot: ContextSnapshot) -> None:
        self.context.computed_metrics = snapshot.computed_metrics
        self.context.flags = snapshot.flags
        self.context.alerts = snapshot.alerts
        self.context.categories = snapshot.categories

    def commit(self) -> None:
        self._snapshots.clear()
```

### 回滚场景

| 场景 | 触发条件 | 回滚范围 | 后续动作 |
|------|---------|---------|---------|
| 步骤计算异常 | `operator.execute()` 抛出异常 | 回滚到当前层快照 | 根据错误策略决定是否继续 |
| 条件评估异常 | `expr_engine.evaluate()` 抛出异常 | 回滚到当前层快照 | 标记步骤失败，跳过依赖此步骤的后续步骤 |
| 前置条件不满足 | `precondition` 检查失败 | 回滚到当前层快照 | `reject` 或跳过 |
| 存储写入失败 | `storage.write()` 抛出异常 | 回滚到当前层快照 + 存储层回滚 | 抛出 `StorageWriteError` |

### 与旧设计对比

| 维度 | 旧设计（04-rule-engine-design.md） | 重写设计 |
|------|----------------------------------|---------|
| 回滚粒度 | `@contextmanager rule_transaction()` 全局回滚 | 按 DAG 层回滚，粒度更细 |
| 快照时机 | 无快照 | 每层执行前快照 |
| 存储回滚 | 无 | 配合存储层事务 |
| 异常处理 | 捕获异常继续执行 | 三种策略：STOP_LAYER / CONTINUE / ABORT_ALL |

---

## 错误处理策略

### ErrorStrategy 枚举

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| `STOP_LAYER` | 当前层失败时回滚，抛出 `LayerExecutionError` | 默认策略，保证数据一致性 |
| `CONTINUE` | 当前层失败时跳过失败步骤，继续执行 | 非关键步骤（如 `emit_alert`） |
| `ABORT_ALL` | 任一步骤失败时回滚所有已执行层，抛出 `ExecutionAbortedError` | 关键业务场景（如授信决策） |

### 错误传播

```
Step 执行异常
  ↓
DAGExecutor 捕获
  ↓
根据 ErrorStrategy:
  ├─ STOP_LAYER → 回滚当前层 → 抛出 LayerExecutionError
  │                                    ↓
  │                          PipelineStateManager 记录 FAILED
  │                                    ↓
  │                          上层决定是否重试
  │
  ├─ CONTINUE → 记录警告 → 标记 StepResult(failed=True) → 继续执行
  │
  └─ ABORT_ALL → 逐层回滚 → 抛出 ExecutionAbortedError
                                        ↓
                              PipelineStateManager 记录 FAILED
                                        ↓
                              通知调用方
```

### 依赖步骤失败处理

当步骤 A 失败，且步骤 B `depends_on: [A]` 时：

| 策略 | 步骤 B 行为 |
|------|-----------|
| `STOP_LAYER` | B 在同一层，已被回滚；B 在后续层，因 A 无输出而跳过 |
| `CONTINUE` | B 检测到 A 的输出缺失，标记 `StepResult(skipped=True, skip_reason="dependency_failed")` |
| `ABORT_ALL` | 整体中止，B 不执行 |

---

## 规则筛选与 L4 Grammar 对齐

### applies_to 过滤

```python
def filter_applicable_rules(
    rule_definitions: list[RuleDefinitionDeclaration],
    entity_type: str,
    categories: dict[str, list[str]],
) -> list[RuleDefinitionDeclaration]:
    applicable = []
    for rd in rule_definitions:
        applies_to = rd.applies_to

        fact_match = (
            not applies_to.fact_objects
            or entity_type in applies_to.fact_objects
        )

        cat_match = True
        if applies_to.categories:
            for dim, required_values in applies_to.categories.items():
                entity_values = categories.get(dim, [])
                if not set(required_values) & set(entity_values):
                    cat_match = False
                    break

        if fact_match and cat_match:
            applicable.append(rd)

    return applicable
```

### preconditions 检查

```python
async def check_preconditions(
    preconditions: list[Precondition],
    context: ExecutionContext,
) -> PreconditionCheckResult:
    for pc in preconditions:
        result = expr_engine.evaluate(pc.expression, context.to_eval_dict())
        if not result:
            if pc.fail.reject:
                return PreconditionCheckResult(
                    passed=False,
                    rejected=True,
                    reason=pc.fail.reason,
                )
            if pc.fail.action:
                return PreconditionCheckResult(
                    passed=False,
                    rejected=False,
                    action=pc.fail.action,
                )
    return PreconditionCheckResult(passed=True)
```

---

## 与 KAG 逻辑边对齐

KAG 的 STRUCTURE 块定义了从事实边推导逻辑边的模式。OntologyEngine 的 DAG 执行产出推理边：

```
DAGExecutor 执行步骤
  ↓
步骤产出 (StepResult.output)
  ↓
LogicalEdgeEngine 判断产出类型:
  ├─ action.type == compute → inference 边 (规则推导)
  ├─ action.type == assign_category → inference 边 (分类推导)
  └─ action.type == set_flag → inference 边 (标记推导)
  ↓
写入 KuzuDB (logical_type = "inference")
  ↓
建立 traceability 边 (step → KnowledgeFragment)
```

详见 [logical-edges.md](./logical-edges.md)。

---

## 参考文档

| 主题 | 文档 |
|------|------|
| 规则引擎设计概览 | [README.md](./README.md) |
| L4 grammar Step 定义 | [L1-L4-declarations.md](../schema/L1-L4-declarations.md) |
| Cognee Task 三层结构 | [task.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/cognee/cognee/modules/pipelines/tasks/task.py) |
| KAG Expert Rules DSL | [KAG-Schema.md](file:///Users/dingxuxu/Projects/github/GraphRAGs/KAG-Docs/KAG-Schema.md) |
| 旧规则引擎设计 | [04-rule-engine-design.md](./04-rule-engine-design.md) |

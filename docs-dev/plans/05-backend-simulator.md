# 后端模块详细设计 - simulator.py

> **文件**: `ontology_engine/visualization/simulator.py`
> **职责**: 规则链模拟执行引擎，支持 dry_run 和 what_if 两种模式

## 一、RuleChainSimulator

### 1.1 核心能力

1. **dry_run 模式**：不写存储，仅追踪执行路径，逐步记录快照
2. **what_if 模式**：覆盖变量值，执行后与基线对比
3. **逐步快照**：记录每步的完整上下文（context_before/after）
4. **可解释性**：通过 ConditionExplainer 生成条件拆解和解释

### 1.2 类定义

```python
class RuleChainSimulator:
    """规则链模拟执行器"""

    def __init__(
        self,
        rule_executor: RuleExecutor,
        metric_engine: MetricEngine | None,
        storage: DuckDBStorage,
        schema: KGMLSchema,
    ):
        self.rule_executor = rule_executor
        self.metric_engine = metric_engine
        self.storage = storage
        self.schema = schema
        self.explainer = ConditionExplainer(rule_executor.evaluator)
        self.impact_analyzer = ImpactAnalyzer(schema)
```

### 1.3 主入口

```python
async def simulate(
    self,
    entity_id: str,
    dimension: str,
    overrides: dict[str, Any] | None = None,
    dry_run: bool = True,
) -> SimulationResult:
    """执行模拟

    实现流程:
    1. 获取实体数据
    2. 如有 overrides → 先执行基线模拟（用于对比）
    3. 应用覆盖值到 entity_data
    4. 带快照的规则执行
    5. 构建 What-if 对比（如需要）
    """
    # 1. 获取实体
    entity = await self._find_entity(entity_id)
    if entity is None:
        raise EntityNotFoundError(entity_id)

    entity_data = dict(entity.data)
    entity_data["_concept"] = entity.concept

    # 2. 基线执行（用于 What-if 对比）
    baseline_result: SimulationResult | None = None
    if overrides and not dry_run:
        # what_if 模式需要基线对比
        baseline_result = await self._execute_with_snapshots(
            entity_id, dimension, dict(entity_data)
        )
    elif overrides:
        # dry_run + overrides: 也做对比
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
    if baseline_result and overrides:
        comparison = self._build_comparison(baseline_result, simulation)
        simulation.comparison = comparison

    simulation.simulation_type = "what_if" if overrides else "dry_run"

    return simulation
```

### 1.4 带快照的规则执行

```python
async def _execute_with_snapshots(
    self,
    entity_id: str,
    dimension: str,
    entity_data: dict[str, Any],
) -> SimulationResult:
    """带逐步快照的规则执行 - 核心方法"""

    rules = self.schema.get_rules_for_dimension(dimension) if self.schema.rules else []
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
            # 跳过禁用的规则，记录 skipped 快照
            snapshots.append(self._build_skipped_snapshot(step_idx + 1, rule))
            skipped.append(rule.id)
            continue

        # 检查实体类型是否匹配
        entity_type = entity_data.get("_concept", "")
        if rule.scope and entity_type:
            entity_types = rule.scope.get("entity_types", [])
            if entity_types and entity_type not in entity_types:
                snapshots.append(self._build_skipped_snapshot(step_idx + 1, rule))
                skipped.append(rule.id)
                continue

        # 执行单条规则并记录快照
        step_snapshot = await self._execute_rule_with_snapshot(
            step_idx + 1, rule, context
        )
        snapshots.append(step_snapshot)

        if step_snapshot.status in ("passed", "failed"):
            execution_path.append(rule.id)

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
```

### 1.5 单规则执行快照

```python
async def _execute_rule_with_snapshot(
    self,
    step: int,
    rule: RuleDefinition,
    context: ExecutionContext,
) -> ExecutionStepSnapshot:
    """执行单条规则并记录快照"""

    # 记录执行前上下文
    context_before = self._snapshot_context(context)

    # 求值条件
    condition_result: bool | None = None
    condition_details: list[ConditionDetail] = []

    if rule.when:
        eval_context = self.rule_executor._get_eval_context(context)
        try:
            condition_result = self.rule_executor.evaluator.evaluate(rule.when, eval_context)
            if not isinstance(condition_result, bool):
                condition_result = bool(condition_result)
        except Exception:
            condition_result = False

        # 拆解条件并解释
        condition_details = self.explainer.explain(rule.when, eval_context)

    # 执行规则（复用 RuleExecutor.execute_rule）
    start_time = time.monotonic()
    try:
        rule_result = await self.rule_executor.execute_rule(rule, context)
        duration_ms = (time.monotonic() - start_time) * 1000
        status = "passed" if rule_result.passed else "failed"
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        status = "failed"

    # 记录执行后上下文
    context_after = self._snapshot_context(context)

    # 提取本步输入（从条件中引用的字段）
    inputs = self._extract_inputs(rule, context_before)

    # 提取本步输出
    outputs = rule_result.output if 'rule_result' in dir() else {}

    # 生成解释
    explanation = self._generate_step_explanation(
        rule, condition_result, rule_result if 'rule_result' in dir() else None
    )

    # 受影响的指标
    affected_metrics = self._get_affected_metrics(context_before, context_after)

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
        inputs=inputs,
        outputs=outputs,
        status=status,
        duration_ms=round(duration_ms, 2),
        explanation=explanation,
        affected_metrics=affected_metrics,
    )
```

### 1.6 上下文快照

```python
def _snapshot_context(self, context: ExecutionContext) -> dict[str, Any]:
    """生成上下文快照（深拷贝）"""
    return {
        "entity_data": copy.deepcopy(context.entity_data),
        "computed_metrics": copy.deepcopy(context.computed_metrics),
        "alerts_count": len(context.alerts),
        "rule_results_count": len(context.rule_results),
    }
```

### 1.7 输入提取

```python
def _extract_inputs(self, rule: RuleDefinition, context_before: dict) -> dict[str, Any]:
    """从规则条件中提取引用的字段作为输入"""
    if not rule.when:
        return {}

    inputs = {}
    # 从 context_before 的 computed_metrics 和 entity_data 中提取
    entity_data = context_before.get("entity_data", {})
    computed_metrics = context_before.get("computed_metrics", {})

    # 合并上下文
    merged = {**entity_data, **computed_metrics}

    # 从条件表达式中提取字段引用
    expression = self._serialize_condition(rule.when)
    field_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\b'
    for match in re.finditer(field_pattern, expression):
        field = match.group(1)
        # 跳过保留字和字符串字面量
        if field.lower() in ('and', 'or', 'not', 'true', 'false', 'null', 'none'):
            continue

        # 尝试从上下文中获取值
        value = self._get_nested_value(merged, field)
        if value is not None:
            inputs[field] = value

    return inputs
```

### 1.8 决策判定

```python
def _determine_decision(self, context: ExecutionContext) -> str | None:
    """从执行上下文确定最终决策"""
    # 复用 RuleExecutor.execute_dimension 中的决策逻辑
    eligible = context.computed_metrics.get("eligible")
    if eligible is False:
        return "REJECT"

    critical_alerts = [a for a in context.alerts if a.level == "critical"]
    if critical_alerts:
        return "REVIEW"

    if eligible is True and not critical_alerts:
        credit_score = context.computed_metrics.get("credit_score", 0)
        guarantee_depth = context.computed_metrics.get("guarantee_chain_depth", 0)

        if credit_score >= 80 and guarantee_depth < 2:
            return "APPROVE"
        elif credit_score >= 60:
            return "APPROVE_WITH_CONDITIONS"
        else:
            return "APPROVE_RESTRICTED"

    # 检查是否有 generate_decision 的输出
    final_decision = context.computed_metrics.get("final_decision")
    if final_decision:
        return final_decision

    return None
```

### 1.9 What-if 对比构建

```python
def _build_comparison(
    self,
    baseline: SimulationResult,
    simulated: SimulationResult,
) -> ComparisonResult:
    """构建 What-if 对比结果"""
    baseline_outputs = baseline.final_outputs
    simulated_outputs = simulated.final_outputs

    # 计算差异
    diffs = self.impact_analyzer.compute_diffs(baseline_outputs, simulated_outputs)

    # 追踪影响链
    changed_fields = [d.field for d in diffs if d.change_type != "unchanged"]
    impact_chains = self.impact_analyzer.analyze_impact(changed_fields)

    return ComparisonResult(
        baseline=baseline_outputs,
        simulated=simulated_outputs,
        diffs=diffs,
        impact_chains=impact_chains,
    )
```

### 1.10 覆盖值应用

```python
def _apply_overrides(
    self,
    entity_data: dict[str, Any],
    overrides: dict[str, Any],
) -> None:
    """将覆盖值合并到 entity_data

    支持嵌套路径:
      {"registered_capital.value": 5000000}
      → entity_data["registered_capital"]["value"] = 5000000
    """
    for key, value in overrides.items():
        if "." in key:
            # 嵌套路径
            parts = key.split(".")
            target = entity_data
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = value
        else:
            entity_data[key] = value
```

## 二、模拟执行的关键约束

1. **不写存储**：dry_run 模式下所有计算仅在内存中，不调用 `storage.save_metric()`
2. **RuleExecutor.execute_rule() 的副作用**：该方法会直接修改 `context.computed_metrics` 和 `context.alerts`，这在模拟中是允许的（因为 context 是临时对象）
3. **MetricEngine 依赖**：what_if 模式下如果覆盖了底层指标，需要重算上层指标。Phase 1 暂不支持自动重算，依赖规则链中的 `calculate_credit_score` 等动作重算
4. **时间函数**：`today()` 和 `days_between()` 使用真实时间，模拟中不做冻结

## 三、错误处理

| 场景 | 处理 |
|------|------|
| 实体不存在 | 抛出 EntityNotFoundError |
| 维度无规则 | 返回空 steps + execution_path |
| 条件求值异常 | condition_result=False，explanation 包含错误信息 |
| 规则执行异常 | status="failed"，outputs 包含 error 信息 |
| 覆盖值类型不匹配 | 尝试类型转换，失败则跳过该覆盖 |

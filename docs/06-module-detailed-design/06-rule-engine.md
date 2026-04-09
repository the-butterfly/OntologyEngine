# 模块 06: 规则引擎 (RuleEngine)

> **位置**: `ontology_engine/engine/rule/`
> **依赖**: SchemaLoader, MetricEngine, ExpressionEngine, OperatorRegistry
> **被依赖**: AnalysisService, CategorizationEngine

## 1. 职责

1. **DAG 构建** — 规则依赖图，检测循环
2. **拓扑执行** — 按优先级/依赖顺序执行规则
3. **通用算子体系** — 替代 MVP 硬编码 action
4. **回滚机制** — 规则执行失败回滚上下文
5. **可解释输出** — 每步计算过程可追溯

## 2. 核心接口

```python
# engine/rule/engine.py

class RuleEngine:
    """规则引擎 — DAG 驱动的规则执行"""
    
    def __init__(
        self,
        schema: KGMLSchema,
        metric_engine: MetricEngine,
        expr_engine: ExpressionEngine,
        operator_registry: OperatorRegistry,
        storage: DuckDBStorage
    ):
        self.schema = schema
        self.metric_engine = metric_engine
        self.expr_engine = expr_engine
        self.operators = operator_registry
        self.storage = storage
        
        # 预构建规则 DAG
        self._rule_defs = {r.id: r for r in schema.rules}
        self._dag = self._build_dag()
    
    async def execute_dimension(
        self,
        dimension: str,
        entity_id: str,
        entity_data: dict,
        category_tags: CategoryTags | None = None,
        precomputed_metrics: dict | None = None
    ) -> AnalysisResult:
        """执行指定维度的所有规则
        
        完整流程:
        1. 筛选适用规则
        2. 检查 applies_to (fact_objects + categories)
        3. 构建子 DAG
        4. 拓扑排序
        5. 预计算 L3 指标 (直接调用 MetricEngine，决策 #11)
        6. 顺序执行规则
        7. 组装结果
        """
        # 1. 筛选规则
        applicable_rules = self._filter_rules(dimension, entity_data, category_tags)
        
        if not applicable_rules:
            return AnalysisResult(
                entity_id=entity_id,
                dimension=dimension,
                rule_results=[],
                computed_metrics={},
                alerts=[],
                decision="SKIP",
                decision_reasoning="无适用规则"
            )
        
        # 2. 构建子 DAG 并拓扑排序
        execution_order = self._topological_sort(applicable_rules)
        
        # 3. 预计算 L3 指标 (决策 #11: 直接调用，无中间写入)
        if precomputed_metrics is None:
            required_metrics = self._collect_required_metrics(applicable_rules)
            entity = Entity(id=entity_id, concept_type=entity_data.get("_concept", ""), attributes=entity_data)
            precomputed_metrics = await self.metric_engine.compute_batch(
                required_metrics, entity
            )
        
        # 4. 构建执行上下文
        context = ExecutionContext(
            entity_id=entity_id,
            dimension=dimension,
            entity_data=entity_data,
            computed_metrics=dict(precomputed_metrics),
            category_tags=category_tags.tags if category_tags else {},
            alerts=[],
            rule_results=[]
        )
        
        # 5. 顺序执行规则
        for rule_id in execution_order:
            rule = self._rule_defs.get(rule_id)
            if not rule or not rule.enabled:
                continue
            
            try:
                result = await self._execute_rule(rule, context)
                context.rule_results.append(result)
                
                # 将规则输出注入上下文
                if result.output:
                    context.computed_metrics.update(result.output)
                    if rule.id:
                        for key, value in result.output.items():
                            context.computed_metrics[f"{rule.id}.{key}"] = value
                
                # 记录执行日志
                await self.storage.log_rule_execution(RuleExecutionEntry(
                    entity_id=entity_id,
                    dimension=dimension,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    condition_result=result.passed,
                    action_taken=rule.then.action if rule.then and result.passed else None,
                    output=result.output,
                    duration_ms=result.duration_ms
                ))
                
            except Exception as e:
                # 规则执行失败 → 记录错误，继续执行后续规则
                context.rule_results.append(RuleResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    passed=False,
                    error=str(e)
                ))
        
        # 6. 组装结果
        decision, reasoning = self._determine_decision(context)
        
        return AnalysisResult(
            entity_id=entity_id,
            dimension=dimension,
            rule_results=context.rule_results,
            computed_metrics=context.computed_metrics,
            alerts=context.alerts,
            decision=decision,
            decision_reasoning=reasoning
        )
```

## 3. 规则执行

```python
async def _execute_rule(
    self,
    rule: RuleDefinition,
    context: ExecutionContext
) -> RuleResult:
    """执行单条规则"""
    start_time = time.time()
    
    # 1. 评估条件
    condition_met = True
    condition_detail = None
    
    if rule.when:
        condition_met, condition_detail = self._evaluate_condition(rule.when, context)
    
    # 2. 执行动作
    if condition_met:
        output = await self._execute_action(rule.then, context, rule)
    else:
        if rule.else_:
            output = await self._execute_action(rule.else_, context, rule)
        else:
            output = {"skipped": "condition not met"}
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    return RuleResult(
        rule_id=rule.id,
        rule_name=rule.name,
        passed=condition_met,
        output=output,
        condition_detail=condition_detail,
        duration_ms=duration_ms
    )


def _evaluate_condition(
    self,
    when: ConditionClause,
    context: ExecutionContext
) -> tuple[bool, str]:
    """评估规则条件
    
    Returns:
        (result, detail) — 结果和条件详情
    """
    eval_ctx = self._build_eval_context(context)
    
    if when.expression:
        try:
            result = self.expr_engine.evaluate(when.expression, eval_ctx)
            detail = f"{when.expression} → {result}"
            return bool(result), detail
        except Exception as e:
            return False, f"{when.expression} → ERROR: {e}"
    
    if when.all_of:
        results = []
        for expr in when.all_of:
            try:
                r = bool(self.expr_engine.evaluate(expr, eval_ctx))
                results.append(r)
            except Exception:
                results.append(False)
        detail = " AND ".join(f"({e}→{r})" for e, r in zip(when.all_of, results))
        return all(results), detail
    
    if when.any_of:
        results = []
        for expr in when.any_of:
            try:
                r = bool(self.expr_engine.evaluate(expr, eval_ctx))
                results.append(r)
            except Exception:
                results.append(False)
        detail = " OR ".join(f"({e}→{r})" for e, r in zip(when.any_of, results))
        return any(results), detail
    
    return True, "no condition"
```

## 4. 通用算子体系

替代 MVP 中硬编码的 action 常量，用 OperatorRegistry 实现可扩展算子：

```python
# engine/rule/operators/base.py

class Operator(ABC):
    """算子基类"""
    
    @property
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    def execute(
        self,
        inputs: dict[str, Any],
        config: dict,
        context: ExecutionContext
    ) -> dict[str, Any]: ...


class OperatorRegistry:
    """算子注册表"""
    
    _operators: dict[str, Operator] = {}
    
    @classmethod
    def register(cls, operator: Operator):
        cls._operators[operator.name] = operator
    
    @classmethod
    def get(cls, name: str) -> Operator | None:
        return cls._operators.get(name)
    
    @classmethod
    def execute(
        cls,
        name: str,
        inputs: dict,
        config: dict,
        context: ExecutionContext
    ) -> dict:
        op = cls.get(name)
        if not op:
            raise UnknownOperatorError(name)
        return op.execute(inputs, config, context)


# ===== 内置算子 =====

class SetFlagOperator(Operator):
    """设置标志 — 替代 approve_eligibility / reject_eligibility"""
    name = "set_flag"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        flag = config.get("flag", "")
        value = config.get("value", True)
        context.computed_metrics[flag] = value
        return {flag: value}


class RejectOperator(Operator):
    """拒绝 — 带原因"""
    name = "reject"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        reason = config.get("reason", "未满足条件")
        return {"rejected": True, "reason": reason}


class ComputeFormulaOperator(Operator):
    """公式计算 — 替代 calculate_credit_score 等"""
    name = "compute"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        formula = config.get("formula", "")
        output_name = config.get("output", "result")
        
        if formula:
            result = self.expr_engine.evaluate(formula, inputs)
            context.computed_metrics[output_name] = result
            return {output_name: result}
        return {}


class SwitchOperator(Operator):
    """SWITCH 算子 — 多分支选择"""
    name = "SWITCH"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        input_value = inputs.get(config.get("input", ""))
        branches = config.get("branches", [])
        default = config.get("default")
        output_name = config.get("output", "result")
        
        for branch in branches:
            condition = branch.get("condition", "")
            formula = branch.get("formula", "")
            
            # 匹配分支
            if self._matches(input_value, condition, inputs):
                if formula:
                    result = self.expr_engine.evaluate(formula, inputs)
                else:
                    result = branch.get("value", input_value)
                context.computed_metrics[output_name] = result
                return {output_name: result}
        
        # 默认分支
        if default:
            result = self.expr_engine.evaluate(default, inputs)
            context.computed_metrics[output_name] = result
            return {output_name: result}
        
        return {output_name: None}


class BinningOperator(Operator):
    """分箱算子 — 连续值离散化"""
    name = "BINNING"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        input_value = inputs.get(config.get("input", ""))
        bins = config.get("bins", [])
        output_name = config.get("output", "result")
        
        for bin_spec in bins:
            # bin_spec: "[0, 40)" → range
            if self._in_bin(input_value, bin_spec):
                label = bins[bin_spec]
                context.computed_metrics[output_name] = label
                return {output_name: label}
        
        return {output_name: None}


class ScorecardOperator(Operator):
    """评分卡算子"""
    name = "SCORECARD"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        baseline = config.get("baseline", 0)
        variables = config.get("variables", [])
        output_name = config.get("output", "result")
        post_formula = config.get("post_formula", "baseline + total_points")
        
        total_points = 0
        for var in variables:
            var_name = var.get("name", "")
            var_value = inputs.get(var_name, 0)
            points_table = var.get("points", {})
            
            # 匹配得分
            for condition, points in points_table.items():
                if self._matches_score_condition(var_value, condition, inputs):
                    total_points += points
                    break
        
        result = self.expr_engine.evaluate(
            post_formula,
            {**inputs, "baseline": baseline, "total_points": total_points}
        )
        context.computed_metrics[output_name] = result
        return {output_name: result}


class GraphTraversalOperator(Operator):
    """图遍历算子"""
    name = "GRAPH"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        query = config.get("query", {})
        aggregation = config.get("aggregation", [])
        output_name = config.get("output", "result")
        
        # 执行图遍历 (委托 NetworkX)
        relation_type = query.get("relation", "")
        depth = query.get("depth", 2)
        
        entity_id = context.entity_id
        subgraph = self.graph_store.load_subgraph(entity_id, depth, [relation_type])
        
        results = {}
        for agg in aggregation:
            agg_type = agg.get("type", "sum")
            field = agg.get("field", "")
            agg_output = agg.get("output", field)
            
            values = []
            for _, data in subgraph.edges(data=True):
                if field in data:
                    values.append(data[field])
            
            if agg_type == "sum":
                results[agg_output] = sum(values)
            elif agg_type == "count":
                results[agg_output] = len(values)
            elif agg_type == "max":
                results[agg_output] = max(values) if values else 0
        
        # 后处理
        post_process = config.get("post_process", {})
        if post_process.get("formula"):
            results["result"] = self.expr_engine.evaluate(
                post_process["formula"], {**inputs, **results}
            )
        
        context.computed_metrics.update(results)
        return results


class TriggerAlertOperator(Operator):
    """触发预警"""
    name = "trigger_alert"
    
    def execute(self, inputs: dict, config: dict, context: ExecutionContext) -> dict:
        alert = Alert(
            level=config.get("alert_level", "warning"),
            type=config.get("alert_type", "general"),
            message=config.get("message", ""),
            data=config
        )
        context.alerts.append(alert)
        return {"alert": alert.model_dump()}


# ===== 注册内置算子 =====

def register_builtin_operators():
    """注册所有内置算子"""
    OperatorRegistry.register(SetFlagOperator())
    OperatorRegistry.register(RejectOperator())
    OperatorRegistry.register(ComputeFormulaOperator())
    OperatorRegistry.register(SwitchOperator())
    OperatorRegistry.register(BinningOperator())
    OperatorRegistry.register(ScorecardOperator())
    OperatorRegistry.register(GraphTraversalOperator())
    OperatorRegistry.register(TriggerAlertOperator())
```

## 5. 动作执行

```python
async def _execute_action(
    self,
    action_clause: ActionClause | None,
    context: ExecutionContext,
    rule: RuleDefinition
) -> dict:
    """执行规则动作"""
    if not action_clause:
        return {}
    
    eval_ctx = self._build_eval_context(context)
    output = dict(action_clause.output) if action_clause.output else {}
    
    # 1. 如果有 computation，先执行计算
    if action_clause.computation:
        comp = action_clause.computation
        
        # 检查是否有算子
        operator_name = comp.get("operator")
        if operator_name:
            op = self.operators.get(operator_name)
            if op:
                result = op.execute(eval_ctx, comp, context)
                output.update(result)
            else:
                raise UnknownOperatorError(operator_name)
        elif comp.get("formula"):
            # 纯公式计算
            result = self.expr_engine.evaluate(comp["formula"], eval_ctx)
            output["computed_value"] = result
    
    # 2. 如果有 action，执行动作算子
    if action_clause.action:
        action = action_clause.action
        
        # 特殊 action → 对应算子
        action_to_operator = {
            "approve_eligibility": "set_flag",
            "reject_eligibility": "reject",
            "trigger_alert": "trigger_alert",
            "calculate_credit_score": "compute",
            "calculate_credit_limit": "compute",
            "determine_interest_rate": "compute",
            "generate_decision": "compute",
            "set_category": "set_flag",
        }
        
        operator_name = action_to_operator.get(action, action)
        op = self.operators.get(operator_name)
        if op:
            # 兼容 MVP action → 算子 config 映射
            op_config = self._action_to_config(action, output)
            result = op.execute(eval_ctx, op_config, context)
            output.update(result)
        else:
            # 未知 action，保留 output
            pass
    
    # 3. 解析 output 中的模板变量
    output = self._resolve_templates(output, context)
    
    return output


def _action_to_config(self, action: str, output: dict) -> dict:
    """MVP action → 算子 config 映射 (兼容层)"""
    if action == "approve_eligibility":
        return {"flag": "eligible", "value": True}
    elif action == "reject_eligibility":
        return {"flag": "eligible", "value": False, "reason": output.get("rejection_reason", "")}
    elif action == "trigger_alert":
        return output
    elif action == "set_category":
        return {"flag": output.get("dimension", ""), "value": output.get("category_value", "")}
    else:
        return output
```

## 6. DAG 构建

```python
# engine/rule/dag.py

class RuleDAG:
    """规则依赖 DAG"""
    
    def __init__(self, rules: list[RuleDefinition]):
        self.rules = {r.id: r for r in rules}
        self.graph = self._build()
    
    def _build(self) -> nx.DiGraph:
        G = nx.DiGraph()
        
        for rule in self.rules.values():
            G.add_node(rule.id, rule=rule)
        
        for rule in self.rules.values():
            # 显式依赖 (v2: depends_on)
            for dep_id in rule.depends_on:
                if dep_id in self.rules:
                    G.add_edge(dep_id, rule.id)
            
            # 隐式依赖 (v1: scope + priority)
            # 同维度内按 priority 排序
            if not rule.depends_on:
                scope = rule.scope or {}
                dims = scope.get("dimensions", [])
                for other in self.rules.values():
                    if other.id == rule.id:
                        continue
                    other_dims = (other.scope or {}).get("dimensions", [])
                    if set(dims) & set(other_dims) and other.priority > rule.priority:
                        G.add_edge(other.id, rule.id)
        
        if not nx.is_directed_acyclic_graph(G):
            cycles = list(nx.simple_cycles(G))
            raise RuleDAGError(f"规则存在循环依赖: {cycles}")
        
        return G
    
    def topological_sort(self, rule_ids: list[str] | None = None) -> list[str]:
        if rule_ids is None:
            return list(nx.topological_sort(self.graph))
        
        subgraph = self.graph.subgraph(set(rule_ids) & set(self.graph.nodes))
        return list(nx.topological_sort(subgraph))
```

## 7. 供应链金融规则执行流

```
Supplier (SUP_2024_001), dimension=credit_assessment

1. 筛选规则: R001-R007 (全部属于 credit_assessment 维度)

2. 拓扑排序: R001(100) → R002(90) → R003(95) → R004(80) → R005(70) → R006(60) → R007(50)

3. 预计算 L3 指标 (MetricEngine.compute_batch):
   {total_invoice_amount_90d, overdue_invoice_amount, ...} → computed_metrics

4. 执行规则:
   R001: when="status=='ACTIVE' AND registered_capital.value>=1000000 AND ..." → TRUE
         → action=set_flag(eligible=true)
   
   R002: when="eligible==true" → TRUE
         → action=compute(credit_score=83.9, credit_grade=AA)
   
   R003: when="has_guarantee_circle==true OR guarantee_chain_depth>=3" → FALSE
         → 跳过 (no else)
   
   R004: when="credit_score IS NOT NULL" → TRUE
         → action=SWITCH(credit_grade) → AA → registered_capital*0.5*1.8 = 45000000
   
   R005: when="overdue_invoice_ratio>=15 OR ..." → FALSE → 跳过
   
   R006: when="credit_grade IS NOT NULL" → TRUE
         → action=compute(interest_rate=5.81%)
   
   R007: when="true" → TRUE
         → action=SWITCH(credit_score>=80 AND guarantee_chain_depth<2) → APPROVE

5. 结果:
   decision=APPROVE, credit_limit=45M, interest_rate=5.81%
```

## 8. 文件结构

```
ontology_engine/engine/rule/
├── __init__.py            # 导出 RuleEngine, OperatorRegistry
├── engine.py              # RuleEngine 主类
├── dag.py                 # RuleDAG 构建
├── models.py              # ExecutionContext, RuleResult, AnalysisResult, Alert
├── evaluator.py           # 条件评估
├── action_executor.py     # 动作执行 + 算子调度
│
└── operators/
    ├── __init__.py        # register_builtin_operators()
    ├── base.py            # Operator 基类, OperatorRegistry
    ├── flag_ops.py        # SetFlag, Reject
    ├── compute_ops.py     # ComputeFormula, Switch, Binning, Scorecard
    ├── graph_ops.py       # GraphTraversal
    └── alert_ops.py       # TriggerAlert
```

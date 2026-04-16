# 规则引擎设计

> **状态**: 当前实现与本文档存在偏差，详见 `docs/04-migration-and-gap/README.md`
> **最后核验**: 2026-04-16

## 核心流程

```
Schema.yaml ──▶ Parser ──▶ DAG ──▶ Executor ──▶ Results
```

## 组件

### 1. RuleParser

解析 YAML 规则为内部模型。

```python
class RuleParser:
    def parse(self, raw_rules: list[dict]) -> list[Rule]:
        rules = []
        for r in raw_rules:
            rule = Rule(
                id=r["id"],
                when=self.parse_condition(r["when"]),
                then=self.parse_action(r["then"]),
                else_=self.parse_action(r.get("else")),
                priority=r.get("priority", 0),
            )
            rules.append(rule)
        return rules
```

### 2. DAGBuilder

> **当前实现状态**: ❌ 未实现 (2026-04-16)
> 实际 `RuleExecutor` 使用 `priority` 降序排序替代 DAG 拓扑执行。

构建规则依赖图 (目标设计)。

```python
class DAGBuilder:
    def build(self, rules: list[Rule]) -> nx.DiGraph:
        G = nx.DiGraph()

        for rule in rules:
            G.add_node(rule.id, rule=rule)

        for rule in rules:
            for dep in rule.dependencies:
                G.add_edge(dep, rule.id)

        if not nx.is_directed_acyclic_graph(G):
            raise CycleError("规则存在循环依赖")

        return G
```

### 3. ExpressionEngine

表达式解析与执行。**两级安全执行模型（决策 #10）**。

```python
class ExpressionEngine:
    """两级表达式执行引擎"""
    
    # L1 控制流关键词
    CONTROL_FLOW_KEYWORDS = {"if", "for", "while", "def", "class", "try", "with"}
    
    def evaluate(self, expr: str, context: Context) -> Any:
        # 自动选择执行器
        executor = self._select_executor(expr)
        return executor.evaluate(expr, context)
    
    def _select_executor(self, expr: str) -> FormulaExecutor:
        tokens = set(self.tokenize(expr))
        if tokens & self.CONTROL_FLOW_KEYWORDS:
            return ASTSandboxExecutor(
                whitelist=AST_WHITELIST,
                max_loop_iterations=1000,
                timeout_seconds=5
            )
        else:
            return SimpleEvalExecutor(
                names=context.variables,
                functions=SAFE_FUNCTIONS
            )

class SimpleEvalExecutor:
    """L0: 简单表达式执行器（基于 simpleeval）"""
    def evaluate(self, expr: str, context: Context) -> Any:
        evaluator = SimpleEval()
        evaluator.names = context.variables
        evaluator.functions = SAFE_FUNCTIONS
        return evaluator.eval(expr)

>
> **当前实现状态**: ⚠️ 部分实现 (2026-04-16)
> 当前代码使用 simpleeval + asteval fallback，非独立的 ASTSandboxExecutor。

class ASTSandboxExecutor:
    """L1: AST 白名单沙箱执行器（基于 asteval）(目标设计)"""
    def __init__(self, whitelist, max_loop_iterations, timeout_seconds):
        self.whitelist = whitelist
        self.max_loop_iterations = max_loop_iterations
        self.timeout_seconds = timeout_seconds
    
    def evaluate(self, expr: str, context: Context) -> Any:
        # 1. AST 解析 + 白名单校验
        tree = ast.parse(expr)
        self._validate_ast(tree)
        
        # 2. 带资源限制的执行
        return self._execute_with_limits(tree, context)
    
    def _validate_ast(self, tree):
        """AST 白名单校验"""
        for node in ast.walk(tree):
            if type(node) not in self.whitelist:
                raise FormulaSandboxViolation(
                    f"Disallowed AST node: {type(node).__name__}"
                )
```

### 4. OperatorRegistry

算子注册与执行。 ✅ 已实现 (2026-04-16)

当前实际实现 16 个算子，已覆盖 flag/compute/switch/alert/graph/decision_table/llm_judge/weighted_sum 等类别。

```python
class OperatorRegistry:
    _operators: dict[str, Operator] = {}

    @classmethod
    def register(cls, name: str, op: Operator):
        cls._operators[name] = op

    @classmethod
    def execute(cls, name: str, inputs: dict) -> dict:
        op = cls._operators.get(name)
        if not op:
            raise UnknownOperatorError(name)
        return op.execute(inputs)
```

内置算子：

| 算子 | 用途 |
|------|------|
| `MATH_ADD` | 加法 |
| `MATH_SUB` | 减法 |
| `MATH_MUL` | 乘法 |
| `MATH_DIV` | 除法 |
| `LOGIC_IF` | 条件分支 |
| `LOGIC_SWITCH` | 多分支 |
| `AGG_SUM` | 求和 |
| `AGG_AVG` | 平均 |
| `GRAPH_PATH` | 图路径 |

---

## 执行流程

**跨引擎直接调用模式（决策 #11）**：MetricEngine 计算完成后，直接调用 RuleEngine 传入指标结果。

```python
class RuleExecutor:
    def __init__(
        self,
        metric_engine: MetricEngine,
        storage: Storage,
        expr_engine: ExpressionEngine,
        dag_builder: DAGBuilder
    ):
        self.metric_engine = metric_engine
        self.storage = storage
        self.expr_engine = expr_engine
        self.dag_builder = dag_builder

    def execute(
        self,
        entity_id: str,
        dimension: str,
        rules: list[Rule],
        facts: dict | None = None,
        metrics: dict | None = None
    ) -> ExecutionResult:
        # 1. 加载实体
        entity = self.storage.get_entity(entity_id)

        # 2. 筛选适用规则
        applicable = [
            r for r in rules
            if dimension in r.scope.dimensions
            and entity.concept_type in r.scope.entity_types
        ]

        # 3. 构建DAG
        dag = self.dag_builder.build(applicable)

        # 4. 拓扑排序
        execution_order = list(nx.topological_sort(dag))

        # 5. 预计算 L3 指标（直接调用，无中间写入）
        if metrics is None:
            metrics = self.metric_engine.compute_batch(
                required_metrics(applicable), entity
            )

        # 6. 顺序执行
        context = ExecutionContext(
            entity=entity,
            facts=facts or entity.attributes,
            metrics=metrics
        )
        results = {}

        for rule_id in execution_order:
            rule = dag.nodes[rule_id]["rule"]

            # 评估条件
            condition = self.expr_engine.evaluate(
                rule.when.expression,
                context
            )

            if condition:
                result = self._execute_action(rule.then, context)
            else:
                result = self._execute_action(rule.else_, context)

            context.update(rule_id, result)
            results[rule_id] = result

        return ExecutionResult(
            entity_id=entity_id,
            dimension=dimension,
            results=results,
            computed=context.get_all()
        )
```

---

## 回滚机制

> **当前实现状态**: ❌ 未实现 (2026-04-16)
> 当前仅捕获异常并继续执行后续规则，无 snapshot/restore 机制。

```python
@contextmanager
def rule_transaction():
    snapshot = context.snapshot()
    try:
        yield
    except Exception:
        context.restore(snapshot)
        raise
```

---

## L2 归类规则复用（决策 #6）

L2 的 `categorization_rules` 复用 L4 规则引擎执行。`CategorizationEngine` 将 L2 规则编译为 L4 规则格式后，调用 `RuleExecutor.execute()`。

```python
class CategorizationEngine:
    """L2 归类引擎 - 复用 L4 规则引擎"""
    
    def __init__(self, rule_executor: RuleExecutor):
        self.rule_executor = rule_executor
    
    def categorize(self, entity: Entity, dimensions: list[Dimension]) -> CategoryTags:
        tags = CategoryTags()
        
        for dimension in dimensions:
            if dimension.type == "hierarchical":
                value = self.match_hierarchical(entity, dimension)
            elif dimension.type == "derived":
                # 编译 L2 规则为 L4 格式，复用 RuleExecutor
                rules = self._compile_to_l4_rules(dimension.ruleset, dimension.name)
                result = self.rule_executor.execute(
                    entity_id=entity.id,
                    dimension=dimension.name,
                    rules=rules
                )
                value = result.computed.get(dimension.name)
            elif dimension.type == "tags":
                value = self.apply_tag_rules(entity, dimension)
            
            tags.set(dimension.name, value)
        
        return tags
    
    def _compile_to_l4_rules(self, ruleset: CategorizationRuleset, dimension_name: str) -> list[Rule]:
        """将 L2 categorization_rules 编译为 L4 Rule 格式
        
        L2: condition → result (简单映射)
        L4: id + when + then (DAG 节点)
        """
        rules = []
        for i, cat_rule in enumerate(ruleset.rules):
            rule = Rule(
                id=f"L2_{dimension_name}_{i}",
                when=Condition(expression=self._build_expression(cat_rule.condition)),
                then=Action(
                    type="set_flag",
                    flag=dimension_name,
                    value=cat_rule.result
                ),
                priority=cat_rule.priority
            )
            rules.append(rule)
        return rules
    
    def _build_expression(self, condition: dict) -> str:
        """将 L2 条件结构编译为表达式字符串"""
        if not condition:
            return "True"  # 默认规则
        
        parts = []
        for cond in condition.get("and", []):
            parts.append(f"{cond['fact']} {cond['op']} {cond['value']}")
        return " AND ".join(parts)
```

---

## 示例

```yaml
# schema.yaml
ruleset:
  - id: R001_eligibility
    priority: 100
    when:
      expression: "status == 'ACTIVE'"
    then:
      action: approve_eligibility
      output:
        eligible: true

  - id: R002_credit_score
    priority: 90
    when:
      expression: "R001.eligible == true"
    then:
      action: calculate_credit_score
      computation:
        operator: MATH_ADD
        inputs:
          - source: registered_capital
            weight: 0.3
          - source: years_in_business
            weight: 0.7
```

执行结果：
```json
{
  "entity_id": "S001",
  "dimension": "credit_assessment",
  "results": {
    "R001_eligibility": { "eligible": true },
    "R002_credit_score": { "score": 85 }
  }
}
```

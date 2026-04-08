# 规则引擎设计

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

构建规则依赖图。

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

表达式解析与执行。

```python
class ExpressionEngine:
    def evaluate(self, expr: str, context: Context) -> Any:
        # 当前: 字符串解析
        # 未来: AST 解析 (ADR-003)
        tokens = self.tokenize(expr)
        return self._eval(tokens, context)

    def _eval(self, tokens, context):
        # 处理比较: a > b
        # 处理逻辑: a AND b
        # 处理函数: today()
```

### 4. OperatorRegistry

算子注册与执行。

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

```python
class RuleExecutor:
    def execute(
        self,
        entity_id: str,
        dimension: str,
        rules: list[Rule]
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

        # 5. 顺序执行
        context = ExecutionContext(entity=entity)
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

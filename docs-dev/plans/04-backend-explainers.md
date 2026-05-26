# 后端模块详细设计 - explainers.py

> **文件**: `ontology_engine/visualization/explainers.py`
> **职责**: 条件表达式拆解 + 影响链分析，生成自然语言解释

## 一、ConditionExplainer

### 1.1 职责

将规则条件表达式（可能包含 AND/OR/NOT）拆解为原子子条件，逐一：
1. 展示原始表达式
2. 展示变量替换后的表达式（resolved）
3. 给出求值结果
4. 生成自然语言解释

### 1.2 核心接口

```python
class ConditionExplainer:
    """条件表达式拆解与解释生成器"""

    def __init__(self, evaluator: ExpressionEvaluator):
        self.evaluator = evaluator

    def explain(
        self,
        when: RuleWhen | None,
        eval_context: dict[str, Any],
    ) -> list[ConditionDetail]:
        """将条件拆解为子条件并逐一解释

        示例输入:
          when.expression = "status == 'ACTIVE' AND registered_capital.value >= 1000000"
          eval_context = {"status": "ACTIVE", "registered_capital": {"value": 100000000}, ...}

        示例输出:
          [
            ConditionDetail(
              expression="status == 'ACTIVE'",
              resolved="'ACTIVE' == 'ACTIVE'",
              result=True,
              explanation="企业状态为活跃(ACTIVE)"
            ),
            ConditionDetail(
              expression="registered_capital.value >= 1000000",
              resolved="100000000 >= 1000000",
              result=True,
              explanation="注册资本100000000元满足最低100万元要求"
            )
          ]
        """
        if when is None:
            return []

        # 处理 allOf
        if when.allOf:
            return self._explain_allOf(when.allOf, eval_context)

        # 处理 anyOf
        if when.anyOf:
            return self._explain_anyOf(when.anyOf, eval_context)

        # 处理单个 expression
        if when.expression:
            return self._explain_expression(when.expression, eval_context)

        return []
```

### 1.3 拆解逻辑

```python
def _explain_expression(
    self,
    expression: str,
    eval_context: dict[str, Any],
) -> list[ConditionDetail]:
    """拆解单个表达式"""
    # 1. 按 AND/OR 拆解
    sub_exprs = self._split_condition(expression)

    details = []
    for sub_expr in sub_exprs:
        sub_expr = sub_expr.strip()

        # 2. 生成 resolved 表达式（变量替换）
        resolved = self._resolve_expression(sub_expr, eval_context)

        # 3. 求值
        try:
            result = self.evaluator._evaluate_expression(sub_expr, eval_context)
            if not isinstance(result, bool):
                result = bool(result)
        except Exception:
            result = False

        # 4. 生成自然语言解释
        explanation = self._generate_explanation(sub_expr, resolved, result, eval_context)

        details.append(ConditionDetail(
            expression=sub_expr,
            resolved=resolved,
            result=result,
            explanation=explanation,
        ))

    return details
```

### 1.4 条件拆解 (_split_condition)

```python
def _split_condition(self, expression: str) -> list[str]:
    """按 AND/OR 拆解条件，保留 NOT"""
    # 使用 evaluator 已有的字符串安全拆分
    parts = []

    # 先尝试 AND
    if " AND " in expression.upper():
        and_parts = self.evaluator._split_outside_strings(expression, " AND ")
        if len(and_parts) > 1:
            for part in and_parts:
                parts.extend(self._split_condition(part.strip()))
            return parts

    # 再尝试 OR
    if " OR " in expression.upper():
        or_parts = self.evaluator._split_outside_strings(expression, " OR ")
        if len(or_parts) > 1:
            for part in or_parts:
                parts.extend(self._split_condition(part.strip()))
            return parts

    # 原子条件，不再拆分
    return [expression]
```

### 1.5 变量替换 (_resolve_expression)

复用 `ExpressionEvaluator._resolve_fields()` 方法：

```python
def _resolve_expression(self, expression: str, eval_context: dict[str, Any]) -> str:
    """将条件中的变量替换为实际值"""
    return self.evaluator._resolve_fields(expression, eval_context)
```

### 1.6 自然语言解释生成 (_generate_explanation)

基于模板的解释生成，覆盖供应链金融常见条件模式：

```python
def _generate_explanation(
    self,
    original: str,
    resolved: str,
    result: bool,
    eval_context: dict[str, Any],
) -> str:
    """生成自然语言解释"""
    # 模式匹配 + 模板填充
    patterns = [
        # status == 'ACTIVE'
        (r"(\w+)\s*==\s*'(\w+)'", self._explain_eq_string),
        # registered_capital.value >= 1000000
        (r"(\w+(?:\.\w+)*)\s*>=\s*(\d+)", self._explain_gte_numeric),
        # credit_score < 50
        (r"(\w+(?:\.\w+)*)\s*<\s*(\d+)", self._explain_lt_numeric),
        # guarantee_chain_depth >= 3
        (r"(\w+(?:\.\w+)*)\s*>=\s*(\d+)", self._explain_gte_numeric),
        # IS NOT NULL
        (r"(\w+)\s+IS\s+NOT\s+NULL", self._explain_not_null),
        # IS NULL
        (r"(\w+)\s+IS\s+NULL", self._explain_null),
    ]

    for pattern, handler in patterns:
        match = re.search(pattern, original, re.IGNORECASE)
        if match:
            return handler(match, resolved, result, eval_context)

    # 通用回退
    if result:
        return f"条件满足: {original}"
    else:
        return f"条件不满足: {original}"
```

**解释模板示例**：

```python
def _explain_gte_numeric(self, match, resolved, result, context):
    """解释 >= 数值比较"""
    field = match.group(1)
    threshold = match.group(2)
    field_label = METRIC_LABELS.get(field, field)
    
    if result:
        # 从 resolved 中提取实际值
        actual = self._extract_left_value(resolved)
        if field == "registered_capital.value":
            return f"注册资本{self._format_money(actual)}满足最低{self._format_money(threshold)}要求"
        return f"{field_label}({actual}) >= {threshold}，满足要求"
    else:
        actual = self._extract_left_value(resolved)
        return f"{field_label}({actual}) < {threshold}，不满足要求"
```

## 二、ImpactAnalyzer

### 2.1 职责

分析 What-if 模拟中变量变更的影响链，回答"如果我改了这个指标，会影响哪些下游？"

### 2.2 核心接口

```python
class ImpactAnalyzer:
    """影响链分析器 - 分析变量变更的传播路径"""

    def __init__(self, schema: KGMLSchema):
        self.schema = schema
        # 构建指标依赖图 (与 MetricDAG 一致)
        self._dep_graph = self._build_dependency_graph()

    def analyze_impact(
        self,
        changed_fields: list[str],
    ) -> list[ImpactChain]:
        """分析变量变更的影响路径

        示例:
          changed_fields = ["credit_score"]
          → ImpactChain(
              source_field="credit_score",
              affected_fields=["credit_grade", "credit_limit", "interest_rate", "final_decision"],
              description="credit_score ↓ → credit_grade ↓ → credit_limit ↓ → interest_rate ↑"
            )
        """
        chains = []
        for field in changed_fields:
            affected = self._trace_downstream(field)
            if affected:
                chains.append(ImpactChain(
                    source_field=field,
                    affected_fields=affected,
                    description=self._build_impact_description(field, affected),
                ))
        return chains

    def compute_diffs(
        self,
        baseline: dict[str, Any],
        simulated: dict[str, Any],
    ) -> list[DiffEntry]:
        """计算基线与模拟结果的差异"""
        diffs = []
        all_keys = set(list(baseline.keys()) + list(simulated.keys()))

        for key in sorted(all_keys):
            b_val = baseline.get(key)
            s_val = simulated.get(key)

            if b_val == s_val:
                continue

            # 计算变化类型和幅度
            change_type = self._classify_change(b_val, s_val)
            magnitude = self._compute_magnitude(b_val, s_val)

            diffs.append(DiffEntry(
                field=key,
                baseline_value=b_val,
                simulated_value=s_val,
                change_type=change_type,
                change_magnitude=magnitude,
                impact=self._describe_impact(key, b_val, s_val),
            ))

        return diffs
```

### 2.3 依赖图构建

```python
def _build_dependency_graph(self) -> dict[str, list[str]]:
    """构建指标下游依赖图

    返回: { metric_name: [直接依赖它的其他指标名] }
    """
    downstream: dict[str, list[str]] = {}
    for metric in self.schema.metrics:
        for dep in metric.dependencies:
            if dep not in downstream:
                downstream[dep] = []
            downstream[dep].append(metric.name)
    return downstream
```

### 2.4 下游追踪

```python
def _trace_downstream(self, field: str) -> list[str]:
    """追踪某字段的所有下游影响（BFS）"""
    visited = set()
    queue = [field]
    result = []

    while queue:
        current = queue.pop(0)
        for downstream_field in self._dep_graph.get(current, []):
            if downstream_field not in visited:
                visited.add(downstream_field)
                result.append(downstream_field)
                queue.append(downstream_field)

    return result
```

### 2.5 影响描述生成

```python
def _build_impact_description(self, source: str, affected: list[str]) -> str:
    """生成影响路径描述"""
    # 按依赖层级排序
    path = [source] + affected
    labels = [METRIC_LABELS.get(p, p) for p in path]
    return " → ".join(labels)
```

### 2.6 变化幅度计算

```python
def _compute_magnitude(self, baseline: Any, simulated: Any) -> float | None:
    """计算变化幅度（百分比）"""
    try:
        b = float(baseline) if baseline is not None else 0
        s = float(simulated) if simulated is not None else 0
        if b == 0:
            return None  # 无法计算百分比
        return round((s - b) / abs(b) * 100, 1)
    except (TypeError, ValueError):
        return None
```

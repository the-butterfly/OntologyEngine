# 模块 06: 规则引擎 (RuleEngine)

> **位置**: `ontology_engine/engine/rule/`
> **依赖**: SchemaLoader, MetricEngine, ExpressionEngine, OperatorRegistry
> **被依赖**: AnalysisService, CategorizationEngine
> **状态**: 当前实现与目标设计存在偏差，详见 `docs/04-migration-and-gap/README.md`
> **最后核验**: 2026-04-16

---

## 1. 职责

1. **规则执行** — 按优先级顺序执行规则 (当前实现)
2. **通用算子体系** — 替代 MVP 硬编码 action
3. **可解释输出** — 每步计算过程可追溯
4. **DAG 构建** — 规则依赖图，检测循环 **[目标设计，未实现]**
5. **回滚机制** — 规则执行失败回滚上下文 **[目标设计，未实现]**

---

## 2. 当前实现 (RuleExecutor)

**实际代码**: `ontology_engine/engine/rule/executor.py`

当前执行引擎为 `RuleExecutor`，采用 **priority 降序排序** 的顺序执行模型，而非设计目标中的 DAG 驱动模型。

```python
class RuleExecutor:
    """规则执行器 — 顺序执行模型"""

    async def execute_dimension(
        self,
        dimension: str,
        entity_id: str,
        entity_data: dict,
        category_tags: CategoryTags | None = None,
        precomputed_metrics: dict | None = None
    ) -> AnalysisResult:
        # 1. 筛选适用规则
        applicable_rules = self._filter_rules(dimension, entity_data, category_tags)

        # 2. 按 priority 排序（非 DAG 拓扑）
        applicable_rules.sort(key=lambda r: -r.priority)

        # 3. 顺序执行规则
        for rule in applicable_rules:
            result = await self._execute_rule(rule, context)
            ...
```

### 当前实现特性

| 特性 | 状态 |
|------|------|
| priority 排序执行 | ✅ 已实现 |
| 条件评估 (when/all_of/any_of) | ✅ 已实现 |
| 算子调用 | ✅ 已实现 |
| 计算指标传递 | ✅ 已实现 |
| 异常容错 (单条失败不影响后续) | ✅ 已实现 |
| DAG 拓扑执行 | ❌ 未实现 (2026-04-16) |
| 循环依赖检测 | ❌ 未实现 (2026-04-16) |
| 状态回滚 | ❌ 未实现 (2026-04-16) |

---

## 3. 规则模型状态 (ADR-008)

**Schema 层**: `ontology_engine/engine/rule/models.py` 已定义 `RuleDefinition` + `RuleLogic` 分离结构。

**执行层**: `RuleExecutor` 未使用 `RuleLogic`，仍直接读取 `RuleDefinition.when/then/else_`。

| 组件 | 代码路径 | 状态 |
|------|----------|------|
| `RuleDefinition` | `models.py` | ✅ 已实现 (含 `logic_ids` 字段) |
| `RuleLogic` | `models.py` | ✅ 已定义 (含 `steps` DAG 字段) |
| `RuleLogic` 被 `RuleExecutor` 引用 | `executor.py` | ❌ 未使用 (2026-04-16) |

---

## 4. 算子体系 (已完整实现)

**代码路径**: `ontology_engine/engine/rule/operators/`

当前已实现 16 个算子，覆盖 flag、compute、switch、alert、graph 等类别：

| 算子 | 文件 | 用途 |
|------|------|------|
| `SetFlagOperator` | `set_flag.py` | 设置标志 |
| `ApproveEligibilityOperator` | `set_flag.py` | 批准资格 |
| `RejectEligibilityOperator` | `set_flag.py` | 拒绝资格 |
| `ComputeFormulaOperator` | `compute.py` | 公式计算 |
| `CalculateCreditScoreOperator` | `compute.py` | 信用评分 |
| `CalculateCreditLimitOperator` | `compute.py` | 信用额度 |
| `DetermineInterestRateOperator` | `compute.py` | 利率定价 |
| `SwitchOperator` | `switch.py` | 多分支选择 |
| `BinningOperator` | `switch.py` | 分箱 |
| `ScorecardOperator` | `switch.py` | 评分卡 |
| `TriggerAlertOperator` | `alert.py` | 触发预警 |
| `GraphTraversalOperator` | `alert.py` | 图遍历 |
| `DecisionTableOperator` | `decision_table.py` | 决策表 |
| `LLMJudgeOperator` | `llm_judge.py` | LLM 判断 |
| `WeightedSumOperator` | `weighted_sum.py` | 加权求和 |

---

## 5. 目标设计 (RuleEngine DAG驱动) **[待实现]**

以下内容为 Phase 2 目标设计，当前代码尚未实现：

```python
class RuleEngine:
    """规则引擎 — DAG 驱动的规则执行 (目标设计)"""

    def __init__(...):
        self._rule_defs = {r.id: r for r in schema.rules}
        self._dag = self._build_dag()

    async def execute_dimension(self, ...):
        # 1. 筛选规则
        applicable_rules = self._filter_rules(...)
        # 2. 构建子 DAG 并拓扑排序
        execution_order = self._topological_sort(applicable_rules)
        # 3. 顺序执行...
```

### 目标设计组件

| 组件 | 文件 | 状态 |
|------|------|------|
| `RuleEngine` (DAG驱动) | `engine.py` | ⏭️ 待实现 |
| `RuleDAG` | `dag.py` | ⏭️ 待实现 |
| `action_executor.py` | 独立模块 | ⏭️ 待实现 (当前已内联到 `executor.py`) |

---

## 6. 文件结构

### 当前实现

```
ontology_engine/engine/rule/
├── __init__.py            # 导出 RuleExecutor, OperatorRegistry
├── executor.py            # RuleExecutor 主类 (当前实现)
├── models.py              # ExecutionContext, RuleResult, AnalysisResult, Alert
├── evaluator.py           # 条件评估
├── operators/
│   ├── __init__.py
│   ├── base.py            # Operator 基类, OperatorRegistry
│   ├── set_flag.py
│   ├── compute.py
│   ├── switch.py
│   ├── alert.py
│   ├── decision_table.py
│   ├── llm_judge.py
│   └── weighted_sum.py
```

### 目标设计

```
ontology_engine/engine/rule/
├── __init__.py
├── engine.py              # RuleEngine 主类 (DAG驱动)
├── dag.py                 # RuleDAG 构建
├── models.py
├── evaluator.py
├── action_executor.py     # 动作执行 + 算子调度
└── operators/
    └── ...
```

---

## 7. 代码映射

| 设计组件 | 实际代码路径 | 实现状态 |
|---------|-------------|---------|
| RuleEngine (DAG驱动) | `engine/rule/engine.py` | ⏭️ 待实现 |
| RuleExecutor (顺序执行) | `engine/rule/executor.py` | ✅ 已实现 |
| ExecutionContext | `engine/rule/models.py` | ✅ 已实现 |
| AnalysisResult | `engine/rule/models.py` | ✅ 已实现 |
| OperatorRegistry | `engine/rule/operators/base.py` | ✅ 已实现 |
| 16 个内置算子 | `engine/rule/operators/*.py` | ✅ 已实现 |
| RuleDAG | `engine/rule/dag.py` | ⏭️ 待实现 |
| 回滚机制 | - | ⏭️ 待实现 |

---

## 8. 测试要点

- [ ] 规则执行测试 - 单条规则的完整执行流程
- [ ] 条件评估测试 - 表达式条件评估 (when 子句)
- [ ] allOf 条件测试 - 逻辑与条件组合
- [ ] anyOf 条件测试 - 逻辑或条件组合
- [ ] then 动作执行测试 - 条件满足时执行动作
- [ ] else 动作执行测试 - 条件不满足时执行动作
- [ ] 优先级排序测试 - 规则按 priority 降序执行
- [ ] 维度筛选测试 - 按 dimension 筛选适用规则
- [ ] 实体类型筛选测试 - 按 entity_types 筛选适用规则
- [ ] 禁用规则跳过测试 - enabled=false 的规则不执行
- [ ] 计算指标传递测试 - 规则输出注入执行上下文
- [ ] 各算子单元测试
- [ ] 规则执行异常处理测试 - 单条规则失败不影响后续规则
- [ ] 决策结果判定测试

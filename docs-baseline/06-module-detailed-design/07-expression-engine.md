# 模块 07: 表达式引擎 (ExpressionEngine)

> **位置**: `ontology_engine/engine/expression/`
> **依赖**: simpleeval, asteval (fallback)
> **被依赖**: MetricEngine, RuleEngine, CategorizationEngine
> **状态**: 当前实现满足 Phase 1，与目标设计存在偏差
> **最后核验**: 2026-04-16

---
status: current+target
phase: phase1
last_verified: "2026-04-16"
verified_against: ontology_engine/engine/expression/engine.py
---

## 1. 职责

1. **表达式求值** — 基于 simpleeval 的安全表达式执行
2. **内置函数库** — 数学/日期/空值检查（有限函数集）
3. **字段解析** — 支持嵌套字段（如 `registered_capital.value`）
4. **关键字预处理** — SQL 风格关键字转 Python 语法
5. **L0/L1 两级安全执行** — **[目标设计，未实现]**
6. **完整内置函数库** — **[目标设计，未实现]**
7. **超时保护** — **[目标设计，未实现]**

## 2. 当前实现 [单一事实源]

### 实际代码

位于 `ontology_engine/engine/expression/engine.py`：

```python
class ExpressionEngine:
    """基于 simpleeval 的安全表达式引擎."""

    _KNOWN_FUNCTIONS = frozenset({
        "today", "days_between", "days_since", "is_null",
        "max", "min", "round", "abs", "clamp",
        "int", "float", "bool",
    })

    def evaluate(self, expression: str, context: Mapping[str, Any]) -> Any:
        # 1. 预处理表达式（关键字转换）
        # 2. 字段解析（嵌套字段支持）
        # 3. 使用 simpleeval 执行
        # 4. simpleeval 失败时 fallback 到 asteval
```

### 当前实现特性

| 特性 | 状态 |
|------|------|
| simpleeval 表达式求值 | ✅ 已实现 |
| asteval fallback (含 AST 能力) | ✅ 已实现 |
| 嵌套字段解析 | ✅ 已实现 |
| SQL 关键字预处理 (AND/OR/NOT/IS NULL) | ✅ 已实现 |
| 独立 L0 执行器 | ❌ 未实现 (2026-04-16) |
| 独立 L1 AST 沙箱执行器 | ❌ 未实现 (2026-04-16) |
| 自动执行器调度 | ❌ 未实现 (2026-04-16) |
| 资源限制 (超时/循环/内存) | ❌ 未实现 (2026-04-16) |

### 当前内置函数

| 类别 | 已实现 | 缺失 (目标设计) |
|------|--------|-----------------|
| 数学 | abs, min, max, round, clamp | floor, ceil, pow, sqrt |
| 日期 | today, days_between, days_since | now, months_between, years_between, add_days, day_of_week, is_weekend |
| 字符串 | - | len, upper, lower, contains, starts_with, ends_with |
| 聚合 | - | sum, avg, count, std |
| 类型 | int, float, bool | str, decimal |
| 工具 | - | COALESCE |

**总计**: 文档要求 ~39 函数，当前实现 12 函数。

## 3. 目标设计: 两级执行模型 [待扩展]

> 以下内容属于 Phase 2 目标设计，当前代码尚未实现。

```
表达式字符串
    │
    ▼
词法分析 → 检测控制流关键词 (if, for, while, def)
    │
    ├── 无控制流 → L0: SimpleEvalExecutor
    │               快速、安全、无副作用
    │
    └── 有控制流 → L1: ASTSandboxExecutor
                    AST 白名单 + 资源限制 + 超时
```

### 目标架构

```
ontology_engine/engine/expression/
├── __init__.py
├── engine.py               # ExpressionEngine 主类（调度器）
├── l0_simpleeval.py        # L0: SimpleEvalExecutor
├── l1_ast_sandbox.py       # L1: ASTSandboxExecutor
├── functions.py            # 内置函数库
├── errors.py               # 错误类型
└── validators.py           # 表达式静态校验
```

## 4. 供应链金融表达式示例

```python
from ontology_engine.engine.expression.engine import ExpressionEngine

engine = ExpressionEngine()

# 算术
engine.evaluate("registered_capital.value * 0.5", context)
# → 2500000

# 比较
engine.evaluate("credit_score >= 60", context)
# → True

# 逻辑（支持 SQL 风格关键字）
engine.evaluate(
    "status == 'ACTIVE' AND registered_capital.value >= 1000000",
    context
)
# → True

# 函数
days = engine.evaluate(
    "days_between(establishment_date, today())",
    context
)
# → 2920

# 空值检查
engine.evaluate(
    "registered_capital.value IS NOT NULL",
    context
)
# → True
```

**当前不支持**: 多行表达式、if/elif/else 控制流、变量赋值、循环结构、字符串函数。

## 5. 代码映射

| 设计组件 | 实际代码路径 | 实现状态 |
|---------|-------------|---------|
| ExpressionEngine | `engine/expression/engine.py` | ✅ 已实现 |
| 关键字预处理 | `engine/expression/engine.py` | ✅ 已实现 |
| 嵌套字段解析 | `engine/expression/engine.py` | ✅ 已实现 |
| L0 执行器 (SimpleEval) | `engine/expression/engine.py` (内联) | ⚠️ 部分实现 |
| L1 执行器 (AST沙箱) | asteval fallback | ⚠️ 部分实现 |
| 完整函数库 | - | ❌ 未实现 |
| 资源限制 | - | ❌ 未实现 |

## 6. 测试要点

- [ ] 简单表达式求值测试 - 算术运算
- [ ] 比较表达式测试
- [ ] 逻辑表达式测试 - AND、OR、NOT
- [ ] 嵌套字段访问测试
- [ ] IS NULL / IS NOT NULL 判断测试
- [ ] 日期函数测试
- [ ] 数学函数测试
- [ ] 类型转换测试
- [ ] 无效表达式错误测试
- [ ] 缺失字段处理测试
- [ ] 字符串范围保护测试

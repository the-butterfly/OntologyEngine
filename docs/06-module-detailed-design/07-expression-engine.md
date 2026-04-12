# 模块 07: 表达式引擎 (ExpressionEngine)

> **位置**: `ontology_engine/engine/expression/`
> **依赖**: simpleeval
> **被依赖**: MetricEngine, RuleEngine, CategorizationEngine
> **[单一事实源]**: 本文描述的是目标设计，当前实现请核对 `ontology_engine/engine/expression/engine.py`
> **[关键设计点]**: 表达式执行能力的当前态 / 目标态差异统一在 `docs/04-migration-and-gap/README.md` 跟踪

---
status: design
phase: target
last_verified: "2026-04-12"
verified_against: ontology_engine/engine/expression/engine.py
---

## 1. 职责

### 当前实现 (Current)

1. **表达式求值** — 基于 simpleeval 的安全表达式执行
2. **内置函数库** — 数学/日期/空值检查（有限函数集）
3. **字段解析** — 支持嵌套字段（如 `registered_capital.value`）
4. **关键字预处理** — SQL 风格关键字转 Python 语法

### 目标设计 (Target) **[待扩展]**

1. **两级安全执行** — L0 simpleeval (简单表达式) + L1 AST 沙箱 (复杂逻辑)
2. **完整内置函数库** — 数学/字符串/日期/聚合
3. **字段白名单** — 只允许访问合法数据源
4. **超时保护** — 单条表达式执行超时

## 2. 当前实现 **[单一事实源]**

### ExpressionEngine 类

位于 `ontology_engine/engine/expression/engine.py`：

```python
class ExpressionEngine:
    """基于 simpleeval 的安全表达式引擎."""
    
    _KNOWN_FUNCTIONS = frozenset({
        "today", "days_between", "is_null",
        "max", "min", "round", "abs",
        "int", "float", "bool",
    })
    
    def evaluate(self, expression: str, context: Mapping[str, Any]) -> Any:
        # 1. 预处理表达式（关键字转换）
        # 2. 字段解析（嵌套字段支持）
        # 3. 使用 simpleeval 执行
```

**关键特性：**
- 单行表达式，不支持多行或复杂控制流
- 支持的关键字：today, days_between, is_null, max, min, round, abs, int, float, bool
- 表达式预处理：IS NULL/IS NOT NULL → is_null(), AND/OR/NOT → and/or/not
- 字段解析：支持嵌套字段（如 `registered_capital.value`）

---

## 3. 两级执行模型 (决策 #10) **[待扩展]**

> **[待扩展]**: 目标设计，尚未实现

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

## 4. 核心接口（目标设计） **[待扩展]**

```python
# engine/expression/engine.py

class ExpressionEngine:
    """表达式引擎 — 两级安全执行"""
    
    # 控制流关键词 → 触发 L1 沙箱
    CONTROL_FLOW_KEYWORDS = {"if", "for", "while", "def", "class", "try", "with", "elif", "else"}
    
    def __init__(self):
        self.l0_executor = SimpleEvalExecutor()
        self.l1_executor = ASTSandboxExecutor(
            whitelist=AST_WHITELIST,
            max_loop_iterations=1000,
            timeout_seconds=5
        )
    
    def evaluate(self, expression: str, context: dict) -> Any:
        """评估表达式 — 自动选择执行器"""
        expression = expression.strip()
        
        if not expression:
            return None
        
        executor = self._select_executor(expression)
        
        try:
            return executor.evaluate(expression, context)
        except Exception as e:
            raise ExpressionError(
                f"表达式执行失败: {expression}",
                expression=expression,
                original_error=e
            )
    
    def _select_executor(self, expression: str) -> FormulaExecutor:
        """选择执行器
        
        启发式规则:
        - 包含 if/for/while 等关键词 → L1
        - 包含 return 语句 → L1
        - 包含多行 → L1
        - 其他 → L0
        """
        tokens = set(self._tokenize(expression))
        
        if tokens & self.CONTROL_FLOW_KEYWORDS:
            return self.l1_executor
        
        if "return" in tokens:
            return self.l1_executor
        
        if "\n" in expression:
            return self.l1_executor
        
        return self.l0_executor
    
    def _tokenize(self, expression: str) -> set[str]:
        """简单词法分析"""
        import re
        return set(re.findall(r'\b\w+\b', expression))
```

## 5. L0: SimpleEvalExecutor（目标设计） **[待扩展]**

```python
# engine/expression/l0_simpleeval.py

from simpleeval import simple_eval, EvalWithCompoundTypes

class SimpleEvalExecutor:
    """L0: 基于 simpleeval 的简单表达式执行器
    
    适用于:
    - 算术: registered_capital.value * 0.5
    - 比较: credit_score >= 60
    - 逻辑: status == 'ACTIVE' AND credit_score >= 60
    - 函数: min(a, b), days_between(d1, d2)
    """
    
    # 安全函数白名单
    SAFE_FUNCTIONS = {
        # 数学
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sum": sum,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        
        # 日期
        "today": lambda: date.today().isoformat(),
        "now": lambda: datetime.now().isoformat(),
        "days_between": _days_between,
        "months_between": _months_between,
        "years_between": _years_between,
        "add_days": _add_days,
        
        # 工具
        "COALESCE": lambda *args: next((a for a in args if a is not None), None),
    }
    
    def evaluate(self, expression: str, context: dict) -> Any:
        """执行简单表达式"""
        # 预处理表达式
        expression = self._preprocess(expression)
        
        evaluator = EvalWithCompoundTypes()
        evaluator.names = context
        evaluator.functions = self.SAFE_FUNCTIONS
        
        try:
            return evaluator.eval(expression)
        except Exception as e:
            raise ExpressionError(f"L0 执行失败: {e}", expression=expression)
    
    def _preprocess(self, expression: str) -> str:
        """预处理表达式
        
        转换:
        - IS NULL → == None
        - IS NOT NULL → != None
        - AND → and
        - OR → or
        - IN → in (需要特殊处理)
        """
        # 逻辑运算符转换
        expression = expression.replace(" AND ", " and ")
        expression = expression.replace(" OR ", " or ")
        expression = expression.replace(" NOT ", " not ")
        
        # 空值检查
        expression = expression.replace(" IS NULL", " == None")
        expression = expression.replace(" IS NOT NULL", " != None")
        
        return expression


# ===== 日期工具函数 =====

def _days_between(d1, d2) -> int:
    """天数差"""
    if isinstance(d1, str):
        d1 = date.fromisoformat(d1)
    if isinstance(d2, str):
        d2 = date.fromisoformat(d2)
    if isinstance(d1, datetime):
        d1 = d1.date()
    if isinstance(d2, datetime):
        d2 = d2.date()
    return abs((d2 - d1).days)

def _months_between(d1, d2) -> int:
    """月数差"""
    if isinstance(d1, str):
        d1 = date.fromisoformat(d1)
    if isinstance(d2, str):
        d2 = date.fromisoformat(d2)
    return abs((d2.year - d1.year) * 12 + d2.month - d1.month)

def _years_between(d1, d2) -> int:
    """年数差"""
    if isinstance(d1, str):
        d1 = date.fromisoformat(d1)
    if isinstance(d2, str):
        d2 = date.fromisoformat(d2)
    return abs(d2.year - d1.year)

def _add_days(d, n):
    """日期加减"""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return (d + timedelta(days=int(n))).isoformat()
```

## 6. L1: ASTSandboxExecutor（目标设计） **[待扩展]**

```python
# engine/expression/l1_ast_sandbox.py

import ast
import signal
from contextlib import contextmanager

# AST 白名单 — 只允许安全的节点类型
AST_WHITELIST = {
    # 模块
    ast.Module, ast.Expr,
    # 字面量
    ast.Constant, ast.Num, ast.Str, ast.NameConstant,
    # 名称
    ast.Name, ast.Load, ast.Store,
    # 运算
    ast.UnaryOp, ast.BinOp, ast.BoolOp, ast.Compare,
    ast.UAdd, ast.USub, ast.Not, ast.Invert,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv, ast.Pow,
    ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn,
    # 控制流 (受限制)
    ast.If, ast.IfExp, ast.For,
    # 函数调用 (仅白名单函数)
    ast.Call, ast.keyword,
    # 赋值 (受限)
    ast.Assign, ast.AugAssign,
    # 返回
    ast.Return,
    # 容器
    ast.List, ast.Tuple, ast.Dict, ast.Set,
    # 索引
    ast.Subscript, ast.Index, ast.Slice, ast.Attribute,
}

# 禁止的 AST 节点
AST_BLACKLIST = {
    ast.Import, ast.ImportFrom,       # 不允许 import
    ast.Exec, ast.Global, ast.Nonlocal, # 不允许 exec/global
    ast.ClassDef,                       # 不允许定义类
    ast.Try, ast.ExceptHandler,         # Phase 1 不允许 try/except
    ast.While,                          # 不允许 while (防止死循环)
    ast.Lambda,                         # 不允许 lambda
    ast.Yield, ast.YieldFrom,           # 不允许生成器
}


class ASTSandboxExecutor:
    """L1: AST 白名单沙箱执行器
    
    适用于:
    - 条件分支: if ... : score += 10
    - 循环: for i in range(10): ...
    - 多行计算: business_stability_score 的复杂计算逻辑
    """
    
    def __init__(
        self,
        whitelist: set = AST_WHITELIST,
        max_loop_iterations: int = 1000,
        timeout_seconds: int = 5
    ):
        self.whitelist = whitelist
        self.max_loop_iterations = max_loop_iterations
        self.timeout_seconds = timeout_seconds
    
    def evaluate(self, expression: str, context: dict) -> Any:
        """在沙箱中执行表达式"""
        # 1. 解析 AST
        try:
            tree = ast.parse(expression, mode='exec')
        except SyntaxError as e:
            raise ExpressionSyntaxError(f"语法错误: {e}", expression=expression)
        
        # 2. AST 白名单校验
        self._validate_ast(tree)
        
        # 3. 带资源限制的执行
        return self._execute_with_limits(tree, context)
    
    def _validate_ast(self, tree: ast.AST):
        """AST 白名单校验"""
        for node in ast.walk(tree):
            node_type = type(node)
            
            if node_type in AST_BLACKLIST:
                raise FormulaSandboxViolation(
                    f"禁止的 AST 节点: {node_type.__name__}",
                    node_type=node_type.__name__
                )
            
            if node_type not in self.whitelist:
                raise FormulaSandboxViolation(
                    f"不在白名单中的 AST 节点: {node_type.__name__}",
                    node_type=node_type.__name__
                )
    
    def _execute_with_limits(self, tree: ast.AST, context: dict) -> Any:
        """带资源限制的执行"""
        # 构建安全的执行命名空间
        safe_globals = {
            "__builtins__": {},  # 禁用所有内建函数
            "True": True,
            "False": False,
            "None": None,
        }
        
        safe_locals = dict(context)
        
        # 注入安全函数
        safe_locals.update(SimpleEvalExecutor.SAFE_FUNCTIONS)
        
        # 循环计数器
        loop_counter = [0]
        original_range = range
        
        def safe_range(*args, **kwargs):
            r = original_range(*args, **kwargs)
            if len(r) > self.max_loop_iterations:
                raise FormulaTimeoutError(f"循环次数超过限制: {self.max_loop_iterations}")
            return r
        
        safe_locals["range"] = safe_range
        
        # 超时保护
        try:
            code = compile(tree, '<sandbox>', 'exec')
            exec(code, safe_globals, safe_locals)
            
            # 返回最后一个表达式的值
            # 如果有 return 语句，结果在 __return 中
            if "__return" in safe_locals:
                return safe_locals["__return"]
            
            # 否则返回 None (执行了赋值等副作用)
            return safe_locals.get("result", None)
            
        except RecursionError:
            raise FormulaTimeoutError("递归深度超限")
        except Exception as e:
            raise ExpressionError(f"沙箱执行失败: {e}", expression=str(tree))


# ===== 错误类型 =====

class ExpressionError(Exception):
    """表达式错误基类"""
    def __init__(self, message: str, expression: str = "", original_error: Exception | None = None):
        super().__init__(message)
        self.expression = expression
        self.original_error = original_error

class ExpressionSyntaxError(ExpressionError):
    """语法错误"""

class FormulaSandboxViolation(ExpressionError):
    """沙箱安全约束违反"""
    def __init__(self, message: str, node_type: str = ""):
        super().__init__(message)
        self.node_type = node_type

class FormulaTimeoutError(ExpressionError):
    """执行超时"""

class UnknownFunctionError(ExpressionError):
    """未定义函数"""

class FieldAccessDeniedError(ExpressionError):
    """字段访问被拒绝"""
```

## 7. 供应链金融表达式示例

```python
# 当前实现（已验证）
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

# 空值检查（支持 SQL 风格语法）
engine.evaluate(
    "registered_capital.value IS NOT NULL", 
    context
)
# → True（内部转换为 not is_null(registered_capital.value)）

# L1 复杂逻辑（目标设计） **[待扩展]**
# 以下语法当前不支持：
# - 多行表达式
# - if/elif/else 控制流
# - 变量赋值
# - 循环结构
```

## 8. 文件结构

### 当前实现 **[单一事实源]**

```
ontology_engine/engine/expression/
├── __init__.py             # 导出 ExpressionEngine
└── engine.py               # ExpressionEngine 主类（含所有实现）
```

**实际代码核验** (`ontology_engine/engine/expression/engine.py`):
- 单一 `ExpressionEngine` 类实现
- 无分离的 L0/L1 执行器
- 无 ASTSandboxExecutor 实现

### 目标设计 **[待扩展]**

```
ontology_engine/engine/expression/
├── __init__.py             # 导出 ExpressionEngine
├── engine.py               # ExpressionEngine 主类（调度器）
├── l0_simpleeval.py        # L0: SimpleEvalExecutor
├── l1_ast_sandbox.py       # L1: ASTSandboxExecutor **[待扩展]**
├── functions.py            # 内置函数库 (日期/数学/字符串)
├── errors.py               # 错误类型
└── validators.py           # 表达式静态校验
```

**状态**: 目标设计，文件拆分和 AST 沙箱待实现。

## 9. 代码映射

| 设计组件 | 实际代码路径 | 实现状态 |
|---------|-------------|---------|
| ExpressionEngine | `ontology_engine/engine/expression/engine.py` | ✅ 已实现 |
| ExpressionSyntaxError | `ontology_engine/engine/expression/engine.py` | ✅ 已实现 |
| L0 执行器 (SimpleEval) | `ontology_engine/engine/expression/engine.py` | ✅ 已实现 (内联实现) |
| L1 执行器 (AST沙箱) | `ontology_engine/engine/expression/l1_ast_sandbox.py` | ⏭️ 待实现 |
| SimpleEvalExecutor | `ontology_engine/engine/expression/l0_simpleeval.py` | ⏭️ 待实现 (设计目标) |
| ASTSandboxExecutor | `ontology_engine/engine/expression/l1_ast_sandbox.py` | ⏭️ 待实现 (设计目标) |
| 内置函数库 | `ontology_engine/engine/expression/engine.py` | ⚠️ 部分实现 |
| 错误类型定义 | `ontology_engine/engine/expression/errors.py` | ⏭️ 待实现 (已内联) |
| 表达式校验器 | `ontology_engine/engine/expression/validators.py` | ⏭️ 待实现 |

## 10. 测试要点

- [ ] 简单表达式求值测试 - 算术运算
- [ ] 比较表达式测试 - 大于、小于、等于
- [ ] 逻辑表达式测试 - AND、OR、NOT
- [ ] 嵌套字段访问测试 - 如 `supplier.registered_capital.value`
- [ ] IS NULL 判断测试 - 空值检查
- [ ] IS NOT NULL 判断测试 - 非空检查
- [ ] 字符串字面量测试 - 单引号和双引号
- [ ] 日期函数测试 - `today()` 函数
- [ ] 日期差计算测试 - `days_between()` 函数
- [ ] 数学函数测试 - `min()`, `max()`, `round()`, `abs()`
- [ ] 类型转换测试 - `int()`, `float()`, `bool()`
- [ ] 空表达式处理测试 - 返回 True
- [ ] 空值表达式处理测试 - 返回 True
- [ ] 公式结果返回测试 - 非布尔表达式返回计算值
- [ ] 无效表达式错误测试 - 语法错误抛出 ExpressionSyntaxError
- [ ] 缺失字段处理测试 - 访问不存在的字段返回 None
- [ ] 字符串范围保护测试 - 关键字替换不影响字符串内容
- [ ] 日期解析测试 - 多种日期格式解析
- [ ] 复杂嵌套路径测试 - 多级属性访问
- [ ] ExpressionEvaluator 包装器测试 - 规则条件评估
- [ ] RuleWhen 对象评估测试 - allOf/anyOf 条件
- [ ] 字典条件评估测试 - allOf/anyOf 字典格式

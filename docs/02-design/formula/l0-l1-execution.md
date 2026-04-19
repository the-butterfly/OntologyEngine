---
status: draft
phase: rewrite
source_of_truth: docs/02-design/formula/README.md
last_verified: "2026-04-19"
verified_against: code@ontology_engine/engine/expression/engine.py
---

# L0/L1 两级执行模型

> **[关键设计点]**: Formula 表达式执行的核心架构决策
> **上游**: `docs/02-design/formula/README.md`
> **代码实现**: `ontology_engine/engine/expression/engine.py`

## 目的

定义 Formula 表达式的两级执行模型，根据表达式复杂度自动选择执行器，在安全性和性能之间取得平衡。

## 解决的问题

| # | 问题 | 现状 | 本文档解决 |
|---|------|------|-----------|
| 1 | **无分级执行** | simpleeval 失败后无条件 fallback 到 asteval | 按控制流关键词自动选择 L0 或 L1 |
| 2 | **L1 无安全校验** | asteval fallback 无 AST 白名单校验，存在安全风险 | L1 必须经过 AST 白名单校验 |
| 3 | **L1 无资源限制** | asteval 执行无循环次数和超时限制 | L1 强制 max_loop_iterations + timeout_seconds |
| 4 | **错误信息丢失** | asteval 错误被包装为 ExpressionSyntaxError | 按语义细分错误类型 |

## 执行模型总览

```
evaluate(expression, context)
         │
         ▼
  ┌──────────────────────┐
  │  _select_executor()  │
  │  检测控制流关键词      │
  └──────┬───────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  L0         L1
  SimpleEval  ASTSandbox
  快速路径    安全沙箱
```

## L0: SimpleEvalExecutor

### 定位

基于 `simpleeval` 的快速执行器，适用于**无控制流的单行表达式**。

### 特征

| 维度 | 值 |
|------|---|
| 执行器 | `simpleeval.SimpleEval` |
| 适用表达式 | 单行、无控制流 |
| 安全机制 | 运算符白名单 + 函数白名单 + 名称白名单 |
| 典型延迟 | < 1ms |
| 支持语法 | 算术 / 比较 / 逻辑 / 函数调用 / 字段引用 |

### SAFE_FUNCTIONS 白名单

L0 执行器只允许调用以下函数，任何未在白名单中的函数调用将被拒绝：

```python
SAFE_FUNCTIONS = frozenset({
    "today", "now", "days_between", "days_since",
    "months_between", "years_between", "add_days",
    "is_null", "coalesce", "clamp",
    "max", "min", "round", "abs", "int", "float", "bool", "str",
    "len", "upper", "lower", "trim", "contains",
    "starts_with", "ends_with", "replace", "substring",
    "sum", "avg", "count",
    "if_expr",
})
```

### 运算符限制

L0 禁用以下运算符（已在当前代码中实现）：

| 禁用运算符 | AST 节点 | 原因 |
|-----------|----------|------|
| `<<` | `ast.LShift` | 无业务场景 |
| `>>` | `ast.RShift` | 无业务场景 |
| `&` | `ast.BitAnd` | 无业务场景 |
| `\|` | `ast.BitOr` | 无业务场景 |
| `^` | `ast.BitXor` | 无业务场景 |
| `%` | `ast.Mod` | 使用 `mod()` 函数替代 |

### 关键词预处理

L0 执行前对表达式进行关键词转换（已在当前代码中实现）：

| 原始关键词 | 转换后 | 说明 |
|-----------|--------|------|
| `AND` | `and` | 逻辑与 |
| `OR` | `or` | 逻辑或 |
| `NOT` | `not` | 逻辑非 |
| `true` | `True` | 布尔真 |
| `false` | `False` | 布尔假 |
| `null` / `none` | `None` | 空值 |
| `field IS NULL` | `is_null(field)` | 空值判断 |
| `field IS NOT NULL` | `not is_null(field)` | 非空判断 |

预处理仅在字符串字面量之外执行，避免误替换字符串内容。

### 字段解析

嵌套字段通过点号访问，解析时从 context 中取值并替换为字面量：

```
registered_capital.value → context["registered_capital"]["value"] → 5000000
address.province → context["address"]["province"] → "北京市"
```

## L1: ASTSandboxExecutor

### 定位

基于 `asteval` + AST 白名单校验的沙箱执行器，适用于**包含控制流的复杂表达式**。

### 特征

| 维度 | 值 |
|------|---|
| 执行器 | `asteval.Interpreter` + AST 白名单 |
| 适用表达式 | 多行、含控制流（if/for/while） |
| 安全机制 | AST 白名单校验 + 资源限制 + 函数白名单 |
| 典型延迟 | 1-50ms |
| 支持语法 | L0 全部 + if/elif/else / for 循环 / 赋值 |

### 触发条件

当表达式包含以下**控制流关键词**时，自动选择 L1 执行器：

```python
CONTROL_FLOW_KEYWORDS = {"if", "for", "while", "def", "class", "try", "with"}
```

检测逻辑：对表达式进行 token 化，若 token 集合与 `CONTROL_FLOW_KEYWORDS` 有交集，则选择 L1。

### AST 白名单

L1 执行前对表达式 AST 进行白名单校验，仅允许以下节点类型：

| 类别 | 允许的 AST 节点 |
|------|----------------|
| 模块 | `ast.Module`, `ast.Expression` |
| 语句 | `ast.Assign`, `ast.AugAssign`, `ast.Expr`, `ast.Return` |
| 控制流 | `ast.If`, `ast.For`, `ast.While`, `ast.Break`, `ast.Continue` |
| 运算 | `ast.BoolOp`, `ast.BinOp`, `ast.UnaryOp`, `ast.Compare` |
| 数据 | `ast.Constant`, `ast.Name`, `ast.Attribute`, `ast.Subscript` |
| 调用 | `ast.Call` |
| 容器 | `ast.List`, `ast.Tuple`, `ast.Dict`, `ast.Set` |
| 索引 | `ast.Index`, `ast.Slice` |

**禁止的 AST 节点**（部分）：

| 禁止节点 | 原因 |
|----------|------|
| `ast.Import`, `ast.ImportFrom` | 防止导入模块 |
| `ast.Exec`, `ast.Eval` | 防止动态执行 |
| `ast.ClassDef`（非关键词触发时） | 防止类定义 |
| `ast.FunctionDef` | 防止函数定义（仅允许调用白名单函数） |
| `ast.Global`, `ast.Nonlocal` | 防止作用域逃逸 |
| `ast.Try` | 防止异常捕获绕过安全检查 |
| `ast.With` | 防止上下文管理器滥用 |

### 资源限制

| 限制项 | 默认值 | 说明 |
|--------|--------|------|
| `max_loop_iterations` | 1000 | 单个循环最大迭代次数 |
| `timeout_seconds` | 5 | 单次执行最大超时时间 |
| `max_ast_depth` | 20 | AST 最大嵌套深度 |
| `max_assignments` | 50 | 最大赋值语句数 |

### L1 执行流程

```
1. AST 解析
   tree = ast.parse(expression)
   ↓
2. AST 白名单校验
   _validate_ast(tree) → 失败抛出 FormulaSecurityError
   ↓
3. AST 深度检查
   _check_depth(tree) → 失败抛出 FormulaSecurityError
   ↓
4. 注入安全函数和上下文
   interpreter.symtable.update(SAFE_FUNCTIONS)
   interpreter.symtable.update(context)
   ↓
5. 带超时执行
   _execute_with_limits(tree, context) → 超时抛出 FormulaTimeoutError
   ↓
6. 返回结果
```

## 自动选择逻辑

### 选择算法

```python
def _select_executor(self, expression: str) -> FormulaExecutor:
    if "\n" in expression or "\r" in expression:
        return self._l1_executor

    tokens = set(self._tokenize(expression))
    if tokens & self.CONTROL_FLOW_KEYWORDS:
        return self._l1_executor

    return self._l0_executor
```

### 选择规则

| 条件 | 选择 | 原因 |
|------|------|------|
| 表达式含换行符 | L1 | 多行表达式通常含控制流 |
| 表达式含控制流关键词 | L1 | 需要沙箱环境执行 |
| 其他 | L0 | 简单表达式快速执行 |

### 示例

| 表达式 | 选择 | 原因 |
|--------|------|------|
| `credit_score >= 60` | L0 | 单行、无控制流 |
| `registered_capital * 0.5` | L0 | 单行、无控制流 |
| `if score >= 80: result = 20\nelse: result = 0` | L1 | 含 if 控制流 |
| `total = 0\nfor x in items: total += x` | L1 | 含 for 控制流 |

## 错误类型体系

### 错误层次

```
FormulaError (基类)
├── FormulaSyntaxError      # 语法错误
├── FormulaSecurityError    # 安全违规
├── FormulaTimeoutError     # 执行超时
├── FormulaTypeError        # 类型错误
└── FormulaNameError        # 未定义引用
```

### 错误定义

| 错误类型 | 触发条件 | 所属执行器 | 处理建议 |
|----------|----------|-----------|---------|
| `FormulaSyntaxError` | 非法字符、括号不匹配、语法错误 | L0/L1 | 修正表达式语法 |
| `FormulaSecurityError` | AST 节点不在白名单、禁止的操作 | L1 | 简化表达式或使用算子 |
| `FormulaTimeoutError` | 执行超过 timeout_seconds | L1 | 优化表达式或增加超时 |
| `FormulaTypeError` | 类型不兼容（字符串+数字等） | L0/L1 | 检查字段类型 |
| `FormulaNameError` | 字段不存在、函数未定义 | L0/L1 | 检查字段名和函数名 |

### 错误信息格式

```
FormulaSyntaxError: Invalid expression 'credit_score >='
  expression: "credit_score >="
  position: 15
  message: "unexpected end of expression"

FormulaSecurityError: Disallowed AST node: Import
  expression: "import os"
  node_type: "Import"
  message: "import statements are not allowed"

FormulaTimeoutError: Expression execution timed out
  expression: "for i in range(100000): ..."
  timeout_seconds: 5
  message: "execution exceeded 5 seconds"
```

## 当前实现状态

### 已实现

| 功能 | 实现位置 | 状态 |
|------|----------|------|
| SimpleEval 执行器 | `engine.py:_create_simpleeval()` | ✅ |
| asteval fallback | `engine.py:_evaluate_with_asteval()` | ✅ |
| 关键词预处理 | `engine.py:_normalize_keywords()` | ✅ |
| 字段解析 | `engine.py:_resolve_fields()` | ✅ |
| 运算符限制 | `engine.py:_create_simpleeval()` | ✅ |
| 安全测试 | `test_expression_engine.py:TestSecurityHardening` | ✅ |

### 未实现（目标设计）

| 功能 | 目标 | 优先级 |
|------|------|--------|
| 自动选择逻辑 | 关键词检测 → L0/L1 | P0 |
| AST 白名单校验 | L1 执行前校验 | P0 |
| max_loop_iterations | L1 循环次数限制 | P1 |
| timeout_seconds | L1 执行超时 | P1 |
| max_ast_depth | AST 嵌套深度限制 | P2 |
| 错误类型细分 | 5 种语义错误 | P1 |
| FormulaTimeoutError | 超时错误 | P1 |
| FormulaSecurityError | 安全违规错误 | P1 |

### 当前代码与目标设计的差距

| 维度 | 当前代码 | 目标设计 | 差距 |
|------|----------|----------|------|
| 执行器选择 | simpleeval 失败后 fallback asteval | 关键词检测自动选择 | 需重构 `_select_executor` |
| asteval 安全 | 无 AST 校验、无资源限制 | AST 白名单 + 循环/超时限制 | 需新增 `_validate_ast` |
| 错误类型 | 仅 `ExpressionSyntaxError` | 5 种语义错误 | 需新增 4 种错误类 |
| 函数注册 | L0/L1 分别注册相同函数 | 统一 `SAFE_FUNCTIONS` + 共享注册 | 需抽取函数注册逻辑 |

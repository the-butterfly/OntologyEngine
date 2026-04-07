# ADR-003: 表达式引擎安全沙箱

**状态**: Accepted
**日期**: 2026-04-07
**来源**: critical-review-response.md 问题4

---

## 背景问题

原 KGML 设计中使用 `eval()` 执行任意 Python 代码，存在严重安全风险：

```yaml
# 危险的原设计
metrics:
  - name: "risk_score"
    calculation:
      type: "formula"
      expression: |
        if balance > 1000000:
            return 90
```

**风险**：
- `eval()` 可执行任意代码
- 代码注入：`expression: "__import__('os').system('rm -rf /')"`

---

## 决策

### 1. AST 白名单节点过滤

只允许数学/逻辑运算节点，禁用函数调用和属性访问：

```python
ALLOWED_NODES = frozenset([
    'Expression', 'BinOp', 'UnaryOp', 'BoolOp', 'Compare', 'IfExp',
    'Add', 'Sub', 'Mult', 'Div', 'FloorDiv', 'Mod', 'Pow',
    'Eq', 'NotEq', 'Lt', 'LtE', 'Gt', 'GtE',
    'And', 'Or', 'Not', 'USub', 'UAdd',
    'Constant', 'Num', 'Str', 'NameConstant',
    'List', 'Tuple', 'Dict', 'Set',
    'Name', 'Load', 'Store',
])
```

### 2. 安全内置函数

仅允许有限的安全函数：

```python
SAFE_FUNCTIONS = {
    'abs': abs, 'min': min, 'max': max,
    'sum': sum, 'len': len, 'round': round,
    'pow': pow, 'divmod': divmod,
}
```

### 3. 资源限制

- 最大执行时间：1秒
- 最大内存：10MB
- 最大循环迭代：1000
- 最大字符串长度：1000

---

## 支持的语法

### 支持的操作

| 类型 | 操作符 |
|------|--------|
| 算术 | `+`, `-`, `*`, `/`, `//`, `%`, `**` |
| 比较 | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| 逻辑 | `and`, `or`, `not` |
| 条件 | `value if condition else other` |
| 字面量 | numbers, strings, lists, dicts |
| 变量 | context variable access |

### 禁止的操作

- 函数调用：`No function() allowed`
- 属性访问：`No obj.attr allowed`
- 导入：`No import allowed`
- 循环：`No for/while allowed`
- 赋值：`No = allowed`

---

## KGML 表达式规范更新

```yaml
expression_engine:
  version: "2.0"

  limits:
    max_execution_time_ms: 1000
    max_memory_mb: 10
    max_string_length: 1000
    max_list_length: 100
```

---

## 相关文档

- 问题5: KGML 自研工作量评估 ([004-kgml-linkml-integration.md](./004-kgml-linkml-integration.md))

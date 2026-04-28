---
status: deprecated
phase: mvp
source_of_truth: false
last_verified: "2026-04-12"
verified_against: code-and-docs
---

# Formula 表达式规范

> **[已过期入口]** — 已被 README.md + l0-l1-execution.md + function-library.md 替代
> **约束**: 单行表达式，结构化复杂逻辑使用算子
> **执行引擎**: simpleeval / 自定义安全求值器 (当前仅实现 simpleeval 方案)

## 语法概览

```
expression ::= logical_or

logical_or  ::= logical_and ("OR" | "||" logical_and)*
logical_and ::= equality ("AND" | "&&" equality)*
equality    ::= comparison (("==" | "!=") comparison)*
comparison  ::= additive ((">" | "<" | ">=" | "<=") additive)*
additive    ::= multiplicative (("+" | "-") multiplicative)*
multiplicative ::= unary (("*" | "/" | "%") unary)*
unary       ::= ("NOT" | "!" | "-") unary | primary
primary     ::= literal | field_ref | function_call | "(" expression ")"
```

## 运算符优先级

| 优先级 | 运算符 | 结合性 |
|--------|--------|--------|
| 1 (最高) | `()` 括号 | - |
| 2 | `NOT`, `!`, `-` (一元) | 右 |
| 3 | `*`, `/`, `%` | 左 |
| 4 | `+`, `-` | 左 |
| 5 | `>`, `<`, `>=`, `<=` | 左 |
| 6 | `==`, `!=` | 左 |
| 7 | `AND`, `&&` | 左 |
| 8 (最低) | `OR`, `\|\|` | 左 |

## 字面量

```yaml
# 数值
42          # integer
3.14159     # float
1e-10       # 科学计数

# 字符串
'hello'     # 单引号
"world"     # 双引号
'it\'s ok'  # 转义

# 布尔
true
false

# 空值
null

# 数组 (仅用于 IN 操作)
[1, 2, 3]
['A', 'B', 'C']
```

## 字段引用

### 基础字段

```yaml
# 直接引用实体属性
registered_capital
status
establishment_date

# 嵌套属性 (点号访问)
registered_capital.value
registered_capital.currency
address.province
```

### 指标引用

```yaml
# L3 指标引用 (当前实体)
credit_score
asset_liability_ratio

# 其他规则输出 (跨规则引用)
R001.eligible          # 规则 ID.输出字段
R002.credit_limit      # 支持链式: R002.output.field
```

### 上下文变量

```yaml
# 系统函数
today()                    # 当前日期
days_between(d1, d2)       # 天数差
months_between(d1, d2)     # 月数差
now()                      # 当前时间

# 聚合函数 (用于 composite 指标)
sum(values)
avg(values)
min(values)
max(values)
count(values)
std(values)                # 标准差
```

## 内置函数

### 数学函数

| 函数 | 说明 | 示例 |
|------|------|------|
| `abs(x)` | 绝对值 | `abs(-5)` → 5 |
| `min(a, b, ...)` | 最小值 | `min(credit_score, 100)` |
| `max(a, b, ...)` | 最大值 | `max(0, risk_score)` |
| `round(x, n)` | 四舍五入 | `round(3.14159, 2)` → 3.14 |
| `floor(x)` | 向下取整 | `floor(3.9)` → 3 |
| `ceil(x)` | 向上取整 | `ceil(3.1)` → 4 |
| `pow(x, y)` | 幂运算 | `pow(2, 10)` → 1024 |
| `sqrt(x)` | 平方根 | `sqrt(100)` → 10.0 |

### 字符串函数

| 函数 | 说明 | 示例 |
|------|------|------|
| `len(s)` | 长度 | `len(company_name)` |
| `upper(s)` | 大写 | `upper('abc')` → 'ABC' |
| `lower(s)` | 小写 | `lower('ABC')` → 'abc' |
| `contains(s, substr)` | 包含 | `contains(business_scope, '科技')` |
| `starts_with(s, prefix)` | 前缀 | `starts_with(uscc, '91')` |
| `ends_with(s, suffix)` | 后缀 | `ends_with(email, '@company.com')` |

### 日期函数

| 函数 | 说明 | 示例 |
|------|------|------|
| `today()` | 当前日期 | `today()` → '2026-04-08' |
| `now()` | 当前时间 | `now()` → '2026-04-08T10:00:00Z' |
| `days_between(d1, d2)` | 天数差 | `days_between(establishment_date, today())` |
| `months_between(d1, d2)` | 月数差 | `months_between(date1, date2)` |
| `years_between(d1, d2)` | 年数差 | `years_between(establishment_date, today())` |
| `add_days(d, n)` | 日期加减 | `add_days(today(), 30)` |
| `day_of_week(d)` | 星期几 | `day_of_week(today())` → 1-7 |
| `is_weekend(d)` | 是否周末 | `is_weekend(date)` |

### 类型转换

| 函数 | 说明 | 示例 |
|------|------|------|
| `int(x)` | 转整数 | `int('42')` → 42 |
| `float(x)` | 转浮点 | `float('3.14')` → 3.14 |
| `str(x)` | 转字符串 | `str(100)` → '100' |
| `decimal(x)` | 转精确小数 | `decimal('0.1')` |
| `bool(x)` | 转布尔 | `bool(1)` → true |

## 表达式示例

### 简单计算

```yaml
# 算术
registered_capital.value * 0.5
(total_assets - total_liabilities) / total_assets

# 比较
credit_score >= 60
asset_liability_ratio < 0.7

# 逻辑
status == 'ACTIVE' AND credit_score >= 60
risk_level == 'HIGH' OR overdue_days > 90
```

### 复合条件

```yaml
# 多条件组合
status == 'ACTIVE'
  AND credit_score >= 60
  AND asset_liability_ratio < 0.7
  AND guarantee_chain_length <= 3

# 范围检查
credit_score >= 60 AND credit_score < 80
annual_revenue.value >= 1000000 AND annual_revenue.value < 5000000

# IN 操作
industry_category IN ('C', 'F', 'I')
status IN ('ACTIVE', 'PENDING')
```

### 函数调用

```yaml
# 数学计算
min(registered_capital.value * 0.5, 10000000)
max(0, (credit_score - 60) / 40)

# 日期计算
days_between(establishment_date, today()) >= 365
months_between(last_invoice_date, today()) <= 3

# 字符串
len(company_name) >= 2 AND len(company_name) <= 100
contains(business_scope, '制造业')
```

## 类型系统

### 自动类型提升

```
integer + integer → integer
integer + float   → float
decimal + float   → decimal (高精度优先)
string + any      → error (不支持隐式转换)
```

### 比较规则

| 左操作数 | 右操作数 | 比较方式 |
|----------|----------|----------|
| 数值 | 数值 | 数值比较 |
| 字符串 | 字符串 | 字典序 |
| 日期 | 日期 | 时间先后 |
| 不同类型 | - | error |

### 空值处理

```yaml
# 显式检查
field IS NULL
field IS NOT NULL

# 空值传播 (默认)
null + 5 → null
null == null → true
null > 0 → null (视为 false)

# 空值合并 (COALESCE)
COALESCE(middle_name, first_name)
```

## 安全限制

### 禁止的操作

| 操作 | 原因 | 替代方案 |
|------|------|----------|
| 变量赋值 (`x = 1`) | 副作用 | 无，formula 只读 |
| 循环/迭代 | 复杂度不可控 | 使用算子 (SWITCH/BINNING) |
| 递归调用 | 栈溢出风险 | 无 |
| 动态代码执行 (`eval`) | 注入风险 | 禁止 |
| 属性访问 (`__dict__`) | 信息泄露 | 白名单字段 |
| 网络/IO 调用 | 副作用/延迟 | MODEL_INFERENCE 算子 |

### 字段访问白名单

```python
# 只允许访问以下数据源
ALLOWED_SOURCES = {
    "entity": "实体属性",
    "metric": "L3 指标",
    "rule": "其他规则输出",
    "context": "执行上下文",
    "function": "内置函数"
}

# 禁止访问
FORBIDDEN_PATTERNS = [
    r"__.*__",           # 魔术方法
    r"^storage",         # 存储层
    r"^engine",          # 引擎内部
    r"^config",          # 配置信息
]
```

### 执行超时

```python
MAX_EXECUTION_TIME_MS = 100  # 单条 formula 执行超时

async def evaluate_safe(expression: str, context: dict) -> Any:
    with timeout(MAX_EXECUTION_TIME_MS):
        return await evaluator.evaluate(expression, context)
```

## 错误处理

### 错误类型

```python
class FormulaError(Exception):
    """Formula 错误基类"""
    expression: str
    position: int | None
    message: str

class SyntaxError(FormulaError):
    """语法错误"""
    # 非法字符、括号不匹配等

class TypeError(FormulaError):
    """类型错误"""
    # 字符串 + 数字、日期比较字符串等

class NameError(FormulaError):
    """未定义引用"""
    # 字段不存在、函数未定义

class DivisionByZeroError(FormulaError):
    """除零错误"""

class TimeoutError(FormulaError):
    """执行超时"""
```

### 错误示例

```yaml
# 语法错误
"credit_score >="      # 缺少右操作数
"(1 + 2"                # 括号不匹配

# 类型错误
"'hello' + 42"          # 字符串加数字
"credit_score > 'high'" # 数值比较字符串

# 未定义引用
"undefined_field"       # 字段不存在
"unknown_function()"    # 函数未定义

# 运行时错误
"1 / 0"                 # 除零
"very_slow_function()"  # 超时
```

## 与算子协作

### 简单计算 → Formula

```yaml
action:
  type: compute
  output: risk_adjusted_rate
  # 简单表达式直接用 formula
  formula: "base_rate + (100 - credit_score) / 1000"
```

### 复杂逻辑 → Operator

```yaml
# 多分支 → SWITCH
action:
  type: compute
  output: credit_limit
  operator: SWITCH
  input: credit_score
  branches:
    - condition: ">= 90"
      formula: "registered_capital * 0.8"
    - condition: ">= 80"
      formula: "registered_capital * 0.6"
  default: "registered_capital * 0.2"

# 评分卡 → SCORECARD
action:
  type: compute
  output: credit_score
  operator: SCORECARD
  variables:
    - name: asset_liability_ratio
      points:
        - "< 0.4": 40
        - "[0.4, 0.7)": 25
        - ">= 0.7": 0
  # 评分卡内部使用 formula 计算总分
  # 但分支逻辑由算子管理
```

## 实现状态

### 当前实现 (Current) **[单一事实源]**

基于 `simpleeval` 的 `ExpressionEngine` 类，位于 `ontology_engine/engine/expression/engine.py`：

**已实现功能：**
- ✅ 基于 simpleeval 的单表达式求值
- ✅ 关键字预处理：AND/OR/NOT → and/or/not，IS NULL/IS NOT NULL → is_null()
- ✅ 嵌套字段解析：支持 `registered_capital.value` 格式
- ✅ 内置函数：today, days_between, is_null, max, min, round, abs, int, float, bool

```python
from ontology_engine.engine.expression.engine import ExpressionEngine

engine = ExpressionEngine()
result = engine.evaluate(
    "registered_capital.value >= 1000000 AND days_between(establishment_date, today()) >= 365",
    context={"registered_capital": {"value": 5000000}, "establishment_date": "2020-01-01"}
)
```

**代码核验标记**: `verified_against: code@ontology_engine/engine/expression/engine.py`

### 目标设计 (Target) **[待扩展]**

两级执行模型（L0/L1），详见 `docs/02-design/formula/l0-l1-execution.md`：

- L0: SimpleEvalExecutor — 简单表达式快速执行
- L1: ASTSandboxExecutor — 复杂控制流 AST 沙箱执行 **[待扩展]**

**状态**: 目标设计阶段，尚未实现 AST 沙箱和复杂控制流支持。


## 校验清单

编写 formula 后检查：

- [ ] 单条表达式，无换行
- [ ] 字段名存在且可访问
- [ ] 函数名为内置白名单
- [ ] 无变量赋值
- [ ] 无非法字符 (`;`, `{`, `}` 等)
- [ ] 括号匹配
- [ ] 类型兼容（数值运算、比较）
- [ ] 考虑空值处理

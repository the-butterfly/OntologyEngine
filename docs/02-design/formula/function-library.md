---
status: draft
phase: rewrite
source_of_truth: docs/02-design/formula/README.md
last_verified: "2026-04-19"
verified_against: code@ontology_engine/engine/expression/engine.py
---

# Formula 函数库规范

> **[关键设计点]**: Formula 内置函数的完整定义与实现状态追踪
> **上游**: `docs/02-design/formula/README.md`
> **代码实现**: `ontology_engine/engine/expression/engine.py`

## 目的

定义 Formula 表达式可调用的全部内置函数，包括签名、语义、返回值和实现状态，确保函数库的完整性和一致性。

## 解决的问题

| # | 问题 | 现状 | 本文档解决 |
|---|------|------|-----------|
| 1 | **函数定义分散** | 旧规范和代码中函数列表不一致 | 统一函数库规范，标注实现状态 |
| 2 | **函数签名模糊** | 部分函数缺少参数类型和返回值定义 | 为每个函数定义完整签名 |
| 3 | **函数分类不清** | 无分类体系，难以发现缺失 | 按 6 类组织，逐类盘点 |
| 4 | **实现状态不明** | 不清楚哪些函数已实现、哪些缺失 | 逐函数标注实现状态 |

## 函数分类总览

| 类别 | 函数数量 | 已实现 | 未实现 | 说明 |
|------|----------|--------|--------|------|
| 字符串函数 | 11 | 1 | 10 | 文本处理与匹配 |
| 日期函数 | 8 | 3 | 5 | 日期计算与格式化 |
| 类型转换 | 5 | 3 | 2 | 类型安全转换 |
| 聚合函数 | 6 | 0 | 6 | 集合统计计算 |
| 条件函数 | 3 | 1 | 2 | 条件逻辑与空值处理 |
| 数学函数 | 7 | 4 | 3 | 数值计算 |

## 字符串函数

### len(s: string) → integer

返回字符串长度。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |

示例：`len(company_name)` → 8

实现状态：❌ 未实现

### upper(s: string) → string

将字符串转换为大写。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |

示例：`upper('abc')` → `'ABC'`

实现状态：❌ 未实现

### lower(s: string) → string

将字符串转换为小写。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |

示例：`lower('ABC')` → `'abc'`

实现状态：❌ 未实现

### trim(s: string) → string

去除字符串两端空白字符。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |

示例：`trim('  hello  ')` → `'hello'`

实现状态：❌ 未实现

### replace(s: string, old: string, new: string) → string

替换字符串中的子串。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |
| `old` | string | 被替换子串 |
| `new` | string | 替换子串 |

示例：`replace(status, 'PENDING', 'ACTIVE')` → `'ACTIVE'`

实现状态：❌ 未实现

### substring(s: string, start: integer, length?: integer) → string

截取子串。`start` 从 0 开始。省略 `length` 时截取到末尾。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |
| `start` | integer | 起始位置（0-based） |
| `length` | integer? | 截取长度，省略则到末尾 |

示例：`substring('hello', 1, 3)` → `'ell'`

实现状态：❌ 未实现

### contains(s: string, substr: string) → boolean

判断字符串是否包含子串。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |
| `substr` | string | 搜索子串 |

示例：`contains(business_scope, '科技')` → `true`

实现状态：❌ 未实现

### starts_with(s: string, prefix: string) → boolean

判断字符串是否以指定前缀开头。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |
| `prefix` | string | 前缀 |

示例：`starts_with(uscc, '91')` → `true`

实现状态：❌ 未实现

### ends_with(s: string, suffix: string) → boolean

判断字符串是否以指定后缀结尾。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |
| `suffix` | string | 后缀 |

示例：`ends_with(email, '@company.com')` → `true`

实现状态：❌ 未实现

### split(s: string, delimiter: string) → list

按分隔符拆分字符串为数组。

| 参数 | 类型 | 说明 |
|------|------|------|
| `s` | string | 输入字符串 |
| `delimiter` | string | 分隔符 |

示例：`split('A,B,C', ',')` → `['A', 'B', 'C']`

实现状态：❌ 未实现

### join(parts: list, delimiter: string) → string

用分隔符连接数组为字符串。

| 参数 | 类型 | 说明 |
|------|------|------|
| `parts` | list | 字符串数组 |
| `delimiter` | string | 分隔符 |

示例：`join(['A', 'B', 'C'], ',')` → `'A,B,C'`

实现状态：❌ 未实现

## 日期函数

### today() → string

返回当前日期，格式 `YYYY-MM-DD`。

示例：`today()` → `'2026-04-19'`

实现状态：✅ 已实现（`engine.py`）

### now() → string

返回当前日期时间，格式 `YYYY-MM-DDTHH:MM:SSZ`。

示例：`now()` → `'2026-04-19T10:00:00Z'`

实现状态：❌ 未实现

### date_diff(start: string, end: string, unit: string) → integer

计算两个日期之间的差值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `start` | string | 起始日期 |
| `end` | string | 结束日期 |
| `unit` | string | 单位：`day` / `month` / `year` |

示例：`date_diff('2020-01-01', '2026-01-01', 'year')` → `6`

实现状态：❌ 未实现（当前有 `days_between` 和 `days_since`，但无通用 `date_diff`）

### date_add(date: string, amount: integer, unit: string) → string

日期加减。

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | string | 基准日期 |
| `amount` | integer | 增减量（负数为减） |
| `unit` | string | 单位：`day` / `month` / `year` |

示例：`date_add(today(), 30, 'day')` → `'2026-05-19'`

实现状态：❌ 未实现

### year(date: string) → integer

提取日期的年份。

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期字符串 |

示例：`year('2026-04-19')` → `2026`

实现状态：❌ 未实现

### month(date: string) → integer

提取日期的月份。

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期字符串 |

示例：`month('2026-04-19')` → `4`

实现状态：❌ 未实现

### day(date: string) → integer

提取日期的天。

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期字符串 |

示例：`day('2026-04-19')` → `19`

实现状态：❌ 未实现

### format_date(date: string, format: string) → string

格式化日期。

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期字符串 |
| `format` | string | 格式模板（如 `%Y年%m月%d日`） |

示例：`format_date(today(), '%Y年%m月')` → `'2026年04月'`

实现状态：❌ 未实现

### 当前已实现的日期函数

| 函数 | 签名 | 说明 | 实现位置 |
|------|------|------|----------|
| `today()` | `() → string` | 当前日期 ISO 格式 | `engine.py:88` |
| `days_between(start, end)` | `(any, any) → int` | 两个日期之间的天数差 | `engine.py:262` |
| `days_since(start)` | `(any) → int` | 距今天的天数 | `engine.py:270` |

### 日期函数迁移计划

| 旧函数 | 迁移目标 | 说明 |
|--------|----------|------|
| `days_between(d1, d2)` | 保留，同时新增 `date_diff(d1, d2, 'day')` | `days_between` 为便捷函数 |
| `days_since(d)` | 保留 | 无通用替代 |
| `add_days(d, n)`（旧规范） | 迁移到 `date_add(d, n, 'day')` | 统一接口 |

## 类型转换函数

### to_string(x: any) → string

将值转换为字符串。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | any | 输入值 |

示例：`to_string(100)` → `'100'`

实现状态：❌ 未实现（当前有 `str` 别名，但未注册到函数白名单）

### to_integer(x: any) → integer

将值转换为整数。转换失败返回 `null`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | any | 输入值 |

示例：`to_integer('42')` → `42`

实现状态：✅ 已实现（`int`，`engine.py:98`）

### to_decimal(x: any) → decimal

将值转换为高精度小数。用于金融计算避免浮点误差。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | any | 输入值 |

示例：`to_decimal('0.1')` → `Decimal('0.1')`

实现状态：❌ 未实现

### to_boolean(x: any) → boolean

将值转换为布尔值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | any | 输入值 |

示例：`to_boolean(1)` → `true`

实现状态：✅ 已实现（`bool`，`engine.py:99`）

### to_date(x: any) → string

将值转换为日期字符串（ISO 格式）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | any | 输入值（字符串或日期对象） |

示例：`to_date('20260419')` → `'2026-04-19'`

实现状态：❌ 未实现（当前 `_parse_date` 为内部方法，未暴露为函数）

### 类型转换函数命名规范

| 旧名称 | 新名称 | 原因 |
|--------|--------|------|
| `int` | `to_integer` | 避免与 Python 内置 `int` 冲突，语义更明确 |
| `float` | `to_decimal` | 金融场景使用 `Decimal` 而非 `float` |
| `bool` | `to_boolean` | 语义更明确 |
| `str` | `to_string` | 语义更明确 |

> **[待扩展]**: 旧名称是否保留为别名需要进一步确认。当前代码使用 `int`/`float`/`bool`。

## 聚合函数

聚合函数用于 composite 类型指标的多值聚合计算。输入为列表或数组。

### sum(values: list) → number

求和。

| 参数 | 类型 | 说明 |
|------|------|------|
| `values` | list | 数值列表 |

示例：`sum([1, 2, 3, 4])` → `10`

实现状态：❌ 未实现

### avg(values: list) → number

求平均值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `values` | list | 数值列表 |

示例：`avg([1, 2, 3, 4])` → `2.5`

实现状态：❌ 未实现

### min(values: list) → number

求最小值。

> 注意：当前 `min` 实现为多参数版本 `min(a, b, ...)`，非列表版本。

| 参数 | 类型 | 说明 |
|------|------|------|
| `values` | list | 数值列表 |

示例：`min([1, 2, 3, 4])` → `1`

实现状态：⚠️ 部分实现（多参数版本 ✅，列表版本 ❌）

### max(values: list) → number

求最大值。

> 注意：当前 `max` 实现为多参数版本 `max(a, b, ...)`，非列表版本。

| 参数 | 类型 | 说明 |
|------|------|------|
| `values` | list | 数值列表 |

示例：`max([1, 2, 3, 4])` → `4`

实现状态：⚠️ 部分实现（多参数版本 ✅，列表版本 ❌）

### count(values: list) → integer

计数（非空元素个数）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `values` | list | 值列表 |

示例：`count([1, null, 3, null])` → `2`

实现状态：❌ 未实现

### weighted_sum(components: list, weights: list) → number

加权求和。

| 参数 | 类型 | 说明 |
|------|------|------|
| `components` | list | 分量值列表 |
| `weights` | list | 权重列表 |

示例：`weighted_sum([80, 90, 70], [0.3, 0.5, 0.2])` → `83.0`

实现状态：❌ 未实现

## 条件函数

### if_expr(condition: boolean, then_value: any, else_value: any) → any

条件选择。命名 `if_expr` 避免与 Python 关键字 `if` 冲突。

| 参数 | 类型 | 说明 |
|------|------|------|
| `condition` | boolean | 条件表达式 |
| `then_value` | any | 条件为真时的值 |
| `else_value` | any | 条件为假时的值 |

示例：`if_expr(credit_score >= 60, 'PASS', 'FAIL')` → `'PASS'`

实现状态：❌ 未实现

### coalesce(value1: any, value2: any, ...) → any

返回第一个非空值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `value1, value2, ...` | any | 候选值列表 |

示例：`coalesce(middle_name, first_name, 'N/A')` → `'John'`

实现状态：❌ 未实现

### case(expr: any, when: list, default: any) → any

多分支条件选择，类似 SQL CASE WHEN。

| 参数 | 类型 | 说明 |
|------|------|------|
| `expr` | any | 待匹配表达式 |
| `when` | list | `[[match_value, result], ...]` 匹配对 |
| `default` | any | 默认值 |

示例：`case(risk_level, [['HIGH', 0], ['MEDIUM', 50], ['LOW', 100]], 25)` → `0`

实现状态：❌ 未实现

## 数学函数

### abs(x: number) → number

绝对值。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | number | 输入数值 |

示例：`abs(-5)` → `5`

实现状态：✅ 已实现（`engine.py:97`）

### round(x: number, n: integer = 0) → number

四舍五入。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | number | 输入数值 |
| `n` | integer | 小数位数，默认 0 |

示例：`round(3.14159, 2)` → `3.14`

实现状态：✅ 已实现（`engine.py:96`）

### ceil(x: number) → integer

向上取整。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | number | 输入数值 |

示例：`ceil(3.1)` → `4`

实现状态：❌ 未实现

### floor(x: number) → integer

向下取整。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | number | 输入数值 |

示例：`floor(3.9)` → `3`

实现状态：❌ 未实现

### sqrt(x: number) → number

平方根。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | number | 非负数值 |

示例：`sqrt(100)` → `10.0`

实现状态：❌ 未实现

### pow(base: number, exp: number) → number

幂运算。

| 参数 | 类型 | 说明 |
|------|------|------|
| `base` | number | 底数 |
| `exp` | number | 指数 |

示例：`pow(2, 10)` → `1024`

实现状态：❌ 未实现

### log(x: number, base?: number) → number

对数运算。省略 `base` 时为自然对数。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | number | 正数值 |
| `base` | number? | 底数，默认 e |

示例：`log(100, 10)` → `2.0`

实现状态：❌ 未实现

## 其他已实现函数

以下函数已在当前代码中实现，但未归入上述 6 类：

| 函数 | 签名 | 类别归属 | 说明 |
|------|------|----------|------|
| `is_null(value)` | `(any) → bool` | 条件函数 | 判断值是否为 null |
| `clamp(value, min, max)` | `(number, number, number) → number` | 数学函数 | 将值限制在范围内 |

## 实现状态汇总

### 按类别统计

| 类别 | 总数 | ✅ 已实现 | ⚠️ 部分实现 | ❌ 未实现 |
|------|------|----------|------------|----------|
| 字符串函数 | 11 | 0 | 0 | 11 |
| 日期函数 | 8 | 1 | 0 | 7 |
| 类型转换 | 5 | 2 | 0 | 3 |
| 聚合函数 | 6 | 0 | 2 | 4 |
| 条件函数 | 3 | 1 | 0 | 2 |
| 数学函数 | 7 | 2 | 0 | 5 |
| 其他 | 2 | 2 | 0 | 0 |
| **合计** | **42** | **8** | **2** | **32** |

### 完整实现清单

| 函数 | 类别 | 状态 | 代码位置 |
|------|------|------|----------|
| `today()` | 日期 | ✅ | `engine.py:88` |
| `days_between(start, end)` | 日期 | ✅ | `engine.py:262` |
| `days_since(start)` | 日期 | ✅ | `engine.py:270` |
| `now()` | 日期 | ❌ | - |
| `date_diff(start, end, unit)` | 日期 | ❌ | - |
| `date_add(date, amount, unit)` | 日期 | ❌ | - |
| `year(date)` | 日期 | ❌ | - |
| `month(date)` | 日期 | ❌ | - |
| `day(date)` | 日期 | ❌ | - |
| `format_date(date, format)` | 日期 | ❌ | - |
| `int(x)` / `to_integer(x)` | 类型转换 | ✅ | `engine.py:98` |
| `float(x)` / `to_decimal(x)` | 类型转换 | ✅ | `engine.py:99` |
| `bool(x)` / `to_boolean(x)` | 类型转换 | ✅ | `engine.py:99` |
| `to_string(x)` | 类型转换 | ❌ | - |
| `to_date(x)` | 类型转换 | ❌ | - |
| `max(a, b, ...)` | 聚合 | ⚠️ | `engine.py:94`（仅多参数） |
| `min(a, b, ...)` | 聚合 | ⚠️ | `engine.py:93`（仅多参数） |
| `sum(values)` | 聚合 | ❌ | - |
| `avg(values)` | 聚合 | ❌ | - |
| `count(values)` | 聚合 | ❌ | - |
| `weighted_sum(components, weights)` | 聚合 | ❌ | - |
| `is_null(value)` | 条件 | ✅ | `engine.py:91` |
| `coalesce(value1, value2, ...)` | 条件 | ❌ | - |
| `if_expr(condition, then, else)` | 条件 | ❌ | - |
| `case(expr, when, default)` | 条件 | ❌ | - |
| `abs(x)` | 数学 | ✅ | `engine.py:97` |
| `round(x, n)` | 数学 | ✅ | `engine.py:96` |
| `clamp(value, min, max)` | 数学 | ✅ | `engine.py:92` |
| `ceil(x)` | 数学 | ❌ | - |
| `floor(x)` | 数学 | ❌ | - |
| `sqrt(x)` | 数学 | ❌ | - |
| `pow(base, exp)` | 数学 | ❌ | - |
| `log(x, base?)` | 数学 | ❌ | - |
| `len(s)` | 字符串 | ❌ | - |
| `upper(s)` | 字符串 | ❌ | - |
| `lower(s)` | 字符串 | ❌ | - |
| `trim(s)` | 字符串 | ❌ | - |
| `replace(s, old, new)` | 字符串 | ❌ | - |
| `substring(s, start, length?)` | 字符串 | ❌ | - |
| `contains(s, substr)` | 字符串 | ❌ | - |
| `starts_with(s, prefix)` | 字符串 | ❌ | - |
| `ends_with(s, suffix)` | 字符串 | ❌ | - |
| `split(s, delimiter)` | 字符串 | ❌ | - |
| `join(parts, delimiter)` | 字符串 | ❌ | - |

## 实现优先级建议

| 优先级 | 函数 | 原因 |
|--------|------|------|
| P0 | `coalesce`, `if_expr` | 条件函数是规则引擎的基础需求 |
| P0 | `contains`, `starts_with`, `ends_with` | 字符串匹配是风控场景高频操作 |
| P1 | `sum`, `avg`, `count` | 聚合函数是 composite 指标的基础 |
| P1 | `date_diff`, `date_add` | 日期计算是金融场景核心需求 |
| P1 | `ceil`, `floor`, `pow`, `sqrt` | 数学函数补全 |
| P2 | `upper`, `lower`, `trim`, `len` | 字符串处理增强 |
| P2 | `replace`, `substring`, `split`, `join` | 高级字符串操作 |
| P2 | `year`, `month`, `day`, `format_date` | 日期提取与格式化 |
| P2 | `to_date`, `to_string`, `to_decimal` | 类型转换补全 |
| P2 | `weighted_sum`, `case` | 高级聚合与条件 |

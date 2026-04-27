---
status: active
phase: rewrite
source_of_truth: docs/02-design/formula/README.md
last_verified: "2026-04-22"
verified_against: code@ontology_engine/engine/expression/engine.py
---

# Formula 函数库规范

> **[单一事实源]** Formula 内置函数的完整定义与实现状态
> **上游**: `docs/02-design/formula/README.md`
> **代码实现**: `ontology_engine/engine/expression/engine.py`
> **最后核对**: 2026-04-22（已逐函数对照源码核实）

## 目的

定义 Formula 表达式可调用的全部内置函数，包括：
- 函数签名与语义
- 入参类型约束与特殊值处理规则（`None` / `N/A`、`inf`/`-inf`、空字符串、空列表等）
- 返回值规范
- 当前实现状态

---

## 特殊值处理通用约定

在 Formula 表达式上下文中，以下特殊值出现频率高，所有函数必须声明处理策略：

| 特殊值 | Python 表示 | 函数处理原则 |
|--------|------------|-------------|
| **缺失值** | `None` | 数值函数返回 0 / 0.0；字符串函数返回 `""`；布尔函数返回 `False`。**不抛出异常**。 |
| **N/A 字符串** | `"N/A"` / `"n/a"` | 视为普通字符串，**不自动转换为 None**。调用方需使用 `is_null` 配合 `coalesce` 处理。 |
| **正无穷** | `float("inf")` | 数值函数透传；`round/ceil/floor` 对 `inf` 抛出 `OverflowError` — 调用方需用 `clamp` 预处理。 |
| **负无穷** | `float("-inf")` | 同上。 |
| **NaN** | `float("nan")` | 比较运算返回 `False`；聚合函数会将 NaN 计入结果（Python 行为）。建议调用方过滤。 |
| **空字符串** | `""` | `len("") = 0`；`trim("") = ""`；`split("", ",") = [""]`（Python 标准行为）。 |
| **空列表** | `[]` | 聚合函数（sum/avg/count 等）返回中性值（0 / 0.0）。 |

---

## 函数分类总览

| 类别 | 已实现 | 规划中 | 总计 |
|------|--------|--------|------|
| 字符串函数 | 11 ✅ | 0 | 11 |
| 日期函数 | 8 ✅ | 1 🔧 | 9 |
| 类型转换 | 5 ✅ | 1 🔧 | 6 |
| 聚合函数 | 6 ✅ | 0 | 6 |
| 条件函数 | 3 ✅ | 1 🔧 | 4 |
| 数学函数 | 9 ✅ | 0 | 9 |
| **合计** | **42 ✅** | **2 🔧** | **44** |

> 🔧 = 规划中，尚未实现。

---

## 字符串函数（11/11 已实现）

### len(s) → integer

返回字符串的 Unicode 字符数（不是字节数）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `0`；非字符串类型先 `str(s)` 转换后计长 |

特殊值：
- `len(None)` → `0`
- `len("")` → `0`
- `len("abc")` → `3`

实现状态：✅ 已实现（`engine.py:_len`）

---

### upper(s) → string

将字符串转换为大写。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `""`；非字符串先 `str(s)` |

特殊值：`upper(None)` → `""`

示例：`upper('abc')` → `'ABC'`

实现状态：✅ 已实现（`engine.py:_upper`）

---

### lower(s) → string

将字符串转换为小写。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `""`；非字符串先 `str(s)` |

特殊值：`lower(None)` → `""`

示例：`lower('ABC')` → `'abc'`

实现状态：✅ 已实现（`engine.py:_lower`）

---

### trim(s) → string

去除字符串两端空白字符（含全角空格）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `""`；仅去除 Python 认定的空白符 |

特殊值：`trim(None)` → `""`，`trim("  ")` → `""`

示例：`trim('  hello  ')` → `'hello'`

实现状态：✅ 已实现（`engine.py:_trim`）

---

### replace(s, old, new) → string

将字符串 `s` 中所有 `old` 子串替换为 `new`。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `""` |
| `old` | any | 若为 `None` 返回原字符串（不替换） |
| `new` | any | 允许 `None`，等价于 `""` |

特殊值：`replace(None, "x", "y")` → `""`

示例：`replace('PENDING_OK', 'PENDING', 'ACTIVE')` → `'ACTIVE_OK'`

实现状态：✅ 已实现（`engine.py:_replace`）

---

### substring(s, start, length?) → string

截取子串。`start` 从 **0** 开始（0-based）。省略 `length` 时截取到末尾。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 等价于 `""` |
| `start` | integer | 允许负数（Python 切片语义） |
| `length` | integer? | 省略时截取到末尾；`length=0` 返回 `""` |

特殊值：`substring(None, 0)` → `""`

示例：
- `substring('hello', 1, 3)` → `'ell'`
- `substring('hello', 2)` → `'llo'`

实现状态：✅ 已实现（`engine.py:_substring`）

---

### contains(s, substr) → boolean

判断字符串是否包含子串（大小写敏感）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `False` |
| `substr` | any | 若为 `None` 返回 `False` |

特殊值：`contains(None, "x")` → `False`，`contains("abc", None)` → `False`

示例：`contains('科技公司', '科技')` → `True`

实现状态：✅ 已实现（`engine.py:_contains`）

---

### starts_with(s, prefix) → boolean

判断字符串是否以指定前缀开头。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `False` |
| `prefix` | any | 若为 `None` 返回 `False` |

示例：`starts_with('91330100...', '91')` → `True`

实现状态：✅ 已实现（`engine.py:_starts_with`）

---

### ends_with(s, suffix) → boolean

判断字符串是否以指定后缀结尾。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `False` |
| `suffix` | any | 若为 `None` 返回 `False` |

示例：`ends_with('user@company.com', '@company.com')` → `True`

实现状态：✅ 已实现（`engine.py:_ends_with`）

---

### split(s, delimiter) → list[string]

按分隔符拆分字符串，返回字符串列表。

| 参数 | 类型 | 约束 |
|------|------|------|
| `s` | any | 若为 `None` 返回 `[]` |
| `delimiter` | any | 支持多字符分隔符 |

特殊值：
- `split(None, ",")` → `[]`
- `split("A,,B", ",")` → `["A", "", "B"]`（空元素保留）

示例：`split('A,B,C', ',')` → `['A', 'B', 'C']`

实现状态：✅ 已实现（`engine.py:_split`）

---

### join(parts, delimiter) → string

用分隔符连接列表为字符串，列表中每个元素先 `str()` 转换。

| 参数 | 类型 | 约束 |
|------|------|------|
| `parts` | list | 若为 `None` 返回 `""` |
| `delimiter` | any | 支持多字符；`None` 等价于 `""` |

特殊值：`join(None, ",")` → `""`，`join([], ",")` → `""`

示例：`join(['A', 'B', 'C'], ',')` → `'A,B,C'`

实现状态：✅ 已实现（`engine.py:_join`）

---

## 日期函数（8/9 已实现）

所有日期函数接受多种日期格式：`YYYY-MM-DD`、`YYYY/MM/DD`、`YYYYMMDD`，
以及 Python `date`/`datetime` 对象。不可解析时视为 `None`。

---

### today() → string

返回当前日期，格式 `YYYY-MM-DD`。无参数，不接受输入。

示例：`today()` → `'2026-04-22'`

实现状态：✅ 已实现（`engine.py:_today`）

---

### now() → string

返回当前日期时间，格式 `YYYY-MM-DDTHH:MM:SSZ`（本地时间，不带时区偏移）。

示例：`now()` → `'2026-04-22T16:00:00Z'`

实现状态：✅ 已实现（`engine.py:_now`）

---

### days_between(start, end) → integer

计算两个日期之间的绝对天数差。

| 参数 | 类型 | 约束 |
|------|------|------|
| `start` | string/date | 若无法解析返回 `0` |
| `end` | string/date | 若无法解析返回 `0` |

特殊值：任一参数为 `None` 或无效日期 → `0`

示例：`days_between('2026-01-01', '2026-04-22')` → `111`

实现状态：✅ 已实现（`engine.py:_days_between`）

---

### days_since(start) → integer

计算从 `start` 到今天的绝对天数。

| 参数 | 类型 | 约束 |
|------|------|------|
| `start` | string/date | 若无法解析返回 `0` |

示例：`days_since('2025-01-01')` → `476`（近似值）

实现状态：✅ 已实现（`engine.py:_days_since`）

---

### date_diff(start, end, unit) → integer

计算两个日期之间的差值，支持 `day`/`month`/`year` 单位。

| 参数 | 类型 | 约束 |
|------|------|------|
| `start` | string/date | 若无法解析返回 `0` |
| `end` | string/date | 若无法解析返回 `0` |
| `unit` | string | `"day"`（默认）/ `"month"` / `"year"` |

> **注意**：`month` 和 `year` 使用 `days // 30` 和 `days // 365` 近似，不是精确日历月/年。

特殊值：任一日期无效 → `0`

示例：`date_diff('2020-01-01', '2026-01-01', 'year')` → `6`

实现状态：✅ 已实现（`engine.py:_date_diff`）

---

### date_add(date, amount, unit) → string

日期加减。返回 ISO 格式日期字符串。

| 参数 | 类型 | 约束 |
|------|------|------|
| `date` | string/date | 若无法解析返回 `""` |
| `amount` | integer | 负数表示向前减；允许 `0` |
| `unit` | string | `"day"` / `"month"` / `"year"` |

> **✅ 已修复**：`unit="month"` 跨年时 `d.replace(month=...)` 抛 `ValueError` 的问题已修复（代码已修正，文档同步）。

示例：
- `date_add('2026-04-22', 30, 'day')` → `'2026-05-22'`
- `date_add('2026-04-22', 1, 'year')` → `'2027-04-22'`

实现状态：✅ 已实现（`engine.py:_date_add`）

---

### year(date) → integer

提取日期的年份。

| 参数 | 类型 | 约束 |
|------|------|------|
| `date` | string/date | 若无法解析返回 `0` |

示例：`year('2026-04-22')` → `2026`

实现状态：✅ 已实现（`engine.py:_year`）

---

### month(date) → integer

提取日期的月份（1-12）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `date` | string/date | 若无法解析返回 `0` |

示例：`month('2026-04-22')` → `4`

实现状态：✅ 已实现（`engine.py:_month`）

---

### day(date) → integer

提取日期的天（1-31）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `date` | string/date | 若无法解析返回 `0` |

示例：`day('2026-04-22')` → `22`

实现状态：✅ 已实现（`engine.py:_day`）

---

### format_date(date, format) → string ⏳ 规划中

格式化日期为指定格式字符串。

| 参数 | 类型 | 约束 |
|------|------|------|
| `date` | string/date | 若无法解析返回 `""` |
| `format` | string | Python `strftime` 格式模板（如 `%Y年%m月%d日`） |

示例：`format_date(today(), '%Y年%m月')` → `'2026年04月'`

实现状态：🔧 规划中（低优先级，P2）

---

## 类型转换函数（5/6 已实现）

---

### to_string(x) → string

将任意值转换为字符串。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | any | `None` → `""`；其他值调用 `str(x)` |

特殊值：`to_string(None)` → `""`，`to_string(0)` → `"0"`

> **兼容性**：函数名 `str` 是 `to_string` 的别名，两者均可在表达式中使用。

实现状态：✅ 已实现（`engine.py:_to_string`，别名 `str`）

---

### to_integer(x) → integer

将值转换为整数。转换失败返回 `0`。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | any | 字符串先尝试 `int()`；浮点数截断取整；`None` → `0` |

特殊值：
- `to_integer(None)` → `0`
- `to_integer("42")` → `42`
- `to_integer("abc")` → `0`（转换失败）
- `to_integer(3.9)` → `3`（截断，非四舍五入）

> **兼容性**：`int` 是 `to_integer` 的别名。

实现状态：✅ 已实现（Python 内置 `int`，别名 `to_integer` 未独立注册，通过 `int` 使用）

---

### to_decimal(x) → Decimal

> **✅ 已修复**：`to_decimal` 已改为返回 `decimal.Decimal`，金融计算浮点精度问题已解决（代码已修正，文档同步）。

将值转换为高精度小数（Decimal）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | any | `None` → `Decimal('0')`；转换失败 → `Decimal('0')` |

特殊值：
- `to_decimal(None)` → `Decimal('0')`
- `to_decimal("0.1")` → `Decimal('0.1')`（精确小数，无精度偏差）
- `to_decimal("abc")` → `Decimal('0')`

> **兼容性**：`float` 是 `to_decimal` 的别名。

实现状态：✅ 已实现（`engine.py:_to_decimal`）

---

### to_boolean(x) → boolean

将值转换为布尔值，使用 Python 真值规则。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | any | `None`/`0`/`""`/`[]` → `False`；其他 → `True` |

特殊值：
- `to_boolean(None)` → `False`
- `to_boolean(0)` → `False`
- `to_boolean("")` → `False`
- `to_boolean("false")` → `True`（非空字符串均为 True）

> **注意**：字符串 `"false"` / `"0"` 也返回 `True`（Python bool 规则）。
> 如需语义布尔转换（字符串 "false" → False），请在调用方处理。

> **兼容性**：`bool` 是 `to_boolean` 的别名。

实现状态：✅ 已实现（Python 内置 `bool`）

---

### to_date(x) → string ⏳ 规划中

将值转换为 ISO 日期字符串（`YYYY-MM-DD`）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | any | 支持 `YYYYMMDD`、`YYYY/MM/DD` 等多种格式 |

示例：`to_date('20260422')` → `'2026-04-22'`

> `_parse_date` 内部方法已实现此功能，待封装为公开函数。

实现状态：🔧 规划中（P2）

---

## 聚合函数（6/6 已实现）

---

### sum(values) → number

求和。输入为数值列表。

| 参数 | 类型 | 约束 |
|------|------|------|
| `values` | list[number] | `None` → `0`；空列表 → `0`；包含 `None` 的元素会导致 TypeError（需调用方预过滤） |

特殊值：
- `sum(None)` → `0`
- `sum([])` → `0`
- `sum([1, 2, 3])` → `6`

> **注意**：列表中若含 `None` 元素，Python `sum()` 会抛出 TypeError。建议先用 `[v for v in values if v is not None]` 过滤。

实现状态：✅ 已实现（`engine.py:_sum`）

---

### avg(values) → float

求平均值。

| 参数 | 类型 | 约束 |
|------|------|------|
| `values` | list[number] | `None` → `0.0`；空列表 → `0.0`（不抛除以零异常） |

特殊值：
- `avg(None)` → `0.0`
- `avg([])` → `0.0`

示例：`avg([1, 2, 3, 4])` → `2.5`

实现状态：✅ 已实现（`engine.py:_avg`）

---

### count(values) → integer

计算列表中非 `None` 元素的个数。

| 参数 | 类型 | 约束 |
|------|------|------|
| `values` | list | `None` → `0`；`False`/`0`/`""` 被计入（仅排除 `None`） |

特殊值：
- `count(None)` → `0`
- `count([1, None, 3, None])` → `2`
- `count([0, False, ""])` → `3`（零值和空字符串不算缺失）

示例：`count([1, None, 3, None])` → `2`

实现状态：✅ 已实现（`engine.py:_count`）

---

### weighted_sum(components, weights) → float

加权求和。`len(components)` 必须等于 `len(weights)`。

| 参数 | 类型 | 约束 |
|------|------|------|
| `components` | list[number] | 若为 `None` 返回 `0.0` |
| `weights` | list[number] | 若为 `None` 返回 `0.0`；长度不等于 components 时返回 `0.0` |

特殊值：
- `weighted_sum(None, [0.5])` → `0.0`
- `weighted_sum([80, 90], [0.4])` → `0.0`（长度不匹配）

示例：`weighted_sum([80, 90, 70], [0.3, 0.5, 0.2])` → `83.0`

实现状态：✅ 已实现（`engine.py:_weighted_sum`）

---

### min(a, b, ...) / min([list]) → number

求最小值。支持两种调用方式：
- 多参数：`min(a, b, c)`
- 单列表：`min([a, b, c])`（Python 内置行为，直接透传）

| 参数 | 类型 | 约束 |
|------|------|------|
| 多参数 | number | 参数中含 `None` 时行为取决于 Python：`None < 数值` 在 Python 3 中抛出 TypeError |

> **推荐用法**：确保参数不含 `None`，或先用 `coalesce` 替换。

实现状态：✅ 已实现（Python 内置 `min`）

---

### max(a, b, ...) / max([list]) → number

求最大值。支持两种调用方式：
- 多参数：`max(a, b, c)`
- 单列表：`max([a, b, c])`

同 `min` 的注意事项，参数中含 `None` 时抛出 TypeError。

实现状态：✅ 已实现（Python 内置 `max`）

---

## 条件函数（3/4 已实现）

---

### is_null(value) → boolean

判断值是否为 `None`。

| 参数 | 类型 | 约束 |
|------|------|------|
| `value` | any | 严格判断 `is None`，`0`/`""`/`False` 不算 null |

特殊值：
- `is_null(None)` → `True`
- `is_null(0)` → `False`
- `is_null("")` → `False`

实现状态：✅ 已实现（`engine.py:_is_null`）

---

### coalesce(value1, value2, ...) → any

返回第一个非 `None` 值。若所有参数都为 `None` 则返回 `None`。

| 参数 | 类型 | 约束 |
|------|------|------|
| 可变参数 | any | 至少传 1 个参数；`0`/`""`/`False` 不被跳过（只跳过 `None`） |

特殊值：
- `coalesce(None, None)` → `None`
- `coalesce(None, 0, 1)` → `0`（`0` 是非 None 值）
- `coalesce(None, "", "fallback")` → `""`

示例：`coalesce(middle_name, first_name, 'N/A')` → 第一个非 None 值

实现状态：✅ 已实现（`engine.py:_coalesce`）

---

### if_expr(condition, then_value, else_value) → any

条件选择。命名 `if_expr` 避免与 Python 关键字 `if` 冲突。

| 参数 | 类型 | 约束 |
|------|------|------|
| `condition` | boolean | Python 真值规则；`None` 视为 `False` |
| `then_value` | any | 条件为真时返回 |
| `else_value` | any | 条件为假时返回 |

> **注意**：`then_value` 和 `else_value` 均会被求值（Python 语义），
> 不支持短路求值。如需惰性求值，使用 L1 表达式（含 `if` 语句的多行表达式）。

特殊值：`if_expr(None, 'A', 'B')` → `'B'`（None 视为 False）

示例：`if_expr(credit_score >= 60, 'PASS', 'FAIL')` → `'PASS'`

实现状态：✅ 已实现（`engine.py:_if_expr`）

---

### case(expr, when, default) → any ⏳ 规划中

多分支条件选择，类似 SQL CASE WHEN。

| 参数 | 类型 | 约束 |
|------|------|------|
| `expr` | any | 待匹配表达式 |
| `when` | list[list] | 格式 `[[match_value, result], ...]` |
| `default` | any | 无匹配时的默认值 |

示例：`case(risk_level, [['HIGH', 0], ['MEDIUM', 50], ['LOW', 100]], 25)` → `0`

实现状态：🔧 规划中（P2）

---

## 数学函数（9/9 已实现）

---

### abs(x) → number

绝对值。透传 Python `abs()`。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | number | `None` 不处理（Python abs(None) 抛 TypeError）；建议调用方用 `coalesce` 预处理 |

示例：`abs(-5.5)` → `5.5`

实现状态：✅ 已实现（Python 内置 `abs`）

---

### round(x, n) → number

四舍五入。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | number | `None` 不处理 |
| `n` | integer | 小数位数，默认 `0`；负数表示舍入到十位/百位 |

> **注意**：Python `round()` 使用"银行家舍入法"（Banker's rounding）：`round(2.5) = 2`（非 3）。

示例：`round(3.14159, 2)` → `3.14`，`round(2.5, 0)` → `2.0`（银行家舍入）

实现状态：✅ 已实现（Python 内置 `round`）

---

### clamp(value, min_val, max_val) → number

将值限制在 `[min_val, max_val]` 范围内。

| 参数 | 类型 | 约束 |
|------|------|------|
| `value` | number | 若为 `None` 返回原值（不截断） |
| `min_val` | number | 若为 `None` 返回原值 |
| `max_val` | number | 若为 `None` 返回原值 |

特殊值：`clamp(None, 0, 100)` → `None`（任一参数为 None 则不截断）

示例：`clamp(150, 0, 100)` → `100`，`clamp(-10, 0, 100)` → `0`

实现状态：✅ 已实现（`engine.py:_clamp`）

---

### ceil(x) → integer

向上取整（天花板函数）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | number | 若为 `None` 返回 `0`；`inf`/`-inf` 触发 `OverflowError`（建议用 `clamp` 预处理） |

示例：`ceil(3.1)` → `4`，`ceil(-2.7)` → `-2`

实现状态：✅ 已实现（`engine.py:_ceil`）

---

### floor(x) → integer

向下取整（地板函数）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | number | 若为 `None` 返回 `0`；`inf`/`-inf` 触发 `OverflowError` |

示例：`floor(3.9)` → `3`，`floor(-2.1)` → `-3`

实现状态：✅ 已实现（`engine.py:_floor`）

---

### sqrt(x) → float

平方根。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | number | 若为 `None` 返回 `0.0`；负数返回 `0.0`（不抛异常，因 `math.sqrt` 负数抛 ValueError 被捕获） |

特殊值：`sqrt(None)` → `0.0`，`sqrt(-1)` → `0.0`

示例：`sqrt(100)` → `10.0`

实现状态：✅ 已实现（`engine.py:_sqrt`）

---

### pow(base, exp) → float

幂运算。

| 参数 | 类型 | 约束 |
|------|------|------|
| `base` | number | 若为 `None` 返回 `0.0` |
| `exp` | number | 若为 `None` 返回 `0.0` |

特殊值：`pow(None, 2)` → `0.0`，`pow(2, None)` → `0.0`

示例：`pow(2, 10)` → `1024.0`

实现状态：✅ 已实现（`engine.py:_pow`）

---

### log(x, base?) → float

对数运算。省略 `base` 时为自然对数（`ln`）。

| 参数 | 类型 | 约束 |
|------|------|------|
| `x` | number | 若为 `None` 返回 `0.0`；`x <= 0` 返回 `0.0`（`math.log` 会抛 ValueError，被捕获） |
| `base` | number? | 省略时为 `e`；`base <= 0` 或 `base == 1` 返回 `0.0` |

特殊值：`log(None)` → `0.0`，`log(0)` → `0.0`，`log(-1)` → `0.0`

示例：`log(100, 10)` → `2.0`，`log(math.e)` → `1.0`

实现状态：✅ 已实现（`engine.py:_log`）

---

## Bug 修复记录

| # | 函数 | Bug 描述 | 严重程度 | 状态 |
|---|------|---------|---------|------|
| B-1 | `date_add` | `unit="month"` 跨年时 `d.replace(month=...)` 抛 `ValueError` | 🔴 高 | ✅ 已修复（代码已修正，文档同步） |
| B-2 | `to_decimal` | 返回 `float` 而非 `Decimal`，金融计算有浮点误差 | 🟡 中 | ✅ 已修复（代码已修正，文档同步） |

---

## 实现状态汇总

| 类别 | 总计 | ✅ 已实现 | 🔧 规划中 |
|------|------|----------|---------|
| 字符串函数 | 11 | 11 | 0 |
| 日期函数 | 9 | 8 | 1 |
| 类型转换 | 6 | 5 | 1 |
| 聚合函数 | 6 | 6 | 0 |
| 条件函数 | 4 | 3 | 1 |
| 数学函数 | 9 | 9 | 0 |
| **合计** | **45** | **42** | **3** |

---

## 函数快速索引

| 函数 | 类别 | 状态 | 代码位置 |
|------|------|------|---------|
| `len(s)` | 字符串 | ✅ | `_len` |
| `upper(s)` | 字符串 | ✅ | `_upper` |
| `lower(s)` | 字符串 | ✅ | `_lower` |
| `trim(s)` | 字符串 | ✅ | `_trim` |
| `replace(s, old, new)` | 字符串 | ✅ | `_replace` |
| `substring(s, start, length?)` | 字符串 | ✅ | `_substring` |
| `contains(s, substr)` | 字符串 | ✅ | `_contains` |
| `starts_with(s, prefix)` | 字符串 | ✅ | `_starts_with` |
| `ends_with(s, suffix)` | 字符串 | ✅ | `_ends_with` |
| `split(s, delim)` | 字符串 | ✅ | `_split` |
| `join(parts, delim)` | 字符串 | ✅ | `_join` |
| `today()` | 日期 | ✅ | `_today` |
| `now()` | 日期 | ✅ | `_now` |
| `days_between(s, e)` | 日期 | ✅ | `_days_between` |
| `days_since(s)` | 日期 | ✅ | `_days_since` |
| `date_diff(s, e, unit)` | 日期 | ✅ | `_date_diff` |
| `date_add(d, amt, unit)` | 日期 | ✅⚠️B-1 | `_date_add` |
| `year(d)` | 日期 | ✅ | `_year` |
| `month(d)` | 日期 | ✅ | `_month` |
| `day(d)` | 日期 | ✅ | `_day` |
| `format_date(d, fmt)` | 日期 | 🔧 | — |
| `to_string(x)` / `str(x)` | 类型转换 | ✅ | `_to_string` |
| `to_integer(x)` / `int(x)` | 类型转换 | ✅ | Python `int` |
| `to_decimal(x)` / `float(x)` | 类型转换 | ✅⚠️B-2 | `_to_decimal` |
| `to_boolean(x)` / `bool(x)` | 类型转换 | ✅ | Python `bool` |
| `to_date(x)` | 类型转换 | 🔧 | — |
| `sum(values)` | 聚合 | ✅ | `_sum` |
| `avg(values)` | 聚合 | ✅ | `_avg` |
| `count(values)` | 聚合 | ✅ | `_count` |
| `weighted_sum(c, w)` | 聚合 | ✅ | `_weighted_sum` |
| `min(...)` | 聚合 | ✅ | Python `min` |
| `max(...)` | 聚合 | ✅ | Python `max` |
| `is_null(v)` | 条件 | ✅ | `_is_null` |
| `coalesce(v1, v2, ...)` | 条件 | ✅ | `_coalesce` |
| `if_expr(c, t, e)` | 条件 | ✅ | `_if_expr` |
| `case(expr, when, default)` | 条件 | 🔧 | — |
| `abs(x)` | 数学 | ✅ | Python `abs` |
| `round(x, n)` | 数学 | ✅ | Python `round` |
| `clamp(v, min, max)` | 数学 | ✅ | `_clamp` |
| `ceil(x)` | 数学 | ✅ | `_ceil` |
| `floor(x)` | 数学 | ✅ | `_floor` |
| `sqrt(x)` | 数学 | ✅ | `_sqrt` |
| `pow(base, exp)` | 数学 | ✅ | `_pow` |
| `log(x, base?)` | 数学 | ✅ | `_log` |

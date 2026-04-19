# Formula 规范审视报告

> **审视日期**: 2026-04-19
> **审视范围**: `docs/02-design/formula/06-formula-spec.md` + `ontology_engine/engine/expression/engine.py`
> **审视流程**: Overview 对齐 → Baseline 审视 → 偏差标注 → 重写

## 审视结论

Formula 规范审视已完成，产出 3 份设计文档（README.md / l0-l1-execution.md / function-library.md），覆盖执行模型、函数库和安全约束。核心发现：当前代码与目标设计存在 5 项关键偏差，函数库实现率仅 19%（8/42），L1 执行器缺少安全校验。

## Overview 对齐结果

| Overview 概念 | Formula 规范对齐状态 | 备注 |
|---------------|---------------------|------|
| L3 Analytical Elements — formula 字段 | ✅ 完全对齐 | L3 atomic/derived 使用 formula |
| L4 Business Logic — condition.expression | ✅ 完全对齐 | 规则条件使用 formula |
| L4 Business Logic — action.formula | ✅ 完全对齐 | 算子分支内使用 formula |
| 算子与 Formula 协作边界 | ✅ 完全对齐 | Formula 单行表达式，算子结构化逻辑 |
| 两级安全执行模型 | ⚠️ 设计对齐，代码未实现 | 代码使用 simpleeval + asteval fallback |
| 函数库完整性 | ❌ 严重偏差 | 规范定义 30+ 函数，代码仅实现 11 个 |

## Baseline 审视结果

### 旧规范审视：`06-formula-spec.md`

| 维度 | 旧规范内容 | 偏差 | 处理 |
|------|-----------|------|------|
| 执行模型 | 仅提及 simpleeval / 自定义安全求值器 | 未定义 L0/L1 两级模型 | 重写为 l0-l1-execution.md |
| 函数库 | 定义了数学/字符串/日期/类型转换 4 类 | 缺少聚合/条件函数，与代码不一致 | 重写为 function-library.md |
| 安全限制 | 定义了禁止操作和字段白名单 | asteval fallback 无安全校验 | 在 l0-l1-execution.md 中定义 AST 白名单 |
| 错误处理 | 定义了 5 种错误类型 | 代码仅实现 1 种 | 在 l0-l1-execution.md 中定义错误类型体系 |
| 实现状态 | 标注了部分实现状态 | 未与代码逐项核验 | 在 function-library.md 中逐项核验 |

### 代码审视：`engine.py`

| 维度 | 代码现状 | 偏差 | 处理 |
|------|----------|------|------|
| 执行器选择 | simpleeval 失败后 fallback asteval | 应为关键词检测自动选择 | l0-l1-execution.md 定义自动选择逻辑 |
| asteval 安全 | 无 AST 校验、无资源限制 | L1 必须有 AST 白名单 + 资源限制 | l0-l1-execution.md 定义 AST 白名单 |
| 函数注册 | L0/L1 分别硬编码相同函数列表 | 应统一 SAFE_FUNCTIONS | function-library.md 定义统一函数库 |
| 错误类型 | 仅 `ExpressionSyntaxError` | 应有 5 种语义错误 | l0-l1-execution.md 定义错误类型体系 |
| 关键词预处理 | ✅ 实现完整 | 无偏差 | 保留 |
| 字段解析 | ✅ 实现完整 | 无偏差 | 保留 |
| 运算符限制 | ✅ 禁用位运算和取模 | 无偏差 | 保留 |

## 偏差矩阵

| # | 维度 | Overview 定义 | Baseline 实现 | 选择方向 | 原因 |
|---|------|---------------|---------------|----------|------|
| 1 | 执行模型 | L0/L1 两级（决策 #10） | simpleeval + asteval fallback | 重构为自动选择 | fallback 模式不安全，asteval 无校验 |
| 2 | L1 安全校验 | AST 白名单 + 资源限制 | 无校验 | 新增 AST 白名单 | asteval 可执行任意 Python，必须限制 |
| 3 | 函数库 | 6 类 42 函数 | 11 函数（含 2 个部分实现） | 按优先级补全 | 当前函数库严重不足 |
| 4 | 错误类型 | 5 种语义错误 | 1 种 ExpressionSyntaxError | 新增 4 种错误类 | 不同错误需不同处理策略 |
| 5 | 函数命名 | to_integer/to_decimal/to_boolean | int/float/bool | 迁移到新命名 | 避免 Python 内置冲突，语义更明确 |

## 安全风险分析

| # | 风险 | 严重程度 | 当前状态 | 修复方案 |
|---|------|----------|----------|----------|
| 1 | asteval 可执行 import 语句 | 🔴 高 | 测试已覆盖 import 阻断 | AST 白名单校验在执行前拦截 |
| 2 | asteval 无循环次数限制 | 🟡 中 | 无限制 | max_loop_iterations=1000 |
| 3 | asteval 无执行超时 | 🟡 中 | 无限制 | timeout_seconds=5 |
| 4 | asteval 可访问 __dict__ | 🟡 中 | simpleeval 已阻止 | L1 需额外过滤 |
| 5 | asteval fallback 触发条件过宽 | 🟡 中 | 仅检测换行符 | 关键词检测 + 换行符 |

> 注：测试 `test_import_blocked_in_asteval` 已验证 asteval 阻止了 import，但这依赖 asteval 自身限制而非主动校验。AST 白名单校验是更可靠的防御层。

## 函数库差距分析

### 按业务场景分析

| 场景 | 所需函数 | 已实现 | 缺失 | 影响 |
|------|----------|--------|------|------|
| 信用评分 | `if_expr`, `coalesce`, `round`, `clamp` | 2/4 | `if_expr`, `coalesce` | 条件逻辑必须依赖算子 |
| 风险等级 | `case`, `clamp`, `round` | 2/3 | `case` | 多分支判断必须依赖 SWITCH 算子 |
| 日期合规 | `date_diff`, `date_add`, `today` | 1/3 | `date_diff`, `date_add` | 日期计算受限 |
| 文本匹配 | `contains`, `starts_with`, `ends_with` | 0/3 | 全部 | 无法在 formula 中做文本匹配 |
| 聚合评分 | `sum`, `avg`, `weighted_sum` | 0/3 | 全部 | composite 指标无法在 formula 中聚合 |

### 实现率统计

| 类别 | 总数 | 已实现 | 实现率 |
|------|------|--------|--------|
| 字符串函数 | 11 | 0 | 0% |
| 日期函数 | 8 | 1 | 12.5% |
| 类型转换 | 5 | 2 | 40% |
| 聚合函数 | 6 | 0 | 0% |
| 条件函数 | 3 | 1 | 33.3% |
| 数学函数 | 7 | 2 | 28.6% |
| 其他 | 2 | 2 | 100% |
| **合计** | **42** | **8** | **19%** |

## 产出文件清单

| 文件 | 状态 | 核心内容 |
|------|------|----------|
| `docs/02-design/formula/README.md` | draft | Formula 规范总览、架构概览、关键设计决策 |
| `docs/02-design/formula/l0-l1-execution.md` | draft | L0/L1 两级执行模型、AST 白名单、错误类型体系 |
| `docs/02-design/formula/function-library.md` | draft | 6 类 42 函数完整定义、实现状态、优先级建议 |

## 旧文档处理

| 旧文档 | 处理方式 | 原因 |
|--------|----------|------|
| `docs/02-design/formula/06-formula-spec.md` | **[已过期入口]** 标记废弃 | 内容已被新规范完全覆盖 |

## 后续行动项

| # | 行动 | 优先级 | 依赖 |
|---|------|--------|------|
| 1 | 重构 `_select_executor`：关键词检测自动选择 L0/L1 | P0 | l0-l1-execution.md |
| 2 | 实现 AST 白名单校验 `_validate_ast` | P0 | l0-l1-execution.md |
| 3 | 新增 `FormulaSecurityError` / `FormulaTimeoutError` | P0 | l0-l1-execution.md |
| 4 | 实现 `coalesce` / `if_expr` / `contains` 函数 | P0 | function-library.md |
| 5 | 实现 `sum` / `avg` / `count` 聚合函数 | P1 | function-library.md |
| 6 | 实现 `date_diff` / `date_add` 日期函数 | P1 | function-library.md |
| 7 | 实现 `ceil` / `floor` / `pow` / `sqrt` 数学函数 | P1 | function-library.md |
| 8 | 补全字符串函数 | P2 | function-library.md |
| 9 | 函数命名迁移：int→to_integer 等 | P2 | function-library.md |
| 10 | 更新 `docs/STATUS.md` 和 `docs/TODO.md` | P1 | 全部文档完成 |

---
status: draft
phase: rewrite
source_of_truth: docs/01-overview/05-concepts.md
last_verified: "2026-04-19"
verified_against: code-and-docs
---

# Formula 表达式规范

> **[单一事实源]**: Formula 表达式设计规范的唯一入口
> **上游规范**: `docs/01-overview/05-concepts.md` — 术语定义与架构约束
> **下游实现**: `ontology_engine/engine/expression/engine.py`

## 目的

定义 OntologyEngine 中 Formula 表达式的语法、执行模型、函数库和安全约束，为 L3 指标计算和 L4 规则逻辑提供统一的表达式求值能力。

## 解决的问题

| # | 问题 | 现状 | 目标 |
|---|------|------|------|
| 1 | **执行模型模糊** | simpleeval + asteval 无条件 fallback，无分级策略 | L0/L1 两级执行模型，自动选择执行器 |
| 2 | **函数库不完整** | 仅实现 11 个内置函数，规范定义了 30+ | 按函数库规范补全，标注实现状态 |
| 3 | **安全边界不明确** | asteval fallback 缺少 AST 白名单校验 | L1 执行器必须经过 AST 白名单校验 |
| 4 | **错误类型混乱** | 仅 `ExpressionSyntaxError` 一种错误类型 | 按语义细分：Timeout / Security / Syntax / Type / Name |
| 5 | **规范与代码脱节** | 旧规范 `06-formula-spec.md` 未反映 L0/L1 设计 | 重写规范，与代码实现逐项对齐 |

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│  调用方                                              │
│  L3 MetricEngine / L4 RuleEngine / API              │
└──────────────────────┬──────────────────────────────┘
                       │ evaluate(expr, context)
                       ▼
┌─────────────────────────────────────────────────────┐
│  ExpressionEngine                                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  _select_executor(expr)                       │  │
│  │  检测控制流关键词 → L0 或 L1                   │  │
│  └───────┬───────────────────────┬───────────────┘  │
│          │                       │                   │
│          ▼                       ▼                   │
│  ┌───────────────┐     ┌───────────────────┐        │
│  │ L0: SimpleEval│     │ L1: ASTSandbox    │        │
│  │ Executor      │     │ Executor          │        │
│  │               │     │                   │        │
│  │ simpleeval    │     │ AST 白名单校验     │        │
│  │ SAFE_FUNCTIONS│     │ max_loop_iters    │        │
│  │ 快速执行      │     │ timeout_seconds   │        │
│  └───────────────┘     └───────────────────┘        │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Function Library                                    │
│  String / Date / Type / Aggregation / Conditional   │
│  / Math                                              │
└─────────────────────────────────────────────────────┘
```

## 关键设计决策

| # | 决策 | 选择 | 备选 | 原因 |
|---|------|------|------|------|
| 1 | 执行模型 | L0/L1 两级 | 单一 simpleeval | 简单表达式需要快速执行，复杂控制流需要沙箱隔离 |
| 2 | L0 执行器 | simpleeval | lark 解析器 | simpleeval 已验证，安全模型成熟，社区活跃 |
| 3 | L1 执行器 | asteval + AST 白名单 | 自建解释器 | asteval 提供受限 Python 执行，叠加 AST 白名单增强安全 |
| 4 | 自动选择策略 | 关键词检测 | AST 分析 | 关键词检测简单高效，覆盖 for/while/if/try 等控制流 |
| 5 | 函数库范围 | 6 类 30+ 函数 | 最小集 | 覆盖金融场景常见计算需求，避免算子膨胀 |
| 6 | 错误类型 | 5 种语义错误 | 单一 Exception | 不同错误类型需要不同处理策略（重试/告警/拒绝） |
| 7 | 空值语义 | null 传播 + COALESCE | 三值逻辑 | 与 SQL 一致，领域专家熟悉 |

## 文档索引

| 文档 | 内容 | 状态 |
|------|------|------|
| [l0-l1-execution.md](l0-l1-execution.md) | L0/L1 两级执行模型 | draft |
| [function-library.md](function-library.md) | 完整函数库规范 | draft |

## 旧文档处理

| 旧文档 | 处理方式 | 原因 |
|--------|----------|------|
| `06-formula-spec.md` | **[已过期入口]** 保留但标记废弃 | 内容已被本规范及子文档覆盖 |

## 与算子的协作边界

Formula 负责**单行表达式求值**，算子负责**结构化复杂逻辑**：

| 场景 | 使用 Formula | 使用算子 |
|------|-------------|---------|
| 简单算术 | `registered_capital * 0.5` | - |
| 条件判断 | `credit_score >= 60` | - |
| 多分支逻辑 | - | SWITCH 算子 |
| 评分卡 | - | SCORECARD 算子 |
| 加权求和 | - | WEIGHTED_SUM 算子 |
| 图计算 | - | GRAPH 算子 |

## 与其他模块的关系

| 模块 | 关系 | 接口 |
|------|------|------|
| L3 MetricEngine | 调用方 | `formula` 字段传入 ExpressionEngine |
| L4 RuleEngine | 调用方 | `condition.expression` 和 `action.formula` 传入 |
| OperatorRegistry | 互补 | 算子内部可调用 Formula 做分支内计算 |
| Storage | 禁止直接调用 | 遵守模块边界约束 |

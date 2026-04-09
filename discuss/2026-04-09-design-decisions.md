# 架构评审关键设计决策

> 日期：2026-04-09
> 依据：2026-04-09-architecture-review-report.md
> 参与者：用户 + AI Agent

## 决策总表

| # | 决策点 | 选择 | 理由 |
|---|--------|------|------|
| 1 | 愿景定义 | **B** - 收窄为「结构化知识推理引擎」 | 可衡量、定位清晰，避免「下一代知识库」过于泛化 |
| 2 | Phase 1 性能目标 | **C** - 分级：简单 200ms / 图遍历 1s / 混合 500ms | 务实覆盖不同场景，避免单一激进指标 |
| 3 | L3/L4 覆盖机制 | **B** - L3 标记 `overridable=true` 才允许覆盖 | 显式声明比隐式覆盖更安全，防止意外覆盖 |
| 4 | Hybrid 检索权重 | **C** - 自适应权重（Phase 2 实现） | MVP 先用固定权重，Phase 2 引入自适应 |
| 5 | 反馈闭环机制 | **C** - 自动触发影响分析+生成建议，执行必须人工确认 | 平衡自动化与安全，避免无人监管的自动更新 |
| 6 | L2 归类规则引擎 | **A** - 复用 L4 规则引擎（CategorizationEngine 调用 RuleEngine） | 减少代码重复，统一执行模型 |
| 7 | 平台化策略 | **B** - 本地+平台双模式，审计 Schema Phase 1 纳入 | 满足用户平台化需求，同时保持本地优先 |
| 8 | Schema 版本管理 | **A** - 全量快照 | 简单优先，Phase 1 快速实现 |
| 9 | 图查询 API | **B** - 简化版图遍历 DSL（1-2跳+属性过滤） | 避免 Cypher 空壳，提供实际可用的图查询能力 |
| 10 | L4 Formula 规范 | **C** - 分两级：simpleeval + Python 沙箱 | 安全与表达力的平衡，自动按复杂度切换 |
| 11 | L3→L4 跨引擎协调 | **B** - 直接调用（MetricEngine → RuleEngine） | 性能优先，减少中间写入开销 |
| 12 | 文档结构清理 | **A** - 立即清理，统一到 docs/ | 消除混乱，避免后续维护歧义 |

## 详细决策说明

### 决策 1：愿景定义

- **原愿景**：面向 AI Agent 的下一代知识库系统 —— 让机器像专家一样理解业务语义
- **新愿景**：面向 AI Agent 的结构化知识推理引擎 —— 将专家业务规则转化为可执行、可追溯、可组合的知识网络
- **影响文件**：`docs/01-overview/01-vision.md`

### 决策 2：性能目标分级

| 查询类型 | P99 目标 | 说明 |
|----------|----------|------|
| 简单查询（CRUD/过滤） | < 200ms | 单表操作，索引命中 |
| 图遍历（1-2 跳邻居） | < 1s | DuckDB 递归 CTE |
| 混合检索（语义+图） | < 500ms | 向量召回 + 图过滤 |

- **影响文件**：`docs/01-overview/03-goals.md`

### 决策 3：L3/L4 覆盖机制

- L3 分析要素的 `default_formula` 增加 `overridable` 字段
- `overridable: true`（默认）→ L4 可覆盖
- `overridable: false` → L4 覆盖时抛出 SchemaValidationError
- **影响文件**：`docs/05-schema-v2/03-analytical-elements.md`、`docs/05-schema-v2/04-business-logic.md`

### 决策 4：Hybrid 检索权重

- Phase 1：固定权重 `semantic:0.6 + graph:0.4`
- Phase 2：自适应权重（根据查询意图和结果质量动态调整）
- **影响文件**：`docs/08-knowledge-retrieval.md`

### 决策 5：反馈闭环

- 反馈记录 → 自动触发影响分析 → 生成变更建议 → 人工确认执行
- 不允许自动执行变更，所有变更必须经过人工审核
- **影响文件**：`docs/07-agent-interface.md`

### 决策 6：L2 归类规则复用 L4 引擎

- `CategorizationEngine` 将 L2 的 `condition→result` 规则编译为 L4 规则格式
- 调用 `RuleEngine.execute()` 执行
- 统一 DAG 拓扑执行模型
- **影响文件**：`docs/05-schema-v2/02-categorization.md`、`docs/02-design/04-rule-engine-design.md`

### 决策 7：平台化双模式

- 配置文件驱动：`deployment_mode: local | platform`
- 审计 Schema（audit_log 表）Phase 1 纳入存储设计
- 本地模式：审计写本地 DuckDB
- 平台模式：审计通过中间件转发到平台审计服务
- **影响文件**：`docs/02-design/03-storage-design.md`

### 决策 8：Schema 版本全量快照

- 每次变更存储完整 Schema 副本
- `schema_versions` 表：`id, version, schema_snapshot(JSON), change_description, created_at, created_by`
- 优点：实现简单、回滚直接、无 diff 算法依赖
- 缺点：存储开销（可接受，Schema 文件通常 < 100KB）
- **影响文件**：`docs/02-design/03-storage-design.md`

### 决策 9：简化版图遍历 DSL

- 替代 Cypher，自研轻量 DSL
- 支持：节点查找 → 1-2 跳邻居扩展 → 属性过滤 → 结果聚合
- API：`POST /v1/query/graph` 接受新 DSL 格式
- Phase 2 考虑开放更复杂的图查询能力
- **影响文件**：`docs/02-design/02-api-design.md`

### 决策 10：L4 Formula 两级执行

| 级别 | 触发条件 | 执行器 | 安全约束 |
|------|----------|--------|----------|
| L0-简单表达式 | 无控制流关键词 | simpleeval | 白名单函数，无副作用 |
| L1-复杂逻辑 | 含 if/for/while | AST 白名单沙箱 | 禁止 import/exec/eval/open，循环上限 1000 次，执行超时 5s |

- **影响文件**：`docs/05-schema-v2/04-business-logic.md`

### 决策 11：L3→L4 直接调用

- `MetricEngine.calculate()` → 返回指标结果 dict
- `RuleEngine.execute(facts=..., metrics=metric_result)` 
- 无中间写入，减少 I/O 开销
- 服务层编排调用顺序
- **影响文件**：`docs/02-design/04-rule-engine-design.md`

### 决策 12：文档结构立即清理

- 删除根目录旧文件（roadmap.md, concepts.md 等）
- 合并 `development/` 到 `docs/` 对应位置
- 确保无断链

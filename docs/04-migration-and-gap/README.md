# 当前实现 → 目标架构：迁移与差距

> **状态**: accepted
> **Phase**: phase1
> **Source of Truth**: true
> **Last Verified**: 2026-04-12 (`docs-only`)

## 作用

本目录统一回答一个问题：**当前代码 / 当前设计 / 目标架构之间，哪里一致，哪里冲突，接下来怎么迁移。**

以后凡是遇到“同一主题有多套说法”的情况，优先先落到这里，而不是分散修改多个目录又留下新的重复。

## 迁移矩阵

| 主题 | 当前态 | 目标态 | 实施层 | 当前判断 | 处理建议 |
|------|--------|--------|--------|----------|----------|
| Schema 根结构 + 内层 grammar | [`02-design/01-schema-spec.md`](../02-design/01-schema-spec.md) | [`05-schema-v2/09-canonical-schema-spec.md`](../05-schema-v2/09-canonical-schema-spec.md) | [`06-module-detailed-design/01-schema-loading.md`](../06-module-detailed-design/01-schema-loading.md) | **[关键设计点]** ✅ 已冻结 L1-L4 内层 grammar（2026-04-14） | 01-04 分层文档 + 05-complete-example.md 向 grammar 对齐中（Task #3 #4 执行中） |
| Rule 模型 | 旧 `ruleset / rule_group` 叙述散见于概览与示例 | `rule_definitions + rule_logics` | [`06-module-detailed-design/06-rule-engine.md`](../06-module-detailed-design/06-rule-engine.md) | **[待扩展]** 仍有双轨叙事 | 建议补专题 ADR 或迁移映射表 |
| Formula / Expression | [`02-design/06-formula-spec.md`](../02-design/06-formula-spec.md) | `05-schema-v2/*` 的目标算子与逻辑约定 | [`06-module-detailed-design/07-expression-engine.md`](../06-module-detailed-design/07-expression-engine.md) | **[待核对代码]** 设计描述多于已验证实现 | 继续与 `ontology_engine/engine/expression/`、`ontology_engine/engine/rule/evaluator.py` 逐段核验 |
| API 形态 | `/v1/schema`、`/v1/entities` 等当前 FastAPI 口径 | `/v1/management`、`/v1/consumption` 等空间 API | [`06-module-detailed-design/10-api-layer.md`](../06-module-detailed-design/10-api-layer.md) | **[待扩展]** 现在还没有稳定映射文档 | 建议补 current API / target API / migration 三段式说明 |
| 引擎拆分 | 当前代码与旧设计存在 `Vector / Query` 口径差异 | 目标态倾向统一查询能力 | [`docs/02-design/query-engine-current.md`](../02-design/query-engine-current.md), [`docs/05-schema-v2/query-engine-target.md`](../05-schema-v2/query-engine-target.md) | **[待核对代码]** | 先在模块 README 中标清”当前实现 vs 目标收敛” |
| 查询引擎 | QueryService（当前 BFS/DFS，无向量） | Vector/Hybrid/DSL + kuzu | docs/02-design/query-engine-current.md, docs/05-schema-v2/query-engine-target.md | **[待核对代码]** | |
| 平台化能力 **[待扩展]** | 当前约束仍以本地优先为主 | 目标态引入空间、同步、管理面 | [`05-schema-v2/06-dataset-and-sync.md`](../05-schema-v2/06-dataset-and-sync.md) **[单一事实源]** | **[待扩展]** | 能力矩阵已更新，详见数据集与同步文档第 6 节 |
| StorageBackend | 单体接口 DuckDBStorage | Repository 接口分离 + kuzu 协同 | docs/development/storage-repository-pattern.md | **[待扩展]** |

## Schema Loading 模块核验结论 (2026-04-13)

> 核验文档: [`06-module-detailed-design/01-schema-loading.md`](../06-module-detailed-design/01-schema-loading.md)
> 核验范围: `ontology_engine/core/schema/`

### 当前态 vs 设计差异

| 主题 | 设计 (v2 canonical) | 当前实现 | 差距 |
|------|---------------------|----------|------|
| KGMLSchema 结构 | `entities`, `relations`, `categories`, `rule_dimensions`, `rules` 分离 | `concepts` (含 entity/relation), `rules: RulesDefinition` | **[关键设计点]** v2 分离式模型尚未实现 |
| CategoryDimension | `categories: list[CategoryDimension]` | 不存在 | 缺失 |
| RuleDimension | `rule_dimensions: list[RuleDimension]` | `rules.rule_dimensions: list[RuleDimension]` (在 RulesDefinition 内) | 结构差异 |
| v1 兼容映射 | `v1_compat.py` 完整实现 | 不存在 | 待实现 |
| 版本管理器 | `version_manager.py` 完整实现 | 不存在 | 待实现 |
| Schema 差异计算 | `diff.py` 完整实现 | 不存在 | 待实现 |

### 迁移建议
- 当前 `KGMLSchema` 仍保持 v1 风格 (`concepts` 统一列表)
- v2 分离式模型需等 canonical grammar 稳定后逐步迁移
- v1_compat、version_manager、diff 列入 Phase 2

---

## Rule Engine 模块核验结论 (2026-04-13)

> 核验文档: [`06-module-detailed-design/06-rule-engine.md`](../06-module-detailed-design/06-rule-engine.md)
> 核验范围: `ontology_engine/engine/rule/`

### 当前态 vs 设计差异

| 主题 | 设计 (RuleEngine DAG驱动) | 当前实现 (RuleExecutor) | 差距 |
|------|-------------------------|----------------------|------|
| 主类 | `RuleEngine` (engine.py, DAG驱动) | `RuleExecutor` (executor.py, 顺序执行) | **[关键设计点]** 目标态尚未实现 |
| DAG 构建 | `dag.py` RuleDAG 类 | 不存在 | 待实现 |
| 动作执行器 | `action_executor.py` 独立模块 | 内联在 executor.py | 结构差异 |
| GraphTraversalOperator | `operators/graph_ops.py` | `operators/alert_ops.py` | 文件位置差异 |
| RuleDefinition.else_ | `ActionClause \| None` | `dict \| None` | 类型差异 |
| execute 方法签名 | `execute(inputs, config, context)` | `execute(inputs, config, context)` | ✅ 一致 |
| OperatorRegistry | `@register` 装饰器风格 | `@OperatorRegistry.register(name)` | 风格一致 |

### 迁移建议
- 当前 `RuleExecutor` 是 MVP 实现，顺序执行规则
- 目标态 `RuleEngine` (DAG驱动) 需等 `dag.py` 实现后升级
- 建议保留 `RuleExecutor` 别名兼容，待完全迁移后替换

---

## 本轮收敛结论

- **[关键设计点]** 以后不再让 `README.md` 承担状态页和任务页职责
- **[关键设计点]** 以后不再让不同文档各自维护一套 Schema v2 根语法
- **[关键设计点]** 当前态、目标态、实施态必须分别在不同目录表达，再通过本目录连接
- **[待扩展]** Rule 模型、L3/L4 边界、空间状态机仍需继续用 ADR 或专题规范冻结
- **[待核对代码]** 模块设计文档中的示例代码、固定数字、组件命名都必须与实际代码复核后才能转为 `accepted`

## 使用规则

1. 发现冲突时，先记录“冲突双方 + 影响 + 收敛建议”，不要直接在多个目录复制同一段说明
2. 迁移说明必须同时给出：当前态入口、目标态入口、实施入口
3. 若冲突已经解决，要同步更新 [`STATUS.md`](../STATUS.md) 和相关主题文档
4. 若迁移涉及关键取舍，应沉淀到 `architecture/decisions/` 或 `03-rfc/`

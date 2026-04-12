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
| Schema 根结构 | [`02-design/01-schema-spec.md`](../02-design/01-schema-spec.md) | [`05-schema-v2/09-canonical-schema-spec.md`](../05-schema-v2/09-canonical-schema-spec.md) | [`06-module-detailed-design/01-schema-loading.md`](../06-module-detailed-design/01-schema-loading.md) | **[关键设计点]** 已建立单一 grammar 入口 | 先让完整示例与 loader 设计向 canonical grammar 靠拢 |
| Rule 模型 | 旧 `ruleset / rule_group` 叙述散见于概览与示例 | `rule_definitions + rule_logics` | [`06-module-detailed-design/06-rule-engine.md`](../06-module-detailed-design/06-rule-engine.md) | **[待扩展]** 仍有双轨叙事 | 建议补专题 ADR 或迁移映射表 |
| Formula / Expression | [`02-design/06-formula-spec.md`](../02-design/06-formula-spec.md) | `05-schema-v2/*` 的目标算子与逻辑约定 | [`06-module-detailed-design/07-expression-engine.md`](../06-module-detailed-design/07-expression-engine.md) | **[待核对代码]** 设计描述多于已验证实现 | 继续与 `ontology_engine/engine/expression/`、`ontology_engine/engine/rule/evaluator.py` 逐段核验 |
| API 形态 | `/v1/schema`、`/v1/entities` 等当前 FastAPI 口径 | `/v1/management`、`/v1/consumption` 等空间 API | [`06-module-detailed-design/10-api-layer.md`](../06-module-detailed-design/10-api-layer.md) | **[待扩展]** 现在还没有稳定映射文档 | 建议补 current API / target API / migration 三段式说明 |
| 引擎拆分 | 当前代码与旧设计存在 `Vector / Query` 口径差异 | 目标态倾向统一查询能力 | [`06-module-detailed-design/08-query-engine.md`](../06-module-detailed-design/08-query-engine.md) | **[待核对代码]** | 先在模块 README 中标清“当前实现 vs 目标收敛” |
| 平台化能力 **[待扩展]** | 当前约束仍以本地优先为主 | 目标态引入空间、同步、管理面 | [`05-schema-v2/06-dataset-and-sync.md`](../05-schema-v2/06-dataset-and-sync.md) **[单一事实源]** | **[待扩展]** | 能力矩阵已更新，详见数据集与同步文档第 6 节 |

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

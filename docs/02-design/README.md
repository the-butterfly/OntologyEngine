# 02-design 目录说明

> **角色**: 当前实现基线（MVP / current baseline）
> **状态**: transitional
> **Phase**: mvp
> **Source of Truth**: true（仅针对当前实现口径）

## 这个目录回答什么

本目录回答的是：**今天的代码与当前设计，大致是按什么方式组织和实现的。**

如果某处内容与目标态设计冲突，不代表本目录错误；它通常意味着该主题正在迁移中。迁移关系请看 [`../04-migration-and-gap/README.md`](../04-migration-and-gap/README.md)。

## 推荐阅读顺序

1. `01-schema-spec.md`
2. `03-storage-design.md`
3. `04-rule-engine-design.md`
4. `06-formula-spec.md`
5. `05-services-design.md`
6. `02-api-design.md`

## 目录内文档职责

| 文档 | 当前职责 | 备注 |
|------|----------|------|
| `01-schema-spec.md` | MVP Schema 结构说明 | 后续会逐步向 v2 grammar 迁移 |
| `02-api-design.md` | 当前 FastAPI 设计口径 | 不等同于目标空间 API |
| `03-storage-design.md` | 当前本地优先存储架构 | 与平台化能力需分开理解 |
| `04-rule-engine-design.md` | 当前规则执行模型口径 | 需与模块实施设计进一步对齐 |
| `05-services-design.md` | 当前服务层职责分解 | 需继续与实际 `services/` 代码核验 |
| `06-formula-spec.md` | 当前表达式 / Formula 设计口径 | 需与当前代码逐项核验 |

## 使用边界

- 当问题是“现在代码应该怎么理解”时，优先查本目录
- 当问题是“未来希望收敛成什么规范”时，转到 [`../05-schema-v2/README.md`](../05-schema-v2/README.md)
- 当问题是“怎么落成 Phase 1 模块”时，转到 [`../06-module-detailed-design/README.md`](../06-module-detailed-design/README.md)

## 重点提示

- **[关键设计点]** 本目录是 current baseline，不再承载目标态平台设计
- **[关键设计点]** 若当前代码与本目录冲突，以代码 + [`../STATUS.md`](../STATUS.md) + 迁移层文档综合判断
- **[待扩展]** 各文档后续需要补充 `last_verified` / `verified_against` 元数据
- **[待核对代码]** `02-api-design.md` 需与 `ontology_engine/api/server.py` 继续核验
- **[待核对代码]** `06-formula-spec.md` 需与 `ontology_engine/engine/expression/`、`ontology_engine/engine/rule/evaluator.py` 继续核验

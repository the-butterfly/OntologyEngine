# 文档状态总表

> **作用**: `docs/` 下唯一状态页
> **最后更新**: 2026-04-12
> **使用规则**: 判断文档是否可信、是否过期、是否仍是当前入口时，以本页为准

## 状态说明

| 状态 | 含义 |
|------|------|
| `accepted` | 已收敛，可作为当前规范使用 |
| `draft` | 已成形，但仍可能调整 |
| `transitional` | 过渡态，通常连接当前实现与目标设计 |
| `deprecated` | 仅保留历史参考，不再继续维护 |
| `planned` | 已列入收敛计划，但尚未完整成文 |

## 目录级状态矩阵

| 对象 | 角色 | 状态 | Phase | SoT | 备注 |
|------|------|------|-------|-----|------|
| [`README.md`](./README.md) | 文档地图 | accepted | now | 是 | 只负责导航，不维护细节 |
| [`STATUS.md`](./STATUS.md) | 状态页 | accepted | now | 是 | 统一表达文档有效性 |
| [`ROADMAP.md`](./ROADMAP.md) | 路线图 | accepted | now | 是 | 统一表达阶段目标 |
| [`TODO.md`](./TODO.md) | backlog | accepted | now | 是 | 只保留开放事项 |
| [`01-overview/`](./01-overview/README.md) | 项目概览 | accepted | mvp+phase1 | 主题级 | 仅承担愿景、目标、术语、边界说明 |
| [`02-design/`](./02-design/README.md) | 当前实现基线 | transitional | mvp | 主题级 | 表达当前实现口径，需持续与代码核验 |
| [`04-migration-and-gap/`](./04-migration-and-gap/README.md) | 迁移层 | accepted | phase1 | 是 | 统一记录冲突点与迁移路径 |
| [`05-schema-v2/`](./05-schema-v2/README.md) | 目标架构 | draft | phase1+future | 主题级 | 目标态规范，部分专题仍待冻结 |
| [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) | Schema v2 根语法 | accepted | phase1 | 是 | **[单一事实源]** 根 grammar 以后以此为准 |
| [`06-module-detailed-design/`](./06-module-detailed-design/README.md) | 实施设计 | draft | phase1 | 主题级 | 模块职责与实现拆解，但部分章节需核对代码 |
| [`03-rfc/`](./03-rfc/) | RFC 历史记录 | accepted | history | 是 | 历史决策背景 |
| [`architecture/decisions/`](./architecture/decisions/) | ADR / 决策记录 | accepted | now | 是 | 冻结关键取舍 |
| [`development/`](./development/) | 开发规范 | accepted | now | 是 | 代码 / 测试 / 扩展规则 |
| [`archive/`](./archive/) | 归档区 | deprecated | history | 否 | 仅保留历史参考 |

## 热点质量问题

| 主题 | 标注 | 现状 | 处理入口 |
|------|------|------|----------|
| Schema v2 根结构 | **[关键设计点]** | 已新增 canonical grammar，后续需要逐步同步旧示例 | [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) |
| Rule 模型双轨叙事 | **[待扩展]** | `rule_group` 与 `rule_definition + rule_logic` 仍在部分旧文档并存 | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) |
| Formula / Expression 执行模型 | **[待核对代码]** | 设计文档与当前实现尚未逐段核验 | [`02-design/README.md`](./02-design/README.md) |
| Current API vs Target API | **[待扩展]** | 当前 FastAPI 与目标空间 API 仍需进一步拆清 | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) |
| 术语统一 | **[待扩展]** | `Concept / Fact Object / Entity` 等用法仍需归并 | [`01-overview/README.md`](./01-overview/README.md) |

## 重点核验清单

- **[待核对代码]** `02-design/02-api-design.md`: 需继续和 `ontology_engine/api/server.py` 对齐
- **[待核对代码]** `02-design/06-formula-spec.md`: 需继续和 `ontology_engine/engine/expression/`、`ontology_engine/engine/rule/evaluator.py` 对齐
- **[待核对代码]** `06-module-detailed-design/07-expression-engine.md`: 当前以设计目标为主，不能视为现状实现文档
- **[待核对代码]** `06-module-detailed-design/10-api-layer.md`: 路由细节需与当前 FastAPI 代码逐项复核

## 更新要求

1. 只要出现新的文档入口、角色变化或过期判断变化，必须更新本页
2. 代码实现显著偏离设计文档时，先更新本页和迁移层文档，再决定是否重写专题文档
3. 已完成事项不要继续停留在 `TODO.md`；若影响阶段判断，则同步更新 `ROADMAP.md`
4. 若某篇文档被新文档替代，应在本页与文档头部同时标明 `deprecated` 或 `superseded`

# OntologyEngine 文档地图

> **当前阶段**: MVP 已跑通，Phase 1 设计收敛中
> **最后更新**: 2026-04-12
> **维护原则**: 根 `README.md` 只负责导航、分层说明和单一事实源（SoT）索引，不重复维护详细设计与执行状态

## 从哪里开始读

- **新读者**: 先读 [`01-overview/README.md`](./01-overview/README.md)，再看 [`01-overview/03-goals.md`](./01-overview/03-goals.md)
- **实现者**: 先读 [`02-design/README.md`](./02-design/README.md)、[`06-module-detailed-design/README.md`](./06-module-detailed-design/README.md)、[`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md)
- **架构评审者**: 先读 [`05-schema-v2/README.md`](./05-schema-v2/README.md)、[`STATUS.md`](./STATUS.md)
- **Agent / 自动化任务**: 先读 [`../CLAUDE.md`](../CLAUDE.md)、[`STATUS.md`](./STATUS.md)、[`ROADMAP.md`](./ROADMAP.md)

## 文档分层

| 层级 | 目录 / 文件 | 角色 | 是否承担 SoT | 说明 |
|------|-------------|------|---------------|------|
| 入口层 | [`README.md`](./README.md) | 文档地图 | 否 | 只负责导航和职责边界 |
| 状态层 | [`STATUS.md`](./STATUS.md) | 当前状态总表 | 是 | 统一记录文档状态、有效性、热点风险 |
| 路线层 | [`ROADMAP.md`](./ROADMAP.md) | 阶段目标与收敛顺序 | 是 | 记录阶段性目标，不记录细碎执行项 |
| Backlog 层 | [`TODO.md`](./TODO.md) | 进行中 / 未完成事项 | 是 | 只保留未完成事项，不记录完成项历史 |
| 认知层 | [`01-overview/`](./01-overview/) | 为什么做、做什么、不做什么 | 主题级 SoT | 只放概览与术语，不放实现细节 |
| 当前态 | [`02-design/`](./02-design/) | MVP / 当前实现基线 | 主题级 SoT | 回答“今天代码大致是什么” |
| 目标态 | [`05-schema-v2/`](./05-schema-v2/) | Schema v2 / 目标架构 | 主题级 SoT | 回答“未来规范收敛到什么” |
| 迁移层 | [`04-migration-and-gap/`](./04-migration-and-gap/) | 当前态到目标态映射 | 是 | 统一记录冲突点、缺口、迁移路径 |
| 实施层 | [`06-module-detailed-design/`](./06-module-detailed-design/) | Phase 1 模块设计 | 主题级 SoT | 回答“如何落成模块与接口” |
| 规范层 | [`development/`](./development/) | 开发与协作规范 | 是 | 代码规范、测试规范、扩展指南 |
| 决策层 | [`03-rfc/`](./03-rfc/)、[`architecture/decisions/`](./architecture/decisions/) | RFC / ADR / 决策记录 | 是 | 冻结关键取舍，不再散落在其他文档 |

## 单一事实源（Source of Truth）

| 主题 | 唯一入口 | 说明 |
|------|----------|------|
| 文档有效性 / 过期情况 | [`STATUS.md`](./STATUS.md) | 不再在多个索引页重复维护状态 |
| 阶段目标 / 收敛顺序 | [`ROADMAP.md`](./ROADMAP.md) | 不再在 `README.md` / `TODO.md` 重复维护路线图 |
| 开放任务 / backlog | [`TODO.md`](./TODO.md) | 只保留未完成事项 |
| 当前实现与目标架构的差距 | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) | 统一记录“冲突、缺口、迁移路径” |
| Schema v2 根语法 | [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) | 统一根级 grammar，其他文档不再各写一套 |
| 项目愿景 / 目标 / 非目标 | [`01-overview/`](./01-overview/README.md) | 只在概览层表达，不在实施层重复 |

## 关键标注约定

后续核心设计文档统一使用以下标注：

- **[单一事实源]**: 当前主题的唯一规范入口
- **[关键设计点]**: 已收敛、实现或评审时必须优先关注的核心约束
- **[待扩展]**: 已确认方向，但细节仍待补充
- **[待核对代码]**: 文档内容尚未与当前代码逐项核验，不能直接当作实现真相
- **[已过期入口]**: 历史入口或旧叙述，保留仅为兼容阅读

## 文档地图

### `01-overview/`

项目认知入口，回答“为什么做、要达成什么、边界在哪里”。

- 入口: [`01-overview/README.md`](./01-overview/README.md)
- 推荐阅读: `03-goals.md` → `04-modules.md` → `05-concepts.md`

### `02-design/`

当前实现基线，回答“今天代码大致依赖什么、怎么分层、怎么跑起来”。

- 入口: [`02-design/README.md`](./02-design/README.md)
- 重点: API / Storage / Rule / Formula / Services 的当前口径

### `04-migration-and-gap/`

统一放置当前态与目标态之间的映射关系，避免把“冲突说明”散落在多个目录。

- 入口: [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md)

### `05-schema-v2/`

目标架构与目标 Schema 规范，回答“未来需要收敛到什么结构与语义”。

- 入口: [`05-schema-v2/README.md`](./05-schema-v2/README.md)
- **[单一事实源]**: [`09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md)

### `06-module-detailed-design/`

Phase 1 的模块详细设计，回答“目标架构如何拆成可实现模块”。

- 入口: [`06-module-detailed-design/README.md`](./06-module-detailed-design/README.md)
- 推荐顺序: `00-overview.md` → `01/03/07` → `04/05/06` → `09/10`

### 其他目录

- [`03-rfc/`](./03-rfc/): 历史 RFC
- [`architecture/decisions/`](./architecture/decisions/): 架构决策记录
- [`development/`](./development/): 开发规范与扩展指南
- [`archive/`](./archive/): 已归档或不再维护的文档

## 当前最需要关注的收敛点

- **[关键设计点]**: 当前文档体系已明确区分“认知入口 / 当前态 / 目标态 / 迁移层 / 实施层 / Backlog / 路线图”
- **[关键设计点]**: Schema v2 根级语法以后以 [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) 为准
- **[待扩展]**: L3 / L4 计算边界、空间生命周期、平台化能力边界仍需继续冻结为 ADR 或专题规范
- **[待核对代码]**: `02-design/*` 与 `06-module-detailed-design/*` 中仍有部分内容属于设计口径，不能跳过代码核验直接作为实现真相

## 文档维护约定

1. `README.md` 不再维护详细任务、端点数量、服务数量等易漂移内容
2. `STATUS.md` 是唯一状态页；文档是否过期、是否可信，以它为准
3. `ROADMAP.md` 是唯一阶段路线图；`TODO.md` 只追踪未完成事项
4. 设计冲突、当前态 → 目标态映射，一律先收敛到 [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md)
5. 同一主题只能有一个主规范；其他文档应链接引用，而不是重复定义
6. 核心设计文档新增或重写时，应补充 `status`、`phase`、`source_of_truth`、`last_verified`、`verified_against` 等元数据

## 已知容易误读的文档

| 文档 | 当前标注 | 说明 |
|------|----------|------|
| [`05-schema-v2/05-complete-example.md`](./05-schema-v2/05-complete-example.md) | **[待扩展]** | 示例尚需和 canonical grammar 进一步同步 |
| [`06-module-detailed-design/07-expression-engine.md`](./06-module-detailed-design/07-expression-engine.md) | **[待核对代码]** | 设计口径多于已验证实现 |
| [`06-module-detailed-design/10-api-layer.md`](./06-module-detailed-design/10-api-layer.md) | **[待核对代码]** | 不能再把端点数量当作长期真相 |
| [`01-overview/05-concepts.md`](./01-overview/05-concepts.md) | **[待扩展]** | 仍需继续与 Schema v2 术语统一 |

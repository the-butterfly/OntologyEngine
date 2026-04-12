# 文档与架构收敛路线图

> **作用**: `docs/` 下唯一阶段路线图
> **最后更新**: 2026-04-12
> **使用规则**: 本页只记录阶段目标与收敛顺序，不记录细碎执行项；开放任务请看 [`TODO.md`](./TODO.md)

## 当前判断

当前已从“文档散写”切换到“按职责治理”的阶段，近期重点不是继续扩写更多设计，而是先冻结入口、语法和迁移关系。

## 阶段路线

| 阶段 | 目标 | 主要输出 | 对应文档 |
|------|------|----------|----------|
| Now | 建立文档治理骨架 | 根入口、状态页、路线图、迁移层、目录 README | [`README.md`](./README.md)、[`STATUS.md`](./STATUS.md)、[`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) |
| P0 | 冻结高风险规范 | Canonical schema grammar、API 当前态/目标态边界、Formula 执行口径 | [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md)、[`02-design/README.md`](./02-design/README.md) |
| P1 | 收敛术语与模块映射 | 术语表统一、模块设计逐步加上代码核验标记 | [`01-overview/README.md`](./01-overview/README.md)、[`06-module-detailed-design/README.md`](./06-module-detailed-design/README.md) |
| P2 | 冻结平台化扩展设计 | 语义空间生命周期、版本管理、管理面 / 消费面 API | [`05-schema-v2/`](./05-schema-v2/README.md)、[`10-api-architecture.md`](./10-api-architecture.md) |
| P3 | 以代码为准回写设计 | 关键模块完成实现后，把 `draft` 转为 `accepted` | `02-design/*`、`06-module-detailed-design/*` |

## 当前收敛重点

### P0：必须优先完成

- **冻结 Schema v2 根级 grammar**，后续所有示例统一向它靠拢
- **拆清 Current API 与 Target API**，避免同一实现阶段维护两套真相
- **给高风险文档加显式标注**，尤其是设计口径多于代码现实的章节
- **建立迁移层文档**，统一记录冲突点与收敛路径

### P1：紧随其后

- **统一术语表**，收敛 `Concept / Fact Object / Entity` 等并行概念
- **收敛 Rule 模型**，逐步清理 `rule_group` 历史写法
- **把模块设计和当前代码建立映射**，为后续实现 / review / agent 执行提供可靠入口

### P2：中期工作

- **冻结空间状态机和版本管理口径**
- **收敛平台化能力边界**，明确哪些属于 current / optional / future
- **把关键 ADR 从散落讨论中提炼出来**

## 退出标准

当以下条件满足时，文档体系可视为完成本轮收敛：

1. `README / STATUS / ROADMAP / TODO` 四个根入口职责不再重叠
2. Schema v2 只有一套根语法入口
3. 当前态 / 目标态 / 实施层之间都有明确映射关系
4. 高风险文档均带有 **[待扩展]** 或 **[待核对代码]** 标记
5. `CLAUDE.md` 已同步文档治理约定，后续 Agent 能按同一规则持续演进

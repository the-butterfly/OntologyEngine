# 实施 Backlog

> **作用**: `docs/` 下唯一开放事项列表
> **最后更新**: 2026-04-12
> **说明**: 本文件只保留进行中 / 未完成事项；文档状态看 [`STATUS.md`](./STATUS.md)，阶段路线看 [`ROADMAP.md`](./ROADMAP.md)

## Now

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P0 | 同步 `05-schema-v2/05-complete-example.md` 到 canonical grammar | [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) | **[关键设计点]** 先统一示例，再继续扩写 v2 |
| P0 | 拆清 Current API 与 Target API 的文档边界 | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) | **[待扩展]** 需要形成专题映射或 ADR |
| P0 | 核验 Expression / Formula 设计与当前代码差异 | [`02-design/06-formula-spec.md`](./02-design/06-formula-spec.md)、[`06-module-detailed-design/07-expression-engine.md`](./06-module-detailed-design/07-expression-engine.md) | **[待核对代码]** |
| P0 | 清理模块设计中不稳定的“固定数字真相” | [`06-module-detailed-design/10-api-layer.md`](./06-module-detailed-design/10-api-layer.md) | 如端点数、服务数等 |

## Next

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P1 | 统一术语表并给出对照关系 | [`01-overview/05-concepts.md`](./01-overview/05-concepts.md) | `Concept / Fact Object / Entity / Analytical Element` |
| P1 | 收敛 Rule 模型的历史写法 | [`05-schema-v2/README.md`](./05-schema-v2/README.md) | 逐步淡出 `rule_group` |
| P1 | 为模块详细设计补充代码映射 / 测试要点 | [`06-module-detailed-design/README.md`](./06-module-detailed-design/README.md) | 先补关键模块 |
| P1 | 为关键目标态设计补 `last_verified` / `verified_against` 元数据 | `05-schema-v2/*` | 建立长期维护基线 |

## Later

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P2 | 冻结空间状态机与版本管理的正式口径 | [`05-schema-v2/00b-semantic-space-architecture.md`](./05-schema-v2/00b-semantic-space-architecture.md)、[`05-schema-v2/08-version-management.md`](./05-schema-v2/08-version-management.md) | 可考虑补 ADR |
| P2 | 收敛平台化扩展边界 | [`10-api-architecture.md`](./10-api-architecture.md)、[`05-schema-v2/06-dataset-and-sync.md`](./05-schema-v2/06-dataset-and-sync.md) | 明确 current / optional / future |
| P2 | 关键设计完成实现后回写 accepted 状态 | [`STATUS.md`](./STATUS.md) | 让设计与代码持续闭环 |

## 使用规则

1. 完成项从本文件移除，不在此保留历史完成记录
2. 本文件不再维护端点数、服务数、模块数等容易漂移的数据
3. 若事项属于“判断文档是否过期”，请更新 [`STATUS.md`](./STATUS.md)
4. 若事项属于“阶段目标变化”，请更新 [`ROADMAP.md`](./ROADMAP.md)
5. 若事项属于“当前态与目标态不一致”，先记录到 [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md)

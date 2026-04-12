# 实施 Backlog

> **作用**: `docs/` 下唯一开放事项列表
> **最后更新**: 2026-04-12
> **说明**: 本文件只保留进行中 / 未完成事项；文档状态看 [`STATUS.md`](./STATUS.md)，阶段路线看 [`ROADMAP.md`](./ROADMAP.md)

## 已完成事项归档

以下事项已完成，归档记录供参考：

### P0 完成项
- ✅ 同步 `05-schema-v2/05-complete-example.md` 到 canonical grammar
- ✅ 拆清 Current API 与 Target API 的文档边界（ADR-009）
- ✅ 核验 Expression / Formula 设计与当前代码差异
- ✅ 清理模块设计中不稳定的"固定数字真相"

### P1 完成项
- ✅ 统一术语表并给出对照关系（`01-overview/05-concepts.md`）
- ✅ 收敛 Rule 模型的历史写法（ADR-008）
- ✅ 为模块详细设计补充代码映射 / 测试要点
- ✅ 为关键目标态设计补 `last_verified` / `verified_against` 元数据

### P2 完成项
- ✅ 冻结空间状态机与版本管理的正式口径（ADR-010）
- ✅ 收敛平台化扩展边界（能力矩阵）

### ADR 新增
- ✅ ADR-007: L3-L4 计算边界
- ✅ ADR-008: Rule 模型统一
- ✅ ADR-009: API 架构演进
- ✅ ADR-010: 语义空间生命周期

---

## Now

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P1 | 核验 Schema Loading 模块设计与代码差异 | [`06-module-detailed-design/01-schema-loading.md`](./06-module-detailed-design/01-schema-loading.md) | 已添加代码映射表，需逐段核验 |
| P1 | 核验 Rule Engine 模块设计与代码差异 | [`06-module-detailed-design/06-rule-engine.md`](./06-module-detailed-design/06-rule-engine.md) | 已添加代码映射表，需逐段核验 |

## Next

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P2 | 补全分层设计文档元数据（L1-L4 专题） | `05-schema-v2/01-*.md` ~ `04-*.md` | 补充相关 ADR 链接 |
| P2 | 更新 `05-schema-v2/README.md` 导航 | [`05-schema-v2/README.md`](./05-schema-v2/README.md) | 反映新增文档结构 |

## Later

| 优先级 | 事项 | 关联文档 | 备注 |
|--------|------|----------|------|
| P3 | 关键设计完成实现后回写 accepted 状态 | [`STATUS.md`](./STATUS.md) | 让设计与代码持续闭环 |
| P3 | 清理旧文档中的 `rule_group` 写法 | `05-schema-v2/*` | 统一改为 canonical model |

## 使用规则

1. 完成项从本文件移除，不在此保留历史完成记录（本次为过渡保留，下次清理）
2. 本文件不再维护端点数、服务数、模块数等容易漂移的数据
3. 若事项属于"判断文档是否过期"，请更新 [`STATUS.md`](./STATUS.md)
4. 若事项属于"阶段目标变化"，请更新 [`ROADMAP.md`](./ROADMAP.md)
5. 若事项属于"当前态与目标态不一致"，先记录到 [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md)

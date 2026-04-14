# 文档与架构收敛路线图

> **作用**: `docs/` 下唯一阶段路线图
> **最后更新**: 2026-04-14
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

## Phase 1 实现里程碑

| 里程碑 | 状态 | 内容 |
|--------|------|------|
| Phase 1 增强设计 | ✅ 完成 | 5 篇设计文档（`07-phase1-enhancement/`），覆盖图存储、算子、分类、数据集、增量更新 |
| Schema Models 扩展 | ✅ 完成 | ValueDomain / CategoryValueDomain / DimensionApplicability 等 7 个新模型 |
| 图存储实现 | ✅ 完成 | GraphStoreBackend ABC + NetworkXGraphStore + DualWriteCoordinator |
| 算子增强 | ✅ 完成 | BinningOperator(inclusive_max) / ScorecardOperator(WOE+grade) / DecisionTableOperator / LLMJudgeOperator |
| 值域验证器 | ✅ 完成 | ValueDomainValidator（5 种域类型） |
| Schema Loader 增强 | ✅ 完成 | value_domain / CategoryValueDomain / RuleApplicability 全链路解析 |
| DuckDB 扩展表 | ✅ 完成 | 8 张 Phase 1 新增表（datasets / change_batches / entity_versions 等） |
| 数据集/增量更新服务 | ✅ 完成 | DatasetService + IncrementalUpdateService |
| 前端验证 | ⏳ 进行中 | Playwright 前端展示验证 |
| 全链路 API 验收 | ⏳ 进行中 | API 端点注册 + 端到端测试 |
| 文档一致性审视 | ✅ 完成 | docs/09-examples/ 审视报告 + examples/ 文档修复 + examples/consumer_credit/README.md 新建 |
| 文档与代码 Canonical Grammar 对齐 | ✅ 完成 | 模型层 + API 层 + Schema YAML + JSON 全部对齐 |

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

## Phase 2 改进里程碑

| 里程碑 | 状态 | 内容 | RFC |
|--------|------|------|-----|
| Phase 2 路线规划 | ✅ 已创建 | RFC-010 主路线 + RFC-011/012/013 子 RFC | RFC-010 |
| docs/09-examples 重构 | ⏳ 待启动 | 重写或标记为 Phase 2 设计，先从 REVIEW_REPORT.md 结论出发 | — |
| MCP 工具代码核验 | ⏳ 待启动 | 07-agent-interface.md 与 ontology_engine/tools/ 逐一核验 | RFC-013 |
| RuleExecutor DAG | ⏳ 待实现 | rules[] → steps[] DAG 拓扑排序执行，支撑 Phase 2 Schema 完整表达力 | RFC-011 |
| kuzu 图存储升级 | ⏳ 待实现 | NetworkX → kuzu，支撑 100K 节点规模 | RFC-012 |
| MCP 工具实现 | ⏳ 待实现 | 核验后工具定义落地为可执行 MCP 工具 | RFC-013 |

## 退出标准

当以下条件满足时，文档体系可视为完成本轮收敛：

1. `README / STATUS / ROADMAP / TODO` 四个根入口职责不再重叠
2. Schema v2 只有一套根语法入口
3. 当前态 / 目标态 / 实施层之间都有明确映射关系
4. 高风险文档均带有 **[待扩展]** 或 **[待核对代码]** 标记
5. `CLAUDE.md` 已同步文档治理约定，后续 Agent 能按同一规则持续演进
6. Phase 2 RFC 已创建并评审通过（RFC-010/011/012/013）
7. docs/09-examples 与实现一致性已完成核对或标记为 Phase 2 过期

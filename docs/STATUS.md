# 文档状态总表

> **作用**: `docs/` 下唯一状态页
> **最后更新**: 2026-04-17
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
| [`01-overview/`](./01-overview/README.md) | 项目概览 | accepted | mvp+phase1 | 主题级 | 仅承担愿景、目标、术语、边界说明；**2026-04-17 重构：三层资产链接+上下文栈** |
| [`02-design/`](./02-design/README.md) | 当前实现基线 | transitional | mvp | 主题级 | 表达当前实现口径，需持续与代码核验 |
| [`04-migration-and-gap/`](./04-migration-and-gap/README.md) | 迁移层 | accepted | phase1 | 是 | **2026-04-16 已刷新模块差距总表** |
| [`05-schema-v2/`](./05-schema-v2/README.md) | 目标架构 | draft | phase1+future | 主题级 | 目标态规范，部分专题仍待冻结 |
| [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) | Schema v2 根语法 + 内层 grammar | accepted | phase1 | 是 | **[单一事实源]** 根 grammar + L1-L4 内层 grammar 已冻结 |
| [`06-module-detailed-design/`](./06-module-detailed-design/README.md) | 实施设计 | draft | phase1 | 主题级 | 模块职责与实现拆解 |
| [`03-rfc/`](./03-rfc/) | RFC 历史记录 | accepted | history | 是 | 历史决策背景 |
| [`architecture/decisions/`](./architecture/decisions/) | ADR / 决策记录 | accepted | now | 是 | 冻结关键取舍 |
| [`development/`](./development/) | 开发规范 | accepted | now | 是 | 代码 / 测试 / 扩展规则 |
| [`07-phase1-enhancement/`](./07-phase1-enhancement/README.md) | Phase 1 增强设计 | accepted | phase1 | 是 | 5 篇 GAP 驱动增强设计，已实现对应代码 |
| [`07-agent-interface.md`](./07-agent-interface.md) | Agent 接口设计 | accepted | phase2 | 是 | MCP + CLI + 管理/消费面工具完整，含 API 映射表 |
| [`08-visualization-system.md`](./08-visualization-system.md) | 可视化系统设计 | accepted | phase1 | 是 | **[已核对代码]** 后端全实现，前端 UI 进行中 |
| [`09-examples/`](./09-examples/) | 端到端用户案例 | accepted | now | 是 | 供应链金融完整用户故事；supplies_chain_finance.md **待重构**[待核对代码] |
| [`development/storage-repository-pattern.md`](./development/storage-repository-pattern.md) | Repository 接口分离设计 | draft | phase1-2 | 否 | Phase 2 kuzu 协同架构 |
| [`archive/`](./archive/) | 归档区 | deprecated | history | 否 | 仅保留历史参考 |

## 热点质量问题

| 主题 | 标注 | 现状 | 处理入口 |
|------|------|------|----------|
| Schema 根结构 + 内层 grammar | **[关键设计点]** | 已新增 canonical grammar，后续需要逐步同步旧示例 | [`05-schema-v2/09-canonical-schema-spec.md`](./05-schema-v2/09-canonical-schema-spec.md) |
| Rule 模型双轨叙事 | **[关键设计点]** | ADR-008 Schema 已统一为 `rule_definitions + rule_logics`，但 `RuleExecutor` 仍未使用 (2026-04-16) | [`architecture/decisions/008-rule-model-unification.md`](./architecture/decisions/008-rule-model-unification.md) |
| Formula / Expression 执行模型 | **[单一事实源]** | 已与代码核验，文档区分当前实现与目标设计 | [`02-design/06-formula-spec.md`](./02-design/06-formula-spec.md) |
| Current API vs Target API | **[关键设计点]** | ADR-009 已明确边界，Current API 已核验 | [`architecture/decisions/009-api-architecture-evolution.md`](./architecture/decisions/009-api-architecture-evolution.md) |
| 术语统一 | **[单一事实源]** | `01-overview/05-concepts.md` 已统一术语表并给出对照关系；**2026-04-17 新增上下文栈/三层资产/Agent记忆架构概念** | [`01-overview/05-concepts.md`](./01-overview/05-concepts.md) |
| Phase 2 RFC 路线 | **[待扩展]** | RFC-010 主路线 + RFC-011/012/013 子 RFC 已创建，规划 RuleExecutor DAG / kuzu / MCP 工具实现 | [`03-rfc/RFC-010-phase2-roadmap.md`](./03-rfc/RFC-010-phase2-roadmap.md) |
| docs/09-examples 一致性 | **[关键设计点]** | 发现与实现系统性断裂：虚构 Schema（Company/Guarantee/steps[]）vs 实际（Supplier/supplies_to/when+then_action），详见 REVIEW_REPORT.md | [`09-examples/REVIEW_REPORT.md`](./09-examples/REVIEW_REPORT.md) |
| MCP 工具实现 | **[关键设计点]** | ✅ `ontology_engine/mcp/` 已实现 7 个工具（P1 5 个核心 + P2 2 个）；RFC-013 P1/P2/P3 优先级已对齐；遗留低优先级 review 问题见 TODO.md | [`docs/09-examples/TOOL_AUDIT.md`](./09-examples/TOOL_AUDIT.md) |
| 平台化扩展边界 | **[待扩展]** | 能力矩阵已建立，明确 current/optional/future | [`05-schema-v2/06-dataset-and-sync.md`](./05-schema-v2/06-dataset-and-sync.md) |
| Rule Engine DAG | **[关键设计点]** | ❌ 未实现。`RuleExecutor` 退化为 priority 排序 (2026-04-16) | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) |
| Query Engine | **[关键设计点]** | ❌ 未实现。`engine/query/` 仅占位符 (2026-04-16) | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) |
| Storage 缓存/Faiss/按需子图 | **[关键设计点]** | ⚠️ 偏离。实际为简化本地实现 (2026-04-16) | [`04-migration-and-gap/README.md`](./04-migration-and-gap/README.md) |

## 重点核验清单

- **[已核对代码]** `02-design/06-formula-spec.md`: 已与 `ontology_engine/engine/expression/engine.py` 核验，区分当前实现与目标设计
- **[已核对代码]** `06-module-detailed-design/07-expression-engine.md`: 已区分当前实现（simpleeval）与目标设计（L0/L1）
- **[已核对代码]** `06-module-detailed-design/10-api-layer.md`: 已与 `ontology_engine/api/routes/` 核验，移除固定端点数量
- **[已核对代码]** `04-migration-and-gap/README.md`: 2026-04-16 已完成 Rule/Storage/Services/Expression/Query/API 模块差距核验
- **[待核对代码]** `02-design/02-api-design.md`: 需继续和 `ontology_engine/api/server.py` 对齐
- **[部分已核对]** `07-agent-interface.md`: P1 核心 5 个 MCP 工具已实现并通过单元测试；P2/P3 工具待按 RFC-013 优先级继续
- **[已过期入口]** `docs/09-examples/supply_chain_finance.md`: 使用虚构 Schema，与 `examples/supply_chain_finance/schema.yaml` 不符，详见 REVIEW_REPORT.md

## 更新要求

1. 只要出现新的文档入口、角色变化或过期判断变化，必须更新本页
2. 代码实现显著偏离设计文档时，先更新本页和迁移层文档，再决定是否重写专题文档
3. 已完成事项不要继续停留在 `TODO.md`；若影响阶段判断，则同步更新 `ROADMAP.md`
4. 若某篇文档被新文档替代，应在本页与文档头部同时标明 `deprecated` 或 `superseded`

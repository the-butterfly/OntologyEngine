# 文档状态总表

> **作用**: 判断文档是否过期 / 冲突 / 热点风险
> **最后更新**: 2026-05-25
> **说明**: 本文件是文档状态和有效性的唯一判断入口，仅反映状态，不维护任务列表

## 状态说明

| 状态 | 含义 |
|------|------|
| `accepted` | 已收敛，可作为当前规范使用 |
| `draft` | 已成形，但仍可能调整 |
| `transitional` | 过渡态，通常连接当前实现与目标设计 |
| `deprecated` | 仅保留历史参考，不再继续维护 |
| `planned` | 已列入收敛计划，但尚未完整成文 |
| `under-review` | 正在审视重写中，尚未完成 |

## 目录级状态矩阵

### 活跃文档（docs/）

| 对象 | 角色 | 状态 | SoT | 备注 |
|------|------|------|-----|------|
| [`README.md`](./README.md) | 文档地图 | accepted | 是 | 只负责导航，不维护细节 |
| [`STATUS.md`](./STATUS.md) | 状态页 | accepted | 是 | 统一表达文档有效性 |
| [`ROADMAP.md`](./ROADMAP.md) | 路线图 | accepted | 是 | 统一表达阶段目标 |
| [`TODO.md`](./TODO.md) | backlog | accepted | 是 | 只保留开放事项 |
| [`01-overview/`](./01-overview/README.md) | 项目概览 | accepted | **唯一事实源** | 愿景、目标、术语、边界 |
| [`02-design/schema/`](./02-design/schema/) | Schema 设计 | draft | 主题级 SoT | 审视重写完成，含 6 份文档 |
| [`02-design/storage/`](./02-design/storage/) | 存储设计 | draft | 主题级 SoT | 审视重写完成，含 6 份文档 |
| [`02-design/rule-engine/`](./02-design/rule-engine/) | 规则引擎设计 | draft | 主题级 SoT | 审视重写完成，含 4 份文档 |
| [`02-design/query-engine/`](./02-design/query-engine/) | 查询引擎设计 | draft | 主题级 SoT | 审视重写完成，含 7 份文档 |
| [`02-design/extraction-pipeline/`](./02-design/extraction-pipeline/) | 提取管线设计 | draft | 主题级 SoT | 审视重写完成，含 5 份文档 |
| [`02-design/services/`](./02-design/services/) | 服务层设计 | draft | 主题级 SoT | 审视重写完成，含 6 份文档 |
| [`02-design/api/`](./02-design/api/) | API 设计 | draft | 主题级 SoT | 审视重写完成，含 7 份文档 |
| [`02-design/formula/`](./02-design/formula/) | Formula 规范 | draft | 主题级 SoT | 审视重写完成，含 3 份文档 |
| [`02-design/agent-memory/`](./02-design/agent-memory/) | Agent 记忆系统设计 | accepted | 主题级 SoT | Phase 2 新增，含 8 份文档，15 个 MCP 工具已实现 |
| [`01-overview/09-agent-memory.md`](./01-overview/09-agent-memory.md) | Agent 记忆概念 | draft | 概念级 SoT | Phase 2 新增 |
| [`01-overview/11-agent-onboarding.md`](./01-overview/11-agent-onboarding.md) | Agent 引导文档 | draft | Phase 2 SoT | MCP 工具清单 + 调用示例 |
| [`02-design/ingestion/`](./02-design/ingestion/) | 知识摄入全链路 | draft | 主题级 SoT | 新增，含结构化/非结构化摄入设计 |
| [`02-design/deployment.md`](./02-design/deployment.md) | 部署指南 | draft | 主题级 SoT | 新增，本地部署 + 配置 + 启动流程 |
| [`docs-dev/03-rfc/`](../docs-dev/03-rfc/) | RFC 开发稿 | accepted | 是 | 开发过程中的 RFC 版本 |
| [`04-adr/`](./04-adr/) | 架构决策记录 | accepted | 是 | 冻结关键取舍 |

### 归档文档（docs-baseline/）

| 对象 | 角色 | 状态 | 备注 |
|------|------|------|------|
| `docs-baseline/00-current-baseline/` | 重写前实现基线 | deprecated | 仅供参考 |
| `docs-baseline/05-schema-v2/` | Schema v2 目标架构 | deprecated | 已融入 02-design/schema/ |
| `docs-baseline/06-module-detailed-design/` | Phase 1 模块详细设计 | deprecated | 已融入 02-design/ 对应子目录 |
| `docs-baseline/09-examples/` | 端到端用户案例 | deprecated | 仅供参考 |
| `docs-baseline/architecture/decisions/` | 历史 ADR | deprecated | 仅供参考 |
| `docs-baseline/frontend/` | 前端相关文档 | deprecated | 仅供参考 |

### 开发过程文档（docs-dev/）

| 对象 | 角色 | 状态 | 备注 |
|------|------|------|------|
| `docs-dev/discuss/` | 关键决策讨论记录 | accepted | 持续更新 |
| `docs-dev/04-migration-and-gap/` | 当前态与目标态映射 | accepted | 仅供参考 |
| `docs-dev/review-reports/` | 审视报告 | accepted | 8 份审视报告已完成 |
| `docs-dev/discuss/2026-04-27-agent-memory-design-analysis.md` | SOTA 审视 | accepted | 7 个不足 + 3 个范式 |
| `docs-dev/discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` | 外部批判框架对照 | accepted | lencx 记忆≠蒸馏框架审视 |

## 热点质量问题

| 主题 | 标注 | 现状 | 处理入口 |
|------|------|------|----------|
| 跨模块一致性 | **[关键设计点]** | ⚠️ 5 个严重问题待修复；C-05 CategoryTag 对齐已完成 | `docs-dev/review-reports/consistency-report.md` |
| Schema v2 grammar 与 overview 对齐 | **[关键设计点]** | ✅ 审视重写完成 | `02-design/schema/` |
| Rule Engine DAG | **[关键设计点]** | ✅ 实现完成 | `02-design/rule-engine/` |
| Query Engine | **[关键设计点]** | ✅ 设计完成，待实现 | `02-design/query-engine/` |
| Storage 迁移 | **[关键设计点]** | ✅ 设计完成，待实现 | `02-design/storage/` |
| API 路由统一 | **[关键设计点]** | ✅ 设计完成，待实现 | `02-design/api/` |
| Simulation Embeddable UI | **[已完成]** | ✅ 实现完成 | `docs/plans/2026-04-21-simulation-embeddable-ui.md` |
| Agent 记忆系统 | **[关键设计点]** | ✅ 概念+设计文档完成，**外部批判审视完成，发现 8 项新 GAP**；✅ **实现偏差 Phase 0-1 全部修复**；📊 64/65 eval trajectories passed (98.5%) | `02-design/agent-memory/` |
| 规则模型双分离 | **[关键设计点]** | 📝 RFC-018 draft | `docs-dev/03-rfc/RFC-018-rule-model-dual-separation.md` |
| Step.action 结构化 | **[关键设计点]** | 📝 RFC-019 draft | `docs-dev/03-rfc/RFC-019-step-action-structization.md` |
| Agent 记忆治理层 | **[关键设计点]** | 📝 设计文档待完善 | `docs-dev/discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` |
| Agent Memory QUL 约束类型扩展 | **[关键设计点]** | ⚠️ 设计 8 种约束类型，实现 3 种，剩余 5 种待实施 | `docs-dev/discuss/2026-05-06-agent-memory-implementation-gap-analysis.md` |

## 更新要求

1. 只要出现新的文档入口、角色变化或过期判断变化，必须更新本页
2. 代码实现显著偏离设计文档时，先更新本页和迁移层文档，再决定是否重写专题文档
3. 已完成事项不要继续停留在 `TODO.md`；若影响阶段判断，则同步更新 `ROADMAP.md`
4. 若某篇文档被新文档替代，应在本页与文档头部同时标明 `deprecated` 或 `superseded`
5. 审视重写完成后，将 `under-review` 状态更新为 `accepted` 或 `draft`

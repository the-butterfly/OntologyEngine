# OntologyEngine 文档地图

> **当前阶段**: 重写阶段，从 overview 出发逐一审视重写详细设计
> **最后更新**: 2026-05-25
> **维护原则**: 01-overview 是唯一事实源，02-design 是详细设计唯一入口，docs-baseline 仅供参考

## 从哪里开始读

- **新读者**: 先读 [`01-overview/README.md`](./01-overview/README.md)，再看 [`01-overview/03-goals.md`](./01-overview/03-goals.md)
- **实现者**: 先读 [`02-design/`](./02-design/) 中对应模块的设计文档
- **架构评审者**: 先读 [`01-overview/05-concepts.md`](./01-overview/05-concepts.md)、[`STATUS.md`](./STATUS.md)
- **Agent / 自动化任务**: 先读 [`../AGENTS.md`](../AGENTS.md)、[`STATUS.md`](./STATUS.md)、[`ROADMAP.md`](./ROADMAP.md)

## 文档分层

| 层级 | 目录 / 文件 | 角色 | 是否承担 SoT | 说明 |
|------|-------------|------|---------------|------|
| 入口层 | [`README.md`](./README.md) | 文档地图 | 否 | 只负责导航和职责边界 |
| 状态层 | [`STATUS.md`](./STATUS.md) | 当前状态总表 | 是 | 统一记录文档状态、有效性、热点风险 |
| 路线层 | [`ROADMAP.md`](./ROADMAP.md) | 阶段目标与收敛顺序 | 是 | 记录阶段性目标，不记录细碎执行项 |
| Backlog 层 | [`TODO.md`](./TODO.md) | 进行中 / 未完成事项 | 是 | 只保留未完成事项，不记录完成项历史 |
| 认知层 | [`01-overview/`](./01-overview/) | 为什么做、做什么、不做什么 | **唯一事实源** | 只放概览与术语，不放实现细节 |
| 设计层 | [`02-design/`](./02-design/) | 详细设计 | 主题级 SoT | 审视重写后的版本，与 overview 对齐 |
| 提案层 | [`docs-dev/03-rfc/`](../docs-dev/03-rfc/) | RFC 提案（开发版本） | 是 | 需求提议→功能实施 |
| 决策层 | [`04-adr/`](./04-adr/) | 架构决策记录 | 是 | 冻结关键取舍 |

## 单一事实源（Source of Truth）

| 主题 | 唯一入口 | 说明 |
|------|----------|------|
| 项目愿景 / 目标 / 术语 / 架构 | [`01-overview/`](./01-overview/README.md) | 所有设计必须与 overview 对齐 |
| 文档有效性 / 过期情况 | [`STATUS.md`](./STATUS.md) | 不再在多个索引页重复维护状态 |
| 阶段目标 / 收敛顺序 | [`ROADMAP.md`](./ROADMAP.md) | 不再在 README / TODO 重复维护路线图 |
| 开放任务 / backlog | [`TODO.md`](./TODO.md) | 只保留未完成事项 |
| Schema grammar | [`02-design/schema/`](./02-design/schema/) | 审视重写后的 Schema 设计 |

## 文档地图

### `01-overview/`

项目认知入口，回答"为什么做、要达成什么、边界在哪里"。**唯一事实源**。

- 入口: [`01-overview/README.md`](./01-overview/README.md)
- 推荐阅读: `03-goals.md` → `04-modules.md` → `05-concepts.md`

### `02-design/`

详细设计，回答"如何实现"。每个子目录对应一个核心模块，审视重写后与 overview 对齐。

| 子目录 | 对应模块 | 审视状态 |
|--------|----------|----------|
| [`schema/`](./02-design/schema/) | Schema 设计 | 审视重写完成（draft） |
| [`storage/`](./02-design/storage/) | 存储设计 | 审视重写完成（draft） |
| [`rule-engine/`](./02-design/rule-engine/) | 规则引擎设计 | 审视重写完成（draft） |
| [`query-engine/`](./02-design/query-engine/) | 查询引擎设计 | 审视重写完成（draft） |
| [`extraction-pipeline/`](./02-design/extraction-pipeline/) | 提取管线设计 | 审视重写完成（draft） |
| [`services/`](./02-design/services/) | 服务层设计 | 审视重写完成（draft） |
| [`api/`](./02-design/api/) | API 设计 | 审视重写完成（draft） |
| [`agent-memory/`](./02-design/agent-memory/) | Agent 记忆设计 | 审视重写完成（accepted） |
| [`ingestion/`](./02-design/ingestion/) | 知识摄入全链路 | 新增（draft） |
| [`formula/`](./02-design/formula/) | Formula 规范 | 审视重写完成（draft） |
| [`deployment.md`](./02-design/deployment.md) | 部署指南 | 新增（draft） |

### `03-rfc/`

RFC 提案，记录需求提议到功能实施的决策过程。

### `04-adr/`

架构决策记录，冻结关键取舍。

## 归档区

| 目录 | 角色 | 说明 |
|------|------|------|
| `docs-baseline/` | 现状文档归档 | 仅供参考，不作为开发依据 |
| `docs-dev/` | 开发过程文档 | discuss、migration-and-gap、review-reports |

### `docs-baseline/`

历史文档归档，包含重写前的所有设计文档。仅供审视时参考，**不作为开发依据**。

- `00-current-baseline/`: 重写前的实现基线
- `05-schema-v2/`: Schema v2 目标架构（已融入 02-design/schema/）
- `06-module-detailed-design/`: Phase 1 模块详细设计（已融入 02-design/ 对应子目录）
- `09-examples/`: 端到端用户案例
- `architecture/decisions/`: 历史 ADR
- `frontend/`: 前端相关文档

### `docs-dev/`

开发过程文档。

- `discuss/`: 关键决策讨论记录
- `04-migration-and-gap/`: 当前态与目标态映射
- `review-reports/`: 审视报告

## 关键标注约定

- **[单一事实源]**: 当前主题的唯一规范入口
- **[关键设计点]**: 已收敛、实现或评审时必须优先关注的核心约束
- **[待扩展]**: 已确认方向，但细节仍待补充
- **[待核对代码]**: 文档内容尚未与当前代码逐项核验，不能直接当作实现真相
- **[已过期入口]**: 历史入口或旧叙述，保留仅为兼容阅读

## 文档维护约定

1. `README.md` 不再维护详细任务、端点数量、服务数量等易漂移内容
2. `STATUS.md` 是唯一状态页；文档是否过期、是否可信，以它为准
3. `ROADMAP.md` 是唯一阶段路线图；`TODO.md` 只追踪未完成事项
4. 所有设计文档必须与 01-overview 对齐，标注对齐状态
5. 每个设计决策必须有对应的目的和要解决的问题
6. 核心设计文档新增或重写时，应补充 `status`、`phase`、`source_of_truth`、`last_verified`、`verified_against` 等元数据

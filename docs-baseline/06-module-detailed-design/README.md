# 06-module-detailed-design 目录说明

> **角色**: Phase 1 模块实施设计
> **状态**: draft
> **Phase**: phase1
> **Source of Truth**: true（仅针对模块职责、输入输出契约和实施拆解）

## 这个目录回答什么

本目录回答的是：**目标架构如何拆成可实现模块，以及各模块如何串成 Phase 1 的端到端链路。**

它不是纯粹的当前代码镜像，也不是目标态产品规范；它处于两者之间，是实施层设计。

## 推荐阅读顺序

1. [`00-overview.md`](./00-overview.md)
2. `01-schema-loading.md` → `03-storage-layer.md` → `07-expression-engine.md`
3. `04-metric-engine.md` → `05-categorization-engine.md` → `06-rule-engine.md`
4. `08-query-engine.md` → `09-services-layer.md` → `10-api-layer.md`

## 目录内文档职责

| 文档 | 主要问题 | 备注 |
|------|----------|------|
| `00-overview.md` | 全链路、依赖方向、阶段目标 | 作为总览入口 |
| `01` ~ `03` | 数据进入系统前后的加载、实例、存储 | 与 Schema / 当前代码关系最紧密 |
| `04` ~ `07` | 核心计算引擎 | 是实现风险最高的部分 |
| `08` | 查询、服务、API | 需要持续与当前代码核验 |
| `02-design/query-engine-current.md` | Query Engine 当前实现 | accepted | phase1 | |
| `05-schema-v2/query-engine-target.md` | Query Engine Phase 2 目标 | draft | phase2 | |

## 重点提示

- **[关键设计点]** 本目录主要表达“模块职责与实施路径”，不是产品级愿景说明
- **[关键设计点]** 若与当前实现不一致，应先到 [`../04-migration-and-gap/README.md`](../04-migration-and-gap/README.md) 记录迁移关系
- **[待扩展]** 后续每个模块文档都应增加“与当前代码映射”与“测试要点”章节
- **[待核对代码]** `07-expression-engine.md` 当前更接近目标设计而非已验证实现
- **[待核对代码]** `10-api-layer.md` 中的 API 细节需要与 `ontology_engine/api/server.py` 继续逐项核验
- **[待核对代码]** `09-services-layer.md` 中的服务拆分需持续与 `ontology_engine/services/` 对齐

# ADR-009: API 架构演进策略

**Status**: accepted

**Date**: 2026-04-12

**Deciders**: Ontology Engine 技术团队

---

## Context

当前项目存在两套 API 设计理念，它们并非简单的版本迭代关系，而是反映了架构视角的根本性转变：

### Current API（工程导向）

Current API 采用单租户、单空间的工程设计思路，直接面向工程实现。已实现的路由包括：

- `/v1/schema` - Schema 管理（定义、验证、版本控制）
- `/v1/entities` - 实体 CRUD 操作
- `/v1/rules/execute` - 规则执行引擎调用

Current API 的实现位于 `ontology_engine/api/routes/`，是当前代码基线的主要组成部分。

### Target API（平台化空间导向）

Target API 采用多租户、多空间的平台化设计，引入"语义空间"作为核心资源边界。完整设计详见 `docs/05-schema-v2/10-api-architecture.md`，主要路径包括：

- `/v1/management/*` - 管理层：租户、空间、权限
- `/v1/consumption/*` - 消费层：查询、订阅、分析

### 关键冲突点

两套 API 的差异不仅是路径变化，而是底层资源模型的重新抽象：

| 维度 | Current API | Target API |
|------|-------------|------------|
| 租户模型 | 单租户（隐式） | 多租户（显式） |
| 空间边界 | 无（全局 Schema） | 语义空间隔离 |
| 权限模型 | 无（开放访问） | RBAC + 空间权限 |
| 消费视图 | 直接暴露实体 | 抽象订阅/查询接口 |

---

## Decision

### 核心决策

明确区分 Current API 和 Target API 的边界，采取渐进式演进策略，而非直接替换。

### 分层定位

```
┌─────────────────────────────────────────────────────────┐
│                    Target API (v2 规划)                  │
│  ┌─────────────────┐  ┌─────────────────────────────┐   │
│  │ /v1/management/* │  │   /v1/consumption/*         │   │
│  │ 平台管理入口     │  │   消费端抽象接口             │   │
│  └─────────────────┘  └─────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│                    Current API (v1)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ /v1/schema  │  │ /v1/entities│  │ /v1/rules/exec  │  │
│  │ 单空间 Schema│  │ 单空间实体  │  │  规则执行       │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Current API（v1）定位

- **适用范围**：单租户、单空间、工程导向
- **Phase 1 目标**：优先保证完整稳定，作为基线能力
- **长期规划**：作为 Target API 的底层实现支撑

### Target API（v2 规划）定位

- **适用范围**：多租户、多空间、平台化
- **Phase 1 范围**：仅实现 `/v1/management/spaces` 基础能力
- **Phase 2 规划**：完整实现 `/v1/consumption/*` 消费视图

### 演进路径

采取语义空间概念渐进式演进：

1. **Phase 1 前期**：Current API 稳定运行，无空间概念
2. **Phase 1 后期**：引入 `/v1/management/spaces`，Current API 隐式关联默认空间
3. **Phase 2**：逐步迁移至 Target API，Current API 转为兼容层

---

## API 矩阵

| API 类型 | 路径前缀 | 适用场景 | Phase 1 状态 |
|---------|---------|---------|-------------|
| Current | `/v1/schema` | Schema 管理 | ✅ 已实现 |
| Current | `/v1/entities` | 实体 CRUD | ✅ 已实现 |
| Current | `/v1/rules/execute` | 规则执行 | ✅ 已实现 |
| Target | `/v1/management/spaces` | 空间管理 | ⚠️ 部分实现 |
| Target | `/v1/consumption/*` | 消费视图 | ⏭️ Phase 2 |

---

## Consequences

### 正面影响

- **风险可控**：Current API 作为稳定基线，不阻断现有开发
- **渐进演进**：避免大爆炸式重构，降低迁移风险
- **概念统一**：以语义空间为核心，逐步对齐两套模型

### 负面影响

- **文档负担**：需要同时维护两套 API 的文档（Current 和 Target）
- **代码复杂度**：路由层需要通过前缀区分两套 API
- **长期债务**：Current API 的兼容代码需要后期清理

### 缓解措施

| 问题 | 缓解策略 |
|------|---------|
| 文档维护 | 在 `docs/05-schema-v2/` 中明确标注 Target API，Current API 文档在 `docs/06-module-detailed-design/` 维护 |
| 路由区分 | Current API 保持现有路由注册，Target API 使用独立路由模块 `api/routes/management/` |
| 后期统一 | Phase 2 规划适配层，将 Current API 调用转发至 Target API 实现 |

---

## Related

- [ADR-003: Semantic Space Model](./003-semantic-space-model.md)
- [Schema v2 API 设计](../05-schema-v2/10-api-architecture.md)
- [Phase 1 API 实现](../../06-module-detailed-design/01-api-layer.md)

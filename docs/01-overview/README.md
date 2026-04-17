# 01-overview 目录说明

> **角色**: 项目认知入口
> **状态**: accepted
> **Phase**: mvp + phase1
> **Source of Truth**: true（仅针对愿景、目标、术语和边界）
> **最后更新**: 2026-04-17

## 适合谁看

- 第一次接触项目的人
- 需要快速建立系统边界感的实现者
- 需要确认目标 / 非目标的评审者
- 需要理解三层资产链接价值的架构师

## 推荐阅读顺序

1. [`01-vision.md`](./01-vision.md) — 愿景与三层资产链接
2. [`02-motivation.md`](./02-motivation.md) — 三层资产断裂痛点
3. [`03-goals.md`](./03-goals.md) — 阶段目标与业务逻辑管理
4. [`04-modules.md`](./04-modules.md) — 模块架构与上下文栈对齐
5. [`05-concepts.md`](./05-concepts.md) — 核心术语与新增概念
6. [`06-tech-stack.md`](./06-tech-stack.md) — 技术选型与三层资产存储
7. [`07-project-structure.md`](./07-project-structure.md) — 项目结构（已与代码核验）

## 目录内文档职责

| 文档 | 主要回答的问题 | 使用边界 |
|------|----------------|----------|
| `01-vision.md` | 为什么做、做什么、三层资产链接价值 | 不承载实施细节 |
| `02-motivation.md` | 三层知识资产断裂是什么、痛点矩阵 | 不承载具体 API / Schema 设计 |
| `03-goals.md` | 各阶段要达到什么结果、业务逻辑管理目标 | 阶段目标以此为主，不在实施文档重复 |
| `04-modules.md` | 系统有哪些大模块、上下文栈定位 | 只到模块级边界，不展开模块内实现 |
| `05-concepts.md` | 核心术语、上下文栈、三层资产链接 | **[单一事实源]** 需继续与 Schema v2 术语收敛 |
| `06-tech-stack.md` | 技术路线、三层资产存储策略 | 不直接代表未来平台化能力边界 |
| `07-project-structure.md` | 代码如何组织 | **[已核对代码]** 与当前仓库结构一致 |

## 核心叙事线

本目录文档围绕一条核心叙事线组织：

```
三层知识资产断裂 (02-motivation)
    ↓
OntologyEngine 的价值定位 (01-vision)
    ↓
阶段性解决目标 (03-goals)
    ↓
模块架构如何支撑 (04-modules)
    ↓
关键概念定义 (05-concepts)
    ↓
技术选型如何实现 (06-tech-stack)
    ↓
代码如何组织 (07-project-structure)
```

## 2026-04-17 重构要点

本次重构基于以下外部调研和审视：

| 维度 | 调研来源 | 关键发现 |
|------|----------|----------|
| 上下文栈 | [AI Memory vs RAG vs Knowledge Graph (Atlan 2026)](https://atlan.com/know/ai-memory-vs-rag-vs-knowledge-graph/) | Memory+RAG+KG 是同一上下文栈三层，非替代关系 |
| Agent 记忆架构 | [Agent Memory Race 2026 (OSSInsight)](https://ossinsight.io/blog/agent-memory-race-2026) | 4种架构，图结构最适合业务规则推理 |
| 三层资产断裂 | 行业知识管理实践 | IT资产/个人知识/组织资产断裂是核心痛点 |
| 上下文就绪数据 | Atlan 2026 | 新鲜度/血缘/语义/所有权是数据治理四要素 |

### 主要变更

1. **01-vision.md**: 新增三层资产链接定义、上下文栈定位、行业对标
2. **02-motivation.md**: 从"三层资产断裂"视角重构痛点矩阵
3. **03-goals.md**: 新增资产链接、个人→组织沉淀闭环、业务逻辑管理目标
4. **04-modules.md**: 对齐上下文栈三层架构，新增资产归属标注
5. **05-concepts.md**: 新增上下文栈、知识资产、资产链接、Agent 记忆架构等概念
6. **06-tech-stack.md**: 新增三层资产存储映射、上下文栈集成架构
7. **07-project-structure.md**: 与实际代码完全核验，补充 MCP/可视化/迁移等缺失模块

## 边界约束

- 本目录只表达 **愿景 / 目标 / 边界 / 术语 / 模块认知 / 三层资产链接**
- 不在本目录定义详细字段结构、固定接口列表、实现级流程
- 若需要解释"当前实现"和"未来目标"的差异，应链接到 [`../04-migration-and-gap/README.md`](../04-migration-and-gap/README.md)

## 重点提示

- **[关键设计点]** 本目录是项目认知入口，不再承担详细设计说明书职责
- **[关键设计点]** `03-goals.md` 中的阶段目标仍是项目阶段判断的主入口
- **[关键设计点]** 三层资产链接（IT ↔ 个人 ↔ 组织）是 OntologyEngine 的核心差异化价值
- **[待扩展]** `05-concepts.md` 中 Agent 记忆架构与 OntologyEngine 的深度对齐仍需持续收敛
- **[已核对代码]** `07-project-structure.md` 已与 `ontology_engine/` 目录逐项核验

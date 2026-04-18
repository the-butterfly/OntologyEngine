# 01-overview 目录说明

> **角色**: 项目认知入口
> **状态**: accepted
> **Phase**: mvp + phase1
> **Source of Truth**: true（仅针对愿景、目标、术语和边界）
> **最后更新**: 2026-04-18

## 适合谁看

- 第一次接触项目的人
- 需要快速建立系统边界感的实现者
- 需要确认目标 / 非目标的评审者
- 需要理解 Layer-R / Layer-S 双层认知架构的架构师

## 推荐阅读顺序

1. [`01-vision.md`](./01-vision.md) — 愿景与三层资产链接 + Layer-R/S 双层认知
2. [`02-motivation.md`](./02-motivation.md) — 三层资产断裂痛点
3. [`03-goals.md`](./03-goals.md) — 阶段目标与业务逻辑管理
4. [`04-modules.md`](./04-modules.md) — 模块架构与上下文栈对齐
5. [`05-concepts.md`](./05-concepts.md) — 核心术语 + Layer-R/S + 互索引 + 时序 + 矛盾检测
6. [`06-tech-stack.md`](./06-tech-stack.md) — 技术选型与三层资产存储
7. [`07-project-structure.md`](./07-project-structure.md) — 项目结构（已与代码核验）
8. [`08-knowledge-retrieval.md`](./08-knowledge-retrieval.md) — Layer-R/S 检索机制与查询路由

## 目录内文档职责

| 文档 | 主要回答的问题 | 使用边界 |
|------|----------------|----------|
| `01-vision.md` | 为什么做、做什么，三层资产链接 + Layer-R/S | 不承载实施细节 |
| `02-motivation.md` | 三层知识资产断裂是什么、痛点矩阵 | 不承载具体 API / Schema 设计 |
| `03-goals.md` | 各阶段要达到什么结果、业务逻辑管理目标 | 阶段目标以此为主，不在实施文档重复 |
| `04-modules.md` | 系统有哪些大模块、上下文栈定位 | 只到模块级边界，不展开模块内实现 |
| `05-concepts.md` | 核心术语、Layer-R/S、互索引、时序、矛盾检测 | **[单一事实源]** 需继续与 Schema v2 术语收敛 |
| `06-tech-stack.md` | 技术路线、三层资产存储策略 | 不直接代表未来平台化能力边界 |
| `07-project-structure.md` | 代码如何组织 | **[已核对代码]** 与当前仓库结构一致 |
| `08-knowledge-retrieval.md` | Layer-R/S 双路检索机制、查询路由、RRF 融合 | 不承载具体存储实现细节 |

## 核心叙事线

```
三层知识资产断裂 (02-motivation)
    ↓
OntologyEngine 的价值定位 (01-vision)
    ↓
阶段性解决目标 (03-goals)
    ↓
模块架构如何支撑 (04-modules)
    ↓
关键概念定义 (05-concepts) + Layer-R/S 检索 (08)
    ↓
技术选型如何实现 (06-tech-stack)
    ↓
代码如何组织 (07-project-structure)
```

## 2026-04-18 重构要点

本次重构整合了 OpenSPG KAG、m_flow、MAMGA、MemPalace、LLM-Wiki 等外部调研。

| 维度 | 调研来源 | 关键发现 |
|------|----------|----------|
| 双层认知 | MemPalace + LLM-Wiki | 原文存储（Layer-R）与结构化推理（Layer-S）共存，认知分工 |
| 互索引 | KAG AtomicQuery + m_flow supported_by | 四种关系（extracted_from/supported_by/defined_in/trace_to）实现碎片↔结构化双向溯源 |
| 边语义 | m_flow Bundle Search | 边承载 edge_text + weight，参与推理成本传播 |
| 查询路由 | MAMGA | multi-hop/temporal/analytical 等查询类型自适应检索参数 |
| 时序建模 | MemPalace temporal triple | 实体支持 valid_from/to 时序标注 |
| 矛盾检测 | LLM-Wiki lint | Ingestion 时阻止矛盾写入 + 后台异步扫描 |
| 知识编译 | LLM-Wiki | compile-once 避免重复推理，增量维持 |

### 主要变更

1. **01-vision.md**: 新增 Layer-R/S 双层认知架构，知识编译一次理念
2. **03-goals.md**: Phase 1 新增 Dataset + Fragment + 互索引目标；Phase 2 新增 Layer-R/S 协同 + 矛盾检测 + 时序查询目标
3. **04-modules.md**: QueryEngine 新增 Layer-R/S 双路检索；IngestionService 新增 Dataset 注册 + 矛盾检测
4. **05-concepts.md**: 重大更新，新增 Layer-R/S、Dataset、KnowledgeFragment、互索引（4种关系）、矛盾检测、时序建模、查询路由分类
5. **08-knowledge-retrieval.md**: **[新增]** 统一描述检索机制

## 边界约束

- 本目录只表达 **愿景 / 目标 / 边界 / 术语 / 模块认知 / 双层认知架构**
- 不在本目录定义详细字段结构、固定接口列表、实现级流程
- 若需要解释"当前实现"和"未来目标"的差异，应链接到 [`../04-migration-and-gap/README.md`](../04-migration-and-gap/README.md)

## 重点提示

- **[关键设计点]** 本目录是项目认知入口，不再承担详细设计说明书职责
- **[关键设计点]** `03-goals.md` 中的阶段目标仍是项目阶段判断的主入口
- **[关键设计点]** Layer-R（原文优先）+ Layer-S（结构化推理）是 OntologyEngine 的核心差异化能力
- **[待扩展]** SemanticConcept 层（跨领域顶层概念）对齐 KAG/LLM-Wiki 的 entities/concepts 双轴
- **[已核对代码]** `07-project-structure.md` 已与 `ontology_engine/` 目录逐项核验

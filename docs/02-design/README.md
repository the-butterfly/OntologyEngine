# 模块设计文档索引

> **status**: accepted
> **phase**: phase1+phase2
> **source_of_truth**: 本目录是 OntologyEngine 各模块详细设计的唯一事实源
> **last_verified**: 2026-05-25

本目录包含 OntologyEngine 所有模块的详细设计文档。每个子目录对应一个模块，内含该模块的架构、接口、实现策略等设计文档。

---

## 模块导航

| 模块 | 目录 | 状态 | 核心文档 | 说明 |
|------|------|------|---------|------|
| Schema | [`schema/`](./schema/) | draft (SoT) | [`01-schema-spec.md`](./schema/01-schema-spec.md) | L1-L4 声明语法、实例层、互索引边、时序建模 |
| Storage | [`storage/`](./storage/) | draft (SoT) | [`README.md`](./storage/README.md) | KuzuDB + ChromaDB + SQLite 三引擎架构 |
| Rule Engine | [`rule-engine/`](./rule-engine/) | draft (SoT) | [`README.md`](./rule-engine/README.md) | DAG 构建、并行执行、回滚机制 |
| Query Engine | [`query-engine/`](./query-engine/) | draft (SoT) | [`README.md`](./query-engine/README.md) | Layer-R/S 双路检索、Bundle Search、RRF 融合 |
| Extraction Pipeline | [`extraction-pipeline/`](./extraction-pipeline/) | draft (SoT) | [`README.md`](./extraction-pipeline/README.md) | AST + LLM 双通道提取、消歧、增量缓存 |
| Services | [`services/`](./services/) | draft (SoT) | [`README.md`](./services/README.md) | 快速通道（规则计算）+ 慢速通道（LLM 提取/消歧） |
| API | [`api/`](./api/) | draft (SoT) | [`README.md`](./api/README.md) | REST 路由设计、兼容层、错误码 |
| Formula | [`formula/`](./formula/) | draft (SoT) | [`README.md`](./formula/README.md) | 公式规范、函数库、L0/L1 执行模型 |
| Agent Memory | [`agent-memory/`](./agent-memory/) | accepted (SoT) | [`README.md`](./agent-memory/README.md) | Phase 2 模块：remember/recall/reflect 三操作 |
| Ingestion | [`ingestion/`](./ingestion/) | draft (SoT) | [`README.md`](./ingestion/README.md) | 知识摄入全链路：结构化 + 非结构化来源 |
| Frontend | [`frontend/`](./frontend/) | under-review | [`README.md`](./frontend/README.md) | 前端架构审查、Rule/知识生命周期 UI |
| 通用设计 | [`agent-friendly-design.md`](./agent-friendly-design.md) | draft | — | Agent 友好设计原则 |
| 部署指南 | [`deployment.md`](./deployment.md) | draft | — | 本地部署 + 配置 + 启动流程 |

---

## 模块依赖关系

```
API → Services → Engine (Rule/Query/Extraction) → Storage (KuzuDB/ChromaDB/SQLite)
                                              ↘ Schema (L1-L4 声明)
Formula → Rule Engine
Agent Memory → Services + Storage (Phase 2)
```

详细边界规则见 [`CLAUDE.md`](../../CLAUDE.md) 的模块边界矩阵。

---

## 设计文档使用规则

1. 每个模块目录下的 `README.md` 是该模块的设计入口
2. 标注 `[单一事实源]` 的文档是当前主题的权威规范
3. 新增设计文档时，必须同步更新本索引页
4. 废弃的设计文档移至 `docs-baseline/02-design/`，标注 `[已过期入口]`
5. 代码实现与设计文档不一致时，先更新 [`STATUS.md`](../STATUS.md)

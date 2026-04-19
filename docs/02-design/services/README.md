# 服务层设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

---

## 目的

定义 OntologyEngine 服务层（L3）的完整架构，将当前实现重写为支持双通道摄入、Layer-R/Layer-S 双路检索、跨引擎协调分析、增量更新影响分析、反馈闭环的完整服务编排层。服务层是 API 层与引擎层之间的编排桥梁，负责用例编排、事务管理、跨引擎协调。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **IngestionService 无双通道** | 同步顺序导入，无快速/慢速分离 | 快速通道同步写入 + 慢速通道后台推理，对齐 MAMGA Structural Consolidation |
| 2 | **矛盾检测缺失** | 导入时不检测矛盾，查询时才发现 | Ingest 时 LLM 比对 + contradiction_report 生成 + 人工确认 |
| 3 | **QueryService 无 Layer-R/Layer-S** | 仅有 pattern_match 和 graph_traverse | query_raw / query_structured / query_hybrid 三层接口，对齐 m_flow Retrieval Orchestrator |
| 4 | **AnalysisService 无执行快照** | 规则执行结果无全链路追溯 | ExecutionStepSnapshot + L3 并行预计算 + 指标缓存，对齐 Cognee ECL Pipeline |
| 5 | **IncrementalUpdateService 无自动更新** | 仅手动 diff 检测 | 定时轮询 + SHA256 变更检测 + 影响分析 + 矛盾人工确认 |
| 6 | **反馈闭环缺失** | 无 FeedbackService | feedback_weight 流式更新 + 参与检索评分，对齐 Cognee apply_feedback_weights |
| 7 | **术语体系陈旧** | 使用 concept_type / EntityInstance(concept) | 统一为 Schema v2 术语：_fact_object / EntityInstance |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│  L4: API 层 (FastAPI / MCP / CLI)                                    │
├──────────────────────────────────────────────────────────────────────┤
│  L3: 服务层 (编排)                                                    │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │
│  │ SchemaService  │  │ EntityService  │  │ DatasetService │         │
│  │ Schema CRUD    │  │ 实体/关系 CRUD  │  │ 数据集元数据    │         │
│  │ 版本管理       │  │ 快照管理       │  │ linkage_targets│         │
│  └────────────────┘  └────────────────┘  └────────────────┘         │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │
│  │ Ingestion      │  │ QueryService   │  │ Analysis       │         │
│  │ Service        │  │                │  │ Service        │         │
│  │ 快速通道       │  │ query_raw      │  │ Entity→RuleGrp │         │
│  │ 慢速通道       │  │ query_struct   │  │ L3预计算→L4执行│         │
│  │ 矛盾检测       │  │ query_hybrid   │  │ 执行快照       │         │
│  └────────────────┘  └────────────────┘  └────────────────┘         │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │
│  │ Incremental    │  │ Feedback       │  │ Visualization  │         │
│  │ UpdateService  │  │ Service        │  │ Service        │         │
│  │ 自动轮询       │  │ 反馈评分       │  │ Schema/规则图   │         │
│  │ SHA256检测     │  │ 权重流式更新   │  │ 模拟执行       │         │
│  │ 影响分析       │  │ 检索评分参与   │  │                │         │
│  └────────────────┘  └────────────────┘  └────────────────┘         │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  L2: 引擎层 (推理)                                                    │
│  RuleEngine │ MetricEngine │ QueryEngine │ CategorizationEngine      │
├──────────────────────────────────────────────────────────────────────┤
│  L1: 存储层 (持久化)                                                  │
│  SQLiteStorage │ KuzuDBStorage │ ChromaVectorStore │ FaissVectorStore│
└──────────────────────────────────────────────────────────────────────┘
```

---

## 服务划分

| 服务 | 编排职责 | 资产链接 | 对齐参考 | 详细设计 |
|------|----------|----------|----------|----------|
| **SchemaService** | Schema CRUD + 版本管理 | 组织资产生命周期 | KAG Schema 管理 | [待扩展] |
| **EntityService** | 实体/关系 CRUD + 快照 | IT 资产实例管理 | m_flow Episode 管理 | [待扩展] |
| **DatasetService** | 数据集元数据 + linkage_targets | IT 资产版本管理 | KAG 版本管理 | [dataset-service.md](dataset-service.md) |
| **IngestionService** | 双通道摄入 + 矛盾检测 | IT 资产接入 | MAMGA Structural Consolidation | [ingestion-service.md](ingestion-service.md) |
| **QueryService** | Layer-R/S 双路检索 + 查询路由 | 三层资产联合访问 | m_flow Memory Orchestrator | [query-service.md](query-service.md) |
| **AnalysisService** | 跨引擎协调 + 执行快照 | 个人→组织知识转化 | Cognee ECL Pipeline | [analysis-service.md](analysis-service.md) |
| **IncrementalUpdateService** | 自动更新 + 影响分析 + 矛盾扫描 | 资产变更传播 | Cognee 增量处理 | [incremental-update-service.md](incremental-update-service.md) |
| **FeedbackService** | 反馈评分 + 权重流式更新 | 反馈闭环 | Cognee feedback_weight | [feedback-service.md](feedback-service.md) |
| **VisualizationService** | Schema 图/规则链/模拟 | 资产可视化与解释 | m_flow Cone Graph | [待扩展] |

---

## 关键设计决策

| # | 决策 | 理由 | 参考 |
|---|------|------|------|
| D-SVC-1 | IngestionService 采用双通道（快速/慢速）分离 | 快速通道保证低延迟写入，慢速通道不阻塞主流程 | MAMGA trg_memory.py |
| D-SVC-2 | 矛盾检测在 Ingest 时触发而非 Query 时 | 矛盾越早发现越好，阻止不一致数据写入图谱 | LLM-Wiki-Agent ingest.py |
| D-SVC-3 | QueryService 暴露 query_raw / query_structured / query_hybrid 三层接口 | 不同场景需要不同检索策略，单一接口无法满足 | m_flow Memory Orchestrator |
| D-SVC-4 | AnalysisService 编排 Entity→RuleGroup→L3→L4 执行链 | L3 指标预计算是 L4 规则执行的前置条件，必须显式编排 | Cognee Pipeline |
| D-SVC-5 | IncrementalUpdateService 使用 SHA256 变更检测 | 哈希比对 O(1)，内容比对 O(n)，适合定时轮询场景 | Graphify SHA256 缓存 |
| D-SVC-6 | FeedbackService 使用流式更新公式：updated = previous + α × (normalized - previous) | 流式更新避免全量重算，α 控制学习率 | Cognee apply_feedback_weights |
| D-SVC-7 | 服务层禁止直接调用 storage/local/ | 模块边界约束，服务层只通过 storage/base.py 接口访问 | AGENTS.md 模块边界 |
| D-SVC-8 | 服务层不实现业务逻辑，只编排引擎 | 业务逻辑下沉到引擎层，服务层保持薄编排 | 旧设计原则继承 |

---

## 与引擎层的对齐

| 服务 | 依赖的引擎 | 协调方式 |
|------|-----------|---------|
| IngestionService | CategorizationEngine（慢速通道归类） | 异步队列 |
| QueryService | QueryEngine（检索编排） | 直接调用 |
| AnalysisService | CategorizationEngine + MetricEngine + RuleEngine | 顺序编排 |
| IncrementalUpdateService | RuleEngine（影响分析） + MetricEngine（指标重算） | 事件触发 |
| FeedbackService | QueryEngine（检索评分公式） | 参数注入 |

---

## 与存储层的对齐

| 服务 | 使用的存储 | 访问方式 |
|------|-----------|---------|
| IngestionService | KuzuDB（实体/边写入）、ChromaDB（碎片向量索引）、SQLite（矛盾报告） | storage/base.py |
| QueryService | ChromaDB（Layer-R 向量）、KuzuDB（Layer-S 图遍历）、SQLite（BM25 FTS5） | storage/base.py |
| AnalysisService | KuzuDB（实体/规则读取）、SQLite（指标缓存、执行快照） | storage/base.py |
| IncrementalUpdateService | SQLite（变更日志、SHA256 哈希）、KuzuDB（实体更新） | storage/base.py |
| FeedbackService | KuzuDB（feedback_weight 更新）、SQLite（反馈记录） | storage/base.py |

---

## 事务边界

服务层定义事务边界，保证用例级别一致性：

| 服务 | 事务场景 | 边界策略 |
|------|---------|---------|
| IngestionService | 快速通道批量写入 | batch_size 内原子提交，失败记录 error_log |
| IngestionService | 矛盾检测 | 矛盾时阻止写入，生成 contradiction_report |
| AnalysisService | L3→L4 执行链 | DAG 层级回滚（RuleTransaction） |
| IncrementalUpdateService | 变更传播 | 影响分析后确认，确认后原子应用 |
| EntityService | batch_create | 全成功或全失败 |

---

## 错误处理

```python
class ServiceError(Exception):
    code: str
    message: str
    details: dict | None = None

class EntityNotFoundError(ServiceError):
    code = "ENTITY_NOT_FOUND"

class ContradictionDetectedError(ServiceError):
    code = "CONTRADICTION_DETECTED"

class ImpactAnalysisRequiredError(ServiceError):
    code = "IMPACT_ANALYSIS_REQUIRED"

class EngineExecutionError(ServiceError):
    code = "ENGINE_EXECUTION_ERROR"
```

---

## 目录结构

```
ontology_engine/services/
├── __init__.py
├── schema_service.py
├── entity_service.py
├── dataset_service.py
├── ingestion_service.py
├── query_service.py
├── analysis_service.py
├── incremental_update.py
├── feedback_service.py
├── visualization_service.py
├── rule_service.py
├── dag_service.py
├── simulation_service.py
└── dto/
    ├── __init__.py
    ├── errors.py
    ├── requests.py
    └── responses.py
```

---

## 子文档索引

| 文档 | 状态 | 说明 |
|------|------|------|
| [ingestion-service.md](ingestion-service.md) | draft | IngestionService 双通道设计 |
| [query-service.md](query-service.md) | draft | QueryService 完整接口 |
| [analysis-service.md](analysis-service.md) | draft | AnalysisService 跨引擎协调 |
| [incremental-update-service.md](incremental-update-service.md) | draft | IncrementalUpdateService 增量更新 |
| [feedback-service.md](feedback-service.md) | draft | FeedbackService 反馈闭环 |
| [dataset-service.md](dataset-service.md) | draft | DatasetService L0 数据源层设计 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 模块架构定义 | `docs/01-overview/04-modules.md` |
| 核心概念 | `docs/01-overview/05-concepts.md` |
| Instance 层 Grammar | `docs/02-design/schema/instance-layer.md` |
| DAG 执行设计 | `docs/02-design/rule-engine/dag-execution.md` |
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
| 旧服务层设计 | `docs/02-design/services/05-services-design.md` |

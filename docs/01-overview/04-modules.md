# 模块架构

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19

---

## 五层系统架构 vs 模块分层

OntologyEngine 有两套对应的分层：

| 系统架构层 | 关注问题 | 模块分层 | 对应模块 |
|-----------|---------|---------|---------|
| **L0 数据源层** | 数据从哪来 | — | 外部系统（Dataset 注册） |
| **L1 知识编译层** | 如何把异构数据编译成统一知识 | L0 核心层 | SchemaLoader、ExtractionPipeline |
| **L2 知识表示与存储层** | 如何存储结构化知识和向量 | L1 存储层 | KuzuDB、ChromaDB、SQLite |
| **L3 推理与执行层** | 如何检索、推理、执行规则 | L2 引擎层 | RuleEngine、MetricEngine、QueryEngine |
| **L4 Agent 协同与应用层** | 如何让多 Agent 协同作业 | L3 服务层 + L4 API | services/、mcp/、api/ |

---

## 上下文栈对齐视图

OntologyEngine 在 AI Agent 上下文栈中占据**深度层**，与广度层（RAG）和连续性层（Memory）协同工作：

```
┌─────────────────────────────────────────────────────┐
│  Agent 上下文栈 (Context Stack)                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  连续性层 (Memory)                                      │ │
│  │  ── 会话历史 / 用户偏好 / 跨会话状态                     │ │
│  │  ── 保障 Agent 行为连续性                                │ │
│  │  ── 类比 m-flow 的 Procedural Memory（程序记忆）            │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  广度层 (RAG)                                           │ │
│  │  ── 文档检索 / 向量相似度 / 知识密集型问答               │ │
│  │  ── 保障信息覆盖广度                                    │ │
│  │  ── 类比传统 RAG 系统（向量检索）                         │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  ★ 深度层 (OntologyEngine) ★                        │ │
│  │  ── 实体关系 / 多跳推理 / 规则执行 / 三层资产链接        │ │
│  │  ── 保障推理深度和可解释性                                │ │
│  │  ── 三层资产链接的载体                                       │ │
│  │  ── 类比 m-flow 的 Episodic Memory + KAG 的 Logical Form        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## 分层视图（三类资产视角）

```
┌─────────────────────────────────────────────────────────┐
│ L4: API / 接口层                                        │
│   FastAPI REST / MCP Agent 协议 / CLI                   │
│   ── 消费面：Agent 交互中沉淀个人资产                        │
├─────────────────────────────────────────────────────────┤
│ L3: 服务层 (编排)                                       │
│   SchemaService / EntityService / AnalysisService       │
│   QueryService / IngestionService / VisualizationService │
│   ── 编排三层资产的 CRUD 和推理                                │
├─────────────────────────────────────────────────────────┤
│ L2: 引擎层 (推理)                                       │
│   ├─ RuleEngine    (规则/DAG执行)                       │
│   ├─ MetricEngine  (指标计算)                           │
│   ├─ CategorizationEngine (归类)                        │
│   ├─ QueryEngine   (查询/检索)                          │
│   └─ ExpressionEngine (表达式安全执行)                   │
│   ── 执行 L1-L4 四层推理链                                       │
├─────────────────────────────────────────────────────────┤
│ L1: 存储层 (资产持久化)                                  │
│   ├─ SQLiteStorage    (元数据/版本/审计)                │
│   ├─ KuzuDBStorage   (实体/关系/Rule/互索引)           │
│   ├─ ChromaVectorStore (KnowledgeFragment 向量，<100K)   │
│   └─ FaissVectorStore (向量索引，>100K)                  │
│   ── 存储三类资产：IT 资产 / 个人资产 / 组织资产                      │
├─────────────────────────────────────────────────────────┤
│ L0: 核心层 (Schema 驱动)                                │
│   ├─ SchemaLoader    (KGML 解析)                        │
│   ├─ OperatorRegistry (算子注册与发现)                   │
│   ├─ ExpressionEngine (L0 simpleeval + L1 AST 沙箱)     │
│   └─ ValueDomainValidator (值域校验)                     │
│   ── 定义三类资产的统一本体模型（KGML）                              │
└─────────────────────────────────────────────────────────┘
```

## 模块职责（三类资产视角）

### 核心层 (L0)

| 模块 | 职责 | 对应资产层 | 对齐 m-flow/KAG | 输入 | 输出 |
|------|------|-----------|------------------|------|------|
| **SchemaLoader** | 解析 KGML YAML | 组织资产（规则定义载体） | 对齐 KAG 的 Schema 解析（OpenSPG） | schema.yaml | Pydantic 模型 |
| **OperatorRegistry** | 算子发现与注册 | 组织资产（业务逻辑单元） | 对齐 m-flow 的 Pipeline Tasks | 算子实现类 | 可执行算子池 |
| **ExpressionEngine** | 表达式安全执行 | IT 资产（计算安全边界） | 对齐 KAG 的 Logical Form 执行 | `score > 80` | 布尔结果/数值 |
| **ValueDomainValidator** | 值域校验 | IT ↔ 组织（数据规则对齐） | 对齐 KAG 的概念对齐（Aligner） | 属性值 + 值域定义 | 校验结果 |

### 存储层 (L1)

| 模块 | 本地实现 | 云端扩展 | 承载资产 | 设计来源 |
|------|----------|----------|----------|----------|
| **SQLiteStorage** | ✅ | PostgreSQL | Dataset 元数据、Schema 版本、矛盾报告、变更日志 | m_flow FSCache + MAMGA |
| **KuzuDBStorage** | ✅ | Neo4j | EntityInstance、EdgeInstance、RuleDefinition、互索引边 | m_flow GraphProvider |
| **ChromaVectorStore** | ✅（<100K）| PGVector | KnowledgeFragment 向量、边向量索引 | MemPalace |
| **FaissVectorStore** | ✅（>100K）| - | 规模扩展时的向量索引 | - |
| **FSCacheAdapter** | ✅ | Redis | 指标缓存、会话缓存 | m_flow FSCacheAdapter |

**存储职责矩阵**：

| 数据类型 | 存储引擎 | 原因 |
|---------|---------|------|
| 事务 + 元数据 | SQLite | WAL 模式，低延迟写入 |
| 实体关系 | KuzuDB | 图遍历、边向量、互索引 |
| 向量检索（<100K）| ChromaDB | 自动持久化 + 元数据过滤 |
| 向量检索（>100K）| FAISS | IVF+PQ 压缩 |
| 指标聚合缓存 | SQLite + diskcache | m_flow 模式 |

**边界约束**：
- 上层只能调用 `storage/base.py` 接口
- `local/` 只实现接口，不依赖上层
- 三类资产的链接关系在存储层统一管理
- **废弃**：~~DuckDBStorage~~（分析引擎不适合高频写入，改为 SQLite + KuzuDB）
- **回退保留**：~~NetworkXGraph~~（作为 KuzuDB 不可用时的回退实现保留）

### 引擎层 (L2)

| 模块 | 核心功能 | 资产推理 | 对齐 m-flow/KAG | 依赖 |
|------|----------|-----------|------------------|------|
| **RuleEngine** | DAG 解析、拓扑执行、回滚 | 组织资产执行 | 对齐 m-flow 的 Procedure Execution + KAG 的 Executor | core/, storage/ |
| **MetricEngine** | 指标计算、缓存、增量更新 | 个人→组织知识量化 | 对齐 m-flow 的 FacetPoint 计算 + KAG 的指标计算 | core/, storage/ |
| **CategorizationEngine** | 归类编译、复用规则引擎 | 个人知识结构化 | 对齐 m-flow 的 Facet 归类 + KAG 的概念对齐 | core/, RuleEngine |
| **QueryEngine** | Layer-R/S 双路检索、查询路由、RRF 融合 | 三层资产联合查询 | 对齐 m-flow 的 Bundle Search + KAG 的混合检索 | storage/ |
| **ExpressionEngine** | L0/L1 两级安全执行 | IT 资产计算安全 | 对齐 KAG 的 Logical Form 执行 | core/ |

**边界约束**：
- `engine/` 禁止直接调 `storage/local/`
- 规则执行通过 storage 接口读写
- MetricEngine → RuleEngine 直接调用（无中间写入）

### 服务层 (L3)

| 服务 | 编排职责 | 资产链接 | 对齐 m-flow/KAG |
|------|----------|----------|------------------|
| **SchemaService** | Schema CRUD + 版本管理 | 组织资产生命周期 | 对齐 KAG 的 Schema 管理 |
| **EntityService** | 实体/关系 CRUD + 快照 | IT 资产实例管理 | 对齐 m-flow 的 Episode 管理 |
| **AnalysisService** | 指标/规则编排执行 | 个人→组织知识转化 | 对齐 m-flow 的 Episodic 检索 + Procedural 检索 |
| **QueryService** | 查询路由 + Layer-R/S 双路检索 | 三层资产联合访问 | 对齐 m-flow 的 Memory Orchestrator |
| **IngestionService** | Dataset 注册 + Fragment 导入 + 矛盾检测 | IT 资产接入 | 对齐 KAG 的 Builder Pipeline |
| **VisualizationService** | Schema 图/规则链/模拟 | 资产可视化与解释 | 对齐 m-flow 的 Cone Graph 可视化 |
| **DatasetService** | 数据集元数据管理 + linkage_targets | IT 资产版本管理 | 对齐 KAG 的版本管理 |
| **IncrementalUpdateService** | 自动更新 + 主动调用 + 影响分析 + 矛盾扫描 | 资产变更传播 | 对齐 KAG 的知识更新机制 |

### API 层 (L4)

| 接口 | 用途 | 资产面 | 阶段 |
|------|------|--------|------|
| **FastAPI REST** | 通用 API | 管理面 + 消费面 | Phase 1 |
| **MCP Agent 协议** | Agent 工具调用 | 消费面（Agent 交互中沉淀个人资产） | Phase 2 |
| **CLI** | 命令行管理 | 管理面 | Phase 1 |

## 调用关系

```
api/ ───────▶ services/ ───────▶ engine/ ───────▶ storage/
 │                │                │                │
 │                │                │                ▼
 │                │                │           storage/base.py
 │                │                │                │
 │                │                │                ▼
 │                │                │         storage/local/
 │                │                │
 │                │                ▼
 │                │           core/schema/
 │                │           core/operators/
 │                │
 │                ▼
 │         visualization/
 │         mcp/tools/
 │
 ▼
examples/*/schema.yaml  ← 三类资产定义入口（IT 资产 / 个人资产 / 组织资产）
```

## 关键约束

1. **本地优先**: L1 层必须有本地实现，外部存储为可选
2. **无循环依赖**: 模块依赖只能向下，禁止平级/向上
3. **Schema 驱动**: 业务逻辑在 YAML 定义，非代码
4. **三层资产统一模型**: IT 资产、个人知识、组织资产使用同一本体（KGML）描述
5. **资产可链接**: 存储层维护三层资产间的显式关系，引擎层负责推理
6. **异步更新机制**: IncrementalUpdateService 支持自动轮询 + 主动调用两种模式，矛盾时弹出确认

## 异步更新机制

```
┌─────────────────────────────────────────────────────────────┐
│  IncrementalUpdateService                                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐      ┌─────────────────┐                  │
│  │ Dataset     │      │ 自动更新        │ ← 定时轮询       │
│  │ 注册声明     │ ───▶ │ (后台任务)      │                  │
│  └─────────────┘      └─────────────────┘                  │
│                              │                              │
│                              ▼                              │
│                      ┌───────────────┐                     │
│                      │ 影响分析       │                     │
│                      │ (Impact       │                     │
│                      │  Analysis)    │                     │
│                      └───────────────┘                     │
│                              │                              │
│                              ▼                              │
│                      ┌───────────────┐                     │
│                      │ 关键确认点     │ ◀ 矛盾时触发       │
│                      │ (Critical     │                     │
│                      │  Checkpoints) │                     │
│                      └───────────────┘                     │
│                              │                              │
│  ┌─────────────┐      ┌───────────────┐                  │
│  │ API 主动调用 │ ──▶ │ 手动触发      │ ← 用户控制       │
│  └─────────────┘      └───────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

**影响分析输出**：
```json
{
  "dataset_id": "ds_001",
  "affected_entities": ["ent_A", "ent_B"],
  "affected_rules": ["R001", "R002"],
  "potential_contradictions": [
    {"field": "address", "old": "朝阳区", "new": "海淀区"}
  ],
  "cascade_depth": 2,
  "requires_confirmation": true
}
```

## 对齐参考系统的设计映射

| 参考系统 | 核心概念 | 在 OntologyEngine 中的对应 | 架构层次 |
|----------|---------|--------------------------|---------|
| **LLM-Wiki-Agent** | ingest 时矛盾检测、预编译 Wiki、两通道图构建 | IngestionService 矛盾检测、Living overview | L1 编译层 |
| **KAG** | SPG Schema、Expert Rules DSL、AtomicQuery | SchemaLoader、RuleEngine DSL、互索引 | L2/L3 |
| **m_flow** | Cone Graph、Bundle Search、最小成本路径 | 四层推理 + QueryEngine Bundle Search | L3 |
| **MAMGA** | 时序多图、causal 链接、长期会话记忆 | 时序实体 valid_from/to、causal 关系边 | L2/L3 |
| **MemPalace** | verbatim 存储、validity window、wing/room 分层 | Layer-R 原文存储、时序建模、metadata 过滤 | L1/L2 |
| **Graphify** | 三通道提取、SHA256 缓存、Leiden 社区检测 | ExtractionPipeline 增量处理、Confidence 标签 | L1 |
| **Understand-Anything** | 多 Agent 并行、可插拔 IndexManager | MCP Agent 协同、并行分析管线 | L4 |
| **Cognee** | ECL 管道、DataPoint 溯源、BaseRetriever 三步管道 | IngestionService 管道、互索引溯源、QueryEngine 检索 | L1/L3 |
| **codebase-memory-mcp** | RAM-first 管线、Cypher 查询引擎、增量索引 | 存储层 RAM-first 设计、KuzuDB Cypher 查询 | L1 |

## 模块交互模式技术实现框架

```
参考 Cognee + m_flow + KAG 的模块交互模式：

1. 管道编排模式（参考 Cognee Pipeline）：
   IngestionService 编排：
     Task(resolve_data_directories) → Task(ingest_data) → Task(extract_chunks)
     → Task(extract_graph) → Task(add_data_points) → Task(detect_contradictions)
   支持 batch_size、enriches、_Drop 信号、PipelineContext 注入

2. 适配器模式（参考 m_flow GraphProvider + Cognee VectorDBInterface）：
   storage/base.py 定义抽象接口
   storage/local/kuzu/ → KuzuGraphStore 实现
   storage/local/chroma/ → ChromaVectorStore 实现
   storage/adapters/ → Neo4j/LanceDB 等扩展

3. 策略模式（参考 Cognee register_retriever + KAG IndexManager）：
   QueryEngine 检索器注册：
     use_retriever(QueryType.FACTUAL, FactualRetriever)
     use_retriever(QueryType.MULTI_HOP, BundleSearchRetriever)
     use_retriever(QueryType.TEMPORAL, TemporalRetriever)

4. 双通道处理模式（参考 MAMGA trg_memory.py）：
   IngestionService 快速通道：同步写入 → 时序链接 → 向量索引 → 入队
   IngestionService 慢速通道：后台推理 → 因果推断 → 实体边创建

5. 观察者模式（参考 Cognee observability + m_flow _track_changes）：
   storage/local/kuzu/ 变更追踪 → GraphRelationshipLedger
   engine/ 执行追踪 → audit_log
   services/ 业务追踪 → pipeline_runs

6. MCP 工具暴露模式（参考 Cognee MCP + m_flow MCP + MemPalace MCP）：
   mcp/tools/ 暴露工具：
     memorize → IngestionService.ingest
     search → QueryService.search
     query → QueryService.query
     categorize → EntityService.categorize
     execute_rules → AnalysisService.execute_rules
   双模式：Direct 模式（直接调用库函数）+ API 模式（HTTP 请求远程服务）
```

---

*参考：[M-flow Retrieval Architecture](https://github.com/FlowElement-ai/m_flow/blob/main/docs/RETRIEVAL_ARCHITECTURE.md) | [KAG Core Architecture](https://deepwiki.com/OpenSPG/KAG/2-core-architecture) | [LLM-Wiki-Agent](https://github.com/DeusData/llm-wiki-agent) | [MemPalace](https://mempalace.info/) | [Graphify](https://github.com/DeusData/graphify) | [Understand-Anything](https://github.com/sweep/understand-anything) | [MAMGA](https://github.com/DeusData/MAMGA)*

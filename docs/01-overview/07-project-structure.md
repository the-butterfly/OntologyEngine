# 项目结构（目标架构）

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19
> **[关键设计点]**: 本文档描述 OntologyEngine 的目标框架结构，非文件级实现细节

---

## 分层架构总览

```
┌──────────────────────────────────────────────────────────────┐
│  L4: API / 接口层                                            │
│  ── FastAPI REST / MCP Agent 协议 / CLI                      │
│  ── 消费面：Agent 交互中沉淀个人资产                          │
├──────────────────────────────────────────────────────────────┤
│  L3: 服务层 (编排)                                            │
│  ── SchemaService / EntityService / AnalysisService          │
│  ── QueryService / IngestionService / VisualizationService    │
│  ── 编排三层资产的 CRUD 和推理                                │
├──────────────────────────────────────────────────────────────┤
│  L2: 引擎层 (推理)                                           │
│  ├─ RuleEngine      (DAG执行 / Bundle Search / 规则热更新)  │
│  ├─ MetricEngine    (指标计算 / 增量缓存)                   │
│  ├─ CategorizationEngine  (归类 / 个人→组织沉淀)             │
│  ├─ QueryEngine     (Layer-R/S 双路检索 / 查询路由 / RRF)    │
│  └─ ExpressionEngine (L0 simpleeval + L1 AST 沙箱)          │
│  ── 执行 L1-L4 四层推理链                                    │
├──────────────────────────────────────────────────────────────┤
│  L1: 存储层 (资产持久化)                                     │
│  ├─ KuzuDBStorage   (Entity/Edge/Rule/互索引)               │
│  ├─ ChromaVectorStore (KnowledgeFragment 向量)              │
│  ├─ SQLiteStorage    (元数据/版本/矛盾报告/缓存)             │
│  └─ FSCacheAdapter   (指标缓存/会话缓存)                     │
│  ── 存储三类资产：IT 资产 / 个人资产 / 组织资产                │
├──────────────────────────────────────────────────────────────┤
│  L0: 核心层 (Schema 驱动)                                    │
│  ├─ SchemaLoader     (KGML 解析 / 版本管理)                  │
│  ├─ OperatorRegistry (算子注册与发现)                       │
│  ├─ ExtractionPipeline (三通道提取 / SHA256 缓存)           │
│  └─ ValueDomainValidator (值域校验)                        │
│  ── 定义三类资产的统一本体模型（KGML）                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 核心层 (L0)

| 模块 | 职责 | 对齐参考 | 输入 | 输出 |
|------|------|---------|------|------|
| **SchemaLoader** | KGML YAML 解析、版本快照 | KAG SPG Schema | schema.yaml | Pydantic 模型 |
| **OperatorRegistry** | 算子发现与注册 | KAG IndexManager | 算子实现类 | 可执行算子池 |
| **ExtractionPipeline** | 三通道增量提取 | Graphify | 原始文档 | KnowledgeFragment |
| **ExpressionEngine** | 表达式安全执行 | KAG Logical Form | `score > 80` | 布尔/数值结果 |
| **ValueDomainValidator** | 值域校验 | KAG Aligner | 属性值 + 值域定义 | 校验结果 |

---

## 存储层 (L1)

| 模块 | 本地实现 | 云端扩展 | 承载资产 | 设计来源 |
|------|----------|----------|----------|---------|
| **SQLiteStorage** | ✅ WAL 模式 | PostgreSQL | Dataset 元数据、Schema 版本、矛盾报告、变更日志 | m_flow FSCache + MAMGA |
| **KuzuDBStorage** | ✅ | Neo4j | EntityInstance、EdgeInstance、RuleDefinition、互索引边 | m_flow GraphProvider |
| **ChromaVectorStore** | ✅（<100K）| PGVector | KnowledgeFragment 向量、边向量索引 | MemPalace |
| **FaissVectorStore** | ✅（>100K）| - | 规模扩展时的向量索引 | Graphify |
| **FSCacheAdapter** | ✅ | Redis | 指标缓存、会话缓存 | m_flow FSCacheAdapter |

### 边界约束

- **上层只能调用 `storage/base.py` 接口**
- **`local/` 只实现接口，不依赖上层**
- **三层资产的链接关系在存储层统一管理**

---

## 引擎层 (L2)

| 模块 | 核心功能 | 资产推理 | 对齐参考 | 依赖 |
|------|---------|---------|---------|------|
| **RuleEngine** | DAG 解析、拓扑执行、回滚 | 组织资产执行 | m_flow Procedure Execution + KAG Executor | core/, storage/ |
| **MetricEngine** | 指标计算、缓存、增量更新 | 个人→组织知识量化 | m_flow FacetPoint 计算 | core/, storage/ |
| **CategorizationEngine** | 归类编译、复用规则引擎 | 个人知识结构化 | m_flow Facet 归类 | core/, RuleEngine |
| **QueryEngine** | Layer-R/S 双路检索、查询路由、RRF 融合 | 三层资产联合查询 | m_flow Bundle Search + MAMGA | storage/ |
| **ExpressionEngine** | L0/L1 两级安全执行 | IT 资产计算安全 | KAG Logical Form 执行 | core/ |

### 边界约束

- **`engine/` 禁止直接调 `storage/local/`**
- **规则执行通过 storage 接口读写**
- **MetricEngine → RuleEngine 直接调用（无中间写入）**

---

## 服务层 (L3)

| 服务 | 编排职责 | 资产链接 | 对齐参考 |
|------|---------|---------|---------|
| **SchemaService** | Schema CRUD + 版本管理 | 组织资产生命周期 | KAG Schema 管理 |
| **EntityService** | 实体/关系 CRUD + 快照 | IT 资产实例管理 | m_flow Episode 管理 |
| **AnalysisService** | 指标/规则编排执行 | 个人→组织知识转化 | m_flow Episodic 检索 |
| **QueryService** | 查询路由 + Layer-R/S 双路检索 | 三层资产联合访问 | m_flow Memory Orchestrator |
| **IngestionService** | Dataset 注册 + Fragment 导入 + 矛盾检测 | IT 资产接入 | KAG Builder Pipeline |
| **VisualizationService** | Schema 图/规则链/模拟 | 资产可视化与解释 | m_flow Cone Graph |
| **DatasetService** | 数据集元数据管理 + linkage_targets | IT 资产版本管理 | KAG 版本管理 |
| **IncrementalUpdateService** | 自动更新 + 影响分析 + 矛盾扫描 | 资产变更传播 | KAG 知识更新 |
| **SimulationService** | dry_run + what-if 模拟 | 规则验证 | Understand-Anything |

---

## API 层 (L4)

| 接口 | 用途 | 资产面 | 阶段 |
|------|------|--------|------|
| **FastAPI REST** | 通用 API | 管理面 + 消费面 | Phase 1 |
| **MCP Agent 协议** | Agent 工具调用 | 消费面（Agent 交互中沉淀个人资产） | Phase 1 |
| **CLI** | 命令行管理 | 管理面 | Phase 1 |

---

## 调用关系

```
api/ ───────▶ services/ ───────▶ engine/ ───────▶ storage/
 │                │                │                │
 │                │                │                ▼
 │                │                │           storage/base.py
 │                │                │                │
 │                │                │                ▼
 │                │                │          storage/graph/
 │                │                │          storage/vector/
 │                │                │          storage/sqlite/
 │                │                │
 │                │                ▼
 │                │           core/schema/
 │                │           core/extraction/
 │                │
 │                ▼
 │         visualization/
 │         mcp/tools/
 │
 ▼
examples/*/schema.yaml  ← 三类资产定义入口
```

---

## 关键约束

1. **本地优先**：L1 层必须有本地实现，外部存储为可选
2. **无循环依赖**：模块依赖只能向下，禁止平级/向上
3. **Schema 驱动**：业务逻辑在 YAML 定义，非代码
4. **三层资产统一模型**：IT 资产、个人知识、组织资产使用同一本体描述
5. **资产可链接**：存储层维护三层资产间的显式关系，引擎层负责推理
6. **增量优先**：提取管线按 SHA256 缓存，增量处理变化文件

## 技术实现模式

```
参考各参考系统的实现模式，OntologyEngine 采用以下技术实现策略：

1. 异步优先（参考 Cognee + m_flow）：
   - 所有 I/O 操作使用 async/await
   - KuzuDB 异步包装：ThreadPoolExecutor + run_in_executor
   - ChromaDB 异步搜索：asyncio.gather 并行多集合检索
   - 信号量控制并发：asyncio.Semaphore(data_per_batch)

2. 缓存分层（参考 Graphify + LLM-Wiki-Agent + codebase-memory-mcp）：
   - L0 内存缓存：Python dict/LRU（热数据，<1ms）
   - L1 文件缓存：diskcache/SQLite（温数据，<10ms）
   - L2 SHA256 语义缓存：按 source_file 分组，返回 (cached, uncached)
   - L3 推断检查点：JSONL 格式，支持 resume

3. 增量处理（参考 Graphify + codebase-memory-mcp + LLM-Wiki-Agent）：
   - 文件级：SHA256(内容+相对路径) 比对，仅处理变化文件
   - 图级：推断检查点 .inferred_edges.jsonl，支持 resume
   - 索引级：文件哈希缓存，增量更新向量索引
   - 原子写入：os.replace() 实现原子替换

4. 置信度标注（参考 Graphify + LLM-Wiki-Agent）：
   - EXTRACTED：确定性提取，confidence=1.0
   - INFERRED：LLM 推断，confidence=0.4-0.9
   - AMBIGUOUS：低置信度，需人工审查
   - 边去重：双向边合并，保留最高置信度

5. 多集合向量索引（参考 m_flow）：
   - 按节点类型和字段分集合存储向量
   - Bundle Search 时并行搜索所有集合
   - 元数据过滤提供额外检索 boost（参考 MemPalace 34% 提升）

6. 边语义参与检索（参考 m_flow Edge.edge_text）：
   - 边文本向量化后存入独立集合
   - 检索时构建 edge_hit_map
   - 代价传播中：命中边使用向量距离，未命中边使用 miss_penalty=0.9

7. 管道状态持久化（参考 Cognee PipelineRun）：
   - SQLite pipeline_runs 表记录管道运行状态
   - 支持 started/completed/errored 三种状态
   - 后台执行模式：asyncio.create_task + 状态查询

8. MCP 双模式（参考 Cognee MCP + m_flow MCP）：
   - Direct 模式：直接导入库函数调用
   - API 模式：通过 HTTP 请求连接远程服务
   - 传输层：stdio / SSE / HTTP 三种
   - 后台任务：耗时操作 asyncio.create_task，通过 status 工具查询
```

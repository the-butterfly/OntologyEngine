# 存储设计总览

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/06-tech-stack.md` | **last_verified**: 2026-04-19
> **[单一事实源]**: 本文档为存储层重写后的唯一设计入口

---

## 目的

定义 OntologyEngine 存储层的目标架构，将当前 DuckDB 单一存储拆分为 KuzuDB + ChromaDB + SQLite 三引擎协同架构，实现图遍历、向量检索、事务元数据的职责分离。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | DuckDB 不支持 Cypher 查询，图遍历依赖 JOIN 模拟，性能差 | 多跳推理查询复杂度 O(n^k)，无法支撑 Bundle Search |
| 2 | 向量检索使用内存实现（LocalVectorStore），无持久化 | 重启后向量索引丢失，无法支撑语义检索 |
| 3 | 实体/关系/元数据/指标/规则混在单一 DuckDB 中 | 职责耦合，无法独立扩展和优化 |
| 4 | Schema v2 Instance 层（EntityInstance、EdgeInstance、CategoryTag、MetricValue、KnowledgeFragment）缺乏对应存储模型 | 实例数据结构隐含在代码中，无法跨模块对齐 |
| 5 | 互索引边（EXTRACTED_FROM、SUPPORTED_BY、DEFINED_IN、TRACE_TO）缺乏存储实现 | Layer-R 与 Layer-S 在数据层面完全断连 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    Storage Layer                              │
├──────────────────────────────────────────────────────────────┤
│  GraphStore ──▶ KuzuDB (data/graph/ontology.kuzu)            │
│              └─▶ Neo4j (云端扩展)                              │
├──────────────────────────────────────────────────────────────┤
│  VectorStore ──▶ ChromaDB (data/vectors/)                    │
│               └─▶ LanceDB / FAISS (>100K 规模扩展)                      │
├──────────────────────────────────────────────────────────────┤
│  MetaStore ──▶ SQLite (data/meta.db, WAL 模式)               │
│             └─▶ PostgreSQL (云端扩展)                          │
├──────────────────────────────────────────────────────────────┤
│  Cache ──▶ diskcache (data/cache/)                           │
└──────────────────────────────────────────────────────────────┘
```

### 存储职责矩阵

| 数据类型 | 存储引擎 | 承载资产 | 核心设计来源 |
|---------|---------|---------|-------------|
| 实体关系主存储 | KuzuDB | EntityInstance、EdgeInstance、RuleDefinition、互索引边 | m_flow GraphProvider |
| 向量检索（<100K） | ChromaDB | KnowledgeFragment 向量、边向量、实体名称/摘要向量 | MemPalace |
| 向量检索（>100K） | LanceDB / FAISS | 规模扩展时的向量索引 | Graphify |
| 事务 + 元数据 | SQLite WAL | Dataset 元数据、Schema 版本、矛盾报告、管道状态、文件哈希 | m_flow FSCache + MAMGA |
| 指标聚合缓存 | SQLite + diskcache | 分析结果缓存 | m_flow FSCache 模式 |

---

## 文档地图

| 子文档 | 内容 | 状态 |
|--------|------|------|
| [kuzudb-schema.md](./kuzudb-schema.md) | KuzuDB 节点/边表 Schema，对齐 Schema v2 Instance 层 | draft |
| [chromadb-collections.md](./chromadb-collections.md) | ChromaDB 集合设计、嵌入策略、CRUD 操作 | draft |
| [sqlite-tables.md](./sqlite-tables.md) | SQLite 表结构、WAL 模式、SchemaVersionManager | draft |
| [interfaces.md](./interfaces.md) | 存储接口升级规范（GraphStore、VectorStore、MetaStore） | draft |
| [migration.md](./migration.md) | DuckDB → KuzuDB 迁移路径、数据映射、回滚计划 | draft |
| [03-storage-design.md](./03-storage-design.md) | 旧存储设计（DuckDB 方案），保留供迁移参考 | [已过期入口] |

---

## 关键设计决策

| # | 决策 | 理由 | 对齐参考 |
|---|------|------|---------|
| D-S-1 | DuckDB → KuzuDB + ChromaDB + SQLite 三引擎拆分 | 图遍历、向量检索、事务元数据职责分离，各引擎独立优化 | m_flow GraphProvider + VectorProvider |
| D-S-2 | KuzuDB 使用多节点表而非 Cognee 的 2 表极简设计 | Schema v2 Instance 层有 5 种节点类型（EntityInstance、RuleDefinition、KnowledgeFragment、CategoryTag、MetricValue），多表设计支持类型约束和索引优化 | m_flow GraphProvider 多表模式 |
| D-S-3 | ChromaDB 使用 7 集合分字段索引而非单集合 | 分字段索引支持精确的语义检索场景（名称检索 vs 摘要检索 vs 边语义检索），参考 m_flow 多集合设计 | m_flow VectorProvider |
| D-S-4 | SQLite 使用 WAL 模式 | WAL 支持并发读写，低延迟写入，适合元数据高频更新场景 | MemPalace SQLite WAL |
| D-S-5 | 异步接口优先 | 所有 I/O 操作使用 async/await，KuzuDB 通过 ThreadPoolExecutor 包装 | Cognee KuzuAdapter + m_flow KuzuAdapter |
| D-S-6 | 边分区写入策略 | KuzuDB UNWIND+MERGE 在共享端点时触发 write-write conflict，使用端点分区批处理 | m_flow _partition_edges_by_endpoints |
| D-S-7 | 反馈权重闭环 | EntityInstance.feedback_weight 参与检索评分，支持记忆强化 | Cognee apply_feedback_weights |

---

## 与基线的偏差

| 维度 | 基线（DuckDB） | 目标（KuzuDB+ChromaDB+SQLite） | 偏差原因 |
|------|---------------|-------------------------------|---------|
| 图存储 | DuckDB entities/relations 表 + JOIN | KuzuDB 多节点表 + Cypher 查询 | DuckDB 不支持图遍历，无法支撑 Bundle Search |
| 向量存储 | LocalVectorStore 内存实现 | ChromaDB 持久化 + 7 集合 | 内存实现无持久化，重启丢失 |
| 元数据存储 | DuckDB 复用主数据库 | SQLite WAL 独立数据库 | 事务元数据与图数据职责分离 |
| 接口设计 | StorageBackend 单一接口 | GraphStore + VectorStore + MetaStore 三接口 | 职责分离，各接口独立演化 |
| 批量写入 | 逐条 INSERT OR REPLACE | KuzuDB UNWIND+MERGE + 端点分区 | KuzuDB 批量写入有 write-write conflict 限制 |
| 时序支持 | 无 | valid_from/valid_to 字段 | Schema v2 Instance 层要求时序建模 |
| 溯源支持 | 无 | source_pipeline + source_content_hash | Schema v2 Instance 层要求溯源链 |
| 互索引边 | 无 | EXTRACTED_FROM/SUPPORTED_BY/DEFINED_IN/TRACE_TO | Schema v2 互索引边语法要求 |

---

## 数据流

### 写入流程

```
EntityInstance 写入：
  1. KuzuDB MERGE 节点（EntityNode 表）
  2. ChromaDB upsert 向量（entity_name + entity_summary 集合）
  3. SQLite 写入 audit_log

EdgeInstance 写入：
  1. KuzuDB MERGE 边（对应关系表）
  2. ChromaDB upsert 边向量（edge_relationship_name + edge_text 集合）
  3. SQLite 写入 audit_log

KnowledgeFragment 写入：
  1. KuzuDB MERGE 节点（KnowledgeFragmentNode 表）
  2. ChromaDB upsert 向量（knowledge_fragment 集合）
  3. SQLite 写入 file_hashes + pipeline_runs
```

### 检索流程

```
Layer-R 检索：
  ChromaDB.search(knowledge_fragment, query_vector) → KnowledgeFragment 列表
  → SUPPORTED_BY 边扩展到 EntityInstance

Layer-S 检索：
  KuzuDB.get_neighborhood(entity_id, depth=2) → 子图
  → Bundle Search 成本传播

混合检索：
  ChromaDB.search(多集合并行) → 候选集
  → KuzuDB 图遍历扩展
  → RRF 融合排序
```

---

## 配置模型

```python
class StorageConfig(BaseSettings):
    mode: str = "local"

    graph_backend: str = "kuzu"
    vector_backend: str = "chroma"
    meta_backend: str = "sqlite"

    data_dir: Path = Path("./data")

    kuzu_db_path: str = "data/ontology.kuzu"
    kuzu_buffer_pool_mb: int = 4096
    kuzu_max_db_mb: int = 32768

    chroma_persist_dir: str = "data/vectors"
    chroma_embedding_model: str = "text-embedding-3-small"
    chroma_embedding_dimension: int = 1536

    sqlite_db_path: str = "data/meta.db"

    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None
```

---

## 设计来源

| 来源 | 贡献的设计点 |
|------|-------------|
| **m_flow** | GraphProvider 抽象接口、Kuzu 边分区优化、checkpoint 机制、Bundle Search、多集合向量设计 |
| **Cognee** | KuzuAdapter 异步执行模式、UNWIND 批量操作、feedback_weight 机制、DataPoint 溯源链 |
| **MemPalace** | ChromaDB 向量存储、Wing/Room metadata 过滤、SQLite WAL 时序三元组、verbatim 存储 |
| **Graphify** | 三通道提取、SHA256 缓存、Leiden 社区检测、Confidence 标签 |
| **MAMGA** | SQLite 事务日志、时序多图、causal 链接 |

# 存储设计

> **Primary**: KuzuDB + ChromaDB + SQLite（目标架构）
> **已废弃**: ~~DuckDB + Faiss~~（旧方案，保留供参考）
> **Future**: Neo4j + LanceDB（可选扩展）
> **状态**: 当前实现与本文档存在偏差，详见 `docs/04-migration-and-gap/README.md`
> **最后核验**: 2026-04-19

## 架构

### 分层视图（目标架构）

```
┌──────────────────────────────────────────────────────────────┐
│                    Storage Layer                              │
├──────────────────────────────────────────────────────────────┤
│  GraphStore ──▶ KuzuDB (data/graph/ontology.kuzu)            │
│              └─▶ NetworkX (按需加载，图算法)                   │
├──────────────────────────────────────────────────────────────┤
│  VectorStore ──▶ ChromaDB/LanceDB (data/vector/)             │
│               └─▶ FAISS (离线批量索引构建)                     │
├──────────────────────────────────────────────────────────────┤
│  MetaStore ──▶ SQLite (data/meta.db, WAL 模式)               │
├──────────────────────────────────────────────────────────────┤
│  Cache ──▶ diskcache (data/cache/)                           │
└──────────────────────────────────────────────────────────────┘
```

### 本地存储架构

```
┌───────────────────────────────────────────────────┐
│  Storage Interface (storage/base.py)              │
├───────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ KuzuGraphStore│  │ ChromaVectorStore         │ │
│  │ (图数据库)     │  │ (向量索引+元数据过滤)      │ │
│  └──────────────┘  └───────────────────────────┘ │
├───────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ SQLiteMeta   │  │ NetworkXGraph             │ │
│  │ (元数据+缓存) │  │ (按需加载，图算法)         │ │
│  └──────────────┘  └───────────────────────────┘ │
└───────────────────────────────────────────────────┘
```

### 已废弃分层视图（旧方案）

```
已废弃 ── 以下为 DuckDB + Faiss 旧方案，保留供参考
┌─────────────────────────────────────────────────────────┐
│                    Storage Layer                        │
├─────────────────────────────────────────────────────────┤
│  DuckDBStorage ──▶ DuckDB (data/ontology.db)           │
│                 └─▶ Memory (NetworkX 按需加载)          │
├─────────────────────────────────────────────────────────┤
│  VectorStore ──▶ Faiss (data/vectors/index.faiss)       │
│               └─▶ Metadata (JSON)                       │
├─────────────────────────────────────────────────────────┤
│  MetaStore ──▶ DuckDB (复用主数据库)                    │
├─────────────────────────────────────────────────────────┤
│  Cache ──▶ diskcache (data/cache/)                      │
└─────────────────────────────────────────────────────────┘
```

---

## KuzuDB 图数据库设计（目标架构）

### 数据库文件

```
data/
└── ontology.kuzu       # KuzuDB 单文件，零配置
```

### 表结构

参考 Cognee KuzuAdapter 的 2 表极简设计 + OntologyEngine 业务扩展：

#### Node - 节点表
```cypher
CREATE NODE TABLE EntityNode (
    id STRING PRIMARY KEY,
    name STRING,
    type STRING NOT NULL,          -- EntityType/ConceptType/EventType/IndexType
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    confidence DOUBLE DEFAULT 1.0, -- EXTRACTED=1.0 / INFERRED=0.4-0.9 / AMBIGUOUS=0.1-0.3
    source_file STRING,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    updated_at TIMESTAMP DEFAULT current_timestamp(),
    properties MAP(STRING, STRING)  -- 动态属性（JSON 序列化）
)
```

#### EDGE - 关系表
```cypher
CREATE REL TABLE Relationship (
    FROM EntityNode TO EntityNode,
    relationship_name STRING NOT NULL,
    confidence DOUBLE DEFAULT 1.0,
    edge_text STRING,              -- 边语义文本（参考 m_flow，向量化后参与检索）
    source_file STRING,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    properties MAP(STRING, STRING)  -- 动态属性
)
```

### 关系类型分类

参考 MAMGA + KAG + m_flow 的边类型系统：

| 类别 | 关系名 | 说明 | 置信度 |
|------|--------|------|--------|
| **时序** | PRECEDES / SUCCEEDS | 严格时序，携带 time_delta | 1.0 |
| **时序** | TEMPORALLY_CLOSE | 时间接近，携带 weight | 0.5-1.0 |
| **语义** | RELATED_TO / SIMILAR_TO | 向量相似度关联 | 0.4-1.0 |
| **语义** | SAME_ENTITY | 同义实体互连 | 0.8-1.0 |
| **语义** | PART_OF / CONTAINS | 层级包含 | 1.0 |
| **因果** | LEADS_TO / BECAUSE_OF | 因果推导 | 0.6-1.0 |
| **因果** | ENABLES / PREVENTS | 使能/阻止 | 0.6-1.0 |
| **实体** | REFERS_TO / MENTIONED_IN | 实体引用 | 1.0 |
| **互索引** | EXTRACTED_FROM / SUPPORTED_BY | 知识溯源 | 1.0 |
| **互索引** | DEFINED_IN / TRACE_TO | 规则溯源 | 1.0 |
| **逻辑** | IND#belongTo 等 | KAG 规则推导的逻辑边 | 0.5-1.0 |

### KuzuDB 技术实现框架

```
参考 Cognee KuzuAdapter（2400+ 行，最完整的 Kuzu 适配器）：

异步执行：ThreadPoolExecutor + run_in_executor 将同步 Kuzu 查询包装为异步
并发控制：asyncio.Lock 保护连接变更；可选 Redis 分布式锁（shared_kuzu_lock）
批量操作：UNWIND Cypher 子句实现批量节点/边 MERGE
反馈权重：节点和边都支持 feedback_weight 属性，用于记忆强化
子图查询：get_neighborhood() 支持 k-hop 遍历，get_nodeset_subgraph() 支持按类型和名称过滤
S3 支持：自动 pull/push 图数据库文件到 S3
版本迁移：自动检测 Kuzu 存储版本并迁移

参考 m_flow GraphProvider 适配器模式：
GraphProvider 抽象基类 → Cypher 查询、节点/边 CRUD、子图提取、邻居遍历
_track_changes 装饰器 → 自动记录节点/边变更到 GraphRelationshipLedger
实现：KuzuDB（默认嵌入式）、Neo4j、Neptune
数据集隔离：DatasetDatabaseHandler 接口

参考 codebase-memory-mcp RAM-first 设计：
预编译语句缓存：所有 SQL 语句预编译并缓存，避免重复解析
空闲驱逐：60 秒无活动后关闭缓存的项目 store，释放 SQLite 内存
文件哈希：用于增量索引
```

---

## ChromaDB 向量数据库设计（目标架构）

### 文件结构

```
data/chroma/
├── chroma.sqlite3           # ChromaDB 持久化存储
└── {collection_id}/         # 各集合数据
```

### 集合设计

参考 m_flow 的多集合设计 + QMD 的 FTS5+sqlite-vec 混合索引：

| 集合名 | 向量化字段 | 说明 |
|--------|-----------|------|
| `entity_name` | name + canonical_name | 实体名称检索（参考 m_flow Entity_name） |
| `entity_summary` | summary/description | 实体摘要检索 |
| `facet_search_text` | search_text | 维度检索锚点（参考 m_flow Facet_search_text） |
| `facet_anchor_text` | anchor_text | 中层丰富语义（参考 m_flow Facet_anchor_text） |
| `facetpoint_search_text` | search_text | 原子断言检索（参考 m_flow FacetPoint_search_text） |
| `edge_relationship_name` | edge_text | 边语义检索（参考 m_flow RelationType_relationship_name） |
| `knowledge_fragment` | content | 知识碎片原文检索 |

### 嵌入策略

参考 QMD 双模型族嵌入格式 + m_flow 嵌入引擎：

```
默认嵌入模型：text-embedding-3-small（OpenAI，1536 维）
可选本地模型：all-MiniLM-L6-v2（SentenceTransformer，384 维）

查询/文档嵌入格式（参考 QMD）：
  EmbeddingGemma 格式：
    query: "task: search result | query: {query}"
    doc:   "title: {title} | text: {content}"
  Qwen3-Embedding 格式（CJK 优化）：
    query: "Instruct: Retrieve relevant documents for the given query\nQuery: {query}"
    doc:   "{title}\n{content}"

并行嵌入（参考 QMD llm.ts）：
  GPU：根据 VRAM 的 25% 计算并行度，上限 8
  CPU：根据数学核心数 / 4 计算并行度，上限 4
```

### ChromaDB 技术实现框架

```
参考 m_flow VectorProvider Protocol：
集合管理：create_collection / delete_collection / list_collections
MemoryNode CRUD：add_nodes / update_nodes / delete_nodes
语义搜索：search(query_embedding, top_k, filter)
嵌入生成：embed_data(texts) → embeddings
多租户钩子：create_dataset / delete_dataset

参考 Cognee VectorDBInterface（Protocol）：
has_collection / create_collection / create_data_points / search / batch_search / embed_data
上下文感知配置：get_vectordb_context_config() 允许不同异步任务使用不同数据库配置
多租户隔离：ENABLE_BACKEND_ACCESS_CONTROL=True 时，每个 user+dataset 组合可拥有独立实例

元数据过滤（参考 MemPalace Wing/Room/Hall）：
ChromaDB where 条件支持 wing/room/source_file 等元数据过滤
MemPalace 验证：元数据过滤提供 34% 检索提升
```

---

## SQLite 元数据库设计（目标架构）

### 数据库文件

```
data/
└── meta.db       # SQLite WAL 模式，ACID 安全
```

### 表结构

参考 codebase-memory-mcp + Cognee 管道状态管理：

```sql
-- Schema 版本管理
CREATE TABLE schema_versions (
    id VARCHAR PRIMARY KEY,
    version INTEGER NOT NULL,
    schema_snapshot TEXT NOT NULL,     -- 全量快照 JSON
    change_description VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR NOT NULL
);

-- 审计日志
CREATE TABLE audit_log (
    id VARCHAR PRIMARY KEY,
    operation_type VARCHAR NOT NULL,   -- create | update | delete | execute | schema_change
    target_type VARCHAR NOT NULL,      -- entity | edge | schema | rule
    target_id VARCHAR NOT NULL,
    actor VARCHAR NOT NULL,
    before_state TEXT,                 -- JSON
    after_state TEXT,                  -- JSON
    deployment_mode VARCHAR DEFAULT 'local',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 管道运行状态（参考 Cognee PipelineRun）
CREATE TABLE pipeline_runs (
    id VARCHAR PRIMARY KEY,
    pipeline_name VARCHAR NOT NULL,
    status VARCHAR NOT NULL,           -- started | completed | errored
    dataset_id VARCHAR,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    metadata TEXT                      -- JSON
);

-- 文件哈希缓存（参考 codebase-memory-mcp + Graphify SHA256）
CREATE TABLE file_hashes (
    file_path VARCHAR PRIMARY KEY,
    content_hash VARCHAR NOT NULL,     -- SHA256(内容 + 相对路径)
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 矛盾报告
CREATE TABLE contradiction_reports (
    id VARCHAR PRIMARY KEY,
    entity_id VARCHAR NOT NULL,
    field VARCHAR,
    source_a VARCHAR NOT NULL,
    value_a TEXT,
    source_b VARCHAR NOT NULL,
    value_b TEXT,
    status VARCHAR DEFAULT 'pending',  -- pending | resolved | rejected
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_by VARCHAR
);

CREATE INDEX idx_audit_target ON audit_log(target_type, target_id);
CREATE INDEX idx_audit_actor ON audit_log(actor);
CREATE INDEX idx_audit_time ON audit_log(created_at);
CREATE INDEX idx_pipeline_status ON pipeline_runs(status);
CREATE INDEX idx_file_hash ON file_hashes(content_hash);
CREATE INDEX idx_contradiction_status ON contradiction_reports(status);
```

---

## 已废弃：DuckDB 设计（旧方案）

> 以下为 DuckDB 旧方案，保留供迁移参考

### 数据库文件

```
data/
└── ontology.db       # 单文件，零配置
```

### 表结构

#### entities - 实体表
```sql
CREATE TABLE entities (
    id VARCHAR PRIMARY KEY,
    concept_type VARCHAR NOT NULL,
    attributes JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entities_type ON entities(concept_type);
```

#### relations - 关系表
```sql
CREATE TABLE relations (
    id VARCHAR PRIMARY KEY,
    from_id VARCHAR NOT NULL REFERENCES entities(id),
    to_id VARCHAR NOT NULL REFERENCES entities(id),
    relation_type VARCHAR NOT NULL,
    attributes JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_relations_from ON relations(from_id);
CREATE INDEX idx_relations_to ON relations(to_id);
CREATE INDEX idx_relations_type ON relations(relation_type);
```

#### audit_log - 审计日志（决策 #7）

> **当前实现状态**: ❌ 未实现 (2026-04-16)
```sql
CREATE TABLE audit_log (
    id VARCHAR PRIMARY KEY,
    operation_type VARCHAR NOT NULL,     -- create | update | delete | execute | schema_change
    target_type VARCHAR NOT NULL,        -- entity | edge | schema | rule
    target_id VARCHAR NOT NULL,
    actor VARCHAR NOT NULL,              -- 执行者（用户/Agent ID）
    before_state JSON,                   -- 变更前状态
    after_state JSON,                    -- 变更后状态
    deployment_mode VARCHAR DEFAULT 'local',  -- local | platform
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_target ON audit_log(target_type, target_id);
CREATE INDEX idx_audit_actor ON audit_log(actor);
CREATE INDEX idx_audit_time ON audit_log(created_at);
```

#### schema_versions - Schema 版本管理（决策 #8）

> **当前实现状态**: ❌ 未实现 (2026-04-16)
```sql
CREATE TABLE schema_versions (
    id VARCHAR PRIMARY KEY,
    version INTEGER NOT NULL,
    schema_snapshot JSON NOT NULL,        -- 全量快照
    change_description VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR NOT NULL
);

CREATE INDEX idx_schema_versions ON schema_versions(version);
```

---

## 向量存储

> **当前实现状态**: ⚠️ 偏离目标设计 (2026-04-16)
> 文档设计为 `FaissVectorStore`，实际实现为 `LocalVectorStore` 内存向量存储，无持久化。

### 文件结构

```
data/vectors/
├── index.faiss       # Faiss 索引文件
└── metadata.json     # 向量元数据 (id -> entity 映射)
```

### 元数据格式

```json
{
  "dimension": 1536,
  "index_type": "IndexFlatIP",
  "vectors": [
    {"id": "S001", "entity_type": "Supplier", "text": "..."}
  ]
}
```

---

## 存储接口（目标架构）

```python
# storage/base.py

class GraphStore(ABC):
    @abstractmethod
    async def add_entity(self, entity: Entity) -> None: ...

    @abstractmethod
    async def get_entity(self, entity_id: str) -> Entity | None: ...

    @abstractmethod
    async def add_edge(self, edge: Edge) -> None: ...

    @abstractmethod
    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        direction: str = "both"
    ) -> list[Entity]: ...

    @abstractmethod
    async def get_neighborhood(
        self,
        entity_id: str,
        k: int = 2
    ) -> SubGraph: ...

    @abstractmethod
    async def query(
        self,
        concept_type: str | None = None,
        filters: dict | None = None
    ) -> list[Entity]: ...

    @abstractmethod
    async def query_cypher(self, cypher: str, params: dict | None = None) -> list[dict]: ...


class VectorStore(ABC):
    @abstractmethod
    async def add_vectors(
        self,
        collection: str,
        ids: list[str],
        vectors: np.ndarray,
        metadata: list[dict] | None = None
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_vector: np.ndarray,
        top_k: int = 10,
        filters: dict | None = None
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    async def batch_search(
        self,
        collection: str,
        query_vectors: np.ndarray,
        top_k: int = 10,
        filters: dict | None = None
    ) -> list[list[VectorSearchResult]]: ...

    @abstractmethod
    async def create_collection(self, name: str, dimension: int) -> None: ...

    @abstractmethod
    async def delete_collection(self, name: str) -> None: ...
```

### 已废弃存储接口（旧方案）

```python
已废弃 ── 以下为旧版 GraphStore/VectorStore 接口，保留供参考

class GraphStore(ABC):
    @abstractmethod
    def add_entity(self, entity: Entity) -> None: ...

    @abstractmethod
    def get_entity(self, entity_id: str) -> Entity | None: ...

    @abstractmethod
    def add_edge(self, edge: Edge) -> None: ...

    @abstractmethod
    def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        direction: str = "both"
    ) -> list[Entity]: ...

    @abstractmethod
    def query(
        self,
        concept_type: str | None = None,
        filters: dict | None = None
    ) -> list[Entity]: ...


class VectorStore(ABC):
    @abstractmethod
    def add_vectors(
        self,
        ids: list[str],
        vectors: np.ndarray,
        metadata: list[dict] | None = None
    ) -> None: ...

    @abstractmethod
    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        filters: dict | None = None
    ) -> list[VectorSearchResult]: ...
```

---

## NetworkX 图存储

**当前实现状态**: ⚠️ 偏离目标设计 (2026-04-16)

- 实际实现为独立内存图存储，节点/边直接存入 NetworkX
- 未实现从 DuckDB 按需加载子图的 `load_from_duckdb` 逻辑
- 未实现 LRU 缓存机制

```python
class NetworkXGraph:
    """内存图，用于图算法 (目标设计)"""

    def load_from_duckdb(
        self,
        center_id: str,
        depth: int = 2,
        relation_types: list[str] | None = None
    ) -> nx.DiGraph:
        """从 DuckDB 加载子图到内存"""
        # 目标设计，当前未实现
```

---

## 性能优化

| 优化点 | 方案 |
|--------|------|
| 属性过滤 | DuckDB JSON 索引 + 物化视图 |
| 关系查询 | from_id/to_id 复合索引 |
| 向量检索 | Faiss IVF 索引 (数据量>10万) **[未实现，当前为内存实现]** |
| 图算法 | 子图加载 + NetworkX 缓存 **[未实现按需加载]** |
| 热数据 | diskcache LRU **[未实现]** |

---

## 存储策略对比（目标架构）

| 数据类型 | 本地实现 | 预留接口 | 说明 |
|----------|----------|----------|------|
| 主存储 | KuzuDB | Neo4j, Neptune | 嵌入式 Cypher 图数据库，零运维 |
| 图算法 | NetworkX (按需加载) | - | 社区检测、路径查询、Leiden 聚类 |
| 向量 | ChromaDB | LanceDB, PGVector, Milvus | 轻量嵌入，支持元数据过滤 |
| 离线索引 | FAISS | - | 大规模批量相似度计算 |
| 元数据 | SQLite (WAL) | PostgreSQL | Schema 版本、审计、管道状态、文件哈希 |
| 缓存 | diskcache | Redis | LRU + 持久化 |
| 配置/日志 | 本地文件 | - | YAML/JSON |

### 已废弃存储策略对比（旧方案）

| 数据类型 | 本地实现 | 预留接口 | 说明 |
|----------|----------|----------|------|
| 主存储 | DuckDB | - | OLAP 存储，实体/关系/指标 |
| 图算法 | NetworkX (按需加载) | - | 担保链检测、路径查询 |
| 向量 | faiss-cpu / annoy | pgvector | 本地向量索引 |
| 缓存 | 内存 dict + diskcache | Redis | LRU + 持久化 |
| 配置/日志 | 本地文件 | - | YAML/JSON |

---

## 优缺点分析

| 方面 | 本地存储 | 外部数据库 |
|------|----------|------------|
| **部署** | 零依赖，一键启动 | 需要额外部署 |
| **性能** | 单节点优秀 | 可水平扩展 |
| **容量** | 受单机限制 | 可扩展 |
| **并发** | 适合低频写入 | 高并发优化 |
| **场景** | 开发、演示、小规模 | 生产、大规模 |

---

## 迁移路径

```python
# config.py
class StorageConfig(BaseSettings):
    # 存储模式: local | neo4j | hybrid
    graph_store_type: str = "kuzu"  # 默认 KuzuDB
    vector_store_type: str = "chroma"  # 默认 ChromaDB

    # 本地存储路径
    data_dir: Path = Path("./data")

    # KuzuDB 配置
    kuzu_db_path: str = "data/ontology.kuzu"

    # ChromaDB 配置
    chroma_persist_dir: str = "data/chroma"

    # SQLite 配置
    sqlite_db_path: str = "data/meta.db"

    # Neo4j 配置（预留）
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None

    # PostgreSQL 配置（预留）
    postgres_dsn: str | None = None
```

### 配置切换

**部署模式双模式（决策 #7）**：配置文件驱动切换，本地+平台双模式设计。

```yaml
# config.yaml
ontologyengine:
  # 部署模式: local | platform
  deployment_mode: local

storage:
  graph:
    type: kuzu  # kuzu | neo4j
    kuzu:
      db_path: data/ontology.kuzu
    neo4j:
      uri: bolt://localhost:7687
      user: neo4j
      password: ${NEO4J_PASSWORD}

  vector:
    type: chroma  # chroma | lancedb | pgvector
    chroma:
      persist_dir: data/chroma
      embedding_model: text-embedding-3-small
    lancedb:
      db_path: data/lance
    pgvector:
      dsn: postgresql://...

  meta:
    type: sqlite  # sqlite | postgresql
    sqlite:
      db_path: data/meta.db

# 本地模式审计配置
audit:
  mode: local               # local: 写本地 SQLite | platform: 通过中间件转发
  platform_endpoint: null   # 平台审计服务端点（仅 platform 模式）
```

### 工厂模式

```python
# storage/__init__.py
from .kuzu.store import KuzuGraphStore
from .chroma.store import ChromaVectorStore
from .adapters.neo4j_store import Neo4jGraphStore  # 预留

def create_graph_store(config: StorageConfig) -> GraphStore:
    if config.graph_store_type == "kuzu":
        return KuzuGraphStore(config.kuzu_db_path)
    elif config.graph_store_type == "neo4j":
        return Neo4jGraphStore(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    else:
        raise ValueError(f"Unknown graph store type: {config.graph_store_type}")

def create_vector_store(config: StorageConfig) -> VectorStore:
    if config.vector_store_type == "chroma":
        return ChromaVectorStore(config.chroma_persist_dir)
    else:
        raise ValueError(f"Unknown vector store type: {config.vector_store_type}")
```

### 数据迁移（DuckDB → KuzuDB）

```python
# DuckDB → KuzuDB 迁移脚本
async def migrate_duckdb_to_kuzu(duckdb_path: str, kuzu_path: str):
    duck_conn = duckdb.connect(duckdb_path, read_only=True)
    kuzu_conn = kuzu.Connection(kuzu.Database(kuzu_path))

    # 迁移实体
    entities = duck_conn.execute("SELECT * FROM entities").fetchall()
    for entity in entities:
        kuzu_conn.execute(
            "MERGE (n:EntityNode {id: $id, name: $name, type: $type, properties: $props})",
            {"id": entity[0], "name": entity[1], "type": entity[2], "props": entity[3]}
        )

    # 迁移关系
    relations = duck_conn.execute("SELECT * FROM relations").fetchall()
    for rel in relations:
        kuzu_conn.execute(
            "MATCH (a:EntityNode {id: $from}), (b:EntityNode {id: $to}) "
            "MERGE (a)-[r:Relationship {relationship_name: $name, properties: $props}]->(b)",
            {"from": rel[1], "to": rel[2], "name": rel[3], "props": rel[4]}
        )
```

### 已废弃迁移路径（旧方案）

```python
已废弃 ── 以下为 DuckDB 旧方案迁移路径，保留供参考

# config.py
class StorageConfig(BaseSettings):
    # 存储模式: local | neo4j | hybrid
    graph_store_type: str = "local"  # 默认本地
    vector_store_type: str = "local"

    # 本地存储路径
    data_dir: Path = Path("./data")

    # Neo4j 配置（预留）
    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None

    # PostgreSQL 配置（预留）
    postgres_dsn: str | None = None

# config.yaml
ontologyengine:
  deployment_mode: local
storage:
  graph:
    type: duckdb  # duckdb | neo4j
    neo4j:
      uri: bolt://localhost:7687
      user: neo4j
      password: ${NEO4J_PASSWORD}
  vector:
    type: faiss  # faiss | pgvector
    pgvector:
      dsn: postgresql://...

# storage/__init__.py
from .duckdb.store import DuckDBStorage
from .adapters.neo4j_store import Neo4jGraphStore  # 预留

def create_storage(config: StorageConfig) -> StorageBackend:
    if config.graph_store_type == "duckdb":
        return DuckDBStorage(config.data_dir / "ontology.db")
    elif config.graph_store_type == "neo4j":
        return Neo4jGraphStore(config.neo4j_uri, config.neo4j_user, config.neo4j_password)
    else:
        raise ValueError(f"Unknown storage type: {config.graph_store_type}")

# DuckDB 支持直接导出为 Parquet
async def export_to_parquet(duckdb_store: DuckDBStorage, output_dir: str):
    await asyncio.to_thread(
        duckdb_store._conn.execute,
        f"COPY entities TO '{output_dir}/entities.parquet' (FORMAT PARQUET)"
    )
```

---

## Schema 版本管理（决策 #8）

**全量快照策略**：每次变更存储完整 Schema 副本。

| 策略 | 优点 | 缺点 |
|------|------|------|
| **全量快照（选用）** | 实现简单、回滚直接、无 diff 算法依赖 | 存储开销（Schema 通常 < 100KB，可接受） |
| Schema Diff + 增量 | 存储小 | 需 diff 算法，回滚需重放 |
| Event Sourcing | 最灵活、可重放任意版本 | 复杂度高 |

### 版本管理操作

```python
class SchemaVersionManager:
    """Schema 版本管理"""
    
    def commit_version(
        self,
        schema: Schema,
        change_description: str,
        actor: str
    ) -> SchemaVersion:
        """提交新版本（全量快照）"""
        version = self._next_version()
        snapshot = SchemaVersion(
            id=f"sv_{version}",
            version=version,
            schema_snapshot=schema.to_json(),  # 全量快照
            change_description=change_description,
            created_by=actor
        )
        self.storage.save(snapshot)
        return snapshot
    
    def rollback(self, target_version: int) -> Schema:
        """回滚到指定版本"""
        snapshot = self.storage.get_version(target_version)
        return Schema.from_json(snapshot.schema_snapshot)
    
    def diff(self, v1: int, v2: int) -> SchemaDiff:
        """比较两个版本的差异"""
        s1 = Schema.from_json(self.storage.get_version(v1).schema_snapshot)
        s2 = Schema.from_json(self.storage.get_version(v2).schema_snapshot)
        return self._compute_diff(s1, s2)
    
    def impact_analysis(self, target_version: int) -> ImpactReport:
        """分析回滚影响"""
        current = self.get_current()
        target = Schema.from_json(
            self.storage.get_version(target_version).schema_snapshot
        )
        diff = self._compute_diff(target, current)
        return ImpactReport(
            affected_rules=diff.changed_rules,
            affected_entities=diff.changed_concepts,
            risk_level=self._assess_risk(diff)
        )
```

---

## 审计中间件（决策 #7）

平台双模式下的审计路由：

```python
class AuditMiddleware:
    """审计中间件 - 根据部署模式路由审计日志"""
    
    def __init__(self, config: AuditConfig):
        self.config = config
        self.local_writer = DuckDBAuditWriter()
        self.platform_client = PlatformAuditClient(config.platform_endpoint) if config.mode == "platform" else None
    
    async def record(self, entry: AuditEntry) -> None:
        if self.config.mode == "local":
            await self.local_writer.write(entry)
        elif self.config.mode == "platform":
            try:
                await self.platform_client.send(entry)
            except PlatformUnavailable:
                # 降级到本地存储
                await self.local_writer.write(entry)
                logger.warning("Platform unavailable, audit written locally")
```

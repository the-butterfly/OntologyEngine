# 存储设计

> **Primary**: DuckDB + Faiss
> **Future**: Neo4j + pgvector

## 架构

### 分层视图

```
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

### 本地存储架构

```
┌─────────────────────────────────────────┐
│  Storage Interface (storage/base.py)    │
├─────────────────────────────────────────┤
│  ┌─────────────┐    ┌────────────────┐ │
│  │ DuckDBStore │    │ FaissVectorStore│ │
│  │ (主存储)     │    │ (向量索引)      │ │
│  └─────────────┘    └────────────────┘ │
├─────────────────────────────────────────┤
│  NetworkXGraph (按需加载，内存)          │
└─────────────────────────────────────────┘
```

---

## DuckDB 设计

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

#### edges - 关系表
```sql
CREATE TABLE edges (
    id VARCHAR PRIMARY KEY,
    from_id VARCHAR NOT NULL REFERENCES entities(id),
    to_id VARCHAR NOT NULL REFERENCES entities(id),
    relation_type VARCHAR NOT NULL,
    attributes JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_edges_from ON edges(from_id);
CREATE INDEX idx_edges_to ON edges(to_id);
CREATE INDEX idx_edges_type ON edges(relation_type);
```

#### instances - 实例数据 (JSON 存储)
```sql
CREATE TABLE instances (
    id VARCHAR PRIMARY KEY,
    schema_id VARCHAR NOT NULL,
    entity_data JSON,
    computed_metrics JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### audit_log - 审计日志（决策 #7）
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

## Faiss 向量存储

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

## 存储接口

```python
# storage/base.py

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

## NetworkX 按需加载

```python
class NetworkXGraph:
    """内存图，用于图算法"""

    def load_from_duckdb(
        self,
        center_id: str,
        depth: int = 2,
        relation_types: list[str] | None = None
    ) -> nx.DiGraph:
        """从 DuckDB 加载子图到内存"""
        # 1. BFS 查询节点和边
        # 2. 构建 NetworkX DiGraph
        # 3. 返回图对象

    def find_path(
        self,
        source: str,
        target: str,
        max_depth: int = 5
    ) -> list[str] | None:
        """最短路径"""

    def calculate_centrality(
        self,
        node_id: str,
        method: str = "betweenness"
    ) -> float:
        """中心性计算"""
```

---

## 性能优化

| 优化点 | 方案 |
|--------|------|
| 属性过滤 | DuckDB JSON 索引 + 物化视图 |
| 关系查询 | from_id/to_id 复合索引 |
| 向量检索 | Faiss IVF 索引 (数据量>10万) |
| 图算法 | 子图加载 + NetworkX 缓存 |
| 热数据 | diskcache LRU |

---

## 存储策略对比

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
    type: duckdb  # duckdb | neo4j
    neo4j:
      uri: bolt://localhost:7687
      user: neo4j
      password: ${NEO4J_PASSWORD}

  vector:
    type: faiss  # faiss | pgvector
    pgvector:
      dsn: postgresql://...

# 本地模式审计配置
audit:
  mode: local               # local: 写本地 DuckDB | platform: 通过中间件转发
  platform_endpoint: null   # 平台审计服务端点（仅 platform 模式）
```

### 工厂模式

```python
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
```

### 数据迁移

```python
# DuckDB 支持直接导出为 Parquet
async def export_to_parquet(duckdb_store: DuckDBStorage, output_dir: str):
    await asyncio.to_thread(
        duckdb_store._conn.execute,
        f"COPY entities TO '{output_dir}/entities.parquet' (FORMAT PARQUET)"
    )
```

实现新的 Store 只需继承 `GraphStore` 或 `VectorStore` 接口。

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

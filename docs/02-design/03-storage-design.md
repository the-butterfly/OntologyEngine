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

```yaml
# config.yaml
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

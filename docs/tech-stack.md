# 技术选型 (Python)

## 核心原则

**本地优先**: 零外部依赖，单机可运行  
**预留接口**: Neo4j/PostgreSQL 仅保留适配层接口  
**渐进扩展**: 后期可无缝切换到生产级存储

## 存储策略

| 数据类型 | 本地实现 | 预留接口 | 说明 |
|----------|----------|----------|------|
| 主存储 | DuckDB | - | OLAP 存储，实体/关系/指标 |
| 图算法 | NetworkX (按需加载) | - | 担保链检测、路径查询 |
| 向量 | faiss-cpu / annoy | pgvector | 本地向量索引 |
| 缓存 | 内存 dict + diskcache | Redis | LRU + 持久化 |
| 配置/日志 | 本地文件 | - | YAML/JSON |

## 核心依赖

```toml
[project]
dependencies = [
    # Web 框架
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    
    # 数据验证
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    
    # 本地存储
    "duckdb>=0.9.0",              # 主存储 (OLAP)
    "diskcache>=5.6",             # 本地缓存
    
    # 向量检索 (本地)
    "faiss-cpu>=1.7",             # 或 "annoy>=1.17"
    "numpy>=1.26",
    
    # 图算法 (内存)
    "networkx>=3.0",
    
    # 数据处理
    "pyyaml>=6.0",
    "pandas>=2.0",
    
    # 工具
    "httpx>=0.27",
    "structlog>=24.0",
    "typer>=0.12",
    
    # 预留驱动 (可选安装)
    # "neo4j>=5.0",               # 生产环境启用
    # "psycopg[binary]>=3.0",     # 生产环境启用
    # "redis>=5.0",               # 生产环境启用
]

[project.optional-dependencies]
ai = [
    "openai>=1.0",
    "sentence-transformers>=2.5",  # 本地 Embedding
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "black>=24.0",
    "ruff>=0.3",
    "mypy>=1.0",
]
```

## 本地存储架构

```
┌─────────────────────────────────────────────────────────┐
│                    Storage Layer                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ DuckDBStore │  │ VectorStore │  │  MetaStore  │     │
│  │  (主存储)    │  │  (抽象接口)  │  │  (抽象接口)  │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
└─────────┼────────────────┼────────────────┼────────────┘
          │                │                │
    ┌─────┴─────┐    ┌─────┴─────┐    ┌─────┴─────┐
    │   DuckDB  │    │  faiss    │    │   DuckDB  │  ← 本地实现
    │           │    │  /annoy   │    │  (元数据)  │
    └─────┬─────┘    └───────────┘    └───────────┘
          │
    ┌─────┴─────┐
    │  NetworkX │  ← 按需加载（图算法）
    │ (内存图)  │
    └───────────┘
```

## 存储实现细节

### 1. 主存储 (DuckDB)

```python
class DuckDBStorage(StorageBackend):
    """DuckDB 主存储实现"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = None

    async def initialize(self) -> None:
        self._conn = duckdb.connect(self.db_path)
        # 创建实体表
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS entities (
                concept VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                data JSON NOT NULL,
                PRIMARY KEY (concept, entity_id)
            )
        """)
        # 创建关系表
        await asyncio.to_thread(self._conn.execute, """
            CREATE TABLE IF NOT EXISTS relations (
                relation_type VARCHAR NOT NULL,
                from_entity_id VARCHAR NOT NULL,
                to_entity_id VARCHAR NOT NULL,
                data JSON,
                PRIMARY KEY (relation_type, from_entity_id, to_entity_id)
            )
        """)
```

**DuckDB Schema**:
```sql
-- 实体表 (概念 + JSON 数据)
CREATE TABLE entities (
    concept VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (concept, entity_id)
);

-- 关系表
CREATE TABLE relations (
    relation_type VARCHAR NOT NULL,
    from_entity_id VARCHAR NOT NULL,
    to_entity_id VARCHAR NOT NULL,
    data JSON,
    PRIMARY KEY (relation_type, from_entity_id, to_entity_id)
);

-- 索引
CREATE INDEX idx_entities_concept ON entities(concept);
CREATE INDEX idx_relations_from ON relations(from_entity_id);
```

**注意**: DuckDB 使用 `asyncio.to_thread()` 包装同步操作，避免阻塞事件循环。

### 2. 向量存储 (faiss-cpu)

```python
class FaissVectorStore(VectorStore):
    """本地 Faiss 向量存储"""
    
    def __init__(self, index_path: str = "data/vectors"):
        self.dimension = 1536  # 默认 Embedding 维度
        self.index = faiss.IndexFlatIP(self.dimension)  # 内积相似度
        self.metadata = {}  # id -> metadata 映射
        self.index_path = index_path
    
    async def insert(self, id: str, vector: list[float], metadata: dict):
        # 添加到 Faiss 索引
        # 保存 metadata
        pass
    
    async def search(self, query: list[float], top_k: int = 10):
        # Faiss 相似度搜索
        pass
    
    def persist(self):
        # 保存索引到本地文件
        faiss.write_index(self.index, f"{self.index_path}/index.faiss")
```

### 3. 元数据存储 (DuckDB)

```python
class DuckDBMetaStore(MetaStore):
    """Schema、配置、审计日志存储 (复用 DuckDB)"""

    def __init__(self, db_path: str = "data/meta.db"):
        self.db_path = db_path
        self._conn = None
```

### 4. 缓存 (diskcache)

```python
from diskcache import Cache

cache = Cache("data/cache")  # 本地文件缓存

@cache.memoize(expire=3600)
def expensive_compute(x):
    return x * x
```

## 数据目录结构

```
data/                          # 本地数据目录
├── ontology.db                # DuckDB 主数据库 (实体、关系、指标)
├── vectors/                   # 向量索引
│   ├── index.faiss           # Faiss 索引文件
│   └── metadata.json         # 向量元数据
├── cache/                     # diskcache 目录
├── logs/                      # 本地日志
└── snapshots/                 # 数据快照/备份
```

**注意**: 使用单个 DuckDB 数据库替代原有的 graph.db + meta.db 分离存储。

## 预留接口

### Neo4j 适配器（预留）

```python
class Neo4jGraphStore(GraphStore):
    """Neo4j 实现，生产环境启用"""
    
    def __init__(self, uri: str, user: str, password: str):
        # from neo4j import GraphDatabase
        # self.driver = GraphDatabase.driver(uri, auth=(user, password))
        raise NotImplementedError("Neo4j 适配器需安装 neo4j 驱动")
```

### PostgreSQL 适配器（预留）

```python
class PostgresVectorStore(VectorStore):
    """pgvector 实现，生产环境启用"""
    
    def __init__(self, dsn: str):
        # import asyncpg
        # self.pool = await asyncpg.create_pool(dsn)
        raise NotImplementedError("PostgreSQL 适配器需安装 asyncpg")
```

## 配置切换

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

## 优缺点分析

| 方面 | 本地存储 | 外部数据库 |
|------|----------|------------|
| **部署** | 零依赖，一键启动 | 需要额外部署 |
| **性能** | 单节点优秀 | 可水平扩展 |
| **容量** | 受单机限制 | 可扩展 |
| **并发** | 适合低频写入 | 高并发优化 |
| **场景** | 开发、演示、小规模 | 生产、大规模 |

## 迁移路径

```
Phase 1: 本地 DuckDB + faiss-cpu
    ↓ 数据导出/导入
Phase 2: DuckDB (持久化) + pgvector (生产环境)
```

**数据迁移**:
```python
# DuckDB 支持直接导出为 Parquet
async def export_to_parquet(duckdb_store: DuckDBStorage, output_dir: str):
    await asyncio.to_thread(
        duckdb_store._conn.execute,
        f"COPY entities TO '{output_dir}/entities.parquet' (FORMAT PARQUET)"
    )
```

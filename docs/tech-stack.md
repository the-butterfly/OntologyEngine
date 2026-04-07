# 技术选型 (Python)

## 核心原则

**本地优先**: 零外部依赖，单机可运行  
**预留接口**: Neo4j/PostgreSQL 仅保留适配层接口  
**渐进扩展**: 后期可无缝切换到生产级存储

## 存储策略

| 数据类型 | 本地实现 | 预留接口 | 说明 |
|----------|----------|----------|------|
| 图数据 | SQLite + 自定义 | Neo4j | 节点/边存 SQLite，内存缓存 |
| 向量 | faiss-cpu / annoy | pgvector | 本地向量索引 |
| 元数据/Schema | SQLite | PostgreSQL | 单文件数据库 |
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
    "sqlite3",                    # 内置，图+元数据
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
│  │ GraphStore  │  │ VectorStore │  │  MetaStore  │     │
│  │  (抽象接口)  │  │  (抽象接口)  │  │  (抽象接口)  │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
└─────────┼────────────────┼────────────────┼────────────┘
          │                │                │
    ┌─────┴─────┐    ┌─────┴─────┐    ┌─────┴─────┐
    │  SQLite   │    │  faiss    │    │  SQLite   │  ← 本地实现
    │  + NetworkX│    │  /annoy   │    │           │
    └─────┬─────┘    └───────────┘    └───────────┘
          │
    ┌─────┴─────┐
    │   Neo4j   │  ← 预留接口（可选）
    │  (远程)   │
    └───────────┘
```

## 存储实现细节

### 1. 图存储 (SQLite + NetworkX)

```python
# 本地实现
class SQLiteGraphStore(GraphStore):
    """SQLite + 内存缓存实现"""
    
    def __init__(self, db_path: str = "data/graph.db"):
        self.conn = sqlite3.connect(db_path)
        self.cache = {}  # 内存缓存热数据
        self.nx_graph = nx.DiGraph()  # 内存图算法
    
    async def create_node(self, node: Node) -> NodeId:
        # 1. 写入 SQLite
        # 2. 更新内存缓存
        # 3. 更新 NetworkX
        pass
```

**SQLite Schema**:
```sql
-- 节点表
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    concept_type TEXT NOT NULL,
    properties JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 边表
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    target_id TEXT,
    relation_type TEXT,
    properties JSON,
    created_at TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id)
);

-- 索引
CREATE INDEX idx_nodes_type ON nodes(concept_type);
CREATE INDEX idx_edges_relation ON edges(relation_type);
CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
```

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

### 3. 元数据存储 (SQLite)

```python
class SQLiteMetaStore(MetaStore):
    """Schema、配置、审计日志存储"""
    
    def __init__(self, db_path: str = "data/meta.db"):
        self.conn = sqlite3.connect(db_path)
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
├── graph.db                   # SQLite 图数据库
├── meta.db                    # SQLite 元数据库
├── vectors/                   # 向量索引
│   ├── index.faiss           # Faiss 索引文件
│   └── metadata.json         # 向量元数据
├── cache/                     # diskcache 目录
├── logs/                      # 本地日志
└── snapshots/                 # 数据快照/备份
```

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
Phase 1: 本地 SQLite + faiss-cpu
    ↓ 数据导出/导入
Phase 2: Neo4j + pgvector (生产环境)
```

**数据迁移**:
```python
# 从 SQLite 导出到 Neo4j
async def migrate_to_neo4j(sqlite_store: SQLiteGraphStore, neo4j_store: Neo4jGraphStore):
    nodes = await sqlite_store.get_all_nodes()
    for node in nodes:
        await neo4j_store.create_node(node)
```

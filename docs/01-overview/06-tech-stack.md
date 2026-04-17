# 技术选型

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-17
> **[待核对代码]**: 依赖版本和实际 pyproject.toml 仍需核验

## 核心原则

**本地优先**: 零外部依赖，单机可运行  
**预留接口**: Neo4j/PostgreSQL 仅保留适配层接口  
**渐进扩展**: 后期可无缝切换到生产级存储  
**三层资产统一存储**: IT 资产、个人知识沉淀、组织级资产共用同一存储基础设施

## 存储策略

| 数据类型 | 本地实现 | 预留接口 | 承载资产 | 说明 |
|----------|----------|----------|----------|------|
| 主存储 | DuckDB | - | IT + 组织 | OLAP 存储，实体/关系/指标/审计 |
| 图算法 | NetworkX (按需加载) | Neo4j | 三层链接 | 担保链检测、路径查询、影响分析 |
| 向量 | faiss-cpu | pgvector | IT (语义) | 本地向量索引，混合检索 |
| 缓存 | 内存 dict + diskcache | Redis | 运行时 | LRU + 持久化 |
| 配置/日志 | 本地文件 | - | 组织 | YAML/JSON |

### 三层资产存储映射

```
┌──────────────────────────────────────────────────────────┐
│  存储层统一承载三层知识资产                                 │
│                                                           │
│  DuckDB (主存储)                                          │
│  ├─ IT 资产: entities, relations, datasets                │
│  ├─ 组织资产: schemas, rule_definitions, rule_logics       │
│  └─ 链接元数据: execution_snapshots, change_batches       │
│                                                           │
│  NetworkX (图算法)                                        │
│  ├─ 三层资产链接图: IT数据 ← 专家规则 → 组织策略            │
│  └─ 影响链: BFS 下游追踪                                  │
│                                                           │
│  Faiss (向量索引)                                         │
│  ├─ IT 资产语义索引: 实体/关系 embedding                   │
│  └─ 组织资产语义索引: 规则/指标 embedding                   │
└──────────────────────────────────────────────────────────┘
```

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
│  │ DuckDBStore │  │ VectorStore │  │  GraphStore │     │
│  │  (主存储)    │  │  (抽象接口)  │  │  (抽象接口)  │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
└─────────┼────────────────┼────────────────┼────────────┘
          │                │                │
    ┌─────┴─────┐    ┌─────┴─────┐    ┌─────┴─────┐
    │   DuckDB  │    │  faiss    │    │ NetworkX  │  ← 本地实现
    │           │    │  /annoy   │    │ (按需加载) │
    └─────┬─────┘    └───────────┘    └───────────┘
          │
    ┌─────┴─────┐
    │  DualWrite │  ← 图+关系双写协调
    │ Coordinator│
    └───────────┘
```

## 上下文栈集成架构

OntologyEngine 在上下文栈中的位置决定了其存储设计：

```
┌─────────────────────────────────────────────────────────┐
│  Agent 上下文栈查询时的四阶段集成流程                      │
│                                                          │
│  ① RAG 层: 向量搜索 → 识别最相关文档和实体入口点          │
│     └─ OntologyEngine: FaissVectorStore                  │
│                                                          │
│  ② KG 层: 图遍历 → 从入口点沿关系边收集连接上下文         │
│     └─ OntologyEngine: NetworkXGraphStore + DuckDB       │
│                                                          │
│  ③ Memory 层: 记忆检索 → 注入会话和用户上下文             │
│     └─ 外部 Agent 框架提供                                │
│                                                          │
│  ④ LLM 推理: 在完整上下文窗口上运行                       │
│     └─ 文档 + 关系 + 连续性 → 结构化推理结果              │
└─────────────────────────────────────────────────────────┘
```

## 预留接口

### Neo4j 适配器（预留）

```python
class Neo4jGraphStore(GraphStoreBackend):
    """Neo4j 实现，生产环境启用"""
    
    def __init__(self, uri: str, user: str, password: str):
        raise NotImplementedError("Neo4j 适配器需安装 neo4j 驱动")
```

### PostgreSQL 适配器（预留）

```python
class PostgresVectorStore(VectorStore):
    """pgvector 实现，生产环境启用"""
    
    def __init__(self, dsn: str):
        raise NotImplementedError("PostgreSQL 适配器需安装 asyncpg")
```

## 配置切换

```python
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
| **三层资产** | 单机完整链接 | 分布式资产链接 |

## 迁移路径

```
Phase 1: 本地 DuckDB + NetworkX + faiss-cpu
    ↓ 数据导出/导入
Phase 2: DuckDB (持久化) + kuzu (图数据库) + pgvector (可选)
    ↓ 分布式扩展
Phase 3: 可选 Neo4j (图) + pgvector (向量) + DuckDB 保持默认
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

## 数据目录结构

```
data/                          # 本地数据目录
├── ontology.db                # DuckDB 主数据库 (实体、关系、指标、规则)
├── vectors/                   # Faiss 索引
│   ├── index.faiss           # Faiss 索引文件
│   └── metadata.json         # 向量元数据
├── cache/                     # diskcache 目录
├── logs/                      # 本地日志
└── snapshots/                 # 数据快照/备份
```

---

*参考：[AI Memory vs RAG vs Knowledge Graph (Atlan 2026)](https://atlan.com/know/ai-memory-vs-rag-vs-knowledge-graph/) | [Knowledge Graph Best Practices (Meegle 2026)](https://www.meegle.com/en_us/topics/knowledge-graphs/knowledge-graph-best-practices)*

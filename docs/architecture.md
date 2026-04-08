# 架构概览

## 系统分层

```
┌────────────────────────────────────────┐
│  L3: 应用层 (Agent/业务系统)            │
├────────────────────────────────────────┤
│  L2: 服务层 (FastAPI/gRPC)              │
├────────────────────────────────────────┤
│  L1: 引擎层                             │
│   ├─ QueryEngine: 图查询/向量检索        │
│   ├─ RuleEngine: 规则解析/执行          │
│   ├─ InferenceEngine: 符号+LLM推理      │
│   └─ VectorEngine: Embedding/索引       │
├────────────────────────────────────────┤
│  L0: 存储层 (本地优先)                   │
│   ├─ DuckDBStorage: 主存储 (DuckDB)
│   ├─ FaissVectorStore: 向量存储 (faiss-cpu)
│   ├─ NetworkXGraph: 图算法 (按需加载)
│   └─ DiskCache: 本地缓存 (diskcache)
│
│  预留接口: Neo4jGraphStore / PGVectorStore / RedisCache
└────────────────────────────────────────┘
```

## 核心组件

| 组件 | 本地实现 | 预留接口 | 说明 |
|------|----------|----------|------|
| Storage | DuckDB | - | 主存储 (实体/关系/指标) |
| GraphAlgo | NetworkX (按需) | - | 担保链/路径算法 |
| VectorStore | faiss-cpu / annoy | pgvector | 向量索引/相似度 |
| MetaStore | DuckDB | PostgreSQL | Schema/配置 |
| Cache | diskcache | Redis | LRU + 持久化 |

## 本地存储架构

```
┌─────────────────────────────────────────────────────────┐
│                      Storage Layer                      │
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

## 数据目录

```
data/
├── ontology.db        # DuckDB 主数据库
├── vectors/
│   ├── index.faiss   # Faiss 向量索引
│   └── metadata.json # 向量元数据
└── cache/            # 本地缓存文件
```

## 数据流转

```
KGML/CSV/JSON ──▶ Ingestion ──▶ Schema校验 ──▶ DuckDB ──▶ 事件触发
                                                (ontology.db)  │
                                                              ▼
                                    ┌──────────────────────────────────┐
                                    │ RuleEngine: DAG解析 ──▶ 算子执行  │
                                    └──────────────────────────────────┘
                                                              │
Agent查询 ──▶ QueryEngine ──▶ DuckDB查询/NetworkX算法 ──▶ 结果返回
```

## 非功能性需求

- **部署**: 零外部依赖，`pip install` 即可运行
- **存储**: 单机支持百万级节点，GB 级数据
- **查询**: P99 < 200ms (本地存储)
- **切换**: 配置一键切换到 Neo4j/pgvector

## 预留扩展

```python
# 本地模式 (默认)
STORAGE_TYPE=local
VECTOR_STORE_TYPE=local

# 生产模式 (未来切换)
STORAGE_TYPE=duckdb  # 持久化 DuckDB
NEO4J_URI=bolt://localhost:7687
VECTOR_STORE_TYPE=pgvector
POSTGRES_DSN=postgresql://...
```

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
│   ├─ SQLiteGraphStore: 图存储 (SQLite+NetworkX)
│   ├─ FaissVectorStore: 向量存储 (faiss-cpu)
│   ├─ SQLiteMetaStore: 元数据 (SQLite)
│   └─ DiskCache: 本地缓存 (diskcache)
│
│  预留接口: Neo4jGraphStore / PGVectorStore / RedisCache
└────────────────────────────────────────┘
```

## 核心组件

| 组件 | 本地实现 | 预留接口 | 说明 |
|------|----------|----------|------|
| GraphStore | SQLite + NetworkX | Neo4j | 节点/边/图算法 |
| VectorStore | faiss-cpu / annoy | pgvector | 向量索引/相似度 |
| MetaStore | SQLite | PostgreSQL | Schema/配置 |
| Cache | diskcache | Redis | LRU + 持久化 |

## 本地存储架构

```
┌─────────────────────────────────────────────────────────┐
│                      Storage Layer                      │
├─────────────────────────────────────────────────────────┤
│  GraphStore ──▶ SQLite (graph.db)                       │
│              └─▶ Memory (NetworkX 图算法)               │
├─────────────────────────────────────────────────────────┤
│  VectorStore ──▶ Faiss (data/vectors/index.faiss)       │
│               └─▶ Metadata (JSON)                       │
├─────────────────────────────────────────────────────────┤
│  MetaStore ──▶ SQLite (meta.db)                         │
├─────────────────────────────────────────────────────────┤
│  Cache ──▶ diskcache (data/cache/)                      │
└─────────────────────────────────────────────────────────┘
```

## 数据目录

```
data/
├── graph.db          # SQLite 图数据库
├── meta.db           # SQLite 元数据库  
├── vectors/
│   ├── index.faiss   # Faiss 向量索引
│   └── metadata.json # 向量元数据
└── cache/            # 本地缓存文件
```

## 数据流转

```
KGML/CSV/JSON ──▶ Ingestion ──▶ Schema校验 ──▶ SQLite ──▶ 事件触发
                                              (graph.db)      │
                                                              ▼
                                    ┌──────────────────────────────────┐
                                    │ RuleEngine: DAG解析 ──▶ 算子执行  │
                                    └──────────────────────────────────┘
                                                              │
Agent查询 ──▶ QueryEngine ──▶ NetworkX查询/Faiss检索 ──▶ 结果返回
```

## 非功能性需求

- **部署**: 零外部依赖，`pip install` 即可运行
- **存储**: 单机支持百万级节点，GB 级数据
- **查询**: P99 < 200ms (本地存储)
- **切换**: 配置一键切换到 Neo4j/pgvector

## 预留扩展

```python
# 本地模式 (默认)
GRAPH_STORE_TYPE=local
VECTOR_STORE_TYPE=local

# 生产模式 (未来切换)
GRAPH_STORE_TYPE=neo4j
NEO4J_URI=bolt://localhost:7687
VECTOR_STORE_TYPE=pgvector
POSTGRES_DSN=postgresql://...
```

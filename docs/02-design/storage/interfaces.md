# 存储接口升级规范

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/02-design/storage/README.md` | **last_verified**: 2026-04-19

---

## 目的

定义 OntologyEngine 存储层从单一 StorageBackend 接口升级为 GraphStore + VectorStore + MetaStore 三接口的规范，明确接口方法签名、异步策略、工厂模式和配置模型。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 当前 StorageBackend 接口混合了图操作、向量操作和元数据操作 | 职责耦合，无法独立替换和测试 |
| 2 | 接口方法同步阻塞 | I/O 操作阻塞事件循环，无法支撑高并发 |
| 3 | 缺乏工厂模式 | 上层服务直接依赖具体实现，违反依赖倒置 |
| 4 | 缺乏批量操作接口 | 逐条写入性能差，无法支撑大规模数据导入 |
| 5 | 缺乏时序和溯源查询接口 | Schema v2 Instance 层的时序和溯源需求无法满足 |

---

## 与基线的偏差

| 维度 | 基线（StorageBackend） | 目标（三接口） |
|------|----------------------|--------------|
| 接口数量 | 1 | 3（GraphStore + VectorStore + MetaStore） |
| 异步 | 否 | 是（全部 async） |
| 批量操作 | 无 | batch_create / batch_update |
| 图遍历 | 无 | get_neighborhood / query_cypher |
| 向量检索 | search（内存） | search（ChromaDB 持久化） |
| 时序查询 | 无 | get_entity_at / get_edge_at |
| 溯源查询 | 无 | get_by_source_pipeline |
| 互索引边 | 无 | create_mutual_index_edge / get_mutual_index_edges |
| Schema 版本 | 无 | commit_version / rollback |

---

## GraphStore 接口

### 目的

封装图数据库操作，提供 Cypher 查询、邻域遍历、批量写入和互索引边管理能力。

### 接口定义

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class NodeRecord:
    id: str
    labels: list[str]
    attributes: dict

@dataclass
class EdgeRecord:
    id: str
    type: str
    from_id: str
    to_id: str
    attributes: dict

@dataclass
class PathRecord:
    nodes: list[NodeRecord]
    edges: list[EdgeRecord]

@dataclass
class SubGraph:
    nodes: list[NodeRecord]
    edges: list[EdgeRecord]

class GraphStore(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def query_cypher(
        self,
        query: str,
        parameters: dict | None = None,
    ) -> list[dict]: ...

    @abstractmethod
    async def get_node(
        self,
        label: str,
        id: str,
    ) -> NodeRecord | None: ...

    @abstractmethod
    async def create_node(
        self,
        label: str,
        attributes: dict,
    ) -> NodeRecord: ...

    @abstractmethod
    async def update_node(
        self,
        label: str,
        id: str,
        attributes: dict,
    ) -> NodeRecord: ...

    @abstractmethod
    async def delete_node(
        self,
        label: str,
        id: str,
    ) -> bool: ...

    @abstractmethod
    async def batch_create_nodes(
        self,
        label: str,
        records: list[dict],
    ) -> list[NodeRecord]: ...

    @abstractmethod
    async def create_edge(
        self,
        rel_type: str,
        from_id: str,
        to_id: str,
        attributes: dict,
    ) -> EdgeRecord: ...

    @abstractmethod
    async def batch_create_edges(
        self,
        rel_type: str,
        records: list[dict],
    ) -> list[EdgeRecord]: ...

    @abstractmethod
    async def get_neighborhood(
        self,
        node_id: str,
        depth: int = 1,
        limit: int = 100,
        min_confidence: float = 0.0,
    ) -> SubGraph: ...

    @abstractmethod
    async def get_entity_at(
        self,
        fact_object: str,
        as_of: datetime,
        domain_id: str | None = None,
    ) -> list[NodeRecord]: ...

    @abstractmethod
    async def get_edge_at(
        self,
        relation_name: str,
        as_of: datetime,
        min_confidence: float = 0.0,
    ) -> list[EdgeRecord]: ...

    @abstractmethod
    async def get_by_source_pipeline(
        self,
        source_pipeline: str,
        label: str | None = None,
    ) -> list[NodeRecord]: ...

    @abstractmethod
    async def create_mutual_index_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        attributes: dict,
    ) -> EdgeRecord: ...

    @abstractmethod
    async def get_mutual_index_edges(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "both",
    ) -> list[EdgeRecord]: ...

    @abstractmethod
    async def update_feedback_weight(
        self,
        entity_id: str,
        feedback: float,
        learning_rate: float = 0.1,
    ) -> None: ...
```

### 方法说明

| 方法 | 用途 | 对齐参考 |
|------|------|---------|
| `query_cypher` | 执行任意 Cypher 查询 | Cognee KuzuAdapter.execute_query |
| `get_neighborhood` | 获取节点邻域子图 | m_flow GraphProvider.get_neighborhood |
| `batch_create_nodes` | UNWIND+MERGE 批量创建节点 | Cognee KuzuAdapter.add_nodes |
| `batch_create_edges` | UNWIND+MERGE + 端点分区批量创建边 | m_flow _partition_edges_by_endpoints |
| `get_entity_at` | 时序切片查询 | Schema v2 Instance 层 |
| `get_edge_at` | 时序切片查询 | Schema v2 Instance 层 |
| `get_by_source_pipeline` | 溯源查询 | Cognee DataPoint.source_pipeline |
| `create_mutual_index_edge` | 创建互索引边 | Schema v2 互索引边 |
| `update_feedback_weight` | 反馈权重更新 | Cognee apply_feedback_weights |

---

## VectorStore 接口

### 目的

封装向量数据库操作，提供集合管理、向量写入、语义检索和 metadata 过滤能力。

### 接口定义

```python
@dataclass
class VectorSearchResult:
    id: str
    document: str
    metadata: dict
    distance: float

@dataclass
class VectorQueryResult:
    ids: list[list[str]]
    documents: list[list[str]]
    metadatas: list[list[dict]]
    distances: list[list[float]]

class VectorStore(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        metadata: dict | None = None,
    ) -> None: ...

    @abstractmethod
    async def delete_collection(self, name: str) -> None: ...

    @abstractmethod
    async def list_collections(self) -> list[str]: ...

    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> VectorQueryResult: ...

    @abstractmethod
    async def delete(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict | None = None,
    ) -> None: ...

    @abstractmethod
    async def get(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict | None = None,
        limit: int | None = None,
    ) -> VectorQueryResult: ...

    @abstractmethod
    async def count(self, collection_name: str) -> int: ...

    @abstractmethod
    async def multi_collection_search(
        self,
        collection_names: list[str],
        query_embedding: list[float],
        n_results_per_collection: int = 10,
        where: dict | None = None,
    ) -> dict[str, VectorQueryResult]: ...
```

### 方法说明

| 方法 | 用途 | 对齐参考 |
|------|------|---------|
| `upsert` | 向量写入/更新 | ChromaDB collection.upsert |
| `search` | 语义检索 + metadata 过滤 | ChromaDB collection.query |
| `multi_collection_search` | 多集合并行检索 | m_flow VectorProvider 多集合设计 |
| `delete` | 按 ID 或条件删除 | ChromaDB collection.delete |
| `get` | 按 ID 或条件获取 | ChromaDB collection.get |

---

## MetaStore 接口

### 目的

封装元数据操作，提供 Schema 版本管理、审计日志、管道状态、文件哈希和矛盾报告管理能力。

### 接口定义

```python
@dataclass
class SchemaVersion:
    version: int
    description: str
    migration_up: str
    migration_down: str
    checksum: str
    applied_at: str
    applied_by: str | None

@dataclass
class AuditEntry:
    id: int
    timestamp: str
    operation: str
    target_type: str
    target_id: str
    actor: str | None
    details: dict | None

@dataclass
class PipelineRun:
    id: str
    pipeline: str
    status: str
    started_at: str
    finished_at: str | None
    input_hash: str | None
    output_count: int
    error_message: str | None
    metadata: dict | None

@dataclass
class FileHash:
    file_path: str
    content_hash: str
    file_size: int
    modified_at: str
    processed_at: str | None
    pipeline: str | None

@dataclass
class ContradictionReport:
    id: int
    entity_id: str
    contradiction_type: str
    field_name: str
    existing_value: str
    new_value: str
    severity: str
    status: str

class MetaStore(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def current_schema_version(self) -> int: ...

    @abstractmethod
    async def commit_version(
        self,
        description: str,
        migration_up: str,
        migration_down: str,
    ) -> int: ...

    @abstractmethod
    async def rollback_version(self, target_version: int) -> None: ...

    @abstractmethod
    async def diff_versions(
        self,
        from_version: int,
        to_version: int,
    ) -> list[SchemaVersion]: ...

    @abstractmethod
    async def impact_analysis(self, target_version: int) -> dict: ...

    @abstractmethod
    async def write_audit_log(
        self,
        operation: str,
        target_type: str,
        target_id: str,
        actor: str | None = None,
        details: dict | None = None,
        before_snapshot: dict | None = None,
        after_snapshot: dict | None = None,
    ) -> int: ...

    @abstractmethod
    async def get_audit_log(
        self,
        target_type: str | None = None,
        target_id: str | None = None,
        operation: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]: ...

    @abstractmethod
    async def start_pipeline_run(
        self,
        pipeline: str,
        input_hash: str | None = None,
        metadata: dict | None = None,
    ) -> str: ...

    @abstractmethod
    async def finish_pipeline_run(
        self,
        run_id: str,
        status: str,
        output_count: int = 0,
        error_message: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_file_hash(self, file_path: str) -> FileHash | None: ...

    @abstractmethod
    async def upsert_file_hash(
        self,
        file_path: str,
        content_hash: str,
        file_size: int,
        modified_at: str,
        pipeline: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def create_contradiction_report(
        self,
        entity_id: str,
        contradiction_type: str,
        field_name: str,
        existing_value: str,
        new_value: str,
        existing_source: str | None = None,
        new_source: str | None = None,
        severity: str = "warning",
    ) -> int: ...

    @abstractmethod
    async def resolve_contradiction(
        self,
        report_id: int,
        resolution: str,
        resolved_by: str,
    ) -> None: ...

    @abstractmethod
    async def get_contradiction_reports(
        self,
        entity_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[ContradictionReport]: ...

    @abstractmethod
    async def create_dataset(
        self,
        name: str,
        source_type: str,
        source_uri: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> str: ...

    @abstractmethod
    async def get_dataset(self, dataset_id: str) -> dict | None: ...

    @abstractmethod
    async def update_dataset_counts(
        self,
        dataset_id: str,
        document_count: int | None = None,
        fragment_count: int | None = None,
    ) -> None: ...
```

---

## StorageConfig 配置模型

### 目的

统一存储层配置，支持本地/云端模式切换和各引擎独立配置。

### 定义

```python
from pathlib import Path
from pydantic_settings import BaseSettings

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

    openai_api_key: str | None = None

    learning_rate: float = 0.1
    semantic_weight: float = 0.7

    model_config = {"env_prefix": "OE_STORAGE_"}
```

### 环境变量映射

| 配置项 | 环境变量 | 默认值 |
|--------|---------|--------|
| mode | OE_STORAGE_MODE | local |
| graph_backend | OE_STORAGE_GRAPH_BACKEND | kuzu |
| vector_backend | OE_STORAGE_VECTOR_BACKEND | chroma |
| meta_backend | OE_STORAGE_META_BACKEND | sqlite |
| kuzu_db_path | OE_STORAGE_KUZU_DB_PATH | data/ontology.kuzu |
| chroma_persist_dir | OE_STORAGE_CHROMA_PERSIST_DIR | data/vectors |
| sqlite_db_path | OE_STORAGE_SQLITE_DB_PATH | data/meta.db |
| openai_api_key | OE_STORAGE_OPENAI_API_KEY | None |

---

## 工厂模式

### 目的

通过工厂函数创建存储实例，上层服务仅依赖抽象接口，不依赖具体实现。

### 工厂函数

```python
def create_graph_store(config: StorageConfig) -> GraphStore:
    if config.graph_backend == "kuzu":
        from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore
        return KuzuGraphStore(config)
    elif config.graph_backend == "neo4j":
        from ontology_engine.storage.graph.neo4j_store import Neo4jGraphStore
        return Neo4jGraphStore(config)
    else:
        raise ValueError(f"Unsupported graph backend: {config.graph_backend}")

def create_vector_store(config: StorageConfig) -> VectorStore:
    if config.vector_backend == "chroma":
        from ontology_engine.storage.vector.chroma_store import ChromaVectorStore
        return ChromaVectorStore(config)
    elif config.vector_backend == "faiss":
        from ontology_engine.storage.vector.faiss_store import FAISSVectorStore
        return FAISSVectorStore(config)
    else:
        raise ValueError(f"Unsupported vector backend: {config.vector_backend}")

def create_meta_store(config: StorageConfig) -> MetaStore:
    if config.meta_backend == "sqlite":
        from ontology_engine.storage.meta.sqlite_store import SQLiteMetaStore
        return SQLiteMetaStore(config)
    elif config.meta_backend == "postgres":
        from ontology_engine.storage.meta.postgres_store import PostgresMetaStore
        return PostgresMetaStore(config)
    else:
        raise ValueError(f"Unsupported meta backend: {config.meta_backend}")
```

### 与参考项目的对齐

| 设计点 | Cognee | m_flow | OntologyEngine |
|--------|--------|--------|----------------|
| 接口抽象 | GraphAdapter 抽象类 | GraphProvider Protocol | GraphStore ABC |
| 工厂模式 | get_graph_engine() | 无 | create_graph_store() |
| 配置模型 | 无 | 无 | StorageConfig (pydantic-settings) |
| 异步策略 | ThreadPoolExecutor | ThreadPoolExecutor | ThreadPoolExecutor |
| 向量接口 | 无独立接口 | VectorProvider Protocol | VectorStore ABC |
| 元数据接口 | 无 | 无 | MetaStore ABC |

---

## 异步策略

### KuzuDB 异步包装

KuzuDB 的 Python SDK 是同步的，通过 ThreadPoolExecutor 包装为异步：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class KuzuGraphStore(GraphStore):
    def __init__(self, config: StorageConfig):
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._conn = None

    async def query_cypher(self, query: str, parameters: dict | None = None) -> list[dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._execute_cypher,
            query,
            parameters,
        )

    def _execute_cypher(self, query: str, parameters: dict | None = None) -> list[dict]:
        result = self._conn.execute(query, parameters or {})
        return [dict(row) for row in result]
```

### ChromaDB 异步包装

ChromaDB 的 Python SDK 也是同步的，同样通过 ThreadPoolExecutor 包装：

```python
class ChromaVectorStore(VectorStore):
    def __init__(self, config: StorageConfig):
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._client = None

    async def search(self, collection_name: str, ...) -> VectorQueryResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._sync_search,
            collection_name,
            ...
        )
```

### SQLite 异步包装

SQLite 使用 aiosqlite 或 ThreadPoolExecutor 包装：

```python
class SQLiteMetaStore(MetaStore):
    def __init__(self, config: StorageConfig):
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._conn = None
```

---

## 目录结构

```
ontology_engine/storage/
├── __init__.py
├── base.py              # GraphStore, VectorStore, MetaStore 抽象类
├── config.py            # StorageConfig
├── factory.py           # create_graph_store, create_vector_store, create_meta_store
├── graph/
│   ├── __init__.py
│   ├── kuzu_store.py    # KuzuGraphStore
│   └── neo4j_store.py   # Neo4jGraphStore (Phase 2)
├── vector/
│   ├── __init__.py
│   ├── chroma_store.py  # ChromaVectorStore
│   └── faiss_store.py   # FAISSVectorStore (Phase 2)
├── meta/
│   ├── __init__.py
│   ├── sqlite_store.py  # SQLiteMetaStore
│   └── schema_version.py # SchemaVersionManager
└── duckdb/              # [已过期] 保留供迁移参考
    ├── __init__.py
    └── store.py
```

---

## 模块边界

```
api/           → services/  (禁止直接调 storage/)
services/      → storage/base.py  (禁止直接调 graph/, vector/, meta/)
storage/base.py → storage/factory.py  (禁止上层直接 import 具体实现)
storage/graph/  → 仅实现 GraphStore 接口
storage/vector/ → 仅实现 VectorStore 接口
storage/meta/   → 仅实现 MetaStore 接口
```

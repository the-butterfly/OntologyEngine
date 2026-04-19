# 模块 03: 存储层

> **位置**: `ontology_engine/storage/`
> **依赖**: DuckDB, 可选 NetworkX
> **被依赖**: 所有引擎层、服务层
> **状态**: 当前实现与目标设计存在偏差，详见 `docs/04-migration-and-gap/README.md`
> **最后核验**: 2026-04-16

## 1. 职责

1. **主存储 (DuckDB)** — 实体、关系、指标、归类标签、规则执行日志
2. **图算法 (NetworkX)** — 内存图操作 (当前为独立内存图，非按需加载)
3. **向量索引** — 当前为 `LocalVectorStore` 内存实现 **[目标设计: Faiss]**
4. **缓存** — 未实现 **[目标设计: LRU+TTL]**

## 2. DuckDB 表设计 (当前实现)

### 2.1 已实现表

| 表名 | 状态 | 说明 |
|------|------|------|
| `entities` | ✅ 已实现 | id, concept_type, attributes |
| `relations` | ✅ 已实现 | id, from_id, to_id, relation_type, attributes |
| `computed_metrics` | ✅ 已实现 | entity_id, metric_name, metric_value |
| `category_tags` | ✅ 已实现 | entity_id, dimension, value, confidence, source |
| `rule_execution_log` | ✅ 已实现 | 规则执行记录 |

### 2.2 未实现表

| 表名 | 状态 | 说明 |
|------|------|------|
| `audit_log` | ❌ 未实现 (2026-04-16) | 审计日志 |
| `schema_versions` | ❌ 未实现 (2026-04-16) | Schema 版本快照 |

### 2.3 Phase 1 增强扩展表

代码中还额外实现了以下表（超出原始设计）：

- `datasets`
- `dimension_applicability`
- `category_rule_mapping`
- `change_batches`
- `entity_versions`
- `rule_groups`
- `rule_steps`

## 3. 存储接口

**代码路径**: `ontology_engine/storage/base.py`

当前抽象接口包括 `StorageBackend`、`VectorStoreBackend`、`GraphAlgorithmBackend`。注意：`begin_transaction` 等方法在 Phase 2 可能移除或内部化。

## 4. NetworkX 图算法

**当前实现状态**: ⚠️ 偏离

- **文档设计**: 从 DuckDB 按需加载子图到 NetworkX，带 LRU 缓存
- **实际实现**: `ontology_engine/storage/` 下为独立内存图存储，节点/边直接存入 NetworkX 内部
- **差异**: 无 `load_subgraph` BFS 加载逻辑，无 TTL 缓存

## 5. 向量存储

**当前实现状态**: ⚠️ 偏离

- **文档设计**: `FaissVectorStore` 基于 faiss 库，支持 `save/load` 持久化
- **实际实现**: `LocalVectorStore` 为内存向量存储，暴力搜索，无持久化

## 6. 缓存策略

**当前实现状态**: ❌ 未实现 (2026-04-16)

- `storage/cache.py` 不存在
- `MetricCache` (LRU+TTL) 未实现

## 7. 文件结构

```
ontology_engine/storage/
├── __init__.py                # create_storage() 工厂
├── base.py                    # StorageBackend, VectorStoreBackend, GraphAlgorithmBackend
├── models.py                  # EntityFilter, PaginatedResult, VectorSearchResult
│
├── duckdb/
│   └── store.py               # DuckDBStorage
│
└── adapters/                  # 预留外部存储适配器
    ├── __init__.py
    ├── neo4j_store.py
    └── pgvector_store.py
```

## 8. 代码映射

| 设计组件 | 实际代码路径 | 实现状态 |
|---------|-------------|---------|
| DuckDBStorage | `storage/duckdb/store.py` | ✅ 已实现 |
| entities 表 | `duckdb/store.py` | ✅ 已实现 |
| relations 表 | `duckdb/store.py` | ✅ 已实现 |
| computed_metrics 表 | `duckdb/store.py` | ✅ 已实现 |
| category_tags 表 | `duckdb/store.py` | ✅ 已实现 |
| rule_execution_log 表 | `duckdb/store.py` | ✅ 已实现 |
| audit_log 表 | - | ❌ 未实现 |
| schema_versions 表 | - | ❌ 未实现 |
| FaissVectorStore | `storage/vector/faiss_store.py` (设计) | ❌ 未实现 |
| LocalVectorStore | `storage/local_vector_store.py` (可能路径) | ⚠️ 部分实现 |
| MetricCache | `storage/cache.py` (设计) | ❌ 未实现 |
| NetworkXGraphStore | `storage/graph/nx_store.py` (设计) | ❌ 未实现 |

## 9. 目标设计与当前实现关系

本文档中 NetworkX 按需加载、`FaissVectorStore`、`MetricCache` 等内容属于 **目标设计**，当前代码采用简化实现。具体差距参见 `docs/04-migration-and-gap/README.md`。

## 10. Repository 接口分离

详见 [`docs/development/storage-repository-pattern.md`](../development/storage-repository-pattern.md)

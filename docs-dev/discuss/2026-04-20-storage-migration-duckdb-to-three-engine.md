# 2026-04-20 Storage Migration: DuckDB → SQLite+KuzuDB+ChromaDB

## 决策摘要

完成从 DuckDB 单引擎存储到 SQLite+KuzuDB+ChromaDB 三引擎存储架构的全面迁移。

## 变更清单

### 新增文件
- `ontology_engine/storage/vector/chroma_store.py` — ChromaDB VectorStore 实现（7集合 + 双嵌入策略）
- `ontology_engine/storage/config.py` — StorageConfig 配置模型 + 工厂函数
- `tests/unit/storage/test_sqlite_storage.py` — SQLiteStorage 基础测试
- `tests/unit/storage/test_sqlite_phase1_crud.py` — SQLiteStorage Phase1 CRUD 测试

### 删除文件
- `ontology_engine/storage/duckdb/__init__.py`
- `ontology_engine/storage/duckdb/store.py`
- `tests/unit/storage/test_duckdb_storage.py`
- `tests/unit/storage/test_duckdb_phase1_crud.py`

### 修改文件
- `ontology_engine/storage/__init__.py` — 更新导出，添加 ChromaVectorStore/StorageConfig/工厂函数
- `ontology_engine/storage/vector/__init__.py` — 添加 ChromaVectorStore 条件导出
- `ontology_engine/storage/dual_write.py` — 重构为三引擎协调（MetaStore+GraphStore+VectorStore）
- `ontology_engine/storage/retrieval.py` — 更新 DuckDB 引用为 MetaStore
- `ontology_engine/storage/graph/kuzu_store.py` — 添加 7 个 Schema v2 扩展方法 + 修复 KuzuDB Cypher 兼容性
- `ontology_engine/storage/base.py` — 更新 docstring
- `ontology_engine/storage/sqlite/store.py` — 修复线程安全问题（check_same_thread=False）
- `ontology_engine/core/instances/loader.py` — 从 duckdb 导入改为 base
- `ontology_engine/engine/categorization/engine.py` — 从 duckdb 导入改为 base
- `ontology_engine/migrations/add_source_declaration_id.py` — duckdb → sqlite3
- `ontology_engine/services/incremental_update.py` — 修复 fact_object/concept 字段兼容性
- `ontology_engine/services/{dataset,query,entity,analysis}_service.py` — 更新 docstring
- `ontology_engine/api/server.py` — 更新日志消息
- `pyproject.toml` — 移除 duckdb 依赖，添加 chromadb 可选依赖
- `scripts/migrate_graph_to_kuzu.py` — DuckDB → SQLite
- `examples/demo_hybrid_retrieval.py` — DuckDBStorage → SQLiteStorage
- 10+ 测试文件 — 更新导入和类型注解

## 关键技术决策

1. **SQLite 线程安全**: 使用 `check_same_thread=False` + `asyncio.Lock` 序列化访问
2. **ChromaDB 可选依赖**: 通过 `pip install ontology-engine[chroma]` 安装，未安装时优雅降级
3. **KuzuDB Cypher 兼容性**: `type(r)` → `label(r)`，简化可变长度路径查询
4. **DualWriteCoordinator 三引擎**: 写入顺序 MetaStore→GraphStore→VectorStore，失败记录补偿事务
5. **工厂模式**: `create_meta_store()`, `create_graph_store()`, `create_vector_store()` + `StorageConfig.from_env()`

## KuzuDB GraphStore 新增方法

- `get_neighborhood()` — 邻域子图查询（支持深度和置信度过滤）
- `get_entity_at()` — 时间切片实体查询
- `get_edge_at()` — 时间切片边查询
- `get_by_source_pipeline()` — 源管道追溯查询
- `create_mutual_index_edge()` — 创建互索引边（EXTRACTED_FROM/SUPPORTED_BY/DEFINED_IN/TRACE_TO）
- `get_mutual_index_edges()` — 获取互索引边
- `update_feedback_weight()` — 反馈权重 EMA 更新

## 测试结果

- 307 tests passed (294 unit + 13 integration)
- ruff check: 所有存储层文件通过

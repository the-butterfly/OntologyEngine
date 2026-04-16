# Storage Repository 接口分离设计

> **状态**: draft
> **Phase**: phase1-2
> **Last Updated**: 2026-04-14
> **Source of Truth**: false（设计文档）

## 背景

当前 `StorageBackend`（`ontology_engine/storage/base.py`）是单体接口（约 30 个方法），导致：
- 接口膨胀：新增功能必须修改 base.py
- 难以针对不同存储后端选择性实现
- 测试时无法 mock 单个 Concern

## 设计方案：Repository 接口分离

| Repository 接口 | 职责 | 核心方法 |
|---|---|---|
| `IEntityRepository` | 实体 CRUD | `save_entity`, `get_entity`, `query_entities`, `delete_entity` |
| `IRelationRepository` | 关系 CRUD | `save_relation`, `get_relations`, `get_neighbors` |
| `IMetricRepository` | 指标存取 | `save_computed_metrics`, `get_metrics` |
| `ICategoryRepository` | 分类标签 | `save_category_tags`, `get_category_tags` |
| `IDatasetRepository` | 数据集管理 | `save_dataset`, `get_dataset`, `list_datasets` |
| `ISyncRepository` | 同步记录 | `save_sync_record`, `get_sync_history` |
| `IChangeBatchRepository` | 增量批次 | `save_change_batch`, `get_change_batch` |
| `IExecutionLogRepository` | 执行日志 | `log_rule_execution`, `query_execution_history` |

## Phase 1 过渡策略

- 当前 DuckDBStorage 同时实现所有 Repository
- Phase 1 末：在 DuckDBStorage 内部先按 Concern 组织代码（用 `====` 分隔），不改变外部接口
- Phase 2：提取 `I*Repository` 接口，`StorageBackend` 降级为聚合根（Facade）
- NetworkXGraphStore → Phase 2 升级为 kuzu 嵌入图数据库，与 DuckDB 共存

## kuzu 与 DuckDB 协同

| 能力 | DuckDB | kuzu |
|---|---|---|
| 实体存储 | ✅ | ❌ |
| 关系存储 | ✅（SQL 表） | ✅（原生图） |
| 图遍历 | BFS/DFS SQL | 原生图遍历 |
| 路径查询 | DFS SQL（depth≤3） | 高效路径算法 |
| 担保圈检测 | SQL 循环检测 | 循环检测算法 |
| 指标计算 | ✅ | ❌ |
| 审计日志 | ✅ | ❌ |

## 迁移路径

1. **Phase 1**：内部代码按 Repository 分组（不暴露接口）
2. **Phase 2**：抽象 `I*Repository` 接口，DuckDBStorage 实现；引入 KuzuGraphStore
3. **Phase 3**：支持可插拔后端（PostgreSQL、Neo4j 等）

## Transaction 方法降级

当前 `StorageBackend` 中的 `begin_transaction`、`commit_transaction`、`rollback_transaction` 方法标记为 **[待降级]**：
- DuckDB 不支持真正的 ACID 事务（单连接写入）
- Phase 2 移除或在 Repository 层内部化

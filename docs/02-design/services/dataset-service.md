# DatasetService 数据集管理服务设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19
> **[待扩展]**: 本文档定义 L0 数据源层的完整设计，需与 `core/dataset/models.py` 和 `ingestion-service.md` 交叉核验

---

## 目的

定义 DatasetService（L0 数据源层）的完整架构，管理外部数据源的注册、连接、元数据和生命周期。DatasetService 是 OntologyEngine 的数据入口，负责告诉系统"数据在哪里、如何访问、何时刷新"。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **Dataset 模型与存储绑定** | `dataset_service.py` 依赖 DuckDB 存储，违反本地优先原则 | 统一到 SQLite + KuzuDB 存储架构 |
| 2 | **source_type 定义混乱** | `core/dataset/models.py` 定义 POSTGRESQL/MYSQL/FILE/API/S3，`ingestion-service.md` 定义 table/api/file/stream | 统一为 table / api / document / stream 四类 |
| 3 | **Dataset 与 IngestionService 边界不清** | Dataset 注册分散在 IngestionService，DatasetService 只做实体管理 | DatasetService 负责元数据，IngestionService 负责数据摄入 |
| 4 | **无数据新鲜度检查** | 无机制检测外部数据源变更 | DatasetService 提供 freshness_check 接口 |
| 5 | **无 linkage_targets 关联** | Dataset 到 Schema 的关联未明确设计 | Dataset.declares_schema 关联 + linkage_targets 字段 |

---

## 架构定位

```
┌──────────────────────────────────────────────────────────────────────┐
│  L4: API 层 (FastAPI / MCP / CLI)                                    │
├──────────────────────────────────────────────────────────────────────┤
│  L3: 服务层                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  DatasetService ← 本文档                                      │   │
│  │  职责：数据集元数据管理 + linkage_targets 关联                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  L2: 引擎层 (QueryEngine / RuleEngine / MetricEngine)                │
├──────────────────────────────────────────────────────────────────────┤
│  L1: 存储层 (SQLite / KuzuDB / ChromaDB)                             │
│  ── Dataset 元数据 → SQLite                                          │
│  ── Dataset-Entity 关联边 → KuzuDB                                   │
├──────────────────────────────────────────────────────────────────────┤
│  L0: 数据源层 ← 本文档                                                │
│  ── 外部系统：数据库 / API / 文档 / 流数据                             │
│  ── 本地缓存：SQLite + KuzuDB 元数据                                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 核心概念

### L0 数据源层职责

L0 数据源层是 OntologyEngine 与外部数据的桥梁：

| 职责 | 说明 |
|------|------|
| **数据源注册** | 声明外部数据源的位置（URI）和访问方式 |
| **元数据管理** | 管理数据集的名称、描述、标签、负责人 |
| **Schema 关联** | 声明数据集对应的 Schema（linkage_targets） |
| **新鲜度检查** | 检测外部数据是否变更（SHA256 / 时间戳 / 触发器） |
| **访问权限** | 沿用源系统权限，不重复授权 |
| **快照管理** | Dataset 版本的快照，记录 linkage_targets 快照 |

### Dataset 模型（统一）

```yaml
Dataset:
  id: string                    # ds_{uuid8}
  name: string                  # 用户友好的名称
  description: string | null

  # L0 数据源定义
  source_type: enum             # table | api | document | stream
  source_uri: string            # 访问地址
  source_config: dict           # 认证、连接池、超时等配置

  # Schema 关联（L1 知识编译层）
  declares_schema: str          # 关联的 Schema ID
  linkage_targets: list[str]    # 可选的额外关联 Schema ID 列表

  # 同步配置
  sync_mode: enum               # full | incremental
  sync_config:
    incremental_type: enum      # timestamp | conditions
    timestamp_field: string
    last_sync_at: datetime
    schedule_cron: string

  # 状态与审计
  status: enum                  # active | paused | error | syncing
  freshness:
    last_check_at: datetime
    last_data_hash: string      # SHA256 哈希
    is_fresh: boolean

  # 元数据
  metadata:
    owner: string
    sensitivity_level: enum     # public | internal | confidential | restricted
    tags: list[string]
  created_at: datetime
  updated_at: datetime
```

### 数据源类型

| source_type | 说明 | 示例 |
|-------------|------|------|
| **table** | 关系型数据库表 | PostgreSQL 表、MySQL 表 |
| **api** | REST/GraphQL API | 内部微服务、外部 API |
| **document** | 文档文件 | PDF、Markdown、CSV |
| **stream** | 流式数据源 | Kafka Topic、WebSocket |

---

## 接口设计

### 核心接口

| 方法 | 说明 | 存储 |
|------|------|------|
| `create_dataset(declaration)` | 创建数据集 | SQLite |
| `get_dataset(dataset_id)` | 获取数据集 | SQLite |
| `list_datasets(filters)` | 列出数据集 | SQLite |
| `update_dataset(dataset_id, patch)` | 更新数据集 | SQLite |
| `delete_dataset(dataset_id)` | 删除数据集 | SQLite |
| `declare_schema(dataset_id, schema_id)` | 声明 Schema 关联 | KuzuDB |
| `linkage_targets(dataset_id)` | 获取 linkage_targets | KuzuDB |

### 新鲜度检查

| 方法 | 说明 |
|------|------|
| `check_freshness(dataset_id)` | 检查数据是否变更 |
| `get_freshness_status(dataset_id)` | 获取新鲜度状态 |

### 快照管理

| 方法 | 说明 |
|------|------|
| `create_snapshot(dataset_id, description)` | 创建快照 |
| `list_snapshots(dataset_id)` | 列出快照 |
| `restore_snapshot(snapshot_id)` | 恢复快照 |

---

## 数据流

### Dataset 注册流程

```
用户调用 POST /api/v1/datasets
  ↓
DatasetService.create_dataset(declaration)
  ↓
1. 验证 source_uri 可达（ping / 连接测试）
  ↓
2. 生成 dataset_id = ds_{uuid8}
  ↓
3. 写入 SQLite datasets 表
  ↓
4. 如果 declares_schema 存在：
     → 在 KuzuDB 创建 Dataset-DeclaredSchema 边
  ↓
5. 初始化 freshness.last_check_at = now
  ↓
返回 DatasetInfo
```

### Dataset 与 L1 的衔接

```
Dataset（声明）
  │
  ├── declares_schema → Schema ID（L1 知识编译层的入口）
  │
  └── linkage_targets → [Schema ID, ...]（可选的额外 Schema）

  ↓ IngestionService.ingest_*()
  
实际数据（外部系统）
  ↓
KnowledgeFragment（Layer-R）
  ↓ extracted_from 边
EntityInstance（Layer-S）
```

### 快照与版本

```
Dataset 快照记录：
  snapshot_id, dataset_id, declares_schema, linkage_targets_snapshot,
  entity_count, created_at, description

用途：
  1. 回溯某个时间点的数据集状态
  2. 对比不同时间点的 linkage_targets 变更
  3. 支持审计追溯
```

---

## 存储设计

### SQLite 表：datasets

```sql
CREATE TABLE datasets (
    id TEXT PRIMARY KEY,              -- ds_{uuid8}
    name TEXT NOT NULL,
    description TEXT,

    -- L0 数据源定义
    source_type TEXT NOT NULL,        -- table | api | document | stream
    source_uri TEXT NOT NULL,
    source_config TEXT,                -- JSON：认证、连接池、超时等

    -- Schema 关联
    declares_schema TEXT,              -- Schema ID
    linkage_targets TEXT,              -- JSON Array：[schema_id, ...]

    -- 同步配置
    sync_mode TEXT DEFAULT 'full',
    sync_config TEXT,                 -- JSON

    -- 状态
    status TEXT DEFAULT 'active',
    freshness TEXT,                   -- JSON：last_check_at, last_data_hash, is_fresh

    -- 元数据
    metadata TEXT,                    -- JSON：owner, sensitivity_level, tags
    created_at TEXT,
    updated_at TEXT
);
```

### SQLite 表：dataset_snapshots

```sql
CREATE TABLE dataset_snapshots (
    id TEXT PRIMARY KEY,              -- snap_{uuid8}
    dataset_id TEXT NOT NULL,
    description TEXT,
    declares_schema_snapshot TEXT,
    linkage_targets_snapshot TEXT,     -- JSON Array
    entity_count INTEGER DEFAULT 0,
    created_at TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);
```

### KuzuDB 边：DECLARES_SCHEMA

```python
# Dataset → Schema 关联边
(d:Dataset)-[:DECLARES_SCHEMA {created_at: datetime}]→(s:Schema)
```

---

## 与 IngestionService 的边界

| 职责 | DatasetService | IngestionService |
|------|---------------|-----------------|
| Dataset 元数据 CRUD | ✅ | — |
| 数据源连接测试 | ✅ | — |
| 数据新鲜度检查 | ✅ | — |
| Schema 关联声明 | ✅ | — |
| 实际数据摄入 | — | ✅ |
| KnowledgeFragment 创建 | — | ✅ |
| EntityInstance 创建 | — | ✅ |
| 矛盾检测 | — | ✅ |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-DS-1 | Dataset 元数据存 SQLite | WAL 模式适合元数据低频写入，事务保证 |
| D-DS-2 | Dataset-Schema 关联存 KuzuDB | 图数据库适合多跳关联查询 |
| D-DS-3 | source_type 统一为 table/api/document/stream | 与 ingestion-service.md 对齐，简化类型系统 |
| D-DS-4 | 数据新鲜度用 SHA256 哈希检测 | SHA256 比时间戳更可靠，适合文件/API/流 |
| D-DS-5 | 访问权限沿用源系统 | 不重复授权，简化权限管理 |

---

## 与现有代码的差异

### `core/dataset/models.py` 需重构

| 字段 | 当前 | 应改为 |
|------|------|--------|
| DatasetType | POSTGRESQL, MYSQL, FILE, API, S3 | table, api, document, stream |
| SourceConnection | 包含 host/port/database/username/password | source_uri + source_config |
| SyncConfig | 与 DatasetDeclaration 分离 | 内嵌到 Dataset.sync_config |

### `services/dataset_service.py` 需重构

| 问题 | 当前 | 应改为 |
|------|------|--------|
| 存储依赖 | DuckDB | SQLite（通过 storage/base.py） |
| 职责 | 实体成员管理 | Dataset 元数据 + linkage_targets |
| 接口 | add_entities, get_intersection, get_diff | create_dataset, declare_schema, check_freshness |

---

## 待办事项

| 优先级 | 事项 | 说明 |
|--------|------|------|
| P0 | 重构 `core/dataset/models.py` | 统一 Dataset 模型，移除 POSTGRESQL/MYSQL/S3 枚举 |
| P0 | 重构 `services/dataset_service.py` | 迁移到 SQLite 存储，实现 freshness_check |
| P1 | 实现 `declare_schema(dataset_id, schema_id)` | KuzuDB 边创建 |
| P1 | 实现 `check_freshness(dataset_id)` | SHA256 哈希检测 |
| P1 | 实现快照管理 | create_snapshot, restore_snapshot |
| P2 | 数据源连接测试 | create_dataset 时验证 source_uri 可达 |
| P2 | 定时新鲜度检查 | 集成到 IncrementalUpdateService |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 五层架构 L0 定义 | `docs/01-overview/01-vision.md` |
| 服务层模块架构 | `docs/01-overview/04-modules.md` |
| IngestionService 设计 | `docs/02-design/services/ingestion-service.md` |
| 存储层接口定义 | `docs/02-design/storage/interfaces.md` |
| 现有 Dataset 模型 | `ontology_engine/core/dataset/models.py` |
| 现有 DatasetService | `ontology_engine/services/dataset_service.py` |

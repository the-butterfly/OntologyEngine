# SemanticSpace 存储架构完整性审查报告

> **status**: draft | **phase**: review | **last_verified**: 2026-05-15 | **verified_against**: ontology_engine/ 代码 + docs/ 设计文档 + docs-dev/ 讨论记录

---

## 1. 审查背景

### 1.1 触发原因

前端 `/spaces` 页面展示为空，排查发现 `data/semantic_spaces/` 目录无数据。进一步分析发现 `SpaceService` 使用独立的 JSON 文件存储（`SemanticSpaceStorage`），与设计文档定义的 SQLite/KuzuDB 三引擎架构存在严重断裂。

### 1.2 审查范围

| 维度 | 覆盖范围 |
|------|---------|
| 存储层 | `SemanticSpaceStorage`、`SQLiteStorage`、`KuzuGraphStore`、`DualWriteCoordinator` |
| 服务层 | `SpaceService`、`EntityService`、`AnalysisService`、`QueryService` 等 |
| API 层 | `management.py`、`semantic_spaces.py`、`consumption.py`、旧路由 |
| 设计文档 | `docs/02-design/storage/`、`docs-dev/03-rfc/`、`docs-dev/discuss/` |
| Review 报告 | `docs-dev/review-reports/` 下 4 月报告的过时状态 |

### 1.3 审查方法

代码静态分析 + 设计文档交叉比对 + API 运行时验证

---

## 2. 核心发现：双存储体系并行

### 2.1 当前实际架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API Routes Layer                             │
│                                                                     │
│  新路由 (/v1/spaces, /v1/views)                                     │
│    → SpaceService → SemanticSpaceStorage → data/semantic_spaces/*.json│
│    ❌ 不写入 SQLite / KuzuDB                                         │
│                                                                     │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ 完全独立·无交叉读写 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                                                     │
│  旧路由 (/v1/entities, /v1/analysis, /v1/query, /v1/rules...)       │
│    → EntityService/AnalysisService → SQLiteStorage → meta.db        │
│    → DualWriteCoordinator → KuzuGraphStore → graph.kuzu             │
│    ❌ 不读取 SemanticSpaceStorage 的数据                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 设计文档定义的架构

| 来源文档 | 决策状态 | SemanticSpace 数据应存储在 |
|---------|---------|--------------------------|
| `docs-dev/discuss/2026-04-27-storage-architecture-b-to-c-migration.md` | **accepted** | SQLite 为数据真相源，可按语义空间分库物理隔离 |
| `docs-dev/03-rfc/RFC-012-kuzu-storage.md` | **accepted, implementation-ready** | KuzuDB 按 `space_id` 子目录隔离 |
| `docs/02-design/storage/README.md` | **活跃文档** | 三引擎协同：KuzuDB + ChromaDB + SQLite |
| `docs/04-adr/ADR-010-rfc-derived-architecture-decisions.md` | **正式 ADR** | DualWriteCoordinator 三引擎双写 |

### 2.3 代码实际实现

| 存储层 | 代码量 | 实现状态 | SpaceService 是否使用 |
|--------|-------|---------|---------------------|
| `SQLiteStorage` | ~2113 行 | ✅ 完整实现 | ❌ 未使用 |
| `KuzuGraphStore` | ~2660 行 | ✅ 完整实现 | ❌ 未使用 |
| `DualWriteCoordinator` | 完整 | ✅ 完整实现 | ❌ 未使用 |
| `SemanticSpaceStorage` | ~287 行 | ✅ 完整实现 | ✅ 唯一使用者 |

---

## 3. 数据流断裂点清单

### 3.1 写入断裂（数据只存 JSON，不存数据库）

| # | 断裂点 | API 路由 | 数据类型 | 后果 |
|---|--------|---------|---------|------|
| F1 | Schema 加载 | `POST /v1/spaces/{id}/schema/load-yaml` | L1-L4 Schema 定义 | 规则定义只存 JSON，SQLite `rule_groups`/`rule_steps` 表无记录 |
| F2 | 实例加载 | `POST /v1/spaces/{id}/instances/load-yaml` | 实体 + 关系 | 实例只存 JSON，SQLite `entities`/`relations` 表无记录，KuzuDB 无节点/边 |
| F3 | 单实体创建 | `POST /v1/spaces/{id}/instances/entities` | 单个实体 | 同 F2 |
| F4 | 单关系创建 | `POST /v1/spaces/{id}/instances/relations` | 单个关系 | 同 F2 |
| F5 | Schema CRUD | L1-L4 各端点 | Schema 元素 | 全部只存 JSON |
| F6 | Space 激活复制 | `POST /v1/spaces/{id}/activate` | Space 副本到消费视图 | 消费视图也只存 JSON |
| F7 | JSON 导入 | `POST /v1/spaces/load-from-json` | 整个 Space | 同 F1-F6 |

### 3.2 读取断裂（旧路由读不到新路由写入的数据）

| # | 断裂点 | API 路由 | 期望数据来源 | 实际结果 |
|---|--------|---------|------------|---------|
| R1 | 实体查询 | `GET /v1/entities` | SQLiteStorage | ❌ 查不到 Space 中创建的实体 |
| R2 | 关系查询 | `GET /v1/relations` | SQLiteStorage | ❌ 查不到 Space 中创建的关系 |
| R3 | 规则分析 | `POST /v1/analysis/execute` | SQLiteStorage + 内存 Schema | ❌ 查不到 Space 中的规则和实体 |
| R4 | 语义搜索 | `POST /v1/query/semantic-search` | VectorStore | ❌ 无向量数据 |
| R5 | 图遍历 | `GET /v1/query/graph-traverse` | KuzuGraphStore | ❌ 无图节点/边 |
| R6 | 规则组查询 | `GET /v1/rule-groups` | SQLiteStorage | ❌ `rule_groups` 表为空 |
| R7 | 可视化 | `GET /v1/visualize/schema-graph` | 内存 Schema + SQLiteStorage | ❌ Schema 在内存中但实体不在 SQLite |

### 3.3 概念重叠但存储独立

| 数据类型 | 旧路由（SQLiteStorage） | 新路由（SemanticSpaceStorage） | 重叠 |
|---------|----------------------|---------------------------|------|
| Schema 定义 | `SchemaService._current_schema`（内存） | `space.layers`（JSON 文档内） | 概念重叠，存储独立 |
| Entity 实例 | `entities` 表（SQLite） | `space.instances.entities`（JSON 数组） | 概念重叠，存储独立 |
| Relation 实例 | `relations` 表（SQLite） | `space.instances.relations`（JSON 数组） | 概念重叠，存储独立 |
| Rule Groups | `rule_groups` 表（SQLite） | `space.layers.L4.rule_definitions`（JSON 数组） | 概念重叠，存储独立 |
| Rule Steps | `rule_steps` 表（SQLite） | `space.layers.L4.rule_logics`（JSON 数组） | 概念重叠，存储独立 |
| Metrics | `computed_metrics` 表（SQLite） | `space.instances.metric_values`（JSON 数组） | 概念重叠，存储独立 |
| Category Tags | `category_tags` 表（SQLite） | `space.instances.category_tags`（JSON 数组） | 概念重叠，存储独立 |

---

## 4. 前后端字段映射问题

### 4.1 `GET /v1/spaces` 列表接口字段缺失

| 后端返回字段 | 前端 SpaceResponse 期望字段 | 状态 |
|-------------|---------------------------|------|
| `id` | `id` | ✅ 匹配 |
| `name` | `name` | ✅ 匹配 |
| `description` | `description` | ✅ 匹配 |
| `status` | `status` | ✅ 匹配 |
| `version` | `version` | ✅ 匹配 |
| `entity_count` | `entity_count` | ✅ 匹配 |
| `rule_count` | `rule_definition_count` | ❌ 字段名不匹配 |
| — | `relation_count` | ❌ 后端未返回 |
| — | `rule_logic_count` | ❌ 后端未返回 |
| — | `domain` | ❌ 后端未返回 |
| `created_at` | `created_at` | ✅ 匹配 |
| `updated_at` | `updated_at` | ✅ 匹配 |
| `view_id` | `view_id` | ✅ 匹配 |
| `view` | `view` | ✅ 匹配 |

### 4.2 `GET /v1/spaces/{id}` 详情接口字段差异

详情接口返回了 `domain`、`relation_count`、`rule_definition_count`、`rule_logic_count`，但列表接口缺失。前端列表页使用列表接口数据，导致这些列始终显示为 0 或 undefined。

---

## 5. 设计文档过时状态标记

### 5.1 需要更新过时标记的文档

| # | 文档 | 过时程度 | 原因 | 建议操作 |
|---|------|---------|------|---------|
| 1 | `docs-dev/review-reports/storage-review.md` | 🔴 高 | 基于 KuzuDB 为主存储编写，4月27日已决策 SQLite 为主存储 | 按B→C决策重写架构方向部分 |
| 2 | `docs-dev/review-reports/api-review.md` | 🟡 中 | 指出了双存储体系问题，但未解决 | 更新断裂点状态 |
| 3 | `docs-dev/review-reports/services-review.md` | 🟡 中 | 22项偏差部分已修复，核心功能缺失仍存在 | 标记已修复项 |
| 4 | `docs-dev/review-reports/consistency-report.md` | 🟡 中 | 5项严重问题中2项部分修复 | 更新修复状态 |
| 5 | `docs-dev/review-reports/frontend-backend-gap-analysis.md` | 🟡 中 | GAP 1/2 部分修复，数据模型断裂仍存在 | 更新断裂点 |
| 6 | `docs-dev/03-rfc/RFC-002-storage-strategy.md` | 🔴 完全过时 | DuckDB+NetworkX 方案已被取代 | 标记 superseded |
| 7 | `docs-dev/03-rfc/RFC-012-kuzu-storage.md` | 🟡 部分过时 | KuzuDB 从主存储降级为辅助层 | 按B→C决策更新 |
| 8 | `docs/02-design/storage/kuzudb-schema.md` | 🟡 部分过时 | 仍按 KuzuDB 为主存储编写 | 按B→C决策更新 |
| 9 | `docs/02-design/storage/README.md` | 🟡 部分过时 | 未反映B→C决策 | 按B→C决策更新 |

### 5.2 已在本文档审查中标记过时的内容

以下文档的头部元数据已更新 `last_verified` 和过时标记，详见各文件变更。

---

## 6. 修复计划

### Phase 0: 前端字段映射修复（紧急）

**目标**：修复 `GET /v1/spaces` 列表接口字段缺失，使前端能正确显示数据。

| # | 任务 | 涉及文件 | 优先级 |
|---|------|---------|--------|
| P0-1 | 列表接口补充 `domain`、`relation_count`、`rule_definition_count`、`rule_logic_count` 字段 | `ontology_engine/api/routes/management.py` L290-302 | P0 |
| P0-2 | 将 `rule_count` 重命名为 `rule_definition_count` 或前端适配 | `management.py` + `spaceApi.ts` | P0 |

### Phase 1: SpaceService 双写桥接（核心）

**目标**：SpaceService 写入数据时同时写入 SQLiteStorage + KuzuGraphStore，打通数据流。

| # | 任务 | 涉及文件 | 优先级 |
|---|------|---------|--------|
| P1-1 | SpaceService 注入 StorageBackend 和 GraphStoreBackend | `ontology_engine/services/space_service.py` | P0 |
| P1-2 | `load_instances_from_file()` 双写：实体/关系同时写入 SQLite + KuzuDB | `space_service.py` | P0 |
| P1-3 | `load_schema_from_file()` 双写：规则定义/逻辑同时写入 SQLite rule_groups/rule_steps | `space_service.py` | P0 |
| P1-4 | `add_entity()` / `add_relation()` 双写 | `space_service.py` | P0 |
| P1-5 | `activate_space()` 时同步数据到消费视图 + 触发向量索引构建 | `space_service.py` | P1 |
| P1-6 | Space 元数据（name, status, domain）同步到 SQLite datasets 表 | `space_service.py` | P1 |

### Phase 2: 旧路由 Space 感知（对齐）

**目标**：旧路由查询时能感知 Space 隔离，按 `space_id` 过滤数据。

| # | 任务 | 涉及文件 | 优先级 |
|---|------|---------|--------|
| P2-1 | EntityService 查询方法增加 `space_id` 过滤参数 | `ontology_engine/services/entity_service.py` | P1 |
| P2-2 | AnalysisService 执行分析时按 `space_id` 加载 Schema 和实体 | `ontology_engine/services/analysis_service.py` | P1 |
| P2-3 | QueryService 查询方法增加 `space_id` 过滤参数 | `ontology_engine/services/query_service.py` | P1 |
| P2-4 | 旧路由 API 端点增加 `space_id` 查询参数 | `ontology_engine/api/routes/entities.py` 等 | P2 |

### Phase 3: SemanticSpaceStorage 迁移（长期）

**目标**：将 SemanticSpaceStorage 从 JSON 文件迁移到 SQLite，实现按 Space 分库。

| # | 任务 | 涉及文件 | 优先级 |
|---|------|---------|--------|
| P3-1 | 设计 Space 元数据 SQLite 表结构（对齐 `docs/02-design/storage/sqlite-tables.md`） | 新文件 | P2 |
| P3-2 | 实现 `SqliteSpaceStorage` 替代 `SemanticSpaceStorage` | 新文件 | P2 |
| P3-3 | SpaceService 切换到 `SqliteSpaceStorage` | `space_service.py` | P2 |
| P3-4 | 数据迁移脚本：JSON → SQLite | `scripts/migrate_space_to_sqlite.py` | P2 |
| P3-5 | 按 `space_id` 分库实现（`StorageConfig.space_isolation_mode="database_per_space"`） | `storage/config.py` | P3 |

### Phase 4: 文档同步

| # | 任务 | 涉及文件 | 优先级 |
|---|------|---------|--------|
| P4-1 | 更新 `storage/README.md` 反映 B→C 迁移决策 | `docs/02-design/storage/README.md` | P1 |
| P4-2 | 更新 `kuzudb-schema.md` 标注 KuzuDB 为辅助层 | `docs/02-design/storage/kuzudb-schema.md` | P1 |
| P4-3 | 更新 `RFC-012` 标注 B→C 迁移修正 | `docs-dev/03-rfc/RFC-012-kuzu-storage.md` | P1 |
| P4-4 | 标记 `RFC-002` 为 superseded | `docs-dev/03-rfc/RFC-002-storage-strategy.md` | P2 |
| P4-5 | 更新 review 报告过时标记 | 各 review 文件 | P2 |

---

## 7. 依赖关系

```
Phase 0 (前端字段映射)
  │
  ▼
Phase 1 (SpaceService 双写桥接) ← 核心阻塞项
  │
  ├──▶ Phase 2 (旧路由 Space 感知)
  │
  └──▶ Phase 3 (SemanticSpaceStorage 迁移到 SQLite)

Phase 4 (文档同步) 可与 Phase 1-3 并行
```

---

## 8. 验收标准

| Phase | 验收条件 |
|-------|---------|
| Phase 0 | `GET /v1/spaces` 返回 `domain`、`relation_count`、`rule_definition_count`、`rule_logic_count` 字段；前端列表页正确显示所有列 |
| Phase 1 | `setup_all_spaces.py` 执行后，SQLite `entities`/`relations` 表有对应记录；KuzuDB 有对应节点/边；`/v1/analysis/execute` 可查询到 Space 中的实体 |
| Phase 2 | 旧路由查询结果按 `space_id` 过滤；不同 Space 的数据互不干扰 |
| Phase 3 | `data/semantic_spaces/*.json` 不再存在；Space 元数据存储在 SQLite 中；`space_isolation_mode=database_per_space` 可用 |
| Phase 4 | 所有文档过时标记已更新；7 份需同步文档已完成更新 |

---

## 9. 风险评估

| # | 风险 | 影响 | 缓解措施 |
|---|------|------|---------|
| 1 | 双写一致性问题——SpaceService 写 JSON 成功但写 SQLite 失败 | 数据不一致 | 使用 DualWriteCoordinator 已有的补偿事务机制 |
| 2 | 旧路由无 `space_id` 过滤——迁移后查询返回跨 Space 数据 | 数据泄露 | Phase 2 必须在 Phase 1 之后执行 |
| 3 | 前端字段映射变更导致旧版不兼容 | 前端报错 | Phase 0 同时更新前端类型定义 |
| 4 | JSON → SQLite 迁移期间服务不可用 | 停机 | Phase 3 设计为在线迁移，JSON 和 SQLite 并行运行 |

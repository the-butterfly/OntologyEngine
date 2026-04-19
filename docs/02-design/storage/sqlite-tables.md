# SQLite 表结构设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/06-tech-stack.md` | **last_verified**: 2026-04-19

---

## 目的

定义 OntologyEngine 在 SQLite 中的元数据表结构，承载 Schema 版本管理、审计日志、管道运行状态、文件哈希、矛盾报告、数据集元数据和知识碎片索引。SQLite 使用 WAL 模式提供低延迟并发读写。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | DuckDB 中元数据与图数据耦合 | 无法独立扩展和优化元数据操作 |
| 2 | 缺乏 Schema 版本管理 | Schema 变更无法追踪、回滚和影响分析 |
| 3 | 缺乏审计日志 | 数据变更不可追溯 |
| 4 | 管道运行状态无持久化 | 重启后管道状态丢失 |
| 5 | 文件增量处理缺乏依据 | 无法判断文件是否已处理或变更 |

---

## WAL 模式配置

```python
async def initialize(self) -> None:
    self._conn = sqlite3.connect(self.db_path)
    self._conn.execute("PRAGMA journal_mode=WAL")
    self._conn.execute("PRAGMA synchronous=NORMAL")
    self._conn.execute("PRAGMA busy_timeout=5000")
    self._conn.execute("PRAGMA cache_size=-64000")
    self._conn.execute("PRAGMA foreign_keys=ON")
```

| PRAGMA | 值 | 说明 |
|--------|-----|------|
| journal_mode | WAL | 写前日志，支持并发读写 |
| synchronous | NORMAL | 平衡安全性和性能 |
| busy_timeout | 5000ms | 写冲突时等待 5 秒 |
| cache_size | -64000 | 64MB 页缓存 |
| foreign_keys | ON | 启用外键约束 |

**与参考项目的对齐**：

| 设计点 | MemPalace SQLite | m_flow FSCache | OntologyEngine |
|--------|-----------------|----------------|----------------|
| WAL 模式 | 是 | 否（文件系统缓存） | 是 |
| 外键约束 | 是 | 否 | 是 |
| busy_timeout | 5000ms | N/A | 5000ms |
| 事务隔离 | SERIALIZABLE | N/A | SERIALIZABLE |

---

## 表结构

### schema_versions

**目的**：记录 Schema 版本变更历史，支持版本回滚和影响分析。

```sql
CREATE TABLE schema_versions (
    version         INTEGER PRIMARY KEY,
    description     TEXT NOT NULL,
    migration_up    TEXT NOT NULL,
    migration_down  TEXT NOT NULL,
    checksum        TEXT NOT NULL,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now')),
    applied_by      TEXT
);

CREATE INDEX idx_sv_applied_at ON schema_versions(applied_at);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| version | INTEGER PK | 版本号，单调递增 |
| description | TEXT | 版本描述 |
| migration_up | TEXT | 升级 SQL |
| migration_down | TEXT | 降级 SQL |
| checksum | TEXT | 迁移脚本 SHA256 校验和 |
| applied_at | TEXT | 应用时间 |
| applied_by | TEXT | 操作者 |

---

### audit_log

**目的**：记录所有数据变更操作，支持审计追溯。

```sql
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    operation   TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    actor       TEXT,
    details     TEXT,
    before_snapshot TEXT,
    after_snapshot  TEXT
);

CREATE INDEX idx_al_timestamp ON audit_log(timestamp);
CREATE INDEX idx_al_target ON audit_log(target_type, target_id);
CREATE INDEX idx_al_operation ON audit_log(operation);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| operation | TEXT | create / update / delete / merge |
| target_type | TEXT | EntityInstance / EdgeInstance / RuleDefinition / KnowledgeFragment / CategoryTag / MetricValue |
| target_id | TEXT | 目标对象 ID |
| actor | TEXT | 操作者（pipeline 名称或用户 ID） |
| details | TEXT | 变更详情 JSON |
| before_snapshot | TEXT | 变更前快照 JSON |
| after_snapshot | TEXT | 变更后快照 JSON |

---

### pipeline_runs

**目的**：记录管道运行状态，支持管道监控和重试。

```sql
CREATE TABLE pipeline_runs (
    id          TEXT PRIMARY KEY,
    pipeline    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running',
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    input_hash  TEXT,
    output_count INTEGER DEFAULT 0,
    error_message TEXT,
    metadata    TEXT
);

CREATE INDEX idx_pr_pipeline ON pipeline_runs(pipeline);
CREATE INDEX idx_pr_status ON pipeline_runs(status);
CREATE INDEX idx_pr_started_at ON pipeline_runs(started_at);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 运行 ID |
| pipeline | TEXT | 管道名称 |
| status | TEXT | running / completed / failed / cancelled |
| input_hash | TEXT | 输入数据哈希，用于去重 |
| output_count | INTEGER | 产出数量 |
| error_message | TEXT | 错误信息 |
| metadata | TEXT | 扩展元数据 JSON |

---

### file_hashes

**目的**：记录文件哈希，支持增量处理判断。

```sql
CREATE TABLE file_hashes (
    file_path   TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    file_size   INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    processed_at TEXT,
    pipeline    TEXT
);

CREATE INDEX idx_fh_content_hash ON file_hashes(content_hash);
CREATE INDEX idx_fh_processed_at ON file_hashes(processed_at);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| file_path | TEXT PK | 文件路径 |
| content_hash | TEXT | SHA256 内容哈希 |
| file_size | INTEGER | 文件大小（字节） |
| modified_at | TEXT | 文件修改时间 |
| processed_at | TEXT | 处理完成时间 |
| pipeline | TEXT | 处理管道 |

**增量处理逻辑**：

```
文件处理前：
  1. 计算 file_path 对应的 content_hash
  2. 查询 file_hashes 表
  3. 哈希一致 → 跳过处理
  4. 哈希不一致或不存在 → 执行处理
  5. 处理完成后更新 file_hashes
```

**与参考项目的对齐**：

| 设计点 | MemPalace | m_flow FSCache | Graphify | OntologyEngine |
|--------|-----------|----------------|----------|----------------|
| 哈希算法 | MD5 | SHA256 | SHA256 | SHA256 |
| 增量判断 | 无 | 文件修改时间 | content_hash | content_hash + modified_at |
| 处理状态 | 无 | 无 | 无 | processed_at + pipeline |

---

### contradiction_reports

**目的**：记录知识图谱中发现的矛盾，支持矛盾检测和解决。

```sql
CREATE TABLE contradiction_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id       TEXT NOT NULL,
    contradiction_type TEXT NOT NULL,
    field_name      TEXT NOT NULL,
    existing_value  TEXT NOT NULL,
    new_value       TEXT NOT NULL,
    existing_source TEXT,
    new_source      TEXT,
    severity        TEXT NOT NULL DEFAULT 'warning',
    status          TEXT NOT NULL DEFAULT 'open',
    resolved_at     TEXT,
    resolved_by     TEXT,
    resolution      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_cr_entity_id ON contradiction_reports(entity_id);
CREATE INDEX idx_cr_status ON contradiction_reports(status);
CREATE INDEX idx_cr_severity ON contradiction_reports(severity);
CREATE INDEX idx_cr_created_at ON contradiction_reports(created_at);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| contradiction_type | TEXT | value_conflict / temporal_overlap / reference_broken / type_mismatch |
| severity | TEXT | info / warning / error / critical |
| status | TEXT | open / resolved / dismissed |
| resolution | TEXT | keep_existing / keep_new / merge / manual |

---

### datasets

**目的**：记录数据集元数据，支持 KnowledgeFragment 的数据集归属。

```sql
CREATE TABLE datasets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    source_type TEXT NOT NULL,
    source_uri  TEXT NOT NULL,
    document_count INTEGER DEFAULT 0,
    fragment_count  INTEGER DEFAULT 0,
    metadata    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_ds_source_type ON datasets(source_type);
CREATE INDEX idx_ds_created_at ON datasets(created_at);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 数据集 ID |
| source_type | TEXT | pdf / docx / csv / api / manual |
| source_uri | TEXT | 数据源 URI |
| document_count | INTEGER | 文档数量 |
| fragment_count | INTEGER | 碎片数量 |
| metadata | TEXT | 扩展元数据 JSON |

---

### knowledge_fragments

**目的**：KnowledgeFragment 的 SQLite 索引副本，支持 SQL 级联查询和统计。

```sql
CREATE TABLE knowledge_fragments (
    id                TEXT PRIMARY KEY,
    dataset_id        TEXT NOT NULL,
    document_id       TEXT NOT NULL,
    chunk_index       INTEGER NOT NULL,
    offset_start      INTEGER NOT NULL,
    offset_end        INTEGER NOT NULL,
    text              TEXT NOT NULL,
    vector_id         TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    content_hash      TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE INDEX idx_kf_dataset_id ON knowledge_fragments(dataset_id);
CREATE INDEX idx_kf_document_id ON knowledge_fragments(document_id);
CREATE INDEX idx_kf_extraction_status ON knowledge_fragments(extraction_status);
CREATE INDEX idx_kf_content_hash ON knowledge_fragments(content_hash);
CREATE INDEX idx_kf_dataset_doc ON knowledge_fragments(dataset_id, document_id, chunk_index);
```

> **[关键设计点]**：knowledge_fragments 表是 KuzuDB KnowledgeFragmentNode 的 SQLite 副本。KuzuDB 承载图遍历和互索引边导航，SQLite 承载 SQL 聚合查询和统计。双写保证一致性。

---

## SchemaVersionManager

### 目的

管理 Schema 版本的提交、回滚、差异比较和影响分析。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | Schema 变更无法追踪 | commit_version 记录每次变更的升级/降级 SQL |
| 2 | 变更回滚困难 | rollback 执行 migration_down SQL |
| 3 | 变更影响不可评估 | impact_analysis 分析受影响的表和索引 |
| 4 | 迁移脚本完整性无法验证 | checksum 校验迁移脚本 SHA256 |

### 接口定义

```python
class SchemaVersionManager:
    async def current_version(self) -> int: ...

    async def commit_version(
        self,
        description: str,
        migration_up: str,
        migration_down: str,
    ) -> int: ...

    async def rollback(self, target_version: int) -> None: ...

    async def diff(self, from_version: int, to_version: int) -> list[dict]: ...

    async def impact_analysis(self, target_version: int) -> dict: ...
```

### commit_version 流程

```
1. 验证 migration_up 语法正确性
2. 计算 migration_up + migration_down 的 SHA256 checksum
3. 在事务中执行：
   a. 执行 migration_up SQL
   b. INSERT INTO schema_versions (version, description, migration_up, migration_down, checksum)
4. 事务提交
5. 返回新版本号
```

### rollback 流程

```
1. 查询当前版本 N
2. 从 N 到 target_version + 1，依次：
   a. 读取 schema_versions 中 version=i 的 migration_down
   b. 验证 checksum
   c. 执行 migration_down
   d. DELETE FROM schema_versions WHERE version=i
3. 返回回滚后的版本号
```

### impact_analysis 流程

```
1. 从 current_version 到 target_version，收集所有 migration_up SQL
2. 解析 SQL，提取涉及的表名和操作类型（CREATE/ALTER/DROP）
3. 查询每个表的行数和索引数
4. 生成影响报告：
   {
     "affected_tables": ["EntityNode", "RELATES_TO"],
     "operations": ["ALTER TABLE", "CREATE INDEX"],
     "estimated_rows_affected": 15000,
     "risk_level": "medium",
     "recommendations": ["备份数据", "在测试环境验证"]
   }
```

---

## 事务管理

### 事务模式

```python
async def execute_in_transaction(self, operations: list[Callable]) -> None:
    self._conn.execute("BEGIN IMMEDIATE")
    try:
        for op in operations:
            await op(self._conn)
        self._conn.commit()
    except Exception:
        self._conn.rollback()
        raise
```

### 跨引擎事务协调

SQLite 事务仅覆盖 MetaStore 操作。跨引擎（KuzuDB + ChromaDB + SQLite）的一致性通过补偿事务保证：

```
写入流程：
  1. SQLite BEGIN → 写入 audit_log → COMMIT
  2. KuzuDB MERGE 节点/边
  3. ChromaDB upsert 向量
  4. 若步骤 2/3 失败 → SQLite 写入补偿记录 → 异步重试

补偿事务：
  compensation_log 表记录未完成的跨引擎操作
  后台线程定期扫描并重试
```

---

## 初始化

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-64000;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_versions (...);
CREATE TABLE IF NOT EXISTS audit_log (...);
CREATE TABLE IF NOT EXISTS pipeline_runs (...);
CREATE TABLE IF NOT EXISTS file_hashes (...);
CREATE TABLE IF NOT EXISTS contradiction_reports (...);
CREATE TABLE IF NOT EXISTS datasets (...);
CREATE TABLE IF NOT EXISTS knowledge_fragments (...);

CREATE INDEX IF NOT EXISTS idx_sv_applied_at ON schema_versions(applied_at);
CREATE INDEX IF NOT EXISTS idx_al_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_al_target ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_al_operation ON audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_pr_pipeline ON pipeline_runs(pipeline);
CREATE INDEX IF NOT EXISTS idx_pr_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pr_started_at ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_fh_content_hash ON file_hashes(content_hash);
CREATE INDEX IF NOT EXISTS idx_fh_processed_at ON file_hashes(processed_at);
CREATE INDEX IF NOT EXISTS idx_cr_entity_id ON contradiction_reports(entity_id);
CREATE INDEX IF NOT EXISTS idx_cr_status ON contradiction_reports(status);
CREATE INDEX IF NOT EXISTS idx_cr_severity ON contradiction_reports(severity);
CREATE INDEX IF NOT EXISTS idx_cr_created_at ON contradiction_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_ds_source_type ON datasets(source_type);
CREATE INDEX IF NOT EXISTS idx_ds_created_at ON datasets(created_at);
CREATE INDEX IF NOT EXISTS idx_kf_dataset_id ON knowledge_fragments(dataset_id);
CREATE INDEX IF NOT EXISTS idx_kf_document_id ON knowledge_fragments(document_id);
CREATE INDEX IF NOT EXISTS idx_kf_extraction_status ON knowledge_fragments(extraction_status);
CREATE INDEX IF NOT EXISTS idx_kf_content_hash ON knowledge_fragments(content_hash);
CREATE INDEX IF NOT EXISTS idx_kf_dataset_doc ON knowledge_fragments(dataset_id, document_id, chunk_index);

INSERT INTO schema_versions (version, description, migration_up, migration_down, checksum)
VALUES (1, 'initial schema', '', '', '');
```

---

## 与参考项目的对齐总结

| 维度 | MemPalace SQLite | m_flow FSCache | OntologyEngine |
|------|-----------------|----------------|----------------|
| WAL 模式 | 是 | 否 | 是 |
| Schema 版本管理 | 无 | 无 | SchemaVersionManager |
| 审计日志 | 无 | 无 | audit_log |
| 管道状态 | 无 | 无 | pipeline_runs |
| 文件哈希 | 无 | 文件修改时间 | SHA256 content_hash |
| 矛盾报告 | 无 | 无 | contradiction_reports |
| 数据集元数据 | 无 | 无 | datasets |
| 知识碎片索引 | 无 | 无 | knowledge_fragments（KuzuDB 副本） |
| 事务隔离 | SERIALIZABLE | N/A | SERIALIZABLE + 补偿事务 |
| 外键约束 | 是 | 否 | 是 |

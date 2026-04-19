# DuckDB → KuzuDB 迁移路径

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/02-design/storage/README.md` | **last_verified**: 2026-04-19

---

## 目的

定义从当前 DuckDB 单一存储到 KuzuDB + ChromaDB + SQLite 三引擎架构的迁移策略、数据映射、迁移脚本规范和回滚计划。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | DuckDB 数据无法直接导入 KuzuDB | 表结构差异大，需要数据转换和映射 |
| 2 | 迁移期间服务不可用 | 需要并行运行策略，最小化停机时间 |
| 3 | 迁移失败无法回滚 | 需要回滚计划，确保数据安全 |
| 4 | 向量数据需要重新生成 | LocalVectorStore 内存数据无法导出，需要重新嵌入 |
| 5 | 迁移数据一致性无法验证 | 需要校验机制，确保迁移后数据完整 |

---

## 迁移策略

### 总体策略：并行运行 → 验证 → 切换

```
Phase 0: 准备
  ├── 部署 KuzuDB + ChromaDB + SQLite
  ├── 初始化 Schema
  └── 编写迁移脚本

Phase 1: 数据迁移
  ├── DuckDB → KuzuDB（实体/关系/规则）
  ├── DuckDB → ChromaDB（向量数据重新嵌入）
  ├── DuckDB → SQLite（元数据/审计/管道状态）
  └── 数据校验

Phase 2: 并行运行
  ├── 写入双写（DuckDB + 新引擎）
  ├── 读取从新引擎
  └── 对比验证

Phase 3: 切换
  ├── 停止 DuckDB 写入
  ├── 全量读取切换到新引擎
  └── 保留 DuckDB 只读 7 天

Phase 4: 清理
  ├── 删除 DuckDB 双写逻辑
  └── 归档 DuckDB 数据文件
```

---

## 数据映射

### DuckDB entities → KuzuDB EntityNode

| DuckDB 字段 | KuzuDB EntityNode 字段 | 转换规则 |
|-------------|----------------------|---------|
| id | id | 直接映射 |
| type | _fact_object | type → _fact_object |
| name | name | 直接映射 |
| properties | attributes | JSON → MAP(STRING, STRING) |
| created_at | created_at | 直接映射 |
| updated_at | updated_at | 直接映射 |
| — | valid_from | 新增，默认 NULL |
| — | valid_to | 新增，默认 NULL |
| — | domain_id | 新增，默认 NULL |
| — | confidence | 新增，默认 1.0 |
| — | source_pipeline | 新增，默认 "migration" |
| — | source_content_hash | 新增，默认 NULL |
| — | feedback_weight | 新增，默认 0.5 |

**转换脚本**：

```sql
SELECT
    id,
    type AS _fact_object,
    name,
    properties AS attributes,
    NULL AS valid_from,
    NULL AS valid_to,
    created_at,
    updated_at,
    NULL AS domain_id,
    1.0 AS confidence,
    'migration' AS source_pipeline,
    NULL AS source_content_hash,
    0.5 AS feedback_weight
FROM entities
```

### DuckDB relations → KuzuDB RELATES_TO

| DuckDB 字段 | KuzuDB RELATES_TO 字段 | 转换规则 |
|-------------|----------------------|---------|
| id | id | 直接映射 |
| source_id | from_id | source_id → from_id |
| target_id | to_id | target_id → to_id |
| relation_type | relation_name | relation_type → relation_name |
| properties | attributes | JSON → MAP(STRING, STRING) |
| — | edge_text | 新增，默认 NULL |
| — | weight | 新增，默认 NULL |
| — | valid_from | 新增，默认 NULL |
| — | valid_to | 新增，默认 NULL |
| — | confidence | 新增，默认 1.0 |
| — | source_pipeline | 新增，默认 "migration" |
| — | source_content_hash | 新增，默认 NULL |

### DuckDB → ChromaDB 向量

当前 LocalVectorStore 内存数据无法导出，需要重新嵌入：

```
1. 从 DuckDB entities 读取所有实体
2. 对每个实体的 name 生成嵌入 → entity_name 集合
3. 对每个实体的 attributes 生成摘要文本 → entity_summary 集合
4. 从 DuckDB relations 读取所有关系
5. 对每个关系的 relation_type 生成嵌入 → edge_relationship_name 集合
6. 关系的 edge_text 为空 → edge_text 集合暂不填充
```

### DuckDB → SQLite 元数据

| DuckDB 表 | SQLite 表 | 转换规则 |
|-----------|----------|---------|
| — | schema_versions | 初始化 version=1 |
| — | audit_log | 为迁移操作生成审计记录 |
| — | pipeline_runs | 记录迁移管道运行 |
| — | file_hashes | 需要重新扫描文件生成哈希 |
| — | contradiction_reports | 无历史数据，空表 |
| — | datasets | 需要手动创建数据集记录 |
| — | knowledge_fragments | 无 DuckDB 对应表，空表 |

---

## 迁移脚本规范

### 目的

定义迁移脚本的接口、执行流程和校验机制。

### 接口

```python
class MigrationScript(ABC):
    @abstractmethod
    async def migrate(self, source_config: StorageConfig, target_config: StorageConfig) -> MigrationResult: ...

    @abstractmethod
    async def validate(self, source_config: StorageConfig, target_config: StorageConfig) -> ValidationResult: ...

    @abstractmethod
    async def rollback(self, target_config: StorageConfig) -> None: ...

@dataclass
class MigrationResult:
    migrated_count: int
    failed_count: int
    duration_seconds: float
    errors: list[str]

@dataclass
class ValidationResult:
    source_count: int
    target_count: int
    missing_count: int
    extra_count: int
    consistency_rate: float
```

### 执行流程

```
1. 连接源 DuckDB
2. 连接目标 KuzuDB / ChromaDB / SQLite
3. 初始化目标 Schema
4. 分批读取源数据（batch_size=1000）
5. 转换数据格式
6. 写入目标引擎
7. 记录迁移进度
8. 执行数据校验
9. 生成迁移报告
```

### 校验机制

```
1. 计数校验：源表行数 = 目标表行数
2. 抽样校验：随机抽取 100 条记录，对比源和目标
3. 引用完整性校验：所有 from_id / to_id 在目标中存在
4. 向量校验：ChromaDB 集合记录数 = 预期数量
5. 元数据校验：SQLite 表行数 = 预期数量
```

---

## 回滚计划

### 触发条件

| # | 条件 | 动作 |
|---|------|------|
| 1 | 迁移数据一致性率 < 99% | 停止迁移，回滚目标引擎 |
| 2 | 迁移过程中源数据损坏 | 停止迁移，从备份恢复源数据 |
| 3 | 并行运行期间新引擎查询结果与 DuckDB 差异 > 1% | 切回 DuckDB 读取 |
| 4 | 切换后关键业务功能异常 | 切回 DuckDB 读写 |

### 回滚步骤

```
Phase 3 回滚（切换后）：
  1. 停止新引擎写入
  2. 恢复 DuckDB 读写
  3. 通知所有服务切换回 DuckDB
  4. 保留新引擎数据供分析

Phase 2 回滚（并行运行期间）：
  1. 停止双写
  2. 切回 DuckDB 读取
  3. 清理新引擎数据
  4. 修复问题后重新迁移

Phase 1 回滚（迁移期间）：
  1. 停止迁移脚本
  2. 清理目标引擎数据（CALL clear_db()）
  3. 清理 SQLite 数据（DROP 所有表）
  4. 清理 ChromaDB 数据（DELETE 所有集合）
  5. 重新迁移
```

### 数据备份

```
迁移前：
  1. DuckDB 数据文件完整复制 → data/backup/duckdb/
  2. 记录 DuckDB 各表行数 → migration_snapshot.json
  3. 记录 LocalVectorStore 向量数量 → migration_snapshot.json

迁移后：
  1. KuzuDB 数据文件完整复制 → data/backup/kuzu/
  2. SQLite 数据文件完整复制 → data/backup/sqlite/
  3. ChromaDB 数据目录完整复制 → data/backup/chroma/
  4. 校验报告 → migration_report.json
```

---

## 迁移时间估算

| 阶段 | 数据量 | 预估时间 | 说明 |
|------|--------|---------|------|
| Phase 0 准备 | — | 1 天 | 部署、Schema 初始化、脚本编写 |
| Phase 1 数据迁移 | 10K 实体 + 50K 关系 | 2-4 小时 | DuckDB→KuzuDB 批量写入 |
| Phase 1 向量重新嵌入 | 10K 实体 | 1-2 小时 | OpenAI API 调用，受速率限制 |
| Phase 2 并行运行 | — | 3-7 天 | 观察数据一致性 |
| Phase 3 切换 | — | 1 天 | 停写→切换→验证 |
| Phase 4 清理 | — | 1 天 | 删除双写逻辑 |

---

## 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|------|------|------|---------|
| 1 | KuzuDB UNWIND+MERGE write-write conflict | 高 | 迁移中断 | 端点分区批处理 |
| 2 | 向量重新嵌入 API 速率限制 | 中 | 延长迁移时间 | 批量请求 + 指数退避 |
| 3 | DuckDB MAP 类型与 KuzuDB MAP 类型不兼容 | 中 | 数据转换错误 | 预先测试类型转换 |
| 4 | 并行运行期间双写性能下降 | 中 | 服务延迟增加 | 异步双写 + 队列缓冲 |
| 5 | 迁移后查询结果差异 | 低 | 业务逻辑异常 | 抽样对比 + 自动化测试 |

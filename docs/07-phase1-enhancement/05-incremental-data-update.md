# 05: 增量数据更新机制设计

---
status: draft
phase: phase1
source_of_truth: true   # [单一事实源] 增量数据更新机制的唯一规范
last_verified: 2026-04-13
verified_against: docs-only
related_docs:
  - ../07-phase1-enhancement/04-dataset-management.md
  - ../05-schema-v2/06-dataset-and-sync.md
  - ../05-schema-v2/08-version-management.md
  - ../06-module-detailed-design/02-instance-management.md
related_adrs: []
---

## 1. 背景与动机

### 1.1 当前状态

当前数据导入机制是**全量覆盖**:

```
instances.yaml (50个实体)
  → 全量解析
  → INSERT OR REPLACE INTO entities (覆盖所有)
```

**问题**:

| 问题 | 影响 |
|------|------|
| 无法识别变更 | 不知道哪些实体新增/修改/删除 |
| 无变更追踪 | 没有审计日志记录"什么时间谁改了什么" |
| 无差异比对 | 无法知道新旧数据之间的具体差异 |
| 无影响传播 | 实体属性变更后，依赖它的指标/分类/规则结果不会自动失效 |
| 无回滚能力 | 覆盖后无法恢复到之前的状态 |

### 1.2 目标

建立**增量数据更新机制**，支持：

1. **变更检测** —— 自动识别新增/修改/删除
2. **差异比对** —— 列出每个字段的变化详情
3. **增量导入** —— 只写入有变化的实体
4. **影响传播** —— 变更自动触发下游指标/分类失效
5. **变更审计** —— 完整的变更历史记录
6. **回滚支持** —— 可回滚到任意版本

## 2. 核心概念

### 2.1 变更类型

```python
class ChangeType(str, Enum):
    """实体变更类型。"""
    CREATED = "created"       # 新增实体
    UPDATED = "updated"       # 修改实体 (属性变化)
    DELETED = "deleted"       # 删除实体
    UNCHANGED = "unchanged"   # 无变化
```

### 2.2 变更记录

```python
class EntityChange(BaseModel):
    """单条实体变更记录。"""
    entity_id: str
    concept: str                          # 实体类型
    change_type: ChangeType

    # 变更详情 (仅 UPDATED 时)
    field_changes: list[FieldChange] = Field(default_factory=list)

    # 元数据
    source: str                           # "file_import" | "api" | "manual"
    dataset_id: str | None = None         # 来源数据集
    source_line: int | None = None         # 文件行号
    timestamp: str
    actor: str                            # 操作者 (用户ID 或 "system")

class FieldChange(BaseModel):
    """字段级变更。"""
    field_name: str
    old_value: Any | None                 # None 表示字段被删除
    new_value: Any | None                 # None 表示字段被新增
```

### 2.3 变更批次

```python
class ChangeBatch(BaseModel):
    """一次导入操作的变更批次。"""
    batch_id: str                         # UUID
    space_id: str

    # 变更统计
    summary: ChangeSummary

    # 变更详情
    changes: list[EntityChange] = Field(default_factory=list)

    # 来源信息
    source: str
    source_description: str | None = None
    dataset_id: str | None = None

    # 影响传播
    impact_analysis: ImpactAnalysis | None = None

    # 版本
    version_before: int
    version_after: int

    timestamp: str
    actor: str

class ChangeSummary(BaseModel):
    """变更统计。"""
    created: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    total: int = 0

class ImpactAnalysis(BaseModel):
    """变更影响分析。"""
    affected_entities: list[str]         # 受影响的关联实体
    affected_metrics: list[str]          # 需要重新计算的指标
    affected_categories: list[str]       # 需要重新归类的维度
    affected_rules: list[str]            # 需要重新执行的规则
    estimated_recompute_time_ms: float    # 预估重算时间
```

## 3. 差异比对算法

### 3.1 实体级比对

```python
class EntityDiffer:
    """实体差异比对器。"""

    def diff(
        self,
        old_entities: dict[str, EntityInstance],    # entity_id → EntityInstance
        new_entities: dict[str, EntityInstance],
    ) -> list[EntityChange]:
        """比对两组实体, 返回变更列表。"""
        changes = []

        old_ids = set(old_entities.keys())
        new_ids = set(new_entities.keys())

        # 新增
        for entity_id in new_ids - old_ids:
            changes.append(EntityChange(
                entity_id=entity_id,
                concept=new_entities[entity_id].concept,
                change_type=ChangeType.CREATED,
                timestamp=datetime.utcnow().isoformat(),
            ))

        # 删除
        for entity_id in old_ids - new_ids:
            changes.append(EntityChange(
                entity_id=entity_id,
                concept=old_entities[entity_id].concept,
                change_type=ChangeType.DELETED,
                timestamp=datetime.utcnow().isoformat(),
            ))

        # 修改 (逐字段比对)
        for entity_id in old_ids & new_ids:
            old_data = old_entities[entity_id].data
            new_data = new_entities[entity_id].data

            field_changes = self._diff_fields(old_data, new_data)
            if field_changes:
                changes.append(EntityChange(
                    entity_id=entity_id,
                    concept=new_entities[entity_id].concept,
                    change_type=ChangeType.UPDATED,
                    field_changes=field_changes,
                    timestamp=datetime.utcnow().isoformat(),
                ))
            else:
                changes.append(EntityChange(
                    entity_id=entity_id,
                    concept=new_entities[entity_id].concept,
                    change_type=ChangeType.UNCHANGED,
                    timestamp=datetime.utcnow().isoformat(),
                ))

        return changes

    def _diff_fields(
        self, old_data: dict, new_data: dict
    ) -> list[FieldChange]:
        """递归比对两个字典的字段差异。"""
        field_changes = []
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val == new_val:
                continue

            if key not in old_data:
                # 新增字段
                field_changes.append(FieldChange(
                    field_name=key, old_value=None, new_value=new_val
                ))
            elif key not in new_data:
                # 删除字段
                field_changes.append(FieldChange(
                    field_name=key, old_value=old_val, new_value=None
                ))
            elif isinstance(old_val, dict) and isinstance(new_val, dict):
                # 嵌套对象: 递归比对
                nested = self._diff_fields(old_val, new_val)
                for nested_change in nested:
                    field_changes.append(FieldChange(
                        field_name=f"{key}.{nested_change.field_name}",
                        old_value=nested_change.old_value,
                        new_value=nested_change.new_value,
                    ))
            else:
                # 值变化
                field_changes.append(FieldChange(
                    field_name=key, old_value=old_val, new_value=new_val
                ))

        return field_changes
```

### 3.2 影响传播分析

```python
class ImpactAnalyzer:
    """变更影响传播分析器。"""

    def __init__(self, schema: KGMLSchema):
        self.schema = schema

    def analyze(
        self,
        changes: list[EntityChange],
        space_id: str,
    ) -> ImpactAnalysis:
        """分析变更对下游的影响。"""
        affected_entities = set()
        affected_metrics = set()
        affected_categories = set()
        affected_rules = set()

        for change in changes:
            if change.change_type == ChangeType.UNCHANGED:
                continue

            entity_id = change.entity_id
            concept = change.concept

            # 1. 找到关联实体 (通过关系)
            affected_entities.add(entity_id)

            # 2. 找到依赖此实体的指标
            for metric in self.schema.metrics:
                if self._metric_depends_on_entity(metric, concept, change.field_changes):
                    affected_metrics.add(metric.id)

            # 3. 找到依赖此实体的分类
            for cat_dim in self.schema.categorizations.dimensions:
                if cat_dim.applicable_to and any(
                    a.object_type == concept for a in cat_dim.applicable_to
                ):
                    affected_categories.add(cat_dim.id)

            # 4. 找到依赖此实体的规则
            for rule in self.schema.rules:
                if rule.scope and concept in rule.scope.get("entity_types", []):
                    affected_rules.add(rule.id)

        # 5. 找到关联实体
        # (需要查询存储层获取关系链上的实体)

        # 6. 估算重算时间
        estimated_time = (
            len(affected_metrics) * 50 +     # 每个指标 ~50ms
            len(affected_categories) * 20 +   # 每个分类 ~20ms
            len(affected_rules) * 100          # 每个规则 ~100ms
        )

        return ImpactAnalysis(
            affected_entities=list(affected_entities),
            affected_metrics=list(affected_metrics),
            affected_categories=list(affected_categories),
            affected_rules=list(affected_rules),
            estimated_recompute_time_ms=estimated_time,
        )
```

## 4. 存储层

### 4.1 DuckDB 表设计

```sql
-- 变更批次记录
CREATE TABLE IF NOT EXISTS change_batches (
    batch_id VARCHAR PRIMARY KEY,
    space_id VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    source_description VARCHAR,
    dataset_id VARCHAR,
    created_count INTEGER DEFAULT 0,
    updated_count INTEGER DEFAULT 0,
    deleted_count INTEGER DEFAULT 0,
    unchanged_count INTEGER DEFAULT 0,
    version_before INTEGER,
    version_after INTEGER,
    impact_json JSON,                     -- ImpactAnalysis 序列化
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor VARCHAR
);

CREATE INDEX idx_batches_space ON change_batches(space_id);

-- 变更明细记录
CREATE TABLE IF NOT EXISTS entity_changes (
    id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    concept VARCHAR NOT NULL,
    change_type VARCHAR NOT NULL,         -- created/updated/deleted/unchanged
    field_changes_json JSON,             -- list[FieldChange] 序列化
    source VARCHAR,
    source_line INTEGER,
    dataset_id VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor VARCHAR
);

CREATE INDEX idx_changes_batch ON entity_changes(batch_id);
CREATE INDEX idx_changes_entity ON entity_changes(entity_id);

-- 实体版本快照 (存储实体完整数据的版本)
CREATE TABLE IF NOT EXISTS entity_versions (
    id VARCHAR PRIMARY KEY,
    entity_id VARCHAR NOT NULL,
    concept VARCHAR NOT NULL,
    data JSON NOT NULL,                   -- 完整实体数据快照
    version INTEGER NOT NULL,
    batch_id VARCHAR,                     -- 关联变更批次
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_versions_entity ON entity_versions(entity_id, version);
```

## 5. 服务层

```python
# services/ingestion_service.py (扩展)

class IngestionService:
    """数据导入服务 —— 支持增量更新。"""

    async def import_with_diff(
        self,
        space_id: str,
        entities: list[EntityInstance],
        relations: list[RelationInstance] | None = None,
        source: str = "file_import",
        source_description: str | None = None,
        dataset_id: str | None = None,
        actor: str = "system",
        dry_run: bool = False,
    ) -> IngestionResult:
        """增量导入数据。

        流程:
        1. 加载当前实体快照
        2. 差异比对
        3. 影响分析
        4. [可选] 执行写入
        5. 记录变更审计
        6. 失效下游缓存
        """
        # Step 1: 加载当前数据
        current_entities = await self._load_current_entities(space_id)

        # Step 2: 差异比对
        new_entity_map = {e.entity_id: e for e in entities}
        differ = EntityDiffer()
        changes = differ.diff(current_entities, new_entity_map)

        # Step 3: 影响分析
        impact = self.impact_analyzer.analyze(changes, space_id)

        # Step 4: 执行写入 (非 dry_run)
        if not dry_run:
            await self._apply_changes(space_id, changes, new_entity_map)
            if relations:
                for rel in relations:
                    await self.storage.save_relation(rel)

        # Step 5: 记录审计
        batch_id = str(uuid.uuid4())
        await self._record_change_batch(
            batch_id, space_id, changes, source,
            source_description, dataset_id, impact, actor,
        )

        # Step 6: 失效缓存
        await self._invalidate_downstream(impact, space_id)

        summary = ChangeSummary(
            created=sum(1 for c in changes if c.change_type == ChangeType.CREATED),
            updated=sum(1 for c in changes if c.change_type == ChangeType.UPDATED),
            deleted=sum(1 for c in changes if c.change_type == ChangeType.DELETED),
            unchanged=sum(1 for c in changes if c.change_type == ChangeType.UNCHANGED),
            total=len(changes),
        )

        return IngestionResult(
            batch_id=batch_id,
            summary=summary,
            changes=[c for c in changes if c.change_type != ChangeType.UNCHANGED],
            impact=impact,
            dry_run=dry_run,
        )

    async def rollback(
        self, space_id: str, batch_id: str
    ) -> RollbackResult:
        """回滚到指定变更批次之前的状态。

        流程:
        1. 获取 batch 对应的变更列表
        2. 反向执行变更 (created→delete, deleted→create, updated→restore)
        3. 失效下游缓存
        """
        # 获取变更记录
        changes = await self.storage.get_entity_changes(batch_id)
        if not changes:
            raise BatchNotFoundError(batch_id)

        reverted = 0
        for change in changes:
            entity_id = change.entity_id
            concept = change.concept

            if change.change_type == ChangeType.CREATED:
                # 回滚: 删除
                await self.storage.delete_entity(entity_id)
                reverted += 1
            elif change.change_type == ChangeType.DELETED:
                # 回滚: 从版本快照恢复
                version = await self._get_version_before_batch(entity_id, batch_id)
                if version:
                    snapshot = await self.storage.get_entity_version(entity_id, version)
                    if snapshot:
                        await self.storage.save_entity(EntityInstance(
                            concept=concept,
                            entity_id=entity_id,
                            data=snapshot.data,
                        ))
                        reverted += 1
            elif change.change_type == ChangeType.UPDATED:
                # 回滚: 从版本快照恢复旧值
                version = await self._get_version_before_batch(entity_id, batch_id)
                if version:
                    snapshot = await self.storage.get_entity_version(entity_id, version)
                    if snapshot:
                        await self.storage.save_entity(EntityInstance(
                            concept=concept,
                            entity_id=entity_id,
                            data=snapshot.data,
                        ))
                        reverted += 1

        return RollbackResult(reverted=reverted)
```

## 6. API 设计

```
# 增量导入
POST   /v1/management/{spaceId}/ingestion/incremental
# Body: {
#   "entities": [...],
#   "relations": [...],
#   "source": "file_import",
#   "source_description": "从ERP同步",
#   "dataset_id": "ds_erp_companies",
#   "dry_run": false
# }
# Response: IngestionResult (含 changes + impact)

# 变更历史
GET    /v1/management/{spaceId}/ingestion/history
# ?entity_id=xxx&change_type=updated&limit=50

# 变更详情
GET    /v1/management/{spaceId}/ingestion/batches/{batchId}

# 实体变更历史
GET    /v1/management/{spaceId}/entities/{entityId}/changes
# ?limit=20

# 实体版本历史
GET    /v1/management/{spaceId}/entities/{entityId}/versions
# ?limit=10

# 回滚
POST   /v1/management/{spaceId}/ingestion/rollback
# Body: { "batch_id": "xxx" }

# 影响分析 (预检)
POST   /v1/management/{spaceId}/ingestion/analyze-impact
# Body: { "entities": [...], "changes": [...] }
# Response: ImpactAnalysis (不执行, 只分析)
```

## 7. 缓存失效策略

```
实体属性变更
  │
  ├─→ 标记实体所有 computed_metrics 为 expired
  │     SELECT metric_name FROM computed_metrics
  │     WHERE entity_id = ? AND metric_type IN ('derived', 'composite', 'graph')
  │
  ├─→ 标记实体所有 category_tags 为 stale
  │     UPDATE category_tags SET confidence = 0.5
  │     WHERE entity_id = ?
  │
  └─→ 记录需要重新计算的指标列表
        供下次 analysis 执行时判断是否需要重算
```

```python
async def _invalidate_downstream(self, impact: ImpactAnalysis, space_id: str):
    """失效受影响的缓存。"""
    for entity_id in impact.affected_entities:
        # 失效指标缓存
        await self.storage.invalidate_metrics(entity_id)

        # 标记分类标签需要重新计算
        await self.storage.mark_categories_stale(entity_id)

    # 记录待重算列表 (下次 analysis 时触发)
    await self.storage.save_recompute_queue(
        space_id=space_id,
        entity_ids=impact.affected_entities,
        metric_ids=impact.affected_metrics,
        category_ids=impact.affected_categories,
        rule_ids=impact.affected_rules,
    )
```

## 8. 验收场景

### 场景 1: 首次全量导入

```
Given: 空 DuckDB, entities.yaml 含 8 个 Company
When: 增量导入
Then:
  - 8 条 CREATED 变更
  - batch_id 已记录
  - 实体版本 v1 已保存
```

### 场景 2: 修改后增量导入

```
Given: 已有 8 个 Company (v1)
When: 更新 entities.yaml (修改3个, 新增1个, 删除1个) 后增量导入
Then:
  - 3 条 UPDATED 变更 (含 field_changes)
  - 1 条 CREATED 变更
  - 1 条 DELETED 变更
  - 3 条 UNCHANGED 变更
  - 实体版本 v2 已保存
  - 影响分析列出受影响的指标和规则
```

### 场景 3: 影响传播

```
Given: Company SUP_001 的 registered_capital 从 1000万 改为 500万
When: 增量导入
Then:
  - 影响分析: affected_metrics = ["credit_limit", "debt_ratio"]
  - 对应指标的缓存已失效
  - 下次分析时自动重新计算
```

### 场景 4: 回滚

```
Given: batch_id = "xxx" 包含 3 个 UPDATED + 1 个 CREATED
When: 执行回滚
Then:
  - 3 个 UPDATED 实体恢复到 v_before 数据
  - 1 个 CREATED 实体被删除
  - 缓存再次失效
```

### 场景 5: Dry-run 预检

```
Given: 准备更新 100 个实体
When: dry_run=true 执行
Then:
  - 返回变更列表和影响分析
  - 数据库无任何变化
  - 用户可审查后决定是否执行
```

---

*文档结束*

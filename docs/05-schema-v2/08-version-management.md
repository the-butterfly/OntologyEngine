# 版本管理

> **Status**: v1.0
> **Date**: 2026-04-12

## 1. 设计原则

### 1.1 分层版本

Schema v2 采用**分层版本管理**策略：

```
语义空间
├── L1_fact_objects ──────── 版本历史 (完整快照)
├── L2_categorizations ───── 版本历史 (完整快照)
├── L3_analytical_elements ─ 版本历史 (完整快照)
├── L4_business_logic
│   ├── rule_definitions ─── 版本历史 (完整快照)
│   └── rule_logics ─────── 版本历史 (增量 diff)
└── Instances
    └── entities ─────────── 版本历史 (增量 diff)
```

### 1.2 版本策略选择

| 层 | 存储策略 | 原因 |
|---|----------|------|
| L1-L4 声明 | **完整快照** | 容量小，变更不频繁，需要精确回滚 |
| L4 rule_logics | **增量 diff** | 变更频繁，但需要保留历史 |
| Instances | **增量 diff** | 数据量大，但记录数有上限 |

## 2. 版本记录结构

### 2.1 层版本记录

```yaml
layer_version:
  layer: string                # L1_fact_objects | L2_categorizations | ...
  version: integer             # 版本号，从 1 开始
  snapshot: object             # 该层的完整数据快照
  change_description: string | null
  created_at: string           # ISO 时间
  created_by: string           # 用户或系统
  change_type: create | update | delete
  change_stats:                # 变更统计
    added: integer
    modified: integer
    deleted: integer
```

### 2.2 实例变更记录

```yaml
instance_diff:
  entity_id: string
  layer: L1 | L2 | L3 | L4_instances
  version: integer
  diff:
    - field: string
      action: add | update | delete
      old_value: any | null
      new_value: any | null
  timestamp: string
  source: sync | manual | import
```

### 2.3 实例版本历史 (简化)

```yaml
# 实际存储：只记录变更，不记录完整快照
entity_versions:
  entity_id: SUP_001

  current_version: 5
  current_snapshot:             # 最新版本的完整数据
    entity_id: SUP_001
    _concept: Supplier
    name: "XX 供应商"
    registered_capital: 10000000
    ...

  versions:
    1:
      timestamp: "2026-01-01T00:00:00Z"
      source: initial_import
      diff_count: 1
    2:
      timestamp: "2026-02-15T10:30:00Z"
      source: manual_update
      diff:
        - field: registered_capital
          action: update
          old_value: 5000000
          new_value: 8000000
    3:
      timestamp: "2026-03-20T14:00:00Z"
      source: sync(erp_suppliers)
      diff:
        - field: annual_revenue
          action: update
          old_value: 50000000
          new_value: 75000000
    ...
```

## 3. 版本操作

### 3.1 创建版本快照

```python
async def create_layer_snapshot(space_id: str, layer: str, description: str = None):
    """
    1. 读取当前层数据
    2. 生成新版本号
    3. 存储完整快照
    4. 返回版本记录
    """
    version_record = {
        "layer": layer,
        "version": current_version + 1,
        "snapshot": current_data,
        "change_description": description,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": get_current_user(),
    }
    await storage.save_version(version_record)
    return version_record
```

### 3.2 回滚

```python
async def rollback_layer(space_id: str, layer: str, target_version: int):
    """
    1. 验证目标版本存在
    2. 评估影响范围（哪些实体/规则会受影响）
    3. 创建回滚前快照
    4. 恢复目标版本数据
    5. 记录回滚操作
    """
    target = await storage.get_version(space_id, layer, target_version)
    current = await storage.get_current_version(space_id, layer)

    # 影响分析
    impact = analyze_impact(current, target)

    if impact.risk_level > threshold:
        raise RollbackRiskExceeded(f"风险等级: {impact.risk_level}")

    # 执行回滚
    await storage.restore_version(space_id, layer, target_version)
    await create_layer_snapshot(space_id, layer, f"回滚到 v{target_version}")
```

### 3.3 影响分析

```yaml
impact_report:
  target_version: integer
  target_layer: string

  affected:
    entities: list[string]      # 受影响的实体ID
    rules: list[string]         # 受影响的规则ID
    dimensions: list[string]    # 受影响的维度

  risk_level: low | medium | high | critical

  details:
    - entity: SUP_001
      reason: "当前版本的 category_tag '行业:制造业' 在目标版本不存在"
    - rule: R001
      reason: "引用的 metric 'credit_score' 在目标版本中已删除"
```

## 4. 实例版本管理

### 4.1 版本限制

```yaml
# 每个实体的版本数限制
instance_version_limits:
  max_versions_per_entity: 100  # 单个实体的最大版本数
  max_total_records: 100000    # 空间内实例版本记录总数
  on_exceed: oldest | archive   # 超过时的处理策略

# 默认行为
# 1. 单实体版本超限 → 删除最老版本
# 2. 全局记录超限 → 按时间删除最老记录
```

### 4.2 实例版本查询

```python
# 查询实体的版本历史
GET /v1/management/{spaceId}/instances/entities/{entityId}/versions

# 返回
{
  "entity_id": "SUP_001",
  "current_version": 5,
  "versions": [
    {
      "version": 5,
      "timestamp": "2026-04-10T10:00:00Z",
      "source": "sync(erp_suppliers)",
      "change_summary": {"modified": 2, "added": 0, "deleted": 0}
    },
    ...
  ]
}
```

### 4.3 版本对比

```python
# 对比两个版本
GET /v1/management/{spaceId}/instances/entities/{entityId}/versions/compare?from=3&to=5

# 返回
{
  "entity_id": "SUP_001",
  "from_version": 3,
  "to_version": 5,
  "diff": [
    {
      "field": "registered_capital",
      "from": 5000000,
      "to": 10000000,
      "action": "update"
    },
    {
      "field": "annual_revenue",
      "from": null,
      "to": 75000000,
      "action": "add"
    }
  ]
}
```

## 5. 空间状态与版本

### 5.1 PUBLISHED 快照

当空间从 ACTIVE 发布时：

```
状态转换: ACTIVE → PUBLISHED

执行:
1. 为 L1-L4 创建完整快照
2. 为 Instances 创建增量快照
3. 快照版本标记为 immutable
4. 记录发布历史
```

### 5.2 回滚与激活

```
ARCHIVED → ACTIVE (通过 rollback)

执行:
1. 选择要恢复的版本
2. 影响分析
3. 确认回滚
4. 恢复数据
5. 状态变更为 ACTIVE
```

## 6. API 设计

### 6.1 版本查询

```
GET  /v1/management/{spaceId}/versions
GET  /v1/management/{spaceId}/versions/{layer}
GET  /v1/management/{spaceId}/versions/{layer}/{version}
```

### 6.2 版本操作

```
POST /v1/management/{spaceId}/versions/{layer}/snapshot
# Body:
{
  "description": "发布前快照"
}

POST /v1/management/{spaceId}/versions/{layer}/{version}/rollback

GET  /v1/management/{spaceId}/versions/{layer}/{version}/impact
```

### 6.3 实例版本

```
GET  /v1/management/{spaceId}/instances/entities/{entityId}/versions
GET  /v1/management/{spaceId}/instances/entities/{entityId}/versions/{version}
GET  /v1/management/{spaceId}/instances/entities/{entityId}/versions/compare?from=X&to=Y
```

---

*文档结束*

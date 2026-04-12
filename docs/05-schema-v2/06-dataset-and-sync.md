# 数据集与同步

> **Status**: v1.0
> **Date**: 2026-04-12

## 1. 概念定义

### 1.1 什么是 Dataset

Dataset (数据集) 是**外部数据源**的逻辑抽象，表示可以同步到语义空间的外部数据。

支持的类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| `postgresql` | 关系型数据库 | ERP系统、财务系统 |
| `mysql` | 关系型数据库 | CRM系统 |
| `file` | 文件 | CSV、JSON、Excel |
| `api` | REST API | 第三方数据服务 |
| `s3` | 对象存储 | S3、MinIO |

### 1.2 核心能力

1. **字段级映射**：精确控制字段对应关系
2. **全量同步**：一次性覆盖更新
3. **增量同步**：按时间/条件筛选更新
4. **版本追踪**：记录每次同步的历史

## 2. Dataset 声明

### 2.1 结构

```yaml
dataset:
  id: string                    # 全局唯一标识
  name: string                  # 显示名称
  description: string | null    # 描述

  # 数据源配置
  source:
    type: string                # postgresql | mysql | file | api | s3
    connection:                 # 类型相关的连接配置
      host: string
      port: integer
      database: string
      username: string
      password: string         # 或引用 secret
      # 或
      url: string              # file path 或 API URL

  # 数据集字段声明
  schema:
    fields:
      - name: string            # 字段名
        type: string            # string | integer | float | boolean | timestamp
        description: string
      - ...

  # 映射规则
  mapping_rules:
    - id: string                # 映射规则ID
      target_entity_type: string # 目标实体类型
      field_mappings:
        source_field: target_field
        ...
      filters:                 # 可选：同步时的筛选条件
        - field: string
          operator: string
          value: any
      enabled: boolean

  # 同步配置
  sync_config:
    mode: full | incremental    # 默认 full
    incremental:
      type: timestamp | conditions  # 增量类型
      timestamp_field: string   # 用于增量同步的时间戳字段
      last_sync: string         # ISO 时间
      conditions:               # 业务条件 (与 timestamp_field 二选一)
        - field: string
          operator: string
          value: any

    # 调度配置
    schedule:
      enabled: boolean
      cron: string              # 标准 cron 表达式
      timezone: string           # 默认 UTC

    # 记录数限制
    limits:
      max_records: integer      # 默认 100,000
      on_exceed: string         # truncate | skip | error

  status: active | paused | error
  created_at: string
  updated_at: string
```

### 2.2 字段映射示例

```yaml
dataset:
  id: erp_suppliers
  name: ERP 供应商数据
  source:
    type: postgresql
    connection:
      host: erp-db.company.com
      port: 5432
      database: erp
      username: readonly_user
      password: ${ERP_PASSWORD}

  schema:
    fields:
      - name: supplier_id
        type: string
        description: 供应商编码
      - name: supplier_name
        type: string
      - name: annual_revenue
        type: float
      - name: employee_count
        type: integer
      - name: industry_code
        type: string
      - name: registered_capital
        type: float
      - name: updated_at
        type: timestamp

  mapping_rules:
    - id: mapping_supplier
      target_entity_type: Supplier
      field_mappings:
        supplier_id: entity_id
        supplier_name: name
        annual_revenue: annual_revenue
        employee_count: employee_count
        industry_code: industry_category  # 字段映射
        registered_capital: registered_capital
      filters:
        - field: status
          operator: eq
          value: ACTIVE

  sync_config:
    mode: incremental
    incremental:
      type: timestamp
      timestamp_field: updated_at
      last_sync: "2026-04-01T00:00:00Z"
    limits:
      max_records: 100000
      on_exceed: truncate
```

## 3. 同步执行

### 3.1 全量同步

```python
async def sync_full(dataset_id: str):
    """
    1. 从 Dataset 拉取全部数据
    2. 按 mapping_rule 转换
    3. 对比现有实例，执行 upsert/delete
    4. 记录同步历史
    """
```

### 3.2 增量同步

**基于时间戳**:
```python
async def sync_incremental_timestamp(dataset_id: str, last_sync: datetime):
    """
    1. 查询 updated_at > last_sync 的记录
    2. 按 mapping_rule 转换
    3. 执行 upsert
    4. 更新 last_sync 时间戳
    """
```

**基于条件**:
```python
async def sync_incremental_conditions(dataset_id: str, conditions: list):
    """
    1. 按条件查询 Dataset 记录
    2. 按 mapping_rule 转换
    3. 执行 upsert
    4. 记录同步历史
    """
```

### 3.3 冲突处理

当 Dataset 数据与现有数据冲突时：

| 策略 | 说明 |
|------|------|
| `overwrite` | Dataset 数据覆盖现有数据 |
| `preserve` | 保留现有数据，忽略 Dataset 更新 |
| `merge` | 合并，Dataset 数据优先 |

## 4. 同步历史

每次同步都会记录历史：

```yaml
sync_history:
  - id: sync_001
    dataset_id: erp_suppliers
    triggered_by: manual | scheduled
    started_at: "2026-04-12T10:00:00Z"
    completed_at: "2026-04-12T10:00:30Z"

    mode: incremental
    parameters:
      last_sync: "2026-04-01T00:00:00Z"
      conditions: null

    stats:
      records_read: 1500
      records_created: 120
      records_updated: 350
      records_skipped: 30
      records_truncated: 0

    status: success | partial | failed
    error: null | string
```

### 4.1 记录数限制

```
配置: max_records = 100,000, on_exceed = truncate

处理流程:
1. 读取 Dataset 数据 (已排序 by updated_at DESC)
2. 前 100,000 条 → 同步
3. 100,001+ 条 → 按 on_exceed 处理:
   - truncate: 丢弃，不记录
   - skip: 丢弃，记录到 skipped
   - error: 中断同步，抛出异常
```

## 5. API 设计

### 5.1 Dataset 管理

```
POST   /v1/management/{spaceId}/datasets
GET    /v1/management/{spaceId}/datasets
GET    /v1/management/{spaceId}/datasets/{datasetId}
PUT    /v1/management/{spaceId}/datasets/{datasetId}
DELETE /v1/management/{spaceId}/datasets/{datasetId}

# 映射规则
GET    /v1/management/{spaceId}/datasets/{datasetId}/mappings
POST   /v1/management/{spaceId}/datasets/{datasetId}/mappings
PUT    /v1/management/{spaceId}/datasets/{datasetId}/mappings/{mappingId}
DELETE /v1/management/{spaceId}/datasets/{datasetId}/mappings/{mappingId}

# 同步配置
GET    /v1/management/{spaceId}/datasets/{datasetId}/sync-config
PUT    /v1/management/{spaceId}/datasets/{datasetId}/sync-config
```

### 5.2 同步执行

```
POST /v1/management/{spaceId}/datasets/{datasetId}/sync
# Body:
{
  "mode": "full" | "incremental",
  "override_last_sync": "2026-04-01T00:00:00Z"  # 可选
}

GET  /v1/management/{spaceId}/datasets/{datasetId}/sync/history
GET  /v1/management/{spaceId}/datasets/{datasetId}/sync/history/{syncId}
```

### 5.3 请求/响应示例

**触发同步**:
```json
POST /v1/management/{spaceId}/datasets/erp_suppliers/sync
{
  "mode": "incremental"
}

Response:
{
  "success": true,
  "data": {
    "sync_id": "sync_001",
    "status": "running",
    "started_at": "2026-04-12T10:00:00Z"
  }
}
```

**查询同步历史**:
```json
GET /v1/management/{spaceId}/datasets/erp_suppliers/sync/history

Response:
{
  "success": true,
  "data": [
    {
      "id": "sync_001",
      "triggered_by": "manual",
      "started_at": "2026-04-12T10:00:00Z",
      "completed_at": "2026-04-12T10:00:30Z",
      "mode": "incremental",
      "stats": {
        "records_read": 1500,
        "records_created": 120,
        "records_updated": 350,
        "records_skipped": 30
      },
      "status": "success"
    }
  ]
}
```

## 6. 权限模型

Dataset 可能包含敏感数据，权限控制：

| 操作 | 权限 |
|------|------|
| 查看 Dataset 配置 | `dataset:read` |
| 创建/修改 Dataset | `dataset:write` |
| 执行同步 | `dataset:sync` |
| 查看同步历史 | `dataset:read` |
| 删除 Dataset | `dataset:delete` |

---

*文档结束*

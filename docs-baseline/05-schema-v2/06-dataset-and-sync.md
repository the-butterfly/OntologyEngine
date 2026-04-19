# 数据集与同步

---
status: proposed
phase: phase2
source_of_truth: false
last_verified: 2026-04-12
verified_against: docs-only
related_docs:
  - 00-overview.md
  - 00b-semantic-space-architecture.md
  - 01-fact-objects.md
  - 08-version-management.md
---

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

## 6. 能力边界与阶段规划 **[单一事实源]**

本文档作为平台化数据集与同步能力的唯一规范入口，明确区分当前实现、可选扩展与未来规划。

### 6.1 能力矩阵

| 能力 | Current (当前) | Optional (可选) | Future (未来) |
|------|---------------|-----------------|---------------|
| 外部数据库同步 | 占位接口 | PostgreSQL/MySQL 适配器 | 完整 CDC |
| 文件导入 | CSV/JSON 本地导入 | S3 数据源 | 多源自动同步 |
| 计划任务 | 手动触发 | cron 表达式 | 完整调度器 |
| 数据版本 | 基础快照 | 增量 diff | 完整版本树 |
| 跨空间授权 | 概念设计 | 单空间授权 | 多空间聚合 |
| JWT/权限 | 无 | 基础 token | RBAC |

### 6.2 各能力详细说明

#### 6.2.1 外部数据库同步

| 维度 | 说明 |
|------|------|
| **Phase 1 实现范围** | 仅定义 `Dataset` 结构规范与占位接口，不实现具体连接逻辑 |
| **依赖条件** | 存储层适配器接口 (`storage/base.py`) 完成外部数据源抽象 |
| **风险** | 外部连接配置涉及敏感信息存储，需先解决 secret 管理机制 |
| **Current** | Schema 定义支持 postgresql/mysql 类型，但无实际连接器 |
| **Optional** | 实现基于 `psycopg2` 和 `PyMySQL` 的基础适配器，支持简单查询 |
| **Future** | 基于 Debezium 或自研 CDC 的实时变更捕获 |

#### 6.2.2 文件导入

| 维度 | 说明 |
|------|------|
| **Phase 1 实现范围** | 支持本地 CSV/JSON 文件上传导入，最大 10MB |
| **依赖条件** | 文件上传 API 与临时存储机制 |
| **风险** | 大文件解析内存占用；字符编码检测复杂性 |
| **Current** | 本地文件路径读取，pandas/标准库解析 |
| **Optional** | 集成 boto3，支持 S3 预签名 URL 导入 |
| **Future** | 多源自动同步（文件系统监听、云存储事件触发） |

#### 6.2.3 计划任务

| 维度 | 说明 |
|------|------|
| **Phase 1 实现范围** | 仅支持手动触发同步，API 端点保留 schedule 配置字段但不执行 |
| **依赖条件** | 异步任务队列（APScheduler/Celery）选型与部署 |
| **风险** | 调度器与多实例部署时的分布式锁问题 |
| **Current** | `POST /datasets/{id}/sync` 手动触发 |
| **Optional** | 解析 cron 表达式，基于 APScheduler 单机调度 |
| **Future** | 分布式调度器，支持任务依赖、重试策略、监控告警 |

#### 6.2.4 数据版本

| 维度 | 说明 |
|------|------|
| **Phase 1 实现范围** | 同步历史记录，不包含数据版本 |
| **依赖条件** | 实例级版本管理模块实现 |
| **风险** | 版本存储空间膨胀，需设计保留策略 |
| **Current** | `sync_history` 表记录每次同步元数据 |
| **Optional** | 实例级增量 diff 存储，支持版本对比 |
| **Future** | 完整版本树，支持分支、回滚、合并 |

#### 6.2.5 跨空间授权

| 维度 | 说明 |
|------|------|
| **Phase 1 实现范围** | 仅在文档层面定义授权概念模型，无实现 |
| **依赖条件** | 多空间管理 UI 与权限服务 |
| **风险** | 授权粒度与性能权衡；授权传播复杂性 |
| **Current** | Schema 预留 `authorizations` 字段，无后端逻辑 |
| **Optional** | 单空间内角色-权限绑定，简单 ACL |
| **Future** | 跨空间资源聚合与细粒度 RBAC |

#### 6.2.6 JWT/权限

| 维度 | 说明 |
|------|------|
| **Phase 1 实现范围** | 无认证，或仅 API Key 级别简单鉴权 |
| **依赖条件** | 身份提供商集成决策 |
| **风险** | 过早引入复杂权限影响开发迭代速度 |
| **Current** | 无认证，或开发模式透传用户标识 |
| **Optional** | JWT 解析中间件，基础 token 验证 |
| **Future** | 完整 RBAC，支持角色继承、资源级权限、审计日志 |

### 6.3 决策原则

1. **本地优先**：Phase 1 仅实现本地文件与占位接口，外部连接推迟到 Phase 2
2. **显式禁用**：Optional/Future 能力在 Phase 1 代码中必须显式标记为 `NotImplementedError` 或配置关闭
3. **接口预留**：Future 能力在 API/Schema 中预留字段，但文档必须标注 `[预留]`

---

## 7. 权限模型

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

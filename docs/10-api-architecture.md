# API 架构

---
status: proposed
phase: phase2
source_of_truth: false
last_verified: 2026-04-12
verified_against: docs-only
related_docs:
  - 05-schema-v2/06-dataset-and-sync.md
  - 04-migration-and-gap/README.md
---

> **Status**: v1.0
> **Date**: 2026-04-12

> **平台化能力边界** **[待扩展]**
> 
> 本文档定义的 `/v1/management/` 与 `/v1/consumption/` 是目标态 API 结构。
> - **Current (当前)**：仅实现 `/v1/schema`、`/v1/entities` 等基础端点
> - **Optional (可选)**：Dataset 管理、版本管理 API（占位实现）
> - **Future (未来)**：完整的空间管理、授权、同步调度 API
> 
> 详细能力矩阵参见 [`05-schema-v2/06-dataset-and-sync.md`](./05-schema-v2/06-dataset-and-sync.md) 第 6 节

## 1. 架构概览

API 分为两个独立模块：

| 模块 | 前缀 | 用途 |
|------|------|------|
| 管理面 API | `/v1/management/` | Space/Schema/Instances/Datasets/Versions/Authorizations |
| 消费面 API | `/v1/consumption/` | Visualize/Execute/Simulate |

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer                              │
├────────────────────────┬────────────────────────────────────┤
│    Management API      │       Consumption API              │
│    /v1/management/     │       /v1/consumption/            │
├────────────────────────┼────────────────────────────────────┤
│                        │                                    │
│  Spaces (CRUD)         │  Views (CRUD)                     │
│  Schema (L1-L4)        │  Visualize                        │
│  Instances             │  Execute                           │
│  Datasets              │  Simulate                          │
│  Versions              │  Query (read-only)                │
│  Authorizations        │                                    │
│  Sync                  │                                    │
│                        │                                    │
└────────────────────────┴────────────────────────────────────┘
```

---

## 2. 管理面 API

### 2.1 Space 管理

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/spaces` | 创建管理空间 |
| `GET` | `/spaces` | 列出所有管理空间 |
| `GET` | `/spaces/{spaceId}` | 获取空间详情 |
| `PUT` | `/spaces/{spaceId}` | 更新空间元数据 |
| `DELETE` | `/spaces/{spaceId}` | 删除空间 |
| `POST` | `/spaces/{spaceId}/activate` | 激活空间 |
| `POST` | `/spaces/{spaceId}/archive` | 归档空间 |
| `POST` | `/spaces/{spaceId}/publish` | 发布版本快照 |

### 2.2 Schema 管理

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/schema` | 获取完整 Schema |
| `PUT` | `/{spaceId}/schema` | 更新完整 Schema |
| `PATCH` | `/{spaceId}/schema` | 部分更新 Schema |

#### L1: 事实对象

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/schema/L1/fact-objects` | 获取事实对象列表 |
| `POST` | `/{spaceId}/schema/L1/fact-objects` | 创建事实对象 |
| `PUT` | `/{spaceId}/schema/L1/fact-objects/{id}` | 更新事实对象 |
| `DELETE` | `/{spaceId}/schema/L1/fact-objects/{id}` | 删除事实对象 |

#### L2: 分类

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/schema/L2/categorizations` | 获取分类列表 |
| `POST` | `/{spaceId}/schema/L2/categorizations` | 创建分类 |
| `PUT` | `/{spaceId}/schema/L2/categorizations/{id}` | 更新分类 |
| `DELETE` | `/{spaceId}/schema/L2/categorizations/{id}` | 删除分类 |

#### L3: 分析要素

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/schema/L3/analytical-elements` | 获取分析要素列表 |
| `POST` | `/{spaceId}/schema/L3/analytical-elements` | 创建分析要素 |
| `PUT` | `/{spaceId}/schema/L3/analytical-elements/{id}` | 更新分析要素 |
| `DELETE` | `/{spaceId}/schema/L3/analytical-elements/{id}` | 删除分析要素 |

#### L4: 规则

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/schema/L4/rules` | 获取规则完整信息 |
| `GET` | `/{spaceId}/schema/L4/rules/definitions` | 获取规则声明列表 |
| `POST` | `/{spaceId}/schema/L4/rules/definitions` | 创建规则声明 |
| `GET` | `/{spaceId}/schema/L4/rules/definitions/{id}` | 获取规则声明 |
| `PUT` | `/{spaceId}/schema/L4/rules/definitions/{id}` | 更新规则声明 |
| `DELETE` | `/{spaceId}/schema/L4/rules/definitions/{id}` | 删除规则声明 |
| `GET` | `/{spaceId}/schema/L4/rules/logics` | 获取规则实例列表 |
| `POST` | `/{spaceId}/schema/L4/rules/logics` | 创建规则实例 |
| `GET` | `/{spaceId}/schema/L4/rules/logics/{id}` | 获取规则实例 |
| `PUT` | `/{spaceId}/schema/L4/rules/logics/{id}` | 更新规则实例 |
| `DELETE` | `/{spaceId}/schema/L4/rules/logics/{id}` | 删除规则实例 |

### 2.3 Instance 管理

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/instances/entities` | 获取实体实例列表 |
| `POST` | `/{spaceId}/instances/entities` | 创建实体实例 |
| `GET` | `/{spaceId}/instances/entities/{entityId}` | 获取实体详情 |
| `PUT` | `/{spaceId}/instances/entities/{entityId}` | 更新实体 |
| `DELETE` | `/{spaceId}/instances/entities/{entityId}` | 删除实体 |
| `GET` | `/{spaceId}/instances/entities/{entityId}/versions` | 获取版本历史 |
| `GET` | `/{spaceId}/instances/entities/{entityId}/versions/{v}` | 获取指定版本 |
| `GET` | `/{spaceId}/instances/entities/{entityId}/versions/compare` | 版本对比 |
| `GET` | `/{spaceId}/instances/category-tags` | 获取分类标签 |
| `POST` | `/{spaceId}/instances/category-tags` | 创建分类标签 |
| `GET` | `/{spaceId}/instances/metrics` | 获取指标值 |
| `POST` | `/{spaceId}/instances/metrics/compute` | 计算指标 |

### 2.4 Dataset 管理

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/datasets` | 获取数据集列表 |
| `POST` | `/{spaceId}/datasets` | 创建数据集 |
| `GET` | `/{spaceId}/datasets/{datasetId}` | 获取数据集详情 |
| `PUT` | `/{spaceId}/datasets/{datasetId}` | 更新数据集 |
| `DELETE` | `/{spaceId}/datasets/{datasetId}` | 删除数据集 |
| `GET` | `/{spaceId}/datasets/{datasetId}/mappings` | 获取映射规则 |
| `POST` | `/{spaceId}/datasets/{datasetId}/mappings` | 创建映射规则 |
| `PUT` | `/{spaceId}/datasets/{datasetId}/mappings/{mappingId}` | 更新映射规则 |
| `DELETE` | `/{spaceId}/datasets/{datasetId}/mappings/{mappingId}` | 删除映射规则 |
| `GET` | `/{spaceId}/datasets/{datasetId}/sync-config` | 获取同步配置 |
| `PUT` | `/{spaceId}/datasets/{datasetId}/sync-config` | 更新同步配置 |
| `POST` | `/{spaceId}/datasets/{datasetId}/sync` | 触发同步 |
| `GET` | `/{spaceId}/datasets/{datasetId}/sync/history` | 获取同步历史 |
| `GET` | `/{spaceId}/datasets/{datasetId}/sync/history/{syncId}` | 获取同步详情 |

### 2.5 版本管理

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/versions` | 获取所有层版本历史 |
| `GET` | `/{spaceId}/versions/{layer}` | 获取指定层版本历史 |
| `GET` | `/{spaceId}/versions/{layer}/{version}` | 获取指定版本 |
| `POST` | `/{spaceId}/versions/{layer}/snapshot` | 创建快照 |
| `POST` | `/{spaceId}/versions/{layer}/{version}/rollback` | 回滚到指定版本 |
| `GET` | `/{spaceId}/versions/{layer}/{version}/impact` | 评估回滚影响 |

### 2.6 授权管理

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/{spaceId}/authorizations` | 获取授权列表 |
| `POST` | `/{spaceId}/authorizations` | 创建授权 |
| `GET` | `/{spaceId}/authorizations/{authId}` | 获取授权详情 |
| `PUT` | `/{spaceId}/authorizations/{authId}` | 更新授权 |
| `DELETE` | `/{spaceId}/authorizations/{authId}` | 删除授权 |

---

## 3. 消费面 API

### 3.1 View 管理

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/views` | 创建消费视图 |
| `GET` | `/views` | 列出所有消费视图 |
| `GET` | `/views/{viewId}` | 获取视图详情 |
| `PUT` | `/views/{viewId}` | 更新视图 |
| `DELETE` | `/views/{viewId}` | 删除视图 |

### 3.2 可视化

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/views/{viewId}/visualize/schema-graph` | 获取 Schema 图数据 |
| `GET` | `/views/{viewId}/visualize/entity/{entityId}` | 获取实体详情 |
| `GET` | `views/{viewId}/visualize/rule-chain/{dimension}` | 获取规则链 DAG |

### 3.3 执行

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/views/{viewId}/execute/analyze` | 执行规则分析 |
| `POST` | `/views/{viewId}/execute/simulate` | What-if 模拟 |
| `GET` | `/views/{viewId}/execute/history` | 执行历史 |

### 3.4 查询

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/views/{viewId}/entities` | 查询实体（只读） |
| `GET` | `/views/{viewId}/entities/{entityId}` | 获取实体详情 |
| `GET` | `/views/{viewId}/metrics/{entityId}` | 获取指标值 |

---

## 4. 请求/响应格式

### 4.1 统一响应格式

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2026-04-12T10:00:00Z"
}
```

### 4.2 错误响应

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid field mappings",
    "details": [
      { "field": "field_mappings.supplier_id", "reason": "required" }
    ]
  },
  "timestamp": "2026-04-12T10:00:00Z"
}
```

### 4.3 分页

```json
{
  "success": true,
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5
    }
  }
}
```

---

## 5. 认证与权限

### 5.1 认证

- Bearer Token (JWT)
- Header: `Authorization: Bearer <token>`

### 5.2 权限

| 端点前缀 | 所需权限 |
|----------|----------|
| `/v1/management/` | `management:read` / `management:write` |
| `/v1/consumption/` | `consumption:read` / `consumption:execute` |

---

*文档结束*

# /v1/views 路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [02-api-redesign-proposal.md](02-api-redesign-proposal.md) | **last_verified**: 2026-04-19

---

## 目的

定义消费视图（View）的 API 路由。View 是 Semantic Space 的只读投影，供前端和 Agent 消费。View 在 Space 激活时自动创建，提供可视化、查询、执行和模拟能力。

## 解决的问题

| # | 问题 | 旧路由 | 新路由 |
|---|------|--------|--------|
| 1 | 消费面前缀冗余 | `/v1/consumption/views` | `/v1/views` |
| 2 | 可视化端点重复 | `/v1/visualize/*` + `/v1/consumption/views/{id}/visualize/*` | 统一到 `/v1/views/{id}/*` |
| 3 | 执行端点重复 | `/v1/analysis/execute` + `/v1/consumption/views/{id}/execute/analyze` | 保留 `/v1/views/{id}/execute/analyze`，废弃 `/v1/analysis` |
| 4 | 依赖图重复 | `/{space_id}/schema/L4/rules/dependency-graph` + `/views/{id}/rules/dependency-graph` | Space 内为管理面依赖图，View 内为消费面依赖图，语义不同 |

---

## 核心概念

### View 与 Space 的关系

```
Space (管理面)                    View (消费面)
├── L1-L4 Schema 定义            ├── L1-L4 Schema 只读副本
├── Instances (可写)              ├── Instances (只读)
├── Versions (可管理)             └── 无版本管理
└── 激活时自动创建 View ──────────▶  自动同步
```

- View 是 Space 激活时自动创建的只读投影
- View ID 格式: `view_{domain}`（与 Space 的 `space_{domain}` 对应）
- View 不支持独立 CRUD，生命周期由 Space 管理

---

## 路由详情

### GET /v1/views — 列出视图

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `domain` | string | 按领域过滤 |
| `status` | string | 按状态过滤 |

**响应：**

```json
{
  "success": true,
  "data": {
    "views": [
      {
        "view_id": "view.supply_chain_finance",
        "name": "供应链金融空间 (消费视图)",
        "space_id": "space.supply_chain_finance",
        "domain": "supply_chain_finance",
        "status": "ACTIVE",
        "entity_count": 25,
        "rule_count": 12
      }
    ]
  }
}
```

**对齐服务：** `SemanticSpaceStorage.list` (过滤 `SpaceType.CONSUMPTION`)

---

### GET /v1/views/{view_id} — 获取视图

返回 View 完整信息，包含 metadata 和 schema 总览。

**对齐服务：** `SemanticSpaceStorage.load`

---

### GET /v1/views/{view_id}/entities — 视图实体列表

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `concept_type` | string | 按概念类型过滤 |
| `dimension` | string | 按维度过滤 |
| `limit` | int | 分页大小 |
| `offset` | int | 分页偏移 |

**对齐服务：** `EntityService.query_entities`

---

## 可视化端点

### GET /v1/views/{view_id}/schema-graph — Schema 图可视化

返回 Schema 的图结构数据，供前端 G6 渲染。

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `graph_type` | string | 图类型: `entity_relation` / `full` |
| `layer_filter` | string[] | 层级过滤: `L1` / `L2` / `L3` / `L4` |

**响应结构：**

```json
{
  "success": true,
  "data": {
    "nodes": [
      { "id": "Supplier", "type": "L1", "label": "供应商" },
      { "id": "credit_score", "type": "L3", "label": "信用分数" }
    ],
    "edges": [
      { "source": "Supplier", "target": "credit_score", "type": "L3_dependency" }
    ]
  }
}
```

**对齐服务：** `VisualizationService.get_schema_graph`

---

### GET /v1/views/{view_id}/rule-chain/{dimension} — 规则链 DAG

返回指定维度的规则执行链 DAG。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `dimension` | string | 维度名称，如 `credit_assessment` |

**对齐服务：** `VisualizationService.get_rule_chain_graph`

---

### GET /v1/views/{view_id}/rules/dependency-graph — 规则依赖图

返回 View 内所有规则的依赖关系图。

**对齐服务：** `DAGService`

---

### GET /v1/views/{view_id}/rules/for-entity/{entity_id} — 实体适用规则

返回指定实体适用的所有规则及其执行状态。

**对齐服务：** `AnalysisService`

---

### GET /v1/views/{view_id}/metrics/{entity_id} — 指标快照

返回指定实体的 L3 指标快照值。

**对齐服务：** `VisualizationService`

---

### GET /v1/views/{view_id}/execution/{entity_id}/{dimension} — 执行追溯

返回指定实体在指定维度的规则执行追溯链。

**对齐服务：** `AnalysisService`

---

## 执行端点

### POST /v1/views/{view_id}/execute/analyze — 执行分析

在 View 上下文中执行完整维度分析。

**请求：**

```json
{
  "entity_id": "S001",
  "rule_groups": ["credit_assessment"],
  "context_overrides": {
    "market_condition": "BULL"
  }
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "entity_id": "S001",
    "rule_results": {
      "credit_assessment": {
        "outputs": {
          "eligible": true,
          "credit_score": 85,
          "credit_grade": "A"
        },
        "execution_details": {
          "steps_executed": 3,
          "execution_time_ms": 12
        }
      }
    },
    "computed_metrics": {
      "credit_score": 85,
      "credit_grade": "A"
    }
  }
}
```

**对齐服务：** `AnalysisService.execute_analysis`

---

### POST /v1/views/{view_id}/execute/simulate — What-if 模拟

干运行模拟，不持久化结果。

**请求：**

```json
{
  "entity_id": "S001",
  "rule_groups": ["credit_assessment"],
  "context_overrides": {
    "registered_capital": { "value": 10000000, "currency": "CNY" }
  }
}
```

**对齐服务：** `SimulationService`

---

## 旧路由映射

| 旧路由 | 新路由 | 兼容策略 |
|--------|--------|---------|
| `GET /v1/consumption/views` | `GET /v1/views` | 301 重定向 |
| `GET /v1/consumption/views/{id}` | `GET /v1/views/{id}` | 301 重定向 |
| `GET /v1/consumption/views/{id}/entities` | `GET /v1/views/{id}/entities` | 301 重定向 |
| `GET /v1/consumption/views/{id}/visualize/schema-graph` | `GET /v1/views/{id}/schema-graph` | 301 重定向 |
| `GET /v1/consumption/views/{id}/rules/dependency-graph` | `GET /v1/views/{id}/rules/dependency-graph` | 301 重定向 |
| `GET /v1/consumption/views/{id}/rules/for-entity/{eid}` | `GET /v1/views/{id}/rules/for-entity/{eid}` | 301 重定向 |
| `POST /v1/consumption/views/{id}/execute/analyze` | `POST /v1/views/{id}/execute/analyze` | 301 重定向 |
| `POST /v1/consumption/views/{id}/execute/simulate` | `POST /v1/views/{id}/execute/simulate` | 301 重定向 |
| `GET /v1/visualize/schema/graph` | `GET /v1/views/{id}/schema-graph` | 301 重定向 |
| `GET /v1/visualize/entities` | `GET /v1/views/{id}/entities` | 301 重定向 |
| `GET /v1/visualize/metrics/{eid}` | `GET /v1/views/{id}/metrics/{eid}` | 301 重定向 |
| `GET /v1/visualize/rule-chain/{dim}` | `GET /v1/views/{id}/rule-chain/{dim}` | 301 重定向 |
| `POST /v1/visualize/simulate` | `POST /v1/views/{id}/execute/simulate` | 301 重定向 |
| `GET /v1/visualize/execution/{eid}/{dim}` | `GET /v1/views/{id}/execution/{eid}/{dim}` | 301 重定向 |
| `POST /v1/analysis/execute` | `POST /v1/views/{id}/execute/analyze` | 301 重定向 |
| `POST /v1/analysis/dry-run` | `POST /v1/views/{id}/execute/simulate` | 301 重定向 |

# /v1/query 路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [02-api-redesign-proposal.md](02-api-redesign-proposal.md) | **last_verified**: 2026-04-19

---

## 目的

定义知识检索（Query）的 API 路由。Query 层提供向量搜索、图遍历、混合检索和查询解释能力，是 Agent 和前端进行知识发现的核心入口。

## 解决的问题

| # | 问题 | 旧路由 | 新路由 |
|---|------|--------|--------|
| 1 | GET+POST 重复端点 | `/v1/query/pattern-match/{concept}` GET+POST 重复 | 统一为 POST `/v1/query/graph` |
| 2 | GET+POST 重复端点 | `/v1/query/traverse/{entity_id}` GET+POST 重复 | 合并到 POST `/v1/query/graph` |
| 3 | GET+POST 重复端点 | `/v1/query/path` GET+POST 重复 | 合并到 POST `/v1/query/graph` |
| 4 | 命名不一致 | `/v1/query/vector` | 重命名为 `/v1/query/search`（语义更准确） |
| 5 | 缺少查询解释 | 无 | 新增 POST `/v1/query/explain` |
| 6 | 端点过多过细 | 10 个端点 | 精简为 5 个 |

---

## 路由详情

### POST /v1/query/search — 向量/语义搜索

替代旧 `/v1/query/vector`，支持纯语义搜索。

**请求：**

```json
{
  "text": "芯片供应商",
  "concept_type": "Supplier",
  "top_k": 10,
  "filters": {
    "status": { "eq": "ACTIVE" }
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 搜索文本 |
| `concept_type` | string | 否 | 按概念类型过滤 |
| `top_k` | int | 否 | 返回数量（默认 10） |
| `filters` | object | 否 | 属性过滤条件 |

**响应：**

```json
{
  "success": true,
  "data": {
    "results": [
      {
        "entity_id": "S003",
        "concept_type": "Supplier",
        "relevance_score": 0.95,
        "attributes": {
          "company_name": "芯片供应商A",
          "products": ["CPU", "GPU"]
        }
      }
    ],
    "total": 1,
    "query_type": "semantic"
  }
}
```

**对齐服务：** `QueryService.semantic_search`

---

### POST /v1/query/graph — 图遍历查询

整合旧 `/v1/query/graph`、`/v1/query/pattern-match/{concept}`、`/v1/query/traverse/{entity_id}`、`/v1/query/path`，统一为图遍历 DSL。

**请求 — 邻居遍历模式：**

```json
{
  "mode": "traverse",
  "start_entity_id": "S001",
  "relation_type": "guarantees",
  "direction": "outgoing",
  "depth": 2
}
```

**请求 — 模式匹配模式：**

```json
{
  "mode": "pattern",
  "start": {
    "concept_type": "Supplier",
    "filter": { "status": { "eq": "ACTIVE" } }
  },
  "traverse": [
    {
      "relation": "guarantees",
      "direction": "both",
      "depth": 2,
      "target_filter": {
        "concept_type": "Supplier",
        "attributes": { "risk_level": { "eq": "HIGH" } }
      }
    }
  ],
  "return": {
    "attributes": ["company_name", "registered_capital"],
    "include_path": true,
    "aggregate": [
      { "type": "sum", "field": "guarantee_amount.value" },
      { "type": "count", "field": "related_entities" }
    ]
  },
  "limit": 50
}
```

**请求 — 路径查询模式：**

```json
{
  "mode": "path",
  "from_entity_id": "S001",
  "to_entity_id": "S005",
  "max_depth": 3
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `mode` | enum | 是 | `traverse` / `pattern` / `path` |
| `start_entity_id` | string | traverse 模式 | 起始实体 ID |
| `relation_type` | string | traverse 模式 | 关系类型 |
| `direction` | string | 否 | `outgoing` / `incoming` / `both` |
| `depth` | int | 否 | 遍历深度（最大 2） |
| `start` | object | pattern 模式 | 起始节点定义 |
| `traverse` | array | pattern 模式 | 遍历步骤 |
| `from_entity_id` | string | path 模式 | 起始实体 |
| `to_entity_id` | string | path 模式 | 目标实体 |
| `max_depth` | int | path 模式 | 最大路径深度（最大 3） |

**对齐服务：** `QueryService.graph_traverse` / `QueryService.graph_pattern_match` / `QueryService.find_path`

---

### POST /v1/query/hybrid — 混合检索

结合语义搜索和图结构检索的加权融合检索。

**请求：**

```json
{
  "query": "高信用的芯片供应商",
  "concept_type": "Supplier",
  "top_k": 10,
  "semantic_weight": 0.6,
  "graph_weight": 0.4,
  "graph_seed_id": "S001",
  "filters": {
    "status": { "eq": "ACTIVE" }
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本 |
| `concept_type` | string | 否 | 概念类型过滤 |
| `top_k` | int | 否 | 返回数量 |
| `semantic_weight` | float | 否 | 语义权重（默认 0.6） |
| `graph_weight` | float | 否 | 图权重（默认 0.4） |
| `graph_seed_id` | string | 否 | 图扩展种子实体 |
| `filters` | object | 否 | 属性过滤 |

**对齐服务：** `QueryService.hybrid_search`

---

### POST /v1/query/explain — 查询解释

解释查询的执行计划和预期结果范围。

**请求：**

```json
{
  "query": "高信用的芯片供应商",
  "concept_type": "Supplier",
  "explain_mode": "plan"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 查询文本 |
| `concept_type` | string | 否 | 概念类型 |
| `explain_mode` | enum | 否 | `plan` / `cost` / `full` |

**响应：**

```json
{
  "success": true,
  "data": {
    "query_plan": {
      "steps": [
        { "type": "semantic_search", "description": "向量检索 '高信用的芯片供应商'" },
        { "type": "graph_expansion", "description": "从种子实体扩展 1 跳邻居" },
        { "type": "fusion", "description": "RRF 融合，语义权重 0.6，图权重 0.4" },
        { "type": "filter", "description": "过滤 concept_type=Supplier" }
      ],
      "estimated_cost": {
        "vector_ops": 1,
        "graph_traversals": 1,
        "fusion_ops": 1
      }
    }
  }
}
```

**对齐服务：** `QueryService`

---

### GET /v1/query/trace/{entity_id} — 规则追溯

追溯指定实体的规则执行历史。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `entity_id` | string | 实体 ID |

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `rule_id` | string | 指定规则 ID |
| `trace_mode` | string | `categorization` / `rules` / `dependency` / `full` |

**对齐服务：** `QueryService.trace_rule`

---

## DSL 能力边界

| 能力 | 支持 | 说明 |
|------|------|------|
| 节点查找 | 是 | 按 concept_type + 属性过滤 |
| 1-2 跳邻居扩展 | 是 | 指定关系类型、方向、深度 |
| 属性过滤 | 是 | eq / gte / lte / in / contains |
| 路径返回 | 是 | include_path=true |
| 聚合计算 | 是 | sum / count / avg / max |
| 3+ 跳遍历 | 否 | Phase 2 考虑 |
| 任意路径匹配 | 否 | 不支持通配符路径 |
| Cypher 语法 | 否 | 不开放 Cypher |

---

## 过滤操作符

| 操作符 | 说明 | 示例 |
|--------|------|------|
| `eq` | 等于 | `{"status": {"eq": "ACTIVE"}}` |
| `ne` | 不等于 | `{"status": {"ne": "INACTIVE"}}` |
| `gt` / `gte` | 大于/大于等于 | `{"value": {"gt": 1000}}` |
| `lt` / `lte` | 小于/小于等于 | `{"value": {"lte": 5000}}` |
| `in` | 包含在列表 | `{"status": {"in": ["ACTIVE", "PENDING"]}}` |
| `contains` | 字符串包含 | `{"name": {"contains": "科技"}}` |

---

## 旧路由映射

| 旧路由 | 新路由 | 兼容策略 |
|--------|--------|---------|
| `POST /v1/query/vector` | `POST /v1/query/search` | 301 重定向 |
| `POST /v1/query/hybrid` | `POST /v1/query/hybrid` | 路径不变 |
| `POST /v1/query/graph` | `POST /v1/query/graph` | 路径不变，扩展 mode 参数 |
| `GET /v1/query/pattern-match/{concept}` | `POST /v1/query/graph` (mode=pattern) | 移除 GET |
| `POST /v1/query/pattern-match/{concept}` | `POST /v1/query/graph` (mode=pattern) | 合并 |
| `GET /v1/query/traverse/{entity_id}` | `POST /v1/query/graph` (mode=traverse) | 移除 GET |
| `POST /v1/query/traverse/{entity_id}` | `POST /v1/query/graph` (mode=traverse) | 合并 |
| `GET /v1/query/path/{from}/{to}` | `POST /v1/query/graph` (mode=path) | 移除 GET |
| `POST /v1/query/path` | `POST /v1/query/graph` (mode=path) | 合并 |
| `GET /v1/query/trace/{entity_id}` | `GET /v1/query/trace/{entity_id}` | 路径不变 |

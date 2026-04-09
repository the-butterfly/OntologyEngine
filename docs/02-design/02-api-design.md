# API 设计

> **Version**: MVP
> **Protocol**: REST (FastAPI)

## 设计原则

1. **资源导向** —— URL 表示资源，HTTP 方法表示操作
2. **版本化** —— `/v1/` 前缀
3. **一致性** —— 统一响应格式
4. **可发现** —— Schema 驱动 API 文档

---

## 响应格式

```json
{
  "success": true,
  "data": { },
  "error": null,
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-04-08T10:00:00Z"
  }
}
```

错误响应：
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Supplier S001 not found",
    "details": { "entity_id": "S001" }
  }
}
```

---

## 端点

### Schema 管理

#### 加载 Schema
```http
POST /v1/schema/load
Content-Type: application/json

{
  "schema_path": "examples/supply_chain_finance/schema.yaml"
}
```

#### 获取当前 Schema
```http
GET /v1/schema
```

---

### 实体管理

#### 创建实体
```http
POST /v1/entities
Content-Type: application/json

{
  "concept_type": "Supplier",
  "entity_id": "S001",
  "attributes": {
    "company_name": "供应商A",
    "registered_capital": { "value": 5000000, "currency": "CNY" },
    "status": "ACTIVE"
  }
}
```

#### 批量创建
```http
POST /v1/entities/batch
Content-Type: application/json

{
  "entities": [ ... ]
}
```

#### 查询实体
```http
GET /v1/entities/{entity_id}
```

#### 条件查询
```http
POST /v1/entities/query
Content-Type: application/json

{
  "concept_type": "Supplier",
  "filter": {
    "status": { "eq": "ACTIVE" },
    "registered_capital.value": { "gte": 1000000 }
  },
  "limit": 100
}
```

---

### 关系管理

#### 创建关系
```http
POST /v1/edges
Content-Type: application/json

{
  "relation_type": "guarantees",
  "from_id": "S001",
  "to_id": "S002",
  "attributes": {
    "amount": { "value": 1000000, "currency": "CNY" }
  }
}
```

#### 查询邻居
```http
GET /v1/entities/{entity_id}/neighbors?relation_type=guarantees&depth=2
```

---

### 规则执行

#### 执行规则
```http
POST /v1/rules/execute
Content-Type: application/json

{
  "entity_id": "S001",
  "dimension": "credit_assessment",
  "rules": ["R001", "R002"]
}
```

响应：
```json
{
  "success": true,
  "data": {
    "entity_id": "S001",
    "dimension": "credit_assessment",
    "results": {
      "R001": { "eligible": true },
      "R002": { "score": 85, "grade": "A" }
    },
    "computed_metrics": {
      "credit_score": 85,
      "credit_grade": "A"
    }
  }
}
```

#### 获取规则列表
```http
GET /v1/rules?dimension=credit_assessment
```

---

### 图查询 (Graph Traversal DSL)

**简化版图遍历 DSL（决策 #9）**：替代 Cypher，自研轻量 DSL，支持 1-2 跳邻居查询 + 属性过滤。

```http
POST /v1/query/graph
Content-Type: application/json

{
  "start": {
    "concept_type": "Supplier",
    "filter": {"status": {"eq": "ACTIVE"}}
  },
  "traverse": [
    {
      "relation": "guarantees",
      "direction": "both",
      "depth": 2,
      "target_filter": {
        "concept_type": "Supplier",
        "attributes": {"risk_level": {"eq": "HIGH"}}
      }
    }
  ],
  "return": {
    "attributes": ["company_name", "registered_capital"],
    "include_path": true,
    "aggregate": [
      {"type": "sum", "field": "guarantee_amount.value"},
      {"type": "count", "field": "related_entities"}
    ]
  },
  "limit": 50
}
```

**DSL 能力边界**：

| 能力 | 支持 | 说明 |
|------|------|------|
| 节点查找 | ✅ | 按 concept_type + 属性过滤 |
| 1-2 跳邻居扩展 | ✅ | 指定关系类型、方向、深度 |
| 属性过滤 | ✅ | eq/gte/lte/in/contains |
| 路径返回 | ✅ | include_path=true |
| 聚合计算 | ✅ | sum/count/avg/max |
| 3+ 跳遍历 | ❌ | Phase 2 考虑 |
| 任意路径匹配 | ❌ | 不支持通配符路径 |
| Cypher 语法 | ❌ | 不开放 Cypher |

#### 向量检索
```http
POST /v1/query/vector
Content-Type: application/json

{
  "text": "芯片供应商",
  "concept_type": "Supplier",
  "top_k": 10
}
```

---

## 错误码

| Code | HTTP | 说明 |
|------|------|------|
| ENTITY_NOT_FOUND | 404 | 实体不存在 |
| CONCEPT_NOT_DEFINED | 400 | Schema 未定义该概念 |
| INVALID_ATTRIBUTE | 400 | 属性类型错误 |
| RULE_NOT_FOUND | 404 | 规则不存在 |
| EXPRESSION_ERROR | 400 | 表达式语法错误 |
| SCHEMA_NOT_LOADED | 500 | Schema 未加载 |
| GRAPH_TRAVERSAL_TOO_DEEP | 400 | 图遍历深度超过限制（最大2跳） |
| OVERRIDABLE_VIOLATION | 400 | L3 指标 overridable=false 不允许覆盖 |
| FORMULA_SANDBOX_VIOLATION | 400 | Formula 沙箱安全约束违反 |
| FORMULA_EXECUTION_TIMEOUT | 408 | Formula 执行超时 |

---

## 流式响应 (Future)

```http
GET /v1/rules/execute/stream
Accept: text/event-stream
```

```
event: rule_start
data: {"rule_id": "R001"}

event: rule_complete
data: {"rule_id": "R001", "result": {...}}

event: complete
data: {"final_result": {...}}
```

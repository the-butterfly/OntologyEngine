# /v1/spaces 路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [02-api-redesign-proposal.md](02-api-redesign-proposal.md) | **last_verified**: 2026-04-19

---

## 目的

定义 Semantic Space（语义空间）的完整 CRUD、生命周期管理、Schema L1-L4 管理、实例管理和版本管理的 API 路由。Space 是 OntologyEngine 的核心容器，所有资产（Schema、实例、规则）必须关联到 Space。

## 解决的问题

| # | 问题 | 旧路由 | 新路由 |
|---|------|--------|--------|
| 1 | Space 管理路由重复 | `/v1/management/spaces` + `/v1/spaces` | 统一 `/v1/spaces` |
| 2 | 前缀冗余 | `/v1/management/{space_id}/schema/L1/...` | `/v1/spaces/{space_id}/schema/L1/...` |
| 3 | 路径缺少资源名 | `/{space_id}/instances/entities` | `/v1/spaces/{space_id}/instances/entities` |
| 4 | Rule Groups 与 L4 重复 | `/v1/rule-groups` + `/{space_id}/schema/L4/rules/definitions` | 统一到 `/v1/spaces/{space_id}/schema/L4/rules` |
| 5 | Rule Steps 与 L4 Logic 重复 | `/v1/rule-groups/{name}/steps` + `/{space_id}/schema/L4/rules/logics` | 统一到 `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics` |

---

## Space CRUD

### POST /v1/spaces — 创建 Space

**请求：**

```json
{
  "space_id": "space.supply_chain_finance",
  "name": "供应链金融空间",
  "description": "用于供应链金融场景的语义空间",
  "space_type": "domain",
  "domain": "supply_chain_finance"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `space_id` | string | 是 | 格式: `space.{name}` |
| `name` | string | 是 | 人类可读名称 |
| `description` | string | 否 | 描述 |
| `space_type` | enum | 否 | `domain` / `project` / `sandbox` |
| `domain` | string | 否 | 领域标识 |

**响应：**

```json
{
  "success": true,
  "data": {
    "space_id": "space.supply_chain_finance",
    "name": "供应链金融空间",
    "status": "DRAFT",
    "space_type": "domain",
    "domain": "supply_chain_finance",
    "created_at": "2026-04-19T10:00:00Z"
  }
}
```

**对齐服务：** `SemanticSpaceStorage.save`

---

### GET /v1/spaces — 列出 Space

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | 按状态过滤: `DRAFT` / `ACTIVE` / `ARCHIVED` |
| `domain` | string | 按领域过滤 |
| `space_type` | string | 按类型过滤 |

**对齐服务：** `SemanticSpaceStorage.list`

---

### GET /v1/spaces/{space_id} — 获取 Space

返回 Space 完整信息，包含 metadata 和 schema 总览。

**对齐服务：** `SemanticSpaceStorage.load`

---

### PUT /v1/spaces/{space_id} — 更新 Space

**请求：**

```json
{
  "name": "供应链金融空间 v2",
  "description": "更新后的描述"
}
```

**对齐服务：** `SemanticSpaceStorage.save`

---

### DELETE /v1/spaces/{space_id} — 删除 Space

仅 `DRAFT` 或 `ARCHIVED` 状态可删除。`ACTIVE` 状态需先停用。

**错误码：** `SPACE_NOT_DRAFT` (400)

**对齐服务：** `SemanticSpaceStorage.delete`

---

## 生命周期管理

### POST /v1/spaces/{space_id}/activate — 激活 Space

激活后：
1. Space 状态变为 `ACTIVE`
2. 自动创建消费 View（`view_{domain}`）
3. 同步 Schema 和实例到 View

**响应：**

```json
{
  "success": true,
  "data": {
    "space_id": "space.supply_chain_finance",
    "status": "ACTIVE",
    "consumption_view_id": "view.supply_chain_finance",
    "activated_at": "2026-04-19T10:05:00Z"
  }
}
```

**对齐服务：** `SemanticSpaceStorage.save` + 自动创建 View

---

### POST /v1/spaces/{space_id}/deactivate — 停用 Space

停用后 Space 状态变为 `DRAFT`，关联 View 不可用。

**对齐服务：** `SemanticSpaceStorage.save`

---

### POST /v1/spaces/{space_id}/archive — 归档 Space

归档后 Space 只读，不可修改 Schema 和实例。

**对齐服务：** `SemanticSpaceStorage.save`

---

## Schema 管理

### GET /v1/spaces/{space_id}/schema — Schema 总览

返回 Space 内完整的 L1-L4 Schema 结构。

**响应：**

```json
{
  "success": true,
  "data": {
    "space_id": "space.supply_chain_finance",
    "layers": {
      "L1_fact_objects": [...],
      "L2_categorizations": [...],
      "L3_analytical_elements": [...],
      "L4_business_logic": {
        "rule_definitions": [...],
        "rule_logics": [...]
      }
    }
  }
}
```

**对齐服务：** `SemanticSpaceStorage.load`

---

### POST /v1/spaces/{space_id}/schema/load-yaml — 从 YAML 加载 Schema

**请求：**

```json
{
  "schema_path": "examples/supply_chain_finance/schema.yaml"
}
```

**对齐服务：** `SchemaLoader.load` + `SemanticSpaceStorage.save`

---

## Schema L1 — 要素对象

### GET /v1/spaces/{space_id}/schema/L1/fact-objects

返回 Space 内所有 L1 要素对象定义。

**对齐服务：** `SemanticSpaceStorage.load` → `layers.L1_fact_objects`

---

### POST /v1/spaces/{space_id}/schema/L1/fact-objects

**请求：**

```json
{
  "concept_type": "Supplier",
  "properties": {
    "company_name": { "type": "string", "required": true },
    "registered_capital": { "type": "MonetaryValue", "required": true },
    "status": { "type": "string", "enum": ["ACTIVE", "INACTIVE"] }
  },
  "relations": [
    { "name": "guarantees", "target": "Supplier", "cardinality": "many_to_many" }
  ]
}
```

**对齐服务：** `SemanticSpaceStorage.save`

---

## Schema L2 — 分类体系

### GET /v1/spaces/{space_id}/schema/L2/categorizations

**对齐服务：** `SemanticSpaceStorage.load` → `layers.L2_categorizations`

---

### POST /v1/spaces/{space_id}/schema/L2/categorizations

**请求：**

```json
{
  "dimension": "risk_level",
  "description": "风险等级分类",
  "values": ["HIGH", "MEDIUM", "LOW"],
  "applicable_to": ["Supplier", "Product"]
}
```

**对齐服务：** `SemanticSpaceStorage.save`

---

## Schema L3 — 分析要素

### GET /v1/spaces/{space_id}/schema/L3/analytical-elements

**对齐服务：** `SemanticSpaceStorage.load` → `layers.L3_analytical_elements`

---

### POST /v1/spaces/{space_id}/schema/L3/analytical-elements

**请求：**

```json
{
  "name": "credit_score",
  "element_type": "derived",
  "formula": "weighted_sum(registered_capital, guarantee_exposure)",
  "overridable": false,
  "dependencies": ["registered_capital", "guarantee_exposure"]
}
```

**对齐服务：** `SemanticSpaceStorage.save`

---

## Schema L4 — 规则定义与逻辑

### 规则定义 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/spaces/{space_id}/schema/L4/rules` | 规则列表 |
| POST | `/v1/spaces/{space_id}/schema/L4/rules` | 创建规则 |
| GET | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}` | 获取规则 |
| PUT | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}` | 更新规则 |
| DELETE | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}` | 删除规则 |

**POST 创建规则请求：**

```json
{
  "name": "credit_assessment",
  "description": "信用评估规则组",
  "type": "decision",
  "priority": 100,
  "applies_to": {
    "fact_objects": ["Supplier"],
    "categories": {}
  },
  "inputs": [
    { "name": "registered_capital", "type": "attribute", "attribute": "registered_capital" }
  ],
  "outputs": [
    { "name": "eligible", "type": "boolean" },
    { "name": "credit_score", "type": "integer" }
  ],
  "preconditions": [
    { "expression": "status == 'ACTIVE'", "fail": { "eligible": false } }
  ],
  "enabled": true
}
```

**对齐服务：** `SemanticSpaceStorage.save`

**映射关系：** Phase 2 `RuleGroup` = L4 `RuleDefinition`

---

### 规则逻辑 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics` | 逻辑列表 |
| POST | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics` | 添加逻辑 |
| PUT | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}` | 更新逻辑 |
| DELETE | `/v1/spaces/{space_id}/schema/L4/rules/{rule_id}/logics/{logic_id}` | 删除逻辑 |

**POST 添加逻辑请求：**

```json
{
  "id": "step.uuid-xxx",
  "name": "计算信用分数",
  "step_order": 1,
  "when": {
    "type": "expression",
    "expression": "registered_capital.value >= 1000000"
  },
  "then": {
    "operator": "COMPUTE",
    "params": { "formula": "min(registered_capital.value * 0.5, 10000000)" },
    "output_mapping": { "credit_limit": "result" }
  },
  "else": {
    "operator": "COMPUTE",
    "params": { "formula": "registered_capital.value * 0.3" },
    "output_mapping": { "credit_limit": "result" }
  },
  "enabled": true
}
```

**对齐服务：** `SemanticSpaceStorage.save`

**映射关系：** Phase 2 `RuleStep` = L4 `RuleLogic`

---

### 规则依赖图

#### GET /v1/spaces/{space_id}/schema/rules/dependency-graph

返回 Space 内所有规则的依赖关系 DAG。

**对齐服务：** `DAGService`

---

## 实例管理

### 实体实例

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/spaces/{space_id}/instances/entities` | 实体列表 |
| POST | `/v1/spaces/{space_id}/instances/entities` | 添加实体 |
| POST | `/v1/spaces/{space_id}/instances/entities/batch` | 批量添加 |
| POST | `/v1/spaces/{space_id}/instances/entities/load-yaml` | 从 YAML 加载 |

**POST 添加实体请求：**

```json
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

**对齐服务：** `EntityService.create_entity` / `EntityService.batch_create`

---

### 关系实例

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/spaces/{space_id}/instances/relations` | 关系列表 |
| POST | `/v1/spaces/{space_id}/instances/relations` | 添加关系 |

**POST 添加关系请求：**

```json
{
  "relation_type": "guarantees",
  "from_id": "S001",
  "to_id": "S002",
  "attributes": {
    "amount": { "value": 1000000, "currency": "CNY" },
    "start_date": "2026-01-01"
  }
}
```

**对齐服务：** `EntityService`

---

## 版本管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/spaces/{space_id}/versions` | 版本列表 |
| POST | `/v1/spaces/{space_id}/versions` | 创建快照 |
| POST | `/v1/spaces/{space_id}/versions/{version}/rollback` | 版本回滚 |

**POST 创建快照请求：**

```json
{
  "description": "上线前快照"
}
```

**POST 版本回滚请求：**

```json
{
  "confirm": true
}
```

**对齐服务：** `SemanticSpaceStorage`

---

## Space 状态机

```
DRAFT ──activate──▶ ACTIVE ──deactivate──▶ DRAFT
  │                    │
  │                    └──archive──▶ ARCHIVED
  │                                    │
  └──delete──▶ (removed)              └──delete──▶ (removed)
```

| 状态 | 可执行操作 | 说明 |
|------|-----------|------|
| `DRAFT` | 编辑 Schema、添加实例、激活、删除 | 草稿态 |
| `ACTIVE` | 停用、归档 | 已激活，消费面可用 |
| `ARCHIVED` | 删除 | 只读归档态 |

---

## 旧路由映射

| 旧路由 | 新路由 | 兼容策略 |
|--------|--------|---------|
| `POST /v1/management/spaces` | `POST /v1/spaces` | 301 重定向 |
| `GET /v1/management/spaces` | `GET /v1/spaces` | 301 重定向 |
| `GET /v1/management/spaces/{id}` | `GET /v1/spaces/{id}` | 301 重定向 |
| `PUT /v1/management/spaces/{id}` | `PUT /v1/spaces/{id}` | 301 重定向 |
| `DELETE /v1/management/spaces/{id}` | `DELETE /v1/spaces/{id}` | 301 重定向 |
| `POST /v1/management/{id}/activate` | `POST /v1/spaces/{id}/activate` | 301 重定向 |
| `POST /v1/management/{id}/deactivate` | `POST /v1/spaces/{id}/deactivate` | 301 重定向 |
| `POST /v1/management/{id}/archive` | `POST /v1/spaces/{id}/archive` | 301 重定向 |
| `GET /v1/management/{id}/schema/L1/fact-objects` | `GET /v1/spaces/{id}/schema/L1/fact-objects` | 301 重定向 |
| `POST /v1/management/{id}/schema/L1/fact-objects` | `POST /v1/spaces/{id}/schema/L1/fact-objects` | 301 重定向 |
| `GET /v1/management/{id}/schema/L2/categorizations` | `GET /v1/spaces/{id}/schema/L2/categorizations` | 301 重定向 |
| `POST /v1/management/{id}/schema/L2/categorizations` | `POST /v1/spaces/{id}/schema/L2/categorizations` | 301 重定向 |
| `GET /v1/management/{id}/schema/L3/analytical-elements` | `GET /v1/spaces/{id}/schema/L3/analytical-elements` | 301 重定向 |
| `POST /v1/management/{id}/schema/L3/analytical-elements` | `POST /v1/spaces/{id}/schema/L3/analytical-elements` | 301 重定向 |
| `GET /v1/management/{id}/schema/L4/rules/definitions` | `GET /v1/spaces/{id}/schema/L4/rules` | 301 重定向 |
| `POST /v1/management/{id}/schema/L4/rules/definitions` | `POST /v1/spaces/{id}/schema/L4/rules` | 301 重定向 |
| `GET /v1/management/{id}/schema/L4/rules/definitions/{rid}` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}` | 301 重定向 |
| `PUT /v1/management/{id}/schema/L4/rules/definitions/{rid}` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}` | 301 重定向 |
| `DELETE /v1/management/{id}/schema/L4/rules/definitions/{rid}` | `DELETE /v1/spaces/{id}/schema/L4/rules/{rid}` | 301 重定向 |
| `GET /v1/management/{id}/schema/L4/rules/logics` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 301 重定向 |
| `POST /v1/management/{id}/schema/L4/rules/logics` | `POST /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 301 重定向 |
| `GET /v1/management/{id}/instances/entities` | `GET /v1/spaces/{id}/instances/entities` | 301 重定向 |
| `POST /v1/management/{id}/instances/entities` | `POST /v1/spaces/{id}/instances/entities` | 301 重定向 |
| `GET /v1/management/{id}/instances/relations` | `GET /v1/spaces/{id}/instances/relations` | 301 重定向 |
| `POST /v1/management/{id}/instances/relations` | `POST /v1/spaces/{id}/instances/relations` | 301 重定向 |
| `GET /v1/management/{id}/versions` | `GET /v1/spaces/{id}/versions` | 301 重定向 |
| `POST /v1/management/{id}/versions` | `POST /v1/spaces/{id}/versions` | 301 重定向 |
| `POST /v1/management/{id}/versions/{v}/rollback` | `POST /v1/spaces/{id}/versions/{v}/rollback` | 301 重定向 |
| `POST /v1/management/{id}/schema/load-from-yaml` | `POST /v1/spaces/{id}/schema/load-yaml` | 301 重定向 |
| `POST /v1/management/{id}/instances/load-from-yaml` | `POST /v1/spaces/{id}/instances/entities/load-yaml` | 301 重定向 |
| `GET /v1/management/{id}/schema/overview` | `GET /v1/spaces/{id}/schema` | 301 重定向 |
| `POST /v1/rule-groups` | `POST /v1/spaces/{id}/schema/L4/rules` | 兼容层映射 |
| `GET /v1/rule-groups` | `GET /v1/spaces/{id}/schema/L4/rules` | 兼容层映射 |
| `GET /v1/rule-groups/{id}` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}` | 兼容层映射 |
| `PUT /v1/rule-groups/{id}` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}` | 兼容层映射 |
| `DELETE /v1/rule-groups/{id}` | `DELETE /v1/spaces/{id}/schema/L4/rules/{rid}` | 兼容层映射 |
| `POST /v1/rule-groups/{name}/steps` | `POST /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 兼容层映射 |
| `GET /v1/rule-groups/{name}/steps` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 兼容层映射 |

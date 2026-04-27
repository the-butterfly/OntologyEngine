# /v1/ontology 路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [02-api-redesign-proposal.md](02-api-redesign-proposal.md) | **last_verified**: 2026-04-19

---

## 目的

定义全局本体（Ontology）管理的 API 路由。Ontology 是 OntologyEngine 的全局 Schema 定义层，包含 L1-L4 的完整本体模型。Ontology 由 Semantic Space 实例化，Space 内的 schema 是 Ontology 的具体实例。

## 解决的问题

| # | 问题 | 旧路由 | 新路由 |
|---|------|--------|--------|
| 1 | Schema/schema 概念混淆 | `/v1/schema`（全局 KGMLSchema）与 `/{space_id}/schema`（Space 内 L1-L4）混用 | 全局 → `/v1/ontology`；Space 内 → `/v1/spaces/{id}/schema` |
| 2 | 全局 Schema 不关联 Space | `/v1/schema` 是全局单例，与 Space 无关 | Ontology 作为模板，Space 实例化 |
| 3 | 版本回退位置混乱 | `/v1/schema/rollback/{v}` + `/{space_id}/versions/{v}/rollback` 两套 | Ontology 级版本 → `/v1/ontology/rollback/{v}`；Space 级 → `/v1/spaces/{id}/versions/{v}/rollback` |

---

## 核心概念

### Ontology vs Space Schema

```
Ontology (全局本体)                 Space Schema (实例化)
├── L1-L4 完整定义                  ├── L1-L4 实例化定义
├── 全局版本管理                     ├── Space 级版本管理
├── 模板/蓝图角色                    ├── 具体业务实例
├── 路径: /v1/ontology              ├── 路径: /v1/spaces/{id}/schema
└── 可被多个 Space 实例化            └── 绑定到特定 Space
```

- Ontology 是"蓝图"，Space Schema 是"实例"
- Ontology 变更不自动传播到已创建的 Space
- 新 Space 可从 Ontology 加载初始 Schema

---

## 路由详情

### GET /v1/ontology — 获取完整 Ontology

返回当前全局 Ontology 的完整 L1-L4 定义。

**响应：**

```json
{
  "success": true,
  "data": {
    "ontology_id": "ontology.supply_chain_finance",
    "version": "1.0.0",
    "loaded_at": "2026-04-19T10:00:00Z",
    "layers": {
      "L1_fact_objects": [
        {
          "_fact_object": "Supplier",
          "attributes": {
            "company_name": { "type": "string", "required": true },
            "registered_capital": { "type": "MonetaryValue", "required": true }
          }
        }
      ],
      "L2_categorizations": [...],
      "L3_analytical_elements": [...],
      "L4_business_logic": {
        "rule_definitions": [...],
        "rule_logics": [...]
      }
    },
    "stats": {
      "entity_count": 5,
      "rule_count": 12,
      "metric_count": 8
    }
  }
}
```

**对齐服务：** `SchemaService.get_schema`

---

### POST /v1/ontology/load — 加载 Ontology YAML

从 YAML 文件加载全局 Ontology 定义。

**请求：**

```json
{
  "schema_path": "examples/supply_chain_finance/schema.yaml"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_path` | string | 是 | Schema YAML 文件路径 |

**响应：**

```json
{
  "success": true,
  "data": {
    "ontology_id": "ontology.supply_chain_finance",
    "version": "1.0.0",
    "loaded_at": "2026-04-19T10:00:00Z",
    "entity_count": 5,
    "rule_count": 12
  }
}
```

**对齐服务：** `SchemaService.load_schema`

---

### GET /v1/ontology/versions — 版本历史

返回 Ontology 的版本变更历史。

**响应：**

```json
{
  "success": true,
  "data": {
    "versions": [
      {
        "version": "1.0.0",
        "loaded_at": "2026-04-19T10:00:00Z",
        "entity_count": 5,
        "rule_count": 12,
        "description": "初始版本"
      }
    ],
    "current_version": "1.0.0"
  }
}
```

**对齐服务：** `SchemaService._schema_versions`

---

### POST /v1/ontology/rollback/{version} — 版本回退

将 Ontology 回退到指定版本。

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `version` | string | 目标版本号 |

**请求：**

```json
{
  "confirm": true
}
```

**响应：**

```json
{
  "success": true,
  "data": {
    "ontology_id": "ontology.supply_chain_finance",
    "previous_version": "1.1.0",
    "current_version": "1.0.0",
    "rolled_back_at": "2026-04-19T11:00:00Z"
  }
}
```

**对齐服务：** `SchemaService`

---

## 版本管理策略

### Ontology 级版本 vs Space 级版本

| 维度 | Ontology 版本 | Space 版本 |
|------|--------------|-----------|
| 作用域 | 全局 Schema 定义 | 特定 Space 的完整快照 |
| 包含内容 | L1-L4 定义 | L1-L4 + Instances + 配置 |
| 触发时机 | load/reload 时 | 手动创建快照 |
| 回退影响 | 影响后续新 Space 创建 | 仅影响该 Space |
| 已有 Space | 不自动传播变更 | 回退后立即生效 |

---

## 旧路由映射

| 旧路由 | 新路由 | 兼容策略 |
|--------|--------|---------|
| `POST /v1/schema/load` | `POST /v1/ontology/load` | 301 重定向 + Deprecation Header |
| `GET /v1/schema` | `GET /v1/ontology` | 301 重定向 + Deprecation Header |
| `POST /v1/schema/reload` | `POST /v1/ontology/load` | 301 重定向 + Deprecation Header |
| `GET /v1/schema/versions` | `GET /v1/ontology/versions` | 301 重定向 + Deprecation Header |
| `POST /v1/schema/rollback/{version}` | `POST /v1/ontology/rollback/{version}` | 301 重定向 + Deprecation Header |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| 1 | 使用 `Ontology` 而非 `Schema` | 消除 Schema/schema 大小写混淆，Ontology 更准确表达"全局本体论"语义 |
| 2 | Ontology 变更不自动传播 | 避免破坏已运行的 Space，需手动更新 |
| 3 | 保留 `/v1/schema` 兼容层 | 旧端点返回 301 + Deprecation Header，过渡期不直接删除 |
| 4 | Ontology 版本与 Space 版本分离 | 两者生命周期不同，独立管理 |

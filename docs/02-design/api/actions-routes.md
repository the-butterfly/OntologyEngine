# /v1/actions 路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [02-api-redesign-proposal.md](02-api-redesign-proposal.md) | **last_verified**: 2026-04-19

---

## 目的

定义统一业务动作（Actions）的 API 路由。Actions 是规则执行的统一抽象层，消除旧架构中执行入口分散在 `/v1/rules/execute`、`/v1/analysis/execute`、`/v1/consumption/views/{id}/execute/analyze` 三处的问题。

## 解决的问题

| # | 问题 | 旧路由 | 新路由 |
|---|------|--------|--------|
| 1 | 执行入口分散 | `/v1/rules/execute` + `/v1/analysis/execute` + `/v1/consumption/views/{id}/execute/analyze` | 统一到 `/v1/actions/{action_name}/execute` |
| 2 | 模拟入口分散 | `/v1/rule-groups/{name}/simulate` + `/v1/analysis/dry-run` + `/v1/consumption/views/{id}/execute/simulate` | 统一到 `/v1/actions/{action_name}/simulate` |
| 3 | 缺少执行解释 | 无专门端点 | `/v1/actions/{action_name}/explain/{entity_id}` |
| 4 | 动作发现缺失 | 无 | `GET /v1/actions` 列出所有可用动作 |

---

## 核心概念

### Action 与 Rule Group 的关系

```
Action (业务动作)                 Rule Group (规则组)
├── action_name = "credit_assessment"  ├── name = "credit_assessment"
├── 对外暴露的统一入口              ├── 内部执行逻辑
├── execute → 实际执行              ├── steps → 执行步骤
├── simulate → 干运行              └── DAG → 依赖关系
└── explain → 执行解释
```

- Action 是 Rule Group 的面向消费者的封装
- 一个 Action 对应一个 Rule Group（1:1 映射）
- Action 名称 = Rule Group 名称
- Action 通过 Space 关联获取执行上下文

---

## 路由详情

### GET /v1/actions — 列出所有可用动作

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `space_id` | string | 指定 Space 内的动作 |
| `enabled` | boolean | 仅返回启用的动作 |

**响应：**

```json
{
  "success": true,
  "data": {
    "actions": [
      {
        "action_name": "credit_assessment",
        "description": "信用评估",
        "type": "decision",
        "applies_to": {
          "fact_objects": ["Supplier"],
          "categories": {}
        },
        "inputs": [
          { "name": "registered_capital", "type": "attribute" }
        ],
        "outputs": [
          { "name": "eligible", "type": "boolean" },
          { "name": "credit_score", "type": "integer" }
        ],
        "enabled": true
      }
    ]
  }
}
```

**对齐服务：** `RuleService` + `SemanticSpaceStorage`

---

### GET /v1/actions/{action_name} — 获取动作详情

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `action_name` | string | 动作名称，对应 Rule Group name |

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `space_id` | string | 指定 Space |

**响应：**

```json
{
  "success": true,
  "data": {
    "action_name": "credit_assessment",
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
    "steps_count": 3,
    "enabled": true
  }
}
```

**对齐服务：** `RuleService`

---

### POST /v1/actions/{action_name}/execute — 执行动作

**请求：**

```json
{
  "space_id": "space.supply_chain_finance",
  "entity_id": "S001",
  "context_overrides": {
    "market_condition": "BULL"
  },
  "dry_run": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `space_id` | string | 是 | 目标 Space |
| `entity_id` | string | 是 | 目标实体 |
| `context_overrides` | object | 否 | 上下文覆盖 |
| `dry_run` | boolean | 否 | 干运行模式（默认 false） |

**响应：**

```json
{
  "success": true,
  "data": {
    "action_name": "credit_assessment",
    "entity_id": "S001",
    "space_id": "space.supply_chain_finance",
    "execution_time_ms": 15,
    "results": {
      "steps_executed": [
        {
          "step_id": "step.uuid-xxx",
          "step_name": "计算信用分数",
          "condition_evaluated": "True",
          "action_taken": "then",
          "computation": {
            "formula": "min(5000000 * 0.5, 10000000)",
            "result": 2500000
          }
        }
      ]
    },
    "outputs": {
      "eligible": true,
      "credit_score": 85,
      "credit_grade": "A"
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

### POST /v1/actions/{action_name}/simulate — 模拟执行

干运行模式，不持久化结果。适用于 What-if 场景分析。

**请求：**

```json
{
  "space_id": "space.supply_chain_finance",
  "entity_data": {
    "entity_id": "S001",
    "_fact_object": "Supplier",
    "attributes": {
      "company_name": "供应商A",
      "registered_capital": { "value": 5000000, "currency": "CNY" },
      "status": "ACTIVE"
    }
  },
  "context_overrides": {
    "registered_capital": { "value": 10000000, "currency": "CNY" }
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `space_id` | string | 是 | 目标 Space |
| `entity_data` | object | 是 | 模拟实体数据 |
| `context_overrides` | object | 否 | 上下文覆盖 |

**响应：**

```json
{
  "success": true,
  "data": {
    "action_name": "credit_assessment",
    "simulation": true,
    "entity_id": "S001",
    "execution_time_ms": 8,
    "results": {
      "steps_executed": [
        {
          "step_id": "step.uuid-xxx",
          "step_name": "计算信用分数",
          "condition_evaluated": "True",
          "action_taken": "then",
          "computation": {
            "formula": "min(10000000 * 0.5, 10000000)",
            "result": 5000000
          }
        }
      ]
    },
    "outputs": {
      "eligible": true,
      "credit_score": 92,
      "credit_grade": "A+"
    }
  }
}
```

**对齐服务：** `SimulationService`

---

### GET /v1/actions/{action_name}/explain/{entity_id} — 解释执行

返回指定实体在该动作下的执行解释，包含：
1. 适用规则列表
2. 指标计算过程
3. 规则判定依据
4. 决策推理链

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `space_id` | string | 目标 Space |
| `explain_level` | string | 解释深度: `summary` / `detailed` / `full` |

**响应：**

```json
{
  "success": true,
  "data": {
    "action_name": "credit_assessment",
    "entity_id": "S001",
    "space_id": "space.supply_chain_finance",
    "explanation": {
      "applicable_rules": [
        {
          "rule_id": "rg.credit.assessment",
          "rule_name": "信用评估",
          "applies": true,
          "reason": "Supplier 类型实体，状态 ACTIVE"
        }
      ],
      "metric_computation": [
        {
          "metric_name": "credit_score",
          "formula": "weighted_sum(registered_capital, guarantee_exposure)",
          "inputs": {
            "registered_capital": 5000000,
            "guarantee_exposure": 2000000
          },
          "result": 85
        }
      ],
      "rule_evaluation": [
        {
          "step_name": "资本门槛检查",
          "condition": "registered_capital.value >= 1000000",
          "evaluated": true,
          "action": "then",
          "output": { "eligible": true }
        }
      ],
      "decision_reasoning": "供应商 S001 注册资本 500 万元，超过 100 万元门槛，信用评分 85 分，评级 A，准入通过。"
    }
  }
}
```

**对齐服务：** `AnalysisService`

---

## 旧路由映射

| 旧路由 | 新路由 | 兼容策略 |
|--------|--------|---------|
| `POST /v1/rules/execute` | `POST /v1/actions/{action_name}/execute` | 301 重定向 |
| `POST /v1/analysis/execute` | `POST /v1/actions/{action_name}/execute` | 301 重定向 |
| `POST /v1/analysis/dry-run` | `POST /v1/actions/{action_name}/simulate` | 301 重定向 |
| `POST /v1/rule-groups/{name}/simulate` | `POST /v1/actions/{action_name}/simulate` | 301 重定向 |
| `POST /v1/consumption/views/{id}/execute/analyze` | `POST /v1/views/{id}/execute/analyze`（保留）或 `POST /v1/actions/{name}/execute` | 301 重定向 |
| `POST /v1/consumption/views/{id}/execute/simulate` | `POST /v1/views/{id}/execute/simulate`（保留）或 `POST /v1/actions/{name}/simulate` | 301 重定向 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| 1 | Actions 与 Views 执行端点并存 | Views 执行端点保留用于前端消费面场景；Actions 用于 API/MCP 直接调用场景 |
| 2 | Action 必须指定 `space_id` | 消除全局执行，确保执行上下文明确 |
| 3 | `simulate` 使用 `entity_data` 而非 `entity_id` | 模拟场景下实体可能不存在，允许传入假设数据 |
| 4 | `explain` 为新增端点 | 旧架构缺少执行解释能力，对 Agent 可解释性至关重要 |

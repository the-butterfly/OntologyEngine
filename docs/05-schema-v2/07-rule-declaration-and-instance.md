# 规则声明与实例分离

> **Status**: v1.0
> **Date**: 2026-04-12

## 1. 设计背景

在 Schema v2 中，**规则 (Rule)** 被明确区分为两个概念：

1. **规则声明 (Rule Definition)** - 定义规则的作用对象、输入输出要素
2. **规则实例 (Rule Logic)** - 定义具体的条件表达式和动作

这样设计的好处：
- 一个声明可以对应多个场景实例
- 业务逻辑可独立于声明演进
- 便于版本管理和回滚

## 2. 规则声明 (Rule Definition)

### 2.1 结构

```yaml
rule_definition:
  id: string                    # 全局唯一标识 (如 R001)
  name: string                  # 显示名称
  description: string | null     # 描述
  rule_type: string             # constraint | inference | alert | decision
  priority: integer             # 优先级 (数字越大越优先)

  # 作用对象 - 声明此规则作用于哪些实体类型
  target_objects:
    - string  # 如 "Supplier", "CoreEnterprise"

  # 输入要素 - 声明此规则需要哪些输入
  input_elements:
    - id: string
      name: string
      type: string  # metric | attribute | category_tag
    - ...

  # 输出要素 - 声明此规则会产生哪些输出
  output_elements:
    - id: string
      name: string
      type: string  # flag | computed_value | alert
    - ...

  # 关联的规则实例
  logic_ids:
    - string  # 关联的 rule_logic.id

  enabled: boolean              # 是否启用
```

### 2.2 规则类型

| 类型 | 说明 | 典型用途 |
|------|------|----------|
| `constraint` | 约束规则 | 准入检查、资格校验 |
| `inference` | 推理规则 | 从已知推导未知 |
| `alert` | 预警规则 | 风险监控、异常告警 |
| `decision` | 决策规则 | 最终决策输出 |

### 2.3 示例

```yaml
rule_definition:
  id: R001_credit_limit
  name: 授信额度计算
  description: 根据信用评分和资产情况计算授信额度
  rule_type: decision
  priority: 100

  target_objects:
    - Supplier
    - CoreEnterprise

  input_elements:
    - id: credit_score
      name: 信用评分
      type: metric
    - id: net_asset
      name: 净资产
      type: metric
    - id: industry
      name: 行业分类
      type: category_tag

  output_elements:
    - id: credit_limit
      name: 授信额度
      type: computed_value
    - id: risk_level
      name: 风险等级
      type: flag

  logic_ids:
    - R001_logic_manufacturing
    - R001_logic_retail

  enabled: true
```

## 3. 规则实例 (Rule Logic)

### 3.1 结构

```yaml
rule_logic:
  id: string                    # 全局唯一标识 (如 R001_logic_1)
  definition_id: string         # 关联的规则声明 ID

  name: string | null          # 显示名称
  description: string | null    # 描述

  # 适用条件 - 此实例在什么条件下生效
  applicable_conditions:
    - classification: string    # 分类维度 (如 "industry", "scale")
      operator: string          # in | eq | contains
      value: any               # 匹配值

  # 前置条件表达式
  when:
    expression: string          # 条件表达式 (如 "credit_score >= 60")
    # 或
    allOf:
      - expression: string
      - ...
    anyOf:
      - expression: string
      - ...

  # 满足条件时的动作
  then_action:
    action_type: string         # set_flag | compute | alert | approve | reject
    output:
      # action_type-specific fields

  # 不满足条件时的动作 (可选)
  else_action:
    action_type: string
    output: {...}

  priority: integer             # 实例优先级 (在同一声明的实例间排序)
  version: integer             # 版本号
  environment: string          # 环境标签 (default | test | production)
```

### 3.2 动作类型

| 动作类型 | 说明 | 输出结构 |
|----------|------|----------|
| `set_flag` | 设置标志 | `{ flag_name: value }` |
| `compute` | 计算值 | `{ result_name: expression }` |
| `alert` | 触发预警 | `{ alert_level, message }` |
| `approve` | 批准通过 | `{ decision: APPROVED }` |
| `reject` | 拒绝 | `{ decision: REJECTED, reason }` |

### 3.3 示例

```yaml
# 制造业场景
rule_logic:
  id: R001_logic_manufacturing
  definition_id: R001_credit_limit
  name: 制造业授信规则

  applicable_conditions:
    - classification: industry
      operator: eq
      value: 制造业

  when:
    expression: "credit_score >= 60 AND net_asset >= 5000000"

  then_action:
    action_type: compute
    output:
      credit_limit: "net_asset * 0.5"
      risk_level: "LOW"

  else_action:
    action_type: set_flag
    output:
      eligible: false
      reason: "不满足授信条件"

  priority: 100
  version: 1
  environment: default
---
# 批发零售场景
rule_logic:
  id: R001_logic_retail
  definition_id: R001_credit_limit
  name: 批发零售授信规则

  applicable_conditions:
    - classification: industry
      operator: eq
      value: 批发零售

  when:
    expression: "credit_score >= 70 AND net_asset >= 2000000"

  then_action:
    action_type: compute
    output:
      credit_limit: "net_asset * 0.3"
      risk_level: "MEDIUM"

  priority: 100
  version: 1
  environment: default
```

## 4. 执行流程

### 4.1 规则选择

给定一个实体和维度，执行时按以下步骤选择规则实例：

```
1. 根据 entity.concept_type 筛选 target_objects 包含该类型的规则声明
2. 根据 dimension 筛选 applicable_scope.dimensions 包含该维度的规则声明
3. 对筛选后的规则声明，按 priority 降序排序
4. 对于每个规则声明，遍历其关联的 rule_logics：
   a. 检查 applicable_conditions 是否满足
   b. 满足则选中，执行 then_action
   c. 不满足则尝试下一个 logic
   d. 都不满足则执行 else_action（如果有）
```

### 4.2 DAG 构建

规则实例之间可能存在依赖关系，通过 `input_elements` 引用其他规则的 `output_elements`：

```
R001: 准入检查 ──(passed)──▶ R002: 信用评分
                                  │
                                  ▼ (score)
R003: 额度计算 ◀──(input)── R002
```

### 4.3 依赖解析

在执行前，系统自动解析依赖图并进行拓扑排序：

```python
class RuleExecutor:
    def execute(self, entity_id, dimension, context):
        # 1. 构建 DAG
        dag = self.build_dag(
            rules=self.get_applicable_rules(entity_id, dimension),
            context=context
        )

        # 2. 拓扑排序
        execution_order = list(nx.topological_sort(dag))

        # 3. 按序执行
        for rule_id in execution_order:
            self.execute_rule(rule_id, context)
```

## 5. API 设计

### 5.1 规则声明 CRUD

```
POST   /v1/management/{spaceId}/schema/L4/rules/definitions
GET    /v1/management/{spaceId}/schema/L4/rules/definitions
GET    /v1/management/{spaceId}/schema/L4/rules/definitions/{definitionId}
PUT    /v1/management/{spaceId}/schema/L4/rules/definitions/{definitionId}
DELETE /v1/management/{spaceId}/schema/L4/rules/definitions/{definitionId}
```

### 5.2 规则实例 CRUD

```
POST   /v1/management/{spaceId}/schema/L4/rules/logics
GET    /v1/management/{spaceId}/schema/L4/rules/logics
GET    /v1/management/{spaceId}/schema/L4/rules/logics/{logicId}
PUT    /v1/management/{spaceId}/schema/L4/rules/logics/{logicId}
DELETE /v1/management/{spaceId}/schema/L4/rules/logics/{logicId}
```

### 5.3 请求/响应示例

**创建规则声明**:
```json
POST /v1/management/{spaceId}/schema/L4/rules/definitions
{
  "id": "R001_credit_limit",
  "name": "授信额度计算",
  "rule_type": "decision",
  "priority": 100,
  "target_objects": ["Supplier", "CoreEnterprise"],
  "input_elements": [
    { "id": "credit_score", "name": "信用评分", "type": "metric" }
  ],
  "output_elements": [
    { "id": "credit_limit", "name": "授信额度", "type": "computed_value" }
  ],
  "enabled": true
}
```

**创建规则实例**:
```json
POST /v1/management/{spaceId}/schema/L4/rules/logics
{
  "id": "R001_logic_manufacturing",
  "definition_id": "R001_credit_limit",
  "name": "制造业授信规则",
  "applicable_conditions": [
    { "classification": "industry", "operator": "eq", "value": "制造业" }
  ],
  "when": {
    "expression": "credit_score >= 60 AND net_asset >= 5000000"
  },
  "then_action": {
    "action_type": "compute",
    "output": {
      "credit_limit": "net_asset * 0.5",
      "risk_level": "LOW"
    }
  },
  "priority": 100
}
```

## 6. 版本管理

### 6.1 声明版本

规则声明的变更是分层版本的一部分：
- 修改声明 → 记录到 `L4_business_logic` 版本
- 声明版本只增不减

### 6.2 实例版本

规则实例独立版本管理：
- 修改实例 → 记录到 `L4_business_logic.rule_logics` 版本
- 可独立于声明进行回滚
- `version` 字段记录实例版本号

### 6.3 兼容性

修改规则声明时需考虑：
- `input_elements` 减少：可能导致已有 logic 引用不存在的输入
- `output_elements` 减少：可能导致依赖此输出的规则失效
- `target_objects` 变更：可能影响已匹配的实体

**建议**：变更声明前先检查影响的实例。

---

*文档结束*

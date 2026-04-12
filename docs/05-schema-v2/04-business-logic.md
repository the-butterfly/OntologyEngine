# L4: 业务逻辑 (Business Logic)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-12
verified_against: docs-only
related_docs:
  - 00-overview.md
  - 00b-semantic-space-architecture.md
  - 01-fact-objects.md
  - 02-categorization.md
  - 03-analytical-elements.md
  - 08-version-management.md
  - 09-canonical-schema-spec.md
---

> **Status**: v2.0 (with Declaration/Instance separation)
> **Date**: 2026-04-12

## 核心概念

L4 业务逻辑包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Rule Definition)** | 规则定义 | 作用对象、输入/输出要素、优先级 |
| **实例 (Rule Logic)** | 规则逻辑 | 条件表达式、动作、执行分支 |

---

## 1. 声明：规则定义 (Rule Definition)

### 1.1 结构

```yaml
rule_definition:
  id: string                    # 全局唯一标识 (如 R001)
  name: string                  # 显示名称
  description: string | null    # 描述

  rule_type: constraint | inference | alert | decision

  # 作用域声明: 哪些实体类型适用
  target_objects:
    - string  # 如 "Supplier", "Company"

  # 输入要素 - 声明此规则需要哪些输入
  input_elements:
    - id: string
      name: string
      type: metric | attribute | category_tag

  # 输出要素 - 声明此规则会产生哪些输出
  output_elements:
    - id: string
      name: string
      type: flag | computed_value | alert

  priority: integer             # 优先级 (数字越大越优先)

  # 关联的规则实例
  logic_ids:
    - string  # 关联的 rule_logic.id

  enabled: boolean              # 是否启用
```

### 1.2 规则类型

| 类型 | 说明 | 典型用途 |
|------|------|----------|
| `constraint` | 约束规则 | 准入检查、资格校验 |
| `inference` | 推理规则 | 从已知推导未知 |
| `alert` | 预警规则 | 风险监控、异常告警 |
| `decision` | 决策规则 | 最终决策输出 |

### 1.3 示例

```yaml
rule_definition:
  id: R001_credit_check
  name: 信用检查
  description: 根据信用评分和资产情况判断授信资格
  rule_type: constraint

  target_objects:
    - Supplier
    - CoreEnterprise

  input_elements:
    - id: credit_score
      name: 信用评分
      type: metric
    - id: overdue_ratio
      name: 逾期比例
      type: metric
    - id: registered_capital
      name: 注册资本
      type: attribute

  output_elements:
    - id: eligible
      name: 是否合格
      type: flag
    - id: risk_level
      name: 风险等级
      type: flag

  priority: 100
  logic_ids:
    - R001_logic_manufacturing
    - R001_logic_retail
  enabled: true
```

---

## 2. 实例：规则逻辑 (Rule Logic)

### 2.1 结构

```yaml
rule_logic:
  id: string                    # 全局唯一标识
  definition_id: string          # 关联的规则声明 ID

  name: string | null
  description: string | null

  # 适用条件 - 此实例在什么条件下生效
  applicable_conditions:
    - classification: string    # 分类维度
      operator: string          # eq | in | contains
      value: any               # 匹配值

  # 前置条件
  when:
    expression: string          # 条件表达式

  # 满足条件时的动作
  then_action:
    action_type: set_flag | compute | alert | approve | reject
    output:
      # action_type-specific fields

  # 不满足条件时的动作 (可选)
  else_action:
    action_type: set_flag | compute | reject
    output: {...}

  priority: integer             # 实例优先级
  version: integer             # 版本号
  environment: string          # default | test | production
```

### 2.2 动作类型

| 动作类型 | 说明 | 输出结构 |
|----------|------|----------|
| `set_flag` | 设置标志 | `{ flag_name: value }` |
| `compute` | 计算值 | `{ result_name: expression }` |
| `alert` | 触发预警 | `{ alert_level, message }` |
| `approve` | 批准通过 | `{ decision: APPROVED }` |
| `reject` | 拒绝 | `{ decision: REJECTED, reason }` |

### 2.3 示例

```yaml
# 制造业场景
rule_logic:
  id: R001_logic_manufacturing
  definition_id: R001_credit_check
  name: 制造业信用检查

  applicable_conditions:
    - classification: industry_category
      operator: eq
      value: "C"  # 制造业

  when:
    expression: "credit_score >= 60 AND overdue_ratio <= 0.05"

  then_action:
    action_type: set_flag
    output:
      eligible: true
      risk_level: "LOW"

  else_action:
    action_type: set_flag
    output:
      eligible: false
      reason: "不满足制造业信用条件"

  priority: 100
  version: 1
  environment: default
---
# 批发零售场景
rule_logic:
  id: R001_logic_retail
  definition_id: R001_credit_check
  name: 批发零售信用检查

  applicable_conditions:
    - classification: industry_category
      operator: eq
      value: "F"  # 批发零售

  when:
    expression: "credit_score >= 70 AND overdue_ratio <= 0.03"

  then_action:
    action_type: set_flag
    output:
      eligible: true
      risk_level: "MEDIUM"

  priority: 100
  version: 1
  environment: default
```

---

## 3. Formula 计算逻辑

### 3.1 两级安全执行模型

Formula 按复杂度自动选择执行器：

| 级别 | 触发条件 | 执行器 | 安全约束 |
|------|----------|--------|----------|
| L0 | 无控制流关键词 | simpleeval | 白名单函数 |
| L1 | 含 if/for/while 等 | AST 白名单沙箱 | 循环上限 1000，超时 5s |

### 3.2 L0: 简单计算

```yaml
# 单行 formula，自动使用 simpleeval
action:
  action_type: compute
  output:
    credit_limit: "registered_capital * 0.5"
```

### 3.3 L1: 复杂逻辑

```yaml
# 含控制流，切换 AST 沙箱
action:
  action_type: compute
  output:
    discount_rate: |
      if credit_score >= 90:
          rate = 0.15
      elif credit_score >= 80:
          rate = 0.10
      else:
          rate = 0.05
      rate
```

---

## 4. 算子类型

| 算子 | 用途 | 说明 |
|------|------|------|
| `FORMULA` | 简单表达式 | 直接计算 |
| `SWITCH` | 多分支条件 | 根据值匹配不同计算 |
| `SCORECARD` | 评分卡模型 | 加权打分 |
| `DECISION_TABLE` | 决策表 | 多条件组合查表 |
| `GRAPH` | 图检索计算 | 遍历关系网络 |
| `MODEL_INFERENCE` | 外部模型 | 调用 ML 模型 |
| `LLM_INFERENCE` | 大模型推理 | 调用 LLM |

---

## 5. 运行时行为

### 5.1 规则选择流程

```
1. 根据 entity.concept_type 筛选 target_objects 包含该类型的规则声明
2. 对筛选后的规则声明，按 priority 降序排序
3. 对于每个规则声明，遍历其关联的 rule_logics：
   a. 检查 applicable_conditions 是否满足
   b. 满足则选中
   c. 执行 then_action
```

### 5.2 依赖解析与 DAG

规则实例之间可能存在依赖，通过 `input_elements` 引用：

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

---

## 6. 与 L3 的交互

### 6.1 指标覆盖

L3 指标可声明 `overridable: true`（默认），允许 L4 提供覆盖计算：

```yaml
# L3: 声明指标
analytical_element_declaration:
  id: credit_score
  name: 信用评分
  element_type: derived
  overridable: true
  dependencies:
    - financial_health_score
    - external_credit_score

# L4: 覆盖计算逻辑
rule_logic:
  id: R002_logic
  definition_id: R002_custom_scoring
  when:
    expression: "has_external_score == true"
  then_action:
    action_type: compute
    output:
      credit_score: "external_credit_score"  # 直接使用外部评分
```

### 6.2 跨引擎调用

```
规则执行 → L3 指标计算 → L4 规则执行
                ↓
         按需计算或从缓存获取
```

---

## 7. API 设计

### 7.1 声明 CRUD

```
GET    /v1/management/{spaceId}/schema/L4/rules/definitions
POST   /v1/management/{spaceId}/schema/L4/rules/definitions
GET    /v1/management/{spaceId}/schema/L4/rules/definitions/{id}
PUT    /v1/management/{spaceId}/schema/L4/rules/definitions/{id}
DELETE /v1/management/{spaceId}/schema/L4/rules/definitions/{id}
```

### 7.2 实例 CRUD

```
GET    /v1/management/{spaceId}/schema/L4/rules/logics
POST   /v1/management/{spaceId}/schema/L4/rules/logics
GET    /v1/management/{spaceId}/schema/L4/rules/logics/{id}
PUT    /v1/management/{spaceId}/schema/L4/rules/logics/{id}
DELETE /v1/management/{spaceId}/schema/L4/rules/logics/{id}
```

---

## 8. 与 v1 的区别

| v1 | v2 |
|-----|-----|
| 规则硬编码 entity_types | 规则声明 + 作用对象分离 |
| 规则逻辑散落各处 | 规则声明 + 规则实例分离 |
| 无多实例支持 | 一声声明 + 多逻辑实例 |
| 无条件分支 | applicable_conditions 支持场景分支 |
| 无版本管理 | 声明/实例独立版本 |

---

*文档结束*

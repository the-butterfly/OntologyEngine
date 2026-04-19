# L4: 业务逻辑 (Business Logic)

---
status: draft
phase: phase1
source_of_truth: false
last_verified: 2026-04-14
verified_against: docs/05-schema-v2/09-canonical-schema-spec.md
related_docs:
  - 00-overview.md
  - 00b-semantic-space-architecture.md
  - 01-fact-objects.md
  - 02-categorization.md
  - 03-analytical-elements.md
  - 08-version-management.md
  - 09-canonical-schema-spec.md
related_adrs:
  - architecture/decisions/007-l3-l4-computation-boundary.md
  - architecture/decisions/008-rule-model-unification.md
---

> **Status**: v2.0 (aligned with Canonical Grammar)
> **Last Verified**: 2026-04-14
> **verified_against**: docs/05-schema-v2/09-canonical-schema-spec.md

## 核心概念

L4 业务逻辑包含**声明**和**实例**两个层面：

| 层面 | 内容 | 说明 |
|------|------|------|
| **声明 (Rule Definition)** | 规则定义 | 作用对象、输入/输出要素、优先级 |
| **实例 (Rule Logic)** | 规则逻辑 | 条件表达式、动作、执行分支 |

---

## 1. 声明：规则定义 (Rule Definition)

### 1.1 结构

在 Schema v2 中，规则定义通过 `business_logic.rule_definitions[]` 声明：

```yaml
business_logic:
  rule_definitions:
    - name: string                    # 规则定义名，全局唯一
      description: string?
      type: enum                      # constraint | inference | alert | decision
      priority: integer?             # 执行优先级，数字越大越先执行，默认 100

      applies_to:                     # 规则适用对象
        fact_objects: [string]?       # 实体类型名列表；空数组 [] 表示 GLOBAL（所有实体）
        categories: dict?              # 分类过滤，格式: {dimension_name: [value_codes]}

      preconditions: [Precondition]? # 前置条件，不满足则跳过整个规则组
      inputs: [IOElement]?            # 输入要素
      outputs: [IOElement]?           # 输出要素

      overrides: string?              # 可选，覆盖 L3 overridable 指标（引用 metric.name）
```

### Precondition（前置条件）

```yaml
- expression: string              # 布尔表达式
  fail:                           # 不满足时的动作
    reject: boolean?               # 是否拒绝
    reason: string?                # 拒绝原因
    action: string?                # 其他动作
```

### IOElement（输入/输出要素）

```yaml
- metric: string?                 # 引用 L3 指标名
  attribute: string?              # 引用 L1 属性路径
  rule_output: string?            # 引用其他规则的输出名
  name: string?                    # 要素名称
  type: enum                       # boolean | integer | decimal | Money | string | flag
```

> **设计原则**：优先使用 `metric` 引用 L3 指标；`attribute` 直接引用 L1 属性；两者都指定时，`metric` 优先。

### applies_to 结构详解

`applies_to` 定义规则的适用范围：

```yaml
applies_to:
  # 实体类型过滤
  fact_objects:
    - Supplier          # 仅适用于 Supplier 实体
    - CoreEnterprise    # 仅适用于核心企业

  # 或全局规则（空数组表示所有实体）
  fact_objects: []

  # 分类维度过滤（可选）
  categories:
    industry_category: ["C", "F"]   # 仅当行业分类为制造业或批发零售时生效
    company_scale: ["LARGE", "MEDIUM"]  # 仅当规模为大型或中型时生效
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
business_logic:
  rule_definitions:
    - name: credit_check
      description: 信用检查 - 根据信用评分和资产情况判断授信资格
      type: constraint

      applies_to:
        fact_objects:
          - Supplier
          - CoreEnterprise

      preconditions:
        - expression: "credit_score > 0"
          fail:
            reject: true
            reason: "无有效信用评分"

      inputs:
        - metric: credit_score
          type: score
        - metric: overdue_ratio
          type: percentage
        - attribute: registered_capital.value
          type: decimal

      outputs:
        - name: eligible
          type: flag
        - name: risk_level
          type: flag
        - name: credit_limit
          type: Money

      priority: 100

    - name: credit_limit_override
      description: 自定义授信额度计算
      type: decision
      overrides: credit_limit           # 覆盖 L3 的 credit_limit 指标
      inputs:
        - metric: credit_score
          type: score
        - metric: guarantee_exposure
          type: Money
      outputs:
        - name: credit_limit
          type: Money
```

---

## 2. 实例：规则逻辑 (Rule Logic)

### 2.1 结构

在 Schema v2 中，规则逻辑通过 `business_logic.rule_logics[]` 声明：

```yaml
business_logic:
  rule_logics:
    - name: string                    # 规则逻辑名，全局唯一
      description: string?
      type: enum                      # decision_table | scorecard | switch | binning | graph_op | custom
      steps: [Step]                   # 步骤序列，支持 DAG 依赖
```

### Step（步骤定义）

```yaml
- id: string                      # 步骤 ID，唯一
  name: string                    # 步骤名称
  description: string?
  priority: integer?              # 执行优先级，默认 100
  depends_on: [string]?           # 依赖的前置步骤 ID 列表（形成 DAG）

  condition:                      # 触发条件（支持复杂表达式）
    expression: string?            # 布尔表达式（当 type!=graph_op 时）
    and: [string]?                 # 复合 AND 条件
    or: [string]?                 # 复合 OR 条件
    not: string?                  # 取反条件
    # 条件表达式中可用变量：
    #   - L1 属性：attribute_name（如 status, registered_capital.value）
    #   - L3 指标：metric_name（如 credit_score, guarantee_exposure）
    #   - 规则输出：step_id.output（如 R001.eligible）
    #   - L2 维度：dimension_name（如 company_scale, risk_level）

  action:                         # 触发动作
    type: enum                    # set_flag | compute | reject | emit_alert | assign_category
    flag: string?                 # type=set_flag 时：flag 名称
    value: any?                   # type=set_flag 时：flag 值
    output: string?               # type=compute 时：输出变量名
    operator: enum?                # type=compute 时：算子类型
    formula: string?               # 通用计算公式
    category: string?              # type=assign_category 时：分类维度值
    reason: string?               # type=reject/emit_alert 时：原因
    severity: enum?                # type=emit_alert 时：INFO | WARNING | CRITICAL

  else:                           # 条件不满足时的备选动作（同 action 结构）
```

### 2.2 算子类型

| 算子 | 说明 | 使用场景 |
|------|------|----------|
| `GRAPH` | 图遍历算子 | 遍历关系网络计算担保敞口等 |
| `BINNING` | 分箱算子 | 将连续值分段映射 |
| `SWITCH` | 分支算子 | 根据值匹配不同计算分支 |
| `SCORECARD` | 评分卡算子 | 加权打分模型 |
| `WEIGHTED_SUM` | 加权求和算子 | 多因素加权求和 |
| `FORMULA` | 通用公式 | 任意表达式计算 |

### 2.3 规则逻辑类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| `decision_table` | 决策表 | 多条件组合查表 |
| `scorecard` | 评分卡 | 加权打分 |
| `switch` | 多分支 | 根据条件匹配不同分支 |
| `binning` | 分箱 | 连续值分段 |
| `graph_op` | 图操作 | 图遍历计算 |
| `custom` | 自定义 | 复杂自定义逻辑 |

### 2.4 示例

```yaml
business_logic:
  rule_logics:
    # 制造业信用检查
    - name: credit_check_manufacturing
      description: 制造业信用检查
      type: switch
      steps:
        - id: check_eligible
          priority: 100
          condition:
            and:
              - "credit_score >= 60"
              - "overdue_ratio <= 0.05"
          action:
            type: set_flag
            flag: eligible
            value: true
          else:
            type: set_flag
            flag: eligible
            value: false

        - id: assess_risk
          priority: 90
          depends_on: [check_eligible]
          condition:
            expression: "eligible == true"
          action:
            type: set_flag
            flag: risk_level
            value: "LOW"
          else:
            type: emit_alert
            severity: WARNING
            reason: "不满足制造业信用条件"

    # 批发零售信用检查
    - name: credit_check_retail
      description: 批发零售信用检查
      type: switch
      steps:
        - id: check
          condition:
            and:
              - "credit_score >= 70"
              - "overdue_ratio <= 0.03"
          action:
            type: set_flag
            flag: eligible
            value: true
          else:
            type: set_flag
            flag: eligible
            value: false

        - id: set_risk
          condition:
            expression: "eligible == true"
          action:
            type: set_flag
            flag: risk_level
            value: "MEDIUM"

    # 授信额度计算（评分卡）
    - name: credit_limit_scoring
      type: scorecard
      steps:
        - id: calculate
          action:
            type: compute
            output: credit_limit
            operator: SCORECARD
            variables:
              - name: credit_score_points
                points:
                  - condition: "credit_score >= 800"
                    score: 50
                  - condition: "credit_score >= 600"
                    score: 30
                  - condition: "credit_score >= 400"
                    score: 10
                  - condition: "credit_score < 400"
                    score: 0
                baseline: 0

              - name: capital_points
                points:
                  - condition: "registered_capital.value >= 100000000"
                    score: 30
                  - condition: "registered_capital.value >= 10000000"
                    score: 20
                  - condition: "registered_capital.value >= 1000000"
                    score: 10
                  - condition: "registered_capital.value < 1000000"
                    score: 0
                baseline: 0

            post_formula: "base_amount * (credit_score_points + capital_points) / 100"
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
  type: compute
  output: credit_limit
  formula: "registered_capital.value * 0.5"
```

### 3.3 L1: 复杂逻辑

```yaml
# 含控制流，切换 AST 沙箱
action:
  type: compute
  output: discount_rate
  formula: |
    if credit_score >= 90:
        rate = 0.15
    elif credit_score >= 80:
        rate = 0.10
    else:
        rate = 0.05
    rate
```

---

## 4. 算子详解

### GRAPH（图遍历算子）

```yaml
action:
  type: compute
  output: guarantee_exposure
  operator: GRAPH
  query:
    type: traversal
    relation: Guarantee
    direction: outgoing
    depth: 2
  aggregation:
    - type: sum
      field: guarantee_amount.value
      output: total_exposure
  post_process:
    formula: "total_exposure"
```

### BINNING（分箱算子）

```yaml
action:
  type: compute
  output: risk_band
  operator: BINNING
  bins:
    - range: [0, 30]
      result: LOW
    - range: [30, 70]
      result: MEDIUM
    - range: [70, 100]
      result: HIGH
```

### SWITCH（分支算子）

```yaml
action:
  type: compute
  output: grade
  operator: SWITCH
  branches:
    - condition: "credit_score >= 800"
      formula: "AAA"
    - condition: "credit_score >= 700"
      formula: "AA"
    - condition: "credit_score >= 600"
      formula: "A"
    - condition: "credit_score >= 400"
      formula: "B"
    - condition: "true"
      formula: "C"
```

### SCORECARD（评分卡算子）

```yaml
action:
  type: compute
  output: total_score
  operator: SCORECARD
  variables:
    - name: financial_score
      points:
        - condition: "current_ratio >= 2.0"
          score: 30
        - condition: "current_ratio >= 1.5"
          score: 20
        - condition: "current_ratio >= 1.0"
          score: 10
        - condition: "current_ratio < 1.0"
          score: 0
      baseline: 0

    - name: operation_score
      points:
        - condition: "business_stability >= 80"
          score: 30
        - condition: "business_stability >= 60"
          score: 20
        - condition: "business_stability >= 40"
          score: 10
        - condition: "business_stability < 40"
          score: 0
      baseline: 0

  post_formula: "financial_score + operation_score"
```

### WEIGHTED_SUM（加权求和算子）

```yaml
action:
  type: compute
  output: credit_limit
  operator: WEIGHTED_SUM
  variables:
    - name: score_factor
      points:
        - condition: "credit_score >= 800"
          score: 0.5
        - condition: "credit_score >= 600"
          score: 0.3
        - condition: "credit_score >= 400"
          score: 0.2
      baseline: 0.1
  formula: "registered_capital.value * score_factor"
```

---

## 5. 运行时行为

### 5.1 规则选择流程

```
1. 根据 entity._concept 筛选 applies_to.fact_objects 包含该类型的规则声明
2. 对筛选后的规则声明，按 priority 降序排序
3. 检查 applies_to.categories 分类过滤条件
4. 检查 preconditions 前置条件
5. 对于每个规则声明，遍历其关联的 rule_logics：
   a. 执行 steps 序列（支持 DAG 依赖排序）
   b. 执行 then_action 或 else_action
```

### 5.2 依赖解析与 DAG

规则步骤之间可能存在依赖，通过 `depends_on` 引用：

```python
class RuleExecutor:
    def execute(self, entity_id, context):
        # 1. 构建 DAG
        dag = self.build_dag(
            steps=self.rule_logic.steps,
            context=context
        )

        # 2. 拓扑排序
        execution_order = list(nx.topological_sort(dag))

        # 3. 按序执行
        for step_id in execution_order:
            self.execute_step(step_id, context)
```

---

## 6. 与 L3 的交互

### 6.1 指标覆盖

L3 指标可声明 `overridable=true`（默认 false），允许 L4 提供覆盖计算：

```yaml
# L3: 声明指标
analytical_elements:
  metrics:
    - name: credit_limit
      type: derived
      overridable: true
      dependencies:
        - credit_score
        - guarantee_exposure

# L4: 覆盖计算逻辑
business_logic:
  rule_definitions:
    - name: credit_limit_override
      overrides: credit_limit           # ← 引用 L3 指标名
      inputs:
        - metric: credit_score
        - attribute: registered_capital.value
      outputs:
        - name: credit_limit
          type: Money

  rule_logics:
    - name: custom_credit_limit
      steps:
        - id: calc
          action:
            type: compute
            output: credit_limit
            operator: WEIGHTED_SUM
            formula: "registered_capital.value * credit_score_factor"
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

| v1 | v2 (Canonical) |
|-----|----------------|
| 规则硬编码 entity_types | `applies_to` 结构化定义 |
| 规则逻辑散落各处 | `rule_definitions` + `rule_logics` 分离 |
| `input_elements` / `output_elements` | `inputs` / `outputs` |
| Flat `when/then_action` | `steps[].condition/action` |
| 无多实例支持 | 一声声明 + 多逻辑实例 |
| 无条件分支 | `applies_to.categories` 支持场景分支 |
| 无版本管理 | 声明/实例独立版本 |
| 无算子类型 | 明确 GRAPH/BINNING/SWITCH/SCORECARD/WEIGHTED_SUM |
| 无 `overrides` | 支持覆盖 L3 overridable 指标 |

---

## 9. 完整结构参考

完整 Schema v2 语法结构参见 [09-canonical-schema-spec.md](./09-canonical-schema-spec.md) 的 **L4: business_logic** 节。

*文档结束*

# 02: 规则算子与值域体系完善设计

---
status: draft
phase: phase1
source_of_truth: true   # [单一事实源] 算子体系 + 值域声明的唯一规范
last_verified: 2026-04-13
verified_against: docs-only
related_docs:
  - ../06-module-detailed-design/06-rule-engine.md
  - ../06-module-detailed-design/07-expression-engine.md
  - ../05-schema-v2/03-analytical-elements.md
  - ../05-schema-v2/04-business-logic.md
  - ../development/operator.md
related_adrs:
  - architecture/decisions/003-expression-engine-security.md
  - architecture/decisions/007-l3-l4-computation-boundary.md
---

## 1. 现状分析

### 1.1 当前算子清单

已有算子（`ontology_engine/engine/rule/operators/`）:

| 算子 | 注册名 | 文件 | 状态 |
|------|--------|------|------|
| SetFlag | `set_flag` | set_flag.py | ✅ 可用 |
| ApproveEligibility | `approve_eligibility` | set_flag.py | ✅ 可用 (向后兼容) |
| RejectEligibility | `reject_eligibility` | set_flag.py | ✅ 可用 (向后兼容) |
| ComputeFormula | `compute_formula` | compute.py | ✅ 可用 |
| CalculateCreditScore | `calculate_credit_score` | compute.py | ✅ 可用 (业务硬编码) |
| CalculateCreditLimit | `calculate_credit_limit` | compute.py | ✅ 可用 (业务硬编码) |
| DetermineInterestRate | `determine_interest_rate` | compute.py | ✅ 可用 (业务硬编码) |
| Switch | `switch` | switch.py | ✅ 可用 |
| Binning | `binning` | switch.py | ⚠️ 基础可用，缺闭区间和自定义映射 |
| Scorecard | `scorecard` | switch.py | ⚠️ 基础可用，缺 WOE/IV 计算 |
| TriggerAlert | `trigger_alert` | alert.py | ✅ 可用 |
| GraphTraversal | `graph_traversal` | alert.py | ❌ 桩实现，返回占位符 |

### 1.2 L4 设计文档定义的算子类型 vs 实际实现

| L4 设计定义 | 实际实现 | Gap |
|------------|----------|-----|
| `FORMULA` (简单表达式) | ✅ compute_formula | - |
| `SWITCH` (多分支条件) | ✅ switch | - |
| `SCORECARD` (评分卡模型) | ⚠️ scorecard | 缺 WOE/IV，缺分值→等级映射 |
| `DECISION_TABLE` (决策表) | ❌ 无 | 完全缺失 |
| `BINNING` (分箱) | ⚠️ binning | 缺闭区间、缺反向映射 |
| `GRAPH` (图检索计算) | ❌ 桩实现 | 依赖图存储 (01 文档) |
| `MODEL_INFERENCE` (外部模型) | ❌ 无 | 完全缺失 |
| `LLM_INFERENCE` (大模型推理) | ❌ 无 | 完全缺失 |

### 1.3 值域声明现状

**当前状态**: 几乎没有值域声明。

- L1 属性只有 `type` (string/integer/decimal 等) 和可选的 `validation.pattern`
- L3 AnalyticalElement 有 `range: [min, max]` 和 `unit`，但**不是强制的**，实际案例中极少使用
- L4 规则的输出要素没有值域约束
- 没有枚举值域、评分等级、金额区间等业务语义的值域声明

## 2. 值域体系设计 (Value Domain)

### 2.1 值域类型

```yaml
# value_domain 定义结构
value_domain:
  type: continuous | discrete | enum | score_grade | money_range
  name: string                    # 值域名 (如 "risk_level", "credit_grade")
  description: string             # 描述

  # type = continuous 时
  min: number                     # 最小值
  max: number                     # 最大值
  step: number | null             # 步长 (离散化后)
  unit: string | null             # 单位

  # type = discrete 时
  values:                         # 离散值列表
    - value: any
      label: string               # 显示名称
      sort_order: integer          # 排序权重
      color: string | null         # 前端展示色

  # type = enum 时
  enum_ref: string                # 引用 L1 enums 中的枚举名

  # type = score_grade 时
  grades:                         # 评分等级映射
    - grade: string               # 等级代码 (如 "AAA", "A")
      min_score: number           # 最低分 (含)
      max_score: number           # 最高分 (不含, 使用 exclusive_max: true)
      exclusive_max: boolean      # 是否不含上限
      label: string
      color: string | null
    default_grade: string         # 未命中任何等级时的默认

  # type = money_range 时
  currency: string                # 货币
  ranges:
    - min: number
      max: number
      label: string
```

### 2.2 在 Schema 各层中的使用

#### L1 事实对象属性值域

```yaml
fact_objects:
  declarations:
    - id: Company
      properties:
        - name: registered_capital
          type: Money
          value_domain:
            type: money_range
            currency: "CNY"
            min: 0
            description: "注册资本金额"

        - name: establishment_date
          type: date
          value_domain:
            type: continuous
            min: "1900-01-01"
            max: "2099-12-31"
            description: "成立日期"

        - name: status
          type: string
          value_domain:
            type: enum
            enum_ref: "CompanyStatus"
            description: "企业经营状态"
```

#### L3 分析要素值域

```yaml
analytical_elements:
  declarations:
    - id: credit_score
      name: 综合信用评分
      element_type: composite
      value_domain:
        type: score_grade
        min: 0
        max: 100
        unit: "分"
        grades:
          - grade: "AAA"
            min_score: 90
            max_score: 100
            exclusive_max: false
            label: "信用极好"
            color: "#52C41A"
          - grade: "AA"
            min_score: 85
            max_score: 90
            exclusive_max: true
            label: "信用优秀"
            color: "#73D13D"
          - grade: "A"
            min_score: 80
            max_score: 85
            exclusive_max: true
            label: "信用良好"
            color: "#95DE64"
          - grade: "BBB"
            min_score: 70
            max_score: 80
            exclusive_max: true
            label: "信用较好"
            color: "#FAAD14"
          - grade: "BB"
            min_score: 60
            max_score: 70
            exclusive_max: true
            label: "信用一般"
            color: "#FAAD14"
          - grade: "B"
            min_score: 50
            max_score: 60
            exclusive_max: true
            label: "信用偏低"
            color: "#FF7A45"
          - grade: "C"
            min_score: 30
            max_score: 50
            exclusive_max: true
            label: "信用较差"
            color: "#FF4D4F"
          - grade: "D"
            min_score: 0
            max_score: 30
            exclusive_max: true
            label: "信用极差"
            color: "#F5222D"
        default_grade: "D"
        description: "信用评分 → 信用等级映射"

    - id: overdue_ratio
      name: 逾期率
      element_type: derived
      value_domain:
        type: continuous
        min: 0.0
        max: 1.0
        unit: "百分比(小数)"
        description: "逾期金额占总应收的比例"

    - id: risk_level
      name: 风险等级
      element_type: derived
      value_domain:
        type: discrete
        values:
          - value: "LOW"
            label: "低风险"
            sort_order: 1
            color: "#52C41A"
          - value: "MEDIUM"
            label: "中风险"
            sort_order: 2
            color: "#FAAD14"
          - value: "HIGH"
            label: "高风险"
            sort_order: 3
            color: "#FF4D4F"
          - value: "CRITICAL"
            label: "极高风险"
            sort_order: 4
            color: "#F5222D"
        description: "综合风险等级判定"
```

#### L4 规则输出值域

```yaml
business_logic:
  rule_definitions:
    - id: R007_final_decision
      name: 综合授信决策
      rule_type: decision
      output_elements:
        - id: decision
          name: 决策结果
          type: flag
          value_domain:
            type: enum
            values: ["APPROVE", "APPROVE_WITH_CONDITIONS", "APPROVE_RESTRICTED", "REJECT"]
        - id: credit_limit
          name: 授信额度
          type: computed_value
          value_domain:
            type: money_range
            currency: "CNY"
            min: 0
            description: "最终批准授信额度"
```

### 2.3 值域校验服务

```python
# engine/validation/value_domain_validator.py

class ValueDomainValidator:
    """值域校验器 —— 在计算结果写入前做合法性检查。"""

    def validate(self, value: Any, domain: ValueDomain) -> ValidationResult:
        """校验值是否在值域内。"""
        result = ValidationResult(valid=True, violations=[])

        if domain.type == "continuous":
            if isinstance(value, (int, float)):
                if domain.min is not None and value < domain.min:
                    result.valid = False
                    result.violations.append(f"值 {value} 低于下限 {domain.min}")
                if domain.max is not None and value > domain.max:
                    result.valid = False
                    result.violations.append(f"值 {value} 超过上限 {domain.max}")
            else:
                result.valid = False
                result.violations.append(f"期望数值类型, 实际 {type(value)}")

        elif domain.type == "discrete":
            valid_values = {v["value"] for v in domain.values}
            if value not in valid_values:
                result.valid = False
                result.violations.append(f"值 '{value}' 不在合法集合 {valid_values} 中")

        elif domain.type == "enum":
            # 从 schema.enums 中查找合法值
            pass

        elif domain.type == "score_grade":
            # 检查分数范围
            pass

        elif domain.type == "money_range":
            if isinstance(value, (int, float)) and domain.min is not None:
                if value < domain.min:
                    result.valid = False
                    result.violations.append(f"金额 {value} 低于下限 {domain.min}")

        return result

    def map_to_grade(self, score: float, domain: ScoreGradeDomain) -> str:
        """将分数映射到等级。"""
        if domain.grades:
            for grade_def in domain.grades:
                min_s = grade_def["min_score"]
                max_s = grade_def["max_score"]
                exclusive = grade_def.get("exclusive_max", False)
                if exclusive:
                    if min_s <= score < max_s:
                        return grade_def["grade"]
                else:
                    if min_s <= score <= max_s:
                        return grade_def["grade"]
        return domain.default_grade
```

## 3. 算子增强设计

### 3.1 Binning 算子增强

**当前问题**: `BinningOperator` 不支持闭区间（`[min, max]`），只支持左闭右开 `[min, max)`。

**增强方案**:

```yaml
# Binning 算子增强
action:
  operator: "binning"
  inputs:
    value: "overdue_ratio"                    # 要分箱的字段
    bins:
      - min: 0
        max: 5
        inclusive_max: false                    # 新增: 是否包含上限 (默认 false)
        label: "LOW"
        description: "低逾期率"                  # 新增: 区间描述
      - min: 5
        max: 10
        inclusive_max: false
        label: "MED"
        description: "中逾期率"
      - min: 10
        max: 100
        inclusive_max: true                     # 闭区间: [10, 100]
        label: "HIGH"
        description: "高逾期率"
    default: "HIGH"
    output_key: "overdue_level"
```

**增强实现要点**:

```python
@OperatorRegistry.register("binning")
class BinningOperator(Operator):
    async def execute(self, inputs, config, context) -> dict:
        # ... 现有逻辑 ...
        for bin_def in bins:
            min_val = bin_def.get("min", float("-inf"))
            max_val = bin_def.get("max", float("inf"))
            inclusive_max = bin_def.get("inclusive_max", False)  # 新增
            label = bin_def.get("label", "UNKNOWN")

            if inclusive_max:
                if min_val <= value <= max_val:
                    return {
                        "bin": label,
                        "bin_value": value,
                        "bin_description": bin_def.get("description", ""),  # 新增
                    }
            else:
                if min_val <= value < max_val:
                    return {
                        "bin": label,
                        "bin_value": value,
                        "bin_description": bin_def.get("description", ""),
                    }

        return {"bin": default, "bin_value": value, "bin_description": "默认分组"}
```

### 3.2 Scorecard 算子增强

**当前问题**: `ScorecardOperator` 缺少 WOE (Weight of Evidence) 和 IV (Information Value) 支持，缺少分值→等级自动映射。

**增强方案**:

```yaml
# Scorecard 算子增强 — 支持 WOE 评分卡和分值映射
action:
  operator: "scorecard"
  inputs:
    # 方式一: 简单加权 (已有)
    factors:
      - name: "payment_score"
        weight: 0.3
        transform: "payment_score / 10"
      - name: "utilization_score"
        weight: 0.2
        transform: "1 - utilization_rate"

    # 方式二: WOE 评分卡 (新增)
    mode: "woe"                            # "simple" (默认) | "woe"
    base_score: 600                        # 基础分 (PDO 模型)
    pdo: 20                                # 每翻倍几率增加的分值
    base_odds: 1.0                         # 基础好坏比

    woe_variables:
      - name: "age_group"
        bins:
          - bin: "18-25"
            woe: -0.35
          - bin: "26-35"
            woe: -0.12
          - bin: "36-50"
            woe: 0.15
          - bin: "50+"
            woe: 0.28
        binning_input: "age"               # 从上下文获取的字段

      - name: "income_level"
        bins:
          - bin: "LOW"
            woe: -0.45
          - bin: "MEDIUM"
            woe: 0.05
          - bin: "HIGH"
            woe: 0.38
        binning_input: "annual_income"

    # 分值 → 等级映射 (新增)
    grade_mapping:
      - min_score: 700
        grade: "AAA"
      - min_score: 650
        grade: "AA"
      - min_score: 600
        grade: "A"
      - min_score: 550
        grade: "BBB"
      - min_score: 500
        grade: "BB"
      - min_score: 0
        grade: "B"

    output_key: "credit_scorecard"
```

**WOE 评分卡计算公式**:

```
Score = Base_Score + PDO × ln(Odds)
Odds = Base_Odds × Π exp(WOE_i)
```

```python
import math

def compute_woe_score(base_score, pdo, base_odds, woe_values):
    """计算 WOE 评分卡分数。"""
    log_odds = math.log(base_odds)
    for woe in woe_values:
        log_odds += woe
    score = base_score + pdo / math.log(2) * log_odds
    return round(score, 2)
```

### 3.3 DecisionTable 算子 (新增)

**决策树**: 多条件组合查表，等价于决策树的一组规则。

```yaml
# DecisionTable 算子 — 多条件组合决策
action:
  operator: "decision_table"
  inputs:
    # 决策条件列
    conditions:
      - name: "credit_score_bin"       # 字段名 (可以是 binning 的输出)
      - name: "debt_ratio_bin"
      - name: "has_guarantee"
    # 决策行: 每行是一个条件组合 → 输出
    rules:
      - conditions: ["LOW", "LOW", true]      # 高分低债有担保
        output:
          decision: "APPROVE"
          rate: 0.04
          max_amount_ratio: 2.0

      - conditions: ["LOW", "LOW", false]     # 高分低债无担保
        output:
          decision: "APPROVE_WITH_CONDITIONS"
          rate: 0.05
          max_amount_ratio: 1.5

      - conditions: ["LOW", "*", true]        # 高分任意负债有担保
        output:
          decision: "APPROVE_WITH_CONDITIONS"
          rate: 0.05
          max_amount_ratio: 1.2

      - conditions: ["HIGH", "*", "*"]        # 低分任意条件
        output:
          decision: "REJECT"
          reason: "信用评分过低"

    # "*" 表示通配 (匹配任意值)
    default:
      decision: "REVIEW"
      reason: "需人工审核"
```

**实现要点**:

```python
@OperatorRegistry.register("decision_table")
class DecisionTableOperator(Operator):
    """多条件组合决策表。

    支持:
    - 多列条件匹配 (AND 语义)
    - "*" 通配符 (匹配任意值)
    - 列表匹配 (["A", "B"] 表示值在列表中)
    - 按行优先顺序匹配 (第一条命中即返回)
    """

    @property
    def name(self) -> str:
        return "decision_table"

    async def execute(self, inputs, config, context) -> dict:
        conditions = inputs.get("conditions", [])
        rules = inputs.get("rules", [])
        default = inputs.get("default", {})

        # 从 context 中获取各条件的实际值
        eval_context = self._build_context(context)
        actual_values = [eval_context.get(c["name"]) for c in conditions]

        # 逐行匹配
        for rule in rules:
            rule_conds = rule.get("conditions", [])
            if self._matches(actual_values, rule_conds):
                return rule.get("output", {})

        # 默认行
        return default

    def _matches(self, actual: list, pattern: list) -> bool:
        """检查实际值是否匹配规则行。"""
        if len(actual) != len(pattern):
            return False
        for a, p in zip(actual, pattern):
            if p == "*":
                continue
            if isinstance(p, list) and a not in p:
                return False
            if a != p:
                return False
        return True
```

### 3.4 LLMJudge 算子 (新增)

**大模型推理**: 将上下文信息发送给 LLM，获取结构化判断结果。

```yaml
# LLMJudge 算子
action:
  operator: "llm_judge"
  inputs:
    # LLM 配置
    model: "gpt-4o-mini"                    # 或 "claude-3-haiku" 等
    temperature: 0.0                        # 0 = 确定性输出
    max_tokens: 200

    # 超时与成本控制
    timeout_ms: 5000                        # 单次调用超时
    max_retries: 2                          # 失败重试次数

    # Prompt 模板
    prompt: |
      你是信贷风险评估专家。根据以下信息判断风险等级。
      
      企业名称: {company_name}
      信用评分: {credit_score}
      逾期率: {overdue_ratio}
      担保链深度: {guarantee_chain_depth}
      近期预警: {recent_alerts_summary}

      请从以下选项中选择风险等级:
      LOW / MEDIUM / HIGH / CRITICAL

      同时给出简要理由(不超过50字)。

    # 输出解析
    output_format:
      type: "json_schema"
      schema:
        type: "object"
        properties:
          risk_level:
            type: "string"
            enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
          reason:
            type: "string"
        required: ["risk_level", "reason"]

    # 值域校验: LLM 输出必须符合此值域
    value_domain_ref: "risk_level"           # 引用 L3 声明中的值域

    output_key: "llm_risk_assessment"
```

**实现要点**:

```python
@OperatorRegistry.register("llm_judge")
class LLMJudgeOperator(Operator):
    """LLM 推理算子 — 调用大语言模型做结构化判断。

    安全约束:
    1. 超时保护: 单次调用 < timeout_ms
    2. 重试策略: 指数退避, 最多 max_retries 次
    3. 输出校验: JSON Schema 验证 + 值域校验
    4. 成本追踪: 记录 token 用量 (input/output)
    5. 降级策略: 超时/错误时返回 fallback_output
    """

    @property
    def name(self) -> str:
        return "llm_judge"

    async def execute(self, inputs, config, context) -> dict:
        model = inputs.get("model", "gpt-4o-mini")
        prompt_template = inputs.get("prompt", "")
        output_format = inputs.get("output_format", {})
        value_domain_ref = inputs.get("value_domain_ref")
        output_key = inputs.get("output_key", "llm_result")
        timeout_ms = inputs.get("timeout_ms", 5000)
        fallback_output = inputs.get("fallback_output", {"llm_error": "timeout"})

        # Step 1: 渲染 prompt
        eval_context = self._build_context(context)
        prompt = self._render_template(prompt_template, eval_context)

        # Step 2: 调用 LLM (带超时)
        try:
            result = await asyncio.wait_for(
                self._call_llm(model, prompt, inputs, output_format),
                timeout=timeout_ms / 1000.0,
            )
        except asyncio.TimeoutError:
            return {output_key: fallback_output, "llm_status": "timeout"}
        except Exception as e:
            return {output_key: fallback_output, "llm_status": f"error: {e}"}

        # Step 3: 值域校验
        if value_domain_ref:
            # 从 schema 中获取值域定义并校验
            validated = self._validate_output(result, value_domain_ref)
            if not validated.valid:
                result["validation_warnings"] = validated.violations

        result["llm_status"] = "success"
        result["llm_model"] = model
        result["llm_token_usage"] = self._last_token_usage
        return result
```

**降级策略**: 当 LLM 不可用时，可配置规则降级：

```yaml
action:
  operator: "llm_judge"
  inputs:
    # ... 正常配置 ...
    fallback:
      operator: "decision_table"              # 降级到决策表
      inputs: { ... }                         # 决策表的配置
```

### 3.5 GraphTraversal 算子完善

**依赖**: 01 图存储扩展文档。

```yaml
# GraphTraversal 算子完善
action:
  operator: "graph_traversal"
  inputs:
    # 查询配置
    relation_type: "Guarantee"                # 要遍历的关系类型
    direction: "outgoing"                     # 方向
    max_depth: 3                              # 最大深度

    # 聚合配置
    aggregation:
      type: "sum"                             # "count" | "sum" | "avg" | "min" | "max" | "collect"
      target_field: "guarantee_amount.value"   # 要聚合的字段 (从邻居实体属性中取)
      filter:                                 # 对邻居的过滤条件
        field: "status"
        operator: "eq"
        value: "ACTIVE"

    # 图算法 (与 aggregation 互斥)
    algorithm:
      type: "cycle_detection"                 # "shortest_path" | "cycle_detection" | "centrality"
      target_id: null                         # 目标节点 (shortest_path 时使用)

    # 输出
    output_key: "graph_result"
```

## 4. 算子注册表总览 (增强后)

| 算子 | 注册名 | 类别 | 新增/增强 | YAML 示例 |
|------|--------|------|-----------|-----------|
| SetFlag | `set_flag` | 逻辑 | 已有 | - |
| ComputeFormula | `compute_formula` | 计算 | 已有 | - |
| Switch | `switch` | 条件 | 已有 | 多分支选择 |
| **Binning** | `binning` | 条件 | **增强** | 闭区间、描述 |
| **Scorecard** | `scorecard` | 计算 | **增强** | WOE/IV、等级映射 |
| **DecisionTable** | `decision_table` | 条件 | **新增** | 多条件组合决策 |
| **LLMJudge** | `llm_judge` | 外部 | **新增** | LLM 推理+降级 |
| **GraphTraversal** | `graph_traversal` | 图 | **完善** | 真实图查询 |
| TriggerAlert | `trigger_alert` | 逻辑 | 已有 | - |
| ApproveEligibility | `approve_eligibility` | 兼容 | 已有 | - |
| RejectEligibility | `reject_eligibility` | 兼容 | 已有 | - |
| CalculateCreditScore | `calculate_credit_score` | 兼容 | 已有 | - |
| CalculateCreditLimit | `calculate_credit_limit` | 兼容 | 已有 | - |
| DetermineInterestRate | `determine_interest_rate` | 兼容 | 已有 | - |

## 5. Schema v2 变更

### 5.1 L1 属性扩展

```yaml
# L1 Property 增加可选 value_domain
property_declaration:
  name: string
  type: string | custom_type
  required: boolean
  unique: boolean
  default: any
  description: string
  validation:                              # 已有
    pattern: string
  value_domain:                            # 新增
    type: continuous | discrete | enum | score_grade | money_range
    # ... (值域定义见 2.1)
```

### 5.2 L3 AnalyticalElement 扩展

```yaml
# L3 增加必填 value_domain 和可选 expression_domain
analytical_element_declaration:
  id: string
  name: string
  element_type: atomic | derived | composite | graph | variable
  value_domain:                            # 新增: 指标值的值域声明 (建议必填)
    type: continuous | discrete | score_grade | ...
    # ...
  expression_domain:                       # 新增: 输入要素的值域约束
    - element_id: string                    # 依赖的要素 ID
      constraints:                          # 约束条件
        type: "range" | "enum" | "not_null"
        min: number | null
        max: number | null
        values: list | null
  # ... (其他字段不变)
```

## 6. 验收场景

### 场景 1: 评分卡 + WOE 计算

```
Given: 个人消费信贷 Schema, 含 age/income/debt_ratio 属性
When: 执行 WOE 评分卡算子
Then:
  - 输出 score 在 [0, 1000] 范围内
  - 输出 grade 在 ["AAA","AA","A","BBB","BB","B"] 中
  - 值域校验通过
```

### 场景 2: 决策表多条件匹配

```
Given: credit_score_bin = "LOW", debt_ratio_bin = "HIGH", has_guarantee = false
When: 执行 decision_table 算子
Then:
  - 匹配到 "HIGH, *, *" 规则行
  - 输出 decision = "REJECT"
```

### 场景 3: LLM Judge + 降级

```
Given: LLM 配置 timeout_ms = 100 (极短超时)
When: 执行 llm_judge 算子
Then:
  - 超时返回 fallback_output
  - llm_status = "timeout"
  - 不抛异常
```

### 场景 4: 值域校验拦截

```
Given: credit_score 计算结果 = 105
When: 值域校验 (max = 100)
Then:
  - 校验失败, violation = "值 105 超过上限 100"
  - 结果不写入 computed_metrics (或写入但标记 warning)
```

---

*文档结束*

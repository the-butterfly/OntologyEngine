# L4: 业务逻辑 (Business Logic)

> 定义作用的分析事实对象、适用的业务分类、输入要素、输出要素
>
> **核心原则**: Formula 统一在 L4 承载，结构化表达，单行限制

## 核心概念

```yaml
business_logic:
  rule_groups:       # 规则组
  decisions:         # 决策定义
  workflows:         # 流程编排
  operators:         # 算子注册
```

---

## 规则组

规则组是业务场景的逻辑单元，明确定义作用域。

### applies_to 作用域

```yaml
business_logic:
  rule_groups:
    - name: credit_assessment
      description: "融资授信评估"

      # 作用域声明: 哪些实体 + 哪些分类
      applies_to:
        # 为空表示 GLOBAL，适用于所有实体
        # fact_objects: []

        # 指定实体类型
        fact_objects:
          - Company

        # 指定分类条件（可选）
        categories:
          industry_category: ["C", "F", "I"]
          risk_level: [LOW, MEDIUM]

    - name: universal_alert_rules
      description: "全局预警规则"
      applies_to:
        # GLOBAL: 所有实体无条件适用
        fact_objects: []
        categories: {}
```

**applies_to 匹配规则**:

| 配置 | 含义 | 示例 |
|------|------|------|
| `fact_objects: []` | 所有实体类型 | 全局规则 |
| `fact_objects: [Company]` | 仅 Company 类型 | 特定对象规则 |
| `categories: {}` | 无视分类 | 仅按实体类型匹配 |
| `categories: {industry: ["C"]}` | 需同时满足分类 | 精确匹配 |

---

### 输入与输出

```yaml
      # 输入要素: 从 L3 获取的基础指标
      inputs:
        - metric: credit_score
          required: true
          # 指标计算逻辑在 rule 中声明，非 L3 formula
        - metric: guarantee_exposure
          required: true

      # 输出要素: 规则执行结果
      outputs:
        - name: eligible
          type: boolean
        - name: credit_limit
          type: Money
        - name: credit_level
          type: enum
          enum_type: CreditLevel
```

**关键设计**:
- L3 仅定义「指标存在」和「数据来源」
- L4 定义「指标如何计算」（通过 formula 或 operator）
- 输出要素可在多规则中复用，BY 场景有不同的计算逻辑

---

### 规则集

```yaml
      rules:
        - id: CA001
          name: "基础准入"
          priority: 100
          condition:
            and:
              - "credit_score >= 60"
              - "guarantee_exposure <= registered_capital * 2"
          action:
            type: set_flag
            flag: basic_eligible
            value: true
          else:
            type: reject
            reason: "基础准入未通过"
```

---

## Formula 计算逻辑

**约束**: Formula 必须为单行表达式，复杂逻辑使用结构化算子。

### 简单计算

```yaml
        - id: CA003
          name: "风险定价"
          action:
            type: compute
            output: risk_adjusted_rate
            # 单行 formula，仅支持基础运算和函数
            formula: "base_rate + (100 - credit_score) / 1000"
```

**Formula 语法限制**:

| 特性 | 支持 | 示例 |
|------|------|------|
| 算术运算 | ✅ | `a + b * c / d` |
| 比较运算 | ✅ | `a > b`, `x == y` |
| 逻辑运算 | ✅ | `a AND b`, `NOT c` |
| 字段/指标引用 | ✅ | `credit_score`, `registered_capital.value` |
| 函数调用 | ✅ | `min(a, b)`, `max(c, d)`, `abs(x)` |
| **变量赋值** | ❌ | `base = a + b` → 用 operator 替代 |
| **多行语句** | ❌ | 用 SWITCH/决策表替代 |
| **图查询** | ❌ | 用 GRAPH 算子替代 |
| **外部调用** | ❌ | 用 MODEL_INFERENCE 算子替代 |

---

### 条件分支 (SWITCH)

```yaml
        - id: CA002
          name: "额度计算"
          priority: 90
          depends_on: [CA001]
          condition:
            ref: "basic_eligible == true"
          action:
            type: compute
            output: credit_limit
            # 多分支条件用 SWITCH 算子，非多行 formula
            operator: SWITCH
            input: credit_score
            branches:
              - condition: ">= 90"
                formula: "registered_capital * 0.8"
              - condition: ">= 80"
                formula: "registered_capital * 0.6"
              - condition: ">= 70"
                formula: "registered_capital * 0.4"
            default: "registered_capital * 0.2"
```

---

## 复杂规则算子

### 1. 连续数值分箱 (BINNING)

```yaml
        - id: RISK_BINNING
          name: "风险分箱"
          action:
            type: compute
            output: risk_bucket
            operator: BINNING
            input: credit_score
            bins:
              - [0, 40): HIGH_RISK
              - [40, 60): MEDIUM_RISK
              - [60, 80): LOW_RISK
              - [80, 100]: EXCELLENT
            method: "manual"  # manual | equal_freq | equal_width
```

### 2. 评分卡 (SCORECARD)

```yaml
        - id: CREDIT_SCORECARD
          name: "信用评分卡"
          action:
            type: compute
            output: credit_score
            operator: SCORECARD
            variables:
              - name: "business_years"
                weight: 0.15
                points:
                  - "< 1": 0
                  - "[1, 3)": 20
                  - "[3, 5)": 40
                  - ">= 5": 60
              - name: "asset_liability_ratio"
                weight: 0.25
                points:
                  - "> 0.8": 0
                  - "(0.6, 0.8]": 30
                  - "(0.4, 0.6]": 60
                  - "<= 0.4": 80
              - name: "guarantee_chain_length"
                weight: 0.10
                points:
                  - "== 0": 40
                  - "== 1": 30
                  - "== 2": 15
                  - ">= 3": 0
            baseline: 400
            scale_factor: 1
```

### 3. 决策表 (DECISION_TABLE)

```yaml
        - id: INTEREST_RATE_TABLE
          name: "利率决策表"
          action:
            type: compute
            output: interest_rate
            operator: DECISION_TABLE
            inputs:
              - credit_level
              - company_scale
              - risk_level
            table:
              - conditions: {credit_level: A, company_scale: LARGE, risk_level: LOW}
                action: {rate: 0.045}
              - conditions: {credit_level: A, company_scale: MEDIUM, risk_level: LOW}
                action: {rate: 0.055}
              - conditions: {credit_level: B, company_scale: LARGE, risk_level: LOW}
                action: {rate: 0.060}
              - conditions: {credit_level: "*", company_scale: "*", risk_level: HIGH}
                action: {rate: 0.095, requires_approval: true}
            default: {rate: 0.080}
```

### 4. 决策树 (DECISION_TREE)

```yaml
        - id: COMPLEX_ELIGIBILITY
          name: "复杂准入判定"
          action:
            type: compute
            output: {eligible: boolean, reason: string}
            operator: DECISION_TREE
            tree:
              node: root
              condition: "asset_liability_ratio > 0.7"
              true_branch:
                node: high_debt_check
                condition: "guarantee_chain_length > 3"
                true_branch:
                  result: {eligible: false, reason: "高负债且担保链过长"}
                false_branch:
                  node: revenue_check
                  condition: "annual_revenue > 10000000"
                  true_branch:
                    result: {eligible: true, reason: "高负债但营收充足"}
                  false_branch:
                    result: {eligible: false, reason: "高负债且营收不足"}
              false_branch:
                node: normal_check
                condition: "credit_score >= 60"
                true_branch:
                  result: {eligible: true, reason: "资质正常"}
                false_branch:
                  result: {eligible: false, reason: "信用分不足"}
```

### 5. 图检索与计算 (GRAPH)

```yaml
        - id: GUARANTEE_NETWORK_RISK
          name: "担保网络风险"
          action:
            type: compute
            output: network_risk_score
            operator: GRAPH
            query:
              type: traversal
              start: entity_id  # 当前实体
              relation: Guarantee
              direction: both
              depth: 2
            aggregation:
              - type: sum
                field: guarantee_amount.value
              - type: count
                field: related_entities
              - type: max
                field: guarantee_chain_depth
            post_process:
              formula: "total_amount / entity.registered_capital.value * related_count"
```

### 6. 外部模型调用 (MODEL_INFERENCE)

```yaml
        - id: ML_RISK_PREDICTION
          name: "机器学习风险预测"
          action:
            type: compute
            output: ml_risk_score
            operator: MODEL_INFERENCE
            model:
              id: "risk_v2_model"
              version: "2.1.0"
              source: "local"  # local | remote | huggingface
            inputs:
              - name: financial_features
                mapping:
                  asset_liability_ratio: "alr"
                  current_ratio: "cr"
                  revenue_growth: "rg"
            outputs:
              - name: risk_score
                type: float
              - name: risk_level
                type: enum
                enum_type: RiskLevel
            timeout: 5000
            fallback:
              action: use_default
              default_value: 0.5
```

### 7. 大模型语义推理 (LLM_INFERENCE)

```yaml
        - id: SEMANTIC_RISK_ANALYSIS
          name: "语义风险分析"
          action:
            type: compute
            output: semantic_risk_assessment
            operator: LLM_INFERENCE
            prompt_template: |
              请根据以下企业信息评估潜在风险：

              企业名称: {{company_name}}
              经营范围: {{business_scope}}
              负面新闻: {{negative_news}}

              请输出：
              1. 风险等级（高/中/低）
              2. 主要风险点
              3. 建议措施

            llm_config:
              model: "claude-sonnet-4.6"
              temperature: 0.3
              max_tokens: 500

            output_parser:
              type: structured_json
              schema:
                risk_level: enum[HIGH, MEDIUM, LOW]
                risk_points: list[string]
                recommendations: list[string]

            cache:
              enabled: true
              ttl: 3600  # 基于输入哈希缓存

            guardrails:
              - type: cost_limit
                max_tokens_per_day: 100000
              - type: timeout
                max_wait: 10000
```

---

## 算子类型汇总

| 算子 | 用途 | 复杂度 |
|------|------|--------|
| `FORMULA` | 简单表达式 | ⭐ |
| `SWITCH` | 多分支条件 | ⭐⭐ |
| `BINNING` | 数值分箱 | ⭐⭐ |
| `SCORECARD` | 评分卡模型 | ⭐⭐⭐ |
| `DECISION_TABLE` | 决策表 | ⭐⭐ |
| `DECISION_TREE` | 决策树 | ⭐⭐⭐ |
| `GRAPH` | 图检索计算 | ⭐⭐⭐⭐ |
| `MODEL_INFERENCE` | 外部模型 | ⭐⭐⭐ |
| `LLM_INFERENCE` | 大模型推理 | ⭐⭐⭐⭐ |

---

## 决策定义

多规则组的综合决策。

```yaml
    - name: financing_decision
      description: "融资综合决策"

      components:
        - rule_group: credit_assessment
          weight: 0.6
        - rule_group: collateral_assessment
          weight: 0.3
        - rule_group: industry_policy
          weight: 0.1

      strategy:
        type: weighted_veto
        veto_conditions:
          - "credit_assessment.eligible == false"
          - "industry_policy.blocked == true"

      final_decision:
        - name: approved
          expression: "weighted_score >= 60 AND veto_count == 0"
        - name: final_limit
          formula: "min(credit_assessment.credit_limit, collateral_assessment.max_limit)"
```

---

## 流程编排

```yaml
  workflows:
    - name: loan_application
      steps:
        - id: step1
          name: "资料完整性检查"
          type: validation
          rules: [VAL001, VAL002]
          on_fail: reject

        - id: step2
          name: "ML风险预测"
          type: assessment
          rule: ML_RISK_PREDICTION
          parallel: false

        - id: step3
          name: "语义风险分析"
          type: assessment
          rule: SEMANTIC_RISK_ANALYSIS
          parallel: true
          depends_on: [step1]

        - id: step4
          name: "综合决策"
          type: decision
          decision: financing_decision
          depends_on: [step2, step3]
```

---

## 运行时: 跨引擎协调

```python
class BusinessLogicEngine:
    def __init__(self, metric_engine, storage, model_registry):
        self.metric_engine = metric_engine  # L3 指标引擎
        self.storage = storage
        self.model_registry = model_registry
        self.orchestrator = ExecutionOrchestrator()

    def execute(self, rule_group: str, entity: Entity) -> LogicResult:
        # 1. 检查 applies_to
        if not self.matches_scope(rule_group, entity):
            raise NotApplicable()

        # 2. 预计算 L3 指标 (跨引擎协调点)
        inputs = self._compute_l3_inputs(rule_group.inputs, entity)

        # 3. 执行 L4 规则
        context = ExecutionContext(inputs=inputs)
        for rule in self.topological_sort(rule_group.rules):
            result = self._execute_rule(rule, context)
            context.update(rule.id, result)

        return LogicResult(outputs=context.resolve_outputs(rule_group.outputs))

    def _compute_l3_inputs(self, inputs: list, entity: Entity) -> dict:
        """跨引擎协调: 按需计算 L3 指标"""
        results = {}
        for inp in inputs:
            # 调用 MetricEngine 计算基础指标
            metric_value = self.metric_engine.compute(inp.metric, entity)
            results[inp.metric] = metric_value
        return results

    def _execute_rule(self, rule: Rule, context: ExecutionContext) -> RuleResult:
        # 条件判断
        if not self.evaluate(rule.condition, context):
            return self._execute_else(rule.else_, context)

        # 根据算子类型分发
        if rule.action.type == "compute":
            return self._execute_compute(rule.action, context)
        elif rule.action.type == "MODEL_INFERENCE":
            return self.model_registry.infer(rule.action.model, context)
        elif rule.action.type == "LLM_INFERENCE":
            return self._execute_llm(rule.action, context)
        # ... 其他算子
```

---

## 与 v1 的区别

| v1 | v2 |
|-----|-----|
| formula 分散在各处 | 统一在 L4，结构化表达 |
| 多行 formula 文本 | 单行 formula + 算子 |
| 无复杂规则支持 | 评分卡/决策表/图/MLOps/LLM |
| 规则硬编码 entity_types | 声明式 applies_to + GLOBAL 支持 |
| 无跨引擎协调说明 | 显式 ExecutionOrchestrator |

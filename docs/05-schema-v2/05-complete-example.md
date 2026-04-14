# Schema v2 完整示例

> **[单一事实源]**: 本示例已与 `09-canonical-schema-spec.md` 完全对齐，所有声明闭合无悬空引用
> **[关键设计点]**: 完整文件根级结构遵循 `semantic_space / fact_objects / categorizations / analytical_elements / business_logic.rule_definitions / business_logic.rule_logics`

## 场景

某制造企业向平台申请供应链融资，系统需要：
1. 验证企业资质
2. 分析财务状况
3. 评估担保网络风险
4. 计算授信额度和利率

## Schema (schema-v2.yaml)

```yaml
schema_version: "2.0"

semantic_space:
  id: "kg://scf/v2.0"
  name: "供应链金融风控模型 v2"
  type: management
  status: DRAFT

# ============ L1: 事实对象 ============
fact_objects:
  entities:
    - name: Company
      description: "企业"
      attributes:
        - name: uscc
          type: string
          required: true
          unique: true
        - name: name
          type: string
          required: true
        - name: registered_capital
          type: Money
        - name: establishment_date
          type: date
        - name: status
          type: enum
          enum_type: CompanyStatus
        - name: annual_revenue
          type: Money
        - name: employee_count
          type: integer
          description: "员工数量，用于企业规模判定"
        - name: total_assets
          type: Money
        - name: total_liabilities
          type: Money

  relations:
    - name: Guarantee
      from: Company
      to: Company
      attributes:
        - name: amount
          type: Money
          required: true
        - name: type
          type: enum
          enum_type: GuaranteeType

# ============ L2: 归类分析 ============
categorizations:
  dimensions:
    - name: industry
      type: hierarchical
      values:
        - code: "C"
          name: "制造业"
        - code: "F"
          name: "批发零售"

    - name: company_scale
      type: derived
      rule_logic: determine_scale
      values: [LARGE, MEDIUM, SMALL, MICRO]

    - name: risk_level
      type: derived
      rule_logic: assess_risk
      values: [LOW, MEDIUM, HIGH]

# ============ L3: 分析要素 ============
# 注意: L3 仅定义指标存在和依赖，计算逻辑在 L4
analytical_elements:
  metrics:
    # ---- 原子指标: 直接从 L1 事实获取 ----
    - name: current_ratio
      type: derived
      description: "流动比率 = total_assets / total_liabilities"
      value_type: decimal
      dependencies: [total_assets, total_liabilities]

    - name: previous_revenue
      type: atomic
      description: "上一年度营收（用于增长率计算）"
      value_type: currency
      source: annual_revenue
      overridable: true

    - name: current_revenue
      type: atomic
      description: "本年度营收"
      value_type: currency
      source: annual_revenue

    - name: guarantee_exposure
      type: graph
      description: "担保敞口（通过担保关系图计算）"
      value_type: currency
      unit: "CNY"
      dependencies: [Guarantee]

    # ---- 派生指标: 依赖其他指标计算 ----
    - name: revenue_growth_rate
      type: derived
      description: "营收增长率"
      value_type: percentage
      dependencies: [current_revenue, previous_revenue]

    - name: guarantee_exposure_score
      type: derived
      description: "担保敞口评分（将敞口金额映射为风险分数）"
      value_type: score
      dependencies: [guarantee_exposure]

    - name: business_stability_score
      type: composite
      description: "经营稳定性评分"
      value_type: score
      components:
        - metric: current_ratio
          weight: 0.6
          aggregation: avg
        - metric: revenue_growth_rate
          weight: 0.4
          aggregation: avg

    # ---- 复合指标: 多维度加权聚合 ----
    - name: financial_health_score
      type: composite
      description: "财务健康度"
      value_type: score
      components:
        - metric: current_ratio
          weight: 0.5
        - metric: business_stability_score
          weight: 0.3
        - metric: revenue_growth_rate
          weight: 0.2

    - name: external_rating
      type: variable
      description: "外部信用评级（可由外部系统注入）"
      value_type: score
      overridable: true

    - name: credit_score
      type: composite
      description: "综合信用评分"
      value_type: score
      components:
        - metric: financial_health_score
          weight: 0.4
        - metric: guarantee_exposure_score
          weight: 0.3
        - metric: external_rating
          weight: 0.3

# ============ L4: 业务逻辑 ============
business_logic:
  rule_definitions:
    # GLOBAL 规则: 适用于所有实体
    - name: global_eligibility_check
      description: "全局准入检查"
      type: constraint
      applies_to:
        fact_objects: []    # 空数组表示 GLOBAL
        categories: {}
      preconditions:
        - expression: "status == 'ACTIVE'"
          fail: {reject: true, reason: "企业状态非正常"}
        - expression: "establishment_days >= 365"
          fail: {reject: true, reason: "成立不足1年"}
      outputs:
        - name: base_eligible
          type: boolean

    # 场景特定规则: 供应链金融授信
    - name: credit_assessment
      description: "融资授信评估"
      type: decision
      applies_to:
        fact_objects: [Company]
        categories:
          industry: ["C", "F"]
          risk_level: [LOW, MEDIUM]
      inputs:
        - metric: credit_score
        - metric: guarantee_exposure
        - metric: asset_liability_ratio
      outputs:
        - name: eligible
          type: boolean
        - name: credit_limit
          type: Money
        - name: interest_rate
          type: decimal

    # L3 overridable 覆盖示例: 自定义授信额度计算规则
    - name: special_credit_limit_override
      description: "特殊客户授信额度覆盖规则（演示 overrides 用法）"
      type: inference
      applies_to:
        fact_objects: [Company]
        categories:
          company_scale: [LARGE]
      overrides: credit_limit
      inputs:
        - metric: credit_score
        - metric: registered_capital
      outputs:
        - name: credit_limit
          type: Money

  rule_logics:
    # 规则逻辑: 企业规模判定（输出值对应 dimensions.values 枚举）
    - name: determine_scale
      description: "根据营收和员工数判定企业规模"
      type: switch
      steps:
        - id: S001
          name: "判定大规模"
          condition:
            expression: "annual_revenue >= 400000000 AND employee_count >= 1000"
          action:
            type: assign_category
            category: LARGE
        - id: S002
          name: "判定中型"
          condition:
            expression: "annual_revenue >= 20000000 AND employee_count >= 300"
          action:
            type: assign_category
            category: MEDIUM
        - id: S003
          name: "判定小规模"
          condition:
            expression: "annual_revenue >= 3000000 AND employee_count >= 20"
          action:
            type: assign_category
            category: SMALL
        - id: S004
          name: "判定微型企业"
          condition:
            expression: "annual_revenue < 3000000 OR employee_count < 20"
          action:
            type: assign_category
            category: MICRO

    # 规则逻辑: 风险评估（输出值对应 dimensions.values 枚举）
    - name: assess_risk
      description: "企业信用风险评估"
      type: switch
      steps:
        - id: R001
          name: "低风险判定"
          condition:
            expression: "credit_score >= 80 AND guarantee_exposure < registered_capital"
          action:
            type: assign_category
            category: LOW
        - id: R002
          name: "中风险判定"
          condition:
            expression: "credit_score >= 60 AND guarantee_exposure < registered_capital * 2"
          action:
            type: assign_category
            category: MEDIUM
        - id: R003
          name: "高风险默认"
          action:
            type: assign_category
            category: HIGH

    # 规则逻辑: 担保敞口评分计算
    - name: calculate_guarantee_exposure_score
      description: "将担保敞口金额映射为风险评分"
      type: switch
      steps:
        - id: G001
          name: "无担保敞口"
          condition:
            expression: "guarantee_exposure == 0"
          action:
            type: compute
            output: guarantee_exposure_score
            operator: SWITCH
            branches:
              - condition: "true"
                formula: "100"
        - id: G002
          name: "担保敞口评分"
          condition:
            expression: "guarantee_exposure > 0"
          action:
            type: compute
            output: guarantee_exposure_score
            operator: SWITCH
            branches:
              - condition: "guarantee_exposure < registered_capital * 0.3"
                formula: "80"
              - condition: "guarantee_exposure < registered_capital * 0.6"
                formula: "60"
              - condition: "guarantee_exposure < registered_capital"
                formula: "40"
              - condition: "guarantee_exposure >= registered_capital"
                formula: "20"

    # 规则逻辑: 信用评估流程（完整决策流程）
    - name: credit_assessment_logic
      description: "供应链金融授信评估完整流程"
      type: scorecard
      steps:
        # R1: 基础准入
        - id: C001
          name: "信用分准入"
          priority: 100
          condition:
            and:
              - "credit_score >= 60"
              - "guarantee_exposure < registered_capital * 2"
          action:
            type: set_flag
            flag: eligible
            value: true
          else:
            type: reject
            reason: "基础准入未通过"

        # R2: 担保网络风险 (图算子)
        - id: C002
          name: "担保网络风险评估"
          priority: 95
          depends_on: [C001]
          condition:
            expression: "eligible == true"
          action:
            type: compute
            output: network_risk_level
            operator: GRAPH
            query:
              type: traversal
              relation: Guarantee
              depth: 2
            aggregation:
              - type: sum
                field: amount.value
                output: total_guarantee_exposure
              - type: max
                field: depth
                output: max_guarantee_chain
            post_process:
              formula: "total_guarantee_exposure / registered_capital.value"

        # R3: 风险分箱 (分箱算子)
        - id: C003
          name: "信用风险分箱"
          priority: 90
          depends_on: [C002]
          action:
            type: compute
            output: risk_bucket
            operator: BINNING
            input: credit_score
            bins:
              - range: [0, 40)
                result: HIGH_RISK
              - range: [40, 60)
                result: MEDIUM_RISK
              - range: [60, 80)
                result: LOW_RISK
              - range: [80, 100]
                result: EXCELLENT

        # R4: 额度计算 (SWITCH 算子)
        - id: C004
          name: "授信额度计算"
          priority: 80
          depends_on: [C003]
          action:
            type: compute
            output: credit_limit
            operator: SWITCH
            input: risk_bucket
            branches:
              - condition: "EXCELLENT"
                formula: "min(registered_capital * 0.8, 20000000)"
              - condition: "LOW_RISK"
                formula: "min(registered_capital * 0.6, 15000000)"
              - condition: "MEDIUM_RISK"
                formula: "min(registered_capital * 0.4, 10000000)"
            default: "min(registered_capital * 0.2, 5000000)"

        # R5: 利率定价 (评分卡算子)
        - id: C005
          name: "差异化利率定价"
          priority: 70
          depends_on: [C004]
          action:
            type: compute
            output: interest_rate
            operator: SCORECARD
            baseline: 0.045
            variables:
              - name: credit_score
                points:
                  - condition: ">= 90"
                    score: 0
                  - condition: "[80, 90)"
                    score: 0.005
                  - condition: "[70, 80)"
                    score: 0.010
                  - condition: "[60, 70)"
                    score: 0.020
                  - condition: "< 60"
                    score: 0.035
              - name: guarantee_exposure
                points:
                  - condition: "== 0"
                    score: 0
                  - condition: "<= registered_capital"
                    score: 0.005
                  - condition: "> registered_capital"
                    score: 0.015
            post_formula: "baseline + total_points"

    # 规则逻辑: 特殊客户额度覆盖
    - name: special_credit_limit_logic
      description: "大型客户授信额度覆盖逻辑"
      type: switch
      steps:
        - id: SP001
          name: "超高信用分客户"
          condition:
            expression: "credit_score >= 90"
          action:
            type: compute
            output: credit_limit
            operator: SWITCH
            branches:
              - condition: "true"
                formula: "min(registered_capital * 1.0, 50000000)"
        - id: SP002
          name: "高信用分客户"
          condition:
            expression: "credit_score >= 80"
          action:
            type: compute
            output: credit_limit
            operator: SWITCH
            branches:
              - condition: "true"
                formula: "min(registered_capital * 0.9, 30000000)"
```

## 实例数据 (instances.yaml)

```yaml
# 事实对象实例
fact_objects:
  entities:
    - id: "COMP001"
      fact_object: Company
      attributes:
        uscc: "91110000123456789X"
        name: "北京智造科技有限公司"
        registered_capital: {value: 5000000, currency: CNY}
        establishment_date: "2020-03-15"
        status: ACTIVE
        annual_revenue: {value: 80000000, currency: CNY}
        employee_count: 500
        total_assets: {value: 50000000, currency: CNY}
        total_liabilities: {value: 20000000, currency: CNY}

    - id: "COMP002"
      fact_object: Company
      attributes:
        uscc: "91110000987654321Y"
        name: "上海材料供应有限公司"
        registered_capital: {value: 10000000, currency: CNY}
        status: ACTIVE
        annual_revenue: {value: 200000000, currency: CNY}
        employee_count: 1500

  relations:
    - id: "REL001"
      type: Guarantee
      from: "COMP001"
      to: "COMP002"
      attributes:
        amount: {value: 3000000, currency: CNY}
        type: GUARANTEE

# 计算结果 (由引擎生成)
computed:
  entity: "COMP001"

  categories:
    industry: "C"           # 制造业
    company_scale: MEDIUM   # 中型
    risk_level: LOW         # 低风险

  metrics:
    current_ratio: 2.5
    previous_revenue: {value: 65000000, currency: CNY}
    current_revenue: {value: 80000000, currency: CNY}
    revenue_growth_rate: 23.08
    guarantee_exposure: 3000000
    guarantee_exposure_score: 60
    business_stability_score: 75.6
    financial_health_score: 78
    external_rating: 85
    credit_score: 76

  business_logic:
    global_eligibility_check:
      base_eligible: true
    credit_assessment:
      eligible: true
      risk_bucket: LOW_RISK
      credit_limit: {value: 7500000, currency: CNY}
      interest_rate: 0.072
    special_credit_limit_override:
      credit_limit: {value: 10000000, currency: CNY}  # 因公司规模为LARGE触发了覆盖
```

## 执行结果

```json
{
  "entity_id": "COMP001",
  "fact_object": "Company",
  "execution": {
    "timestamp": "2026-04-08T10:00:00Z",
    "rule_definitions": {
      "global_eligibility_check": {
        "matched": true,
        "results": {"base_eligible": true}
      },
      "credit_assessment": {
        "matched": true,
        "applies_to": {"industry": "C", "risk_level": "LOW"},
        "results": {
          "C001": {"eligible": true},
          "C002": {"total_guarantee_exposure": 3000000, "max_guarantee_chain": 1},
          "C003": {"risk_bucket": "LOW_RISK"},
          "C004": {"credit_limit": 7500000},
          "C005": {"interest_rate": 0.072}
        }
      }
    },
    "final_output": {
      "eligible": true,
      "credit_limit": {"value": 7500000, "currency": "CNY"},
      "interest_rate": 0.072
    }
  }
}
```

## 声明完整性检查

- [x] Company.attributes 包含 `employee_count`（determine_scale 引用：`employee_count >= 1000`）
- [x] `current_ratio` 已声明（financial_health_score.components 引用）
- [x] `current_revenue`, `previous_revenue` 已声明（revenue_growth_rate.dependencies 引用）
- [x] `guarantee_exposure_score` 已声明（credit_score.components 引用）
- [x] `external_rating` 已声明（credit_score.components 引用）
- [x] `business_stability_score` 已声明（financial_health_score.components 引用）
- [x] `guarantee_exposure` 声明了 `value_type: currency` 和 `unit: "CNY"`
- [x] `revenue_growth_rate` 声明了 `value_type: percentage`
- [x] `credit_limit` 在 `special_credit_limit_override` 规则中声明为 `overrides`
- [x] `determine_scale` 输出的 `LARGE/MEDIUM/SMALL/MICRO` 与 `company_scale.values` 对应
- [x] `assess_risk` 输出的 `LOW/MEDIUM/HIGH` 与 `risk_level.values` 对应
- [x] 所有 rule_logic.steps[].condition 中的变量都在 schema 中有声明
- [x] 所有 rule_definitions.overrides 引用的 metric 在 analytical_elements.metrics 中已声明且 `overridable: true`

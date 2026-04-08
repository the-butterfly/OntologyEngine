# Schema v2 完整示例

> 供应链金融场景

## 场景

某制造企业向平台申请供应链融资，系统需要：
1. 验证企业资质
2. 分析财务状况
3. 评估担保网络风险
4. 计算授信额度和利率

## Schema (schema-v2.yaml)

```yaml
metadata:
  id: "kg://scf/v2.0"
  version: "2.0.0"
  description: "供应链金融风控模型 v2"

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
categorization:
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
      ruleset: determine_scale
      values: [LARGE, MEDIUM, SMALL, MICRO]

    - name: risk_level
      type: derived
      ruleset: assess_risk
      values: [LOW, MEDIUM, HIGH]

  rules:
    - name: determine_scale
      rules:
        - condition:
            "annual_revenue >= 400000000 AND employee_count >= 1000"
          result: LARGE
        - condition:
            "annual_revenue >= 20000000 AND employee_count >= 300"
          result: MEDIUM
        - condition:
            "annual_revenue >= 3000000 AND employee_count >= 20"
          result: SMALL
        - default: MICRO

# ============ L3: 分析要素 ============
# 注意: L3 仅定义指标存在和依赖，计算逻辑在 L4
analytical_elements:
  metrics:
    # 基础指标: 直接从事实获取
    - name: asset_liability_ratio
      type: derived
      description: "资产负债率"
      dependencies: [total_assets, total_liabilities]

    - name: revenue_growth_rate
      type: derived
      description: "营收增长率"
      dependencies: [current_revenue, previous_revenue]

    # 图指标: 依赖图计算
    - name: guarantee_exposure
      type: graph
      description: "担保敞口"
      dependencies: [Guarantee]

    # 复合指标: 多维度聚合
    - name: financial_health_score
      type: composite
      description: "财务健康度"
      components:
        - metric: asset_liability_ratio
        - metric: current_ratio
        - metric: revenue_growth_rate

    - name: credit_score
      type: composite
      description: "综合信用评分"
      components:
        - metric: financial_health_score
        - metric: guarantee_exposure_score
        - metric: external_rating

# ============ L4: 业务逻辑 ============
business_logic:
  rule_groups:
    # GLOBAL 规则: 适用于所有实体
    - name: global_eligibility_check
      description: "全局准入检查"
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

      applies_to:
        fact_objects: [Company]
        categories:
          industry: ["C", "F"]
          risk_level: [LOW, MEDIUM]

      inputs:
        - metric: credit_score
        - metric: guarantee_exposure
        - metric: asset_liability_ratio

      rules:
        # R1: 基础准入
        - id: R001
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
        - id: R002
          name: "担保网络风险评估"
          priority: 95
          depends_on: [R001]
          condition: "eligible == true"
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
        - id: R003
          name: "信用风险分箱"
          priority: 90
          depends_on: [R002]
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

        # R4: 额度计算 (SWITCH 算子)
        - id: R004
          name: "授信额度计算"
          priority: 80
          depends_on: [R003]
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
        - id: R005
          name: "差异化利率定价"
          priority: 70
          depends_on: [R004]
          action:
            type: compute
            output: interest_rate
            operator: SCORECARD
            baseline: 0.045
            variables:
              - name: credit_score
                points:
                  - ">= 90": 0
                  - "[80, 90)": 0.005
                  - "[70, 80)": 0.010
                  - "[60, 70)": 0.020
                  - "< 60": 0.035
              - name: guarantee_exposure
                points:
                  - "== 0": 0
                  - "<= registered_capital": 0.005
                  - "> registered_capital": 0.015
            post_formula: "baseline + total_points"

      outputs:
        - name: eligible
          type: boolean
          source: R001.eligible
        - name: credit_limit
          type: Money
          source: R004.credit_limit
        - name: interest_rate
          type: decimal
          source: R005.interest_rate
```

## 实例数据 (instances.yaml)

```yaml
# 事实对象实例
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
      total_assets: {value: 50000000, currency: CNY}
      total_liabilities: {value: 20000000, currency: CNY}

  - id: "COMP002"
    fact_object: Company
    attributes:
      uscc: "91110000987654321Y"
      name: "上海材料供应有限公司"
      registered_capital: {value: 10000000, currency: CNY}
      status: ACTIVE

relations:
  - type: Guarantee
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
    asset_liability_ratio: 0.4
    financial_health_score: 75
    guarantee_exposure: 3000000
    credit_score: 78

  business_logic:
    global_eligibility_check:
      base_eligible: true
    credit_assessment:
      eligible: true
      risk_bucket: LOW_RISK
      credit_limit: {value: 7500000, currency: CNY}
      interest_rate: 0.072
```

## 执行结果

```json
{
  "entity_id": "COMP001",
  "fact_object": "Company",
  "execution": {
    "timestamp": "2026-04-08T10:00:00Z",
    "rule_groups": {
      "global_eligibility_check": {
        "matched": true,
        "results": {"base_eligible": true}
      },
      "credit_assessment": {
        "matched": true,
        "applies_to": {"industry": "C", "risk_level": "LOW"},
        "results": {
          "R001": {"eligible": true},
          "R002": {"total_guarantee_exposure": 3000000, "max_guarantee_chain": 1},
          "R003": {"risk_bucket": "LOW_RISK"},
          "R004": {"credit_limit": 7500000},
          "R005": {"interest_rate": 0.072}
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

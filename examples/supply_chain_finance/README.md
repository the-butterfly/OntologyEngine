# 供应链金融授信评估 MVP 案例

## 概述

本案例演示了基于 **KGML Schema v3.0** 的完整知识图谱分析链路：

```
分析对象(Supplier) -> 分析维度/场景(BY) -> 分析逻辑(指标计算+规则推理)
```

## 核心设计

### 1. Schema 层 (`schema.yaml`)

#### 分析对象：供应商(Supplier)
```yaml
concepts:
  - name: "Supplier"
    category: "entity"
    attributes:
      # 基础属性
      - supplier_id, company_name, registered_capital, ...
      
      # 维度特定属性（核心设计）
      dimension_attributes:
        credit_assessment:    # 融资授信评估维度
          - credit_limit_recommendation  (派生)
          - financing_eligibility        (派生)
          - interest_rate_suggestion     (派生)
        
        transaction_monitoring:  # 交易监控维度
          - transaction_volatility_30d   (派生)
          - buyer_concentration_ratio    (派生)
```

#### 分析维度定义
```yaml
rule_dimensions:
  dimensions:
    - name: "credit_assessment"
      description: "融资授信评估维度"
      applicable_entities: ["Supplier"]
      triggers:
        - event: "financing_application_submitted"
        - event: "credit_review_scheduled"
```

#### 指标定义
```yaml
metrics:
  # 原子指标（直接输入）
  - name: "total_invoice_amount_90d"
    metric_type: "atomic"
  
  # 派生指标（规则计算）
  - name: "overdue_invoice_ratio"
    metric_type: "derived"
    formula: "overdue_invoice_amount.value / total_invoice_amount_90d.value * 100"
  
  # 复合指标（多维度聚合）
  - name: "credit_score"
    metric_type: "composite"
    components:
      - metric: "business_stability_score"  weight: 0.30
      - metric: "tax_compliance_score"      weight: 0.25
      - metric: "reputation_score"          weight: 0.25
      - metric: "guarantee_risk_score"      weight: 0.20
  
  # 图算法指标
  - name: "guarantee_chain_depth"
    metric_type: "graph"
    algorithm: "longest_path"
```

#### 规则定义
```yaml
rules:
  # R001: 基础准入检查
  - id: "R001_basic_eligibility"
    type: "constraint"
    when:
      allOf:
        - expression: "status == 'ACTIVE'"
        - expression: "registered_capital.value >= 1000000"
        - expression: "days_between(today(), establishment_date) >= 365"
  
  # R002: 信用评分计算
  - id: "R002_credit_score_calculation"
    type: "inference"
    when:
      expression: "eligible == true"
  
  # R003: 担保圈检测（图查询规则）
  - id: "R003_guarantee_circle_detection"
    type: "alert"
    when:
      graph_query: |
        MATCH cycle = (s:Supplier)-[:guarantees_for|guaranteed_by*3..10]-(s)
        RETURN count(cycle) > 0 AS has_cycle
  
  # ... 更多规则
```

### 2. 实例层 (`instances.yaml`)

包含三个典型场景：

#### 案例1: 优质供应商（深圳智造科技）
- 注册资本5000万，成立8年
- 与华为、比亚迪等核心企业合作
- 近90天交易1245万，仅1张小额逾期发票
- **预期结果**: 正常授信，额度约5000万

#### 案例2: 高风险供应商（某贸易公司）
- 注册资本100万，成立不到1年
- 无核心企业合作
- 逾期发票占比80%
- 5条负面新闻
- **预期结果**: 拒绝授信

#### 案例3: 担保圈供应商（供应商A/B/C）
- 本身资质良好
- 但处于A→B→C→A的担保圈中
- **预期结果**: 担保圈预警，有条件授信

## 运行演示

```bash
cd examples/supply_chain_finance
python mvp_demo.py
```

## 分析链路详解

### 步骤1: 确定分析对象
```python
supplier = Supplier(
    supplier_id="SUP_2024_001",
    company_name="深圳智造科技有限公司",
    ...
)
```

### 步骤2: 确定分析维度
```python
ctx = AnalysisContext(
    supplier=supplier,
    dimension="credit_assessment",  # 融资授信评估维度
    as_of_date=date(2026, 4, 7)
)
```

### 步骤3: 执行分析逻辑

#### 阶段3.1: 原子指标输入
- `total_invoice_amount_90d`: 1245万
- `invoice_count_90d`: 5
- `overdue_invoice_amount`: 15万
- ...

#### 阶段3.2: 派生指标计算
```
overdue_invoice_ratio = 15万 / 1245万 * 100 = 1.20%
avg_invoice_amount = 1245万 / 5 = 249万
contract_utilization_rate = 1245万 / 2300万 * 100 = 54.13%
business_stability_score = 50 + 10 + 5 + 15 = 80
reputation_score = 100 - 0 - 2.4 = 97.6
```

#### 阶段3.3: 图算法指标计算
```
guarantee_chain_depth = 1
guarantee_risk_score = 70
```

#### 阶段3.4: 复合指标计算
```
credit_score = 80*0.30 + 85*0.25 + 97.6*0.25 + 70*0.20 = 83.9
credit_grade = "AA"
```

#### 阶段3.5: 规则推理
```
R001 基础准入检查: 通过
R002 信用评分计算: 信用分83.9，等级AA
R003 担保圈检测: 未检测到担保圈
R004 授信额度计算: 5000万 * 0.5 * 1.8 = 4500万
R005 风险预警: 无预警
R006 利率定价: 5% + (100-83.9)/100*5% = 5.81%
R007 综合决策: APPROVE
```

## 输出结果

```
┌─────────────────────────────────────────────────────────────────────┐
│                      分析结果汇总                                    │
├─────────────────────────────────────────────────────────────────────┤
│ 企业信息:                                                            │
│   供应商ID: SUP_2024_001                                             │
│   企业名称: 深圳智造科技有限公司                                       │
├─────────────────────────────────────────────────────────────────────┤
│ 派生指标:                                                            │
│   逾期发票占比: 1.20%                                                │
│   平均发票金额: CNY 2,490,000.00                                     │
│   合同执行率: 54.13%                                                 │
│   业务稳定性评分: 80/100                                             │
│   声誉风险评分: 97/100                                               │
├─────────────────────────────────────────────────────────────────────┤
│ 复合指标:                                                            │
│   综合信用评分: 83.9/100                                             │
│   信用等级: AA                                                       │
│   担保链深度: 1                                                      │
│   担保风险评分: 70/100                                               │
├─────────────────────────────────────────────────────────────────────┤
│ 授信决策:                                                            │
│   准入资格: 通过                                                     │
│   最终决策: APPROVE                                                  │
│   推荐授信额度: CNY 45,000,000.00                                   │
│   建议利率: 5.81%                                                    │
│   需要追加担保: 否                                                   │
│   决策理由: 信用良好，担保风险可控                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 案例对比

| 案例 | 企业名称 | 信用分 | 等级 | 决策 | 授信额度 | 关键风险点 |
|------|---------|--------|------|------|---------|-----------|
| 案例1 | 深圳智造科技 | 83.9 | AA | APPROVE | 4500万 | 无 |
| 案例2 | 某贸易公司 | 22.3 | D | REJECT | 0 | 成立时间短、逾期多、负面新闻 |
| 案例3 | 供应商A | 76.5 | A | APPROVE_WITH_CONDITIONS | 2700万 | 担保圈风险 |

## 关键技术点

### 1. 维度特定属性
同一实体在不同业务维度下有不同的派生属性：
- `credit_assessment` 维度: 授信相关属性
- `transaction_monitoring` 维度: 交易监控相关属性

### 2. 多策略计算
指标支持多种计算策略（优先级回退）：
- SQL查询（首选）
- 图查询（备选）
- LLM推理（最后备选）

### 3. 图算法集成
- 担保链深度检测
- 担保圈检测（循环路径检测）
- 网络中心性计算

### 4. 规则链执行
```
R001(准入) -> R002(评分) -> R003(担保圈) -> R004(额度) -> R005(预警) -> R006(定价) -> R007(决策)
```

## 扩展建议

1. **更多维度**
   - `aml_monitoring`: 反洗钱监控
   - `fraud_detection`: 欺诈检测
   - `supply_chain_optimization`: 供应链优化

2. **更多算子**
   - 机器学习模型算子
   - 时序分析算子
   - 知识图谱推理算子

3. **实时计算**
   - Kafka流处理
   - 增量指标更新
   - 实时风险预警

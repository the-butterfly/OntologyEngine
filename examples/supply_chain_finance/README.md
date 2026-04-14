# 供应链金融授信评估 Demo

基于 **OntologyEngine** 的完整知识图谱分析演示，展示 KGML Schema 驱动的多维度分析能力。

## 概述

本 Demo 演示了基于 **KGML Schema v3.0** 的完整分析链路：

```
KGML Schema (schema.yaml) → 实例数据 (instances.yaml) → OntologyEngine → 分析结果
```

### 核心能力

- **Schema 驱动**: 所有分析逻辑由 `schema.yaml` 定义，非硬编码
- **多维度分析**: 支持 `credit_assessment`、`risk_early_warning` 等维度
- **10+ 测试案例**: 覆盖优质/高风险/担保圈等多种场景
- **完整指标计算**: 原子指标 → 派生指标 → 复合指标 → 图算法指标
- **规则推理链**: 7条规则按优先级执行，生成最终决策

## 快速开始

### 运行 Demo

```bash
# 方法1: 使用 OntologyEngine（推荐）
python -m examples.supply_chain_finance.demo

# 方法2: 直接运行
cd examples/supply_chain_finance
python demo.py
```

### 预期输出

```
======================================================================
  ONTOLOGYENGINE DEMO - Supply Chain Finance Credit Assessment
======================================================================

📦 Initializing OntologyEngine...
   ✅ Engine initialized

======================================================================
  CREDIT ASSESSMENT ANALYSIS
======================================================================

🏢 SUP_2024_001
   深圳智造科技有限公司

🟡 Decision: APPROVE_WITH_CONDITIONS
   Reason: Credit score acceptable but requires guarantee

... (10个案例分析) ...

======================================================================
  ANALYSIS SUMMARY
======================================================================

ID                 Decision                  Score    Grade  Alerts
---------------------------------------------------------------------------
SUP_2024_001       APPROVE_WITH_CONDITIONS   76       BBB    0
SUP_2024_003       APPROVE_RESTRICTED        46       CCC    0
SUP_2024_A         REJECT                    N/A      N/A    1
SUP_2024_NEW       REJECT                    N/A      N/A    0
SUP_2024_NEG       REJECT                    N/A      N/A    0
SUP_2024_EXC       APPROVE                   98       AAA    0
SUP_2024_MULTI     APPROVE                   89       AA     0
SUP_2024_TRADE     APPROVE_WITH_CONDITIONS   69       BB     0
SUP_2024_MFG       APPROVE                   82       A      0
SUP_2024_PARTIAL   APPROVE_WITH_CONDITIONS   72       BBB    0
```

## 测试案例

### 案例列表

| ID | 案例名称 | 描述 | 预期决策 | 关键特征 |
|----|---------|------|---------|---------|
| SUP_2024_001 | 优质供应商 | 深圳智造科技，与华为/比亚迪合作 | APPROVE_WITH_CONDITIONS | 成立8年，交易稳定 |
| SUP_2024_003 | 高风险供应商 | 某贸易公司，多逾期发票 | APPROVE_RESTRICTED | 成立<1年，逾期率高 |
| SUP_2024_A | 担保圈供应商 | 供应商A，处于A→B→C→A担保圈 | REJECT | 担保圈风险 |
| SUP_2024_NEW | 新供应商 | 新兴科技，成立<1年 | REJECT | 基础准入不通过 |
| SUP_2024_NEG | 负面舆情供应商 | 多条负面新闻 | REJECT | 舆情风险 |
| SUP_2024_EXC | 优秀供应商 | 卓越供应商，1亿注册资本 | APPROVE | 完美记录，AAA级 |
| SUP_2024_MULTI | 多核心企业供应商 | 服务4家核心企业 | APPROVE | 高度稳定 |
| SUP_2024_TRADE | 贸易公司 | 小贸易商 | APPROVE_WITH_CONDITIONS | 规模小但合规 |
| SUP_2024_MFG | 制造企业 | 大型制造 | APPROVE | 制造业主力 |
| SUP_2024_PARTIAL | 部分担保供应商 | 有担保支持 | APPROVE_WITH_CONDITIONS | 有担保背书 |

### 决策类型说明

| 决策 | 含义 | 条件 |
|------|------|------|
| APPROVE | 正常授信 | score≥80 且担保链深度<2 |
| APPROVE_WITH_CONDITIONS | 有条件授信 | score≥60 且担保链深度<3 |
| APPROVE_RESTRICTED | 限制授信 | score≥40 |
| REJECT | 拒绝授信 | score<40 或有严重风险 |

## 文件结构

```
examples/supply_chain_finance/
├── schema.yaml          # KGML Schema 定义
├── instances.yaml       # 测试实例数据
├── demo.py             # OntologyEngine Demo (10案例)
├── mvp_demo.py         # 旧版硬编码Demo (3案例，保留参考)
├── SCHEMA_DESIGN.md    # Schema 设计文档
└── README.md           # 本文件
```

## Schema 详解

### 1. 概念定义 (Fact Objects)

```yaml
fact_objects:
  entities:
    - id: "Supplier"
      name: "供应商"
      properties:
        - name: "entity_id"         # 供应商ID
        - name: "company_name"      # 企业名称
        - name: "registered_capital" # 注册资本
        - name: "establishment_date" # 成立日期
      relations:
        - name: "supplies_to"        # 为核心企业供货
        - name: "has_invoice"        # 持有的发票
        - name: "has_contract"       # 持有的合同
        - name: "guarantees"        # 担保其他供应商
```

### 2. 指标定义 (Metrics)

#### 原子指标
```yaml
- total_invoice_amount_90d    # 近90天发票总额
- invoice_count_90d           # 发票数量
- tax_compliance_score        # 税务合规分
- negative_news_count_90d     # 负面新闻数
```

#### 派生指标
```yaml
- overdue_invoice_ratio: |
    overdue_invoice_amount / total_invoice_amount_90d * 100
  
- business_stability_score: |
    base=50, 根据合同执行率/核心企业数/逾期率调整
```

#### 复合指标
```yaml
- credit_score:
    business_stability_score * 0.30 +
    tax_compliance_score * 0.25 +
    network_centrality_score * 0.15 +
    reputation_score * 0.15 +
    guarantee_risk_adjustment * 0.15
```

### 3. 规则定义 (Rules)

| 规则 | 类型 | 说明 |
|------|------|------|
| R001 | 准入 | 基础资质检查（状态/资本/成立时间/交易额） |
| R002 | 计算 | 信用评分计算 |
| R003 | 预警 | 担保圈风险检测 |
| R004 | 计算 | 授信额度计算 |
| R005 | 预警 | 风险预警触发 |
| R006 | 计算 | 利率定价 |
| R007 | 决策 | 综合授信决策 |

## 核心指标计算逻辑

### 业务稳定性评分

```python
score = 50  # 基础分

# 合同执行率加分
if contract_utilization_rate >= 80: score += 20
elif contract_utilization_rate >= 50: score += 10

# 核心企业数加分
if core_enterprise_count >= 3: score += 15
elif core_enterprise_count >= 1: score += 5

# 逾期率加分
if overdue_invoice_ratio < 5: score += 15
elif overdue_invoice_ratio < 10: score += 5
```

### 声誉风险评分

```python
base_score = 100
news_deduction = negative_news_count_90d * 10
overdue_deduction = overdue_invoice_ratio * 2
reputation_score = max(0, base_score - news_deduction - overdue_deduction)
```

### 担保风险评分

```python
if guarantee_chain_depth >= 5: score = 20
elif guarantee_chain_depth >= 3: score = 40
elif guarantee_chain_depth >= 1: score = 70
else: score = 100
```

## 多维度分析

Demo 支持对同一实体进行多维度分析：

```python
# 授信评估维度
result1 = await engine.analyze("SUP_2024_003", "credit_assessment")

# 风险预警维度
result2 = await engine.analyze("SUP_2024_003", "risk_early_warning")
```

不同维度会触发不同的规则集，生成不同的分析结果和预警信息。

## 技术架构

```
demo.py
    ↓
OntologyEngine
    ├── SchemaLoader (加载 schema.yaml)
    ├── InstanceLoader (加载 instances.yaml)
    ├── DuckDBStorage (存储实体和关系)
    └── RuleExecutor (执行规则)
        ├── ExpressionEvaluator (表达式求值)
        └── OperatorRegistry (算子注册表)
```

## 扩展建议

### 1. 添加新维度

```yaml
# schema.yaml
rule_dimensions:
  dimensions:
    - name: "transaction_monitoring"
      description: "交易监控维度"
      triggers:
        - event: "large_transaction_detected"
```

### 2. 添加新案例

```yaml
# instances.yaml
- concept: "Supplier"
  data:
    - supplier_id: "SUP_2024_NEW"
      company_name: "新供应商"
      ...
```

### 3. 自定义规则

```yaml
# schema.yaml
rules:
  - id: "R008_custom_rule"
    when:
      expression: "custom_metric > threshold"
    then:
      action: "trigger_alert"
```

## 常见问题

### Q: Demo 和 mvp_demo.py 的区别？

| | demo.py | mvp_demo.py |
|--|---------|-------------|
| 架构 | OntologyEngine | 纯 Python 硬编码 |
| 配置驱动 | ✅ Schema 驱动 | ❌ 代码内硬编码 |
| 案例数 | 10个 | 3个 |
| 灵活性 | 修改 YAML 即可 | 需修改代码 |
| 用途 | 展示引擎能力 | MVP 原型验证 |

### Q: 如何修改评分权重？

编辑 `schema.yaml` 中的 `metrics.credit_score.components` 部分，修改各组件的 `weight` 值即可，无需修改代码。

### Q: 如何添加新的风险规则？

在 `schema.yaml` 的 `rules` 部分添加新规则定义，指定 `when` 条件和 `then` 动作，重新运行 Demo 即可生效。

## 相关文档

- [Schema 设计](SCHEMA_DESIGN.md) - KGML Schema 详细设计
- [OntologyEngine 文档](../../docs/) - 引擎完整文档
- [API 文档](../../docs/development/api-design.md) - API 设计规范

## License

Apache-2.0

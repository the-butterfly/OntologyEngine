# OntologyEngine 示例案例

> 本目录包含多个完整的 Schema v2 案例，用于验收 OntologyEngine 核心能力。  
> 每个案例遵循 [canonical grammar spec](../docs/05-schema-v2/09-canonical-schema-spec.md)，结构统一，互补设计。

---

## 案例目录

| 案例 | 场景 | 核心验收能力 |
|------|------|------------|
| [`supply_chain_finance/`](./supply_chain_finance/) | 供应链金融授信评估 | L3 图指标（担保链+担保圈）、规则声明/逻辑分离、多维指标 DAG |
| [`consumer_credit/`](./consumer_credit/) | 个人消费信贷风险评估 | Indicator 类型、产品分流（三类贷款）、一票否决、关系网络风险传导 |

---

## 设计原则

每个案例包含四个文件：

```
{case}/
  schema.yaml         # Schema v2 定义（L1~L4 完整四层）
  instances.yaml      # 验收实例数据（精选 3-4 个典型场景）
  testcases.yaml      # 验收用例规格（预期指标值 + 预期规则步骤 + 预期输出）
  SCHEMA_DESIGN.md    # 设计说明（意图、关键设计点、与文档对应关系）
```

---

## 案例一：供应链金融授信评估

**路径**：`supply_chain_finance/`

### 场景描述

以供应商为核心分析对象，融合发票交易、担保图谱数据，
通过四层知识模型驱动融资授信决策推理。

### 三个验收场景

| 场景 | 供应商 | 核心特征 | 预期决策 |
|------|--------|---------|---------|
| CASE-A | 深圳智造科技（制造业） | 5000万注册资本，成立8年，逾期率1.2%，无担保风险 | **APPROVE**，额度约4500万元 |
| CASE-B | 某贸易有限公司 | 100万注册资本，成立7个月，逾期率80% | **REJECT**（准入失败） |
| CASE-C | 联华/联盛/联合（三角担保圈） | 三方互保形成 A→C→B→A 循环，基础面尚可 | **APPROVE_WITH_CONDITIONS** + CRITICAL 预警 |

### 关键设计能力演示

```
L3 图指标：
  guarantee_chain_depth  — BFS 最长路径（GuaranteeRelation 边）
  has_guarantee_cycle    — 环路检测（boolean 输出）

规则声明/逻辑分离：
  RD002_credit_score_compute
    ├── RL002_score_standard           (所有行业)
    └── RL002_score_manufacturing_boost (制造业 +5分加成)

指标 DAG 拓扑：
  原子(5个) → 派生(3个) → 复合(credit_score)
                  ↑
              图算法(2个)
```

---

## 案例二：个人消费信贷风险评估

**路径**：`consumer_credit/`

### 场景描述

面向个人借款人，融合收入负债、还款历史、社会关系网络，
通过五级评分卡驱动三类贷款产品（快贷/分期/大额）的差异化审批。

### 三个验收场景

| 场景 | 借款人 | 核心特征 | 验收侧重 |
|------|--------|---------|---------|
| CASE-P | 张伟（优质） | 全职工程师，月入3万，720征信，零逾期 | 完整正常路径 + 产品分流 |
| CASE-M | 李敏（中等风险） | 自雇月入8000（低于12万门槛），1次逾期 | 准入门槛精确判断、产品边界 |
| CASE-R | 王芳（关联风险） | 自身良好但共借人陈刚当前逾期 | 图算法网络风险传导 |

### 关键设计能力演示（与供应链案例互补）

```
L3 Indicator 类型（布尔指示器）：
  is_blacklisted       — atomic，直接取 fact_attribute
  has_stable_income    — derived，就业类型 + 收入条件
  has_current_overdue  — derived，current_overdue_amount > 0

产品分流（applicable_conditions）：
  RD104_credit_scoring
    ├── RL104_scoring_standard         (通用)
    ├── RL104_scoring_quick_loan       (快贷：行为权重↑，征信权重↓)
    └── RL104_scoring_large_credit     (大额：征信权重↑↑，净资产加入)

  RD107_approval_decision
    ├── RL107_decision_quick           (R4 也可附条件通过)
    ├── RL107_decision_installment     (R3 需附条件)
    └── RL107_decision_large           (仅 R1-R3，净资产严格)

一票否决（priority=200，最高级）：
  RD101_veto_check → 黑名单/当前逾期 → 立即 REJECT，后续规则不执行
```

---

## 如何使用

### 加载 Schema

```python
from ontology_engine.services.schema_service import SchemaService

service = SchemaService()
space = service.load_from_yaml("examples/supply_chain_finance/schema.yaml")
```

### 加载实例并执行规则

```python
from ontology_engine.services.entity_service import EntityService
from ontology_engine.services.analysis_service import AnalysisService

entity_service = EntityService(space_id="space.supply_chain_finance")
entity_service.load_from_yaml("examples/supply_chain_finance/instances.yaml")

analysis_service = AnalysisService(space_id="space.supply_chain_finance")
result = analysis_service.execute_rules(
    entity_id="SUP_A",
    categorization="credit_assessment"
)
print(result.final_decision)   # APPROVE
```

### 运行验收用例

```python
from ontology_engine.services.query_service import QueryService

query_service = QueryService(space_id="space.supply_chain_finance")
results = query_service.run_testcases(
    testcases_path="examples/supply_chain_finance/testcases.yaml"
)
for tc in results:
    print(f"{tc.id}: {'PASS' if tc.passed else 'FAIL'}")
```

---

## 与设计文档关联

| 主题 | 参考文档 |
|------|---------|
| Schema v2 根级 grammar | `docs/05-schema-v2/09-canonical-schema-spec.md` |
| L1 事实对象 | `docs/05-schema-v2/01-fact-objects.md` |
| L2 分类层 | `docs/05-schema-v2/02-categorization.md` |
| L3 分析要素（含图指标） | `docs/05-schema-v2/03-analytical-elements.md` |
| L4 规则声明/实例分离 | `docs/05-schema-v2/04-business-logic.md` |
| 规则声明与实例详细规范 | `docs/05-schema-v2/07-rule-declaration-and-instance.md` |
| L3/L4 计算边界 ADR | `docs/architecture/decisions/007-l3-l4-computation-boundary.md` |

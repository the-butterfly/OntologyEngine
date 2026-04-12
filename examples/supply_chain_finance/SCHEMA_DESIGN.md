# 供应链金融授信评估 — Schema 设计说明

> 文件角色：当前案例的设计意图说明，**非** OntologyEngine canonical grammar 规范  
> 关联规范：`docs/05-schema-v2/09-canonical-schema-spec.md`  
> 关联配置：`schema.yaml`（定义）`instances.yaml`（数据）`testcases.yaml`（验收）

---

## 一、设计目标

本案例以**供应链金融授信评估**为场景，演示 OntologyEngine 四层 Schema v2 架构的完整推理链路：

```
L1 事实对象  →  L2 分类视角  →  L3 指标计算  →  L4 规则决策
（结构/关系）    （分析范围）    （量化度量）     （条件+动作）
```

核心演示能力：
1. **多维指标 DAG**：原子 → 派生 → 复合，自动拓扑排序执行
2. **图算法指标**：担保链深度、担保圈检测（`GuaranteeRelation` 图遍历）
3. **规则声明/逻辑分离**：同一规则声明绑定多个行业特化逻辑实例
4. **可解释决策**：每个规则执行步骤输出条件满足情况和推理依据

---

## 二、L1 事实对象层：领域模型

### 2.1 实体关系图

```
CoreEnterprise
      ▲  (procures_from)
      │
  Supplier ──has_invoice──▶ Invoice
      │
      ├──has_contract──▶ Contract
      │
      └──GuaranteeRelation──▶ Supplier（担保边，带属性）
              ▲
              └── 自引用，构成担保网络图
```

### 2.2 关键设计点

| 设计点 | 说明 |
|--------|------|
| **税务/舆情字段作原子指标来源** | `tax_compliance_score`、`negative_news_count_90d` 直接存于 Supplier 属性，模拟外部系统注入；L3 通过 `source.type: fact_attribute` 读取 |
| **GuaranteeRelation 作为关系对象** | 担保关系带属性（金额、类型、状态），在 L3 图指标中参与图遍历 |
| **Invoice 状态不派生** | 逾期判断依赖 `status == 'OVERDUE'`，不在 L1 计算派生布尔字段，保持事实层的纯洁性 |

---

## 三、L2 分类层：分析视角

本案例定义三个互相独立的分析维度：

| 维度 ID | 业务场景 | 触发事件 |
|---------|---------|---------|
| `credit_assessment` | 供应商提交融资申请时的信用评估 | `financing_application_submitted` |
| `transaction_monitoring` | 日常交易行为的持续监控 | `daily_batch_check`、`large_invoice_detected` |
| `risk_early_warning` | 多维风险信号的预警聚合 | `overdue_invoice_detected`、`negative_news_detected` |

**关键设计点**：分类层只定义"哪些实体在哪些视角下参与分析"，不存储派生属性值，不含任何计算逻辑。

---

## 四、L3 分析要素层：指标体系

### 4.1 指标依赖 DAG

```
                         ┌──────────────────────────────┐
                         │       credit_score (复合)     │
                         │     5维度加权 → [0,100]       │
                         └────────────┬─────────────────┘
                                      │
         ┌──────────────┬─────────────┼────────────────┬──────────────┐
         ▼              ▼             ▼                ▼              ▼
 business_stability  tax_score   reputation_score  guarantee_depth  core_ent_count
   (derived)         (atomic)       (derived)        (graph)         (atomic)
         │                              │
         ├── contract_fulfillment_rate  ├── negative_news_count_90d
         │       (derived)             └── overdue_invoice_ratio
         │            │                       (derived)
         ├── core_ent_count        ┌───────────────────┤
         └── overdue_invoice_ratio │ overdue_inv_amount│ total_inv_amount_90d
                    ▲              └───────────────────┘
                    │              (atomic)              (atomic)
                    └── [图遍历] Supplier→Invoice (status=OVERDUE)
```

### 4.2 指标类型对照

| 指标 | 类型 | 计算来源 |
|------|------|---------|
| `total_invoice_amount_90d` | atomic | 图遍历聚合 `SUM(Invoice.amount.value)` |
| `overdue_invoice_amount` | atomic | 图遍历聚合（`OVERDUE` 过滤） |
| `tax_compliance_score` | atomic | `Supplier.tax_compliance_score` 属性 |
| `overdue_invoice_ratio` | derived | `overdue_amount / total_amount * 100` |
| `contract_fulfillment_rate` | derived | `total_90d / total_contract * 100` |
| `business_stability_score` | derived | 多条件打分公式（L1 沙箱） |
| `guarantee_chain_depth` | graph | BFS 最长路径，`GuaranteeRelation` 边 |
| `has_guarantee_cycle` | graph | 环路检测，输出 boolean |
| `credit_score` | composite | 5维度加权求和 × 100 |
| `credit_grade` | scorecard | `credit_score` → 等级映射 |

### 4.3 L3 可覆盖性设计

标记 `overridable: true` 的指标允许 L4 规则逻辑通过 `$metric:xxx` 引用覆盖：

```yaml
# schema.yaml 中
- id: credit_score
  overridable: true     # L4 可以为特定行业提供自定义评分逻辑

# RL002_score_manufacturing_boost 中
then_action:
  output:
    credit_score: "min(100, $metric:credit_score + 5)"   # 覆盖标准值
```

---

## 五、L4 业务逻辑层：规则声明与逻辑

### 5.1 规则声明/逻辑分离设计

```
Rule Definition（声明）      Rule Logic（逻辑实例）
─────────────────────────    ─────────────────────────────────────────
RD002_credit_score_compute → RL002_score_standard         (通用行业)
                           → RL002_score_manufacturing_boost (制造业)

RD001_basic_eligibility    → RL001_eligibility_standard   (统一准入)
```

**价值**：同一声明（I/O 契约不变）可绑定多个逻辑实例，按 `applicable_conditions` 分流，实现"场景化规则"而无需重复声明元数据。

### 5.2 规则执行链（credit_assessment 维度）

```
输入：Supplier 实体 + 激活 credit_assessment 维度
       │
       ▼ priority=100
  RD001 基础准入检查
  RL001_eligibility_standard
       │ is_eligible=false → 终止，输出 REJECT
       │ is_eligible=true
       ▼ priority=95
  RD003 担保圈检测（图算法）
  RL003_guarantee_alert
       │ 触发 CRITICAL 预警（如有担保圈）
       │
       ▼ priority=90
  RD002 信用评分计算
  RL002_score_standard / RL002_score_manufacturing_boost
       │ 输出 credit_score + credit_grade
       │
       ▼ priority=80
  RD004 授信额度计算
  RL004_limit_formula
       │ 输出 recommended_credit_limit
       │
       ▼ priority=70
  RD005 风险预警
  RL005_warning_thresholds
       │ （可能触发多条 MEDIUM/HIGH 预警）
       │
       ▼ priority=50
  RD006 综合授信决策
  RL006_decision_table
       │
       ▼
  输出：final_decision + approved_credit_limit + decision_reason
```

### 5.3 算子使用说明

| 算子类型 | 使用场景 | 规则 |
|----------|---------|------|
| `set_flag` | 设置布尔/枚举状态 | RL001（准入标志） |
| `compute` | 公式计算或引用 L3 指标 | RL002、RL004、RL006 |
| `alert` | 触发结构化预警 | RL003、RL005 |
| `$metric:xxx` | 引用 L3 指标计算结果 | RL002（score 引用） |

---

## 六、三个验收场景设计意图

### CASE-A：优质供应商（正常路径）

| 维度 | 数值 | 结论 |
|------|------|------|
| 注册资本 | 5000万 | ✅ 远超门槛 |
| 成立年限 | 8年 | ✅ 通过 |
| 逾期发票占比 | ~1.2%（15万/1245万） | ✅ 远低于5%警戒线 |
| 税务合规 | 88分 | ✅ 优 |
| 担保链深度 | 0 | ✅ 无风险 |
| **预期信用评分** | **~85-88分（AA级）** | |
| **预期决策** | **APPROVE，额度约3375万** | |

验收要点：完整执行链路通过，无预警触发，高评分正常批准。

---

### CASE-B：高风险供应商（失败路径）

| 维度 | 数值 | 结论 |
|------|------|------|
| 注册资本 | 100万 | ⚠️ 刚在门槛 |
| 成立年限 | 约7个月 | ❌ 未满1年 |
| 逾期发票占比 | 80%（800万/1000万） | ❌ 极高 |
| 舆情条数 | 4条 | ❌ 超阈值 |
| **预期结论** | **准入检查失败 → REJECT** | |

验收要点：准入规则（RL001）的 `else_action` 正确触发，整体流程短路终止，不进入评分阶段。

---

### CASE-C：担保圈供应商（图算法路径）

```
SUP_C_A ──担保──▶ SUP_C_C ──担保──▶ SUP_C_B ──担保──▶ SUP_C_A
                                                          ↑
                                                        (循环！)
```

| 维度 | 数值 | 结论 |
|------|------|------|
| 各方注册资本 | 800万~1200万 | ✅ 基础面尚可 |
| 成立年限 | 5-6年 | ✅ 通过 |
| 担保链深度 | 2（三角圈） | ⚠️ 达阈值 |
| `has_guarantee_cycle` | true | ❌ 担保圈 |
| **预期信用评分** | **约55-65分（BB/B级）** | 担保风险拉低评分 |
| **预期决策** | **APPROVE_WITH_CONDITIONS，额度打8折** | |
| **预警** | **RL003 触发 CRITICAL 担保圈预警** | |

验收要点：图算法指标正确计算担保圈，预警规则正确触发，额度计算正确应用担保折扣。

---

## 七、与设计文档的对应关系

| 本案例设计元素 | 对应设计文档 |
|---------------|-------------|
| canonical 根级结构 | `docs/05-schema-v2/09-canonical-schema-spec.md` |
| fact_objects / relations | `docs/05-schema-v2/01-fact-objects.md` |
| categorizations | `docs/05-schema-v2/02-categorization.md` |
| analytical_elements（含 graph 类型） | `docs/05-schema-v2/03-analytical-elements.md` |
| rule_definitions / rule_logics | `docs/05-schema-v2/04-business-logic.md` |
| 规则声明/实例分离 | `docs/05-schema-v2/07-rule-declaration-and-instance.md` |
| L3 overridable + L4 覆盖 | `docs/architecture/decisions/007-l3-l4-computation-boundary.md` |

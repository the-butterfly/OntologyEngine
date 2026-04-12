# 个人消费信贷风险评估 — 案例设计说明

> 文件角色：本案例的设计意图说明与关键设计点注释  
> 关联配置：`schema.yaml` / `instances.yaml` / `testcases.yaml`  
> 与供应链案例对比阅读效果最佳

---

## 一、案例定位：互补供应链案例的关键设计维度

| 设计能力 | 供应链金融案例 | 消费信贷案例 |
|---------|-------------|------------|
| 多维指标 DAG | ✅ 5维评分，图指标 | ✅ 5维评分卡，行为/网络维度 |
| 规则声明/逻辑分离 | ✅ 制造业加成分流 | ✅ 三类产品（快贷/分期/大额）分流 |
| 图算法指标 | ✅ 担保链深度+担保圈检测 | ✅ 共借人/担保人逾期传导 |
| **一票否决逻辑** | ❌ 无 | ✅ is_blacklisted 最高优先级短路 |
| **L3 Indicator（布尔指示器）** | ❌ 无 | ✅ is_blacklisted / has_stable_income / has_current_overdue |
| **多实体联合评估** | 单实体（Supplier） | ✅ Borrower + LoanApplication 联合 |
| **产品差异化规则** | 单一维度 | ✅ 三类产品不同评分权重+不同决策阈值 |
| **What-if 模拟** | ✅ 基础 | ✅ 黑名单拦截 / 产品边界 |

---

## 二、L1 设计亮点：多实体联合与关系网络

```
Borrower ──has_applications──▶ LoanApplication
    │
    ├──co_borrows_with──▶ Borrower (BorrowerRelation 边，带 relation_type)
    ├──guarantees_for──▶  Borrower
    └──belongs_to(inverse)──▶ RepaymentRecord
```

**关键设计点**：
- `BorrowerRelation` 是自引用关系对象，`relation_type` 区分共借/担保/紧急联系
- `RepaymentRecord` 通过图遍历计算 `repayment_on_time_count` / `total_repayment_count`，与传统字段存储方式形成对比

---

## 三、L3 设计亮点：Indicator 类型

L3 新增 `indicators` 区分布尔类型指示器：

```yaml
indicators:
  - id: is_blacklisted      # 直接取 fact_attribute，boolean
  - id: has_stable_income   # 派生计算，条件组合
  - id: has_current_overdue # 派生，current_overdue_amount.value > 0
```

**与 metrics 的区别**：
- Metric：连续量（评分、比例、金额）
- Indicator：离散状态（是/否、枚举级别）

**L4 使用方式**：RD101 通过 `type: indicator` 引用，做一票否决判断。

---

## 四、L4 规则声明/逻辑分离的三层嵌套

```
RD104_credit_scoring（声明：信用评分，I/O 契约固定）
  ├── RL104_scoring_standard       (通用行业，默认逻辑)
  ├── RL104_scoring_quick_loan     (快贷：行为评分↑，征信↓)
  └── RL104_scoring_large_credit   (大额：征信↑，行为↓，净资产加入)

RD107_approval_decision（声明：最终决策，I/O 契约固定）
  ├── RL107_decision_quick         (快贷：R4 也可附条件通过)
  ├── RL107_decision_installment   (分期：R3 需附条件)
  └── RL107_decision_large         (大额：仅 R1-R3，净资产严格)
```

**applicable_conditions 分流机制**：
```yaml
applicable_conditions:
  - classification: loan_type
    operator: eq
    value: QUICK_LOAN
```
运行时按 `LoanApplication.loan_type` 选择对应的逻辑实例，同一声明实现产品差异化。

---

## 五、规则优先级设计意图

| 优先级 | 规则 | 设计意图 |
|--------|------|---------|
| 200 | RD101 一票否决 | **最先执行**，失败立即短路整个链路 |
| 180 | RD102 基础准入 | 门槛校验，不满足则后续评分无意义 |
| 160 | RD103 偿债能力 | 准入通过后计算压力指标，为决策提供输入 |
| 140 | RD104 信用评分 | 准入通过后触发 L3 评分卡 |
| 130 | RD105 网络风险 | 并行图算法，结果影响最终决策 |
| 80  | RD106 利率定价 | 评分完成后根据风险等级定价 |
| 50  | RD107 最终决策 | **最后执行**，汇总所有输入做综合决策 |

---

## 六、三个实例的验收场景设计意图

### CASE-P：张伟（优质借款人）

- 月收入3万，DTI=0.1，征信720，零逾期，无网络风险
- 验证**完整正常路径**：从准入到利率定价到 APPROVED
- 同时验证**快贷分流**（TC-C02）：RL104_scoring_quick_loan 权重重分配

### CASE-M：李敏（中等风险，边界测试）

- 自雇，月收入8000元（年收入9.6万 < 12万自雇收入门槛）
- **TC-C03 核心验证点**：`has_stable_income=false` 导致准入失败
- 体现设计中"自雇收入稳定性门槛"的逻辑精确性

### CASE-R：王芳（关系网络风险）

- 自身资质良好（R2 评分），但共同借款人陈刚当前逾期1.5万
- **TC-C05 核心验证点**：图遍历识别 `co_borrower_risk_count=1`，触发 MEDIUM 网络预警
- 验证**图算法对非直接风险的识别能力**：王芳自身无问题，但系统识别出潜在风险并纳入决策

---

## 七、与 docs/ 设计文档的对应关系

| 本案例设计元素 | 对应设计文档 |
|---------------|-------------|
| 多实体联合 Rule Definition | `docs/05-schema-v2/04-business-logic.md §1.3` |
| L3 indicators 类型 | `docs/05-schema-v2/03-analytical-elements.md §1.2` |
| applicable_conditions 分流 | `docs/05-schema-v2/04-business-logic.md §2.1` |
| priority + 短路执行 | `docs/05-schema-v2/04-business-logic.md §5.1` |
| graph traversal 聚合指标 | `docs/05-schema-v2/03-analytical-elements.md §1.3` |
| L3 overridable + L4 覆盖 | `docs/architecture/decisions/007-l3-l4-computation-boundary.md` |

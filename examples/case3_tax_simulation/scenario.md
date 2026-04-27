# Case 3 场景说明 — 亚太区总部策略沙盘

> **文件角色**: 业务场景与资产说明 **[待核对代码]**

---

## 一、目标用户

- **CFO / 战略财务负责人**：比较不同区域总部布局方案
- **税务与财务架构经理**：维护场景参数、成本假设和风险说明
- **投资决策支持团队**：需要把推荐方案直接转成管理层报告

---

## 二、业务背景

某消费品集团正在评估下一财年的亚太区总部布局。现有组织同时涉及：

- 香港 IP 管理职能
- 新加坡运营协调与共享服务职能
- 中国大陆制造与采购职能

管理层需要比较 3 套方案：

| 场景 | 方案 | 核心差异 |
|------|------|----------|
| A | 香港主导 | IP 与总部治理集中，运营协同较轻 |
| B | 新加坡主导 | 共享服务与区域运营集中 |
| C | 双中心混合 | 香港管 IP，新加坡管运营 |

过去的问题是：

- 假设参数分散在邮件、Excel、会议纪要中
- 一旦改场景参数，就很难同步更新对比矩阵与管理层报告
- 管理层看到结论，却很难知道结论基于哪版假设

本案例要把“场景假设”本身也变成知识资产。

---

## 三、本案例中的知识资产

### 3.1 可编辑资产

| 资产 | 示例 | 用途 | 资产类型 |
|------|------|------|----------|
| 场景包 | `scenario_pack.apac_hq_a@v1` | 香港主导方案参数 | 固定资产对象 |
| 场景包 | `scenario_pack.apac_hq_b@v1.1` | 新加坡主导方案参数 | 固定资产对象 |
| 场景包 | `scenario_pack.apac_hq_c@v1` | 双中心方案参数 | 固定资产对象 |
| 假设卡 | `assumption.service_fee_rate` | 服务费率、IP 费率、人员编制 | 固定资产对象 |
| 评分卡 | `strategy_scorecard@v1` | 推荐逻辑和权重 | 固定资产对象 |
| 仿真报告模板 | `report_template.strategy_decision@v1` | CFO 报告模板（含章节结构、指标引用、版本索引） | 固定资产对象 |

> **固定资产对象说明**：场景包、假设卡和报告模板是独立于单次仿真运行的知识资产。
> 它们有版本号、可编辑、可被多次仿真消费，且消费结果可回溯到具体版本的参数与模板。

### 3.2 消费资产

| 资产 | 示例 | 用途 |
|------|------|------|
| 视图 | `view.apac_strategy_sandbox` | 三方案比较视图 |
| 报告 | `report.apac_hq_decision` | CFO 决策报告（由 `report_template.strategy_decision@v1` 生成） |
| 执行轨迹 | `trace.strategy_recommendation` | 推荐结论解释链 |

### 3.3 报告模板作为固定资产对象

仿真报告模板 `report_template.strategy_decision@v1` 定义了 CFO 报告的结构：

```yaml
report_template:
  id: "report_template.strategy_decision"
  version: "v1"
  sections:
    - title: "基线方案对比"
      source: "view.apac_strategy_sandbox"
      metrics: ["effective_tax_rate", "annual_tax_cost_cny", "cash_repatriation_days"]
    - title: "场景参数 diff"
      source: "scenario_pack.diff"
      show_version: true
    - title: "推荐切换原因"
      source: "trace.strategy_recommendation"
      show_defined_in: true
    - title: "关键指标变化表"
      source: "view.apac_strategy_sandbox"
      show_before_after: true
    - title: "证据索引与版本索引"
      source: "trace.*"
      show_all_mutual_index: true
```

报告模板的关键特性：
- **版本化**：模板本身有版本号，报告可追溯到模板版本
- **参数化引用**：章节内容引用视图和场景包，不是硬编码
- **消费结果互证**：报告中的数字来自视图，推荐来自评分卡，参数 diff 来自场景包

---

## 四、核心比较指标

案例中的结果消费不只看单一“税务成本”，而是统一看 5 个指标：

| 指标 | 含义 |
|------|------|
| `effective_tax_rate` | 综合有效税率 |
| `annual_tax_cost_cny` | 年化税务成本 |
| `cash_repatriation_days` | 资金回流周期 |
| `compliance_workload_index` | 合规管理复杂度 |
| `top_up_tax_exposure` | 最低税补足风险 |

---

## 五、真实感数据结构

### 5.1 基线场景对比（合成但真实）

| 场景 | 年税务成本（百万元） | ETR | 资金回流（天） | 合规工作量指数 | 综合得分 |
|------|---------------------:|----:|---------------:|---------------:|---------:|
| A 香港主导 | 450 | 13.2% | 21 | 52 | 82 |
| B 新加坡主导 | 520 | 14.1% | 18 | 47 | 78 |
| C 双中心混合 | 480 | 12.8% | 28 | 73 | 75 |

### 5.2 可编辑假设样例

- `service_fee_rate`
- `royalty_rate`
- `regional_hq_headcount`
- `duplicated_control_cost`
- `cash_pooling_efficiency`

这些参数的变化，会直接影响：

- 场景对比矩阵
- 推荐结论
- 报告正文

---

## 六、案例闭环

```text
场景包 / 假设卡 / 评分卡
  ↓
运行 simulation compare
  ↓
view.apac_strategy_sandbox
  ↓
trace.strategy_recommendation
  ↓
report.apac_hq_decision
  ↓
修改 scenario_pack.apac_hq_b@v1.1 后重新执行
```

---

## 七、本案例要证明什么

1. **仿真不是一次性结果，而是基于可编辑参数包的连续分析过程**
2. **推荐结论必须能回溯到场景参数和权重定义**
3. **参数更新后，视图和报告需要同步变化，避免“结果与报告脱节”**

这使 `case3` 从“能做 What-if”提升为“能做可解释的策略沙盘”。
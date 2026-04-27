# Case 3 用户旅程 — 场景参数包驱动的策略沙盘

> **文件角色**: narrative journey **[待核对代码]**

---

## 旅程概览

本案例通过 8 个步骤展示：

1. 加载区域总部策略空间
2. 注册三个场景包
3. 创建策略沙盘视图
4. 运行基线对比
5. 编辑场景 B 假设并发布新版本
6. 重新运行比较并观察推荐变化
7. 查看推荐解释链
8. 生成 CFO 报告

---

## Step 1：创建策略空间并导入基础数据

### 操作

```bash
ontology-cli space create --name apac_strategy_sandbox
ontology-cli schema load --space space.tax_apac_2026 --file schema.yaml
ontology-cli entities batch-import --space space.tax_apac_2026 --file instances.yaml
```

### 验证点

- [ ] 子公司、交易和场景基础数据已导入
- [ ] 可用于后续 What-if 干运行

---

## Step 2：注册三个场景包

### 场景包

- `scenario_pack.apac_hq_a@v1`
- `scenario_pack.apac_hq_b@v1`
- `scenario_pack.apac_hq_c@v1`

### 样例参数

```json
{
  "scenario_id": "apac_hq_b",
  "version": "v1",
  "assumptions": {
    "service_fee_rate": 0.07,
    "regional_hq_headcount": 180,
    "cash_pooling_efficiency": 0.72,
    "duplicated_control_cost": 32
  }
}
```

### 验证点

- [ ] 场景参数包作为资产可独立管理
- [ ] 每个场景包都带版本号和说明

---

## Step 3：创建策略沙盘视图

### 操作

```json
POST /v1/views
{
  "view_id": "view.apac_strategy_sandbox",
  "space_id": "space.tax_apac_2026",
  "dimensions": ["scenario_id", "version"],
  "metrics": [
    "effective_tax_rate",
    "annual_tax_cost_cny",
    "cash_repatriation_days",
    "compliance_workload_index",
    "top_up_tax_exposure"
  ],
  "rules": ["strategy_scorecard"]
}
```

### 目标

所有场景结果最终都要回到同一个视图消费入口，而不是散落在脚本输出里。

---

## Step 4：运行基线对比

### 操作

```bash
ontology-cli simulation compare \
  --space space.tax_apac_2026 \
  --view view.apac_strategy_sandbox \
  --scenarios apac_hq_a,apac_hq_b,apac_hq_c
```

### 基线结果

| 场景 | 得分 | 推荐状态 |
|------|-----:|----------|
| A | 82 | 推荐 |
| B | 78 | 备选 |
| C | 75 | 不推荐 |

### 结论

基线下场景 A 被推荐，原因是：

- 税务成本较低
- 合规工作量可控
- 资金回流周期处于中等偏优水平

---

## Step 5：编辑场景 B 假设并发布 `v1.1`

### 背景

管理层提出：若把新加坡共享服务编制从 180 调整为 140，并同步优化服务费率，场景 B 可能更具吸引力。

### 操作

```json
{
  "scenario_id": "apac_hq_b",
  "from_version": "v1",
  "to_version": "v1.1",
  "changes": {
    "service_fee_rate": 0.06,
    "regional_hq_headcount": 140,
    "duplicated_control_cost": 24
  }
}
```

### 预期

- 场景 B 税务成本下降
- 合规工作量指数改善
- 综合得分提升

---

## Step 6：重新运行比较并观察推荐变化

### 操作

```bash
ontology-cli simulation compare \
  --space space.tax_apac_2026 \
  --view view.apac_strategy_sandbox \
  --scenarios apac_hq_a,apac_hq_b@v1.1,apac_hq_c
```

### 期望输出摘要

```json
{
  "comparison_result": {
    "scenario_A": {"score": 82},
    "scenario_B_v1_1": {"score": 83},
    "scenario_C": {"score": 75}
  },
  "recommended": "scenario_B_v1.1"
}
```

### 验证点

- [ ] 参数包变化直接反映到对比视图
- [ ] 推荐方案可以从 A 切换到 B v1.1
- [ ] 差异解释不再停留在“看分数”，而是有具体假设变更说明

---

## Step 7：查看推荐解释链

### 操作

```json
GET /v1/views/view.apac_strategy_sandbox/execution/recommendation
```

### 期望链路

- `defined_in`: `strategy_scorecard@v1`
- `supported_by`: `assumption.service_fee_rate`, `assumption.regional_hq_headcount`
- `extracted_from`: 各场景的计算结果
- `trace_to`: `report.apac_hq_decision`

### 验证点

- [ ] 用户能知道推荐结论基于哪版评分卡和哪版场景包
- [ ] 用户能打开参数 diff 做人工判断

---

## Step 8：生成 CFO 报告

### 操作

```bash
ontology-cli report generate \
  --space space.tax_apac_2026 \
  --view view.apac_strategy_sandbox \
  --type strategy_decision \
  --format pdf
```

### 报告必须包含

- 基线方案对比
- 场景 B `v1 → v1.1` 参数 diff
- 推荐切换原因
- 关键指标变化表
- 证据索引与版本索引

---

## 结论

只要用户能够完成一次“改场景参数包 → 重新 compare → 推荐方案变化 → 报告同步更新”的操作，`case3` 就真正具备了策略沙盘价值，而不是单纯的 What-if 结果截图。
# Case 3 可视化稿 — 亚太区总部策略沙盘

> **文件角色**: 视觉化叙事草图 **[待核对代码]**

---

## 一、策略沙盘总览

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                        Strategy Sandbox / view.apac_strategy_sandbox                    │
├──────────────────────────────┬────────────────────────────────────┬──────────────────────┤
│ 左侧：场景参数资产            │ 中间：比较视图                     │ 右侧：推荐解释链       │
│                              │                                    │                      │
│ scenario A @v1               │ 基线结果                           │ Recommendation Trace │
│ • 香港主导                   │ A: 82  ★ 推荐                      │ • defined_in         │
│                              │ B: 78                              │   strategy_scorecard │
│ scenario B @v1               │ C: 75                              │ • supported_by       │
│ • 新加坡主导                 │                                    │   service_fee_rate   │
│ • fee=7%                     │ 参数编辑后                         │   headcount          │
│ • headcount=180              │ A: 82                              │ • extracted_from     │
│                              │ B v1.1: 83 ★ 新推荐               │   scenario outputs   │
│ scenario B @v1.1             │ C: 75                              │ • trace_to           │
│ • fee=6%                     │                                    │   report.apac_hq...  │
│ • headcount=140              │ 关键差异                           │                      │
│                              │ • tax cost ↓                       │ Version Diff         │
│ scenario C @v1               │ • workload index ↓                 │ v1 → v1.1            │
│ • 双中心混合                 │ • cash repatriation stable         │ fee 7% → 6%         │
└──────────────────────────────┴────────────────────────────────────┴──────────────────────┘
```

---

## 二、场景参数 diff 表

| 参数 | B v1 | B v1.1 | 影响 |
|------|------|---------|------|
| `service_fee_rate` | 7% | 6% | 年税务成本下降 |
| `regional_hq_headcount` | 180 | 140 | 管理冗余减少 |
| `duplicated_control_cost` | 32 | 24 | 合规工作量指数下降 |

---

## 三、推荐切换说明

```text
Baseline recommendation:
  Scenario A
    └─ 原因：成本低 + 工作量可控

After B v1.1:
  Scenario B v1.1
    ├─ 年税务成本下降
    ├─ 合规工作量下降
    └─ 综合得分超过 A
```

---

## 四、这个页面要证明什么

1. **场景包是资产，不是一次性输入参数**
2. **参数改动后，compare 视图和报告都会变化**
3. **推荐结论能回到参数版本与评分卡定义**

这也是 `case3` 从“税务仿真案例”升级为“策略沙盘案例”的关键。
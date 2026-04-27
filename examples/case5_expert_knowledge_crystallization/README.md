# Case 5: 风控专家经验规则化

> **status**: draft | **phase**: phase1-2 | **last_verified**: 2026-04-26
> **文件角色**: hybrid case，叙事旅程 + 结构化验收 **[待核对代码]**

---

## 一、案例定位

本案例用于补齐 `examples/` 中另一个关键空白：**个人经验如何变成组织可复用的规则资产。**

它强调的不是规则执行本身，而是：

- 专家如何提交观察
- 系统如何形成候选规则
- 评审如何决定发布或拒绝
- 发布后如何验证对风险名单的实际影响

---

## 二、核心资产

| 资产类型 | 示例 |
|----------|------|
| 专家观察卡 | `note.expert_zhang.2026-04-12` |
| 候选规则卡 | `candidate.guarantee_depth_plus_news` |
| 评审记录 | `review.rule_candidate.2026-04-18` |
| 已发布规则组 | `risk_pattern_pack@v1.0` |
| 风险名单视图 | `view.risk_watchlist_daily` |

---

## 三、案例价值

这个案例要证明两件事：

1. **知识不只来自文档，也来自一线专家反复验证的经验**
2. **经验升级成规则后，必须能在下游结果中被验证，而不是停留在“我觉得这样更对”**

---

## 四、建议阅读顺序

1. [`scenario.md`](./scenario.md)
2. [`journey.md`](./journey.md)
3. [`visualization/knowledge_review_board.md`](./visualization/knowledge_review_board.md)

---

## 五、当前状态说明

本案例已完成以下内容：

- ✅ narrative content（scenario / journey / visualization）
- ✅ `schema.yaml` — L1-L4 完整四层模型，含专家观察卡、候选规则卡、已发布规则组
- ✅ `instances.yaml` — 6 家供应商、3 条专家观察、2 条候选规则、1 个已发布规则组、2 条风险标记
- ✅ `testcases.yaml` — 8 条验收用例（TC-301 ~ TC-308），覆盖规则命中、边界、指标计算、知识资产溯源

本案例当前可作为 **结构化验收案例 + 叙事旅程案例** 的混合体使用。
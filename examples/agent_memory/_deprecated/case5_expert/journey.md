# Case 5 用户旅程 — 专家经验规则化闭环

> **文件角色**: narrative journey **[待核对代码]**

---

## 旅程概览

本案例通过 7 个步骤展示：

1. 导入专家观察卡
2. 聚合为候选规则
3. 在评审看板中评估覆盖与误报风险
4. 发布组织规则组
5. 重新计算风险名单视图
6. 查看新增命中对象
7. 如有必要执行回滚

---

## Step 1：记录专家观察

### 样例观察卡

```json
{
  "note_id": "note.expert_zhang.2026-04-12",
  "pattern": "guarantee_depth >= 4 AND negative_news_90d >= 2",
  "related_entities": ["SUP_R_012", "SUP_R_044", "SUP_R_077"],
  "comment": "历史上该组合特征出现后，违约前预警信号明显增强"
}
```

### 验证点

- [ ] 专家观察作为独立资产存储
- [ ] 可关联样本实体和理由说明

---

## Step 2：生成候选规则卡

### 目标

把多条相似观察聚合成一个候选规则：

`candidate.guarantee_depth_plus_news`

### 需要展示的信息

- 被多少条专家观察支持
- 命中过哪些高风险历史样本
- 潜在误报范围

---

## Step 3：进入评审看板

### 评审维度

| 维度 | 示例值 |
|------|--------|
| 样本覆盖数 | 18 |
| 高风险样本命中率 | 72% |
| 潜在误报率 | 11% |
| 推荐动作 | 通过试运行 |

### 验证点

- [ ] 评审人能看到候选规则的收益与风险
- [ ] 评审结论成为独立资产，不只是聊天记录

---

## Step 4：发布组织规则组

### 操作

```json
{
  "rule_group": "risk_pattern_pack",
  "version": "v1.0",
  "source_candidate": "candidate.guarantee_depth_plus_news",
  "status": "ACTIVE"
}
```

### 验证点

- [ ] 组织规则组带来源候选规则引用
- [ ] 发布后具备版本号和回滚入口

---

## Step 5：重算风险名单视图

### 操作

```json
POST /v1/views/view.risk_watchlist_daily/execute/analyze
{
  "version": "risk_pattern_pack@v1.0"
}
```

### 预期变化

- 新增命中对象进入风险名单
- 原有高风险对象的解释链更完整

---

## Step 6：查看新增命中对象

### 示例

| 实体 | 命中原因 | 来源 |
|------|----------|------|
| `SUP_R_101` | 担保链深度=5 且负面舆情=3 | `risk_pattern_pack@v1.0` |
| `SUP_R_123` | 担保链深度=4 且负面舆情=2 | `candidate.guarantee_depth_plus_news` |

### 期望证据链

- `defined_in`: `risk_pattern_pack@v1.0`
- `supported_by`: `review.rule_candidate.2026-04-18`
- `trace_to`: `view.risk_watchlist_daily`

---

## Step 7：必要时回滚

如果试运行后误报偏高，可以：

- 回退到 `risk_pattern_pack@draft`
- 或直接禁用 `risk_pattern_pack@v1.0`

### 验证点

- [ ] 风险名单会恢复到旧版本结果
- [ ] 用户可以证明回滚与名单变化是同一因果链条

---

## 结论

本案例最终要证明：**知识沉淀不是“收集意见”，而是“把专家经验变成能发布、能验证、能回滚的组织资产”。**
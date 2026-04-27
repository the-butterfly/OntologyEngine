# Case 5 场景说明 — 从专家观察到组织规则

> **文件角色**: 业务场景与资产说明 **[待核对代码]**
> **规则组模型映射**: 候选规则 → RuleDefinition + RuleLogic → 已发布规则组

---

## 一、业务背景

供应链金融风控团队里，一位资深专家连续数周发现一个模式：

> “当供应商担保链深度 ≥ 4，且近 90 天负面舆情 ≥ 2 条时，违约前的预警信号显著增强。”

过去这个经验通常停留在：

- 专家私有 Excel
- 飞书/邮件备注
- 评审会议口头经验

问题在于：

- 新同事很难复用
- 规则团队不知道什么时候值得正式发布
- 发布后也无法量化“这条经验到底有没有价值”

---

## 二、本案例中的资产对象

| 资产 | 示例 | 用途 |
|------|------|------|
| 专家观察卡 | `note.expert_zhang.2026-04-12` | 记录专家判断与理由 |
| 候选规则卡 | `candidate.guarantee_depth_plus_news` | 聚合相似观察，形成待评审规则 |
| 评审记录 | `review.rule_candidate.2026-04-18` | 记录评审意见、通过与否 |
| 组织规则组 | `risk_pattern_pack@v1.0` | 发布后供全体用户使用 |
| 风险名单视图 | `view.risk_watchlist_daily` | 验证规则发布后的实际命中情况 |

---

## 三、案例闭环

```text
专家观察卡
  ↓
候选规则卡
  ↓
评审结论
  ↓
组织规则组发布
  ↓
view.risk_watchlist_daily 命中结果变化
  ↓
trace 回到专家原始观察与评审记录
```

---

## 四、关键验证问题

- 这条经验是否真的反复出现，而不是偶然现象？
- 发布成规则后，新增命中的对象有哪些？
- 如果误报过高，能不能快速回滚或下线？
- 用户是否能知道某条规则最初来自哪位专家的观察？

---

## 五、规则组模型映射

### 5.1 候选规则到 RuleDefinition 的映射

| 候选规则卡 | 映射到 RuleDefinition | 映射到 RuleLogic |
|-----------|----------------------|-----------------|
| `candidate.guarantee_depth_plus_news` | `RD_guarantee_depth_news_check` | `RL_guarantee_depth_news_standard` |
| 条件：`guarantee_depth >= 4 AND negative_news_90d >= 2` | `when.expression` | `when.expression` + `then_action` |

### 5.2 已发布规则组到现有模型的映射

| 发布后规则组 | 对应 RuleDefinition | 版本 | 状态 |
|-------------|--------------------|------|------|
| `risk_pattern_pack@v1.0` | `RD_guarantee_depth_news_check` | v1 | ACTIVE |
| `risk_pattern_pack@v1.1` | `RD_guarantee_depth_news_check` | v1.1 | DRAFT（阈值调整中） |

### 5.3 资产升级链路

```text
专家观察卡（personal note）
  ↓ 聚合相似观察
候选规则卡（candidate rule）
  ↓ 评审通过
RuleDefinition + RuleLogic（规则声明 + 规则逻辑）
  ↓ 发布
规则组 risk_pattern_pack@vX（已发布组织规则）
  ↓ 执行
view.risk_watchlist_daily（风险名单视图）
  ↓ 回溯
trace → 原始专家观察 + 评审记录
```

### 5.4 知识资产呈现与编辑互证

| 呈现场景 | 资产对象 | 呈现方式 |
|----------|----------|----------|
| 观察卡列表 | `note.expert_zhang.2026-04-12` | 左侧面板，含模式描述、关联实体、专家评论 |
| 候选规则卡 | `candidate.guarantee_depth_plus_news` | 样本覆盖数、命中率、误报率、支持观察数 |
| 评审看板 | `review.rule_candidate.2026-04-18` | 评审维度、结论、通过/拒绝/试运行 |
| 已发布规则组 | `risk_pattern_pack@v1.0` | 规则条件、版本号、回滚入口 |
| 风险名单视图 | `view.risk_watchlist_daily` | 新增命中实体、命中原因、来源规则 |

| 编辑动作 | 变更内容 | 影响范围 |
|----------|----------|----------|
| 候选规则评审通过 | 状态从 DRAFT → ACTIVE | 规则组发布、风险名单更新 |
| 规则组阈值调整 | 担保链深度从 4 调为 3 | 命中实体增加、误报可能上升 |
| 规则组回滚 | v1.0 → draft | 风险名单恢复到旧版本 |

---

## 六、案例价值

这是 OntologyEngine 相比传统“文档库 + 规则库”更独特的部分：

- 不只是消费知识
- 也不只是执行知识
- 而是把**组织知识的形成过程**变成可以管理、评审、发布和验证的资产链路
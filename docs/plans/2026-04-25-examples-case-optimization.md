# Examples 案例补强实施计划（2026-04-25）

> **status**: in-progress | **phase**: phase1-2 | **last_verified**: 2026-04-26
> **related_analysis**: `docs/plans/use-case-plan-competitive-analysis.md`
> **定位**: 面向 `examples/` 的落地实施计划，补齐案例内容、知识资产闭环与真实业务口径

---

## 一、背景与本轮目标

`docs/plans/use-case-plan-competitive-analysis.md` 已经明确指出：当前案例对 **Layer-R / Layer-S 协同检索、知识沉淀闭环、四类互索引完整展示、时序回溯、矛盾检测** 的覆盖不足，且已有案例更多停留在"功能展示"，未形成 **知识资产编辑 → 资产呈现 → 结果消费 → 证据回溯** 的完整闭环。

本轮补强的目标不是继续堆功能点，而是让 `examples/` 里的核心案例具备以下 4 个特征：

1. **案例数据口径真实**：优先采用公开通行的企业经营分析公式与场景结构，数值可做合成，但不能脱离真实业务习惯。
2. **知识资产可见**：让用户能看见被消费的资产对象是什么，例如指标卡、规则组、视图、证据碎片、报告模板、场景参数包。
3. **知识资产可编辑**：案例中必须出现一次明确的编辑动作，例如修正规则阈值、修订指标公式、发布规则新版本、回滚到旧版本。
4. **消费结果可反证资产**：视图结果、问答结果、仿真报告需要能回溯到资产版本与证据来源，证明"结果不是黑箱"。

---

## 二、设计原则

## 2.1 闭环优先于功能罗列

每个重点案例至少覆盖以下闭环：

```text
源数据 / 文档碎片
  ↓
知识资产建模（指标 / 规则 / 视图 / 场景）
  ↓
资产编辑 / 发布 / 版本化
  ↓
视图消费 / 问答消费 / 报告消费
  ↓
证据回溯 / 影响分析 / 版本比对
```

## 2.2 使用真实企业经营口径，而非"玩具指标"

本轮以公开通用财务/经营指标口径作为样板，重点引入：

- **毛利率（Gross Margin）**：
  \[
  \text{Gross Margin} = \frac{Revenue - COGS}{Revenue}
  \]
- **DSO（应收账款周转天数）**：
  \[
  \text{DSO} = \frac{Accounts\ Receivable}{Net\ Credit\ Sales} \times Days
  \]
- **DIO（库存周转天数）**：
  \[
  \text{DIO} = \frac{Average\ Inventory}{COGS} \times Days
  \]

> 说明：以上口径参考 Corporate Finance Institute（CFI）的公开定义；案例数值允许使用**合成但真实感足够**的数据，避免伪造具体上市公司事实。
>
> 行业基准参考：中国百货商业协会《2024-2025 大型零售企业发展指数》报告——百货零售企业平均毛利率 41.1%，超市 24.7%；CreditPulse 2025 DSO Benchmark——零售行业 5-30 天。

## 2.3 区分"实现事实"与"案例蓝图"

新增或补强的 narrative case 文档统一按以下口径编写：

- 已有代码路径可以直接支撑的部分：写成"当前案例可演示"
- 依赖 Phase 2 的能力：明确标记 **[待核对代码]**
- 不再把设计稿写成已实现事实

---

## 三、本轮补强范围

| 对象 | 动作 | 重点补强 | 完成状态 |
|------|------|----------|----------|
| `examples/README.md` | 重写目录索引 | 增加 narrative case、闭环矩阵、真实口径说明、case6/case7 | ✅ 已完成 |
| `case1_regulatory_compliance/` | 重构叙事 + 增加版本对比 API | 从"单点热更新"提升到"规则版本→影响分析→版本对比→视图变化→回滚验证" | ✅ 已完成 |
| `case3_tax_simulation/` | 重构叙事 + 增加报告模板 | 从"税务仿真"提升到"策略沙盘"，强调场景参数包、报告模板和消费结果互证 | ✅ 已完成 |
| `case4_bi_query_agent/` | 新增 + 补齐结构化实现 | 重点补 Layer-R/S 协同、指标卡编辑、问数与视图联动、schema+instances+testcases | ✅ 已完成 |
| `case5_expert_knowledge_crystallization/` | 新增 + 规则组模型映射 | 重点补知识沉淀闭环、候选规则评审、规则组模型映射、发布后影响验证 | ✅ 已完成 |
| `case6_contradiction_detection/` | 预留大纲 | 多源矛盾检测场景预留 | ✅ 已完成 |
| `case7_knowledge_compilation/` | 预留大纲 | 文档→知识编译场景预留 | ✅ 已完成 |
| `docs/plans/` | 更新计划 | 同步本轮完成情况与下一步路径 | ✅ 已完成 |

---

## 四、案例级补强策略

### 4.1 Case 1：从"热更新演示"升级为"规则资产生命周期"

**本轮新增重点**：

- 让案例中出现一个明确的**规则资产编辑动作**：例如白名单例外条目发布新版本
- 增加 **impact analysis**：发布新版本后，哪几个供应商结果发生变化
- 增加 **版本对比 API**：`GET /v1/spaces/{space_id}/versions/diff?from=v1&to=v2`，展示资产变更 diff 和规则逻辑 diff
- 增加 **rollback**：通过版本回滚证明结果可逆、可审计
- 把互索引关系从 2 类补到 4 类：
  - `extracted_from`
  - `supported_by`
  - `defined_in`
  - `trace_to`
- 消费结果统一通过 `view.supply_chain_compliance_q2` 进行展示，再从视图回到规则版本和证据碎片

**关键用户问题**：
- "这次规则变更到底影响了哪些供应商？"
- "为什么 `SUP_C2` 这次从失败变成通过？"
- "如果回滚到上一个版本，结果会不会恢复？"
- "v2026.04.1 和 v2026.04.2 之间到底改了什么？"（版本对比 API）

### 4.2 Case 3：从"税务仿真"升级为"策略沙盘"

**本轮新增重点**：

- 把场景配置明确为一种**可编辑资产**：Scenario Pack / Assumption Card
- 把仿真报告模板明确为**固定资产对象**：`report_template.strategy_decision@v1`
- 增加一次参数编辑与重新运行，证明：
  - 改参数包
  - 对比视图变化
  - 报告与推荐结论同步变化
- 强化"策略消费结果"而不是只看单次仿真输出
- 补一个"推荐结论可解释"链路，回到参数版本、假设说明与指标权重

**关键用户问题**：
- "为什么场景 A 被推荐？"
- "如果把服务费率或总部编制改掉，推荐会变吗？"
- "报告中的结论，对应的是哪一版参数假设？"
- "报告模板是什么版本？章节内容引用了哪些视图和场景包？"

### 4.3 Case 4：新增 BI 智能问数 Agent（已完成结构化实现）

**本轮新增重点**：

- 以真实经营分析问法为入口，而不是纯技术检索示例
- 让用户看见以下资产：
  - 指标卡（Gross Margin / DSO / DIO）
  - 规则包（异常门店识别，v1 统一阈值 → v2 差异化阈值）
  - 问数视图（`view.ops_health_q2`）
  - 证据碎片（董事会月报、应收账龄、库存报表）
- 案例中至少出现一次**指标卡修订**或**规则阈值修订**
- 问答结果、异常门店列表、经营看板三者要能互相印证
- **新增 `schema.yaml`**：L1-L4 完整四层模型，含指标卡版本化与规则包版本化
- **新增 `instances.yaml`**：13 家门店、4 大区域、合成但真实的经营数据
- **新增 `testcases.yaml`**：10 条验收用例（TC-201 ~ TC-210）

**关键用户问题**：
- "华东大区 Q2 毛利率为什么低于预算？"
- "哪些门店毛利率高但回款慢？"
- "如果我修正毛利率口径，问答结果和看板会怎么变？"
- "加盟门店 NJ-007 为什么在 v2 规则下不再被标记为异常？"

**行业基准数据**：

| 区域 | 收入（亿元） | 毛利率 | DSO（天） | DIO（天） | 门店数 |
|------|-------------:|-------:|----------:|----------:|-------:|
| 华东 | 2.29 | 41.9% | 63 | 74 | 5 |
| 华南 | 1.32 | 40.8% | 51 | 61 | 3 |
| 华北 | 0.91 | 38.4% | 69 | 83 | 3 |
| 电商 | 0.61 | 49.0% | 18 | 37 | 2 |

### 4.4 Case 5：新增专家经验规则化（已增加规则组模型映射）

**本轮新增重点**：

- 明确区分 4 类资产：
  - 专家观察卡（personal note）
  - 候选规则卡（candidate rule）
  - 评审结论（review decision）
  - 已发布规则组（published rule group）
- 演示"个人知识 → 候选知识 → 组织规则"的升级链路
- 发布后，要能在风险名单视图中看到结果变化，并支持溯源到原始专家判断
- **新增规则组模型映射**：候选规则 → RuleDefinition + RuleLogic → 已发布规则组
- **新增知识资产呈现与编辑互证**：观察卡列表、候选规则卡、评审看板、已发布规则组、风险名单视图

**关键用户问题**：
- "这条规则为什么值得推广成组织规则？"
- "发布后影响了哪些客户/供应商？"
- "如果误报太多，能不能快速下线或回滚？"
- "候选规则如何映射到 RuleDefinition + RuleLogic？"

### 4.5 Case 6：多源矛盾检测（预留大纲）

- 场景：多系统供应商评级矛盾 / 多渠道收入数据矛盾
- 预期资产：矛盾检测规则、矛盾记录卡、裁决记录、裁决后视图
- 闭环：多源数据 → 矛盾检测 → 矛盾记录 → 裁决 → 统一视图 → 回溯
- 状态：预留大纲，待 Phase 2 矛盾检测能力落地

### 4.6 Case 7：文档→知识编译（预留大纲）

- 场景：监管政策编译 / 企业内部制度编译 / 行业标准编译
- 预期资产：文档碎片、编译草稿、审核记录、正式资产
- 闭环：文档导入 → 三通道提取 → 编译草稿 → 审核 → 正式资产 → 回溯
- 状态：预留大纲，待 Phase 2 三通道提取能力落地

---

## 五、真实场景口径与公开参考

### 5.1 BI 问数场景参考口径

| 指标 | 公开口径参考 | 用途 | 行业基准 |
|------|--------------|------|----------|
| 毛利率 | CFI Gross Margin Ratio | 经营盈利能力 | 百货零售 ~41%，超市 ~25%，电商 ~49% |
| DSO | CFI Days Sales Outstanding | 回款效率 | 零售行业 5-30 天，传统百货 50-80 天 |
| DIO | CFI Days Inventory Outstanding | 库存周转效率 | 零售行业 30-90 天 |

### 5.2 口径使用原则

- **保留公开定义，避免硬拷贝公开案例数据**
- **数值可合成，但结构必须真实**：例如按区域、门店、渠道、账龄、品类组织
- **必须给出口径说明**：防止用户只看到"答案"，看不到"定义与算法"
- **行业基准可查证**：引用中国百货商业协会、CreditPulse 等公开来源

---

## 六、本轮文档产物

### 6.1 已纳入本轮补强的 examples 文档

- `examples/README.md`（已更新闭环矩阵、case6/case7、hybrid 类型）
- `examples/case1_regulatory_compliance/scenario.md` + `journey.md`（已增加版本对比 API）
- `examples/case3_tax_simulation/scenario.md` + `journey.md`（已增加报告模板固定资产对象）
- `examples/case4_bi_query_agent/schema.yaml`（新增：L1-L4 完整四层模型）
- `examples/case4_bi_query_agent/instances.yaml`（新增：13 家门店真实数据）
- `examples/case4_bi_query_agent/testcases.yaml`（新增：10 条验收用例）
- `examples/case4_bi_query_agent/scenario.md` + `journey.md` + `README.md`（已更新）
- `examples/case5_expert_knowledge_crystallization/scenario.md`（已增加规则组模型映射）
- `examples/case6_contradiction_detection/scenario.md`（新增：预留大纲）
- `examples/case7_knowledge_compilation/scenario.md`（新增：预留大纲）

### 6.2 本轮已完成的实现层内容

- ✅ `case4` 的完整 schema / instances / testcases
- ✅ `case5` 的规则组模型映射（候选规则 → RuleDefinition + RuleLogic）
- ✅ `case1` 的版本对比 API 示例
- ✅ `case3` 的报告模板固定资产对象
- ✅ `case6` / `case7` 的预留大纲

### 6.3 仍待后续完成的内容

- `case5` 的完整 `schema.yaml / instances.yaml / testcases.yaml`
- `case6` / `case7` 的详细场景与旅程（待 Phase 2 能力落地）
- QueryEngine 的完整查询路由与 Bundle Search
- 所有 narrative case 的代码层落地验证（当前标注 **[待核对代码]**）

---

## 七、实施进度与下一步

### P0（已完成 ✅）

1. ✅ 给 `case4_bi_query_agent` 补 `schema.yaml` / `instances.yaml` / `testcases.yaml`
2. ✅ 用现有 `QueryService` + `views` 先做半自动版问数闭环（案例层面已设计）
3. ✅ 把 `gross_margin_rate`、`dso_days`、`dio_days` 做成第一批指标卡样板

### P1（已完成 ✅）

1. ✅ 把 `case5` 的候选规则与已发布规则映射到现有规则组模型
2. ✅ 给 `case1` 增加版本对比的真实 API 示例
3. ✅ 把 `case3` 的参数卡与仿真报告模板做成固定资产对象

### P2（已完成 ✅）

1. ✅ 为 `case6` 预留多源矛盾检测案例
2. ✅ 为 `case7` 预留文档→知识编译案例
3. ⬜ 把闭环矩阵同步回 `docs/ROADMAP.md` 或 `docs/TODO.md`（若优先级发生变化）

### P3（下一步建议）

1. 给 `case5_expert_knowledge_crystallization` 补 `schema.yaml / instances.yaml / testcases.yaml`
2. 用现有 `QueryService` + `views` 实现 case4 的半自动版问数闭环代码
3. 为 case6 / case7 补充详细旅程和可视化稿（待 Phase 2 能力落地）
4. 所有 narrative case 的代码层落地验证，移除 **[待核对代码]** 标记

---

## 八、结论

本轮补强的核心不是"新增更多案例"，而是把案例从 **功能截图** 提升成 **知识资产闭环演示**。只要用户能在 `examples/` 中直观看到 **资产是什么、怎么改、改完结果怎么变、为什么变**，OntologyEngine 相比纯 RAG / 纯规则引擎的差异化才真正可感知。

本轮已完成的重点成果：

1. **case4 从 narrative 升级为 hybrid**：补齐了 schema/instances/testcases，成为第一个同时具备结构化验收和叙事旅程的混合案例
2. **知识资产闭环从 4 个案例扩展到 6 个**：新增 case6/case7 预留大纲
3. **消费结果互证链路更完整**：每个案例都明确了"编辑→呈现→消费→回溯"的完整路径
4. **行业基准数据可查证**：引用了中国百货商业协会和 CreditPulse 的公开数据

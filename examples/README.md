# OntologyEngine 示例案例

> **status**: draft | **last_verified**: 2026-05-06

本目录包含三类案例：
- **canonical schema case**：以 `schema.yaml / instances.yaml / testcases.yaml` 为核心的结构化验收案例
- **narrative journey case**：以 `scenario / journey / visualization` 为核心的用户旅程案例
- **agent memory case**：以 `run_eval.py` 为核心的 Agent 记忆系统验证案例（位于 [`agent_memory/`](./agent_memory/)）

---

## 一、案例总览

### 1.1 Ontology Schema 案例

| 案例 | 类型 | 场景 | 本轮重点 |
|------|------|------|----------|
| [`supply_chain_finance/`](./supply_chain_finance/) | canonical | 供应链金融授信评估 | L3 图指标、规则声明/逻辑分离、多维指标 DAG |
| [`consumer_credit/`](./consumer_credit/) | canonical | 个人消费信贷风险评估 | Indicator、一票否决、产品分流、关系网络风险 |
| [`case1_regulatory_compliance/`](./case1_regulatory_compliance/) | narrative | 供应链金融准入规则热更新与追溯 | 规则版本、影响分析、版本对比 API、视图消费、回滚验证 |
| [`case3_tax_simulation/`](./case3_tax_simulation/) | narrative | 亚太区总部策略沙盘 | 场景参数包、仿真报告模板、推荐解释、报告消费 |
| [`case4_bi_query_agent/`](./case4_bi_query_agent/) | hybrid | BI 智能问数与经营看板联动 | Layer-R / Layer-S、指标卡编辑、问答与视图互证 |

### 1.2 Agent Memory 案例

所有 Agent 记忆系统验证案例已整合到 [`agent_memory/`](./agent_memory/) 目录：

| 目录 | 验证维度 | 轨迹数 | 原案例编号 |
|------|---------|:------:|-----------|
| [`01_ingestion_pipeline/`](./agent_memory/01_ingestion_pipeline/) | 摄取管线 | 8 | case5 |
| [`02_contradiction_belief/`](./agent_memory/02_contradiction_belief/) | 矛盾+信念修订 | 7 | case6 |
| [`03_consolidation_compilation/`](./agent_memory/03_consolidation_compilation/) | 巩固+编译 | 8 | case7 |
| [`04_locomo_eval/`](./agent_memory/04_locomo_eval/) | LOCOMO综合评估 | 10+6+6 | case8+9+10 |
| [`05_lifecycle_governance/`](./agent_memory/05_lifecycle_governance/) | 生命周期+治理 | 8+8 | case11+12 |
| [`06_full_agent_eval/`](./agent_memory/06_full_agent_eval/) | 全量评估+LLM | 8+8 | case13+14 |
| [`07_modeling_objects/`](./agent_memory/07_modeling_objects/) | 建模对象+权限 | 8 | case15 |
| [`08_qul_lifecycle/`](./agent_memory/08_qul_lifecycle/) | QUL+生命周期 | 8 | case16 |

详见 [`agent_memory/README.md`](./agent_memory/README.md)。

---

## 二、本轮统一设计原则

### 2.1 真实业务口径

新案例不再使用“玩具化问法”，而是优先采用真实企业经营分析与策略分析的口径组织内容。

本轮重点引入的公开通用指标定义包括：

- **毛利率（Gross Margin）**
- **DSO（应收账款周转天数）**
- **DIO（库存周转天数）**

> 指标定义参考公开财务教育资料；案例数值采用**合成但真实感足够**的业务数据，避免伪造具体上市公司事实。

### 2.2 知识资产闭环

每个 narrative case 都尽量覆盖以下对象：

- **资产编辑**：规则组、指标卡、场景参数包、候选规则卡
- **资产呈现**：依赖图、证据链、资产目录、版本 diff、仪表盘
- **结果消费**：视图、问答、报告、异常清单、推荐结论
- **相互印证**：结果可回溯到资产版本和证据来源；资产变更可反映到结果变化

---

## 三、知识资产闭环矩阵

| 案例 | 资产编辑 | 资产呈现 | 结果消费 | 互相印证方式 |
|------|----------|----------|----------|--------------|
| `case1_regulatory_compliance` | 发布白名单新版本、回滚旧版本 | 规则版本 diff、版本对比 API、证据链、合规仪表盘 | 合规视图、审计报告 | 规则版本变化直接改变通过率，版本对比 API 展示 diff，且可回溯到证据与定义来源 |
| `case3_tax_simulation` | 编辑场景参数包、发布假设版本 | 参数卡、仿真报告模板、对比矩阵、推荐解释链 | 场景比较视图、CFO 报告 | 参数版本变化导致推荐方案变化，报告由模板生成可追溯到模板版本 |
| `case4_bi_query_agent` | 修订指标卡 v1.4→v1.5、修订异常阈值 v1→v2 | 资产目录、问答证据链、经营看板、版本 diff | 问数回答、视图列表、异常门店清单 | 指标口径变更后问答答案与看板数值同步变化；规则阈值变更后异常门店清单与问答一致 |
| `case5_expert_knowledge_crystallization` | 专家标注、候选规则评审、发布组织规则 | 评审看板、候选规则卡、规则组模型映射、版本谱系 | 风险名单视图、规则解释 | 发布后新增命中实体可追溯到原始专家经验；规则组映射到 RuleDefinition+RuleLogic |
| `case6_contradiction_detection` | 矛盾裁决 | 矛盾记录卡、裁决看板 | 裁决后统一视图 | 裁决结果可追溯到矛盾来源与裁决理由（预留） |
| `case7_knowledge_compilation` | 编译草稿审核修正 | 编译草稿、审核记录 | 正式知识资产 | 编译结果可溯源到原始文档段落（预留） |

---

## 四、如何阅读这些案例

### 4.1 如果你想看结构化 Schema 能力

优先阅读：

- `supply_chain_finance/`
- `consumer_credit/`

这两组案例更适合验证：

- L1-L4 四层表达
- 图指标
- 规则声明 / 逻辑分离
- What-if 与图遍历

### 4.2 如果你想看用户体验与产品化演示

优先阅读：

- `case1_regulatory_compliance/`
- `case3_tax_simulation/`
- `case4_bi_query_agent/`
- `case5_expert_knowledge_crystallization/`

这几组案例更适合验证：

- 规则热更新的用户旅程
- 策略沙盘的消费结果
- 问答 + 视图 + 证据链的联动
- 知识沉淀闭环

---

## 五、目录约定

### 5.1 canonical case

```text
{case}/
  schema.yaml
  instances.yaml
  testcases.yaml
  README.md / SCHEMA_DESIGN.md
```

### 5.2 narrative journey case

```text
{case}/
  scenario.md
  journey.md
  visualization/
    *.md
  expected_outputs/        # 如已有
  api_examples/            # 如已有
```

> 若 narrative case 依赖的 schema / API 尚未完整落地，文档中必须显式标注 **[待核对代码]**。

---

## 六、建议阅读顺序

1. 先读本文件，理解不同案例的角色分工
2. 再读 `case4_bi_query_agent/`，理解“为什么不只是 RAG”
3. 读 `case1_regulatory_compliance/`，理解“规则资产如何影响消费结果”
4. 读 `case3_tax_simulation/`，理解“参数包如何驱动策略沙盘”
5. 读 `case5_expert_knowledge_crystallization/`，理解“个人经验如何沉淀为组织规则”

---

## 七、关联文档

| 主题 | 参考文档 |
|------|---------|
| 竞争分析与案例优先级 | `docs/plans/use-case-plan-competitive-analysis.md` |
| 本轮 examples 落地计划 | `docs/plans/2026-04-25-examples-case-optimization.md` |
| API / views 设计 | `docs/02-design/api/README.md` |
| 规则管理 UI 设计 | `docs-ui/03-rule-management-ui-design.md` |
| Query Engine 设计 | `docs/02-design/query-engine/README.md` |

---

## 八、当前空缺与后续演进

以下主题仍需继续补强：

- `case5_expert_knowledge_crystallization` 的完整 `schema.yaml / instances.yaml / testcases.yaml`
- `case6_contradiction_detection` 的详细场景与旅程（待 Phase 2 矛盾检测能力落地）
- `case7_knowledge_compilation` 的详细场景与旅程（待 Phase 2 三通道提取能力落地）
- 所有 narrative case 的代码层落地验证（当前标注 **[待核对代码]**）
# Case 4 用户旅程 — 指标卡、问数与经营看板闭环

> **文件角色**: narrative journey **[待核对代码]**
> **结构化验收**: 对应 `testcases.yaml` 中 TC-201 ~ TC-210

---

## 旅程概览

本案例通过 8 个步骤展示：

1. 如何把经营文档和经营底表组织成知识资产
2. 如何创建指标卡、规则包和经营视图
3. 如何用自然语言进行问数
4. 如何通过编辑资产改变问答与看板结果
5. 如何把消费结果回溯到资产版本与原始证据

**预计演示时间**: 15-20 分钟

---

## Step 1：注册经营数据集与文档碎片

### 操作

```bash
ontology-cli schema load \
  --space space.ops_bi_q2 \
  --file schema.yaml

ontology-cli entities batch-import \
  --space space.ops_bi_q2 \
  --file instances.yaml
```

### 资产结果

- 13 家门店（华东 5 / 华南 3 / 华北 3 / 电商 2）
- 13 条月度销售记录
- 13 条应收账龄记录
- 10 条库存快照记录
- 文档碎片：`board_pack_q2_2026.pdf`、`metric_dictionary_v1.4.md`

### 验证点

- [ ] 门店与经营数据已就绪（对应 TC-207 区域级汇总）
- [ ] 文档碎片可被 Layer-R 检索
- [ ] 结构化底表可被视图和指标卡引用

---

## Step 2：创建 3 张核心指标卡

### 操作

- 创建 `metric.gross_margin_rate@v1.4`（初始版本，以 gross_sales 为分母）
- 创建 `metric.dso_days@v1.0`
- 创建 `metric.dio_days@v1.0`

### 指标卡样例（gross_margin_rate v1.4）

```json
{
  "metric_id": "gross_margin_rate",
  "version": "v1.4",
  "display_name": "毛利率",
  "formula": "(gross_sales - cogs) / gross_sales",
  "unit": "%",
  "source_fragments": [
    "frag.metric_dictionary.gross_margin",
    "frag.board_pack.q2.margin_note"
  ],
  "thresholds": { "warning": 30.0, "critical": 20.0 }
}
```

### 指标卡样例（dso_days v1.0）

```json
{
  "metric_id": "dso_days",
  "version": "v1.0",
  "display_name": "应收账款周转天数（DSO）",
  "formula": "total_receivable / net_credit_sales * 90",
  "unit": "天",
  "source_fragments": [
    "frag.metric_dictionary.dso",
    "frag.ar_aging_note"
  ],
  "thresholds": { "warning": 60, "critical": 90 }
}
```

### 验证点

- [ ] 指标卡包含公式、解释、来源碎片（对应 TC-201 / TC-202 / TC-203）
- [ ] 指标卡可在问数与视图执行中被统一调用
- [ ] 指标卡版本号可被后续编辑动作引用

---

## Step 3：创建经营异常规则包与视图

### 操作

**规则包**：`ops_exception_rules@v1`

```yaml
name: ops_exception_rules
version: v1
rules:
  - id: high_margin_slow_cash
    when: gross_margin_rate > 0.45 AND dso_days > 60
    output: flag_exception = true
```

**视图**：`view.ops_health_q2`

```json
{
  "view_id": "view.ops_health_q2",
  "dimensions": ["region", "store_type", "category"],
  "metrics": ["gross_margin_rate", "dso_days", "dio_days"],
  "rules": ["ops_exception_rules"]
}
```

### 验证点

- [ ] 视图能返回区域/门店级经营结果
- [ ] 异常门店规则能被同一视图消费

---

## Step 4：自然语言问数

### 样例问题 1

> “华东大区 Q2 毛利率为什么低于预算？”

### 期望输出

```json
{
  "question": "华东大区 Q2 毛利率为什么低于预算？",
  "answer": {
    "short_conclusion": "华东 Q2 毛利率为 41.9%，较预算低 2.6 个点，主要受折扣加深和退货冲减影响。",
    "evidence": [
      "board_pack_q2_2026.pdf#p12",
      "metric.gross_margin_rate@v1.4",
      "view.ops_health_q2.region.east"
    ]
  },
  "query_route": "hybrid_explainable"
}
```

### 样例问题 2

> “哪些直营网点毛利率高于 45%，但 DSO 超过 60 天？”

### 期望输出

- 返回门店列表
- 返回命中的规则：`high_margin_slow_cash`
- 返回排序依据：毛利率高、DSO 高、账龄集中度高

### 验证点

- [ ] Layer-R 返回定义类碎片
- [ ] Layer-S 返回结构化筛选结果
- [ ] 问答结论与 `view.ops_health_q2` 一致

---

## Step 5：修正毛利率指标卡口径

### 背景

财务 BP 发现 `gross_margin_rate@v1.4` 仍以 `gross_sales` 为分母，未扣除退货与折让。经营例会要求统一改为 `net_revenue`。

### 操作

在资产编辑界面发布新版本：

```json
{
  "metric_id": "gross_margin_rate",
  "from_version": "v1.4",
  "to_version": "v1.5",
  "formula": "(net_revenue - cogs) / net_revenue",
  "change_reason": "统一经营月报与财务口径，扣除退货和折让"
}
```

### 预期变化

| 对象 | v1.4 | v1.5 | 变化说明 |
|------|------|------|----------|
| SH-001 毛利率 | ~45.0% | ~41.5% | 扣除退货折让后下降 |
| 华东区域毛利率 | ~42.5% | ~41.9% | 区域汇总同步变化 |
| 问题 1 的结论 | "低于预算 2.0 个点" | "低于预算 2.6 个点" | 口径收紧后偏差加大 |
| 报告说明 | 未解释退货影响 | 明确指出退货冲减 | 解释更准确 |

### 验证点

- [ ] 指标卡版本变化会影响问答和视图（对应 TC-206）
- [ ] 用户可看到从 `v1.4` 到 `v1.5` 的 diff
- [ ] 结果中可回溯到 `defined_in: metric.gross_margin_rate@v1.5`
- [ ] 问答结论、视图数据、报告说明三者同步变化且一致

---

## Step 6：修订异常规则阈值

### 背景

经营团队认为直营网点和加盟门店的回款节奏不同，DSO 统一用 60 天阈值会产生误报。

### 操作

发布 `ops_exception_rules@v2`：

```yaml
name: ops_exception_rules
version: v2
rules:
  - id: high_margin_slow_cash
    when: |
      (store_type == 'DIRECT' AND gross_margin_rate > 0.45 AND dso_days > 60)
      OR
      (store_type == 'FRANCHISE' AND gross_margin_rate > 0.45 AND dso_days > 75)
```

### 预期变化

| 门店 | 类型 | DSO | v1 异常 | v2 异常 | 变化原因 |
|------|------|-----|:-------:|:-------:|----------|
| SH-014 | 直营 | 82 | ✓ | ✓ | 直营阈值仍为 60 |
| NJ-007 | 加盟 | 68 | ✓ | ✗ | 加盟阈值调整为 75 |
| NB-012 | 加盟 | 65 | ✓ | ✗ | 加盟阈值调整为 75 |
| BJ-009 | 直营 | 72 | ✗ | ✗ | 毛利率35%未达25%阈值，不触发综合风险 |

**汇总**：v1 有 3 家异常门店，v2 减少到 1 家，加盟门店误报减少 2 家。

### 验证点

- [ ] 规则资产变化反映到异常清单（对应 TC-204 / TC-205 / TC-209）
- [ ] 问答"哪些门店命中异常"与看板一致
- [ ] 影响分析能列出新增/移除的门店
- [ ] 移出的门店可追溯到规则版本变更原因

---

## Step 7：查看证据链与资产版本

### 操作

```bash
GET /v1/views/view.ops_health_q2/execution/store_hz_014
```

### 期望看到的 4 类关联

- `extracted_from`: 门店经营底表、账龄表
- `supported_by`: 月报说明片段、退货说明、账龄备注
- `defined_in`: 指标卡版本、规则包版本
- `trace_to`: 问答回答节点、异常门店清单、经营报告章节

### 验证点

- [ ] 用户能证明"这条结果用了哪版公式和规则"（对应 TC-208）
- [ ] 用户能打开原始文档碎片做人工复核
- [ ] 四类互索引关系完整覆盖

---

## Step 8：生成经营复盘报告

### 操作

```bash
ontology-cli report generate \
  --space space.ops_bi_q2 \
  --view view.ops_health_q2 \
  --type monthly_ops_review \
  --format pdf
```

### 期望输出章节

- 区域经营摘要
- 异常门店清单
- 关键指标口径说明
- 版本变更说明（v1.4 → v1.5 / v1 → v2）
- 证据索引

### 最终验收

- [ ] 报告中的数字与问答结果一致
- [ ] 报告中的异常门店与视图一致
- [ ] 报告能回溯到指标卡和规则包版本

---

## 结论

当用户能够看到 **口径修订前后的问答答案、视图数据和报告结论同步变化**，并且还能回到原始指标卡与证据碎片，这个案例才真正完成了从“问数”到“可解释知识消费”的闭环。

### 闭环验收清单

| 验收项 | 对应测试用例 | 状态 |
|--------|-------------|------|
| 毛利率 v1.5 口径计算正确 | TC-201 | [ ] |
| DSO 指标计算正确 | TC-202 | [ ] |
| DIO 指标计算正确 | TC-203 | [ ] |
| 异常门店 v1 统一阈值识别 | TC-204 | [ ] |
| 异常门店 v2 差异化阈值识别 | TC-205 | [ ] |
| 毛利率口径修订影响验证 | TC-206 | [ ] |
| 区域级经营快照汇总 | TC-207 | [ ] |
| 证据链四类互索引完整性 | TC-208 | [ ] |
| 规则版本变化对异常清单的影响 | TC-209 | [ ] |
| 电商渠道经营健康度 | TC-210 | [ ] |
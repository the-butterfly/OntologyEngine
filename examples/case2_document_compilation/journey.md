# Case 2 用户旅程 — 原始文档知识编译闭环

> **文件角色**: narrative journey
> **对应愿景旅程**: J1

---

## 旅程概览

本案例通过 8 个步骤展示：

1. 上传 4 份异构文档到 Dataset
2. 触发 ingest 编译管线
3. 验证编译产物（Wiki 页面 + 图谱节点）
4. 检查矛盾检测报告
5. 更新一份文档（增量处理）
6. 验证 SHA256 缓存生效（仅变化文件重处理）
7. 消费编译后的知识（查询 + 规则执行）
8. 验证溯源链路完整性

**预计演示时间**: 15-20 分钟

---

## Step 1：上传原始文档

### 操作

```bash
ontology-cli dataset create --space space.green_finance_2026
ontology-cli dataset upload --space space.green_finance_2026 \
  --files docs/green_finance_guideline.pdf \
          docs/supply_chain_ops_manual.md \
          docs/q1_business_report.md \
          docs/risk_committee_minutes.md
```

### 上传文档清单

| 文档 | 类型 | 大小 | 核心实体预期 |
|------|------|------|-------------|
| `green_finance_guideline.pdf` | PDF | ~2.3MB | GreenEnterprise, GreenLoan, RiskWeight |
| `supply_chain_ops_manual.md` | Markdown | ~8KB | Supplier, GuaranteeRule, ApprovalRule |
| `q1_business_report.md` | Markdown | ~5KB | Store, MetricValue, Region |
| `risk_committee_minutes.md` | Markdown | ~3KB | RiskConstraint, ExpertOpinion |

### 验证点

- [ ] 4 份文档全部上传成功
- [ ] 每份文档生成 SHA256 哈希（用于增量比对）

---

## Step 2：触发 Ingest 编译管线

### 操作

```bash
ontology-cli ingest run --space space.green_finance_2026 --all
```

### 系统响应

```
Ingest Pipeline:
  Pass 1: 确定性提取
    ✓ green_finance_guideline.pdf → 23 个表格/列表候选
    ✓ supply_chain_ops_manual.md → 15 个流程/规则候选
    ✓ q1_business_report.md → 13 个指标数据点
    ✓ risk_committee_minutes.md → 8 个判断/约束候选

  Pass 2: LLM 语义提取
    ✓ 概念/关系提取完成（4 文档，~120 个实体，~85 条关系）
    ✓ Confidence 标签：EXTRACTED(92), INFERRED(28), AMBIGUOUS(5)

  矛盾检测:
    ⚠ 发现 2 处矛盾（见 Step 4）

  Wiki 页面生成:
    ✓ 生成 47 个实体页面 + 12 个概念页面 + 1 个 Living Overview
```

### 验证点

- [ ] Pass 1 提取候选数合理
- [ ] Pass 2 LLM 提取完成，Confidence 标签分布正常
- [ ] 矛盾检测报告生成
- [ ] Wiki 页面数量合理

---

## Step 3：验证编译产物

### 操作

```bash
# 查询编译后的实体
ontology-cli query entities --space space.green_finance_2026 --type GreenEnterprise

# 查看 Wiki 页面
ontology-cli wiki show --space space.green_finance_2026 --page "GreenEnterprise"

# 查看 Living Overview
ontology-cli wiki show --space space.green_finance_2026 --page "overview"
```

### 期望输出

**GreenEnterprise 实体页面**：

```markdown
# GreenEnterprise（绿色企业）

## 定义
符合《绿色融资指引》第 3 条规定的企业。

## 属性
| 属性 | 类型 | 说明 |
|------|------|------|
| industry_category | enum | 制造业/服务业/农业 |
| carbon_intensity | float | 单位营收碳排放（吨/万元） |
| green_revenue_ratio | float | 绿色业务收入占比 |

## 提取来源
- `extracted_from`: green_finance_guideline.pdf §3.1（第 5 页）
- `supported_by`: "绿色企业是指..."（原文引用）

## 相关关系
- `has_standard` → GreenLoanStandard
- `subject_to` → RiskWeightRule
```

### 验证点

- [ ] 实体页面包含定义、属性、提取来源
- [ ] 四类互索引关系完整（extracted_from / supported_by / defined_in / trace_to）
- [ ] Living Overview 反映最新知识状态

---

## Step 4：检查矛盾检测报告

### 操作

```bash
ontology-cli contradictions list --space space.green_finance_2026
```

### 期望输出

```json
{
  "contradictions": [
    {
      "id": "CTR-001",
      "topic": "绿色企业认定标准",
      "severity": "high",
      "side_a": {
        "source": "green_finance_guideline.pdf §3.1",
        "claim": "carbon_intensity < 0.5 吨/万元"
      },
      "side_b": {
        "source": "risk_committee_minutes.md §2",
        "claim": "carbon_intensity < 0.3 吨/万元（风控委员会建议收紧）"
      },
      "status": "pending_review",
      "suggested_action": "提交领域专家评审"
    },
    {
      "id": "CTR-002",
      "topic": "毛利率计算口径",
      "severity": "medium",
      "side_a": {
        "source": "q1_business_report.md §4",
        "claim": "毛利率 = (gross_sales - cogs) / gross_sales"
      },
      "side_b": {
        "source": "supply_chain_ops_manual.md §7.2",
        "claim": "毛利率 = (net_revenue - cogs) / net_revenue"
      },
      "status": "pending_review",
      "suggested_action": "确认财务统一口径"
    }
  ]
}
```

### 验证点

- [ ] 矛盾在 ingest 时即被发现（非查询时）
- [ ] 每个矛盾标注冲突双方的原文来源
- [ ] 矛盾状态为 `pending_review`（等待人工确认）

---

## Step 5：更新文档（增量处理）

### 操作

```bash
# 替换操作手册为 v3.3（新增一条审批规则）
ontology-cli dataset upload --space space.green_finance_2026 \
  --file docs/supply_chain_ops_manual_v3.3.md \
  --replace supply_chain_ops_manual.md

# 重新触发 ingest
ontology-cli ingest run --space space.green_finance_2026 --all
```

### 系统响应

```
SHA256 缓存比对:
  ✓ green_finance_guideline.pdf → 未变化（跳过）
  ✓ q1_business_report.md → 未变化（跳过）
  ✓ risk_committee_minutes.md → 未变化（跳过）
  ⚡ supply_chain_ops_manual.md → 已变化（重新处理）

增量处理:
  Pass 1: 1 个新增规则候选（审批规则 AR-005）
  Pass 2: 3 个新实体 + 2 条新关系
  矛盾检测: 无新矛盾
  Wiki 更新: 新增 3 个页面，更新 1 个页面
```

### 验证点

- [ ] 3 份未变化文档被跳过（SHA256 匹配）
- [ ] 仅变化文档被重新处理
- [ ] 新增实体正确写入

---

## Step 6：验证增量处理正确性

### 操作

```bash
# 验证未变化文档的实体未受影响
ontology-cli query entities --space space.green_finance_2026 \
  --source green_finance_guideline.pdf --count

# 验证新增实体存在
ontology-cli query entities --space space.green_finance_2026 \
  --name "ApprovalRule.AR-005"
```

### 期望输出

```
未变化文档实体数: 23（与 Step 2 一致）✓
新增实体 AR-005: 存在 ✓
AR-005 extracted_from: supply_chain_ops_manual_v3.3.md §8.1 ✓
```

### 验证点

- [ ] 未变化文档的实体数量和属性不变
- [ ] 新增实体正确关联到新版本文档
- [ ] 旧版本文档的实体保留（版本历史可追溯）

---

## Step 7：消费编译后的知识

### 操作

```bash
# 查询：绿色信贷准入条件
ontology-cli query ask --space space.green_finance_2026 \
  "绿色信贷的准入条件是什么？"

# 规则执行：供应商是否符合绿色融资标准
ontology-cli analyze --space space.green_finance_2026 \
  --entity SUP_001 --dimension green_finance_compliance
```

### 期望输出

**查询结果**：

```json
{
  "answer": "绿色信贷准入条件：\n1. 企业 carbon_intensity < 0.5 吨/万元\n2. green_revenue_ratio > 30%\n3. 无重大环保处罚记录",
  "evidence": [
    {"source": "green_finance_guideline.pdf §3.1", "confidence": 1.0},
    {"source": "risk_committee_minutes.md §2", "confidence": 0.6, "note": "存在矛盾，待评审"}
  ],
  "contradiction_warning": "CTR-001：绿色企业认定标准存在矛盾"
}
```

### 验证点

- [ ] 查询结果来自编译后的结构化知识，非原文检索
- [ ] 证据链包含原文溯源
- [ ] 矛盾标记出现在查询结果中

---

## Step 8：验证溯源链路完整性

### 操作

```bash
# 查看某条规则的完整溯源
ontology-cli trace --space space.green_finance_2026 \
  --entity "RiskWeightRule.RWR-001" --full-chain
```

### 期望链路

```
RiskWeightRule.RWR-001
  ├─ extracted_from: green_finance_guideline.pdf §5.2（第 8 页，偏移 3200）
  ├─ supported_by: "绿色信贷风险权重为 50%..."（原文引用）
  ├─ defined_in: GreenFinanceSchema@v1.0
  ├─ relates_to: GreenEnterprise（适用对象）
  └─ trace_to:
      ├─ query "绿色信贷准入条件"（被查询消费）
      └─ analyze SUP_001 green_finance_compliance（被规则执行消费）
```

### 验证点

- [ ] 四类互索引关系全部存在
- [ ] 原文溯源包含页码和偏移量
- [ ] 消费链路可追溯到具体查询/分析操作

---

## 结论

这个案例最终要证明的不是"文档能被索引"，而是：

- **多源异构文档 → 统一结构化知识表示**
- **Knowledge 编译一次，增量处理变化文件**
- **矛盾在 ingest 时即被发现，而非查询时**
- **每个结论都能回溯到原始文档的具体段落**
- **编译后的知识可被查询、规则执行、多 Agent 消费**

这比单纯演示"RAG 检索"或"知识图谱查询"更接近 OntologyEngine 的核心价值。

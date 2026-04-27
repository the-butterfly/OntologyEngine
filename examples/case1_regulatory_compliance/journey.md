# Case 1 用户旅程 — 规则版本发布、影响分析与回滚验证

> **文件角色**: narrative journey **[待核对代码]**

---

## 旅程概览

本案例通过 9 个步骤展示：

1. 导入规则与证据资产
2. 创建合规消费视图
3. 查看基线结果
4. 编辑白名单资产并发布新版本
5. 执行影响分析
6. 在视图中验证结果变化
7. 查看单实体完整证据链
8. 回滚旧版本验证结果恢复
9. 输出审计报告

**预计演示时间**: 12-15 分钟

---

## Step 1：加载规则包、实体与证据碎片

### 操作

```bash
ontology-cli schema load \
  --space space.supply_chain_finance \
  --file schema.yaml

ontology-cli entities batch-import \
  --space space.supply_chain_finance \
  --file instances.yaml
```

### 当前资产

- `Circular23_rule_pack@v2026.04.1`
- `core_enterprise_whitelist@v2026.04`
- `frag.whitelist.memo.001`
- `frag.invoice.ocr.sup_c3`
- `frag.guarantee.contract.sup_c4`

### 验证点

- [ ] 供应商与证据资产已就绪
- [ ] 规则包与白名单资产可被后续版本化

---

## Step 2：创建合规消费视图

### 操作

```json
POST /v1/views
{
  "view_id": "view.supply_chain_compliance_q2",
  "space_id": "space.supply_chain_finance",
  "dimensions": ["compliance_status", "core_enterprise", "risk_level"],
  "metrics": ["compliance_score", "guarantee_ratio", "invoice_auth_pass_rate"],
  "rules": ["Circular23_rule_pack"]
}
```

### 目标

把原本零散的规则执行结果统一收敛到一个消费入口，用于：

- 通过率看板
- 失败对象列表
- 审计报告引用

---

## Step 3：查看基线结果（版本 v2026.04.1）

### 操作

```json
POST /v1/views/view.supply_chain_compliance_q2/execute/analyze
{
  "entity_ids": ["SUP_C1", "SUP_C2", "SUP_C3", "SUP_C4", "SUP_C5"],
  "include_trace": true
}
```

### 期望输出摘要

```json
{
  "version": "Circular23_rule_pack@v2026.04.1",
  "summary": {
    "total": 5,
    "passed": 1,
    "failed": 4,
    "pass_rate": "20%"
  },
  "failed_entities": ["SUP_C2", "SUP_C3", "SUP_C4", "SUP_C5"]
}
```

### 关注点

- `SUP_C2` 当前失败原因为：核心企业未命中例外白名单
- 这为后续版本变更提供可验证的对照组

---

## Step 4：编辑白名单资产并发布新版本

### 操作

规则运营在 UI 中打开：

`/spaces/space.supply_chain_finance/rules/compliance_circular23`

在右侧资产面板中补充：

- 新增例外核心企业：`CE_RETAIL_PILOT_001`
- 关联审批备忘录：`frag.whitelist.memo.001`
- 发布新版本：`Circular23_rule_pack@v2026.04.2`

### 期望输出

```json
{
  "published_version": "Circular23_rule_pack@v2026.04.2",
  "changed_assets": [
    "core_enterprise_whitelist@v2026.04.1",
    "frag.whitelist.memo.001"
  ],
  "change_reason": "补充合作资方确认的试点核心企业白名单"
}
```

---

## Step 5：执行影响分析

### 操作

```json
GET /v1/views/view.supply_chain_compliance_q2/rules/dependency-graph?diff_from=v2026.04.1&diff_to=v2026.04.2
```

### 版本对比 API 示例

```json
GET /v1/spaces/space.supply_chain_finance/versions/diff?from=v2026.04.1&to=v2026.04.2
```

#### 期望输出

```json
{
  "from_version": "Circular23_rule_pack@v2026.04.1",
  "to_version": "Circular23_rule_pack@v2026.04.2",
  "asset_changes": [
    {
      "asset_id": "core_enterprise_whitelist",
      "change_type": "ITEM_ADDED",
      "detail": "新增核心企业 CE_RETAIL_PILOT_001",
      "evidence": "frag.whitelist.memo.001"
    }
  ],
  "rule_logic_diff": [
    {
      "logic_id": "RL_circular23_whitelist_check",
      "field": "whitelist_entries",
      "before": ["CE_HW", "CE_BYD", "CE_ALI"],
      "after": ["CE_HW", "CE_BYD", "CE_ALI", "CE_RETAIL_PILOT_001"]
    }
  ],
  "affected_entities": [
    {
      "entity_id": "SUP_C2",
      "before": "FAILED",
      "after": "PASSED",
      "reason": "核心企业白名单命中"
    }
  ],
  "unaffected_entities": ["SUP_C1", "SUP_C3", "SUP_C4", "SUP_C5"]
}
```

### 期望输出摘要

```json
{
  "changed_rule_pack": "Circular23_rule_pack@v2026.04.2",
  "affected_entities": [
    {
      "entity_id": "SUP_C2",
      "before": "FAILED",
      "after": "PASSED",
      "reason": "核心企业白名单命中"
    }
  ],
  "unaffected_entities": ["SUP_C1", "SUP_C3", "SUP_C4", "SUP_C5"]
}
```

### 验证点

- [ ] 能明确列出受影响对象
- [ ] 能说明为什么只有 `SUP_C2` 变化
- [ ] 版本对比 API 能展示资产变更 diff 和规则逻辑 diff

---

## Step 6：在视图中验证结果变化

### 操作

```json
POST /v1/views/view.supply_chain_compliance_q2/execute/analyze
{
  "entity_ids": ["SUP_C1", "SUP_C2", "SUP_C3", "SUP_C4", "SUP_C5"],
  "include_trace": true,
  "version": "Circular23_rule_pack@v2026.04.2"
}
```

### 期望输出摘要

```json
{
  "version": "Circular23_rule_pack@v2026.04.2",
  "summary": {
    "total": 5,
    "passed": 2,
    "failed": 3,
    "pass_rate": "40%"
  },
  "newly_passed_entities": ["SUP_C2"]
}
```

### 验证点

- [ ] 视图通过率从 20% 提升为 40%
- [ ] 视图中的新增通过实体与影响分析一致

---

## Step 7：查看 `SUP_C2` 的完整证据链

### 操作

```json
GET /v1/views/view.supply_chain_compliance_q2/execution/SUP_C2
```

### 期望看到的链路

- `extracted_from`: `Supplier.supplies_to → CoreEnterprise`
- `supported_by`: `frag.whitelist.memo.001`
- `defined_in`: `Circular23_rule_pack@v2026.04.2`
- `trace_to`: `view.supply_chain_compliance_q2` 与 `report.compliance_q2`

### 验证点

- [ ] 用户能证明 `SUP_C2` 变化不是人工改结果，而是资产变更生效
- [ ] 用户能打开审批备忘录做人工复核

---

## Step 8：回滚到旧版本并验证结果恢复

### 操作

```json
POST /v1/spaces/space.supply_chain_finance/versions/v2026.04.1/rollback
```

随后重新执行同一视图。

### 期望输出摘要

```json
{
  "active_version": "Circular23_rule_pack@v2026.04.1",
  "summary": {
    "total": 5,
    "passed": 1,
    "failed": 4,
    "pass_rate": "20%"
  },
  "rolled_back_entities": ["SUP_C2"]
}
```

### 验证点

- [ ] `SUP_C2` 从 PASSED 恢复为 FAILED
- [ ] 用户能证明结果恢复与版本回滚一致

---

## Step 9：生成审计报告

### 操作

```bash
ontology-cli report generate \
  --space space.supply_chain_finance \
  --view view.supply_chain_compliance_q2 \
  --type compliance_audit \
  --format pdf
```

### 报告中必须包含

- 规则包版本摘要
- 版本变更记录
- 受影响实体清单
- 单实体可解释证据索引
- 回滚验证记录

---

## 结论

这个案例最终要证明的不是“规则可以改”，而是：

- **规则改动会反映到视图与报告**
- **结果变化可以被影响分析和证据链解释**
- **回滚能让结果恢复，从而反向证明系统可信**
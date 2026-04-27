# Case 1 可视化稿 — 合规规则资产与结果联动面板

> **文件角色**: 视觉化叙事草图 **[待核对代码]**

---

## 一、规则版本与合规视图联动

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                    Supply Chain Compliance / view.supply_chain_compliance_q2            │
├──────────────────────────────┬────────────────────────────────────┬──────────────────────┤
│ 左侧：规则资产                │ 中间：合规结果视图                 │ 右侧：证据与回滚       │
│                              │                                    │                      │
│ Circular23_rule_pack         │ v2026.04.1                         │ Trace: SUP_C2        │
│ • v2026.04.1                 │ 通过 1 / 失败 4 / 通过率 20%        │ • extracted_from     │
│ • v2026.04.2                 │                                    │ • supported_by       │
│                              │ v2026.04.2                         │ • defined_in         │
│ 白名单资产                    │ 通过 2 / 失败 3 / 通过率 40%        │ • trace_to           │
│ • whitelist@v2026.04.1       │                                    │                      │
│ • whitelist@v2026.04.2       │ 变化对象                            │ Rollback             │
│                              │ • SUP_C2  FAILED → PASSED          │ • active: v2026.04.1│
│ 变更原因                      │ • SUP_C3  no change                │ • restored pass rate│
│ • 新增 CE_RETAIL_PILOT_001   │ • SUP_C4  no change                │   20%               │
│ • 关联 memo.001              │ • SUP_C5  no change                │                      │
└──────────────────────────────┴────────────────────────────────────┴──────────────────────┘
```

---

## 二、版本 diff 面板

| 资产 | v2026.04.1 | v2026.04.2 | 影响 |
|------|------------|------------|------|
| 白名单 | 不含 `CE_RETAIL_PILOT_001` | 新增 `CE_RETAIL_PILOT_001` | `SUP_C2` 命中白名单 |
| 证据碎片 | 无审批备忘录绑定 | 绑定 `frag.whitelist.memo.001` | 可补充人工审核依据 |
| 合规结果 | `SUP_C2 = FAILED` | `SUP_C2 = PASSED` | 通过率 +20 个点 |

---

## 三、`SUP_C2` 证据链可视化

```text
Supplier: SUP_C2
  │
  ├─ extracted_from ──> CoreEnterprise relation / supplier master
  │
  ├─ supported_by ───> frag.whitelist.memo.001
  │                     “试点合作企业可纳入临时白名单”
  │
  ├─ defined_in ─────> Circular23_rule_pack@v2026.04.2
  │
  └─ trace_to ───────> view.supply_chain_compliance_q2
                        └─ report.compliance_q2.section.failed_entities
```

---

## 四、这个页面要让用户看到什么

1. **资产改了，结果真的会变**
2. **结果变了，能说清楚是哪个资产导致的**
3. **回滚之后，结果恢复，可反向证明系统可信**

只要这个页面能够同时展示 **版本 diff、影响对象、证据链、回滚结果**，`case1` 就不再只是一个“热更新 demo”，而是一套完整的规则资产演示。
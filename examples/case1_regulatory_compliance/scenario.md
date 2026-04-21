# Case 1: Supply Chain Finance Risk Control — Rule Hot-Update + Decision Traceability

## Scenario Overview

### Target User
**Risk Control Manager** at a supply chain finance platform

### Business Context
The People's Bank of China has issued **Circular 23** (《供应链金融票据业务监管办法》) requiring:
1. Core enterprises must be on a regulatory whitelist
2. All invoices must pass authenticity verification
3. Single guarantee amounts cannot exceed 10% of guarantor registered capital
4. Supplier risk concentration with single core enterprise must not exceed 50%

**Deadline**: Complete compliance transformation within **48 hours** + prepare for quarterly audit

### Key Differentiator
| Traditional Approach | OntologyEngine Approach |
|---------------------|------------------------|
| Rule changes require 2-4 weeks (IT deployment) | Rule takes effect in **seconds** via YAML hot-update |
| Decision audit requires manual documentation | Automatic evidence chain with `extracted_from` / `trace_to` edges |
| Compliance verification is periodic batch job | Real-time continuous compliance monitoring |

---

## Scenario Narrative

### Day 0: Circular 23 Issued (April 18, 2026)
Risk Control Manager receives notification that Circular 23 will take effect in 48 hours. Traditional systems would require:
- Rule specification documents
- IT development tickets
- Testing cycles
- Deployment windows

With OntologyEngine, the manager can:
1. Load the new `RD_circular23_compliance.yaml` rule via API
2. Immediately test against existing supplier base
3. Query decision traces to verify all evidence links
4. Generate audit report with full traceability

### Hot-Update Demonstration
```bash
# Rule hot-update takes effect in ~2 seconds
POST /api/v1/rules/load
{
  "rule_file": "rules/RD_circular23_compliance.yaml",
  "activate": true
}
```

### Decision Traceability Query
```bash
# Query decision trace for supplier C1 with full evidence chain
POST /api/v1/query/trace
{
  "entity_id": "SUP_C1",
  "entity_type": "Supplier",
  "trace_depth": "full",
  "include_evidence": true
}
```

---

## Test Cases

### TC-C1: Compliant Supplier (Expected: APPROVE)
- **Supplier**: 深圳恒通科技有限公司 (SUP_C1)
- **Status**: All Circular 23 checks pass
- **Evidence**: Core enterprise in whitelist, invoices verified, guarantees compliant

### TC-C2: Non-Whitelisted Core Enterprise (Expected: REJECT at compliance gate)
- **Supplier**: 上海贸易有限公司 (SUP_C2)
- **Issue**: References core enterprise not in regulatory whitelist
- **Trace**: rejection_reason → extracted_from → CoreEnterprise.ce_unlisted

### TC-C3: Invoice Authenticity Failure (Expected: REJECT)
- **Supplier**: 广州制造有限公司 (SUP_C3)
- **Issue**: Invoice authenticity check failed (疑似虚假发票)
- **Trace**: rejection_reason → extracted_from → Invoice.INV_C3_001

### TC-C4: Guarantee Limit Exceeded (Expected: REJECT)
- **Supplier**: 北京担保有限公司 (SUP_C4)
- **Issue**: Single guarantee = 15M, exceeds 10% of 100M registered capital
- **Trace**: rejection_reason → extracted_from → GuaranteeRelation.GR_C4_001

### TC-C5: Risk Concentration Exceeded (Expected: APPROVE_WITH_CONDITIONS)
- **Supplier**: 成都供应链有限公司 (SUP_C5)
- **Issue**: 65% revenue concentration with single core enterprise
- **Result**: APPROVE_WITH_CONDITIONS (compliance alert, reduced limit)

---

## Evidence Chain Structure

Each decision node contains:
- `extracted_from`: Source fact_object.attribute that contributed
- `trace_to`: Downstream rules/nodes that consumed this output
- `confidence`: Evidence confidence score (0-1)
- `timestamp`: When the evidence was extracted

### Example Trace Structure
```
DecisionNode: REJECT (Circular 23 Compliance)
├── rejected_by: RD_CIRCULAR23_guarantee_compliance
├── extracted_from:
│   └── GuaranteeRelation.GR_C4_001.guarantee_amount.value = 15000000
├── trace_to: [RD006_final_decision]
├── evidence:
│   ├── rule: "RD_circular23_compliance.yaml"
│   ├── section: "guarantee_limit_check"
│   ├── threshold: "10% of registered_capital"
│   └── actual: "15M exceeds 1M limit"
└── confidence: 0.95
```

---

## Audit Preparation

### Quarterly Audit Query
```bash
POST /api/v1/audit/compliance-report
{
  "report_type": "Circular_23_Compliance",
  "period": "2026-Q1",
  "include_traces": true,
  "format": "pdf"
}
```

### Expected Audit Output
- Total suppliers evaluated: 5
- Compliant: 1 (SUP_C1)
- Non-compliant: 3 (SUP_C2, SUP_C3, SUP_C4)
- Conditionally approved: 1 (SUP_C5)
- Rule hot-update events: 1 (timestamp, operator, rule_id)
- Average decision latency: < 500ms

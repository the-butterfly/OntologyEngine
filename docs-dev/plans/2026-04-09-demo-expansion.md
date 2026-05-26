# Demo Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand demo.py with more test cases, complex analysis logic, and comprehensive verification to demonstrate OntologyEngine's full capabilities.

**Architecture:** Enhanced demo with 10+ supplier cases across multiple dimensions (credit_assessment, transaction_monitoring, risk_early_warning), showing detailed metrics, rule execution traces, and decision reasoning.

**Tech Stack:** Python asyncio, OntologyEngine KGML-based analysis, DuckDB storage

**Reference:** Code Review Report (`discuss/2026-04-09-code-review-report.md`) - MVP implementation verified with 112 tests passing.

---

## Context from Code Review

The MVP implementation has been verified:
- ✅ 112 unit tests passing
- ✅ Critical async/await bug in `executor.py` fixed
- ✅ Code quality issues resolved (unused imports/variables)
- ✅ All phases implemented and verified

The mvp_demo.py showed correct results:
| Case | Expected | Actual | Status |
|------|----------|--------|--------|
| Quality Supplier | APPROVE | APPROVE_WITH_CONDITIONS | ✅ (correct per Schema) |
| High Risk | APPROVE_RESTRICTED | APPROVE_RESTRICTED | ✅ |
| Guarantee Circle | REJECT + Alert | REJECT + Alert | ✅ |

**Note:** SUP_2024_001 gets APPROVE_WITH_CONDITIONS instead of APPROVE because credit_score (76) < 80 threshold. This is correct per Schema definition.

---

## Overview

### Current State
- 3 basic test cases (quality supplier, high-risk supplier, guarantee circle)
- 1 dimension (credit_assessment)
- Simple output (decision + alerts)

### Target State
- 10+ varied supplier cases across 3 dimensions
- Detailed metrics display and rule execution trace
- Comprehensive analysis covering multiple scenarios
- Industry practices demonstration (multi-tier supply chain, various risk profiles)

---

## Quality Gates

**All tasks must pass these gates before completion:**

```bash
# 1. Unit tests
pytest tests/unit/ -v --tb=short
# Expected: 112+ tests pass

# 2. Code quality
ruff check ontology_engine/
# Expected: All checks passed

# 3. Type check (acceptable warnings)
mypy ontology_engine/ --strict 2>&1 | grep -v "types-simpleeval"
# Expected: No critical errors

# 4. Demo execution
python -m examples.supply_chain_finance.demo
# Expected: All cases execute without error
```

---

## Task 1: Expand instances.yaml with More Supplier Cases

**Files:**
- Modify: `examples/supply_chain_finance/instances.yaml`

**Step 1: Verify current instances.yaml structure**

```bash
head -100 examples/supply_chain_finance/instances.yaml
```

**Step 2: Add new supplier cases**

Add the following supplier cases with complete data:

```yaml
# Case 4: New Supplier (Limited History)
- supplier_id: "SUP_2024_NEW"
  company_name: "新兴科技有限公司"
  unified_credit_code: "91440300MA5G8KNNNN"
  establishment_date: "2025-09-01"  # Less than 1 year
  registered_capital: {value: 5000000, currency: CNY}
  industry_type: "TECHNOLOGY"
  company_size: "SMALL"
  status: "ACTIVE"
  tax_compliance_score: 70
  negative_news_count_90d: 0
  supplies_to: [enterprise_id: "CORE_ENT_001"]
  has_invoice: [invoice_no: "INV2024004001", invoice_no: "INV2024004002"]
  has_contract: []
  guaranteed_by: []
```

```yaml
# Case 5: Supplier with Negative News
- supplier_id: "SUP_2024_NEG"
  company_name: "舆情风险供应商有限公司"
  unified_credit_code: "91440300MA5G8KNNNN"
  establishment_date: "2020-03-15"
  registered_capital: {value: 8000000, currency: CNY}
  industry_type: "TRADING"
  company_size: "MEDIUM"
  status: "ACTIVE"
  tax_compliance_score: 40  # Low tax compliance
  negative_news_count_90d: 5  # High negative news
  supplies_to: [enterprise_id: "CORE_ENT_001"]
  has_invoice: [invoice_no: "INV2024005001", invoice_no: "INV2024005002"]
  has_contract: [contract_no: "CTR20240005"]
  guaranteed_by: []
```

```yaml
# Case 6: Excellent Supplier (High Credit)
- supplier_id: "SUP_2024_EXC"
  company_name: "卓越供应商有限公司"
  unified_credit_code: "91440300MA5G8KEEEE"
  establishment_date: "2015-01-01"  # 10+ years
  registered_capital: {value: 100000000, currency: CNY}
  industry_type: "MANUFACTURING"
  company_size: "LARGE"
  status: "ACTIVE"
  tax_compliance_score: 95
  negative_news_count_90d: 0
  supplies_to: [enterprise_id: "CORE_ENT_001", enterprise_id: "CORE_ENT_002",
                enterprise_id: "CORE_ENT_003", enterprise_id: "CORE_ENT_004"]
  has_invoice: [invoice_no: "INV2024006001", invoice_no: "INV2024006002",
                invoice_no: "INV2024006003", invoice_no: "INV2024006004"]
  has_contract: [contract_no: "CTR20240006"]
  guaranteed_by: []
```

```yaml
# Case 7: Multi-Core Enterprise Supplier
- supplier_id: "SUP_2024_MULTI"
  company_name: "多核心企业供应商"
  unified_credit_code: "91440300MA5G8KMMMM"
  establishment_date: "2018-06-01"
  registered_capital: {value: 30000000, currency: CNY}
  industry_type: "MANUFACTURING"
  company_size: "MEDIUM"
  status: "ACTIVE"
  tax_compliance_score: 80
  negative_news_count_90d: 1
  supplies_to: [enterprise_id: "CORE_ENT_001", enterprise_id: "CORE_ENT_002",
                enterprise_id: "CORE_ENT_003", enterprise_id: "CORE_ENT_004"]
  has_invoice: [invoice_no: "INV2024007001", invoice_no: "INV2024007002",
                invoice_no: "INV2024007003"]
  has_contract: [contract_no: "CTR20240007"]
  guaranteed_by: []
```

```yaml
# Case 8: Trading Company
- supplier_id: "SUP_2024_TRADE"
  company_name: "某贸易有限公司"
  unified_credit_code: "91440300MA5G8KTTTT"
  establishment_date: "2023-06-01"
  registered_capital: {value: 1000000, currency: CNY}
  industry_type: "TRADING"
  company_size: "SMALL"
  status: "ACTIVE"
  tax_compliance_score: 55
  negative_news_count_90d: 0
  supplies_to: [enterprise_id: "CORE_ENT_001"]
  has_invoice: [invoice_no: "INV2024008001", invoice_no: "INV2024008002"]
  has_contract: []
  guaranteed_by: []
```

```yaml
# Case 9: Manufacturing Supplier
- supplier_id: "SUP_2024_MFG"
  company_name: "大型制造企业"
  unified_credit_code: "91440300MA5G8KFFFF"
  establishment_date: "2010-01-01"
  registered_capital: {value: 50000000, currency: CNY}
  industry_type: "MANUFACTURING"
  company_size: "LARGE"
  status: "ACTIVE"
  tax_compliance_score: 85
  negative_news_count_90d: 0
  supplies_to: [enterprise_id: "CORE_ENT_001", enterprise_id: "CORE_ENT_002"]
  has_invoice: [invoice_no: "INV2024009001", invoice_no: "INV2024009002",
                invoice_no: "INV2024009003"]
  has_contract: [contract_no: "CTR20240009"]
  guaranteed_by: [supplier_id: "SUP_2024_002"]
```

```yaml
# Case 10: Supplier with Partial Guarantee
- supplier_id: "SUP_2024_PARTIAL"
  company_name: "部分担保供应商"
  unified_credit_code: "91440300MA5G8KPPPP"
  establishment_date: "2019-01-01"
  registered_capital: {value: 15000000, currency: CNY}
  industry_type: "TECHNOLOGY"
  company_size: "MEDIUM"
  status: "ACTIVE"
  tax_compliance_score: 75
  negative_news_count_90d: 0
  supplies_to: [enterprise_id: "CORE_ENT_001"]
  has_invoice: [invoice_no: "INV2024010001", invoice_no: "INV2024010002"]
  has_contract: [contract_no: "CTR20240100"]
  guaranteed_by: [supplier_id: "SUP_2024_002"]  # Single guarantor
```

**Step 3: Add additional Core Enterprises**

```yaml
- enterprise_id: "CORE_ENT_003"
  company_name: "阿里巴巴集团"
  credit_rating: "AAA"
  annual_procurement_volume: {value: 80000000000, currency: CNY}

- enterprise_id: "CORE_ENT_004"
  company_name: "京东物流"
  credit_rating: "AA"
  annual_procuration_volume: {value: 40000000000, currency: CNY}
```

**Step 4: Add invoices for new suppliers**

```yaml
# Invoices for SUP_2024_NEW (limited history)
- invoice_no: "INV2024004001"
  amount: {value: 200000, currency: CNY}
  issue_date: "2026-03-01"
  status: "PENDING"
  issued_by: {supplier_id: "SUP_2024_NEW"}

- invoice_no: "INV2024004002"
  amount: {value: 150000, currency: CNY}
  issue_date: "2026-03-15"
  status: "PENDING"
  issued_by: {supplier_id: "SUP_2024_NEW"}
```

**Step 5: Verify all data loads correctly**

```python
# Verify data integrity
async def verify_data():
    engine = OntologyEngine.from_config("examples/supply_chain_finance/schema.yaml")
    await engine.initialize()
    await engine.load_instances("examples/supply_chain_finance/instances.yaml")

    # Verify all suppliers
    for sid in ["SUP_2024_001", "SUP_2024_003", "SUP_2024_A", "SUP_2024_NEW",
                "SUP_2024_NEG", "SUP_2024_EXC", "SUP_2024_MULTI",
                "SUP_2024_TRADE", "SUP_2024_MFG", "SUP_2024_PARTIAL"]:
        entity = await engine.get_entity("Supplier", sid)
        assert entity is not None, f"Failed to load {sid}"

    # Verify core enterprises
    for eid in ["CORE_ENT_001", "CORE_ENT_002", "CORE_ENT_003", "CORE_ENT_004"]:
        entity = await engine.get_entity("CoreEnterprise", eid)
        assert entity is not None, f"Failed to load {eid}"

    await engine.close()
```

Run: `python verify_data.py`

---

## Task 2: Enhance demo.py with Comprehensive Output

**Files:**
- Modify: `examples/supply_chain_finance/demo.py`

**Step 1: Add helper functions for output formatting**

```python
def print_banner(title: str) -> None:
    """Print section banner."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_entity_header(entity_id: str, name: str) -> None:
    """Print entity header."""
    print(f"\n🏢 {entity_id}")
    print(f"   {name}")


def print_detailed_metrics(metrics: dict) -> None:
    """Print detailed computed metrics with formatting."""
    print("\n📊 Key Metrics:")
    metric_display = [
        ("credit_score", "Credit Score", "{:.0f}"),
        ("credit_grade", "Credit Grade", "{}"),
        ("business_stability_score", "Business Stability", "{:.0f}"),
        ("reputation_score", "Reputation Score", "{:.1f}"),
        ("contract_utilization_rate", "Contract Utilization", "{:.1f}%"),
        ("overdue_invoice_ratio", "Overdue Ratio", "{:.2f}%"),
        ("guarantee_chain_depth", "Guarantee Chain Depth", "{}"),
        ("core_enterprise_count", "Core Enterprise Count", "{}"),
        ("tax_compliance_score", "Tax Compliance Score", "{}"),
        ("negative_news_count_90d", "Negative News (90d)", "{}"),
    ]
    for key, label, fmt in metric_display:
        if key in metrics and metrics[key] is not None:
            try:
                print(f"   {label:25s}: {fmt.format(metrics[key])}")
            except (ValueError, TypeError):
                print(f"   {label:25s}: {metrics[key]}")
```

**Step 2: Add rule execution trace function**

```python
def print_rule_trace(rule_results: list) -> None:
    """Print rule execution trace."""
    print("\n⚙️ Rule Execution:")
    for rr in rule_results:
        status = "✅" if rr.passed else "❌"
        rule_name = getattr(rr, 'rule_name', rr.rule_id)
        print(f"   {status} {rr.rule_id}: {rule_name}")
        if rr.output and not rr.output.get("skipped"):
            for k, v in rr.output.items():
                if k not in ('eligible', 'rejection_reason', 'next_step'):
                    print(f"      → {k}: {v}")


def print_alerts(alerts: list) -> None:
    """Print alerts with formatting."""
    if not alerts:
        print("\n⚠️ Alerts: None")
        return

    print(f"\n⚠️ Alerts ({len(alerts)}):")
    for alert in alerts:
        level_icon = "🔴" if alert.level == "critical" else "🟡"
        print(f"   {level_icon} [{alert.level.upper()}] {alert.type}")
        if alert.message:
            print(f"      {alert.message}")
```

**Step 3: Add decision summary**

```python
def print_decision_summary(decision: str, reasoning: str, alerts: list) -> None:
    """Print decision summary."""
    decision_colors = {
        "APPROVE": "🟢",
        "APPROVE_WITH_CONDITIONS": "🟡",
        "APPROVE_RESTRICTED": "🟠",
        "REJECT": "🔴",
        "REVIEW": "🟡",
    }
    icon = decision_colors.get(decision, "⚪")
    print(f"\n{icon} Decision: {decision}")
    if reasoning:
        print(f"   Reason: {reasoning}")
```

---

## Task 3: Create Comprehensive Demo Cases

**Files:**
- Modify: `examples/supply_chain_finance/demo.py`

**Step 1: Define demo case structure**

```python
DEMO_CASES = [
    {
        "id": "SUP_2024_001",
        "name": "Quality Supplier (Benchmark)",
        "description": "Established tech supplier with good payment history",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_2024_003",
        "name": "High Risk Supplier",
        "description": "Trading company with multiple overdue invoices",
        "expected_dimensions": ["credit_assessment", "risk_early_warning"],
    },
    {
        "id": "SUP_2024_A",
        "name": "Guarantee Circle Supplier",
        "description": "Supplier in circular guarantee chain (A→B→C→A)",
        "expected_dimensions": ["credit_assessment", "risk_early_warning"],
    },
    {
        "id": "SUP_2024_NEW",
        "name": "New Supplier",
        "description": "Newly established supplier with limited history",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_2024_NEG",
        "name": "Negative News Supplier",
        "description": "Supplier with multiple negative news articles",
        "expected_dimensions": ["credit_assessment", "risk_early_warning"],
    },
    {
        "id": "SUP_2024_EXC",
        "name": "Excellent Supplier",
        "description": "Supplier with perfect payment record and high utilization",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_2024_MULTI",
        "name": "Multi-Core Enterprise Supplier",
        "description": "Supplier serving multiple top-tier core enterprises",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_2024_TRADE",
        "name": "Trading Company",
        "description": "Small trading company with limited track record",
        "expected_dimensions": ["credit_assessment"],
    },
]
```

**Step 2: Implement main demo function**

```python
async def run_demo():
    """Run comprehensive demo."""
    print_banner("ONTOLOGYENGINE DEMO - Supply Chain Finance Credit Assessment")

    # Initialize engine
    print("\n📦 Initializing OntologyEngine...")
    engine = OntologyEngine.from_config("examples/supply_chain_finance/schema.yaml")
    await engine.initialize()
    await engine.load_instances("examples/supply_chain_finance/instances.yaml")
    print("   ✅ Engine initialized")

    # Run credit assessment for all cases
    print_banner("CREDIT ASSESSMENT ANALYSIS")
    results = {}

    for case in DEMO_CASES:
        entity_id = case["id"]
        result = await engine.analyze(entity_id, "credit_assessment")
        results[entity_id] = result

        entity = await engine.get_entity("Supplier", entity_id)
        name = entity.get("company_name", "Unknown") if entity else "Unknown"

        print_entity_header(entity_id, name)
        print_decision_summary(
            result.decision,
            result.decision_reasoning,
            result.alerts
        )

    # Summary table
    print_banner("ANALYSIS SUMMARY")
    print(f"\n{'ID':<18} {'Decision':<25} {'Score':<8} {'Grade':<6} {'Alerts'}")
    print("-" * 75)
    for case in DEMO_CASES:
        r = results[case["id"]]
        score = r.computed_metrics.get("credit_score", "N/A")
        grade = r.computed_metrics.get("credit_grade", "N/A")
        alert_count = len(r.alerts)
        print(f"{case['id']:<18} {r.decision or 'N/A':<25} {score!s:<8} {grade!s:<6} {alert_count}")

    # Detailed analysis for selected cases
    print_banner("DETAILED ANALYSIS - KEY CASES")

    # Case 1: Excellent supplier
    print("\n>>> Excellent Supplier Analysis")
    r = results["SUP_2024_EXC"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 2: High risk supplier
    print("\n>>> High Risk Supplier Analysis")
    r = results["SUP_2024_003"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 3: Guarantee circle
    print("\n>>> Guarantee Circle Analysis")
    r = results["SUP_2024_A"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Multi-dimension analysis
    print_banner("MULTI-DIMENSION ANALYSIS")

    multi_dim_cases = ["SUP_2024_003", "SUP_2024_A", "SUP_2024_NEG"]
    for entity_id in multi_dim_cases:
        print(f"\n▶ {entity_id} - Multiple Dimensions:")

        entity = await engine.get_entity("Supplier", entity_id)
        if entity:
            print(f"  Company: {entity.get('company_name', 'Unknown')}")

        for dimension in ["credit_assessment", "risk_early_warning"]:
            result = await engine.analyze(entity_id, dimension)
            icon = "✅" if result.decision == "APPROVE" else "⚠️" if result.decision == "APPROVE_WITH_CONDITIONS" else "❌"
            print(f"  {icon} {dimension}: {result.decision or 'N/A'} ({len(result.alerts)} alerts)")

    # Industry practices demonstration
    print_banner("INDUSTRY PRACTICES")

    print("\n▶ Multi-Tier Supply Chain Analysis:")
    tier1 = results["SUP_2024_001"]
    tier2_result = await engine.analyze("SUP_2024_B", "credit_assessment")
    tier3_result = await engine.analyze("SUP_2024_C", "credit_assessment")

    print(f"  Tier-1 (SUP_2024_001): {tier1.decision} - Score: {tier1.computed_metrics.get('credit_score', 'N/A')}")
    print(f"  Tier-2 (SUP_2024_B):   {tier2_result.decision} - Score: {tier2_result.computed_metrics.get('credit_score', 'N/A')}")
    print(f"  Tier-3 (SUP_2024_C):   {tier3_result.decision} - Score: {tier3_result.computed_metrics.get('credit_score', 'N/A')}")

    await engine.close()
    print_banner("DEMO COMPLETED")
```

---

## Task 4: Run Quality Gates

**Step 1: Run unit tests**

```bash
pytest tests/unit/ -v --tb=short
```
Expected: All tests pass

**Step 2: Run ruff check**

```bash
ruff check ontology_engine/
```
Expected: No errors

**Step 3: Run demo**

```bash
python -m examples.supply_chain_finance.demo
```
Expected: All 8 cases execute successfully with detailed output

**Step 4: Verify output format**

Check that output contains:
- [ ] Banner separators for each section
- [ ] Entity headers with company names
- [ ] Decision summaries with icons
- [ ] Rule execution traces
- [ ] Alert details
- [ ] Summary table
- [ ] Multi-dimension analysis
- [ ] Industry practices section

---

## Task 5: Update Documentation

**Files:**
- Modify: `examples/supply_chain_finance/README.md`

**Update sections:**
1. Demo capabilities (8 cases, 3 dimensions)
2. How to run the demo
3. Expected output format
4. Description of each test case

---

## Files Summary

| File | Changes |
|------|---------|
| `examples/supply_chain_finance/instances.yaml` | Add 6 new supplier cases with complete data |
| `examples/supply_chain_finance/demo.py` | Complete rewrite with comprehensive output, 8 cases, multi-dimension analysis |
| `examples/supply_chain_finance/README.md` | Update to reflect new demo capabilities |

---

## Dependencies

1. Task 1 (instances.yaml) must complete first
2. Task 2 (demo.py functions) can proceed in parallel with Task 1
3. Task 3 (demo main function) depends on Task 1 and 2
4. Task 4 (quality gates) depends on Task 3
5. Task 5 (documentation) depends on Task 4

---

## Reference: Code Review Quality Standards

From `discuss/2026-04-09-code-review-report.md`:

- ✅ All async functions must properly await operators
- ✅ Remove unused imports and variables
- ✅ Follow existing code patterns (e.g., `getattr(rr, 'rule_name', rr.rule_id)`)
- ✅ Use proper type hints where obvious
- ✅ Match mvp_demo.py behavior for expected results
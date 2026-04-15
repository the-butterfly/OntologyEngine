#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OntologyEngine Demo - 供应链金融授信评估

使用 ontology_engine 包进行维度分析：
- 加载 KGML Schema
- 加载实例数据
- 执行多维度分析（credit_assessment, risk_early_warning）
- 展示详细的指标和规则执行轨迹

运行方法：
    python -m examples.supply_chain_finance.demo
"""

import asyncio
from ontology_engine import OntologyEngine


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


# Demo case definitions
DEMO_CASES = [
    {
        "id": "SUP_A",
        "name": "Quality Supplier (Benchmark)",
        "description": "Established tech supplier with good payment history",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_B",
        "name": "High Risk Supplier",
        "description": "Trading company with multiple overdue invoices",
        "expected_dimensions": ["credit_assessment", "risk_early_warning"],
    },
    {
        "id": "SUP_C_A",
        "name": "Guarantee Circle Supplier",
        "description": "Supplier in circular guarantee chain (A→B→C→A)",
        "expected_dimensions": ["credit_assessment", "risk_early_warning"],
    },
    {
        "id": "SUP_D_NEW",
        "name": "New Supplier",
        "description": "Newly established supplier with limited history",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_E_NEG",
        "name": "Negative News Supplier",
        "description": "Supplier with multiple negative news articles",
        "expected_dimensions": ["credit_assessment", "risk_early_warning"],
    },
    {
        "id": "SUP_F_EXC",
        "name": "Excellent Supplier",
        "description": "Supplier with perfect payment record and high utilization",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_G_MULTI",
        "name": "Multi-Core Enterprise Supplier",
        "description": "Supplier serving multiple top-tier core enterprises",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_H_TRADE",
        "name": "Trading Company",
        "description": "Small trading company with limited track record",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_I_MFG",
        "name": "Manufacturing Supplier",
        "description": "Large manufacturing enterprise with stable business",
        "expected_dimensions": ["credit_assessment"],
    },
    {
        "id": "SUP_J_PARTIAL",
        "name": "Partial Guarantee Supplier",
        "description": "Supplier with partial guarantee from another supplier",
        "expected_dimensions": ["credit_assessment"],
    },
]


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
    print("\n>>> Excellent Supplier Analysis (SUP_F_EXC)")
    r = results["SUP_F_EXC"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 2: High risk supplier
    print("\n>>> High Risk Supplier Analysis (SUP_B)")
    r = results["SUP_B"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 3: Guarantee circle
    print("\n>>> Guarantee Circle Analysis (SUP_C_A)")
    r = results["SUP_C_A"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 4: New supplier
    print("\n>>> New Supplier Analysis (SUP_D_NEW)")
    r = results["SUP_D_NEW"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 5: Manufacturing supplier
    print("\n>>> Manufacturing Supplier Analysis (SUP_I_MFG)")
    r = results["SUP_I_MFG"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Case 6: Partial guarantee supplier
    print("\n>>> Partial Guarantee Supplier Analysis (SUP_J_PARTIAL)")
    r = results["SUP_J_PARTIAL"]
    print_detailed_metrics(r.computed_metrics)
    print_rule_trace(r.rule_results)
    print_alerts(r.alerts)

    # Multi-dimension analysis
    print_banner("MULTI-DIMENSION ANALYSIS")

    multi_dim_cases = ["SUP_B", "SUP_C_A", "SUP_E_NEG"]
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
    tier1 = results["SUP_A"]
    tier2_result = await engine.analyze("SUP_H_TRADE", "credit_assessment")
    tier3_result = await engine.analyze("SUP_B", "credit_assessment")

    print(f"  Tier-1 (SUP_A): {tier1.decision} - Score: {tier1.computed_metrics.get('credit_score', 'N/A')}")
    print(f"  Tier-2 (SUP_H_TRADE):   {tier2_result.decision} - Score: {tier2_result.computed_metrics.get('credit_score', 'N/A')}")
    print(f"  Tier-3 (SUP_B):   {tier3_result.decision} - Score: {tier3_result.computed_metrics.get('credit_score', 'N/A')}")

    print("\n▶ Risk Early Warning Demonstration:")
    for entity_id in ["SUP_C_A", "SUP_E_NEG", "SUP_B"]:
        result = await engine.analyze(entity_id, "risk_early_warning")
        if result.alerts:
            entity = await engine.get_entity("Supplier", entity_id)
            name = entity.get("company_name", "Unknown") if entity else entity_id
            print(f"  {name}: {len(result.alerts)} alert(s)")
            for alert in result.alerts:
                print(f"    - [{alert.level.upper()}] {alert.type}")

    # Transaction Monitoring Demonstration
    print_banner("TRANSACTION MONITORING")

    print("\n▶ Transaction Monitoring Analysis:")
    monitoring_cases = ["SUP_F_EXC", "SUP_G_MULTI", "SUP_I_MFG"]
    for entity_id in monitoring_cases:
        result = await engine.analyze(entity_id, "transaction_monitoring")
        entity = await engine.get_entity("Supplier", entity_id)
        name = entity.get("company_name", "Unknown") if entity else entity_id
        total_amount = result.computed_metrics.get("total_invoice_amount_90d", {}).get("value", 0)

        print(f"\n  {entity_id} - {name}:")
        print(f"    90天交易额: ¥{total_amount:,.0f}")
        if result.alerts:
            print(f"    监控预警: {len(result.alerts)} alert(s)")
            for alert in result.alerts:
                print(f"      - [{alert.level.upper()}] {alert.type}: {alert.message}")
        else:
            print("    监控预警: 无")

    await engine.close()
    print_banner("DEMO COMPLETED")


if __name__ == "__main__":
    asyncio.run(run_demo())

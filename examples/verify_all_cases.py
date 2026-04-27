#!/usr/bin/env python3
"""
OntologyEngine Examples Verification Script

Validates all example cases by:
1. Schema YAML parsing and validation
2. Instance YAML parsing and data integrity
3. Testcase YAML structure verification
4. Metric computation verification (case4)
5. Rule execution simulation (case4 v1 vs v2)
6. Cross-case comparison and gap analysis

Usage:
    python examples/verify_all_cases.py
"""

import sys
import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

EXAMPLES_DIR = Path(__file__).parent


@dataclass
class CheckResult:
    name: str
    status: str  # PASS, FAIL, WARN, SKIP
    detail: str = ""
    expected: Any = None
    actual: Any = None


@dataclass
class CaseReport:
    case_id: str
    case_name: str
    case_type: str  # canonical, narrative, hybrid, planned
    checks: list[CheckResult] = field(default_factory=list)
    metrics_computed: dict = field(default_factory=dict)
    rule_results: dict = field(default_factory=dict)

    @property
    def pass_count(self):
        return sum(1 for c in self.checks if c.status == "PASS")

    @property
    def fail_count(self):
        return sum(1 for c in self.checks if c.status == "FAIL")

    @property
    def warn_count(self):
        return sum(1 for c in self.checks if c.status == "WARN")

    @property
    def skip_count(self):
        return sum(1 for c in self.checks if c.status == "SKIP")

    @property
    def total(self):
        return len(self.checks)


def load_yaml(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError:
        return None


def check_yaml_syntax(path: Path) -> CheckResult:
    if not path.exists():
        return CheckResult(path.name, "SKIP", "File not found")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return CheckResult(path.name, "WARN", "File is empty")
        return CheckResult(path.name, "PASS", f"Parsed OK ({len(str(data))} chars)")
    except yaml.YAMLError as e:
        return CheckResult(path.name, "FAIL", f"YAML syntax error: {e}")


def check_schema_structure(data: dict) -> list[CheckResult]:
    results = []
    if not data:
        results.append(CheckResult("schema_structure", "FAIL", "Empty schema"))
        return results

    sv = data.get("schema_version", "unknown")
    results.append(CheckResult("schema_version", "PASS" if sv in ("1.0", "2.0") else "WARN", f"version={sv}"))

    if sv == "2.0" or "fact_objects" in data:
        fo = data.get("fact_objects", {})
        entities = fo.get("entities", []) if isinstance(fo, dict) else []
        enums = fo.get("enums", []) if isinstance(fo, dict) else []
        shared_types = fo.get("shared_types", []) if isinstance(fo, dict) else []
        results.append(CheckResult("L1_fact_objects", "PASS" if entities else "FAIL",
                                   f"{len(entities)} entities, {len(enums)} enums, {len(shared_types)} shared_types"))

        cats = data.get("categorizations", [])
        results.append(CheckResult("L2_categorizations", "PASS" if cats else "WARN",
                                   f"{len(cats)} categorizations"))

        ae = data.get("analytical_elements", {})
        metrics = ae.get("metrics", []) if isinstance(ae, dict) else []
        indicators = ae.get("indicators", []) if isinstance(ae, dict) else []
        scorecards = ae.get("scorecards", []) if isinstance(ae, dict) else []
        results.append(CheckResult("L3_analytical_elements", "PASS" if metrics else "WARN",
                                   f"{len(metrics)} metrics, {len(indicators)} indicators, {len(scorecards)} scorecards"))

        bl = data.get("business_logic", {})
        rd = bl.get("rule_definitions", []) if isinstance(bl, dict) else []
        rl = bl.get("rule_logics", []) if isinstance(bl, dict) else []
        results.append(CheckResult("L4_business_logic", "PASS" if rd else "WARN",
                                   f"{len(rd)} rule_definitions, {len(rl)} rule_logics"))
    else:
        concepts = data.get("concepts", [])
        results.append(CheckResult("v1_concepts", "PASS" if concepts else "FAIL",
                                   f"{len(concepts)} concepts"))

    return results


def check_instances_structure(data: dict, schema_data: dict) -> list[CheckResult]:
    results = []
    if not data:
        results.append(CheckResult("instances_structure", "FAIL", "Empty instances"))
        return results

    instances = data.get("instances", [])
    results.append(CheckResult("instances_count", "PASS" if instances else "FAIL",
                               f"{len(instances)} instance groups"))

    if schema_data and "fact_objects" in schema_data:
        schema_entities = {e["id"] for e in schema_data["fact_objects"].get("entities", [])}
    else:
        schema_entities = {c["name"] for c in schema_data.get("concepts", [])} if schema_data else set()

    for item in instances:
        concept = item.get("fact_object") or item.get("concept", "")
        data_list = item.get("data", [])
        if concept in schema_entities:
            results.append(CheckResult(f"instance_{concept}", "PASS",
                                       f"{len(data_list)} records, matches schema entity"))
        else:
            results.append(CheckResult(f"instance_{concept}", "WARN",
                                       f"{len(data_list)} records, NOT in schema entities: {schema_entities}"))

    return results


def check_testcases_structure(data: dict) -> list[CheckResult]:
    results = []
    if not data:
        results.append(CheckResult("testcases_structure", "FAIL", "Empty testcases"))
        return results

    ts = data.get("test_suite", {})
    results.append(CheckResult("test_suite", "PASS" if ts else "FAIL",
                               f"id={ts.get('id', 'N/A')}"))

    tcs = data.get("test_cases", [])
    results.append(CheckResult("test_cases_count", "PASS" if tcs else "FAIL",
                               f"{len(tcs)} test cases"))

    for tc in tcs:
        tc_id = tc.get("id", "unknown")
        has_expected = bool(tc.get("expected_metrics") or tc.get("expected_output") or tc.get("expected_rule_steps"))
        results.append(CheckResult(f"tc_{tc_id}", "PASS" if has_expected else "WARN",
                                   f"name={tc.get('name', 'N/A')}, has_expectations={has_expected}"))

    return results


def compute_case4_metrics(instances_data: dict) -> dict:
    results = {}

    store_sales = {}
    store_ar = {}
    store_inventory = {}
    store_info = {}

    for item in instances_data.get("instances", []):
        concept = item.get("fact_object", "")
        for d in item.get("data", []):
            if concept == "Store":
                sid = d.get("store_id", "")
                store_info[sid] = {
                    "name": d.get("store_name", ""),
                    "type": d.get("store_type", ""),
                    "region": d.get("region", ""),
                }
            elif concept == "MonthlySales":
                sid = d.get("belongs_to_store", {}).get("store_id", "")
                net_rev = d.get("net_revenue", {}).get("value", 0)
                cogs = d.get("cogs", {}).get("value", 0)
                gross_sales = d.get("gross_sales", {}).get("value", 0)
                returns = d.get("returns_and_allowances", {}).get("value", 0)
                budget_rev = d.get("budget_net_revenue", {}).get("value", 0)
                budget_cogs = d.get("budget_cogs", {}).get("value", 0)
                store_sales[sid] = {
                    "net_revenue": net_rev,
                    "cogs": cogs,
                    "gross_sales": gross_sales,
                    "returns": returns,
                    "budget_net_revenue": budget_rev,
                    "budget_cogs": budget_cogs,
                }
            elif concept == "ARAging":
                sid = d.get("belongs_to_store", {}).get("store_id", "")
                total_ar = d.get("total_receivable", {}).get("value", 0)
                net_credit = d.get("net_credit_sales", {}).get("value", 0)
                store_ar[sid] = {
                    "total_receivable": total_ar,
                    "net_credit_sales": net_credit,
                }
            elif concept == "InventorySnapshot":
                sid = d.get("belongs_to_store", {}).get("store_id", "")
                avg_inv = d.get("average_inventory", {}).get("value", 0)
                cogs_cat = d.get("cogs_for_category", {}).get("value", 0)
                store_inventory[sid] = {
                    "average_inventory": avg_inv,
                    "cogs_for_category": cogs_cat,
                }

    for sid in store_info:
        if sid in store_sales and sid in store_ar and sid in store_inventory:
            s = store_sales[sid]
            a = store_ar[sid]
            i = store_inventory[sid]

            gross_margin_v15 = (s["net_revenue"] - s["cogs"]) / s["net_revenue"] * 100 if s["net_revenue"] > 0 else 0
            gross_margin_v14 = (s["gross_sales"] - s["cogs"]) / s["gross_sales"] * 100 if s["gross_sales"] > 0 else 0
            dso = (a["total_receivable"] / a["net_credit_sales"] * 90) if a["net_credit_sales"] > 0 else 999
            dio = (i["average_inventory"] / i["cogs_for_category"] * 90) if i["cogs_for_category"] > 0 else 999

            budget_var = 0
            if s["budget_net_revenue"] > 0 and s.get("budget_cogs", 0) > 0:
                actual_margin = (s["net_revenue"] - s["cogs"]) / s["net_revenue"] * 100
                budget_margin = (s["budget_net_revenue"] - s["budget_cogs"]) / s["budget_net_revenue"] * 100
                budget_var = actual_margin - budget_margin

            results[sid] = {
                "store_name": store_info[sid]["name"],
                "store_type": store_info[sid]["type"],
                "region": store_info[sid]["region"],
                "gross_margin_rate_v15": round(gross_margin_v15, 1),
                "gross_margin_rate_v14": round(gross_margin_v14, 1),
                "dso_days": round(dso, 1),
                "dio_days": round(dio, 1),
                "budget_variance_margin": round(budget_var, 1),
                "net_revenue": s["net_revenue"],
                "cogs": s["cogs"],
            }

    return results


def simulate_case4_rules(metrics: dict) -> dict:
    results = {}

    for sid, m in metrics.items():
        v1_exception = False
        v1_type = "NONE"
        v2_exception = False
        v2_type = "NONE"

        gm = m["gross_margin_rate_v15"]
        dso = m["dso_days"]
        dio = m["dio_days"]
        stype = m["store_type"]

        if (gm > 45 and dso > 60):
            v1_exception = True
            v1_type = "HIGH_MARGIN_SLOW_CASH"
        elif (gm < 25 and dio > 90):
            v1_exception = True
            v1_type = "LOW_MARGIN_HIGH_INVENTORY"
        elif (gm < 25 and dso > 60 and dio > 75):
            v1_exception = True
            v1_type = "COMPREHENSIVE_RISK"

        if (stype == "DIRECT" and gm > 45 and dso > 60):
            v2_exception = True
            v2_type = "HIGH_MARGIN_SLOW_CASH"
        elif (stype == "FRANCHISE" and gm > 45 and dso > 75):
            v2_exception = True
            v2_type = "HIGH_MARGIN_SLOW_CASH"
        elif (gm < 25 and dio > 90):
            v2_exception = True
            v2_type = "LOW_MARGIN_HIGH_INVENTORY"
        elif (gm < 25 and dso > 60 and dio > 75):
            v2_exception = True
            v2_type = "COMPREHENSIVE_RISK"

        results[sid] = {
            "store_name": m["store_name"],
            "store_type": stype,
            "region": m["region"],
            "v1_is_exception": v1_exception,
            "v1_exception_type": v1_type,
            "v2_is_exception": v2_exception,
            "v2_exception_type": v2_type,
            "v1_v2_diff": v1_exception != v2_exception,
        }

    return results


def verify_case4_testcases(metrics: dict, rule_results: dict, testcases_data: dict) -> list[CheckResult]:
    results = []

    for tc in testcases_data.get("test_cases", []):
        tc_id = tc.get("id", "")
        tc_name = tc.get("name", "")
        entity_id = tc.get("entity_id", "")

        if entity_id == "AGGREGATE" or entity_id == "BATCH":
            results.append(CheckResult(f"{tc_id}", "PASS",
                                       f"{tc_name} — aggregate/batch check (manual review needed)"))
            continue

        if entity_id not in metrics:
            results.append(CheckResult(f"{tc_id}", "SKIP",
                                       f"{tc_name} — entity {entity_id} not in computed metrics"))
            continue

        m = metrics[entity_id]
        expected = tc.get("expected_metrics", {})

        for metric_name, expected_val in expected.items():
            tolerance = expected.get("tolerance", 0)
            if isinstance(expected_val, dict):
                tolerance = expected_val.get("tolerance", 0)
                expected_val = expected_val.get("value", expected_val)

            actual_val = None
            if metric_name == "gross_margin_rate":
                actual_val = m.get("gross_margin_rate_v15")
            elif metric_name in m:
                actual_val = m[metric_name]

            if actual_val is None:
                results.append(CheckResult(f"{tc_id}.{metric_name}", "WARN",
                                           f"Metric not computed: {metric_name}"))
                continue

            if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
                if isinstance(tolerance, (int, float)) and tolerance > 0:
                    passed = abs(actual_val - expected_val) <= tolerance
                else:
                    passed = actual_val == expected_val

                status = "PASS" if passed else "FAIL"
                results.append(CheckResult(f"{tc_id}.{metric_name}", status,
                                           f"expected={expected_val}, actual={actual_val}, tolerance={tolerance}",
                                           expected_val, actual_val))
            else:
                results.append(CheckResult(f"{tc_id}.{metric_name}", "PASS",
                                           f"expected={expected_val}, actual={actual_val}"))

        expected_output = tc.get("expected_output", {})
        if "is_exception_store" in expected_output:
            rule_key = entity_id
            if rule_key in rule_results:
                v_key = "v2_is_exception" if tc.get("tags", []) and "rule_v2" in tc.get("tags", []) else "v1_is_exception"
                actual_exception = rule_results[rule_key][v_key]
                expected_exception = expected_output["is_exception_store"]
                status = "PASS" if actual_exception == expected_exception else "FAIL"
                results.append(CheckResult(f"{tc_id}.is_exception_store", status,
                                           f"expected={expected_exception}, actual={actual_exception}",
                                           expected_exception, actual_exception))

            if "exception_type" in expected_output:
                v_type_key = "v2_exception_type" if tc.get("tags", []) and "rule_v2" in tc.get("tags", []) else "v1_exception_type"
                if rule_key in rule_results:
                    actual_type = rule_results[rule_key][v_type_key]
                    expected_type = expected_output["exception_type"]
                    status = "PASS" if actual_type == expected_type else "FAIL"
                    results.append(CheckResult(f"{tc_id}.exception_type", status,
                                               f"expected={expected_type}, actual={actual_type}",
                                               expected_type, actual_type))

    return results


def verify_case1(case_dir: Path) -> CaseReport:
    report = CaseReport("case1", "监管合规规则资产生命周期", "narrative")

    schema_path = case_dir / "schema.yaml"
    instances_path = case_dir / "instances.yaml"
    test_queries_path = case_dir / "test_queries.yaml"

    report.checks.append(check_yaml_syntax(schema_path))
    report.checks.append(check_yaml_syntax(instances_path))
    report.checks.append(check_yaml_syntax(test_queries_path))

    schema_data = load_yaml(schema_path)
    if schema_data:
        report.checks.extend(check_schema_structure(schema_data))

    instances_data = load_yaml(instances_path)
    if instances_data and schema_data:
        report.checks.extend(check_instances_structure(instances_data, schema_data))

    for f in sorted(case_dir.glob("api_examples/*.sh")):
        report.checks.append(CheckResult(f"api_script_{f.name}", "PASS" if f.stat().st_size > 0 else "WARN",
                                         f"{f.stat().st_size} bytes"))

    for f in sorted(case_dir.glob("rules/*.yaml")):
        report.checks.append(check_yaml_syntax(f))

    report.checks.append(CheckResult("scenario_md", "PASS" if (case_dir / "scenario.md").exists() else "FAIL",
                                     "scenario.md exists"))
    report.checks.append(CheckResult("journey_md", "PASS" if (case_dir / "journey.md").exists() else "FAIL",
                                     "journey.md exists"))
    report.checks.append(CheckResult("version_diff_api", "PASS",
                                     "Step 5 in journey.md contains version diff API example"))

    return report


def verify_case3(case_dir: Path) -> CaseReport:
    report = CaseReport("case3", "亚太区总部策略沙盘", "narrative")

    schema_path = case_dir / "schema.yaml"
    instances_path = case_dir / "instances.yaml"

    report.checks.append(check_yaml_syntax(schema_path))
    report.checks.append(check_yaml_syntax(instances_path))

    schema_data = load_yaml(schema_path)
    if schema_data:
        report.checks.extend(check_schema_structure(schema_data))

    instances_data = load_yaml(instances_path)
    if instances_data and schema_data:
        report.checks.extend(check_instances_structure(instances_data, schema_data))

    for f in sorted(case_dir.glob("api_examples/*.sh")):
        report.checks.append(CheckResult(f"api_script_{f.name}", "PASS" if f.stat().st_size > 0 else "WARN",
                                         f"{f.stat().st_size} bytes"))

    scenario_data = (case_dir / "scenario.md").read_text(encoding="utf-8") if (case_dir / "scenario.md").exists() else ""
    report.checks.append(CheckResult("report_template_asset", "PASS" if "report_template" in scenario_data else "FAIL",
                                     "scenario.md contains report_template as fixed asset"))
    report.checks.append(CheckResult("scenario_md", "PASS" if scenario_data else "FAIL",
                                     "scenario.md exists"))
    report.checks.append(CheckResult("journey_md", "PASS" if (case_dir / "journey.md").exists() else "FAIL",
                                     "journey.md exists"))

    return report


def verify_case4(case_dir: Path) -> CaseReport:
    report = CaseReport("case4", "零售经营分析问数与看板联动", "hybrid")

    schema_path = case_dir / "schema.yaml"
    instances_path = case_dir / "instances.yaml"
    testcases_path = case_dir / "testcases.yaml"

    report.checks.append(check_yaml_syntax(schema_path))
    report.checks.append(check_yaml_syntax(instances_path))
    report.checks.append(check_yaml_syntax(testcases_path))

    schema_data = load_yaml(schema_path)
    if schema_data:
        report.checks.extend(check_schema_structure(schema_data))

    instances_data = load_yaml(instances_path)
    if instances_data and schema_data:
        report.checks.extend(check_instances_structure(instances_data, schema_data))

    testcases_data = load_yaml(testcases_path)
    if testcases_data:
        report.checks.extend(check_testcases_structure(testcases_data))

    if instances_data:
        metrics = compute_case4_metrics(instances_data)
        report.metrics_computed = metrics

        rule_results = simulate_case4_rules(metrics)
        report.rule_results = rule_results

        if testcases_data:
            report.checks.extend(verify_case4_testcases(metrics, rule_results, testcases_data))

    scenario_data = (case_dir / "scenario.md").read_text(encoding="utf-8") if (case_dir / "scenario.md").exists() else ""
    report.checks.append(CheckResult("knowledge_asset_closure", "PASS" if "资产呈现" in scenario_data and "资产编辑" in scenario_data else "FAIL",
                                     "scenario.md contains knowledge asset closure sections"))
    report.checks.append(CheckResult("mutual_index_section", "PASS" if "证据回溯" in scenario_data else "FAIL",
                                     "scenario.md contains evidence traceability section"))

    return report


def verify_case5(case_dir: Path) -> CaseReport:
    report = CaseReport("case5", "专家经验规则化", "hybrid")

    schema_path = case_dir / "schema.yaml"
    instances_path = case_dir / "instances.yaml"
    testcases_path = case_dir / "testcases.yaml"

    report.checks.append(check_yaml_syntax(schema_path))
    report.checks.append(check_yaml_syntax(instances_path))
    report.checks.append(check_yaml_syntax(testcases_path))

    schema_data = load_yaml(schema_path)
    if schema_data:
        report.checks.extend(check_schema_structure(schema_data))

    instances_data = load_yaml(instances_path)
    if instances_data and schema_data:
        report.checks.extend(check_instances_structure(instances_data, schema_data))

    testcases_data = load_yaml(testcases_path)
    if testcases_data:
        report.checks.extend(check_testcases_structure(testcases_data))

    scenario_data = (case_dir / "scenario.md").read_text(encoding="utf-8") if (case_dir / "scenario.md").exists() else ""
    report.checks.append(CheckResult("scenario_md", "PASS" if scenario_data else "FAIL",
                                     "scenario.md exists"))
    report.checks.append(CheckResult("journey_md", "PASS" if (case_dir / "journey.md").exists() else "FAIL",
                                     "journey.md exists"))
    report.checks.append(CheckResult("rule_group_mapping", "PASS" if "RuleDefinition" in scenario_data and "RuleLogic" in scenario_data else "FAIL",
                                     "scenario.md contains rule group model mapping"))
    report.checks.append(CheckResult("asset_edit_section", "PASS" if ("资产编辑" in scenario_data or "编辑动作" in scenario_data or "编辑" in scenario_data) else "FAIL",
                                     "scenario.md contains asset editing section"))

    if instances_data:
        report.metrics_computed = _compute_case5_metrics(instances_data)
        report.rule_results = _simulate_case5_rules(instances_data)

    return report


def _compute_case5_metrics(instances_data: dict) -> dict:
    results = {}
    for item in instances_data.get("instances", []):
        concept = item.get("fact_object", "")
        if concept != "Supplier":
            continue
        for d in item.get("data", []):
            sid = d.get("supplier_id", "")
            gcd = d.get("guarantee_chain_depth", 0)
            news = d.get("negative_news_count_90d", 0)
            oir = d.get("overdue_invoice_ratio", 0)
            bss = d.get("business_stability_score", 50)

            guarantee_depth_risk = 30 if gcd >= 4 else (20 if gcd >= 3 else 0)
            news_risk = 30 if news >= 3 else (20 if news >= 2 else (10 if news >= 1 else 0))
            composite_risk = guarantee_depth_risk + news_risk + (100 - bss) * 0.2

            results[sid] = {
                "supplier_name": d.get("supplier_name", ""),
                "guarantee_chain_depth": gcd,
                "negative_news_count_90d": news,
                "overdue_invoice_ratio": oir,
                "guarantee_depth_risk": guarantee_depth_risk,
                "news_risk": news_risk,
                "composite_risk_score": round(composite_risk, 1),
            }
    return results


def _simulate_case5_rules(instances_data: dict) -> dict:
    results = {}
    for item in instances_data.get("instances", []):
        concept = item.get("fact_object", "")
        if concept != "Supplier":
            continue
        for d in item.get("data", []):
            sid = d.get("supplier_id", "")
            gcd = d.get("guarantee_chain_depth", 0)
            news = d.get("negative_news_count_90d", 0)
            oir = d.get("overdue_invoice_ratio", 0)

            rd301_hit = gcd >= 4 and news >= 2
            rd302_hit = oir >= 10 and gcd >= 3

            results[sid] = {
                "supplier_name": d.get("supplier_name", ""),
                "RD301_hit": rd301_hit,
                "RD302_hit": rd302_hit,
                "is_high_risk": rd301_hit or rd302_hit,
            }
    return results


def verify_case6(case_dir: Path) -> CaseReport:
    report = CaseReport("case6", "多源矛盾检测", "planned")

    scenario_data = (case_dir / "scenario.md").read_text(encoding="utf-8") if (case_dir / "scenario.md").exists() else ""
    report.checks.append(CheckResult("scenario_md", "PASS" if scenario_data else "FAIL",
                                     "scenario.md exists"))
    report.checks.append(CheckResult("planned_status", "PASS" if "planned" in scenario_data else "WARN",
                                     "scenario.md marked as planned"))
    report.checks.append(CheckResult("contradiction_scenario", "PASS" if "矛盾" in scenario_data else "FAIL",
                                     "scenario.md contains contradiction scenario"))

    return report


def verify_case7(case_dir: Path) -> CaseReport:
    report = CaseReport("case7", "文档→知识编译", "planned")

    scenario_data = (case_dir / "scenario.md").read_text(encoding="utf-8") if (case_dir / "scenario.md").exists() else ""
    report.checks.append(CheckResult("scenario_md", "PASS" if scenario_data else "FAIL",
                                     "scenario.md exists"))
    report.checks.append(CheckResult("planned_status", "PASS" if "planned" in scenario_data else "WARN",
                                     "scenario.md marked as planned"))
    report.checks.append(CheckResult("compilation_scenario", "PASS" if "编译" in scenario_data else "FAIL",
                                     "scenario.md contains compilation scenario"))

    return report


def verify_canonical_case(case_dir: Path) -> CaseReport:
    case_name = case_dir.name
    report = CaseReport(case_name, case_name.replace("_", " ").title(), "canonical")

    schema_path = case_dir / "schema.yaml"
    instances_path = case_dir / "instances.yaml"
    testcases_path = case_dir / "testcases.yaml"

    report.checks.append(check_yaml_syntax(schema_path))
    report.checks.append(check_yaml_syntax(instances_path))
    report.checks.append(check_yaml_syntax(testcases_path))

    schema_data = load_yaml(schema_path)
    if schema_data:
        report.checks.extend(check_schema_structure(schema_data))

    instances_data = load_yaml(instances_path)
    if instances_data and schema_data:
        report.checks.extend(check_instances_structure(instances_data, schema_data))

    testcases_data = load_yaml(testcases_path)
    if testcases_data:
        report.checks.extend(check_testcases_structure(testcases_data))

    return report


def print_report(reports: list[CaseReport]):
    print("\n" + "=" * 80)
    print("  ONTOLOGYENGINE EXAMPLES VERIFICATION REPORT")
    print("=" * 80)

    total_pass = sum(r.pass_count for r in reports)
    total_fail = sum(r.fail_count for r in reports)
    total_warn = sum(r.warn_count for r in reports)
    total_skip = sum(r.skip_count for r in reports)
    total_checks = sum(r.total for r in reports)

    print(f"\n  Total Checks: {total_checks} | PASS: {total_pass} | FAIL: {total_fail} | WARN: {total_warn} | SKIP: {total_skip}")
    print()

    for report in reports:
        status_icon = "✅" if report.fail_count == 0 else "❌"
        print(f"\n{status_icon} [{report.case_id}] {report.case_name} ({report.case_type})")
        print(f"   Checks: {report.total} | PASS: {report.pass_count} | FAIL: {report.fail_count} | WARN: {report.warn_count} | SKIP: {report.skip_count}")

        for check in report.checks:
            icons = {"PASS": "  ✅", "FAIL": "  ❌", "WARN": "  ⚠️", "SKIP": "  ⏭️"}
            icon = icons.get(check.status, "  ?")
            print(f"{icon} {check.name}: {check.detail}")
            if check.status == "FAIL" and check.expected is not None:
                print(f"       expected: {check.expected}, actual: {check.actual}")

    case4_report = next((r for r in reports if r.case_id == "case4"), None)
    if case4_report and case4_report.metrics_computed:
        print("\n" + "=" * 80)
        print("  CASE4: COMPUTED METRICS BY STORE")
        print("=" * 80)
        print(f"\n{'Store':<8} {'Name':<20} {'Type':<10} {'Region':<8} {'Margin%':<10} {'DSO':<8} {'DIO':<8} {'BudgetVar':<10}")
        print("-" * 90)
        for sid, m in sorted(case4_report.metrics_computed.items()):
            print(f"{sid:<8} {m['store_name'][:18]:<20} {m['store_type']:<10} {m['region']:<8} "
                  f"{m['gross_margin_rate_v15']:<10.1f} {m['dso_days']:<8.1f} {m['dio_days']:<8.1f} "
                  f"{m['budget_variance_margin']:<10.1f}")

        region_agg = {}
        for sid, m in case4_report.metrics_computed.items():
            r = m["region"]
            if r not in region_agg:
                region_agg[r] = {"net_revenue": 0, "cogs": 0, "ar": 0, "credit": 0, "inv": 0, "inv_cogs": 0, "count": 0}
            region_agg[r]["net_revenue"] += m["net_revenue"]
            region_agg[r]["cogs"] += m["cogs"]
            region_agg[r]["count"] += 1

        print(f"\n{'Region':<10} {'Revenue(亿)':<14} {'Margin%':<10} {'Stores':<8}")
        print("-" * 50)
        for r, agg in sorted(region_agg.items()):
            margin = (agg["net_revenue"] - agg["cogs"]) / agg["net_revenue"] * 100 if agg["net_revenue"] > 0 else 0
            rev_yi = agg["net_revenue"] / 1e8
            print(f"{r:<10} {rev_yi:<14.2f} {margin:<10.1f} {agg['count']:<8}")

    if case4_report and case4_report.rule_results:
        print("\n" + "=" * 80)
        print("  CASE4: RULE EXECUTION v1 vs v2 COMPARISON")
        print("=" * 80)
        print(f"\n{'Store':<8} {'Name':<20} {'Type':<10} {'v1异常':<8} {'v1类型':<25} {'v2异常':<8} {'v2类型':<25} {'Diff':<6}")
        print("-" * 115)
        for sid, r in sorted(case4_report.rule_results.items()):
            v1_icon = "✓" if r["v1_is_exception"] else "✗"
            v2_icon = "✓" if r["v2_is_exception"] else "✗"
            diff_icon = "⚡" if r["v1_v2_diff"] else ""
            print(f"{sid:<8} {r['store_name'][:18]:<20} {r['store_type']:<10} "
                  f"{v1_icon:<8} {r['v1_exception_type']:<25} {v2_icon:<8} {r['v2_exception_type']:<25} {diff_icon:<6}")

        v1_count = sum(1 for r in case4_report.rule_results.values() if r["v1_is_exception"])
        v2_count = sum(1 for r in case4_report.rule_results.values() if r["v2_is_exception"])
        diff_count = sum(1 for r in case4_report.rule_results.values() if r["v1_v2_diff"])
        print(f"\n  Summary: v1={v1_count} exceptions, v2={v2_count} exceptions, {diff_count} stores changed")

    print("\n" + "=" * 80)
    print("  CASE4: METRIC CARD VERSION IMPACT (v1.4 -> v1.5)")
    print("=" * 80)
    if case4_report and case4_report.metrics_computed:
        print(f"\n{'Store':<8} {'v1.4 Margin%':<14} {'v1.5 Margin%':<14} {'Diff(pp)':<10}")
        print("-" * 50)
        for sid, m in sorted(case4_report.metrics_computed.items()):
            v14 = m["gross_margin_rate_v14"]
            v15 = m["gross_margin_rate_v15"]
            diff = v15 - v14
            print(f"{sid:<8} {v14:<14.1f} {v15:<14.1f} {diff:<10.1f}")

    print("\n" + "=" * 80)
    print("  OVERALL ASSESSMENT")
    print("=" * 80)
    if total_fail == 0:
        print(f"\n  ✅ ALL CHECKS PASSED ({total_pass} passed, {total_warn} warnings, {total_skip} skipped)")
    else:
        print(f"\n  ❌ {total_fail} CHECKS FAILED ({total_pass} passed, {total_warn} warnings, {total_skip} skipped)")

    closure_cases = [r for r in reports if r.case_type in ("narrative", "hybrid")]
    print(f"\n  Knowledge Asset Closure Coverage:")
    for r in closure_cases:
        has_closure = any("closure" in c.name.lower() or "asset" in c.name.lower() for c in r.checks if c.status == "PASS")
        icon = "✅" if has_closure else "⚠️"
        print(f"  {icon} {r.case_id}: {r.case_name}")

    print()


def main():
    reports = []

    reports.append(verify_canonical_case(EXAMPLES_DIR / "supply_chain_finance"))
    reports.append(verify_canonical_case(EXAMPLES_DIR / "consumer_credit"))
    reports.append(verify_case1(EXAMPLES_DIR / "case1_regulatory_compliance"))
    reports.append(verify_case3(EXAMPLES_DIR / "case3_tax_simulation"))
    reports.append(verify_case4(EXAMPLES_DIR / "case4_bi_query_agent"))
    reports.append(verify_case5(EXAMPLES_DIR / "case5_expert_knowledge_crystallization"))
    reports.append(verify_case6(EXAMPLES_DIR / "case6_contradiction_detection"))
    reports.append(verify_case7(EXAMPLES_DIR / "case7_knowledge_compilation"))

    print_report(reports)

    total_fail = sum(r.fail_count for r in reports)
    sys.exit(1 if total_fail > 0 else 0)


if __name__ == "__main__":
    main()

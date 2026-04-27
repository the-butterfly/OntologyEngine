#!/usr/bin/env python3
"""
Case4 Visualization Data Generator

Generates G6-compatible knowledge graph, metric card version diff,
and rule version impact visualization data for case4.

Usage:
    python examples/case4_bi_query_agent/generate_visualization.py
"""

import json
import yaml
from pathlib import Path

CASE_DIR = Path(__file__).parent


def generate_knowledge_graph():
    """Generate G6-compatible knowledge graph for case4."""
    instances_data = yaml.safe_load(open(CASE_DIR / "instances.yaml", encoding="utf-8"))
    schema_data = yaml.safe_load(open(CASE_DIR / "schema.yaml", encoding="utf-8"))

    nodes = []
    edges = []

    for item in instances_data.get("instances", []):
        concept = item.get("fact_object", "")
        for d in item.get("data", []):
            entity_id = _get_id(concept, d)
            if not entity_id:
                continue

            label = _get_label(concept, d)
            node_type = _get_node_type(concept)

            nodes.append({
                "id": entity_id,
                "type": node_type,
                "data": {
                    "label": label,
                    "concept": concept,
                    "region": d.get("region", ""),
                    "store_type": d.get("store_type", ""),
                    "primary_category": d.get("primary_category", ""),
                },
            })

            for key, value in d.items():
                if isinstance(value, dict) and any(k.endswith("_id") for k in value):
                    target_id = next((v for k, v in value.items() if k.endswith("_id")), None)
                    if target_id:
                        edges.append({
                            "id": f"edge-{entity_id}-{target_id}-{key}",
                            "source": entity_id,
                            "target": target_id,
                            "type": "relation",
                            "data": {"relation_name": key},
                        })

    for metric in schema_data.get("analytical_elements", {}).get("metrics", []):
        mid = metric.get("id", "")
        nodes.append({
            "id": f"metric.{mid}",
            "type": "metric",
            "data": {
                "label": metric.get("name", mid),
                "metric_type": metric.get("type", ""),
                "unit": metric.get("unit", ""),
            },
        })

        for dep in metric.get("dependencies", []):
            edges.append({
                "id": f"edge-metric-{dep}-{mid}",
                "source": f"metric.{dep}",
                "target": f"metric.{mid}",
                "type": "metric_dep",
                "data": {"dependency": dep},
            })

    for rd in schema_data.get("business_logic", {}).get("rule_definitions", []):
        rid = rd.get("id", "")
        nodes.append({
            "id": f"rule.{rid}",
            "type": "rule",
            "data": {
                "label": rd.get("name", rid),
                "rule_type": rd.get("rule_type", ""),
                "priority": rd.get("priority", 0),
            },
        })
        for inp in rd.get("inputs", []):
            if inp.get("type") == "metric":
                edges.append({
                    "id": f"edge-rule-input-{inp['id']}-{rid}",
                    "source": f"metric.{inp['id']}",
                    "target": f"rule.{rid}",
                    "type": "rule_input",
                    "data": {"input_name": inp.get("name", "")},
                })

    graph = {
        "schema_id": "space.ops_bi_q2",
        "graph_type": "full",
        "nodes": nodes,
        "edges": edges,
        "layout_config": {
            "type": "dagre",
            "rankdir": "LR",
            "nodesep": 50,
            "ranksep": 80,
        },
        "metadata": {
            "entity_count": sum(1 for n in nodes if n["type"] == "entity"),
            "relation_count": sum(1 for e in edges if e["type"] == "relation"),
            "metric_count": sum(1 for n in nodes if n["type"] == "metric"),
            "rule_count": sum(1 for n in nodes if n["type"] == "rule"),
        },
    }

    return graph


def generate_metric_version_diff():
    """Generate metric card version diff visualization data."""
    return {
        "metric_id": "gross_margin_rate",
        "diffs": [
            {
                "from_version": "v1.4",
                "to_version": "v1.5",
                "formula": {
                    "from": "(gross_sales - cogs) / gross_sales",
                    "to": "(net_revenue - cogs) / net_revenue",
                },
                "change_reason": "统一经营月报与财务口径，扣除退货和折让",
                "impact_by_store": [
                    {"store_id": "SH-001", "store_name": "上海南京东路旗舰店", "v14": 45.0, "v15": 41.5, "diff_pp": -3.5},
                    {"store_id": "SH-014", "store_name": "上海浦东联洋店", "v14": 48.7, "v15": 46.0, "diff_pp": -2.7},
                    {"store_id": "HZ-003", "store_name": "杭州武林广场店", "v14": 44.6, "v15": 41.7, "diff_pp": -2.9},
                    {"store_id": "BJ-002", "store_name": "北京国贸旗舰店", "v14": 42.8, "v15": 38.4, "diff_pp": -4.4},
                    {"store_id": "BJ-009", "store_name": "北京望京店", "v14": 39.6, "v15": 35.0, "diff_pp": -4.6},
                    {"store_id": "EC-001", "store_name": "天猫旗舰店", "v14": 51.6, "v15": 49.0, "diff_pp": -2.6},
                ],
                "regional_impact": [
                    {"region": "华东", "v14": 45.7, "v15": 43.2, "diff_pp": -2.5},
                    {"region": "华南", "v14": 42.5, "v15": 40.8, "diff_pp": -1.7},
                    {"region": "华北", "v14": 39.8, "v15": 37.1, "diff_pp": -2.7},
                    {"region": "电商", "v14": 51.2, "v15": 49.0, "diff_pp": -2.2},
                ],
            },
        ],
    }


def generate_rule_impact_sankey():
    """Generate rule version impact Sankey diagram data."""
    return {
        "title": "规则版本 v1 → v2 对异常门店的影响",
        "nodes": [
            {"id": "v1_total", "label": "v1 异常门店", "value": 3},
            {"id": "v2_kept", "label": "v2 保留异常", "value": 1},
            {"id": "v2_removed", "label": "v2 移出异常", "value": 2},
            {"id": "SH-014", "label": "SH-014\n浦东联洋", "value": 1},
            {"id": "NJ-007", "label": "NJ-007\n南京新街口", "value": 1},
            {"id": "NB-012", "label": "NB-012\n宁波天一", "value": 1},
            {"id": "HIGH_MARGIN_SLOW_CASH", "label": "高毛利慢回款", "value": 3},
            {"id": "direct_threshold", "label": "直营DSO>60", "value": 1},
            {"id": "franchise_threshold", "label": "加盟DSO>60(v1)", "value": 2},
            {"id": "franchise_new_threshold", "label": "加盟DSO>75(v2)", "value": 0},
        ],
        "links": [
            {"source": "v1_total", "target": "v2_kept", "value": 1, "reason": "直营门店阈值不变"},
            {"source": "v1_total", "target": "v2_removed", "value": 2, "reason": "加盟门店阈值调整"},
            {"source": "SH-014", "target": "HIGH_MARGIN_SLOW_CASH", "value": 1},
            {"source": "NJ-007", "target": "HIGH_MARGIN_SLOW_CASH", "value": 1},
            {"source": "NB-012", "target": "HIGH_MARGIN_SLOW_CASH", "value": 1},
            {"source": "SH-014", "target": "direct_threshold", "value": 1, "dso": 82},
            {"source": "NJ-007", "target": "franchise_threshold", "value": 1, "dso": 68},
            {"source": "NB-012", "target": "franchise_threshold", "value": 1, "dso": 65},
            {"source": "v2_kept", "target": "direct_threshold", "value": 1, "reason": "DSO=82>60"},
            {"source": "v2_removed", "target": "franchise_new_threshold", "value": 0, "reason": "DSO=68,65均<75"},
        ],
        "summary": {
            "v1_exception_count": 3,
            "v2_exception_count": 1,
            "removed_count": 2,
            "removal_reason": "加盟门店DSO阈值从60天调整为75天",
        },
    }


def _get_id(concept: str, data: dict) -> str | None:
    id_fields = {
        "Store": "store_id",
        "MonthlySales": "record_id",
        "ARAging": "aging_id",
        "InventorySnapshot": "snapshot_id",
    }
    field = id_fields.get(concept)
    if field and field in data:
        return data[field]
    for k, v in data.items():
        if k.endswith("_id") or k.endswith("_no"):
            if isinstance(v, str) and v:
                return v
    return None


def _get_label(concept: str, data: dict) -> str:
    if concept == "Store":
        return data.get("store_name", data.get("store_id", ""))
    elif concept == "MonthlySales":
        return f"Sales-{data.get('period', '')}"
    elif concept == "ARAging":
        return f"AR-{data.get('period', '')}"
    elif concept == "InventorySnapshot":
        return f"Inv-{data.get('period', '')}"
    return _get_id(concept, data) or ""


def _get_node_type(concept: str) -> str:
    return "entity"


def main():
    output_dir = CASE_DIR / "visualization_data"
    output_dir.mkdir(exist_ok=True)

    kg = generate_knowledge_graph()
    with open(output_dir / "knowledge_graph.json", "w", encoding="utf-8") as f:
        json.dump(kg, f, ensure_ascii=False, indent=2)
    print(f"Knowledge graph: {len(kg['nodes'])} nodes, {len(kg['edges'])} edges")

    diff = generate_metric_version_diff()
    with open(output_dir / "metric_version_diff.json", "w", encoding="utf-8") as f:
        json.dump(diff, f, ensure_ascii=False, indent=2)
    print(f"Metric version diff: {len(diff['diffs'])} diffs")

    sankey = generate_rule_impact_sankey()
    with open(output_dir / "rule_impact_sankey.json", "w", encoding="utf-8") as f:
        json.dump(sankey, f, ensure_ascii=False, indent=2)
    print(f"Rule impact Sankey: {len(sankey['nodes'])} nodes, {len(sankey['links'])} links")

    print(f"\nAll visualization data written to {output_dir}/")


if __name__ == "__main__":
    main()

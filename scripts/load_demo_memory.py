"""Load demo memory data into a space for visualization testing.

Usage:
    python scripts/load_demo_memory.py [--space-id SPACE_ID] [--api-base URL]

If --space-id is not provided, creates a new space called "Demo: TechNova Knowledge Graph".
If --api-base is not provided, defaults to http://localhost:8000.
"""

import argparse
import json
import sys
import time

try:
    import requests
except ImportError:
    print("requests is required: pip install requests")
    sys.exit(1)


def create_space(api_base: str, name: str) -> str:
    r = requests.post(f"{api_base}/v1/spaces", json={"name": name, "description": "Demo space for visualization testing"})
    d = r.json()
    if d.get("success"):
        data = d.get("data", {})
        return data.get("id") or data.get("space_id")
    r2 = requests.get(f"{api_base}/v1/spaces")
    for s in r2.json().get("data", []):
        if s.get("name") == name:
            return s.get("id") or s.get("space_id")
    raise Exception(f"Failed to create space: {d}")


def remember(api_base: str, space_id: str, content: str, memory_type: str = "entity",
             tags: dict = None, confidence: float = 0.9, created_by: str = "demo") -> dict:
    payload = {
        "content": content,
        "memory_type": memory_type,
        "confidence": confidence,
        "created_by": created_by,
    }
    if tags:
        payload["tags"] = tags
    r = requests.post(f"{api_base}/v1/spaces/{space_id}/memory/remember", json=payload)
    d = r.json()
    if not d.get("success"):
        print(f"  WARNING: remember failed: {d.get('error', {}).get('message', d)}")
        return {}
    return d.get("data", {})


def consolidate(api_base: str, space_id: str) -> dict:
    r = requests.post(f"{api_base}/v1/spaces/{space_id}/memory/consolidate", json={})
    d = r.json()
    return d.get("data", {})


def reflect(api_base: str, space_id: str, query: str) -> dict:
    r = requests.post(f"{api_base}/v1/spaces/{space_id}/memory/reflect", json={"query": query})
    d = r.json()
    return d.get("data", {})


def correct(api_base: str, space_id: str, node_id: str, corrected_text: str, reason: str = "更新") -> dict:
    r = requests.patch(f"{api_base}/v1/spaces/{space_id}/memory/{node_id}/correct", json={
        "corrected_text": corrected_text,
        "reason": reason,
    })
    d = r.json()
    return d.get("data", {})


def get_graph_stats(api_base: str, space_id: str) -> dict:
    r = requests.get(f"{api_base}/v1/spaces/{space_id}/memory/graph", params={"node_limit": 1000, "edge_limit": 1000})
    d = r.json()
    data = d.get("data", {})
    return {
        "nodes": len(data.get("nodes", [])),
        "edges": len(data.get("edges", [])),
        "metadata": data.get("metadata", {}),
    }


def load_demo_data(api_base: str, space_id: str):
    print(f"Loading demo data into space {space_id}...")

    print("\n[Phase 1] Multi-type ingestion...")
    remember(api_base, space_id, "TechNova公司总部位于深圳南山区", "entity", {"domain": "company", "location": "深圳"}, 0.95)
    remember(api_base, space_id, "TechNova成立于2020年，是一家专注于AI的科技公司", "observation", {"domain": "company", "founding": "2020"}, 0.9)
    remember(api_base, space_id, "王芳是TechNova技术负责人，拥有10年架构经验", "entity", {"domain": "person", "role": "CTO"}, 0.85)
    remember(api_base, space_id, "王芳主导架构迁移到CloudGroup平台", "observation", {"domain": "architecture", "migration": "CloudGroup"}, 0.8)
    remember(api_base, space_id, "CloudGroup平台底层使用Kubernetes编排容器化服务", "observation", {"domain": "infrastructure", "platform": "Kubernetes"}, 0.85)
    remember(api_base, space_id, "TechNova架构变更须经安全委员会审批", "rule", {"domain": "governance", "process": "approval"}, 0.9)
    remember(api_base, space_id, "如果API错误率超过1%则触发告警通知运维团队", "constraint", {"domain": "operations", "metric": "error_rate", "threshold": "1%"}, 0.9)
    remember(api_base, space_id, "TechNova的核心业务系统采用微服务架构，包含用户服务、订单服务、支付服务三大模块", "mental_model", {"domain": "architecture", "pattern": "microservices"}, 0.75)
    remember(api_base, space_id, "张明是TechNova的CEO，曾在Google工作8年", "entity", {"domain": "person", "role": "CEO"}, 0.9)
    remember(api_base, space_id, "TechNova 2024年营收达到5亿元，同比增长30%", "observation", {"domain": "finance", "year": "2024"}, 0.85)
    remember(api_base, space_id, "供应商准入规则：信用评分>=70且无重大违约记录", "rule", {"domain": "supply_chain", "type": "access_control"}, 0.95)
    remember(api_base, space_id, "TechNova采用GitFlow分支管理策略，所有合并须经Code Review", "procedure", {"domain": "engineering", "process": "code_review"}, 0.8)

    print("[Phase 2] Contradiction injection...")
    remember(api_base, space_id, "TechNova总部在上海浦东新区", "entity", {"domain": "company", "location": "上海"}, 0.7)

    print("[Phase 3] Consolidation...")
    consolidate(api_base, space_id)
    time.sleep(1)

    print("[Phase 4] Version correction to create SUPERSEDES edges...")
    r = requests.post(f"{api_base}/v1/spaces/{space_id}/memory/recall", json={
        "query": "TechNova总部",
        "max_results": 5,
        "include_evidence": True,
    })
    recall_data = r.json().get("data", {})
    results = recall_data.get("results", [])
    if results:
        first_id = results[0].get("id")
        if first_id:
            correct(api_base, space_id, first_id, "TechNova总部位于深圳前海区（2024年搬迁）", "地址更新")

    print("[Phase 5] Reflection to create CONTRADICTS/SUPPORTS edges...")
    reflect(api_base, space_id, "TechNova技术架构与组织结构分析")

    print("[Phase 6] Additional data...")
    remember(api_base, space_id, "TechNova的供应链包含200+供应商，覆盖硬件、软件、云服务三大类", "observation", {"domain": "supply_chain", "scale": "200+"}, 0.7)
    remember(api_base, space_id, "核心供应商需通过ISO9001认证和年度审计", "constraint", {"domain": "supply_chain", "compliance": "ISO9001"}, 0.85)
    remember(api_base, space_id, "TechNova使用Prometheus+Grafana监控生产环境", "procedure", {"domain": "operations", "tools": "Prometheus+Grafana"}, 0.8)
    remember(api_base, space_id, "李华是运维团队负责人，负责7x24小时系统稳定性", "entity", {"domain": "person", "role": "Ops Lead"}, 0.75)

    print("[Phase 7] Final consolidation...")
    consolidate(api_base, space_id)

    stats = get_graph_stats(api_base, space_id)
    print(f"\n{'='*50}")
    print(f"Demo data loaded successfully!")
    print(f"  Nodes: {stats['nodes']}")
    print(f"  Edges: {stats['edges']}")
    print(f"  Metadata: {json.dumps(stats['metadata'], ensure_ascii=False, indent=2)}")
    print(f"{'='*50}")
    print(f"\nAccess the Knowledge Explorer at:")
    print(f"  http://localhost:3001/spaces/{space_id}/explorer")


def main():
    parser = argparse.ArgumentParser(description="Load demo memory data")
    parser.add_argument("--space-id", default=None, help="Space ID (creates new if not provided)")
    parser.add_argument("--api-base", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()

    space_id = args.space_id
    if not space_id:
        space_id = create_space(args.api_base, "Demo: TechNova Knowledge Graph")
        print(f"Created space: {space_id}")

    load_demo_data(args.api_base, space_id)


if __name__ == "__main__":
    main()

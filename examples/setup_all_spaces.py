#!/usr/bin/env python3
"""Business script to construct all example graph spaces via OntologyEngine API.

This script demonstrates the intended usage pattern:
  1. Start the OntologyEngine API server (clean, no pre-loaded data)
  2. Run this business script to construct graph space assets
  3. Assets become available for retrieval and visualization

Usage:
    # Start the server first
    python -m ontology_engine.api.server

    # Then run this script to construct all example spaces
    python examples/setup_all_spaces.py

    # Or construct a specific case
    python examples/setup_all_spaces.py --case supply_chain_finance
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API_BASE = "http://localhost:8000"

EXAMPLE_CASES = [
    {
        "name": "供应链金融授信",
        "description": "供应链金融核心企业授信场景，含担保链图指标和规则分离设计",
        "domain": "supply_chain_finance",
        "schema_path": "examples/supply_chain_finance/schema.yaml",
        "instances_path": "examples/supply_chain_finance/instances.yaml",
    },
    {
        "name": "个人消费信贷",
        "description": "个人消费信贷评分场景，含L3指标、产品分流和一票否决逻辑",
        "domain": "consumer_credit",
        "schema_path": "examples/consumer_credit/schema.yaml",
        "instances_path": "examples/consumer_credit/instances.yaml",
    },
    {
        "name": "Circular 23 合规检查",
        "description": "银保监会23号文合规场景，含白名单核验、发票真实性、担保限额、风险集中度四项检查",
        "domain": "regulatory_compliance",
        "schema_path": "examples/case1_regulatory_compliance/schema.yaml",
        "instances_path": "examples/case1_regulatory_compliance/instances.yaml",
    },
    {
        "name": "亚太区税务架构分析",
        "description": "转让定价+支柱二+BEPS风险评估场景，含多辖区子公司和税收协定",
        "domain": "tax_simulation",
        "schema_path": "examples/case3_tax_simulation/schema.yaml",
        "instances_path": "examples/case3_tax_simulation/instances.yaml",
    },
    {
        "name": "零售经营分析问数",
        "description": "百货零售经营健康度复盘场景，含指标卡版本化和规则包版本化",
        "domain": "bi_query_agent",
        "schema_path": "examples/case4_bi_query_agent/schema.yaml",
        "instances_path": "examples/case4_bi_query_agent/instances.yaml",
    },
    {
        "name": "专家经验规则化",
        "description": "专家观察到候选规则到发布规则的知识沉淀闭环场景",
        "domain": "expert_knowledge_crystallization",
        "schema_path": "examples/case5_expert_knowledge_crystallization/schema.yaml",
        "instances_path": "examples/case5_expert_knowledge_crystallization/instances.yaml",
    },
]


def _resolve_path(path_str: str) -> str:
    p = Path(path_str)
    if not p.is_absolute():
        p = Path.cwd() / p
    return str(p.resolve())


async def wait_for_server(client: httpx.AsyncClient, max_retries: int = 30, interval: float = 1.0) -> bool:
    for i in range(max_retries):
        try:
            resp = await client.get("/health")
            if resp.status_code == 200:
                print(f"  ✅ Server is ready (attempt {i + 1})")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        if i < max_retries - 1:
            await asyncio.sleep(interval)
    return False


async def find_existing_space(client: httpx.AsyncClient, domain: str) -> str | None:
    resp = await client.get("/v1/spaces")
    if resp.status_code != 200:
        return None
    data = resp.json().get("data", [])
    for space in data:
        if space.get("domain") == domain and space.get("space_type") == "management":
            return space.get("id")
    return None


async def setup_case(client: httpx.AsyncClient, case: dict[str, Any]) -> bool:
    domain = case["domain"]
    name = case["name"]
    print(f"\n{'=' * 60}")
    print(f"  Setting up: {name} ({domain})")
    print(f"{'=' * 60}")

    schema_path = _resolve_path(case["schema_path"])
    instances_path = _resolve_path(case["instances_path"])

    if not Path(schema_path).exists():
        print(f"  ⚠️  Schema file not found: {schema_path}, skipping")
        return False

    existing_id = await find_existing_space(client, domain)
    if existing_id:
        print(f"  📋 Found existing space: {existing_id}")
        space_id = existing_id
    else:
        print(f"  📝 Creating management space...")
        resp = await client.post("/v1/spaces", json={
            "name": name,
            "description": case["description"],
            "domain": domain,
            "create_default_view": True,
        })
        if resp.status_code not in (200, 201):
            print(f"  ❌ Failed to create space: {resp.text}")
            return False
        space_id = resp.json()["data"]["id"]
        print(f"  ✅ Created space: {space_id}")

    print(f"  📂 Loading schema from {schema_path}...")
    resp = await client.post(
        f"/v1/spaces/{space_id}/schema/load-yaml",
        json={"yaml_path": schema_path, "overwrite": True},
    )
    if resp.status_code not in (200, 201):
        print(f"  ❌ Failed to load schema: {resp.text}")
        return False
    schema_data = resp.json().get("data", {})
    loaded = schema_data.get("loaded", {})
    print(f"  ✅ Schema loaded: L1={loaded.get('L1_fact_objects', 0)}, "
          f"L2={loaded.get('L2_categorizations', 0)}, "
          f"L3={loaded.get('L3_analytical_elements', 0)}, "
          f"L4_RD={loaded.get('L4_rule_definitions', 0)}, "
          f"L4_RL={loaded.get('L4_rule_logics', 0)}")

    if Path(instances_path).exists():
        print(f"  📂 Loading instances from {instances_path}...")
        resp = await client.post(
            f"/v1/spaces/{space_id}/instances/load-yaml",
            json={"yaml_path": instances_path, "overwrite": True},
        )
        if resp.status_code not in (200, 201):
            print(f"  ❌ Failed to load instances: {resp.text}")
            return False
        inst_data = resp.json().get("data", {})
        print(f"  ✅ Instances loaded: {inst_data.get('added_entities', 0)} entities, "
              f"{inst_data.get('added_relations', 0)} relations")
    else:
        print(f"  ⚠️  No instances file: {instances_path}")

    print(f"  🔄 Activating space...")
    resp = await client.post(f"/v1/spaces/{space_id}/activate")
    if resp.status_code not in (200, 201):
        print(f"  ❌ Failed to activate: {resp.text}")
        return False
    activate_data = resp.json().get("data", {})
    print(f"  ✅ Space activated: status={activate_data.get('status')}, view_id={activate_data.get('view_id')}")

    return True


async def main() -> None:
    parser = argparse.ArgumentParser(description="Setup OntologyEngine example graph spaces")
    parser.add_argument("--case", type=str, default=None,
                        help="Only setup a specific case by domain name (e.g. supply_chain_finance)")
    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE,
                        help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--wait", type=float, default=30.0,
                        help="Max seconds to wait for server to be ready (default: 30)")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")

    cases = EXAMPLE_CASES
    if args.case:
        cases = [c for c in EXAMPLE_CASES if c["domain"] == args.case]
        if not cases:
            print(f"❌ Unknown case domain: {args.case}")
            print(f"   Available: {', '.join(c['domain'] for c in EXAMPLE_CASES)}")
            sys.exit(1)

    print("🚀 OntologyEngine Example Space Setup")
    print(f"   API: {api_base}")
    print(f"   Cases: {len(cases)}")

    async with httpx.AsyncClient(timeout=60.0, base_url=api_base) as client:
        print("\n⏳ Waiting for API server...")
        if not await wait_for_server(client, max_retries=int(args.wait)):
            print("❌ Server not available. Please start the server first:")
            print("   python -m ontology_engine.api.server")
            sys.exit(1)

        results = []
        for case in cases:
            ok = await setup_case(client, case)
            results.append((case["domain"], ok))

    print(f"\n{'=' * 60}")
    print("📊 Setup Summary")
    print(f"{'=' * 60}")
    success = 0
    for domain, ok in results:
        status = "✅ SUCCESS" if ok else "❌ FAILED"
        print(f"  {domain:40s} {status}")
        if ok:
            success += 1
    print(f"\n  Total: {success}/{len(results)} successful")

    if success < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

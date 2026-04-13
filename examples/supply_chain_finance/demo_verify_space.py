#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OntologyEngine Space Verification Demo

使用 SemanticSpace API 验证 demo_space.json 的完整功能：
1. 从 JSON 文件加载 Space
2. 通过 API 创建并激活 Space
3. 执行规则分析和 What-If 模拟

运行方法：
    python -m examples.supply_chain_finance.demo_verify_space
"""

import asyncio
import httpx


BASE_URL = "http://localhost:8000"


async def wait_for_server(timeout: int = 10) -> bool:
    """Wait for server to be ready."""
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{BASE_URL}/health")
                if resp.status_code == 200:
                    return True
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return False


async def main():
    print("=" * 70)
    print("  OntologyEngine Space Verification Demo")
    print("=" * 70)

    # Check server
    print("\n📦 Checking server...")
    if not await wait_for_server():
        print("   ❌ Server not responding at", BASE_URL)
        print("   请先启动服务: uvicorn ontology_engine.api.server:app --reload --port 8000")
        return
    print("   ✅ Server is ready")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:

        # Step 1: Load demo_space.json
        print("\n📥 Step 1: 加载 demo_space.json")
        resp = await client.post(
            "/v1/management/spaces/load-from-json",
            json={
                "json_path": "examples/supply_chain_finance/demo_space.json",
                "space_id": "space_supply_chain_demo"
            }
        )
        if resp.status_code != 200:
            print(f"   ❌ 加载失败: {resp.text}")
            return

        data = resp.json()["data"]
        space_id = data["id"]
        view_id = data["view_id"]
        print(f"   ✅ Space 创建成功: {space_id}")
        print(f"      - L1 entities: {data['loaded']['L1_fact_objects']}")
        print(f"      - L2 categorizations: {data['loaded']['L2_categorizations']}")
        print(f"      - L3 analytical elements: {data['loaded']['L3_analytical_elements']}")
        print(f"      - L4 rule definitions: {data['loaded']['L4_rule_definitions']}")
        print(f"      - L4 rule logics: {data['loaded']['L4_rule_logics']}")
        print(f"      - Entities: {data['loaded']['entities']}")
        print(f"      - Relations: {data['loaded']['relations']}")

        # Step 2: Activate space (sync to consumption view)
        print("\n🚀 Step 2: 激活 Space")
        resp = await client.post(f"/v1/management/spaces/{space_id}/activate")
        if resp.status_code != 200:
            print(f"   ❌ 激活失败: {resp.text}")
            return
        print(f"   ✅ Space 激活成功")

        # Step 3: List entities in consumption view
        print("\n📋 Step 3: 列出消费视图中的实体")
        resp = await client.get(f"/v1/consumption/views/{view_id}/entities")
        if resp.status_code != 200:
            print(f"   ❌ 获取实体失败: {resp.text}")
            return

        entities = resp.json()["data"]
        print(f"   共有 {len(entities)} 个实体:")
        for e in entities:
            print(f"      - {e['entity_id']}: {e.get('company_name', 'N/A')} ({e.get('_concept')})")

        # Step 4: Get rule dependency graph
        print("\n🔗 Step 4: 获取规则依赖图")
        resp = await client.get(f"/v1/consumption/views/{view_id}/rules/dependency-graph")
        if resp.status_code != 200:
            print(f"   ❌ 获取依赖图失败: {resp.text}")
            return

        dep_data = resp.json()["data"]
        print(f"   ✅ 规则依赖图:")
        print(f"      - 总规则数: {dep_data['stats']['total_rules']}")
        print(f"      - 依赖边: {dep_data['stats']['dependency_edges']}")
        print(f"      - 互斥对: {dep_data['stats']['exclusion_pairs']}")
        print(f"      - 执行顺序: {' → '.join(dep_data['execution_order'])}")

        # Step 5: Execute analyze on SUP_001
        print("\n⚙️ Step 5: 对 东方钢铁(SUP_001) 执行信用评估")
        resp = await client.post(
            f"/v1/consumption/views/{view_id}/execute/analyze",
            json={
                "entity_id": "SUP_001",
                "dimension": "credit_assessment",
                "include_trace": True
            }
        )
        if resp.status_code != 200:
            print(f"   ❌ 执行分析失败: {resp.text}")
            return

        result = resp.json()["data"]
        print(f"   ✅ 分析完成:")
        print(f"      - 决策: {result['decision']}")
        print(f"      - 执行规则: {len(result['execution_path'])} 条")
        print(f"      - 跳过规则: {len(result['skipped_rules'])} 条")

        # Show steps
        if result.get("steps"):
            print(f"\n   执行步骤:")
            for step in result["steps"]:
                status_icon = "✅" if step["status"] == "passed" else "⏭️" if step["status"] == "skipped" else "❌"
                print(f"      {status_icon} [{step['step']}] {step['rule_name']}: {step['explanation']}")

        # Final outputs
        if result.get("final_outputs"):
            print(f"\n   最终输出:")
            for k, v in result["final_outputs"].items():
                print(f"      - {k}: {v}")

        # Step 6: What-If simulation
        print("\n🔄 Step 6: What-If 模拟 - 将年营收降低")
        resp = await client.post(
            f"/v1/consumption/views/{view_id}/execute/simulate",
            json={
                "entity_id": "SUP_001",
                "dimension": "credit_assessment",
                "overrides": {
                    "annual_revenue": {"value": 100000000}  # 从 200000000 降到 100000000
                },
                "include_trace": True
            }
        )
        if resp.status_code != 200:
            print(f"   ❌ What-If 模拟失败: {resp.text}")
            return

        sim_result = resp.json()["data"]
        print(f"   ✅ 模拟完成:")
        print(f"      - 基线决策: {sim_result.get('baseline_outputs', {}).get('decision', 'N/A')}")
        print(f"      - 模拟决策: {sim_result.get('decision', 'N/A')}")

        # Show diffs
        if sim_result.get("comparison", {}).get("diffs"):
            print(f"\n   变化字段:")
            for diff in sim_result["comparison"]["diffs"]:
                print(f"      - {diff['field']}: {diff['baseline_value']} → {diff['simulated_value']} ({diff['change_type']})")

        # Step 7: Get rules for entity
        print("\n📌 Step 7: 获取 SUP_001 的适用规则")
        resp = await client.get(
            f"/v1/consumption/views/{view_id}/rules/for-entity/SUP_001"
        )
        if resp.status_code != 200:
            print(f"   ❌ 获取适用规则失败: {resp.text}")
            return

        rules_data = resp.json()["data"]
        print(f"   ✅ 适用规则: {rules_data['total']} 条")
        for rule in rules_data.get("applicable_rules", []):
            print(f"      - {rule['name']} ({rule['id']})")
            print(f"        类型: {rule['rule_type']}, 优先级: {rule['priority']}")
            print(f"        输入: {[e.get('name') or e.get('id') for e in rule.get('input_elements', [])]}")
            print(f"        输出: {[e.get('name') or e.get('id') for e in rule.get('output_elements', [])]}")
            print(f"        匹配逻辑: {len(rule.get('matching_logics', []))} 个")

        # Step 8: Schema visualization
        print("\n📊 Step 8: 获取 Schema 可视化数据")
        resp = await client.get(
            f"/v1/consumption/views/{view_id}/visualize/schema-graph",
            params={"layer_filter": "L1,L2,L3,L4"}
        )
        if resp.status_code != 200:
            print(f"   ❌ 获取可视化数据失败: {resp.text}")
            return

        viz_data = resp.json()["data"]
        print(f"   ✅ 可视化数据:")
        print(f"      - 节点总数: {len(viz_data['nodes'])}")
        print(f"      - 边总数: {viz_data['metadata']['edge_count']}")
        print(f"      - 实体节点: {viz_data['metadata']['entity_count']}")
        print(f"      - 分类节点: {viz_data['metadata']['category_count']}")
        print(f"      - 指标节点: {viz_data['metadata']['metric_count']}")
        print(f"      - 规则节点: {viz_data['metadata']['rule_count']}")

    print("\n" + "=" * 70)
    print("  验证完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

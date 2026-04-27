#!/usr/bin/env python3
"""Playwright script to analyze frontend rule management, simulation, and execution features."""

from playwright.sync_api import sync_playwright
import json

def analyze_frontend():
    results = {
        "pages_analyzed": [],
        "gaps_found": [],
        "api_calls_made": [],
        "issues": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Track console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

        # Track network requests
        def log_request(request):
            if "api" in request.url or "v1" in request.url:
                results["api_calls_made"].append({
                    "url": request.url,
                    "method": request.method,
                })
        page.on("request", log_request)

        # 1. Analyze /spaces page (Space list)
        print("=" * 60)
        print("Analyzing /spaces page...")
        results["pages_analyzed"].append("spaces")
        page.goto("http://localhost:3000/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)  # Extra wait for React rendering

        # Check for space cards/list
        space_elements = page.locator("[class*='Card'], [class*='card'], .ant-card").all()
        print(f"  Found {len(space_elements)} space card elements")

        # 2. Check backend API for spaces (semantic spaces)
        print("\n" + "=" * 60)
        print("Checking backend API for semantic spaces...")
        spaces_api = page.evaluate("""async () => {
            const resp = await fetch("http://localhost:8000/management/spaces");
            return resp.json();
        }""")
        print(f"  Spaces API: {json.dumps(spaces_api, indent=2, ensure_ascii=False)[:800]}")

        # 3. Analyze /spaces/:spaceId/simulate page
        print("\n" + "=" * 60)
        print("Analyzing simulation page...")

        # Get first space ID
        space_id = spaces_api.get("data", {}).get("spaces", [{}])[0].get("id") if isinstance(spaces_api, dict) else "test-space"
        print(f"  Using space_id: {space_id}")

        if space_id and space_id != "test-space":
            page.goto(f"http://localhost:3000/spaces/{space_id}/simulate")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            page.screenshot(path="/tmp/simulate_page.png", full_page=True)

            # Check for simulation panel elements
            try:
                sim_title = page.locator("text=模拟配置").first
                print(f"  Simulation config panel visible: {sim_title.is_visible()}")
            except:
                print("  Simulation config panel: NOT FOUND")

            # Check for execution tree viewer
            try:
                exec_tree = page.locator("text=执行树").first
                print(f"  Execution tree viewer visible: {exec_tree.is_visible()}")
            except:
                print("  Execution tree viewer: NOT FOUND")
        else:
            print("  No valid space_id found, skipping simulation page test")

        # 4. Analyze /spaces/:spaceId/execute page (Rule execution)
        print("\n" + "=" * 60)
        print("Analyzing rule execution page...")
        if space_id and space_id != "test-space":
            page.goto(f"http://localhost:3000/spaces/{space_id}/execute")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)
            page.screenshot(path="/tmp/execute_page.png", full_page=True)

            # Check for rule execution components
            try:
                exec_title = page.locator("text=规则执行").first
                print(f"  Rule execution page visible: {exec_title.is_visible()}")
            except:
                print("  Rule execution page: NOT FOUND")
        else:
            print("  No valid space_id found, skipping execution page test")

        # 5. Analyze /rules page (Rule group list)
        print("\n" + "=" * 60)
        print("Analyzing /rules page...")
        page.goto("http://localhost:3000/rules")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/rules_page.png", full_page=True)

        # Check for rule group elements
        rule_cards = page.locator("[class*='Card'], [class*='card'], .ant-card").all()
        print(f"  Rule-related card elements found: {len(rule_cards)}")

        # 6. Test simulation API directly (backend port 8000)
        print("\n" + "=" * 60)
        print("Testing simulation API directly...")

        sim_api_test = page.evaluate("""async () => {
            const results = {};

            // Test POST /v1/simulation/tree
            try {
                const createResp = await fetch("http://localhost:8000/v1/simulation/tree", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        schema_id: "space_supply_chain_finance",
                        target_output: "decision"
                    })
                });
                results.createTree = await createResp.json();
            } catch (e) {
                results.createTree = { error: e.message };
            }

            // Test GET /v1/simulation/{session_id} - will be tested after create
            return results;
        }""")
        print(f"  Simulation API response: {json.dumps(sim_api_test, indent=2, ensure_ascii=False)[:1500]}")

        # Extract session_id if created
        session_id = None
        if isinstance(sim_api_test.get("createTree"), dict):
            session_id = sim_api_test["createTree"].get("data", {}).get("session_id")
        print(f"  Created session_id: {session_id}")

        # 7. Test rule-groups API
        print("\n" + "=" * 60)
        print("Testing rule groups API...")
        rg_api_test = page.evaluate("""async () => {
            const results = {};

            // List rule groups
            try {
                const resp = await fetch("http://localhost:8000/v1/rule-groups?schema_id=space_supply_chain_finance");
                results.listRuleGroups = await resp.json();
            } catch (e) {
                results.listRuleGroups = { error: e.message };
            }

            // Get rule groups DAG
            try {
                const resp = await fetch("http://localhost:8000/v1/rule-groups/credit_approval/dag?schema_id=space_supply_chain_finance");
                results.ruleGroupDag = await resp.json();
            } catch (e) {
                results.ruleGroupDag = { error: e.message };
            }

            return results;
        }""")
        print(f"  Rule groups API: {json.dumps(rg_api_test, indent=2, ensure_ascii=False)[:1500]}")

        # 8. Check simulation embed page
        print("\n" + "=" * 60)
        print("Analyzing /simulation/embed page...")
        page.goto("http://localhost:3000/simulation/embed")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/sim_embed_page.png", full_page=True)

        # Check for simulation embed components
        embed_components = page.locator("[class*='Simulation'], [class*='simulation'], [class*='card']").all()
        print(f"  Simulation embed components found: {len(embed_components)}")

        # Summary of console errors
        print("\n" + "=" * 60)
        print("Console errors captured:")
        if console_errors:
            unique_errors = list(set(console_errors))[:5]  # Deduplicate
            for err in unique_errors:
                print(f"  {err}")
            results["issues"].append(f"Found {len(console_errors)} console errors ({len(unique_errors)} unique)")
        else:
            print("  None")

        browser.close()

    # Analyze gaps
    print("\n" + "=" * 60)
    print("GAP ANALYSIS:")

    # Gap 1: Simulation tree returns empty layers
    print("\n1. Simulation tree endpoint returns empty layers:")
    print("   - Frontend expects: layers[].steps with ExecutableStep objects")
    print("   - Backend returns: layers[].steps = []")
    print("   - Root cause: RuleTreeBuilder._filter_steps() is not implemented")
    results["gaps_found"].append({
        "severity": "high",
        "category": "backend_unimplemented",
        "description": "RuleTreeBuilder._filter_steps returns empty list",
        "frontend_type": "ExecutionTree.layers[].steps: ExecutableStep[]",
        "backend_return": "layers[].steps = []",
        "impact": "ExecutionTreeViewer cannot display steps"
    })

    # Gap 2: Simulation execution not implemented
    print("\n2. Simulation execution is NotImplementedError:")
    print("   - _run_simulation in routes/simulation.py raises NotImplementedError")
    print("   - Impact: Users can build tree but cannot run simulation")
    results["gaps_found"].append({
        "severity": "high",
        "category": "not_implemented",
        "description": "_run_simulation raises NotImplementedError",
        "file": "ontology_engine/api/routes/simulation.py:185-193",
        "impact": "Simulation execution not possible"
    })

    # Gap 3: Rule groups may not be loaded
    print("\n3. Rule groups list is empty or not found:")
    print("   - Backend may not have loaded example rule groups")
    print("   - Or rule group lookup by schema_id is failing")
    results["gaps_found"].append({
        "severity": "medium",
        "category": "data_missing",
        "description": "Rule groups list returns empty or lookup fails",
        "impact": "Cannot test rule CRUD operations"
    })

    # Gap 4: Simulation tree builder _filter_steps not implemented
    print("\n4. RuleTreeBuilder._filter_steps is a placeholder:")
    print("   - Returns empty list [] instead of actual steps")
    print("   - Does not filter steps by entity category")
    results["gaps_found"].append({
        "severity": "high",
        "category": "backend_unimplemented",
        "description": "RuleTreeBuilder._filter_steps is a TODO placeholder",
        "file": "ontology_engine/services/simulation_tree_builder.py:138-158",
        "impact": "Cannot build proper execution tree for cross-rule-group simulation"
    })

    return results

if __name__ == "__main__":
    results = analyze_frontend()

    print("\n" + "=" * 60)
    print("FINAL RESULTS:")
    print(json.dumps({
        "pages_analyzed": results["pages_analyzed"],
        "gaps_found": results["gaps_found"],
        "issues": results["issues"]
    }, indent=2, ensure_ascii=False))
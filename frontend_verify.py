#!/usr/bin/env python3
"""Verify frontend components with Playwright."""

from playwright.sync_api import sync_playwright
import json

def verify_frontend():
    results = {
        "pages_tested": [],
        "components_found": {},
        "api_calls": [],
        "gaps": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Track API calls
        def log_request(request):
            if "api" in request.url or "v1" in request.url:
                results["api_calls"].append({
                    "url": request.url.replace("http://localhost:8000", ""),
                    "method": request.method
                })
        page.on("request", log_request)

        # Track console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        space_id = "space_supply_chain_finance"
        view_id = "view_supply_chain_finance"

        # =============================================
        # Test 1: Space List Page
        # =============================================
        print("=" * 60)
        print("Test 1: Space List Page (/spaces)")
        page.goto("http://localhost:3000/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Check for space cards
        cards = page.locator(".ant-card").all()
        print(f"  Space cards found: {len(cards)}")
        results["components_found"]["space_cards"] = len(cards)

        # Take screenshot
        page.screenshot(path="/tmp/01_spaces.png", full_page=True)
        results["pages_tested"].append("spaces")
        print("  Screenshot: /tmp/01_spaces.png")

        # =============================================
        # Test 2: Space Detail Page with Schema
        # =============================================
        print("\n" + "=" * 60)
        print("Test 2: Space Detail Page (/spaces/{id}/schema)")
        page.goto(f"http://localhost:3000/spaces/{space_id}/schema")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Check for tabs/content
        tabs = page.locator(".ant-tabs-tab").all()
        print(f"  Tabs found: {len(tabs)}")
        results["components_found"]["schema_tabs"] = len(tabs)

        page.screenshot(path="/tmp/02_schema.png", full_page=True)
        results["pages_tested"].append("schema")
        print("  Screenshot: /tmp/02_schema.png")

        # =============================================
        # Test 3: Space Detail Page with Rules
        # =============================================
        print("\n" + "=" * 60)
        print("Test 3: Space Rules Page (/spaces/{id}/rules)")
        page.goto(f"http://localhost:3000/spaces/{space_id}/rules")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Check for rule components
        rule_components = page.locator("[class*='rule'], [class*='Rule']").all()
        print(f"  Rule components: {len(rule_components)}")
        results["components_found"]["rule_components"] = len(rule_components)

        # Check for DAG button
        dag_btn = page.locator("text=/DAG|dag|可视化/i").first
        dag_visible = dag_btn.is_visible() if dag_btn else False
        print(f"  DAG button visible: {dag_visible}")
        results["components_found"]["dag_button"] = dag_visible

        page.screenshot(path="/tmp/03_rules.png", full_page=True)
        results["pages_tested"].append("rules")
        print("  Screenshot: /tmp/03_rules.png")

        # =============================================
        # Test 4: Space Simulate Page
        # =============================================
        print("\n" + "=" * 60)
        print("Test 4: Space Simulate Page (/spaces/{id}/simulate)")
        page.goto(f"http://localhost:3000/spaces/{space_id}/simulate")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Check for simulation config
        sim_config = page.locator("text=/模拟|simulate|simulation/i").all()
        print(f"  Simulation text elements: {len(sim_config)}")
        results["components_found"]["simulation_elements"] = len(sim_config)

        # Check for entity selector
        entity_select = page.locator(".ant-select").first
        entity_visible = entity_select.is_visible() if entity_select else False
        print(f"  Entity selector visible: {entity_visible}")

        page.screenshot(path="/tmp/04_simulate.png", full_page=True)
        results["pages_tested"].append("simulate")
        print("  Screenshot: /tmp/04_simulate.png")

        # =============================================
        # Test 5: Simulation Embed Page
        # =============================================
        print("\n" + "=" * 60)
        print("Test 5: Simulation Embed Page (/simulation/embed)")
        page.goto("http://localhost:3000/simulation/embed")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        sim_embed_components = page.locator("[class*='Simulation'], [class*='simulation']").all()
        print(f"  Simulation embed components: {len(sim_embed_components)}")
        results["components_found"]["sim_embed_components"] = len(sim_embed_components)

        page.screenshot(path="/tmp/05_sim_embed.png", full_page=True)
        results["pages_tested"].append("simulation_embed")
        print("  Screenshot: /tmp/05_sim_embed.png")

        # =============================================
        # Test 6: Check API calls made by frontend
        # =============================================
        print("\n" + "=" * 60)
        print("Test 6: API Calls Analysis")

        # Group by endpoint
        endpoints = {}
        for call in results["api_calls"]:
            url = call["url"]
            method = call["method"]
            key = f"{method} {url}"
            endpoints[key] = endpoints.get(key, 0) + 1

        print(f"  Total API calls: {len(results['api_calls'])}")
        print(f"  Unique endpoints: {len(endpoints)}")

        # Show first 10 endpoints
        print("\n  Top endpoints:")
        for endpoint, count in sorted(endpoints.items(), key=lambda x: -x[1])[:10]:
            print(f"    {endpoint}: {count}")

        # Check for simulation/tree calls
        sim_tree_calls = [c for c in results["api_calls"] if "simulation/tree" in c["url"]]
        print(f"\n  simulation/tree calls: {len(sim_tree_calls)}")

        # =============================================
        # Test 7: Console Errors
        # =============================================
        print("\n" + "=" * 60)
        print("Test 7: Console Errors")
        if console_errors:
            unique_errors = list(set(console_errors))[:5]
            print(f"  Errors found: {len(console_errors)}")
            for err in unique_errors:
                print(f"    - {err[:100]}")
            results["gaps"].append({"type": "console_errors", "count": len(console_errors)})
        else:
            print("  No console errors")

        browser.close()

    # =============================================
    # Summary
    # =============================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Pages tested: {results['pages_tested']}")
    print(f"Components found: {json.dumps(results['components_found'], indent=2)}")

    if results["gaps"]:
        print(f"\nGaps identified:")
        for gap in results["gaps"]:
            print(f"  - {gap}")

    return results

if __name__ == "__main__":
    results = verify_frontend()
    print("\n" + "=" * 60)
    print("DONE - Screenshots saved to /tmp/0X_*.png")
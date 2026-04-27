#!/usr/bin/env python3
"""Detailed frontend verification with simulation API test."""

from playwright.sync_api import sync_playwright
import json

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # =============================================
        # Test: Simulation Embed Page with schemaId
        # =============================================
        print("=" * 60)
        print("Testing /simulation/embed?schemaId=space_supply_chain_finance")
        print("=" * 60)

        # Navigate with schemaId
        page.goto("http://localhost:3000/simulation/embed?schemaId=space_supply_chain_finance")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Take screenshot
        page.screenshot(path="/tmp/sim_embed_with_schema.png", full_page=True)
        print("Screenshot: /tmp/sim_embed_with_schema.png")

        # Check for visible text
        page_content = page.content()

        # Look for specific elements
        checks = [
            ("目标输出", "Target output label"),
            ("schemaId", "Schema ID text"),
            ("模拟", "Simulation text"),
            ("Card", "Card component"),
            ("input", "Input element"),
        ]

        print("\nElement checks:")
        for selector, name in checks:
            found = selector.lower() in page_content.lower()
            print(f"  {name} ({selector}): {'✓' if found else '✗'}")

        # Check API calls made
        api_calls = []
        def log_request(request):
            if "v1" in request.url and "localhost:8000" in request.url:
                api_calls.append(request.url.replace("http://localhost:8000", ""))
        page.on("request", log_request)

        # Refresh to capture API calls
        page.goto("http://localhost:3000/simulation/embed?schemaId=space_supply_chain_finance")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        print(f"\nAPI calls made: {len(api_calls)}")
        for call in api_calls[:10]:
            print(f"  {call}")

        # Check for simulation/tree call
        sim_tree_calls = [c for c in api_calls if "simulation/tree" in c]
        print(f"\nsimulation/tree calls: {len(sim_tree_calls)}")
        if sim_tree_calls:
            print(f"  Found: {sim_tree_calls[0]}")
        else:
            print("  NOT FOUND - Frontend is NOT calling the simulation tree API!")

        # =============================================
        # Test: Rules page with DAG
        # =============================================
        print("\n" + "=" * 60)
        print("Testing /spaces/{id}/rules")
        print("=" * 60)

        space_id = "space_supply_chain_finance"
        page.goto(f"http://localhost:3000/spaces/{space_id}/rules")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        page.screenshot(path="/tmp/rules_page.png", full_page=True)

        # Check for rule list
        rules_text = page.locator("text=/RD00|规则|rule/i").all()
        print(f"\nRule-related text elements: {len(rules_text)}")

        # Check for DAG visualization
        dag_visualization = page.locator("[class*='dag'], [class*='DAG'], canvas, svg").all()
        print(f"DAG visualization elements: {len(dag_visualization)}")

        browser.close()

        print("\n" + "=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)

if __name__ == "__main__":
    main()
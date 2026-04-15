#!/usr/bin/env python3
"""Deep UI exploration with screenshots"""
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # Explore all consumption pages
        print("=" * 60)
        print("CONSUMPTION SURFACE EXPLORATION")
        print("=" * 60)

        # Navigate directly to space detail
        page.goto("http://localhost:3000/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Get list of spaces
        spaces = page.locator("table tbody tr").all()
        print(f"\nFound {len(spaces)} spaces in list")

        # Get space names and statuses
        for i, row in enumerate(spaces[:5]):
            cols = row.locator("td").all_inner_texts()
            if len(cols) > 1:
                print(f"  {i+1}. {cols[0][:30]} - Status: {cols[1]}")

        # Navigate to first space
        if spaces:
            first_space_link = page.locator("table tbody tr:first-child a").first
            space_name = first_space_link.inner_text()
            print(f"\nNavigating to: {space_name}")
            first_space_link.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            # Check all menu items
            menu_items = page.locator(".ant-menu-item").all_inner_texts()
            print(f"Menu items: {menu_items}")

            # Check space status
            tags = page.locator(".ant-tag").all_inner_texts()
            print(f"Space tags: {tags}")

        # Check Schema tab in detail
        print("\n--- Schema Declaration ---")
        schema_tab = page.locator(".ant-tabs-tab").first
        if schema_tab:
            schema_tab.click()
            page.wait_for_timeout(2000)
            page.screenshot(path="/tmp/schema-tab.png", full_page=True)

            # Get tab counts
            tabs_content = page.locator(".ant-tabs-tab").all_inner_texts()
            print(f"Tabs: {tabs_content}")

            # Get L1 table
            l1_rows = page.locator(".ant-table-row").count()
            print(f"L1 rows: {l1_rows}")

        # Navigate to Rule Declarations
        print("\n--- Rule Declarations ---")
        page.locator("text=规则声明").click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/rule-declarations.png", full_page=True)

        # Check table
        table_rows = page.locator(".ant-table-row").count()
        print(f"Rule rows: {table_rows}")

        # Check if create button exists
        create_btn_texts = page.locator("button").all_inner_texts()
        print(f"Button texts: {[t[:30] for t in create_btn_texts if t]}")

        # Navigate to Rule Logics
        print("\n--- Rule Logics ---")
        page.locator("text=规则逻辑").click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/rule-logics.png", full_page=True)

        table_rows = page.locator(".ant-table-row").count()
        print(f"Logic rows: {table_rows}")

        # Navigate to Instances
        print("\n--- Instance Data ---")
        page.locator("text=数据实例").click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/instances.png", full_page=True)

        instance_tabs = page.locator(".ant-tabs-tab").all_inner_texts()
        print(f"Instance tabs: {instance_tabs}")

        # Navigate to Schema Visualization
        print("\n--- Schema Visualization (Consumption) ---")
        page.locator("text=Schema 可视化").click()
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/schema-visualization.png", full_page=True)

        # Check for G6 canvas
        canvas_count = page.locator("canvas").count()
        print(f"Canvas elements: {canvas_count}")

        # Check for graph type selector
        graph_types = page.locator(".ant-segmented").inner_text() if page.locator(".ant-segmented").count() > 0 else "Not found"
        print(f"Graph types: {graph_types}")

        # Navigate to Rule Execution
        print("\n--- Rule Execution (Consumption) ---")
        page.locator("text=规则执行").click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/rule-execution.png", full_page=True)

        # Check for selectors
        selects = page.locator(".ant-select").count()
        print(f"Select dropdowns: {selects}")

        # Navigate to Simulation
        print("\n--- What-If Simulation (Consumption) ---")
        page.locator("text=What-If 模拟").click()
        page.wait_for_timeout(2000)
        page.screenshot(path="/tmp/simulation.png", full_page=True)

        sim_elements = page.locator("text=模拟参数").count()
        print(f"Simulation params visible: {sim_elements > 0}")

        # Check for console errors
        print("\n--- Console Errors ---")
        errors = [l for l in console_logs if "error" in l.lower()]
        for e in errors[:10]:
            print(f"  {e[:200]}")

        browser.close()
        print("\nDone! Screenshots saved to /tmp/")

if __name__ == "__main__":
    main()

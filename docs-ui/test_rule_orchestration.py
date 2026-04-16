#!/usr/bin/env python3
"""Test rule orchestration UI functionality using Playwright"""
from playwright.sync_api import sync_playwright
import re

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Enable console logging
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[PAGE ERROR] {err}"))

        print("=" * 70)
        print("RULE ORCHESTRATION UI TEST")
        print("=" * 70)

        # Step 1: Go to spaces list first to get a schemaId
        print("\n[STEP 1] Navigate to Spaces List")
        page.goto("http://localhost:3001/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Check page loaded
        page_title = page.title()
        print(f"  Page title: {page_title}")

        # Get visible table rows (skip hidden measure rows)
        table_rows = page.locator("table tbody tr:visible")
        row_count = table_rows.count()
        print(f"  Visible table rows: {row_count}")

        if row_count == 0:
            print("  ERROR: No spaces found.")
            page.screenshot(path="/tmp/error-spaces.png", full_page=True)
            browser.close()
            return

        # Click on first visible data row link
        print("  Clicking first space...")
        try:
            first_link = page.locator("table tbody tr:visible a").first
            if first_link.count() > 0:
                space_name = first_link.inner_text(timeout=5000)
                print(f"  Space name: {space_name}")
                first_link.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)
            else:
                # Try clicking the row directly
                first_link = page.locator("table tbody tr:visible").first
                first_link.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  Click error: {e}")
            page.screenshot(path="/tmp/error-click.png", full_page=True)

        # Get current URL to extract spaceId
        current_url = page.url
        print(f"  Current URL: {current_url}")

        # Extract spaceId from URL
        match = re.search(r'/spaces/([^/?#]+)', current_url)
        if match:
            space_id = match.group(1)
            print(f"  Space ID extracted: {space_id}")
        else:
            print("  ERROR: Could not extract spaceId")
            browser.close()
            return

        # Step 2: Navigate to Rule Group List Page
        print("\n[STEP 2] Navigate to Rule Group List Page")
        page.goto(f"http://localhost:3001/rules?schemaId={space_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/rule-list.png", full_page=True)

        # Check page content
        page_text = page.content()
        print(f"  Page contains '规则': {'规则' in page_text}")

        # Check for rule groups
        rule_rows = page.locator("table tbody tr:visible").count()
        print(f"  Rule groups in table: {rule_rows}")

        # Console errors check
        errors = [l for l in console_logs if "error" in l.lower()]
        if errors:
            print(f"  Console errors: {len(errors)}")
            for e in errors[:3]:
                print(f"    - {e[:100]}")
        console_logs.clear()

        # Step 3: Test Rule Group Create Page
        print("\n[STEP 3] Test Rule Group Create Page")
        page.goto(f"http://localhost:3001/rules/new?schemaId={space_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/rule-create.png", full_page=True)

        # Count form inputs
        inputs = page.locator(".ant-input, .ant-select").count()
        print(f"  Input/select elements: {inputs}")

        # Try to fill name
        try:
            name_input = page.locator("input").first
            name_input.fill("Test Rule Group")
            print("  Filled name: Test Rule Group")
        except Exception as e:
            print(f"  Fill error: {e}")

        # Check for buttons
        buttons = [b.strip() for b in page.locator("button").all_inner_texts() if b.strip()]
        print(f"  Buttons: {buttons}")

        # Click submit if exists
        submit = page.locator("button:has-text('创建')").first
        if submit.count() > 0:
            submit.click()
            page.wait_for_timeout(3000)
            print(f"  After submit URL: {page.url}")
            page.screenshot(path="/tmp/rule-create-result.png", full_page=True)

        # Step 4: Test Rule Group Detail Page
        print("\n[STEP 4] Test Rule Group Detail Page")

        # Go back to list
        page.goto(f"http://localhost:3001/rules?schemaId={space_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        rule_rows = page.locator("table tbody tr:visible").count()
        print(f"  Rule groups: {rule_rows}")

        if rule_rows > 0:
            # Try to click a rule group
            try:
                rule_link = page.locator("table tbody tr:visible td a").first
                if rule_link.count() > 0:
                    name = rule_link.inner_text(timeout=5000)
                    print(f"  Clicking rule: {name}")
                    rule_link.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(3000)
                    page.screenshot(path="/tmp/rule-detail-page.png", full_page=True)
                    print(f"  URL: {page.url}")

                    # Check components
                    has_framework = page.locator("text=规则组框架").count() > 0
                    has_steps = page.locator("text=规则实例").count() > 0
                    has_dag = page.locator("text=要素依赖图").count() > 0
                    has_entities = page.locator("text=作用对象").count() > 0
                    has_applicability = page.locator("text=适用场景").count() > 0
                    has_io = page.locator("text=I/O 要素").count() > 0

                    print(f"  Components found:")
                    print(f"    - Rule Group Framework: {has_framework}")
                    print(f"    - Rule Steps: {has_steps}")
                    print(f"    - Element DAG: {has_dag}")
                    print(f"    - Target Entities: {has_entities}")
                    print(f"    - Applicability: {has_applicability}")
                    print(f"    - I/O Elements: {has_io}")

                    # Screenshots of key sections
                    if has_framework:
                        page.locator("text=规则组框架").screenshot(path="/tmp/rule-framework.png")
                    if has_steps:
                        page.locator("text=规则实例").screenshot(path="/tmp/rule-steps.png")

                else:
                    print("  No clickable rule group link")
            except Exception as e:
                print(f"  Rule click error: {e}")
        else:
            print("  No rule groups to test")

        # Step 5: Test Step Edit Page
        print("\n[STEP 5] Test Step Edit Page")
        page.goto(f"http://localhost:3001/rules/test-group/steps/test-step/edit?schemaId={space_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/step-edit.png", full_page=True)

        # Check tabs
        tabs = page.locator(".ant-tabs-tab").all_inner_texts()
        print(f"  Tabs: {tabs}")

        # Check for ConditionEditor
        if any("条件" in t for t in tabs):
            print("  SUCCESS: Condition tab exists")
            page.locator(".ant-tabs-tab").filter(has_text="条件").click()
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/condition-editor.png", full_page=True)

        # Check for ActionEditor
        if any("THEN" in t for t in tabs):
            print("  SUCCESS: THEN action tab exists")
            page.locator(".ant-tabs-tab").filter(has_text="THEN").click()
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/action-editor.png", full_page=True)

        # Check for SimulationPanel
        if any("模拟" in t for t in tabs):
            print("  SUCCESS: Simulation tab exists")
            page.locator(".ant-tabs-tab").filter(has_text="模拟").click()
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/simulation-panel.png", full_page=True)

            # Check simulation button
            has_sim_btn = page.locator("button:has-text('执行模拟')").count() > 0
            print(f"  Execute Simulation button: {has_sim_btn}")

        # Final error check
        print("\n[FINAL] Console Errors")
        errors = [l for l in console_logs if "error" in l.lower()]
        if errors:
            print(f"  Total: {len(errors)}")
            for e in errors[:5]:
                print(f"    - {e[:150]}")
        else:
            print("  None detected!")

        browser.close()
        print("\n" + "=" * 70)
        print("TEST COMPLETE - Screenshots in /tmp/rule-*.png, /tmp/step-*.png")
        print("=" * 70)

if __name__ == "__main__":
    main()

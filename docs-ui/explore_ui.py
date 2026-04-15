#!/usr/bin/env python3
"""Quick UI exploration script using Playwright"""
from playwright.sync_api import sync_playwright
import json

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Enable console logging
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[PAGE ERROR] {err}"))

        # Step 1: Go to spaces list
        print("=" * 60)
        print("STEP 1: Spaces List Page")
        print("=" * 60)
        page.goto("http://localhost:3000/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Take screenshot
        page.screenshot(path="/tmp/01-spaces-list.png", full_page=True)

        # Check for spaces
        spaces = page.locator("table tbody tr").count()
        print(f"Spaces found: {spaces}")

        # Get page title/text
        print("\n--- Page Content ---")
        print(page.content()[:2000])

        # Check for console errors
        print("\n--- Console Errors ---")
        errors = [l for l in console_logs if "error" in l.lower()]
        for e in errors[:5]:
            print(e)
        console_logs.clear()

        # Step 2: Click create space button
        print("\n" + "=" * 60)
        print("STEP 2: Create Space Modal")
        print("=" * 60)

        create_btn = page.locator("button:has-text('创建空间')").first
        if create_btn:
            create_btn.click()
            page.wait_for_timeout(500)
            page.screenshot(path="/tmp/02-create-space-modal.png", full_page=True)

            modal_visible = page.locator(".ant-modal").is_visible()
            print(f"Create modal visible: {modal_visible}")

            # Get modal content
            if modal_visible:
                modal_content = page.locator(".ant-modal-body").inner_text()
                print(f"Modal content: {modal_content[:500]}")
        else:
            print("Create button not found")

        # Close modal
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # Step 3: If there are spaces, navigate to first one
        if spaces > 0:
            print("\n" + "=" * 60)
            print("STEP 3: Space Detail Page")
            print("=" * 60)

            first_space_link = page.locator("table tbody tr:first-child a").first
            space_name = first_space_link.inner_text()
            print(f"Clicking space: {space_name}")
            first_space_link.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/03-space-detail.png", full_page=True)

            # Check menu items
            menu_items = page.locator(".ant-menu-item").all_inner_texts()
            print(f"Menu items: {menu_items}")

        # Step 4: Check Schema tab
        print("\n" + "=" * 60)
        print("STEP 4: Schema Declaration Tab")
        print("=" * 60)

        schema_tab = page.locator("text=Schema 声明").first
        if schema_tab:
            schema_tab.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/04-schema-declaration.png", full_page=True)

            tabs = page.locator(".ant-tabs-tab").all_inner_texts()
            print(f"Schema tabs: {tabs}")

            # Check if data loaded
            l1_rows = page.locator("table tbody tr").count()
            print(f"L1 table rows: {l1_rows}")

        console_logs.clear()

        # Step 5: Check Rule Declarations
        print("\n" + "=" * 60)
        print("STEP 5: Rule Declarations Tab")
        print("=" * 60)

        rules_decl_tab = page.locator("text=规则声明").first
        if rules_decl_tab:
            rules_decl_tab.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="/tmp/05-rule-declarations.png", full_page=True)

            rules_table = page.locator("table").count()
            print(f"Tables found: {rules_table}")

            # Try to open create modal
            create_rule_btn = page.locator("button:has-text('创建声明')").first
            if create_rule_btn:
                create_rule_btn.click()
                page.wait_for_timeout(500)
                page.screenshot(path="/tmp/05a-create-rule-modal.png", full_page=True)

        # Check for any console errors
        print("\n--- Console Errors During Navigation ---")
        errors = [l for l in console_logs if "error" in l.lower()]
        for e in errors[:10]:
            print(e)

        browser.close()
        print("\nDone! Screenshots saved to /tmp/01-*.png")

if __name__ == "__main__":
    main()

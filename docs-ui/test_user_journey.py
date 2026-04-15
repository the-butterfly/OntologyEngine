#!/usr/bin/env python3
"""
Comprehensive user journey test for Ontology Engine UI
Tests all major pages and checks for console errors
Ignores known library warnings (React Router v7 migration, Ant Design prop warnings)
"""
from playwright.sync_api import sync_playwright, ConsoleMessage

# Collect console errors
console_errors = []

# Known library warnings to ignore
KNOWN_WARNINGS = [
    "React Router Future Flag Warning",  # React Router v7 migration warnings
    "React does not recognize",  # Ant Design prop warnings
    "Download the React DevTools",  # React DevTools info message
    "[vite]",  # Vite HMR messages
]

def is_known_warning(text):
    for kw in KNOWN_WARNINGS:
        if kw in text:
            return True
    return False

def handle_console(msg: ConsoleMessage):
    if msg.type == 'error' and not is_known_warning(msg.text):
        console_errors.append({
            'text': msg.text,
            'location': msg.location
        })

def main():
    errors = []  # Track test failures

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on('console', handle_console)

        print("=" * 60)
        print("ONTOLOGY ENGINE UI - USER JOURNEY TEST")
        print("=" * 60)

        # Test 1: Load homepage (space list)
        print("\n[1/7] Testing Space List Page...")
        try:
            page.goto("http://localhost:3002/spaces", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Check page loaded
            title = page.title()
            print(f"  Page title: {title}")

            # Check for main elements
            spaces_heading = page.locator("text=语义空间").first
            if spaces_heading.count() > 0:
                print("  ✓ Space list page loaded")
            else:
                errors.append("Space list heading not found")
                print("  ✗ Space list heading not found")

            # Check table exists
            table = page.locator("table")
            if table.count() > 0:
                print("  ✓ Space table found")
            else:
                print("  ! No spaces table (may be empty)")

        except Exception as e:
            errors.append(f"Space list page error: {e}")
            print(f"  ✗ Error: {e}")

        # Test 2: Navigate to first space if exists
        print("\n[2/7] Testing Space Detail Page...")
        try:
            first_space_link = page.locator("table tbody tr:first-child a").first
            if first_space_link.count() > 0:
                first_space_link.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)

                # Check we're on space detail page
                breadcrumb = page.locator(".ant-breadcrumb")
                if breadcrumb.count() > 0:
                    print("  ✓ Space detail page loaded")

                # Check header tags
                tags = page.locator(".ant-tag").all()
                print(f"  ✓ Found {len(tags)} tags in header")
                for i, tag in enumerate(tags[:6]):
                    print(f"    Tag {i+1}: {tag.inner_text()[:30]}")

                # Check menu items
                menu_items = page.locator(".ant-menu-item")
                menu_count = menu_items.count()
                print(f"  ✓ Found {menu_count} menu items")

            else:
                print("  ! No spaces to navigate to")
        except Exception as e:
            errors.append(f"Space detail page error: {e}")
            print(f"  ✗ Error: {e}")

        # Test 3: Schema Declaration Page
        print("\n[3/7] Testing Schema Declaration Page...")
        try:
            # Find and click Schema menu item
            schema_menu = page.locator("text=Schema 声明").first
            if schema_menu.count() > 0:
                # Click the menu item (may need parent)
                parent = schema_menu.locator("..")
                if parent.count() > 0:
                    parent.click()
                else:
                    schema_menu.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                print("  ✓ Schema declaration page loaded")

                # Check tabs exist
                tabs = page.locator(".ant-tabs-tab")
                if tabs.count() > 0:
                    print(f"  ✓ Found {tabs.count()} schema layer tabs")
            else:
                print("  ! Schema menu not found")
        except Exception as e:
            errors.append(f"Schema declaration page error: {e}")
            print(f"  ✗ Error: {e}")

        # Test 4: Rule Declarations Page
        print("\n[4/7] Testing Rule Declarations Page...")
        try:
            rule_menu = page.locator("text=规则声明").first
            if rule_menu.count() > 0:
                parent = rule_menu.locator("..")
                if parent.count() > 0:
                    parent.click()
                else:
                    rule_menu.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                print("  ✓ Rule declarations page loaded")

                # Check for create button
                create_btn = page.locator("button:has-text('创建')")
                if create_btn.count() > 0:
                    print("  ✓ Create button found")
            else:
                print("  ! Rule declarations menu not found")
        except Exception as e:
            errors.append(f"Rule declarations page error: {e}")
            print(f"  ✗ Error: {e}")

        # Test 5: Rule Logics Page
        print("\n[5/7] Testing Rule Logics Page...")
        try:
            logics_menu = page.locator("text=规则逻辑").first
            if logics_menu.count() > 0:
                parent = logics_menu.locator("..")
                if parent.count() > 0:
                    parent.click()
                else:
                    logics_menu.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                print("  ✓ Rule logics page loaded")
            else:
                print("  ! Rule logics menu not found")
        except Exception as e:
            errors.append(f"Rule logics page error: {e}")
            print(f"  ✗ Error: {e}")

        # Test 6: Data Instances Page
        print("\n[6/7] Testing Data Instances Page...")
        try:
            instances_menu = page.locator("text=数据实例").first
            if instances_menu.count() > 0:
                parent = instances_menu.locator("..")
                if parent.count() > 0:
                    parent.click()
                else:
                    instances_menu.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(2000)
                print("  ✓ Data instances page loaded")
            else:
                print("  ! Data instances menu not found")
        except Exception as e:
            errors.append(f"Data instances page error: {e}")
            print(f"  ✗ Error: {e}")

        # Test 7: Check for console errors
        print("\n[7/7] Checking Console Errors...")
        if console_errors:
            print(f"  ✗ Found {len(console_errors)} console error(s):")
            for i, err in enumerate(console_errors[:5]):  # Show first 5
                print(f"    {i+1}. {err['text'][:100]}")
                if err['location']:
                    print(f"       at {err['location'].get('url', 'unknown')}:{err['location'].get('lineNumber', '?')}")
            if len(console_errors) > 5:
                print(f"    ... and {len(console_errors) - 5} more")
            errors.append(f"{len(console_errors)} console errors found")
        else:
            print("  ✓ No console errors detected")

        browser.close()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    if errors:
        print(f"FAILURES: {len(errors)}")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("ALL TESTS PASSED ✓")
        return 0

if __name__ == "__main__":
    exit(main())
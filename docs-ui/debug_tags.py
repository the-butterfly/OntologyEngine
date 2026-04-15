#!/usr/bin/env python3
"""Debug: Inspect exact tag content in Space Detail Page"""
from playwright.sync_api import sync_playwright

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to first space
        page.goto("http://localhost:3000/spaces")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # Click first space
        page.locator("table tbody tr:first-child a").first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Get ALL tags in the header area
        print("=== ALL .ant-tag elements ===")
        tags = page.locator(".ant-space .ant-tag, .ant-space-item .ant-tag").all()
        for i, tag in enumerate(tags):
            text = tag.inner_text()
            print(f"  Tag {i}: '{text}'")

        # Get the header section specifically
        print("\n=== Header Space Content ===")
        header_space = page.locator(".ant-space").first
        if header_space.count() > 0:
            content = header_space.inner_text()
            print(f"Content: {content}")

        # Get full page HTML snippet around header
        print("\n=== Header HTML ===")
        header_html = page.evaluate("""() => {
            const header = document.querySelector('.ant-layout-header') || document.querySelector('[style*="padding: 24px"]');
            return header ? header.outerHTML.substring(0, 2000) : 'No header found';
        }""")
        print(header_html[:2000])

        browser.close()

if __name__ == "__main__":
    main()

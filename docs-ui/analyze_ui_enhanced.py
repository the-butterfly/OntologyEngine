"""
docs-ui 与代码已有功能全面分析 - 增强版
检查控制台错误和实际页面内容
"""
from playwright.sync_api import sync_playwright
import json

BASE_URL = "http://localhost:3000"

def analyze_page_enhanced(page, url, page_name):
    """分析单个页面并捕获控制台错误"""
    console_messages = []
    page_errors = []

    # 监听控制台消息
    def on_console(msg):
        if msg.type == 'error':
            console_messages.append(f"[Console Error] {msg.text}")

    def on_page_error(err):
        page_errors.append(f"[Page Error] {err}")

    page.on('console', on_console)
    page.on('pageerror', on_page_error)

    try:
        page.goto(url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        # 获取 body 文本
        body_text = page.locator('body').inner_text()
        body_text_preview = body_text[:500] if body_text else "[empty]"

        result = {
            "page": page_name,
            "url": url,
            "status": "success",
            "body_preview": body_text_preview,
            "html_length": len(page.content()),
            "console_errors": console_messages,
            "page_errors": page_errors,
        }
    except Exception as e:
        result = {
            "page": page_name,
            "url": url,
            "status": "error",
            "error": str(e),
            "console_errors": console_messages,
            "page_errors": page_errors,
        }

    page.remove_listener('console', on_console)
    page.remove_listener('pageerror', on_page_error)

    return result

def main():
    print("=" * 80)
    print("docs-ui 与代码已有功能全面分析 - 增强版")
    print("=" * 80)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        pages_to_check = [
            ("/", "Home_Redirect"),
            ("/spaces", "SpaceList"),
            ("/spaces/demo_space", "SpaceDetail"),
            ("/spaces/demo_space/schema", "SchemaDeclaration"),
            ("/spaces/demo_space/instances", "InstanceData"),
            ("/spaces/demo_space/versions", "VersionHistory"),
            ("/spaces/demo_space/rules", "RulesEmbed"),
            ("/consumption", "ConsumptionList"),
            ("/consumption/demo_view", "ConsumptionView"),
            ("/simulation/embed", "SimulationEmbed"),
            ("/rules", "RuleGroupList"),
        ]

        for path, name in pages_to_check:
            print(f"\n分析: {name} ({path})")
            result = analyze_page_enhanced(page, f"{BASE_URL}{path}", name)
            results.append(result)
            print(f"  状态: {result['status']}")
            if result['status'] == 'success':
                print(f"  HTML长度: {result['html_length']}")
                print(f"  Body预览: {result['body_preview'][:200]}...")
            if result.get('console_errors'):
                print(f"  控制台错误: {result['console_errors']}")
            if result.get('page_errors'):
                print(f"  页面错误: {result['page_errors']}")

        browser.close()

    # 保存结果
    with open('/tmp/ui_analysis_enhanced.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
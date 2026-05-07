"""
docs-ui 与代码已有功能全面分析 - 最终版
分析实际存在的数据并与 examples 期望对比
"""
from playwright.sync_api import sync_playwright
import json

BASE_URL = "http://localhost:3000"

def get_real_spaces(page):
    """获取实际存在的空间列表"""
    page.goto(f"{BASE_URL}/spaces", wait_until='networkidle')
    page.wait_for_timeout(1000)

    spaces = []
    # 查找表格中的空间名称
    rows = page.locator('table tbody tr').all()
    for row in rows:
        cells = row.locator('td').all()
        if cells and len(cells) > 0:
            space_name = cells[0].inner_text().strip()
            if space_name:
                spaces.append(space_name)
    return spaces

def get_real_consumption_views(page):
    """获取实际存在的消费视图"""
    page.goto(f"{BASE_URL}/consumption", wait_until='networkidle')
    page.wait_for_timeout(1000)

    views = []
    rows = page.locator('table tbody tr').all()
    for row in rows:
        cells = row.locator('td').all()
        if cells and len(cells) > 0:
            view_name = cells[0].inner_text().strip()
            if view_name:
                # 获取视图 ID - 尝试多种方式
                href = None
                link = row.locator('a').first
                if link.is_visible(timeout=1000):
                    try:
                        href = link.get_attribute('href')
                    except:
                        pass
                if not href:
                    # 可能通过按钮或其他方式导航
                    buttons = row.locator('button').all()
                    for btn in buttons:
                        text = btn.inner_text().strip()
                        if "进入" in text:
                            href = f"/consumption/view_{view_name[:10]}"
                            break
                views.append({"name": view_name, "href": href})
    return views

def analyze_real_space(page, space_name):
    """分析实际空间的所有页面"""
    results = {}
    space_url = space_name.replace(" ", "-").lower()

    pages = [
        ("schema", "Schema"),
        ("instances", "Instances"),
        ("versions", "Versions"),
        ("rules", "Rules"),
    ]

    for path, name in pages:
        url = f"{BASE_URL}/spaces/{space_url}/{path}"
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(1000)

        body_text = page.locator('body').inner_text()[:1000]
        results[name] = {
            "url": url,
            "body_preview": body_text,
            "console_errors": []
        }

    return results

def analyze_real_consumption_view(page, view_href):
    """分析实际消费视图页面"""
    page.goto(f"{BASE_URL}{view_href}", wait_until='networkidle')
    page.wait_for_timeout(1500)

    body_text = page.locator('body').inner_text()[:2000]

    return {
        "url": f"{BASE_URL}{view_href}",
        "body_preview": body_text
    }

def compare_with_examples(page, real_data):
    """与 examples 中的期望输出对比"""
    print("\n" + "=" * 80)
    print("examples 期望输出 vs 实际实现 对比")
    print("=" * 80)

    # case4 bi_workbench 设计要点
    bi_workbench_design = {
        "经营分析工作台": False,
        "毛利率 / gross_margin": False,
        "DSO / 周转天数": False,
        "异常门店清单": False,
        "区域看板": False,
        "版本 diff": False,
        "指标卡": False,
        "规则包": False,
        "视图": False,
        "证据碎片": False,
    }

    # 检查实际数据中是否包含这些设计要点
    combined_text = str(real_data).lower()

    if "经营分析工作台" in combined_text or "bi" in combined_text or "问数" in combined_text:
        bi_workbench_design["经营分析工作台"] = True

    if "毛利率" in combined_text or "gross_margin" in combined_text:
        bi_workbench_design["毛利率 / gross_margin"] = True

    if "dso" in combined_text or "周转天数" in combined_text or "应收" in combined_text:
        bi_workbench_design["DSO / 周转天数"] = True

    if "异常" in combined_text or "门店" in combined_text:
        bi_workbench_design["异常门店清单"] = True

    if "区域" in combined_text or "看板" in combined_text:
        bi_workbench_design["区域看板"] = True

    if "版本" in combined_text or "diff" in combined_text or "v1" in combined_text:
        bi_workbench_design["版本 diff"] = True

    if "指标" in combined_text:
        bi_workbench_design["指标卡"] = True

    if "规则" in combined_text:
        bi_workbench_design["规则包"] = True

    if "视图" in combined_text or "view" in combined_text:
        bi_workbench_design["视图"] = True

    if "证据" in combined_text or "pdf" in combined_text or "csv" in combined_text:
        bi_workbench_design["证据碎片"] = True

    print("\n[case4_bi_query_agent / bi_workbench.md 设计要点覆盖检查]")
    for key, covered in bi_workbench_design.items():
        status = "✓ 已实现" if covered else "✗ 未实现"
        print(f"  {status}: {key}")

    # case1 regulatory compliance 设计要点
    case1_design = {
        "白名单": False,
        "版本": False,
        "diff": False,
        "证据链": False,
        "合规": False,
        "审计": False,
    }

    if "白名单" in combined_text or "whitelist" in combined_text:
        case1_design["白名单"] = True
    if "版本" in combined_text:
        case1_design["版本"] = True
    if "diff" in combined_text:
        case1_design["diff"] = True
    if "证据" in combined_text:
        case1_design["证据链"] = True
    if "合规" in combined_text:
        case1_design["合规"] = True
    if "审计" in combined_text:
        case1_design["审计"] = True

    print("\n[case1_regulatory_compliance 设计要点覆盖检查]")
    for key, covered in case1_design.items():
        status = "✓ 已实现" if covered else "✗ 未实现"
        print(f"  {status}: {key}")

def main():
    print("=" * 80)
    print("docs-ui 与代码已有功能全面分析")
    print("=" * 80)

    results = {
        "spaces": [],
        "consumption_views": [],
        "space_details": {},
        "consumption_view_details": {},
        "comparison": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. 获取实际空间列表
        print("\n[1] 获取实际存在的语义空间...")
        spaces = get_real_spaces(page)
        results["spaces"] = spaces
        print(f"  发现 {len(spaces)} 个空间:")
        for s in spaces[:5]:
            print(f"    - {s}")

        # 2. 获取实际消费视图列表
        print("\n[2] 获取实际存在的消费视图...")
        views = get_real_consumption_views(page)
        results["consumption_views"] = views
        print(f"  发现 {len(views)} 个消费视图:")
        for v in views[:5]:
            print(f"    - {v['name']}: {v['href']}")

        # 3. 分析第一个空间（假设是完整数据）
        if spaces:
            first_space = spaces[0].replace(" ", "-").lower()
            print(f"\n[3] 分析空间详情: {spaces[0]}")
            results["space_details"] = analyze_real_space(page, spaces[0])

            print(f"\n  Schema 页面:")
            print(f"    {results['space_details']['Schema']['body_preview'][:300]}...")

            print(f"\n  Rules 页面:")
            print(f"    {results['space_details']['Rules']['body_preview'][:300]}...")

        # 4. 分析第一个消费视图
        if views:
            print(f"\n[4] 分析消费视图详情: {views[0]['name']}")
            results["consumption_view_details"] = analyze_real_consumption_view(page, views[0]['href'])
            print(f"  内容预览:")
            print(f"    {results['consumption_view_details']['body_preview'][:500]}...")

        # 5. 与 examples 期望对比
        all_real_content = (
            str(results.get("spaces", [])) +
            str(results.get("consumption_views", [])) +
            str(results.get("space_details", {})) +
            str(results.get("consumption_view_details", {}))
        )
        compare_with_examples(page, all_real_content)

        browser.close()

    # 保存结果
    with open('/tmp/ui_analysis_final.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("分析完成")
    print(f"详细结果已保存到: /tmp/ui_analysis_final.json")
    print("=" * 80)

if __name__ == "__main__":
    main()
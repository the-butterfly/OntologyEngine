"""
docs-ui 与代码已有功能全面分析
对比 localhost:3000 当前页面与 examples 期望输出的差异
"""
from playwright.sync_api import sync_playwright
import json
import os

# 分析目标
BASE_URL = "http://localhost:3000"

# examples 目录
EXAMPLES_DIR = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/examples"
DOCS_UI_DIR = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/docs-ui"

def analyze_page(page, url, page_name):
    """分析单个页面的所有元素"""
    page.goto(url)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)  # 等待动态内容

    result = {
        "page": page_name,
        "url": url,
        "title": page.title(),
        "routes": [],
        "buttons": [],
        "links": [],
        "inputs": [],
        "tables": [],
        "headings": [],
        "visible_text": []
    }

    # 获取所有 heading
    for h in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for elem in page.locator(h).all():
            text = elem.inner_text().strip()
            if text:
                result["headings"].append(f"{h}: {text}")

    # 获取所有按钮
    for btn in page.locator('button').all():
        if btn.is_visible():
            text = btn.inner_text().strip()
            result["buttons"].append(text or "[icon-button]")

    # 获取所有链接
    for link in page.locator('a[href]').all():
        if link.is_visible():
            text = link.inner_text().strip()
            href = link.get_attribute('href')
            result["links"].append({"text": text[:50], "href": href})

    # 获取所有输入框
    for inp in page.locator('input, textarea, select').all():
        name = inp.get_attribute('name') or inp.get_attribute('id') or "[unnamed]"
        input_type = inp.get_attribute('type') or 'text'
        result["inputs"].append(f"{name} ({input_type})")

    # 获取表格
    for table in page.locator('table').all():
        headers = [th.inner_text().strip() for th in table.locator('th').all()]
        result["tables"].append({"headers": headers[:10]})  # 最多10列

    # 截图
    screenshot_path = f"/tmp/{page_name.replace('/', '_')}.png"
    page.screenshot(path=screenshot_path, full_page=True)
    result["screenshot"] = screenshot_path

    return result

def load_expected_outputs():
    """加载 examples 的期望输出"""
    expected = {}

    # case1_regulatory_compliance
    case1_expected = os.path.join(EXAMPLES_DIR, "case1_regulatory_compliance/expected_outputs/analysis_result.json")
    if os.path.exists(case1_expected):
        with open(case1_expected) as f:
            expected["case1"] = json.load(f)

    # case4_bi_query_agent - bi_workbench.md
    case4_workbench = os.path.join(EXAMPLES_DIR, "case4_bi_query_agent/visualization/bi_workbench.md")
    if os.path.exists(case4_workbench):
        with open(case4_workbench) as f:
            expected["case4_bi_workbench"] = f.read()

    return expected

def load_docs_ui_design():
    """加载 docs-ui 中的设计文档"""
    designs = {}

    design_files = [
        "01-frontend-architecture-review.md",
        "02-frontend-ux-audit-rfc.md",
        "03-rule-management-ui-design.md",
        "04-simulation-dag-design.md"
    ]

    for fname in design_files:
        fpath = os.path.join(DOCS_UI_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath) as f:
                designs[fname] = f.read()

    return designs

def main():
    print("=" * 80)
    print("docs-ui 与代码已有功能全面分析")
    print("=" * 80)

    # 加载期望输出和设计文档
    expected = load_expected_outputs()
    designs = load_docs_ui_design()

    print(f"\n[1] 已加载 {len(expected)} 个 expected_outputs")
    print(f"[2] 已加载 {len(designs)} 个 docs-ui 设计文档")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 分析管理面
        print("\n" + "=" * 80)
        print("管理面分析")
        print("=" * 80)

        # Space List
        results["space_list"] = analyze_page(page, f"{BASE_URL}/spaces", "SpaceList")

        # Space Detail
        results["space_detail"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space", "SpaceDetail")

        # Schema Declaration
        results["schema_declaration"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space/schema", "SchemaDeclaration")

        # Instance Data
        results["instance_data"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space/instances", "InstanceData")

        # Version History
        results["version_history"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space/versions", "VersionHistory")

        # Rules Embed
        results["rules_embed"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space/rules", "RulesEmbed")

        # Rule Logic Canvas
        results["rule_logic_canvas"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space/rules/demo_group/logic/demo_logic", "RuleLogicCanvas")

        # 分析消费面
        print("\n" + "=" * 80)
        print("消费面分析")
        print("=" * 80)

        # Consumption Views List
        results["consumption_list"] = analyze_page(page, f"{BASE_URL}/consumption", "ConsumptionList")

        # Consumption View Detail
        results["consumption_view"] = analyze_page(page, f"{BASE_URL}/consumption/demo_view", "ConsumptionView")

        # Simulation Embed
        results["simulation_embed"] = analyze_page(page, f"{BASE_URL}/simulation/embed", "SimulationEmbed")

        # Simulation Page
        results["simulation_page"] = analyze_page(page, f"{BASE_URL}/spaces/demo_space/simulate", "SimulationPage")

        # 独立规则管理
        results["rule_group_list"] = analyze_page(page, f"{BASE_URL}/rules", "RuleGroupList")

        browser.close()

    # 输出分析结果
    print("\n" + "=" * 80)
    print("页面元素摘要")
    print("=" * 80)

    for page_name, data in results.items():
        print(f"\n### {page_name} ({data['url']})")
        print(f"  标题: {data['title']}")
        print(f"  按钮: {len(data['buttons'])} 个 - {data['buttons'][:5]}")
        print(f"  链接: {len(data['links'])} 个")
        print(f"  输入框: {len(data['inputs'])} 个")
        print(f"  表格: {len(data['tables'])} 个")
        print(f"  截图: {data['screenshot']}")

    # 保存完整结果
    output_file = "/tmp/ui_analysis_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n完整结果已保存到: {output_file}")

    # 生成差异报告
    print("\n" + "=" * 80)
    print("与期望输出对比 (case4_bi_query_agent)")
    print("=" * 80)

    if "case4_bi_workbench" in expected:
        print("\n[bi_workbench.md 设计目标]:")
        bi_doc = expected["case4_bi_workbench"]
        # 提取关键设计点
        if "经营分析工作台" in bi_doc:
            print("  ✓ 包含'经营分析工作台'设计")
        if "gross_margin_rate" in bi_doc:
            print("  ✓ 包含指标卡 gross_margin_rate")
        if "dso_days" in bi_doc:
            print("  ✓ 包含指标卡 dso_days")
        if "异常门店清单" in bi_doc:
            print("  ✓ 包含'异常门店清单'功能")
        if "区域看板" in bi_doc:
            print("  ✓ 包含'区域看板'功能")
        if "版本变化" in bi_doc:
            print("  ✓ 包含版本 diff 功能")

    print("\n[当前实现检查]:")
    for page_name, data in results.items():
        page_text = " ".join([str(l) for l in data.get('links', [])])
        if "gross_margin" in page_text.lower() or "毛利率" in str(data.get('headings', [])):
            print(f"  ✓ {page_name} 包含毛利率相关内容")
        if "dso" in page_text.lower() or "周转天数" in str(data.get('headings', [])):
            print(f"  ✓ {page_name} 包含 DSO 相关内容")

    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
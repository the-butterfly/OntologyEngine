"""
docs-ui 设计文档 vs 实际实现 详细对比分析
"""
from playwright.sync_api import sync_playwright
import json
import os
import re

BASE_URL = "http://localhost:3000"
DOCS_UI_DIR = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/docs-ui"
EXAMPLES_DIR = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/examples"

def load_design_docs():
    """加载 docs-ui 中的设计文档"""
    designs = {}
    design_files = [
        "03-rule-management-ui-design.md",
        "04-simulation-dag-design.md",
    ]

    for fname in design_files:
        fpath = os.path.join(DOCS_UI_DIR, fname)
        if os.path.exists(fpath):
            with open(fpath) as f:
                designs[fname] = f.read()

    return designs

def load_case_expectations():
    """加载 examples 中的期望"""
    expectations = {}

    # case1 regulatory compliance
    case1_journey = os.path.join(EXAMPLES_DIR, "case1_regulatory_compliance/journey.md")
    if os.path.exists(case1_journey):
        with open(case1_journey) as f:
            expectations["case1_journey"] = f.read()

    # case4 bi query agent
    case4_workbench = os.path.join(EXAMPLES_DIR, "case4_bi_query_agent/visualization/bi_workbench.md")
    if os.path.exists(case4_workbench):
        with open(case4_workbench) as f:
            expectations["case4_bi_workbench"] = f.read()

    case4_journey = os.path.join(EXAMPLES_DIR, "case4_bi_query_agent/journey.md")
    if os.path.exists(case4_journey):
        with open(case4_journey) as f:
            expectations["case4_journey"] = f.read()

    # case3 tax simulation
    case3_journey = os.path.join(EXAMPLES_DIR, "case3_tax_simulation/journey.md")
    if os.path.exists(case3_journey):
        with open(case3_journey) as f:
            expectations["case3_journey"] = f.read()

    return expectations

def extract_design_requirements(doc_content):
    """从设计文档中提取关键设计要点"""
    requirements = {
        "功能模块": [],
        "页面元素": [],
        "交互流程": [],
        "数据展示": []
    }

    # 提取标题
    headings = re.findall(r'^#{1,3}\s+(.+)$', doc_content, re.MULTILINE)
    requirements["功能模块"] = headings

    # 提取关键术语
    key_terms = re.findall(r'\b(?:规则|指标|视图|看板|版本|diff|白名单|仿真|DAG|节点|边)\b', doc_content)
    requirements["数据展示"] = list(set(key_terms))

    return requirements

def analyze_live_pages(page):
    """分析所有活跃页面的实际内容"""
    analysis = {}

    # 需要分析的页面 - 使用实际存在的空间
    pages = [
        ("/spaces", "SpaceList", "空间列表页"),
        ("/spaces/apex-tax-architecture/schema", "SchemaPage", "Schema声明页"),
        ("/spaces/apex-tax-architecture/rules", "RulesPage", "规则管理页"),
        ("/spaces/circular-23-compliance/rules", "RulesPage_C23", "Circular23规则页"),
        ("/consumption", "ConsumptionList", "消费视图列表"),
        ("/simulation/embed", "SimulationEmbed", "仿真嵌入页"),
    ]

    for url, key, desc in pages:
        try:
            page.goto(f"{BASE_URL}{url}", wait_until='networkidle', timeout=15000)
            page.wait_for_timeout(1000)

            # 截图
            page.screenshot(path=f"/tmp/design_diff_{key}.png", full_page=True)

            # 获取页面内容
            body_text = page.locator('body').inner_text()

            # 获取所有可点击元素
            buttons = [b.inner_text().strip() for b in page.locator('button').all() if b.is_visible()]
            links = [l.inner_text().strip()[:50] for l in page.locator('a').all() if l.is_visible()]

            analysis[key] = {
                "url": f"{BASE_URL}{url}",
                "description": desc,
                "body_length": len(body_text),
                "body_preview": body_text[:1000],
                "buttons": buttons[:10],
                "links": links[:10],
                "screenshot": f"/tmp/design_diff_{key}.png"
            }
        except Exception as e:
            analysis[key] = {
                "url": f"{BASE_URL}{url}",
                "description": desc,
                "error": str(e)
            }

    return analysis

def generate_diff_report(designs, expectations, live_analysis):
    """生成差异报告"""
    report = []
    report.append("=" * 80)
    report.append("docs-ui 设计 vs 实际实现 差异分析报告")
    report.append("=" * 80)

    # 1. 设计文档覆盖情况
    report.append("\n[一] 设计文档覆盖情况")
    report.append("-" * 40)
    for fname, content in designs.items():
        word_count = len(content)
        headings = len(re.findall(r'^#{1,3}\s+', content, re.MULTILINE))
        report.append(f"  {fname}: {word_count} 字, {headings} 个章节")

    # 2. 示例案例期望覆盖
    report.append("\n[二] 示例案例期望覆盖")
    report.append("-" * 40)
    for fname, content in expectations.items():
        word_count = len(content)
        report.append(f"  {fname}: {word_count} 字")

    # 3. 实际页面实现情况
    report.append("\n[三] 实际页面实现情况")
    report.append("-" * 40)
    for key, data in live_analysis.items():
        if "error" in data:
            report.append(f"  {key}: 加载失败 - {data['error']}")
        else:
            report.append(f"  {key} ({data['description']}):")
            report.append(f"    URL: {data['url']}")
            report.append(f"    内容长度: {data['body_length']} 字符")
            report.append(f"    按钮数量: {len(data.get('buttons', []))}")
            report.append(f"    链接数量: {len(data.get('links', []))}")

    # 4. 关键差异分析
    report.append("\n[四] 关键差异分析")
    report.append("-" * 40)

    # 检查 rule management UI 设计
    if "03-rule-management-ui-design.md" in designs:
        rule_design = designs["03-rule-management-ui-design.md"]
        if "规则组" in rule_design:
            report.append("  ✓ 设计文档包含'规则组'设计")
        if "DAG" in rule_design:
            report.append("  ✓ 设计文档包含'DAG'设计")
        if "画布" in rule_design or "canvas" in rule_design.lower():
            report.append("  ✓ 设计文档包含'画布'设计")

    # 检查 simulation DAG 设计
    if "04-simulation-dag-design.md" in designs:
        sim_design = designs["04-simulation-dag-design.md"]
        if "仿真" in sim_design:
            report.append("  ✓ 设计文档包含'仿真'设计")
        if "DAG" in sim_design:
            report.append("  ✓ 设计文档包含'DAG'设计")
        if "执行树" in sim_design:
            report.append("  ✓ 设计文档包含'执行树'设计")

    # 5. BI Workbench 期望 vs 实现
    report.append("\n[五] case4_bi_query_agent BI工作台期望 vs 实现")
    report.append("-" * 40)

    if "case4_bi_workbench" in expectations:
        workbench = expectations["case4_bi_workbench"]
        required_features = [
            ("经营分析工作台", "经营分析工作台"),
            ("gross_margin_rate", "毛利率指标"),
            ("dso_days", "DSO指标"),
            ("异常门店清单", "异常门店清单"),
            ("区域看板", "区域看板"),
            ("版本变化", "版本变化"),
        ]

        for keyword, desc in required_features:
            if keyword in workbench:
                # 检查实际分析结果
                found = False
                for key, data in live_analysis.items():
                    if data.get("body_preview", "").find(keyword) != -1:
                        found = True
                        break
                status = "✓ 已实现" if found else "✗ 未实现"
                report.append(f"  {status}: {desc} ({keyword})")

    # 6. 待实现功能清单
    report.append("\n[六] 待实现功能清单")
    report.append("-" * 40)

    unimplemented = []

    # 从 case4 bi_workbench 提取
    if "case4_bi_workbench" in expectations:
        workbench = expectations["case4_bi_workbench"]
        if "gross_margin" in workbench or "毛利率" in workbench:
            unimplemented.append("  - BI工作台的毛利率/DSO等指标卡")
        if "异常门店清单" in workbench:
            unimplemented.append("  - 异常门店清单功能")
        if "证据碎片" in workbench or "pdf" in workbench.lower() or "csv" in workbench.lower():
            unimplemented.append("  - 证据碎片管理（PDF/CSV）")

    # 从 case1 提取
    if "case1_journey" in expectations:
        journey = expectations["case1_journey"]
        if "diff" in journey.lower() or "版本对比" in journey:
            unimplemented.append("  - 规则版本 diff 功能")
        if "证据链" in journey:
            unimplemented.append("  - 证据链功能")
        if "审计" in journey:
            unimplemented.append("  - 审计报告功能")

    if unimplemented:
        for item in unimplemented:
            report.append(item)
    else:
        report.append("  (无)")

    return "\n".join(report)

def main():
    print("=" * 80)
    print("docs-ui 设计文档 vs 实际实现 详细对比分析")
    print("=" * 80)

    # 加载设计文档和期望
    designs = load_design_docs()
    expectations = load_case_expectations()

    print(f"\n已加载 {len(designs)} 个设计文档")
    print(f"已加载 {len(expectations)} 个案例期望")

    # 分析实际页面
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        live_analysis = analyze_live_pages(page)

        browser.close()

    # 生成差异报告
    report = generate_diff_report(designs, expectations, live_analysis)
    print(report)

    # 保存报告
    with open('/tmp/ui_design_diff_report.txt', 'w') as f:
        f.write(report)

    # 保存完整分析数据
    analysis_data = {
        "designs": {k: f"{len(v)} chars" for k, v in designs.items()},
        "expectations": {k: f"{len(v)} chars" for k, v in expectations.items()},
        "live_analysis": live_analysis
    }

    with open('/tmp/ui_design_analysis.json', 'w') as f:
        json.dump(analysis_data, f, indent=2, ensure_ascii=False)

    print(f"\n报告已保存到: /tmp/ui_design_diff_report.txt")
    print(f"数据已保存到: /tmp/ui_design_analysis.json")

if __name__ == "__main__":
    main()
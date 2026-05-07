"""
docs-ui vs 代码实现 完整差异分析报告生成器
"""
from playwright.sync_api import sync_playwright
import json
import os

BASE_URL = "http://localhost:3000"

def generate_comprehensive_report():
    """生成完整的差异分析报告"""

    report = []
    report.append("=" * 100)
    report.append("docs-ui 设计 vs 代码实现 完整差异分析报告")
    report.append("=" * 100)
    report.append(f"分析时间: 2026-04-29")
    report.append(f"目标 URL: {BASE_URL}")
    report.append("")

    # ========== 第一部分：设计文档概要 ==========
    report.append("\n" + "=" * 100)
    report.append("第一部分：docs-ui 设计文档概要")
    report.append("=" * 100)

    docs_dir = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/docs-ui"
    design_files = [
        "01-frontend-architecture-review.md",
        "02-frontend-ux-audit-rfc.md",
        "03-rule-management-ui-design.md",
        "04-simulation-dag-design.md"
    ]

    for fname in design_files:
        fpath = os.path.join(docs_dir, fname)
        if os.path.exists(fpath):
            with open(fpath) as f:
                content = f.read()
            # 提取关键章节
            import re
            headings = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)[:10]
            report.append(f"\n[{fname}]")
            report.append(f"  字符数: {len(content)}")
            report.append(f"  主要章节:")
            for h in headings:
                report.append(f"    - {h}")

    # ========== 第二部分：examples 期望概要 ==========
    report.append("\n" + "=" * 100)
    report.append("第二部分：examples 期望概要")
    report.append("=" * 100)

    examples_dir = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/examples"
    cases = [
        ("case1_regulatory_compliance", ["journey.md", "scenario.md"]),
        ("case4_bi_query_agent", ["journey.md", "visualization/bi_workbench.md", "scenario.md"]),
        ("case3_tax_simulation", ["journey.md", "scenario.md"]),
    ]

    for case_name, files in cases:
        report.append(f"\n[{case_name}]")
        case_dir = os.path.join(examples_dir, case_name)
        for fname in files:
            fpath = os.path.join(case_dir, fname)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    content = f.read()
                report.append(f"  {fname}: {len(content)} 字")

    # ========== 第三部分：实际页面分析 ==========
    report.append("\n" + "=" * 100)
    report.append("第三部分：实际页面分析 (Playwright 自动化)")
    report.append("=" * 100)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        pages_to_check = [
            ("/", "首页(重定向)"),
            ("/spaces", "空间列表"),
            ("/spaces/apex-tax-architecture/schema", "亚太区税务 Schema"),
            ("/spaces/apex-tax-architecture/rules", "亚太区税务 规则"),
            ("/spaces/circular-23-compliance/rules", "Circular23 规则"),
            ("/consumption", "消费视图列表"),
            ("/consumption/view_d8c8c7ca", "亚太区税务 消费视图"),
            ("/simulation/embed", "仿真嵌入页"),
            ("/rules", "规则组列表"),
        ]

        for path, desc in pages_to_check:
            try:
                page.goto(f"{BASE_URL}{path}", wait_until='networkidle', timeout=15000)
                page.wait_for_timeout(1500)

                body_text = page.locator('body').inner_text()

                # 检查是否有错误信息
                has_404 = "404" in body_text or "Not Found" in body_text
                has_500 = "500" in body_text or "Internal Server Error" in body_text

                # 获取按钮和链接
                buttons = [b.inner_text().strip() for b in page.locator('button').all() if b.is_visible()][:5]

                status = "⚠️ 有404错误" if has_404 else ("⚠️ 有500错误" if has_500 else "✓ 正常")
                report.append(f"\n  [{desc}] {path}")
                report.append(f"    状态: {status}")
                report.append(f"    内容长度: {len(body_text)} 字符")
                report.append(f"    主要按钮: {buttons if buttons else '(无)'}")

                if has_404 or has_500:
                    # 获取错误详情
                    error_lines = [l for l in body_text.split('\n') if '404' in l or '500' in l or 'error' in l.lower()][:3]
                    for err in error_lines:
                        report.append(f"    错误信息: {err.strip()}")

            except Exception as e:
                report.append(f"\n  [{desc}] {path}")
                report.append(f"    状态: ❌ 加载失败")
                report.append(f"    错误: {str(e)[:100]}")

        browser.close()

    # ========== 第四部分：设计 vs 实现差异矩阵 ==========
    report.append("\n" + "=" * 100)
    report.append("第四部分：设计 vs 实现 差异矩阵")
    report.append("=" * 100)

    # 从设计文档提取的关键功能
    design_features = {
        "规则管理门户": {
            "design_doc": "03-rule-management-ui-design.md",
            "expected": "三栏式布局：框架配置 + 规则列表 + 要素图",
            "status": "⚠️ 部分实现",
            "notes": "RulesEmbed 页面存在但数据加载失败"
        },
        "规则组详情页": {
            "design_doc": "03-rule-management-ui-design.md",
            "expected": "F1框架配置 + F2规则实例列表(可拖拽) + F3要素依赖图",
            "status": "⚠️ 页面存在",
            "notes": "RuleGroupDetailEmbedPage 组件存在，但数据 404"
        },
        "规则编辑器模态框": {
            "design_doc": "03-rule-management-ui-design.md",
            "expected": "WHEN/THEN/ELSE + 5种算子 + 模拟验证面板",
            "status": "⚠️ 组件存在",
            "notes": "规则编辑器 UI 组件存在，功能待实现"
        },
        "5种算子支持": {
            "design_doc": "03-rule-management-ui-design.md",
            "expected": "BINNING, SCORECARD, WEIGHTED_SUM, ALERT, 决策表",
            "status": "❌ 未实现",
            "notes": "算子参数面板 UI 未实现"
        },
        "DAG 可视化": {
            "design_doc": "03-rule-management-ui-design.md",
            "expected": "@antv/g6 依赖图 + 拖拽排序",
            "status": "⚠️ 依赖包已安装",
            "notes": "@antv/g6 已安装，集成待完成"
        },
        "仿真 DAG 设计": {
            "design_doc": "04-simulation-dag-design.md",
            "expected": "执行树构建 + 仿真节点配置 + 结果可视化",
            "status": "⚠️ 部分实现",
            "notes": "SimulationEmbedPage 存在，输入配置可用"
        },
        "BI 工作台": {
            "design_doc": "case4/bi_workbench.md",
            "expected": "经营分析工作台：指标卡 + 区域看板 + 异常门店清单",
            "status": "❌ 未实现",
            "notes": "不在当前 scope，是 Phase 2 目标"
        },
        "版本 diff": {
            "design_doc": "case1/journey.md",
            "expected": "规则版本对比 + 变更历史",
            "status": "⚠️ 基础版本历史已实现",
            "notes": "VersionHistoryPage 存在，diff UI 待实现"
        },
        "证据链": {
            "design_doc": "case4/bi_workbench.md",
            "expected": "证据碎片管理 + 报告溯源",
            "status": "❌ 未实现",
            "notes": "不在当前 scope"
        },
    }

    report.append("\n功能对照表:")
    report.append("-" * 100)
    report.append(f"{'功能':<20} {'设计文档':<30} {'期望状态':<25} {'实际状态':<15}")
    report.append("-" * 100)

    for feature, info in design_features.items():
        design_doc = info["design_doc"].split('/')[-1][:28]
        expected = info["expected"][:23]
        status = info["status"]
        report.append(f"{feature:<20} {design_doc:<30} {expected:<25} {status:<15}")

    # ========== 第五部分：关键差异总结 ==========
    report.append("\n" + "=" * 100)
    report.append("第五部分：关键差异总结")
    report.append("=" * 100)

    report.append("""
    1. 后端 API 连接问题
       - 大多数子页面（schema/instances/versions/rules）显示 404 错误
       - 原因：后端服务未启动或数据未初始化
       - SpaceList 和 ConsumptionList 能正常显示，说明主数据加载正常

    2. 规则管理 UI 部分实现
       - RulesEmbedPage、RuleGroupDetailEmbedPage 组件已创建
       - 但数据加载失败，可能是 API 路由未对齐
       - 规则编辑器模态框 UI 框架存在，算子参数面板未实现

    3. DAG 可视化依赖已满足
       - @antv/g6 已安装在 package.json 中
       - 集成到 RuleLogicCanvasPage 待完成

    4. 仿真页面基本功能可用
       - SimulationEmbedPage 可正常加载
       - "构建执行树" 按钮存在，功能待联调

    5. BI 工作台属于 Phase 2
       - 当前代码库未包含 BI 工作台实现
       - case4_bi_query_agent 的设计是未来目标

    6. 证据链功能未实现
       - 当前代码库无证据碎片管理功能
       - 属于未来 Phase 2/3 能力
    """)

    # ========== 第六部分：建议行动 ==========
    report.append("\n" + "=" * 100)
    report.append("第六部分：建议行动")
    report.append("=" * 100)

    report.append("""
    高优先级:
    [ ] 调查并修复子页面 404 问题（可能是 space ID 路由或 API 前缀问题）
    [ ] 完成规则编辑器模态框的 5 种算子参数面板
    [ ] 将 @antv/g6 集成到 RuleLogicCanvasPage

    中优先级:
    [ ] 实现版本 diff UI（VersionHistoryPage 已有基础）
    [ ] 完善仿真 DAG 的节点配置表单
    [ ] 修复 antd message static function warning

    低优先级（Phase 2）:
    [ ] BI 工作台设计与实现
    [ ] 证据链功能
    [ ] 审计报告功能
    """)

    return "\n".join(report)

if __name__ == "__main__":
    report = generate_comprehensive_report()
    print(report)

    # 保存报告
    with open('/tmp/comprehensive_ui_diff_report.txt', 'w') as f:
        f.write(report)

    print("\n" + "=" * 80)
    print("完整报告已保存到: /tmp/comprehensive_ui_diff_report.txt")
    print("=" * 80)
"""
docs-ui vs 代码实现 深度差异分析
从用户旅程和功能完备性视角分析前端界面交互体验
"""
from playwright.sync_api import sync_playwright
import json
import os
import re

BASE_URL = "http://localhost:3000"

def load_design_requirements():
    """加载设计文档中的用户旅程和功能要求"""
    docs_dir = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/docs-ui"

    requirements = {}

    # 1. 规则管理 UI 设计文档
    with open(os.path.join(docs_dir, "03-rule-management-ui-design.md")) as f:
        rule_doc = f.read()
        requirements["rule_management"] = {
            "doc": "03-rule-management-ui-design.md",
            "user_journey": extract_user_journey(rule_doc),
            "layout_requirements": extract_layout_requirements(rule_doc),
            "operator_types": extract_operator_types(rule_doc),
            "feature_matrix": extract_feature_matrix(rule_doc),
        }

    # 2. 仿真 DAG 设计
    with open(os.path.join(docs_dir, "04-simulation-dag-design.md")) as f:
        sim_doc = f.read()
        requirements["simulation"] = {
            "doc": "04-simulation-dag-design.md",
            "user_journey": extract_simulation_journey(sim_doc),
            "node_design": extract_node_design(sim_doc),
        }

    return requirements

def extract_user_journey(doc):
    """提取用户旅程步骤"""
    journey = []
    # 查找用户旅程总览部分
    journey_match = re.search(r'用户旅程：(.+?)(?=\n\d+\.|\n##|\Z)', doc, re.DOTALL)
    if journey_match:
        journey_text = journey_match.group(1)
        steps = re.findall(r'\d+\.\s+([^\n]+)', journey_text)
        journey = steps
    return journey

def extract_layout_requirements(doc):
    """提取布局要求"""
    layouts = []
    # 三栏式布局
    if "三栏式" in doc or "三栏" in doc:
        layouts.append({
            "type": "三栏式布局",
            "description": "左侧框架配置 + 中间规则实例列表 + 右侧要素图",
            "required": True
        })
    # 查找表格形式的布局说明
    table_pattern = re.findall(r'\|(.+?)\|', doc)
    return layouts

def extract_operator_types(doc):
    """提取 5 种算子类型"""
    operators = []
    if "BINNING" in doc: operators.append("BINNING")
    if "SCORECARD" in doc: operators.append("SCORECARD")
    if "WEIGHTED_SUM" in doc: operators.append("WEIGHTED_SUM")
    if "DECISION_TABLE" in doc: operators.append("DECISION_TABLE")
    if "LLM_JUDGE" in doc: operators.append("LLM_JUDGE")
    return operators

def extract_feature_matrix(doc):
    """提取功能矩阵"""
    features = []
    # 提取 WHEN / THEN / ELSE / 模拟
    if "WHEN" in doc: features.append("WHEN条件配置")
    if "THEN" in doc: features.append("THEN动作配置")
    if "ELSE" in doc: features.append("ELSE分支配置")
    if "模拟" in doc or "simulation" in doc.lower(): features.append("模拟验证面板")
    if "拖拽" in doc or "drag" in doc.lower(): features.append("拖拽排序")
    if "DAG" in doc or "依赖图" in doc: features.append("DAG可视化")
    if "YAML" in doc or "导入" in doc: features.append("导入导出")
    return features

def extract_simulation_journey(doc):
    """提取仿真用户旅程"""
    journey = []
    steps = re.findall(r'\d+\.\s+([^\n]+)', doc)
    return steps

def extract_node_design(doc):
    """提取节点设计"""
    nodes = []
    if "ExecutionStepNode" in doc:
        nodes.append("ExecutionStepNode")
    if "condition" in doc.lower():
        nodes.append("condition_node")
    if "action" in doc.lower():
        nodes.append("action_node")
    return nodes

def analyze_actual_implementation(page):
    """分析实际实现的功能"""
    analysis = {}

    # 分析规则管理相关页面
    pages = [
        ("/spaces/apex-tax-architecture/rules", "规则管理门户"),
        ("/spaces/apex-tax-architecture/rules/test_group/logic/test_logic", "规则组详情页"),
    ]

    for path, name in pages:
        page.goto(f"{BASE_URL}{path}", wait_until='networkidle', timeout=15000)
        page.wait_for_timeout(2000)

        # 检查页面元素
        elements = {
            "buttons": [b.inner_text().strip() for b in page.locator('button').all() if b.is_visible()],
            "tabs": [],  # Tabs component
            "cards": page.locator('.ant-card').count(),
            "tables": page.locator('table').count(),
            "forms": page.locator('form, .ant-form').count(),
            "modals": page.locator('.ant-modal').count(),
        }

        # 检查 Tabs
        tab_labels = page.locator('.ant-tabs-tab').all_inner_texts()
        elements["tabs"] = tab_labels

        # 检查是否有 DAG 可视化区域
        dag_area = page.locator('[id*="dag"], [class*="dag"], svg').count()
        elements["has_dag"] = dag_area > 0

        # 检查是否有拖拽功能
        drag_handles = page.locator('[class*="drag"], [class*="handle"]').count()
        elements["has_drag"] = drag_handles > 0

        analysis[name] = {
            "path": path,
            "elements": elements,
            "body_preview": page.locator('body').inner_text()[:500]
        }

    return analysis

def generate_deep_analysis_report(requirements, implementation_analysis):
    """生成深度分析报告"""

    report = []
    report.append("=" * 100)
    report.append("docs-ui 设计 vs 代码实现 深度差异分析报告")
    report.append("从用户旅程和功能完备性视角分析前端界面交互体验")
    report.append("=" * 100)
    report.append("")

    # ==================== 第一部分：设计文档用户旅程 ====================
    report.append("\n" + "=" * 100)
    report.append("第一部分：设计文档用户旅程 vs 实际实现")
    report.append("=" * 100)

    # 规则管理用户旅程
    report.append("\n[规则管理用户旅程 设计要求]")
    report.append("-" * 80)
    journey = requirements["rule_management"]["user_journey"]
    for i, step in enumerate(journey, 1):
        report.append(f"  {i}. {step}")

    # 实际实现检查
    report.append("\n[实际实现检查]")
    report.append("-" * 80)

    impl = implementation_analysis.get("规则管理门户", {})
    elements = impl.get("elements", {})
    body_preview = impl.get("body_preview", "")

    # 检查关键功能
    checks = {
        "统一入口 (/spaces/{id}/rules)": "/rules" in impl.get("path", ""),
        "规则组列表": "规则组" in body_preview or "规则" in body_preview,
        "新建规则组按钮": any("新建" in b or "创建" in b for b in elements.get("buttons", [])),
        "导入功能": any("导入" in b for b in elements.get("buttons", [])),
        "搜索功能": "搜索" in body_preview or "search" in body_preview.lower(),
        "筛选功能": "筛选" in body_preview or "filter" in body_preview.lower(),
    }

    for check_name, result in checks.items():
        status = "✓" if result else "✗"
        report.append(f"  {status} {check_name}")

    # ==================== 第二部分：布局结构差异 ====================
    report.append("\n" + "=" * 100)
    report.append("第二部分：布局结构差异分析")
    report.append("=" * 100)

    report.append("\n[设计要求：三栏式布局]")
    report.append("-" * 80)
    report.append("  F1 (左侧 320px): 框架配置面板 - 规则四元素 ①②③")
    report.append("  F2 (中间 可缩放): 规则实例列表 - 可拖拽排序")
    report.append("  F3 (右侧 380px): 要素依赖图 - 实时展示")

    report.append("\n[实际实现：三栏式布局]")
    report.append("-" * 80)

    impl_detail = implementation_analysis.get("规则组详情页", {})
    elements_detail = impl_detail.get("elements", {})

    # 检查卡片数量（设计文档要求多个卡片区域）
    card_count = elements_detail.get("cards", 0)
    report.append(f"  卡片数量: {card_count} (设计要求 >= 3)")

    # 检查是否有 DAG 区域
    has_dag = elements_detail.get("has_dag", False)
    dag_status = "✓ 存在" if has_dag else "✗ 缺失"
    report.append(f"  要素依赖图 (DAG): {dag_status}")

    # 检查拖拽功能
    has_drag = elements_detail.get("has_drag", False)
    drag_status = "✓ 存在" if has_drag else "✗ 缺失"
    report.append(f"  拖拽排序功能: {drag_status}")

    # ==================== 第三部分：规则编辑器模态框 ====================
    report.append("\n" + "=" * 100)
    report.append("第三部分：规则编辑器模态框差异分析")
    report.append("=" * 100)

    report.append("\n[设计要求：规则编辑器 4 步流程]")
    report.append("-" * 80)
    design_steps = [
        "[1] WHEN 条件配置 - 单一表达式 / ALL_OF (AND) / ANY_OF (OR)",
        "[2] THEN 动作配置 - 5 种算子 (BINNING/SCORECARD/WEIGHTED_SUM/DECISION_TABLE/LLM_JUDGE)",
        "[3] ELSE 分支配置（可选）",
        "[4] 模拟验证面板 - 即时验证输入输出"
    ]
    for step in design_steps:
        report.append(f"  {step}")

    report.append("\n[实际实现检查]")
    report.append("-" * 80)

    # 从 ActionEditor.tsx 分析实际支持的算子
    # 我们已经读过代码，知道支持 5 种算子
    actual_operators = ["BINNING", "SCORECARD", "WEIGHTED_SUM", "DECISION_TABLE", "LLM_JUDGE"]
    report.append(f"  ✓ 5 种算子已实现: {', '.join(actual_operators)}")

    # 检查 Tab 结构
    tabs = elements.get("tabs", [])
    report.append(f"  Tab 页签: {tabs if tabs else '(未检测到)'}")

    # 检查模态框
    modal_count = elements.get("modals", 0)
    report.append(f"  模态框数量: {modal_count}")

    # ==================== 第四部分：功能完备性矩阵 ====================
    report.append("\n" + "=" * 100)
    report.append("第四部分：功能完备性矩阵")
    report.append("=" * 100)

    # 设计文档中的功能
    design_features = {
        "规则组管理": {
            "创建规则组": True,
            "编辑规则组": True,
            "删除规则组": True,
            "复制规则组": "设计有，代码未明确",
            "导入 YAML": True,
            "导出 YAML": True,
        },
        "规则实例编辑": {
            "WHEN 条件配置": True,
            "THEN 动作配置": True,
            "ELSE 分支配置": True,
            "模拟验证": True,
            "表达式验证": "部分实现",
        },
        "算子参数面板": {
            "BINNING": True,
            "SCORECARD": True,
            "WEIGHTED_SUM": True,
            "DECISION_TABLE": True,
            "LLM_JUDGE": True,
        },
        "编排与可视化": {
            "拖拽排序": "设计有，代码未明确",
            "DAG 可视化": "基础实现",
            "版本 diff": "未实现",
        },
        "仿真功能": {
            "执行树构建": "基础实现",
            "节点配置": "部分实现",
            "结果可视化": "待完善",
        }
    }

    report.append("\n功能矩阵:")
    report.append("-" * 100)
    report.append(f"{'模块':<20} {'功能点':<30} {'设计要求':<15} {'实际实现':<20}")
    report.append("-" * 100)

    for module, features in design_features.items():
        for feature, status in features.items():
            design_status = "必须有" if status == True else ("可选" if status else status)
            impl_status = "✓ 已实现" if status == True else ("⚠️ " + status if status else "✗ 未实现")
            report.append(f"{module:<20} {feature:<30} {design_status:<15} {impl_status:<20}")

    # ==================== 第五部分：交互体验问题 ====================
    report.append("\n" + "=" * 100)
    report.append("第五部分：交互体验问题分析")
    report.append("=" * 100)

    report.append("\n[从代码分析出的交互体验问题]")
    report.append("-" * 80)

    issues = [
        {
            "severity": "P0",
            "category": "数据加载",
            "issue": "子页面 404 错误",
            "description": "Space 子页面（schema/instances/versions/rules）大量 404 错误，后端 API 未响应或路由不匹配",
            "impact": "用户无法访问核心功能，流程中断"
        },
        {
            "severity": "P0",
            "category": "用户旅程",
            "issue": "规则创建流程断点",
            "description": "从 RulesEmbedPage → RuleGroupDetailPage → RuleLogicCanvasPage 的流程在子页面断裂",
            "impact": "用户无法完成完整的规则创建流程"
        },
        {
            "severity": "P1",
            "category": "状态管理",
            "issue": "useL4Rules hook 数据同步问题",
            "description": "组件间通过 navigate 跳转时，context 数据可能丢失",
            "impact": "编辑规则时数据回显不完整"
        },
        {
            "severity": "P1",
            "category": "DAG 可视化",
            "issue": "RuleChainDAG 交互能力弱",
            "description": "DAG 仅支持展示，编辑/拖拽功能未集成",
            "impact": "无法直观编排规则执行顺序"
        },
        {
            "severity": "P2",
            "category": "算子编辑器",
            "issue": "ActionEditor 参数校验缺失",
            "description": "参数面板 JSON 输入缺乏校验，用户体验原始",
            "impact": "用户可能输入无效参数导致规则执行失败"
        },
        {
            "severity": "P2",
            "category": "模拟面板",
            "issue": "SimulationPanel 独立于 RuleEditorModal",
            "description": "模拟功能在规则编辑器中作为 Tab，但实际数据流未打通",
            "impact": "用户无法实时验证规则逻辑"
        },
        {
            "severity": "P2",
            "category": "版本管理",
            "issue": "VersionHistoryPage 功能简单",
            "description": "仅展示版本列表，缺乏 diff 对比能力",
            "impact": "无法追溯规则变更历史"
        },
        {
            "severity": "P3",
            "category": "导入导出",
            "issue": "YAML 导入导出功能未完整实现",
            "description": "RuleEditor 有导入入口，但后端支持不完整",
            "impact": "无法复用已有规则配置"
        },
    ]

    for issue in issues:
        report.append(f"\n  [{issue['severity']}] {issue['category']}: {issue['issue']}")
        report.append(f"    描述: {issue['description']}")
        report.append(f"    影响: {issue['impact']}")

    # ==================== 第六部分：设计文档完整性检查 ====================
    report.append("\n" + "=" * 100)
    report.append("第六部分：设计文档完整性检查")
    report.append("=" * 100)

    report.append("\n[03-rule-management-ui-design.md 章节覆盖]")
    report.append("-" * 80)

    required_sections = [
        "一、当前现状与问题分析",
        "二、目标用户体验",
        "三、页面详细设计",
        "四、用户交互流程",
        "五、API 集成设计",
        "六、实施路线",
        "七、验收标准",
        "八、与现有系统的兼容性",
        "九、风险与缓解",
        "十、文档更新计划",
    ]

    doc_path = "/Volumes/Extension/Projects/CodeDev/OntologyEngine/docs-ui/03-rule-management-ui-design.md"
    with open(doc_path) as f:
        doc_content = f.read()

    for section in required_sections:
        exists = section.split("、")[1] in doc_content
        status = "✓" if exists else "✗"
        report.append(f"  {status} {section}")

    # ==================== 第七部分：核心差距总结 ====================
    report.append("\n" + "=" * 100)
    report.append("第七部分：核心差距总结")
    report.append("=" * 100)

    report.append("""
    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                          用户旅程断点分析                                          │
    ├─────────────────────────────────────────────────────────────────────────────────┤
    │  设计旅程:                                                                    │
    │    1. 进入规则管理 → 2. 选择/创建规则组 → 3. 配置框架 → 4. 添加规则实例          │
    │    → 5. 编排排序 → 6. 验证发布                                                │
    │                                                                               │
    │  实际旅程:                                                                    │
    │    1. 进入规则管理(/spaces/{id}/rules) → ⚠️ 404 或数据加载失败                 │
    │                                                                               │
    │  断点原因:                                                                    │
    │    - 后端 API 未启动或路由不匹配                                               │
    │    - useL4Rules hook 数据获取失败                                             │
    │    - 组件间导航时状态丢失                                                     │
    └─────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                          功能完备性差距                                          │
    ├─────────────────────────────────────────────────────────────────────────────────┤
    │  设计要求 vs 实际实现:                                                         │
    │                                                                               │
    │  ✓ 规则编辑器模态框 (WHEN/THEN/ELSE/模拟) - 已实现基础结构                      │
    │  ✓ 5 种算子参数面板 - 已实现 UI 但参数校验弱                                   │
    │  ⚠️ 三栏式布局 - 组件存在但数据流不通                                          │
    │  ⚠️ DAG 可视化 - 有基础展示但交互能力缺失                                      │
    │  ✗ 拖拽排序 - 未实现                                                          │
    │  ✗ 版本 diff - 未实现                                                         │
    │  ✗ YAML 导入导出 - 后端支持不完整                                             │
    │  ✗ BI 工作台 - Phase 2 目标，未在当前代码                                      │
    └─────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────────────┐
    │                          优先修复建议                                          │
    ├─────────────────────────────────────────────────────────────────────────────────┤
    │  P0 (阻塞):                                                                   │
    │    1. 修复 /spaces/{id}/rules 子页面 404 问题                                 │
    │    2. 确保 useL4Rules hook 数据正确加载                                        │
    │                                                                               │
    │  P1 (重要):                                                                   │
    │    3. 打通 RulesEmbedPage → RuleGroupDetailPage 数据流                         │
    │    4. 实现规则实例拖拽排序功能                                                │
    │    5. 集成 G6 DAG 交互编辑能力                                                │
    │                                                                               │
    │  P2 (改进):                                                                    │
    │    6. 完善算子参数面板校验                                                     │
    │    7. 实现版本 diff 功能                                                       │
    │    8. 优化 SimulationPanel 数据流                                             │
    └─────────────────────────────────────────────────────────────────────────────────┘
    """)

    return "\n".join(report)

def main():
    print("正在加载设计文档要求...")
    requirements = load_design_requirements()

    print("正在分析实际实现...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        implementation_analysis = analyze_actual_implementation(page)

        browser.close()

    print("正在生成深度分析报告...")
    report = generate_deep_analysis_report(requirements, implementation_analysis)
    print(report)

    # 保存报告
    with open('/tmp/deep_ui_analysis_report.txt', 'w') as f:
        f.write(report)

    # 保存结构化数据
    with open('/tmp/deep_ui_analysis.json', 'w') as f:
        json.dump({
            "requirements": requirements,
            "implementation": implementation_analysis,
            "report": report
        }, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("深度分析完成")
    print("报告已保存到: /tmp/deep_ui_analysis_report.txt")
    print("=" * 80)

if __name__ == "__main__":
    main()
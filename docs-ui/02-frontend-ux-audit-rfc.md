# OntologyEngine 前端 UX 审计与改进 RFC

> **类型**: RFC / 设计文档
> **版本**: v1.0
> **日期**: 2026-04-15
> **作者**: Claude (AI Assistant)
> **基准代码**: `ontology-engine-ui/` + `ontology_engine/`
> **状态**: 待评审

---

## 摘要

通过对 `ontology-engine-ui` 前端进行 Playwright 浏览器自动化测试，发现 **7 个关键 UX 问题**，涵盖 UI 渲染缺陷、导航歧义、数据流断点、可视化组件未集成四个维度。本文档提供完整的根因分析和改进方案。

**问题分级**:
- **P0**: 阻断性问题 - 直接影响核心功能使用
- **P1**: 重要缺陷 - 影响用户效率或数据准确性
- **P2**: 改进建议 - 优化体验但非阻断

---

## 1. 问题详细分析

### 1.1 P0: Space 头部标签渲染错误

**文件**: `ontology-engine-ui/src/pages/spaces/SpaceDetailPage.tsx` (第 106 行附近)

**现象**: Space 详情页顶部标签区域显示的是 fact object 的属性名和类型（如 `entity_id: string`, `company_name: string`），而不是语义元数据。

**Playwright 验证**:
```
Space tags: ['v1', 'DRAFT', '1 实体', '1 规则声明', '1 规则逻辑',
            'entity_id: string', 'company_name: string', 'annual_revenue: Money']
                                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                         错误：这些是 fact object 的属性，不是 space 元数据
```

**根因**: 代码错误地将 `factObjects` 数组的每个对象的 `properties` 展开渲染在标签区，而不是显示 space 的结构化元数据。

**当前代码**:
```typescript
// 错误实现
<Space style={{ marginBottom: 16 }}>
  <Tag color="blue">v{activeSpace.version}</Tag>
  <Tag>{activeSpace.entity_count} 实体</Tag>
  {/* BUG: 错误地渲染 fact object 属性 */}
  {factObjects.map((fo: any) =>
    fo.properties?.map((p: any) => (
      <Tag>{p.name}: {p.type}</Tag>
    ))
  )}
</Space>
```

**修复方案**:
```typescript
// 正确实现
<Space style={{ marginBottom: 16 }}>
  <Tag color="blue">v{activeSpace.version}</Tag>
  <Tag color={activeSpace.status === 'active' ? 'green' : 'orange'}>
    {activeSpace.status.toUpperCase()}
  </Tag>
  <Tag>{activeSpace.entity_count ?? 0} 实体</Tag>
  <Tag>{activeSpace.rule_definition_count ?? 0} 规则声明</Tag>
  <Tag>{activeSpace.rule_logic_count ?? 0} 规则逻辑</Tag>
  {activeSpace.view_id && (
    <Tag color="purple">视图: {activeSpace.view_id}</Tag>
  )}
</Space>
```

**验收标准**:
- [ ] 头部标签只显示：版本、状态、实体数、规则数、视图 ID
- [ ] 不再显示 fact object 属性名或类型

---

### 1.2 P0: 菜单导航选择器歧义

**文件**: `ontology-engine-ui/src/pages/spaces/SpaceDetailPage.tsx` (第 67-76 行)

**现象**: Playwright 自动化测试中出现 `strict mode violation`，因为 `text=规则声明` 同时匹配了：
1. 菜单项 `<span class="ant-menu-title-content">规则声明</span>`
2. Tab 徽章 `<span class="ant-tag">1 规则声明</span>`

**Playwright 错误**:
```
Locator.click: Error: strict mode violation: locator("text=规则声明")
resolved to 2 elements:
  1) <span class="ant-tag">1 规则声明</span>
  2) <span class="ant-menu-title-content">规则声明</span>
```

**根因**: `getSelectedKey()` 函数使用 `path.includes(suffix)` 匹配，当路径包含 `/rules/declarations` 时，同时也匹配了 badge 文本。

**当前代码**:
```typescript
const getSelectedKey = () => {
  const path = location.pathname;
  const suffixes = ['schema', 'rules/declarations', 'rules/logics', ...];
  for (const suffix of suffixes) {
    if (path.includes(`/${suffix}`)) {  // 过于宽泛
      return suffix;
    }
  }
  return 'schema';
};
```

**修复方案 A**: 使用精确路径匹配
```typescript
const getSelectedKey = () => {
  const path = location.pathname;
  // 精确匹配，避免歧义
  if (path.endsWith('/rules/declarations')) return 'rules/declarations';
  if (path.endsWith('/rules/logics')) return 'rules/logics';
  if (path.endsWith('/schema')) return 'schema';
  if (path.endsWith('/instances')) return 'instances';
  if (path.endsWith('/versions')) return 'versions';
  if (path.endsWith('/visualize')) return 'visualize';
  if (path.endsWith('/execute')) return 'execute';
  if (path.endsWith('/simulate')) return 'simulate';
  return 'schema';
};
```

**修复方案 B**: 使用语义化 Role Selector（Playwright 最佳实践）
```typescript
// 在 SpaceDetailPage 菜单项添加 testid
const menuItems = [
  { key: 'schema', icon: <ApartmentOutlined />, label: 'Schema 声明', testId: 'menu-schema' },
  { key: 'rules/declarations', icon: <SettingOutlined />, label: '规则声明', testId: 'menu-rules-declarations' },
  // ...
];

// Playwright 测试使用
page.getByTestId('menu-rules-declarations').click();
```

**推荐方案**: A + B 结合使用，同时修复前端代码和提升测试健壮性。

**验收标准**:
- [ ] 菜单高亮逻辑精确匹配当前路由
- [ ] Playwright 测试使用 role selector 或 testid，无歧义

---

### 1.3 P1: Space 激活状态阻塞消费面功能

**文件**: `ontology-engine-ui/src/pages/spaces/SpaceDetailPage.tsx` (第 133-151 行)

**现象**: 大部分测试空间处于 `DRAFT` 状态，用户无法访问消费面功能（Schema 可视化、规则执行、What-If 模拟），页面显示警告但流程不清晰。

**当前 UX 流程**:
```
创建空间 → DRAFT 状态 → 手动 API 调用激活 → 仍需手动创建消费视图 → 才能使用消费面
```

**问题**:
1. 用户不知道如何激活空间（`docs/11-frontend-user-guide.md` 提示需要 API 调用）
2. 激活后消费视图数据可能为空
3. 警告提示不引导用户操作

**当前警告代码**:
```typescript
{isConsumptionRoute() && !activeSpace.view_id && (
  <Alert
    message="消费视图未创建"
    description="请先激活空间以创建消费视图，才能使用可视化、规则执行和模拟功能。"
    type="warning"
    showIcon
  />
)}
```

**改进 UX 方案**:

**Phase 1: 前端引导优化**
```typescript
{isConsumptionRoute() && !activeSpace.view_id && (
  <Alert
    message="消费视图未创建"
    description={
      <div>
        <p>请先激活空间以创建消费视图，才能使用可视化、规则执行和模拟功能。</p>
        <Button
          type="primary"
          size="small"
          onClick={async () => {
            await activateSpace(spaceId);
            message.success('空间已激活，正在创建消费视图...');
          }}
        >
          一键激活并创建视图
        </Button>
      </div>
    }
    type="warning"
    showIcon
  />
)}

{isConsumptionRoute() && activeSpace.view_id && activeSpace.status !== 'active' && (
  <Alert
    message="空间未激活"
    description={
      <div>
        <p>请先激活空间后才能使用消费视图功能。</p>
        <Button
          type="primary"
          size="small"
          onClick={async () => {
            await activateSpace(spaceId);
            message.success('空间已激活');
          }}
        >
          激活空间
        </Button>
      </div>
    }
    type="warning"
    showIcon
  />
)}
```

**Phase 2: 后端数据同步**
- 激活空间时自动同步 Schema 数据到消费视图
- 或提供"加载示例数据"按钮

**验收标准**:
- [ ] DRAFT 状态空间在消费面页面显示激活引导按钮
- [ ] 点击"一键激活"能完成激活 + 视图创建流程
- [ ] 激活后自动刷新页面状态

---

### 1.4 P1: L2/L3 Schema 数据为空

**文件**: `ontology-engine-ui/src/pages/spaces/SchemaDeclarationPage.tsx`

**现象**: Schema 声明页面的 L2 分类体系和 L3 分析要素 Tab 显示为 0，尽管 L1 有数据。

**Playwright 验证**:
```
Schema tabs: [' L1 事实对象\n1', ' L2 分类体系', ' L3 分析要素', ' L4 业务规则\n1']
L1 rows: 1
L2 count: 0
L3 count: 0
```

**根因分析**:

1. **可能性 A**: `schema/overview` API 返回的 `L2.items` 和 `L3.items` 确实为空
2. **可能性 B**: API 返回了数据但前端没有正确解析
3. **可能性 C**: YAML 导入时 L2/L3 数据未被加载

**诊断步骤**:
```bash
# 检查 API 返回
curl http://localhost:8000/v1/management/{spaceId}/schema/overview
```

**检查代码** (SchemaDeclarationPage.tsx 第 294-299 行):
```typescript
const overview = schemaOverview || {
  L1: { count: factObjects.length, items: factObjects },
  L2: { count: 0, items: [] },  // 可能问题在这里
  L3: { count: 0, items: [] },
  L4: { ... },
};
```

**改进方案**:

**方案 A: 确认后端数据完整性**
```typescript
// 检查 overview 中 L2/L3 是否真正为空
useEffect(() => {
  const loadOverview = async () => {
    const data = await spaceApi.getSchemaOverview(activeSpaceId);
    console.log('L2 items:', data.L2);  // 调试
    console.log('L3 items:', data.L3);  // 调试
    setSchemaOverview(data);
  };
}, [activeSpaceId]);
```

**方案 B: 添加 L2/L3 创建功能**
如果后端支持 L2/L3 的 CRUD API：
- L2: `POST /v1/management/{spaceId}/schema/L2/categorizations`
- L3: `POST /v1/management/{spaceId}/schema/L3/elements`

前端需要添加创建 Modal 表单（参考 `RuleDeclarationsPage.tsx` 的 CRUD Modal）。

**方案 C: 明确标注数据来源**
如果 L2/L3 必须通过 YAML 导入：
- 在 Tab 标题旁添加"通过 YAML 导入"提示
- 添加示例 YAML 路径按钮

**验收标准**:
- [ ] 确认 L2/L3 数据为空是 API 问题还是 UI 问题
- [ ] 如有数据，正确显示 L2/L3 表格
- [ ] 如需导入，提供清晰的导入引导

---

### 1.5 P2: SchemaGraph G6 可视化交互不清晰

**文件**: `ontology-engine-ui/src/components/schema/SchemaGraph.tsx`

**现象**: G6 图渲染了 canvas，但节点交互（如点击、悬停高亮）效果不明确，节点详情面板的触发条件不清晰。

**Playwright 观察**:
```
Canvas elements: 1
Graph types: 实体关系|指标依赖|全景图|规则概览
```

**问题分析**:

1. **节点点击**: 当前 `onNodeClick` 设置 `selectedNode`，但 `NodeDetailPanel` 需要 node 对象
2. **悬停高亮**: `highlightDependencies` 函数存在但依赖图数据可能不完整
3. **导出功能**: `toDataURL` 可能因 G6 异步渲染导致图片不完整

**当前实现问题**:
```typescript
// SchemaGraph.tsx 第 221-233 行
graph.on('node:click', (evt: any) => {
  const nodeId = evt.target?.id;  // 问题：evt.target 可能不是 node
  if (nodeId && data && !isDestroyedRef.current) {
    const node = data.nodes.find(n => n.id === nodeId);
    onNodeClick?.(node || null);  // 问题：找不到时传入 null
  }
});
```

**改进方案**:

**1. 增强节点点击处理**
```typescript
graph.on('node:click', (evt: any) => {
  const nodeId = evt.target?.id;
  if (!nodeId) return;

  // 使用 graph.getNodeData() 获取完整节点数据
  const nodeData = graph.getNodeData(nodeId);
  if (nodeData && data) {
    const originalNode = data.nodes.find(n => n.id === nodeId);
    if (originalNode) {
      onNodeClick?.(originalNode);
      graph.setElementState(nodeId, 'selected');
    }
  }
});
```

**2. 增强悬停效果**
```typescript
graph.on('node:mouseenter', (evt: any) => {
  const nodeId = evt.target?.id;
  if (nodeId) {
    onNodeHover?.(nodeId);
    highlightDependencies(graph, nodeId);
  }
});

graph.on('node:mouseleave', () => {
  onNodeHover?.(null);
  clearHighlights(graph);
});
```

**3. 修复图片导出时序**
```typescript
// 在 exportImage 中等待布局完成
exportImage: async () => {
  if (graphRef.current) {
    try {
      const graph = graphRef.current;
      // 等待所有动画和布局完成
      await graph.waitForRender();
      await new Promise(resolve => setTimeout(resolve, 500));  // 额外等待

      const dataURL = await graph.toDataURL({
        type: 'image/png',
        encoderOptions: 1.0,
      });
      return dataURL;
    } catch (e) {
      console.error('Failed to export graph:', e);
      return null;
    }
  }
  return null;
}
```

**验收标准**:
- [ ] 节点点击后右侧面板正确显示节点详情
- [ ] 节点悬停时高亮相邻节点和边
- [ ] 图片导出包含完整的渲染内容

---

### 1.6 P2: RuleChainDAG 组件未在消费面集成

**文件**: `ontology-engine-ui/src/pages/consumption/RuleExecutionPage.tsx`

**现象**: `RuleChainDAG.tsx` 组件已实现并用于 `RuleLogicsPage` (管理面)，但 `RuleExecutionPage` (消费面) 的"规则依赖图"Tab 使用的是自定义表格渲染，而非 G6 DAG 图。

**当前实现** (RuleExecutionPage.tsx 第 361-505 行):
```typescript
const renderDependencyGraph = () => {
  // 使用自定义表格渲染，而非 G6 DAG
  return (
    <div>
      <Row>...</Row>
      <Card>拓扑执行顺序</Card>
      <Card>规则节点详情</Card>
      <Card>数据依赖关系</Card>
      <Card>互斥规则对</Card>
    </div>
  );
};
```

**改进方案**:

**在消费面使用统一的 DAG 组件**:
```typescript
import RuleChainDAG from '../../components/rule/RuleChainDAG';
import type { RuleChainGraphData } from '../../types/visualization';

const DependencyGraphTab = () => {
  const [dagData, setDagData] = useState<RuleChainGraphData | null>(null);

  // 从 dependencyGraph 数据转换
  const transformToRuleChainData = (depGraph: any): RuleChainGraphData => {
    return {
      dimension: depGraph.dimension || 'dependency',
      nodes: depGraph.nodes.map((n: any) => ({
        id: n.id,
        position: { x: 0, y: 0 },  // G6 自动布局
        data: {
          ruleId: n.id,
          ruleName: n.label,
          ruleType: n.rule_type,
          priority: n.priority,
        },
      })),
      edges: depGraph.edges.map((e: any) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        data: { type: 'dependency' },
      })),
      dimension_info: {
        name: '规则依赖图',
        description: '规则执行依赖关系',
        applicable_entities: [],
        rule_count: depGraph.nodes.length,
      },
    };
  };

  if (!dagData) {
    return <Spin>加载中...</Spin>;
  }

  return (
    <div style={{ height: 600 }}>
      <RuleChainDAG
        chainData={dagData}
        executionSteps={executionSteps}
        currentStep={currentStep}
        onNodeClick={(nodeId) => {
          // 显示节点详情
          const node = dagData.nodes.find(n => n.id === nodeId);
          setSelectedRule(node);
        }}
      />
    </div>
  );
};
```

**验收标准**:
- [ ] 消费面"规则依赖图"Tab 使用 `RuleChainDAG` 组件
- [ ] DAG 节点可点击，弹出规则详情
- [ ] 执行步骤可在 DAG 上高亮显示

---

### 1.7 P2: ExecutionReplay 组件存在但未集成

**文件**: `ontology-engine-ui/src/components/rule/ExecutionReplay.tsx`

**现象**: `ExecutionReplay.tsx` 组件已存在，提供了步骤回放功能，但未集成到 `RuleExecutionPage` 或 `SimulationPage` 中。

**当前状态**:
- `ExecutionReplay.tsx` 已实现完整的时间线回放 UI
- `StepDetailPanel.tsx` 已实现步骤详情面板
- 但 RuleExecutionPage 使用内联折叠面板渲染步骤

**改进方案**:

**在 RuleExecutionPage 中添加"回放视图"切换**:
```typescript
const [viewMode, setViewMode] = useState<'table' | 'replay'>('table');

const tabItems = [
  {
    key: 'result',
    label: '执行结果',
    children: viewMode === 'table' ? renderExecutionTable() : <ExecutionReplay steps={steps} />,
  },
  // ...
];

// 添加工具栏切换
<Space>
  <Segmented
    value={viewMode}
    onChange={(v) => setViewMode(v as 'table' | 'replay')}
    options={[
      { value: 'table', label: '表格' },
      { value: 'replay', label: '回放' },
    ]}
  />
</Space>
```

**验收标准**:
- [ ] 执行结果 Tab 支持"表格"和"回放"两种视图切换
- [ ] 回放视图使用 `ExecutionReplay` 组件
- [ ] 步骤详情面板使用 `StepDetailPanel` 组件

---

## 2. 问题优先级矩阵

| 优先级 | 问题 | 影响 | 修复复杂度 |
|-------|------|------|-----------|
| **P0** | Space 头部标签渲染错误 | 误导用户，界面丑陋 | 低 |
| **P0** | 菜单导航选择器歧义 | Playwright 测试失败 | 低 |
| **P1** | Space 激活状态阻塞消费面 | 无法测试核心功能 | 中 |
| **P1** | L2/L3 Schema 数据为空 | Schema 声明不完整 | 中（需后端确认） |
| **P2** | SchemaGraph G6 交互不清晰 | 可视化体验不佳 | 中 |
| **P2** | RuleChainDAG 未在消费面集成 | DAG 功能重复实现 | 中 |
| **P2** | ExecutionReplay 未集成 | 回放功能不可用 | 低 |

---

## 3. 改进实施计划

### Phase 1: P0 问题修复 (1-2 天)

| # | 任务 | 文件 | 预估工时 |
|---|------|------|---------|
| 1.1 | 修复 Space 头部标签渲染 | `SpaceDetailPage.tsx` | 1h |
| 1.2 | 修复菜单高亮逻辑 + 添加 testid | `SpaceDetailPage.tsx` | 2h |

### Phase 2: P1 问题修复 (2-3 天)

| # | 任务 | 文件 | 预估工时 |
|---|------|------|---------|
| 2.1 | 添加激活引导按钮 | `SpaceDetailPage.tsx` | 2h |
| 2.2 | 诊断 L2/L3 数据问题 | `SchemaDeclarationPage.tsx` + 后端 | 4h |
| 2.3 | 如需要，添加 L2/L3 创建 Modal | `SchemaDeclarationPage.tsx` | 4h |

### Phase 3: P2 问题修复 (3-4 天)

| # | 任务 | 文件 | 预估工时 |
|---|------|------|---------|
| 3.1 | 增强 SchemaGraph 交互 | `SchemaGraph.tsx` | 4h |
| 3.2 | 集成 RuleChainDAG 到消费面 | `RuleExecutionPage.tsx` | 4h |
| 3.3 | 集成 ExecutionReplay 组件 | `RuleExecutionPage.tsx` | 2h |

---

## 4. 测试验收标准

### Playwright E2E 测试用例

```python
def test_space_detail_header():
    """P0: Space 头部只显示语义元数据，不显示 fact object 属性"""
    page.goto("/spaces/供应链金融演示")
    tags = page.locator(".ant-space .ant-tag").all_inner_texts()
    assert "entity_id" not in str(tags)
    assert "company_name" not in str(tags)
    assert "DRAFT" in str(tags) or "ACTIVE" in str(tags)

def test_menu_navigation_no_ambiguity():
    """P0: 菜单导航无选择器歧义"""
    page.goto("/spaces/供应链金融演示")
    # 使用精确选择器
    page.get_by_role("menuitem", name="规则声明").click()
    assert "/rules/declarations" in page.url

def test_activation_button_visible():
    """P1: 消费面页面显示激活引导按钮"""
    page.goto("/spaces/测试空间/visualize")
    # 如果是 DRAFT 状态，应显示激活按钮
    if page.locator(".ant-alert").is_visible():
        activate_btn = page.locator("button:has-text('激活')")
        assert activate_btn.is_visible()

def test_schema_graph_node_click():
    """P2: Schema 图节点点击显示详情"""
    page.goto("/spaces/供应链金融演示/visualize")
    page.wait_for_selector("canvas", timeout=5000)
    # 点击第一个节点
    page.locator("canvas").click(position={"x": 100, "y": 100})
    # 检查右侧面板是否显示详情
    detail_panel = page.locator(".detail-panel")
    assert detail_panel.is_visible()
```

---

## 5. 相关文档

| 文档 | 关系 |
|------|-----|
| [`docs-ui/01-frontend-architecture-review.md`](./01-frontend-architecture-review.md) | 前端架构审查基准 |
| [`docs/08-visualization-system.md`](../docs/08-visualization-system.md) | 可视化系统设计规范 |
| [`docs/11-frontend-user-guide.md`](../docs/11-frontend-user-guide.md) | 前端用户操作指南 |
| [`examples/README.md`](../examples/README.md) | 示例案例说明 |

---

## 6. 变更日志

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-04-15 | v1.0 | 初始版本，基于 Playwright 浏览器测试结果 |

---

## 附录 A: Playwright 测试脚本

见 [`explore_ui.py`](./explore_ui.py) 和 [`explore_ui2.py`](./explore_ui2.py)

## 附录 B: 截图证据

| 截图 | 问题 |
|------|------|
| `/tmp/01-spaces-list.png` | Space 列表 |
| `/tmp/03-space-detail.png` | Space 详情头部标签问题 |
| `/tmp/schema-tab.png` | Schema 声明 L1 数据 |
| `/tmp/rule-declarations.png` | 规则声明表格 |
| `/tmp/schema-visualization.png` | G6 可视化 canvas |
| `/tmp/rule-execution.png` | 规则执行页面 |
| `/tmp/simulation.png` | What-If 模拟页面 |

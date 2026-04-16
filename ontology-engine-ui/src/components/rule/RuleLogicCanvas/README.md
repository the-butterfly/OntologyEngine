# 规则逻辑 DAG 画布设计

## 1. 设计目标

将"编辑规则"从 Schema 声明中分离，形成独立的规则逻辑画布：

| 动作 | 位置 | 功能 |
|------|------|------|
| **规则定义** | RuleGroupDetailEmbedPage | Schema 声明：基础信息、作用对象、适用场景、输入输出要素 |
| **编辑逻辑** | RuleLogicCanvasPage | DAG 画布：编排计算节点、配置算子参数、设置执行顺序 |

## 2. 数据模型

### 2.1 DAG 节点类型

```typescript
// 节点类型枚举
type DAGNodeType =
  | 'input'        // 输入要素节点（继承自规则组）
  | 'output'       // 输出要素节点（继承自规则组）
  | 'binning'      // 分箱
  | 'scorecard'    // 评分卡
  | 'weighted_sum'  // 加权计算
  | 'decision_table' // 决策表
  | 'llm_judge'    // LLM定性分析
  | 'switch'       // 条件分支
  | 'compute';     // 计算公式

// DAG 节点
interface DAGNode {
  id: string;
  type: DAGNodeType;
  label: string;
  position: { x: number; y: number };
  config: Record<string, unknown>;  // 算子配置参数
  inputs: string[];   // 连接的输入节点ID
  outputs: string[];  // 连接的输出节点ID
}

// DAG 边
interface DAGEdge {
  id: string;
  source: string;     // 源节点ID
  target: string;     // 目标节点ID
  sourceHandle?: string;  // 源端口
  targetHandle?: string;  // 目标端口
}

// DAG 数据
interface DAGData {
  nodes: DAGNode[];
  edges: DAGEdge[];
}
```

### 2.2 算子配置结构

```typescript
// 分箱配置
interface BinningConfig {
  input: string;       // 输入变量名
  output: string;      // 输出变量名
  inclusive_max: boolean;
  bins: Array<{
    range: [number, number];
    label: string;
  }>;
}

// 评分卡配置
interface ScorecardConfig {
  output: string;
  baseline: number;
  post_formula?: string;
  variables: Array<{
    name: string;
    points: Record<string, number>;
  }>;
}

// 加权计算配置
interface WeightedSumConfig {
  output: string;
  weights: Array<{
    input: string;
    weight: number;
  }>;
  grade_multipliers?: Record<string, number>;
  grade_input?: string;
}

// 决策表配置
interface DecisionTableConfig {
  conditions: Array<{
    variable: string;
    format?: string;
  }>;
  output: string;
  matrix: Array<{
    when: Record<string, string>;
    result: string;
    default?: string;
  }>;
}

// LLM定性分析配置
interface LLMJudgeConfig {
  output: string;
  prompt_template: string;
  input_mapping: Record<string, string>;
  expected_format?: string;
  confidence_threshold?: number;
  timeout_ms?: number;
  fallback_value?: string;
}

// 计算公式配置
interface ComputeConfig {
  formula: string;
  output_field: string;
}
```

## 3. 组件架构

```
RuleLogicCanvasPage
├── Header (标题、操作按钮)
├── Toolbar
│   ├── 算子选择器 (拖拽添加)
│   ├── 保存/撤销/重做
│   └── 视图控制 (缩放、全屏)
├── DAGCanvas (React Flow)
│   ├── Nodes
│   │   ├── InputNode (输入要素)
│   │   ├── OutputNode (输出要素)
│   │   ├── BinningNode
│   │   ├── ScorecardNode
│   │   ├── WeightedSumNode
│   │   ├── DecisionTableNode
│   │   ├── LLMJudgeNode
│   │   ├── SwitchNode
│   │   └── ComputeNode
│   └── Edges (连线)
├── ConfigPanel (右侧配置面板)
│   └── OperatorConfigForm
└── MiniMap (小地图)
```

## 4. 算子节点设计

### 4.1 节点外观

| 节点类型 | 颜色 | 图标 | 描述 |
|----------|------|------|------|
| Input | #1890ff (蓝) | Input | 输入要素 |
| Output | #52c41a (绿) | Output | 输出要素 |
| Binning | #722ed1 (紫) | BarChart | 分箱离散化 |
| Scorecard | #fa8c16 (橙) | Star | 评分卡计算 |
| WeightedSum | #f5222d (红) | Calculator | 加权求和 |
| DecisionTable | #faad14 (黄) | Table | 决策矩阵 |
| LLMJudge | #13c2c2 (青) | Robot | LLM定性分析 |
| Switch | #eb2f96 (粉) | ForkRight | 条件分支 |
| Compute | #8c8c8c (灰) | Function | 公式计算 |

### 4.2 节点结构

```
┌─────────────────────────────────────┐
│ ● [图标] 节点名称            [⋮]  │  ← 头部：颜色条、图标、名称、操作菜单
├─────────────────────────────────────┤
│ 输入: [变量1] [变量2]              │  ← 端口区：输入端口
├─────────────────────────────────────┤
│ 输出: [结果变量]                    │  ← 端口区：输出端口
├─────────────────────────────────────┤
│ 状态: 已配置 / 未配置               │  ← 底部：状态指示
└─────────────────────────────────────┘
```

## 5. 交互设计

### 5.1 添加节点

1. 从左侧工具栏拖拽算子到画布
2. 或点击算子图标，自动添加到画布中央
3. 新节点默认命名为"新节点 + 序号"

### 5.2 连接节点

1. 从输出端口拖拽到输入端口
2. 连线过程中显示可连接的目标端口高亮
3. 不允许循环依赖（拓扑排序验证）

### 5.3 配置节点

1. 点击节点，打开右侧配置面板
2. 配置表单根据节点类型动态渲染
3. 输入输出变量可从下拉列表选择（继承自规则组）
4. 保存后节点状态更新

### 5.4 删除节点

1. 选中节点 → Delete 键或右键菜单
2. 删除时清理所有相关连线
3. 确认对话框防止误删

## 6. 画布功能

### 6.1 画布操作

- 平移：鼠标拖拽空白区域
- 缩放：滚轮缩放，范围 25% - 200%
- 选中：单击节点选中，Ctrl+单击多选
- 框选：鼠标框选多个节点
- 全屏：F11 或点击全屏按钮

### 6.2 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+S | 保存 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Delete | 删除选中 |
| Ctrl+A | 全选 |
| Escape | 取消选中 |

## 7. 数据持久化

### 7.1 保存格式

```typescript
// 保存到后端的格式
interface RuleLogicSaveData {
  rule_id: string;           // 规则定义ID
  logic_id?: string;         // 逻辑ID（更新时）
  dag_data: DAGData;         // DAG数据
  version: number;           // 版本号
}
```

### 7.2 API 接口

```
GET    /v1/management/{spaceId}/schema/L4/rules/logics/{logicId}
PUT    /v1/management/{spaceId}/schema/L4/rules/logics/{logicId}
POST   /v1/management/{spaceId}/schema/L4/rules/logics
DELETE /v1/management/{spaceId}/schema/L4/rules/logics/{logicId}
```

## 8. 技术实现

### 8.1 技术栈

- **画布引擎**: React Flow (@xyflow/react)
- **状态管理**: Zustand
- **UI 组件**: Ant Design 5
- **拖拽**: dnd-kit

### 8.2 目录结构

```
src/
├── components/rule/
│   ├── RuleLogicCanvas/
│   │   ├── index.tsx
│   │   ├── DAGCanvas.tsx
│   │   ├── nodes/
│   │   │   ├── BaseNode.tsx
│   │   │   ├── InputNode.tsx
│   │   │   ├── OutputNode.tsx
│   │   │   ├── BinningNode.tsx
│   │   │   ├── ScorecardNode.tsx
│   │   │   ├── WeightedSumNode.tsx
│   │   │   ├── DecisionTableNode.tsx
│   │   │   ├── LLMJudgeNode.tsx
│   │   │   ├── SwitchNode.tsx
│   │   │   └── ComputeNode.tsx
│   │   ├── config/
│   │   │   ├── OperatorConfigPanel.tsx
│   │   │   ├── BinningConfigForm.tsx
│   │   │   ├── ScorecardConfigForm.tsx
│   │   │   └── ...
│   │   └── Toolbar.tsx
│   └── types/
│       └── dag.ts
└── pages/spaces/
    └── RuleLogicCanvasPage.tsx
```

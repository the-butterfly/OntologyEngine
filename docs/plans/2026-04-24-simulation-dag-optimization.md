# 模拟执行树 DAG 画布优化 — 改动记录

> 日期: 2026-04-24
> 涉及文件: 3 个核心文件

---

## 一、改动概览

| # | 改动项 | 文件 | 说明 |
|---|--------|------|------|
| 1 | DAG 渲染引擎替换 | `ExecutionDAGCanvas.tsx` | G6 → ReactFlow + dagre |
| 2 | 模拟面板增强 | `SimulationPanel.tsx` | 新增 autoBuild 自动构建 |
| 3 | 嵌入页面增强 | `SimulationEmbedPage.tsx` | 传递 autoBuild 参数 |

---

## 二、详细改动

### 2.1 ExecutionDAGCanvas.tsx — DAG 渲染引擎替换

**问题**: G6 的 `labelText` 只支持纯文本，无法做分段着色和布局；HTML Overlay 与 G6 Canvas `autoFit` 坐标变换不同步，导致内容飘到节点外。

**方案**: 彻底替换为 `@xyflow/react` + `dagre`，用 React 组件作为节点，原生支持富 HTML/CSS 渲染。

#### 核心变更

| 项目 | 旧 (G6) | 新 (ReactFlow + dagre) |
|------|---------|----------------------|
| 渲染引擎 | `@antv/g6` v5 | `@xyflow/react` v12 + `dagre` |
| 布局算法 | `antv-dagre` (G6 内置) | `dagre` (独立库) |
| 布局方向 | `rankdir: 'TB'` → `'LR'` | `rankdir: 'LR'` |
| 节点渲染 | G6 `rect` + `labelText` | React 组件 `ExecutionStepNode` |
| 节点尺寸 | 180×60 | 300×180 |
| 节点拖动 | `drag-element` 行为 | `nodesDraggable` 属性 |
| 坐标同步 | HTML Overlay 需手动同步 | React 组件自动跟随 |
| 连线样式 | G6 `polyline` | ReactFlow `smoothstep` + `MarkerType.ArrowClosed` |

#### 复合节点设计 (ExecutionStepNode)

```
┌──────────────────────────────────────┐
│ ████████████████████████████████████ │  ← 顶部渐变色条（规则类型色）
│ [约束规则]                    ● 通过  │  ← 类型标签 + 执行状态
│ 基础准入检查                          │  ← 步骤名称（加粗）
│ ▸ status is not null AND reg_cap..   │  ← 条件表达式（等宽字体）
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│ IN  status=ACTIVE, reg_capital=50M   │  ← 输入变量及值（蓝色 IN 标签）
│ OUT is_eligible=true                  │  ← 输出变量及值（绿色 OUT 标签）
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│ ◇ is_eligible, rejection_reason       │  ← 输出要素名称
└──────────────────────────────────────┘
○ (左Handle)                  ○ (右Handle)
```

- **模拟执行前**: 只显示类型、名称、表达式、输出要素
- **模拟执行后**: 额外显示 `IN`（输入变量值）和 `OUT`（输出变量值）
- **浅色系配色**: 沿用 `colorSchemes.ts` 中 `RULE_TYPE_COLORS` 的浅色 fill + 深色 stroke
- **执行状态覆盖**: passed=浅绿、failed=浅红、skipped=浅橙
- **边颜色**: passed=绿色、failed=红色、pending=灰色；passed 的边带动画

#### 新增功能

- **MiniMap**: 右上角缩略图，节点按规则类型着色
- **Controls**: 右下角缩放/平移控件
- **Background**: 点阵背景
- **图例**: 左下角，展示规则类型和执行状态

#### 关键代码结构

```typescript
// 自定义节点组件
const ExecutionStepNode = memo(({ data }) => {
  // data.step: ExecutableStep
  // data.status: 'passed' | 'skipped' | 'failed' | 'pending'
  // data.result?: StepExecutionResult (模拟执行后)
  return <div>...</div>;
});

// dagre 布局计算
const { nodes, edges } = useMemo(() => {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 120 });
  // ... 添加节点和边
  dagre.layout(g);
  // ... 计算位置
}, [tree, executionResults, resultKey]);
```

### 2.2 SimulationPanel.tsx — 自动构建执行树

**问题**: 用户需要手动选择目标输出、实体、点击构建、填写输入、点击运行，步骤繁琐。

**方案**: 新增 `autoBuild` 属性，当 URL 参数提供 `targetOutput` + `entityId` 时，自动完成整个流程。

#### 新增属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `autoBuild` | `boolean` | `false` | 是否自动构建执行树并运行模拟 |
| `initialEntityId` | `string` | `undefined` | 初始实体 ID（来自 URL 参数） |
| `initialTargetOutput` | `string` | `''` | 初始目标输出（来自 URL 参数） |

#### 自动构建流程

```
URL 参数解析 → availableOutputs 加载完成 → entitiesLoading=false
  ↓
autoBuildDoneRef 防重入
  ↓
createSession(entityId, targetOutput)  ← 自动构建执行树
  ↓
自动填充实体属性到输入
  ↓
runSimulation(sessionId, inputs)  ← 自动运行模拟（仅当 entityId 存在时）
  ↓
stepResults → ExecutionDAGCanvas  ← 节点显示 I/O 值
```

#### 关键改动

1. `createSession` 新增 `overrideEntityId` 和 `overrideTargetOutput` 参数
2. `runSimulation` 新增 `overrideSessionId` 和 `overrideInputs` 参数
3. 自动构建时，从实体属性中提取输入值并填充
4. `autoBuildDoneRef` 防止 useEffect 重复执行

### 2.3 SimulationEmbedPage.tsx — URL 参数传递

**改动**: 解析 URL 参数后，计算 `hasUrlParams` 并传递 `autoBuild` 给 `SimulationPanel`。

#### 支持的 URL 参数

| 参数 | 示例 | 说明 |
|------|------|------|
| `schemaId` | `space_supply_chain_finance` | Schema ID |
| `targetOutput` | `final_decision` | 目标输出要素 ID |
| `entityId` | `SUP001` | 实体 ID |

#### 示例 URL

```
/simulation/embed?schemaId=space_supply_chain_finance&targetOutput=final_decision&entityId=SUP001
```

访问此 URL 后，页面将自动：
1. 选中 `final_decision` 作为目标输出
2. 选中 `SUP001` 作为实体
3. 构建执行树
4. 自动运行模拟
5. DAG 画布上显示各节点的输入输出变量值

---

## 三、I/O 变量值显示机制

### 数据流

```
后端 API (PATCH /v1/simulation/{session_id})
  ↓
response.result.steps: StepExecutionResult[]
  ↓
SimulationPanel.setStepResults()
  ↓
ExecutionTreeViewer.executionResults
  ↓
ExecutionDAGCanvas.executionResults
  ↓
useMemo → nodes[].data.result
  ↓
ExecutionStepNode → data.result.input_values_used / data.result.output
  ↓
IN/OUT 标签 + formatKVPairs()
```

### 后端返回的 Step 数据格式

```json
{
  "step_id": "step_1",
  "step_name": "基础准入检查",
  "condition_result": true,
  "condition_detail": {
    "type": "expression",
    "expression": "status == 'ACTIVE' AND ...",
    "result": true,
    "explanation": "Condition '...' evaluated to True"
  },
  "action_taken": "set_flag",
  "output": {"is_eligible": true},
  "input_values_used": {"status": "ACTIVE", "registered_capital": 50000000},
  "duration_ms": 1
}
```

### 前端渲染逻辑

```typescript
// ExecutionStepNode 中的 I/O 渲染
const hasResult = status !== 'pending' && result;
const inputValuesUsed = result?.input_values_used;
const outputValues = result?.output;
const hasInputs = inputValuesUsed && typeof inputValuesUsed === 'object' && Object.keys(inputValuesUsed).length > 0;
const hasOutputs = outputValues && typeof outputValues === 'object' && Object.keys(outputValues).length > 0;
```

---

## 四、依赖变更

| 包 | 操作 | 版本 | 说明 |
|----|------|------|------|
| `dagre` | 新增 | ^0.8.5 | DAG 布局算法（已作为间接依赖，现显式安装） |
| `@xyflow/react` | 已有 | v12 | React Flow 渲染引擎 |
| `@antv/g6` | 保留 | v5 | 其他组件仍使用（RuleChainDAG、SchemaGraph 等） |

---

## 五、验收验证

| 验证项 | URL |
|--------|-----|
| 嵌入式页面（自动构建） | http://localhost:3002/simulation/embed?schemaId=space_supply_chain_finance&targetOutput=final_decision&entityId=SUP001 |
| 嵌入式页面（仅 schema） | http://localhost:3002/simulation/embed?schemaId=space_supply_chain_finance |
| 嵌入式页面（指定目标输出） | http://localhost:3002/simulation/embed?schemaId=space_supply_chain_finance&targetOutput=credit_score |

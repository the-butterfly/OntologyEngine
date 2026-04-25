# 前端 DAG 可视化试错经验

> **日期**: 2026-04-24
> **模块**: 模拟执行树 DAG 画布
> **场景**: 将 G6 纵向 DAG 改为 ReactFlow 横向复合节点 DAG

---

## 1. G6 HTML Overlay 坐标不同步

### 问题描述

使用 `@antv/g6` v5 渲染 DAG 时，为了在节点上显示富文本内容（表达式、I/O 变量值），采用了 HTML Overlay 模式：在 G6 Canvas 外层用绝对定位的 DOM 元素渲染节点内容。

**现象**：节点内容飘到节点外面，位置偏移严重。

### 根因

G6 的 `autoFit: 'view'` 会对 Canvas 施加缩放/平移变换（transform），但 HTML Overlay 的 DOM 定位基于图坐标系（`node.getModel().x/y`），两者不一致：

- Canvas 通过 CSS transform 实现缩放/平移
- DOM overlay 通过 `left/top` 绝对定位
- 当 Canvas 缩放后，overlay 的 `left/top` 不会自动跟随

### 解决方案

彻底放弃 HTML Overlay，改用 ReactFlow（`@xyflow/react`），用 React 组件作为节点。ReactFlow 的节点本身就是 DOM 元素，缩放/平移由 CSS transform 统一管理，不存在坐标不同步问题。

### 经验

> **G6 HTML Overlay 仅适用于不需要 autoFit 的固定尺寸场景**。一旦涉及 fitView/autoFit，DOM overlay 坐标就会与 Canvas 不同步。对于需要富文本节点的 DAG，应优先考虑 ReactFlow。

---

## 2. G6 labelText 纯文本限制

### 问题描述

G6 的 `labelText` 属性只支持纯文本字符串，无法实现：
- 分段着色（如 IN 蓝色、OUT 绿色）
- 不同字号（如标题大字、表达式小字）
- 多行布局控制

### 解决方案

ReactFlow 的自定义节点是 React 组件，可以用任意 HTML/CSS 渲染。

### 经验

> **G6 适合简单标签的只读图**（如 SchemaGraph、RuleChainDAG），**ReactFlow 适合需要富文本节点的交互图**。项目应保持双图库策略，按场景选择。

---

## 3. ReactFlow 节点拖动不生效

### 问题描述

设置了 `nodesDraggable` 属性，但节点拖动后弹回原位。

### 根因

ReactFlow 需要 `onNodesChange` 回调来处理节点位置变更。没有此回调，ReactFlow 内部状态不会更新，拖动后的位置无法持久化。

### 解决方案

```typescript
const onNodesChange = useCallback((changes: NodeChange[]) => {
  setNodes((nds) => applyNodeChanges(changes, nds));
}, []);
```

### 经验

> **ReactFlow 的 `nodesDraggable` 只是启用拖动交互，必须配合 `onNodesChange` + `applyNodeChanges` 才能持久化位置**。这是 ReactFlow 受控模式的基本要求。

---

## 4. ReactFlow useMemo 导致数据不更新

### 问题描述

模拟执行后，DAG 节点上不显示 I/O 变量值。`executionResults` 已传入组件，但节点内容未更新。

### 根因

之前用 `useMemo` 统一计算节点和布局：

```typescript
const { nodes, edges } = useMemo(() => {
  // 计算 dagre 布局
  // 同时设置 node.data.result
}, [tree, executionResults]);
```

当 `executionResults` 变化时，整个节点数组被重新创建（包括位置重置为 dagre 初始值），ReactFlow 内部状态与外部 `nodes` prop 不同步。

### 解决方案

分离两个关注点：

1. **布局计算**（`tree` 变化时）：`computeDagreLayout()` → `setNodes/setEdges`
2. **数据更新**（`executionResults` 变化时）：`setNodes(prev => map data update)` — 只更新 `node.data`，不重置位置

```typescript
// 布局：只在 tree 结构变化时
useEffect(() => {
  if (treeJson === treeJsonRef.current) return;
  const layout = computeDagreLayout(tree);
  setNodes(layout.nodes);
  setEdges(layout.edges);
}, [tree]);

// 数据：executionResults 变化时只更新 data
useEffect(() => {
  setNodes((prev) => prev.map((node) => ({
    ...node,
    data: { ...node.data, status, result },
  })));
}, [executionResults]);
```

### 经验

> **ReactFlow 的节点状态管理必须区分"布局变化"和"数据变化"**。布局变化需要重新计算 dagre，数据变化只需更新 node.data。如果混在一起，会导致位置重置或 UI 不更新。

---

## 5. 后端模拟 500 错误导致前端无结果

### 问题描述

前端模拟执行后，`result` 始终为 `null`，节点上不显示 I/O 值。

### 根因

后端 `_run_simulation()` 抛出 `ValueError`（如 "Entity SUP001 not found"），PATCH 端点没有 try/except，直接返回 500。前端 axios 收到 500 后走 error 回调，`result` 不更新。

### 解决方案

在 PATCH 端点添加 try/except，将异常转为 `simulation_error` 字段：

```python
try:
    result = await _run_simulation(session)
except ValueError as e:
    simulation_error = str(e)
except Exception as e:
    simulation_error = f"Simulation execution failed: {type(e).__name__}: {e}"
```

### 经验

> **后端 API 端点必须有顶层 try/except**，将业务异常转为可读的错误信息返回前端，而非 500。前端也应检查 `simulation_error` 字段并展示给用户。

---

## 6. 实体 ID 不匹配

### 问题描述

URL 参数 `entityId=SUP001` 导致模拟失败。

### 根因

Schema 中的实体 ID 是 `SUP_A`、`CE_HW` 等，而非 `SUP001`。前端 `SimulationPanel` 的 `autoBuild` 流程直接使用 URL 参数，未校验实体是否存在。

### 经验

> **URL 参数中的 entityId 必须与后端实际数据一致**。前端应在 autoBuild 前校验实体是否存在，或从实体列表中自动选择第一个匹配实体。

---

## 总结：DAG 可视化技术选型决策树

```
需要富文本节点？
  ├─ 是 → ReactFlow + dagre
  │       适用于：执行树、模拟结果、交互式编辑
  └─ 否 → G6
          适用于：Schema 全景图、规则链只读展示
```

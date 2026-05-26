# 模拟执行树 DAG 可视化设计文档

> **模块**: ontology-engine-ui 模拟执行树 DAG 画布
> **版本**: v1.0
> **日期**: 2026-04-24
> **状态**: [单一事实源]
> **phase**: Phase 1

---

## 0. 文档状态

| 项目 | 值 |
|------|-----|
| **状态** | ✅ 已实施 |
| **代码基准** | `ontology-engine-ui/src/components/simulation/ExecutionDAGCanvas.tsx` |
| **依赖** | `@xyflow/react` v12 + `dagre` |
| **验收 URL** | `/simulation/embed?schemaId=space_supply_chain_finance&targetOutput=final_decision&entityId=SUP_A` |

---

## 1. 技术选型

### 1.1 渲染引擎：ReactFlow + dagre

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| `@antv/g6` v5 | 项目已有依赖 | labelText 纯文本无法富渲染；HTML Overlay 与 autoFit 坐标不同步 | ❌ 不采用 |
| `@xyflow/react` v12 | React 组件即节点，原生富 HTML/CSS；项目已有依赖 | 需手动集成 dagre 布局 | ✅ 采用 |

**关键设计点**：G6 的 HTML Overlay 模式在 `autoFit: 'view'` 下，DOM 定位与 Canvas 坐标变换不同步，导致内容飘到节点外。ReactFlow 的 React 组件节点无此问题。

### 1.2 布局算法：dagre

- 方向：`rankdir: 'LR'`（从左到右横向布局）
- 节点间距：`nodesep: 40`
- 层间距：`ranksep: 120`

---

## 2. 复合节点设计（ExecutionStepNode）

### 2.1 节点结构

```
┌──────────────────────────────────────┐
│ ████████████████████████████████████ │  ← 顶部渐变色条（规则类型色）
│ [约束规则]                    ● 通过  │  ← 类型标签 + 执行状态
│ 基础准入检查                          │  ← 步骤名称（加粗）
│ ▸ status is not null AND reg_cap..   │  ← 条件表达式（等宽字体）
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│ IN  status="ACTIVE", reg_cap="50M"   │  ← 输入变量及值（蓝色 IN 标签）
│ OUT is_eligible="true"                │  ← 输出变量及值（绿色 OUT 标签）
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│ ◇ is_eligible, rejection_reason       │  ← 输出要素名称（浅灰色）
└──────────────────────────────────────┘
○ (左Handle)                  ○ (右Handle)
```

### 2.2 节点尺寸

- 宽度：300px
- 高度：自适应（约 180px）

### 2.3 I/O 变量值显示

| 区域 | 条件 | 数据来源 | 格式 |
|------|------|----------|------|
| IN | `status !== 'pending' && result.input_values_used` 非空 | `StepExecutionResult.input_values_used` | `k="v"` 等宽字体 |
| OUT | `status !== 'pending' && result.output` 非空 | `StepExecutionResult.output` | `k="v"` 等宽字体 |
| Error | `result.error` 存在 | `StepExecutionResult.error` | 红色文本 |

### 2.4 浅色系配色

沿用 `colorSchemes.ts` 中 `RULE_TYPE_COLORS` 的浅色 fill + 深色 stroke：

| 规则类型 | fill | stroke |
|----------|------|--------|
| constraint（约束） | `#FFF1F0` | `#FF4D4F` |
| inference（推理） | `#E6F7FF` | `#1890FF` |
| alert（预警） | `#FFF7E6` | `#FA8C16` |
| decision（决策） | `#F6FFED` | `#52C41A` |

执行状态覆盖：

| 状态 | fill | stroke |
|------|------|--------|
| passed | `#F6FFED` | `#52C41A` |
| failed | `#FFF1F0` | `#F5222D` |
| skipped | `#FFF7E6` | `#FA8C16` |
| pending | 规则类型默认色 | 规则类型默认色 |

---

## 3. 状态管理

### 3.1 布局与数据分离

```
tree 变化 → computeDagreLayout() → setNodes/setEdges（重置位置）
executionResults 变化 → setNodes(prev => map data update)（保留位置）
```

**关键设计点**：布局计算和数据更新必须分离。如果 `executionResults` 变化时重新计算 dagre 布局，节点位置会被重置，用户拖动后的位置丢失。

### 3.2 节点拖动

ReactFlow 需要 `onNodesChange` + `applyNodeChanges` 来持久化节点位置变更。没有此回调，拖动后节点会弹回原位。

```typescript
const onNodesChange = useCallback((changes: NodeChange[]) => {
  setNodes((nds) => applyNodeChanges(changes, nds));
}, []);
```

### 3.3 tree 结构变化检测

使用 `treeJsonRef` 对比 tree 的 step_id + depends_on 序列化结果，避免 tree 对象引用变化但结构未变时重复计算布局。

---

## 4. URL 参数自动构建

### 4.1 支持的 URL 参数

| 参数 | 示例 | 说明 |
|------|------|------|
| `schemaId` | `space_supply_chain_finance` | Schema ID |
| `targetOutput` | `final_decision` | 目标输出要素 ID |
| `entityId` | `SUP_A` | 实体 ID |

### 4.2 自动构建流程

```
URL 参数 → SimulationEmbedPage 解析 → SimulationPanel(autoBuild=true)
  ↓
availableOutputs 加载完成 + entitiesLoading=false
  ↓
autoBuildDoneRef 防重入
  ↓
createSession(entityId, targetOutput) → 构建执行树 + 填充实体属性
  ↓
runSimulation(sessionId, inputs) → 运行模拟（仅当 entityId 存在时）
  ↓
stepResults → ExecutionDAGCanvas → 节点显示 I/O 值
```

---

## 5. 后端 API 错误处理

### 5.1 PATCH /v1/simulation/{session_id}

`_run_simulation()` 可能抛出 `ValueError`（Entity not found）或其他异常。PATCH 端点必须用 try/except 包裹，将异常转为 `simulation_error` 字段返回，而非 500 错误。

### 5.2 返回数据格式

```json
{
  "session_id": "...",
  "updated_inputs": {...},
  "result": {
    "steps": [
      {
        "step_id": "RD001_basic_eligibility",
        "step_name": "基础准入检查",
        "condition_result": true,
        "action_taken": "set_flag",
        "input_values_used": {"status": "ACTIVE", "registered_capital": 50000000},
        "output": {"is_eligible": true},
        "duration_ms": 1
      }
    ],
    "final_output": {...},
    "alerts": [],
    "errors": []
  },
  "missing_inputs": [],
  "simulation_error": null
}
```

---

## 6. 依赖变更

| 包 | 版本 | 说明 |
|----|------|------|
| `@xyflow/react` | v12 | 已有依赖，ReactFlow 渲染引擎 |
| `dagre` | ^0.8.5 | 新增显式依赖，DAG 布局算法 |
| `@antv/g6` | v5 | 保留，其他组件（RuleChainDAG、SchemaGraph）仍使用 |

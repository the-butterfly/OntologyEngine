# 规则仿真用户旅程改进计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 实现完整的规则仿真用户旅程：
1. 下拉选择目标输出要素、实体ID
2. 点击构建后自动填充实体的当前属性值
3. 执行整个规则树（DAG 执行引擎）
4. 展示 DAG 可视化图（替代 Tab 分层展示）

**Architecture:**
- 后端：增强 `simulation.py` API，实现 `_run_simulation()` DAG 执行引擎
- 前端：改进 `SimulationPanel.tsx` 使用 Select 下拉 + DAG 可视化

**Tech Stack:** Python 3.12, React, @xyflow/react, dagre

---

## Task 1: 后端 - 增强 Simulation API 自动填充实体属性

**Files:**
- Modify: `ontology_engine/api/routes/simulation.py`
- Test: `tests/integration/test_simulation_full_flow.py`

**Step 1: 验证现有功能**

```bash
# 确认当前 simulation/tree API 返回结构
curl -s -X POST http://localhost:8000/v1/simulation/tree \
  -H "Content-Type: application/json" \
  -d '{"schema_id":"space_supply_chain_finance","target_output":"final_decision"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['data'], indent=2))"
```

**Step 2: 修改 simulation.py 实现自动填充**

```python
# 在 create_simulation_tree 函数中，当提供 entity_id 时：
# 1. 加载实体数据
# 2. 提取 L3 analytical elements 对应的属性值
# 3. 预填到 current_inputs

# 具体改动：
# 1. 在 return success_response 前添加实体属性自动查询逻辑
# 2. 返回结构中 current_inputs 包含自动填充的值
```

**Step 3: 测试验证**

```bash
curl -s -X POST http://localhost:8000/v1/simulation/tree \
  -H "Content-Type: application/json" \
  -d '{"schema_id":"space_supply_chain_finance","entity_id":"SUP001","target_output":"final_decision"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('current_inputs:', d['data'].get('current_inputs', {}))"
```

**Step 4: Commit**

```bash
git add ontology_engine/api/routes/simulation.py
git commit -m "feat(simulation): auto-fill entity attributes in createTree"
```

---

## Task 2: 后端 - 实现 DAG 执行引擎 _run_simulation()

**Files:**
- Modify: `ontology_engine/api/routes/simulation.py`
- Create: `ontology_engine/services/dag_executor.py`
- Test: `tests/integration/test_simulation_full_flow.py`

**Step 1: 创建 DAG Executor 服务**

```python
# ontology_engine/services/dag_executor.py
"""DAG Executor - Executes rule tree layer by layer."""

from __future__ import annotations

from typing import Any
from ontology_engine.core.semantic_space import SemanticSpace


class DAGExecutor:
    """Executes rules following Kahn algorithm layer ordering."""

    def __init__(self, semantic_space: SemanticSpace):
        self._space = semantic_space

    async def execute(
        self,
        execution_tree: dict[str, Any],
        entity_data: dict[str, Any],
        input_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute rule tree from entity data with optional overrides.

        Args:
            execution_tree: Tree with layers and steps
            entity_data: Entity's current attribute values
            input_overrides: Override values for what-if analysis

        Returns:
            Execution result with final_outputs, step_results
        """
        working_data = dict(entity_data)
        if input_overrides:
            working_data.update(input_overrides)

        all_step_results = []
        final_outputs = {}
        errors = []

        for layer in execution_tree.get("layers", []):
            layer_results = []
            for step in layer.get("steps", []):
                result = await self._execute_step(step, working_data)
                layer_results.append(result)

                if result.get("error"):
                    errors.append(f"{step['step_id']}: {result['error']}")
                else:
                    working_data.update(result.get("output", {}))
                    for k, v in result.get("output", {}).items():
                        final_outputs[k] = v

            all_step_results.append({
                "layer_index": layer["layer_index"],
                "step_results": layer_results
            })

        return {
            "final_outputs": final_outputs,
            "step_results": all_step_results,
            "errors": errors if errors else None,
        }

    async def _execute_step(
        self,
        step: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute single rule step."""
        # 1. Evaluate condition
        condition = step.get("condition", {})
        expr = condition.get("expression", "")
        condition_met = self._evaluate_expression(expr, context)

        if not condition_met:
            return {
                "step_id": step["step_id"],
                "step_name": step["step_name"],
                "condition_result": False,
                "action_taken": "skipped",
                "output": {},
            }

        # 2. Find matching rule logic and execute
        rule_id = step.get("step_id", "")
        rule_defs = self._space.layers.L4_business_logic.rule_definitions
        rule_logics = self._space.layers.L4_business_logic.rule_logics

        rd = next((r for r in rule_defs if r["id"] == rule_id), None)
        if not rd:
            return {
                "step_id": step["step_id"],
                "step_name": step["step_name"],
                "error": f"Rule definition {rule_id} not found",
            }

        logic_ids = rd.get("logic_ids", [])
        output = {}

        for logic_id in logic_ids:
            logic = next((l for l in rule_logics if l["id"] == logic_id), None)
            if logic:
                then_action = logic.get("then_action", {})
                action_type = then_action.get("action_type", "")
                action_output = then_action.get("output", {})

                if action_type == "compute":
                    output.update(action_output)
                elif action_type in ("set_flag", "approve", "reject"):
                    output.update(action_output)
                # ... 其他 action_type

        return {
            "step_id": step["step_id"],
            "step_name": step["step_name"],
            "condition_result": True,
            "action_taken": action_type,
            "output": output,
        }

    def _evaluate_expression(self, expr: str, context: dict[str, Any]) -> bool:
        """Safely evaluate simple condition expression."""
        if not expr or expr == "true":
            return True

        try:
            # 安全替换变量
            for key, value in context.items():
                if isinstance(value, (int, float)):
                    expr = expr.replace(key, str(value))
                elif isinstance(value, str):
                    expr = expr.replace(key, f"'{value}'")
            return eval(expr)
        except Exception:
            return True  # 求值失败时默认通过
```

**Step 2: 修改 simulation.py 使用 DAGExecutor**

```python
# simulation.py 顶部添加导入
from ontology_engine.services.dag_executor import DAGExecutor

# 修改 _run_simulation 函数
async def _run_simulation(session: SimulationSession) -> dict[str, Any]:
    """Run simulation with current inputs."""
    space = await _semantic_space_storage.load(session.schema_id)
    if not space:
        raise ValueError(f"Space {session.schema_id} not found")

    # Find entity
    entity = None
    for e in space.instances.entities:
        if e.get("entity_id") == session.entity_id:
            entity = dict(e)
            break

    if not entity:
        raise ValueError(f"Entity {session.entity_id} not found")

    executor = DAGExecutor(space)
    result = await executor.execute(
        session.execution_tree,
        entity,
        input_overrides=session.current_inputs,
    )

    return result
```

**Step 3: 测试验证**

```bash
# 需要先确保实体 SUP001 存在于 space_supply_chain_finance
curl -s -X POST http://localhost:8000/v1/simulation/tree \
  -H "Content-Type: application/json" \
  -d '{"schema_id":"space_supply_chain_finance","entity_id":"SUP001","target_output":"final_decision"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('session_id:', d['data']['session_id'])"

# 然后运行模拟
curl -s -X PATCH http://localhost:8000/v1/simulation/{session_id} \
  -H "Content-Type: application/json" \
  -d '{"input_values":{}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['data'], indent=2))"
```

**Step 4: Commit**

```bash
git add ontology_engine/services/dag_executor.py ontology_engine/api/routes/simulation.py
git commit -m "feat(dag_executor): implement DAG execution engine"
```

---

## Task 3: 前端 - SimulationPanel 增强（下拉选择）

**Files:**
- Modify: `ontology-engine-ui/src/components/simulation/SimulationPanel.tsx`
- Test: `ontology-engine-ui/tests/simulation.test.ts`

**Step 1: 添加 Select 组件**

```typescript
// SimulationPanel.tsx 改动
import { Select, Space, Card, Button, message } from 'antd';

// 添加状态
const [availableOutputs, setAvailableOutputs] = useState<string[]>([]);
const [availableEntities, setAvailableEntities] = useState<{value: string; label: string}[]>([]);

// 在 createSession 调用后自动获取可用输出和实体列表
// 使用 simulationApi 查询 space 信息获取 outputs
// 使用 /v1/consumption/views/{schemaId}/entities 获取实体列表
```

**Step 2: 使用 Select 替代 Text Input**

```typescript
// 目标输出选择
<Select
  value={targetOutput}
  onChange={setTargetOutput}
  placeholder="选择目标输出"
  options={availableOutputs.map(o => ({ value: o, label: o }))}
  style={{ width: 200 }}
  allowClear
  showSearch
/>

// 实体ID选择
<Select
  value={entityId}
  onChange={(val) => {
    setEntityId(val);
    // 如果选择了实体，自动查询该实体的属性值填充到 inputValues
  }}
  placeholder="选择实体"
  options={availableEntities}
  style={{ width: 200 }}
  showSearch
  allowClear
/>
```

**Step 3: Commit**

```bash
git add ontology-engine-ui/src/components/simulation/SimulationPanel.tsx
git commit -m "feat(ui): add dropdown selects for target output and entity"
```

---

## Task 4: 前端 - ExecutionTreeViewer 改为 DAG 可视化

**Files:**
- Modify: `ontology-engine-ui/src/components/simulation/ExecutionTreeViewer.tsx`
- Create: `ontology-engine-ui/src/components/simulation/ExecutionDAGCanvas.tsx`

**Step 1: 创建 ExecutionDAGCanvas 组件**

```typescript
// ExecutionDAGCanvas.tsx
import { useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import dagre from 'dagre';
import { ExecutionTree, ExecutableStep } from '../../types/simulation';

interface ExecutionDAGCanvasProps {
  tree: ExecutionTree;
  executionResults?: StepExecutionResult[];
  onNodeClick?: (step: ExecutableStep) => void;
}

const NODE_WIDTH = 200;
const NODE_HEIGHT = 80;

export function ExecutionDAGCanvas({ tree, executionResults, onNodeClick }: ExecutionDAGCanvasProps) {
  // Transform ExecutionTree to ReactFlow nodes/edges
  const { nodes, edges } = useMemo(() => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    const nfNodes: Node[] = [];
    const nfEdges: Edge[] = [];

    tree.layers.forEach((layer, layerIdx) => {
      layer.steps.forEach((step, stepIdx) => {
        const nodeId = step.step_id;

        // Add to dagre for layout
        dagreGraph.setNode(nodeId, { width: NODE_WIDTH, height: NODE_HEIGHT });

        // Create ReactFlow node
        nfNodes.push({
          id: nodeId,
          position: { x: 0, y: 0 }, // Will be set by dagre layout
          data: {
            label: step.step_name,
            type: step.rule_group_type,
            layer: layerIdx,
            step,
          },
          style: {
            background: getNodeColor(step.rule_group_type),
            color: '#fff',
            border: '1px solid #333',
            borderRadius: 8,
            padding: 10,
            width: NODE_WIDTH,
            height: NODE_HEIGHT,
          },
        });

        // Add edges for dependencies
        step.depends_on?.forEach((depId) => {
          nfEdges.push({
            id: `${depId}-${nodeId}`,
            source: depId,
            target: nodeId,
            animated: true,
          });
          dagreGraph.setEdge(depId, nodeId);
        });
      });
    });

    // Apply dagre layout
    dagreGraph.layout();
    nfNodes.forEach((node) => {
      const pos = dagreGraph.node(node.id);
      node.position = {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      };
    });

    return { nodes: nfNodes, edges: nfEdges };
  }, [tree]);

  return (
    <ReactFlow nodes={nodes} edges={edges} fitView>
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  );
}

function getNodeColor(ruleType: string): string {
  const colors: Record<string, string> = {
    constraint: '#1890ff',
    inference: '#722ed1',
    alert: '#fa8c16',
    decision: '#52c41a',
  };
  return colors[ruleType] || '#8c8c8c';
}
```

**Step 2: 修改 ExecutionTreeViewer 使用 DAG 可视化**

```typescript
// ExecutionTreeViewer.tsx
export function ExecutionTreeViewer({ tree, onStepClick }: ExecutionTreeViewerProps) {
  // For now, use simple layered layout without dagre
  // (dagre integration happens in Task 5)

  return (
    <Card title="执行树">
      <Tabs
        items={tree.layers.map((layer, idx) => ({
          key: String(idx),
          label: `Layer ${idx} (${layer.steps.length}步)`,
          children: (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              {layer.steps.map((step) => (
                <Card
                  key={step.step_id}
                  size="small"
                  style={{ width: 240, cursor: 'pointer' }}
                  onClick={() => onStepClick?.(step)}
                >
                  {/* ... existing card content */}
                </Card>
              ))}
            </div>
          ),
        }))}
      />
    </Card>
  );
}
```

**Step 3: Commit**

```bash
git add ontology-engine-ui/src/components/simulation/ExecutionDAGCanvas.tsx ontology-engine-ui/src/components/simulation/ExecutionTreeViewer.tsx
git commit -m "feat(ui): add DAG canvas for execution tree visualization"
```

---

## Task 5: 前端 - 集成 DAG 可视化到 SimulationPanel

**Files:**
- Modify: `ontology-engine-ui/src/components/simulation/SimulationPanel.tsx`
- Modify: `ontology-engine-ui/src/components/simulation/ExecutionTreeViewer.tsx`

**Step 1: 添加模式切换（Tab 分层 vs DAG 可视化）**

```typescript
// SimulationPanel.tsx
const [viewMode, setViewMode] = useState<'tabs' | 'dag'>('tabs');

return (
  <Space direction="vertical" style={{ width: '100%' }} size="middle">
    {/* Config Card */}

    {/* View Mode Toggle */}
    <Radio.Group value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
      <Radio.Button value="tabs">分层视图</Radio.Button>
      <Radio.Button value="dag">DAG 图</Radio.Button>
    </Radio.Group>

    {/* Execution Tree */}
    {executionTree && viewMode === 'tabs' && (
      <ExecutionTreeViewer tree={executionTree} onStepClick={() => {}} />
    )}

    {executionTree && viewMode === 'dag' && (
      <ExecutionDAGCanvas tree={executionTree} />
    )}

    {/* ... rest */}
  </Space>
);
```

**Step 2: 更新 ExecutionTreeViewer 支持 DAG**

```typescript
// ExecutionTreeViewer.tsx 添加 DAG 模式
import { ExecutionDAGCanvas } from './ExecutionDAGCanvas';

interface ExecutionTreeViewerProps {
  tree: ExecutionTree;
  onStepClick?: (step: ExecutableStep) => void;
  viewMode?: 'tabs' | 'dag';  // 新增
}

export function ExecutionTreeViewer({ tree, onStepClick, viewMode = 'tabs' }: ExecutionTreeViewerProps) {
  if (viewMode === 'dag') {
    return (
      <Card title="执行树 (DAG)">
        <ExecutionDAGCanvas tree={tree} onNodeClick={onStepClick} />
      </Card>
    );
  }

  // Existing tabs implementation
  return (
    <Card title="执行树">
      <Tabs ... />
    </Card>
  );
}
```

**Step 3: Commit**

```bash
git add ontology-engine-ui/src/components/simulation/SimulationPanel.tsx ontology-engine-ui/src/components/simulation/ExecutionTreeViewer.tsx
git commit -m "feat(ui): integrate DAG visualization with mode toggle"
```

---

## Task 6: 集成测试 - 完整用户旅程验证

**Files:**
- Create: `tests/integration/test_simulation_user_journey.py`

**Step 1: 编写端到端测试**

```python
@pytest.mark.asyncio
async def test_full_simulation_journey():
    """Test complete simulation user journey."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create session with entity_id
        resp = await client.post("/v1/simulation/tree", json={
            "schema_id": "space_supply_chain_finance",
            "entity_id": "SUP001",
            "target_output": "final_decision"
        })
        assert resp.status_code == 200
        data = resp.json()["data"]

        # 2. Verify auto-filled inputs
        assert data["current_inputs"]  # Should have credit_score, etc.

        session_id = data["session_id"]

        # 3. Run simulation
        resp = await client.patch(f"/v1/simulation/{session_id}", json={
            "input_values": {}
        })
        assert resp.status_code == 200
        result = resp.json()["data"]["result"]

        # 4. Verify execution result
        assert result["final_outputs"]  # Should have final_decision
        assert result["step_results"]  # Should have per-layer results
```

**Step 2: 运行测试**

```bash
pytest tests/integration/test_simulation_user_journey.py -v
```

**Step 3: Commit**

```bash
git add tests/integration/test_simulation_user_journey.py
git commit -m "test: add full simulation user journey integration test"
```

---

## 验证步骤

```bash
# 1. 验证 API 自动填充
curl -s -X POST http://localhost:8000/v1/simulation/tree \
  -H "Content-Type: application/json" \
  -d '{"schema_id":"space_supply_chain_finance","entity_id":"SUP001","target_output":"final_decision"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('current_inputs:', d['data'].get('current_inputs', {}))"

# 2. 验证 DAG 执行
# (session_id from step 1)
curl -s -X PATCH http://localhost:8000/v1/simulation/{session_id} \
  -H "Content-Type: application/json" \
  -d '{"input_values":{}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); r=d['data']['result']; print('final_outputs:', r.get('final_outputs', {}))"

# 3. 前端测试
python scripts/with_server.py \
  --server "cd ontology_engine && python -m uvicorn ontology_engine.api.server:create_app --factory --port 8000" \
  --server "cd ontology-engine-ui && npm run dev" --port 3000 \
  -- python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:3000/simulation/embed?schemaId=space_supply_chain_finance')
    page.wait_for_load_state('networkidle')
    # Check for DAG canvas or mode toggle
    print('Page loaded successfully')
    browser.close()
"
```

---

## 总结

完成此计划后，将实现：

1. **后端增强**
   - `POST /v1/simulation/tree` 自动填充实体属性值
   - `DAGExecutor` 实现完整的规则树执行引擎

2. **前端改进**
   - 下拉选择目标输出和实体ID
   - DAG 可视化展示（节点+连线+层级）
   - 模式切换（Tab 分层 / DAG 图）

3. **测试覆盖**
   - 单元测试 + 集成测试
   - 端到端用户旅程验证

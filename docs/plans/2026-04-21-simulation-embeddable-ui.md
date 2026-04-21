# Simulation Embeddable UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an embeddable simulation sub-interface for rule tree execution, supporting multi-round what-if analysis with backend session management.

**Architecture:**
- Backend: New `/simulation/*` API routes with in-memory SessionManager for session state
- Frontend: Embeddable React component at `/simulation/embed` route with URL params support
- AGUI postMessage interface预留 for future Agent integration

**Tech Stack:** FastAPI, React, Zustand, Ant Design, G6

---

## Phase 1: Backend Simulation Session API

### Task 1: Simulation Session Data Models

**Files:**
- Create: `ontology_engine/services/simulation_session.py`

**Step 1: Write the failing test**

```python
# tests/unit/services/test_simulation_session.py
import pytest
from ontology_engine.services.simulation_session import SimulationSession, SessionManager

def test_session_creation():
    session = SimulationSession(
        session_id="test-123",
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    assert session.session_id == "test-123"
    assert session.current_inputs == {}

def test_session_manager_create():
    manager = SessionManager()
    session = manager.create_session(
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
        execution_tree={"layers": []},
    )
    assert session.session_id is not None
    assert len(manager._sessions) == 1

def test_session_manager_get():
    manager = SessionManager()
    created = manager.create_session(...)
    retrieved = manager.get_session(created.session_id)
    assert retrieved is not None
    assert retrieved.session_id == created.session_id

def test_session_manager_update_inputs():
    manager = SessionManager()
    session = manager.create_session(...)
    manager.update_inputs(session.session_id, {"credit_score": 80})
    assert session.current_inputs["credit_score"] == 80

def test_session_manager_delete():
    manager = SessionManager()
    session = manager.create_session(...)
    manager.delete_session(session.session_id)
    assert manager.get_session(session.session_id) is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/services/test_simulation_session.py -v`
Expected: FAIL with "No module named 'ontology_engine.services.simulation_session'"

**Step 3: Write minimal implementation**

```python
# ontology_engine/services/simulation_session.py
"""Simulation Session Management for multi-round what-if analysis."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

@dataclass
class SimulationSession:
    """Simulation session state."""
    session_id: str
    schema_id: str
    entity_id: str
    target_output: str
    execution_tree: dict[str, Any]
    current_inputs: dict[str, Any] = field(default_factory=dict)
    current_result: dict[str, Any] | None = None
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

class SessionManager:
    """In-memory session manager with TTL support."""

    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: dict[str, SimulationSession] = {}
        self._ttl = ttl_seconds

    def create_session(
        self,
        schema_id: str,
        entity_id: str,
        target_output: str,
        execution_tree: dict[str, Any],
    ) -> SimulationSession:
        session_id = str(uuid.uuid4())
        session = SimulationSession(
            session_id=session_id,
            schema_id=schema_id,
            entity_id=entity_id,
            target_output=target_output,
            execution_tree=execution_tree,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SimulationSession | None:
        return self._sessions.get(session_id)

    def update_inputs(
        self,
        session_id: str,
        inputs: dict[str, Any],
        partial: bool = True,
    ) -> SimulationSession:
        session = self._sessions[session_id]
        if partial:
            session.current_inputs.update(inputs)
        else:
            session.current_inputs = inputs
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/services/test_simulation_session.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/services/simulation_session.py tests/unit/services/test_simulation_session.py
git commit -m "feat(simulation): add SimulationSession and SessionManager"
```

---

### Task 2: Simulation Tree Builder

**Files:**
- Create: `ontology_engine/services/simulation_tree_builder.py`
- Modify: `ontology_engine/services/simulation_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/services/test_simulation_tree_builder.py
import pytest
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder

@pytest.fixture
def tree_builder():
    return RuleTreeBuilder()

def test_locate_rule_groups_by_output(tree_builder):
    # Mock rule service
    result = await tree_builder._locate_by_output("decision", "schema_001")
    assert isinstance(result, list)

def test_build_execution_tree(tree_builder):
    result = await tree_builder.build_tree(
        schema_id="schema_001",
        entity_id="entity_001",
        target_output="decision",
    )
    assert "layers" in result
    assert len(result["layers"]) > 0
```

**Step 2: Run test to verify it fails**

Expected: FAIL

**Step 3: Write implementation**

```python
# ontology_engine/services/simulation_tree_builder.py
"""Rule Tree Builder for cross-rule-group execution."""
from __future__ import annotations
from typing import Any

class RuleTreeBuilder:
    """Builds execution tree from target output, tracing dependencies."""

    def __init__(self, rule_service=None):
        self._rule_service = rule_service

    async def build_tree(
        self,
        schema_id: str,
        entity_id: str | None,
        target_output: str,
    ) -> dict[str, Any]:
        # 1. Locate target rule groups by output
        target_groups = await self._locate_by_output(target_output, schema_id)

        # 2. Trace dependencies recursively
        layers = []
        current_outputs = {target_output}
        visited_groups = set()

        while current_outputs:
            # Find groups producing current outputs
            next_groups = []
            for output_name in current_outputs:
                groups = await self._locate_by_output(output_name, schema_id)
                for group in groups:
                    if group.name not in visited_groups:
                        visited_groups.add(group.name)
                        next_groups.append(group)

            if not next_groups:
                break

            # 3. Filter steps by entity category
            steps = await self._filter_steps(next_groups, entity_id)

            # 4. Build layer
            layers.append({
                "layer_index": len(layers),
                "rule_groups": [g.name for g in next_groups],
                "steps": steps,
                "output_names": list(current_outputs),
            })

            # 5. Collect new input dependencies
            current_outputs = set()
            for step in steps:
                for inp in step.get("inputs", []):
                    if inp.get("type") == "attribute":
                        current_outputs.add(inp["name"])

        return {
            "schema_id": schema_id,
            "target_output": target_output,
            "layers": layers,
            "total_steps": sum(len(l["steps"]) for l in layers),
            "rule_group_count": len(visited_groups),
        }

    async def _locate_by_output(self, output_name: str, schema_id: str):
        # Use existing ruleGroupsApi.locateRuleGroups
        from ontology_engine.services.rule_service import RuleService
        service = RuleService()
        result = await service.locate_rule_groups(output_name, schema_id)
        return result

    async def _filter_steps(self, groups, entity_id):
        # Filter steps by entity category
        return []
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 3: Simulation API Routes

**Files:**
- Modify: `ontology_engine/api/routes/simulation.py` (NEW)
- Modify: `ontology_engine/api/server.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_simulation_api.py
import pytest

def test_create_simulation_session(client):
    response = client.post("/v1/simulation/tree", json={
        "schema_id": "schema_001",
        "target_output": "decision",
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "execution_tree" in data

def test_get_simulation_session(client):
    # Create first
    create_resp = client.post("/v1/simulation/tree", json={...})
    session_id = create_resp.json()["session_id"]

    # Get
    response = client.get(f"/v1/simulation/{session_id}")
    assert response.status_code == 200

def test_update_simulation_inputs(client):
    create_resp = client.post("/v1/simulation/tree", json={...})
    session_id = create_resp.json()["session_id"]

    response = client.patch(f"/v1/simulation/{session_id}", json={
        "input_values": {"credit_score": 80},
    })
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

**Step 3: Write implementation**

```python
# ontology_engine/api/routes/simulation.py
"""Simulation API endpoints for cross-rule-group execution."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ontology_engine.services.simulation_session import SessionManager
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder
from ontology_engine.api.dto.responses import success_response, error_response

router = APIRouter(prefix="/v1/simulation", tags=["Simulation"])

# Global session manager
_session_manager = SessionManager()
_tree_builder = RuleTreeBuilder()


class CreateSimulationRequest(BaseModel):
    schema_id: str
    entity_id: str | None = None
    target_output: str
    input_values: dict[str, Any] | None = None


class UpdateSimulationRequest(BaseModel):
    input_values: dict[str, Any]
    full_override: bool = False


@router.post("/tree")
async def create_simulation_tree(body: CreateSimulationRequest):
    """Create a new simulation session and build execution tree."""
    try:
        # Build execution tree
        tree = await _tree_builder.build_tree(
            schema_id=body.schema_id,
            entity_id=body.entity_id,
            target_output=body.target_output,
        )

        # Create session
        session = _session_manager.create_session(
            schema_id=body.schema_id,
            entity_id=body.entity_id or "",
            target_output=body.target_output,
            execution_tree=tree,
        )

        # Pre-fill inputs if provided
        if body.input_values:
            _session_manager.update_inputs(
                session.session_id,
                body.input_values,
                partial=False,
            )

        return success_response(data={
            "session_id": session.session_id,
            "execution_tree": tree,
            "required_inputs": _extract_required_inputs(tree),
            "current_inputs": session.current_inputs,
        })
    except Exception as e:
        return error_response(code="INTERNAL_ERROR", message=str(e))


@router.get("/{session_id}")
async def get_simulation_session(session_id: str):
    """Get current simulation session state."""
    session = _session_manager.get_session(session_id)
    if not session:
        return error_response(code="NOT_FOUND", message=f"Session {session_id} not found")

    return success_response(data={
        "session_id": session.session_id,
        "execution_tree": session.execution_tree,
        "current_inputs": session.current_inputs,
        "current_result": session.current_result,
    })


@router.patch("/{session_id}")
async def update_simulation_inputs(session_id: str, body: UpdateSimulationRequest):
    """Update simulation inputs (partial or full override)."""
    session = _session_manager.get_session(session_id)
    if not session:
        return error_response(code="NOT_FOUND", message=f"Session {session_id} not found")

    _session_manager.update_inputs(
        session_id,
        body.input_values,
        partial=not body.full_override,
    )

    # Run simulation if all inputs are filled
    missing = _get_missing_inputs(session)
    result = None
    if not missing:
        result = await _run_simulation(session)

    return success_response(data={
        "session_id": session_id,
        "updated_inputs": session.current_inputs,
        "result": result,
        "missing_inputs": missing,
    })


@router.delete("/{session_id}")
async def delete_simulation_session(session_id: str):
    """Delete a simulation session."""
    deleted = _session_manager.delete_session(session_id)
    if not deleted:
        return error_response(code="NOT_FOUND", message=f"Session {session_id} not found")
    return success_response(data={"deleted": True})


def _extract_required_inputs(tree: dict) -> list:
    """Extract required input elements from execution tree."""
    inputs = []
    for layer in tree.get("layers", []):
        for step in layer.get("steps", []):
            for inp in step.get("inputs", []):
                if inp.get("type") == "attribute" and inp.get("name") not in inputs:
                    inputs.append(inp["name"])
    return inputs


def _get_missing_inputs(session) -> list:
    """Get list of missing required inputs."""
    required = _extract_required_inputs(session.execution_tree)
    return [inp for inp in required if inp not in session.current_inputs]


async def _run_simulation(session):
    """Run simulation with current inputs."""
    # TODO: Integrate with DAGExecutor
    return {"final_output": {}, "steps": [], "errors": []}
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

## Phase 2: Frontend Simulation Embeddable UI

### Task 4: Frontend Simulation Types

**Files:**
- Modify: `ontology_engine-ui/src/types/simulation.ts` (NEW)

**Step 1: Create types**

```typescript
// ontology-engine-ui/src/types/simulation.ts
export interface SimulationSession {
  session_id: string;
  schema_id: string;
  entity_id: string;
  target_output: string;
  created_at: string;
}

export interface ExecutionTree {
  schema_id: string;
  target_output: string;
  layers: ExecutionLayer[];
  total_steps: number;
  rule_group_count: number;
}

export interface ExecutionLayer {
  layer_index: number;
  rule_groups: string[];
  steps: ExecutableStep[];
  output_names: string[];
  input_requirements: InputRequirement[];
}

export interface ExecutableStep {
  step_id: string;
  step_name: string;
  rule_group_name: string;
  rule_group_type: 'constraint' | 'inference' | 'alert' | 'decision';
  condition: {
    type: 'expression' | 'all_of' | 'any_of';
    expression?: string;
    sub_conditions?: string[];
  };
  action: {
    operator: string;
    params: Record<string, unknown>;
  };
  output_names: string[];
  depends_on: string[];
}

export interface InputRequirement {
  name: string;
  type: 'attribute' | 'metric' | 'flag';
  required: boolean;
  default_value?: unknown;
  description?: string;
}

export interface SimulationResult {
  session_id: string;
  final_output: Record<string, unknown>;
  steps: StepExecutionResult[];
  alerts: Alert[];
  errors: string[];
  execution_time_ms: number;
}

export interface StepExecutionResult {
  step_id: string;
  step_name: string;
  layer_index: number;
  condition_result: boolean;
  condition_detail?: {
    type: string;
    expression?: string;
    result: boolean;
    explanation: string;
  };
  action_taken: string;
  output: Record<string, unknown>;
  input_values_used: Record<string, unknown>;
  error?: string;
  duration_ms: number;
}

export interface Alert {
  level: 'info' | 'warning' | 'high' | 'critical';
  type: string;
  message: string;
  source_step?: string;
}

// API Request/Response types
export interface CreateSimulationRequest {
  schema_id: string;
  entity_id?: string;
  target_output: string;
  input_values?: Record<string, unknown>;
}

export interface UpdateSimulationRequest {
  input_values: Record<string, unknown>;
  full_override?: boolean;
}
```

**Step 2: Verify TypeScript compilation**

**Step 3: Commit**

---

### Task 5: Frontend Simulation API Client

**Files:**
- Create: `ontology_engine-ui/src/api/simulation.ts`

**Step 1: Write tests**

```typescript
// ontology_engine-ui/src/api/__tests__/simulation.test.ts
import { simulationApi } from '../simulation';

describe('simulationApi', () => {
  it('should create simulation session', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      json: () => Promise.resolve({
        success: true,
        data: {
          session_id: 'test-123',
          execution_tree: { layers: [] },
          required_inputs: [],
          current_inputs: {},
        },
      }),
    });

    const result = await simulationApi.createTree({
      schema_id: 'schema_001',
      target_output: 'decision',
    });

    expect(result.session_id).toBe('test-123');
  });
});
```

**Step 2: Write implementation**

```typescript
// ontology_engine-ui/src/api/simulation.ts
import { apiClient } from './client';
import type {
  ExecutionTree,
  SimulationResult,
  CreateSimulationRequest,
  UpdateSimulationRequest,
} from '../types/simulation';

export interface CreateSimulationResponse {
  session_id: string;
  execution_tree: ExecutionTree;
  required_inputs: string[];
  current_inputs: Record<string, unknown>;
}

export interface UpdateSimulationResponse {
  session_id: string;
  updated_inputs: Record<string, unknown>;
  result: SimulationResult | null;
  missing_inputs: string[];
}

export const simulationApi = {
  /**
   * Create a new simulation session and build execution tree
   */
  createTree: async (request: CreateSimulationRequest): Promise<CreateSimulationResponse> => {
    const response = await apiClient.post('/simulation/tree', request);
    return response.data.data;
  },

  /**
   * Get current simulation session state
   */
  getSession: async (sessionId: string): Promise<CreateSimulationResponse> => {
    const response = await apiClient.get(`/simulation/${sessionId}`);
    return response.data.data;
  },

  /**
   * Update simulation inputs (partial or full override)
   */
  updateInputs: async (sessionId: string, request: UpdateSimulationRequest): Promise<UpdateSimulationResponse> => {
    const response = await apiClient.patch(`/simulation/${sessionId}`, request);
    return response.data.data;
  },

  /**
   * Delete a simulation session
   */
  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/simulation/${sessionId}`);
  },
};

export default simulationApi;
```

**Step 3: Verify TypeScript compilation**

**Step 4: Commit**

---

### Task 6: SimulationEmbedPage Component

**Files:**
- Create: `ontology_engine-ui/src/pages/simulation/SimulationEmbedPage.tsx`

**Step 1: Write component**

```typescript
// ontology_engine-ui/src/pages/simulation/SimulationEmbedPage.tsx
import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, Button, Space, message, Spin } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { simulationApi } from '../../api/simulation';
import { SimulationProvider } from '../../components/simulation/SimulationProvider';
import { SimulationPanel } from '../../components/simulation/SimulationPanel';
import type { ExecutionTree, SimulationResult } from '../../types/simulation';

interface SimulationEmbedPageProps {
  schemaId?: string;
  entityId?: string;
  targetOutput?: string;
  onResultChange?: (result: SimulationResult) => void;
  onError?: (error: string) => void;
}

export default function SimulationEmbedPage({
  schemaId: initialSchemaId,
  entityId: initialEntityId,
  targetOutput: initialTargetOutput,
  onResultChange,
  onError,
}: SimulationEmbedPageProps) {
  const [searchParams] = useSearchParams();

  // URL params take precedence over props
  const schemaId = searchParams.get('schemaId') || initialSchemaId || '';
  const entityId = searchParams.get('entityId') || initialEntityId;
  const targetOutput = searchParams.get('targetOutput') || initialTargetOutput || '';

  return (
    <SimulationProvider schemaId={schemaId}>
      <div style={{ padding: 16 }}>
        <SimulationPanel
          initialSchemaId={schemaId}
          initialEntityId={entityId}
          initialTargetOutput={targetOutput}
          onResultChange={onResultChange}
          onError={onError}
        />
      </div>
    </SimulationProvider>
  );
}
```

**Step 2: Verify build**

**Step 3: Commit**

---

### Task 7: SimulationProvider (postMessage预留)

**Files:**
- Create: `ontology_engine-ui/src/components/simulation/SimulationProvider.tsx`

**Step 1: Write provider**

```typescript
// ontology_engine-ui/src/components/simulation/SimulationProvider.tsx
import React, { createContext, useContext, useEffect, useRef } from 'react';
import type { SimulationResult } from '../../types/simulation';

interface SimulationContextValue {
  schemaId: string;
  sessionId: string | null;
  result: SimulationResult | null;
  // AGUI postMessage预留
  postMessage: (type: string, payload: unknown) => void;
}

const SimulationContext = createContext<SimulationContextValue | null>(null);

export function SimulationProvider({
  schemaId,
  children,
}: {
  schemaId: string;
  children: React.ReactNode;
}) {
  const sessionIdRef = useRef<string | null>(null);

  // postMessage预留 - 未来Agent集成
  const postMessage = useCallback((type: string, payload: unknown) => {
    if (typeof window !== 'undefined' && window.parent !== window) {
      window.parent.postMessage({ type, payload }, '*');
    }
  }, []);

  // Listen for postMessage from parent (AGUI预留)
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const { type, payload } = event.data || {};
      // Future: handle INIT, UPDATE_INPUT, RUN commands from Agent
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const value: SimulationContextValue = {
    schemaId,
    sessionId: sessionIdRef.current,
    result: null,
    postMessage,
  };

  return (
    <SimulationContext.Provider value={value}>
      {children}
    </SimulationContext.Provider>
  );
}

export function useSimulationContext() {
  const context = useContext(SimulationContext);
  if (!context) {
    throw new Error('useSimulationContext must be used within SimulationProvider');
  }
  return context;
}
```

**Step 2: Verify build**

**Step 3: Commit**

---

### Task 8: SimulationPanel Component

**Files:**
- Create: `ontology_engine-ui/src/components/simulation/SimulationPanel.tsx`

**Step 1: Write component**

```typescript
// ontology_engine-ui/src/components/simulation/SimulationPanel.tsx
import { useState } from 'react';
import { Card, Button, Space, message, Empty, Spin } from 'antd';
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { simulationApi } from '../../api/simulation';
import { ExecutionTreeViewer } from './ExecutionTreeViewer';
import { InputValuesForm } from './InputValuesForm';
import { SimulationResultPanel } from './SimulationResultPanel';
import type { ExecutionTree, SimulationResult } from '../../types/simulation';

interface SimulationPanelProps {
  initialSchemaId: string;
  initialEntityId?: string;
  initialTargetOutput?: string;
  onResultChange?: (result: SimulationResult) => void;
  onError?: (error: string) => void;
}

export function SimulationPanel({
  initialSchemaId,
  initialEntityId,
  initialTargetOutput = '',
  onResultChange,
  onError,
}: SimulationPanelProps) {
  const [schemaId] = useState(initialSchemaId);
  const [entityId, setEntityId] = useState(initialEntityId || '');
  const [targetOutput, setTargetOutput] = useState(initialTargetOutput);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [executionTree, setExecutionTree] = useState<ExecutionTree | null>(null);
  const [inputValues, setInputValues] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);

  const createSession = async () => {
    if (!schemaId || !targetOutput) {
      message.warning('请输入目标输出要素');
      return;
    }

    setLoading(true);
    try {
      const response = await simulationApi.createTree({
        schema_id: schemaId,
        entity_id: entityId || undefined,
        target_output: targetOutput,
      });

      setSessionId(response.session_id);
      setExecutionTree(response.execution_tree);
      setInputValues(response.current_inputs || {});
      setResult(null);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : '创建会话失败');
    } finally {
      setLoading(false);
    }
  };

  const runSimulation = async () => {
    if (!sessionId) return;

    setLoading(true);
    try {
      const response = await simulationApi.updateInputs(sessionId, {
        input_values: inputValues,
      });

      setResult(response.result);
      onResultChange?.(response.result);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : '模拟执行失败');
    } finally {
      setLoading(false);
    }
  };

  const updateInputs = (updates: Record<string, unknown>) => {
    const newInputs = { ...inputValues, ...updates };
    setInputValues(newInputs);
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {/* Configuration Card */}
      <Card title="模拟配置">
        <Space wrap>
          <div>
            <label>目标输出: </label>
            <input
              value={targetOutput}
              onChange={(e) => setTargetOutput(e.target.value)}
              placeholder="如: decision"
              style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
            />
          </div>
          <div>
            <label>实体ID: </label>
            <input
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="可选"
              style={{ padding: '4px 8px', border: '1px solid #d9d9d9', borderRadius: 4 }}
            />
          </div>
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            onClick={createSession}
            loading={loading}
            disabled={!schemaId || !targetOutput}
          >
            构建执行树
          </Button>
        </Space>
      </Card>

      {/* Execution Tree */}
      {executionTree && (
        <ExecutionTreeViewer
          tree={executionTree}
          onStepClick={(step) => {
            // Highlight step
          }}
        />
      )}

      {/* Input Values */}
      {executionTree && (
        <InputValuesForm
          inputs={executionTree.layers.flatMap(l => l.input_requirements || [])}
          values={inputValues}
          onChange={updateInputs}
        />
      )}

      {/* Run Button */}
      {executionTree && (
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          onClick={runSimulation}
          loading={loading}
          disabled={!sessionId}
        >
          运行模拟
        </Button>
      )}

      {/* Result */}
      {result && <SimulationResultPanel result={result} tree={executionTree} />}

      {!executionTree && !loading && (
        <Empty description="配置目标输出后构建执行树" />
      )}
    </Space>
  );
}
```

**Step 2: Verify build**

**Step 3: Commit**

---

### Task 9: ExecutionTreeViewer Component

**Files:**
- Create: `ontology_engine-ui/src/components/simulation/ExecutionTreeViewer.tsx`

**Step 1: Write component**

```typescript
// ontology_engine-ui/src/components/simulation/ExecutionTreeViewer.tsx
import { Card, Tabs, Tag, Typography } from 'antd';
import type { ExecutionTree, ExecutableStep } from '../../types/simulation';

const { Text } = Typography;

interface ExecutionTreeViewerProps {
  tree: ExecutionTree;
  onStepClick?: (step: ExecutableStep) => void;
}

export function ExecutionTreeViewer({ tree, onStepClick }: ExecutionTreeViewerProps) {
  const tabItems = tree.layers.map((layer, idx) => ({
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
            <div style={{ marginBottom: 8 }}>
              <Tag color={getTypeColor(step.rule_group_type)}>
                {step.rule_group_name}
              </Tag>
            </div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              {step.step_name}
            </Text>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>
              条件: {step.condition.expression || `${step.condition.type}`}
            </div>
            <div style={{ fontSize: 12, color: '#1890ff' }}>
              → {step.action.operator}
            </div>
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
              输出: {step.output_names.join(', ')}
            </div>
          </Card>
        ))}
      </div>
    ),
  }));

  return (
    <Card title="执行树">
      <Tabs items={tabItems} />
    </Card>
  );
}

function getTypeColor(type: string): string {
  const colors: Record<string, string> = {
    constraint: 'blue',
    inference: 'purple',
    alert: 'orange',
    decision: 'green',
  };
  return colors[type] || 'default';
}
```

**Step 2: Verify build**

**Step 3: Commit**

---

### Task 10: InputValuesForm Component

**Files:**
- Create: `ontology_engine-ui/src/components/simulation/InputValuesForm.tsx`

**Step 1: Write component**

```typescript
// ontology_engine-ui/src/components/simulation/InputValuesForm.tsx
import { Card, Input, Typography } from 'antd';
import type { InputRequirement } from '../../types/simulation';

const { Text } = Typography;

interface InputValuesFormProps {
  inputs: InputRequirement[];
  values: Record<string, unknown>;
  onChange: (updates: Record<string, unknown>) => void;
}

export function InputValuesForm({ inputs, values, onChange }: InputValuesFormProps) {
  return (
    <Card title="输入要素">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, 200px)', gap: 12 }}>
        {inputs.map((input) => (
          <div key={input.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {input.name}
              {input.required && <span style={{ color: '#ff4d4f' }}> *</span>}
            </Text>
            <Input
              value={String(values[input.name] ?? input.default_value ?? '')}
              onChange={(e) => onChange({ [input.name]: e.target.value })}
              placeholder={input.description || input.type}
            />
            <Text type="secondary" style={{ fontSize: 10 }}>{input.type}</Text>
          </div>
        ))}
      </div>
    </Card>
  );
}
```

**Step 2: Verify build**

**Step 3: Commit**

---

### Task 11: SimulationResultPanel Component

**Files:**
- Create: `ontology_engine-ui/src/components/simulation/SimulationResultPanel.tsx`

**Step 1: Write component**

```typescript
// ontology_engine-ui/src/components/simulation/SimulationResultPanel.tsx
import { Card, Collapse, Tag, Space, Typography, Alert } from 'antd';
import type { SimulationResult } from '../../types/simulation';

const { Text, Pre } = Typography;

interface SimulationResultPanelProps {
  result: SimulationResult | null;
  tree: any;
}

export function SimulationResultPanel({ result, tree }: SimulationResultPanelProps) {
  if (!result) {
    return (
      <Card title="模拟结果">
        <Text type="secondary">暂无结果</Text>
      </Card>
    );
  }

  const collapseItems = result.steps.map((step, idx) => ({
    key: step.step_id,
    label: (
      <Space>
        <Tag color={step.error ? 'red' : step.condition_result ? 'green' : 'orange'}>
          {step.condition_result ? '通过' : '跳过'}
        </Tag>
        <Text>{step.step_name}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {step.duration_ms}ms
        </Text>
      </Space>
    ),
    children: (
      <div>
        <div>条件: {step.condition_detail?.explanation || '-'}</div>
        <div>动作: {step.action_taken}</div>
        <div>输入: {JSON.stringify(step.input_values_used)}</div>
        <div>输出: {JSON.stringify(step.output)}</div>
        {step.error && (
          <Alert type="error" message={step.error} />
        )}
      </div>
    ),
  }));

  return (
    <Card title="模拟结果">
      {/* Final Output */}
      <div style={{ marginBottom: 16 }}>
        <Text strong>最终输出:</Text>
        <Pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
          {JSON.stringify(result.final_output, null, 2)}
        </Pre>
      </div>

      {/* Steps */}
      <Collapse items={collapseItems} />

      {/* Alerts */}
      {result.alerts.length > 0 && (
        <Alert
          type="warning"
          message={`${result.alerts.length} 个预警`}
          description={result.alerts.map(a => a.message).join(', ')}
          style={{ marginTop: 16 }}
        />
      )}

      {/* Errors */}
      {result.errors.length > 0 && (
        <Alert
          type="error"
          message={`${result.errors.length} 个错误`}
          description={result.errors.join('\n')}
          style={{ marginTop: 16 }}
        />
      )}

      <Text type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
        执行时间: {result.execution_time_ms}ms
      </Text>
    </Card>
  );
}
```

**Step 2: Verify build**

**Step 3: Commit**

---

### Task 12: Add Simulation Embed Route

**Files:**
- Modify: `ontology_engine-ui/src/App.tsx`

**Step 1: Add route**

```typescript
// Add import
import SimulationEmbedPage from './pages/simulation/SimulationEmbedPage';

// Add route
<Route path="/simulation/embed" element={<SimulationEmbedPage />} />
```

**Step 2: Verify build**

**Step 3: Commit**

---

## Phase 3: Integration & Documentation

### Task 13: Integration Test

**Files:**
- Create: `tests/integration/test_simulation_flow.py`

**Step 1: Write integration test**

```python
def test_simulation_flow(client):
    # 1. Create session
    response = client.post("/v1/simulation/tree", json={
        "schema_id": "test_schema",
        "target_output": "decision",
    })
    assert response.status_code == 200
    session_id = response.json()["data"]["session_id"]

    # 2. Get session
    response = client.get(f"/v1/simulation/{session_id}")
    assert response.status_code == 200

    # 3. Update inputs
    response = client.patch(f"/v1/simulation/{session_id}", json={
        "input_values": {"credit_score": 80},
    })
    assert response.status_code == 200

    # 4. Delete session
    response = client.delete(f"/v1/simulation/{session_id}")
    assert response.status_code == 200
```

**Step 2: Run test**

**Step 3: Commit**

---

### Task 14: Update Documentation

**Files:**
- Modify: `docs/STATUS.md` — Update rule-engine status
- Create: `docs/plans/2026-04-21-simulation-embeddable-ui.md` — This plan

**Step 1: Update STATUS.md**

**Step 2: Commit**

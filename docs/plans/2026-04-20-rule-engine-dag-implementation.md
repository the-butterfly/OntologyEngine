# 规则引擎 DAG 化实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将规则引擎从 priority 排序执行升级为 DAG 拓扑执行，实现规则串联、模拟仿真、发布执行能力。

**Architecture:** DAGBuilder 构建依赖图 → DAGExecutor 拓扑执行 → PipelineStateManager 持久化 → LogicalEdgeEngine 管理推理边。RuleStep 增加 `depends_on` 字段支持显式依赖声明，支持跨规则组调用。

**Tech Stack:** Python asyncio, simpleeval/asteval (已有), SQLite (已有), KuzuDB (已有)

---

## 背景：当前状态 vs 目标状态

| 维度 | 当前实现 | 目标设计 |
|------|----------|----------|
| 执行模型 | `sorted(rules, key=lambda r: -r.priority)` | DAGBuilder 拓扑排序 |
| 依赖声明 | 无 `depends_on` 字段 | 显式 `depends_on: [step_id, ...]` |
| 并行执行 | 顺序执行 | 同层 `asyncio.gather` 并行 |
| 状态持久化 | 仅内存 `AnalysisResult` | `PipelineRun` + `ExecutionStepSnapshot` 入 SQLite |
| 回滚机制 | 无 | `RuleTransaction.snapshot/restore` |
| 推理边 | 无 | `LogicalEdgeEngine` 按需计算 |

---

## 讨论点（需确认）

1. **跨规则组依赖**：`RuleStep.depends_on` 是否支持跨规则组引用？格式为 `"rule_group/step_id"` 还是 `"step_id"` + 跨规则组校验？

2. **回滚粒度**：当前设计按 DAG 层回滚，是否需要支持更细粒度的单步回滚？

3. **模拟 vs 执行**：模拟是否走同样的 DAGExecutor 但不持久化结果？还是有独立的模拟路径？

4. **推理边存储**：inference 边是否写入 KuzuDB（与 business 边共存），还是仅存在内存中？

---

## Task 1: RuleStep 模型扩展 — 增加 depends_on 字段

**Files:**
- Modify: `ontology_engine/engine/rule/models.py:236-294`

**Step 1: Write the failing test**

```python
# tests/unit/engine/rule/test_models.py
def test_rule_step_depends_on_field():
    """RuleStep should support depends_on for DAG dependency declaration."""
    step = RuleStep(
        id="step_a",
        name="Step A",
        rule_group="test_group",
        order=1,
        when=ConditionClause(type="expression", expression="True"),
        then=ActionClause(operator="set_flag", params={"flag": "a", "value": True}),
        depends_on=[],  # New field
    )
    assert step.depends_on == []

    step_with_deps = RuleStep(
        id="step_c",
        name="Step C",
        rule_group="test_group",
        order=3,
        when=ConditionClause(type="expression", expression="a == True"),
        then=ActionClause(operator="compute", params={"formula": "b + 1"}),
        depends_on=["step_a", "step_b"],  # Depends on other steps
    )
    assert step_with_deps.depends_on == ["step_a", "step_b"]
    assert "step_a" in step_with_deps.depends_on
    assert "step_b" in step_with_deps.depends_on

def test_rule_step_to_dict_includes_depends_on():
    """RuleStep.to_dict() should include depends_on field."""
    step = RuleStep(
        id="step_a",
        name="Step A",
        rule_group="test_group",
        order=1,
        when=ConditionClause(type="expression", expression="True"),
        then=ActionClause(operator="set_flag", params={"flag": "a", "value": True}),
        depends_on=["step_x"],
    )
    d = step.to_dict()
    assert "depends_on" in d
    assert d["depends_on"] == ["step_x"]

def test_rule_step_from_dict_with_depends_on():
    """RuleStep.from_dict() should parse depends_on field."""
    data = {
        "id": "step_b",
        "name": "Step B",
        "rule_group": "test_group",
        "step_order": 2,
        "when": {"type": "expression", "expression": "x > 0"},
        "then": {"operator": "compute", "params": {}},
        "depends_on": ["step_a"],
    }
    step = RuleStep.from_dict(data)
    assert step.depends_on == ["step_a"]
```

**Step 2: Run test to verify it fails**

```bash
cd /Volumes/Extension/Projects/CodeDev/OntologyEngine
pytest tests/unit/engine/rule/test_models.py::test_rule_step_depends_on_field -v
```
Expected: FAIL — `'RuleStep' object has no attribute 'depends_on'`

**Step 3: Modify RuleStep model**

```python
# In models.py, add depends_on field to RuleStep dataclass (around line 237)
@dataclass
class RuleStep:
    """..."""
    id: str
    name: str
    rule_group: str
    order: int
    when: ConditionClause
    then: ActionClause
    else_: ActionClause | None = None
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # NEW: DAG dependency declaration

    def to_dict(self) -> dict[str, Any]:
        return {
            # ... existing fields ...
            "depends_on": self.depends_on,  # NEW
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleStep":
        # ... existing parsing ...
        return cls(
            id=data["id"],
            # ... existing fields ...
            depends_on=data.get("depends_on", []),  # NEW
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/engine/rule/test_models.py::test_rule_step_depends_on_field tests/unit/engine/rule/test_models.py::test_rule_step_to_dict_includes_depends_on tests/unit/engine/rule/test_models.py::test_rule_step_from_dict_with_depends_on -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/engine/rule/models.py tests/unit/engine/rule/test_models.py
git commit -m "feat(rule): add depends_on field to RuleStep for DAG dependencies"
```

---

## Task 2: DAGBuilder 实现

**Files:**
- Create: `ontology_engine/engine/rule/dag_builder.py`
- Test: `tests/unit/engine/rule/test_dag_builder.py`

**Step 1: Write the failing test**

```python
# tests/unit/engine/rule/test_dag_builder.py
import pytest
from ontology_engine.engine.rule.dag_builder import DAGBuilder, DAGNode, DAGLayer, ExecutionDAG, CycleError

def test_dag_builder_single_step():
    """Single step with no dependencies should be in Layer 0."""
    steps = [
        RuleStep(id="A", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="set_flag", params={}),
                 depends_on=[]),
    ]
    builder = DAGBuilder()
    dag = builder.build(steps)

    assert len(dag.layers) == 1
    assert dag.layers[0].index == 0
    assert len(dag.layers[0].nodes) == 1
    assert dag.layers[0].nodes[0].step_id == "A"

def test_dag_builder_linear_dependency():
    """A -> B -> C should result in 3 layers."""
    steps = [
        RuleStep(id="A", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="set_flag", params={}),
                 depends_on=[]),
        RuleStep(id="B", name="B", rule_group="G", order=2,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["A"]),
        RuleStep(id="C", name="C", rule_group="G", order=3,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["B"]),
    ]
    builder = DAGBuilder()
    dag = builder.build(steps)

    assert len(dag.layers) == 3
    assert dag.layers[0].nodes[0].step_id == "A"
    assert dag.layers[1].nodes[0].step_id == "B"
    assert dag.layers[2].nodes[0].step_id == "C"

def test_dag_builder_parallel_steps():
    """A -> B, A -> C (B and C parallel) should result in 2 layers."""
    steps = [
        RuleStep(id="A", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="set_flag", params={}),
                 depends_on=[]),
        RuleStep(id="B", name="B", rule_group="G", order=2,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["A"]),
        RuleStep(id="C", name="C", rule_group="G", order=3,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["A"]),
    ]
    builder = DAGBuilder()
    dag = builder.build(steps)

    assert len(dag.layers) == 2
    assert dag.layers[0].nodes[0].step_id == "A"
    assert set(n.step_id for n in dag.layers[1].nodes) == {"B", "C"}

def test_dag_builder_complex_dag():
    """D depends on B and C; B and C depend on A. Should be 3 layers."""
    steps = [
        RuleStep(id="A", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="set_flag", params={}),
                 depends_on=[]),
        RuleStep(id="B", name="B", rule_group="G", order=2,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["A"]),
        RuleStep(id="C", name="C", rule_group="G", order=3,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["A"]),
        RuleStep(id="D", name="D", rule_group="G", order=4,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["B", "C"]),
    ]
    builder = DAGBuilder()
    dag = builder.build(steps)

    assert len(dag.layers) == 3
    assert dag.layers[0].nodes[0].step_id == "A"
    assert set(n.step_id for n in dag.layers[1].nodes) == {"B", "C"}
    assert dag.layers[2].nodes[0].step_id == "D"

def test_dag_builder_cycle_detection():
    """A -> B -> C -> A should raise CycleError."""
    steps = [
        RuleStep(id="A", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="set_flag", params={}),
                 depends_on=["C"]),  # A depends on C
        RuleStep(id="B", name="B", rule_group="G", order=2,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["A"]),
        RuleStep(id="C", name="C", rule_group="G", order=3,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="compute", params={}),
                 depends_on=["B"]),
    ]
    builder = DAGBuilder()
    with pytest.raises(CycleError) as exc_info:
        dag = builder.build(steps)
    assert "cycle" in str(exc_info.value).lower()

def test_dag_builder_missing_dependency():
    """Depends on non-existent step should raise KeyError."""
    steps = [
        RuleStep(id="A", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="set_flag", params={}),
                 depends_on=["nonexistent"]),
    ]
    builder = DAGBuilder()
    with pytest.raises(KeyError) as exc_info:
        dag = builder.build(steps)
    assert "nonexistent" in str(exc_info.value)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/engine/rule/test_dag_builder.py -v
```
Expected: FAIL — `No module named 'ontology_engine.engine.rule.dag_builder'`

**Step 3: Implement DAGBuilder**

```python
# ontology_engine/engine/rule/dag_builder.py
"""DAG Builder for rule execution ordering."""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
from typing import Any

from ontology_engine.engine.rule.models import RuleStep


class CycleError(Exception):
    """Raised when a circular dependency is detected in rule steps."""
    def __init__(self, message: str, cycle_path: list[str] | None = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []


@dataclass
class DAGNode:
    """A node in the execution DAG."""
    step_id: str
    step: RuleStep
    in_degree: int = 0
    dependents: list[str] = field(default_factory=list)


@dataclass
class DAGLayer:
    """A topological layer of the DAG."""
    index: int
    nodes: list[DAGNode]


@dataclass
class ExecutionDAG:
    """Complete execution DAG with topological layers."""
    layers: list[DAGLayer]
    step_map: dict[str, DAGNode]
    has_cycle: bool = False


class DAGBuilder:
    """Builds execution DAG from rule steps with depends_on declarations."""

    def build(self, steps: list[RuleStep]) -> ExecutionDAG:
        """Build DAG from steps using Kahn's algorithm.

        Args:
            steps: List of RuleStep objects with depends_on declarations

        Returns:
            ExecutionDAG with topological layers

        Raises:
            CycleError: If circular dependencies detected
            KeyError: If depends_on references non-existent step
        """
        # Create nodes for all steps
        step_map: dict[str, DAGNode] = {}
        for step in steps:
            node = DAGNode(step_id=step.id, step=step)
            step_map[step.id] = node

        # Build edges from depends_on
        for step in steps:
            node = step_map[step.id]
            for dep_id in step.depends_on:
                if dep_id not in step_map:
                    raise KeyError(f"Step '{step.id}' depends on non-existent step '{dep_id}'")
                dep_node = step_map[dep_id]
                dep_node.dependents.append(step.id)
                node.in_degree += 1

        # Kahn's algorithm for topological sort
        layers: list[DAGLayer] = []
        queue = deque()
        
        # Initialize queue with nodes that have no dependencies
        for node in step_map.values():
            if node.in_degree == 0:
                queue.append(node)

        layer_index = 0
        while queue:
            current_layer_nodes = []
            next_queue = deque()

            for _ in range(len(queue)):
                node = queue.popleft()
                current_layer_nodes.append(node)

                # For each dependent, decrease in_degree
                for dependent_id in node.dependents:
                    dependent_node = step_map[dependent_id]
                    dependent_node.in_degree -= 1
                    if dependent_node.in_degree == 0:
                        next_queue.append(dependent_node)

            layers.append(DAGLayer(index=layer_index, nodes=current_layer_nodes))
            queue = next_queue
            layer_index += 1

        # Check for cycles
        total_nodes = len(step_map)
        nodes_in_layers = sum(len(layer.nodes) for layer in layers)
        if nodes_in_layers != total_nodes:
            # Find nodes not in any layer (part of cycle)
            nodes_in_layers_set = set()
            for layer in layers:
                for node in layer.nodes:
                    nodes_in_layers_set.add(node.step_id)
            cycle_nodes = set(step_map.keys()) - nodes_in_layers_set
            cycle_path = list(cycle_nodes)[:5]  # Show first 5 nodes
            raise CycleError(
                f"Circular dependency detected involving steps: {cycle_path}",
                cycle_path=cycle_path
            )

        return ExecutionDAG(layers=layers, step_map=step_map, has_cycle=False)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/engine/rule/test_dag_builder.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/engine/rule/dag_builder.py tests/unit/engine/rule/test_dag_builder.py
git commit -m "feat(rule): implement DAGBuilder with Kahn's algorithm for topological sort"
```

---

## Task 3: RuleTransaction (快照回滚)

**Files:**
- Create: `ontology_engine/engine/rule/transaction.py`
- Test: `tests/unit/engine/rule/test_transaction.py`

**Step 1: Write the failing test**

```python
# tests/unit/engine/rule/test_transaction.py
import pytest
from ontology_engine.engine.rule.transaction import ContextSnapshot, RuleTransaction
from ontology_engine.engine.rule.models import ExecutionContext, Alert

def test_snapshot_captures_current_state():
    """Snapshot should capture all context state."""
    context = ExecutionContext(
        entity_id="E1",
        dimension="risk",
        entity_data={"score": 80},
        computed_metrics={"credit_score": 75, "risk_level": "low"},
        alerts=[Alert(level="warning", type="large_transaction", message="Big deal")],
    )
    
    tx = RuleTransaction(context)
    snap = tx.snapshot()
    
    assert snap.computed_metrics == {"credit_score": 75, "risk_level": "low"}
    assert snap.alerts[0].message == "Big deal"
    assert snap.flags == {}

def test_restore_rolls_back_changes():
    """Restore should revert context to snapshot state."""
    context = ExecutionContext(
        entity_id="E1",
        dimension="risk",
        entity_data={"score": 80},
        computed_metrics={"a": 1},
        alerts=[],
        flags={"flag_x": False},
    )
    
    tx = RuleTransaction(context)
    original_snap = tx.snapshot()
    
    # Modify context
    context.computed_metrics["b"] = 2
    context.computed_metrics["a"] = 99
    context.flags["flag_x"] = True
    context.alerts.append(Alert(level="info", type="test", message="New alert"))
    
    assert context.computed_metrics == {"a": 99, "b": 2}
    assert context.flags == {"flag_x": True}
    assert len(context.alerts) == 1
    
    # Restore
    tx.restore(original_snap)
    
    assert context.computed_metrics == {"a": 1}
    assert "b" not in context.computed_metrics
    assert context.flags == {"flag_x": False}
    assert len(context.alerts) == 0

def test_snapshot_is_independent():
    """Modifying context after snapshot should not affect snapshot."""
    context = ExecutionContext(
        entity_id="E1",
        dimension="risk",
        entity_data={},
        computed_metrics={"x": 1},
    )
    
    tx = RuleTransaction(context)
    snap = tx.snapshot()
    
    context.computed_metrics["x"] = 999
    context.computed_metrics["y"] = 2
    
    assert snap.computed_metrics == {"x": 1}  # Unchanged
    assert "y" not in snap.computed_metrics

def test_commit_clears_snapshots():
    """Commit should clear snapshot history."""
    context = ExecutionContext(entity_id="E1", dimension="risk", entity_data={})
    tx = RuleTransaction(context)
    
    tx.snapshot()
    tx.snapshot()
    assert len(tx._snapshots) == 2
    
    tx.commit()
    assert len(tx._snapshots) == 0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/engine/rule/test_transaction.py -v
```
Expected: FAIL — `No module named 'ontology_engine.engine.rule.transaction'`

**Step 3: Implement RuleTransaction**

```python
# ontology_engine/engine/rule/transaction.py
"""Rule transaction with snapshot/restore for rollback support."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import copy

from ontology_engine.engine.rule.models import ExecutionContext, Alert


@dataclass
class ContextSnapshot:
    """Point-in-time snapshot of ExecutionContext."""
    timestamp: str
    computed_metrics: dict[str, Any]
    flags: dict[str, Any]
    alerts: list[Alert]
    categories: dict[str, str]


class RuleTransaction:
    """Manages snapshots for rollback support in DAG execution."""

    def __init__(self, context: ExecutionContext):
        self.context = context
        self._snapshots: list[ContextSnapshot] = []

    def snapshot(self) -> ContextSnapshot:
        """Capture current state of context.

        Returns:
            ContextSnapshot with deep copy of mutable state
        """
        snap = ContextSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            computed_metrics=copy.deepcopy(self.context.computed_metrics),
            flags=copy.deepcopy(self.context.flags),
            alerts=list(self.context.alerts),  # Alert is immutable dataclass
            categories=copy.deepcopy(getattr(self.context, 'categories', {})),
        )
        self._snapshots.append(snap)
        return snap

    def restore(self, snapshot: ContextSnapshot) -> None:
        """Restore context to snapshot state.

        Args:
            snapshot: The snapshot to restore to
        """
        self.context.computed_metrics = snapshot.computed_metrics
        self.context.flags = snapshot.flags
        self.context.alerts = snapshot.alerts
        if hasattr(self.context, 'categories'):
            self.context.categories = snapshot.categories

    def commit(self) -> None:
        """Clear snapshots after successful layer execution."""
        self._snapshots.clear()

    @property
    def has_snapshots(self) -> bool:
        return len(self._snapshots) > 0
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/engine/rule/test_transaction.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/engine/rule/transaction.py tests/unit/engine/rule/test_transaction.py
git commit -m "feat(rule): implement RuleTransaction with snapshot/restore for rollback"
```

---

## Task 4: DAGExecutor 实现

**Files:**
- Create: `ontology_engine/engine/rule/dag_executor.py`
- Modify: `ontology_engine/engine/rule/models.py` (add StepResult, ErrorStrategy)
- Test: `tests/unit/engine/rule/test_dag_executor.py`

**Step 1: Write the failing test**

```python
# tests/unit/engine/rule/test_dag_executor.py
import pytest
import asyncio
from ontology_engine.engine.rule.dag_executor import DAGExecutor, StepResult, ErrorStrategy, LayerExecutionError
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.models import (
    ExecutionContext, RuleStep, ConditionClause, ActionClause, Alert
)
from ontology_engine.engine.rule.operators.base import OperatorRegistry

@pytest.fixture
def operator_registry():
    """Reset and return operator registry."""
    OperatorRegistry._operators = {}
    # Register a simple test operator
    from ontology_engine.engine.rule.operators.base import Operator
    class TestAddOperator(Operator):
        name = "test_add"
        def execute(self, inputs, config, context):
            a = inputs.get("a", 0)
            b = inputs.get("b", 0)
            return {"result": a + b}
    OperatorRegistry.register("test_add", TestAddOperator())
    return OperatorRegistry

@pytest.fixture
def sample_steps():
    return [
        RuleStep(id="step_a", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="test_add", params={"a": 1, "b": 2}),
                 depends_on=[]),
        RuleStep(id="step_b", name="B", rule_group="G", order=2,
                 when=ConditionClause(type="expression", expression="result > 0"),
                 then=ActionClause(operator="test_add", params={"a": 3, "b": 4}),
                 depends_on=["step_a"]),
    ]

@pytest.mark.asyncio
async def test_execute_linear_dag(operator_registry, sample_steps):
    """Linear DAG A -> B should execute in correct order."""
    from ontology_engine.engine.expression.engine import ExpressionEngine
    
    builder = DAGBuilder()
    dag = builder.build(sample_steps)
    
    executor = DAGExecutor(operator_registry, ExpressionEngine())
    context = ExecutionContext(entity_id="E1", dimension="test", entity_data={})
    
    result = await executor.execute(dag, context)
    
    assert "step_a" in result.results
    assert "step_b" in result.results
    assert result.results["step_a"].output.get("result") == 3  # 1 + 2

@pytest.mark.asyncio
async def test_condition_not_met_skips_step(operator_registry):
    """Step with false condition should be skipped."""
    steps = [
        RuleStep(id="step_a", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="False"),
                 then=ActionClause(operator="test_add", params={"a": 1, "b": 2}),
                 depends_on=[]),
    ]
    
    builder = DAGBuilder()
    dag = builder.build(steps)
    
    executor = DAGExecutor(operator_registry, ExpressionEngine())
    context = ExecutionContext(entity_id="E1", dimension="test", entity_data={})
    
    result = await executor.execute(dag, context)
    
    assert "step_a" in result.results
    assert result.results["step_a"].skipped == True

@pytest.mark.asyncio
async def test_parallel_layer_execution(operator_registry):
    """Parallel steps in same layer should execute concurrently."""
    steps = [
        RuleStep(id="step_a", name="A", rule_group="G", order=1,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="test_add", params={"a": 1, "b": 1}),
                 depends_on=[]),
        RuleStep(id="step_b", name="B", rule_group="G", order=2,
                 when=ConditionClause(type="expression", expression="True"),
                 then=ActionClause(operator="test_add", params={"a": 10, "b": 10}),
                 depends_on=[]),  # No dependency on A
    ]
    
    builder = DAGBuilder()
    dag = builder.build(steps)
    
    executor = DAGExecutor(operator_registry, ExpressionEngine())
    context = ExecutionContext(entity_id="E1", dimension="test", entity_data={})
    
    result = await executor.execute(dag, context)
    
    assert len(result.results) == 2
    # Both should complete (order may vary but both present)
    assert "step_a" in result.results
    assert "step_b" in result.results
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/engine/rule/test_dag_executor.py -v
```
Expected: FAIL — `No module named 'ontology_engine.engine.rule.dag_executor'`

**Step 3: Add missing model classes to models.py**

```python
# Add to models.py

@dataclass
class StepResult:
    """Result of a single step execution."""
    step_id: str
    skipped: bool = False
    rejected: bool = False
    reason: str | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    alert_emitted: bool = False


class ErrorStrategy(Enum):
    """Error handling strategy for DAG layer execution."""
    STOP_LAYER = "stop_layer"  # Rollback layer, raise error
    CONTINUE = "continue"  # Skip failed, continue
    ABORT_ALL = "abort_all"  # Rollback all, stop immediately


class ExecutionAbortedError(Exception):
    """Raised when ABORT_ALL strategy is triggered."""
    pass


class LayerExecutionError(Exception):
    """Raised when a layer fails with STOP_LAYER strategy."""
    def __init__(self, layer_index: int, errors: list[Exception]):
        self.layer_index = layer_index
        self.errors = errors
        super().__init__(f"Layer {layer_index} failed with {len(errors)} error(s)")
```

**Step 4: Implement DAGExecutor**

```python
# ontology_engine/engine/rule/dag_executor.py
"""DAG Executor with parallel execution and error handling."""

from __future__ import annotations
import asyncio
import logging
from typing import Any

from ontology_engine.engine.rule.dag_builder import ExecutionDAG, DAGNode
from ontology_engine.engine.rule.models import (
    ExecutionContext, RuleStep, ActionClause, Alert,
    StepResult, ErrorStrategy
)
from ontology_engine.engine.rule.transaction import RuleTransaction
from ontology_engine.engine.expression.engine import ExpressionEngine
from ontology_engine.engine.rule.operators.base import OperatorRegistry

logger = logging.getLogger(__name__)


class LayerExecutionError(Exception):
    """Raised when a layer fails with STOP_LAYER strategy."""
    def __init__(self, layer_index: int, errors: list[Exception]):
        self.layer_index = layer_index
        self.errors = errors
        super().__init__(f"Layer {layer_index} failed with {len(errors)} error(s)")


class ExecutionAbortedError(Exception):
    """Raised when ABORT_ALL strategy is triggered."""
    pass


@dataclass
class ExecutionResult:
    """Result of DAG execution."""
    results: dict[str, StepResult]
    context: ExecutionContext


from dataclasses import dataclass, field


class DAGExecutor:
    """Executes rules using DAG topology with parallel layer execution."""

    def __init__(
        self,
        operator_registry: OperatorRegistry,
        expression_engine: ExpressionEngine,
        max_concurrency: int = 8,
    ):
        self.operators = operator_registry
        self.expr_engine = expression_engine
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def execute(
        self,
        dag: ExecutionDAG,
        context: ExecutionContext,
        error_strategy: ErrorStrategy = ErrorStrategy.STOP_LAYER,
    ) -> ExecutionResult:
        """Execute DAG with topological ordering and parallel layer execution.

        Args:
            dag: ExecutionDAG from DAGBuilder
            context: ExecutionContext with entity data
            error_strategy: How to handle step failures

        Returns:
            ExecutionResult with all step results and final context
        """
        results: dict[str, StepResult] = {}
        tx = RuleTransaction(context)

        for layer in dag.layers:
            # Snapshot before layer execution
            layer_snapshot = tx.snapshot()

            # Execute layer nodes in parallel
            tasks = [
                self._execute_with_semaphore(node, context)
                for node in layer.nodes
            ]
            layer_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process layer results
            failed = []
            for step_id, result in zip(
                [n.step_id for n in layer.nodes],
                layer_results
            ):
                if isinstance(result, Exception):
                    failed.append(result)
                    results[step_id] = StepResult(
                        step_id=step_id,
                        error=str(result)
                    )
                else:
                    results[step_id] = result
                    if not result.skipped and not result.rejected:
                        context.update(step_id, result.output)

            # Handle failures
            if failed:
                if error_strategy == ErrorStrategy.STOP_LAYER:
                    tx.restore(layer_snapshot)
                    raise LayerExecutionError(layer.index, failed)
                elif error_strategy == ErrorStrategy.CONTINUE:
                    logger.warning(f"Layer {layer.index} had {len(failed)} failures, continuing")
                elif error_strategy == ErrorStrategy.ABORT_ALL:
                    tx.restore(layer_snapshot)
                    raise ExecutionAbortedError(f"Execution aborted at layer {layer.index}")

            tx.commit()

        return ExecutionResult(results=results, context=context)

    async def _execute_with_semaphore(
        self, node: DAGNode, context: ExecutionContext
    ) -> StepResult:
        async with self.semaphore:
            return await self._execute_step(node, context)

    async def _execute_step(
        self, node: DAGNode, context: ExecutionContext
    ) -> StepResult:
        """Execute a single step."""
        step = node.step

        # Evaluate condition
        condition_met = True
        if step.when and step.when.expression:
            eval_dict = {**context.entity_data, **context.computed_metrics}
            condition_met = self.expr_engine.evaluate(
                step.when.expression, eval_dict
            )

        if not condition_met:
            if step.else_ and step.else_.operator:
                # Execute else action
                return await self._execute_action(step.else_, context, step.id)
            return StepResult(step_id=step.id, skipped=True)

        return await self._execute_action(step.then, context, step.id)

    async def _execute_action(
        self, action: ActionClause, context: ExecutionContext, step_id: str
    ) -> StepResult:
        """Execute an action clause."""
        if not action.operator:
            return StepResult(step_id=step_id, output={})

        try:
            operator = self.operators.get(action.operator)
        except KeyError:
            return StepResult(
                step_id=step_id,
                error=f"Unknown operator: {action.operator}"
            )

        # Build inputs from context
        inputs = {**action.params}
        config = {}
        
        # Execute operator
        try:
            result = await operator.execute(inputs, config, context)
            return StepResult(step_id=step_id, output=result)
        except Exception as e:
            return StepResult(step_id=step_id, error=str(e))


# Add flags/categories to ExecutionContext if not present
def _ensure_context_fields(context: ExecutionContext):
    if not hasattr(context, 'flags'):
        context.flags = {}
    if not hasattr(context, 'categories'):
        context.categories = {}
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/unit/engine/rule/test_dag_executor.py -v
```
Expected: PASS (or FAIL with import errors to fix)

**Step 6: Commit**

```bash
git add ontology_engine/engine/rule/dag_executor.py ontology_engine/engine/rule/models.py tests/unit/engine/rule/test_dag_executor.py
git commit -m "feat(rule): implement DAGExecutor with parallel layer execution"
```

---

## Task 5: PipelineStateManager 实现

**Files:**
- Create: `ontology_engine/engine/rule/pipeline_state.py`
- Modify: `ontology_engine/storage/sqlite/store.py` (add pipeline tables)
- Test: `tests/unit/engine/rule/test_pipeline_state.py`

**Step 1: Write the failing test**

```python
# tests/unit/engine/rule/test_pipeline_state.py
import pytest
import uuid
from ontology_engine.engine.rule.pipeline_state import (
    PipelineStateManager, PipelineRun, ExecutionStepSnapshot,
    PipelineStatus, StepStatus
)

@pytest.mark.asyncio
async def test_create_pipeline_run():
    """Should create a new pipeline run with PENDING status."""
    manager = PipelineStateManager(storage=mock_storage)
    
    run = await manager.create_run(
        rule_logic_name="credit_assessment",
        rule_definition_name="rule_def_001",
        entity_id="E1",
        dimension="risk",
        run_config={"version": "1.0"},
    )
    
    assert run.rule_logic_name == "credit_assessment"
    assert run.status == PipelineStatus.PENDING
    assert run.entity_id == "E1"

@pytest.mark.asyncio
async def test_complete_pipeline_run():
    """Should transition run to COMPLETED status."""
    manager = PipelineStateManager(storage=mock_storage)
    
    run = await manager.create_run(...)
    await manager.start_run(run.id)
    
    await manager.complete_run(run.id)
    
    updated = await manager.get_run(run.id)
    assert updated.status == PipelineStatus.COMPLETED
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/engine/rule/test_pipeline_state.py -v
```
Expected: FAIL — `No module named 'ontology_engine.engine.rule.pipeline_state'`

**Step 3: Implement PipelineStateManager**

```python
# ontology_engine/engine/rule/pipeline_state.py
"""Pipeline state persistence for DAG execution."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

# Pipeline and Step status enums
class PipelineStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class StepStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass
class PipelineRun:
    """Represents a single execution of a rule logic."""
    id: str
    rule_logic_name: str
    rule_definition_name: str
    entity_id: str
    dimension: str
    status: PipelineStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    run_config: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    source_pipeline: str = "rule_engine"
    source_user: str | None = None
    source_content_hash: str | None = None
    supersedes: str | None = None


@dataclass
class ExecutionStepSnapshot:
    """Snapshot of a single step execution."""
    id: str
    pipeline_run_id: str
    step_id: str
    step_name: str
    status: StepStatus
    started_at: str | None = None
    completed_at: str | None = None
    condition_met: bool | None = None
    action_type: str | None = None
    operator_name: str | None = None
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    output_snapshot: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    skip_reason: str | None = None
    dag_layer: int = 0
    depends_on: list[str] = field(default_factory=list)
    trace_to: list[str] | None = None


class PipelineStateManager:
    """Manages pipeline run and step snapshot persistence."""

    def __init__(self, storage):
        self.storage = storage

    async def create_run(
        self,
        rule_logic_name: str,
        rule_definition_name: str,
        entity_id: str,
        dimension: str,
        run_config: dict[str, Any],
    ) -> PipelineRun:
        """Create a new pipeline run."""
        run_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        run = PipelineRun(
            id=run_id,
            rule_logic_name=rule_logic_name,
            rule_definition_name=rule_definition_name,
            entity_id=entity_id,
            dimension=dimension,
            status=PipelineStatus.PENDING,
            created_at=now,
            run_config=run_config,
        )
        
        # Persist to SQLite
        await self._save_pipeline_run(run)
        return run

    async def start_run(self, run_id: str) -> None:
        """Transition run to RUNNING status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.storage.execute(
            "UPDATE pipeline_runs SET status = ?, started_at = ? WHERE id = ?",
            [PipelineStatus.RUNNING.value, now, run_id]
        )

    async def complete_run(self, run_id: str) -> None:
        """Transition run to COMPLETED status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.storage.execute(
            "UPDATE pipeline_runs SET status = ?, completed_at = ? WHERE id = ?",
            [PipelineStatus.COMPLETED.value, now, run_id]
        )

    async def fail_run(self, run_id: str, error: str) -> None:
        """Transition run to FAILED status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.storage.execute(
            "UPDATE pipeline_runs SET status = ?, completed_at = ?, error_message = ? WHERE id = ?",
            [PipelineStatus.FAILED.value, now, error, run_id]
        )

    async def create_step_snapshot(
        self,
        run_id: str,
        step_id: str,
        step_name: str,
        dag_layer: int,
        depends_on: list[str],
    ) -> ExecutionStepSnapshot:
        """Create a new step snapshot."""
        snapshot_id = str(uuid4())
        
        snapshot = ExecutionStepSnapshot(
            id=snapshot_id,
            pipeline_run_id=run_id,
            step_id=step_id,
            step_name=step_name,
            status=StepStatus.PENDING,
            dag_layer=dag_layer,
            depends_on=depends_on,
        )
        
        await self._save_step_snapshot(snapshot)
        return snapshot

    async def start_step(self, snapshot_id: str, input_snapshot: dict[str, Any]) -> None:
        """Transition step to RUNNING status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.storage.execute(
            "UPDATE execution_step_snapshots SET status = ?, started_at = ?, input_snapshot = ? WHERE id = ?",
            [StepStatus.RUNNING.value, now, json.dumps(input_snapshot), snapshot_id]
        )

    async def complete_step(
        self,
        snapshot_id: str,
        output_snapshot: dict[str, Any],
        condition_met: bool,
        action_type: str | None = None,
        operator_name: str | None = None,
    ) -> None:
        """Transition step to COMPLETED status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.storage.execute(
            """UPDATE execution_step_snapshots 
               SET status = ?, completed_at = ?, output_snapshot = ?, 
                   condition_met = ?, action_type = ?, operator_name = ?
               WHERE id = ?""",
            [StepStatus.COMPLETED.value, now, json.dumps(output_snapshot),
             condition_met, action_type, operator_name, snapshot_id]
        )

    async def skip_step(self, snapshot_id: str, reason: str) -> None:
        """Transition step to SKIPPED status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.storage.execute(
            "UPDATE execution_step_snapshots SET status = ?, completed_at = ?, skip_reason = ? WHERE id = ?",
            [StepStatus.SKIPPED.value, now, reason, snapshot_id]
        )

    async def get_run(self, run_id: str) -> PipelineRun | None:
        """Get pipeline run by ID."""
        rows = await self.storage.query(
            "SELECT * FROM pipeline_runs WHERE id = ?",
            [run_id]
        )
        if not rows:
            return None
        return self._row_to_pipeline_run(rows[0])

    async def get_latest_run(
        self,
        rule_logic_name: str,
        entity_id: str,
    ) -> PipelineRun | None:
        """Get latest pipeline run for rule logic and entity."""
        rows = await self.storage.query(
            """SELECT * FROM pipeline_runs 
               WHERE rule_logic_name = ? AND entity_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            [rule_logic_name, entity_id]
        )
        if not rows:
            return None
        return self._row_to_pipeline_run(rows[0])

    async def get_step_snapshots(self, run_id: str) -> list[ExecutionStepSnapshot]:
        """Get all step snapshots for a pipeline run."""
        rows = await self.storage.query(
            "SELECT * FROM execution_step_snapshots WHERE pipeline_run_id = ? ORDER BY dag_layer, id",
            [run_id]
        )
        return [self._row_to_step_snapshot(r) for r in rows]

    async def get_completed_step_ids(self, run_id: str) -> list[str]:
        """Get IDs of completed steps for checkpoint restart."""
        rows = await self.storage.query(
            """SELECT step_id FROM execution_step_snapshots 
               WHERE pipeline_run_id = ? AND status = ?""",
            [run_id, StepStatus.COMPLETED.value]
        )
        return [r["step_id"] for r in rows]

    # Internal helpers
    async def _save_pipeline_run(self, run: PipelineRun) -> None:
        await self.storage.execute(
            """INSERT INTO pipeline_runs 
               (id, rule_logic_name, rule_definition_name, entity_id, dimension, 
                status, created_at, run_config, source_pipeline)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [run.id, run.rule_logic_name, run.rule_definition_name, run.entity_id,
             run.dimension, run.status.value, run.created_at, json.dumps(run.run_config),
             run.source_pipeline]
        )

    async def _save_step_snapshot(self, snapshot: ExecutionStepSnapshot) -> None:
        await self.storage.execute(
            """INSERT INTO execution_step_snapshots
               (id, pipeline_run_id, step_id, step_name, status, dag_layer, depends_on)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [snapshot.id, snapshot.pipeline_run_id, snapshot.step_id, snapshot.step_name,
             snapshot.status.value, snapshot.dag_layer, json.dumps(snapshot.depends_on)]
        )

    def _row_to_pipeline_run(self, row: dict) -> PipelineRun:
        return PipelineRun(
            id=row["id"],
            rule_logic_name=row["rule_logic_name"],
            rule_definition_name=row["rule_definition_name"],
            entity_id=row["entity_id"],
            dimension=row["dimension"],
            status=PipelineStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            run_config=json.loads(row.get("run_config", "{}")),
            error_message=row.get("error_message"),
            source_pipeline=row.get("source_pipeline", "rule_engine"),
        )

    def _row_to_step_snapshot(self, row: dict) -> ExecutionStepSnapshot:
        return ExecutionStepSnapshot(
            id=row["id"],
            pipeline_run_id=row["pipeline_run_id"],
            step_id=row["step_id"],
            step_name=row["step_name"],
            status=StepStatus(row["status"]),
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            condition_met=row.get("condition_met"),
            action_type=row.get("action_type"),
            operator_name=row.get("operator_name"),
            input_snapshot=json.loads(row.get("input_snapshot", "{}")),
            output_snapshot=json.loads(row.get("output_snapshot", "{}")),
            error_message=row.get("error_message"),
            skip_reason=row.get("skip_reason"),
            dag_layer=row.get("dag_layer", 0),
            depends_on=json.loads(row.get("depends_on", "[]")),
        )


import json
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/engine/rule/test_pipeline_state.py -v
```
Expected: PASS or FAIL with storage interface adjustments

**Step 5: Commit**

```bash
git add ontology_engine/engine/rule/pipeline_state.py tests/unit/engine/rule/test_pipeline_state.py
git commit -m "feat(rule): implement PipelineStateManager for execution persistence"
```

---

## Task 6: 更新 RuleExecutor 以支持 DAG 执行

**Files:**
- Modify: `ontology_engine/engine/rule/executor.py`
- Test: `tests/unit/engine/rule/test_executor.py`

**Step 1: Review current executor**

```python
# Current executor.py uses priority-based sorting (line 424):
# rules = sorted(rules, key=lambda r: -r.priority)
```

**Step 2: Write the failing test**

```python
# tests/unit/engine/rule/test_executor.py
@pytest.mark.asyncio
async def test_execute_rule_with_dag_falls_back_to_priority():
    """When no depends_on, should fall back to priority-based ordering."""
    # This test ensures backward compatibility
    pass
```

**Step 3: Modify RuleExecutor**

```python
# Add to RuleExecutor class in executor.py

async def execute_rule_dag(
    self,
    rule_group: RuleGroupDefinition,
    steps: list[RuleStep],
    context: ExecutionContext,
) -> AnalysisResult:
    """Execute rules using DAG topology (new method).
    
    Falls back to priority-based execution if no depends_on declarations exist.
    """
    if not steps:
        return AnalysisResult(
            entity_id=context.entity_id,
            dimension=context.dimension,
            rule_results=[],
            computed_metrics=context.computed_metrics,
            alerts=context.alerts,
        )
    
    # Check if any step has dependencies
    has_dependencies = any(len(step.depends_on) > 0 for step in steps)
    
    if has_dependencies:
        # Use DAG execution
        builder = DAGBuilder()
        dag = builder.build(steps)
        
        executor = DAGExecutor(
            operator_registry=OperatorRegistry,
            expression_engine=self.evaluator,
        )
        
        result = await executor.execute(dag, context)
        
        # Convert StepResults to RuleResults
        rule_results = []
        for step in steps:
            step_result = result.results.get(step.id)
            if step_result:
                rule_results.append(RuleResult(
                    rule_id=step.id,
                    rule_name=step.name,
                    passed=not step_result.skipped and not step_result.rejected,
                    output=step_result.output or {},
                    error=step_result.error,
                ))
        
        return AnalysisResult(
            entity_id=context.entity_id,
            dimension=context.dimension,
            rule_results=rule_results,
            computed_metrics=context.computed_metrics,
            alerts=context.alerts,
            decision=context.computed_metrics.get("final_decision"),
            decision_reasoning=context.computed_metrics.get("decision_reasoning"),
        )
    else:
        # Fall back to legacy priority-based execution
        return await self._execute_with_priority(steps, context)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/engine/rule/test_executor.py -v
```

**Step 5: Commit**

```bash
git add ontology_engine/engine/rule/executor.py tests/unit/engine/rule/test_executor.py
git commit -m "feat(rule): add execute_rule_dag method with DAG execution support"
```

---

## Task 7: SimulationService 升级 — 支持 DAG 模拟

**Files:**
- Modify: `ontology_engine/services/simulation_service.py`
- Test: `tests/unit/services/test_simulation_service.py`

**Step 1: Write the failing test**

```python
# tests/unit/services/test_simulation_service.py
@pytest.mark.asyncio
async def test_simulate_rule_group_with_dag():
    """Simulation should use DAG execution when steps have depends_on."""
    # Get rule group with steps
    # Run simulation
    # Verify DAG execution was used
```

**Step 2: Modify SimulationService**

Update `simulate_rule_group` method to use new `execute_rule_dag` method.

**Step 3: Commit**

---

## Task 8: API 端点增强 — 支持 DAG 可视化

**Files:**
- Modify: `ontology_engine/api/routes/rules.py`
- Create: `ontology_engine/engine/rule/dag_visualizer.py`

**Step 1: Add endpoint for DAG visualization**

```python
@router.get("/rule-groups/{name}/dag")
async def get_rule_group_dag(
    name: str,
    schema_id: str | None = Query(None),
    service: RuleService = Depends(get_rule_service),
):
    """Get DAG structure for a rule group."""
    rule_group = await service.get_rule_group(name, schema_id=schema_id)
    if rule_group is None:
        return error_response(code="NOT_FOUND", message=f"Rule group '{name}' not found")
    
    steps = await service.list_rule_steps(name, schema_id=schema_id)
    
    builder = DAGBuilder()
    dag = builder.build(steps)
    
    # Convert to visualization format
    layers = []
    for layer in dag.layers:
        layers.append({
            "index": layer.index,
            "steps": [
                {
                    "id": node.step_id,
                    "name": node.step.name,
                    "depends_on": node.step.depends_on,
                    "in_degree": node.in_degree,
                    "dependents": node.dependents,
                }
                for node in layer.nodes
            ]
        })
    
    return success_response(data={
        "rule_group_name": name,
        "total_steps": len(steps),
        "total_layers": len(dag.layers),
        "layers": layers,
    })
```

**Step 2: Commit**

---

## Task 9: 集成测试 — 端到端 DAG 执行

**Files:**
- Create: `tests/integration/test_rule_dag_execution.py`

**Step 1: Write integration test**

```python
# tests/integration/test_rule_dag_execution.py
import pytest
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.dag_executor import DAGExecutor
from ontology_engine.engine.rule.models import (
    ExecutionContext, RuleStep, ConditionClause, ActionClause
)
from ontology_engine.engine.rule.operators.base import OperatorRegistry

@pytest.mark.asyncio
async def test_end_to_end_dag_execution():
    """Test complete DAG execution flow."""
    # Register operators
    # Create test steps with depends_on
    # Build DAG
    # Execute
    # Verify results
```

**Step 2: Run integration test**

```bash
pytest tests/integration/test_rule_dag_execution.py -v
```

**Step 3: Commit**

---

## Task 10: 文档更新

**Files:**
- Modify: `docs/02-design/rule-engine/04-rule-engine-design.md`
- Create: `docs/02-design/rule-engine/dag-execution-status.md`

Update to reflect implementation status.

---

## 实施顺序

```
1. Task 1: RuleStep 模型扩展 (depends_on 字段)
   ↓
2. Task 2: DAGBuilder 实现
   ↓
3. Task 3: RuleTransaction (快照回滚)
   ↓
4. Task 4: DAGExecutor 实现
   ↓
5. Task 5: PipelineStateManager (可与 Task 4 并行)
   ↓
6. Task 6: RuleExecutor 升级 (调用 DAGExecutor)
   ↓
7. Task 7: SimulationService 升级
   ↓
8. Task 8: API 端点增强
   ↓
9. Task 9: 集成测试
   ↓
10. Task 10: 文档更新
```

---

## 讨论点确认后更新

完成讨论后，在此处记录决策：

1. **跨规则组依赖格式**: `[待确认]`
2. **回滚粒度**: `[待确认]`
3. **模拟 vs 执行**: `[待确认]`
4. **推理边存储**: `[待确认]`

---

**Plan complete.**
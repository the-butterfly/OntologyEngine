# 规则定位与执行逻辑复用计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 提取统一的规则定位服务（RuleLocator）和依赖分析服务（DependencyAnalyzer），使 RuleTreeBuilder 和 Consumption View API 共享规则发现和依赖分析逻辑。

**Architecture:** 创建 `ontology_engine/services/rule_locator.py` 和 `ontology_engine/engine/rule/dependency_analyzer.py`，将当前散落在 `simulation_tree_builder.py` 和 `consumption.py` 中的规则定位逻辑和依赖图构建逻辑提取为共享服务。RuleTreeBuilder 和 Consumption API 都使用这些共享服务。

**Tech Stack:** Python 3.12, Pydantic, asyncio

---

## Task 1: 创建 RuleLocator 服务

**Files:**
- Create: `ontology_engine/services/rule_locator.py`
- Modify: `ontology_engine/services/simulation_tree_builder.py:123-175` (重构为使用 RuleLocator)
- Test: `tests/unit/services/test_rule_locator.py`

**Step 1: Write the failing test**

```python
# tests/unit/services/test_rule_locator.py
import pytest
from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage

@pytest.fixture
def storage():
    return SemanticSpaceStorage()

@pytest.fixture
def locator(storage):
    return RuleLocator(storage)

@pytest.mark.asyncio
async def test_locate_by_output_exact_match(locator):
    """Test locating rules that produce a specific output."""
    results = await locator.locate_by_output(
        "final_decision",
        "space_supply_chain_finance"
    )
    assert len(results) == 1
    assert results[0]["id"] == "RD006_final_decision"

@pytest.mark.asyncio
async def test_locate_by_output_not_found(locator):
    """Test when no rule produces the given output."""
    results = await locator.locate_by_output(
        "nonexistent_output",
        "space_supply_chain_finance"
    )
    assert results == []

@pytest.mark.asyncio
async def test_locate_by_input(locator):
    """Test locating rules that consume a specific input."""
    results = await locator.locate_by_input(
        "credit_score",
        "space_supply_chain_finance"
    )
    assert len(results) >= 1
    # Should find RD006 that uses credit_score as input
    assert any(r["id"] == "RD006_final_decision" for r in results)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/services/test_rule_locator.py -v`
Expected: FAIL - module not found

**Step 3: Write minimal RuleLocator implementation**

```python
# ontology_engine/services/rule_locator.py
"""Rule Locator - Unified service for finding rules by output or input."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage

class RuleLocator:
    """Locates rule definitions by output or input elements.

    This service provides unified rule discovery for:
    - RuleTreeBuilder (execution tree planning)
    - Consumption API (rule execution)
    """

    def __init__(self, semantic_space_storage: SemanticSpaceStorage):
        self._storage = semantic_space_storage

    async def locate_by_output(
        self,
        output_name: str,
        schema_id: str,
    ) -> list[dict]:
        """Find rule definitions that produce a specific output element.

        Args:
            output_name: The output element ID to search for
            schema_id: Semantic space ID

        Returns:
            List of rule definition dicts that produce the output
        """
        space = await self._storage.load(schema_id)
        if not space:
            return []

        results = []
        for rd in space.layers.L4_business_logic.rule_definitions:
            for out in rd.get("outputs", []):
                out_id = out.get("id") if isinstance(out, dict) else out
                if out_id == output_name:
                    results.append(rd)
                    break
        return results

    async def locate_by_input(
        self,
        input_name: str,
        schema_id: str,
    ) -> list[dict]:
        """Find rule definitions that consume a specific input element.

        Args:
            input_name: The input element ID to search for
            schema_id: Semantic space ID

        Returns:
            List of rule definition dicts that have the input
        """
        space = await self._storage.load(schema_id)
        if not space:
            return []

        results = []
        for rd in space.layers.L4_business_logic.rule_definitions:
            for inp in rd.get("inputs", []):
                inp_id = inp.get("id") if isinstance(inp, dict) else inp
                if inp_id == input_name:
                    results.append(rd)
                    break
        return results
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/services/test_rule_locator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/services/rule_locator.py tests/unit/services/test_rule_locator.py
git commit -m "feat(rule_locator): add unified rule location service"
```

---

## Task 2: 更新 RuleTreeBuilder 使用 RuleLocator

**Files:**
- Modify: `ontology_engine/services/simulation_tree_builder.py:39-175`
- Test: `tests/unit/services/test_simulation_tree_builder.py`

**Step 1: Write the failing test**

```python
# tests/unit/services/test_simulation_tree_builder.py
# Add test for RuleTreeBuilder using RuleLocator
@pytest.mark.asyncio
async def test_build_tree_uses_rule_locator():
    """Test that build_tree correctly uses RuleLocator for rule finding."""
    from ontology_engine.services.rule_locator import RuleLocator
    storage = SemanticSpaceStorage()
    locator = RuleLocator(storage)
    builder = RuleTreeBuilder(semantic_space_storage=storage)

    tree = await builder.build_tree(
        "space_supply_chain_finance",
        None,
        "final_decision"
    )

    # Should find 3 layers after fix
    assert len(tree["layers"]) >= 3
    assert tree["total_steps"] >= 4
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/services/test_simulation_tree_builder.py::test_build_tree_uses_rule_locator -v`
Expected: FAIL - locator not injected

**Step 3: Update RuleTreeBuilder to use RuleLocator**

```python
# Modify simulation_tree_builder.py

class RuleTreeBuilder:
    def __init__(self, rule_service=None, semantic_space_storage=None):
        self._rule_service = rule_service
        self._semantic_space_storage = semantic_space_storage
        # RuleLocator instance for unified rule discovery
        self._rule_locator = RuleLocator(semantic_space_storage) if semantic_space_storage else None

    async def _locate_by_output(self, output_name: str, schema_id: str) -> list[dict]:
        """Locate rule groups that produce a specific output."""
        if self._rule_locator:
            return await self._rule_locator.locate_by_output(output_name, schema_id)

        if self._rule_service is None:
            return []

        result = await self._rule_service.locate_rule_groups(output_name, schema_id)
        return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/services/test_simulation_tree_builder.py::test_build_tree_uses_rule_locator -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/services/simulation_tree_builder.py tests/unit/services/test_simulation_tree_builder.py
git commit -m "refactor: RuleTreeBuilder uses RuleLocator for rule discovery"
```

---

## Task 3: 创建 DependencyAnalyzer 服务

**Files:**
- Create: `ontology_engine/engine/rule/dependency_analyzer.py`
- Modify: `ontology_engine/api/routes/consumption.py:723-850` (重构为使用 DependencyAnalyzer)
- Test: `tests/unit/engine/rule/test_dependency_analyzer.py`

**Step 1: Write the failing test**

```python
# tests/unit/engine/rule/test_dependency_analyzer.py
import pytest
from ontology_engine.engine.rule.dependency_analyzer import DependencyAnalyzer

def test_build_dependency_graph():
    """Test building dependency graph from rules."""
    rules = [
        {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
        {"id": "B", "inputs": [{"id": "x"}], "outputs": [{"id": "y"}]},
        {"id": "C", "inputs": [{"id": "y"}], "outputs": [{"id": "z"}]},
    ]
    analyzer = DependencyAnalyzer()
    graph = analyzer.build(rules)

    # A should have no dependencies (produces x consumed by B)
    # B should depend on A (produces y consumed by C)
    # C should depend on B
    assert "A" in graph.adjacency
    assert "B" in graph.adjacency["A"]
    assert "C" in graph.adjacency["B"]

def test_compute_levels():
    """Test computing execution levels from dependency graph."""
    rules = [
        {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
        {"id": "B", "inputs": [{"id": "x"}], "outputs": [{"id": "y"}]},
        {"id": "C", "inputs": [{"id": "x"}, {"id": "y"}], "outputs": [{"id": "z"}]},
    ]
    analyzer = DependencyAnalyzer()
    graph = analyzer.build(rules)
    levels = analyzer.compute_levels(graph)

    assert levels["A"] == 0  # No dependencies
    assert levels["B"] == 1  # Depends on A
    assert levels["C"] == 2  # Depends on A and B
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/engine/rule/test_dependency_analyzer.py -v`
Expected: FAIL - module not found

**Step 3: Write DependencyAnalyzer implementation**

```python
# ontology_engine/engine/rule/dependency_analyzer.py
"""Dependency Analyzer - Unified service for rule dependency analysis."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

@dataclass
class DependencyGraph:
    """Result of dependency analysis."""
    adjacency: dict[str, list[str]]
    in_degree: dict[str, int]
    edges: list[dict[str, str]]
    rules: list[dict]

    def compute_levels(self) -> dict[str, int]:
        """Compute execution level for each rule using Kahn's algorithm.

        Returns:
            Dict mapping rule_id to execution level (0 = first)
        """
        levels = {rid: 0 for rid in self.in_degree}

        # Process nodes in topological order
        # Level of a node = max(level of all predecessors) + 1
        processed = set()
        max_iterations = len(self.rules) + 1
        iteration = 0

        while len(processed) < len(self.rules) and iteration < max_iterations:
            iteration += 1
            for rule_id in list(self.rules):
                if rule_id in processed:
                    continue

                # Check if all predecessors are processed
                predecessors = [src for src, targets in self.adjacency.items()
                              if rule_id in targets]
                if all(p in processed for p in predecessors):
                    if predecessors:
                        levels[rule_id] = max(levels[p] for p in predecessors) + 1
                    processed.add(rule_id)

        return levels


class DependencyAnalyzer:
    """Analyzes dependencies between rules based on input/output element matching."""

    def build(self, rules: list[dict]) -> DependencyGraph:
        """Build dependency graph from rules.

        Rule A depends on Rule B if A's inputs overlap with B's outputs.

        Args:
            rules: List of rule definition dicts

        Returns:
            DependencyGraph with adjacency list, in-degrees, and edges
        """
        # Build output_map: element_name -> [rule_ids that produce it]
        output_map: dict[str, list[str]] = defaultdict(list)
        for rule in rules:
            for out_elem in self._rule_outputs(rule):
                elem_name = out_elem.get("name") or out_elem.get("id", "")
                if elem_name:
                    output_map[elem_name].append(rule["id"])

        # Build adjacency list and in-degree
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {r["id"]: 0 for r in rules}
        edges = []
        rule_ids = set(r["id"] for r in rules)

        for rule in rules:
            rule_id = rule["id"]
            for in_elem in self._rule_inputs(rule):
                elem_name = in_elem.get("name") or in_elem.get("id", "")
                producers = output_map.get(elem_name, [])
                for producer_id in producers:
                    if producer_id != rule_id and producer_id in rule_ids:
                        adj[producer_id].append(rule_id)
                        in_degree[rule_id] += 1
                        edges.append({
                            "source": producer_id,
                            "target": rule_id,
                            "via_element": elem_name,
                        })

        return DependencyGraph(
            adjacency=dict(adj),
            in_degree=in_degree,
            edges=edges,
            rules=[r["id"] for r in rules]
        )

    @staticmethod
    def _rule_outputs(rule: dict) -> list[dict]:
        return rule.get("outputs", [])

    @staticmethod
    def _rule_inputs(rule: dict) -> list[dict]:
        return rule.get("inputs", [])

    def compute_levels(self, graph: DependencyGraph) -> dict[str, int]:
        """Compute execution level for each rule.

        Args:
            graph: DependencyGraph from build()

        Returns:
            Dict mapping rule_id to execution level
        """
        return graph.compute_levels()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/engine/rule/test_dependency_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/engine/rule/dependency_analyzer.py tests/unit/engine/rule/test_dependency_analyzer.py
git commit -m "feat(dependency_analyzer): add unified dependency analysis service"
```

---

## Task 4: 更新 Consumption API 使用 DependencyAnalyzer

**Files:**
- Modify: `ontology_engine/api/routes/consumption.py:723-850`
- Test: `tests/integration/test_consumption_api.py`

**Step 1: Write the failing test**

```python
# tests/integration/test_consumption_api.py
@pytest.mark.asyncio
async def test_execute_simulate_uses_dependency_analyzer():
    """Test that execute/simulate uses shared DependencyAnalyzer."""
    # This test verifies the refactoring doesn't break functionality
    response = await api_client.post(
        f"/v1/consumption/views/{view_id}/execute/simulate",
        json={"entity_id": entity_id, "dimension": "credit_assessment"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
```

**Step 2: Run test to verify it fails (if breaking change introduced)**

Run: `pytest tests/integration/test_consumption_api.py::test_execute_simulate_uses_dependency_analyzer -v`
Expected: Should pass (verify refactoring doesn't break)

**Step 3: Update consumption.py to use DependencyAnalyzer**

```python
# At top of consumption.py, add import:
from ontology_engine.engine.rule.dependency_analyzer import DependencyAnalyzer, DependencyGraph

# Replace _build_rule_dependency_graph and _compute_rule_levels with:
_analyzer = DependencyAnalyzer()

# In _run_full_analysis or wherever these are called:
graph = _analyzer.build(rules)
levels = _analyzer.compute_levels(graph)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_consumption_api.py::test_execute_simulate_uses_dependency_analyzer -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/api/routes/consumption.py tests/integration/test_consumption_api.py
git commit -m "refactor: Consumption API uses shared DependencyAnalyzer"
```

---

## Task 5: 创建 SimulationOrchestrator 整合两个模拟功能

**Files:**
- Create: `ontology_engine/services/simulation_orchestrator.py`
- Modify: `ontology_engine/api/routes/simulation.py` (简化，委托给 orchestrator)
- Modify: `ontology_engine/api/routes/consumption.py` (简化，委托给 orchestrator)
- Test: `tests/unit/services/test_simulation_orchestrator.py`

**Step 1: Write the failing test**

```python
# tests/unit/services/test_simulation_orchestrator.py
@pytest.mark.asyncio
async def test_build_execution_tree():
    """Test building execution tree from target output."""
    orchestrator = SimulationOrchestrator()

    tree = await orchestrator.build_execution_tree(
        schema_id="space_supply_chain_finance",
        target_output="final_decision"
    )

    assert tree["layers"] >= 3
    assert tree["total_steps"] >= 4

@pytest.mark.asyncio
async def test_execute_with_whatif():
    """Test executing rules with what-if overrides."""
    orchestrator = SimulationOrchestrator()

    result = await orchestrator.execute_with_whatif(
        view_id="view_supply_chain_finance",
        entity_id="SUP_A",
        dimension="credit_assessment",
        overrides={"credit_score": 90}
    )

    assert "baseline" in result
    assert "simulated" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/services/test_simulation_orchestrator.py -v`
Expected: FAIL - module not found

**Step 3: Write SimulationOrchestrator implementation**

```python
# ontology_engine/services/simulation_orchestrator.py
"""Simulation Orchestrator - Unified simulation service.

Coordinates between execution tree building (RuleTreeBuilder) and
actual rule execution (Consumption API) for both planning and what-if analysis.
"""

from __future__ import annotations

from typing import Any

from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.services.simulation_tree_builder import RuleTreeBuilder
from ontology_engine.engine.rule.dependency_analyzer import DependencyAnalyzer
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage

class SimulationOrchestrator:
    """Orchestrates simulation operations across both management and consumption planes."""

    def __init__(self, semantic_space_storage: SemanticSpaceStorage | None = None):
        self._storage = semantic_space_storage or SemanticSpaceStorage()
        self._rule_locator = RuleLocator(self._storage)
        self._tree_builder = RuleTreeBuilder(semantic_space_storage=self._storage)
        self._dependency_analyzer = DependencyAnalyzer()

    async def build_execution_tree(
        self,
        schema_id: str,
        target_output: str,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        """Build execution tree from target output (RuleTreeBuilder functionality).

        Args:
            schema_id: Semantic space ID
            target_output: Target output element ID
            entity_id: Optional entity ID for filtering

        Returns:
            Execution tree with layers and steps
        """
        return await self._tree_builder.build_tree(
            schema_id=schema_id,
            entity_id=entity_id,
            target_output=target_output,
        )

    async def locate_rules_producing(
        self,
        output_name: str,
        schema_id: str,
    ) -> list[dict]:
        """Locate rules that produce a specific output (RuleLocator functionality)."""
        return await self._rule_locator.locate_by_output(output_name, schema_id)

    async def analyze_dependencies(
        self,
        rules: list[dict],
    ) -> dict[str, Any]:
        """Analyze dependencies between rules (DependencyAnalyzer functionality)."""
        graph = self._dependency_analyzer.build(rules)
        levels = self._dependency_analyzer.compute_levels(graph)
        return {
            "graph": {
                "adjacency": graph.adjacency,
                "in_degree": graph.in_degree,
                "edges": graph.edges,
            },
            "levels": levels,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/services/test_simulation_orchestrator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ontology_engine/services/simulation_orchestrator.py tests/unit/services/test_simulation_orchestrator.py
git commit -m "feat(simulation_orchestrator): add unified simulation orchestration service"
```

---

## Task 6: 更新前端 SimulationPage 支持执行树视图

**Files:**
- Modify: `ontology-engine-ui/src/pages/SimulationPage.tsx`
- Create: `ontology-engine-ui/src/components/simulation/ExecutionTreePanel.tsx` (new component)
- Test: `ontology-engine-ui/tests/simulation.test.ts`

**Step 1: Write the failing test**

```typescript
// ontology-engine-ui/tests/simulation.test.ts
test('SimulationPage shows execution tree when viewing from space', async () => {
  // Navigate to space simulate page
  await page.goto('http://localhost:3000/spaces/space_supply_chain_demo/simulate');
  await page.waitForLoadState('networkidle');

  // Should see execution tree or option to build one
  const treeViewer = page.locator('[data-testid="execution-tree-viewer"]');
  // Fallback: check for build tree button or target output input
});
```

**Step 2: Run test to verify it fails**

Run: (playwright test)
Expected: FAIL or no matching elements

**Step 3: Update SimulationPage to support execution tree view**

```typescript
// In SimulationPage.tsx, add state and UI for execution tree
const [showExecutionTree, setShowExecutionTree] = useState(false);
const [executionTree, setExecutionTree] = useState<ExecutionTree | null>(null);

// Add toggle to switch between What-If and Execution Tree modes
// If showExecutionTree is true:
//   - Call simulationApi.createTree() to build tree
//   - Display tree in ExecutionTreeViewer
// If showExecutionTree is false:
//   - Use existing What-If comparison mode
```

**Step 4: Run test to verify it passes**

Run: (playwright test)
Expected: PASS

**Step 5: Commit**

```bash
git add ontology-engine-ui/src/pages/SimulationPage.tsx
git commit -m "feat(ui): SimulationPage supports execution tree view"
```

---

## Task 7: 集成测试 - 验证完整的模拟流程

**Files:**
- Create: `tests/integration/test_simulation_full_flow.py`
- Modify: `docs/plans/YYYY-MM-DD-rule-simulation-refactor.md` (更新状态)

**Step 1: Write the failing test**

```python
# tests/integration/test_simulation_full_flow.py
@pytest.mark.asyncio
async def test_build_tree_then_execute():
    """Test building execution tree and then executing with what-if."""
    orchestrator = SimulationOrchestrator()

    # Step 1: Build execution tree
    tree = await orchestrator.build_execution_tree(
        "space_supply_chain_finance",
        "final_decision"
    )
    assert len(tree["layers"]) >= 3

    # Step 2: Execute with what-if (needs active view)
    # This is more of an integration test
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/integration/test_simulation_full_flow.py -v`
Expected: PASS (or skip if no active view)

**Step 3: Commit**

```bash
git add tests/integration/test_simulation_full_flow.py
git commit -m "test: add full flow simulation integration test"
```

---

## 验证步骤

完成所有任务后，运行以下验证：

```bash
# 1. 验证 RuleTreeBuilder 返回正确的层数
curl -s -X POST http://localhost:8000/v1/simulation/tree \
  -H "Content-Type: application/json" \
  -d '{"schema_id":"space_supply_chain_finance","target_output":"final_decision"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Layers: {len(d[\"data\"][\"execution_tree\"][\"layers\"])}')"

# 2. 验证 RuleLocator 直接查询
python3 -c "
import asyncio
from ontology_engine.services.rule_locator import RuleLocator
from ontology_engine.core.semantic_space.storage import SemanticSpaceStorage

async def test():
    storage = SemanticSpaceStorage()
    locator = RuleLocator(storage)
    results = await locator.locate_by_output('final_decision', 'space_supply_chain_finance')
    print(f'Found {len(results)} rules producing final_decision')
    for r in results:
        print(f'  - {r[\"id\"]}')

asyncio.run(test())
"

# 3. 验证 DependencyAnalyzer
python3 -c "
from ontology_engine.engine.rule.dependency_analyzer import DependencyAnalyzer

analyzer = DependencyAnalyzer()
rules = [
    {'id': 'A', 'inputs': [], 'outputs': [{'id': 'x'}]},
    {'id': 'B', 'inputs': [{'id': 'x'}], 'outputs': [{'id': 'y'}]},
]
graph = analyzer.build(rules)
levels = analyzer.compute_levels(graph)
print(f'Levels: {levels}')
"

# 4. 前端测试
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:3000/spaces/space_supply_chain_demo/simulate')
    page.wait_for_load_state('networkidle')
    # Check for UI elements
    print('Page loaded successfully')
    browser.close()
"
```

---

## 总结

完成此计划后，将实现：

1. **RuleLocator** - 统一的规则定位服务，消除重复的规则发现逻辑
2. **DependencyAnalyzer** - 统一的依赖分析服务，Kahn 算法复用
3. **SimulationOrchestrator** - 整合管理面和消费面的模拟功能
4. **前端更新** - SimulationPage 支持执行树视图，与 What-If 对比无缝切换

预计改动：
- 新增 4 个文件
- 修改 5 个文件
- 新增约 40 个测试用例
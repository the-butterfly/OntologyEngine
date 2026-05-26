# 前端-后端规则管理、仿真、执行功能 GAP 分析报告

> 日期: 2026-04-22 | **last_verified**: 2026-05-15
> 工具: Playwright + 手动代码审查
> **⚠️ 过时标记**: GAP 1（Simulation Tree 空 layers）和 GAP 2（Simulation 执行 NotImplementedError）部分修复。GAP 3（规则组数据分离：SQLite rule_groups 为空，L4 规则在 SemanticSpace）的根因是双存储体系断裂，仍未解决。新增问题：`GET /v1/spaces` 列表接口缺少 `domain`/`relation_count`/`rule_logic_count` 字段。详见 `docs-dev/review-reports/semantic-space-storage-integrity-review.md`

---

## 一、测试环境

| 组件 | 端口 | 状态 |
|------|------|------|
| 前端 (Vite) | localhost:3000 | 运行中 |
| 后端 (FastAPI) | localhost:8000 | 运行中 |

---

## 二、GAP 分析结果

### GAP 1: Simulation Tree 构建返回空 layers [严重]

**现象:**
```json
POST /v1/simulation/tree
{
  "schema_id": "space_supply_chain_finance",
  "target_output": "decision"
}
Response:
{
  "execution_tree": {
    "layers": [],
    "total_steps": 0,
    "rule_group_count": 0
  }
}
```

**根本原因:**
- `RuleTreeBuilder._filter_steps()` 方法是 TODO 占位实现，返回空列表 `[]`
- 文件: `ontology_engine/services/simulation_tree_builder.py:138-158`

**前端期望:**
- `ExecutionTree.layers[].steps: ExecutableStep[]` 需要包含完整的步骤信息
- 类型定义 (simulation.ts):
  ```typescript
  interface ExecutableStep {
    step_id: string;
    step_name: string;
    rule_group_name: string;
    rule_group_type: 'constraint' | 'inference' | 'alert' | 'decision';
    condition: Condition;
    action: { operator: string; params: Record<string, unknown>; };
    output_names: string[];
    depends_on: string[];
  }
  ```

**影响:**
- ExecutionTreeViewer 组件无法显示任何步骤节点
- 用户无法看到执行树的结构

---

### GAP 2: Simulation 执行未实现 [严重]

**现象:**
```python
# ontology_engine/api/routes/simulation.py:185-193
async def _run_simulation(session: SimulationSession) -> dict[str, Any]:
    raise NotImplementedError("Simulation execution requires DAGExecutor integration")
```

**根本原因:**
- `_run_simulation` 方法抛出 `NotImplementedError`
- DAGExecutor 尚未实现

**影响:**
- 用户可以构建执行树，但无法实际运行模拟
- SimulationPanel 的"运行模拟"按钮无法正常工作

---

### GAP 3: Rule Groups 数据分离 [中等]

**现象:**
- `/v1/rule-groups` 返回空列表
- 但 `/v1/spaces/space_2125bdaa/schema/L4/rules/definitions` 有 6 条规则定义

**根本原因:**
- 规则组 (rule_groups) 存储在 SQLite 的 `rule_groups` 表
- 规则定义 (L4 rule definitions) 存储在 SemanticSpace 中
- 两者数据不互通

**RuleService.list_rule_groups() 查询的是:**
```python
# ontology_engine/services/rule_service.py:133
rows = await self._storage.list_rule_groups(schema_id=schema_id, enabled=enabled)
```

**而 L4 规则定义存储在:**
```python
# ontology_engine/api/routes/management.py:741
space.layers.L4_business_logic.rule_definitions
```

**影响:**
- 前端通过 `/v1/rule-groups` API 看不到任何规则组
- 无法使用规则组的 CRUD 功能

---

### GAP 4: 前端 SimulationPanel 与后端 API 不匹配 [中等]

**前端 SimulationPanel 组件问题:**
1. `SimulationPanel.tsx:26` - `schemaId` 应该来自 prop，但组件内部用 `useState` 重新定义
2. 缺少错误边界 - API 调用失败时用户体验不佳
3. `updateInputs` 虽然使用了 `useCallback`，但依赖数组缺少 `sessionId`

**后端 Simulation API 问题:**
- `POST /simulation/tree` 返回格式与前端期望部分匹配
- 但缺少 `input_requirements` 字段

---

### GAP 5: 规则定位 (Rule Location) API 缺失 [中等]

**讨论点 #1 中提到的需求:**
> 规则组的 depends_on 格式用 "rule_group/step_id", 是一个可选项, 默认留空的话, 按照 输入/输出 要素被其他规则组的调用关系来自动管理依赖.

**当前状态:**
- `/v1/rule-groups/locate` 端点存在 (rules.py:621-653)
- 但 `RuleTreeBuilder._locate_by_output` 方法依赖 `RuleService.locate_rule_groups()`
- 该方法只在 rule_groups 表中查找，不查 SemanticSpace L4 层

---

## 三、待讨论的关键决策

### 1. 规则组 vs 规则定义 数据模型统一

**选项 A:** 将 L4 规则定义映射为规则组
- 优点: 复用 SemanticSpace 中的规则数据
- 缺点: 需要扩展 RuleTreeBuilder 来查询 L4 层

**选项 B:** 规则组和规则定义分离存储
- 优点: 职责清晰
- 缺点: 前端需要调用不同 API

### 2. Simulation 执行架构

**选项 A:** 在 SimulationService 中实现完整 DAG 执行
- 使用 `DAGBuilder` 构建执行图
- 使用 `SimulationService.simulate_dag()` 执行

**选项 B:** 引入独立的 DAGExecutor
- 优点: 分离关注点
- 缺点: 增加复杂度

### 3. 回滚粒度

**讨论点 #2:**
> 回滚粒度按照 DAG 层, 即报错节点前可以执行到的最后一层节点

需要确认:
- 错误处理策略是在 DAGExecutor 层还是 SimulationService 层?
- 是否需要实现快照机制?

---

## 四、修复优先级

| 优先级 | GAP | 修复方案 |
|--------|-----|----------|
| P0 | GAP 1 | 实现 `RuleTreeBuilder._filter_steps()` |
| P0 | GAP 2 | 实现 `_run_simulation` 或集成 DAGExecutor |
| P1 | GAP 3 | 统一规则组数据源或扩展 locate_rule_groups |
| P1 | GAP 4 | 修复 SimulationPanel 和 API 格式 |
| P2 | GAP 5 | 实现跨 SemanticSpace 的规则定位 |

---

## 五、截图证据

| 页面 | 截图路径 |
|------|----------|
| Spaces 列表 | /tmp/spaces_page.png |
| Simulation 页面 | /tmp/simulate_page.png |
| Rule Execution 页面 | /tmp/execute_page.png |
| Rules 列表 | /tmp/rules_page.png |
| Simulation Embed | /tmp/sim_embed_page.png |

---

## 六、Playwright 测试脚本

测试脚本: `/Volumes/Extension/Projects/CodeDev/OntologyEngine/frontend_test.py`

运行:
```bash
python3 frontend_test.py
```

---

## 七、相关文件索引

### 后端 - Simulation
- `ontology_engine/api/routes/simulation.py` - Simulation API 路由
- `ontology_engine/services/simulation_service.py` - SimulationService
- `ontology_engine/services/simulation_tree_builder.py` - RuleTreeBuilder
- `ontology_engine/services/simulation_session.py` - SessionManager

### 后端 - Rules
- `ontology_engine/services/rule_service.py` - RuleService
- `ontology_engine/api/routes/rules.py` - Rules API
- `ontology_engine/api/routes/management.py` - Management API (L4 层)

### 前端 - Simulation
- `ontology-engine-ui/src/api/simulation.ts` - API client
- `ontology-engine-ui/src/types/simulation.ts` - TypeScript 类型
- `ontology-engine-ui/src/components/simulation/SimulationPanel.tsx`
- `ontology-engine-ui/src/components/simulation/SimulationResultPanel.tsx`
- `ontology-engine-ui/src/components/simulation/ExecutionTreeViewer.tsx`
- `ontology-engine-ui/src/components/simulation/InputValuesForm.tsx`

### 前端 - Rules
- `ontology-engine-ui/src/api/ruleGroups.ts` - API client
- `ontology-engine-ui/src/types/rule.ts` - TypeScript 类型
- `ontology-engine-ui/src/pages/rules/` - 规则页面

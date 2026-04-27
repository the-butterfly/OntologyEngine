# 语义空间管理→模拟→执行 完整交互旅程 GAP 分析报告

> 日期: 2026-04-23
> 工具: Playwright journey_analysis.py
> 状态: 分析完成

---

## 一、测试环境

| 组件 | 端口 | URL | 状态 |
|------|------|-----|------|
| 前端 (Vite) | 3000 | http://localhost:3000 | 运行中 |
| 后端 (FastAPI) | 8000 | http://localhost:8000 | 运行中 |
| Vite 代理配置 | - | `/v1` → `localhost:8000` | ✓ 有效 |

---

## 二、完整旅程分析 (LEG-by-LEG)

### LEG 1: Space List Page (/spaces)

**目的**: 查看所有语义空间列表

**API 调用**:
```
GET /v1/spaces
Response: 200, 返回 8 个空间
```

**前端表现**:
- 页面加载 1 个 Space Card
- Card 显示正确

**结论**: ✓ 正常

---

### LEG 2: Space Schema Page (/spaces/{id}/schema)

**目的**: 查看语义空间的 L1-L4 层 Schema

**API 调用**:
```
GET /v1/spaces/space_supply_chain_finance/schema
GET /v1/spaces/space_supply_chain_finance/schema/L4/rules/definitions
GET /v1/spaces/space_supply_chain_finance/schema/L4/rules/logics
GET /v1/spaces/space_supply_chain_finance/versions
GET /v1/spaces/space_supply_chain_finance/schema/L1/fact-objects
```

**前端表现**:
- 4 个 Layer Tabs (L1, L2, L3, L4) 正确显示
- L1: 3 个元素, L2: 2 个, L3: 2 个, L4: 3 个

**结论**: ✓ 正常

---

### LEG 3: Space Rules Page (/spaces/{id}/rules)

**目的**: 查看和管理空间内的规则

**API 调用**:
```
GET /v1/spaces/space_supply_chain_finance/schema
GET /v1/spaces/space_supply_chain_finance/schema/L4/rules/definitions
GET /v1/spaces/space_supply_chain_finance/schema/L4/rules/logics
GET /v1/spaces/space_supply_chain_finance/versions
```

**前端表现**:
- Rule elements: 0 个 (❌ 问题)
- DAG button 可见: True
- Rule 引用: 15 个

**问题**:
- 虽然调用了 `/L4/rules/definitions` API 并获取了 6 条规则定义
- 但前端 `Rule elements: 0` 表示组件未正确渲染规则数据
- DAG button 可见但点击后无 DAG 可视化

**结论**: ⚠ 前端渲染问题 - API 有数据但组件未显示

---

### LEG 4: Space Simulate Page (/spaces/{id}/simulate)

**目的**: 在空间内执行模拟

**API 调用**:
```
49 个请求 (主要是 JS/CSS 加载和 API 调用)
```

**前端表现**:
- Simulation text elements: 5 个
- Entity selector 可见: True
- Target output input 可见: False (❌ 问题)

**问题**:
- 目标输出输入框未正确显示
- 模拟配置面板不完整

**结论**: ⚠ 前端组件缺失

---

### LEG 5: Simulation Embed Page (/simulation/embed?schemaId=...)

**目的**: 嵌入式模拟面板，可通过 URL 参数指定 schemaId

**API 调用**:
```
GET /v1/spaces/space_supply_chain_finance/schema (via proxy)
GET /v1/spaces/space_supply_chain_finance/schema/L4/rules/definitions (via proxy)
```

**前端表现**:
- Config card 可见: True ✓
- Build tree button 可见: True ✓
- Empty state 可见: True (❌ 预期行为，因为无数据)

**结论**: ✓ 正常 - 空白状态是正确的直到用户输入 target_output

---

### LEG 6: Build Execution Tree Action (关键)

**目的**: 用户输入 target_output="decision" 并触发构建执行树

**用户操作**:
1. 在 target output 输入框输入 "decision"
2. 点击 "构建执行树" 按钮

**API 调用**:
```
POST /v1/simulation/tree
Body: {"schema_id": "space_supply_chain_finance", "target_output": "decision"}
Response: 200
{
  "success": true,
  "data": {
    "session_id": "b34ae695-...",
    "execution_tree": {
      "layers": [],          ← ★ 空！
      "total_steps": 0,
      "rule_group_count": 0
    },
    "required_inputs": [],
    "current_inputs": {}
  }
}
```

**前端表现**:
- Empty state after build: False (表明有响应)
- Tree viewer elements: 0

**结论**: ⚠ 后端阻塞 - 返回空 layers

---

### LEG 7: Views/Consumption Page (/views)

**目的**: 查看消费视图列表

**API 调用**:
```
GET /v1/views
Response: 200
```

**前端表现**:
- View cards: 1 个

**结论**: ✓ 正常

---

### LEG 8: View Execute Page (/views/{id}/execute)

**目的**: 执行视图模拟

**API 调用**:
```
GET /views/view_supply_chain_finance/execute (前端路由，无 API 调用)
```

**前端表现**:
- Execute text elements: 0 (❌ 问题)
- Run button 可见: False (❌ 问题)

**问题**:
- 前端未调用后端 API
- 执行页面组件缺失

**结论**: ❌ 前端组件未实现或未连接 API

---

## 三、GAP 汇总

### GAP 分类

| GAP ID | 位置 | 严重度 | 描述 |
|--------|------|--------|------|
| GAP-FE3 | 前端 | P1 | Rules 页面有 Rule elements: 0 |
| GAP-FE4 | 前端 | P1 | Simulate 页面 Target output input 不可见 |
| GAP-FE8 | 前端 | P2 | View Execute 页面无 Run button |
| GAP-B1 | 后端 | P0 | simulation/tree 返回空 layers |
| GAP-B2 | 后端 | P1 | _locate_by_output 查询 SQLite 而非 SemanticSpace L4 |

---

### GAP 详细分析

#### GAP-B1: simulation/tree 返回空 layers [P0 - 阻塞]

**现象**:
```json
POST /v1/simulation/tree
{
  "schema_id": "space_supply_chain_finance",
  "target_output": "decision"
}

Response:
{
  "execution_tree": {
    "layers": [],      ← 永远是空的
    "total_steps": 0,
    "rule_group_count": 0
  }
}
```

**根因定位**:
```
simulation.py:create_simulation_tree()
  └→ RuleTreeBuilder.build_tree()
      └→ _locate_by_output() → 返回 RuleGroupDefinition[]
      └→ _filter_steps() → 返回 [] (TODO)
```

**关键代码**:
```python
# simulation_tree_builder.py:138-158
async def _filter_steps(
    self,
    groups: list[RuleGroupDefinition],
    entity_id: str | None,
) -> list[dict[str, Any]]:
    """Filter steps from rule groups by entity category."""
    # TODO: Implement actual step filtering by entity category
    return []  # ← 永远返回空列表
```

**影响**:
- 前端 ExecutionTreeViewer 无法显示任何步骤
- 用户无法看到执行树结构
- 整个模拟功能不可用

---

#### GAP-B2: _locate_by_output 查询错误数据源 [P1]

**现象**:
```python
# _locate_by_output 依赖 RuleService
async def _locate_by_output(self, output_name: str, schema_id: str):
    result = await self._rule_service.locate_rule_groups(output_name, schema_id)
    return result
```

**问题**:
- `RuleService.locate_rule_groups()` 查询 SQLite `rule_groups` 表
- SQLite 表为空 (从未写入过)
- 真正有数据的是 SemanticSpace L4 层

**数据模型断裂**:
| 数据模型 | 存储位置 | API 路径 | 状态 |
|---------|---------|---------|------|
| L4 规则定义 | SemanticSpace.layers.L4 | `/v1/spaces/{id}/schema/L4/rules/definitions` | ✓ 6 条 |
| RuleGroups | SQLite `rule_groups` 表 | `/v1/rule-groups` | ✗ 空 |

---

#### GAP-FE3: Rules 页面 Rule elements: 0 [P1]

**现象**: 前端检测到 0 个 rule 组件，但 API 返回了规则数据

**可能原因**:
1. 前端组件未正确解析 API 响应
2. 组件选择器错误
3. 数据映射问题

**需要检查**:
- RulesEmbedPage.tsx 如何处理 `/L4/rules/definitions` 响应
- RuleChainDAG 组件如何渲染

---

#### GAP-FE4: Simulate 页面 Target output input 不可见 [P1]

**现象**: Simulate 页面缺少目标输出输入框

**需要检查**:
- SimulationPanel 是否在 SimulatePage 中正确渲染
- Schema ID 传递是否正确

---

#### GAP-FE8: View Execute 页面 Run button 缺失 [P2]

**现象**:
- Execute text elements: 0
- Run button visible: False

**需要检查**:
- ViewExecutePage 组件是否实现
- API 调用是否连接

---

## 四、完整旅程 API 调用图

```
用户旅程                          API 调用                           前端状态
─────────────────────────────────────────────────────────────────────────────
/spaces                          GET /v1/spaces                     ✓ 显示空间列表
   │
   ▼
/spaces/{id}/schema              GET /v1/spaces/{id}/schema         ✓ 显示 L1-L4
   │                              GET /v1/spaces/{id}/schema/L4/...
   │
   ▼
/spaces/{id}/rules               GET /v1/spaces/{id}/schema/L4/...  ⚠ 0 rule elements
   │                              (API 有数据，前端未渲染)
   │
   ▼
/spaces/{id}/simulate            (49 个请求)                        ⚠ target input 缺失
   │
   ▼
/simulation/embed?schemaId=...   GET /v1/spaces/{id}/schema         ✓ 正确显示配置卡
   │
   ▼ 输入 "decision" + 点击构建
/simulation/embed               POST /v1/simulation/tree           ⚠ 返回空 layers
   │                              (返回 200 但数据为空)
   │
   ▼
/views                           GET /v1/views                     ✓ 显示视图列表
   │
   ▼
/views/{id}/execute             (无 API 调用)                      ❌ Run button 缺失
```

---

## 五、关键阻塞点

### 阻塞点 1: simulation/tree 返回空 layers [P0]

**影响范围**: 整个模拟功能

**阻塞原因**: `RuleTreeBuilder._filter_steps()` 是 TODO 占位实现

**修复优先级**: P0

---

### 阻塞点 2: RuleService.locate_rule_groups() 查询空表 [P1]

**影响范围**: 跨规则组依赖追踪

**阻塞原因**: 数据模型分离 - L4 规则在 SemanticSpace，RuleGroups 在 SQLite

**修复优先级**: P1

---

### 阻塞点 3: View Execute 页面未连接 API [P2]

**影响范围**: 消费视图执行功能

**阻塞原因**: 前端组件未实现或未连接

**修复优先级**: P2

---

## 六、已验证正常功能

| 功能 | API | 状态 |
|------|-----|------|
| 空间列表 | GET /v1/spaces | ✓ |
| 空间 Schema | GET /v1/spaces/{id}/schema | ✓ |
| L4 规则定义 | GET /v1/spaces/{id}/schema/L4/rules/definitions | ✓ (6 条) |
| 消费视图列表 | GET /v1/views | ✓ |
| simulation/tree API 调用 | POST /v1/simulation/tree | ✓ (被调用，返回空) |
| Vite 代理配置 | /v1 → localhost:8000 | ✓ |

---

## 七、截图证据

| LEG | 截图路径 | 说明 |
|-----|----------|------|
| LEG 1 | /tmp/leg1_spaces_list.png | 空间列表页 |
| LEG 2 | /tmp/leg2_schema.png | Schema 页面 |
| LEG 3 | /tmp/leg3_rules.png | Rules 页面 |
| LEG 4 | /tmp/leg4_simulate.png | Simulate 页面 |
| LEG 5 | /tmp/leg5_sim_embed.png | Simulation Embed |
| LEG 6 | /tmp/leg6_after_build.png | 构建后状态 |
| LEG 7 | /tmp/leg7_views.png | Views 页面 |
| LEG 8 | /tmp/leg8_view_execute.png | View Execute |

---

## 八、测试脚本

```bash
# 运行完整旅程分析
python3 journey_analysis.py

# 分析结果
cat /tmp/journey_analysis_*.json | python3 -m json.tool
```

---

## 九、相关文件索引

### 后端 - 关键阻塞文件
- `ontology_engine/services/simulation_tree_builder.py` - _filter_steps TODO
- `ontology_engine/services/rule_service.py` - locate_rule_groups
- `ontology_engine/api/routes/simulation.py` - create_simulation_tree

### 前端 - 待检查文件
- `ontology-engine-ui/src/pages/spaces/RulesEmbedPage.tsx` - GAP-FE3
- `ontology-engine-ui/src/pages/SimulationPage.tsx` - GAP-FE4
- `ontology-engine-ui/src/pages/consumption/RuleExecutionPage.tsx` - GAP-FE8

---

## 十、后续行动

### P0 - 立即修复
1. 实现 `RuleTreeBuilder._filter_steps()` 从 L4 层提取规则步骤

### P1 - 近期修复
2. 扩展 `_locate_by_output` 直接查询 SemanticSpace L4 层
3. 检查 Rules 页面组件渲染问题

### P2 - 计划修复
4. 实现 View Execute 页面组件
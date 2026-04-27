# 规则模拟流程阻塞点分析报告

> 日期: 2026-04-23
> 状态: 分析完成，待实施

---

## 关键决策

### 决策 1: 语义空间逻辑隔离

**规则模拟必须限定在某一语义空间下，所有本体资产的访问/接口调用都已经在语义空间层面做了逻辑隔离。**

---

### 决策 2: 不允许 Mock 数据

**所有集成测试和前端测试不允许通过 mock 数据模拟，缺失内容必须弹出。**

---

### 决策 3: 规则执行时获取指标值

**规则执行时应当根据数据集映射的指标获取数据。**

当前数据流：
```
实体数据 (L1) + 关系数据 (Relations)
       ↓
   L3 指标计算 (图遍历)
       ↓
   规则执行 (L4)
```

---

## 前端验证结果 (2026-04-23)

### 测试方法
- Playwright 自动化测试
- 直接访问 `/simulation/embed?schemaId=space_supply_chain_finance`
- 抓取所有 API 调用

### 关键发现

**simulation/tree API 被正确调用，但返回空 layers**

```json
POST /v1/simulation/tree
{
  "schema_id": "space_supply_chain_finance",
  "target_output": "decision"
}

Response:
{
  "success": true,
  "data": {
    "session_id": "b34ae695-...",
    "execution_tree": {
      "layers": [],
      "total_steps": 0,
      "rule_group_count": 0
    },
    "required_inputs": [],
    "current_inputs": {}
  }
}
```

**前端组件工作正常**：
- SimulationPanel 正确渲染
- 调用 `simulationApi.createTree()` 发送请求
- 正确处理空 layers 响应并显示 Empty 状态

**真正的问题在后端**: `RuleTreeBuilder._filter_steps()` 返回 `[]`

---

## 后端阻塞点分析

### 阻塞点 1: RuleTreeBuilder._filter_steps() 是 TODO 占位实现

**文件**: `ontology_engine/services/simulation_tree_builder.py:138-158`

```python
async def _filter_steps(
    self,
    groups: list[RuleGroupDefinition],
    entity_id: str | None,
) -> list[dict[str, Any]]:
    """Filter steps from rule groups by entity category."""
    # TODO: Implement actual step filtering by entity category
    # For now, return empty list as placeholder
    return []
```

**问题**:
1. `_filter_steps` 永远返回空列表 `[]`
2. 导致 `build_tree` 中 layers 永远为空
3. 前端 ExecutionTreeViewer 无法显示任何步骤

**影响规则**:
- RD001 基础准入检查
- RD003 担保圈风险检测
- RD004 授信额度计算
- RD005 风险指标预警
- RD006 综合授信决策

**修复方案**: 实现 `_filter_steps` 从 L4 层提取规则步骤信息

---

### 阻塞点 2: L3 图遍历计算未实现

**问题**:
```
Schema 定义:
  total_invoice_amount_90d:
    source.type: "graph_traversal"
    traversal: "Supplier --has_invoice--> Invoice"
    aggregate: "SUM(Invoice.amount.value)"

实际计算:
  computed_metrics.total_invoice_amount_90d = null
```

**已创建的关系数据 (59 条)**:
- has_invoice: 14 条
- issued_by: 14 条
- issued_to: 14 条
- supplies_to: 7 条
- has_contract: 5 条
- signed_with: 5 条

---

### 阻塞点 3: L1 属性字段名与规则期望不匹配

**问题**:
```
实体数据:
  registered_capital: { value: 50000000, currency: "CNY" }

规则表达式:
  registered_capital_value >= 1000000  ← 期望扁平值
```

---

## 已禁用规则 (待 L3 图遍历实现后启用)

```bash
RD001_basic_eligibility (disabled)
RD003_guarantee_risk_check (disabled)
RD004_credit_limit_calc (disabled)
RD005_risk_early_warning (disabled)
RD006_final_decision (disabled)
```

---

## 当前可用功能验证

| 功能 | API | 状态 |
|-----|-----|------|
| 消费视图 Simulate | `/v1/views/{id}/execute/simulate` | ✓ 可调用 |
| 消费视图 Entities | `/v1/views/{id}/entities` | ✓ 27 个实体 |
| Schema Overview | `/v1/spaces/{id}/schema` | ✓ L1-L4 完整 |
| 规则依赖图 | `/v1/spaces/{id}/schema/L4/rules/dependency-graph` | ⚠ 边为空 |
| SimulationTreeBuilder | `/v1/simulation/tree` | ⚠ 返回空 layers |
| RuleTreeBuilder._filter_steps | simulation_tree_builder.py:138 | ✗ TODO 占位 |

---

## 前端组件验证结果

| 组件 | 路径 | 状态 |
|------|------|------|
| SimulationPanel | `/simulation/embed` | ✓ 正确调用 API，显示空状态 |
| SimulationEmbedPage | `/simulation/embed?schemaId=...` | ✓ URL 参数正确传递 |
| ExecutionTreeViewer | SimulationPanel 内 | ⚠ 无数据可显示 |
| InputValuesForm | SimulationPanel 内 | ⚠ 无数据可显示 |
| SimulationResultPanel | SimulationPanel 内 | ⚠ 无数据可显示 |

---

## 修复优先级

| 优先级 | 阻塞点 | 修复方案 |
|--------|--------|----------|
| P0 | `_filter_steps` TODO | 实现从 L4 层提取规则步骤 |
| P1 | L3 图遍历 | 实现图遍历计算引擎 |
| P2 | L1 属性映射 | 实现属性映射层 |

---

## 相关文件

- `ontology_engine/services/simulation_tree_builder.py` - RuleTreeBuilder
- `ontology_engine/services/rule_service.py` - RuleService
- `ontology_engine/api/routes/simulation.py` - Simulation API
- `ontology_engine/core/semantic_space.py` - SemanticSpace 模型
- `ontology-engine-ui/src/components/simulation/SimulationPanel.tsx` - 前端调用方

---

## 下一步行动

1. 实现 `RuleTreeBuilder._filter_steps()` 从 L4 层提取规则步骤
2. 验证执行树正确构建
3. 实现 L3 图遍历计算
4. 重新启用依赖图遍历的规则
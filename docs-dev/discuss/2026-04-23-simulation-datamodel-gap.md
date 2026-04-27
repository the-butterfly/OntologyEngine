# 关键决策点：语义空间逻辑隔离与规则模拟数据模型

> 日期: 2026-04-23
> 状态: 已讨论，待实施

## 关键决策

**规则的模拟必须限定在某一语义空间下，所有本体资产的访问/接口调用都已经在语义空间层面做了逻辑隔离。**

## 当前问题

### 问题描述

系统中存在**两套并行的规则数据模型**：

| 数据模型 | 存储位置 | API 路径 | 当前状态 |
|---------|---------|---------|---------|
| L4 规则定义 | SemanticSpace.layers.L4_business_logic | `/v1/spaces/{id}/schema/L4/rules/definitions` | **有效数据** (6 条规则) |
| RuleGroups | SQLite `rule_groups` 表 | `/v1/rule-groups` | **空** |

### 断裂的调用链

```
SimulationTreeBuilder.build_tree()
  └→ _locate_by_output(output_name, schema_id)
      └→ RuleService.locate_rule_groups(output_name, schema_id)
          └→ Storage.list_rule_groups(schema_id)  ← 查询 SQLite → 返回 []
          ✗ 错误：应该查询 SemanticSpace L4 层
```

### 影响

1. `/v1/simulation/tree` API 返回空 layers，无法构建执行树
2. 前端 SimulationPanel 无法显示任何规则步骤
3. 跨规则组依赖追踪功能完全失效

## 修复方向

### 选项 A: 扩展 RuleTreeBuilder 直接查询 SemanticSpace L4 层

**方案**：
- 修改 `RuleTreeBuilder._locate_by_output()` 直接从 SemanticSpace L4 层查找规则
- 使用 SemanticSpaceStorage 或 Management API 获取规则定义
- 不依赖 RuleService

**优点**：
- 直接访问数据源，无数据同步问题
- 符合语义空间隔离原则

**缺点**：
- 绕过 RuleService，需要处理权限/隔离逻辑

### 选项 B: 打通 rule_groups 表和 L4 层

**方案**：
- 在 L4 规则导入/创建时，同步写入 rule_groups 表
- 或修改 RuleService 使其从 SemanticSpace L4 层读取

**优点**：
- 复用现有 RuleService 接口

**缺点**：
- 数据冗余，需要同步维护
- 违反单一数据源原则

## 推荐方案

**选项 A** - 扩展 RuleTreeBuilder 直接查询 SemanticSpace L4 层

**理由**：
1. 符合语义空间逻辑隔离原则
2. 无数据同步问题
3. 减少中间层复杂度

## 实施要点

1. `RuleTreeBuilder` 需要注入 `SemanticSpaceStorage` 或类似依赖
2. `_locate_by_output` 需要根据 `output_name` 在 L4.rule_definitions 中搜索匹配的规则
3. 需要处理 `applies_to` (target_objects) 的分类过滤逻辑
4. 前端 SimulationPanel 的 `schemaId` 应正确传递到 API

## 相关文件

- `ontology_engine/services/simulation_tree_builder.py` - RuleTreeBuilder
- `ontology_engine/services/rule_service.py` - RuleService
- `ontology_engine/api/routes/simulation.py` - Simulation API
- `ontology_engine/core/semantic_space.py` - SemanticSpace 模型

## 相关 Issue

- 前端 SimulationPanel 未使用真实 backend 数据
- Simulation 执行 (_run_simulation) 抛出 NotImplementedError

---

## 问题 2: L3 图遍历计算未实现

### 问题描述

L3 指标 (analytical_elements) 定义了图遍历计算公式，但计算引擎未实现：

```
Schema 定义:
  total_invoice_amount_90d:
    source.type: "graph_traversal"
    traversal: "Supplier --has_invoice--> Invoice"
    aggregate: "SUM(Invoice.amount.value)"

实际计算:
  computed_metrics.total_invoice_amount_90d = null
```

### 影响的规则

| 规则 ID | 规则名称 | 依赖的图遍历指标 |
|---------|---------|-----------------|
| RD001 | 基础准入检查 | total_invoice_amount_90d |
| RD003 | 担保圈风险检测 | has_guarantee_cycle, guarantee_chain_depth |
| RD004 | 授信额度计算 | guarantee_chain_depth |
| RD005 | 风险指标预警 | guarantee_chain_depth |
| RD006 | 综合授信决策 | guarantee_chain_depth, has_guarantee_cycle |

### 修复方向

**选项 A: 实现 L3 图遍历计算引擎**
- 在 QueryService 或独立服务中实现图遍历逻辑
- 读取 SemanticSpace 中的关系数据
- 沿遍历路径聚合计算

**选项 B: 将依赖图遍历的规则暂时禁用**
- 在 schema 定义中将 `enabled: false`
- 保留规则定义，后续实现后启用

---

## 问题 3: L1 属性字段名与规则期望不匹配

### 问题描述

实体数据的属性结构与规则表达式期望的字段名不一致：

```
实体数据 (Entity):
  registered_capital: { value: 50000000, currency: "CNY" }
  establishment_date: "2018-03-15"
  status: "ACTIVE"

规则表达式 (RuleLogic.when.expression):
  "status == 'ACTIVE'"
  "AND registered_capital_value >= 1000000"
  "AND days_since(establishment_date) >= 365"
```

### 问题分析

1. `registered_capital` 是嵌套对象 (Money 类型)，规则期望扁平值 `registered_capital_value`
2. 规则引擎需要将实体属性映射到表达式变量

### 修复方向

**选项 A: 修改规则表达式使用正确的字段名**
- 将 `registered_capital_value` 改为 `registered_capital.value`

**选项 B: 在实体加载时扁平化属性**
- 将 `registered_capital: {value, currency}` 扁平为 `registered_capital_value`

---

## 关键约束

**所有集成测试和前端测试不允许通过 mock 数据模拟，缺失内容必须弹出。**

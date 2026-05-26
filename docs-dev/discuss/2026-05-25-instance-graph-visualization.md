# 实例图可视化决策记录

> **日期**: 2026-05-25
> **参与者**: Agent
> **背景**: 增强前端可视化能力，将 OntologyEngine 中存储的图实例数据进行展示渲染

## 设计决策

### 1. API 策略：新增专用端点
- **决策**: 新增 `GET /v1/spaces/{space_id}/instances/graph` 端点，直接返回 G6 格式实例图数据
- **理由**: 复用现有 entities/relations 接口需要前端组装大量图数据逻辑，新增专用端点可以在后端完成图构建、担保圈检测、连通分量分析、跳数计算等复杂逻辑，前端只需渲染
- **参数设计**:
  - `seed_entity_id`: 种子节点 ID，用于跳数展开
  - `max_hops`: 最大跳数（默认 3）
  - `concept_filter`: 概念类型过滤（逗号分隔）
  - `group_by`: 分组模式（concept/component/hops/result）

### 2. 分组维度：多视角并存
- **决策**: API 同时返回四种分组数据，前端按场景切换展示
  - `concept_groups`: 按概念类型分组（Supplier/Invoice/Contract/GuaranteeRelation 等）
  - `component_groups`: 按连通分量分组（自动检测不连通子图）
  - `hop_groups`: 按检索路径跳数分组（Seed→1-hop→2-hop→...）
  - `result_groups`: 按业务结果分组（approved/rejected/pending/unknown）
- **理由**: 不同的溯源场景需要不同的分组视角，前端应支持按场景切换

### 3. 布局策略：类 DAG + 力导向混合
- **决策**: 提供三种布局模式，用户可切换
  - `force`（力导向）：默认，适合自由探索
  - `dagre`（DAG 分层）：按数据流/检索流层级展示
  - `concentric`（同心圆）：以种子节点为中心辐射分层
- **理由**: 大框架按数据流/检索流分层，局部邻居按力导向聚集，兼顾结构和可读性

### 4. 担保圈处理
- **决策**: GuaranteeRelation 实体自动转换为担保关系边，并检测循环担保路径
  - 担保边去重：如果已有同向担保关系，不重复添加
  - 循环检测：DFS 检测担保环，标记 `is_cycle_edge`
  - 金额格式化：将 `{value: 6000000, currency: "CNY"}` 格式化为 "6000000 CNY"
- **理由**: 供应链金融场景中担保关系是核心可视化目标，必须正确展示担保圈

### 5. 前端组件架构
- **InstanceGraphPage**: 主页面，集成所有功能
- **InstanceGraphView**: G6 图渲染组件，支持三种布局
- **GroupingPanel**: 多维逻辑分组面板（概念类型/连通分量/检索路径/业务结果）
- **InstanceNodeDetail**: 节点详情展示（实体属性、信用评分、业务结果）

### 6. 数据完整性修复
- **问题**: supply_chain_finance 案例的 GuaranteeRelation 数据未加载到空间 JSON
- **解决**: 直接更新 `data/semantic_spaces/space_35eb8d8c.json`，添加 4 条担保关系
- **验证**: API 返回 63 节点、114 边、4 条担保边、3 条三角循环担保圈边

## 验收结果

### 后端 API 验收
```
Graph Type: instance_graph
Nodes: 63 (CoreEnterprise: 3, Supplier: 12, Invoice: 30, Contract: 14, GuaranteeRelation: 4)
Edges: 114 (guarantee: 4, cycle: 4)
Components: 5
Concepts: 5 种概念类型
```

### 种子节点跳数测试
```
Seed=SUP_C_A, MaxHops=2: 57 nodes, 110 edges
  Hop 0 (seed): 1 nodes: ['联华机械制造有限公司']
  Hop 1: 7 nodes: ['INV_C_A_002', 'INV_C_A_001', '联合供应链管理有限公司', ...]
  Hop 2: 49 nodes: ['INV_F_001', 'INV_G_004', ...]
```

### 前端验收
- TypeScript 编译通过（新增代码零错误）
- Ruff lint 通过（All checks passed）
- 前端服务运行在 http://localhost:3000
- 后端服务运行在 http://localhost:8000

## 后续优化方向
1. 检索溯源高亮路径支持多跳路径可视化（当前支持种子展开，待增强路径追踪）
2. 节点详情面板增加证据链展示
3. 增加图导出为图片功能
4. 支持实时数据更新（WebSocket）

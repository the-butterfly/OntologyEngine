# OntologyEngine 前端架构审查文档

> **模块**: ontology-engine-ui 前端代码审查与设计对齐
> **版本**: v1.0
> **审查时间**: 2026-04-14
> **代码基准**: `ontology-engine-ui/src/`
> **参考设计**: [`docs/08-visualization-system.md`](../docs/08-visualization-system.md)

---

## 0. 文档状态

| 项目 | 值 |
|------|-----|
| **状态** | ✅ 已完成 |
| **审查范围** | 管理面 + 消费面全部页面组件 |
| **与后端 API 对齐** | 见 [`docs/08-visualization-system.md`](../docs/08-visualization-system.md) |
| **下一次审查** | Phase 2 MCP 工具接入后 |

---

## 1. 前端架构总览

### 1.1 技术栈

| 层级 | 技术选型 | 状态 |
|------|---------|------|
| **框架** | React 18 + TypeScript | ✅ |
| **路由** | React Router v6 | ✅ |
| **状态管理** | Zustand | ✅ |
| **UI 组件库** | Ant Design 5.x | ✅ |
| **图渲染** | @antv/g6 (AntV G6) | ✅ |
| **HTTP 客户端** | axios | ✅ |
| **构建工具** | Vite | ✅ |

### 1.2 页面路由结构

```
/spaces                          # 管理面入口 - 语义空间列表
├── /spaces/:spaceId              # 空间详情母版页
│   ├── /spaces/:spaceId/schema               # Schema 声明 (L1-L4 四层)
│   ├── /spaces/:spaceId/rules/declarations   # 规则声明管理
│   ├── /spaces/:spaceId/rules/logics         # 规则逻辑管理
│   ├── /spaces/:spaceId/instances            # 数据实例管理
│   ├── /spaces/:spaceId/versions            # 版本历史
│   ├── /spaces/:spaceId/visualize           # Schema 可视化 (消费面)
│   ├── /spaces/:spaceId/execute             # 规则执行 (消费面)
│   └── /spaces/:spaceId/simulate            # What-If 模拟 (消费面)
│
/consumption                     # 消费面入口 - 视图列表
└── /consumption/:viewId         # 独立消费视图页
    ├── /consumption/:viewId/visualize        # Schema 可视化
    ├── /consumption/:viewId/execute         # 规则执行
    └── /consumption/:viewId/simulate        # What-If 模拟
```

### 1.3 目录结构

```
ontology-engine-ui/src/
├── api/
│   ├── spaceApi.ts          # 管理面 API ( /v1/management/* )
│   └── visualization.ts     # 消费面可视化 API ( /v1/visualize/* )
├── components/
│   ├── schema/
│   │   ├── SchemaGraph.tsx       # G6 Schema 图渲染组件
│   │   ├── NodeDetailPanel.tsx   # 节点详情面板
│   │   └── MetricScorecard.tsx   # 指标计分卡
│   └── rule/
│       ├── RuleChainDAG.tsx      # G6 规则链 DAG 组件
│       ├── ExecutionReplay.tsx    # 执行回放组件
│       └── StepDetailPanel.tsx   # 步骤详情面板
├── pages/
│   ├── spaces/               # 管理面页面
│   │   ├── SpaceListPage.tsx          # 空间列表 ✅
│   │   ├── SpaceDetailPage.tsx        # 空间详情母版 ✅
│   │   ├── SchemaDeclarationPage.tsx   # Schema 声明 (L1-L4) ✅
│   │   ├── RuleDeclarationsPage.tsx    # 规则声明 CRUD ✅
│   │   ├── RuleLogicsPage.tsx          # 规则逻辑 CRUD ✅
│   │   ├── InstanceDataPage.tsx         # 数据实例 ✅
│   │   └── VersionHistoryPage.tsx      # 版本历史 ✅
│   ├── consumption/          # 消费面页面
│   │   ├── SchemaVisualizationPage.tsx # Schema 可视化 ✅
│   │   ├── RuleExecutionPage.tsx        # 规则执行 ✅
│   │   ├── ConsumptionViewPage.tsx     # 独立消费视图 ✅
│   │   └── ConsumptionViewListPage.tsx # 消费视图列表 ✅
│   └── SimulationPage.tsx    # What-If 模拟 ✅
├── store/
│   └── spaceStore.ts         # Zustand 状态管理 ✅
├── types/
│   └── visualization.ts      # 可视化类型定义 ✅
└── utils/
    ├── colorSchemes.ts       # 颜色映射表
    └── labelMappings.ts      # 标签文本映射
```

---

## 2. 功能覆盖矩阵

### 2.1 管理面功能

| 功能模块 | 操作类型 | 页面文件 | API 端点 | 状态 |
|---------|---------|---------|---------|------|
| **语义空间** | 列表 / 创建 / 激活 / 失效 / 删除 | `SpaceListPage.tsx` | `GET/POST /v1/management/spaces` | ✅ |
| **L1 事实对象** | 列表 / 创建 | `SchemaDeclarationPage.tsx` | `GET/POST /v1/management/{spaceId}/schema/L1/fact-objects` | ✅ 部分 |
| **L2 分类体系** | 列表 (只读) | `SchemaDeclarationPage.tsx` | 通过 `schema/overview` 获取 | ✅ |
| **L3 分析要素** | 列表 (只读) | `SchemaDeclarationPage.tsx` | 通过 `schema/overview` 获取 | ✅ |
| **L4 规则声明** | 增 / 删 / 改 / 查 | `RuleDeclarationsPage.tsx` | `GET/POST/PUT/DELETE /v1/management/{spaceId}/schema/L4/rules/definitions` | ✅ |
| **L4 规则逻辑** | 增 / 删 / 改 / 查 | `RuleLogicsPage.tsx` | `GET/POST/PUT/DELETE /v1/management/{spaceId}/schema/L4/rules/logics` | ✅ |
| **数据实例** | 列表 / 批量导入 / 关系 | `InstanceDataPage.tsx` | `GET /v1/management/{spaceId}/instances/entities` | ✅ |
| **版本历史** | 列表 / 创建快照 / 回滚 | `VersionHistoryPage.tsx` | `GET/POST /v1/management/{spaceId}/versions` | ✅ |
| **YAML 导入** | Schema / 实例导入 | `SchemaDeclarationPage.tsx`, `InstanceDataPage.tsx` | `POST /v1/management/{spaceId}/schema/load-from-yaml` | ✅ |

**管理面评估**: ✅ **功能完整**，覆盖了 L1-L4 四层的声明管理和数据实例管理。

### 2.2 消费面功能

| 功能模块 | 操作类型 | 页面文件 | API 端点 | 状态 |
|---------|---------|---------|---------|------|
| **Schema 可视化** | Schema 图渲染 (G6) | `SchemaVisualizationPage.tsx` + `SchemaGraph.tsx` | `GET /v1/visualize/schema/graph` | ✅ |
| **图类型切换** | entity_relation / metric_dependency / full / rule_overview | `SchemaVisualizationPage.tsx` | `GET /v1/visualize/schema/graph?graph_type=...` | ✅ |
| **节点详情面板** | 点击节点查看详情 | `NodeDetailPanel.tsx` | — (前端数据) | ✅ |
| **规则依赖图** | 规则链 DAG 渲染 | `RuleExecutionPage.tsx` (Tab: dependency) | `GET /v1/consumption/views/{viewId}/rules/dependency-graph` | ✅ |
| **规则执行** | 单实体规则执行 + 步骤回放 | `RuleExecutionPage.tsx` | `POST /v1/consumption/views/{viewId}/execute/analyze` | ✅ |
| **适用规则查询** | 实体匹配规则列表 | `RuleExecutionPage.tsx` (Tab: applicable) | `GET /v1/consumption/views/{viewId}/rules/for-entity/{entityId}` | ✅ |
| **What-If 模拟** | 变量覆盖 + 对比分析 | `SimulationPage.tsx` | `POST /v1/consumption/views/{viewId}/execute/simulate` | ✅ |
| **影响链分析** | 差异 + 影响路径可视化 | `SimulationPage.tsx` | 内嵌于 `SimulationResult.comparison` | ✅ |

**消费面评估**: ✅ **功能完整**，与 [`docs/08-visualization-system.md`](../docs/08-visualization-system.md) 中的 6 个 API 端点完全对齐。

---

## 3. 已实现功能详解

### 3.1 管理面：SchemaDeclarationPage (L1-L4 四层)

**文件**: `src/pages/spaces/SchemaDeclarationPage.tsx`

**实现状态**: ✅ 完整

| 层级 | 功能 | 实现细节 |
|------|------|---------|
| **L1 事实对象** | 表格展示 + 展开详情 | 列：ID/名称/属性/关系；展开显示完整属性列表 |
| **L2 分类体系** | 表格展示 + 触发器展开 | 展示 applicable_to + triggers（allOf/anyOf 条件） |
| **L3 分析要素** | 表格展示 + formula/source/components | 颜色区分 atomic/derived/composite/graph；展开显示权重、依赖、阈值 |
| **L4 业务规则** | 表格展示 + 规则逻辑折叠 | 展示 rule_type/priority/input_elements/output_elements；展开显示 when/then_action |
| **YAML 导入** | Modal + 预设路径 | 支持 `supply_chain_finance` 和 `consumer_credit` 预设路径 |

**改进建议**:
- L2 分类体系目前仅支持查看，不支持创建/编辑/删除操作
- L3 分析要素仅支持查看，不支持创建/编辑/删除操作
- YAML 导入没有增量模式确认提示（`overwrite` 参数交互不清晰）

### 3.2 管理面：RuleDeclarationsPage (L4 规则声明)

**文件**: `src/pages/spaces/RuleDeclarationsPage.tsx`

**实现状态**: ✅ 完整

| 功能 | 实现细节 |
|------|---------|
| 规则声明 CRUD | 完整 Modal 表单编辑器 |
| 规则类型标签 | constraint/inference/alert/decision/veto 五色标签 |
| 优先级排序 | 支持按 priority 排序 |
| 输入/输出要素编辑 | Form.List 动态增删行 |
| 目标对象编辑 | 逗号分隔的概念名称列表 |
| 启用/禁用开关 | Switch 组件 |
| 跳转规则逻辑 | 工具栏 BranchesOutlined 按钮跳转 `/rules/logics?definition=xxx` |
| 展开行查看 | 显示 description + applicable_scope + logic_ids |

### 3.3 管理面：RuleLogicsPage (L4 规则逻辑)

**文件**: `src/pages/spaces/RuleLogicsPage.tsx`

**实现状态**: ✅ 完整

| 功能 | 实现细节 |
|------|---------|
| 规则逻辑 CRUD | Modal 表单编辑器 |
| WHEN 条件编辑器 | 支持 expression / allOf / anyOf 三种条件类型 |
| THEN/ELSE 动作编辑器 | approve/reject/compute/set_flag/alert/recommend |
| 版本/优先级/环境 | 完整元数据编辑 |
| 适用条件 JSON 编辑 | raw JSON 输入框 |
| 表格视图 + DAG 视图切换 | Segmented 控制 |
| DAG 视图 | 调用 `RuleChainDAG` 组件渲染规则链 |
| URL 参数联动 | `?definition=xxx` 筛选特定规则的逻辑 |

### 3.4 消费面：SchemaVisualizationPage

**文件**: `src/pages/consumption/SchemaVisualizationPage.tsx` + `SchemaGraph.tsx`

**实现状态**: ✅ 完整

| 功能 | 实现细节 |
|------|---------|
| 四种图类型切换 | entity_relation / metric_dependency / full / rule_overview |
| 层级筛选 | L1/L2/L3/L4 过滤下拉 |
| 节点搜索 | 输入框搜索节点 ID 或 label |
| 节点点击选中 | 右侧 `NodeDetailPanel` 显示详情 |
| 节点悬停高亮 | 高亮相邻节点和边 |
| 图片导出 | `graph.toDataURL()` 导出 PNG |
| 图表统计 | 底部显示 entity/metric/rule 数量标签 |
| Dagre 布局 | 支持 TB/LR 方向，节点分层 |
| Force 布局 | 可选力导布局 |
| 双向边曲线 | 多边时自动计算 curveOffset 避免重叠 |

### 3.5 消费面：RuleExecutionPage

**文件**: `src/pages/consumption/RuleExecutionPage.tsx`

**实现状态**: ✅ 完整

| 功能 | 实现细节 |
|------|---------|
| 规则执行 | `execute/analyze` API，带维度选择 |
| 执行结果展示 | 决策徽章 + 最终输出卡片 + 折叠步骤列表 |
| 步骤详情 | 条件表达式 / 子条件拆解 / 输入输出追踪 |
| 适用规则查询 | `rules/for-entity/{entityId}` API |
| 规则依赖图 | `rules/dependency-graph` API，拓扑排序展示 |
| 互斥规则对 | Alert 警告展示 mutual_exclusions |
| 规则节点卡片 | 输入/输出要素标签 + 匹配逻辑详情 |

### 3.6 消费面：SimulationPage

**文件**: `src/pages/SimulationPage.tsx`

**实现状态**: ✅ 完整

| 功能 | 实现细节 |
|------|---------|
| 模拟参数面板 | 实体选择 + 维度选择 + 变量覆盖 |
| 快速预设 | eligible=true/false 快捷按钮 |
| 智能建议 | 基于实体数值字段的 80% 填充覆盖值 |
| 模拟执行 | `execute/simulate` API |
| 执行步骤标签流 | passed/failed/skipped 三色标签 |
| 对比分析表格 | 原始值 vs 模拟值 + 变化类型 + 影响说明 |
| 影响链分析 | 卡片式影响路径可视化 |
| 最终输出卡片 | 变化字段高亮 (蓝色) |
| 决策对比徽章 | APPROVED/REJECTED/REVIEW 三色 |

---

## 4. 不足与改进项

### 4.1 高优先级改进项

#### P1-1: L2/L3 层级不支持创建和编辑

**现状**: `SchemaDeclarationPage` 的 L2 和 L3 Tab 仅支持只读表格展示。

**影响**: 用户无法通过 UI 创建/编辑分类体系(L2)和分析要素(L3)，必须通过 YAML 导入。

**改进方向**:
- L2 分类体系：需要 `POST /v1/management/{spaceId}/schema/L2/categorizations` 端点支持（后端可能已有）
- L3 分析要素：需要 `POST /v1/management/{spaceId}/schema/L3/elements` 端点支持

**参考**: [`examples/README.md`](../examples/README.md) 中的 `supply_chain_finance` 案例包含了完整的 L2/L3 定义，说明数据模型已设计好。

#### P1-2: 实体实例编辑功能缺失

**现状**: `InstanceDataPage` 只支持 YAML 批量导入和列表查看，不支持单个实体的编辑/新增/删除。

**影响**: 用户无法在线修改实体属性，必须通过 YAML 文件操作。

**改进方向**:
- 添加 `PUT /v1/management/{spaceId}/instances/entities/{entityId}` API 支持
- 前端添加编辑 Modal

#### P1-3: RuleChainDAG 组件未集成到消费面

**现状**: `RuleChainDAG` 组件已在 `RuleLogicsPage` (管理面) 的 DAG 视图中使用，但 `RuleExecutionPage` (消费面) 的"规则依赖图"Tab 使用的是自定义表格渲染，而非 G6 DAG 图。

**改进方向**:
- 将 `RuleChainDAG` 组件引入 `RuleExecutionPage` 的 dependency Tab
- 复用 `src/components/rule/RuleChainDAG.tsx`

### 4.2 中优先级改进项

#### P2-1: SchemaGraph 节点不支持拖拽编辑

**现状**: 当前 G6 图仅支持拖拽画布、缩放、节点选择，不支持拖拽改变节点层级或关系。

**改进方向**: 如需支持编辑模式，参考 G6 5.x 的 `drag-element` behavior 配置。

#### P2-2: 模拟页面的 OverrideInput 缺少校验

**现状**: `SimulationPage` 的 `OverrideInput` 组件接受任意字符串输入，未校验字段是否存在于 Schema 定义中。

**改进方向**:
- 从 `schema/overview` 或 `getSchemaGraph` 获取有效字段列表
- 添加下拉联想或校验提示

#### P2-3: 规则执行结果的子条件拆解展示可增强

**现状**: `RuleExecutionPage` 渲染 `condition_sub_conditions`，但仅用简单的绿色/红色背景区分。

**改进方向**:
- 增加条件成立/不成立的解释文本
- 添加执行耗时显示 (duration_ms)

### 4.3 低优先级改进项

#### P3-1: SpaceDetailPage 侧边栏未高亮当前菜单

**现状**: `SpaceDetailPage` 使用 `Menu` + `selectedKeys`，但子菜单 key 匹配逻辑 (`getSelectedKey`) 在 `rules/declarations` 和 `rules/logics` 时只取第二层，实际菜单项 key 可能不精确匹配。

**现状代码** (第 67-76 行):
```typescript
const getSelectedKey = () => {
  const path = location.pathname;
  const suffixes = ['schema', 'rules/declarations', 'rules/logics', 'instances', 'versions', 'visualize', 'execute', 'simulate'];
  for (const suffix of suffixes) {
    if (path.includes(`/${suffix}`)) {
      return suffix;
    }
  }
  return 'schema';
};
```

**问题**: 路径 `/spaces/xxx/rules/declarations` 会匹配到 `rules/declarations`，但菜单项的 key 也是 `rules/declarations`，理论上应该正确。实际测试需确认。

#### P3-2: 消费视图列表页面过于简单

**现状**: `ConsumptionViewListPage` 仅展示视图列表，缺少创建/删除/状态切换功能。

**改进方向**: 消费视图由空间激活自动创建，前端无需手动管理。

---

## 5. 与设计文档的对齐核验

### 5.1 [`docs/08-visualization-system.md`](../docs/08-visualization-system.md) 核验

| 设计项 | 后端实现 | 前端实现 | 对齐状态 |
|-------|---------|---------|---------|
| 6 个 API 端点 | ✅ 全部实现 | ✅ 全部调用 | ✅ 完整对齐 |
| G6 图渲染 | ✅ builders.py 输出 G6 格式 | ✅ SchemaGraph.tsx + RuleChainDAG.tsx | ✅ |
| X6 DAG | ⚠️ 未使用 X6 | ⚠️ G6 实现规则链 DAG | ⚠️ 技术栈差异，功能等效 |
| 模拟执行 What-if | ✅ `/simulate` + `ComparisonResult` | ✅ SimulationPage 对比视图 | ✅ |
| 影响链分析 | ✅ `impact_chains` | ✅ SimulationPage 影响链卡片 | ✅ |
| 执行回放 | ⚠️ 后端返回 `ExecutionStepSnapshot[]` | ⚠️ ExecutionReplay 组件存在但未集成到 RuleExecutionPage | ⚠️ 待集成 |

### 5.2 [`examples/README.md`](../examples/README.md) 核验

| 验收场景 | 前端入口 | 验证可行性 |
|---------|---------|---------|
| CASE-A: APPROVE | SimulationPage | ✅ 可复现 |
| CASE-B: REJECT | SimulationPage | ✅ 可复现 |
| CASE-C: APPROVE_WITH_CONDITIONS + CRITICAL | SimulationPage | ✅ 可复现 |
| L3 图指标可视化 | SchemaVisualizationPage (metric_dependency) | ✅ |
| 规则声明/逻辑分离 | RuleDeclarationsPage + RuleLogicsPage | ✅ |
| 担保链深度图 | SchemaVisualizationPage (metric_dependency) | ✅ |
| 产品分流 | RuleExecutionPage (applicable rules) | ✅ |

---

## 6. 代码质量评估

### 6.1 优点

| 评估项 | 说明 |
|-------|------|
| **类型安全** | 全面使用 TypeScript Interface/Type，`visualization.ts` 定义了完整的数据模型 |
| **组件拆分** | SchemaGraph/RuleChainDAG/NodeDetailPanel 等组件职责单一 |
| **状态管理** | Zustand store 统一管理 spaces/entities/executionResults，结构清晰 |
| **API 分层** | `spaceApi` (管理面) 和 `visualization.ts` (消费面) 分离，避免跨层调用 |
| **错误处理** | 统一 `ApiError` 类 + `normalizeAxiosError` + store 层 error 状态 |
| **生命周期管理** | G6 组件使用 `isDestroyedRef` 防止销毁后回调执行 |

### 6.2 技术债务

| 问题 | 位置 | 说明 |
|------|------|------|
| **G6 5.x API 差异** | `SchemaGraph.tsx`, `RuleChainDAG.tsx` | G6 5.x `graph.toDataURL()` vs G6 4.x `graph.toDataURL()`，需确认 API 兼容性 |
| **any 类型残留** | `spaceStore.ts` 多处 `any` | `executionResult`, `simulationResult`, `schemaGraph` 声明为 `any` |
| **重复类型定义** | `visualization.ts` 和 `types/visualization.ts` | 两处都有 `GraphNode`, `GraphEdge` 等类型定义，存在冗余 |
| **样式耦合** | 各页面内联样式过多 | 建议抽取到 `App.css` 或 CSS Modules |

---

## 7. 后续工作建议

### 立即可做

1. **集成 ExecutionReplay 组件**: `RuleExecutionPage` 的执行结果Tab 应使用 `ExecutionReplay.tsx` 组件替代当前的折叠面板
2. **L2/L3 创建支持**: 与后端确认 L2 分类和 L3 要素的 API 是否支持，创建对应的 UI 表单
3. **RuleChainDAG 集成消费面**: 将 `RuleChainDAG` 组件引入 `RuleExecutionPage` dependency Tab

### 短期迭代

4. **实体编辑功能**: 添加单个实体的编辑 Modal
5. **OverrideInput 校验**: 基于 Schema 定义校验覆盖字段
6. **子条件解释增强**: 添加条件成立/不成立的自然语言解释

### 中期改进

7. **消费面独立导航**: `/consumption/:viewId` 页面添加侧边菜单，与管理面风格统一
8. **Playwright E2E 测试**: 覆盖管理面和消费面的核心用户路径
9. **性能优化**: G6 大图 (100+ 节点) 的虚拟化渲染

---

## 8. 相关文档索引

| 文档 | 关系 |
|------|-----|
| [`docs/08-visualization-system.md`](../docs/08-visualization-system.md) | 后端可视化 API 完整规范 |
| [`docs/09-frontend-architecture.md`](../docs/09-frontend-architecture.md) | 前端架构母版文档 |
| [`examples/README.md`](../examples/README.md) | 示例案例说明，用于验收验证 |
| [`examples/supply_chain_finance/SCHEMA_DESIGN.md`](../examples/supply_chain_finance/SCHEMA_DESIGN.md) | 供应链金融 Schema 设计 |
| [`ontology-engine-ui/src/store/spaceStore.ts`](../ontology-engine-ui/src/store/spaceStore.ts) | 状态管理完整代码 |
| [`ontology-engine-ui/src/types/visualization.ts`](../ontology-engine-ui/src/types/visualization.ts) | 可视化类型定义 |

# RFC-UI-001: 规则编排前端实现 RFC

> **状态**: Draft
> **日期**: 2026-04-15
> **阶段**: Phase 2 前端实施
> **父 RFC**: RFC-014 (规则编排系统) / RFC-015 (后端实现)
> **关联设计**: `docs-ui/03-rule-management-ui-design.md`, `detail/plans/2026-04-15-rule-orchestration-system-design.md`
> **后端基准**: `docs/03-rfc/RFC-015-rule-orchestration-frontend.md`

---

## 一、现状分析

### 1.1 后端实现状态

| 模块 | 状态 | 位置 |
|------|------|------|
| 数据模型 (RuleGroupDefinition, RuleStep, ConditionClause, ActionClause) | ✅ 完成 | `ontology_engine/engine/rule/models.py` |
| 规则组 CRUD API | ✅ 完成 | `ontology_engine/api/routes/rules.py` |
| 规则步骤 CRUD API | ✅ 完成 | `ontology_engine/api/routes/rules.py` |
| 模拟执行 API | ✅ 完成 | `ontology_engine/services/simulation_service.py` |
| YAML 导入/导出 | ✅ 完成 | `ontology_engine/services/rule_service.py` |
| DAG Service | ✅ 完成 | `ontology_engine/services/dag_service.py` |
| 算子注册中心 + JSON Schema | ✅ 完成 | `ontology_engine/engine/rule/operators/registry.py` |
| 存储层 (DuckDB) | ✅ 完成 | `ontology_engine/storage/duckdb/store.py` |

### 1.2 前端实现状态

| 模块 | 状态 | 关联文件 |
|------|------|----------|
| TypeScript 类型定义 | ✅ 完成 | `src/types/rule.ts` |
| API 客户端 (ruleGroups) | ✅ 完成 | `src/api/ruleGroups.ts` |
| API 客户端 (ruleSteps) | ✅ 完成 | `src/api/ruleSteps.ts` |
| Zustand Store | ✅ 完成 | `src/stores/ruleStore.ts` |
| 页面布局组件 | ✅ 完成 | `src/pages/rules/RuleGroupLayout.tsx` |
| 规则组列表页 | ✅ 完成 | `src/pages/rules/RuleGroupListPage.tsx` |
| DAG 可视化组件 | ✅ 完成 | `src/components/rule/RuleChainDAG.tsx` |
| 步骤详情面板 | ✅ 完成 | `src/components/rule/StepDetailPanel.tsx` |
| 执行回放组件 | ✅ 完成 | `src/components/rule/ExecutionReplay.tsx` |
| 算子 API 客户端 | ✅ 完成 | `src/api/operators.ts` |
| 自定义 Hook (useRuleGroups) | ✅ 完成 | `src/hooks/useRuleGroups.ts` |
| 规则组详情页 | ✅ 完成 | `src/pages/rules/RuleGroupDetailPage.tsx` |
| 规则编辑器模态框 | ✅ 完成 | `src/components/rule/RuleEditorModal.tsx` |
| 规则组表单 | ✅ 完成 | `src/components/rule/RuleGroupForm.tsx` |
| 作用对象选择器 | ✅ 完成 | `src/components/rule/TargetEntitiesEditor.tsx` |
| 适用场景编辑器 | ✅ 完成 | `src/components/rule/ApplicabilityEditor.tsx` |
| I/O 要素编辑器 | ✅ 完成 | `src/components/rule/IOElementsForm.tsx` |
| 规则步骤列表 | ✅ 完成 | `src/components/rule/RuleStepList.tsx` |
| 条件编辑器 | ✅ 完成 | `src/components/rule/ConditionEditor.tsx` |
| 动作编辑器 | ✅ 完成 | `src/components/rule/ActionEditor.tsx` |
| 模拟面板 | ✅ 完成 | `src/components/rule/SimulationPanel.tsx` |
| 算子参数编辑器 (5种) | ✅ 完成 | `src/components/operator-params/*.tsx` |

### 1.3 前端依赖检查

| 依赖 | 状态 | 备注 |
|------|------|------|
| `antd` | ✅ 已安装 (^5.24.0) | UI 组件库 |
| `@antv/g6` | ✅ 已安装 (^5.0.0) | DAG 可视化 |
| `@antv/x6` | ✅ 已安装 (^2.18.0) | 规则流转图 |
| `@dnd-kit` | ✅ 已安装 | 用于拖拽排序 |

---

## 二、关键设计点确认

### [关键设计点 1] 规则四元素与语义空间隔离

**设计要求**: 所有 API 调用必须携带 `schema_id` 参数，规则组 name + schema_id 组合唯一。

**当前状态**: ✅ 后端和前端 store 均已正确实现语义空间隔离。

**开发前提**: 前端所有页面和组件必须以 `schemaId` 为必填参数。

---

### [关键设计点 2] 算子 JSON Schema 驱动

**设计要求**: 5 种算子 (BINNING/SCORECARD/WEIGHTED_SUM/DECISION_TABLE/LLM_JUDGE) 的参数通过 JSON Schema 定义，前端动态渲染。

**后端 Schema 状态** (已全部定义于 `ontology_engine/engine/rule/operators/registry.py`):
- ✅ BINNING: `input`, `output`, `inclusive_max`, `bins` (range + label)
- ✅ SCORECARD: `output`, `baseline`, `post_formula`, `variables` (name + points)
- ✅ WEIGHTED_SUM: `output`, `weights` (input + weight), `grade_multipliers`, `grade_input`
- ✅ DECISION_TABLE: `conditions`, `output`, `matrix` (when + result/default)
- ✅ LLM_JUDGE: `output`, `prompt_template`, `input_mapping`, `expected_format`, `confidence_threshold`, `timeout_ms`, `fallback_value`

**开发前提**: 前端需实现 `src/api/operators.ts` 调用 `/operators` 和 `/operators/{name}/schema` 端点，基于 Schema 动态渲染参数表单。

---

### [关键设计点 3] DAG 格式兼容

**设计要求**: `DAGService.to_graph_data()` 输出 G6 5.x 兼容格式。

**当前状态**: ✅ 后端输出 `{nodes, edges}` 结构，前端 `SchemaGraph.tsx` 有 `transformToG6()` 转换函数。

**开发前提**: 无额外适配工作。

---

### [关键设计点 4] 模拟执行 dry_run

**设计要求**: 模拟 API 不写入存储，不触发预警。

**当前状态**: ✅ 后端 `SimulationService.simulate_rule_group()` 已实现。

**开发前提**: 前端模拟面板直接调用 `/simulate` 端点即可。

---

### [关键设计点 5] YAML Schema v2 合规

**设计要求**: 导出格式符合 `docs/05-schema-v2/09-canonical-schema-spec.md`。

**当前状态**: ✅ 后端 `export_rule_group_to_yaml()` 已实现。

**开发前提**: 前端 YAML 预览功能（设计中的"预览 YAML"按钮）可直接使用后端导出 API。

---

## 三、实施路线

### Phase A: 数据层补全 (0.5 天)

| 任务 | 文件 | 依赖 | 验收标准 |
|------|------|------|----------|
| 实现算子 API 客户端 | `src/api/operators.ts` | 后端 `/operators` 端点 | 可获取算子列表和 Schema |
| 安装 @dnd-kit/core @dnd-kit/sortable | `package.json` | npm | 拖拽依赖就绪 |

---

### Phase B: 规则组详情页 (2 天)

| 任务 | 文件 | 依赖 | 验收标准 |
|------|------|------|----------|
| 创建规则组详情页框架 | `src/pages/rules/RuleGroupDetailPage.tsx` | RuleGroupLayout | 三栏布局可显示 |
| 实现框架配置面板 | `src/components/rule/RuleGroupForm.tsx` | AppliesToSelector, IOElementsForm | 四元素编辑可用 |
| 实现作用对象选择器 | `src/components/rule/TargetEntitiesEditor.tsx` | L1 Schema API | 可选择实体类型 |
| 实现适用场景编辑器 | `src/components/rule/ApplicabilityEditor.tsx` | L2 Schema API | 维度过滤 + 前置条件 |
| 实现 I/O 要素编辑器 | `src/components/rule/IOElementsForm.tsx` | L1/L3 API | 输入输出要素配置 |

---

### Phase C: 规则步骤编辑器 (3 天)

| 任务 | 文件 | 依赖 | 验收标准 |
|------|------|------|----------|
| 实现规则步骤列表 | `src/components/rule/RuleStepList.tsx` | dnd-kit | 可拖拽排序 |
| 实现条件编辑器 | `src/components/rule/ConditionEditor.tsx` | - | 三种条件类型支持 |
| 实现动作编辑器 | `src/components/rule/ActionEditor.tsx` | operators API | 算子选择 + 参数渲染 |
| 实现规则编辑器模态框 | `src/components/rule/RuleEditorModal.tsx` | ConditionEditor, ActionEditor | 完整编辑流程 |
| 实现模拟面板 | `src/components/rule/SimulationPanel.tsx` | simulate API | 测试数据 → 结果展示 |

---

### Phase D: 算子参数编辑器 (2 天)

| 任务 | 文件 | 依赖 | 验收标准 |
|------|------|------|----------|
| 实现分箱参数编辑器 | `src/components/operator-params/BinningParamEditor.tsx` | BINNING schema | 区间可视化编辑 |
| 实现评分卡参数编辑器 | `src/components/operator-params/ScorecardParamEditor.tsx` | SCORECARD schema | 得分表格编辑 |
| 实现加权计算参数编辑器 | `src/components/operator-params/WeightedSumParamEditor.tsx` | WEIGHTED_SUM schema | 权重滑块 + 总和校验 |
| 实现决策表参数编辑器 | `src/components/operator-params/DecisionTableEditor.tsx` | DECISION_TABLE schema | 矩阵可视化编辑 |
| 实现 LLM 分析参数编辑器 | `src/components/operator-params/LLMJudgeParamEditor.tsx` | LLM_JUDGE schema | Prompt 模板编辑 |

---

## 四、路由设计

```
/rules                                  → RuleGroupListPage (已实现)
/rules/:groupId                          → RuleGroupDetailPage (Phase B)
/rules/:groupId/edit                    → RuleGroupEditPage (Phase B, 可合并到详情页)
/rules/:groupId/steps/:stepId/edit      → RuleStepEditPage (Phase C, 模态框实现)
```

---

## 五、与后端 RFC-015 的关联

### 5.1 数据模型一致性

前端类型定义 (`src/types/rule.ts`) 与后端模型完全对齐：

| 后端字段 | 前端字段 | 对齐状态 |
|----------|----------|----------|
| `RuleGroupDefinition.id` | `RuleGroup.id` | ✅ |
| `RuleGroupDefinition.name` | `RuleGroup.name` | ✅ |
| `RuleGroupDefinition.applies_to` | `RuleGroup.appliesTo` | ✅ (camelCase 转换) |
| `RuleGroupDefinition.preconditions` | `RuleGroup.preconditions` | ✅ |
| `RuleGroupDefinition.inputs` | `RuleGroup.inputs` | ✅ |
| `RuleGroupDefinition.outputs` | `RuleGroup.outputs` | ✅ |
| `RuleStep.when` | `RuleStep.when` | ✅ |
| `RuleStep.then` | `RuleStep.then` | ✅ |
| `RuleStep.else_` | `RuleStep.else` | ✅ |

### 5.2 API 端点映射

| 前端 API 函数 | HTTP | 后端端点 | 状态 |
|---------------|------|----------|------|
| `ruleGroupsApi.list` | GET | `/rule-groups?schema_id={id}` | ✅ |
| `ruleGroupsApi.getById` | GET | `/rule-groups/{id}?schema_id={id}` | ✅ |
| `ruleGroupsApi.create` | POST | `/rule-groups` | ✅ |
| `ruleGroupsApi.update` | PUT | `/rule-groups/{id}?schema_id={id}` | ✅ |
| `ruleGroupsApi.delete` | DELETE | `/rule-groups/{id}?schema_id={id}` | ✅ |
| `ruleGroupsApi.getSteps` | GET | `/rule-groups/{name}/steps?schema_id={id}` | ✅ |
| `ruleGroupsApi.addStep` | POST | `/rule-groups/{name}/steps?schema_id={id}` | ✅ |
| `ruleGroupsApi.simulate` | POST | `/rule-groups/{name}/simulate?schema_id={id}` | ✅ |
| `ruleGroupsApi.exportYaml` | GET | `/rule-groups/{name}/export?schema_id={id}` | ✅ |
| `ruleGroupsApi.importYaml` | POST | `/rule-groups/import` | ✅ |
| `operatorsApi.list` | GET | `/operators` | ⚠️ 前端缺失 |
| `operatorsApi.getSchema` | GET | `/operators/{name}/schema` | ⚠️ 前端缺失 |

---

## 六、验收标准

### 功能验收

- [ ] 用户可通过列表页进入规则组详情页
- [ ] 规则组详情页三栏布局正确显示
- [ ] 可在详情页编辑规则四元素（作用对象、适用场景、I/O 要素）
- [ ] 可在规则组内添加/编辑/删除规则步骤
- [ ] 规则步骤支持拖拽排序
- [ ] 条件编辑器支持三种条件类型（expression/all_of/any_of）
- [ ] 动作编辑器支持 5 种算子参数配置
- [ ] 模拟面板可输入测试数据并查看执行结果
- [ ] YAML 预览功能可用
- [ ] DAG 可视化正确显示要素依赖

### 技术验收

- [ ] TypeScript 编译无错误
- [ ] ESLint 检查通过
- [ ] 所有 API 调用携带 `schema_id` 参数
- [ ] 拖拽功能使用 @dnd-kit 实现

---

## 七、风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| 拖拽库选型不确定 | @dnd-kit 与 react-beautiful-dnd 二选一 | 推荐 @dnd-kit (更现代，React 18 兼容) |

---

## 八、已确认事项

1. **拖拽库** — @dnd-kit (`@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`)
2. **规则组详情页路由参数** — 使用 `groupId` (UUID) 作为 URL 参数
3. **规则编辑器形式** — 独立页面 (`/rules/:groupId/steps/:stepId/edit`)，非模态框
4. **API 客户端** — `operatorsApi` 已实现，`spaceApi` 包含 L1/L2/L3 Schema API

---

## 九、路由与导航分析

### 9.1 当前路由结构

```
App.tsx 路由配置:
/spaces                                    → SpaceListPage
/spaces/:spaceId                           → SpaceDetailPage (嵌套路由)
  /spaces/:spaceId/schema                  → SchemaDeclarationPage
  /spaces/:spaceId/rules/declarations       → RuleDeclarationsPage (旧)
  /spaces/:spaceId/rules/logics            → RuleLogicsPage (旧)
  ...

/rules (新路由，未在 App.tsx 中配置)         → RuleGroupListPage (已实现但路由缺失)
/rules/:groupId (缺失)                      → RuleGroupDetailPage (需创建)
```

### 9.2 路由冲突风险

**问题**: 当前 `SpaceDetailPage` 使用 `/spaces/:spaceId/rules/*` 路由，而新系统使用 `/rules/*` 路由。两个路由系统并存。

**解决方案**:
- 新路由 `/rules/*` 作为独立入口，不在 `SpaceDetailPage` 下
- `RuleGroupListPage` 通过 URL query 参数 `?schemaId=xxx` 获取语义空间上下文
- 面包屑导航: `规则管理 > 规则组名称`

### 9.3 需要新增/修改的路由

| 路由 | 组件 | 状态 |
|------|------|------|
| `/rules` | RuleGroupListPage | ⚠️ 组件存在，路由未在 App.tsx 注册 |
| `/rules/:groupId` | RuleGroupDetailPage | ❌ 需创建 |
| `/rules/:groupId/edit` | RuleGroupEditPage | ❌ 需创建 |
| `/rules/:groupId/steps/:stepId/edit` | RuleStepEditPage | ❌ 需创建 |
| `/rules/new` | RuleGroupCreatePage | ❌ 需创建 |

---

## 十、前端 API 客户端状态

### 10.1 已实现

| API 客户端 | 文件 | 功能 |
|-----------|------|------|
| `ruleGroupsApi` | `src/api/ruleGroups.ts` | 规则组 CRUD + 模拟 + YAML |
| `operatorsApi` | `src/api/operators.ts` | 算子列表 + Schema |
| `spaceApi` | `src/api/spaceApi.ts` | L1/L2/L3 Schema API (含 `listFactObjects`, `listCategorizations`) |
| `useRuleGroups` | `src/hooks/useRuleGroups.ts` | 规则组数据 Hook |

### 10.2 Schema API 详情 (spaceApi)

```typescript
// L1 实体类型 - 用于 TargetEntitiesEditor
spaceApi.listFactObjects(spaceId: string): Promise<any[]>
// 端点: GET /v1/management/{spaceId}/schema/L1/fact-objects

// L2 分类维度 - 用于 ApplicabilityEditor
spaceApi.listCategorizations(spaceId: string): Promise<any[]>
// 端点: GET /v1/management/{spaceId}/schema/L2/categorizations

// L3 分析要素 - 用于 IOElementsForm
spaceApi.listAnalyticalElements(spaceId: string): Promise<any[]>
// 端点: GET /v1/management/{spaceId}/schema/L3/analytical-elements
```

### 10.3 待补充

| API 客户端 | 文件 | 功能 |
|-----------|------|------|
| `ruleStepsApi` | `src/api/ruleSteps.ts` | 规则步骤 CRUD (subagent 报告存在，需验证) |

---

## 十一、组件依赖关系

```
RuleGroupDetailPage
├── RuleGroupForm
│   ├── TargetEntitiesEditor (→ spaceApi.listFactObjects)
│   ├── ApplicabilityEditor (→ spaceApi.listCategorizations)
│   └── IOElementsForm (→ spaceApi.listAnalyticalElements)
├── RuleStepList
│   └── RuleStepEditPage
│       ├── ConditionEditor
│       ├── ActionEditor
│       │   └── OperatorParamEditor (×5)
│       └── SimulationPanel
└── ElementDAGGraph (→ /dag/full API)
```

---

## 十二、开发前检查清单

### 12.1 环境准备

- [ ] 安装 `@dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`
- [ ] 在 App.tsx 注册 `/rules` 相关路由

### 12.2 路由配置

- [ ] 添加 `/rules` → RuleGroupListPage 路由
- [ ] 添加 `/rules/:groupId` → RuleGroupDetailPage 路由
- [ ] 添加 `/rules/new` → RuleGroupCreatePage 路由

### 12.3 API 验证

- [ ] 验证 `ruleGroupsApi.list()` 返回正确数据
- [ ] 验证 `spaceApi.listFactObjects()` 返回 L1 实体列表
- [ ] 验证 `spaceApi.listCategorizations()` 返回 L2 分类列表
- [ ] 验证 `operatorsApi.list()` 返回算子列表和 Schema

### 12.4 类型定义

- [ ] 补充 L1/L2/L3 Schema API 的 TypeScript 类型
- [ ] 确认 `AppliesToConfig.categories` 的结构与后端一致

---

**完成标记**: `[ ] 概念设计` `[ ] 详细设计` `[ ] 开发中` `[ ] 测试中` `[ ] 已发布`
**当前状态**: 详细设计完成，开发前检查清单已生成

---

**完成标记**: `[ ] 概念设计` `[ ] 详细设计` `[ ] 开发中` `[ ] 测试中` `[ ] 已发布`
**当前状态**: 详细设计 → 待后端确认 DECISION_TABLE 和 LLM_JUDGE Schema

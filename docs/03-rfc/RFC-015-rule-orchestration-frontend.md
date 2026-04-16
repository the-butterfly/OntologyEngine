# RFC-015: 规则编排前端实现

> **状态**: updated
> **父 RFC**: RFC-014
> **创建日期**: 2026-04-15
> **最后更新**: 2026-04-16
> **关联**: 后端 Phase 2 规则编排 + 语义空间隔离
> **关联 RFC**: [RFC-016](./RFC-016-rule-orchestration-gap-analysis.md) · [RFC-017](./RFC-017-rule-orchestration-yaml-format.md)

## 摘要

本文档定义规则编排系统的前端实现方案，涵盖 TypeScript 类型定义、API 客户端、自定义 Hooks、Zustand 状态管理和基础页面组件。前端实现遵循语义空间隔离原则，所有 API 调用均需携带 `schema_id` 参数。

## 一、现状与目标

### 1.1 Phase 2-A 实施状态（2026-04-16）

| 组件 | 文件 | 状态 |
|------|------|------|
| TypeScript 类型 | `src/types/rule.ts` | ✅ 完成 |
| API 客户端 | `src/api/ruleGroups.ts` | ✅ 完成 |
| Hooks | `src/hooks/useRuleGroups.ts` | ✅ 完成 |
| Zustand Store | `src/stores/ruleStore.ts` | ✅ 完成 |
| 规则组列表页 | `src/pages/rules/RuleGroupListPage.tsx` | ✅ 完成 |
| 规则组详情页 | `src/pages/rules/RuleGroupDetailPage.tsx` | ✅ 完成 |
| 规则组创建页 | `src/pages/rules/RuleGroupCreatePage.tsx` | ✅ 完成 |
| 规则步骤编辑页 | `src/pages/rules/RuleStepEditPage.tsx` | ✅ 完成 |
| 规则步骤列表 + 拖拽 | `src/components/rule/RuleStepList.tsx` | ✅ 完成 |
| DAG 可视化 | `src/components/rule/RuleChainDAG.tsx` | ✅ 完成（只读） |
| 动作编辑器 | `src/components/rule/ActionEditor.tsx` | ✅ 完成 |
| 条件编辑器 | `src/components/rule/ConditionEditor.tsx` | ✅ 完成 |
| 统一导航入口 | `src/pages/spaces/SpaceDetailPage.tsx` | ✅ 完成 |
| YAML 导入/导出 | UI 层 | ✅ 完成（后端格式待升级，见 RFC-017） |

**待完成（Phase 2-B/C）**：
- G6/X6 画布拖拽排序（`RuleChainDAG` 可编辑模式）
- BFS 上下游路径高亮
- DAG 右侧路径详情面板

### 1.2 目标

本 RFC 定义 Week 4-6 的实施内容：
- **Week 4**: 数据层 + 骨架（类型、API 客户端、Hooks、Store、页面布局） ✅
- **Week 5**: 规则组编辑（RuleGroupListPage、RuleGroupForm） ✅
- **Week 6**: 规则逻辑实例编辑（RuleStepList、ConditionEditor、ActionEditor） ✅

## 二、类型定义（TypeScript）

**文件**: `src/types/rule.ts`

```typescript
// 核心类型定义 - 与后端 RuleGroupDefinition 完全对齐
export interface RuleGroup {
  id: string;                        // UUID
  name: string;                      // 业务名称
  schemaId: string;                  // 语义空间 ID
  description?: string;
  type: 'constraint' | 'inference' | 'alert' | 'decision';
  priority: number;
  appliesTo: AppliesToConfig;
  inputs: IOElement[];
  outputs: IOElement[];
  preconditions: Precondition[];
  enabled: boolean;
}

export interface AppliesToConfig {
  factObjects: string[];
  categories: Record<string, string[]>;
}

export interface IOElement {
  name: string;
  type?: string;
  metric?: string;
  attribute?: string;
  description?: string;
}

export interface Precondition {
  expression: string;
  fail?: Record<string, any>;
}

// 条件从句类型
export type ConditionClause = 
  | { type: 'expression'; expression: string }
  | { type: 'all_of'; subConditions: string[] }
  | { type: 'any_of'; subConditions: string[] };

// 动作从句类型
export interface ActionClause {
  operator: string;
  params: Record<string, any>;
  outputMapping: Record<string, string>;
}

// 规则步骤 - 对应后端 RuleStep
export interface RuleStep {
  id: string;
  ruleGroup: string;                 // 关联 RuleGroup name
  name: string;
  order: number;
  when: ConditionClause;
  then: ActionClause;
  else?: ActionClause;
  enabled: boolean;
  description?: string;
  tags: string[];
}

// 算子类型
export type OperatorName = 
  | 'SET_FLAG' | 'REJECT' | 'COMPUTE' | 'TRIGGER_ALERT'
  | 'BINNING' | 'SCORECARD' | 'WEIGHTED_SUM' 
  | 'DECISION_TABLE' | 'LLM_JUDGE';

// 模拟结果类型
export interface SimulationResult {
  rule_group_name: string;
  steps: StepResult[];
  final_output: Record<string, any>;
  alerts: any[];
  errors: string[];
}

export interface StepResult {
  step_id: string;
  step_name: string;
  condition_result: boolean;
  condition_detail?: {
    type: string;
    expression?: string;
    sub_conditions: any[];
    result: boolean;
    explain: string;
  };
  action_taken?: string;
  output: Record<string, any>;
  error?: string;
  duration_ms: number;
}
```

## 三、API 客户端设计

### 3.1 规则组 API

**文件**: `src/api/ruleGroups.ts`

```typescript
import { apiClient } from './client';

export interface SimulationResult {
  rule_group_name: string;
  steps: StepResult[];
  final_output: Record<string, any>;
  alerts: any[];
  errors: string[];
}

export interface StepResult {
  step_id: string;
  step_name: string;
  condition_result: boolean;
  condition_detail?: {
    type: string;
    expression?: string;
    sub_conditions: any[];
    result: boolean;
    explain: string;
  };
  action_taken?: string;
  output: Record<string, any>;
  error?: string;
  duration_ms: number;
}

export const ruleGroupsApi = {
  list: async (schemaId: string, params?: { enabled?: boolean }) => {
    const query = new URLSearchParams({ schema_id: schemaId });
    if (params?.enabled !== undefined) query.set('enabled', String(params.enabled));
    const response = await apiClient.get(`/rule-groups?${query}`);
    return response.data.rule_groups;
  },

  getById: async (id: string, schemaId?: string) => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    const response = await apiClient.get(`/rule-groups/${id}${query}`);
    return response.data.rule_group;
  },

  create: async (ruleGroup: Partial<RuleGroup>, schemaId: string) => {
    const response = await apiClient.post('/rule-groups', {
      ...ruleGroup,
      schema_id: schemaId,
    });
    return response.data.rule_group;
  },

  update: async (id: string, updates: Partial<RuleGroup>, schemaId?: string) => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    const response = await apiClient.put(`/rule-groups/${id}${query}`, updates);
    return response.data.rule_group;
  },

  delete: async (id: string, schemaId?: string) => {
    const query = schemaId ? `?schema_id=${schemaId}` : '';
    await apiClient.delete(`/rule-groups/${id}${query}`);
  },

  // Nested resources - Rule Steps
  getSteps: async (name: string, schemaId: string) => {
    const response = await apiClient.get(`/rule-groups/${name}/steps?schema_id=${schemaId}`);
    return response.data.steps;
  },

  addStep: async (name: string, step: Partial<RuleStep>, schemaId: string) => {
    const response = await apiClient.post(
      `/rule-groups/${name}/steps?schema_id=${schemaId}`,
      step
    );
    return response.data.step;
  },

  simulate: async (name: string, schemaId: string, entityData: Record<string, any>) => {
    const response = await apiClient.post(
      `/rule-groups/${name}/simulate?schema_id=${schemaId}`,
      { entity_data: entityData }
    );
    return response.data;
  },

  exportYaml: async (name: string, schemaId: string) => {
    const response = await apiClient.get(
      `/rule-groups/${name}/export?schema_id=${schemaId}`
    );
    return response.data.yaml_content;
  },

  importYaml: async (yamlContent: string, schemaId: string) => {
    const response = await apiClient.post('/rule-groups/import', {
      yaml_content: yamlContent,
      schema_id: schemaId,
    });
    return response.data.rule_group;
  },
};
```

### 3.2 算子 API

**文件**: `src/api/operators.ts`

```typescript
import { apiClient } from './client';

export const operatorsApi = {
  list: async () => {
    const response = await apiClient.get('/operators');
    return response.data.operators;
  },

  getSchema: async (operatorName: string) => {
    const response = await apiClient.get(`/operators/${operatorName}/schema`);
    return response.data.schema;
  },
};
```

### 3.3 API 端点映射

| 前端方法 | HTTP | 端点 | 说明 |
|----------|------|------|------|
| list | GET | `/rule-groups?schema_id={id}` | 规则组列表 |
| getById | GET | `/rule-groups/{id}?schema_id={id}` | 规则组详情 |
| create | POST | `/rule-groups` | 创建规则组 |
| update | PUT | `/rule-groups/{id}?schema_id={id}` | 更新规则组 |
| delete | DELETE | `/rule-groups/{id}?schema_id={id}` | 删除规则组 |
| getSteps | GET | `/rule-groups/{name}/steps?schema_id={id}` | 获取规则步骤 |
| addStep | POST | `/rule-groups/{name}/steps?schema_id={id}` | 添加规则步骤 |
| simulate | POST | `/rule-groups/{name}/simulate?schema_id={id}` | 模拟执行 |
| exportYaml | GET | `/rule-groups/{name}/export?schema_id={id}` | YAML 导出 |
| importYaml | POST | `/rule-groups/import` | YAML 导入 |

## 四、组件清单

### 4.1 Week 4 交付物（数据层 + 骨架）

| 组件 | 文件路径 | 说明 |
|------|----------|------|
| TypeScript 类型 | `src/types/rule.ts` | RuleGroup, RuleStep, OperatorName 等 |
| API 客户端 | `src/api/ruleGroups.ts` | 规则组 CRUD + 模拟 + YAML |
| API 客户端 | `src/api/operators.ts` | 算子列表 + schema |
| 自定义 Hook | `src/hooks/useRuleGroups.ts` | useRuleGroups + useSimulation |
| 状态管理 | `src/stores/ruleStore.ts` | Zustand store |
| 页面布局 | `src/pages/rules/RuleGroupLayout.tsx` | 统一布局 + 面包屑 |
| 列表页面 | `src/pages/rules/RuleGroupListPage.tsx` | 规则组表格 + 筛选 |

### 4.2 Week 5 计划（规则组编辑）

| 组件 | 文件路径 | 说明 |
|------|----------|------|
| RuleGroupForm | `src/components/rule/RuleGroupForm.tsx` | Tab 式表单 |
| TargetEntitiesEditor | `src/components/rule/TargetEntitiesEditor.tsx` | 实体类型选择 |
| ApplicabilityEditor | `src/components/rule/ApplicabilityEditor.tsx` | 维度分类编辑 |
| IOElementsForm | `src/components/rule/IOElementsForm.tsx` | 输入输出要素 |

### 4.3 Week 6 计划（规则逻辑实例）

| 组件 | 文件路径 | 说明 |
|------|----------|------|
| RuleStepList | `src/components/rule/RuleStepList.tsx` | 步骤列表 + 拖拽排序 |
| ConditionEditor | `src/components/rule/ConditionEditor.tsx` | 条件编辑器 |
| ActionEditor | `src/components/rule/ActionEditor.tsx` | 动作编辑器 |
| SimulationPanel | `src/components/rule/SimulationPanel.tsx` | 模拟面板 |

## 五、路由设计

```
/rules                                    → RuleGroupListPage
/rules/:groupId                           → RuleGroupDetailPage
  /rules/:groupId/edit                    → RuleGroupEditPage
  /rules/:groupId/steps/:stepId/edit       → RuleStepEditPage
/rules/:schemaId/new                      → RuleGroupCreatePage
```

## 六、实施任务分解

### Week 4 任务（数据层 + 骨架）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|----------|
| 4.1 | 创建 TypeScript 类型定义 | 0.5d | `src/types/rule.ts` 编译通过 |
| 4.2 | 实现 API 客户端层 | 1d | 所有 API 函数签名完成 |
| 4.3 | 创建自定义 Hook | 1d | useRuleGroups 功能完整 |
| 4.4 | 实现 Zustand 状态管理 | 1d | store 可用 |
| 4.5 | 创建基础布局组件 | 0.5d | 页面骨架可用 |
| 4.6 | 配置路由和导航 | 1d | `/rules` 相关路由配置完成 |

### Week 5 任务（规则组编辑）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|----------|
| 5.1 | RuleGroupListPage 实现 | 1.5d | 表格显示 + 筛选 + 分页 |
| 5.2 | RuleGroupForm 基础框架 | 1d | Tab 式布局 |
| 5.3 | TargetEntitiesEditor 组件 | 0.5d | 实体类型多选 |
| 5.4 | ApplicabilityEditor 组件 | 1.5d | 维度分类 + 前置条件 |
| 5.5 | IOElementsForm 组件 | 1d | 输入输出要素列表 |
| 5.6 | 创建/更新页面集成 | 0.5d | 完整流程 |

### Week 6 任务（规则逻辑实例）

| # | 任务 | 工时 | 验收标准 |
|---|------|------|----------|
| 6.1 | RuleStepList 步骤列表 | 1d | 拖拽排序 |
| 6.2 | ConditionEditor 条件编辑器 | 1.5d | 三种条件类型 |
| 6.3 | ActionEditor 动作编辑器 | 1d | 基础动作 + 算子 |
| 6.4 | RuleStepEditorModal 模态框 | 1d | 完整编辑流程 |
| 6.5 | SimulationPanel 模拟面板 | 1d | 测试数据 + 结果展示 |

## 七、验收标准

### 功能验收

- [ ] 用户可以通过页面创建新的规则组
- [ ] 规则组支持四元素配置（作用对象、适用场景、输入、输出）
- [ ] 可在规则组内添加、编辑规则步骤
- [ ] 规则步骤支持 WHEN/THEN/ELSE 结构
- [ ] 可对规则进行模拟执行测试
- [ ] 规则可导出为 YAML 格式
- [ ] 可从 YAML 文件导入规则组
- [ ] 支持规则步骤的拖拽排序
- [ ] 完整的错误处理和用户反馈

### 技术验收

- [ ] TypeScript 编译无错误
- [ ] ESLint 检查通过
- [ ] 组件单元测试覆盖率达标
- [ ] 所有 API 调用携带 `schema_id` 参数

## 八、关键设计决策

### 8.1 语义空间隔离

所有 API 调用必须携带 `schema_id` 参数，确保数据隔离。Store 和 Hook 设计均以 `schemaId` 为必填参数。

### 8.2 状态管理策略

使用 Zustand 进行状态管理，遵循以下原则：
- 异步操作在 store 内部处理
- UI 状态（如 editingStepId）与数据状态分离
- 支持按需加载数据，避免过度获取

### 8.3 组件分层

```
pages/rules/          → 页面容器，处理布局和路由参数
components/rule/      → 可复用业务组件
hooks/               → 数据获取逻辑
stores/              → 全局状态管理
api/                 → API 调用
types/               → TypeScript 类型定义
```

## 九、后续计划

### Phase 2-B 优化项

- 表达式编辑器升级为 Monaco Editor
- 规则画布可视化（拖拽编排）
- 规则模板库
- 版本管理/回滚
- 批量操作

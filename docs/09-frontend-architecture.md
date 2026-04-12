# 前端架构与操作逻辑说明

**文档版本**: v2.0
**更新日期**: 2026-04-12
**适用范围**: OntologyEngine 可视化前端

---

## 0. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.2 | 2026-04-11 | 完成真实数据接入，修复 G6 兼容问题 |
| v2.0 | 2026-04-12 | 管理面/消费面拆分，新路由结构 |

---

## 1. 整体架构

### 1.1 路由结构

前端采用**管理面**和**消费面**完全分离的路由设计：

```
/management/                          # 管理面
├── /                                  # Space 列表
└── /{spaceId}/
    ├── /overview                     # 空间概览
    ├── /schema                       # Schema 编辑器
    │   ├── /L1                      # 事实对象
    │   ├── /L2                      # 分类定义
    │   ├── /L3                      # 分析要素
    │   └── /L4                      # 规则
    │       ├── /definitions          # 声明管理
    │       └── /logics               # 实例管理
    ├── /entities                     # 实体管理
    ├── /datasets                     # 数据集配置
    ├── /versions                     # 版本历史
    ├── /authorizations              # 授权配置
    └── /sync                         # 同步管理

/consumption/                         # 消费面
├── /                                  # 视图列表
└── /{viewId}/
    ├── /overview                     # 视图概览
    ├── /visualize                    # Schema 可视化
    ├── /execute                      # 规则执行
    └── /simulate                     # What-if 模拟
```

### 1.2 模块结构

```
ontology-engine-ui/src/
├── api/
│   ├── management.ts               # 管理面 API 客户端
│   ├── consumption.ts               # 消费面 API 客户端
│   └── visualization.ts            # 可视化 API 客户端
│
├── pages/
│   ├── management/                 # 管理面页面
│   │   ├── ManagementSpacesPage.tsx
│   │   ├── SpaceOverviewPage.tsx
│   │   ├── schema/
│   │   │   ├── L1FactObjectsPage.tsx
│   │   │   ├── L2CategorizationsPage.tsx
│   │   │   ├── L3ElementsPage.tsx
│   │   │   └── L4RulesPage.tsx
│   │   ├── entities/
│   │   │   ├── EntitiesPage.tsx
│   │   │   └── EntityDetailPage.tsx
│   │   ├── datasets/
│   │   │   ├── DatasetsPage.tsx
│   │   │   ├── DatasetDetailPage.tsx
│   │   │   └── SyncHistoryPage.tsx
│   │   ├── versions/
│   │   │   └── VersionsPage.tsx
│   │   ├── authorizations/
│   │   │   └── AuthorizationsPage.tsx
│   │   └── sync/
│   │       └── SyncConfigPage.tsx
│   │
│   └── consumption/                # 消费面页面
│       ├── ConsumptionViewsPage.tsx
│       ├── ViewOverviewPage.tsx
│       ├── visualize/
│       │   └── SchemaVisualizationPage.tsx
│       ├── execute/
│       │   └── RuleExecutionPage.tsx
│       └── simulate/
│           └── SimulationPage.tsx
│
├── components/
│   ├── management/                 # 管理面组件
│   │   ├── schema/
│   │   │   ├── FactObjectEditor.tsx
│   │   │   ├── CategorizationEditor.tsx
│   │   │   ├── ElementEditor.tsx
│   │   │   ├── RuleDefinitionEditor.tsx
│   │   │   └── RuleLogicEditor.tsx
│   │   ├── dataset/
│   │   │   ├── DatasetForm.tsx
│   │   │   ├── MappingRuleEditor.tsx
│   │   │   └── SyncConfigForm.tsx
│   │   └── version/
│   │       ├── VersionHistory.tsx
│   │       └── VersionCompare.tsx
│   │
│   └── consumption/                # 消费面组件
│       ├── schema/
│       │   ├── SchemaGraph.tsx     # G6 图谱
│       │   ├── NodeDetailPanel.tsx
│       │   └── MetricScorecard.tsx
│       ├── rule/
│       │   ├── RuleChainDAG.tsx    # G6 规则链
│       │   ├── ExecutionReplay.tsx
│       │   └── StepDetailPanel.tsx
│       └── simulation/
│           ├── VariableOverride.tsx
│           └── ImpactAnalysis.tsx
│
├── stores/                         # Zustand 状态管理
│   ├── managementStore.ts         # 管理面状态
│   ├── consumptionStore.ts        # 消费面状态
│   └── spaceStore.ts              # (保留) 语义空间状态
│
└── types/
    ├── management.ts              # 管理面类型定义
    └── consumption.ts             # 消费面类型定义
```

---

## 2. 页面详情

### 2.1 管理面页面

#### 2.1.1 Space 列表页 (`/management/`)

```
┌──────────────────────────────────────────────────────────────┐
│  OntologyEngine / 管理                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [+ 创建管理空间]                                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  供应链金融空间                              [ACTIVE] │   │
│  │  ID: space_supply_chain                            │   │
│  │  状态: ACTIVE │ 版本: v3 │ 实体: 150 │ 规则: 12   │   │
│  │  创建时间: 2026-04-01                               │   │
│  │  [进入管理] [授权配置] [归档]                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  电商信用空间                                [DRAFT] │   │
│  │  ...                                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 2.1.2 Schema 编辑器 (`/management/{spaceId}/schema/`)

Tab 切换 L1/L2/L3/L4，或使用左侧导航：

```
┌──────────────────────────────────────────────────────────────┐
│  供应链金融空间 / Schema 编辑器                                │
├──────────────────────────────────────────────────────────────┤
│  [L1 事实对象] [L2 分类] [L3 要素] [L4 规则]                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌───────────────────────────────┐   │
│  │ Fact Objects     │  │ 编辑面板                        │   │
│  │                  │  │                                │   │
│  │ ┌──────────────┐ │  │  ID: Supplier                  │   │
│  │ │ Supplier    ▼│ │  │  Name: 供应商                   │   │
│  │ └──────────────┘ │  │                                │   │
│  │ ┌──────────────┐ │  │  Properties:                   │   │
│  │ │ CoreEnt     │ │  │  ┌──────────────────────────┐  │   │
│  │ └──────────────┘ │  │  │ registered_capital (F)  │  │   │
│  │ ┌──────────────┐ │  │  │ annual_revenue (F)      │  │   │
│  │ │ Invoice     │ │  │  │ employee_count (I)       │  │   │
│  │ └──────────────┘ │  │  └──────────────────────────┘  │   │
│  │                  │  │                                │   │
│  │ [+ 添加]         │  │  Relations:                     │   │
│  └──────────────────┘  │  ┌──────────────────────────┐  │   │
│                         │  │ supplies → CoreEnterprise│  │   │
│                         │  └──────────────────────────┘  │   │
│                         │                                │   │
│                         │  [保存] [删除]                  │   │
│                         └───────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 2.1.3 规则声明与实例编辑 (`/management/{spaceId}/schema/L4/`)

```
┌──────────────────────────────────────────────────────────────┐
│  L4 规则 / 授信额度计算 (R001)                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [声明] [实例: 2个]                                           │
│                                                              │
│  ┌──────────────────┐  ┌───────────────────────────────┐   │
│  │ 规则声明         │  │ 编辑面板                        │   │
│  │                  │  │                                │   │
│  │ 声明信息:        │  │ ID: R001_credit_limit          │   │
│  │ - ID: R001      │  │ Name: 授信额度计算             │   │
│  │ - 类型: decision │  │ Type: decision                 │   │
│  │ - 优先级: 100   │  │ Priority: [100]                │   │
│  │                  │  │                                │   │
│  │ 作用对象:        │  │ Target Objects:                │   │
│  │ - Supplier      │  │ ☑ Supplier                     │   │
│  │ - CoreEnterprise│  │ ☑ CoreEnterprise               │   │
│  │                  │  │                                │   │
│  │ 输入要素:        │  │ Input Elements:                │   │
│  │ - credit_score │  │ [+ 添加]                        │   │
│  │ - net_asset    │  │ - credit_score (metric)         │   │
│  │                  │  │ - net_asset (metric)           │   │
│  │ 输出要素:        │  │                                │   │
│  │ - credit_limit │  │ Output Elements:                │   │
│  │ - risk_level   │  │ [+ 添加]                        │   │
│  └──────────────────┘  └───────────────────────────────┘   │
│                                                              │
│  规则实例 (2个):                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ R001_logic_manufacturing (制造业)     [优先: 100]  │   │
│  │ When: credit_score >= 60 AND net_asset >= 5M      │   │
│  │ Then: credit_limit = net_asset * 0.5              │   │
│  │ [编辑] [删除]                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ R001_logic_retail (批发零售)        [优先: 100]   │   │
│  │ When: credit_score >= 70 AND net_asset >= 2M      │   │
│  │ Then: credit_limit = net_asset * 0.3              │   │
│  │ [编辑] [删除]                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 2.1.4 数据集配置 (`/management/{spaceId}/datasets/`)

```
┌──────────────────────────────────────────────────────────────┐
│  供应链金融空间 / 数据集管理                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [+ 注册数据集]                                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ERP 供应商数据                                 [ACTIVE]│   │
│  │ Type: PostgreSQL │ Records: 1,500 │ Last Sync: ... │   │
│  │ [配置映射] [同步] [编辑] [删除]                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ CRM 客户数据                                    [ACTIVE]│   │
│  │ Type: MySQL │ Records: 3,200 │ Last Sync: ...      │   │
│  │ [配置映射] [同步] [编辑] [删除]                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 消费面页面

#### 2.2.1 视图概览 (`/consumption/{viewId}/`)

```
┌──────────────────────────────────────────────────────────────┐
│  消费视图 / 供应链金融总览                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  来源: space_supply_chain (管理空间 A)                        │
│  授权: L1(Supplier,CoreEnt), L3(全部), L4(全部)             │
│                                                              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐              │
│  │  实体数     │ │  指标数    │ │  规则数    │              │
│  │   150      │ │    28      │ │    12      │              │
│  └────────────┘ └────────────┘ └────────────┘              │
│                                                              │
│  [进入可视化] [执行规则] [What-if 模拟]                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 2.2.2 Schema 可视化 (`/consumption/{viewId}/visualize/`)

（与 v1.2 一致，细节见原文档）

#### 2.2.3 规则执行 (`/consumption/{viewId}/execute/`)

（与 v1.2 一致，细节见原文档）

#### 2.2.4 What-if 模拟 (`/consumption/{viewId}/simulate/`)

（与 v1.2 一致，细节见原文档）

---

## 3. 数据流链路

### 3.1 管理面数据流

```
用户操作 → 前端组件 → managementStore → management.ts API
                                                        │
                                                        ▼
                                              FastAPI /v1/management/
                                                        │
                                                        ▼
                                              VisualizationService / Storage
```

### 3.2 消费面数据流

```
用户操作 → 前端组件 → consumptionStore → consumption.ts API
                                                      │
                                                      ▼
                                            FastAPI /v1/consumption/
                                                      │
                                                      ▼
                                            VisualizationService / Storage
```

---

## 4. 状态管理

### 4.1 managementStore

```typescript
interface ManagementState {
  // 当前空间
  currentSpace: SemanticSpace | null;

  // Schema 状态
  L1_fact_objects: FactObject[];
  L2_categorizations: Categorization[];
  L3_analytical_elements: AnalyticalElement[];
  L4_rule_definitions: RuleDefinition[];
  L4_rule_logics: RuleLogic[];

  // 加载状态
  loading: {
    space: boolean;
    schema: boolean;
    entities: boolean;
  };

  // Actions
  loadSpace: (spaceId: string) => Promise<void>;
  saveFactObject: (obj: FactObject) => Promise<void>;
  // ...
}
```

### 4.2 consumptionStore

```typescript
interface ConsumptionState {
  // 当前视图
  currentView: ConsumptionView | null;

  // 视图数据
  authorizedLayers: AuthorizedLayers;
  entities: Entity[];
  ruleDefinitions: RuleDefinition[];

  // 执行状态
  executionResult: ExecutionResult | null;

  // Actions
  loadView: (viewId: string) => Promise<void>;
  executeAnalyze: (entityId: string, dimension: string) => Promise<void>;
  executeSimulate: (entityId: string, overrides: Record<string, any>) => Promise<void>;
  // ...
}
```

---

## 5. 组件清单

### 5.1 管理面组件

| 组件 | 页面 | 说明 |
|------|------|------|
| `FactObjectEditor` | L1 | 事实对象编辑器 |
| `CategorizationEditor` | L2 | 分类定义编辑器 |
| `ElementEditor` | L3 | 分析要素编辑器 |
| `RuleDefinitionEditor` | L4 | 规则声明编辑器 |
| `RuleLogicEditor` | L4 | 规则实例编辑器 |
| `DatasetForm` | datasets | 数据集配置表单 |
| `MappingRuleEditor` | datasets | 字段映射编辑器 |
| `SyncConfigForm` | datasets | 同步配置表单 |
| `VersionHistory` | versions | 版本历史列表 |
| `VersionCompare` | versions | 版本对比组件 |
| `AuthorizationForm` | authorizations | 授权配置表单 |

### 5.2 消费面组件

| 组件 | 页面 | 说明 |
|------|------|------|
| `SchemaGraph` | visualize | G6 Schema 图谱 |
| `NodeDetailPanel` | visualize | 节点详情面板 |
| `MetricScorecard` | visualize | 评分卡组件 |
| `RuleChainDAG` | execute | G6 规则链图 |
| `ExecutionReplay` | execute | 执行回放控制 |
| `StepDetailPanel` | execute | 步骤详情面板 |
| `VariableOverride` | simulate | What-if 变量覆盖 |
| `ImpactAnalysis` | simulate | 影响路径分析 |

---

## 6. API 客户端

### 6.1 management.ts

```typescript
// Space 管理
createSpace(data: CreateSpaceRequest): Promise<Space>
updateSpace(spaceId: string, data: UpdateSpaceRequest): Promise<Space>
activateSpace(spaceId: string): Promise<void>
archiveSpace(spaceId: string): Promise<void>

// Schema 管理
getSchema(spaceId: string): Promise<SemanticSpaceLayers>
saveFactObject(spaceId: string, obj: FactObject): Promise<void>
saveCategorization(spaceId: string, cat: Categorization): Promise<void>
// ...

// Dataset 管理
createDataset(spaceId: string, dataset: Dataset): Promise<Dataset>
triggerSync(spaceId: string, datasetId: string, mode: SyncMode): Promise<SyncResult>

// 版本管理
createSnapshot(spaceId: string, layer: string): Promise<VersionRecord>
rollbackToVersion(spaceId: string, layer: string, version: number): Promise<void>

// 授权管理
createAuthorization(spaceId: string, auth: Authorization): Promise<Authorization>
```

### 6.2 consumption.ts

```typescript
// View 管理
createView(data: CreateViewRequest): Promise<ConsumptionView>
getView(viewId: string): Promise<ConsumptionView>

// 可视化
getSchemaGraph(viewId: string, graphType: GraphType): Promise<GraphData>
getRuleChain(viewId: string, dimension: string): Promise<RuleChainData>

// 执行
executeAnalyze(viewId: string, entityId: string, dimension: string): Promise<ExecutionResult>
executeSimulate(viewId: string, entityId: string, overrides: Record<string, any>): Promise<SimulationResult>

// 查询
queryEntities(viewId: string, filters?: EntityFilters): Promise<Entity[]>
getMetricSnapshot(viewId: string, entityId: string): Promise<MetricSnapshot>
```

---

*文档结束*

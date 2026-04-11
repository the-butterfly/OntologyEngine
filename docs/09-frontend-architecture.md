# 前端架构与操作逻辑说明

**文档版本**: v1.2
**更新日期**: 2026-04-11
**适用范围**: OntologyEngine 可视化前端

---

## 0. 已知问题修复记录

### 2026-04-11 修复

| # | 问题 | 修复方案 | 影响文件 |
|---|------|----------|----------|
| 1 | EntityNotFoundError: SUP_2024_001 | server.py 启动时加载 instances.yaml | `ontology_engine/api/server.py` |
| 2 | RuleChainDAG 画布重影 | 销毁前清理容器 DOM 元素 | `RuleChainDAG.tsx` |
| 3 | 实体关系图平行边重叠 | 使用 `cubic-vertical/horizontal` 边类型 + curveOffset | `SchemaGraph.tsx` |
| 4 | 导出 PNG 文件损坏 | `exportImage` 改为返回 `Promise<string \| null>` (G6 5.x async) | `SchemaGraph.tsx` |
| 5 | `MetricScorecard` 显示 Mock 数据 | 新增实体列表/指标快照 API，评分卡直接读取真实快照，规则链页面改为动态实体选择 | `visualization.py`, `visualization_service.py`, `visualization.ts`, `MetricScorecard.tsx`, `RuleChainPage.tsx`, `SchemaPage.tsx` |

---

## 1. 数据流链路

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (React + Vite)                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  SchemaPage │    │ RuleChain   │    │   SimulationPage    │  │
│  │  (Schema图)  │    │   Page      │    │    (What-if模拟)     │  │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘  │
│         │                  │                      │             │
│         └──────────────────┼──────────────────────┘             │
│                            ▼                                    │
│              ┌─────────────────────────┐                        │
│              │   api/visualization.ts  │  ← API 客户端层         │
│              │   (axios HTTP client)   │                        │
│              └───────────┬─────────────┘                        │
└──────────────────────────┼──────────────────────────────────────┘
                           │ HTTP/JSON
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      后端 (FastAPI + Python)                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  API Routes │───▶│Visualization│───▶│  SchemaGraphBuilder │  │
│  │/v1/visualize│    │  Service    │    │  (构建图数据)         │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                               │                 │
│                                               ▼                 │
│                              ┌─────────────────────────────┐    │
│                              │   KGML Schema (内存中)       │    │
│                              │  examples/supply_chain_...  │    │
│                              └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 数据来源确认

**✅ 真实数据，非 Mock**

| 层级 | 数据来源 | 说明 |
|------|----------|------|
| Schema 定义 | `examples/supply_chain_finance/schema.yaml` | 后端启动时加载 |
| 实体数据 | `examples/supply_chain_finance/instances.yaml` | `server.py` 启动时通过 `InstanceLoader` 加载到 DuckDB |
| 实体下拉选项 | `VisualizationService.list_entities()` | `SchemaPage` / `RuleChainPage` 动态拉取实体，不再硬编码实体 ID |
| 指标快照 | `VisualizationService.get_metric_snapshot()` | `MetricScorecard` 基于真实计算结果渲染评分、等级、雷达图和权重贡献 |
| 图结构 | `SchemaGraphBuilder` 实时构建 | 基于 KGML Schema 定义 |
| 规则链 | `RuleChainGraphBuilder` 实时构建 | 基于规则优先级和依赖 |

**实体加载流程** (server.py lifespan):
```python
instance_loader = InstanceLoader()
instances_path = "examples/supply_chain_finance/instances.yaml"
entities, relations = instance_loader.load(instances_path)
for entity in entities:
    await storage.save_entity(entity)
for relation in relations:
    await storage.save_relation(relation)
```

**数据流验证**:
```bash
# 前端 API 调用路径
Frontend: /v1/visualize/schema/graph?graph_type=entity_relation
         ↓ (Vite 代理)
Backend:  http://localhost:8000/v1/visualize/schema/graph
         ↓
Service:  VisualizationService.get_schema_graph()
         ↓
Builder:  SchemaGraphBuilder.build()
         ↓
Source:   KGMLSchema (加载自 schema.yaml)
```

---

## 2. 组件架构

### 2.1 目录结构

```
ontology-engine-ui/src/
├── api/
│   └── visualization.ts          # API 客户端
├── components/
│   ├── schema/                   # Schema 相关组件
│   │   ├── SchemaGraph.tsx       # G6 图谱组件
│   │   ├── NodeDetailPanel.tsx   # 节点详情面板
│   │   ├── MetricScorecard.tsx   # 评分卡组件
│   │   └── index.ts              # 导出
│   └── rule/                     # 规则链相关组件
│       ├── RuleChainDAG.tsx      # 规则 DAG 图
│       ├── ExecutionReplay.tsx   # 执行回放控制
│       ├── StepDetailPanel.tsx   # 步骤详情面板
│       └── index.ts              # 导出
├── pages/
│   ├── SchemaPage.tsx            # Schema 可视化页面
│   ├── RuleChainPage.tsx         # 规则链页面
│   └── SimulationPage.tsx        # 模拟页面
├── stores/                       # Zustand 状态管理
├── utils/
│   ├── colorSchemes.ts           # 配色方案
│   └── labelMappings.ts          # 中文标签映射
└── types/
    └── visualization.ts          # TypeScript 类型定义
```

### 2.2 组件职责

| 组件 | 职责 | 关键 Props |
|------|------|------------|
| `SchemaGraph` | 渲染 G6 图谱，处理交互 | `data`, `onNodeClick`, `onNodeHover` |
| `NodeDetailPanel` | 展示选中节点详情 | `node`, `onMetricClick` |
| `MetricScorecard` | 基于真实指标快照展示评分卡与权重贡献 | `node`, `entityId`, `dimension` |
| `RuleChainDAG` | 规则链 DAG 图与执行态叠加 | `chainData`, `executionSteps`, `currentStep`, `onNodeClick` |
| `ExecutionReplay` | 回放控制面板 | `steps`, `onStepChange` |
| `StepDetailPanel` | 执行步骤详情 | `step`, `comparison` |

---

## 3. 页面操作逻辑

### 3.1 SchemaPage (Schema 可视化)

```
┌──────────────────────────────────────────────────────────────┐
│  [实体关系] [指标依赖] [全景图] [规则概览]    [搜索] [导出]    │ ← 工具栏
├────────────────────────────────────┬─────────────────────────┤
│                                    │                         │
│         ┌──────────────┐           │   ┌─────────────────┐   │
│         │   供应商      │           │   │ 节点详情 / 评分卡 │   │
│         └──────┬───────┘           │   │                 │   │
│                │                   │   │ - 类型: 实体      │   │
│         ┌──────┴───────┐           │   │ - 属性数: 8      │   │
│         │   发票        │           │   │ - 关键属性...    │   │
│         └──────────────┘           │   │                 │   │
│                                    │   └─────────────────┘   │
│         G6 图 (可拖拽/缩放)          │                         │
│                                    │                         │
├────────────────────────────────────┴─────────────────────────┤
│  实体: 5  指标: 18  规则: 9  关系: 42                         │ ← 统计栏
└──────────────────────────────────────────────────────────────┘
```

**操作流程**:
1. **切换视图**: 点击顶部 Segmented 控件切换 4 种图类型
2. **图层过滤**: 通过 Checkbox 控制显示 L1/L3/L4 层
3. **节点交互**:
   - 点击节点 → 右侧面板显示详情
   - 悬停节点 → 高亮相关节点和边
   - 拖拽画布 → 移动视图
   - 滚轮 → 缩放
4. **搜索**: 输入节点 ID 或标签，回车定位
5. **选择实体**: 通过右上角实体下拉框切换当前实体，评分卡显示对应真实指标快照
6. **导出**: 将当前画布导出为 PNG

**视图类型说明**:

| 视图 | 显示内容 | 图层 | 边类型 |
|------|----------|------|--------|
| 实体关系 | 5个核心实体 | L1 | 实体关联关系 |
| 指标依赖 | 18个指标 + 勾稽权重 | L3 | 指标依赖 (实线) + 权重标签 |
| 全景图 | 所有层级 | L1+L3+L4 | 所有边类型 |
| 规则概览 | 9条规则 + 执行顺序 | L4 | 规则执行流 (橙色) |

### 3.2 RuleChainPage (规则链执行)

```
┌──────────────────────────────────────────────────────────────┐
│  [授信评估] [准入评估] ...      实体: [供应商 ▼] [加载执行] │
├────────────────────────────────────┬─────────────────────────┤
│                                    │                         │
│    ┌─────┐                        │   ┌─────────────────┐   │
│    │ R001 │──┐                     │   │   执行步骤详情    │   │
│    └──┬──┘  │                     │   │                 │   │
│       │     │                     │   │ Step 3/6        │   │
│       ▼     │                     │   │ 担保圈风险检测    │   │
│    ┌─────┐  │                     │   │ Status: passed  │   │
│    │ R002 │  │                     │   │                 │   │
│    └──┬──┘  │                     │   │ 条件拆解:        │   │
│       │     └────▶ ┌─────┐        │   │ - 条件1: ✓      │   │
│       ▼            │ R007 │        │   │ - 条件2: ✓      │   │
│    ┌─────┐         └──┬──┘        │   │                 │   │
│    │ R003 │            │           │   │ 输入/输出...     │   │
│    └─────┘            ▼           │   │                 │   │
│                    ┌─────┐        │   └─────────────────┘   │
│                    │ ... │        │                         │
│                    └─────┘        │   ┌─────────────────┐   │
│                                   │   │    执行回放      │   │
│        规则 DAG 图 (G6)            │   │  [◀] [▶] [⏸]   │   │
│                                   │   │  进度: [████░░]  │   │
│                                   │   └─────────────────┘   │
└───────────────────────────────────┴─────────────────────────┘
```

**操作流程**:
1. **选择维度**: Segmented 控件切换评估维度
2. **选择实体**: 从下拉列表选择要评估的实体，页面通过 `/v1/visualize/entities` 拉取候选项后点击“加载执行”
3. **查看DAG**: 规则按优先级从上到下排列，边表示数据依赖
4. **查看执行结果**: 节点颜色表示执行状态 (passed/failed/executing)
5. **步骤回放**: 使用底部控制面板逐步查看执行过程
6. **查看详情**: 点击节点查看该步骤的详细执行快照

### 3.3 SimulationPage (What-if 模拟)

```
┌──────────────────────────────────────────────────────────────┐
│  维度: [授信评估 ▼]  实体: [ENT_001]  [运行模拟]               │
├────────────────────────────────────┬─────────────────────────┤
│  ┌─────────────────────────────┐   │   ┌─────────────────┐   │
│  │ 变量覆盖 (What-if)           │   │   │   模拟结果       │   │
│  │                             │   │   │                 │   │
│  │ total_invoice_amount_90d    │   │   │ Decision:       │   │
│  │ [ 500000 ] [x]              │   │   │ APPROVE_WITH... │   │
│  │                             │   │   │                 │   │
│  │ overdue_invoice_ratio       │   │   │ Final Score: 78 │   │
│  │ [ 0.05    ] [x]             │   │   │                 │   │
│  │                             │   │   │ [查看对比详情]   │   │
│  │ [+ 添加变量]                │   │   │                 │   │
│  └─────────────────────────────┘   │   └─────────────────┘   │
│                                    │                         │
│  ┌─────────────────────────────┐   │   ┌─────────────────┐   │
│  │       影响路径分析           │   │   │    变更明细      │   │
│  │                             │   │   │                 │   │
│  │ credit_score ──▶ decision   │   │   │ 触发新预警:     │   │
│  │    ↓              ↓         │   │   │ - R005 高风险   │   │
│  │ credit_limit    final_...   │   │   │                 │   │
│  │                             │   │   │ credit_limit    │   │
│  │ 变更幅度: -79.2%            │   │   │  100万 → 20万   │   │
│  └─────────────────────────────┘   │   └─────────────────┘   │
└────────────────────────────────────┴─────────────────────────┘
```

**操作流程**:
1. **选择维度**: 选择要模拟的评估维度
2. **输入实体ID**: 指定要模拟的实体
3. **设置变量覆盖**: 添加要修改的指标值 (What-if 场景)
4. **运行模拟**: 点击按钮执行模拟
5. **查看结果**:
   - 决策结果 (APPROVE/REJECT 等)
   - 最终评分
   - 与基准的对比
6. **影响分析**: 查看变更的传播路径和影响幅度

---

## 4. 关键技术实现

### 4.1 G6 图生命周期管理

**问题**: React 严格模式下组件双重渲染导致 G6 实例未正确销毁，产生"重影"

**解决方案**:
```typescript
// 1. 完整的清理函数 - 确保 DOM 元素也被清除
const cleanupGraph = useCallback(() => {
  isDestroyedRef.current = true;

  if (graphRef.current) {
    graphRef.current.destroy();
    graphRef.current = null;
  }

  // 清理容器中的所有子元素 (G6 会创建多个 canvas/layer)
  if (containerRef.current) {
    while (containerRef.current.firstChild) {
      containerRef.current.removeChild(containerRef.current.firstChild);
    }
  }
}, []);

// 2. renderGraph 开头也清理容器
const renderGraph = useCallback(async () => {
  // 销毁前先清理容器
  if (containerRef.current) {
    while (containerRef.current.firstChild) {
      containerRef.current.removeChild(containerRef.current.firstChild);
    }
  }
  // ... 然后创建新 graph
}, []);

// 3. useEffect 正确管理生命周期
useEffect(() => {
  isDestroyedRef.current = false;
  if (data && !loading) {
    renderGraph(data);
  }
  return () => cleanupGraph();
}, [data, loading, renderGraph, cleanupGraph]);
```

### 4.2 数据过滤与边有效性

**问题**: 切换视图时，边可能引用不存在的节点，导致 G6 报错

**解决方案**:
```typescript
// 后端过滤 (builders.py)
node_ids = {n.id for n in nodes}
for edge in edges:
    if edge.source in node_ids and edge.target in node_ids:
        unique_edges.append(edge)

// 前端二次过滤 (transformToG6)
const nodeIds = new Set(nodes.map(n => n.id));
edges: edges.filter(edge => 
  nodeIds.has(edge.source) && nodeIds.has(edge.target)
)
```

### 4.3 规则执行流边生成

**问题**: 规则概览视图下规则节点孤立，没有展示执行顺序

**解决方案**:
```python
def _build_rule_execution_flow_edges(self) -> list[GraphEdge]:
    # 1. 按优先级排序规则
    rules = sorted(rules, key=lambda r: (-r.priority, r.id))
    
    # 2. 添加已知的数据流依赖
    KNOWN_RULE_FLOWS = [
        ("R001", "R002", "基础准入后→信用评分"),
        ("R002", "R004", "信用评分后→额度计算"),
        # ...
    ]
    
    # 3. 为无依赖的规则添加顺序边
    for i in range(len(rules) - 1):
        if (rules[i].id, rules[i+1].id) not in existing_edges:
            edges.append(rule_flow_edge)
```

---

## 5. 配色与样式规范

### 5.1 节点配色

| 类型 | 背景色 | 边框色 | 用途 |
|------|--------|--------|------|
| 实体 | `#E8F4FD` | `#1890FF` | L1 实体概念 |
| 原子指标 | `#F6FFED` | `#52C41A` | L3 原子指标 |
| 派生指标 | `#FFF7E6` | `#FA8C16` | L3 派生指标 |
| 复合指标 | `#F9F0FF` | `#722ED1` | L3 复合指标 |
| 图指标 | `#FFF1F0` | `#F5222D` | L3 图算法指标 |
| 约束规则 | `#FFF1F0` | `#F5222D` | L4 约束规则 |
| 推理规则 | `#E6F7FF` | `#1890FF` | L4 推理规则 |
| 预警规则 | `#FFF7E6` | `#FA8C16` | L4 预警规则 |
| 决策规则 | `#F6FFED` | `#52C41A` | L4 决策规则 |

### 5.2 边配色

| 类型 | 颜色 | 线型 | 用途 |
|------|------|------|------|
| 实体关系 | `#A0A0A0` | 实线 | 实体关联 |
| 指标依赖 | `#722ED1` | 虚线 | L3 指标计算依赖 |
| 规则输入 | `#1890FF` | 点线 | 指标→规则数据流 |
| 规则执行流 | `#FA8C16` | 实线 | 规则间执行顺序 |

### 5.3 状态色

| 状态 | 颜色 | 说明 |
|------|------|------|
| passed | `#52C41A` | 规则通过 |
| failed | `#F5222D` | 规则失败 |
| executing | `#1890FF` | 执行中 |
| pending | `#D9D9D9` | 待执行 |
| skipped | `#FA8C16` | 跳过 |

---

## 6. API 端点清单

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/visualize/schema/graph` | GET | 获取 Schema 图数据 |
| `/v1/visualize/entities` | GET | 获取实体下拉选项，可按概念和维度过滤 |
| `/v1/visualize/metrics/{entity_id}` | GET | 获取实体在指定维度下的真实指标快照 |
| `/v1/visualize/rule-chain/{dimension}` | GET | 获取规则链 DAG |
| `/v1/visualize/simulate` | POST | 执行 What-if 模拟 |
| `/v1/visualize/execution/{entity_id}/{dimension}` | GET | 获取执行追踪 |

### 6.1 实体与指标快照响应结构

```typescript
interface VisualizationEntityOption {
  entity_id: string;
  concept_type: string;
  label: string;
  active_dimensions: string[];
}

interface MetricSnapshot {
  entity_id: string;
  dimension: string;
  metrics: Record<string, any>;
  outputs: Record<string, any>;
  decision: string | null;
  decision_reasoning: string | null;
}
```

### 6.2 SimulationResult 响应结构

```typescript
interface SimulationResult {
  entity_id: string;
  dimension: string;
  simulation_type: 'dry_run' | 'what_if';
  steps: ExecutionStepSnapshot[];      // 每步执行快照
  execution_path: string[];            // 执行的规则ID序列
  skipped_rules: string[];             // 跳过的规则
  final_outputs: Record<string, any>; // 最终决策输出 (eligible, credit_score 等)
  decision: string | null;            // REJECT / APPROVE / APPROVE_WITH_CONDITIONS
  decision_reasoning: string | null;  // 决策原因
  alerts: Alert[];                     // 预警列表
  comparison: ComparisonResult | null;  // What-if 对比结果 (仅 what_if 模式)
  final_context: {                     // ✅ 完整计算上下文 (含子指标)
    entity_data: Record<string, any>;  // 实体原始数据
    computed_metrics: Record<string, any>; // 所有计算的指标 (含中间子指标)
  };
}
```

---

## 7. 调试指南

### 7.1 常见问题排查

**问题1**: 页面空白，控制台报错 `Cannot read properties of undefined (reading 'map')`
- **原因**: API 响应结构错误
- **解决**: 检查后端是否返回 `{ data: { nodes: [], edges: [] } }` 结构

**问题2**: 画布出现重影
- **原因**: G6 实例未正确销毁
- **解决**: 检查 cleanupGraph 是否被调用，DOM 中的 canvas 是否被清除

**问题3**: 切换视图后节点孤立
- **原因**: 边引用的节点不在当前图层
- **解决**: 检查 builders.py 的边过滤逻辑

**问题4**: Spin 组件警告 `tip only work in nest or fullscreen pattern`
- **原因**: antd Spin tip 属性使用错误
- **解决**: 使用嵌套子元素模式 `<Spin><div>...</div></Spin>`

**问题5**: Ant Design Card 组件警告 `headStyle is deprecated`
- **原因**: antd v5 中 `headStyle` 属性已弃用
- **解决**: 改为 `styles={{ header: { ... } }}` 新 API

**问题6**: 导出按钮点击无响应或下载文件损坏
- **原因**: G6 5.x 的 `toDataURL()` 返回 `Promise<string>` 而非同步 string
- **解决**: `exportImage` 方法改为 `async`，返回 `Promise<string | null>`

```typescript
// SchemaGraphRef 接口
export interface SchemaGraphRef {
  exportImage: () => Promise<string | null>;  // G6 5.x 是异步的
}

// SchemaPage 调用
const handleExport = async () => {
  const dataUrl = await graphRef.current?.exportImage();
  if (dataUrl) {
    // download
  }
};
```

**问题7**: 两个节点间多条边重叠
- **原因**: G6 默认直线边在同节点对间会重叠
- **解决**: 使用 `cubic-vertical` (TB布局) 或 `cubic-horizontal` (LR布局) 边类型，通过 `curveOffset` 使边呈扇形分布

```typescript
// SchemaGraph.tsx edge type
type: (d: any) => {
  if (graphData.layout_config?.rankdir === 'TB') {
    return 'cubic-vertical';  // 支持 curveOffset
  }
  return 'cubic-horizontal';
},
style: {
  curveOffset: (d: any) => d.data?.curveOffset || 0,
}
```

**问题8**: 规则概览视图节点孤立
- **原因**: 只显示 L4 规则节点，缺少规则间执行顺序边
- **解决**: 后端添加 `_build_rule_execution_flow_edges()` 生成规则流边

### 7.2 日志检查

```typescript
// 前端数据检查
console.log('API Response:', res.data);
console.log('Nodes count:', data?.nodes?.length);
console.log('Edges count:', data?.edges?.length);

// G6 数据检查
console.log('G6 Data:', g6Data);
console.log('Node IDs:', Array.from(nodeIds));
```

---

*文档结束*

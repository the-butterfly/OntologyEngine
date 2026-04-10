# 前端详细设计 - React + AntV 可视化系统

> **目录**: `ontology-engine-ui/`
> **技术栈**: React 18 + Vite 5 + TypeScript 5 + AntV G6 5.x + X6 2.x + Ant Design 5

## 一、项目搭建

### 1.1 初始化

```bash
cd /Volumes/Extension/Projects/CodeDev/OntologyEngine
npm create vite@latest ontology-engine-ui -- --template react-ts
cd ontology-engine-ui
npm install
```

### 1.2 依赖安装

```bash
# 图可视化
npm install @antv/g6 @antv/x6 @antv/x6-plugin-selection @antv/x6-plugin-snapline

# UI
npm install antd @ant-design/icons

# 状态管理
npm install zustand

# HTTP
npm install axios

# 路由
npm install react-router-dom
```

### 1.3 Vite 配置

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

## 二、页面布局

### 2.1 整体布局 (AppLayout)

```
┌─────────────────────────────────────────────────────────────┐
│  🏗️ OntologyEngine                     [Schema] [规则] [模拟] │  ← Header + 导航
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  主内容区域 (根据路由切换)                                      │
│                                                               │
│  /schema  → SchemaPage                                       │
│  /rules   → RuleChainPage                                    │
│  /simulate → SimulationPage                                  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 SchemaPage 布局

```
┌─────────────────────────────────────────────────────────────┐
│  Schema 可视化                                               │
│  [实体关系] [指标依赖(勾稽)] [全景] [规则概览]    🔍 搜索     │
├──────────────────────────────────────────────┬──────────────┤
│                                              │              │
│                                              │  EntityDetail│
│           G6 SchemaGraph                     │  / MetricInfo│
│           (主视图区)                          │  / RuleInfo  │
│                                              │  (右侧面板)  │
│                                              │              │
│                                              │              │
├──────────────────────────────────────────────┴──────────────┤
│  [L1✓] [L2✓] [L3✓] [L4✓]   层级过滤   [导出PNG] [导出SVG]   │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 RuleChainPage 布局

```
┌─────────────────────────────────────────────────────────────┐
│  规则链可视化              维度: [credit_assessment ▼]        │
├──────────────────────────────────────────────┬──────────────┤
│                                              │              │
│           X6 RuleChainDAG                    │  StepSnapshot│
│           (规则链 DAG)                        │  (步骤详情)  │
│                                              │              │
│           R001 ──→ R002 ──→ R003            │  条件拆解    │
│              └──→ R004 ──→ R006            │  输入/输出   │
│                  └──→ R007                   │  解释文本    │
│                                              │              │
├──────────────────────────────────────────────┴──────────────┤
│  ◀◀ ◀ ▶ ▶▶  ⏸   Step 3/7   2.3ms                          │
│  ────●────────────────────── 执行回放时间线                    │
│  ✓  ✓  ▶●  ○  ○  ○  ○                                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.4 SimulationPage 布局

```
┌─────────────────────────────────────────────────────────────┐
│  What-if 模拟                                               │
├──────────────────────┬──────────────────────────────────────┤
│  SimulationPanel     │  ComparisonView                       │
│  ┌────────────────┐  │  ┌──────────────────────────────────┐│
│  │ 实体: SUP_EXC  │  │  │ 原始值   模拟值   变化          ││
│  │ 维度: credit   │  │  │ score:92  50    ↓45.7% 🔴       ││
│  │                │  │  │ grade:AA  B     ↓3级 🔴         ││
│  │ 覆盖变量:      │  │  │ limit:1.8亿 4千万 ↓77.8% 🔴    ││
│  │ credit_score   │  │  └──────────────────────────────────┘│
│  │ [50      ] ✏️  │  │                                      │
│  │ guarantee_depth│  │  ImpactAnalysis                      │
│  │ [5       ] ✏️  │  │  credit_score↓ → grade↓ → limit↓   │
│  │                │  │  guarantee↑ → alert触发               │
│  │ [▶ 运行模拟]   │  │                                      │
│  └────────────────┘  │                                      │
└──────────────────────┴──────────────────────────────────────┘
```

## 三、核心组件设计

### 3.1 SchemaGraph (G6) — 勾稽逻辑主视图

**关键需求**：指标依赖图必须展示权重边 + 公式预览 + 分层结构

```typescript
// components/schema/SchemaGraph.tsx

interface SchemaGraphProps {
  graphType: 'entity_relation' | 'metric_dependency' | 'full' | 'rule_overview';
  layerFilter?: string[];
  onNodeClick?: (node: GraphNode) => void;
}

function SchemaGraph({ graphType, layerFilter, onNodeClick }: SchemaGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  useEffect(() => {
    // 1. 从 API 获取图数据
    fetchSchemaGraph(graphType, layerFilter).then(data => {
      // 2. 转换为 G6 格式
      const g6Data = transformToG6(data);
      // 3. 创建/更新 G6 图
      if (!graphRef.current) {
        graphRef.current = createG6Graph(containerRef.current!, data.layout_config);
      }
      graphRef.current.setData(g6Data);
      graphRef.current.render();
    });
  }, [graphType, layerFilter]);

  // 注册事件
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    graph.on('node:click', (evt) => {
      const nodeModel = evt.item?.getModel();
      onNodeClick?.(nodeModel);
    });

    graph.on('node:mouseenter', (evt) => {
      // 高亮依赖链
      highlightDependencies(graph, evt.item);
    });

    graph.on('node:mouseleave', (evt) => {
      // 清除高亮
      clearHighlights(graph);
    });
  }, [onNodeClick]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
```

### 3.2 MetricDepGraph (G6) — 勾稽逻辑专用视图

**重点**：权重标注 + 雷达图 + 评分卡联动

```typescript
// components/schema/MetricDepGraph.tsx

function MetricDepGraph() {
  // 专门用于 metric_dependency 视图
  // 额外功能：
  // 1. 依赖边上显示权重值 (如 "0.30")
  // 2. 点击 credit_score 节点时，右侧展示评分卡面板
  // 3. 评分卡 = 5个维度 × 权重的雷达图

  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{ flex: 1 }}>
        <SchemaGraph
          graphType="metric_dependency"
          onNodeClick={(node) => {
            if (node.type === 'metric') setSelectedMetric(node.id);
          }}
        />
      </div>
      {selectedMetric && (
        <div style={{ width: 320, borderLeft: '1px solid #f0f0f0', padding: 16 }}>
          <MetricScorecard metricName={selectedMetric} />
        </div>
      )}
    </div>
  );
}
```

### 3.3 MetricScorecard — 评分卡组件

```typescript
// components/rule/ScorecardView.tsx

interface ScorecardProps {
  metricName: string;
  metricData?: Record<string, any>;
}

function MetricScorecard({ metricName, metricData }: ScorecardProps) {
  // 信用评分评分卡：
  // ┌───────────────────────┐
  // │ 综合信用评分: 92      │
  // │ 等级: AA              │
  // ├───────────────────────┤
  // │  [雷达图]             │
  // │  业务稳定性 30%: 85   │
  // │  税务合规 25%: 90     │
  // │  网络中心性 15%: 60   │
  // │  声誉风险 15%: 95     │
  // │  担保风险 15%: 70     │
  // ├───────────────────────┤
  // │  计算公式:             │
  // │  score = Σ(wi × vi)  │
  // │  = 0.30×85 + ...     │
  // └───────────────────────┘

  const weights = CREDIT_SCORE_WEIGHTS; // 从 schema 获取

  return (
    <Card title={`${METRIC_LABELS[metricName] || metricName}`}>
      {/* 评分数值 */}
      <Statistic title="评分" value={metricData?.value || 0} suffix="/ 100" />

      {/* 雷达图 */}
      <RadarChart weights={weights} values={metricData?.components} />

      {/* 各维度明细 */}
      <List
        dataSource={Object.entries(weights)}
        renderItem={([name, weight]) => (
          <List.Item>
            <span>{METRIC_LABELS[name]}</span>
            <Tag>{(weight * 100).toFixed(0)}%</Tag>
          </List.Item>
        )}
      />

      {/* 公式 */}
      <Paragraph code>
        {metricData?.formula || 'score = Σ(weight_i × value_i)'}
      </Paragraph>
    </Card>
  );
}
```

### 3.4 RuleChainDAG (X6) — 规则链 DAG

```typescript
// components/rule/RuleChainDAG.tsx

function RuleChainDAG({ dimension }: { dimension: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  useEffect(() => {
    fetchRuleChainGraph(dimension).then(data => {
      const graph = createX6Graph(containerRef.current!);

      // 添加自定义节点
      data.nodes.forEach(node => {
        graph.addNode({
          id: node.id,
          shape: 'rule-node',  // 自定义形状
          x: node.position.x,
          y: node.position.y,
          width: 240,
          height: 140,
          data: node.data,
          attrs: getRuleNodeAttrs(node.data),  // 根据类型着色
        });
      });

      // 添加边
      data.edges.forEach(edge => {
        graph.addEdge({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          attrs: {
            line: {
              stroke: '#A0A0A0',
              strokeWidth: 1.5,
              targetMarker: { name: 'block' },
            },
          },
          labels: [{
            attrs: { label: { text: edge.data.description || '' } },
          }],
        });
      });

      graphRef.current = graph;
    });
  }, [dimension]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
```

### 3.5 ExecutionReplay — 执行回放

```typescript
// components/rule/ExecutionReplay.tsx

function ExecutionReplay({ steps, currentStep, onStepChange }: ReplayProps) {
  return (
    <div className="execution-replay">
      {/* 播放控制 */}
      <Space>
        <Button icon={<BackwardOutlined />} onClick={() => onStepChange(1)} />
        <Button icon={<StepBackwardOutlined />} onClick={() => onStepChange(Math.max(1, currentStep - 1))} />
        <Button icon={playing ? <PauseOutlined /> : <CaretRightOutlined />} onClick={togglePlay} />
        <Button icon={<StepForwardOutlined />} onClick={() => onStepChange(Math.min(steps.length, currentStep + 1))} />
        <Button icon={<ForwardOutlined />} onClick={() => onStepChange(steps.length)} />
      </Space>

      {/* 时间线 */}
      <div className="timeline">
        {steps.map((step, idx) => (
          <div
            key={step.rule_id}
            className={`timeline-node ${getStepStatusClass(step, idx + 1, currentStep)}`}
            onClick={() => onStepChange(idx + 1)}
          >
            <div className="status-icon">
              {step.status === 'passed' ? '✓' :
               step.status === 'failed' ? '✗' :
               idx + 1 === currentStep ? '▶' : '○'}
            </div>
            <div className="rule-label">{step.rule_id.replace(/_.*$/, '')}</div>
          </div>
        ))}
      </div>

      <Text type="secondary">
        Step {currentStep}/{steps.length} · {steps[currentStep - 1]?.duration_ms?.toFixed(1)}ms
      </Text>
    </div>
  );
}
```

### 3.6 ComparisonView — 对比视图

```typescript
// components/simulation/ComparisonView.tsx

function ComparisonView({ comparison }: { comparison: ComparisonResult }) {
  return (
    <div>
      <Table
        dataSource={comparison.diffs}
        columns={[
          { title: '指标', dataIndex: 'field', render: (f) => METRIC_LABELS[f] || f },
          { title: '原始值', dataIndex: 'baseline_value' },
          { title: '模拟值', dataIndex: 'simulated_value' },
          {
            title: '变化',
            dataIndex: 'change_magnitude',
            render: (mag: number | null, record: DiffEntry) => (
              <ChangeIndicator magnitude={mag} type={record.change_type} />
            ),
          },
          { title: '影响', dataIndex: 'impact' },
        ]}
      />

      {/* 影响路径 */}
      <Card title="影响路径" size="small">
        {comparison.impact_chains.map(chain => (
          <Paragraph key={chain.source_field}>
            <Text type="warning">{chain.description}</Text>
          </Paragraph>
        ))}
      </Card>
    </div>
  );
}
```

## 四、数据转换层

### 4.1 G6 Transformer (g6Transformers.ts)

```typescript
// utils/g6Transformers.ts

export function transformToG6(data: SchemaGraphData): G6GraphData {
  return {
    nodes: data.nodes.map(node => ({
      id: node.id,
      data: {
        type: getG6NodeType(node.type),
        ...getNodeStyle(node),
      },
    })),
    edges: data.edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      data: {
        type: getG6EdgeType(edge.type),
        ...getEdgeStyle(edge),
      },
    })),
  };
}

function getNodeStyle(node: GraphNode): G6NodeStyle {
  const styles = {
    entity: {
      type: 'rect',
      style: {
        size: [120, 50],
        fill: '#E8F4FD',
        stroke: '#1890FF',
        radius: 8,
        labelText: node.data.label,
        labelFill: '#333',
        iconSrc: '/icons/entity.svg',
      },
    },
    metric: {
      type: 'diamond',
      style: {
        size: 40,
        fill: METRIC_TYPE_COLORS[node.data.metric_type]?.fill || '#F0F0F0',
        stroke: METRIC_TYPE_COLORS[node.data.metric_type]?.stroke || '#D9D9D9',
        labelText: node.data.label,
      },
    },
    rule: {
      type: 'rect',
      style: {
        size: [140, 60],
        fill: RULE_TYPE_COLORS[node.data.rule_type]?.fill || '#F0F0F0',
        stroke: RULE_TYPE_COLORS[node.data.rule_type]?.stroke || '#D9D9D9',
        radius: 4,
        labelText: `${node.id}: ${node.data.label}`,
      },
    },
  };
  return styles[node.type] || styles.entity;
}
```

### 4.2 配色方案 (colorSchemes.ts)

```typescript
// utils/colorSchemes.ts

export const METRIC_TYPE_COLORS = {
  atomic: { fill: '#F6FFED', stroke: '#52C41A', label: '原子指标' },
  derived: { fill: '#FFF7E6', stroke: '#FA8C16', label: '派生指标' },
  composite: { fill: '#F9F0FF', stroke: '#722ED1', label: '复合指标' },
  graph: { fill: '#FFF1F0', stroke: '#F5222D', label: '图指标' },
};

export const RULE_TYPE_COLORS = {
  constraint: { fill: '#FFF1F0', stroke: '#F5222D', label: '约束规则' },
  inference: { fill: '#E6F7FF', stroke: '#1890FF', label: '推理规则' },
  alert: { fill: '#FFF7E6', stroke: '#FA8C16', label: '预警规则' },
  decision: { fill: '#F6FFED', stroke: '#52C41A', label: '决策规则' },
};

export const EXECUTION_STATUS_COLORS = {
  pending: '#D9D9D9',
  executing: '#1890FF',
  passed: '#52C41A',
  failed: '#F5222D',
  skipped: '#FA8C16',
};

export const EDGE_TYPE_STYLES = {
  relation: { stroke: '#A0A0A0', lineWidth: 1.5, lineDash: [], endArrow: true },
  metric_dep: { stroke: '#722ED1', lineWidth: 1, lineDash: [4, 4], endArrow: true },
  rule_input: { stroke: '#1890FF', lineWidth: 1, lineDash: [2, 2], endArrow: true },
};
```

## 五、状态管理 (Zustand)

```typescript
// stores/schemaStore.ts
interface SchemaStore {
  graphType: string;
  layerFilter: string[];
  selectedNode: GraphNode | null;
  schemaData: SchemaGraphData | null;
  setGraphType: (type: string) => void;
  setLayerFilter: (layers: string[]) => void;
  selectNode: (node: GraphNode | null) => void;
  fetchSchema: () => Promise<void>;
}

// stores/executionStore.ts
interface ExecutionStore {
  dimension: string;
  steps: ExecutionStepSnapshot[];
  currentStep: number;
  playing: boolean;
  setDimension: (dim: string) => void;
  setCurrentStep: (step: number) => void;
  togglePlay: () => void;
  fetchExecution: (entityId: string) => Promise<void>;
}

// stores/simulationStore.ts
interface SimulationStore {
  entityId: string;
  dimension: string;
  overrides: Record<string, any>;
  simulationResult: SimulationResult | null;
  loading: boolean;
  setOverride: (field: string, value: any) => void;
  removeOverride: (field: string) => void;
  runSimulation: () => Promise<void>;
  reset: () => void;
}
```

## 六、API 客户端

```typescript
// api/visualization.ts

const BASE_URL = '/v1/visualize';

export async function fetchSchemaGraph(
  graphType: string,
  layerFilter?: string[],
): Promise<SchemaGraphData> {
  const params = new URLSearchParams({ graph_type: graphType });
  if (layerFilter?.length) params.set('layer_filter', layerFilter.join(','));
  const res = await axios.get(`${BASE_URL}/schema/graph`, { params });
  return res.data.data;
}

export async function fetchRuleChainGraph(dimension: string): Promise<RuleChainGraphData> {
  const res = await axios.get(`${BASE_URL}/rule-chain/${dimension}`);
  return res.data.data;
}

export async function simulateExecution(req: SimulationRequest): Promise<SimulationResult> {
  const res = await axios.post(`${BASE_URL}/simulate`, req);
  return res.data.data;
}

export async function fetchExecutionTrace(entityId: string, dimension: string): Promise<ExecutionStepSnapshot[]> {
  const res = await axios.get(`${BASE_URL}/execution/${entityId}/${dimension}`);
  return res.data.data;
}
```

## 七、评分卡设计细节

### 7.1 信用评分评分卡

```
┌────────────────────────────────────┐
│  综合信用评分                        │
│  ┌──────────────────────────────┐  │
│  │      92                       │  │
│  │      ╱ AA ╲                  │  │
│  │  ─────────────────           │  │
│  │  等级: AA  |  决策: APPROVE  │  │
│  └──────────────────────────────┘  │
│                                     │
│  [雷达图 - 5个维度]                  │
│        业务稳定性                    │
│           85                        │
│      ╱    │    ╲                    │
│  声誉95 ── 92 ── 税务90            │
│      ╲    │    ╱                    │
│  担保70 ── 网络中心性60             │
│                                     │
│  维度明细:                           │
│  ┌───────────────────────────────┐ │
│  │ 业务稳定性  ████████░░ 85  30%│ │
│  │ 税务合规    █████████░ 90  25%│ │
│  │ 网络中心性  ██████░░░░ 60  15%│ │
│  │ 声誉风险    █████████░ 95  15%│ │
│  │ 担保风险    ███████░░░ 70  15%│ │
│  └───────────────────────────────┘ │
│                                     │
│  公式:                              │
│  score = 0.30×85 + 0.25×90          │
│       + 0.15×60 + 0.15×95           │
│       + 0.15×70 = 81.75             │
│  (含关键预警惩罚后 = 92)             │
└────────────────────────────────────┘
```

### 7.2 勾稽逻辑可视化

指标依赖图中的**勾稽边**必须标注权重，表示"上游指标如何影响下游指标"：

```
  业务稳定性 ──── 0.30 ────→ 信用评分
  税务合规   ──── 0.25 ────→ 信用评分
  网络中心性 ──── 0.15 ────→ 信用评分
  声誉风险   ──── 0.15 ────→ 信用评分
  担保链深度 ──── 0.15 ────→ 信用评分

  逾期金额   ─────────────→ 逾期占比
  发票总额   ─────────────→ 逾期占比
  逾期占比   ──── 0.30 ────→ 业务稳定性
  合同执行率 ──── 0.30 ────→ 业务稳定性
  核心企业数 ──── 0.15 ────→ 业务稳定性
```

权重边样式：
- 有权重：紫色实线 + 权重标签（如 "0.30"），线宽按权重比例 1-3px
- 无权重：紫色虚线，1px

## 八、前端交互规格

| 场景 | 交互 | 反馈 |
|------|------|------|
| Schema图节点点击 | 更新右侧面板 | 面板展示节点详情 |
| Schema图节点悬停 | 高亮依赖链 | 节点+直接边变亮，其余变暗 |
| 指标依赖图节点点击 | 展开评分卡 | 右侧面板显示评分卡 |
| 权重边悬停 | 展示权重tooltip | "业务稳定性 → 信用评分, 权重: 0.30" |
| 规则DAG节点点击 | 展示规则详情 | 右侧面板显示条件+动作 |
| 执行回放步骤点击 | DAG节点高亮+快照面板更新 | 目标步骤节点高亮，面板显示该步快照 |
| What-if变量修改 | 输入框编辑 | 实时显示原始值对比 |
| 运行模拟 | 发起API请求 | Loading → 结果展示 → 对比表格 |

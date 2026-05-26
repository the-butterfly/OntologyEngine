# 可视化系统实施计划 - 总览

> **版本**: v1.0
> **日期**: 2026-04-10
> **前置文档**: docs/08-visualization-system.md

## 一、实施策略

采用 **"后端先行 → 前端跟进 → 联调验收"** 三阶段推进：

| 阶段 | 内容 | 产出 | 预估 |
|------|------|------|------|
| **P1** | 后端 visualization 模块 + API | 4个Python模块 + 1个Service + 1个路由 | 3天 |
| **P2** | 前端 React 项目搭建 + 核心组件 | Schema图 + 规则DAG + 模拟执行 | 5天 |
| **P3** | 联调 + 样式打磨 + 验收 | 5个验收场景全通过 | 2天 |

## 二、模块文件清单

### 后端新增文件

```
ontology_engine/
├── visualization/
│   ├── __init__.py              # 模块导出
│   ├── models.py                # 数据模型 (SchemaGraphData, RuleChainGraphData, ExecutionStepSnapshot, SimulationResult, ComparisonResult)
│   ├── builders.py              # 图数据构建器 (SchemaGraphBuilder, RuleChainGraphBuilder)
│   ├── explainers.py            # 可解释性引擎 (ConditionExplainer, ImpactAnalyzer)
│   └── simulator.py             # 模拟执行引擎 (RuleChainSimulator)
├── services/
│   └── visualization_service.py # 可视化服务 (VisualizationService)
├── api/routes/
│   └── visualization.py         # API 路由 (4个端点)
├── api/
│   └── dependencies.py          # 新增 get_visualization_service
└── api/
    └── server.py                # 注册 visualization 路由

tests/unit/visualization/
├── __init__.py
├── test_models.py
├── test_schema_graph_builder.py
├── test_rule_chain_builder.py
├── test_condition_explainer.py
├── test_impact_analyzer.py
├── test_simulator.py
└── test_visualization_service.py
```

### 前端新增文件

```
ontology-engine-ui/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── index.html
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts
│   │   ├── schema.ts
│   │   ├── analysis.ts
│   │   └── visualization.ts
│   ├── stores/
│   │   ├── schemaStore.ts
│   │   ├── executionStore.ts
│   │   └── simulationStore.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx
│   │   │   └── Sidebar.tsx
│   │   ├── schema/
│   │   │   ├── SchemaGraph.tsx         # G6 实体关系图
│   │   │   ├── MetricDepGraph.tsx      # G6 指标依赖图(勾稽逻辑)
│   │   │   └── EntityDetail.tsx        # 实体详情侧栏
│   │   ├── rule/
│   │   │   ├── RuleChainDAG.tsx        # X6 规则链 DAG
│   │   │   ├── ExecutionReplay.tsx     # 执行回放控制器
│   │   │   ├── StepSnapshot.tsx        # 单步快照面板
│   │   │   └── ScorecardView.tsx       # 评分卡视图
│   │   ├── simulation/
│   │   │   ├── SimulationPanel.tsx     # What-if 输入面板
│   │   │   ├── ComparisonView.tsx      # 原始 vs 模拟对比
│   │   │   └── ImpactAnalysis.tsx      # 影响路径分析
│   │   └── common/
│   │       ├── G6Container.tsx
│   │       ├── X6Container.tsx
│   │       └── StatusBadge.tsx
│   ├── pages/
│   │   ├── SchemaPage.tsx
│   │   ├── RuleChainPage.tsx
│   │   └── SimulationPage.tsx
│   ├── utils/
│   │   ├── g6Transformers.ts          # KGML → G6 数据转换
│   │   ├── x6Transformers.ts          # Rule → X6 数据转换
│   │   └── colorSchemes.ts            # 配色方案
│   └── types/
│       ├── schema.ts
│       ├── rule.ts
│       └── visualization.ts
```

## 三、验收场景映射

| 场景 | 后端 API | 前端组件 | 验证点 |
|------|----------|----------|--------|
| 1. Schema实体关系图 | GET /v1/visualize/schema/graph?graph_type=entity_relation | SchemaGraph (G6) | 5节点4边，力导布局 |
| 2. 指标依赖图(勾稽逻辑) | GET /v1/visualize/schema/graph?graph_type=metric_dependency | MetricDepGraph (G6) | 4层分层，依赖边带权重 |
| 3. 规则链模拟-通过 | POST /v1/visualize/simulate (SUP_2024_EXC) | RuleChainDAG + ExecutionReplay | 7步全绿，APPROVE |
| 4. 规则链模拟-拒绝 | POST /v1/visualize/simulate (SUP_2024_003) | RuleChainDAG + StepSnapshot | R001红色，REJECT |
| 5. What-if担保圈模拟 | POST /v1/visualize/simulate (overrides) | SimulationPanel + ComparisonView | 额度↓70%+，新增alert |

## 四、关键设计原则

1. **后端不生成渲染字符串**：仅输出 G6/X6 兼容的结构化 JSON
2. **模拟不写存储**：dry_run 仅内存追踪，What-if 复用 AnalysisService 但跳过 persist
3. **勾稽逻辑是核心**：指标依赖图必须展示权重边 + 公式预览 + 分层结构
4. **评分卡是重点**：信用评分的5个维度 × 权重，雷达图+数值面板
5. **执行可解释**：每步必须有条件拆解 + 输入/输出快照 + 自然语言解释

## 五、配色方案 (Ant Design 5 体系)

| 元素 | 颜色 | 语义 |
|------|------|------|
| Entity 节点 | fill:#E8F4FD, stroke:#1890FF | 蓝色系 - 实体 |
| Atomic 指标 | fill:#F6FFED, stroke:#52C41A | 绿色 - 原子指标 |
| Derived 指标 | fill:#FFF7E6, stroke:#FA8C16 | 橙色 - 派生指标 |
| Composite 指标 | fill:#F9F0FF, stroke:#722ED1 | 紫色 - 复合指标 |
| Graph 指标 | fill:#FFF1F0, stroke:#F5222D | 红色 - 图指标 |
| Constraint 规则 | fill:#FFF1F0, stroke:#F5222D | 红色 - 约束 |
| Inference 规则 | fill:#E6F7FF, stroke:#1890FF | 蓝色 - 推理 |
| Alert 规则 | fill:#FFF7E6, stroke:#FA8C16 | 橙色 - 预警 |
| Decision 规则 | fill:#F6FFED, stroke:#52C41A | 绿色 - 决策 |
| 依赖边(metric_dep) | stroke:#722ED1, lineDash:[4,4] | 紫色虚线 |
| 数据流边(rule_input) | stroke:#1890FF, lineDash:[2,2] | 蓝色虚线 |
| 关系边(relation) | stroke:#A0A0A0, 实线 | 灰色实线 |

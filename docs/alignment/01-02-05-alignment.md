# 文档对齐分析报告

> **分析目标**: 对齐 01-overview、02-design、05-schema-v2 三块设计
> **分析时间**: 2026-04-10
> **更新时间**: 2026-04-10 (v2 - 增加可视化模块对齐)

## 一、对齐矩阵

| 设计维度 | 01-overview | 02-design | 05-schema-v2 | 对齐状态 |
|----------|--------------|------------|--------------|----------|
| **分层模型** | L1-L4 四层 | 未明确分层 | L1-L4 四层 | ✅ 已对齐 |
| **Schema 格式** | KGML (YAML) | KGML v1 | KGML v2 | ⚠️ 版本差异（V1CompatMapper 兼容） |
| **核心组件** | SchemaLoader, Engine | RuleParser, DAGBuilder | 四层分离 | ✅ 基本对齐 |
| **规则执行** | DAG 拓扑排序 | DAG 执行器 | 跨引擎协调 | ✅ 已对齐 |
| **维度概念** | 多维度分析 | rule_dimensions | categorization | ✅ 术语统一 |
| **指标类型** | atomic/derived/composite | atomic/derived/composite/graph | 同左 | ✅ 对齐 |
| **算子体系** | 8 个内置算子 | 8 个内置算子 | 9 种算子类型 | ✅ 扩展对齐 |
| **可视化模块** | (无) | (无) | (无) | ✅ 新增 docs/08 |

## 二、可视化模块对齐

### 2.1 新增模块与存量架构的关系

```
┌───────────────────────────────────────────────────────┐
│ API Layer                                             │
│  /v1/schema  /v1/entities  /v1/analysis  /v1/query   │
│  /v1/ingestion            /v1/visualize  ← 新增       │
├───────────────────────────────────────────────────────┤
│ Services Layer                                        │
│  SchemaService  EntityService  AnalysisService  ...  │
│  VisualizationService  ← 新增                         │
├───────────────────────────────────────────────────────┤
│ Engine Layer                                          │
│  MetricEngine  CategorizationEngine  RuleEngine  ...  │
│  (RuleChainSimulator ← 新增, 位于 visualization/)     │
├───────────────────────────────────────────────────────┤
│ Storage Layer                                         │
│  DuckDBStorage  FaissVectorStore  NetworkXGraph       │
└───────────────────────────────────────────────────────┘
```

### 2.2 可视化模块遵循的架构约束

| 约束 | 遵循方式 |
|------|----------|
| **API 边界封闭** | visualization route 只调 VisualizationService |
| **禁止跨层调用** | VisualizationService 调 SchemaService/AnalysisService，不直接调 engine/storage |
| **测试先行** | 5 个验收场景 → 对应测试用例 |
| **文档同步** | docs/08-visualization-system.md 同步更新 |
| **本地存储优先** | 不引入 neo4j/redis，模拟数据走 DuckDB |

### 2.3 前端技术栈对齐

| 组件 | 技术选型 | 与后端交互方式 |
|------|----------|---------------|
| Schema 实体关系图 | @antv/g6 5.x | GET /v1/visualize/schema/graph → G6 nodes/edges |
| 指标依赖图 | @antv/g6 5.x | 同上 (graph_type=metric_dependency) |
| 规则链 DAG | @antv/x6 2.x | GET /v1/visualize/rule-chain/{dim} → X6 nodes/edges |
| 执行回放 | @antv/x6 2.x + React | POST /v1/visualize/simulate → 逐步快照 |
| What-if 模拟 | React + @antv/g2 | POST /v1/visualize/simulate (overrides) → 对比数据 |

**关键设计决策：后端不生成渲染字符串（Mermaid/Plotly），仅输出结构化图数据（G6/X6 兼容的 nodes/edges JSON）。**

## 三、统一分层视图（含可视化）

```
01-overview          02-design              05-schema-v2          08-visualization
──────────────────────────────────────────────────────────────────────────────────
L1 事实层       →   concepts              →   fact_objects       → 实体关系图 (G6)
L2 归类层       →   (隐含)                →   categorization     → 维度筛选过滤
L3 分析层       →   metrics               →   analytical_elements → 指标依赖图 (G6)
L4 决策层       →   rules                 →   business_logic     → 规则链 DAG (X6)
执行可解释      →   (无)                  →   (无)               → 执行回放 + What-if
```

## 四、关键设计决策

### 4.1 前后端分离

| 决策 | 内容 | 理由 |
|------|------|------|
| 后端输出图数据 JSON | 不输出 Mermaid/Plotly/DOT 字符串 | 前端需要交互能力（hover/click/zoom），纯字符串无法实现 |
| 前端负责渲染 | G6/X6 渲染引擎 | 成熟的图可视化引擎，交互能力完善 |
| API 返回 G6/X6 兼容格式 | nodes/edges 结构 | 直接消费，无需二次转换 |

### 4.2 模拟执行不写存储

| 决策 | 内容 | 理由 |
|------|------|------|
| dry_run 模式不写 DuckDB | 仅在内存中追踪执行路径 | 避免模拟数据污染实际业务数据 |
| What-if 复用 AnalysisService | 但跳过 persist 步骤 | 代码复用，行为一致 |

### 4.3 执行可解释性核心

| 决策 | 内容 | 理由 |
|------|------|------|
| ExecutionStepSnapshot | 每步记录完整上下文快照 | 支持任意步骤回放 |
| ConditionExplainer | 拆解复合条件为子条件 | 用户看到的是逐步推理，不是黑盒 |
| ComparisonResult | 原始 vs 模拟对比 | What-if 核心价值 |

## 五、对齐清单

- [x] 统一 L1-L4 分层术语
- [x] 明确 01-overview → 02-design → 05-schema-v2 映射关系
- [x] 定义统一的 Schema v2 格式
- [x] 定义 V1CompatMapper 转换规则
- [x] 新增 08-visualization-system.md 设计文档
- [x] 前端技术栈选型（AntV G6 + X6 + React）
- [ ] examples/schema.yaml 适配 v2 格式
- [ ] 更新 02-design/01-schema-spec.md 补充 v2 说明
- [ ] 前端项目 ontology-engine-ui 初始化

# 模块详细设计 —— 总览

> **状态**: Phase 1 详细设计
> **基于**: 供应链金融授信评估场景 (examples/supply_chain_finance)
> **目标**: 打通 Schema → 加载 → 存储 → 计算 → 规则 → 输出 的完整链路

## 设计范围

本文档群覆盖从 MVP Demo 到 Phase 1 产品化所需的全部功能模块详细设计，以供应链金融场景为主线，确保每个模块有明确的接口、数据流和依赖关系。

## 文档索引

| 编号 | 文档 | 核心内容 |
|------|------|----------|
| 01 | [Schema 加载与校验](./01-schema-loading.md) | KGML 解析、v1→v2 兼容、Schema 校验 |
| 02 | [实例加载与实体管理](./02-instance-management.md) | 实例 YAML 加载、实体 CRUD、属性校验 |
| 03 | [存储层](./03-storage-layer.md) | DuckDB 表设计、图存储、向量索引、缓存 |
| 04 | [指标引擎](./04-metric-engine.md) | MetricEngine 四类指标计算、DAG 依赖、缓存策略 |
| 05 | [归类引擎](./05-categorization-engine.md) | L2 归类、复用规则引擎、标签管理 |
| 06 | [规则引擎](./06-rule-engine.md) | DAG 构建、拓扑执行、算子体系、回滚 |
| 07 | [表达式引擎](./07-expression-engine.md) | 两级安全模型、Formula 规范、内置函数 |
| 08 | [查询引擎](./08-query-engine.md) | 图遍历 DSL、向量检索、混合融合 |
| 09 | [服务层](./09-services-layer.md) | 用例编排、事务管理、跨引擎协调 |
| 10 | [API 层](./10-api-layer.md) | FastAPI 路由、DTO、错误码、流式响应 |

## 架构全景

```
                         ┌─────────────────────────────────┐
                         │         API 层 (FastAPI)         │
                         │  schema / entity / rule / query  │
                         └───────────────┬─────────────────┘
                                         │
                         ┌───────────────▼─────────────────┐
                         │          服务层 (Services)        │
                         │ SchemaService / EntityService    │
                         │ AnalysisService / IngestionSvc   │
                         │ QueryService                     │
                         └───────────────┬─────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
┌─────────────▼──────────┐ ┌────────────▼───────────┐ ┌───────────▼──────────┐
│   规则引擎 RuleEngine  │ │  指标引擎 MetricEngine │ │  查询引擎 QueryEngine │
│  DAG / 拓扑 / 算子    │ │  atomic/derived/       │ │  图遍历 / 向量 /      │
│  归类引擎(Categorize) │ │  composite / graph     │ │  混合融合             │
└─────────────┬──────────┘ └────────────┬───────────┘ └───────────┬──────────┘
              │                          │                          │
              │              ┌───────────▼───────────┐              │
              │              │  表达式引擎 ExprEngine │              │
              │              │  L0 simpleeval         │              │
              │              │  L1 AST 沙箱           │              │
              │              └───────────┬───────────┘              │
              │                          │                          │
┌─────────────▼──────────────────────────▼──────────────────────────▼──────────┐
│                            存储层 (Storage)                                   │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────────┐ │
│  │  DuckDBStorage   │  │ FaissVectorStore │  │ NetworkXGraph (按需加载)    │ │
│  │  entities/relations│  │  语义索引        │  │  子图 / 路径 / 中心性       │ │
│  │  metrics/cache   │  │                  │  │                             │ │
│  └─────────────────┘  └──────────────────┘  └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
              │
┌─────────────▼────────────────────────────────────────────────────────────────┐
│                            核心层 (Core)                                      │
│  ┌──────────────────┐  ┌────────────────────┐  ┌────────────────────────┐   │
│  │  SchemaLoader    │  │  InstanceLoader    │  │  TypeSystem            │   │
│  │  KGML → Pydantic │  │  YAML → Entities   │  │  枚举 / Money / Date   │   │
│  └──────────────────┘  └────────────────────┘  └────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 供应链金融场景端到端数据流

以"供应商融资授信评估"完整链路为例：

```
1. Schema 加载
   schema.yaml → SchemaLoader → KGMLSchema (L1事实/L2归类/L3指标/L4规则)

2. 实例加载
   instances.yaml → InstanceLoader → Entity[] + Relation[] → DuckDBStorage

3. 归类计算 (L2)
   Entity → CategorizationEngine → CategoryTags (行业/规模/风险等级)

4. 指标计算 (L3)
   Entity + CategoryTags → MetricEngine → ComputedMetrics
     ├─ atomic: total_invoice_amount_90d, overdue_invoice_amount
     ├─ derived: overdue_invoice_ratio, contract_utilization_rate
     ├─ composite: credit_score, reputation_score
     └─ graph: guarantee_chain_depth, network_centrality

5. 规则执行 (L4)
   Entity + CategoryTags + Metrics → RuleEngine → AnalysisResult
     R001 基础准入 → R002 信用评分 → R003 担保圈检测
     → R004 授信额度 → R005 风险预警 → R006 利率定价 → R007 综合决策

6. 结果输出
   AnalysisResult → API Response / MCP Tool Output / CLI Display
     ├─ 决策: APPROVE / REJECT / APPROVE_WITH_CONDITIONS
     ├─ 额度: recommended_credit_limit
     ├─ 利率: recommended_interest_rate
     └─ 可解释: 完整计算链路追溯
```

## 关键设计原则

1. **Schema 驱动**: 业务逻辑在 YAML 定义，代码只实现通用执行机制
2. **分层解耦**: 严格 L0→L1→L2→L3→Services→API 依赖方向
3. **v1 兼容 v2**: 代码同时支持 v1 扁平 Schema 和 v2 四层分离 Schema
4. **可解释性**: 每个计算结果可追溯到原始事实 + 计算公式 + 规则ID
5. **渐进增强**: Phase 1 先跑通链路，性能/高可用/实时 在后续 Phase 迭代

## 图查询 SLA（Phase 1）

> 基于 DuckDB 关系查询 + NetworkX 按需加载子图，Phase 1 实测达标后固定。

| 查询类型 | 操作 | Phase 1 P99 目标 | 说明 |
|----------|------|-----------------|------|
| 点查 | `get_entity(id)` | < 50ms | 直接 PK 查询 |
| 邻居查询 | `get_neighbors(id, depth=1)` | < 100ms | 单跳邻居，返回实体+关系 |
| 路径查询 | `find_paths(depth=2)` | < 200ms | 两跳可达路径 |
| 图指标 | `compute_graph(gurantee_chain_depth)` | < 1s | NetworkX 子图算法 |
| 混合检索 | `hybrid_query(struct + semantic)` | < 500ms | 向量+结构化融合（Phase 1 固定权重 0.6+0.4） |

> **注**：超过 SLA 阈值的查询触发告警，但不阻塞返回。后续 Phase 优化方案：图索引预加载、热点节点内存常驻、Faiss 批处理。

## 与已有文档的关系

| 已有文档 | 本设计的处理 |
|----------|-------------|
| `02-design/01-schema-spec.md` | 继承 Schema 格式，补充 v1/v2 兼容策略 |
| `02-design/02-api-design.md` | 继承端点设计，补充 DTO 和错误处理细节 |
| `02-design/03-storage-design.md` | 继承存储架构，补充指标/缓存表设计 |
| `02-design/04-rule-engine-design.md` | 继承规则引擎，补充算子体系和归类复用 |
| `02-design/05-services-design.md` | 继承服务划分，补充完整用例编排流程 |
| `02-design/06-formula-spec.md` | 继承表达式规范，补充两级执行实现 |
| `05-schema-v2/*` | v2 四层设计作为目标架构，设计迁移路径 |
| `07-agent-interface.md` | MCP 接口设计，Phase 2 实现 |
| `08-knowledge-retrieval.md` | 检索服务设计，Phase 1 实现基础版 |

## MVP 代码 → Phase 1 的关键变化

| 模块 | MVP 状态 | Phase 1 目标 | 变化程度 |
|------|---------|-------------|---------|
| SchemaLoader | ✅ 已实现 | 支持 v1+v2、增强校验 | 🔄 增强 |
| InstanceLoader | ✅ 基础版 | 属性校验、批量导入 | 🔄 增强 |
| DuckDBStorage | ✅ 基础版 | 指标表、缓存表、审计表 | 🔄 增强 |
| RuleExecutor | ✅ 硬编码action | 通用算子体系、DAG | 🔴 重写 |
| ExpressionEvaluator | ✅ simpleeval | 两级安全模型 | 🔄 增强 |
| MetricEngine | ❌ 缺失 | 四类指标计算 | 🟢 新增 |
| CategorizationEngine | ❌ 缺失 | L2 归类 | 🟢 新增 |
| QueryEngine | ❌ 缺失 | 图遍历+向量 | 🟢 新增 |
| Services 层 | ❌ 缺失 | 5个 Service | 🟢 新增 |
| API 层 | ❌ 缺失 | FastAPI 路由 | 🟢 新增 |
| OntologyEngine 主类 | ✅ 编排逻辑 | 瘦身为 facade | 🔄 重构 |

# 模块架构

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-17

## 上下文栈对齐视图

OntologyEngine 在 AI Agent 上下文栈中占据**深度层**，与广度层（RAG）和连续性层（Memory）协同工作：

```
┌─────────────────────────────────────────────────────┐
│  Agent 上下文栈 (Context Stack)                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  连续性层 (Memory)                                      │ │
│  │  ── 会话历史 / 用户偏好 / 跨会话状态                     │ │
│  │  ── 保障 Agent 行为连续性                                │ │
│  │  ── 类比 m-flow 的 Procedural Memory（程序记忆）            │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  广度层 (RAG)                                           │ │
│  │  ── 文档检索 / 向量相似度 / 知识密集型问答               │ │
│  │  ── 保障信息覆盖广度                                    │ │
│  │  ── 类比传统 RAG 系统（向量检索）                         │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  ★ 深度层 (OntologyEngine) ★                        │ │
│  │  ── 实体关系 / 多跳推理 / 规则执行 / 三层资产链接        │ │
│  │  ── 保障推理深度和可解释性                                │ │
│  │  ── 三层资产链接的载体                                       │ │
│  │  ── 类比 m-flow 的 Episodic Memory + KAG 的 Logical Form        │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## 分层视图（三类资产视角）

```
┌─────────────────────────────────────────────────────────┐
│ L4: API / 接口层                                        │
│   FastAPI REST / MCP Agent 协议 / CLI                   │
│   ── 消费面：Agent 交互中沉淀个人资产                        │
├─────────────────────────────────────────────────────────┤
│ L3: 服务层 (编排)                                       │
│   SchemaService / EntityService / AnalysisService       │
│   QueryService / IngestionService / VisualizationService │
│   ── 编排三层资产的 CRUD 和推理                                │
├─────────────────────────────────────────────────────────┤
│ L2: 引擎层 (推理)                                       │
│   ├─ RuleEngine    (规则/DAG执行)                       │
│   ├─ MetricEngine  (指标计算)                           │
│   ├─ CategorizationEngine (归类)                        │
│   ├─ QueryEngine   (查询/检索)                          │
│   └─ ExpressionEngine (表达式安全执行)                   │
│   ── 执行 L1-L4 四层推理链                                       │
├─────────────────────────────────────────────────────────┤
│ L1: 存储层 (资产持久化)                                  │
│   ├─ DuckDBStorage   (实体/关系/元数据/审计)             │
│   ├─ NetworkXGraph   (图算法，按需)                      │
│   └─ FaissVectorStore (向量索引)                        │
│   ── 存储三类资产：IT 资产 / 个人资产 / 组织资产                      │
├─────────────────────────────────────────────────────────┤
│ L0: 核心层 (Schema 驱动)                                │
│   ├─ SchemaLoader    (KGML 解析)                        │
│   ├─ OperatorRegistry (算子注册与发现)                   │
│   ├─ ExpressionEngine (L0 simpleeval + L1 AST 沙箱)     │
│   └─ ValueDomainValidator (值域校验)                     │
│   ── 定义三类资产的统一本体模型（KGML）                              │
└─────────────────────────────────────────────────────────┘
```

## 模块职责（三类资产视角）

### 核心层 (L0)

| 模块 | 职责 | 对应资产层 | 对齐 m-flow/KAG | 输入 | 输出 |
|------|------|-----------|------------------|------|------|
| **SchemaLoader** | 解析 KGML YAML | 组织资产（规则定义载体） | 对齐 KAG 的 Schema 解析（OpenSPG） | schema.yaml | Pydantic 模型 |
| **OperatorRegistry** | 算子发现与注册 | 组织资产（业务逻辑单元） | 对齐 m-flow 的 Pipeline Tasks | 算子实现类 | 可执行算子池 |
| **ExpressionEngine** | 表达式安全执行 | IT 资产（计算安全边界） | 对齐 KAG 的 Logical Form 执行 | `score > 80` | 布尔结果/数值 |
| **ValueDomainValidator** | 值域校验 | IT ↔ 组织（数据规则对齐） | 对齐 KAG 的概念对齐（Aligner） | 属性值 + 值域定义 | 校验结果 |

### 存储层 (L1)

| 模块 | 本地实现 | 预留接口 | 承载资产 | 对齐 m-flow/KAG | 数据位置 |
|------|----------|----------|----------|------------------|----------|
| **DuckDBStorage** | ✅ | - | IT 资产 + 组织资产 | 对齐 KAG 的存储层（OpenSPG） | `data/ontology.db` |
| **FaissVectorStore** | ✅ | pgvector | IT 资产（语义索引） | 对齐 m-flow 的向量存储 | `data/vectors/` |
| **NetworkXGraph** | 按需加载 | Neo4j | 三层资产链接图 | 对齐 m-flow 的 Cone Graph + KAG 的图存储 | 内存 |

**边界约束**：
- 上层只能调用 `storage/base.py` 接口
- `local/` 只实现接口，不依赖上层
- 三类资产的链接关系在存储层统一管理

### 引擎层 (L2)

| 模块 | 核心功能 | 资产推理 | 对齐 m-flow/KAG | 依赖 |
|------|----------|-----------|------------------|------|
| **RuleEngine** | DAG 解析、拓扑执行、回滚 | 组织资产执行 | 对齐 m-flow 的 Procedure Execution + KAG 的 Executor | core/, storage/ |
| **MetricEngine** | 指标计算、缓存、增量更新 | 个人→组织知识量化 | 对齐 m-flow 的 FacetPoint 计算 + KAG 的指标计算 | core/, storage/ |
| **CategorizationEngine** | 归类编译、复用规则引擎 | 个人知识结构化 | 对齐 m-flow 的 Facet 归类 + KAG 的概念对齐 | core/, RuleEngine |
| **QueryEngine** | 图查询、向量检索、混合融合 | 三层资产联合查询 | 对齐 m-flow 的 Bundle Search + KAG 的混合检索 | storage/ |
| **ExpressionEngine** | L0/L1 两级安全执行 | IT 资产计算安全 | 对齐 KAG 的 Logical Form 执行 | core/ |

**边界约束**：
- `engine/` 禁止直接调 `storage/local/`
- 规则执行通过 storage 接口读写
- MetricEngine → RuleEngine 直接调用（无中间写入）

### 服务层 (L3)

| 服务 | 编排职责 | 资产链接 | 对齐 m-flow/KAG |
|------|----------|----------|------------------|
| **SchemaService** | Schema CRUD + 版本管理 | 组织资产生命周期 | 对齐 KAG 的 Schema 管理 |
| **EntityService** | 实体/关系 CRUD + 快照 | IT 资产实例管理 | 对齐 m-flow 的 Episode 管理 |
| **AnalysisService** | 指标/规则编排执行 | 个人→组织知识转化 | 对齐 m-flow 的 Episodic 检索 + Procedural 检索 |
| **QueryService** | 查询路由 + 混合检索 | 三层资产联合访问 | 对齐 m-flow 的 Memory Orchestrator |
| **IngestionService** | 数据导入 + 增量更新 | IT 资产接入 | 对齐 KAG 的 Builder Pipeline |
| **VisualizationService** | Schema 图/规则链/模拟 | 资产可视化与解释 | 对齐 m-flow 的 Cone Graph 可视化 |
| **DatasetService** | 数据集管理 + diff | IT 资产版本管理 | 对齐 KAG 的版本管理 |
| **IncrementalUpdateService** | 变更检测 + 影响分析 | 资产变更传播 | 对齐 KAG 的知识更新机制 |

### API 层 (L4)

| 接口 | 用途 | 资产面 | 阶段 |
|------|------|--------|------|
| **FastAPI REST** | 通用 API | 管理面 + 消费面 | Phase 1 |
| **MCP Agent 协议** | Agent 工具调用 | 消费面（Agent 交互中沉淀个人资产） | Phase 2 |
| **CLI** | 命令行管理 | 管理面 | Phase 1 |

## 调用关系

```
api/ ───────▶ services/ ───────▶ engine/ ───────▶ storage/
 │                │                │                │
 │                │                │                ▼
 │                │                │           storage/base.py
 │                │                │                │
 │                │                │                ▼
 │                │                │         storage/local/
 │                │                │
 │                │                ▼
 │                │           core/schema/
 │                │           core/operators/
 │                │
 │                ▼
 │         visualization/
 │         mcp/tools/
 │
 ▼
examples/*/schema.yaml  ← 三类资产定义入口（IT 资产 / 个人资产 / 组织资产）
```

## 关键约束

1. **本地优先**: L1 层必须有本地实现，外部存储为可选
2. **无循环依赖**: 模块依赖只能向下，禁止平级/向上
3. **Schema 驱动**: 业务逻辑在 YAML 定义，非代码
4. **三层资产统一模型**: IT 资产、个人知识、组织资产使用同一本体（KGML）描述
5. **资产可链接**: 存储层维护三层资产间的显式关系，引擎层负责推理

## 对齐 m-flow 的四层 Cone Graph

| m-flow 概念 | OntologyEngine 对应 | 映射关系 |
|--------------|-------------------|----------|
| **Episode**（场景存储） | L1 事实层（IT 资产实例） | 存储完整的业务场景（如贷款申请记录） |
| **Facet**（维度分类） | L2 归类层（个人归类规则） | 从多个维度对场景进行分类（如行业、规模、风险等级） |
| **FacetPoint**（原子断言） | L3 分析层（指标计算） | 从维度中提取具体的指标值（如信用分=720） |
| **Entity**（命名实体） | Schema 实体定义 | 跨场景的实体关联（如客户ID、产品代码） |

## 对齐 KAG 的逻辑形式引导推理

| KAG 概念 | OntologyEngine 对应 | 映射关系 |
|-----------|-------------------|----------|
| **Logical Form Planner**（逻辑形式规划） | L2 归类层 + L3 分析层 | 将业务问题分解为可执行的逻辑形式（如归类、计算、决策） |
| **Executor**（执行器） | L4 规则引擎 | 执行逻辑形式，包括 op_deduce（演绎）和 op_retrieval（检索） |
| **OpenSPG 引擎** | Schema 驱动的图存储 | 统一的本体模型，支持结构化知识推理 |
| **互索引结构** | IT↔组织资产的双向关联 + 知识碎片↔结构化知识的双向链接 | 四种互索引关系（extracted_from/supported_by/defined_in/trace_to），支持从任一端导航到另一端 |

---

*参考：[M-flow Retrieval Architecture](https://github.com/FlowElement-ai/m_flow/blob/main/docs/RETRIEVAL_ARCHITECTURE.md) | [KAG Core Architecture](https://deepwiki.com/OpenSPG/KAG/2-core-architecture)*

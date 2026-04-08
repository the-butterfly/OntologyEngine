# 模块架构

## 分层视图

```
┌─────────────────────────────────────────┐
│ L3: API 层                              │
│   FastAPI / GraphQL / gRPC / MCP        │
├─────────────────────────────────────────┤
│ L2: 引擎层                              │
│   ├─ QueryEngine   (查询/检索)          │
│   ├─ RuleEngine    (规则/DAG执行)       │
│   ├─ MetricEngine  (指标计算)           │
│   └─ VectorEngine  (向量/语义)          │
├─────────────────────────────────────────┤
│ L1: 存储层                              │
│   ├─ DuckDBStorage   (实体/关系/元数据) │
│   ├─ FaissVectorStore (向量索引)        │
│   └─ NetworkXGraph   (图算法，按需)     │
├─────────────────────────────────────────┤
│ L0: 核心层                              │
│   ├─ SchemaLoader    (KGML解析)         │
│   ├─ OperatorRegistry (算子注册)        │
│   └─ ExpressionEngine (表达式)          │
└─────────────────────────────────────────┘
```

## 模块职责

### 核心层 (L0)

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| SchemaLoader | 解析 KGML YAML | schema.yaml | Pydantic 模型 |
| OperatorRegistry | 算子发现与注册 | 算子实现类 | 可执行算子池 |
| ExpressionEngine | 表达式解析执行 | `score > 80` | 布尔结果/数值 |

### 存储层 (L1)

| 模块 | 本地实现 | 预留接口 | 数据文件 |
|------|----------|----------|----------|
| DuckDBStorage | ✅ | - | `data/ontology.db` |
| FaissVectorStore | ✅ | pgvector | `data/vectors/` |
| NetworkXGraph | 按需加载 | Neo4j | 内存 |

**边界约束**:
- 上层只能调用 `storage/base.py` 接口
- `local/` 只实现接口，不依赖上层

### 引擎层 (L2)

| 模块 | 核心功能 | 依赖 |
|------|----------|------|
| QueryEngine | 图查询、向量检索、混合 | storage/ |
| RuleEngine | DAG解析、拓扑执行、回滚 | core/, storage/ |
| MetricEngine | 指标计算、缓存、增量更新 | core/, storage/ |
| VectorEngine | Embedding、索引、相似度 | storage/vector/ |

**边界约束**:
- `engine/` 禁止直接调 `storage/local/`
- 规则执行通过 storage 接口读写

### API 层 (L3)

| 接口 | 用途 | 阶段 |
|------|------|------|
| FastAPI | 通用 REST | Phase 1 |
| GraphQL | 灵活查询 | Phase 2 |
| gRPC | 高性能内部调用 | Phase 2 |
| MCP | Agent 协议 | Phase 2 |

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
 │         ontology_engine/toolchain
 │
 ▼
examples/*/schema.yaml
```

## 关键约束

1. **本地优先**: L1 层必须有本地实现，外部存储为可选
2. **无循环依赖**: 模块依赖只能向下，禁止平级/向上
3. **Schema 驱动**: 业务逻辑在 YAML 定义，非代码

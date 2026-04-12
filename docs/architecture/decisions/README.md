# Architecture Decisions

> Collected decisions from critical review and implementation learning.

## Decision Index

| ID | Title | Status | Date |
|----|-------|--------|------|
| ADR-001 | SQLite + NetworkX Storage Strategy | Deprecated | 2026-04-07 |
| ADR-002 | FaissVectorStore Persistence | Pending | 2026-04-07 |
| ADR-003 | Expression Engine Security | Pending | 2026-04-07 |
| ADR-004 | KGML/LinkML Integration | Pending | 2026-04-07 |
| ADR-005 | Agent Memory Design | Pending | 2026-04-07 |
| ADR-006 | DuckDB + NetworkX Hybrid Storage | Accepted | 2026-04-08 |
| ADR-007 | L3/L4 计算边界划分 | Accepted | 2026-04-12 |
| ADR-008 | Rule 模型统一 | Accepted | 2026-04-12 |
| ADR-009 | API 架构演进策略 | Accepted | 2026-04-12 |
| ADR-010 | Semantic Space 生命周期管理 | Accepted | 2026-04-12 |

### By Category

#### 存储 (Storage)
- [ADR-001](./001-sqlite-networkx-storage.md) - SQLite + NetworkX 存储策略
- [ADR-002](./002-faiss-vector-store-persistence.md) - FaissVectorStore 持久化
- [ADR-006](./006-duckdb-networkx-hybrid-storage.md) - DuckDB + NetworkX 混合存储

#### 安全 (Security)
- [ADR-003](./003-expression-engine-security.md) - 表达式引擎安全

#### 集成 (Integration)
- [ADR-004](./004-kgml-linkml-integration.md) - KGML/LinkML 集成

#### 架构 (Architecture)
- [ADR-005](./005-agent-memory-design.md) - Agent 内存设计
- [ADR-007](./007-l3-l4-computation-boundary.md) - L3/L4 计算边界划分
- [ADR-008](./008-rule-model-unification.md) - Rule 模型统一
- [ADR-009](./009-api-architecture-evolution.md) - API 架构演进策略
- [ADR-010](./010-semantic-space-lifecycle.md) - Semantic Space 生命周期管理

---

## ADR Details

### ADR-001: SQLite + NetworkX Storage Strategy
- **状态**: Deprecated
- **摘要**: 采用 SQLite + NetworkX 作为存储引擎，后因性能和扩展性问题被 ADR-006 取代
- **相关 ADR**: [ADR-006](./006-duckdb-networkx-hybrid-storage.md)

### ADR-002: FaissVectorStore Persistence
- **状态**: Pending
- **摘要**: Faiss 向量存储的持久化策略，待 Schema v2 存储层设计稳定后实现
- **相关 ADR**: [ADR-006](./006-duckdb-networkx-hybrid-storage.md)

### ADR-003: Expression Engine Security
- **状态**: Pending
- **摘要**: 表达式执行引擎的安全沙箱机制，防止恶意代码执行
- **相关 ADR**: [ADR-007](./007-l3-l4-computation-boundary.md)

### ADR-004: KGML/LinkML Integration
- **状态**: Pending
- **摘要**: 与 KGML/LinkML 的集成策略，支持外部 Schema 导入

### ADR-005: Agent Memory Design
- **状态**: Pending
- **摘要**: Agent 内存管理的设计，支持短期和长期记忆

### ADR-006: DuckDB + NetworkX Hybrid Storage
- **状态**: Accepted
- **摘要**: 采用 DuckDB + NetworkX 混合存储替代 SQLite，支持高效的关系和图查询
- **相关 ADR**: [ADR-001](./001-sqlite-networkx-storage.md), [ADR-002](./002-faiss-vector-store-persistence.md)

### ADR-007: L3/L4 计算边界划分
- **状态**: Accepted
- **摘要**: 明确 L3 (analytical_elements) 和 L4 (business_logic) 的计算职责边界，L3 负责声明+可选标准公式，L4 负责具体计算逻辑编排
- **相关 ADR**: [ADR-003](./003-expression-engine-security.md), [ADR-004](./004-kgml-linkml-integration.md)

### ADR-008: Rule 模型统一
- **状态**: Accepted
- **摘要**: 统一新旧两套 Rule 模型，采用 `rule_definitions + rule_logics` 双轨结构作为 canonical 标准
- **相关 ADR**: [ADR-003](./003-expression-engine-security.md)

### ADR-009: API 架构演进策略
- **状态**: Accepted
- **摘要**: 明确区分 Current API (v1 工程导向) 和 Target API (v2 平台化空间导向)，采取渐进式演进策略
- **相关 ADR**: [ADR-010](./010-semantic-space-lifecycle.md)

### ADR-010: Semantic Space 生命周期管理
- **状态**: Accepted
- **摘要**: 定义语义空间的生命周期状态机和管理策略，支持空间的创建、激活、归档和销毁
- **相关 ADR**: [ADR-009](./009-api-architecture-evolution.md)

---

## Creating New Decisions

When a significant architectural decision is made:

1. Create `docs/architecture/decisions/XXX-title.md`
2. Follow ADR format (Status, Context, Decision, Consequences)
3. Update this index
4. Commit with `docs: add ADR-XXX`

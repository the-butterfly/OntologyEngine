# RFC-012: kuzu 图存储升级

> **状态**: draft
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **创建日期**: 2026-04-14
> **作者**: the-butterfly
> **评审截止**: 待定

## 动机

Phase 1 使用 NetworkX 作为内存图存储，在实体数量超过 1K 时面临：
- 内存占用线性增长，无法持久化
- 图遍历性能随节点数 O(n) 退化
- 无法支持并发读写

Phase 1 node target: **100K 节点**，NetworkX 无法满足。

## 设计目标

1. **性能**: 100K 节点 + 200K 边图遍历 < 100ms
2. **持久化**: 图数据落盘，重启不丢失
3. **向后兼容**: 不破坏现有 DuckDB Entity/Relation 表的存储格式
4. **双写协调**: Entity 创建时同时写入 DuckDB + kuzu

## 架构

```
                    ┌─────────────────────────────┐
                    │     OntologyEngine          │
                    │                             │
  ┌──────────────┐  │  ┌─────────────────────┐  │
  │ DuckDB       │  │  │ GraphStoreBackend ABC │  │
  │ (Entity/Rel/ │◄─┼──│                     │  │
  │  Metric/...) │  │  └──────────┬──────────┘  │
  └──────────────┘  │             │               │
                    │  ┌──────────▼──────────┐  │
                    │  │ DualWriteCoordinator │  │
                    │  └──────────┬──────────┘  │
                    │             │               │
                    │    ┌────────┴────────┐     │
                    │    │                 │     │
                    │    ▼                 ▼     │
                    │ ┌──────┐       ┌────────┐ │
                    │ │kuzu  │       │NetworkX│ │
                    │ │(prod)│       │(dev/   │ │
                    │ └──────┘       │fallback)│ │
                    │                 └────────┘ │
                    └─────────────────────────────┘
```

## 关键设计决策

### Q1: kuzu 数据库文件放在哪里？

**决策**: `~/.ontology_engine/data/` 下，按 space_id 子目录隔离：`~/.ontology_engine/data/{space_id}/graph.kuzu`

### Q2: 如何处理 DuckDB 和 kuzu 数据不一致？

**决策**: `DualWriteCoordinator` 使用"先 DuckDB 再 kuzu"顺序，写入后记录同步状态。若 kuzu 写入失败：
- 开发模式（`NETWORKX_FALLBACK=1`）：回退到 NetworkX，记录 WARN
- 生产模式：抛出异常，标记 entity 为"图同步待处理"

### Q3: kuzu Schema 如何与 DuckDB entity_schema 映射？

**决策**: kuzu 使用固定的节点/边 Schema，与具体 space 无关：

```cypher
CREATE NODE TABLE Entity(
    entity_id STRING PRIMARY KEY,
    concept STRING NOT NULL,
    space_id STRING NOT NULL,
    properties JSON,
    PRIMARY KEY(entity_id)
);

CREATE REL TABLE Relation(
    FROM Entity TO Entity,
    relation_type STRING NOT NULL,
    relation_id STRING,
    properties JSON,
    PRIMARY KEY(FROM, TO, relation_type)
);
```

## 实现范围

### 包含
- [ ] `KuzuGraphStore` 实现 `GraphStoreBackend` 接口
- [ ] `DualWriteCoordinator` 双写协调器
- [ ] DuckDB → kuzu 数据迁移脚本
- [ ] NetworkX fallback 模式（开发用）
- [ ] Phase 1 node target 基准测试（100K 节点）

### 不包含
- kuzu 的 Schema 动态扩展（Phase 3）
- 分布式 kuzu 集群（Phase 3）
- 图算法引擎（PageRank / LPA 等，Phase 3）

## 相关文档

- **ADR-006** — [DuckDB + NetworkX 混合存储](../architecture/decisions/006-duckdb-networkx-hybrid-storage.md)
- **07-phase1-enhancement** — [图存储扩展](../07-phase1-enhancement/01-graph-storage-extension.md)

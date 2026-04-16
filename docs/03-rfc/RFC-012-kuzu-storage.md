# RFC-012: kuzu 图存储升级

> **状态**: implementation-ready
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **创建日期**: 2026-04-14
> **作者**: the-butterfly
> **最后更新**: 2026-04-15
> **评审截止**: 2026-04-16

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
- [ ] `get_neighbors` 增加 `node_concept` 下推参数
- [ ] `execute_cypher` 原生 Cypher 支持
- [ ] `DualWriteCoordinator` 双写协调器
- [ ] DuckDB → kuzu 数据迁移脚本
- [ ] Phase 1 node target 基准测试（100K 节点）

### 不包含
- kuzu 的 Schema 动态扩展（Phase 3）
- 分布式 kuzu 集群（Phase 3）
- 图算法引擎（PageRank / LPA 等，Phase 3）

---

## 实现细节

### 1. 文件结构

```
ontology_engine/storage/graph/
├── __init__.py
├── networkx_store.py      # 保留作 dev/fallback
└── kuzu_store.py          # 新增：KuzuGraphStore
```

### 2. KuzuGraphStore 实现

#### 2.1 基础接口

```python
# ontology_engine/storage/graph/kuzu_store.py
import kuzu

class KuzuGraphStore(GraphStoreBackend):
    def __init__(self):
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None
        self._initialized = False

    async def initialize(self, db_path: str | None = None) -> None:
        # db_path 格式: ~/.ontology_engine/data/{space_id}/graph.kuzu
        # 若未指定，使用空间隔离的默认路径
        path = db_path or self._default_path()
        self._db = kuzu.Database(path)
        self._conn = kuzu.Connection(self._db)
        await self._ensure_schema()

    def _default_path(self) -> str:
        """返回 ~/.ontology_engine/data/{space_id}/graph.kuzu"""
        import os
        base = os.path.expanduser("~/.ontology_engine/data")
        # 默认 space_id 为 "default"，实际使用时由调用方传入具体 path
        return os.path.join(base, "default", "graph.kuzu")

    async def _ensure_schema(self) -> None:
        """创建节点/边表（若不存在）"""
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity(
                entity_id STRING PRIMARY KEY,
                concept STRING NOT NULL,
                space_id STRING NOT NULL,
                properties JSON,
                PRIMARY KEY(entity_id)
            )
        """)
        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS Relation(
                FROM Entity TO Entity,
                relation_type STRING NOT NULL,
                relation_id STRING,
                properties JSON,
                PRIMARY KEY(FROM, TO, relation_type)
            )
        """)
```

#### 2.2 get_neighbors with node_concept 下推

```python
async def get_neighbors(
    self,
    node_id: str,
    edge_type: str | None = None,
    direction: str = "outgoing",
    limit: int = 100,
    filter_props: dict[str, Any] | None = None,
    node_concept: str | None = None,  # 新增参数
) -> list[dict[str, Any]]:
    """kuzu 原生实现：node_concept 条件下推至 WHERE 子句"""
    # 方向映射
    arrow = {
        "outgoing": "->",
        "incoming": "<-",
        "both": "-",
    }[direction]

    rel_match = f"[r:Relation {{relation_type: '{edge_type}'}}]" if edge_type else "[r:Relation]"
    where_clause = f"WHERE n.concept = '{node_concept}'" if node_concept else ""
    limit_clause = f"LIMIT {limit}"

    cypher = f"""
        MATCH (src:Entity {{entity_id: '{node_id}'}}){arrow}{rel_match}{arrow}(n:Entity)
        {where_clause}
        RETURN n.entity_id AS neighbor_id, r.relation_type AS edge_type,
               r.relation_id AS edge_id, type(r) AS rel_table
        {limit_clause}
    """
    result = self._conn.execute(cypher)
    return [dict(row) for row in result.get_as_df().to_dict("records")]
```

#### 2.3 execute_cypher 原生支持

```python
async def execute_cypher(
    self,
    query: str,
    parameters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """执行原生 Cypher 查询，返回结果列表"""
    self._ensure_initialized()
    result = self._conn.execute(query, parameters or {})
    return [dict(row) for row in result.get_as_df().to_dict("records")]
```

### 3. graph_pattern_match 实现策略

#### 3.1 路径长度判断

```python
# retrieval.py - DefaultRetrievalBackend.graph_pattern_match
async def graph_pattern_match(
    self,
    start_concept: str,
    path_pattern: list[tuple[str, str]],
    start_filters: dict[str, Any] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:

    path_length = len(path_pattern)  # hop 数

    if path_length <= 2:
        # 短路径：get_neighbors 多跳（低延迟）
        return await self._traverse_short_path(...)
    else:
        # 长路径：Cypher 原生 MATCH（kuzu 优化器全局优化）
        return await self._execute_cypher_pattern(...)
```

#### 3.2 Cypher 原生模式

```python
async def _execute_cypher_pattern(
    self,
    start_concept: str,
    path_pattern: list[tuple[str, str]],
    start_filters: dict[str, Any] | None,
    limit: int,
) -> list[dict[str, Any]]:
    """构造 Cypher MATCH 语句并执行"""
    # 构建 MATCH 模式
    # (start)-[r0:{rel0}]->(n1:{concept1})-[r1:{rel1}]->(n2:{concept2})...
    segments = [f"(start:Entity {{concept: '{start_concept}'}})"]
    for i, (rel_type, target_concept) in enumerate(path_pattern):
        segments.append(f"-[r{i}:Relation {{relation_type: '{rel_type}'}}]->")
        segments.append(f"(n{i+1}:Entity {{concept: '{target_concept}'}})")

    cypher = "MATCH " + "".join(segments)

    # WHERE 子句（start_filters）
    if start_filters:
        where_parts = [f"start.{k} = '{v}'" for k, v in start_filters.items()]
        cypher += " WHERE " + " AND ".join(where_parts)

    # RETURN + LIMIT
    return_cols = ["start.entity_id"] + [f"n{i+1}.entity_id" for i in range(len(path_pattern))]
    cypher += f" RETURN {', '.join(return_cols)} LIMIT {limit}"

    result = await self.graph.execute_cypher(cypher)
    return [self._format_pattern_result(row) for row in result]
```

### 4. hybrid_search 扩展

#### 4.1 新增参数

```python
async def hybrid_search(
    self,
    query_text: str | None = None,
    query_vector: list[float] | None = None,
    graph_seed_id: str | None = None,
    top_k: int = 10,
    semantic_weight: float = 0.6,
    graph_weight: float = 0.4,
    fusion_strategy: str = "independent_then_fuse",
    # --- 新增 ---
    path_pattern: list[tuple[str, str]] | None = None,
    path_weight: float = 0.2,
) -> HybridSearchResult:
```

#### 4.2 三种融合策略

| 策略 | 语义 |
|------|------|
| `filter_then_fuse` | path_pattern 过滤候选集 → 再与语义腿融合 |
| `independent_then_fuse` | 语义分 + 图扩展分 + 路径匹配分各自独立 → 融合（默认） |
| `fuse_then_filter` | 先三者融合 → 再 path_pattern 过滤 |

#### 4.3 路径匹配得分规则

- **无权边**：0/1 二值（匹配到 = 1，否则 = 0）
- **有权边**：边的权重归一化（0~1）
- 多路径覆盖：取最高分

#### 4.4 返回结构

> **注意**: `HybridSearchResult` 需新增定义于 `storage/base.py`

```python
@dataclass
class HybridSearchResult:
    results: list[VectorSearchResult]         # 最终结果（id/score/metadata）
    semantic_scores: dict[str, float]        # {entity_id: cosine_score}
    graph_scores: dict[str, float]           # {entity_id: proximity_score}
    path_match_scores: dict[str, float]       # {entity_id: path_score}
    fusion_metadata: dict[str, Any]           # {strategy, weights, candidate_count}
```

### 5. DualWriteCoordinator

```python
class DualWriteCoordinator:
    """实体创建时同时写入 DuckDB + kuzu"""

    async def save_entity_with_graph(
        self,
        entity: EntityInstance,
        relations: list[RelationInstance] | None = None,
    ) -> str:
        # Step 1: DuckDB 写入（主存储）
        entity_id = await self.storage.save_entity(entity)

        # Step 2: kuzu 写入节点
        await self.graph.upsert_node(
            node_id=entity_id,
            labels=[entity.concept],
            properties=entity.data,
        )

        # Step 3: kuzu 写入边
        if relations:
            for rel in relations:
                await self.graph.upsert_edge(...)

        return entity_id
```

失败时标记 entity 为"图同步待处理"，由后台任务重试。

### 6. DuckDB → kuzu 迁移脚本

```python
# scripts/migrate_graph_to_kuzu.py
async def migrate_graph_data(
    storage: StorageBackend,
    kuzu_store: KuzuGraphStore,
    batch_size: int = 1000,
):
    """从 DuckDB 批量读取关系数据，写入 kuzu"""
    # 1. 遍历所有 entity，写入 kuzu Entity 节点
    # 2. 遍历所有 relation，写入 kuzu Relation 边
    # 3. 记录迁移进度（checkpoint）
```

### 7. 实现 Checklist

- [ ] `KuzuGraphStore` 实现 `GraphStoreBackend` 接口
- [ ] `get_neighbors` 增加 `node_concept` 下推参数
- [ ] `execute_cypher` 原生 Cypher 支持
- [ ] `DefaultRetrievalBackend` 短路径（≤2-hop）走 `get_neighbors` 多跳，复杂路径走 Cypher 原生 MATCH
- [ ] `hybrid_search` 增加 `path_pattern` + `path_weight` 参数
- [ ] `hybrid_search` 返回 `HybridSearchResult`（含过程值）
- [ ] `DualWriteCoordinator` 实现
- [ ] DuckDB → kuzu 迁移脚本
- [ ] 单元测试（`test_kuzu_graph_store.py`）
- [ ] 集成测试（`test_kuzu_pattern_match.py`）

### 8. 依赖项

- `kuzu` Python binding: `pip install kuzu`
- 需在 `pyproject.toml` 新增可选依赖

## 相关文档

- **ADR-006** — [DuckDB + NetworkX 混合存储](../architecture/decisions/006-duckdb-networkx-hybrid-storage.md)
- **07-phase1-enhancement** — [图存储扩展](../07-phase1-enhancement/01-graph-storage-extension.md)

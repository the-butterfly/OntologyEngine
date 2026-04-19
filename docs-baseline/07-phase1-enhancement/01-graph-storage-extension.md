# 01: 存储层图数据库扩展设计

---
status: draft
phase: phase1
source_of_truth: true   # [单一事实源] 图存储扩展设计的唯一规范
last_verified: 2026-04-13
verified_against: docs-only
related_docs:
  - ../06-module-detailed-design/03-storage-layer.md
  - ../05-schema-v2/01-fact-objects.md
  - ../development/storage-adapter.md
related_adrs:
  - architecture/decisions/004-kgml-linkml-integration.md
---

## 1. 背景与动机

### 1.1 现状

当前存储架构：

```
StorageBackend (ABC)
  └── DuckDBStorage (唯一实现)
       ├── entities / relations 表 (关系型)
       ├── computed_metrics / category_tags 表
       └── rule_execution_log 表

图算法能力:
  └── NetworkXGraphStore (按需加载子图到内存)
       └── 从 DuckDB JOIN 查询构建 NetworkX 图 → 执行算法
```

**核心瓶颈**：
- 图遍历（邻居查询、路径搜索、环检测）需要多表 JOIN + 应用层构建 NetworkX 图，性能差
- DuckDB 无原生图查询能力（无 Cypher-like 语法）
- 深度遍历（>2 跳）需多次 DB 往返，延迟线性增长
- 无法利用图索引加速模式匹配

### 1.2 目标

引入**嵌入式图数据库**作为存储层的图能力补充，形成**混合存储架构**：

```
StorageBackend (ABC) ← 保持不变
  ├── DuckDBStorage     ← 主存储（实体/关系属性/指标/日志）
  │
  └── GraphStoreBackend (新增 ABC) ← 图专用存储
       ├── KuzuGraphStore    ← Phase 1: 嵌入式图数据库 (推荐)
       └── Neo4jGraphStore   ← Phase 2: 远程图数据库 (预留适配器)
```

### 1.3 为什么选择 Kuzu

| 特性 | Kuzu | Neo4j | NetworkX (当前) |
|------|------|-------|------------------|
| **部署模式** | 嵌入式（库级别） | 服务端（独立进程） | 内存中 |
| **依赖** | `pip install kuzu` | 需要运行 Neo4j Server | 已有 |
| **查询语言** | Cypher (子集) | 完整 Cypher | Python API |
| **图原生存储** | ✅ 列式节点/边存储 | ✅ 行式+索引 | ❌ 需从外部加载 |
| **嵌入便利性** | ✅ Python import 即用 | ❌ 需连接管理 | ✅ |
| **并发模型** | 单写多读（内置锁） | 多写多读 | 单线程 |
| **许可证** | MIT | GPL/Commercial | BSD |
| **适用场景** | 本地/单机 | 分布式/集群 | 小规模原型 |

**决策**: Phase 1 选择 **Kuzu** 作为嵌入式图存储，原因：
1. **零运维** —— 无需启动额外服务，与 DuckDB 一样嵌入应用进程
2. **Cypher 兼容** —— 未来迁移 Neo4j 时查询语句可复用
3. **列式存储** —— 分析型场景（图指标计算）性能优秀
4. **MIT 许可** —— 商业友好

## 2. 架构设计

### 2.1 GraphStoreBackend 抽象接口

```python
# storage/base.py (扩展)

class GraphStoreBackend(ABC):
    """图存储抽象接口 —— 提供图原生存储和查询能力。

    设计原则:
    - 与 StorageBackend 正交：StorageBackend 负责「实体/关系的属性存储」，
      GraphStoreBackend 负责「图的拓扑结构和图查询」。
    - 双写策略: 写入时同时更新 DuckDB (属性) + 图库 (拓扑)。
    - 读取时根据查询类型自动路由: 属性查询走 DuckDB, 图查询走图库。
    """

    # --- 生命周期 ---
    @abstractmethod
    async def initialize(self, db_path: str | None = None) -> None:
        """初始化图存储。

        Args:
            db_path: 图数据库文件路径。None 表示内存模式。
        """

    @abstractmethod
    async def close(self) -> None:
        """释放资源。"""

    # --- 节点管理 (映射到 L1 Fact Objects) ---
    @abstractmethod
    async def upsert_node(
        self,
        node_id: str,
        labels: list[str],          # 对应 concept 类型，如 ["Company", "Supplier"]
        properties: dict[str, Any],  # 节点属性 (冗余存储，加速图查询过滤)
    ) -> None:
        """创建或更新节点。"""

    @abstractmethod
    async def get_node(
        self, node_id: str
    ) -> dict[str, Any] | None:
        """获取单个节点。"""

    @abstractmethod
    async def delete_node(self, node_id: str) -> None:
        """删除节点及其所有关联边。"""

    # --- 边管理 (映射到 L1 Relations) ---
    @abstractmethod
    async def upsert_edge(
        self,
        edge_id: str,                # 全局唯一边 ID
        from_node_id: str,
        to_node_id: str,
        edge_type: str,              # 关系类型，如 "Guarantee", "Transaction"
        properties: dict[str, Any] = {},
    ) -> None:
        """创建或更新边。"""

    @abstractmethod
    async def get_edges(
        self,
        from_node_id: str | None = None,
        to_node_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询边。"""

    @abstractmethod
    async def delete_edge(self, edge_id: str) -> None:
        """删除边。"""

    # --- 图查询 (核心差异化能力) ---

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",   # "outgoing" | "incoming" | "both"
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """获取节点的邻居 (1-hop)。

        Returns:
            邻居列表，每项包含 {node, edge} 信息。
        """

    @abstractmethod
    async def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_depth: int = 3,
        edge_types: list[str] | None = None,
    ) -> list[list[dict]]:
        """查找路径。

        Args:
            source_id: 起始节点
            target_id: 目标节点。None 表示找所有从 source 出发的路径
            max_depth: 最大深度
            edge_types: 限制边类型

        Returns:
            路径列表，每条路径是 [node, edge, node, ...] 的序列
        """

    @abstractmethod
    async def detect_cycles(
        self,
        center_id: str,
        edge_types: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[list[str]]:
        """检测环路。

        供应链金融场景: 检测担保圈 (A→B→C→A)

        Returns:
            环路列表，每条环路是 [node_id, ...] 的序列
        """

    @abstractmethod
    async def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """执行 Cypher 查询 (高级接口)。

        用于复杂图模式匹配。实现方应做安全校验（只读白名单）。

        Raises:
            GraphQueryError: 查询语法错误或执行失败
        """

    # --- 图算法 ---
    @abstractmethod
    async def compute_graph_metric(
        self,
        algorithm: str,              # "centrality" | "component" | "community"
        node_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行图算法。

        支持的算法:
        - centrality: betweenness / closeness / pagerank (指定 node 或全图)
        - component: weakly_connected / strongly_connected (返回组件归属)
        - community: louvain / label_propagation (社区发现)
        """

    # --- 批量操作 ---
    @abstractmethod
    async def batch_upsert(
        self,
        nodes: list[dict] | None = None,
        edges: list[dict] | None = None,
    ) -> dict[str, int]:
        """批量写入节点和边。

        Returns:
            {"nodes_written": N, "edges_written": M}
        """
```

### 2.2 KuzuGraphStore 实现

```python
# storage/graph/kuzu_store.py

import kuzu
from typing import Any
from storage.base import GraphStoreBackend, GraphQueryError


class KuzuGraphStore(GraphStoreBackend):
    """基于 Kuzu 嵌入式图数据库的 GraphStoreBackend 实现。

    数据模型映射:
    - L1 Fact Object (Company, Supplier, ...) → Kuzu Node Table (label = concept 名)
    - L1 Relation (Guarantee, Transaction, ...) → Kuzu Edge Table (label = relation 名)
    - 每个 concept 创建一个 Node Table
    - 每个 relation_type 创建一个 Edge Table
    """

    def __init__(self, db_path: str | None = ":memory:"):
        self.db_path = db_path or ":memory:"
        self._db: kuzu.Database | None = None
        self._conn: kuzu.Connection | None = None
        self._table_registry: dict[str, str] = {}  # concept → table_name mapping
        self._edge_table_registry: dict[str, str] = {}  # rel_type → table_name

    async def initialize(self, db_path: str | None = None) -> None:
        path = db_path or self.db_path
        self._db = kuzu.Database(path)
        self._conn = kuzu.Connection(self._db)

        # 初始化 Schema（懒创建：首次写入时按需建表）
        self._ensure_system_tables()

    def _ensure_system_tables(self):
        """确保系统元表存在。"""
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS _Meta (
                key STRING,
                value STRING,
                PRIMARY KEY (key)
            )
        """)

    # --- 表管理 (Schema 同步) ---

    def _ensure_node_table(self, concept: str) -> str:
        """确保概念对应的 Node Table 存在。

        Kuzu 要求先定义 schema 再插入数据。
        使用通用属性 bag (JSON-like) 存储异构属性。
        """
        if concept in self._table_registry:
            return self._table_registry[concept]

        table_name = f"node_{concept}"
        # 转义概念名中的特殊字符
        safe_name = table_name.replace("-", "_").replace(" ", "_")

        try:
            self._conn.execute(f"""
                CREATE NODE TABLE IF NOT EXISTS {safe_name} (
                    id STRING,
                    _concept STRING,
                    _created_at TIMESTAMP,
                    PRIMARY KEY (id)
                )
            """)
            self._table_registry[concept] = safe_name
            return safe_name
        except Exception as e:
            raise GraphQueryError(f"Failed to create node table for '{concept}': {e}")

    def _ensure_edge_table(self, relation_type: str) -> str:
        """确保关系类型对应的 Edge Table 存在。"""
        if relation_type in self._edge_table_registry:
            return self._edge_table_registry[relation_type]

        table_name = f"edge_{relation_type}"
        safe_name = table_name.replace("-", "_").replace(" ", "_")

        try:
            self._conn.execute(f"""
                CREATE EDGE TABLE IF NOT EXISTS {safe_name} (
                    id STRING,
                    from_id STRING,
                    to_id STRING,
                    _properties STRING,   # JSON string for flexible attributes
                    _created_at TIMESTAMP,
                    PRIMARY KEY (id)
                )
            """)
            self._edge_table_registry[relation_type] = safe_name
            return safe_name
        except Exception as e:
            raise GraphQueryError(f"Failed to create edge table for '{relation_type}': {e}")

    # --- 节点/边 CRUD ---

    async def upsert_node(
        self, node_id: str, labels: list[str],
        properties: dict[str, Any]
    ) -> None:
        assert self._conn
        primary_label = labels[0] if labels else "Entity"

        # 将 properties 序列为 JSON 字符串存入通用字段
        props_json = json.dumps(properties, ensure_ascii=False, default=str)
        created_at = datetime.utcnow().isoformat()

        table = self._ensure_node_table(primary_label)

        # Kuzu UPSERT 语义: ON CONFLICT DO UPDATE
        props_pairs = ", ".join(
            f"{k} = '{self._escape_string(v)}'" for k, v in {
                "id": node_id,
                "_concept": primary_label,
                "_created_at": created_at,
            }.items()
        )

        # 动态属性: 直接写入 JSON bag 或逐字段
        # Kuzu 支持 STRUCT 类型，但为了灵活性使用 JSON
        self._conn.execute(f"""
            MERGE (n:{table} {{ id: '{self._escape_string(node_id)}' }})
            ON MATCH SET n._concept = '{primary_label}',
                       n._created_at = '{created_at}'
            ON CREATE SET n.id = '{self._escape_string(node_id)}',
                         n._concept = '{primary_label}',
                         n._created_at = '{created_at}'
        """)

    async def get_neighbors(
        self, node_id: str, edge_type: str | None = None,
        direction: str = "outgoing", limit: int = 100,
        filter_props: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        assert self._conn

        # 构建 Cypher 查询
        rel_pattern = ""
        if edge_type:
            # 查找对应的 edge table
            safe_edge = f"edge_{edge_type}".replace("-", "_")
            rel_pattern = f":[{safe_edge}]"

        if direction == "outgoing":
            match = f"(a)-{rel_pattern}->(b)"
        elif direction == "incoming":
            match = f"(a)<-{rel_pattern}-(b)"
        else:
            match = f"(a)-{rel_pattern}-(b)"

        query = f"""
            MATCH {match}
            WHERE a.id = $node_id
            RETURN b.id AS neighbor_id, labels(b) AS labels
            LIMIT $limit
        """

        result = self._conn.execute(query, {"node_id": node_id, "limit": limit})
        return [dict(row) for row in result]

    # ... (其他方法类似实现，详见完整代码)

    async def close(self) -> None:
        """释放 Kuzu 连接和数据库。"""
        # Kuzu 的 Connection 和 Database 不需要显式 close
        # 但引用置空帮助 GC
        self._conn = None
        self._db = None
```

### 2.3 双写协调器 (DualWriteCoordinator)

关键问题：写入实体时如何保证 DuckDB + Kuzu 一致性？

```python
# storage/dual_write.py

class DualWriteCoordinator:
    """协调 DuckDB (属性存储) 与 GraphStore (拓扑存储) 的双写。

    写入流程:
    1. 先写 DuckDB (主存储，不可失败)
    2. 异步写 Kuzu (图存储，失败不阻塞，记录补偿日志)
    3. 定期对账: 比较两边数据量，差异则触发全量同步

    读取流程:
    1. 属性查询 → 只读 DuckDB
    2. 图查询 (邻居/路径/环路) → 只读 Kuzu
    3. 混合查询 (带属性条件的图遍历) → Kuzu 返回拓扑 + DuckDB 补充属性
    """

    def __init__(
        self,
        storage: StorageBackend,          # DuckDB
        graph_store: GraphStoreBackend,    # Kuzu
    ):
        self.storage = storage
        self.graph = graph_store
        self._sync_log: list[dict] = []

    async def save_entity_with_graph(
        self, entity: EntityInstance, relations: list[RelationInstance] | None = None
    ) -> str:
        """保存实体并同步到图库。"""
        # Step 1: 写入 DuckDB (强一致)
        entity_id = await self.storage.save_entity(entity)

        # Step 2: 写入 Kuzu (最终一致)
        try:
            await self.graph.upsert_node(
                node_id=entity.entity_id,
                labels=[entity.concept],
                properties=entity.data,
            )
        except Exception as e:
            self._log_sync_failure("upsert_node", entity.entity_id, e)

        # Step 3: 写入关系到两个存储
        if relations:
            for rel in relations:
                await self.storage.save_relation(rel)
                try:
                    await self.graph.upsert_edge(
                        edge_id=f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_type}",
                        from_node_id=rel.from_entity_id,
                        to_node_id=rel.to_entity_id,
                        edge_type=rel.relation_type,
                        properties=rel.data or {},
                    )
                except Exception as e:
                    self._log_sync_failure("upsert_edge", rel.relation_type, e)

        return entity_id

    async def get_neighbor_details(
        self, entity_id: str, relation_type: str, direction: str = "outgoing"
    ) -> list[tuple[EntityInstance, RelationInstance]]:
        """混合查询: 图库查拓扑 + DuckDB 查属性详情。"""
        # 1. 从图库快速获取邻居 ID 列表
        neighbors = await self.graph.get_neighbors(
            node_id=entity_id, edge_type=relation_type, direction=direction
        )

        # 2. 从 DuckDB 批量获取实体详情
        result = []
        for neighbor in neighbors:
            neighbor_id = neighbor["neighbor_id"]
            entity = await self.storage.get_entity(concept=None, entity_id=neighbor_id)
            if entity:
                # 同时获取关系
                relations = await self.storage.get_relations(
                    from_entity_id=entity_id if direction != "incoming" else neighbor_id,
                    relation_type=relation_type,
                )
                rel = next((r for r in relations
                           if (direction == "outgoing" and r.to_entity_id == neighbor_id) or
                               (direction == "incoming" and r.from_entity_id == neighbor_id)),
                          None)
                result.append((entity, rel))

        return result

    def _log_sync_failure(self, operation: str, target: str, error: Exception):
        """记录图同步失败，供后续补偿。"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "target": target,
            "error": str(error),
        }
        self._sync_log.append(entry)
        # TODO: 持久化到 sync_log 表
```

### 2.4 Neo4j 适配器 (Phase 2 预留)

```python
# storage/adapters/neo4j_graph_store.py

class Neo4jGraphStore(GraphStoreBackend):
    """Neo4j 远程图数据库适配器 (Phase 2 预留)。

    接口完全兼容 GraphStoreBackend，
    内部通过 neo4j Python Driver 连接远程 Neo4j Server。
    """

    def __init__(self, uri: str, auth: tuple[str, str], database: str = "neo4j"):
        raise NotImplementedError(
            "Neo4j 适配器需安装: pip install neo4j"
            "详见 storage-adapter.md 开发指南"
        )
```

### 2.5 文件结构

```
ontology_engine/storage/
├── __init__.py                    # 导出 DualWriteCoordinator, 所有 Store 类
├── base.py                        # StorageBackend + 新增 GraphStoreBackend ABC
├── models.py                      # EntityFilter, PaginatedResult 等
├── cache.py                       # MetricCache (已有)
├── dual_write.py                  # DualWriteCoordinator (新增)
│
├── duckdb/
│   ├── __init__.py
│   └── store.py                   # DuckDBStorage (不变)
│
├── graph/                         # 图存储目录 (新增)
│   ├── __init__.py                # 导出 KuzuGraphStore, GraphStoreBackend
│   ├── kuzu_store.py             # KuzuGraphStore 实现
│   └── models.py                 # GraphQueryError, PathResult 等
│
├── adapters/                      # 外部适配器 (Phase 2)
│   ├── __init__.py
│   └── neo4j_graph_store.py      # Neo4jGraphStore (预留桩)
│
└── vector/
    └── faiss_store.py             # FaissVectorStore (已有，不动)
```

## 3. Schema 变更

### 3.1 无需变更现有 Schema 格式

图存储的 schema 是**从 KGML Schema 自动推导**的：

```python
def sync_schema_to_graph(schema: KGMLSchema, graph: GraphStoreBackend):
    """将 Schema 中的 fact_objects 和 relations 同步为图存储的表结构。

    - 每个 fact_object declaration → 一个 Node Label/Table
    - 每个 relation declaration → 一个 Edge Type/Table
    - 属性约束 (required, type) → 图存储的可选校验
    """
    for fo in schema.fact_objects:
        # 注册节点标签 (懒创建，实际在建表时触发)
        pass

    for rel in schema.relations:
        # 注册边类型 (懒创建)
        pass
```

### 3.2 配置项

```yaml
# server.py 或配置文件中启用图存储
storage:
  duck_db: ":memory:"           # 或 "data/ontologies.db"
  graph:
    backend: "kuzu"              # "kuzu" | "none" (禁用图存储)
    db_path: "data/graph.kuzu"   # Kuzu 数据库文件路径
    sync_mode: "async"           # "sync" (同步双写) | "async" (异步双写)
    # phase_2:
    # backend: "neo4j"
    # uri: "bolt://localhost:7687"
    # auth: ["neo4j", "password"]
```

## 4. 性能预期

### 4.1 对比: 当前 (DuckDB+NetworkX) vs 目标 (DuckDB+Kuzu)

| 操作 | 当前 (DuckDB+NX) | 目标 (DuckDB+Kuzu) | 提升 |
|------|-------------------|---------------------|------|
| 1-hop 邻居 | 50-100ms (JOIN) | < 10ms (原生索引) | **5-10x** |
| 2-hop 邻居 | 200-500ms (N次查询) | < 30ms (Cypher VARLENGTH) | **10x** |
| 路径搜索 (depth=3) | 500ms-2s (内存构建) | < 100ms (BFS 原生) | **5-20x** |
| 环检测 | 1-3s (NX simple_cycles) | < 200ms (Cypher PATH) | **10x** |
| 批量导入 1000 节点 | 2-5s | < 1s (批量 UPSERT) | **2-5x** |

### 4.2 SLA 更新

| 查询类型 | 原 P99 | 增强 P99 | 说明 |
|----------|--------|---------|------|
| 点查 | < 50ms | < 50ms | 不变 (DuckDB PK) |
| 邻居 (1-hop) | < 100ms | **< 20ms** | Kuzu 索引 |
| 邻居 (2-3 hop) | < 200ms | **< 50ms** | Kuzu VARLENGTH PATH |
| 路径 (depth≤3) | < 200ms | **< 100ms** | Kuzu BFS |
| 环检测 | 未定义 | **< 500ms** | Kuzu CYCLE 检测 |
| 图指标 (中心性) | < 1s | **< 500ms** | Kuzu 内置算法 |

## 5. 验收场景

### 场景 1: 供应链金融担保链深度查询

```
Given: 供应链金融 Schema (5个实体, Guarantee关系), 20个企业实例
When: 查询 CORE_001 的担保链深度
Then: 
  - 结果应与 NetworkX 计算结果一致
  - P99 < 50ms
  - Kuzu 和 DuckDB 数据一致性 100%
```

### 场景 2: 担保圈检测

```
Given: 包含 A→B→C→A 环路的实例数据
When: 执行 detect_cycles(center_id="A", edge_types=["Guarantee"])
Then: 返回环路 [A, B, C, A]
      P99 < 200ms
```

### 场景 3: 双写一致性

```
Given: 空 Kuzu 数据库 + 空 DuckDB
When: 导入 supply_chain_finance instances.yaml (8实体, 12关系)
Then: 
  - DuckDB 中 8 个实体, 12 条关系
  - Kuzu 中 8 个节点, 12 条边
  - 邻居查询两边结果等价
```

### 场景 4: 图存储降级

```
Given: 配置 graph.backend = "none"
When: 启动服务, 执行分析
Then: 图查询回退到 DuckDB JOIN + NetworkX 方式 (行为不变)
```

## 6. 迁移路径

### Phase 1 (当前)

1. 定义 `GraphStoreBackend` ABC
2. 实现 `KuzuGraphStore` (核心 CRUD + 邻居/路径/环路)
3. 实现 `DualWriteCoordinator`
4. 在 `server.py` 中可选启用
5. 图查询 API (`consumption.py`) 优先使用 `graph_store`，降级到旧逻辑

### Phase 2 (后续)

1. 实现 `Neo4jGraphStore` 适配器
2. 增加 Cypher 复杂查询支持（模式匹配、最短路径）
3. 图存储独立部署（与 DuckDB 分离服务器）
4. 图数据增量同步机制

---

*文档结束*

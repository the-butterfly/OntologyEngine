# 模块 03: 存储层

> **位置**: `ontology_engine/storage/`
> **依赖**: DuckDB, Faiss, NetworkX
> **被依赖**: 所有引擎层、服务层

## 1. 职责

1. **主存储 (DuckDB)** — 实体、关系、指标、归类标签、审计日志、Schema 版本
2. **向量索引 (Faiss)** — 语义检索
3. **图算法 (NetworkX)** — 按需加载子图，路径/中心性计算
4. **缓存 (内存 LRU)** — 热点指标缓存

## 2. 完整表设计

### 2.1 entities — 实体表

```sql
CREATE TABLE entities (
    id VARCHAR PRIMARY KEY,
    concept_type VARCHAR NOT NULL,
    attributes JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entities_type ON entities(concept_type);
-- DuckDB 支持 JSON 路径索引
CREATE INDEX idx_entities_status ON entities(attributes->>'$.status');
```

### 2.2 edges — 关系表

```sql
CREATE TABLE edges (
    id VARCHAR PRIMARY KEY,
    from_id VARCHAR NOT NULL,
    to_id VARCHAR NOT NULL,
    relation_type VARCHAR NOT NULL,
    attributes JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_edges_from ON edges(from_id);
CREATE INDEX idx_edges_to ON edges(to_id);
CREATE INDEX idx_edges_type ON edges(relation_type);
CREATE INDEX idx_edges_from_type ON edges(from_id, relation_type);
```

### 2.3 computed_metrics — 指标缓存

```sql
CREATE TABLE computed_metrics (
    entity_id VARCHAR NOT NULL,
    metric_name VARCHAR NOT NULL,
    metric_value JSON NOT NULL,
    metric_type VARCHAR NOT NULL DEFAULT 'derived',  -- atomic/derived/composite/graph
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,             -- 过期时间 (用于增量更新判断)
    PRIMARY KEY (entity_id, metric_name)
);

CREATE INDEX idx_metrics_entity ON computed_metrics(entity_id);
CREATE INDEX idx_metrics_type ON computed_metrics(metric_type);
```

### 2.4 category_tags — 归类标签

```sql
CREATE TABLE category_tags (
    entity_id VARCHAR NOT NULL,
    dimension VARCHAR NOT NULL,        -- 归类维度名 (industry, company_scale, risk_level)
    value VARCHAR NOT NULL,            -- 归类值 (C, MEDIUM, LOW)
    confidence FLOAT DEFAULT 1.0,      -- 置信度 (规则=1.0, 模型<1.0)
    source VARCHAR DEFAULT 'rule',     -- rule / model / manual
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_id, dimension)
);
```

### 2.5 rule_execution_log — 规则执行日志

```sql
CREATE TABLE rule_execution_log (
    id VARCHAR PRIMARY KEY,
    entity_id VARCHAR NOT NULL,
    dimension VARCHAR NOT NULL,
    rule_group VARCHAR,                -- L4 规则组名
    rule_id VARCHAR NOT NULL,
    rule_name VARCHAR,
    condition_result BOOLEAN,
    action_taken VARCHAR,
    output JSON,
    duration_ms INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exec_log_entity ON rule_execution_log(entity_id, dimension);
CREATE INDEX idx_exec_log_rule ON rule_execution_log(rule_id);
```

### 2.6 audit_log — 审计日志

```sql
-- 详见 02-design/03-storage-design.md，保持一致
CREATE TABLE audit_log (
    id VARCHAR PRIMARY KEY,
    operation_type VARCHAR NOT NULL,
    target_type VARCHAR NOT NULL,
    target_id VARCHAR NOT NULL,
    actor VARCHAR NOT NULL,
    before_state JSON,
    after_state JSON,
    deployment_mode VARCHAR DEFAULT 'local',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.7 schema_versions — Schema 版本

```sql
-- 详见 02-design/03-storage-design.md
CREATE TABLE schema_versions (
    id VARCHAR PRIMARY KEY,
    version INTEGER NOT NULL,
    schema_snapshot JSON NOT NULL,
    change_description VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR NOT NULL
);
```

## 3. 存储接口

```python
# storage/base.py

from abc import ABC, abstractmethod

class StorageBackend(ABC):
    """主存储抽象接口"""
    
    # --- 生命周期 ---
    @abstractmethod
    async def initialize(self) -> None: ...
    
    @abstractmethod
    async def close(self) -> None: ...
    
    # --- Entity ---
    @abstractmethod
    async def save_entity(self, entity: Entity) -> str: ...
    
    @abstractmethod
    async def get_entity(self, concept_type: str, entity_id: str) -> Entity | None: ...
    
    @abstractmethod
    async def get_entity_by_id(self, entity_id: str) -> Entity | None: ...
    
    @abstractmethod
    async def query_entities(
        self, concept_type: str | None = None,
        filters: EntityFilter | None = None,
        limit: int = 100, offset: int = 0
    ) -> PaginatedResult: ...
    
    @abstractmethod
    async def delete_entity(self, entity_id: str) -> bool: ...
    
    # --- Relation ---
    @abstractmethod
    async def save_relation(self, relation: Relation) -> str: ...
    
    @abstractmethod
    async def get_neighbors(
        self, entity_id: str,
        relation_type: str | None = None,
        direction: str = "both",
        limit: int = 100
    ) -> list[tuple[Entity, Relation]]: ...
    
    @abstractmethod
    async def get_relations(
        self, from_id: str | None = None,
        to_id: str | None = None,
        relation_type: str | None = None
    ) -> list[Relation]: ...
    
    # --- Metrics ---
    @abstractmethod
    async def save_metric(self, entity_id: str, name: str, value: Any) -> None: ...
    
    @abstractmethod
    async def get_metric(self, entity_id: str, name: str) -> Any | None: ...
    
    @abstractmethod
    async def get_metrics_batch(
        self, entity_id: str, names: list[str]
    ) -> dict[str, Any]: ...
    
    # --- Categories ---
    @abstractmethod
    async def save_category_tag(
        self, entity_id: str, dimension: str, value: str,
        confidence: float = 1.0, source: str = "rule"
    ) -> None: ...
    
    @abstractmethod
    async def get_category_tags(self, entity_id: str) -> dict[str, str]: ...
    
    # --- Execution Log ---
    @abstractmethod
    async def log_rule_execution(self, entry: RuleExecutionEntry) -> None: ...
    
    @abstractmethod
    async def get_execution_history(
        self, entity_id: str, dimension: str | None = None,
        limit: int = 50
    ) -> list[RuleExecutionEntry]: ...
    
    # --- Transaction ---
    @abstractmethod
    async def begin_transaction(self) -> Any: ...
    
    @abstractmethod
    async def commit_transaction(self, tx: Any) -> None: ...
    
    @abstractmethod
    async def rollback_transaction(self, tx: Any) -> None: ...


class VectorStoreBackend(ABC):
    """向量存储抽象接口"""
    
    @abstractmethod
    async def add_vectors(
        self, ids: list[str], vectors: np.ndarray,
        metadata: list[dict] | None = None
    ) -> None: ...
    
    @abstractmethod
    async def search(
        self, query_vector: np.ndarray, top_k: int = 10,
        filters: dict | None = None
    ) -> list[VectorSearchResult]: ...
    
    @abstractmethod
    async def delete_vectors(self, ids: list[str]) -> None: ...


class GraphAlgorithmBackend(ABC):
    """图算法抽象接口"""
    
    @abstractmethod
    def load_subgraph(
        self, center_id: str, depth: int = 2,
        relation_types: list[str] | None = None
    ) -> nx.DiGraph: ...
    
    @abstractmethod
    def find_paths(
        self, source: str, target: str,
        max_depth: int = 5
    ) -> list[list[str]]: ...
    
    @abstractmethod
    def detect_cycles(
        self, center_id: str,
        max_depth: int = 10
    ) -> list[list[str]]: ...
    
    @abstractmethod
    def calculate_centrality(
        self, node_id: str,
        method: str = "betweenness"
    ) -> float: ...
```

## 4. NetworkX 图算法集成

```python
# storage/graph/nx_store.py

class NetworkXGraphStore(GraphAlgorithmBackend):
    """基于 NetworkX 的图算法实现
    
    设计: 按需从 DuckDB 加载子图到内存，执行图算法后释放。
    不作为主存储，仅提供算法能力。
    """
    
    def __init__(self, storage: DuckDBStorage):
        self.storage = storage
        self._cache: dict[str, tuple[nx.DiGraph, float]] = {}  # LRU 缓存
        self._cache_ttl = 300.0  # 5 分钟
    
    def load_subgraph(
        self,
        center_id: str,
        depth: int = 2,
        relation_types: list[str] | None = None
    ) -> nx.DiGraph:
        """从 DuckDB 加载子图到 NetworkX
        
        使用 BFS 逐层加载:
        1. 起点 center_id
        2. 扩展 depth 跳邻居
        3. 构建有向图
        """
        # 检查缓存
        cache_key = f"{center_id}:{depth}:{relation_types}"
        if cache_key in self._cache:
            graph, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return graph
        
        G = nx.DiGraph()
        visited = set()
        current_level = [center_id]
        
        for d in range(depth + 1):
            next_level = []
            for node_id in current_level:
                if node_id in visited:
                    continue
                visited.add(node_id)
                
                # 加载节点
                entity = self.storage.get_entity_by_id_sync(node_id)
                if entity:
                    G.add_node(node_id, **entity.attributes, _concept=entity.concept_type)
                    
                    # 加载出边
                    neighbors = self.storage.get_neighbors_sync(
                        node_id, direction="outgoing", limit=1000
                    )
                    for neighbor, rel in neighbors:
                        if relation_types and rel.relation_type not in relation_types:
                            continue
                        G.add_edge(
                            rel.from_id, rel.to_id,
                            relation_type=rel.relation_type,
                            **rel.attributes
                        )
                        if neighbor.id not in visited:
                            next_level.append(neighbor.id)
            
            current_level = next_level
        
        # 缓存
        self._cache[cache_key] = (G, time.time())
        return G
    
    def detect_cycles(self, center_id: str, max_depth: int = 10) -> list[list[str]]:
        """检测从 center_id 出发可达的环
        
        供应链金融场景: 检测担保圈 (A→B→C→A)
        """
        G = self.load_subgraph(center_id, depth=max_depth,
                               relation_types=["guarantees_for", "guaranteed_by"])
        
        cycles = []
        try:
            # 使用 NetworkX 简单环检测
            for cycle in nx.simple_cycles(G):
                if center_id in cycle:
                    cycles.append(cycle)
        except nx.NetworkXError:
            pass  # 图过大，跳过
        
        return cycles
    
    def calculate_centrality(self, node_id: str, method: str = "betweenness") -> float:
        """计算节点中心性"""
        G = self.load_subgraph(node_id, depth=3)
        
        if method == "betweenness":
            centrality = nx.betweenness_centrality(G)
        elif method == "closeness":
            centrality = nx.closeness_centrality(G)
        elif method == "pagerank":
            centrality = nx.pagerank(G)
        else:
            raise ValueError(f"Unknown centrality method: {method}")
        
        return centrality.get(node_id, 0.0)
    
    def find_longest_path(
        self,
        source: str,
        relation_type: str | None = None,
        max_depth: int = 10
    ) -> int:
        """从 source 出发的最长路径长度
        
        供应链金融场景: 担保链深度
        """
        G = self.load_subgraph(source, depth=max_depth, relation_types=[relation_type] if relation_type else None)
        
        try:
            # DAG 最长路径
            if nx.is_directed_acyclic_graph(G):
                return nx.dag_longest_path_length(G)
            else:
                # 有环时，用 BFS 限制深度
                max_depth_found = 0
                for target in G.nodes():
                    if target != source:
                        try:
                            length = nx.shortest_path_length(G, source, target)
                            max_depth_found = max(max_depth_found, length)
                        except nx.NetworkXNoPath:
                            pass
                return max_depth_found
        except nx.NetworkXError:
            return 0
```

## 5. Faiss 向量存储

```python
# storage/vector/faiss_store.py

class FaissVectorStore(VectorStoreBackend):
    """Faiss 向量索引"""
    
    def __init__(self, dimension: int = 1536, index_type: str = "Flat"):
        self.dimension = dimension
        self.index_type = index_type
        self.index = faiss.IndexFlatIP(dimension)  # 内积 (余弦相似度需归一化)
        self.id_map: dict[int, str] = {}           # faiss_id → entity_id
        self.metadata: dict[str, dict] = {}        # entity_id → metadata
    
    async def add_vectors(
        self, ids: list[str], vectors: np.ndarray,
        metadata: list[dict] | None = None
    ) -> None:
        """添加向量"""
        # 归一化 (用于余弦相似度)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        normalized = vectors / norms
        
        start_idx = self.index.ntotal
        self.index.add(normalized.astype(np.float32))
        
        for i, entity_id in enumerate(ids):
            self.id_map[start_idx + i] = entity_id
            if metadata:
                self.metadata[entity_id] = metadata[i]
    
    async def search(
        self, query_vector: np.ndarray, top_k: int = 10,
        filters: dict | None = None
    ) -> list[VectorSearchResult]:
        """向量检索"""
        query = query_vector.reshape(1, -1).astype(np.float32)
        norms = np.linalg.norm(query)
        query = query / norms  # 归一化
        
        scores, indices = self.index.search(query, top_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            entity_id = self.id_map.get(int(idx))
            if entity_id:
                results.append(VectorSearchResult(
                    entity_id=entity_id,
                    score=float(score),
                    metadata=self.metadata.get(entity_id, {})
                ))
        
        return results
    
    def save(self, path: str) -> None:
        """持久化索引"""
        faiss.write_index(self.index, f"{path}/index.faiss")
        with open(f"{path}/metadata.json", "w") as f:
            json.dump({
                "id_map": {str(k): v for k, v in self.id_map.items()},
                "metadata": self.metadata,
                "dimension": self.dimension
            }, f)
    
    def load(self, path: str) -> None:
        """加载索引"""
        self.index = faiss.read_index(f"{path}/index.faiss")
        with open(f"{path}/metadata.json") as f:
            data = json.load(f)
            self.id_map = {int(k): v for k, v in data["id_map"].items()}
            self.metadata = data["metadata"]
```

## 6. 缓存策略

```python
# storage/cache.py

class MetricCache:
    """指标缓存 — LRU + TTL"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.max_size = max_size
        self.default_ttl = default_ttl
    
    def get(self, entity_id: str, metric_name: str) -> Any | None:
        key = f"{entity_id}:{metric_name}"
        if key in self._cache:
            value, expires_at = self._cache[key]
            if time.time() < expires_at:
                self._cache.move_to_end(key)  # LRU
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, entity_id: str, metric_name: str, value: Any, ttl: int | None = None):
        key = f"{entity_id}:{metric_name}"
        expires_at = time.time() + (ttl or self.default_ttl)
        
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (value, expires_at)
        
        # 驱逐
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)
    
    def invalidate(self, entity_id: str, metric_name: str | None = None):
        if metric_name:
            key = f"{entity_id}:{metric_name}"
            self._cache.pop(key, None)
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{entity_id}:")]
            for k in keys_to_remove:
                del self._cache[k]
```

## 7. 文件结构

```
ontology_engine/storage/
├── __init__.py                # create_storage() 工厂
├── base.py                    # StorageBackend, VectorStoreBackend, GraphAlgorithmBackend
├── models.py                  # EntityFilter, PaginatedResult, VectorSearchResult
├── cache.py                   # MetricCache
│
├── duckdb/
│   ├── __init__.py
│   └── store.py               # DuckDBStorage (完整版)
│
├── vector/
│   ├── __init__.py
│   └── faiss_store.py         # FaissVectorStore
│
├── graph/
│   ├── __init__.py
│   └── nx_store.py            # NetworkXGraphStore
│
└── adapters/                  # 预留
    ├── __init__.py
    ├── neo4j_store.py
    └── pgvector_store.py
```

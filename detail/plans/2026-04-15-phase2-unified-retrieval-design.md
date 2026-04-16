# Phase 2 统一检索与向量存储详细设计

> **状态**: draft  
> **Phase**: phase2  
> **创建日期**: 2026-04-15  
> **来源**: `docs/02-design/query-engine-current.md` + `docs/05-schema-v2/query-engine-target.md` + Session 决策  
> **verified_against**: `ontology_engine/storage/base.py`, `ontology_engine/storage/retrieval.py`, `ontology_engine/services/query_service.py`  
> **单一事实源**: 本文档是 Phase 2 统一检索层的唯一设计入口（直至被 RFC 正式取代）

---

## 1. 背景与缺口

### 1.1 当前态 (Phase 1)

QueryService 提供三种查询能力：

| 能力 | 实现位置 | 限制 |
|------|----------|------|
| `pattern_match` | `services/query_service.py` | 仅精确匹配，无向量语义 |
| `graph_traverse` | `services/query_service.py` | depth > 2 抛异常 |
| `find_path` | `services/query_service.py` | max_depth > 3 抛异常，硬编码 `has_invoice` 关系 |

存储层现状：
- `StorageBackend` (`storage/base.py`)：DuckDB 负责实体/属性/指标/审计
- `GraphStoreBackend` (`storage/base.py`)：NetworkXGraphStore 负责拓扑查询
- **缺失**：`VectorStoreBackend` 及统一检索门面

### 1.2 目标态 (Phase 2)

根据 [`docs/05-schema-v2/query-engine-target.md`](../../docs/05-schema-v2/query-engine-target.md)，目标能力：

1. **Vector Query**：Faiss ANN + sentence-transformers 嵌入
2. **Hybrid Query**：语义分 × 0.6 + 图 proximity × 0.4（可配置），支持 RRF / 交叉编码重排
3. **Graph Query DSL**：路径模式匹配（如 `Company -(guarantees)-> Company -(supplies)-> CoreEnterprise`）
4. **kuzu 协同**：NetworkX 升级为 kuzu，DuckDB 继续负责实体/指标/日志

### 1.3 当前 Session 已完成的前置工作

- [x] `VectorStoreBackend` 抽象接口已入 `storage/base.py`
- [x] `RetrievalBackend` 统一 Repository 接口已入 `storage/base.py`
- [x] `LocalVectorStore` 内存占位实现已入 `storage/vector/local_vector_store.py`
- [x] `DefaultRetrievalBackend` 协调实现已入 `storage/retrieval.py`
- [x] `QueryService` 已新增 `semantic_search`、`hybrid_search`、`graph_pattern_match` 方法
- [x] `DuckDBStorage` 已补充 `get_entity_by_id` 跨概念查询

---

## 2. 架构设计

### 2.1 分层视图

```text
┌─────────────────────────────────────────────────────────────┐
│  Service Layer                                               │
│  QueryService ──▶ pattern_match / graph_traverse / find_path │
│              ──▶ semantic_search / hybrid_search             │
│              ──▶ graph_pattern_match                         │
├─────────────────────────────────────────────────────────────┤
│  Retrieval Layer (新增)                                      │
│  DefaultRetrievalBackend ──▶ RetrievalBackend (统一门面)     │
├─────────────────────────────────────────────────────────────┤
│  Storage Backend Layer                                       │
│  ┌─────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │ DuckDBStore │  │ NetworkXGraphStore│  │ LocalVectorStore│ │
│  │ (属性/指标)  │  │ (拓扑/路径/循环)  │  │ (语义/占位)      │ │
│  └─────────────┘  └──────────────────┘  └─────────────────┘ │
│       ▲                    ▲                      ▲         │
│  目标: 保留使用      目标: 升级为 kuzu        目标: 升级为 Faiss│
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块边界 [关键设计点]

```text
services/query_service.py  ──▶  storage/base.RetrievalBackend
services/query_service.py  ──▶  storage/base.StorageBackend (保留现有调用)

storage/retrieval.py       ──▶  storage/base.StorageBackend
                           ──▶  storage/base.GraphStoreBackend
                           ──▶  storage/base.VectorStoreBackend

storage/local/             ──▶  仅实现 base.py 接口 (禁止依赖上层)
```

---

## 3. API 设计

### 3.1 存储抽象接口

位置：`ontology_engine/storage/base.py`

#### VectorStoreBackend

```python
class VectorStoreBackend(ABC):
    @abstractmethod
    async def initialize(self, dimension: int) -> None: ...

    @abstractmethod
    async def add_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None: ...

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    async def delete_vectors(self, ids: list[str]) -> None: ...
```

#### RetrievalBackend（统一 Repository）

```python
class RetrievalBackend(ABC):
    @abstractmethod
    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 10,
        concept_type: str | None = None,
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    async def hybrid_search(
        self,
        query_text: str | None = None,
        query_vector: list[float] | None = None,
        graph_seed_id: str | None = None,
        top_k: int = 10,
        semantic_weight: float = 0.6,
        graph_weight: float = 0.4,
        fusion_strategy: str = "weighted_sum",
    ) -> list[VectorSearchResult]: ...

    @abstractmethod
    async def graph_pattern_match(
        self,
        start_concept: str,
        path_pattern: list[tuple[str, str]],
        start_filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...
```

### 3.2 QueryService 新增方法

位置：`ontology_engine/services/query_service.py`

```python
class QueryService:
    def __init__(
        self,
        storage: StorageBackend,
        rule_executor: RuleExecutor | None = None,
        retrieval: RetrievalBackend | None = None,
        graph_store: GraphStoreBackend | None = None,
        vector_store: VectorStoreBackend | None = None,
    ): ...

    # --- Phase 2 ---
    async def semantic_search(...)
    async def hybrid_search(...)
    async def graph_pattern_match(...)
```

### 3.3 数据模型

```python
@dataclass
class VectorSearchResult:
    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 4. 应用场景说明

### 4.1 场景 A：语义检索（Semantic Search）

**需求**：用户输入 `"应收账款逾期严重的供应商"`，系统返回最相关的 Supplier 实体。

**调用链**：
```text
QueryService.semantic_search("应收账款逾期严重的供应商", concept_type="Supplier")
  ↓
DefaultRetrievalBackend.semantic_search
  ↓
embedder(query_text) → query_vector
  ↓
VectorStoreBackend.search(query_vector)
  ↓
按 concept_type 过滤 → list[VectorSearchResult]
```

**当前实现状态**：`LocalVectorStore` 使用精确余弦相似度，适合 <10k 向量测试。Phase 2 中期替换为 Faiss。

### 4.2 场景 B：混合检索（Hybrid Search）

**需求**：已知核心企业 `CE_001`，查找与其有业务往来且语义上接近 "高风险" 的供应商。

**调用链**：
```text
QueryService.hybrid_search(
    query_text="高风险",
    graph_seed_id="CE_001",
    top_k=10,
    semantic_weight=0.6,
    graph_weight=0.4,
    fusion_strategy="weighted_sum"
)
```

**融合逻辑** [关键设计点]：
1. **语义腿**：向量检索得到候选 ID 及其 cosine score
2. **图腿**：从 `graph_seed_id` 做 BFS 2-hop 扩散，邻居得分按深度衰减（`1/(1+depth)`）
3. **融合**：
   - `weighted_sum`：`final = 0.6 * sem + 0.4 * graph`
   - `rrf`：Reciprocal Rank Fusion，`score = Σ 1/(60 + rank_i)`
   - `cross_encoder`：当前为 placeholder，待接入重排模型

### 4.3 场景 C：图 DSL 模式匹配（Graph Pattern Match）

**需求**：查找担保链模式 `Company -(guarantees)-> Company -(supplies)-> CoreEnterprise`。

**调用方式**：
```python
await service.graph_pattern_match(
    start_concept="Company",
    path_pattern=[
        ("guarantees", "Company"),
        ("supplies", "CoreEnterprise"),
    ],
    start_filters={"region": "华东"},
    limit=50,
)
```

**返回格式**：
```json
{
  "nodes": [
    {"entity_id": "C1", "concept": "Company"},
    {"entity_id": "C2", "concept": "Company"},
    {"entity_id": "CE1", "concept": "CoreEnterprise"}
  ],
  "edges": [
    {"relation_type": "guarantees"},
    {"relation_type": "supplies"}
  ]
}
```

**实现策略** [关键设计点]：
- **无 kuzu 时**：DuckDB `get_neighbors` 逐跳 BFS fallback
- **有 kuzu 时**：通过 `GraphStoreBackend.execute_cypher` 下发 Cypher（待扩展）

---

## 5. 实现计划

### 5.1 已落地项（本 Session）

- [x] `VectorStoreBackend` / `RetrievalBackend` 接口定义
- [x] `LocalVectorStore` 内存实现 + 单元测试
- [x] `DefaultRetrievalBackend` 协调器 + 单元测试
- [x] `QueryService` Phase 2 方法代理 + 单元测试
- [x] `DuckDBStorage.get_entity_by_id` 补全

### 5.2 待落地项（Next Session / Phase 2 中期）

- [ ] **Faiss 集成**
  - 新建 `storage/vector/faiss_store.py` 实现 `VectorStoreBackend`
  - 支持 `IndexFlatIP`、`IndexIVFFlat`（数据量 >10万时自动切换）
  - 持久化：`data/vectors/index.faiss` + `metadata.json`

- [ ] **Embedder 接入**
  - 在 `pyproject.toml` 增加 `sentence-transformers` 可选依赖
  - 提供默认 embedder 工厂（如 `all-MiniLM-L6-v2`）
  - `DefaultRetrievalBackend` 注入 embedder

- [ ] **kuzu 升级**
  - 新建 `storage/graph/kuzu_store.py` 实现 `GraphStoreBackend`
  - 替换 `NetworkXGraphStore` 为默认图存储
  - `graph_pattern_match` 优先走 Cypher

- [ ] **双写协调扩展**
  - `DualWriteCoordinator` 增加 `save_entity_with_vectors`：写入 DuckDB + GraphStore + VectorStore

- [ ] **API 路由暴露**
  - `api/routes/query.py` 新增 POST `/v1/query/semantic`、POST `/v1/query/hybrid`、POST `/v1/query/pattern`

- [ ] **集成测试**
  - 覆盖语义搜索端到端、混合检索端到端、图 DSL 端到端

---

## 6. 关键测试用例

### 6.1 VectorStoreBackend 契约测试

文件：`tests/unit/storage/test_local_vector_store.py`（已实现）

| 用例 | 断言 |
|------|------|
| `test_add_and_search` | 相同向量 cosine similarity = 1.0 |
| `test_search_with_metadata_filter` | metadata 精确过滤生效 |
| `test_dimension_mismatch_on_add` | 抛出 `ValueError` |
| `test_uninitialized_store_raises` | 抛出 `StorageError` |

### 6.2 RetrievalBackend 协调测试

文件：`tests/unit/storage/test_retrieval_backend.py`（已实现）

| 用例 | 断言 |
|------|------|
| `test_semantic_search_with_embedder` | embedder 被调用，结果按 concept_type 过滤 |
| `test_hybrid_search_weighted_sum` | 语义结果与图结果并集存在，权重融合后排序 |
| `test_hybrid_search_rrf` | RRF 融合公式计算正常 |
| `test_graph_pattern_match_with_fallback` | DuckDB fallback 遍历返回正确 path 结构 |
| `test_graph_pattern_match_no_match` | 无匹配时返回空列表 |

### 6.3 QueryService 代理测试

文件：`tests/unit/services/test_query_service.py`（已实现）

| 用例 | 断言 |
|------|------|
| `test_semantic_search_delegates_to_retrieval` | 有 `retrieval` 时正确代理参数 |
| `test_semantic_search_without_retrieval_raises` | 无 `retrieval` 时抛 `NotImplementedError` |
| `test_hybrid_search_delegates_to_retrieval` | 参数透传无误 |
| `test_graph_pattern_match_fallback_without_retrieval` | 无 `retrieval` 时自动构造 fallback 并返回结果 |

### 6.4 Phase 2 集成测试（待实现）

文件（预留）：`tests/integration/test_retrieval_phase2.py`

```python
async def test_semantic_search_end_to_end()
    """注入 LocalVectorStore，写入实体向量，执行语义搜索并返回真实实体属性."""

async def test_hybrid_search_combines_graph_and_semantic()
    """构建简单三角图 + 向量，验证 hybrid_search 融合得分高于纯语义/纯图."""

async def test_graph_pattern_match_guarantee_chain()
    """写入 Company -(guarantees)-> Company -(supplies)-> CoreEnterprise，
    验证 DSL 模式匹配返回完整路径."""

async def test_graph_pattern_match_no_concept_match_returns_empty()
    """路径中间节点 concept 不匹配时返回空列表."""
```

---

## 7. 性能目标与验收标准

引用自 [`docs/05-schema-v2/query-engine-target.md`](../../docs/05-schema-v2/query-engine-target.md)：

| 指标 | Phase 1 | Phase 2 目标 | 验收方式 |
|------|---------|--------------|----------|
| 节点规模 | 100K | 500K | 压测脚本导入 500K 实体 |
| 向量检索 P99 | - | < 1s | `pytest tests/perf/test_vector_perf.py` |
| 图遍历 P99 | 2s | 1s | kuzu 替代 NetworkX 后复测 |

---

## 8. 迁移路径

### 8.1 Phase 1 → Phase 2 代码迁移

1. **无侵入**：`QueryService` 原有 `pattern_match` / `graph_traverse` / `find_path` 接口不变
2. **可选注入**：`retrieval`、`graph_store`、`vector_store` 均为 `__init__` 可选参数
3. **配置驱动**：新增 `StorageConfig` 字段：
   ```python
   vector_store_type: str = "local"   # local | faiss
   graph_store_type: str = "networkx" # networkx | kuzu
   ```

### 8.2 数据迁移

- DuckDB 实体数据零迁移
- 向量索引需重新构建（从 DuckDB 批量读取实体文本字段，调用 embedder 生成向量后写入 Faiss）
- kuzu 图数据可通过 `DualWriteCoordinator.batch_sync_from_storage()` 全量同步

---

## 9. 风险与决策记录

| # | 决策 | 理由 | 状态 |
|---|------|------|------|
| 1 | `LocalVectorStore` 作为 Phase 1→2 桥梁 | Faiss 未集成前需要可测试的向量存储 | 已实施 |
| 2 | `RetrievalBackend` 独立于 `StorageBackend` | 避免在已有 DuckDB 接口上过度膨胀，保持正交 | 已实施 |
| 3 | `graph_pattern_match` 先提供 DuckDB fallback | kuzu 未接入前，DSL 能力即可被上层调用 | 已实施 |
| 4 | 混合检索 graph 信号采用 2-hop BFS 代理 | NetworkX/kuzu 统一可用，计算轻量 | 已实施 |
| 5 | 交叉编码重排为 placeholder | 交叉编码器模型选型未确定，接口先预留 | 待扩展 |

---

## 10. 相关链接

- 当前态规范：`docs/02-design/query-engine-current.md`
- 目标态规范：`docs/05-schema-v2/query-engine-target.md`
- 存储设计：`docs/02-design/03-storage-design.md`
- 代码接口：`ontology_engine/storage/base.py`
- 协调实现：`ontology_engine/storage/retrieval.py`

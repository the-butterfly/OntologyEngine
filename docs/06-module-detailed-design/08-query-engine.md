# 模块 08: 查询引擎 (QueryEngine)

> **位置**: `ontology_engine/engine/query/`
> **依赖**: DuckDBStorage, FaissVectorStore, NetworkXGraphStore
> **被依赖**: QueryService, AnalysisService

## 1. 职责

1. **图遍历 DSL** — 1-2 跳邻居查询 + 属性过滤 (决策 #9)
2. **向量语义检索** — 基于自然语言的实体搜索
3. **混合融合检索** — 向量 + 图加权融合 (决策 #4: Phase 1 固定 0.6+0.4)
4. **路径查询** — 两点间最短路径、模式匹配

## 2. 图遍历 DSL

### 2.1 请求结构

```python
# engine/query/models.py

class GraphQuery(BaseModel):
    """图遍历查询 DSL (决策 #9: 简化版)"""
    
    start: StartNode                     # 起始节点
    traverse: list[TraversalStep]        # 遍历步骤
    return_: ReturnSpec | None = None    # 返回规格
    limit: int = 50                      # 结果数量限制


class StartNode(BaseModel):
    """起始节点"""
    concept_type: str | None = None
    filter: dict[str, FilterCondition] = {}   # 属性过滤
    entity_id: str | None = None              # 直接指定 ID


class TraversalStep(BaseModel):
    """遍历步骤"""
    relation: str                         # 关系类型
    direction: str = "both"               # outgoing | incoming | both
    depth: int = 1                        # 1-2 跳 (Phase 1 限制)
    target_filter: TargetFilter | None = None


class TargetFilter(BaseModel):
    """目标节点过滤"""
    concept_type: str | None = None
    attributes: dict[str, FilterCondition] = {}


class ReturnSpec(BaseModel):
    """返回规格"""
    attributes: list[str] = []            # 返回哪些属性
    include_path: bool = False            # 是否包含路径信息
    aggregate: list[AggregateSpec] = []   # 聚合计算


class AggregateSpec(BaseModel):
    """聚合规格"""
    type: str                             # sum | count | avg | max | min
    field: str                            # 聚合字段
    output: str | None = None             # 输出名称
```

### 2.2 图遍历执行器

```python
# engine/query/graph_executor.py

class GraphQueryExecutor:
    """图遍历查询执行器"""
    
    def __init__(self, storage: DuckDBStorage, graph_store: NetworkXGraphStore):
        self.storage = storage
        self.graph_store = graph_store
    
    async def execute(self, query: GraphQuery) -> GraphQueryResult:
        """执行图遍历查询"""
        
        # 1. 确定起始节点
        start_entities = await self._resolve_start_nodes(query.start)
        if not start_entities:
            return GraphQueryResult(items=[], total=0)
        
        # 2. 执行遍历
        all_results = []
        
        for entity in start_entities:
            for step in query.traverse:
                # 深度校验 (决策 #9: 最多 2 跳)
                if step.depth > 2:
                    raise GraphTraversalTooDeepError(
                        f"图遍历深度 {step.depth} 超过限制 (最大 2)"
                    )
                
                # BFS 遍历
                visited = set()
                current_level = [(entity, [])]
                
                for d in range(step.depth):
                    next_level = []
                    for current_entity, path in current_level:
                        if current_entity.id in visited:
                            continue
                        visited.add(current_entity.id)
                        
                        # 获取邻居
                        neighbors = await self.storage.get_neighbors(
                            current_entity.id,
                            relation_type=step.relation,
                            direction=step.direction,
                            limit=1000
                        )
                        
                        for neighbor, relation in neighbors:
                            # 过滤目标节点
                            if step.target_filter:
                                if not self._matches_filter(neighbor, step.target_filter):
                                    continue
                            
                            new_path = path + [relation.relation_type, neighbor.id]
                            next_level.append((neighbor, new_path))
                            all_results.append((neighbor, new_path))
                    
                    current_level = next_level
        
        # 3. 去重
        seen = set()
        unique_results = []
        for entity, path in all_results:
            if entity.id not in seen:
                seen.add(entity.id)
                unique_results.append((entity, path))
        
        # 4. 构建返回
        items = []
        for entity, path in unique_results[:query.limit]:
            item = GraphQueryItem(
                entity_id=entity.id,
                concept_type=entity.concept_type,
                attributes=self._select_attributes(entity, query.return_),
                path=path if query.return_ and query.return_.include_path else None
            )
            items.append(item)
        
        # 5. 聚合
        aggregates = {}
        if query.return_ and query.return_.aggregate:
            aggregates = self._compute_aggregates(items, query.return_.aggregate)
        
        return GraphQueryResult(
            items=items,
            total=len(unique_results),
            aggregates=aggregates
        )
    
    async def _resolve_start_nodes(self, start: StartNode) -> list[Entity]:
        """解析起始节点"""
        if start.entity_id:
            entity = await self.storage.get_entity_by_id(start.entity_id)
            return [entity] if entity else []
        
        filter_spec = EntityFilter(
            concept_type=start.concept_type,
            attributes=start.filter
        )
        result = await self.storage.query_entities(
            concept_type=start.concept_type,
            filters=filter_spec
        )
        return result.items


class GraphTraversalTooDeepError(Exception):
    """图遍历深度超过限制"""
    pass
```

## 3. 向量语义检索

```python
# engine/query/vector_executor.py

class VectorQueryExecutor:
    """向量语义检索执行器"""
    
    def __init__(
        self,
        vector_store: FaissVectorStore,
        storage: DuckDBStorage,
        embedding_model: str = "text-embedding-3-small"
    ):
        self.vector_store = vector_store
        self.storage = storage
        self.embedding_model = embedding_model
        self._embedder = None
    
    async def search(
        self,
        query: str,
        concept_type: str | None = None,
        top_k: int = 10
    ) -> list[SearchResult]:
        """向量语义检索"""
        
        # 1. 生成 query embedding
        query_vector = await self._embed(query)
        
        # 2. Faiss 检索 (扩大候选集)
        candidates = await self.vector_store.search(
            query_vector, top_k=top_k * 3
        )
        
        # 3. 结构化过滤
        results = []
        for candidate in candidates:
            entity = await self.storage.get_entity_by_id(candidate.entity_id)
            if not entity:
                continue
            
            # 类型过滤
            if concept_type and entity.concept_type != concept_type:
                continue
            
            results.append(SearchResult(
                entity_id=entity.id,
                concept_type=entity.concept_type,
                attributes=entity.attributes,
                relevance_score=candidate.score,
                match_details={
                    "semantic_score": candidate.score,
                    "match_type": "semantic"
                }
            ))
            
            if len(results) >= top_k:
                break
        
        return results
    
    async def _embed(self, text: str) -> np.ndarray:
        """生成文本 embedding"""
        if self._embedder is None:
            # Phase 1: 使用简单的 TF-IDF 或占位
            # Phase 2: 接入 OpenAI / 本地模型
            self._embedder = self._create_embedder()
        
        return await self._embedder(text)
```

## 4. 混合融合检索

```python
# engine/query/hybrid_executor.py

class HybridQueryExecutor:
    """混合融合检索 (决策 #4: Phase 1 固定权重 0.6 + 0.4)"""
    
    def __init__(
        self,
        graph_executor: GraphQueryExecutor,
        vector_executor: VectorQueryExecutor,
        storage: DuckDBStorage
    ):
        self.graph_executor = graph_executor
        self.vector_executor = vector_executor
        self.storage = storage
    
    # Phase 1 固定权重
    SEMANTIC_WEIGHT = 0.6
    GRAPH_WEIGHT = 0.4
    
    async def search(
        self,
        query: str,
        match_mode: str = "hybrid",
        concept_type: str | None = None,
        filters: dict | None = None,
        top_k: int = 10
    ) -> list[SearchResult]:
        """混合检索
        
        Args:
            match_mode: semantic | graph | hybrid
        """
        if match_mode == "semantic":
            return await self.vector_executor.search(query, concept_type, top_k)
        
        elif match_mode == "graph":
            # 图匹配: 从 query 提取关键词 → 属性过滤
            return await self._graph_search(query, concept_type, filters, top_k)
        
        else:  # hybrid
            return await self._hybrid_search(query, concept_type, filters, top_k)
    
    async def _hybrid_search(
        self,
        query: str,
        concept_type: str | None,
        filters: dict | None,
        top_k: int
    ) -> list[SearchResult]:
        """混合融合"""
        
        # 并行执行两种检索
        semantic_results = await self.vector_executor.search(
            query, concept_type, top_k=top_k * 2
        )
        
        graph_results = await self._graph_search(
            query, concept_type, filters, top_k=top_k * 2
        )
        
        # 合并分数
        score_map: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}
        
        for r in semantic_results:
            score_map[r.entity_id] = score_map.get(r.entity_id, 0) + r.relevance_score * self.SEMANTIC_WEIGHT
            result_map[r.entity_id] = r
        
        for r in graph_results:
            score_map[r.entity_id] = score_map.get(r.entity_id, 0) + r.relevance_score * self.GRAPH_WEIGHT
            if r.entity_id not in result_map:
                result_map[r.entity_id] = r
        
        # 排序
        sorted_ids = sorted(score_map.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for entity_id, score in sorted_ids[:top_k]:
            result = result_map[entity_id]
            results.append(SearchResult(
                entity_id=result.entity_id,
                concept_type=result.concept_type,
                attributes=result.attributes,
                relevance_score=round(score, 4),
                match_details={
                    "semantic_score": next((r.relevance_score for r in semantic_results if r.entity_id == entity_id), 0),
                    "graph_score": next((r.relevance_score for r in graph_results if r.entity_id == entity_id), 0),
                    "match_type": "hybrid"
                }
            ))
        
        return results
    
    async def _graph_search(
        self,
        query: str,
        concept_type: str | None,
        filters: dict | None,
        top_k: int
    ) -> list[SearchResult]:
        """基于属性过滤的图匹配"""
        
        filter_spec = EntityFilter(
            concept_type=concept_type,
            attributes=filters or {}
        )
        
        result = await self.storage.query_entities(
            concept_type=concept_type,
            filters=filter_spec,
            limit=top_k
        )
        
        return [
            SearchResult(
                entity_id=e.id,
                concept_type=e.concept_type,
                attributes=e.attributes,
                relevance_score=1.0,  # 图匹配精确匹配 → 1.0
                match_details={"graph_score": 1.0, "match_type": "graph"}
            )
            for e in result.items
        ]
```

## 5. 供应链金融查询示例

### 5.1 担保圈检测

```python
# 查询 SUP_2024_001 的担保圈
query = GraphQuery(
    start=StartNode(entity_id="SUP_2024_001"),
    traverse=[
        TraversalStep(
            relation="guarantees_for",
            direction="both",
            depth=2,
            target_filter=TargetFilter(concept_type="Supplier")
        )
    ],
    return_=ReturnSpec(
        attributes=["company_name", "registered_capital", "status"],
        include_path=True,
        aggregate=[
            AggregateSpec(type="count", field="related_entities", output="total_guarantors")
        ]
    )
)

result = await graph_executor.execute(query)
# → 找到 A→B→C 担保链
```

### 5.2 供应商搜索

```python
# 混合检索: "提供芯片的供应商"
results = await hybrid_executor.search(
    query="提供芯片的供应商",
    match_mode="hybrid",
    concept_type="Supplier",
    filters={"status": {"eq": "ACTIVE"}},
    top_k=10
)
# → 语义匹配 + 属性过滤融合排序
```

## 6. 文件结构

```
ontology_engine/engine/query/
├── __init__.py               # 导出 QueryEngine
├── engine.py                 # QueryEngine 主类 (分发)
├── models.py                 # GraphQuery, SearchResult 等
├── graph_executor.py         # 图遍历执行器
├── vector_executor.py        # 向量检索执行器
├── hybrid_executor.py        # 混合融合执行器
└── errors.py                 # 错误类型
```

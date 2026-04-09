# 模块 09: 服务层 (Services)

> **位置**: `ontology_engine/services/`
> **依赖**: 所有引擎层、存储层
> **被依赖**: API 层

## 1. 职责

1. **用例编排** — 组合多个引擎完成业务场景
2. **事务管理** — 定义事务边界，保证一致性
3. **跨引擎协调** — L2→L3→L4 数据流协调
4. **DTO 转换** — 领域模型 ↔ API 模型隔离
5. **权限检查** — 接口级别权限验证

## 2. 服务划分

| 服务 | 职责 | 依赖引擎 |
|------|------|----------|
| SchemaService | Schema 加载/校验/版本管理 | SchemaLoader, SchemaVersionManager |
| EntityService | 实体 CRUD/批量导入 | DuckDBStorage |
| AnalysisService | 分析编排 (核心) | CategorizationEngine, MetricEngine, RuleEngine |
| QueryService | 知识检索 | QueryEngine |
| IngestionService | 数据导入/ETL | DuckDBStorage, InstanceLoader |

## 3. SchemaService

```python
# services/schema_service.py

class SchemaService:
    """Schema 管理服务"""
    
    def __init__(
        self,
        storage: DuckDBStorage,
        version_manager: SchemaVersionManager
    ):
        self.storage = storage
        self.version_manager = version_manager
        self._current_schema: KGMLSchema | None = None
        self._loader = SchemaLoader()
    
    async def load_schema(self, schema_path: str) -> SchemaInfo:
        """加载 Schema — 事务: 全成功或全失败"""
        # 1. 解析
        schema = self._loader.load(schema_path)
        
        # 2. 校验
        issues = self._loader.validate(schema)
        errors = [i for i in issues if i.level == "error"]
        if errors:
            raise SchemaValidationError(errors)
        
        # 3. 版本提交
        version = self.version_manager.commit(
            schema, description=f"Loaded from {schema_path}"
        )
        
        # 4. 激活
        self._current_schema = schema
        
        return SchemaInfo(
            schema_id=schema.metadata.id,
            version=version.version,
            entity_count=len(schema.entities),
            metric_count=len(schema.metrics),
            rule_count=len(schema.rules),
            warnings=[i for i in issues if i.level == "warning"]
        )
    
    async def get_schema(self) -> KGMLSchema | None:
        """获取当前 Schema"""
        return self._current_schema
    
    async def reload_schema(self, schema_path: str) -> SchemaInfo:
        """热更新 Schema"""
        return await self.load_schema(schema_path)
    
    async def get_schema_versions(self) -> list[SchemaVersionSummary]:
        """获取版本历史"""
        # ...
    
    async def rollback_schema(self, target_version: int) -> SchemaInfo:
        """回滚 Schema"""
        schema = self.version_manager.rollback(target_version)
        self._current_schema = schema
        return SchemaInfo(schema_id=schema.metadata.id, ...)
```

## 4. EntityService

```python
# services/entity_service.py

class EntityService:
    """实体管理服务"""
    
    def __init__(self, storage: DuckDBStorage, schema: KGMLSchema):
        self.storage = storage
        self.schema = schema
    
    async def create_entity(
        self,
        concept_type: str,
        entity_id: str,
        attributes: dict
    ) -> EntityResponse:
        """创建实体"""
        # 1. 验证 concept_type 存在
        entity_def = next(
            (e for e in self.schema.entities if e.name == concept_type), None
        )
        if not entity_def:
            raise ConceptNotDefinedError(concept_type)
        
        # 2. 验证属性
        self._validate_attributes(entity_def, attributes)
        
        # 3. 持久化
        entity = Entity(id=entity_id, concept_type=concept_type, attributes=attributes)
        await self.storage.save_entity(entity)
        
        return EntityResponse.from_domain(entity)
    
    async def batch_create(
        self,
        entities: list[EntityCreateRequest]
    ) -> BatchOperationResult:
        """批量创建 (事务)"""
        results = []
        errors = []
        
        for req in entities:
            try:
                entity = await self.create_entity(
                    concept_type=req.concept_type,
                    entity_id=req.entity_id,
                    attributes=req.attributes
                )
                results.append(entity)
            except Exception as e:
                errors.append(BatchError(entity_id=req.entity_id, error=str(e)))
        
        return BatchOperationResult(
            success_count=len(results),
            error_count=len(errors),
            entities=results,
            errors=errors
        )
    
    async def query_entities(
        self,
        concept_type: str | None = None,
        filters: dict | None = None,
        pagination: PaginationSpec | None = None
    ) -> PaginatedResult[EntityResponse]:
        """查询实体"""
        filter_spec = EntityFilter(concept_type=concept_type, attributes=filters) if filters else None
        result = await self.storage.query_entities(
            concept_type=concept_type,
            filters=filter_spec,
            limit=pagination.limit if pagination else 100,
            offset=pagination.offset if pagination else 0
        )
        
        return PaginatedResult(
            items=[EntityResponse.from_domain(e) for e in result.items],
            total=result.total,
            offset=result.offset,
            limit=result.limit
        )
    
    async def create_relation(
        self,
        relation_type: str,
        from_id: str,
        to_id: str,
        attributes: dict | None = None
    ) -> RelationResponse:
        """创建关系"""
        # 验证两端实体存在
        from_entity = await self.storage.get_entity_by_id(from_id)
        to_entity = await self.storage.get_entity_by_id(to_id)
        if not from_entity or not to_entity:
            raise EntityNotFoundError(f"{from_id} 或 {to_id}")
        
        relation = Relation(
            id=f"{relation_type}:{from_id}->{to_id}",
            relation_type=relation_type,
            from_id=from_id,
            to_id=to_id,
            attributes=attributes or {}
        )
        await self.storage.save_relation(relation)
        
        return RelationResponse.from_domain(relation)
    
    async def get_neighbors(
        self,
        entity_id: str,
        relation_type: str | None = None,
        depth: int = 1
    ) -> list[NeighborResponse]:
        """获取邻居"""
        # depth > 1 需要递归
        if depth > 2:
            raise ValueError("Phase 1 最多支持 2 跳")
        
        neighbors = await self.storage.get_neighbors(
            entity_id, relation_type, direction="both"
        )
        
        return [
            NeighborResponse(
                entity=EntityResponse.from_domain(entity),
                relation=RelationResponse.from_domain(relation)
            )
            for entity, relation in neighbors
        ]
```

## 5. AnalysisService (核心编排)

```python
# services/analysis_service.py

class AnalysisService:
    """分析服务 — 核心业务编排
    
    协调: CategorizationEngine → MetricEngine → RuleEngine
    """
    
    def __init__(
        self,
        categorization_engine: CategorizationEngine,
        metric_engine: MetricEngine,
        rule_engine: RuleEngine,
        storage: DuckDBStorage
    ):
        self.categorization_engine = categorization_engine
        self.metric_engine = metric_engine
        self.rule_engine = rule_engine
        self.storage = storage
    
    async def execute_analysis(
        self,
        entity_id: str,
        dimension: str,
        context: AnalysisContext | None = None
    ) -> AnalysisResponse:
        """执行完整维度分析
        
        完整流程:
        1. 获取实体
        2. L2 归类
        3. L3 指标预计算
        4. L4 规则执行
        5. 组装结果
        """
        # 1. 获取实体
        entity = await self.storage.get_entity_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError(entity_id)
        
        # 2. L2 归类
        category_tags = await self.categorization_engine.categorize(entity)
        
        # 3. L3 指标预计算 (决策 #11: 直接调用 MetricEngine)
        required_metrics = self._collect_required_metrics(dimension)
        computed_metrics = await self.metric_engine.compute_batch(
            required_metrics, entity,
            context=context.overrides if context else None
        )
        
        # 4. L4 规则执行
        entity_data = dict(entity.attributes)
        entity_data["_concept"] = entity.concept_type
        
        analysis_result = await self.rule_engine.execute_dimension(
            dimension=dimension,
            entity_id=entity_id,
            entity_data=entity_data,
            category_tags=category_tags,
            precomputed_metrics=computed_metrics
        )
        
        # 5. 组装结果
        return AnalysisResponse(
            entity_id=entity_id,
            concept_type=entity.concept_type,
            dimension=dimension,
            category_tags=category_tags.tags,
            computed_metrics=analysis_result.computed_metrics,
            rule_results=[
                RuleResultResponse(
                    rule_id=r.rule_id,
                    rule_name=r.rule_name,
                    passed=r.passed,
                    output=r.output,
                    condition_detail=r.condition_detail
                )
                for r in analysis_result.rule_results
            ],
            alerts=[AlertResponse(level=a.level, type=a.type, message=a.message) for a in analysis_result.alerts],
            decision=analysis_result.decision,
            decision_reasoning=analysis_result.decision_reasoning
        )
    
    async def execute_dry_run(
        self,
        entity_id: str,
        dimension: str,
        context: AnalysisContext | None = None
    ) -> AnalysisPreview:
        """预览分析 (dry run) — 不持久化结果"""
        # 与 execute_analysis 相同，但不写 storage
        ...
    
    def _collect_required_metrics(self, dimension: str) -> list[str]:
        """收集维度所需的所有指标"""
        metrics = []
        for rule in self.rule_engine.schema.rules:
            scope = rule.scope or {}
            if dimension in scope.get("dimensions", []):
                # 从 when 条件和 computation 中提取指标引用
                if rule.when and rule.when.expression:
                    metrics.extend(self._extract_metric_refs(rule.when.expression))
                if rule.then and rule.then.computation:
                    comp = rule.then.computation
                    if comp.get("formula"):
                        metrics.extend(self._extract_metric_refs(comp["formula"]))
        return list(set(metrics))
    
    def _extract_metric_refs(self, expression: str) -> list[str]:
        """从表达式中提取指标引用"""
        # 简单实现: 提取所有标识符，过滤出已知指标名
        import re
        identifiers = set(re.findall(r'\b([a-zA-Z_]\w*)\b', expression))
        metric_names = {m.name for m in self.metric_engine.schema.metrics}
        return list(identifiers & metric_names)
```

## 6. QueryService

```python
# services/query_service.py

class QueryService:
    """查询服务"""
    
    def __init__(
        self,
        query_engine: QueryEngine,
        storage: DuckDBStorage
    ):
        self.query_engine = query_engine
        self.storage = storage
    
    async def pattern_match(
        self,
        query: str,
        match_mode: str = "hybrid",
        concept_type: str | None = None,
        filters: dict | None = None,
        top_k: int = 10
    ) -> list[SearchResultResponse]:
        """知识检索"""
        results = await self.query_engine.search(
            query=query,
            match_mode=match_mode,
            concept_type=concept_type,
            filters=filters,
            top_k=top_k
        )
        return [SearchResultResponse.from_domain(r) for r in results]
    
    async def graph_traverse(self, query: GraphQuery) -> GraphQueryResponse:
        """图遍历"""
        result = await self.query_engine.graph_execute(query)
        return GraphQueryResponse.from_domain(result)
    
    async def trace_rule(
        self,
        entity_id: str,
        trace_mode: str = "full",
        rule_group: str | None = None
    ) -> TraceResult:
        """规则追溯 — 从实例追溯到完整计算树"""
        entity = await self.storage.get_entity_by_id(entity_id)
        if not entity:
            raise EntityNotFoundError(entity_id)
        
        # 获取归类标签
        tags = await self.storage.get_category_tags(entity_id)
        
        # 获取指标计算历史
        metrics = await self._get_all_metrics(entity_id)
        
        # 获取规则执行历史
        exec_history = await self.storage.get_execution_history(entity_id)
        
        # 构建追溯树
        trace = TraceResult(
            entity=EntitySummary.from_entity(entity),
            categorization=tags,
            atomic_metrics={k: v for k, v in metrics.items() if k.startswith("atomic_")},
            computation_tree=self._build_computation_tree(exec_history)
        )
        
        return trace
```

## 7. IngestionService

```python
# services/ingestion_service.py

class IngestionService:
    """数据导入服务"""
    
    def __init__(
        self,
        storage: DuckDBStorage,
        schema: KGMLSchema
    ):
        self.storage = storage
        self.schema = schema
    
    async def import_instances(self, instances_path: str) -> IngestionResult:
        """从 YAML 导入实例数据"""
        loader = InstanceLoader(self.schema)
        entities, relations = loader.load(instances_path)
        
        # 批量保存
        entity_count = 0
        relation_count = 0
        errors = []
        
        for entity in entities:
            try:
                await self.storage.save_entity(entity)
                entity_count += 1
            except Exception as e:
                errors.append(IngestionError(
                    type="entity", id=entity.id, error=str(e)
                ))
        
        for relation in relations:
            try:
                await self.storage.save_relation(relation)
                relation_count += 1
            except Exception as e:
                errors.append(IngestionError(
                    type="relation", id=relation.id, error=str(e)
                ))
        
        return IngestionResult(
            entity_count=entity_count,
            relation_count=relation_count,
            error_count=len(errors),
            errors=errors
        )
```

## 8. 端到端编排流

以供应链金融授信评估为例：

```
API: POST /v1/rules/execute
  {entity_id: "SUP_2024_001", dimension: "credit_assessment"}
    │
    ▼
AnalysisService.execute_analysis()
    │
    ├─ 1. Storage.get_entity("SUP_2024_001")
    │     → Supplier {supplier_id, company_name, registered_capital, ...}
    │
    ├─ 2. CategorizationEngine.categorize(entity)
    │     → {industry: "MANUFACTURING", company_scale: "LARGE", risk_level: "LOW"}
    │
    ├─ 3. MetricEngine.compute_batch([all required metrics], entity)
    │     ├─ atomic: total_invoice_amount_90d, overdue_invoice_amount, ...
    │     ├─ derived: overdue_invoice_ratio, business_stability_score, ...
    │     ├─ composite: credit_score (83.9), reputation_score (97.6), ...
    │     └─ graph: guarantee_chain_depth (1), network_centrality (0.12)
    │
    ├─ 4. RuleEngine.execute_dimension("credit_assessment", ...)
    │     ├─ R001: 准入检查 → PASS
    │     ├─ R002: 信用评分 → credit_score=83.9, credit_grade=AA
    │     ├─ R003: 担保圈检测 → SKIP (no circle)
    │     ├─ R004: 授信额度 → 45000000
    │     ├─ R005: 风险预警 → SKIP
    │     ├─ R006: 利率定价 → 5.81%
    │     └─ R007: 综合决策 → APPROVE
    │
    └─ 5. 组装 AnalysisResponse
          {decision: "APPROVE", credit_limit: 45000000, interest_rate: 5.81%}
```

## 9. 文件结构

```
ontology_engine/services/
├── __init__.py
├── schema_service.py       # SchemaService
├── entity_service.py       # EntityService
├── analysis_service.py     # AnalysisService (核心编排)
├── query_service.py        # QueryService
├── ingestion_service.py    # IngestionService
│
└── dto/                    # DTO 模型 (与 API 层共享)
    ├── __init__.py
    ├── requests.py          # 请求 DTO
    ├── responses.py         # 响应 DTO
    └── errors.py            # 服务层错误
```

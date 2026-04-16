# Services 层设计

> **定位**: Application Service 层 —— 编排用例、管理事务、协调引擎
> **状态**: 当前实现与本文档存在偏差，详见 `docs/04-migration-and-gap/README.md`
> **最后核验**: 2026-04-16

## 架构位置

```
API (FastAPI) ───────▶ DTO 校验/序列化
    │
    ▼
Services ────────────▶ 用例编排、事务管理、跨引擎协调
    │
    ▼
Engine ──────────────▶ 核心业务逻辑
    │
    ▼
Storage ─────────────▶ 数据持久化
```

## 核心职责

| 职责 | 说明 | 示例 |
|------|------|------|
| **用例编排** | 组合多个引擎完成业务场景 | 授信评估 = 准入检查 + 指标计算 + 规则执行 |
| **事务管理** | 定义事务边界，保证一致性 | Schema 加载失败回滚 |
| **跨引擎协调** | L3 MetricEngine → L4 RuleEngine | 预计算指标并注入规则上下文 |
| **DTO 转换** | 领域模型 ↔ API 模型 | Entity → EntityResponse |
| **权限检查** | 接口级别权限验证 | 用户是否有权访问该维度 **[未实现]** |

**不负责**:
- 具体规则执行 (下沉到 RuleEngine)
- 存储操作 (下沉到 Storage)
- 业务逻辑硬编码 (配置在 YAML)

---

## 服务划分

```python
# services/schema_service.py
class SchemaService:
    """Schema 管理服务"""

    async def load_schema(self, schema_path: Path) -> SchemaInfo:
        """加载 Schema，事务：全成功或全失败"""
        # 1. 解析 YAML
        # 2. 验证合法性
        # 3. 持久化元数据
        # 4. 初始化引擎
        ...

    async def get_schema(self, schema_id: str) -> Schema | None:
        """获取当前 Schema"""
        ...

    async def reload_schema(self, schema_id: str) -> SchemaInfo:
        """热更新 Schema"""
        ...


# services/entity_service.py
class EntityService:
    """实体管理服务"""

    def __init__(self, storage: StorageBackend):
        self.storage = storage

    async def create_entity(
        self,
        concept_type: str,
        entity_id: str,
        attributes: dict
    ) -> EntityResponse:
        """创建实体"""
        # 1. 验证 concept_type 存在
        # 2. 验证属性类型
        # 3. 持久化
        # 4. 返回 DTO
        ...

    async def batch_create(
        self,
        entities: list[EntityCreateRequest]
    ) -> BatchOperationResult:
        """批量创建（事务）"""
        # 全成功或全失败
        ...

    async def query_entities(
        self,
        concept_type: str | None,
        filters: FilterSpec,
        pagination: PaginationSpec
    ) -> PaginatedResult[EntityResponse]:
        """高级查询"""
        ...


# services/analysis_service.py
class AnalysisService:
    """
    分析服务 —— 核心业务编排
    协调 MetricEngine + RuleEngine + VectorEngine
    """

    def __init__(
        self,
        metric_engine: MetricEngine,
        rule_engine: RuleEngine,
        vector_engine: VectorEngine,
        storage: StorageBackend
    ):
        self.metric_engine = metric_engine
        self.rule_engine = rule_engine
        self.vector_engine = vector_engine
        self.storage = storage

    async def execute_analysis(
        self,
        entity_id: str,
        dimension: str,
        context: AnalysisContext | None = None
    ) -> AnalysisResult:
        """
        执行完整维度分析

        流程:
        1. 获取实体
        2. 获取适用规则组
        3. 预计算 L3 指标
        4. 执行 L4 规则
        5. 组装结果
        """
        # 1. 获取实体
        entity = await self.storage.get_entity(entity_id)
        if not entity:
            raise EntityNotFoundError(entity_id)

        # 2. 获取规则组
        rule_group = self.rule_engine.get_rule_group(dimension)
        if not rule_group:
            raise DimensionNotFoundError(dimension)

        # 3. 检查 applies_to
        categories = await self._get_categories(entity)
        if not self._matches_scope(rule_group, entity, categories):
            raise NotApplicableError(
                f"维度 {dimension} 不适用于该实体"
            )

        # 4. 预计算 L3 指标 (跨引擎协调)
        computed_metrics = await self._compute_l3_inputs(
            rule_group.inputs,
            entity,
            context
        )

        # 5. 执行 L4 规则
        rule_results = await self.rule_engine.execute(
            rule_group=rule_group,
            entity=entity,
            inputs=computed_metrics,
            context=context
        )

        # 6. 组装结果
        return AnalysisResult(
            entity_id=entity_id,
            dimension=dimension,
            metrics=computed_metrics,
            rule_results=rule_results,
            outputs=self._resolve_outputs(
                rule_group.outputs,
                rule_results
            )
        )

    async def _compute_l3_inputs(
        self,
        inputs: list[InputSpec],
        entity: Entity,
        context: AnalysisContext | None
    ) -> dict[str, Any]:
        """
        跨引擎协调: 按需计算 L3 指标

        优化:
        - 并行计算无依赖指标
        - 缓存已计算指标
        - 支持外部注入 (context 中已存在则跳过)
        """
        results = {}

        for inp in inputs:
            # 检查外部注入
            if context and inp.metric in context.overrides:
                results[inp.metric] = context.overrides[inp.metric]
                continue

            # 检查缓存
            if cached := await self._get_cached_metric(entity.id, inp.metric):
                results[inp.metric] = cached
                continue

            # 计算指标
            value = await self.metric_engine.compute(
                metric_name=inp.metric,
                entity=entity
            )
            results[inp.metric] = value

            # 写入缓存
            await self._cache_metric(entity.id, inp.metric, value)

        return results

    async def hybrid_search(
        self,
        query: str,
        concept_type: str | None = None,
        filters: FilterSpec | None = None,
        top_k: int = 10
    ) -> list[SearchResult]:
        """
        混合检索：向量相似 + 结构化过滤

        协调 VectorEngine + Storage
        """
        # 1. 向量检索
        vector_results = await self.vector_engine.search(
            query=query,
            top_k=top_k * 2  # 扩大候选集
        )

        # 2. 结构化过滤
        entity_ids = [r.entity_id for r in vector_results]
        filtered = await self.storage.filter_entities(
            entity_ids=entity_ids,
            concept_type=concept_type,
            filters=filters
        )

        # 3. 合并排序
        return self._merge_rank(
            vector_results,
            filtered,
            top_k=top_k
        )


# services/ingestion_service.py
class IngestionService:
    """数据导入服务"""

    async def import_entities(
        self,
        source: DataSource,
        mapping: EntityMapping,
        options: IngestOptions
    ) -> IngestionResult:
        """
        批量导入实体

        事务边界:
        - batch_size 内原子提交
        - 失败记录到 error_log
        """
        ...

    async def import_relations(
        self,
        source: DataSource,
        mapping: RelationMapping
    ) -> IngestionResult:
        """批量导入关系"""
        ...
```

---

## 事务边界

> **当前实现状态**: ⚠️ 偏离目标设计 (2026-04-16)
> 当前 `batch_create`/`import_instances` 为软失败模式（错误收集后继续执行），非原子性回滚。

目标设计 (尚未完全实现):

```python
# 装饰器方式
from contextlib import asynccontextmanager


@asynccontextmanager
async def transaction(storage: StorageBackend):
    """事务上下文管理器"""
    tx = await storage.begin_transaction()
    try:
        yield tx
        await tx.commit()
    except Exception:
        await tx.rollback()
        raise


class EntityService:
    async def batch_create(
        self,
        entities: list[EntityCreateRequest]
    ) -> BatchOperationResult:
        """批量创建 —— 事务边界在 Service 层"""
        async with transaction(self.storage) as tx:
            results = []
            for req in entities:
                entity = await self._create_entity_tx(tx, req)
                results.append(entity)

            # 事务提交点
            return BatchOperationResult(
                success_count=len(results),
                entities=results
            )
```

---

## 跨引擎协调时序

```
AnalysisService.execute_analysis()
    │
    ├─▶ 1. 获取 Entity (Storage)
    │
    ├─▶ 2. 获取 RuleGroup (RuleEngine)
    │
    ├─▶ 3. 预计算 L3 指标 ─────────────┐
    │   ├─▶ asset_liability_ratio      │
    │   │   └─▶ MetricEngine.compute() │
    │   ├─▶ credit_score               │
    │   │   └─▶ MetricEngine.compute() │
    │   └─▶ guarantee_exposure         │
    │       └─▶ MetricEngine.compute()─┘
    │                                  │
    ├─▶ 4. 执行 L4 规则 ◀──────────────┘
    │   └─▶ RuleEngine.execute(inputs={...})
    │
    └─▶ 5. 返回 AnalysisResult
```

---

## 错误处理

```python
class ServiceError(Exception):
    """Service 层错误基类"""
    code: str
    message: str
    details: dict | None = None


class EntityNotFoundError(ServiceError):
    code = "ENTITY_NOT_FOUND"

    def __init__(self, entity_id: str):
        self.message = f"实体不存在: {entity_id}"
        self.details = {"entity_id": entity_id}


class ValidationError(ServiceError):
    code = "VALIDATION_ERROR"

    def __init__(self, field: str, reason: str):
        self.message = f"字段验证失败: {field}"
        self.details = {"field": field, "reason": reason}


class EngineExecutionError(ServiceError):
    """引擎执行错误 —— 包装底层异常"""
    code = "ENGINE_EXECUTION_ERROR"

    def __init__(self, engine: str, original_error: Exception):
        self.message = f"{engine} 执行失败: {original_error}"
        self.details = {"engine": engine, "error": str(original_error)}
```

---

## 与 API 层关系

```python
# api/entities.py
from fastapi import APIRouter, Depends
from services.entity_service import EntityService

router = APIRouter()


def get_entity_service() -> EntityService:
    """依赖注入"""
    storage = get_storage()
    return EntityService(storage)


@router.post("/v1/entities")
async def create_entity(
    request: EntityCreateRequest,
    service: EntityService = Depends(get_entity_service)
) -> EntityResponse:
    """
    API 层职责:
    - 接收 HTTP 请求
    - DTO 校验 (Pydantic)
    - 调用 Service
    - 返回响应
    """
    entity = await service.create_entity(
        concept_type=request.concept_type,
        entity_id=request.entity_id,
        attributes=request.attributes
    )
    return EntityResponse.from_domain(entity)
```

---

## 目录结构

```
ontology_engine/
├── api/                    # FastAPI 路由 (薄层)
│   ├── entities.py
│   ├── rules.py
│   └── schema.py
│
├── services/               # Application Service 层
│   ├── __init__.py
│   ├── schema_service.py
│   ├── entity_service.py
│   ├── analysis_service.py
│   └── ingestion_service.py
│
├── engine/                 # 核心业务引擎
│   ├── metric/
│   ├── rule/
│   └── vector/
│
└── storage/                # 存储层
    └── base.py
```

---

## 设计原则

1. **Services 是编排层** —— 不实现业务逻辑，只协调引擎
2. **事务边界在 Service** —— 保证用例级别一致性
3. **跨引擎协调显式化** —— 明确 L3 → L4 数据流
4. **DTO 隔离** —— API 模型与领域模型分离
5. **错误封装** —— 底层异常转换为业务错误

# 模块 10: API 层

> **位置**: `ontology_engine/api/`
> **依赖**: 服务层
> **被依赖**: 外部调用方 (CLI / MCP / HTTP Client)
> **状态**: 已与代码核验，本文档描述与当前实现一致
> **last_verified**: 2026-04-12
> **verified_against**: `ontology_engine/api/routes/`
> **[关键设计点]**: Current API 与 Target API 的边界统一在 `docs/04-migration-and-gap/README.md` 跟踪

## 1. 职责

1. **HTTP 路由** — FastAPI 端点定义
2. **DTO 校验** — Pydantic 请求/响应模型
3. **依赖注入** — 服务实例注入
4. **统一错误格式** — 标准化错误响应
5. **请求追踪** — request_id + 日志

## 2. 应用配置

```python
# api/server.py

from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 初始化
    config = load_config()
    storage = DuckDBStorage(config.data_dir / "ontology.db")
    await storage.initialize()
    
    schema_loader = SchemaLoader()
    # ... 其他组件初始化
    
    app.state.storage = storage
    app.state.schema_service = SchemaService(storage, version_manager)
    app.state.entity_service = EntityService(storage, schema)
    app.state.analysis_service = AnalysisService(...)
    app.state.query_service = QueryService(...)
    app.state.ingestion_service = IngestionService(...)
    
    yield
    
    # 清理
    await storage.close()


app = FastAPI(
    title="OntologyEngine API",
    version="0.1.0",
    lifespan=lifespan
)
```

## 3. 依赖注入

```python
# api/dependencies.py

from fastapi import Depends, Request

def get_schema_service(request: Request) -> SchemaService:
    return request.app.state.schema_service

def get_entity_service(request: Request) -> EntityService:
    return request.app.state.entity_service

def get_analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service

def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service

def get_ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service
```

## 4. DTO 模型

```python
# api/dto/requests.py

class SchemaLoadRequest(BaseModel):
    schema_path: str

class EntityCreateRequest(BaseModel):
    concept_type: str
    entity_id: str
    attributes: dict[str, Any]

class EntityBatchCreateRequest(BaseModel):
    entities: list[EntityCreateRequest]

class EntityQueryRequest(BaseModel):
    concept_type: str | None = None
    filter: dict[str, dict] | None = None
    limit: int = 100
    offset: int = 0

class RelationCreateRequest(BaseModel):
    relation_type: str
    from_id: str
    to_id: str
    attributes: dict[str, Any] | None = None

class RuleExecuteRequest(BaseModel):
    entity_id: str
    dimension: str
    rules: list[str] | None = None           # 指定规则，为空则全部
    dry_run: bool = False                     # 预览模式
    context_overrides: dict[str, Any] | None = None  # 外部注入指标值

class GraphQueryRequest(BaseModel):
    start: dict
    traverse: list[dict]
    return_: dict | None = Field(None, alias="return")
    limit: int = 50

class VectorSearchRequest(BaseModel):
    text: str
    concept_type: str | None = None
    top_k: int = 10

class HybridSearchRequest(BaseModel):
    query: str
    match_mode: str = "hybrid"    # semantic | graph | hybrid
    concept_type: str | None = None
    filters: dict | None = None
    top_k: int = 10


# api/dto/responses.py

class APIResponse(BaseModel):
    """统一响应格式"""
    success: bool
    data: Any = None
    error: ErrorDetail | None = None
    meta: ResponseMeta

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None

class ResponseMeta(BaseModel):
    request_id: str
    timestamp: datetime

class SchemaInfoResponse(BaseModel):
    schema_id: str
    version: int
    entity_count: int
    metric_count: int
    rule_count: int
    warnings: list[str] = []

class EntityResponse(BaseModel):
    id: str
    concept_type: str
    attributes: dict[str, Any]

class AnalysisResponse(BaseModel):
    entity_id: str
    concept_type: str
    dimension: str
    category_tags: dict[str, str]
    computed_metrics: dict[str, Any]
    rule_results: list[dict]
    alerts: list[dict]
    decision: str | None
    decision_reasoning: str | None

class SearchResultResponse(BaseModel):
    entity_id: str
    concept_type: str
    relevance_score: float
    attributes: dict[str, Any]
    match_details: dict | None = None
```

## 5. 路由定义

### 5.1 Schema 管理

```python
# api/routes/schema.py

router = APIRouter(prefix="/v1/schema", tags=["schema"])

@router.post("/load", response_model=APIResponse)
async def load_schema(
    request: SchemaLoadRequest,
    service: SchemaService = Depends(get_schema_service)
):
    """加载 Schema"""
    info = await service.load_schema(request.schema_path)
    return APIResponse(
        success=True,
        data=info,
        meta=ResponseMeta(request_id=get_request_id(), timestamp=datetime.now())
    )

@router.get("", response_model=APIResponse)
async def get_schema(
    service: SchemaService = Depends(get_schema_service)
):
    """获取当前 Schema"""
    schema = await service.get_schema()
    if not schema:
        raise HTTPException(status_code=500, detail="Schema not loaded")
    return APIResponse(success=True, data=schema.metadata, meta=...)
```

### 5.2 实体管理

```python
# api/routes/entities.py

router = APIRouter(prefix="/v1/entities", tags=["entities"])

@router.post("", response_model=APIResponse)
async def create_entity(
    request: EntityCreateRequest,
    service: EntityService = Depends(get_entity_service)
):
    """创建实体"""
    entity = await service.create_entity(
        concept_type=request.concept_type,
        entity_id=request.entity_id,
        attributes=request.attributes
    )
    return APIResponse(success=True, data=entity, meta=...)

@router.post("/batch", response_model=APIResponse)
async def batch_create_entities(
    request: EntityBatchCreateRequest,
    service: EntityService = Depends(get_entity_service)
):
    """批量创建"""
    result = await service.batch_create(request.entities)
    return APIResponse(success=True, data=result, meta=...)

@router.get("/{entity_id}", response_model=APIResponse)
async def get_entity(
    entity_id: str,
    concept_type: str = Query(default=""),
    service: EntityService = Depends(get_entity_service)
):
    """获取实体"""
    entity = await service.storage.get_entity(concept_type, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return APIResponse(success=True, data=EntityResponse.from_domain(entity), meta=...)

@router.post("/query", response_model=APIResponse)
async def query_entities(
    request: EntityQueryRequest,
    service: EntityService = Depends(get_entity_service)
):
    """条件查询"""
    result = await service.query_entities(
        concept_type=request.concept_type,
        filters=request.filter,
        pagination=PaginationSpec(limit=request.limit, offset=request.offset)
    )
    return APIResponse(success=True, data=result, meta=...)

@router.get("/{entity_id}/neighbors", response_model=APIResponse)
async def get_neighbors(
    entity_id: str,
    relation_type: str | None = Query(default=None),
    depth: int = Query(default=1, ge=1, le=2),
    service: EntityService = Depends(get_entity_service)
):
    """获取邻居"""
    neighbors = await service.get_neighbors(entity_id, relation_type, depth)
    return APIResponse(success=True, data=neighbors, meta=...)
```

### 5.3 关系管理

```python
# api/routes/relations.py

router = APIRouter(prefix="/v1/relations", tags=["relations"])

@router.post("", response_model=APIResponse)
async def create_relation(
    request: RelationCreateRequest,
    service: EntityService = Depends(get_entity_service)
):
    """创建关系"""
    relation = await service.create_relation(
        relation_type=request.relation_type,
        from_id=request.from_id,
        to_id=request.to_id,
        attributes=request.attributes
    )
    return APIResponse(success=True, data=relation, meta=...)
```

### 5.4 规则执行

```python
# api/routes/rules.py

router = APIRouter(prefix="/v1/rules", tags=["rules"])

@router.post("/execute", response_model=APIResponse)
async def execute_rules(
    request: RuleExecuteRequest,
    service: AnalysisService = Depends(get_analysis_service)
):
    """执行规则"""
    context = AnalysisContext(overrides=request.context_overrides) if request.context_overrides else None
    
    if request.dry_run:
        result = await service.execute_dry_run(
            entity_id=request.entity_id,
            dimension=request.dimension,
            context=context
        )
    else:
        result = await service.execute_analysis(
            entity_id=request.entity_id,
            dimension=request.dimension,
            context=context
        )
    
    return APIResponse(success=True, data=result, meta=...)

@router.get("", response_model=APIResponse)
async def list_rules(
    dimension: str | None = Query(default=None),
    service: SchemaService = Depends(get_schema_service)
):
    """获取规则列表"""
    schema = await service.get_schema()
    if not schema:
        raise HTTPException(status_code=500, detail="Schema not loaded")
    
    rules = schema.rules
    if dimension:
        rules = [r for r in rules if dimension in (r.scope or {}).get("dimensions", [])]
    
    return APIResponse(
        success=True,
        data=[{"id": r.id, "name": r.name, "type": r.type, "priority": r.priority} for r in rules],
        meta=...
    )
```

### 5.5 图查询与向量检索

```python
# api/routes/query.py

router = APIRouter(prefix="/v1/query", tags=["query"])

@router.post("/graph", response_model=APIResponse)
async def graph_query(
    request: GraphQueryRequest,
    service: QueryService = Depends(get_query_service)
):
    """图遍历查询"""
    query = GraphQuery(**request.model_dump(by_alias=True))
    result = await service.graph_traverse(query)
    return APIResponse(success=True, data=result, meta=...)

@router.post("/vector", response_model=APIResponse)
async def vector_search(
    request: VectorSearchRequest,
    service: QueryService = Depends(get_query_service)
):
    """向量检索"""
    results = await service.pattern_match(
        query=request.text,
        match_mode="semantic",
        concept_type=request.concept_type,
        top_k=request.top_k
    )
    return APIResponse(success=True, data=results, meta=...)

@router.post("/hybrid", response_model=APIResponse)
async def hybrid_search(
    request: HybridSearchRequest,
    service: QueryService = Depends(get_query_service)
):
    """混合检索"""
    results = await service.pattern_match(
        query=request.query,
        match_mode=request.match_mode,
        concept_type=request.concept_type,
        filters=request.filters,
        top_k=request.top_k
    )
    return APIResponse(success=True, data=results, meta=...)
```

### 5.6 数据导入

```python
# api/routes/ingestion.py

router = APIRouter(prefix="/v1/ingestion", tags=["ingestion"])

@router.post("/import", response_model=APIResponse)
async def import_instances(
    instances_path: str = Query(...),
    service: IngestionService = Depends(get_ingestion_service)
):
    """导入实例数据"""
    result = await service.import_instances(instances_path)
    return APIResponse(success=True, data=result, meta=...)
```

## 6. 错误处理

```python
# api/errors.py

from fastapi import Request
from fastapi.responses import JSONResponse

class ServiceError(Exception):
    """服务层错误基类"""
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    message: str = ""

class EntityNotFoundError(ServiceError):
    code = "ENTITY_NOT_FOUND"
    status_code = 404

class ConceptNotDefinedError(ServiceError):
    code = "CONCEPT_NOT_DEFINED"
    status_code = 400

class InvalidAttributeError(ServiceError):
    code = "INVALID_ATTRIBUTE"
    status_code = 400

class SchemaNotLoadedError(ServiceError):
    code = "SCHEMA_NOT_LOADED"
    status_code = 500

class GraphTraversalTooDeepError(ServiceError):
    code = "GRAPH_TRAVERSAL_TOO_DEEP"
    status_code = 400

class ExpressionError(ServiceError):
    code = "EXPRESSION_ERROR"
    status_code = 400

class FormulaSandboxViolation(ServiceError):
    code = "FORMULA_SANDBOX_VIOLATION"
    status_code = 400

class FormulaTimeoutError(ServiceError):
    code = "FORMULA_EXECUTION_TIMEOUT"
    status_code = 408


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": getattr(exc, 'details', None)
            },
            "meta": {
                "request_id": get_request_id(request),
                "timestamp": datetime.now().isoformat()
            }
        }
    )
```

## 7. 完整 API 端点汇总

> **说明**: 端点数量随实现演进，请以实际代码为准。以下分类说明各功能域的路由位置。

### 7.1 端点分类与代码位置

| 功能域 | 路由文件 | 说明 |
|--------|----------|------|
| Schema 管理 | [`ontology_engine/api/routes/schema.py`](../../../ontology_engine/api/routes/schema.py) | Schema 加载、获取 |
| 实体管理 | [`ontology_engine/api/routes/entities.py`](../../../ontology_engine/api/routes/entities.py) | 实体 CRUD、批量操作、邻居查询 |
| 关系管理 | [`ontology_engine/api/routes/relations.py`](../../../ontology_engine/api/routes/relations.py) | 关系创建、查询 |
| 规则执行 | [`ontology_engine/api/routes/rules.py`](../../../ontology_engine/api/routes/rules.py) | 规则执行、规则列表 |
| 查询与检索 | [`ontology_engine/api/routes/query.py`](../../../ontology_engine/api/routes/query.py) | 图遍历、向量检索、混合检索 |
| 数据导入 | [`ontology_engine/api/routes/ingestion.py`](../../../ontology_engine/api/routes/ingestion.py) | 实例数据导入 |
| 分析服务 | [`ontology_engine/api/routes/analysis.py`](../../../ontology_engine/api/routes/analysis.py) | 实体分析、维度评估 |
| 消费接口 | [`ontology_engine/api/routes/consumption.py`](../../../ontology_engine/api/routes/consumption.py) | API 消费端点 |
| 管理服务 | [`ontology_engine/api/routes/management.py`](../../../ontology_engine/api/routes/management.py) | 系统管理接口 |
| 语义空间 | [`ontology_engine/api/routes/semantic_spaces.py`](../../../ontology_engine/api/routes/semantic_spaces.py) | 语义空间管理 |
| 可视化 | [`ontology_engine/api/routes/visualization.py`](../../../ontology_engine/api/routes/visualization.py) | 可视化数据接口 |

## 8. 文件结构

```
ontology_engine/api/
├── __init__.py
├── server.py              # FastAPI 应用 + 生命周期
├── dependencies.py        # 依赖注入
├── errors.py              # 错误处理
│
├── routes/
│   ├── __init__.py
│   ├── schema.py          # Schema 管理路由
│   ├── entities.py        # 实体管理路由
│   ├── relations.py       # 关系管理路由
│   ├── rules.py           # 规则执行路由
│   ├── query.py           # 查询路由
│   ├── ingestion.py       # 数据导入路由
│   ├── analysis.py        # 分析服务路由
│   ├── consumption.py     # 消费接口路由
│   ├── management.py      # 管理服务路由
│   ├── semantic_spaces.py # 语义空间路由
│   └── visualization.py   # 可视化路由
│
└── dto/
    ├── __init__.py
    ├── requests.py         # 请求 DTO
    ├── responses.py        # 响应 DTO
    └── errors.py           # DTO 错误模型
```

## 9. Current API 与 Target API 边界

Current API（本文档描述）与 Target API（Schema v2 目标态）的演进边界定义参见：

- **ADR-009**: [API Architecture Evolution](../../architecture/decisions/009-api-architecture-evolution.md)

### 关键边界说明

| 维度 | Current API | Target API |
|------|-------------|------------|
| 版本前缀 | `/v1/` | `/v2/` (预计) |
| Schema 管理 | 文件路径加载 | KGML + LinkML 集成 |
| 查询语言 | 专用 DSL | GQL (Graph Query Language) 子集 |
| 向量检索 | FAISS 本地索引 | 可插拔向量存储 |
| 消费层 | 直接暴露 | 通过 Consumption Layer 封装 |

有关 Current → Target 的详细迁移路径和缺口分析，参阅 [`docs/04-migration-and-gap/README.md`](../../04-migration-and-gap/README.md)。

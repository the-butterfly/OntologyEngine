# 后端模块详细设计 - VisualizationService + API

> **文件**:
> - `ontology_engine/services/visualization_service.py`
> - `ontology_engine/api/routes/visualization.py`
> - `ontology_engine/api/dependencies.py` (更新)
> - `ontology_engine/api/server.py` (更新)

## 一、VisualizationService

### 1.1 职责

可视化服务层，编排 visualization 模块的各个组件，对 API 层提供统一接口。

### 1.2 类定义

```python
class VisualizationService:
    """可视化数据服务 - 将 KGML Schema 转换为图数据模型"""

    def __init__(
        self,
        schema_service: SchemaService,
        analysis_service: AnalysisService,
        storage: DuckDBStorage,
        schema: KGMLSchema | None = None,
    ):
        self.schema_service = schema_service
        self.analysis_service = analysis_service
        self.storage = storage
        self._schema = schema

    def _get_schema(self) -> KGMLSchema:
        """获取当前 schema"""
        if self._schema:
            return self._schema
        schema = self.schema_service.get_schema()
        if not schema:
            raise SchemaNotLoadedError("Schema not loaded")
        return schema
```

### 1.3 API 方法

#### get_schema_graph

```python
async def get_schema_graph(
    self,
    graph_type: str = "entity_relation",
    layer_filter: list[str] | None = None,
) -> SchemaGraphData:
    """生成 Schema 图数据（G6 格式）"""
    schema = self._get_schema()
    builder = SchemaGraphBuilder(schema)
    return builder.build(graph_type, layer_filter)
```

#### get_rule_chain_graph

```python
async def get_rule_chain_graph(
    self,
    dimension: str,
) -> RuleChainGraphData:
    """生成规则链 DAG 图数据（X6 格式）"""
    schema = self._get_schema()
    builder = RuleChainGraphBuilder(schema)
    return builder.build(dimension)
```

#### simulate_execution

```python
async def simulate_execution(
    self,
    entity_id: str,
    dimension: str,
    overrides: dict[str, Any] | None = None,
    dry_run: bool = True,
) -> SimulationResult:
    """模拟执行规则链"""
    schema = self._get_schema()

    # 构建模拟器（复用 analysis_service 的引擎）
    simulator = RuleChainSimulator(
        rule_executor=self.analysis_service.rule_executor,
        metric_engine=self.analysis_service.metric_engine,
        storage=self.storage,
        schema=schema,
    )

    return await simulator.simulate(entity_id, dimension, overrides, dry_run)
```

#### get_execution_trace

```python
async def get_execution_trace(
    self,
    entity_id: str,
    dimension: str,
) -> list[ExecutionStepSnapshot]:
    """获取历史执行轨迹（从 rule_execution_log 重建）

    Phase 1: 简化实现，直接执行一次 dry_run
    Phase 2: 从 storage 中读取历史 log 重建
    """
    return list((await self.simulate_execution(
        entity_id, dimension, dry_run=True
    )).steps)
```

## 二、API 路由

### 2.1 端点定义

```python
# ontology_engine/api/routes/visualization.py

from fastapi import APIRouter, Depends, Query
from typing import Any

from ontology_engine.api.dependencies import get_visualization_service
from ontology_engine.services.visualization_service import VisualizationService

router = APIRouter(prefix="/v1/visualize", tags=["visualization"])


# ========== Schema 可视化 ==========

@router.get("/schema/graph")
async def get_schema_graph(
    graph_type: str = Query(
        default="entity_relation",
        description="图类型: entity_relation | metric_dependency | full | rule_overview"
    ),
    layer_filter: str | None = Query(
        default=None,
        description="层过滤(逗号分隔): L1,L3,L4"
    ),
    service: VisualizationService = Depends(get_visualization_service),
):
    """获取 Schema 图数据（G6 格式）"""
    layers = layer_filter.split(",") if layer_filter else None
    result = await service.get_schema_graph(graph_type, layers)
    return {"code": 0, "data": dataclasses_asdict(result)}


# ========== 规则链可视化 ==========

@router.get("/rule-chain/{dimension}")
async def get_rule_chain_graph(
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """获取规则链 DAG 图数据（X6 格式）"""
    result = await service.get_rule_chain_graph(dimension)
    return {"code": 0, "data": dataclasses_asdict(result)}


# ========== 模拟执行 ==========

class SimulationRequest(BaseModel):
    entity_id: str
    dimension: str
    overrides: dict[str, Any] | None = None
    dry_run: bool = True


@router.post("/simulate")
async def simulate_execution(
    request: SimulationRequest,
    service: VisualizationService = Depends(get_visualization_service),
):
    """模拟执行规则链"""
    result = await service.simulate_execution(
        entity_id=request.entity_id,
        dimension=request.dimension,
        overrides=request.overrides,
        dry_run=request.dry_run,
    )
    return {"code": 0, "data": dataclasses_asdict(result)}


# ========== 执行回放 ==========

@router.get("/execution/{entity_id}/{dimension}")
async def get_execution_trace(
    entity_id: str,
    dimension: str,
    service: VisualizationService = Depends(get_visualization_service),
):
    """获取历史执行轨迹"""
    steps = await service.get_execution_trace(entity_id, dimension)
    return {"code": 0, "data": [dataclasses_asdict(s) for s in steps]}
```

### 2.2 序列化辅助

```python
def dataclasses_asdict(obj: Any) -> Any:
    """递归将 dataclass 转为 dict，处理特殊类型"""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = dataclasses_asdict(value)
        return result
    elif isinstance(obj, list):
        return [dataclasses_asdict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclasses_asdict(v) for k, v in obj.items()}
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj
```

## 三、依赖注入更新

### dependencies.py 新增

```python
def get_visualization_service() -> VisualizationService:
    """Get visualization service."""
    if _services is None or "visualization" not in _services:
        raise HTTPException(
            status_code=500,
            detail="Visualization service not initialized"
        )
    return _services["visualization"]
```

### server.py 更新

```python
# lifespan 中新增:
from ontology_engine.services.visualization_service import VisualizationService

services["visualization"] = VisualizationService(
    schema_service=services["schema"],
    analysis_service=services["analysis"],
    storage=storage,
    schema=schema,
)

# create_app 中新增:
from ontology_engine.api.routes import visualization
app.include_router(visualization.router, tags=["Visualization"])
```

## 四、API 端点汇总

| 方法 | 端点 | 请求 | 响应 | 核心场景 |
|------|------|------|------|----------|
| GET | /v1/visualize/schema/graph | graph_type, layer_filter | SchemaGraphData | 场景1+2 |
| GET | /v1/visualize/rule-chain/{dim} | dimension | RuleChainGraphData | 场景3+4 |
| POST | /v1/visualize/simulate | SimulationRequest | SimulationResult | 场景3+4+5 |
| GET | /v1/visualize/execution/{eid}/{dim} | entity_id, dimension | ExecutionStepSnapshot[] | 场景3+4 |

## 五、错误响应

```python
# Schema 未加载
{"code": 1, "message": "Schema not loaded"}

# 实体不存在
{"code": 2, "message": "Entity not found: {entity_id}"}

# 维度无规则
{"code": 0, "data": {"dimension": "xxx", "nodes": [], "edges": []}}

# 模拟执行异常
{"code": 3, "message": "Simulation failed: {error_detail}"}
```

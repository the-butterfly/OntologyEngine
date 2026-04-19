# 模块 09: 服务层 (Services)

> **位置**: `ontology_engine/services/`
> **依赖**: 所有引擎层、存储层
> **被依赖**: API 层
> **状态**: 基本功能已实现，事务与权限待完善
> **最后核验**: 2026-04-16

## 1. 职责

1. **用例编排** — 组合多个引擎完成业务场景
2. **跨引擎协调** — L2→L3→L4 数据流协调
3. **DTO 转换** — 领域模型 ↔ API 模型隔离
4. **事务管理** — 当前为软失败模式，非原子回滚 **[待完善]**
5. **权限检查** — 未实现 **[待实现]**

## 2. 服务划分 (当前实现)

| 服务 | 职责 | 代码路径 | 状态 |
|------|------|----------|------|
| SchemaService | Schema 加载/校验 | `services/schema_service.py` | ✅ 已实现 |
| EntityService | 实体 CRUD/批量导入 | `services/entity_service.py` | ✅ 已实现 |
| AnalysisService | 分析编排 (核心) | `services/analysis_service.py` | ✅ 已实现 |
| QueryService | 知识检索 | `services/query_service.py` | ✅ 已实现 |
| IngestionService | 数据导入/ETL | `services/ingestion_service.py` | ✅ 已实现 |

### 额外服务 (代码中存在，设计文档未覆盖)

| 服务 | 代码路径 | 说明 |
|------|----------|------|
| DAGService | `services/dag_service.py` | DAG 编排服务 |
| DatasetService | `services/dataset_service.py` | 数据集服务 |
| RuleService | `services/rule_service.py` | 规则管理 (与 AnalysisService 有重叠) |
| SimulationService | `services/simulation_service.py` | 模拟服务 |
| VisualizationService | `services/visualization_service.py` | 可视化服务 |
| IncrementalUpdate | `services/incremental_update.py` | 增量更新 |

## 3. 核心编排流 (已验证)

`AnalysisService.execute_analysis()` 实际实现：

```python
async def execute_analysis(self, entity_id, dimension, context=None):
    # 1. 获取实体
    entity = await self.storage.get_entity_by_id(entity_id)

    # 2. L2 归类
    category_tags = await self.categorization_engine.categorize(entity)

    # 3. L3 指标预计算
    computed_metrics = await self.metric_engine.compute_batch(...)

    # 4. L4 规则执行
    analysis_result = await self.rule_executor.execute_dimension(...)

    # 5. 组装结果
    return AnalysisResponse(...)
```

**验证结果**: 跨引擎协调流程与设计完全一致。

## 4. 事务管理状态

**设计目标**: 原子性事务，"全成功或全失败"

**当前实现**: 软失败模式

- `EntityService.batch_create()`: 逐条处理，失败记录到 `errors` 列表，继续执行后续
- `IngestionService.import_instances()`: 逐条处理，失败记录到 `errors` 列表

**差距**: 无显式事务回滚机制。中途失败的批次不会回滚已成功写入的数据。

## 5. 权限检查状态

**设计目标**: 接口级别权限验证

**当前实现**: ❌ 未实现 (2026-04-16)

代码中无任何权限检查逻辑。

## 6. DTO 转换

**代码路径**: `ontology_engine/services/dto/`

| 文件 | 状态 |
|------|------|
| `requests.py` | ✅ 已实现 |
| `responses.py` | ✅ 已实现 |
| `errors.py` | ✅ 已实现 |

## 7. 文件结构

```
ontology_engine/services/
├── __init__.py
├── schema_service.py       # SchemaService
├── entity_service.py       # EntityService
├── analysis_service.py     # AnalysisService (核心编排)
├── query_service.py        # QueryService
├── ingestion_service.py    # IngestionService
├── dag_service.py          # DAGService
├── dataset_service.py      # DatasetService
├── rule_service.py         # RuleService
├── simulation_service.py   # SimulationService
├── visualization_service.py # VisualizationService
├── incremental_update.py   # 增量更新
│
└── dto/                    # DTO 模型
    ├── __init__.py
    ├── requests.py
    ├── responses.py
    └── errors.py
```

## 8. 代码映射

| 设计组件 | 实际代码路径 | 实现状态 |
|---------|-------------|---------|
| SchemaService | `services/schema_service.py` | ✅ 已实现 |
| EntityService | `services/entity_service.py` | ✅ 已实现 |
| AnalysisService | `services/analysis_service.py` | ✅ 已实现 |
| QueryService | `services/query_service.py` | ✅ 已实现 |
| IngestionService | `services/ingestion_service.py` | ✅ 已实现 |
| 事务管理 (原子回滚) | - | ❌ 未实现 |
| 权限检查 | - | ❌ 未实现 |

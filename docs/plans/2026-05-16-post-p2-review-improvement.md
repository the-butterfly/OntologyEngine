# P0-P2 改造后代码审查改进计划

> **status**: planned
> **phase**: post-p2-review
> **source_of_truth**: 本文档
> **last_verified**: 2026-05-16
> **verified_against**: 两轮代码审查（P0-P2 改造 + P0 StorageInterface 改造）
> **review_round_1**: P0-P2 改造审查（16 项发现）
> **review_round_2**: P0 StorageInterface + Memory 改造审查（15 项发现）

---

## 一、审查发现总览

两轮审查共发现 **31 项问题**，按严重程度分布：

| 严重度 | 数量 | 说明 |
|--------|------|------|
| P0（必须修复） | 7 | 安全漏洞、数据丢失、运行时崩溃 |
| P1（应当修复） | 12 | 架构违规、类型不安全、功能缺陷 |
| P2（建议改进） | 12 | 代码质量、测试覆盖、评估体系 |

### P0 问题清单

| # | 来源 | 问题 | 影响范围 |
|---|------|------|----------|
| P0-1 | R2 | `_apply_belief_revision_rules()` 使用 `eval()` | 代码注入风险，安全漏洞 |
| P0-2 | R2 | Repository 双接口适配使用 `hasattr` 运行时检查 | 7 方法 × 2 分支 = 14 个 type:ignore，脆弱 |
| P0-3 | R2 | `CognitiveStorage.batch_save()` ID 丢失 | 双写时 sqlite ID 被 chromadb 覆盖 |
| P0-4 | R2 | SQLiteAdapter FTS5 BM25 排序方向错误 | 搜索结果相关性倒序 |
| P0-5 | R1 | ConsumptionService 1484 行，搬家而非重构 | 新的上帝对象 |
| P0-6 | R1 | API 路由层大量业务逻辑未下沉 | management.py 1349 行，semantic_spaces.py 1652 行 |
| P0-7 | R1 | visualization.py 直接引用 engine 层 | 跨层违规，请求仍可达 |

### P1 问题清单

| # | 来源 | 问题 | 影响范围 |
|---|------|------|----------|
| P1-1 | R1 | DI 模式不一致（Depends vs 直接调用） | 9 个路由使用直接调用 |
| P1-2 | R1 | FeedbackService/MemoryService 初始化不统一 | 资源泄漏风险 |
| P1-3 | R1 | 12 个 deprecated 路由仍活跃注册 | API 表面积膨胀 |
| P1-4 | R1 | 前端 SimulationResult 三处不同别名 | 类型安全漏洞 |
| P1-5 | R1 | ruleGroupsApi.simulate() 返回值不一致 | 可能是 bug |
| P1-6 | R1 | spaceStore 7 个字段使用 any | 类型安全缺失 |
| P1-7 | R1 | memoryApi.ts 目录位置不一致 | 目录约定违反 |
| P1-8 | R2 | MemoryAPI 2109 行上帝对象 | 28 个公开方法，SRP 违反 |
| P1-9 | R2 | oe_delete_memory 调用不存在的 api.delete_memory() | 运行时 AttributeError |
| P1-10 | R2 | ChromaDBAdapter.count() 参数不匹配 | ChromaDB API 不支持 where |
| P1-11 | R2 | SQLiteAdapter 异步模式混用 | 事件循环阻塞 + 线程安全 |
| P1-12 | R2 | 测试使用已废弃的 asyncio.get_event_loop() | Python 3.10+ DeprecationWarning |

### P2 问题清单

| # | 来源 | 问题 |
|---|------|------|
| P2-1 | R1 | SchemaV2 `_normalize_element_type` 重复三次 |
| P2-2 | R1 | `KGMLSchema.to_space_layers_dict()` 264 行手动序列化 |
| P2-3 | R1 | CognitiveStore.search_cognitive() 仅子串匹配 |
| P2-4 | R1 | 评估框架新旧体系并存（EvalReport vs AcptReport） |
| P2-5 | R1 | 验证脚本只做静态检查 |
| P2-6 | R1 | benchmark_performance.py P99 计算偏差 |
| P2-7 | R2 | StorageRouting 与 VALID_MEMORY_TYPES 同步风险 |
| P2-8 | R2 | _rrf_fuse() sorted_ids 使用 dict.get 作为 key |
| P2-9 | R2 | ChromaDBAdapter 重建 CognitiveNode 丢失 20+ 字段 |
| P2-10 | R2 | kuzu_store list_cognitive_nodes 未传递 as_of |
| P2-11 | R2 | _infer_memory_type() 正则仅英文，中文无效 |
| P2-12 | R1 | 前端 visualization.ts 间接调用模式冗余 |

---

## 二、改进计划

### 依赖关系图

```
Sprint 1 (安全 + 数据完整性)
├── P0-1 eval() → 安全表达式求值器
├── P0-3 batch_save ID 丢失 → 修复合并逻辑
├── P0-4 FTS5 BM25 排序 → 修复排序方向
└── P1-9 oe_delete_memory → 添加缺失方法

Sprint 2 (架构合规)
├── P0-2 Repository 双接口 → LegacyStorageAdapter
├── P0-7 visualization.py 跨层 → 异常重导出
├── P1-11 SQLiteAdapter 异步 → 统一 to_thread + threading.Lock
└── P1-12 测试 asyncio → pytest-asyncio 迁移

Sprint 3 (上帝对象拆分)
├── P0-5 ConsumptionService → 拆分 3 个子服务
├── P0-6 API 路由业务逻辑 → 下沉到 Service 层
├── P1-8 MemoryAPI → 按职责域拆分
└── P1-3 deprecated 路由 → 制定移除时间表

Sprint 4 (DI + 前端统一)
├── P1-1 DI 模式 → 全部 Depends()
├── P1-2 服务初始化 → lifespan 统一管理
├── P1-4 SimulationResult 别名 → 消除冲突
├── P1-5 ruleGroupsApi.simulate() → 修复返回值
├── P1-6 spaceStore 类型 → 替换 any
├── P1-7 memoryApi.ts → 迁移到 api/
└── P1-10 ChromaDBAdapter.count() → 修复 API 调用

Sprint 5 (质量提升)
├── P2-1 _normalize_element_type → 公共 mixin
├── P2-2 to_space_layers_dict → model_dump()
├── P2-7 StorageRouting 同步 → 编译期断言
├── P2-8 _rrf_fuse key → lambda 替换
├── P2-9 ChromaDB 字段 → 扩展 metadata 或补查询
├── P2-10 as_of 传递 → 修复参数透传
└── P2-11 中文推断 → 添加中文正则

Sprint 6 (评估体系)
├── P2-3 search_cognitive → 实现真正的混合搜索
├── P2-4 评估框架统一 → EvalReport → AcptReport 迁移
├── P2-5 验证脚本 → 增加功能验证
└── P2-6 P99 计算 → 修复百分位算法
```

---

## 三、Sprint 详细规格

### Sprint 1: 安全 + 数据完整性

**目标**: 消除安全漏洞和数据丢失风险，确保搜索结果正确性。

#### S1-1: 替换 eval() 为安全表达式求值器

**文件**: `ontology_engine/engine/cognitive/memory_api.py` L1933

**当前代码**:
```python
if eval(rule.condition, {"__builtins__": {}}, context):
```

**改进方案**:
1. 引入 `ontology_engine/engine/cognitive/rule_eval.py` 模块
2. 实现基于 AST 的安全求值器，仅支持比较运算符（`>`, `<`, `>=`, `<=`, `==`, `!=`）和逻辑运算符（`and`, `or`, `not`）
3. 白名单允许的变量名（`confidence`, `feedback_weight`, `evidence_count`, `is_newer`, `schema_alignment`, `source`, `belief_status`）
4. 替换 `_apply_belief_revision_rules()` 中的 `eval()` 调用

**验证**:
- 现有 `DEFAULT_BELIEF_REVISION_RULES` 中所有条件表达式求值结果不变
- 恶意表达式（如 `__import__`, `().__class__`）抛出 `ValueError`
- 新增单元测试覆盖安全求值器

#### S1-2: 修复 CognitiveStorage.batch_save() ID 丢失

**文件**: `ontology_engine/storage/cognitive_storage.py` L84-98

**改进方案**:
```python
async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
    sqlite_nodes = [n for n in nodes if "sqlite" in StorageRouting.get_stores(n.memory_type)]
    chroma_nodes = [n for n in nodes if "chromadb" in StorageRouting.get_stores(n.memory_type) and self._chromadb is not None]

    sqlite_ids = await self._sqlite.batch_save(sqlite_nodes) if sqlite_nodes else []
    if chroma_nodes:
        await self._chromadb.batch_save(chroma_nodes)

    id_map = {n.id: n.id for n in nodes}
    for n, sid in zip(sqlite_nodes, sqlite_ids):
        id_map[n.id] = sid
    return [id_map[n.id] for n in nodes]
```

**验证**: 新增测试——混合 sqlite+chromadb 类型节点批量保存，验证返回 ID 列表顺序与输入一致。

#### S1-3: 修复 SQLiteAdapter FTS5 BM25 排序方向

**文件**: `ontology_engine/storage/sqlite/cognitive_adapter.py` L254-263

**改进方案**:
```sql
ORDER BY fts_score ASC
```

同时修改 L273 的 scores 计算，使用归一化的 BM25 分数而非位置序号：
```python
raw_scores = {}
for i, row in enumerate(rows):
    raw_score = row["fts_score"] if "fts_score" in row.keys() else -(i + 1)
    raw_scores[row["id"]] = raw_score
min_score = min(raw_scores.values()) if raw_scores else -1
max_score = max(raw_scores.values()) if raw_scores else 0
score_range = max_score - min_score if max_score != min_score else 1.0
scores = {nid: (s - min_score) / score_range for nid, s in raw_scores.items()}
```

**验证**: 新增测试——插入 3 个文档，验证 FTS5 搜索结果按相关性降序排列。

#### S1-4: 修复 oe_delete_memory 调用不存在方法

**文件**: `ontology_engine/mcp/tools/memory.py` L287

**改进方案**: 在 `MemoryAPI` 中添加 `delete_memory()` 方法，委托给 `CognitiveRepository.delete_node()`。

**验证**: MCP 工具 `oe_delete_memory` 端到端测试通过。

---

### Sprint 2: 架构合规

**目标**: 消除跨层违规，统一异步模式，提升类型安全。

#### S2-1: 引入 LegacyStorageAdapter 消除 Repository 双接口分支

**文件**: 新增 `ontology_engine/storage/legacy_adapter.py`

**改进方案**:
```python
class LegacyStorageAdapter(StorageInterface):
    """Adapts CognitiveStorageBackend to StorageInterface."""

    def __init__(self, backend: CognitiveStorageBackend) -> None:
        self._backend = backend

    async def save_node(self, node: CognitiveNode) -> str:
        await self._backend.save_cognitive_node(node.to_dict())
        return node.id

    async def get_node(self, node_id: str) -> CognitiveNode | None:
        data = await self._backend.get_cognitive_node(node_id)
        if data is None:
            return None
        return CognitiveNode.from_dict(data) if isinstance(data, dict) else data

    async def search(self, query: SearchQuery) -> SearchResult:
        data_list = await self._backend.list_cognitive_nodes(
            memory_type=query.memory_type,
            cognitive_layer=query.cognitive_layer,
            belief_status=query.belief_status,
            domain_id=query.space_id,
            limit=query.top_k,
        )
        nodes = [CognitiveNode.from_dict(d) for d in data_list]
        return SearchResult(nodes=nodes, scores={n.id: 1.0 for n in nodes})

    async def delete_node(self, node_id: str, soft: bool = True) -> None:
        await self._backend.delete_cognitive_node(node_id)

    async def batch_save(self, nodes: list[CognitiveNode]) -> list[str]:
        for n in nodes:
            await self._backend.save_cognitive_node(n.to_dict())
        return [n.id for n in nodes]

    async def count(self, filter: dict[str, Any]) -> int:
        data = await self._backend.list_cognitive_nodes(limit=999999, **filter)
        return len(data)
```

然后修改 `CognitiveRepository.__init__` 签名为 `def __init__(self, storage: StorageInterface)`，移除 `_is_new_interface()` 和所有分支。

**验证**: 现有 24 个 repository 测试全部通过，无 `type: ignore[union-attr]`。

#### S2-2: 修复 visualization.py 跨层违规

**文件**: `ontology_engine/api/routes/visualization.py` L15-19

**改进方案**: 将 `EntityNotFoundError`、`SchemaNotLoadedError` 等异常类型重新导出到 `ontology_engine/services/types.py`，visualization.py 从 services 层导入。

**验证**: `grep -r "from.*engine.*import" ontology_engine/api/ --include="*.py"` 无结果（LAYER-EXCEPTION 除外）。

#### S2-3: 统一 SQLiteAdapter 异步模式

**文件**: `ontology_engine/storage/sqlite/cognitive_adapter.py`

**改进方案**:
1. 将 `asyncio.Lock` 替换为 `threading.Lock`
2. 所有数据库操作统一使用 `asyncio.to_thread()`
3. `save_node()` 和 `batch_save()` 中的同步调用改为 `await asyncio.to_thread()`

**验证**: 新增并发测试——10 个协程同时写入，无数据竞争。

#### S2-4: 测试迁移到 pytest-asyncio

**文件**: `tests/unit/storage/test_sqlite_cognitive_adapter.py`, `test_cognitive_storage.py`

**改进方案**: 所有 `asyncio.get_event_loop().run_until_complete()` 替换为 `@pytest.mark.asyncio` + `await`。

**验证**: `pytest tests/unit/storage/ -v` 全部通过，无 DeprecationWarning。

---

### Sprint 3: 上帝对象拆分

**目标**: 消除 3 个核心上帝对象，将业务逻辑下沉到正确的层。

#### S3-1: 拆分 ConsumptionService

**文件**: `ontology_engine/services/consumption_service.py` (1484 行)

**拆分方案**:

| 新服务 | 来源行范围 | 职责 |
|--------|-----------|------|
| `AnalysisOrchestrator` | L853-1018 `_run_full_analysis()` | DAG 分析 + 优先级回退 + 规则循环编排 |
| `RuleExecutionService` | L1020-1144 `_execute_single_rule()` | 规则条件评估 + 动作执行 + 解释生成 |
| `ImpactChainService` | L1416-1483 `_compute_impact_chains()` | BFS 影响链计算 |
| `ConsumptionService` | 剩余 ~200 行 | 消费视图查询 + 编排上述 3 个子服务 |

**验证**: 现有 consumption 相关测试全部通过。

#### S3-2: 下沉 API 路由业务逻辑

**文件**: `ontology_engine/api/routes/management.py` (1349 行), `semantic_spaces.py` (1652 行)

**下沉方案**:

| 逻辑 | 当前位置 | 目标服务 |
|------|---------|---------|
| `_topological_sort()` | management.py L1321-1349 | `RuleService` |
| `get_rule_dependency_graph()` | management.py L1224-1318 | `RuleService` |
| `execute_analyze()` | semantic_spaces.py L1174-1308 | `AnalysisOrchestrator` |
| `execute_simulate()` | semantic_spaces.py L1311-1436 | `SimulationService` |
| Schema 影响分析 | semantic_spaces.py L1439-1513 | `SchemaService` |

**验证**: API 路由文件行数 < 300 行；`grep -r "_topological_sort\|execute_analyze\|execute_simulate" ontology_engine/api/` 无结果。

#### S3-3: 拆分 MemoryAPI

**文件**: `ontology_engine/engine/cognitive/memory_api.py` (2109 行)

**拆分方案**:

| 新类 | 方法 | 职责 |
|------|------|------|
| `MemoryAPI` | remember, recall, reflect | 核心三操作编排 |
| `RecallService` | _recall 内部逻辑, 证据展开, Disposition 权重, 时间衰减, token budget | 检索编排 |
| `CommitmentService` | record_commitment, check_commitments | 承诺管理 |
| `CompilationService` | compile_entity_page, compile_topic_page | 编译页面 |
| `MaintenanceService` | run_consolidation, run_forgetting, dream, correct_memory | 维护操作 |
| `ApprovalService` | approve_memory, update_disposition | 审批流 |

**验证**: `MemoryAPI` 行数 < 400 行；每个子服务 < 300 行；现有 MCP 工具测试全部通过。

#### S3-4: 制定 deprecated 路由移除时间表

**改进方案**:
1. 在 `DeprecationMiddleware` 中添加 `sunset_date` header（RFC 8594）
2. 设置移除日期为 2026-06-30
3. 在 v1.1 版本中返回 `410 Gone` 而非 `200 OK + Deprecation header`
4. 前端确认已全部迁移到新路由后，删除旧路由文件

**验证**: `curl -I /v1/spaces/{id}/entities` 返回 `Deprecation: true` + `Sunset: 2026-06-30`。

---

### Sprint 4: DI + 前端统一

**目标**: 统一后端 DI 模式，消除前端类型安全隐患。

#### S4-1: 统一 DI 模式为 Depends()

**文件**: `ontology_engine/api/routes/` 中 9 个使用直接调用的路由

**改进方案**: 将所有 `service = get_xxx_service()` 替换为 `service: XxxService = Depends(get_xxx_service)`。

**验证**: `grep -r "get_.*_service()" ontology_engine/api/routes/` 无结果。

#### S4-2: 统一服务初始化

**文件**: `ontology_engine/api/server.py`, `ontology_engine/api/dependencies.py`

**改进方案**:
1. 将 `FeedbackService` 纳入 lifespan 初始化，注册到 `_services` 字典
2. 修复 `MemoryService` 关闭逻辑，使用已注册的实例而非创建新实例
3. 在 `services/__init__.py` 中导出 `FeedbackService`

**验证**: lifespan 中所有服务统一初始化和关闭；无 `MemoryService()` 直接构造。

#### S4-3: 统一前端 SimulationResult 命名

**文件**: `ontology-engine-ui/src/types/simulation.ts`, `visualization.ts`, `rule.ts`

**改进方案**:
1. 保留 `simulation.ts` 中的 `SimulationResult` 作为唯一权威定义
2. `visualization.ts` 中 `export { ConsumptionSimulationResult }` （不再 re-export 为 SimulationResult）
3. `rule.ts` 中 `export { RuleSimulationResult }` （不再 re-export 为 SimulationResult）
4. 消费方按实际类型导入

**验证**: `grep -r "as SimulationResult" ontology-engine-ui/src/types/` 无结果。

#### S4-4: 修复 ruleGroupsApi.simulate() 返回值

**文件**: `ontology-engine-ui/src/api/ruleGroups.ts` L354

**改进方案**: `return response.data.data` （与其他方法一致）。需确认后端 simulate 端点是否使用标准 `{ data: {...} }` 响应格式。

**验证**: 前端 simulate 功能端到端测试通过。

#### S4-5: spaceStore 类型安全化

**文件**: `ontology-engine-ui/src/stores/spaceStore.ts`

**改进方案**: 将 7 个 `any` 字段替换为对应类型：
- `views: ViewDetails[]`
- `factObjects: FactObject[]`
- `categorizations: Categorization[]`
- `schemaGraph: SchemaGraphData | null`
- `ruleChainGraph: RuleChainGraphData | null`
- `executionResult: ExecutionResult | null`
- `simulationResult: SimulationResult | null`

**验证**: `tsc --noEmit` 无错误。

#### S4-6: 迁移 memoryApi.ts 到 api/ 目录

**改进方案**:
1. 移动 `src/services/memoryApi.ts` → `src/api/memoryApi.ts`
2. 更新 `MemorySpacePage.tsx` 和 `MemoryDetailDrawer.tsx` 的导入路径
3. 删除空的 `src/services/` 目录

**验证**: `ls src/services/` 不存在；`tsc --noEmit` 无错误。

#### S4-7: 修复 ChromaDBAdapter.count()

**文件**: `ontology_engine/storage/vector/chromadb_adapter.py` L214

**改进方案**: 使用 `Collection.get(where=where)` 计算返回 ID 数量，或直接使用 `Collection.count()` 不带参数。

**验证**: 新增测试验证 count() 返回正确值。

---

### Sprint 5: 质量提升

#### S5-1: 提取 _normalize_element_type 公共 mixin

**文件**: `ontology_engine/core/schema/models.py`

**改进方案**: 创建 `ElementTypeMixin` 类，包含 `_normalize_element_type` validator，`MetricDefinitionV2`、`IndicatorDefinition`、`ScorecardDefinition` 继承该 mixin。

#### S5-2: 简化 to_space_layers_dict()

**文件**: `ontology_engine/core/schema/models.py` L1069-1332

**改进方案**: 使用 `model_dump()` + 后处理替代 264 行手动序列化。

#### S5-3: StorageRouting 编译期同步

**文件**: `ontology_engine/storage/cognitive_interface.py`

**改进方案**: 在模块末尾添加断言：
```python
from ontology_engine.engine.cognitive.models import VALID_MEMORY_TYPES
assert set(StorageRouting.ROUTING.keys()) == set(VALID_MEMORY_TYPES), \
    f"StorageRouting mismatch: missing={set(VALID_MEMORY_TYPES) - set(StorageRouting.ROUTING.keys())}, extra={set(StorageRouting.ROUTING.keys()) - set(VALID_MEMORY_TYPES)}"
```

#### S5-4: _rrf_fuse key 函数安全化

**文件**: `ontology_engine/storage/cognitive_storage.py` L139

**改进方案**: `key=lambda k: doc_scores[k]` 替换 `key=doc_scores.get`。

#### S5-5: ChromaDB 字段扩展

**文件**: `ontology_engine/storage/vector/chromadb_adapter.py`

**改进方案**: 在 `_node_to_metadata()` 中添加 `strength`, `feedback_weight`, `confirmation_count`, `source_fragment_ids`, `scope`, `entity_name`, `entity_type` 等字段。对于 `get_node()` 返回的节点，在 `CognitiveStorage.get_node()` 中补充查询 SQLite 获取完整数据。

#### S5-6: kuzu_store as_of 参数传递

**文件**: `ontology_engine/storage/graph/kuzu_store.py` L2533-2551

**改进方案**: `list_cognitive_nodes()` 传递 `as_of` 参数到 `query_cognitive_nodes()`。

#### S5-7: 中文 memory_type 推断

**文件**: `ontology_engine/engine/cognitive/memory_api.py` L192-230

**改进方案**: 添加中文正则模式：
```python
("entity", [r"(公司|企业|机构|组织|人物|产品|地点|城市|国家)"]),
("relation", [r"(任职|拥有|位于|总部|创办|管理|汇报|合作|子公司|母公司|供应商|客户)"]),
("rule", [r"(应该|必须|不得|禁止|如果.*则|规则|政策|规定)"]),
("episode", [r"(昨天|今天|上周|上月|发生|出现|事件|事故)"]),
("procedure", [r"(首先|然后|接着|最后|步骤|流程|操作|方法)"]),
("opinion", [r"(我认为|我觉得|相信|希望|可能|大概|似乎)"]),
("observation", [r"(观察到|发现|检测到|测量|记录|数据显示)"]),
```

---

### Sprint 6: 评估体系

#### S6-1: 实现 CognitiveStore.search_cognitive() 真正的混合搜索

**文件**: `ontology_engine/storage/cognitive/store.py` L239-262

**改进方案**: 委托给 `CognitiveStorage.search()`，利用 RRF 融合 SQLite FTS5 + ChromaDB 向量搜索。

#### S6-2: 统一评估框架

**改进方案**:
1. 将 01-10 的 `EvalReport` / `_ok()` 迁移到 `AcptReport` / `r()`
2. 统一评分函数（f1_score, rank_weighted_score, score_behavior）
3. 统一输出格式为 `acpt_*.json`
4. 更新 README.md 覆盖 01-12

#### S6-3: 增强验证脚本

**改进方案**:
1. `verify-evaluation-framework.sh` 增加实际运行 benchmark_performance.py --quick
2. 新增 `verify-api-contract.sh` 验证前后端 API 契约一致性
3. 新增 `verify-frontend-types.sh` 验证前端类型定义与后端 DTO 对齐

#### S6-4: 修复 P99 计算

**文件**: `scripts/benchmark_performance.py` L51

**改进方案**:
```python
def p99(values: list[float]) -> float:
    sorted_v = sorted(values)
    idx = min(int(math.ceil(len(sorted_v) * 0.99)) - 1, len(sorted_v) - 1)
    return sorted_v[idx]
```

---

## 四、验收标准

### 全局验收

| 检查项 | 命令 |
|--------|------|
| 后端类型检查 | `mypy ontology_engine/ --strict` |
| 后端代码规范 | `ruff check ontology_engine/` |
| 单元测试 | `pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing` |
| 跨层调用检查 | `grep -r "from.*storage.*import\|from.*engine.*import" ontology_engine/api/ --include="*.py"` |
| 外部存储依赖 | `grep -r "neo4j\|redis\|psycopg" ontology_engine/ --include="*.py" \| grep -v "adapters/"` |
| 前端类型检查 | `cd ontology-engine-ui && tsc --noEmit` |
| 前端代码规范 | `cd ontology-engine-ui && eslint .` |

### Sprint 级验收

| Sprint | 核心验收指标 |
|--------|-------------|
| S1 | `eval()` 调用数 = 0；batch_save 混合类型测试通过；FTS5 搜索结果相关性正确；oe_delete_memory 端到端通过 |
| S2 | Repository 无 `type: ignore[union-attr]`；api 层无 engine 直接导入；SQLiteAdapter 无同步 DB 调用；测试无 DeprecationWarning |
| S3 | ConsumptionService < 300 行；management.py < 300 行；semantic_spaces.py < 300 行；MemoryAPI < 400 行；deprecated 路由有 sunset header |
| S4 | DI 全部 Depends()；前端无 `as SimulationResult` re-export；spaceStore 无 any；tsc --noEmit 通过 |
| S5 | _normalize_element_type 仅 1 处定义；to_space_layers_dict < 80 行；StorageRouting 断言通过；中文推断测试通过 |
| S6 | search_cognitive 使用 RRF 融合；评估框架统一为 AcptReport；P99 计算正确 |

---

## 五、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| S3 拆分引入回归 | 中 | 高 | 每个子服务拆分后立即运行全量单元测试 |
| LegacyStorageAdapter 性能损耗 | 低 | 中 | 基准测试对比；如损耗 > 5%，考虑直接迁移到 StorageInterface |
| deprecated 路由移除影响前端 | 中 | 高 | 先确认前端已迁移，再设置 sunset，最后才删除 |
| ChromaDB metadata 扩展导致迁移 | 中 | 中 | 新增字段设默认值，不破坏现有数据 |
| MemoryAPI 拆分影响 MCP 工具 | 高 | 高 | MCP 工具层保持不变，MemoryAPI 内部委托给子服务 |

---

## 六、时间线

| Sprint | 预计周期 | 依赖 |
|--------|---------|------|
| S1 | 2 天 | 无 |
| S2 | 3 天 | S1 完成 |
| S3 | 5 天 | S2 完成（S3-1 依赖 S2-1 的 LegacyStorageAdapter） |
| S4 | 3 天 | S3 完成（S4-2 依赖 S3-3 的 MemoryAPI 拆分） |
| S5 | 3 天 | S4 完成 |
| S6 | 3 天 | S5 完成（S6-1 依赖 S5-5 的 ChromaDB 字段扩展） |

总计约 **19 个工作日**。

---

## 七、与现有文档的关系

| 文档 | 关系 |
|------|------|
| `docs/plans/2026-05-17-agent-memory-optimization.md` | 本计划是其实施后的审查改进，补充 Q1-Q4 之外的发现 |
| `docs/STATUS.md` | 需更新 Agent 记忆系统状态，标注本改进计划 |
| `docs/ROADMAP.md` | 需在 P2 阶段后增加"审查改进"里程碑 |
| `docs/01-overview/09-agent-memory.md` | S3-3 MemoryAPI 拆分后需同步更新架构描述 |
| `docs/02-design/agent-memory/` | S2-1 LegacyStorageAdapter 需同步更新存储层设计 |

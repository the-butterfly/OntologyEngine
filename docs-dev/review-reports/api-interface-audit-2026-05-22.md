# API 对外接口审查报告（设计-实现一致性复核）

> **审查日期**: 2026-05-22
> **审查范围**: REST API + MCP Server 全量对外接口，含前端调用链路和 examples 使用验证
> **审查方法**: 设计文档 ↔ 代码实现 ↔ 前端调用 ↔ examples/tests 用例 四方交叉验证
> **前置报告**: `docs-dev/review-reports/api-review.md`（2026-04-19，侧重路由重复和命名问题）
> **本次增量**: 前端/Examples 实际调用验证、兼容层实现状态复核、路由注册树完整映射、双前缀 Bug 发现

---

## 1. 审查结论修正

与 2026-04-19 的前置报告及本次初版报告相比，以下结论需要修正：

| # | 初版结论 | 修正后结论 | 修正原因 |
|---|---------|-----------|---------|
| 1 | "兼容层完全未实现" | **DeprecationMiddleware 已实现，但仅 header 模式** | [middleware.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/api/middleware.py) 已注册，映射了 11 条废弃路径，但 mode="header" 不执行 301 重定向 |
| 2 | "前端未使用旧路由" | **前端仍大量使用旧路由** | 前端 `ruleGroups.ts` 调用 `/v1/rule-groups/*`，`memoryApi.ts` 调用 `/v1/memory/reflect_status`（路径错误），`spaceApi.ts` 调用 `/v1/management/schemas/{id}/load-from-yaml` |
| 3 | "Actions API 完全未实现" | **旧版 Actions 已实现，新版设计未落地** | `actions.py` 实现了 `/v1/spaces/{space_id}/actions/*`（旧版），设计文档的 `/v1/actions/{action_name}` 未实现 |
| 4 | 无 | **发现 categories/actions 双前缀 Bug** | `rules_router`(prefix="/v1") 内嵌套 `categories_router`(prefix="/v1/categories")，实际路径变为 `/v1/v1/categories/*` |

---

## 2. 问题清单（按严重程度排序）

### P0 — 运行时 Bug

#### P0-1: categories/actions 子路由双前缀导致端点不可达

**位置**: [rules.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/api/routes/rules.py) → include_router(categories_router / actions_router)

**现象**: `rules_router` 自身 prefix="/v1"，其内嵌套的 `categories_router`(prefix="/v1/categories") 和 `actions_router`(prefix="/v1/spaces/{space_id}/actions") 的实际注册路径变为：
- `/v1/v1/categories/*` （预期 `/v1/categories/*`）
- `/v1/v1/spaces/{space_id}/actions/*` （预期 `/v1/spaces/{space_id}/actions/*`）

**影响**:
- 前端 `ruleGroups.ts` 的 `importYamlFromPath()` 调用 `/v1/management/schemas/{id}/load-from-yaml`，此路径在 DeprecationMiddleware 映射中会添加 header 但不重定向，仍可工作
- 集成测试 `test_category_api_flow.py` 调用 `/v1/categories/rule-mappings`，此路径因双前缀 Bug 不可达，测试应失败
- `DeprecationMiddleware` 对 `/v1/categories` 的匹配无法触达实际路由

**修复方案**: 将 `categories_router` 和 `actions_router` 的 prefix 改为相对路径（去掉 `/v1` 前缀），或在 `rules_router` 中不设 prefix 而在各子路由各自带完整 prefix

**关联影响**:
- 前端: 无直接影响（前端不使用 categories 端点，使用 rule-groups 代替）
- 测试: `test_category_api_flow.py` 需更新路径
- 中间件: DeprecationMiddleware 的 categories 映射可正常工作

---

#### P0-2: 前端 memoryApi 路径错误

**位置**: [memoryApi.ts](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology-engine-ui/src/api/memoryApi.ts) L227

**现象**: `getReflectStatus()` 调用 `/v1/memory/reflect_status`，缺少 `/spaces/{spaceId}` 前缀，与后端路由 `/v1/spaces/{space_id}/memory/*` 不匹配

**影响**: 此端点调用必然 404，前端"反思状态查询"功能不可用

**修复方案**: 改为 `/v1/spaces/${spaceId}/memory/reflect_status`，后端需同步添加此端点（当前后端也无此路由）

**关联影响**: 后端 `memory.py` 路由需新增 `GET /reflect-status` 或 `GET /{reflection_id}` 端点

---

### P1 — 设计-实现严重偏差

#### P1-1: Actions API 设计未落地

**设计**: [actions-routes.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/api/actions-routes.md) 定义了 `/v1/actions/{action_name}` 统一执行入口（5 个端点）

**实现**: `actions.py` 实现的是旧版 `/v1/spaces/{space_id}/actions/ingest|analyze|query|feedback|export`

**影响**:
- 执行入口仍分散在三处（`/v1/rules/execute`、`/v1/views/{id}/execute/analyze`、`/v1/spaces/{id}/actions/analyze`）
- Agent 无法通过统一入口发现和调用动作
- MCP 层 `oe_execute_rule` 部分覆盖了此需求，但 REST API 层缺失

**修复方案**:
1. 实现 `/v1/actions` GET（动作发现）
2. 实现 `/v1/actions/{action_name}/execute` POST（统一执行）
3. 旧版 actions 路由标记 deprecated，通过 DeprecationMiddleware 重定向

**关联影响**:
- 前端: `spaceApi.ts` 的 `executeAnalyze`/`executeSimulate` 需迁移到新路径
- MCP: `oe_execute_rule` 和 `oe_simulate` 逻辑可复用
- 测试: 需新增 Actions API 集成测试

---

#### P1-2: Ontology API 路径结构根本性偏差

**设计**: [ontology-routes.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/api/ontology-routes.md) 定义全局 `/v1/ontology` 入口

**实现**: `ontology.py` 实现为 `/v1/spaces/{space_id}/ontology/*`，Ontology 降级为 Space 内 Schema 视图

**影响**:
- 全局本体概念被 Space 限定，无法表达跨 Space 共享的 Schema
- 旧 `/v1/schema` 路由仍独立存在，三者（/v1/schema、/v1/spaces/{id}/ontology、/v1/spaces/{id}/schema）语义重叠
- 前端未使用 ontology 路由，仍使用 `/v1/spaces/{spaceId}/schema/*`

**修复方案**: 暂缓实现全局 Ontology（当前架构下 Schema 绑定 Space 是合理的），但需：
1. 将 `ontology.py` 标记为 experimental
2. 在设计文档中更新 Ontology 的定位说明
3. 删除或重定向旧 `/v1/schema` 路由

**关联影响**:
- 前端: 无直接影响（未使用 ontology 路由）
- MCP: `oe_load_schema` 使用 Space 内 Schema，与当前实现一致
- 文档: 需更新 ontology-routes.md 的 status

---

#### P1-3: Spaces 路由重复导致死路由

**位置**: [spaces.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/api/routes/spaces.py) → include_router(semantic_spaces_router, management_router)

**现象**: `semantic_spaces_router`(prefix="/v1/spaces") 和 `management_router`(prefix="/v1") 注册了 12+ 个完全相同的 HTTP 路径。由于 semantic_spaces 先注册，management 的同名路由全部成为死路由：

| 路径 | 生效处理函数 | 死路由处理函数 |
|------|------------|--------------|
| `POST /v1/spaces` | semantic_spaces.create_space | management.create_space |
| `GET /v1/spaces` | semantic_spaces.list_spaces | management.list_spaces |
| `GET /v1/spaces/{space_id}` | semantic_spaces.get_space | management.get_space |
| `PUT /v1/spaces/{space_id}` | semantic_spaces.update_space_metadata | management.update_space |
| `DELETE /v1/spaces/{space_id}` | semantic_spaces.delete_space | management.delete_space |
| ... | ... | ... |

**影响**:
- management 独有的路由（activate/deactivate/archive/schema L1-L4 CRUD/load-yaml/update-entity/delete-entity）仍可正常工作
- 但同名路由的行为差异（如 `PUT /v1/spaces/{space_id}` 在 semantic_spaces 中需要 `If-Match` header，在 management 中不需要）被掩盖
- 维护成本翻倍，修改一处容易遗漏另一处

**修复方案**:
1. 将 management 独有的路由迁移到 semantic_spaces_router
2. 删除 management_router 中的重复路由
3. 最终删除 management.py 文件

**关联影响**:
- 前端: `spaceApi.ts` 调用的 activate/deactivate/archive/schema L1-L4/load-yaml/update-entity/delete-entity 均在 management 独有路由中，迁移后路径不变
- 测试: `test_middleware.py` 验证了 management → spaces 重定向，需更新
- 中间件: DeprecationMiddleware 的 `/v1/management` 映射可保留

---

### P2 — 兼容层与废弃管理

#### P2-1: DeprecationMiddleware 仅 header 模式，未执行 301 重定向

**位置**: [server.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/api/server.py) L138

**现状**: `DeprecationMiddleware(mode="header")` 仅添加 `Deprecation: true`、`Sunset: 2026-06-30`、`X-Deprecation-Warning`、`Link` 响应头，不执行 301 重定向

**影响**:
- 旧路由仍直接处理请求，调用方无感知
- Sunset 日期 2026-06-30 临近，但无实际迁移压力
- 前端和 examples 仍大量使用旧路由（见下方统计）

**旧路由实际使用统计**:

| 旧路由前缀 | 前端使用 | Examples 使用 | 测试覆盖 |
|-----------|---------|-------------|---------|
| `/v1/management/*` | ✅ 1 处 (load-from-yaml) | ✅ 2 处 (load-from-json, activate) | ✅ test_middleware.py |
| `/v1/consumption/*` | ❌ | ✅ 5 处 (demo_verify_space.py) | ✅ test_consumption_api_flow.py |
| `/v1/visualize/*` | ❌ | ❌ | ❌ |
| `/v1/analysis/*` | ❌ | ❌ | ❌ |
| `/v1/entities/*` | ❌ | ❌ | ❌ |
| `/v1/relations/*` | ❌ | ❌ | ❌ |
| `/v1/datasets/*` | ❌ | ❌ | ✅ test_dataset_api_flow.py |
| `/v1/incremental/*` | ❌ | ❌ | ✅ test_incremental_api_flow.py |
| `/v1/ingestion/*` | ❌ | ❌ | ❌ |
| `/v1/categories/*` | ❌ | ❌ | ✅ test_category_api_flow.py（因双前缀 Bug 可能失败） |
| `/v1/schema/*` | ❌ | ❌ | ❌ |

**修复方案**:
1. 切换到 `mode="redirect"` 启用 301 重定向
2. 前端优先迁移：`ruleGroups.ts` 的 `importYamlFromPath` 改用 `/v1/spaces/{spaceId}/schema/load-yaml`
3. Examples 优先迁移：`demo_verify_space.py` 改用 `/v1/views/*` 替代 `/v1/consumption/*`
4. 测试同步更新

**关联影响**:
- 前端: 1 处需修改
- Examples: 7 处需修改
- 测试: 5 个测试文件需更新路径

---

#### P2-2: Query API 端点未按设计精简

**设计**: [query-routes.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/api/query-routes.md) 定义 5 个端点

**实现**: 11 个端点（含 deprecated 的 `/vector`，GET+POST 双模式的 pattern-match/traverse/path）

**影响**:
- OpenAPI 文档膨胀，调用方认知负担重
- `POST /v1/query/explain` 未实现（Agent 可解释性关键端点）
- 旧端点无 Deprecation 标记

**修复方案**:
1. 标记 `/vector`、GET 版 pattern-match/traverse/path 为 deprecated
2. 实现 `POST /v1/query/explain`
3. 在 DeprecationMiddleware 中添加旧 Query 端点的映射

**关联影响**:
- 前端: 无直接影响（前端不使用 query 端点）
- 测试: `test_query_api_flow.py` 使用旧端点，需更新
- MCP: `oe_query` 使用 service 层直接调用，不受影响

---

### P3 — 数据一致性与安全

#### P3-1: Space 状态机未在 API 层强制执行

**设计**: spaces-routes.md 定义了 DRAFT → ACTIVE → ARCHIVED 状态机，ACTIVE 状态需先停用才能删除

**实现**: API 层无状态校验，可在任何状态下执行任何操作

**影响**: 可在 ACTIVE 状态下直接删除 Space，破坏关联 View 和实例数据的一致性

**修复方案**: 在 `semantic_spaces.py` 的 `delete_space` 和 `update_space_metadata` 中添加状态校验

**关联影响**: 前端 `spaceApi.ts` 的 deleteSpace 需处理 409 Conflict 响应

---

#### P3-2: Space 读-改-写无并发控制

**现象**: management.py 和 semantic_spaces.py 中的 Schema/Instance 修改均采用 `get_space` → 修改内存对象 → `save_space` 模式，无乐观锁

**影响**: 并发修改同一 Space 时存在 Lost Update 风险

**修复方案**: semantic_spaces.py 已实现 ETag 机制（`get_space_etag` + `If-Match` header），但 management.py 未使用。需统一到 ETag 方案。

**关联影响**: 前端 `spaceApi.ts` 的 `updateSpace` 已支持 `If-Match` header

---

### P4 — 代码质量与可维护性

#### P4-1: 请求模型类型安全不足

**现象**: actions.py、categories.py、memory.py、datasets.py 等路由使用 `dict[str, Any]` 接收请求体，缺乏 Pydantic BaseModel 校验

**影响**:
- OpenAPI 文档不完整（无法生成请求体 Schema）
- 运行时类型错误风险
- 无法自动生成前端 TypeScript 类型

**修复方案**: 逐步迁移到 Pydantic BaseModel，优先处理高频使用端点（memory、datasets）

**关联影响**: 前端类型定义需同步更新

---

#### P4-2: MCP `oe_update_relation` 未完成实现

**位置**: [management.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/mcp/tools/management.py)

**现象**: `oe_update_relation` 仅验证节点存在，未实际更新属性

**修复方案**: 调用 `MemoryAPI.correct_memory()` 或 `SpaceService.update_relation_in_space()` 执行属性更新

---

#### P4-3: MCP `oe_query` 降级策略不透明

**现象**: vector/hybrid 搜索抛出 NotImplementedError 时静默降级到 pattern_match，调用方无法感知

**修复方案**: 在响应中添加 `fallback_used: true` 字段，或在 error 中提示降级原因

---

#### P4-4: 前端绕过统一 API 客户端

**位置**: [ConsumptionViewPage.tsx](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology-engine-ui/src/pages/ConsumptionViewPage.tsx) L53, [ConsumptionViewListPage.tsx](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology-engine-ui/src/pages/consumption/ConsumptionViewListPage.tsx) L26

**现象**: 直接使用原生 `fetch()` 调用 `/v1/views` 端点，绕过统一 `apiClient`（缺少认证 token 注入和统一错误处理）

**修复方案**: 改用 `spaceApi.listViews()` / `spaceApi.getView()`

---

## 3. 路由注册树（完整映射）

```
app (FastAPI)
│
├── DeprecationMiddleware (mode="header", sunset=2026-06-30)
├── CORSMiddleware (allow_origins=["*"])
│
├── GET  /health
├── GET  /
│
├── [1] spaces_router (tags=["Spaces"])
│   ├── semantic_spaces_router (prefix="/v1/spaces") [deprecated]
│   │   ├── POST   /                              → create_space
│   │   ├── GET    /                              → list_spaces
│   │   ├── GET    /{space_id}                    → get_space
│   │   ├── PUT    /{space_id}                    → update_space_metadata (If-Match)
│   │   ├── DELETE /{space_id}                    → delete_space (dry_run)
│   │   ├── ... (rules/definitions, rules/logics, versions, metrics, instances, execute, schema)
│   │   └── GET    /{space_id}/etag               → get_space_etag
│   │
│   └── management_router (prefix="/v1") [deprecated]
│       ├── POST   /spaces                        → create_space [DEAD ROUTE]
│       ├── GET    /spaces                        → list_spaces [DEAD ROUTE]
│       ├── GET    /spaces/{space_id}             → get_space [DEAD ROUTE]
│       ├── PUT    /spaces/{space_id}             → update_space [DEAD ROUTE]
│       ├── DELETE /spaces/{space_id}             → delete_space [DEAD ROUTE]
│       ├── POST   /spaces/{space_id}/activate    → activate_space [UNIQUE]
│       ├── POST   /spaces/{space_id}/deactivate  → deactivate_space [UNIQUE]
│       ├── POST   /spaces/{space_id}/archive     → archive_space [UNIQUE]
│       ├── POST   /spaces/load-from-json         → load_space_from_json [UNIQUE]
│       ├── ... (schema L1-L4 CRUD, instances CRUD, versions) [MIXED]
│       ├── PATCH  /spaces/{id}/instances/entities/{eid}    → update_entity [UNIQUE]
│       ├── DELETE /spaces/{id}/instances/entities/{eid}    → delete_entity [UNIQUE]
│       ├── PATCH  /spaces/{id}/instances/relations/{rid}   → update_relation [UNIQUE]
│       └── DELETE /spaces/{id}/instances/relations/{rid}   → delete_relation [UNIQUE]
│
├── [2] schema_router (prefix="/v1/schema") [deprecated by middleware]
│   └── POST /load, GET /, POST /reload, GET /versions, POST /rollback/{v}
│
├── [3] instances_router (tags=["Instances"])
│   ├── entities_router (prefix="/v1/entities") [deprecated]
│   ├── relations_router (prefix="/v1/relations") [deprecated]
│   ├── datasets_router (prefix="/v1/datasets") [deprecated]
│   ├── incremental_router (prefix="/v1/incremental") [deprecated]
│   └── ingestion_router (prefix="/v1/ingestion") [deprecated]
│
├── [4] rules_router (prefix="/v1", tags=["Rules"])
│   ├── categories_router (prefix="/v1/categories") → 实际路径 /v1/v1/categories [BUG]
│   ├── actions_router (prefix="/v1/spaces/{sid}/actions") → 实际路径 /v1/v1/spaces/... [BUG]
│   └── ... (rule-groups, operators, dag, rules/execute)
│
├── [5] query_router (prefix="/v1/query")
│   └── 11 endpoints (含 deprecated /vector)
│
├── [6] views_router (tags=["Views"])
│   ├── consumption_router (prefix="/v1") [deprecated]
│   ├── visualization_router (prefix="/v1/visualize") [deprecated]
│   └── analysis_router (prefix="/v1/analysis") [deprecated]
│
├── [7] ontology_router (prefix="/v1/spaces/{space_id}/ontology") [experimental]
│
├── [8] memory_router (prefix="/v1/spaces/{space_id}/memory")
│
└── [9] simulation_router (prefix="/v1/simulation")
```

---

## 4. 前端调用与后端路由对照表

### 4.1 前端活跃使用的路由

| 前端文件 | 路由前缀 | 端点数 | 后端路由文件 | 状态 |
|----------|---------|-------|------------|------|
| spaceApi.ts | `/v1/spaces` | 30+ | semantic_spaces + management | 活跃 |
| ruleGroups.ts | `/v1/rule-groups` | 15 | rules.py | 活跃 |
| ruleSteps.ts | `/v1/rule-groups/{name}/steps` | 6 | rules.py | 活跃 |
| memoryApi.ts | `/v1/spaces/{id}/memory` | 17 | memory.py | 活跃 |
| simulation.ts | `/v1/simulation` | 4 | simulation.py | 活跃 |
| operators.ts | `/v1/operators` | 2 | rules.py | 活跃 |

### 4.2 前端使用的旧路由

| 前端文件 | 旧路由 | 替代路由 | 迁移难度 |
|----------|-------|---------|---------|
| ruleGroups.ts L385 | `/v1/management/schemas/{id}/load-from-yaml` | `/v1/spaces/{id}/schema/load-yaml` | 低 |
| memoryApi.ts L227 | `/v1/memory/reflect_status` | `/v1/spaces/{id}/memory/reflect-status`（需后端新增） | 中 |
| ConsumptionViewPage.tsx L53 | 原生 fetch `/v1/views/{id}` | `spaceApi.getView()` | 低 |
| ConsumptionViewListPage.tsx L26 | 原生 fetch `/v1/views` | `spaceApi.listViews()` | 低 |

### 4.3 Examples 使用的旧路由

| Example 文件 | 旧路由 | 替代路由 | 迁移难度 |
|-------------|-------|---------|---------|
| demo_verify_space.py | `/v1/management/spaces/load-from-json` | `/v1/spaces` POST + load-yaml | 中 |
| demo_verify_space.py | `/v1/management/spaces/{id}/activate` | `/v1/spaces/{id}/activate` | 低 |
| demo_verify_space.py | `/v1/consumption/views/{id}/entities` | `/v1/views/{id}/entities` | 低 |
| demo_verify_space.py | `/v1/consumption/views/{id}/rules/dependency-graph` | `/v1/views/{id}/rules/dependency-graph` | 低 |
| demo_verify_space.py | `/v1/consumption/views/{id}/execute/analyze` | `/v1/views/{id}/execute/analyze` | 低 |
| demo_verify_space.py | `/v1/consumption/views/{id}/execute/simulate` | `/v1/views/{id}/execute/simulate` | 低 |
| demo_verify_space.py | `/v1/consumption/views/{id}/rules/for-entity/{eid}` | `/v1/views/{id}/rules/for-entity/{eid}` | 低 |
| demo_verify_space.py | `/v1/consumption/views/{id}/visualize/schema-graph` | `/v1/views/{id}/schema-graph` | 低 |

---

## 5. 优化计划

### Phase 1: 紧急修复（影响运行时正确性）

| # | 任务 | 关联问题 | 前置条件 | 影响范围 |
|---|------|---------|---------|---------|
| 1.1 | 修复 categories/actions 双前缀 Bug | P0-1 | 无 | rules.py, categories.py, actions.py |
| 1.2 | 修复前端 memoryApi getReflectStatus 路径 | P0-2 | 后端需新增 reflect-status 端点 | memoryApi.ts, memory.py |
| 1.3 | 后端新增 `GET /v1/spaces/{space_id}/memory/reflect-status` | P0-2 | 无 | memory.py, MemoryService |

### Phase 2: 路由去重与废弃管理（设计-实现对齐）

| # | 任务 | 关联问题 | 前置条件 | 影响范围 |
|---|------|---------|---------|---------|
| 2.1 | 将 management 独有路由迁移到 semantic_spaces | P1-3 | 1.1 | spaces.py, semantic_spaces.py, management.py |
| 2.2 | 删除 management.py 中的重复路由 | P1-3 | 2.1 | management.py |
| 2.3 | 切换 DeprecationMiddleware 到 redirect 模式 | P2-1 | 2.1, 前端迁移完成 | server.py, middleware.py |
| 2.4 | 前端迁移旧路由（4 处） | P2-1 | 无 | ruleGroups.ts, memoryApi.ts, ConsumptionViewPage.tsx, ConsumptionViewListPage.tsx |
| 2.5 | Examples 迁移旧路由（8 处） | P2-1 | 无 | demo_verify_space.py |
| 2.6 | 标记 Query 旧端点为 deprecated | P2-2 | 无 | query.py, middleware.py |
| 2.7 | 实现 `POST /v1/query/explain` | P2-2 | 无 | query.py, QueryService |

### Phase 3: 新 API 落地（功能扩展）

| # | 任务 | 关联问题 | 前置条件 | 影响范围 |
|---|------|---------|---------|---------|
| 3.1 | 实现 Actions API（5 个端点） | P1-1 | RFC 审批 | 新文件 actions_v2.py, 前端, MCP |
| 3.2 | 更新 Ontology API 定位文档 | P1-2 | 无 | ontology-routes.md |
| 3.3 | 删除/重定向旧 `/v1/schema` 路由 | P1-2 | 2.3 | schema.py, middleware.py |

### Phase 4: 质量提升（代码健壮性）

| # | 任务 | 关联问题 | 前置条件 | 影响范围 |
|---|------|---------|---------|---------|
| 4.1 | Space 状态机 API 层校验 | P3-1 | 无 | semantic_spaces.py |
| 4.2 | 统一 ETag 并发控制 | P3-2 | 2.1 | management.py → semantic_spaces.py |
| 4.3 | 请求模型 Pydantic 化 | P4-1 | 无 | actions.py, categories.py, memory.py, datasets.py |
| 4.4 | 修复 MCP oe_update_relation | P4-2 | 无 | mcp/tools/management.py |
| 4.5 | MCP oe_query 降级提示 | P4-3 | 无 | mcp/tools/query.py |
| 4.6 | 前端统一 API 客户端 | P4-4 | 无 | ConsumptionViewPage.tsx, ConsumptionViewListPage.tsx |

---

## 6. 风险评估

### 6.1 高风险变更

| 变更 | 风险 | 缓解措施 |
|------|------|---------|
| 切换 DeprecationMiddleware 到 redirect 模式 | 前端/examples 旧路由调用 301 后行为变化 | 先完成前端/examples 迁移，再切换模式 |
| 删除 management.py 重复路由 | management 独有路由可能遗漏迁移 | 逐端点验证，确保 semantic_spaces 覆盖所有独有路由 |
| 实现 Actions API | 新增统一执行入口可能改变现有行为 | 旧端点保留为 deprecated，新端点并行运行 |

### 6.2 低风险变更

| 变更 | 风险 | 缓解措施 |
|------|------|---------|
| 修复双前缀 Bug | categories/actions 端点路径变化 | 前端未使用这些端点，影响仅限测试 |
| 前端 memoryApi 路径修复 | 无 | 纯前端修改 |
| Space 状态机校验 | 非法操作被拒绝 | 前端需处理 409 Conflict |

---

## 7. 设计文档状态同步建议

| 文档 | 当前状态 | 建议更新 |
|------|---------|---------|
| `docs/02-design/api/spaces-routes.md` | 定义了完整 Spaces API | 补充 management 独有路由的归属说明 |
| `docs/02-design/api/views-routes.md` | 定义了 Views API | 标记缺失端点（rule-chain, execution trace）为 [待扩展] |
| `docs/02-design/api/actions-routes.md` | 定义了 Actions API | 标记 status 为 `not-implemented` |
| `docs/02-design/api/query-routes.md` | 定义了精简 Query API | 补充旧端点废弃时间线 |
| `docs/02-design/api/ontology-routes.md` | 定义了全局 Ontology | 标记 status 为 `deferred`，说明当前 Space-bound 实现的合理性 |
| `docs/02-design/api/compatibility-layer.md` | 定义了兼容策略 | 更新 DeprecationMiddleware 实际状态（header 模式），补充前端/examples 迁移进度 |
| `docs/02-design/api/error-codes.md` | 定义了错误码注册表 | 标记 [待核对代码] — 实际错误码使用与定义偏差较大 |

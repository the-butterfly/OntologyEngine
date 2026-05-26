# API 接口优化计划：GAP 修复 + 预存问题 + 前后端对齐

> **status**: draft
> **phase**: phase6-api-optimization
> **source_of_truth**: 本文档
> **last_verified**: 2026-05-23
> **verified_against**: `docs-dev/review-reports/api-interface-audit-2026-05-22.md`, `docs/02-design/api/`, `docs/ROADMAP.md`, `docs/TODO.md`
> **supersedes**: 无（与审查报告 Phase 1-4 计划互补，非替代）

---

## 一、总体改进方向与预期效果

### 1.1 核心目标

修复 API 层设计-实现 GAP、消除前端核心功能不可用问题、接入已有但未使用的安全机制（状态机/ETag），使 API 层达到"设计可追溯、前后端对齐、状态安全"的基线。

### 1.2 改进方向

| 方向 | 当前状态 | 目标状态 | 核心价值 |
|------|---------|---------|---------|
| **前端核心功能可用** | 2 个 P0 端点缺失（getEvidence/correctNode） | 前端调用的端点 100% 后端实现 | 用户可用性 |
| **状态安全** | 状态机已实现但未接入，任何状态可执行任何操作 | API 层强制执行状态转换约束 | 数据一致性 |
| **设计-实现对齐** | 4 个 P0 架构偏差 + 15 个设计端点未实现 | 架构决策落地，GAP 可追溯 | 可维护性 |
| **文档覆盖** | Memory/Simulation 19+ 端点无设计文档 | 所有活跃端点有设计规范 | 可审计性 |
| **兼容层完整** | DeprecationMiddleware 仅 11 条映射（设计要求 70+） | 关键废弃路由有重定向/Header | 迁移安全 |

### 1.3 预期效果

| 指标 | 当前 | 目标 |
|------|------|------|
| 前端调用后端缺失端点 | 4 个 | 0 个 |
| Space 状态机 API 层接入 | 0% | 100%（activate/deactivate/archive/delete） |
| 活跃路由设计文档覆盖 | ~60%（缺 memory/simulation） | 100% |
| DeprecationMiddleware 映射 | 11 条 | 30+ 条（覆盖关键废弃路由） |
| memory.py Pydantic 化 | 0/6 端点 | 6/6 端点 |
| MCP oe_update_relation | 不存在 | 完整四层实现 |
| mypy --strict | 0 新增错误 | 0 新增错误 |

---

## 二、实施阶段总览

```
Stage 0: 架构决策 ────────────────────────────────────── [前置条件，阻塞 Stage 5]
    ↓
Stage 1: 前端核心功能修复 ─────────────────────────────── [P0，可立即启动]
    ↓
Stage 2: 安全机制接入 ────────────────────────────────── [P1]
    ↓
Stage 3: 功能缺口补齐 ────────────────────────────────── [P2]
    ↓
Stage 4: 文档与兼容层 ────────────────────────────────── [P2]
    ↓
Stage 5: 架构对齐（依赖 Stage 0 决策）────────────────── [P1-P2，决策驱动]
```

**依赖关系**：
```
Stage 0 ──→ Stage 5（架构决策决定 Stage 5 方向）
Stage 1 ──→ Stage 2 ──→ Stage 3 ──→ Stage 4
                                    ↓
                              Stage 5（可并行）
```

**与审查报告 Phase 对齐**：
- Stage 0 = 审查报告 Phase 3 前置决策
- Stage 1 = 审查报告 Phase 1 补充（P0-2 遗留 + 新发现）
- Stage 2 = 审查报告 Phase 4.1 + 4.2
- Stage 3 = 审查报告 Phase 4.3 + 4.4 + 新发现
- Stage 4 = 审查报告 Phase 2 补充 + Phase 4.5
- Stage 5 = 审查报告 Phase 3

---

## 三、各阶段详细实施方案

### Stage 0: 架构决策

**目标**：对 3 个 P0 架构级 GAP 做出决策，确定后续实施方向
**对应 GAP**：GAP-01（Actions）、GAP-02（Ontology）、GAP-03（Views）
**前置条件**：无

#### 0-1: Actions 路由模型决策

| 维度 | 内容 |
|------|------|
| **问题** | 设计文档定义 `/v1/actions/{action_name}` 统一执行入口（含 explain），实现为 `/v1/spaces/{space_id}/actions/{operation_type}` 操作类型路由 |
| **选项 A** | 按设计文档重构：实现 action_name 寻址 + explain 能力，旧版标记 deprecated |
| **选项 B** | 更新设计文档：承认当前操作类型路由为 Phase 1 实现，explain 标注 `[待扩展]` |
| **建议** | **选项 B**——当前操作类型路由已满足 MCP 层需求（oe_execute_rule/oe_simulate），explain 可在 Phase 2 通过 Query API 补充。重构成本高且无即时收益 |
| **决策输出** | RFC-026（draft）或设计文档更新 |

#### 0-2: Ontology 全局层决策

| 维度 | 内容 |
|------|------|
| **问题** | 设计文档定义全局 `/v1/ontology`（蓝图/模板），实现为 Space 内 `/v1/spaces/{space_id}/ontology`（实例化） |
| **选项 A** | 实现全局 Ontology 层，支持跨 Space 共享 Schema |
| **选项 B** | 更新设计文档标注 `[待扩展]`，当前 Phase Schema 绑定 Space 是合理的 |
| **建议** | **选项 B**——当前无跨 Space 共享 Schema 的需求，且 `/v1/schema` 旧路由可通过 DeprecationMiddleware 重定向到 `/v1/spaces/default/schema` |
| **决策输出** | 更新 ontology-routes.md 添加 `[待扩展]` 标注 |

#### 0-3: View 消费面分离决策

| 维度 | 内容 |
|------|------|
| **问题** | 设计文档定义独立 `/v1/views/{view_id}` 消费面路由，实现将消费面端点挂在 Space 路由下 |
| **选项 A** | 实现 View 路由层，消费面端点迁移至 `/v1/views/{view_id}/*` |
| **选项 B** | 保持当前结构，Space activate 自动创建 View 但 API 入口不分离，更新设计文档 |
| **建议** | **选项 A（延后至 Phase 7）**——消费面/管理面分离是架构目标，但当前前端已适配 Space 路由下的消费端点，立即迁移破坏面大。建议在 Phase 7 代码实现阶段统一处理 |
| **决策输出** | 更新 views-routes.md 标注 `phase: 7`，当前以 Space 路由为准 |

**验收标准**：
- [ ] 3 个架构决策有明确结论（选 A 或 B）
- [ ] 决策结论记录到 `docs-dev/discuss/2026-05-23-api-architecture-decisions.md`
- [ ] 受影响的设计文档已更新标注

---

### Stage 1: 前端核心功能修复

**目标**：消除前端核心功能不可用的 P0 级问题
**对应问题**：前端审查 #1（getEvidence）、#2（correctNode）、#3（getReflectStatus 路径）、#6（memoryApi 双份）
**前置条件**：无，可立即启动

#### 1-1: 实现 GET /{node_id}/evidence 端点

| 维度 | 内容 |
|------|------|
| **问题** | 前端 `MemoryConsumePage` 调用 `GET /spaces/{spaceId}/memory/{nodeId}/evidence`，后端无此路由，每次调用 404 |
| **位置** | `ontology_engine/api/routes/memory.py`（新增路由） |
| **底层能力** | `MemoryAPI.expand_evidence()` 和 `QueryRouter.expand_evidence()` 已实现 |
| **修复** | 1. 在 memory.py 新增 `GET /{node_id}/evidence` 路由<br>2. 调用 `memory_service.get_evidence(space_id, node_id)`<br>3. 在 `MemoryService` 新增 `get_evidence()` 方法桥接 `MemoryAPI.expand_evidence()` |
| **验证** | `pytest tests/unit/api/test_memory_evidence.py -v` |

**验收标准**：
- [ ] `GET /v1/spaces/{space_id}/memory/{node_id}/evidence` 返回证据链数据
- [ ] 返回字段包含 `source_fragment_ids`、`proof_count`、`related_edges`（对齐 TODO "Agent Memory 证据链扩展"）
- [ ] 前端 `MemoryConsumePage` 证据链查看功能可用
- [ ] 单元测试覆盖正常/异常场景

**ADR 关联**：evidence 查询属于 recall 的扩展操作（查询证据链），不违反 ADR-011 D11-2 的 3 大认知操作模型。需在 memory-routes.md 中明确归属为 recall 的子操作。

#### 1-2: 实现 PATCH /{node_id}/correct 端点

| 维度 | 内容 |
|------|------|
| **问题** | 前端 `MemoryBuildPage` + `MemoryDetailDrawer` 调用 `PATCH /spaces/{spaceId}/memory/{nodeId}/correct`，后端无此路由 |
| **位置** | `ontology_engine/api/routes/memory.py`（新增路由） |
| **底层能力** | `MemoryAPI.correct_memory()` 已实现 |
| **修复** | 1. 在 memory.py 新增 `PATCH /{node_id}/correct` 路由<br>2. 调用 `memory_service.correct_node(space_id, node_id, corrected_text, reason)`<br>3. 在 `MemoryService` 新增 `correct_node()` 方法桥接 `MemoryAPI.correct_memory()` |
| **验证** | `pytest tests/unit/api/test_memory_correct.py -v` |

**验收标准**：
- [ ] `PATCH /v1/spaces/{space_id}/memory/{node_id}/correct` 返回纠正结果
- [ ] 前端 `MemoryBuildPage` 和 `MemoryDetailDrawer` 纠正功能可用
- [ ] 单元测试覆盖正常/异常场景

**ADR 关联**：correct 操作属于 reflect 的扩展操作（纠正记忆），不违反 ADR-011 D11-2 的 3 大认知操作模型。需在 memory-routes.md 中明确归属为 reflect 的子操作。

#### 1-3: 统一前端 memoryApi 文件

| 维度 | 内容 |
|------|------|
| **问题** | `api/memoryApi.ts` 与 `services/memoryApi.ts` 95% 代码重复，`getReflectStatus` 路径不一致 |
| **位置** | `ontology-engine-ui/src/services/memoryApi.ts`（删除）、`ontology-engine-ui/src/api/memoryApi.ts`（保留） |
| **修复** | 1. 删除 `services/memoryApi.ts`<br>2. 更新所有 import 路径指向 `api/memoryApi.ts`<br>3. 确认 `getReflectStatus` 使用正确路径 `spacePath(spaceId, '/reflect-status')` |
| **验证** | 前端构建无报错，ReflectCenterPage 状态轮询正常 |

**验收标准**：
- [ ] `services/memoryApi.ts` 已删除
- [ ] 所有页面 import 统一指向 `api/memoryApi.ts`
- [ ] `getReflectStatus` 路径为 `/spaces/{spaceId}/memory/reflect-status`
- [ ] 前端构建通过

---

### Stage 2: 安全机制接入

**目标**：接入已有但未使用的安全机制，消除数据一致性风险
**对应问题**：预存问题 #2（状态机）、#3（ETag）
**前置条件**：Stage 1 完成

#### 2-1: Space 状态机 API 层接入

| 维度 | 内容 |
|------|------|
| **问题** | `SemanticSpaceStateMachine` 已完整实现但未被 API 层调用，activate/deactivate/archive/delete 直接赋值，可在 ACTIVE 状态下直接删除 Space |
| **位置** | `ontology_engine/api/routes/semantic_spaces.py` L1782-1862、`ontology_engine/services/space_service.py` L186-218 |
| **修复** | 1. 在 `SpaceService.activate_space()` 中调用 `state_machine.transition(space, SpaceStatus.ACTIVE)`<br>2. 同理接入 deactivate/archive<br>3. 在 `delete_space()` 中增加状态校验（仅 DRAFT/ARCHIVED 可删除）<br>4. 捕获 `InvalidTransitionError` 返回 409 Conflict |
| **验证** | `pytest tests/unit/services/test_space_service_state.py -v` |

**验收标准**：
- [ ] activate/deactivate/archive 操作经过状态机校验
- [ ] 非法状态转换返回 409 Conflict + 清晰错误信息
- [ ] 仅 DRAFT/ARCHIVED 状态可删除 Space
- [ ] 状态机单元测试覆盖所有转换路径

#### 2-2: 删除/归档 management.py 死代码

| 维度 | 内容 |
|------|------|
| **问题** | management.py 未在 server.py 中注册，属于死代码，与 semantic_spaces.py 高度重复 |
| **位置** | `ontology_engine/api/routes/management.py` |
| **修复** | 1. 确认 management.py 中无独有逻辑未被 semantic_spaces.py 覆盖<br>2. 将 management.py 移动到 `docs-baseline/` 归档<br>3. 文件头添加 `[已过期入口]` 标注 |
| **验证** | `grep -r "management" ontology_engine/api/ --include="*.py" | grep -v "docs-baseline"` 无引用 |

**验收标准**：
- [ ] management.py 已归档到 docs-baseline/
- [ ] 无代码引用 management.py
- [ ] 所有测试通过

---

### Stage 3: 功能缺口补齐

**目标**：补齐 MCP 关键功能缺口和 API 类型安全
**对应问题**：预存问题 #4（oe_update_relation）、#5（Pydantic 化）、前端审查 #4/#5（deleteCategorization/deleteAnalyticalElement）
**前置条件**：Stage 2 完成

#### 3-1: MCP oe_update_relation 四层实现

| 维度 | 内容 |
|------|------|
| **问题** | MCP 工具 `oe_update_relation` 不存在（非占位实现，完全缺失），Agent 无法通过 MCP 修改关系属性 |
| **位置** | 四层：`storage/` → `services/` → `api/` → `mcp/` |
| **修复** | 1. `StorageBackend.update_relation()`：更新关系属性<br>2. `SpaceService.update_relation_in_space()`：业务逻辑<br>3. `PATCH /v1/spaces/{space_id}/instances/relations/{relation_id}`：REST API<br>4. `oe_update_relation`：MCP 工具（**MCP 层调用 MemoryAPI 路径，对齐 ADR-014 D14-3**） |
| **参考** | `docs/plans/2026-05-19-agent-memory-comprehensive-fix.md` L215-300 |
| **对应 RFC** | **RFC-029**（需新建，冻结 oe_update_relation 实现路径，解决 ADR-014 D14-3 与 SpaceService 路径的冲突） |
| **验证** | `pytest tests/unit/mcp/test_oe_update_relation.py -v` |

**验收标准**：
- [ ] `PATCH /v1/spaces/{space_id}/instances/relations/{relation_id}` 端点可用
- [ ] MCP `oe_update_relation` 工具注册并可调用
- [ ] MCP 层调用路径与 ADR-014 D14-3 对齐（Entity 操作走 SpaceService，CognitiveNode 操作走 MemoryAPI）
- [ ] 四层实现通过单元测试
- [ ] RFC-029 已冻结

#### 3-2: memory.py Pydantic 化

| 维度 | 内容 |
|------|------|
| **问题** | memory.py 6 个端点全部使用 `dict[str, Any]`，OpenAPI 文档无法生成请求体 Schema |
| **位置** | `ontology_engine/api/routes/memory.py` |
| **修复** | 1. 定义 `RememberRequest`、`RecallRequest`、`ReflectRequest`、`ApproveRequest`、`ConsolidateRequest`、`ForgetRequest` Pydantic 模型<br>2. 替换 `request: dict[str, Any]` 为对应 Pydantic 模型<br>3. 更新测试适配新模型 |
| **验证** | `pytest tests/unit/api/test_memory_endpoints.py -v` + OpenAPI 文档生成验证 |

**验收标准**：
- [ ] memory.py 所有端点使用 Pydantic 请求模型
- [ ] OpenAPI 文档正确生成请求体 Schema
- [ ] 单元测试通过

#### 3-3: 前端预留端点实现（低优先级）

| 维度 | 内容 |
|------|------|
| **问题** | 前端 `deleteCategorization`、`deleteAnalyticalElement` 后端未实现 |
| **位置** | `ontology_engine/api/routes/semantic_spaces.py`（新增 DELETE 路由） |
| **修复** | 1. 新增 `DELETE /{space_id}/schema/L2/categorizations/{categorization_id}`<br>2. 新增 `DELETE /{space_id}/schema/L3/analytical-elements/{element_id}` |
| **验证** | `pytest tests/unit/api/test_schema_delete.py -v` |

**验收标准**：
- [ ] L2/L3 DELETE 端点可用
- [ ] 前端 Schema 编辑页面删除功能可用

---

### Stage 4: 文档与兼容层

**目标**：补全设计文档、完善兼容层映射
**对应 GAP**：GAP-04（Memory 无设计文档）、GAP-10（19+ 端点无文档）、GAP-12（Middleware 映射不完整）
**前置条件**：Stage 3 完成

#### 4-1: 新增 memory-routes.md 设计文档

| 维度 | 内容 |
|------|------|
| **问题** | Memory API 15 个端点无设计文档，违反"边界外扩需审批"约束 |
| **位置** | `docs/02-design/api/memory-routes.md`（新增） |
| **修复** | 1. 按项目设计文档格式编写 memory-routes.md<br>2. 覆盖所有 15 个端点的请求/响应/错误码定义<br>3. 补充元数据：status=accepted, phase=6, source_of_truth=本文档 |
| **验证** | 文档评审通过 |

**验收标准**：
- [ ] `docs/02-design/api/memory-routes.md` 存在且覆盖所有端点
- [ ] 文档元数据完整

#### 4-2: 新增 simulation-routes.md 设计文档

| 维度 | 内容 |
|------|------|
| **问题** | Simulation API 4 个端点无设计文档 |
| **位置** | `docs/02-design/api/simulation-routes.md`（新增） |
| **修复** | 同 4-1 |
| **验证** | 文档评审通过 |

#### 4-3: 补全 DeprecationMiddleware 映射

| 维度 | 内容 |
|------|------|
| **问题** | DeprecationMiddleware 仅 11 条映射，设计文档 compatibility-layer.md 定义 70+ 条 |
| **位置** | `ontology_engine/api/middleware.py` |
| **修复** | 1. 补全关键废弃路由映射（/v1/rule-groups → /v1/spaces/{id}/schema/L4/rules 等）<br>2. 为 deprecated 端点添加 Deprecation + Sunset 响应头<br>3. Query 旧端点（pattern-match/traverse/path）添加重定向规则 |
| **验证** | `pytest tests/unit/api/test_middleware.py -v` |

**验收标准**：
- [ ] 关键废弃路由有 Deprecation Header
- [ ] Query 旧端点有重定向或 Header
- [ ] 映射条目数 ≥ 30

#### 4-4: 更新设计文档元数据

| 维度 | 内容 |
|------|------|
| **问题** | `docs/02-design/api/README.md` 标注 `[待核对代码]`，Route Groups 表缺少 memory/simulation |
| **位置** | `docs/02-design/api/README.md` |
| **修复** | 1. 更新 Route Groups 表补充 memory/simulation<br>2. 更新 `last_verified` 为 2026-05-23<br>3. 移除 `[待核对代码]` 标注 |

---

### Stage 5: 架构对齐（决策驱动）

**目标**：根据 Stage 0 决策结果，实施架构级调整
**对应 GAP**：GAP-01/02/03/05/07/08
**前置条件**：Stage 0 决策完成

> 本阶段具体实施方案取决于 Stage 0 的决策结论。以下为选项 A（按设计重构）的实施方案，若选择选项 B 则仅需更新设计文档。

#### 5-1: Actions API 重构（如决策选 A）

| 维度 | 内容 |
|------|------|
| **修复** | 1. 新增 `actions_v2.py`，实现 `/v1/actions` GET + `/v1/actions/{action_name}/execute` POST + `/v1/actions/{action_name}/simulate` POST + `/v1/actions/{action_name}/explain/{entity_id}` GET<br>2. 旧版 actions.py 标记 deprecated<br>3. 前端迁移到新路径 |
| **对应 RFC** | 需新建 RFC-026 |

#### 5-2: Ontology 全局层（如决策选 A）

| 维度 | 内容 |
|------|------|
| **修复** | 1. 实现 `/v1/ontology` GET + POST /load + GET /versions + POST /rollback<br>2. 旧 `/v1/schema` 路由 301 重定向到 `/v1/ontology`<br>3. Space 内 ontology 保持为实例化视图 |
| **对应 RFC** | 需新建 RFC-027 |

#### 5-3: View 消费面分离（如决策选 A）

| 维度 | 内容 |
|------|------|
| **修复** | 1. 实现 `/v1/views/{view_id}` 路由层<br>2. 迁移消费面端点到 View 路由<br>3. 前端适配新路径 |
| **对应 RFC** | 需新建 RFC-028 |

---

## 四、跨阶段一致性检查

### 4.1 与审查报告 Phase 对齐验证

| 审查报告 Phase | 本计划 Stage | 对齐状态 |
|---------------|-------------|---------|
| Phase 1.1 双前缀 Bug | 已完成（P0-1） | ✅ |
| Phase 1.2 getReflectStatus 路径 | Stage 1-3 | ✅ |
| Phase 1.3 reflect-status 端点 | 已完成（P0-2） | ✅ |
| Phase 2.1 management 路由迁移 | 已完成（P1-3） | ✅ |
| Phase 2.2 删除重复路由 | Stage 2-2 | ✅ |
| Phase 2.3 redirect 模式 | Stage 4-3 | ✅ |
| Phase 2.4-2.5 前端/Examples 迁移 | Stage 1-3 + 4-3 | ✅ |
| Phase 2.6 Query deprecated | 已完成（P2-2） | ✅ |
| Phase 2.7 POST /query/explain | Stage 3-4（见下） | 延后至 Phase 7 |
| Phase 3.1 Actions API | Stage 5-1 | 决策驱动 |
| Phase 3.2 Ontology 文档 | Stage 0-2 决策 | ✅ |
| Phase 3.3 schema 路由重定向 | Stage 4-3 | ✅ |
| Phase 4.1 状态机 | Stage 2-1 | ✅ |
| Phase 4.2 ETag 统一 | Stage 2-2（自然解决） | ✅（需验证 ETag 覆盖完整性） |
| Phase 4.3 Pydantic 化 | Stage 3-2 | ✅ |
| Phase 4.4 oe_update_relation | Stage 3-1 | ✅ |
| Phase 4.5 MCP oe_query 降级 | Stage 3-4（见下） | ✅ |
| Phase 4.6 前端统一 API 客户端 | Stage 1-4（见下） | ✅ |

**补充任务**（审查报告 Phase 对齐修正）：

#### 3-4: MCP oe_query 降级提示

| 维度 | 内容 |
|------|------|
| **问题** | 审查报告 P4-3：oe_query 响应缺少 `fallback_used` 字段，降级时无提示 |
| **位置** | `ontology_engine/mcp/tools/query.py` |
| **修复** | 在 oe_query 响应中添加 `fallback_used: true/false` 字段 |
| **验证** | `pytest tests/unit/mcp/test_oe_query.py -v` |

#### 1-4: 前端绕过 apiClient 修复

| 维度 | 内容 |
|------|------|
| **问题** | 审查报告 P4-4：ConsumptionViewPage.tsx 和 ConsumptionViewListPage.tsx 使用原生 fetch 绕过 apiClient |
| **位置** | `ontology-engine-ui/src/pages/` |
| **修复** | 将原生 fetch 调用替换为 apiClient 调用 |
| **验证** | 前端构建通过，无原生 fetch 残留 |

### 4.2 与 ROADMAP 一致性

| ROADMAP 阶段 | 本计划关联 |
|-------------|-----------|
| Phase 6 一致性修复（S-1~S-5） | **有交叉但不直接覆盖**——Stage 1-4 解决 API 层 GAP，S-1~S-5 属于存储/Schema/查询层一致性，需独立修复计划 |
| Phase 6b Agent 记忆修复（GAP-11~18） | Stage 1-1/1-2/3-1/3-2 **部分贡献**——覆盖证据链和纠正能力，不覆盖治理层设计（DeduplicationGate/ArbitrationEngine/PermissionService） |
| Phase 7 代码实现 | Stage 5 为 Phase 7 的 API 层准备 |

### 4.3 与 TODO.md 覆盖

| TODO 事项 | 本计划覆盖 |
|----------|-----------|
| P0 S-1~S-5 跨模块一致性 | 不直接覆盖（独立修复计划） |
| P1 Agent 记忆治理层设计 | Stage 1-1/1-2 **部分贡献**（端点实现，不含治理层设计） |
| P2 Agent Memory 证据链扩展 | Stage 1-1 直接覆盖（含 source_fragment_ids/proof_count/related_edges 字段） |
| P2 按 API 设计重构路由 | Stage 5 覆盖 |

### 4.4 质量门禁

```bash
mypy ontology_engine/ --strict
ruff check ontology_engine/
pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing
```

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 架构决策延迟阻塞 Stage 5 | Stage 5 无法启动 | Stage 0 设定决策截止日期；Stage 1-4 不依赖决策 |
| 状态机接入破坏现有流程 | activate/deactivate 可能因前置条件校验失败 | 先补充状态机单元测试，再接入 API 层；提供 force 参数降级 |
| memory.py Pydantic 化破坏前端 | 请求体格式变更导致前端 422 | Pydantic 模型与现有 dict 结构兼容；前端逐步适配 |
| oe_update_relation 四层实现链长 | 任何一层阻塞导致整体不可用 | 按层独立实现和测试，每层可独立验证 |
| DeprecationMiddleware 映射补全影响性能 | 每个请求都经过映射检查 | 映射检查为 O(1) 哈希查找，性能影响可忽略 |
| RFC-024 未冻结 | Stage 1-1 evidence 端点依赖 RFC-024 D3 的 `MemoryAPI.get_evidence()` 公共方法 | Stage 1-1 实施前需确认 RFC-024 D3 部分冻结，或先行冻结 D3 |
| ADR-014 D14-3 与 Stage 3-1 路径冲突 | MCP 层 oe_update_relation 调用路径不明确 | 新建 RFC-029 明确 Entity 操作走 SpaceService、CognitiveNode 操作走 MemoryAPI |

---

## 六、进度追踪

| Stage | 任务 | 状态 | 完成日期 |
|-------|------|------|---------|
| 0-1 | Actions 路由模型决策 | ⬜ | |
| 0-2 | Ontology 全局层决策 | ⬜ | |
| 0-3 | View 消费面分离决策 | ⬜ | |
| 1-1 | GET /{node_id}/evidence 端点 | ⬜ | |
| 1-2 | PATCH /{node_id}/correct 端点 | ⬜ | |
| 1-3 | 统一前端 memoryApi 文件 | ⬜ | |
| 1-4 | 前端绕过 apiClient 修复 | ⬜ | |
| 2-1 | Space 状态机 API 层接入 | ⬜ | |
| 2-2 | 删除/归档 management.py | ⬜ | |
| 3-1 | MCP oe_update_relation 四层实现 | ⬜ | |
| 3-2 | memory.py Pydantic 化 | ⬜ | |
| 3-3 | 前端预留端点实现 | ⬜ | |
| 3-4 | MCP oe_query 降级提示 | ⬜ | |
| 4-1 | memory-routes.md 设计文档 | ⬜ | |
| 4-2 | simulation-routes.md 设计文档 | ⬜ | |
| 4-3 | DeprecationMiddleware 映射补全 | ⬜ | |
| 4-4 | 设计文档元数据更新 | ⬜ | |
| 5-1 | Actions API 重构 | ⬜（决策驱动） | |
| 5-2 | Ontology 全局层 | ⬜（决策驱动） | |
| 5-3 | View 消费面分离 | ⬜（决策驱动） | |

---

## 七、前置文档索引

| 文档 | 作用 |
|------|------|
| [api-interface-audit-2026-05-22.md](../docs-dev/review-reports/api-interface-audit-2026-05-22.md) | 审查报告原始问题清单 |
| [compatibility-layer.md](../docs/02-design/api/compatibility-layer.md) | 兼容层设计（70+ 条映射定义） |
| [spaces-routes.md](../docs/02-design/api/spaces-routes.md) | Space 路由设计 |
| [actions-routes.md](../docs/02-design/api/actions-routes.md) | Actions 路由设计 |
| [ontology-routes.md](../docs/02-design/api/ontology-routes.md) | Ontology 路由设计 |
| [views-routes.md](../docs/02-design/api/views-routes.md) | Views 路由设计 |
| [RFC-024](../docs-dev/03-rfc/RFC-024-cognitive-node-model-bugfix.md) | CognitiveNode 模型修复（含 get_evidence 接口） |
| [ADR-014](../docs/04-adr/ADR-014-entity-cognitive-node-separation.md) | Entity/CognitiveNode 分离（含 oe_update_relation 记录） |
| [comprehensive-fix plan](./2026-05-19-agent-memory-comprehensive-fix.md) | Agent Memory 全面修复计划（含 oe_update_relation 四层设计） |
| [ROADMAP.md](../docs/ROADMAP.md) | 项目路线图 |
| [TODO.md](../docs/TODO.md) | 当前任务列表 |

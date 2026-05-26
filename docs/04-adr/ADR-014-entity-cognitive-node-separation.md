# ADR-014: Entity 与 CognitiveNode 操作分离

| 元数据 | 值 |
|--------|-----|
| 状态 | implemented |
| 日期 | 2026-05-20 |
| 决策者 | architecture-review |
| 待审视 | 是 — 后续审视 EntityInstance CRUD 是否需要独立 service 层 |

## 上下文

系统中存在两套数据模型和存储路径：
- **EntityInstance / RelationInstance**：Schema 层实体，存储在 SQLite `entities`/`relations` 表
- **CognitiveNode / CognitiveEdge**：认知层节点，存储在 KuzuDB + SQLite `cognitive_nodes` 表

上一轮实施中，`EntityService` 新增了 `update_entity`/`delete_entity`/`update_relation`/`delete_relation` 4 个透传方法，但这些方法：
1. 零调用方（MCP 层改调 MemoryAPI，API 层改调 SpaceService）
2. 零业务逻辑（直接透传 storage 层）
3. 绕过 engine 层的认知模型逻辑（belief transition、FTS 同步、审计轨迹）

## 决策

### D14-1: Entity 与 CognitiveNode 操作分离

- **EntityInstance CRUD**：由 `SpaceService` 负责（操作 Space JSON 内存对象），API 层调用 SpaceService
- **CognitiveNode CRUD**：由 `MemoryAPI` 负责（操作认知节点），MCP 层调用 MemoryAPI
- 两者是**不同的数据域**，不应共享 service 层

### D14-2: 删除 EntityService 4 个透传方法

`EntityService.update_entity`、`delete_entity`、`update_relation`、`delete_relation` 已删除。影响分析确认：零调用方、零测试、零 examples 引用。

### D14-3: MCP 层改调 MemoryAPI

`oe_update_entity` → `MemoryAPI.correct_memory`
`oe_delete_entity` → `MemoryAPI.delete_memory`（cascade 参数不再死代码）
`oe_update_relation` → `MemoryAPI.get_node`（当前为占位实现）
`oe_delete_relation` → `MemoryAPI.delete_memory`

### D14-4: API 层委托 SpaceService

API 层的 PATCH/DELETE 端点不再直接操作 `space.instances` 内存字典，改为调用 `SpaceService.update_entity_in_space` 等方法。

## 待审视项

1. **EntityInstance 是否需要独立的 CRUD service**：当前 EntityInstance 的 update/delete 通过 SpaceService 操作 Space JSON，但 Space JSON 与 SQLite `entities` 表是两套数据源，可能不一致。后续需要审视是否需要统一的 EntityInstance CRUD 路径。

2. **oe_update_relation 的实际更新能力**：当前 `oe_update_relation` 只检查 relation 是否存在，未实际执行属性更新。后续需要实现 CognitiveEdge 的属性更新接口。

3. **Space JSON 与 SQLite 数据一致性**：API 层操作 Space JSON，MCP 层操作认知节点，两者可能对同一实体产生冲突。后续需要设计数据一致性策略。

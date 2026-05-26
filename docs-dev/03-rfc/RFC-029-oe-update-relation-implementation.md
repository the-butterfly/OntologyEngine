# RFC-029: oe_update_relation 实现路径

> **状态**: accepted
> **父 RFC**: [RFC-013](./RFC-013-mcp-tool-implementation.md)
> **前置 RFC**: [RFC-024](./RFC-024-cognitive-node-model-bugfix.md)（D3 MemoryAPI 公共方法收口）
> **创建日期**: 2026-05-23
> **最后更新**: 2026-05-23
> **实施进度**: Phase A ⬜ Phase B ⬜ Phase C ⬜ Phase D ⬜
> **作者**: Agent
> **评审截止**: 2026-05-24
> **关联文档**: [ADR-014](../../docs/04-adr/ADR-014-entity-cognitive-node-separation.md) · [ADR-011](../../docs/04-adr/ADR-011-agent-memory-architecture-decisions.md) · [优化计划](../../docs/plans/2026-05-23-api-optimization-plan.md)

---

## 摘要

明确 `oe_update_relation` MCP 工具的四层实现路径，解决 ADR-014 D14-3 中"占位实现"问题。核心决策：Entity 操作走 SpaceService，CognitiveNode 操作走 MemoryAPI，MCP 层按操作对象类型分发。

---

## 设计决策（2026-05-23）

| # | 决策 | 选择 | 理由 |
|---|------|------|------|
| D1 | MCP 层调用路径 | 按操作对象类型分发 | ADR-014 D14-1 核心决策：Entity 与 CognitiveNode 操作分离 |
| D2 | REST API 层路径 | `PATCH /v1/spaces/{space_id}/instances/relations/{relation_id}` | 与现有 Entity/Relation 实例端点一致 |
| D3 | 在 3 大认知操作中的定位 | 管理面工具，独立于 remember/recall/reflect | 关系属性更新不属于认知操作，属于知识库管理 |

---

## 一、现状与痛点

### 1.1 当前状态

| 层级 | 状态 | 说明 |
|------|------|------|
| Storage | `StorageBackend.update_relation()` 不存在 | 无法更新关系属性 |
| Service | `SpaceService.update_relation_in_space()` 不存在 | 无业务逻辑层 |
| API | `PATCH /instances/relations/{relation_id}` 不存在 | 无 REST 端点 |
| MCP | `oe_update_relation` 不存在 | ADR-014 D14-3 标注为"占位实现" |

### 1.2 核心问题

| 问题 | 表现 | 影响 |
|------|------|------|
| 占位实现 | ADR-014 D14-3 映射 `oe_update_relation → MemoryAPI.get_node` | 仅检查 relation 是否存在，不执行更新 |
| 路径冲突 | ADR-014 走 MemoryAPI，comprehensive-fix plan 走 SpaceService | Entity/CognitiveNode 操作未分离 |
| MCP 工具缺失 | RFC-013 工具列表不包含此工具 | Agent 无法通过 MCP 修改关系属性 |

---

## 二、目标模型定义

### 2.1 四层实现路径

```
StorageBackend.update_relation(space_id, relation_id, attributes)
    ↑
SpaceService.update_relation_in_space(space_id, relation_id, attributes)
    ↑
PATCH /v1/spaces/{space_id}/instances/relations/{relation_id}
    ↑
oe_update_relation MCP 工具
```

### 2.2 MCP 层分发逻辑

```python
async def oe_update_relation(space_id, relation_id, attributes):
    relation = await space_service.get_relation(space_id, relation_id)
    if relation.get("_cognitive_node_id"):
        result = await memory_api.correct_memory(
            node_id=relation["_cognitive_node_id"],
            corrected_text=attributes.get("text", ""),
            reason=attributes.get("reason", "MCP update"),
        )
    else:
        result = await space_service.update_relation_in_space(
            space_id, relation_id, attributes
        )
    return result
```

### 2.3 请求/响应模型

**REST API 请求**：
```python
class UpdateRelationRequest(BaseModel):
    attributes: dict[str, Any]
    reason: str = ""
```

**REST API 响应**：
```python
{
    "success": True,
    "data": {
        "relation_id": "...",
        "updated_attributes": {...},
        "cognitive_node_updated": True | False
    }
}
```

**MCP 工具参数**：
```python
{
    "space_id": "string",
    "relation_id": "string",
    "attributes": {"key": "value"},
    "reason": "string (optional)"
}
```

---

## 三、与现有模型映射

| 旧模型/占位 | 新模型 | 迁移动作 |
|-------------|--------|---------|
| `oe_update_relation → MemoryAPI.get_node` | 按对象类型分发 | 实现 D1 分发逻辑 |
| 无 StorageBackend 方法 | `update_relation()` | 新增 |
| 无 SpaceService 方法 | `update_relation_in_space()` | 新增 |
| 无 REST API 端点 | `PATCH /instances/relations/{id}` | 新增 |
| 无 MCP 工具 | `oe_update_relation` | 新增 |

---

## 四、迁移策略

### 4.1 阶段划分

| 阶段 | 内容 | 验证标准 |
|------|------|----------|
| Phase A | `StorageBackend.update_relation()` | 单元测试通过 |
| Phase B | `SpaceService.update_relation_in_space()` + REST API 端点 | API 集成测试通过 |
| Phase C | MCP `oe_update_relation` 工具 | MCP 工具测试通过 |
| Phase D | ADR-014 D14-3 更新（占位→已实现） | ADR 状态更新 |

### 4.2 向后兼容

- 新增端点，不修改现有端点
- ADR-014 D14-3 映射从 `MemoryAPI.get_node` 更新为分发逻辑
- 不影响现有 `oe_update_entity`（走 MemoryAPI.correct_memory 路径不变）

---

## 五、与 ADR 的对齐

| ADR | 决策 | 本 RFC 对齐方式 |
|-----|------|----------------|
| ADR-014 D14-1 | Entity 与 CognitiveNode 操作分离 | MCP 层按对象类型分发 |
| ADR-014 D14-3 | `oe_update_relation → MemoryAPI.get_node` | 更新为分发逻辑 |
| ADR-011 D11-2 | 3 大认知操作 | `oe_update_relation` 定位为管理面工具，独立于 3 大操作 |

---

## 六、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| CognitiveNode 关联判断不准确 | 分发到错误路径 | 通过 `_cognitive_node_id` 字段明确判断 |
| StorageBackend.update_relation 实现复杂 | 需要双写（Graph+Meta） | 复用现有 dual_write_compensation 机制 |
| RFC-024 D3 未冻结 | MemoryAPI 公共方法可能变更 | Phase C 依赖 RFC-024 D3 冻结 |

---

## 七、验收标准

1. `PATCH /v1/spaces/{space_id}/instances/relations/{relation_id}` 端点可用
2. MCP `oe_update_relation` 工具注册并可调用
3. Entity 操作走 SpaceService，CognitiveNode 操作走 MemoryAPI
4. ADR-014 D14-3 映射已更新
5. mypy --strict + ruff check 无新增错误

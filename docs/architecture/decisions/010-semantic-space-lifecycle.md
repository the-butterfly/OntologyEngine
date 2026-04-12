# ADR-010: Semantic Space Lifecycle and State Machine

**Status**: accepted

**Date**: 2026-04-12

**Deciders**: Ontology Engine 技术团队

---

## Context

语义空间 (Semantic Space) 是 OntologyEngine v2 架构的核心概念，作为知识资产的顶层容器。在 Phase 1 实施过程中，我们需要明确空间从创建到归档的完整生命周期管理，以及状态转换的规则和约束。

### 问题背景

1. **状态定义的模糊性**: 早期设计中，PUBLISHED 被讨论为"事件"还是"状态"存在分歧
2. **版本管理与状态的关系**: 需要明确状态转换如何触发版本快照
3. **回滚语义**: 需要定义从已发布版本回滚的具体行为

### 设计目标

- 清晰定义空间的四个状态：DRAFT、ACTIVE、PUBLISHED、ARCHIVED
- 明确状态转换的操作和约束条件
- 建立状态机与版本管理的关联
- 确保发布快照的不可变性和可追溯性

---

## Decision

### 核心决策

采用四级状态机模型管理语义空间生命周期，明确定义 PUBLISHED 为**快照状态**而非事件。

### 状态定义

| 状态 | 类型 | 说明 |
|------|------|------|
| **DRAFT** | 工作态 | 初始状态，可编辑，不可消费 |
| **ACTIVE** | 工作态 | 生效状态，可编辑（需解锁），可消费 |
| **PUBLISHED** | 快照态 | 不可变快照，可读取，作为回滚基准 |
| **ARCHIVED** | 终结态 | 已下线，保留历史，不可访问 |

### 状态转换规则

```
                    ┌──────────────────┐
                    │      DRAFT       │
                    └────────┬─────────┘
                             │ activate()
                             ▼
                    ┌──────────────────┐
         ┌─────────│     ACTIVE       │◄────────┐
         │         └────────┬─────────┘         │
         │                  │                   │
         │         publish()│                   │
         │                  ▼                   │
         │         ┌──────────────────┐        │
         │         │   PUBLISHED      │────────┘
         │         └──────────────────┘ activate()
         │                  │
         │ rollback()       │
         │                  │
    archive()               │
         │                  │
         ▼                  │
┌──────────────────┐        │
│    ARCHIVED      │◄───────┘
└──────────────────┘
```

| 当前状态 | 操作 | 目标状态 | 约束条件 |
|----------|------|----------|----------|
| DRAFT | activate() | ACTIVE | 至少包含 L1 定义 |
| ACTIVE | publish() | PUBLISHED | 创建不可变快照 |
| PUBLISHED | activate() | ACTIVE | 基于快照新建分支 |
| PUBLISHED | rollback() | ACTIVE | 恢复到快照状态 |
| ACTIVE | archive() | ARCHIVED | 确认无活跃连接 |

### 关键决策点 1: PUBLISHED 是状态而非事件

**决策**: PUBLISHED 定义为**快照状态** (Snapshot State)，而非转换事件。

**理由**:

1. **语义清晰性**: PUBLISHED 代表一个可独立存在的、不可变的版本快照，具有持续的存在期
2. **可追溯性**: 作为状态，PUBLISHED 可以被引用、查询和比较
3. **回滚能力**: 从 PUBLISHED 可以执行 `activate()` 或 `rollback()` 操作，这需要状态具有持久性
4. **并发控制**: PUBLISHED 快照可作为多个 ACTIVE 分支的共同基准

**对比分析**:

| 维度 | 作为事件 | 作为状态 (选定) |
|------|----------|-----------------|
| 存在期 | 瞬时 | 持久 |
| 可查询 | ❌ 仅日志 | ✅ 可独立访问 |
| 回滚基准 | 需额外存储 | 状态即快照 |
| 实现复杂度 | 低 | 中等 |
| 表达能力 | 弱 | 强 |

### 关键决策点 2: 双轨版本号体系

**决策**: 采用层版本（整数递增）+ 空间版本（语义化版本）的双轨制。

| 版本类型 | 格式 | 用途 |
|----------|------|------|
| 层版本 | 整数 (1, 2, 3...) | 层内变更追踪、精确回滚 |
| 空间版本 | SemVer (1.2.3) | 发布管理、兼容性声明 |

**理由**:

1. **层版本**满足技术层面的精确回滚需求
2. **空间版本**满足业务层面的发布管理和兼容性沟通
3. 两者通过发布操作建立映射关系

### 关键决策点 3: 状态与版本的关联

```
状态转换触发版本操作:

ACTIVE → PUBLISHED:
  - 触发: publish()
  - 操作: 
    1. 为各层创建快照
    2. 计算新的 SemVer
    3. 记录层版本 → 空间版本映射
  - 结果: PUBLISHED 状态关联一个完整的版本快照

PUBLISHED → ACTIVE (activate):
  - 触发: activate()
  - 操作:
    1. 基于快照创建新的工作分支
    2. 层版本号继续递增
    3. 空间版本等待下一次 publish 确定

PUBLISHED → ACTIVE (rollback):
  - 触发: rollback()
  - 操作:
    1. 恢复到快照时的层版本
    2. 丢弃当前 ACTIVE 的变更
    3. 创建回滚记录
```

---

## Consequences

### 正面影响

1. **清晰的语义模型**: 状态机明确区分了工作态和快照态
2. **可靠的版本管理**: 每个 PUBLISHED 都是可独立引用的不可变快照
3. **灵活的分支策略**: 可从任意 PUBLISHED 创建新的 ACTIVE 分支
4. **可追溯的历史**: 状态转换与版本快照形成完整追溯链

### 负面影响

1. **存储开销**: PUBLISHED 快照需要独立存储，增加存储成本
2. **实现复杂度**: 需要维护状态机、版本映射和快照存储三个子系统
3. **状态同步**: ACTIVE 和 PUBLISHED 可能同时存在，需要清晰的用户界面区分

### 缓解措施

| 问题 | 缓解策略 |
|------|----------|
| 存储开销 | PUBLISHED 快照采用压缩存储，定期归档旧版本 |
| 实现复杂度 | 版本管理模块独立封装，对外提供统一接口 |
| 状态同步 | UI 明确标注当前操作的是工作态还是快照态 |

---

## Implementation Notes

### 状态机实现要点

```python
class SemanticSpaceStateMachine:
    """
    状态机核心实现
    """
    states = ["DRAFT", "ACTIVE", "PUBLISHED", "ARCHIVED"]
    
    transitions = {
        "DRAFT": {"activate": "ACTIVE"},
        "ACTIVE": {
            "publish": "PUBLISHED",
            "archive": "ARCHIVED"
        },
        "PUBLISHED": {
            "activate": "ACTIVE",
            "rollback": "ACTIVE"
        },
        "ARCHIVED": {}  # 终态，无出口
    }
    
    async def transition(self, space_id: str, action: str) -> State:
        current = await self.get_state(space_id)
        if action not in self.transitions[current]:
            raise InvalidTransition(f"Cannot {action} from {current}")
        
        # 执行前置检查
        await self._validate_preconditions(space_id, current, action)
        
        # 执行状态转换
        new_state = self.transitions[current][action]
        await self._execute_transition(space_id, current, new_state, action)
        
        return new_state
```

### 版本快照实现要点

```python
class SpaceVersionSnapshot:
    """
    空间版本快照
    """
    space_id: str
    semver: str                    # 如 "1.2.3"
    layer_versions: Dict[str, int] # 各层版本映射
    snapshots: Dict[str, Any]      # 各层数据快照
    created_at: datetime
    immutable: bool = True
    
    async def activate(self) -> "SemanticSpace":
        """基于快照创建新的工作空间"""
        # 创建新的 ACTIVE 状态，继承快照数据
        pass
    
    async def rollback(self) -> "SemanticSpace":
        """回滚到快照状态"""
        # 恢复数据，切换到 ACTIVE
        pass
```

---

## Related

- [Schema v2 语义空间架构](../../05-schema-v2/00b-semantic-space-architecture.md)
- [Schema v2 版本管理](../../05-schema-v2/08-version-management.md)
- [ADR-009: API 架构演进策略](./009-api-architecture-evolution.md)

---

## Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-04-12 | 1.0 | 初始版本 | Ontology Engine Team |

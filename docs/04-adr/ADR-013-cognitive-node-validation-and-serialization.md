# ADR-013: CognitiveNode 模型治理与序列化统一

| 元数据 | 值 |
|--------|-----|
| 状态 | accepted |
| 日期 | 2026-05-20 |
| 决策者 | architecture-review |

## 上下文

CognitiveNode 有 35 个字段，序列化存在不对称：`from_dict` 使用 `__dataclass_fields__` 自动过滤，`to_dict` 手动枚举全部字段。新增字段时 `to_dict` 必须手动同步，否则丢失字段。`from_dict` 中的迁移逻辑（tags list→dict, model_domain→tags）混入模型定义。

## 决策

### D13-1: to_dict 改用 dataclasses.asdict

`CognitiveNode.to_dict()` 改用标准库 `dataclasses.asdict(self)` 替代手动枚举。新增字段时自动覆盖，无需手动同步。

### D13-2: 迁移函数独立到 storage/migrations.py

`from_dict` 中的迁移逻辑提取到 `storage/migrations.py`，通过 `apply_cognitive_node_migrations()` 统一调度。新增迁移时只需添加函数并注册到 `MIGRATE_COGNITIVE_NODE` 列表。

### D13-3: __post_init__ 强校验

CognitiveNode 添加 `__post_init__` 校验以下字段：
- `memory_type` ∈ VALID_MEMORY_TYPES
- `cognitive_layer` ∈ VALID_COGNITIVE_LAYERS
- `belief_status` ∈ VALID_BELIEF_STATUSES
- `visibility` ∈ VALID_VISIBILITIES
- `confidence` ∈ [0, 1.0]
- `feedback_weight` ∈ [0, 1.0]
- `strength` ∈ [0, 1.0]
- `version` >= 1
- `source_trust_tier` ∈ {high, normal, low} or None

**治理优先于容量**（ADR-011 D11-7）：非法数据在构造时即被拒绝，而非在运行时静默传播。

### D13-4: 校验同步规则

所有强控制的关键点（字段合法性校验）变更时，必须同步更新：
1. `storage/models.py` 的 `__post_init__` 和 `VALID_*` 常量
2. `docs/02-design/schema/01-schema-spec.md` 的字段定义
3. 本 ADR 的校验列表

## 影响

- 所有构造 CognitiveNode 的路径（包括 `from_dict`）都会触发校验
- 已有测试中如果使用了非法 memory_type/belief_status 等值，需要修正
- `dataclasses.asdict` 对嵌套 dataclass 会递归展开，但 CognitiveNode 无嵌套 dataclass，不受影响

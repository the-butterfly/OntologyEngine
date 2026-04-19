# ADR-008: Rule 模型统一

## Status

**accepted**

## Date

2026-04-12

## Context

当前文档中存在两套 Rule 模型并行，造成概念混淆和维护负担：

### 旧模型

结构为 `rule_group + applies_to + rules[]`，在 `05-complete-example.md` 等历史文档中仍有体现。

```yaml
# 旧模型示例（历史文档）
rule_groups:
  - name: credit_assessment
    applies_to: [entity.company]
    rules:
      - name: revenue_check
        condition: revenue > 1000000
        action: ...
```

### 新模型

结构为 `rule_definitions[] + rule_logics[]`，在 `09-canonical-schema-spec.md` 中被定义为 canonical 标准。

```yaml
# 新模型示例（canonical）
rule_definitions:
  - id: credit_assessment
    applies_to: [entity.company]
    priority: 100
    
rule_logics:
  - id: revenue_check
    rule_def_id: credit_assessment
    expression: revenue > 1000000
    output: ...
```

### 问题

1. **概念分裂**：两套模型并存，文档读者难以判断哪套是当前推荐标准
2. **实现复杂度**：引擎需要理解并支持两种内部表示
3. **迁移债务**：旧模型示例未清理，误导新用户

## Decision

### 核心决策

Canonical 模型采用 `rule_definitions + rule_logics` 双轨结构。

### 模型定义

#### `rule_definition`

承载规则的元数据和触发条件：

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识 |
| `metadata` | 名称、描述、版本等元信息 |
| `applies_to` | 适用实体类型列表 |
| `trigger` | 触发条件（可选） |
| `priority` | 执行优先级 |
| `enabled` | 是否启用 |

#### `rule_logic`

承载具体的计算逻辑：

| 字段 | 说明 |
|------|------|
| `id` | 唯一标识 |
| `rule_def_id` | 关联的 rule_definition |
| `expression` | 计算表达式或算子引用 |
| `inputs` | 输入参数定义 |
| `output` | 输出定义 |
| `depends_on` | 依赖的其他 rule_logic |

### 关键设计点

1. **Authoring Sugar**：旧 `rule_group` 可作为编写语法糖存在，在 SchemaLoader 加载阶段编译为 canonical model
2. **一对多关系**：一个 `rule_definition` 可关联多个 `rule_logic`，支持多分支或多步骤规则
3. **执行顺序**：`rule_logic` 之间通过 `depends_on` 建立执行顺序，引擎据此构建 DAG

### 模型关系

```
rule_definition (1) ────< (N) rule_logic
        │                       │
        │                       ├── depends_on ──> rule_logic
        │                       └── output ──────> context/entity
        │
        └── applies_to ──────> entity_type
```

## Migration Path

### Phase 1: 双模式支持（当前 → 1-2 sprints）

- SchemaLoader 支持读取旧 model，内部转换为新 model
- RuleEngine 统一使用新 model 执行
- 现有示例无需立即修改，保持向后兼容

### Phase 2: 统一迁移（2-4 sprints）

- 所有内部实现统一使用新 model
- 旧 model 标记为 deprecated，输出警告
- 提供迁移工具或详细迁移文档

### Phase 3: 清理（4+ sprints）

- 移除旧 model 支持代码
- 历史示例文档更新或归档
- 仅保留 canonical model

## Consequences

### 正面影响

- **概念清晰**：单一 canonical model，消除歧义
- **职责分离**：元数据与逻辑分离，便于独立演进
- **灵活性**：支持复杂规则编排（多步骤、条件分支）
- **可扩展性**：便于后续添加新逻辑类型（DSL、外部服务调用等）

### 负面影响

- **SchemaLoader 复杂度**：需要同时支持新旧两种格式的解析和转换
- **过渡期维护**：双模型并存期间需要维护兼容层代码
- **文档更新成本**：历史示例需要逐步更新或标注

### 实施任务

| 任务 | 优先级 | 状态 |
|------|--------|------|
| SchemaLoader 双格式支持 | P0 | [待实现] |
| 旧 model → 新 model 转换器 | P0 | [待实现] |
| 更新 `05-complete-example.md` 或标注过期 | P1 | [待实现] |
| 迁移工具/文档 | P1 | [待实现] |
| 移除旧 model 支持（Phase 3） | P2 | [待排期] |

## References

- Canonical Schema Spec: `docs/05-schema-v2/09-canonical-schema-spec.md`
- 历史示例: `docs/05-schema-v2/05-complete-example.md`
- 相关 ADR: ADR-003 (Schema Versioning)

## Notes

- 本决策是 Schema v2 规范的重要组成部分
- 未来如需引入新的 rule 表达形式（如可视化编排），应同样通过编译到 canonical model 的方式实现

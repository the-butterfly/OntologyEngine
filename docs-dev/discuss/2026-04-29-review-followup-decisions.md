# 2026-04-29 Review 后续处理决策记录

## 背景

继续 2026-04-28 全面代码审查的待处理项。原始审查发现 ~245 个 GAP，其中 5 项标记为"仍待后续处理"。

## 待处理项执行情况

### ✅ C-05: engine/categorization 层对齐

**问题**: `CategoryTags` 使用 `dict[str, str]` 代替 `list[CategoryTag]`，分类元数据（assigned_at/assigned_by/confidence）在引擎层完全丢失。

**执行**:
1. 重构 `CategoryTags` 内部存储从 `dict[str, str]` → `list[CategoryTag]`
2. `tags` 属性改为 `@property`，返回向后兼容的 dict 视图
3. `set()` 方法新增 `assigned_by`/`confidence` 关键字参数
4. 新增 `add_tag(tag: CategoryTag)`、`get_tag(dimension)`、`get_records()` 方法
5. `CategorizationEngine.categorize()` 改用 `save_category_tag(tag)` 替代 `save_category_tags(entity_id, tags_dict)`
6. `CategorizationEngine.get_tags()` 修复类型不匹配：`list[CategoryTag]` → `CategoryTags(entity_id, tags=stored)`

**验证**: 30 个测试全部通过，ruff/mypy 无新增错误

**改动文件**:
- `ontology_engine/engine/categorization/models.py` — 重写
- `ontology_engine/engine/categorization/engine.py` — 改用 save_category_tag + 修复 get_tags
- `ontology_engine/engine/categorization/__init__.py` — 导出 CategoryTag
- `tests/unit/engine/categorization/test_categorization.py` — 新增 12 个测试

### ✅ C-16b: 执行层覆盖逻辑统一

**问题**: overrides 执行逻辑存在 3 种不一致实现：
- `RuleChainSimulator._apply_overrides()` — 支持嵌套路径
- `DAGExecutor.execute()` — 简单 `dict.update()`，不支持嵌套
- `_run_full_analysis()` — 简单 `dict.update()`，不支持嵌套

**执行**:
1. 提取 `apply_overrides()` 到 `core/types/__init__.py` 共享模块
2. 支持嵌套路径（dot notation: `"registered_capital.value"`）
3. `DAGExecutor` 和 `consumption.py` 从 `dict.update()` 升级为 `apply_overrides()`
4. `simulator.py` 删除内联 `_apply_overrides` 方法，改用共享函数

**验证**: 9 个新测试通过，666 个单元测试通过（5 个预存失败无关）

**改动文件**:
- `ontology_engine/core/types/__init__.py` — 新增 `apply_overrides()`
- `ontology_engine/services/dag_executor.py` — 使用 `apply_overrides()`
- `ontology_engine/api/routes/consumption.py` — 使用 `apply_overrides()`
- `ontology_engine/visualization/simulator.py` — 删除 `_apply_overrides`，使用共享函数
- `tests/unit/core/types/test_apply_overrides.py` — 新增 9 个测试

### ✅ P0-3: 规则模型双分离 RFC

**问题**: `RuleDefinition` 一体模型与 L4 grammar `rule_definitions + rule_logics` 双分离结构不对齐。

**执行**: 编写 RFC-018，冻结以下设计：
- `RuleDefinitionDeclaration`（规则定义：对谁、输入什么、输出什么）
- `RuleLogicDeclaration`（规则逻辑：怎么算）
- 1:N 关联关系（definition_ref 反向引用）
- 5 阶段迁移策略（定义→适配器→Engine消费→统一→废弃）
- 三套模型统一映射表

**产出文件**: `docs-dev/03-rfc/RFC-018-rule-model-dual-separation.md`

### ✅ P1-1: Step.action 结构化 RFC

**问题**: Step.action 存在 4 种并行表示，无 ActionType 枚举，7 个硬编码 ACTION_* 常量。

**执行**: 编写 RFC-019，冻结以下设计：
- `ActionType` 枚举（5 种：set_flag/compute/reject/emit_alert/assign_category）
- `OperatorType` 枚举（6 种：GRAPH/BINNING/SWITCH/SCORECARD/WEIGHTED_SUM/FORMULA）
- 结构化 `ActionClause`（type + 类型专用字段 + 通用字段）
- `match action.type` 分发逻辑
- 7 个 ACTION_* 常量→ActionType 映射表
- 5 阶段迁移策略

**产出文件**: `docs-dev/03-rfc/RFC-019-step-action-structization.md`

### ⏸ Kuzu 异步化（Phase 2）

**问题**: Kuzu Python binding 非线程安全，`asyncio.to_thread` 导致 segfault。

**当前状态**: ADR-008 D3 已决策回退异步化，保持同步调用。

**Phase 2 三个可选方案**（来自 ADR-008 D3）：

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| A. 专用单线程 executor | 所有 Kuzu 操作路由到同一个线程 | 避免跨线程对象访问 | 吞吐量受限 |
| B. 连接池 + thread-local | 每个线程持有自己的 Kuzu Connection | 并发度可调 | 连接数受 Kuzu 限制 |
| C. 切换 Neo4j | 原生支持异步的图数据库 | 无线程安全问题 | 迁移成本高 |

**参考实现**: Cognee KuzuAdapter 使用 `ThreadPoolExecutor + run_in_executor + asyncio.Lock`，已验证可行。

**决策**: Phase 2 再实施，当前单用户场景下同步调用可接受。

---

## 仍待后续会话处理

| 项目 | 优先级 | 说明 | 状态 |
|------|--------|------|------|
| ~~P0-3 Phase D+E~~ | ~~中~~ | ~~RFC-018 Phase D+E：Semantic Space 统一 + 废弃旧模型~~ | ✅ 已完成（见下方 Phase D+E 记录） |
| ~~P1-1 Phase D+E~~ | ~~中~~ | ~~RFC-019 Phase D+E：删除 ACTION_* 常量 + 统一四套表示~~ | ✅ 已完成（见下方 Phase D+E 记录） |
| Kuzu 异步化 | Phase 2 | 专用线程池或切换数据库 | ⏸ 延期至 Phase 2，当前单用户场景可接受 |

---

## RFC-018 / RFC-019 实施记录 (Phase A-E)

### Batch 1: Phase A — 定义新模型 ✅

**RFC-018 Phase A**:
- `core/schema/models.py`: 新增 `ActionType`(5种)、`OperatorType`(6种) 枚举、`StepAction`、`StepCondition`、`AppliesToDecl`、`PreconditionDecl`、`IOElementDecl`、`ApplicabilityDecl`、`StepDeclaration`、`RuleDefinitionDeclaration`、`RuleLogicDeclaration`、`BusinessLogicV3` Pydantic 模型
- `engine/rule/models.py`: 新增 `StructuredActionClause`、`StepDecl`、`RuleDefinitionDecl`、`RuleLogicDecl` dataclass 运行时模型

**RFC-019 Phase A**:
- `ActionType` 枚举: SET_FLAG / COMPUTE / REJECT / EMIT_ALERT / ASSIGN_CATEGORY
- `OperatorType` 枚举: GRAPH / BINNING / SWITCH / SCORECARD / WEIGHTED_SUM / FORMULA
- `StructuredActionClause`: 包含 `type: ActionType` + 类型专用字段 + `from_legacy()` 转换

**验收**: 30 个 V3 模型测试通过

### Batch 2: Phase B — 适配器/转换函数 ✅

- `RuleDefinitionDeclaration.from_v2()`: RuleDefinitionV2 → RuleDefinitionDeclaration
- `RuleLogicDeclaration.from_legacy_logic()`: RuleLogic → RuleLogicDeclaration
- `BusinessLogicV3.from_business_logic()`: BusinessLogic → BusinessLogicV3
- `RuleDefinitionDecl.from_rule_group()`: RuleGroupDefinition → RuleDefinitionDecl
- `RuleLogicDecl.from_rule_steps()`: list[RuleStep] → RuleLogicDecl
- `_infer_action_type()`: 旧 action 字符串 → ActionType 推断

**验收**: 49 个适配器测试通过

### Batch 3: Phase C — Engine 层消费新模型 ✅

- `RuleExecutor.execute_v3()`: 消费 `RuleDefinitionDecl` + `RuleLogicDecl`，按优先级排序执行步骤
- `RuleExecutor._execute_structured_action()`: 使用 `match action.type` 分发 5 种 ActionType
- `RuleExecutor._evaluate_v3_condition()`: 支持 expression/all_of/any_of 条件评估

**验收**: 12 个 V3 执行测试通过，727 个回归测试通过

### Batch 4: Phase D — Semantic Space 统一消费 ✅

**RFC-018 Phase D**:
- `services/dag_executor.py`: 重写为适配器模式，从 SemanticSpace 加载 rule_definitions + rule_logics，构建 RuleStep 后委托 engine 层 DAGExecutor 执行
- `_build_then_action()`: 从 SemanticSpace rule_logics 加载 then_action，合并 operator 和 params
- `_build_else_action()`: 新增方法，从 SemanticSpace rule_logics 加载 else_action，补齐 else 分支执行支持
- `_convert_result()`: 将 engine 层 ExecutionResult 转换为 services 层格式

**RFC-019 Phase D**:
- `engine/rule/executor.py`: 删除 7 个 ACTION_* 常量（ACTION_APPROVE_ELIGIBILITY 等）
- `engine/rule/executor.py`: 删除 `_execute_legacy_action()` 方法
- `engine/rule/executor.py`: 删除 `_calculate_credit_score()` 和 `_get_credit_grade()` 方法（已迁移到 operator 实现）
- `engine/rule/executor.py`: `_execute_action()` 中 KeyError 改为 raise ValueError，不再静默回退

**验收**: 739 个单元测试通过，服务器启动正常

### Batch 5: Phase E — 废弃旧模型标记 + Bug 修复 ✅

**RFC-018 Phase E**:
- `engine/rule/models.py`: RuleGroupDefinition/ActionClause/ConditionClause/RuleStep 标记 deprecated + DeprecationWarning
- 旧模型保留但不再新增功能，所有新代码使用 V3 模型

**RFC-019 Phase E**:
- `engine/rule/operators/registry.py`: `get_operator_schema()` 新增大小写归一化（name.upper()），修复 OPERATOR_SCHEMAS 大写键名与 OperatorRegistry 小写注册名不匹配的问题
- `validate_operator_params()` 不再永远返回 'Unknown operator'

**本轮审查额外修复**:

| 问题 | 严重度 | 修复 |
|------|--------|------|
| 级联删除 SQL 表名错误 `metrics` → `computed_metrics` | 严重 | `store.py` 修正表名 |
| 级联删除 SQL 列名错误 `from_id` → `from_entity_id` | 严重 | `store.py` 修正列名 |
| 级联删除缺少 `rule_execution_log` 和 `feedback_records` 表 | 高 | `store.py` 补齐两张表 |
| `services/dag_executor.py` 缺少 else_action 支持 | 高 | 新增 `_build_else_action()` |
| 旧数据库 schema 迁移失败（CREATE TABLE IF NOT EXISTS 不修改已存在表） | 严重 | `store.py` 新增 `_migrate_schema_sync()` 自动补齐缺失列 |
| SQLite ALTER TABLE ADD COLUMN 不支持非常量默认值 | 严重 | 时间戳列先添加为可空再 UPDATE 回填 |

**验收**: 739 个单元测试通过，服务器启动无报错，`/health` 接口正常响应

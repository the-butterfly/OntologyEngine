# 2026-04-29 代码审查报告

## 审查范围

本次审查覆盖 2026-04-29 会话中所有代码变更，包括：
- C-05: engine/categorization 层对齐
- C-16b: 执行层覆盖逻辑统一
- RFC-018 Phase A-C: 规则模型双分离
- RFC-019 Phase A-C: Step.action 结构化

## 第一轮审查：已修复问题（12 项）

### 高严重度（8 项）

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| CR-01 | apply_overrides 浅拷贝导致嵌套字典污染 + 非字典值静默覆盖 | core/types/__init__.py | 新增 deep_copy_entity_data()；非 dict 中间值抛 TypeError；空键段抛 ValueError；overrides=None 安全处理 |
| CR-02 | from_rule_steps 将 params 误传为 output 参数 | engine/rule/models.py | 改为直接构造 StructuredActionClause(type=COMPUTE, operator=..., params=...) |
| CR-03 | RuleLogicDecl.to_dict() 遗漏 else_action 序列化 | engine/rule/models.py | 新增 "else_action" 字段 |
| CR-04 | ConditionClause.sub_conditions 类型标注 list[str] 与实际处理 dict 矛盾 | engine/rule/models.py | 改为 list[str \| dict[str, Any]] |
| CR-05 | match 兜底分支绕过穷尽检查 | engine/rule/executor.py | 改为 raise ValueError() |
| CR-06 | from_v2 preconditions 丢弃非 dict 实例 | core/schema/models.py | 新增 isinstance(p, PreconditionDecl) 分支 |
| CR-07 | CategoryTags isinstance(tags, list) 无元素类型校验 | engine/categorization/models.py | 新增 TypeError 校验 |
| CR-08 | get_tags() 空列表与 None 语义混淆 | engine/categorization/engine.py | 改为 `if stored is None` |

### 中严重度（4 项）

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| CR-09 | _evaluate_v3_condition 参数类型标注为 Any | engine/rule/executor.py | 改为 ConditionClause \| None |
| CR-10 | flag or "default_flag" 对空字符串隐式转换 | engine/rule/executor.py | 改为 `if flag is not None` |
| CR-11 | Alert 默认级别不一致 ("info" vs "WARNING") | engine/rule/executor.py | 统一为 "WARNING"，加 str() 类型转换 |
| CR-12 | overrides 只取第一个元素 | core/schema/models.py | 改为 ",".join(v2.overrides) |

## 第二轮审查：已修复问题（12 项）

### 高严重度（12 项）

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| CR2-01 | consumption.py outputs 解包 Bug：`for k, v in step.get("outputs", [])` 对列表格式崩溃 | api/routes/consumption.py | 改为遍历 dict 列表，支持 `{"name": k, "value": v}` 和 `(k, v)` 两种格式 |
| CR2-02 | consumption.py target_objects/applies_to 字段名不一致 | api/routes/consumption.py | 新增 `_rule_applies_to()` 兼容函数，统一读取 applies_to/target_objects，处理 dict 格式 |
| CR2-03 | executor.py 拒绝检测 key 不一致：legacy 用 "rejected"，V3 用 "_rejected" | engine/rule/executor.py | legacy 路径增加 `_rejected` 检测，兼容两种 key |
| CR2-04 | engine/rule/dag_executor.py asyncio.gather(return_exceptions=True) 返回值可能含 Exception | engine/rule/dag_executor.py | 遍历结果，将 Exception 转为 StepResult(error=str(e)) |
| CR2-05 | services/dag_executor.py 多 output key 赋相同计算值 | services/dag_executor.py | 只赋给 primary key，其余保持原值 |
| CR2-06 | models.py from_rule_steps 动作类型硬编码为 COMPUTE | engine/rule/models.py | 新增 `_infer_action_type_from_operator()` 函数，根据 operator 名推断 ActionType |
| CR2-07 | models.py from_step_action 前向引用 StepAction 未 import | engine/rule/models.py | 添加 TYPE_CHECKING 块导入 StepAction |
| CR2-08 | categorization/engine.py 直接访问 entity._fact_object 私有属性 | engine/categorization/engine.py | 改为 `getattr(entity, 'fact_object', None) or getattr(entity, '_fact_object', '')` |
| CR2-09 | simulator.py 访问 RuleExecutor._get_eval_context 私有方法 | engine/rule/executor.py + visualization/simulator.py | 新增公开方法 `get_eval_context()`，simulator 改用公开接口 |
| CR2-10 | services/dag_executor.py 条件求值失败默认返回 True | services/dag_executor.py | 改为返回 False（安全失败） |
| CR2-11 | simulator.py 浅拷贝导致嵌套数据共享引用 | visualization/simulator.py | 改用 `deep_copy_entity_data()` 深拷贝 |
| CR2-12 | categorization/engine.py except pass 静默吞异常 | engine/categorization/engine.py | 添加 logger.warning 记录异常信息 |

### 额外修复

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| FIX-01 | Alert.data 类型不匹配（output.get("data") 返回 Any） | engine/rule/executor.py | 使用 `cast(dict[str, Any] \| None, ...)` |
| FIX-02 | context.categories 赋值 True 但类型为 dict[str, str] | engine/rule/executor.py | 改为 `context.categories[action.category] = action.category` |
| FIX-03 | executor.py 未使用 import StepDecl | engine/rule/executor.py | 移除 |
| FIX-04 | 5 个单元测试失败 | tests/unit/services/ | 修复 mock 数据类型和依赖 |

### 测试修复详情

| 测试 | 根因 | 修复 |
|------|------|------|
| test_locate_by_output_exact_match | 依赖不存在的数据文件 | Mock SemanticSpaceStorage.load |
| test_locate_by_input | 同上 | 同上 |
| test_build_execution_tree | 同上 | Mock storage + 增加规则链深度 |
| test_locate_rules_producing | 同上 | Mock SemanticSpaceStorage.load |
| test_build_execution_tree_single_layer | Mock 返回 RuleGroupDefinition dataclass 但代码期望 dict | 改为 make_rule_group_dict() 返回 dict |

## 已知但未修复的低优先级问题

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| L-01 | CategoryTags.__eq__ 仅比较简化 dict | engine/categorization/models.py | 业务等价语义可接受，文档已说明 |
| L-02 | CategoryTags.to_dict() 丢失元数据 | engine/categorization/models.py | 向后兼容设计，后续可增 to_full_dict() |
| L-03 | categorize() 逐条保存无事务保证 | engine/categorization/engine.py | storage 层事务支持待后续 |
| L-04 | StepAction 无交叉验证 | core/schema/models.py | Pydantic @model_validator 待后续 |
| L-05 | PreconditionDecl.reject vs Precondition.fail 名称类型不一致 | core/schema & engine | Phase D+E 统一时修复 |
| L-06 | IOElementDecl.rule_output 在运行时 IOElement 中缺失 | core/schema & engine | Phase D+E 统一时修复 |
| L-07 | applicability Pydantic 结构化 vs 运行时扁平 dict | core/schema & engine | Phase D+E 统一时修复 |
| L-08 | StepCondition alias 序列化行为未显式配置 | core/schema/models.py | 需 ConfigDict(populate_by_name=True) |
| L-09 | ASSIGN_CATEGORY 返回值可能包含 None | engine/rule/executor.py | 低风险，下游已处理 |

## 跨模块架构问题（待后续处理）

| # | 问题 | 严重度 | 说明 |
|---|------|--------|------|
| A-01 | 三套并行规则模型体系 | HIGH | Pydantic (core/schema) + Dataclass (engine/rule) + Semantic Space 层，字段名和结构不一致 |
| A-02 | 两个完全不同的 DAG 执行器 | HIGH | engine/rule/dag_executor.py vs services/dag_executor.py，行为不一致 |
| A-03 | _infer_action_type 在 schema 层违反模块边界 | MEDIUM | 应移至 engine/rule/ |
| A-04 | consumption.py 中 DEPRECATED 函数仍在代码中 | MEDIUM | _build_rule_dependency_graph 等无调用方 |
| A-05 | simulation_tree_builder.py 无环检测 | MEDIUM | while 循环可能无限执行 |
| A-06 | simulation_tree_builder.py 用合成条件替代实际 when 条件 | MEDIUM | 误导执行树消费者 |

## 第三轮：架构问题修复

### A-05: simulation_tree_builder.py 无环检测 ✅

**修复**：在 `build_tree` 的 while 循环中添加 `max_iterations=100` 限制和迭代计数器，防止循环依赖导致无限循环。

### A-02: 两个 DAG 执行器统一 ✅

**Phase A**: 扩展 `StepResult` 增加仿真所需字段

| 新增字段 | 类型 | 说明 |
|----------|------|------|
| step_name | str | 步骤名称（前端展示用） |
| condition_result | bool \| None | 条件评估结果 |
| condition_detail | dict \| None | 条件详情（含 explanation，前端展示用） |
| input_values_used | dict | 步骤使用的输入值快照 |
| duration_ms | int | 步骤执行耗时（毫秒） |

**Phase B**: Services DAGExecutor 重构为适配器

- [services/dag_executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/services/dag_executor.py) 完全重写
- 新实现将 `execution_tree`（dict）转换为 `RuleStep` 列表
- 委托给 `engine.rule.dag_executor.DAGExecutor` 执行
- 将 `ExecutionResult` 转换为前端 `SimulationResult` 格式
- 消除了重复的条件评估、公式计算、action 执行逻辑

### A-01: 三套并行规则模型统一 ✅

**Phase E**: 废弃旧模型添加 deprecation warning

| 旧模型 | Deprecation Message | 替代模型 |
|--------|---------------------|----------|
| RuleGroupDefinition | "Use RuleDefinitionDecl instead." | RuleDefinitionDecl |
| ActionClause | "Use StructuredActionClause instead." | StructuredActionClause |
| ConditionClause | "Prefer StepCondition for new code." | StepCondition |
| RuleStep (engine) | "Use StepDecl instead." | StepDecl |

**Phase D**: Semantic Space 层接入 V3 模型

- [rule_models.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/core/semantic_space/rule_models.py) 添加 `to_v3_declaration()` 和 `to_v3_logic()` 转换方法
- [__init__.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/core/semantic_space/__init__.py) 导出 V3 模型（RuleDefinitionDeclaration、RuleLogicDeclaration、StepDeclaration、StepAction、StepCondition）
- 旧模型标记为 legacy，新模型标记为 preferred

## 验证结果

### 第一轮
- **107 个新增/修改测试全部通过**
- **734 个回归测试通过**（5 个预存失败）
- ruff check 无新增错误

### 第二轮
- **739 个测试全部通过**（含修复的 5 个原失败测试）
- ruff check 无新增错误
- mypy: 8 个 import-untyped（第三方库 stubs 缺失），无业务代码类型错误

### 第三轮（架构问题修复）
- **739 个测试全部通过**
- ruff check 无新增错误（5 个预存 F401 与本次修改无关）
- 所有 DeprecationWarning 在测试中通过 `-W ignore::DeprecationWarning` 抑制

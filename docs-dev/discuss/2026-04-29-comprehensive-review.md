# 2026-04-29 全面代码审查报告（第三轮）

## 审查范围

本轮审查覆盖：
1. 12 个核心模块代码质量
2. 11 个算子模块代码质量
3. 13 个 RFC 文档与代码一致性
4. 1 个 ADR 文档与代码一致性
5. 4 项讨论确认的修复

## 一、代码质量问题

### 核心模块（12 个文件，37 个问题）

| 严重度 | 数量 | 关键问题 |
|--------|------|----------|
| HIGH | 8 | pipeline_state 违反模块边界、partial_complete_run 缺少持久化、storage.save 非原子写入、state_machine 硬编码 Storage、compute_levels 修改原始 in_degree、YAML 解析缺少键校验、rule_service 并行保存无事务、simulation_service 变量提取正则不一致 |
| MEDIUM | 22 | evaluator 列表条件 str() 转换、dag_builder 忽略跨组 ID 冲突、pipeline_state 恢复丢失步骤快照、transaction commit 清除所有快照、logical_edges BFS 重复边、dependency_analyzer 环中节点 level=0、rule_service 启发式检测不可靠、storage 使用已弃用 datetime.utcnow()、storage async 方法执行同步 I/O、loader 吞掉原始异常类型 |
| LOW | 4 | 命名不一致、函数内导入、max_depth=0 语义不清 |

### 算子模块（11 个文件，24 个问题）

| 严重度 | 数量 | 关键问题 |
|--------|------|----------|
| HIGH | 4 | graph_traversal 重复注册、name 属性用类变量而非 @property、OPERATOR_SCHEMAS 大小写不一致导致验证失效、SwitchOperator value=None 时 TypeError |
| MEDIUM | 8 | _build_context 重复实现 10+ 次、ScorecardOperator 归一化空操作、OperatorRegistry 不检查重复注册、_check_type bool/int 判断不准确、WeightedSumOperator _build_context 不一致、DecisionTableOperator 不处理 None、GRAPH_TRAVERSAL 缺少 Schema、测试覆盖不足 |
| LOW | 12 | LLMJudgeOperator max_retries 负数、_call_llm 占位实现、alert.py 空壳占位、ApproveEligibilityOperator 语义矛盾、OperatorRegistry.get 每次创建新实例、ScorecardOperator 方法内 import |

## 二、RFC/ADR 一致性审计

### 一致性状态汇总

| RFC/ADR | 检查项数 | CONSISTENT | PARTIAL | INCONSISTENT | NOT_IMPLEMENTED |
|---------|---------|------------|---------|--------------|-----------------|
| RFC-011 | 4 | 2 | 2 | 0 | 0 |
| RFC-014 | 4 | 2 | 2 | 0 | 0 |
| RFC-017 | 3 | 2 | 0 | 0 | 1 |
| RFC-018 | 3 | 2 | 0 | 1 | 0 |
| RFC-019 | 4 | 3 | 0 | 1 | 0 |
| ADR-008 | 7 | 6 | 0 | 1 | 0 |

### 关键偏差

1. **RFC-011 RuleStep 模型与代码不一致**（已修复：标记 RFC-011 为部分过时，索引到 RFC-014）
2. **RFC-011 CircularDependencyError vs CycleError**（已修复：统一为 CycleError）
3. **RFC-014 LLM_JUDGE 降级策略不完整**（仅第1级实现，第2/3级未实现）
4. **RFC-017 往返一致性测试缺失**
5. **RFC-018/019 Phase D-E 未完成**（已修复：本轮完成）
6. **ADR-008 D6 delete_entity 级联删除未实现**（已修复：本轮实现）

## 三、讨论确认的修复

| # | 问题 | 决策 | 修复状态 |
|---|------|------|----------|
| D-01 | RFC-011 RuleStep 模型与代码矛盾 | 标记 RFC-011 为部分过时，索引到 RFC-014，统一使用 CycleError | ✅ |
| D-02 | RFC-018/019 Phase D-E | 本轮完成 | ✅ |
| D-03 | ADR-008 D6 级联删除 | 实现级联删除 | ✅ |
| D-04 | OPERATOR_SCHEMAS 大小写不一致 | 查询时归一化大小写 | ✅ |

### D-01: RFC-011 标记为部分过时
- 在 RFC-011 顶部添加注意段落，说明数据模型章节已被 RFC-014 部分取代
- 在数据模型章节添加 RFC-014 取代说明
- 将 CircularDependencyError 统一为 CycleError

### D-02: RFC-018/019 Phase D-E 完成
- 删除 executor.py 中的 ACTION_* 常量（7 个）
- 删除信用评分/额度/利率/决策相关常量（约 30 行）
- 删除 `_execute_legacy_action()` 方法（约 120 行）
- 删除 `_calculate_credit_score()` 和 `_get_credit_grade()` 方法
- KeyError fallback 改为 `raise ValueError`
- execute_rule_group 中的决策常量改为字符串字面量
- 更新 RFC-018/019 状态为 implemented（全部 Phase 完成）

### D-03: ADR-008 D6 级联删除实现
- delete_entity 现在级联删除：category_tags、metrics、entity_versions、entity_dataset_membership、relations
- 最后删除 entities 表记录

### D-04: OPERATOR_SCHEMAS 查询归一化
- get_operator_schema() 增加 .upper() fallback，支持大小写不敏感查询
- validate_operator_params() 通过调用 get_operator_schema() 自动受益

## 四、待后续处理的问题

### HIGH 级别（8 项）

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| N-01 | evaluator condition 类型标注过于宽泛 | engine/rule/evaluator.py | object 使类型检查失效 |
| N-04 | dag_builder 忽略跨规则组 ID 冲突 | engine/rule/dag_builder.py | current_rule_group 参数未使用 |
| N-06 | pipeline_state 直接使用 sqlite3 | engine/rule/pipeline_state.py | 违反模块边界规则 |
| N-07 | partial_complete_run 缺少持久化 | engine/rule/pipeline_state.py | 一行修复但影响数据完整性 |
| N-16 | compute_levels 修改原始 in_degree | engine/rule/dependency_analyzer.py | 第二次调用必出错 |
| N-19 | rule_service 并行保存无事务 | services/rule_service.py | asyncio.gather 部分失败 |
| N-22 | simulation_service 变量提取正则不一致 | services/simulation_service.py | 与 ExpressionEngine 不匹配 |
| N-26 | YAML 解析缺少键存在性校验 | core/schema/loader.py | KeyError 无上下文 |

### 算子模块 HIGH 级别（4 项）

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| OP-01 | graph_traversal 重复注册 | alert.py + graph_traversal.py | 静默覆盖 |
| OP-02 | graph_traversal name 用类变量 | graph_traversal.py | 违反基类接口 |
| OP-05 | SwitchOperator value=None 时 TypeError | switch.py | 运行时崩溃 |
| OP-06 | ScorecardOperator 归一化空操作 | switch.py | 逻辑错误 |

### RFC 一致性遗留（3 项）

| # | 问题 | RFC | 说明 |
|---|------|-----|------|
| R-01 | LLM_JUDGE 降级策略不完整 | RFC-014 D5 | 仅第1级实现 |
| R-02 | 往返一致性测试缺失 | RFC-017 | 功能代码已实现但无验证测试 |
| R-03 | GRAPH 算子缺少 JSON Schema | RFC-014 | 参数验证无法覆盖 |

## 验证结果

- **739 个测试全部通过** ✅
- **ruff 无新增错误** ✅
- **RFC-018/019 状态更新为 implemented** ✅
- **ADR-008 D6 级联删除已实现** ✅
- **RFC-011 标记为部分过时** ✅
- **OPERATOR_SCHEMAS 验证机制已修复** ✅

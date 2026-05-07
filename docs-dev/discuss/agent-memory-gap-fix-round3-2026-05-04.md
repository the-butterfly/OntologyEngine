# Agent Memory GAP 第三轮修复 — 2026-05-04

## 背景

第三轮深度审视发现 23 个新 GAP（4🔴/14🟡/5🟢），修复了 4 个临界 + 8 个中等优先级。

## 修复清单

### 🔴 临界 GAP（已修复）

| GAP# | 问题 | 修复 |
|------|------|------|
| GAP-14 | 巩固引擎缺少 UpgradeAction，类型升级路径断裂 | 新增 `UpgradeAction` 数据类 + `execute_upgrade()` 方法 + `maybe_upgrade_to_entity()` 集成到 `execute_create()` |
| GAP-15 | SUPERSEDES/CONTRADICTS/SUMMARIZED_AS/LEARNED_INTO 边从未创建 | supersede 时创建 SUPERSEDES 边；矛盾检测时创建 CONTRADICTS 边；巩固时按 memory_type 选择 SUMMARIZED_AS/LEARNED_INTO/CONSOLIDATED_INTO |
| GAP-25 | remember supersede 未创建 SUPERSEDES 认知边 | 合并到 GAP-15 一起修复 |
| GAP-30 | `_find_related_observations()` 未按 tags 过滤，违反 D-CON-4 | 添加 tag_set 交集过滤，limit 从 50 提升到 200 |

### 🟡 中等 GAP（已修复）

| GAP# | 问题 | 修复 |
|------|------|------|
| GAP-12+29 | DispositionProfile 动态权重未集成到 recall | `_recall()` 中自动加载 profile 并调用 `apply_dynamic_weight()` |
| GAP-16 | CorrectionPropagation 使用错误的边类型名称 | `SUPPORTS/RELATES_TO` → `SUMMARIZED_AS/COGNITIVE_RELATES_TO` |
| GAP-17 | DreamCycle Phase 2 用 ttl_seconds 而非 valid_to | 优先检查 `valid_to`，fallback 到 `ttl_seconds` |
| GAP-24 | ForgettingEngine 软衰减和归档仅计数未执行 | 软衰减：降低 feedback_weight × 0.7；归档：设置 memory_type="archived" |
| GAP-33 | as_of 时序查询用错字段和比较逻辑 | `occurred_at > as_of` → `valid_from <= as_of AND valid_to > as_of` |
| GAP-26+27 | REST/MCP reflect 缺少 L2/L3 参数 | 新增 async_mode/skip_consolidation/skip_forgetting/cascade_depth/skip_correction_propagation |

### 🟢 低优先级 GAP（未修复，记录待办）

| GAP# | 问题 | 说明 |
|------|------|------|
| GAP-11 | recall 的 disposition_override/expansion_rules 死参数 | 需设计决策：是否移除或实现 |
| GAP-13 | reflect 未传递 DispositionProfile 给 ReflectAgent | 需扩展 ReflectRequest |
| GAP-18 | DreamCycle Phase 1 未用 Compiled Page，Phase 5 未用 LLM | 需 LLM 集成 |
| GAP-19 | DreamCycle Phase 3 未检查无入边条件 | 需图遍历查询支持 |
| GAP-20 | EntityResolver L1 消歧未实现 | 需 Schema identity_fields 支持 |
| GAP-21 | EntityResolver L3 消歧未实现 | 需 LLM 集成 |
| GAP-22 | EntityResolver 共现评分未查询 CO_OCCURS_WITH 边 | 需边查询 API |
| GAP-23 | EntityResolver 缺少实体合并流程 | 需设计 merge_entities() |
| GAP-28 | CLI 缺少设计参数 | 低优先级，CLI 可逐步补全 |
| GAP-31 | Directives D-REF-5.5 仅 warning 非 fatal | 需设计决策 |
| GAP-32 | remember 返回值缺少 extracted_relations | 需关系提取实现 |

## LOCOMO 风格端到端验证

新增 `examples/case8_locomo_memory_eval/run_eval.py`，10 个测试轨迹覆盖 4 大评测维度：

| 测试 | 维度 | 结果 | 说明 |
|------|------|------|------|
| T1: Single-hop Recall | 单跳回忆 | ✅ PASS (0.60) | 5 条事实中 3 条直接命中 |
| T2: Multi-hop Reasoning | 多跳推理 | ✅ PASS (1.00) | 跨 3 条记忆的推理链完整 |
| T3: Temporal Reasoning | 时序推理 | ✅ PASS (1.00) | valid_from/valid_to 正确过滤 |
| T4: Contradiction Detection | 矛盾检测 | ❌ FAIL (0.00) | 需要 LLM，无 LLM 环境无法工作 |
| T5: Consolidation & Upgrade | 巩固升级 | ✅ PASS (1.00) | 碎片→观察，tags 隔离正确 |
| T6: Supersede & Correction | 更正传播 | ✅ PASS (1.00) | supersede 正确设置 belief_status |
| T7: Forgetting Protection | 遗忘保护 | ✅ PASS (1.00) | feedback_weight≥0.9 保护生效 |
| T8: Attributes & Metadata | 属性存储 | ✅ PASS (1.00) | 白名单过滤正确 |
| T9: DispositionProfile | 动态权重 | ✅ PASS (1.00) | finance profile 提升mental_model权重 |
| T10: DreamCycle 5-Phase | 梦境循环 | ✅ PASS (1.00) | 5 阶段全部执行 |

**通过率: 90% (9/10)**，唯一失败的 T4 是 LLM 依赖项，非代码缺陷。

## 需讨论的决策点

### 1. 矛盾检测的 LLM 依赖

当前 ReflectAgent 的矛盾检测完全依赖 LLM。在无 LLM 环境下（如单元测试、CI），矛盾检测返回空结果。

**选项**：
- A) 添加基于规则的矛盾检测（关键词冲突、数值矛盾）作为 LLM 的 fallback
- B) 保持纯 LLM 方案，测试时 mock LLM
- C) 混合方案：规则检测低置信度矛盾，LLM 检测语义矛盾

### 2. 认知边查询 API 缺失

`CognitiveRepository` 有 `create_cognitive_edge()` 但没有 `query_cognitive_edges()`。当前无法通过 repository 层查询认知边，只能直接访问 KuzuGraphStore。

**建议**：在 `CognitiveRepository` 中添加 `query_cognitive_edges(from_id, to_id, edge_type)` 方法。

### 3. DispositionProfile 自动加载策略

当前 recall 时自动加载 "default" 场景的 profile。但设计要求根据 space_id 或 scene 自动匹配。

**选项**：
- A) 按 space_id 查找该 space 下的 profile
- B) 按 scene 参数显式指定（需要 RecallRequest 添加 scene 字段）
- C) 两者结合：优先 scene，fallback 到 space 的默认 profile

### 4. EntityResolver 三级消歧策略

L1（确定性 UUID5）和 L3（LLM 辅助）均未实现。当前只有 L2（模糊匹配）。

**建议**：L1 优先级高（结构化数据导入场景），L3 可延后。

## 测试验证

- **单元+集成测试**: 215 passed
- **LOCOMO 端到端**: 9/10 passed (90%)

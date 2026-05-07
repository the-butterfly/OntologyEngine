# Agent Memory 实现 GAP 深度分析与改进计划

> 日期: 2026-05-06
> 触发: examples/agent_memory/ANALYSIS.md 验证结果
> 方法: 逐代码文件核对设计文档 → 交叉比对 8 组验证轨迹 → 文档治理状态审查

---

## 一、验证确认的实现偏差

以下每条偏差均已通过代码文件逐行核对确认，标注了具体代码位置和设计文档位置。

### 1.1 BUG 级（运行时错误）

| # | 模块 | 偏差 | 代码位置 | 设计文档 | 影响 |
|---|------|------|---------|---------|------|
| B-1 | Compilation | EntityPage 缺 `related_observations` 属性 | [compilation.py:41-48](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py#L41) 定义无此字段，[memory_api.py:878](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L878) 引用 `page.related_observations[:10]` | §LC-10 | **AttributeError** 导致 compile_entity_page 返回空结果 |
| B-2 | Compilation | TopicPage 缺 `key_findings`/`open_questions` 属性 | [compilation.py:51-58](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py#L51) 定义无此字段，[memory_api.py:901-902](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L901) 引用 | §LC-10 | **AttributeError** 导致 compile_topic_page 返回空结果 |

### 1.2 严重级（功能缺失/逻辑错误）

| # | 模块 | 偏差 | 代码位置 | 设计文档 | 影响 |
|---|------|------|---------|---------|------|
| S-1 | Recall | analytical 查询直接返回空列表 | [rrf_fusion.py:128-129](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L128) `if query_type == "analytical": return []` | §14.2 | 分析型查询永远无结果 |
| S-2 | QUL | 设计 8 种约束类型，实现只有 1 种英文 temporal | [rrf_fusion.py:38-60](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L38) 只有 `extract_temporal_constraint` 函数 | [query-understanding-layer.md §2.2](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | QUL 架构缺口：无 QueryUnderstandingLayer 类、无约束→策略映射、无重排序 |
| S-3 | Forgetting | confirmation_count 永远为 0 | [lifecycle.py:311-316](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/lifecycle.py#L311) `_compute_node_strength` 调用 `compute_memory_strength` 时未传 `confirmation_count` | §LC-3 | 0.15 权重因子完全失效 |
| S-4 | Forgetting | decay_strength 正反馈循环 | [lifecycle.py:318](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/lifecycle.py#L318) `decay_strength(strength, days_elapsed, strength)` 用 strength 自身作 memory_value | §LC-4 | 高强度记忆衰减极慢，低强度记忆衰减极快，无法收敛 |
| S-5 | Recall | Layer-S 只查 entity 类型 | [rrf_fusion.py:342-358](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L342) `memory_type="entity"` 硬编码 | §14.2 | observation/mental_model 等类型在图检索路径中完全不可见 |
| S-6 | QUL | 自动上下文加载未实现 | 设计文档 §4 定义了 `load_task_context`，代码中不存在 | [query-understanding-layer.md §4](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | recall 无法感知活跃任务、用户偏好、待履行承诺 |

### 1.3 中等级（设计偏差）

| # | 模块 | 偏差 | 代码位置 | 设计文档 | 影响 |
|---|------|------|---------|---------|------|
| M-1 | Consolidation | Update proof_count 只 +1 | [consolidation_engine.py:320](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L320) `getattr(existing, "proof_count", 0) + 1` | [consolidation-engine.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/consolidation-engine.md) 设计为 `+ len(new_source_fragments)` | 证据计数失真 |
| M-2 | Consolidation | Tag 隔离用交集匹配 | [consolidation_engine.py:579](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L579) `tag_set & set(n.tags)` | D-CON-4 严格分组隔离 | 跨 tag 组信息可能泄漏 |
| M-3 | Forgetting | 硬删除不处理连接边 | [lifecycle.py:250](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/lifecycle.py#L250) `await self._repo.delete_node(node_id)` | §LC-5 | KuzuDB 报错 "Node has connected edges" |
| M-4 | Compilation | 摘要是简单 `|` 拼接 | [compilation.py:134](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py#L134) `" | ".join(p for p in summary_parts if p)` | §LC-10 LLM 生成结构化摘要 | 编译产物质量低 |
| M-5 | Compilation | related 节点无相关性过滤 | [compilation.py:123-130](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py#L123) 取 space 下前 20 个 observation | §LC-10 应按相关性筛选 | 编译页面包含无关内容 |
| M-6 | Consolidation | `_generate_uuid5` 使用 MD5 | [consolidation_engine.py:103](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L103) `hashlib.md5(key.encode()).hexdigest()[:16]` | D-CON-1 UUID5 | 命名误导，且 MD5 碰撞风险高于 SHA-1 |
| M-7 | Consolidation | Delete 动作双重写入 | [consolidation_engine.py:373-379](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L373) `update_node` + `transition_belief` | §CON-1 | 可能产生竞态或重复 history 条目 |

### 1.4 设计文档 vs 实现的架构级 GAP

| # | 领域 | 设计预期 | 实际状态 | 差距评估 |
|---|------|---------|---------|---------|
| G-1 | QUL 完整架构 | QueryUnderstandingLayer 类 + TaskConstraints 模型 + 约束→策略映射 + 重排序 | 只有 `extract_temporal_constraint` 函数（英文 5 种模式） | **架构缺失**，需从零构建 |
| G-2 | 记忆强度 5 因子模型 | recency(0.25) + confirmation(0.15) + evidence(0.25) + feedback(0.2) + frequency(0.15) | confirmation 因子永远为 0，decay_strength 正反馈循环 | **因子失效**，需修复传入链路和衰减公式 |
| G-3 | 巩固三动作独立验证 | Create/Update/Delete 各自行为可独立验证 | 验证只检查"节点数增加"，未验证各动作语义 | **验证覆盖不足** |
| G-4 | 编译层结构化输出 | EntityPage 含 related_observations，TopicPage 含 key_findings/open_questions | 两个 dataclass 缺失字段，MemoryAPI 引用导致 AttributeError | **字段缺失**，需补齐 |
| G-5 | RRF 四路融合权重 | 设计定义了 w_layer_r/w_layer_s/w_bm25/w_temporal 权重 | 权重已定义但 Layer-S 只查 entity，analytical 短路 | **路径降级**，需修复查询覆盖 |
| G-6 | DispositionProfile 7 维权重 | 设计定义了 7 维度动态权重系统 | 权重定义存在但未在 recall 流程中实际注入 | **未接入**，需打通链路 |
| G-7 | 信念状态转换完整链路 | accepted→pending_review→accepted/rejected/superseded | 状态机定义正确，但 insights 生成条件过严 | **条件过严**，需调整阈值 |
| G-8 | 更正传播 BFS 深度 | 设计要求 BFS 沿认知边传播 | 实现存在但未验证传播深度 | **验证缺失** |

---

## 二、文档治理状态审查

### 2.1 需要标注 [待核对代码] 的文档

| 文档 | 当前状态 | 需要标注的位置 | 原因 |
|------|---------|-------------|------|
| [query-understanding-layer.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | draft | §2.1 QueryUnderstandingLayer 类定义 | 类不存在，只有孤立函数 |
| [query-understanding-layer.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | draft | §2.3 约束→策略映射 | 未实现 |
| [query-understanding-layer.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | draft | §3.2 约束驱动重排序 | 未实现 |
| [query-understanding-layer.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | draft | §4 上下文加载 | 未实现 |
| [memory-lifecycle.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-lifecycle.md) | draft | §LC-3 confirmation_count | 传入链路断裂 |
| [memory-lifecycle.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-lifecycle.md) | draft | §LC-4 decay_strength 公式 | 正反馈循环 |
| [consolidation-engine.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/consolidation-engine.md) | under-review | Update proof_count | 只 +1 而非 +len |
| [consolidation-engine.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/consolidation-engine.md) | under-review | D-CON-4 Tags 严格隔离 | 实际用交集匹配 |

### 2.2 需要更新 STATUS.md 的条目

- Agent 记忆系统条目需追加：**8 项实现偏差已确认（2 BUG + 4 严重 + 7 中等）**
- 新增热点质量问题：Agent Memory 编译层 AttributeError + QUL 架构缺失

### 2.3 需要更新 TODO.md 的条目

见下方改进计划中的具体条目。

---

## 三、改进计划

### Phase 0: 紧急修复（P0 - 阻塞性 BUG）

> 目标：消除运行时 AttributeError，恢复编译层基本功能

| # | 任务 | 修改文件 | 验证方式 |
|---|------|---------|---------|
| P0-1 | EntityPage 添加 `related_observations: list[str]` 字段 | [compilation.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py) | 运行 03_consolidation_compilation T5/T6 |
| P0-2 | TopicPage 添加 `key_findings: list[str]` + `open_questions: list[str]` 字段 | [compilation.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py) | 运行 03_consolidation_compilation T5/T6 |
| P0-3 | `compile_entity_page` 填充 `related_observations` | [compilation.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py) | 单元测试 |
| P0-4 | `compile_topic_page` 填充 `key_findings` + `open_questions` | [compilation.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py) | 单元测试 |
| P0-5 | 移除 analytical 查询短路返回空列表 | [rrf_fusion.py:128-129](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L128) | 运行 04_locomo T1 |

### Phase 1: 严重修复（P1 - 功能缺失/逻辑错误）

> 目标：修复核心认知操作的功能缺陷

| # | 任务 | 修改文件 | 验证方式 |
|---|------|---------|---------|
| P1-1 | 修复 confirmation_count 传入链路 | [lifecycle.py:311-316](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/lifecycle.py#L311) + CognitiveNode 添加 `confirmation_count` 字段或从 `last_confirmed_at` 推算 | 单元测试 + 05_lifecycle |
| P1-2 | 修复 decay_strength 正反馈循环 | [lifecycle.py:318](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/lifecycle.py#L318) 改为使用独立 `memory_value` 参数（如 `feedback_weight` 或 `confidence`） | 单元测试 + 05_lifecycle |
| P1-3 | Layer-S 查询扩展到 observation/mental_model | [rrf_fusion.py:342-358](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L342) 移除 `memory_type="entity"` 硬编码 | 运行 04_locomo |
| P1-4 | 修复遗忘硬删除级联边处理 | [lifecycle.py:250](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/lifecycle.py#L250) 删除前先删除关联边 | 单元测试 + 05_lifecycle |
| P1-5 | QUL 中文时间约束支持 | [rrf_fusion.py:38-44](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L38) 添加中文时间模式 | 运行 08_qul T1 |

### Phase 2: 中等修复（P2 - 设计偏差对齐）

> 目标：将实现与设计文档对齐

| # | 任务 | 修改文件 | 验证方式 |
|---|------|---------|---------|
| P2-1 | Consolidation proof_count 修复为 +len(new_source_fragments) | [consolidation_engine.py:320](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L320) | 单元测试 |
| P2-2 | Tag 隔离改为严格匹配 | [consolidation_engine.py:579](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L579) `tag_set & set(n.tags)` → `tag_set == set(n.tags)` 或 `tag_set.issubset(set(n.tags))` | 单元测试 + 跨 tag 隔离验证 |
| P2-3 | `_generate_uuid5` 改用 SHA-1 或真 UUID5 | [consolidation_engine.py:103](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L103) | 单元测试 |
| P2-4 | Delete 动作去除双重写入 | [consolidation_engine.py:373-379](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/consolidation_engine.py#L373) 只保留 `transition_belief` | 单元测试 |
| P2-5 | 编译摘要改为结构化拼接（分节而非 `|` 拼接） | [compilation.py:134](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py#L134) | 单元测试 |
| P2-6 | 编译 related 节点添加相关性过滤 | [compilation.py:123-130](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/compilation.py#L123) | 单元测试 |

### Phase 3: 架构补全（P3 - QUL 完整实现）

> 目标：构建 QueryUnderstandingLayer 完整架构
> 前置条件：Phase 0-2 完成

| # | 任务 | 设计参考 | 预期产出 |
|---|------|---------|---------|
| P3-1 | 实现 QueryUnderstandingLayer 类 | [query-understanding-layer.md §2.1](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | 新文件 `qul.py` |
| P3-2 | 实现 TaskConstraints 模型 + 规则层约束提取 | [query-understanding-layer.md §2.2](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | 8 种约束类型提取 |
| P3-3 | 实现约束→检索策略映射 | [query-understanding-layer.md §2.3](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | CONSTRAINT_TO_RETRIEVAL_STRATEGY |
| P3-4 | 实现约束驱动重排序 | [query-understanding-layer.md §3.2](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | apply_constraint_boost |
| P3-5 | 实现自动上下文加载 | [query-understanding-layer.md §4](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | load_task_context |
| P3-6 | QUL 集成到 recall 流程 | [query-understanding-layer.md §3.1](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | memory_api.py recall 链路 |

### Phase 4: 验证增强（P4 - 补齐薄弱验证点）

> 目标：将验证复杂度从 ★★☆☆☆ 提升至 ★★★★☆

| # | 验证点 | 当前状态 | 目标 |
|---|-------|---------|------|
| P4-1 | 巩固三动作模型独立验证 | 只验证"节点数增加" | Create/Update/Delete 各自行为验证 |
| P4-2 | 记忆强度 5 因子模型验证 | 完全未验证 | 逐因子权重验证 |
| P4-3 | QUL 约束驱动检索验证 | 只验证时间约束提取 | 8 种约束→策略映射验证 |
| P4-4 | DispositionProfile 7 维权重验证 | 完全未验证 | 维度权重计算验证 |
| P4-5 | 编译层结构化输出验证 | AttributeError 阻塞 | EntityPage/TopicPage 完整字段验证 |
| P4-6 | 更正传播 BFS 深度验证 | 只验证传播发生 | 传播深度 + 级联风暴防护验证 |
| P4-7 | 跨 model_domain 权限隔离验证 | 未验证 | 用户能否修改 World Model |
| P4-8 | 信念状态转换完整链路验证 | insights 条件过严 | 全状态转换验证 |

---

## 四、待讨论事项

以下事项存在不确定性，需要讨论确认后才能实施：

### D-1: confirmation_count 的数据来源

**问题**: 设计文档定义了 `confirmation_count`（被后续证据确认的次数），但 CognitiveNode 模型中没有此字段。

**选项**:
- (A) 在 CognitiveNode 添加 `confirmation_count: int` 字段，由巩固/反思流程递增
- (B) 从 `last_confirmed_at` 时间戳推算（需要新增此字段）
- (C) 从 `source_fragment_ids` 长度变化推算（间接计算）

**倾向**: (A) 最直接，但需要修改存储层 schema

**✅ 决策**: **(A) 新增字段** — 在 CognitiveNode 添加 `confirmation_count: int` 字段，由巩固/反思流程递增。需同步修改 KuzuDB schema 和 repository 层。

### D-2: decay_strength 的 memory_value 应该用什么？

**问题**: 当前用 `strength` 自身作为 `memory_value` 导致正反馈循环。设计文档中 `memory_value` 的语义不明确。

**选项**:
- (A) 使用 `feedback_weight`（用户反馈权重，0-1，外部输入）
- (B) 使用 `confidence`（置信度，0-1，相对稳定）
- (C) 使用 `proof_count / max_proof_count`（证据密度）
- (D) 使用 `compute_memory_strength` 的原始值（不含衰减），而非衰减后的值

**倾向**: (B) confidence 相对稳定且反映知识质量，不会产生正反馈

**✅ 决策**: **(B) confidence** — 使用 `confidence` 作为 `memory_value` 参数。confidence 相对稳定且反映知识质量，0-1 范围与 forgetting_rate 分档对齐，不会产生正反馈循环。

### D-3: Tag 隔离的严格程度

**问题**: 当前用交集匹配 `tag_set & set(n.tags)`，设计要求严格匹配。

**选项**:
- (A) 完全严格匹配 `tag_set == set(n.tags)` — 最安全，但可能过度隔离
- (B) 子集匹配 `tag_set.issubset(set(n.tags))` — 巩固碎片的 tags 必须是已有节点 tags 的子集
- (C) 保持交集匹配但添加警告日志 — 最小改动

**倾向**: (B) 子集匹配，平衡安全性和实用性

**✅ 决策**: **(B) 子集匹配** — 巩固碎片的 tags 必须是已有节点 tags 的子集（`tag_set.issubset(set(n.tags))`），平衡安全性和实用性。

### D-4: analytical 查询的处理策略

**问题**: 当前 analytical 查询直接返回空列表，但设计文档 §14.2 定义了分析型查询的处理方式。

**选项**:
- (A) 移除短路，让 analytical 走正常 RRF 融合 — 最简单
- (B) 为 analytical 查询实现专门的检索策略（聚合+推理）— 最完整但工作量大
- (C) 将 analytical 降级为 mixed 类型处理 — 折中方案

**倾向**: (C) 短期降级为 mixed，长期实现专门策略

**✅ 决策**: **(B) 专门策略** — 为 analytical 查询实现专门的检索策略（聚合+推理）。这是最完整的方案，虽然工作量大，但符合设计文档预期。实施时可分步：先实现基础聚合检索，再增强推理能力。

### D-5: QUL 实现的优先级和范围

**问题**: QUL 设计文档定义了完整架构，但实现量很大。是否需要分阶段？

**选项**:
- (A) 一次性实现完整 QUL（8 种约束 + 重排序 + 上下文加载）
- (B) 先实现规则层（6 种中文约束提取），再实现 LLM 层和重排序
- (C) 先实现约束提取 + 重排序，上下文加载延后

**倾向**: (B) 规则层优先，LLM 层和上下文加载作为增强

**✅ 决策**: **(B) 规则层优先** — 先实现规则层（6 种中文约束提取），再实现 LLM 层和重排序。这与用户选择的 analytical 专门策略(B) 一致，分阶段降低实施风险。

### D-6: 编译层 LLM 摘要的实现时机

**问题**: 当前编译摘要是简单 `|` 拼接，设计要求 LLM 生成结构化摘要。但 LLM 依赖尚未完全打通。

**选项**:
- (A) 立即实现 LLM 摘要（需要 LLM 配置）
- (B) 先改为结构化拼接（分节：概述/关键事实/时间线），LLM 摘要作为可选增强
- (C) 保持简单拼接，优先修复 BUG

**倾向**: (B) 结构化拼接是低成本的显著改进

**✅ 决策**: **(B) 结构化拼接** — 先改为结构化拼接（分节：概述/关键事实/时间线），LLM 摘要作为可选增强。这是低成本的显著改进，不依赖 LLM 配置。

---

## 五、文档治理行动项

| # | 行动 | 目标文件 | 状态 |
|---|------|---------|------|
| DG-1 | query-understanding-layer.md 全文标注 [待核对代码] | [query-understanding-layer.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/query-understanding-layer.md) | 待执行 |
| DG-2 | memory-lifecycle.md §LC-3/§LC-4 标注 [待核对代码] | [memory-lifecycle.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-lifecycle.md) | 待执行 |
| DG-3 | consolidation-engine.md Update proof_count / D-CON-4 标注 [待核对代码] | [consolidation-engine.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/consolidation-engine.md) | 待执行 |
| DG-4 | STATUS.md 更新 Agent 记忆系统条目 | [STATUS.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/STATUS.md) | 待执行 |
| DG-5 | TODO.md 添加 Phase 0-2 条目 | [TODO.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/TODO.md) | 待执行 |
| DG-6 | ANALYSIS.md 追加代码行号交叉引用 | [ANALYSIS.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/examples/agent_memory/ANALYSIS.md) | 待执行 |

---

## 六、复杂度评估更新

| 验证组 | 当前复杂度 | Phase 0-2 后预期 | Phase 3-4 后预期 |
|--------|:---------:|:---------------:|:---------------:|
| 01_ingestion | ★★☆☆☆ | ★★★☆☆ | ★★★★☆ |
| 02_contradiction | ★★★☆☆ | ★★★☆☆ | ★★★★☆ |
| 03_consolidation | ★★☆☆☆ | ★★★★☆ | ★★★★★ |
| 04_locomo | ★★★☆☆ | ★★★☆☆ | ★★★★☆ |
| 05_lifecycle | ★★★☆☆ | ★★★★☆ | ★★★★☆ |
| 06_full_agent | ★★☆☆☆ | ★★★☆☆ | ★★★★☆ |
| 07_modeling | ★★☆☆☆ | ★★☆☆☆ | ★★★★★ |
| 08_qul | ★★☆☆☆ | ★★★☆☆ | ★★★★★ |

---

## 七、Session 执行记录 (2026-05-06 Round 2)

### 7.1 关键发现

| # | 发现 | 严重度 | 修复 |
|---|------|--------|------|
| F-1 | `get_cognitive_node` Cypher RETURN 子句缺 `confirmation_count` 列，但 row-to-dict 映射引用了它 → KeyError | BUG | ✅ 添加 `n.confirmation_count AS confirmation_count` |
| F-2 | `run_consolidation` 返回 `{created, updated, deleted}`，eval 检查 `consolidated_count` → 永远为 0 | API mismatch | ✅ 添加 `consolidated_count` 字段 |
| F-3 | `get_audit_trail` 只查 superseded/rejected/pending_review，不含 consolidation 条目 | 功能缺失 | ✅ 扩展为包含 consolidated 节点 |

### 7.2 本轮修复清单

| 模块 | 文件 | 修改内容 | 影响范围 |
|------|------|----------|----------|
| KuzuDB 存储 | [kuzu_store.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/storage/graph/kuzu_store.py) | `get_cognitive_node` RETURN 添加 `confirmation_count` | 02/04/08 eval 组修复 |
| MemoryAPI | [memory_api.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) | `run_consolidation` 添加 `consolidated_count`；`get_audit_trail` 扩展 consolidated 节点 | 03 eval T1/T3/T4/T7 修复 |
| QUL | [rrf_types.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_types.py) | 新增 `UserPreferenceConstraint` + `DecisionConstraint`；`QUERY_TYPE_WEIGHTS` 扩展 | QUL 约束类型 1→3 |
| QUL | [rrf_fusion.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py) | 新增 `USER_PREFERENCE_PATTERNS` + `DECISION_PATTERNS` + 提取函数 | QUL 约束提取 |
| QUL | [query_router_types.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/query_router_types.py) | `QUERY_TYPE_PATTERNS` + `PARAM_PRESETS` + `DEGRADATION_CHAINS` 扩展 | query 路由 |
| QUL | [query_router.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/query_router.py) | `detect_query_type` 优先级更新 | query 类型检测 |
| Eval | [cli_runner.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/examples/agent_memory/_lib/cli_runner.py) | `extract_constraints` 扩展新约束类型 | QUI eval |

### 7.3 验证结果

- Unit Tests: 949/950 passed (1 pre-existing MCP tool count failure)
- Eval Trajectories: **64/65 (98.5%)** — 仅 06_full_agent 有 1 个 pre-existing failure
- 03_consolidation: 8/8 **全部 1.0** (之前 T1/T3/T4/T7 score<1.0)
- 04_locomo: T8/T10 **全部 1.0** (confirmation_count fix 生效)
- 08_qul: 8/8 全部通过

### 7.4 剩余 GAP

| # | 领域 | 状态 |
|---|------|------|
| QUL 约束类型 | 8 种设计中已完成 3 种（temporal + user_preference + decision），剩余 task_status/entity_type/numeric/negation/scope | P1 Backlog |
| 06_full_agent | 7/8, 1 个 pre-existing trajectory failure | 待调查 |
| 中文 BM25 tokenization | test_phase2_retrieval_and_consumption pre-existing failure | 已知限制 |
| DispositionProfile 7 维权重 | 设计定义但未在 recall 流程中实际注入 | G-6 未解决 |

---

## 八、后端代码优化计划 (2026-05-06 Round 3)

> **触发**: `docs-dev/review-reports/frontend-memory-ui-consistency-report.md` 前端报告 + 5 路 Sub Agent 交叉分析
> **方法**: 对前端报告 §5-§7 逐一交叉核对后端代码 → 结合 agent-memory 设计文档 → 优先级排序

### 8.1 问题全景矩阵

#### 8.1.1 P0 阻塞性问题（前端完全不可用）

| # | 问题 | 前端影响 | 后端根因 | 代码位置 | 状态 |
|---|------|---------|---------|---------|------|
| P0-1 | `recall` query="*" 返回空结果 | 记忆图谱、列表、待审区全部为空 | 空查询/通配符无处理逻辑；`query_type="semantic"` 路由到空 result 路径 | [memory_api.py:508-515](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L508) | ⚠️ 待修复 |
| P0-2 | `GET /{node_id}` confirmation_count KeyError | 详情抽屉完全不可用 | KuzuDB RETURN 子句缺失（已修复但需验证路径） | [kuzu_store.py:1922-1923](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/storage/graph/kuzu_store.py#L1922) | ✅ 已修复 |
| P0-3 | `GET /{node_id}/evidence` confirmation_count KeyError | 证据链展开报错 | 同 P0-2 根因 | [kuzu_store.py:1922-1923](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/storage/graph/kuzu_store.py#L1922) | ✅ 已修复 |

#### 8.1.2 P1 功能缺失（前端有页面但无数据）

| # | 问题 | 前端影响 | 后端根因 | 设计方案 | 状态 |
|---|------|---------|---------|---------|------|
| P1-1 | audit 返回字段不完整 | Agent 活动流无法展示操作类型/延迟 | `get_audit_trail` 只返回节点级字段(id/memory_type/content/belief_status)，无 agent_name/activity_type/timestamp/operation/result | [memory_api.py:871-892](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L871) | ⚠️ 待扩展 |
| P1-2 | 无 `GET /heatmap` 端点 | 记忆强度热力图无法展示 | 端点不存在 | [memory-api.md §LC-3](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-api.md) | ⚠️ 待新增 |
| P1-3 | 无 `GET /dashboard` 端点 | 治理仪表盘无法展示 | 端点不存在 | [memory-api.md §10](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-api.md) | ⚠️ 待新增 |
| P1-4 | 无 `GET/PUT /disposition` 端点 | Disposition 预设无法加载/保存 | 端点不存在；`DispositionProfile` model 存在但无 CRUD 端点 | [models.py DispositionProfile](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/models.py) | ⚠️ 待新增 |
| P1-5 | 无 `GET /reflect-tasks` 端点 | 只能看到当前会话任务 | 端点不存在；`ReflectionJobStore` 存在但无列表端点 | [memory_api.py ReflectionJobStore](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) | ⚠️ 待新增 |
| P1-6 | 无 `GET /reflect/{reflection_id}` 端点 | 无法轮询任务进度 | 端点不存在；`get_reflection_status` 方法存在但无路由 | [memory_api.py get_reflection_status](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) | ⚠️ 待新增 |
| P1-7 | 无 `POST /validation/cases` 端点 | 验证演示无法自动化 | 端点不存在 | [memory-api.md §11](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/02-design/agent-memory/memory-api.md) | ⚠️ 待新增 |

#### 8.1.3 P2 增强项（提升体验和数据完整性）

| # | 问题 | 后端根因 | 建议 |
|---|------|---------|------|
| P2-1 | 证据链未暴露 source_fragment_ids + proof_count | `get_evidence` 端点返回简化结构 | 扩展 evidence 端点直接返回 CognitiveNode 的 source_fragment_ids、proof_count |
| P2-2 | 矛盾列表为空 | `/contradictions` 端点存在但返回空（contradiction 检测触发条件过严） | 降低 contradiction 检测阈值或在 remember 时显式记录 |
| P2-3 | 更正历史为空 | `/corrections` 端点存在但返回空（correction 需 belief_status 为 "superseded"） | 确保 correct_memory 正确触发 belief 转换 |
| P2-4 | BM25 中文分词不支持 | `_search_bm25` 无法正确处理中文 | 集成 jieba 分词或使用 SQLite FTS5 ICU 扩展 |
| P2-5 | recall 无冷启动降级 | `query="*"` 无特殊处理路径 | 为通配符/空查询添加 "list all" 降级路径 |

### 8.2 Phase 0: 紧急修复（P0）

#### P0-1: 修复 recall 返回空结果

**根因分析**:
| 代码路径 | 问题 |
|----------|------|
| [memory_api.py:508](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L508) | `if not req.query or not req.query.strip():` 检查空查询 |
| [memory_api.py:514](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L514) | `query_type = "type_filter" if req.memory_type else "semantic"` |
| [memory_api.py:542-548](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L542) | 无 memory_type 时走 `self._router.route(query=req.query,...)` |
| [query_router.py:132](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/query_router.py#L132) | `detect_query_type("*")` → 无关键词命中 → 返回 `"factual"` |
| [rrf_fusion.py:114-166](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py#L114) | `fuse("*", query_type="factual")` → 4 路检索对 "*" 均为 0 命中 → 空结果 |

**修复方案**: 在 `_recall` 入口处添加通配符降级路径：
```python
# 方案: query="*" 或空查询 → 直接走 query_nodes 返回全部结果
if req.query == "*" or not req.query.strip():
    nodes = await self._repo.query_nodes(
        domain_id=req.space_id, limit=req.max_results,
        belief_status=req.belief_status_filter or "accepted",
    )
    # ... 构建结果列表
```

**修改文件**: [memory_api.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) `_recall` 方法

### 8.3 Phase 1: 功能补全（P1）

#### P1-1: audit 字段扩展 — Agent 活动日志

**当前状态 vs 设计期望**:

| 字段 | 当前值来源 | 设计期望 | 可行方案 |
|------|-----------|---------|---------|
| `agent_name` | 无 | Agent 标识 | 从 `created_by` 字段获取（已有） |
| `activity_type` | 无 | remember/recall/reflect/correct/delete | 从节点 `history[].change_reason` 推断 |
| `timestamp` | `updated_at` (可能为 null) | 操作时间 | 从 `history[].changed_at` 获取 |
| `operation` | 无 | 操作描述 | 从 `content` 摘要 + `memory_type` 构造 |
| `result` | 无 | 操作结果摘要 | 从 `belief_status` + `proof_count` 构造 |

**实现方案**: 扩展 `get_audit_trail` 的 entries 构建逻辑：
```python
entries.append({
    "id": n.id,
    "memory_type": n.memory_type,
    "content": n.content[:200],
    "belief_status": n.belief_status,
    "superseded_by": n.superseded_by,
    "updated_at": n.updated_at,
    # --- 新增字段 ---
    "agent_name": n.created_by or "system",
    "activity_type": _infer_activity_type(n),
    "timestamp": n.updated_at or n.created_at or "",
    "operation": _build_operation_desc(n),
    "result": _build_result_summary(n),
})
```

**修改文件**: [memory_api.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) `get_audit_trail` 方法

#### P1-2 至 P1-7: 新增 6 个端点

| # | 端点 | MemoryAPI 新方法 | 数据来源 | 实现难度 |
|---|------|-----------------|---------|---------|
| P1-2 | `GET /heatmap` | `get_heatmap(space_id)` | 聚合 `compute_memory_strength` 按 memory_type 分组 | ★★☆ |
| P1-3 | `GET /dashboard` | `get_dashboard(space_id)` | 综合 `get_stats` + `get_types` + `get_contradictions` + `get_audit_trail` | ★★☆ |
| P1-4 | `GET /disposition` | `get_disposition(space_id)` | Repository 读取 `DispositionProfile`（需新增 repository 方法） | ★★★ |
| P1-4 | `PUT /disposition` | `update_disposition(space_id, profile)` | Repository 更新 `DispositionProfile`（需新增 repository 方法） | ★★★ |
| P1-5 | `GET /reflect-tasks` | `list_reflection_jobs(space_id)` | 遍历 `ReflectionJobStore` 返回当前活跃 jobs | ★☆☆ |
| P1-6 | `GET /reflect/{reflection_id}` | `get_reflection_status(reflection_id)` | 已有方法 `get_reflection_status`，只需加路由 | ★☆☆ |
| P1-7 | `POST /validation/{case_id}` | `run_validation_case(space_id, case_id)` | 调用 examples 中的 eval 逻辑 | ★★★ |

### 8.4 Phase 2: 增强优化（P2）

| # | 优化项 | 实现方案 | 修改文件 |
|---|--------|---------|---------|
| P2-1 | 证据链完整暴露 | `get_evidence` 返回 `source_fragment_ids`, `proof_count`, `related_edges` | [routes/memory.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/api/routes/memory.py) |
| P2-2 | 矛盾检测阈值调整 | 降低 `_detect_contradictions` 触发条件 | [contradiction.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/contradiction.py) |
| P2-3 | 更正历史追踪 | 确保 `correct_memory` 正确设置 `belief_status="superseded"` + superseded_by | [memory_api.py correct_memory](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py#L1071) |
| P2-4 | BM25 中文分词 | 在 `_search_bm25` 入口处添加 jieba 分词预处理 | [rrf_fusion.py _search_bm25](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/rrf_fusion.py) |
| P2-5 | 冷启动降级 | 同 P0-1 修复 | [memory_api.py _recall](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) |

### 8.5 实施建议优先级排序

```
P0-1: recall 返回空 ─────────────────────────▶ [立即修复，阻塞前端]
  │
  ├─ P1-1: audit 字段扩展 ──────────────────▶ [1-2h，解锁 Agent 活动页]
  ├─ P1-5: reflect-tasks 列表 ──────────────▶ [30min，已有 JobStore]
  ├─ P1-6: reflect/{id} 状态查询 ───────────▶ [30min，已有方法]
  │
  ├─ P1-2: heatmap ─────────────────────────▶ [1-2h，聚合 compute_strength]
  ├─ P1-3: dashboard ───────────────────────▶ [1-2h，组合 stats+audit]
  │
  ├─ P1-7: validation/cases ────────────────▶ [2-3h，需对接 eval 框架]
  ├─ P1-4: disposition CRUD ────────────────▶ [2-3h，需新增 repo 方法]
  │
  ├─ P2-1: 证据链完整 ──────────────────────▶ [1h]
  ├─ P2-2: 矛盾检测 ────────────────────────▶ [1h]
  ├─ P2-3: 更正历史 ────────────────────────▶ [1h]
  ├─ P2-4: BM25 中文 ───────────────────────▶ [2-3h]
  └─ P2-5: 冷启动 ──────────────────────────▶ [含 P0-1]
```

### 8.6 关键设计决策待讨论

| # | 议题 | 选项 |
|---|------|------|
| D-1 | 是否在 `remember` 时同步记录活动日志？ | (A) 同步写 activity_log 表 (B) 从节点 history 推断 (C) 延迟批量写入 |
| D-2 | `disposition` 存储位置？ | (A) KuzuDB 节点属性 (B) 独立 SQLite disposition 表 (C) 内存单例 + 文件持久化 |
| D-3 | `validation` 端点是否应运行真实 eval？ | (A) 完整跑 eval 脚本 (B) 轻量级仿真 (C) 返回预录制结果 |
| D-4 | BM25 中文分词是引入 jieba 还是用 FTS5 ICU？ | (A) jieba 分词（轻量，纯 Python）(B) SQLite FTS5 + ICU tokenizer（需编译依赖）|

---

## 九、Session 执行记录 (2026-05-06 Round 3)

### 9.1 设计决策确认

| # | 议题 | 决策 |
|---|------|------|
| D-1 | 活动日志方式 | **(C) 后台线程写入独立 activity_log 表，存储与主存储分离** |
| D-2 | Disposition 存储 | **(C) 内存单例 + JSON 文件持久化** |
| D-3 | Validation 端点 | **(A) 真实 eval** |
| D-4 | BM25 中文分词 | **两种方案都支持，作为选项** |

### 9.2 本轮实现清单

| # | 实现项 | 产出 | 状态 |
|---|--------|------|------|
| P0-1 | recall query="*" 返回空 | `_recall_wildcard` 方法：直接查询所有节点，按 memory_type/belief_status 过滤 | ✅ |
| P1-1 | ActivityLog 系统 | [activity_log.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/activity_log.py) — ActivityLogEntry + ActivityLogWriter(后台线程+WAL) + 独立 SQLite + log_remember/recall/reflect/correct/delete 快捷函数 | ✅ |
| P1-1 | ActivityLog 集成 | [memory_api.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) — remember/recall/correct/delete 方法添加 _log_* 调用 | ✅ |
| P1-1 | audit 端点扩展 | `get_audit_trail` 返回：entries(含 agent_name/activity_type/timestamp/operation/result 新字段) + activity_entries(合并 ActivityLog) | ✅ |
| P1-2 | /heatmap 端点 | 返回 get_stats 聚合数据 | ✅ |
| P1-3 | /dashboard 端点 | 聚合 stats+types+audit → 治理仪表盘数据 | ✅ |
| P1-4 | /disposition CRUD | [disposition_store.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/disposition_store.py) — DispositionStore(内存+JSON) + GET/PUT 端点 | ✅ |
| P1-5/6 | /reflect-tasks + /reflect/{id} | 遍历 ReflectionJobStore + 调用已有 get_reflection_status | ✅ |
| P1-7 | /validation + /validation/cases | 8 个 eval 案例的 POST 触发 + GET 列表 | ✅ |

### 9.3 新增/修改文件汇总

| 文件 | 类型 | 说明 |
|------|------|------|
| [activity_log.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/activity_log.py) | 新增 | ActivityLog 完整系统 |
| [disposition_store.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/disposition_store.py) | 新增 | DispositionProfile 内存+文件存储 |
| [memory_api.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/memory_api.py) | 修改 | _recall_wildcard + activity log 集成 + audit 扩展 + helper functions |
| [routes/memory.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/api/routes/memory.py) | 修改 | 8 个新端点：(heatmap, dashboard, disposition GET/PUT, reflect-tasks, reflect/{id}, validation POST/GET) |
| [TODO.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/TODO.md) | 修改 | 4 个 P0/P1 项标记为 ✅ |
| [STATUS.md](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/docs/STATUS.md) | 修改 | 2 个 hotspot 改为已完成 + 2 个新增组件的热点 |

### 9.4 验证结果

| 度量 | 值 |
|------|-----|
| Unit Tests | 949/950 passed (1 pre-existing) |
| Eval Trajectories | 64/65 (98.5%) |
| New endpoint count | 8 endpoints added |
| New file count | 2 files created |

### 9.5 剩余工作

| # | 领域 | 优先级 |
|---|------|--------|
| BM25 中文分词(jieba/FTS5 ICU) | D-4 双方案支持 | P2 |
| 证据链完整暴露(source_fragment_ids/proof_count) | P2-1 | P2 |
| 矛盾检测阈值调整 + 更正历史确保 | P2-2/3 | P2 |
| DispositionProfile 7 维权重注入 recall 流程 | G-6 | P1 |

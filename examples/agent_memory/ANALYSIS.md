# Agent Memory 验证案例深度分析报告

> 日期: 2026-05-06
> 方法: 运行全部 8 组验证 → 逐轨迹分析状态转换 → 交叉比对设计文档与实现代码

---

## 一、运行结果总览

| 验证组 | 通过率 | 关键低分轨迹 | 核心问题 |
|--------|:------:|-------------|---------|
| 01_ingestion | 8/8 | T1 score=0.70 (recall_hits=0) | 向量检索降级，recall 无精确匹配 |
| 02_contradiction | 7/7 | T1 score=0.33 (insights=0) | 规则矛盾检测只发现1个矛盾 |
| 03_consolidation | 8/8 | T1/T4/T5/T6/T7 score=0.50 | 巩固 consolidated=0，编译 summary_len=0 |
| 04_locomo | 10/10 | T1/T2/T3 score=0.50 | 向量检索降级，无法精确召回 |
| 05_lifecycle | 8/8 | T1 score=0.67 (recall=False) | recall 降级 |
| 06_full_agent | 5/8 | T1/T3/T4 FAIL | 编译层 AttributeError，recall 降级 |
| 07_modeling | 8/8 | 全部 score=1.0 | 最稳定的验证组 |
| 08_qul | 8/8 | T1 score=0.25, T3 score=0.50 | QUL 只检测英文时间约束 |

---

## 二、逐模块深度分析

### 2.1 记忆摄取管线 (01_ingestion)

**设计预期** (V-API-1): remember 6步编排链：DeduplicationGate → Ingestion → Extraction → EntityResolver → Layer-S写入 → 可选Consolidation

**实际行为**:
- ✅ T2 DeduplicationGate: 完全相同内容 → 复用同一 node_id，工作正常
- ✅ T3/T4 Entity Resolution: L1 精确匹配复用，L2 trigram 模糊匹配创建新节点
- ⚠️ T1 recall_hits=0: remember 成功写入 Layer-S（图存储），但 recall 无法通过语义检索找到刚写入的内容

**根因**: 向量索引默认 provider="bm25"，BM25 冷启动后 `_total_docs=0` 触发重建，但重建只索引前 5000 节点。且中文子串匹配几乎无效。

**复杂度评估**: 中等。缺少的验证点：
- 跨 memory_type 的去重（如 entity 和 observation 内容相同）
- L3 LLM 实体消歧验证
- 并发写入冲突

### 2.2 矛盾检测与信念修订 (02_contradiction)

**设计预期** (V-REF-7): 混合矛盾检测 = Phase A 规则层(<100ms, 无LLM) + Phase B 搜索循环(需LLM) + Phase C 合并去重 + Phase D 后续动作

**实际行为**:
- ⚠️ T1 score=0.33: 规则矛盾检测只发现 1 个矛盾（否定模式 "不是D级" vs "D级"），但 insights=0
- ✅ T2 score=0.67: LLM 语义矛盾检测发现 2 个矛盾
- ✅ T6: Reflect 搜索序列验证，contradictions=3, insights=1

**关键发现**: 规则矛盾检测的否定模式匹配已修复（限制贪婪捕获），但 insights 生成条件仍然严格——需要 `iteration >= len(type_priority) - 1` 且 `len(all_results) > 0`。当 max_iterations=2 时，第 2 轮（index=1）才满足条件，但此时 type_priority 长度为 3，`1 >= 2` 为 False，所以 insights 不生成。

**复杂度评估**: 中等。缺少的验证点：
- 7 条信念修正规则引擎的逐条验证
- 更正传播 BFS 深度验证（当前只验证了传播发生，未验证传播深度）
- 信念状态转换完整链路（accepted→pending_review→accepted/rejected/superseded）

### 2.3 巩固与编译 (03_consolidation)

**设计预期** (V-CON-1): 三动作模型 Create/Update/Delete + 双通道证据追踪

**实际行为**:
- ⚠️ T1 consolidated=0: 巩固引擎没有创建新节点。原因是 `_find_related_observations` 使用交集匹配，返回已有节点，碎片被追加到已有 observation 而非创建新的
- ⚠️ T5/T6 summary_len=0: 编译层存在已知 bug——EntityPage 缺少 `related_observations` 属性，MemoryAPI 引用会抛 AttributeError，被 try/except 捕获后返回空结果
- ⚠️ T7 audit_entries=0: 巩固后没有产生 superseded/rejected 节点，audit trail 为空

**关键发现（实现偏差）**:
1. **Update 动作 proof_count 只 +1** 而非设计文档要求的 `+len(new_source_fragments)`，导致证据计数失真
2. **编译摘要是简单 `|` 拼接** 而非 LLM 生成的结构化摘要
3. **related 节点无相关性过滤**，只是取 space 下前 20 个 observation
4. **Tag 隔离使用交集匹配** 而非严格匹配，可能泄漏跨 tag 组信息

**复杂度评估**: 低。缺少的验证点：
- 巩固三动作模型（Create/Update/Delete）的独立验证
- 双通道证据追踪（source_fragment_ids + CONSOLIDATED_INTO 边）
- 自适应分批折半重试
- 乐观并发控制（version 字段）
- Schema 对齐评分 0.7 阈值

### 2.4 LOCOMO 综合评估 (04_locomo)

**设计预期**: 四维度评估（单跳/多跳/时序/矛盾）+ 巩固/遗忘/DreamCycle/更正传播

**实际行为**:
- ⚠️ T1 found_shenzhen=False: 单跳召回无法找到精确内容
- ⚠️ T2 cloud=False, k8s=False: 多跳推理无法关联跨实体信息
- ⚠️ T3 has_latest=False: 时序推理无法找到最新策略
- ⚠️ T5 consolidated=0: 巩固未产生新节点
- ⚠️ 遗忘时出现大量 "Node has connected edges" 错误

**关键发现（实现偏差）**:
1. **Analytical 查询直接返回空列表** (`rrf_fusion.py:128-129`)，导致分析型查询永远无结果
2. **Layer-S 只查 entity 类型**，不查 observation/mental_model
3. **Layer-R 无相关性排序降级**，只返回前 N 个节点
4. **BM25 降级为子串匹配**，对中文几乎无效
5. **遗忘硬删除不处理连接边**，导致 KuzuDB 报错

**复杂度评估**: 中等。缺少的验证点：
- RRF 四路融合权重验证
- Embedding 四级降级验证
- 可见性（private/shared/public）的访问控制验证
- Token 预算限制验证

### 2.5 建模对象与权限 (07_modeling)

**设计预期** (V-MOD-1~11): 四建模对象 × 四认知层正交分类 + model_domain 权限治理

**实际行为**:
- ✅ 全部 score=1.0，最稳定的验证组
- T5 list-my-memories: memories=5，用户过滤工作正常
- T6 权限治理: domains_created=4/4，model_domain 写入正常

**复杂度评估**: 低。缺少的验证点：
- DispositionProfile 7 维度权重计算验证
- User Model 渐进更新（仅高置信信号才更新）
- Task Model commitment 状态转换（pending→fulfilled/overdue/cancelled）
- World Model constraint 动态环境感知
- Self Model 暂定假设（Working Hypothesis）
- 跨 model_domain 的权限隔离验证（用户能否修改 World Model）

### 2.6 QUL 与生命周期 (08_qul)

**设计预期** (V-QUL-1~5): 规则层约束提取(<10ms) + 约束→检索策略映射 + 约束驱动重排序

**实际行为**:
- ⚠️ T1 score=0.25: 只检测到 1/4 的约束，因为 `extract_temporal_constraint` 只支持英文时间模式
- ⚠️ T3 score=0.50: 自动上下文加载 recall_hits=0
- ⚠️ T8 score=0.50: E2E 交叉验证 reflect=False, insights=0

**关键发现（实现偏差）**:
1. **QUL 设计文档定义了 8 种约束类型**，实现只有 1 种（temporal 英文模式）
2. **QueryUnderstandingLayer 类不存在**，只有孤立的 `extract_temporal_constraint` 函数
3. **约束驱动重排序未实现**，recall 流程完全跳过 QUL 步骤
4. **自动上下文加载未实现**（活跃任务+用户模型+待履行承诺）

**复杂度评估**: 低。缺少的验证点：
- 7 种约束类型→检索策略映射验证
- 约束驱动重排序（model_domain/memory_type/scope 三维 boost）
- 延迟预算验证（规则层<65ms, LLM层<565ms）
- 记忆强度 5 因子模型验证

---

## 三、关键实现偏差汇总

| # | 严重度 | 模块 | 偏差描述 | 设计文档位置 |
|---|--------|------|---------|-------------|
| 1 | **BUG** | Compilation | EntityPage 缺 `related_observations`，TopicPage 缺 `key_findings`/`open_questions` | §LC-10 |
| 2 | **严重** | Recall | analytical 查询直接返回空列表 | §14.2 |
| 3 | **严重** | QUL | 设计 8 种约束类型，实现只有 1 种英文 temporal | §QUL-1 |
| 4 | **严重** | Forgetting | confirmation_count 永远为 0，0.15 权重因子失效 | §LC-3 |
| 5 | **严重** | Forgetting | decay_strength 用 strength 自身作为 memory_value，正反馈循环 | §LC-4 |
| 6 | **中等** | Consolidation | Update proof_count 只 +1 而非 +len(new_source_fragments) | §CON-2 |
| 7 | **中等** | Consolidation | Tag 隔离用交集匹配而非严格匹配 | §CON |
| 8 | **中等** | Forgetting | 硬删除不处理连接边，导致悬空引用 | §LC-5 |
| 9 | **中等** | Compilation | 摘要是简单拼接而非 LLM 生成，related 节点无相关性过滤 | §LC-10 |
| 10 | **低** | Consolidation | `_generate_uuid5` 使用 MD5 而非 UUID5 | §CON-1 |
| 11 | **低** | Consolidation | Delete 动作双重写入（update_node + transition_belief） | §CON-1 |

---

## 四、复杂度评估与薄弱验证点

### 复杂度评分

| 验证组 | 当前复杂度 | 目标复杂度 | 差距 |
|--------|:---------:|:---------:|------|
| 01_ingestion | ★★☆☆☆ | ★★★★☆ | 缺 L3 消歧、并发冲突 |
| 02_contradiction | ★★★☆☆ | ★★★★☆ | 缺信念状态完整链路 |
| 03_consolidation | ★★☆☆☆ | ★★★★★ | 缺三动作独立验证、证据追踪 |
| 04_locomo | ★★★☆☆ | ★★★★☆ | 缺 RRF 权重、可见性控制 |
| 05_lifecycle | ★★★☆☆ | ★★★★☆ | 缺 5 因子模型验证 |
| 06_full_agent | ★★☆☆☆ | ★★★★☆ | 编译 bug 阻塞 |
| 07_modeling | ★★☆☆☆ | ★★★★★ | 缺 DispositionProfile、权限隔离 |
| 08_qul | ★★☆☆☆ | ★★★★★ | 缺约束类型、重排序 |

### 最薄弱的 5 个验证点

1. **巩固三动作模型** (V-CON-1): 当前只验证了"巩固后节点数增加"，未验证 Create/Update/Delete 各自的行为
2. **记忆强度 5 因子模型** (V-LC-3): 当前完全未验证，confirmation 因子失效
3. **QUL 约束驱动检索** (V-QUL-3/4/5): 当前只验证了时间约束提取，未验证约束→策略映射和重排序
4. **DispositionProfile 7 维权重** (V-HIE-9): 当前完全未验证
5. **编译层结构化输出** (V-LC-10): 当前因 AttributeError 无法验证

---

## 五、建议优先修复项（实现代码层面）

> 注：本次仅分析不改实现代码，以下为后续修复建议

1. **P0**: 修复 EntityPage/TopicPage 属性缺失（#1 BUG）
2. **P0**: 移除 analytical 查询短路返回空列表（#2）
3. **P1**: 实现 QUL 完整约束提取（中文支持 + 8 种约束类型）（#3）
4. **P1**: 修复 confirmation_count 传入和 decay_strength 正反馈循环（#4, #5）
5. **P2**: 修复 Consolidation proof_count 和 Tag 隔离（#6, #7）
6. **P2**: 修复遗忘硬删除级联边处理（#8）

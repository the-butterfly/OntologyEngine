# 记忆层次设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

---

## 目的

定义 OntologyEngine 记忆的双层存储 + 认知分层 + memory_type 类型标签架构，以及统一的 CognitiveNode 数据模型。

## 设计原则

1. **Layer-R 和 Layer-S 的本质差异是存储范式**（向量优先 vs 图优先），不是认知层次
2. **认知分层通过 cognitive_layer 字段实现**（perception/semantic/opinion/procedure），不独立建表
3. **Observation、Opinion、Mental Model、Episode、Procedure 的差异是语义和生命周期差异**，用 memory_type 区分
4. **巩固 = 类型升级 + 编译产物生成**：fragment → observation → entity → mental_model，在同层内完成
5. **共享字段统一建表，核心字段强类型，类型特有字段存为 JSON attributes**
6. **消除影子节点**：CognitiveNode 统一替代 EntityNode + MemoryUnitNode(MAPPED_TO) 的双节点模式

---

## 1. 双层存储架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer-R: KnowledgeFragment（原始碎片）                            │
│  存储: ChromaDB 向量优先 + KuzuDB 知识碎片节点                      │
│  memory_type: fragment                                            │
│  cognitive_layer: perception                                      │
│  特征: 向量检索为主，原文证据，不可推理                                │
│  生命周期: 创建 → 关联 → 巩固升级为 observation → 或归档/遗忘        │
├──────────────────────────────────────────────────────────────────┤
│  Layer-S: CognitiveNode（统一认知节点）                             │
│  存储: KuzuDB 图优先 + ChromaDB 向量索引                            │
│  cognitive_layer: semantic | opinion | procedure                  │
│  memory_type: entity | observation | opinion | mental_model |    │
│               episode | procedure | rule                          │
│  特征: 图遍历 + 向量检索，可推理，有结构                              │
│  生命周期: 创建 → 类型升级/降级 → 编译/巩固/遗忘 → 归档              │
└──────────────────────────────────────────────────────────────────┘
```

### 1.1 为什么保持双层而非合并为单层

| 维度 | Layer-R (fragment) | Layer-S (CognitiveNode) |
|------|-------------------|---------------------|
| **存储范式** | 向量优先（ChromaDB 主存储） | 图优先（KuzuDB 主存储） |
| **检索方式** | 语义相似度为主 | 图遍历 + Bundle Search + 向量 |
| **数据结构** | 自由文本 + 元数据 | 类型化节点 + 边 + 属性 |
| **推理能力** | 无 | 有（规则执行、路径查询） |
| **Schema 约束** | 无 | 有（entity/rule 受 Schema 约束） |

这两者的存储范式差异是根本性的，不适合合并。

### 1.2 认知分层（cognitive_layer）

> **[关键设计点]**：cognitive_layer 是逻辑分区字段，不是物理分层。通过 KuzuDB 索引实现高效查询。

| cognitive_layer | 包含的 memory_type | 语义 | 检索优先级 |
|----------------|-------------------|------|-----------|
| perception | fragment, self_experience | 原始感知碎片 + Agent 自我经验 | 最低（兜底） |
| semantic | entity, rule, task_state | 结构化语义知识 + 任务状态 | 中 |
| opinion | observation, opinion, mental_model, commitment | 归纳观点 + 承诺 | 最高（短路优先） |
| procedure | episode, procedure, constraint | 经验与操作模式 + 环境约束 | 中 |

认知分层的核心价值：
- **分层漏斗检索**：opinion 层优先返回，perception 层兜底
- **巩固方向明确**：perception → semantic → opinion 是知识提炼方向
- **Agent认知负担低**：4层比7种memory_type更容易理解

---

## 2. CognitiveNode 统一数据模型

> **[关键设计点]**：CognitiveNode 替代原 MemoryUnitNode + EntityNode(MAPPED_TO 影子节点)。
> 消除影子节点的同步开销和数据不一致风险。

### 2.1 核心字段

```yaml
CognitiveNode:
  id: string                      # UUID5 确定性生成
  space_id: string                # 所属语义空间
  cognitive_layer: string         # perception | semantic | opinion | procedure
  memory_type: string             # entity | observation | opinion | mental_model | episode | procedure | rule | fragment
  entity_name: string             # 强类型列——实体显示名称
  entity_type: string             # 强类型列——实体类型标识
  schema_ref: string              # 强类型列——引用 Schema L1 EntityDeclaration.name
  text: string                    # 核心文本内容
  tags: [string]                  # 标签（隔离、分类、巩固分组）

  # 证据追踪
  proof_count: integer = 1        # 支撑此知识的证据数量
  source_fragment_ids: string[]   # 支撑此知识的碎片 ID 数组
  history: string                 # JSONB 变更历史（内联快照）

  # 记忆强度
  strength: float = 1.0           # 记忆强度 [0, 1]
  feedback_weight: float = 0.5    # 反馈权重 [0, 1]
  access_count: integer = 0       # 访问次数

  # 信念与可见性
  belief_status: string = 'accepted'  # accepted | pending_review | rejected | superseded
  visibility: string = 'shared'       # private | shared | public

  # 双时序字段
  valid_from: datetime?           # 事实有效起始时间（T）
  valid_to: datetime?             # 事实有效终止时间（T）
  recorded_at: datetime?          # 系统记录时间（T'）——区分"何时发生"与"何时知晓"
  occurred_at: datetime?          # 事件实际发生时间

  # 编译与更正
  compiled_at: datetime?          # 编译产物编译时间
  superseded_by: string?          # 被哪条记忆取代

  # 并发控制
  version: integer = 1            # 乐观并发控制版本号

  # 置信度
  confidence: float = 1.0         # 置信度 [0, 1]

  # 四建模对象 [新增]
  model_domain: string?           # user | task | world | self

  # 来源可信层级 [新增]
  source_trust_tier: string?      # user_declared | behavior_inferred | environment_observed | agent_generated

  # 作用域 [新增]
  scope: string?                  # JSON: {"type": "task|user|global", "ref_id": "...", "window": "..."}

  # 确认时间 [新增]
  last_confirmed_at: datetime?    # 上次被后续证据确认的时间

  # 推理轨迹 [新增]
  consolidation_reasoning: string? # LLM 归纳时的推理摘要

  # 类型特有字段
  attributes: MAP(STRING, STRING)    # 类型特有字段，见下文

  # 元数据
  source_pipeline: string?
  source_content_hash: string?
  created_at: datetime
  updated_at: datetime
  consolidated_at: datetime?      # 巩固时间
```

### 2.2 与原设计的对比

| 维度 | 原设计（MemoryUnitNode + EntityNode） | 新设计（CognitiveNode） |
|------|--------------------------------------|----------------------|
| 节点数 | 2（影子节点对） | 1（统一节点） |
| 同步开销 | MAPPED_TO 边同步 | 无 |
| 数据一致性 | 双节点可能不一致 | 单节点，天然一致 |
| 强类型字段 | EntityNode 有，MemoryUnitNode 无 | 核心字段强类型（entity_name, entity_type, schema_ref） |
| 认知分层 | 无 | cognitive_layer 字段 |
| 双时序 | 无 recorded_at | 有 recorded_at (T') |
| 信念状态 | 无 | belief_status |
| 可见性 | 无 | visibility |
| 并发控制 | 无 | version (OCC) |
| 编译标记 | 无 | compiled_at |
| 建模对象 | 无 | model_domain |
| 来源可信层级 | 无 | source_trust_tier |
| 作用域 | 无 | scope |
| 确认时间 | 无 | last_confirmed_at |
| 推理轨迹 | 无 | consolidation_reasoning |

### 2.3 类型特有字段（attributes MAP）

#### observation 特有字段

```json
{
  "fact_type": "world | experience",
  "consolidation_batch_id": "batch_001",
  "source_fragment_ids": ["frag_001", "frag_002"]
}
```

#### opinion 特有字段 [新增]

> **[关键设计点]**：opinion 与 observation 区分。observation 是归纳性事实，opinion 是主观判断/推测。

```json
{
  "opinion_type": "judgment | speculation | recommendation",
  "confidence_basis": "evidence | intuition | authority",
  "review_required": true,
  "reviewer_id": "user_001"
}
```

#### mental_model 特有字段

```json
{
  "name": "Company A Risk Summary",
  "query_pattern": "risk level of Company A",
  "scope": "personal | team | organization",
  "shared": false,
  "is_stale": false,
  "last_refreshed_at": "2026-04-25T10:00:00Z",
  "source_entity_ids": ["ent_001", "ent_002"],
  "source_observation_ids": ["obs_001"]
}
```

#### episode 特有字段

```json
{
  "title": "Risk Assessment for Company A",
  "description": "User requested risk assessment...",
  "outcome": "Completed with D grade",
  "lessons_learned": ["Need more financial data"],
  "participants": ["agent_001", "user_001"],
  "success": true,
  "duration_minutes": 15,
  "related_entity_ids": ["ent_001"]
}
```

#### procedure 特有字段

```json
{
  "name": "Risk Assessment Procedure",
  "precondition": "Entity has financial data",
  "steps": [
    {"order": 1, "action": "Query financial metrics", "tool": "oe_recall"},
    {"order": 2, "action": "Execute risk rule", "tool": "oe_execute_rule"},
    {"order": 3, "action": "Summarize result", "tool": "reflect"}
  ],
  "postcondition": "Risk grade assigned",
  "invocation_count": 12,
  "success_count": 10,
  "success_rate": 0.83,
  "last_used_at": "2026-04-24T15:00:00Z",
  "source_episode_ids": ["ep_001", "ep_003"]
}
```

#### entity 特有字段

```json
{
  "identity_fields": {"name": "Company A", "unified_code": "91110000MA01XXXX"},
  "version_reason": "Q4 financial data update"
}
```

#### rule 特有字段

```json
{
  "rule_logic": "IF debt_ratio > 0.7 THEN grade = 'D'",
  "priority": 100,
  "is_active": true
}
```

#### commitment 特有字段 [新增]

```json
{
  "deadline": "2026-05-15T10:00:00Z",
  "status": "pending | fulfilled | overdue | cancelled",
  "task_id": "task_001",
  "fulfilled_by": "ep_001",
  "reminder_sent": false
}
```

#### constraint 特有字段 [新增]

```json
{
  "constraint_type": "api_limit | business_rule | technical_boundary",
  "enforceable": true,
  "violation_action": "warn | block | log",
  "affected_memory_types": ["observation", "opinion"]
}
```

#### self_experience 特有字段 [新增]

```json
{
  "tool_name": "oe_execute_rule",
  "call_result": "success | timeout | error | rate_limited",
  "error_type": "network | validation | internal",
  "latency_ms": 1250,
  "retry_count": 2,
  "context_summary": "Rule R-101 evaluation on Company A",
  "lesson": "Pre-validate entity attributes before rule execution"
}
```

#### task_state 特有字段 [新增]

```json
{
  "task_id": "task_001",
  "task_name": "Risk Assessment for Company A",
  "current_phase": "data_collection | analysis | reporting | review",
  "decision_log": [
    {"decision": "reject_microservices", "reason": "user_preference", "timestamp": "2026-04-20T10:00:00Z"}
  ],
  "artifact_versions": [
    {"artifact_id": "report_001", "version": "v1.2", "created_at": "2026-04-25T10:00:00Z"}
  ],
  "pending_commitments": ["commit_001", "commit_002"]
}
```

---

## 3. KuzuDB 存储

> 详细 DDL 见 `docs/02-design/storage/kuzudb-schema.md`。

### 3.1 CognitiveNode 表

```cypher
CREATE NODE TABLE CognitiveNode (
    id                STRING PRIMARY KEY,
    space_id          STRING,
    cognitive_layer   STRING,
    memory_type       STRING,
    entity_name       STRING,
    entity_type       STRING,
    schema_ref        STRING,
    text              STRING,
    tags              STRING[],
    attributes        MAP(STRING, STRING),
    version           INT64 DEFAULT 1,
    confidence        DOUBLE DEFAULT 1.0,
    strength          DOUBLE DEFAULT 1.0,
    feedback_weight   DOUBLE DEFAULT 0.5,
    proof_count       INT64 DEFAULT 1,
    source_fragment_ids STRING[],
    history           STRING,
    access_count      INT64 DEFAULT 0,
    belief_status     STRING DEFAULT 'accepted',
    visibility        STRING DEFAULT 'shared',
    valid_from        DATETIME,
    valid_to          DATETIME,
    recorded_at       DATETIME,
    occurred_at       DATETIME,
    compiled_at       DATETIME,
    superseded_by     STRING,
    source_pipeline   STRING,
    source_content_hash STRING,
    model_domain      STRING,
    source_trust_tier STRING,
    scope             STRING,
    last_confirmed_at DATETIME,
    consolidation_reasoning STRING,
    created_at        DATETIME,
    updated_at        DATETIME,
    consolidated_at   DATETIME
)
```

### 3.2 认知关系边

| 边类型 | 方向 | 语义 |
|--------|------|------|
| COGNITIVE_RELATES_TO | CognitiveNode → CognitiveNode | 业务关系 |
| SUPERSEDES | CognitiveNode → CognitiveNode | 更正链（新取代旧） |
| CONTRADICTS | CognitiveNode → CognitiveNode | 矛盾链 |
| CONSOLIDATED_INTO | KnowledgeFragmentNode → CognitiveNode | 碎片归纳 |
| SUMMARIZED_AS | CognitiveNode → CognitiveNode | 实体摘要为高层洞察 |
| LEARNED_INTO | CognitiveNode → CognitiveNode | 经验归纳为操作模式 |
| FULFILLED_BY | CognitiveNode → CognitiveNode | 承诺履行记录 |
| LIMITS | CognitiveNode → CognitiveNode | 约束限制观察范围 |
| INFORMS | CognitiveNode → CognitiveNode | 自我经验指导操作模式 |
| ALIGNED_WITH | CognitiveNode → EntityNode | Phase 1 过渡关联 |

### 3.3 Phase 1 过渡方案

```
Phase 1（当前）:
  CognitiveNode (新增) ←──ALIGNED_WITH──→ EntityNode (保留)
  
  写入路径：
    新代码 → 写入 CognitiveNode + ALIGNED_WITH → EntityNode
    旧代码 → 写入 EntityNode → 触发同步创建 CognitiveNode
  
  读取路径：
    优先从 CognitiveNode 读取
    CognitiveNode 缺失时回退到 EntityNode

Phase 2（验证后）:
  EntityNode 废弃，ALIGNED_WITH 边删除
```

---

## 4. ChromaDB 存储

### 4.1 统一 cognitive_node_text 集合

```
Collection: "cognitive_node_text"

每条记录:
  id: cognitive_node_id
  embedding: text 的向量嵌入
  metadata: {
    space_id: string,
    cognitive_layer: string,
    memory_type: string,
    model_domain: string,
    belief_status: string,
    proof_count: int,
    strength: float,
    confidence: float,
    source_trust_tier: string,
    tags: list[str]
  }
```

### 4.2 DispositionProfile 驱动动态权重

> **[关键设计点]**：类型权重不再是静态值，而是由 DispositionProfile 动态调整。

```python
BASE_TYPE_WEIGHTS = {
    "mental_model": 3.0,
    "opinion": 2.5,
    "entity": 2.0,
    "rule": 2.0,
    "commitment": 1.9,
    "constraint": 1.8,
    "procedure": 1.8,
    "task_state": 1.6,
    "observation": 1.5,
    "episode": 1.2,
    "self_experience": 1.1,
    "fragment": 1.0
}

def apply_dynamic_weight(rrf_score, memory_type, disposition):
    base = BASE_TYPE_WEIGHTS.get(memory_type, 1.0)
    
    if disposition.abstraction_preference > 0.7:
        layer_boost = {"mental_model": 1.5, "opinion": 1.3, "observation": 0.8, "fragment": 0.5}
    elif disposition.abstraction_preference < 0.3:
        layer_boost = {"mental_model": 0.7, "opinion": 0.8, "observation": 1.2, "fragment": 1.5}
    else:
        layer_boost = {}
    
    if disposition.thoroughness > 0.7:
        thoroughness_boost = {"fragment": 1.2, "observation": 1.1}
    else:
        thoroughness_boost = {}
    
    dynamic = base * layer_boost.get(memory_type, 1.0) * thoroughness_boost.get(memory_type, 1.0)
    return rrf_score * dynamic
```

### 4.3 DispositionProfile 定义

> **[关键设计点]**：7维度合并，同时覆盖Agent交互风格和知识工程视角。
> empathy/risk_tolerance 影响 Agent 交互风格，thoroughness/recency_bias 影响检索消费行为。

```yaml
DispositionProfile:
  skepticism: float = 0.5              # [0.3, 0.9] 对矛盾信息的敏感度
  evidence_demand: float = 0.5         # [0.3, 0.9] 证据要求程度
  abstraction_preference: float = 0.5  # [0.2, 0.8] 抽象偏好（高层摘要 vs 底层碎片）
  thoroughness: float = 0.5            # [0.2, 0.8] 检索彻底性（影响漏斗层数和结果数量）
  recency_bias: float = 0.5            # [0.2, 0.8] 时效偏好（新信息 vs 历史稳定信息）
  empathy: float = 0.5                 # [0.2, 0.8] 共情偏好（影响Agent交互风格）
  risk_tolerance: float = 0.5          # [0.2, 0.8] 风险容忍度（影响Agent决策风格）
```

**维度对检索消费的影响**：

| 维度 | 影响的检索环节 | 具体影响 |
|------|---------------|---------|
| skepticism | 矛盾检测 | 高skepticism→降低mental_model权重，增加entity权重 |
| evidence_demand | 短路策略+证据展开 | 高evidence_demand→禁止短路，要求全层检索+证据链展开 |
| abstraction_preference | 分层漏斗权重 | 高→mental_model权重×1.5, fragment×0.5；低→反转 |
| thoroughness | 检索深度+结果数量 | 高thoroughness→增加top_k，遍历更多层，不短路 |
| recency_bias | 时序排序 | 高recency_bias→优先返回recorded_at最近的结果 |
| empathy | 回答生成策略 | 高→共情表达+模糊查询推断+降级时提供替代结果 |
| risk_tolerance | 置信度过滤+治理策略 | 低→min_confidence=0.8+严格晋升条件；高→min_confidence=0.3+宽松晋升条件 |

**安全边界**：

| 维度 | 最小值 | 最大值 | 说明 |
|------|--------|--------|------|
| skepticism | 0.3 | 0.9 | 过低会传播错误信息，过高会拒绝所有信息 |
| evidence_demand | 0.3 | 0.9 | 过低会接受无证据结论，过高会无法得出结论 |
| abstraction_preference | 0.2 | 0.8 | 过低会返回过多碎片，过高会遗漏细节 |
| thoroughness | 0.2 | 0.8 | 过低会遗漏重要结果，过高会返回过多噪音 |
| recency_bias | 0.2 | 0.8 | 过低会忽略最新变化，过高会丢弃稳定历史信息 |
| empathy | 0.2 | 0.8 | 高→共情表达+模糊查询推断+降级时提供替代；低→简洁客观 |
| risk_tolerance | 0.2 | 0.8 | 低→min_confidence=0.8+严格晋升；高→min_confidence=0.3+宽松晋升 |

**场景强制覆盖**：

| 场景 | 强制设置 | 原因 |
|------|---------|------|
| 审计/合规 | evidence_demand=1.0, skepticism=0.9, thoroughness=0.8 | 必须全层检索，禁止短路，彻底搜索 |
| 快速回答 | abstraction_preference=0.8, thoroughness=0.3 | 允许短路，优先返回摘要，减少结果数 |
| 实时监控 | recency_bias=0.9, evidence_demand=0.7 | 优先最新信息，适度证据要求 |

**初始化策略**：

| 方式 | 说明 |
|------|------|
| 行业模板 | 金融：skepticism=0.7, evidence_demand=0.8；客服：empathy=0.8 |
| 行为学习 | 根据用户反馈（检索结果评分→权重更新）持续调整 |
| 审计日志 | Disposition 变更记录审计日志 |

---

## 5. 类型升级与降级

### 5.1 升级路径

```
fragment ──[ConsolidationEngine]──▶ observation ──[Schema对齐]──▶ entity ──[ReflectAgent]──▶ mental_model
fragment ──[ConsolidationEngine]──▶ opinion ──[人工确认]──▶ entity
episode ──[ConsolidationEngine]──▶ procedure
```

### 5.2 升级操作

```python
async def upgrade_memory(node_id, new_type, new_layer, additional_attrs=None):
    node = await get_cognitive_node(node_id)
    
    old_type = node.memory_type
    node.memory_type = new_type
    node.cognitive_layer = new_layer
    node.attributes.update(additional_attrs or {})
    node.consolidated_at = datetime.utcnow()
    node.version += 1

    await update_cognitive_node(node)

    await create_type_edge(
        from_id=node_id,
        to_id=node_id,
        edge_type=get_upgrade_edge(old_type, new_type)
    )
```

### 5.3 降级路径

遗忘机制触发降级：

```
mental_model → entity → observation → fragment → archived → deleted
```

降级条件：
- strength < 0.3 → 降一级
- strength < 0.1 → 归档
- strength < 0.01 且 proof_count == 0 → 删除
- feedback_weight >= 0.9 → 永不遗忘

### 5.4 信念状态变更

```
accepted ──[矛盾检测]──▶ pending_review ──[人工确认]──▶ accepted
                                              ├──[人工拒绝]──▶ rejected
                                              └──[人工修改]──▶ accepted (modified)

accepted ──[更正写入]──▶ superseded (superseded_by 指向新版本)
superseded ──[更正撤销]──▶ accepted (superseded_by 清空)

pending_review ──[超时未审+confidence>0.9]──▶ accepted (自动晋升)
rejected ──[重新提交]──▶ pending_review
```

---

## 6. 检索优先级

### 6.1 分层漏斗检索

> **[关键设计点]**：分层漏斗是主流程，查询类型是内部检索策略参数。

```
查询输入
  ↓
第1层：opinion（mental_model, opinion）
  ├── 命中且 confidence ≥ 阈值 → 场景允许短路 → 返回
  └── 未命中或 confidence < 阈值 → 继续
  ↓
第2层：semantic（entity, rule）
  ├── 命中 → 返回
  └── 未命中 → 继续
  ↓
第3层：procedure（episode, procedure）
  ├── 命中 → 返回
  └── 未命中 → 继续
  ↓
第4层：perception（fragment）—— 兜底
  └── 总有结果
```

### 6.2 场景感知短路策略

| 场景 | 短路行为 | 原因 |
|------|---------|------|
| 快速回答（abstraction_preference > 0.7） | 允许短路 | 用户需要快速摘要 |
| 审计/合规（evidence_demand > 0.8） | 禁止短路 | 必须全层检索 |
| 默认 | 短路后异步验证 | 平衡速度与准确性 |

### 6.3 冷启动降级策略

```
空知识库场景：
  第1层 opinion → miss
  第2层 semantic → miss
  第3层 procedure → miss
  第4层 perception → miss（无数据）

降级：回退到并行池检索（ChromaDB 全量向量搜索）
  → 返回所有相关碎片，不做类型权重排序
  → 用户体验：碎片化但至少有结果
```

### 6.4 DispositionProfile 存储

```cypher
CREATE NODE TABLE DispositionProfileNode (
    id          STRING PRIMARY KEY,
    space_id    STRING,
    profile_name STRING,
    skepticism  DOUBLE DEFAULT 0.5,
    evidence_demand DOUBLE DEFAULT 0.5,
    abstraction_preference DOUBLE DEFAULT 0.5,
    thoroughness DOUBLE DEFAULT 0.5,
    recency_bias DOUBLE DEFAULT 0.5,
    empathy     DOUBLE DEFAULT 0.5,
    risk_tolerance DOUBLE DEFAULT 0.5,
    is_default  BOOLEAN DEFAULT false,
    created_at  DATETIME,
    updated_at  DATETIME
)
```

---

## 7. 与现有 Schema 的兼容性

### 7.1 不修改现有 Schema v2

cognitive_layer 和 memory_type 是 Layer-S 内部的组织方式，不影响 L1-L4 声明。现有 Schema YAML 无需变更。

### 7.2 互索引边扩展

| 边类型 | 方向 | 语义 |
|--------|------|------|
| COG_EXTRACTED_FROM | CognitiveNode → KnowledgeFragmentNode | 认知节点溯源到碎片 |
| COG_SUPPORTED_BY | KnowledgeFragmentNode → CognitiveNode | 碎片支撑认知节点 |
| CONSOLIDATED_INTO | KnowledgeFragmentNode → CognitiveNode | 碎片归纳为认知节点 |
| SUMMARIZED_AS | CognitiveNode → CognitiveNode | 实体摘要为高层洞察 |
| LEARNED_INTO | CognitiveNode → CognitiveNode | 经验归纳为操作模式 |
| SUPERSEDES | CognitiveNode → CognitiveNode | 更正链 |
| CONTRADICTS | CognitiveNode → CognitiveNode | 矛盾链 |
| ALIGNED_WITH | CognitiveNode → EntityNode | Phase 1 过渡关联 |

### 7.3 现有互索引边保持不变

EXTRACTED_FROM / SUPPORTED_BY / DEFINED_IN / TRACE_TO 四种边继续用于 EntityNode ↔ KnowledgeFragmentNode 的溯源（Phase 1 兼容）。

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| 知识库流程主文档 | `docs/01-overview/10-kb-process.md` |
| KuzuDB Schema 设计 | `docs/02-design/storage/kuzudb-schema.md` |
| 记忆生命周期设计 | `docs/02-design/agent-memory/memory-lifecycle.md` |
| 认知操作 API 设计 | `docs/02-design/agent-memory/memory-api.md` |
| Schema v2 规范 | `docs/02-design/schema/01-schema-spec.md` |
| 审查辩论文档 | `discuss/2026-04-30-kb-memory-design-adversarial-review.md` |
| 交叉对比分析 | `discuss/2026-04-30-02design-cross-comparison-analysis.md` |
| SOTA 审视报告 | `discuss/2026-04-27-agent-memory-design-analysis.md` |
| 外部批判框架对照 | `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` |

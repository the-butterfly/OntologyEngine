# 认知操作 API 设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-05-04 | **verified_against**: case8(12/12) + case9(8/8)

---

## 目的

定义 OntologyEngine Agent 记忆系统的认知操作 API，以 3 个核心操作覆盖 Agent 的日常记忆交互，保持管理 API 不变。API 采用三层抽象（L1/L2/L3），兼顾简洁性与灵活性。

## 设计原则

1. **Agent 只需记住 3 个动词**：remember / recall / reflect
2. **consolidate 和 forget 是 reflect 的内部流程**，不暴露为独立操作
3. **memory_type 对 Agent 是可选的提示**，不是必须理解的层次
4. **高级用户可通过管理 API 单独调用** consolidate / forget
5. **API 三层抽象**：L1 零配置（Agent 日常）、L2 可选参数（高级 Agent）、L3 完整控制（管理/调试）
6. **reflect 异步编排**：返回 reflection_id，支持进度查询
7. **记忆可见性控制**：支持 private / shared / public 三级可见性

---

## 1. 三操作 vs 五操作

| 方案 | 操作数 | Agent 认知负担 | 覆盖场景 |
|------|--------|-------------|---------|
| 五操作 | remember / recall / reflect / consolidate / forget | 高：需理解何时巩固、何时遗忘 | 完整 |
| **三操作** | remember / recall / reflect | 低：记住、回忆、思考 | 完整（consolidate/forget 自动触发） |

三操作的核心理念：
- **remember** = 存入记忆（自动提取、自动巩固）
- **recall** = 取出记忆（自动路由、自动排序）
- **reflect** = 思考记忆（自动发现矛盾、触发巩固和遗忘）

---

## 2. oe_remember

存储记忆，自动提取实体/关系/事实，可选自动巩固。

```python
@mcp_tool(
    name="oe_remember",
    description=(
        "Store information into the agent's memory. Automatically extracts "
        "entities, relations, and facts. Optionally triggers consolidation "
        "to form higher-level observations. Use this whenever you encounter "
        "important information worth retaining."
    )
)
async def remember(
    content: str = Field(
        description="The content to remember. Text, facts, observations, or any information worth retaining.",
        examples=["Alice works at Google as a senior engineer", "The risk score for Company A is 85"]
    ),
    space_id: str = Field(
        description="The space ID to store the memory in.",
        examples=["space.finance"]
    ),
    tags: list[str] | None = Field(
        default=None,
        description="Optional tags for categorization. Tags enable isolation during consolidation.",
        examples=[["domain:risk", "source:annual_report"]]
    ),
    memory_type: str = Field(
        default="fragment",
        description="Memory type hint. 'fragment' for raw info, 'observation' for consolidated knowledge, 'episode' for experience events, 'commitment' for promises, 'self_experience' for agent tool logs.",
        examples=["fragment", "observation", "episode", "commitment", "self_experience"]
    ),
    metadata: dict | None = Field(
        default=None,
        description="Optional metadata: source, confidence, temporal info, etc.",
        examples=[{"source": "user_input", "confidence": 0.9}]
    ),
    auto_consolidate: bool = Field(
        default=False,
        description="If true, trigger consolidation after storing. Consolidation upgrades fragments to observations."
    )
) -> dict:
    """
    Internal orchestration:
    1. DeduplicationGate.check() → marginal_value assessment + duplicate detection
    2. IngestionService.ingest() → KnowledgeFragment created (Layer-R)
    3. ExtractionPipeline.extract() → entities/relations extracted
    4. EntityResolver.resolve() → entity disambiguation
    5. If memory_type != "fragment": create CognitiveNode directly (Layer-S)
    6. If auto_consolidate: ConsolidationEngine.consolidate()

    [设计决策 2026-05-07] 完整实现双层写入：IngestionService 先创建 Layer-R
    KnowledgeFragment，ExtractionPipeline 从碎片中提取实体/关系，再写入 Layer-S
    CognitiveNode。当前实现合并了 Ingestion+Extraction 为直接创建 CognitiveNode，
    需补齐完整的 6 步编排链。
    """
```

**返回格式**：

```json
{
    "success": true,
    "data": {
        "memory_id": "mu_001",
        "memory_type": "fragment",
        "extracted_entities": ["ent_A", "ent_B"],
        "extracted_relations": ["rel_001"],
        "observations_created": 0,
        "consolidation_triggered": false
    }
}
```

---

## 3. oe_recall

检索记忆，自动路由到最优检索策略，按类型权重排序。

```python
@mcp_tool(
    name="oe_recall",
    description=(
        "Recall information from the agent's memory. Automatically routes "
        "to the best retrieval strategy and prioritizes results by memory "
        "type (summaries > entities > observations > fragments). Returns "
        "relevant memories with evidence chains and confidence scores."
    )
)
async def recall(
    query: str = Field(
        description="The query to search for. A question, keyword, or description.",
        examples=["What is the risk level of Company A?", "guarantee chain for Huawei"]
    ),
    space_id: str = Field(
        description="The space ID to search in.",
        examples=["space.finance"]
    ),
    memory_type: str | None = Field(
        default=None,
        description="Optional type filter: mental_model, opinion, entity, observation, rule, episode, procedure, fragment, commitment, constraint, self_experience, task_state. Auto-searches all types if not specified.",
        examples=["entity", "observation"]
    ),
    max_results: int = Field(
        default=10,
        description="Maximum number of results.",
        examples=[5, 10, 20]
    ),
    include_evidence: bool = Field(
        default=True,
        description="Whether to include evidence chains in results.",
        examples=[true, false]
    ),
    evidence_depth: int = Field(
        default=1,
        description="Evidence chain expansion depth. 1=direct sources only, 2=include sources of sources. L1/L2 default=1, L3 can specify up to 3.",
        examples=[1, 2, 3]
    ),
    as_of: str | None = Field(
        default=None,
        description="Optional point-in-time query (ISO 8601 date).",
        examples=["2024-12-31"]
    ),
    token_budget: int | None = Field(
        default=None,
        description="Optional token budget for results.",
        examples=[4000, 8000]
    )
) -> dict:
    """
    Internal orchestration:
    1. QueryUnderstandingLayer.extract_constraints(query, task_context)
       → TaskConstraints: user_preference, task_history, temporal_scope, decision_type
    2. If memory_type specified: search only that type
    3. If memory_type not specified: search all types, apply type weights
    4. QueryEngine.query() → TEMPR retrieval + RRF fusion + type weights
    5. DispositionProfile loading: scene override → default fallback → dynamic weights
    6. Task-constraint reranking: boost memories matching current task constraints
    7. Temporal proximity scoring: exp(-0.05 * days) boost
    8. Optional: Cross-Encoder reranking
    9. If include_evidence: expand via cognitive edges
    10. If token_budget: trim results to fit
    """
```

**返回格式**：

```json
{
    "success": true,
    "data": {
        "results": [
            {
                "id": "mu_001",
                "memory_type": "entity",
                "text": "Company A: risk_grade=D, debt_ratio=0.75",
                "confidence": 0.95,
                "strength": 0.85,
                "proof_count": 3,
                "evidence": [
                    {
                        "id": "frag_001",
                        "memory_type": "fragment",
                        "text": "2024年报：资产负债率75%...",
                        "edge_type": "CONSOLIDATED_INTO",
                        "contribution": 0.7
                    }
                ],
                "type_weight": 2.0,
                "rank_score": 1.9
            }
        ],
        "query_type": "factual",
        "total_tokens": 3200
    }
}
```

---

## 4. oe_reflect

反思记忆，主动审视已有知识，发现矛盾，生成新洞察，触发巩固和遗忘。

```python
@mcp_tool(
    name="oe_reflect",
    description=(
        "Reflect on existing memories to discover contradictions, "
        "generate new insights, or update mental models. The system "
        "searches across all memory types by priority, then produces "
        "a reflective analysis. Reflection automatically triggers "
        "consolidation (upgrading fragments to observations) and "
        "forgetting (decaying low-value memories) as needed."
    )
)
async def reflect(
    query: str = Field(
        description="The question or topic to reflect on.",
        examples=["Are there contradictions in Company A's financial data?"]
    ),
    space_id: str = Field(
        description="The space ID to reflect on.",
        examples=["space.finance"]
    ),
    max_iterations: int = Field(
        default=10,
        description="Maximum number of reflection iterations.",
        examples=[5, 10]
    ),
    focus_types: list[str] | None = Field(
        default=None,
        description="Optional focus on specific memory types: mental_model, opinion, entity, observation, rule, episode, procedure, fragment.",
        examples=[["observation", "entity"]]
    )
) -> dict:
    """
    Internal orchestration:
    1. Rule-based contradiction detection (no LLM required):
       - Group by tags → detect negation conflict patterns
       - e.g. "不使用X" vs "使用X", "不是X" vs "X"
    2. ReflectAgent.reflect() → forced retrieval by type priority
       - mental_model → entity → observation → fragment
    3. LLM generates insights, detects contradictions
    4. Merge rule-based + search-based contradictions (dedup)
    5. ArbitrationEngine.arbitrate() → evidence-weighted auto-resolution
       - proof_count × source_trust_tier × recency → belief_status update
    6. New insights → upgrade to observation or mental_model
    7. Contradictions → generate contradiction_report
    8. Belief revision rules applied by priority
    9. Low-value memories → trigger forgetting (strength decay)
    10. Negation-signal forgetting: superseded/rejected → accelerated decay
    11. Unconsolidated fragments → trigger consolidation
    12. Stale mental models → mark for refresh
    13. Correction propagation along cognitive edges
    """
```

**返回格式**：

```json
{
    "success": true,
    "data": {
        "insights": [
            {
                "text": "Company A's debt ratio has been increasing for 3 consecutive quarters",
                "type": "new_insight",
                "memory_id": "mu_new_001",
                "memory_type": "observation",
                "evidence_ids": ["mu_003", "mu_007", "mu_012"]
            }
        ],
        "contradictions": [
            {
                "description": "Company A address differs between CRM and ERP",
                "sources": {
                    "CRM": "朝阳区建国路88号",
                    "ERP": "海淀区中关村大街1号"
                }
            }
        ],
        "consolidation": {
            "fragments_processed": 15,
            "observations_created": 3,
            "observations_updated": 2
        },
        "forgetting": {
            "memories_decayed": 8,
            "memories_archived": 2
        },
        "mental_model_updates": [
            {"model_id": "mu_mm_001", "action": "marked_stale"}
        ],
        "iterations_used": 4,
        "tokens_used": 5600
    }
}
```

---

## 5. 记忆元数据

### 5.1 记忆强度

所有返回记忆的 API 在每条结果中附带 `strength` 字段：

```json
{
    "id": "mu_001",
    "memory_type": "entity",
    "strength": 0.85,
    "strength_breakdown": {
        "recency": 0.9,
        "evidence": 0.8,
        "feedback": 0.85,
        "access_frequency": 0.7
    }
}
```

### 5.2 证据链

当 `include_evidence=true` 时，recall 返回完整证据链：

```json
{
    "id": "mu_001",
    "proof_count": 2,
    "evidence_chain": [
        {
            "id": "frag_001",
            "memory_type": "fragment",
            "text": "2024年报：营收3.2亿...",
            "edge_type": "CONSOLIDATED_INTO",
            "confidence": 1.0,
            "contribution": 0.7
        },
        {
            "id": "frag_002",
            "memory_type": "fragment",
            "text": "征信报告：逾期2次...",
            "edge_type": "CONSOLIDATED_INTO",
            "confidence": 0.85,
            "contribution": 0.3
        }
    ]
}
```

---

## 6. MCP 工具注册

### 6.1 认知操作工具

| 工具名 | 对应操作 | 前置条件 |
|--------|---------|---------|
| `oe_remember` | 存储 | space_id 存在 |
| `oe_recall` | 检索 | space_id 存在且已激活 |
| `oe_reflect` | 反思+巩固+遗忘 | space_id 存在且有记忆 |
| `oe_approve_memory` | 审批 | 待审区有节点 |
| `oe_consolidate` | 手动巩固 | space_id 存在且有碎片 |
| `oe_forget` | 手动遗忘 | space_id 存在且有记忆 |
| `oe_memory_stats` | 统计 | space_id 存在 |
| `oe_memory_types` | 分布 | space_id 存在 |
| `oe_audit_trail` | 审计 | space_id 存在 |
| `oe_get_reflection_status` | 反思进度 | reflection_id 有效 |
| `oe_list_my_memories` | 列出自己的记忆 | space_id 存在，用户已认证 |
| `oe_correct_memory` | 更正记忆 | node_id 存在，用户有权限 |
| `oe_delete_memory` | 删除记忆 | node_id 存在，用户有权限 |
| `oe_record_commitment` | 记录承诺 | space_id 存在 |
| `oe_check_commitments` | 检查承诺 | space_id 存在 |

**实现状态**: ✅ 全部 15 个工具已实现并注册到 [mcp/server.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/mcp/server.py)。

### 6.2 与现有 MCP 工具的关系

```
认知操作工具（Agent 首选）:
  oe_remember  → 内部调用 oe_import_instances + ExtractionPipeline + 可选 ConsolidationEngine
  oe_recall    → 内部调用 oe_query + 类型权重
  oe_reflect   → 内部调用 ReflectAgent + ConsolidationEngine + ForgettingEngine

管理工具（保持不变）:
  oe_create_space, oe_list_spaces, oe_load_schema,
  oe_import_instances, oe_create_entity, oe_define_rule,
  oe_activate_space, oe_execute_rule, oe_simulate,
  oe_query, oe_snapshot, oe_rollback

高级管理工具（新增，供高级用户单独调用）:
  oe_consolidate  → 单独触发巩固
  oe_forget       → 单独触发遗忘
```

---

## 7. REST API 端点

### 7.1 认知操作端点

| 方法 | 端点 | 对应操作 |
|------|------|---------|
| POST | `/v1/spaces/{space_id}/memory/remember` | oe_remember |
| POST | `/v1/spaces/{space_id}/memory/recall` | oe_recall |
| POST | `/v1/spaces/{space_id}/memory/reflect` | oe_reflect |

### 7.2 高级管理端点

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/v1/spaces/{space_id}/memory/consolidate` | 单独触发巩固 |
| POST | `/v1/spaces/{space_id}/memory/forget` | 单独触发遗忘 |
| GET | `/v1/spaces/{space_id}/memory/stats` | 记忆统计 |
| GET | `/v1/spaces/{space_id}/memory/types` | 各类型数量和强度分布 |
| GET | `/v1/spaces/{space_id}/memory/audit` | 审计日志查询（被更正/废弃的节点） |

### 7.3 统一响应格式

```json
{
    "success": true,
    "data": { ... },
    "error": null,
    "meta": {
        "request_id": "req_001",
        "timestamp": "2026-04-25T10:00:00Z",
        "space_id": "space.finance",
        "memory_version": "2.0"
    }
}
```

### 7.4 新增权限治理端点 [新增]

```python
# 列出当前用户可见的记忆（权限过滤）
GET /v1/spaces/{space_id}/memory/my?scope_type=user&memory_type=observation

# 更正记忆（用户纠错）
PATCH /v1/spaces/{space_id}/memory/{node_id}/correct
Body: {"corrected_text": "...", "reason": "..."}

# 删除记忆（用户有权删除关于自己的记忆）
DELETE /v1/spaces/{space_id}/memory/{node_id}?cascade=false

# 记录承诺
POST /v1/spaces/{space_id}/memory/commitments
Body: {"text": "明天给你报告", "deadline": "2026-05-01T10:00:00Z", "task_id": "task_001"}

# 检查承诺状态
GET /v1/spaces/{space_id}/memory/commitments?status=pending&overdue=true
```

---

## 8. CLI 命令

```
ontology-cli memory remember  --space space.finance --content "..." --tags domain:risk
ontology-cli memory recall    --space space.finance --query "..." --type entity
ontology-cli memory reflect   --space space.finance --query "..."

ontology-cli memory consolidate --space space.finance --dry-run
ontology-cli memory forget    --space space.finance --criteria stale --mode archive
ontology-cli memory stats     --space space.finance

ontology-cli memory list-my    --space space.finance --scope user
ontology-cli memory correct   --node mu_001 --text "更正后的内容"
ontology-cli memory delete    --node mu_001 --cascade false
ontology-cli memory record-commitment --space space.finance --text "明天给你报告" --deadline 2026-05-01
ontology-cli memory check-commitments --space space.finance --status pending
```

---

## 9. 错误码

| 错误码 | HTTP | 含义 | 修复建议 |
|--------|:----:|------|----------|
| MEMORY_NOT_READY | 503 | 记忆系统未初始化 | 等待初始化完成 |
| CONSOLIDATION_IN_PROGRESS | 409 | 巩固任务正在执行 | 等待当前任务完成 |
| PROTECTED_MEMORY | 403 | 受保护记忆不可遗忘 | 使用 force=true（谨慎） |
| REFLECT_TIMEOUT | 504 | 反思超时 | 减少 max_iterations |
| MEMORY_STALE | 200 | 记忆已过期但仍返回 | 触发 reflect 刷新 |
| INVALID_MEMORY_TYPE | 422 | 无效的 memory_type | 使用有效类型：entity/observation/mental_model/episode/procedure/fragment/commitment/constraint/self_experience/task_state |

---

## 10. API 三层抽象 [新增]

> **[关键设计点]**：L1 零配置是 Agent 日常使用的唯一接口，默认行为必须足够好。

### 10.1 三层定义

| 层级 | 目标用户 | 参数量 | 说明 |
|------|---------|--------|------|
| L1 | Agent 日常 | 2-3 | 零配置，默认策略自动选择 |
| L2 | 高级 Agent | 5-10 | 可选参数，按需使用 |
| L3 | 管理/调试 | 全部 | 完整参数暴露，精细控制 |

### 10.2 L1 API（Agent 日常）

```python
remember(content, space_id) → dict
recall(query, space_id) → dict
reflect(query, space_id) → dict  # 异步，返回 reflection_id
```

**关键**：L1 的默认行为必须足够好——
- `recall` 默认使用分层漏斗 + DispositionProfile 自动选择检索策略
- `reflect` 默认异步执行，返回 reflection_id
- `remember` 默认双通道提取（Schema 引导 + 开放提取）

### 10.3 L2 API（高级 Agent）

```python
remember(content, space_id, tags=None, memory_type="fragment",
         visibility="shared", auto_consolidate=False) → dict

recall(query, space_id, memory_type=None, max_results=10,
       include_evidence=True, as_of=None, token_budget=None,
       allow_short_circuit=True, min_confidence=0.5) → dict

reflect(query, space_id, max_iterations=10, focus_types=None,
        async_mode=True) → dict  # async_mode=True 返回 reflection_id
```

### 10.4 L3 API（管理/调试）

```python
remember(content, space_id, tags=None, memory_type="fragment",
         visibility="shared", auto_consolidate=False,
         belief_status="accepted", confidence=1.0,
         valid_from=None, valid_to=None, recorded_at=None,
         occurred_at=None, source_pipeline=None) → dict

recall(query, space_id, memory_type=None, max_results=10,
       include_evidence=True, as_of=None, token_budget=None,
       allow_short_circuit=True, min_confidence=0.5,
       belief_status_filter="accepted", cognitive_layer=None,
       expansion_rules=None, evidence_depth=1,
       disposition_override=None) → dict

reflect(query, space_id, max_iterations=10, focus_types=None,
        async_mode=True, cascade_depth=3,
        skip_consolidation=False, skip_forgetting=False,
        skip_correction_propagation=False) → dict
```

### 10.5 三层接口参数覆盖对比

> **[待核对代码]**：以下对比基于当前实现代码，MCP Schema 和 CLI 参数可能随版本变化。

| 参数 | REST API | MCP Schema | CLI |
|------|----------|------------|-----|
| **remember** | | | |
| content | ✅ | ✅ (必填) | ✅ (必填) |
| space_id | ✅ (路径) | ✅ (必填) | ✅ (--space) |
| tags | ✅ | ✅ | ✅ (逗号分隔) |
| memory_type | ✅ | ✅ | ✅ |
| auto_consolidate | ✅ | ✅ | ✅ |
| visibility | ✅ | ❌ | ❌ |
| metadata | ✅ | ❌ | ❌ |
| created_by | ✅ | ❌ | ❌ |
| confidence | ✅ | ❌ | ❌ |
| schema_ref | ✅ | ❌ | ❌ |
| supersede_target | ✅ | ❌ | ❌ |
| supersede_reason | ✅ | ❌ | ❌ |
| **recall** | | | |
| query | ✅ | ✅ (必填) | ✅ (必填) |
| memory_type | ✅ | ✅ | ✅ |
| max_results | ✅ | ✅ | ✅ |
| include_evidence | ✅ | ✅ | ❌ |
| evidence_depth | ✅ | ❌ | ❌ |
| as_of | ✅ | ❌ | ❌ |
| token_budget | ✅ | ❌ | ❌ |
| belief_status_filter | ✅ | ❌ | ❌ |
| disposition_override | ✅ | ❌ | ❌ |
| audit_trail | ✅ | ❌ | ❌ |
| **reflect** | | | |
| query | ✅ | ✅ (必填) | ✅ (必填) |
| max_iterations | ✅ | ✅ | ✅ |
| focus_types | ✅ | ✅ | ❌ |
| async_mode | ✅ | ❌ | ❌ |
| skip_consolidation | ✅ | ❌ | ❌ |
| skip_forgetting | ✅ | ❌ | ❌ |
| cascade_depth | ✅ | ❌ | ❌ |
| skip_correction_propagation | ✅ | ❌ | ❌ |

**MCP 独有端点**: `oe_get_reflection_status`（REST API 和 CLI 均无对应端点）

**设计意图**：MCP 和 CLI 暴露 L1/L2 参数，REST API 暴露完整 L3 参数。高级参数通过 REST API 或直接调用 MemoryAPI 使用。

---

## 11. 异步 Reflect [新增]

> **[关键设计点]**：reflect 内部编排复杂（7个内部流程），必须异步执行。

### 11.1 异步流程

```
reflect(query, space_id)
  ↓
1. 创建 ReflectionJob → 返回 reflection_id
  ↓
2. 后台执行7个内部流程：
   ├── 分层检索（mental_model → entity → observation → fragment）
   ├── 矛盾检测（CONTRADICTS 边扫描）
   ├── 信念修正（BeliefRevisionEngine）
   ├── 巩固（ConsolidationPipeline）
   ├── 遗忘（ForgettingEngine）
   ├── 更正传播（CorrectionPropagation）
   └── Schema 建议生成（PatternDetector）
  ↓
3. 每个流程独立提交，失败不影响其他流程
  ↓
4. 结果持久化，不因中途失败而丢失
```

### 11.2 进度查询

```python
recall(reflection_id="refl_001") → dict
```

**返回格式**：

```json
{
    "success": true,
    "data": {
        "reflection_id": "refl_001",
        "status": "in_progress",
        "progress": {
            "retrieval": "completed",
            "contradiction_detection": "completed",
            "belief_revision": "in_progress",
            "consolidation": "pending",
            "forgetting": "pending",
            "correction_propagation": "pending",
            "schema_suggestion": "pending"
        },
        "partial_results": {
            "insights": [...],
            "contradictions": [...]
        }
    }
}
```

### 11.3 Reflect 结果查询

```python
recall(reflection_id="refl_001") → dict  # status="completed" 时返回完整结果
```

---

## 12. 记忆可见性 [新增]

> **[关键设计点]**：多用户共享同一 space 时，记忆需要可见性控制。

### 12.1 可见性级别

| 级别 | 说明 | 谁可见 |
|------|------|--------|
| private | 仅创建者可见 | 创建者 |
| shared | space 内共享 | space 内所有用户 |
| public | 跨 space 共享 | 所有用户 |

### 12.2 可见性判断规则

```python
def determine_visibility(content, memory_type, source):
    if contains_personal_info(content):
        return "private"
    if memory_type in ("entity", "rule", "mental_model"):
        return "shared"
    if source == "user_input" and memory_type == "episode":
        return "private"
    return "shared"
```

### 12.3 可见性过滤

```python
async def recall_with_visibility(query, space_id, user_id):
    results = await recall(query, space_id)
    filtered = [
        r for r in results
        if r.visibility == "shared"
        or (r.visibility == "private" and r.created_by == user_id)
        or (r.visibility == "public")
    ]
    return filtered
```

---

## 13. Agent 与人协作 API [新增]

> **[关键设计点]**：三区模型（轨道A/轨道B/待审区）的 API 支持。

### 13.1 待审区查询

```python
recall(query="pending_reviews", space_id=space_id,
       belief_status_filter="pending_review") → dict
```

### 13.2 审批操作

```python
approve_memory(node_id, action="approve", modifier_id="user_001",
               comment="确认此风险信号") → dict
```

| action | 说明 |
|--------|------|
| approve | 批准晋升到轨道A，belief_status → accepted, confidence → 1.0 |
| reject | 拒绝，belief_status → rejected |
| modify | 修改后批准，belief_status → accepted |

### 13.3 更正操作

```python
remember(content="诉讼已撤诉", space_id=space_id,
         supersede_target="obs_001", supersede_reason="correction") → dict
```

### 13.4 审计日志查询

```python
# 通过 API
GET /v1/spaces/{space_id}/memory/audit?limit=50

# 通过 recall 快捷方式
recall(query="audit_trail", space_id=space_id,
       entity_name="华为", include_superseded=True) → dict
```

**实现状态**: ✅ 已实现 — AuditAPI 返回 superseded/rejected 节点列表，MCP 工具 `oe_audit_trail` 已注册，CLI `memory audit` 已可用。

---

## 14. Recall 检索逻辑时序图 [新增]

> **[关键设计点]**：recall 的完整检索管线，从查询输入到结果返回。

### 14.1 完整检索管线

```
recall(query, space_id, ...)
  │
  ├─ 1. 类型过滤路由
  │    ├── memory_type 指定 → search_by_type(query, memory_type)
  │    └── memory_type 未指定 → 分层漏斗检索
  │         ├── L1: opinion(mental_model, opinion) → 命中且confidence≥阈值 → 场景允许短路 → 返回
  │         ├── L2: semantic(entity, rule)
  │         ├── L3: procedure(episode, procedure)
  │         └── L4: perception(fragment) —— 兜底
  │
  ├─ 2. 置信度过滤
  │    └── min_confidence 过滤低置信度结果
  │
  ├─ 3. 信念状态过滤
  │    └── belief_status_filter (默认 "accepted")
  │
  ├─ 4. 可见性过滤
  │    └── visibility: private/shared/public + user_id 匹配
  │
  ├─ 5. DispositionProfile 动态权重 [关键]
  │    ├── 加载策略:
  │    │    ├── disposition_override 为字符串 → 作为 scene 查询 profile
  │    │    ├── 失败 → fallback 查询 "default" scene profile
  │    │    └── 仍失败 → 使用基础 TYPE_WEIGHTS
  │    ├── 权重调整:
  │    │    ├── skepticism↑ → mental_model/entity↑, opinion/episode↓
  │    │    ├── abstraction_preference↑ → mental_model↑, fragment↓
  │    │    ├── empathy↑ → observation↑
  │    │    └── risk_tolerance↑ → procedure↑
  │    └── 最终: type_weight = apply_dynamic_weight(raw_score, memory_type, profile)
  │
  ├─ 6. 时序邻近性评分
  │    ├── temporal_score = exp(-0.05 * days_since_occurred)
  │    └── rank_score = score * type_weight * (0.7 + 0.3 * temporal_score)
  │
  ├─ 7. [可选] Cross-Encoder 重排序
  │    └── 配置 enabled=true 时，top_k_for_rerank → rerank → top_k_after_rerank
  │
  ├─ 8. 证据链展开
  │    ├── include_evidence=true → 沿 COG_SUPPORTED_BY/CONSOLIDATED_INTO 边展开
  │    └── evidence_depth 控制展开深度 (1=直接来源, 2=来源的来源)
  │
  ├─ 9. Token 预算裁剪
  │    └── token_budget 设定时，按 rank_score 降序截断
  │
  └─ 10. 返回结果
       └── results + query_type + total_tokens
```

### 14.2 RRF 四路融合与向量索引 [关键更新]

> **[关键设计点]**：向量检索已接入 recall 路径，通过 `CognitiveVectorIndex` 提供四级降级策略。

```
RRFFusionEngine.fuse(query, query_type, space_id, top_k)
  │
  ├─ Layer-R (向量检索) — 权重: factual=0.5, multi_hop=0.2
  │    └── CognitiveVectorIndex.vector_search()
  │         ├── Tier 1: OpenAI-compatible API (LMStudio/vLLM/OpenAI)
  │         │    └── httpx.AsyncClient → POST /embeddings → cosine similarity
  │         ├── Tier 2: sentence-transformers 本地模型
  │         │    └── SentenceTransformer.encode() → LocalVectorStore.search()
  │         ├── Tier 3: BM25 TF-IDF 评分 (零依赖降级)
  │         │    └── 分词(ASCII词+CJK单字+CJK bigram) → IDF × TF_norm → 排序
  │         └── Tier 4: 子串匹配 (RRF fallback)
  │
  ├─ Layer-S (图检索) — 权重: factual=0.2, multi_hop=0.5
  │    └── query_nodes(memory_type="entity")
  │
  ├─ BM25 (关键词检索) — 权重: factual=0.2, multi_hop=0.1
  │    └── CognitiveVectorIndex.bm25_search()
  │
  └─ Temporal (时间检索) — 权重: factual=0.1, temporal=0.6
       └── extract_temporal_constraint() → 时间范围过滤
```

### 14.3 Embedding 配置体系 [新增]

> **[单一事实源]**：Embedding 配置的完整定义。

**配置来源优先级**: 构造器参数 > 环境变量 > config.yaml > 默认值

```yaml
# config.yaml
embedding:
  provider: openai_compatible    # openai_compatible | sentence_transformers | bm25
  base_url: http://127.0.0.1:7852/v1
  api_key: ~                     # 本地部署通常不需要
  model: text-embedding-qwen3-embedding-4b
  dimension: 2560                # 必须与模型输出维度一致
```

**环境变量覆盖**: `OE_EMBEDDING_PROVIDER`, `OE_EMBEDDING_BASE_URL`, `OE_EMBEDDING_API_KEY`, `OE_EMBEDDING_MODEL`, `OE_EMBEDDING_DIMENSION`, `OE_EMBEDDING_PERSIST_DIR`

**内容增强策略**: 写入时将 content 丰富为 `[memory_type] tags | content`，帮助 embedding 模型捕获类型语义和标签上下文。

**BM25 中文分词策略**: 无外部分词库依赖时，采用 ASCII 词 + CJK 单字 + CJK bigram 三级 token 策略。ASCII 部分用 `[a-zA-Z0-9_]+` 提取；CJK 部分提取 Unicode 范围 `[\u4e00-\u9fff]` 的单字和相邻二字组合(bigram)。此策略在中文场景下相比纯 `\w+` 模式（会将整句中文当作单个 token）有显著提升，同时保持零依赖。

**向量持久化**: 当 `persist_dir` 配置时，向量存储在 ChromaDB PersistentClient 的 `cognitive_node` collection 中；未配置时使用内存存储（重启后丢失）。

**模型签名版本化**: 每个向量附带 `model_signature` 元数据（格式：`provider:model:dimension`）。初始化时检查已有向量的签名是否与当前配置匹配，不匹配则发出警告建议重建索引。维度和模型作为一组信息一起管理，不可独立变更。

### 14.4 DispositionProfile 加载策略详解

```
recall(query, space_id, disposition_override="audit")
  │
  ├─ Step 1: 尝试 scene = "audit"
  │    └── repo.get_profile_by_scene("audit", domain_id=space_id)
  │         ├── 成功 → profile = audit_profile (evidence_demand=1.0, skepticism=0.9)
  │         └── 失败 ↓
  │
  ├─ Step 2: Fallback scene = "default"
  │    └── repo.get_profile_by_scene("default", domain_id=space_id)
  │         ├── 成功 → profile = default_profile
  │         └── 失败 ↓
  │
  └─ Step 3: 使用基础 TYPE_WEIGHTS (无动态调整)
       └── mental_model(3.0) > opinion(2.5) > entity(2.0) > rule(2.0)
           > commitment(1.9) > constraint(1.8) > procedure(1.8) > task_state(1.6)
       > observation(1.5) > episode(1.2) > self_experience(1.1) > fragment(1.0)
```

---

## 15. Reflect 混合矛盾检测时序图 [新增]

> **[关键设计点]**：反思采用混合矛盾检测，规则层无需 LLM，搜索层需要 LLM。

### 15.1 混合检测架构

```
reflect(query, space_id, ...)
  │
  ├─ Phase A: 规则矛盾检测 (无需 LLM)
  │    ├── 1. 查询 space 下所有 CognitiveNode (limit=500)
  │    ├── 2. 按 tags 分组
  │    ├── 3. 同 tag 组内两两检查:
  │    │    ├── 跳过 belief_status ∈ {superseded, rejected} 的节点
  │    │    └── 否定冲突模式匹配:
  │    │         ├── "不是X" vs "X"
  │    │         ├── "不使用X" vs "使用X"
  │    │         ├── "不再X" vs "X"
  │    │         ├── "没有X" vs "有X"
  │    │         └── "并非X" vs "X"
  │    └── 4. 输出: rule_contradictions: list[ContradictionReport]
  │
  ├─ Phase B: 搜索循环矛盾检测 (需 LLM)
  │    ├── 1. 前 N 轮强制检索 (FORCED_SEARCH_SEQUENCE):
  │    │    ├── 轮次1: search_by_type(query, "mental_model")
  │    │    ├── 轮次2: search_by_type(query, "entity")
  │    │    └── 轮次3: search_by_type(query, "observation")
  │    ├── 2. 后续轮次: Agent 自主 recall
  │    ├── 3. 每轮轻量矛盾检测:
  │    │    └── 按 cognitive_layer 分组 → 找 accepted vs contradicted 配对
  │    └── 4. 输出: search_contradictions: list[ContradictionReport]
  │
  ├─ Phase C: 合并去重
  │    └── all_contradictions = dedup(rule_contradictions + search_contradictions)
  │
  └─ Phase D: 后续动作
       ├── 信念修正规则引擎 (按优先级 100→40 匹配规则)
       ├── 巩固 (未归纳碎片)
       ├── 遗忘 (低强度记忆)
       ├── 更正传播 (沿 SUMMARIZED_AS/CONSOLIDATED_INTO/COGNITIVE_RELATES_TO 边)
       └── Schema 建议 (模式检测)
```

---

## 16. 认知边类型完整清单 [新增]

> **[单一事实源]**：所有认知边类型的定义和用途。

### 16.1 边类型与 KuzuDB 边表映射

| 边类型 | KuzuDB 表名 | 时间字段 | 语义 | 创建场景 |
|--------|-------------|---------|------|---------|
| CONSOLIDATED_INTO | CONSOLIDATED_INTO | consolidated_at | fragment → observation 归纳 | 巩固引擎创建 observation |
| SUMMARIZED_AS | SUMMARIZED_AS | created_at | observation → mental_model 摘要 | 巩固引擎创建 mental_model |
| LEARNED_INTO | LEARNED_INTO | created_at | episode → procedure 学习 | 巩固引擎创建 procedure |
| SUPERSEDES | SUPERSEDES | superseded_at | 新节点取代旧节点 | 更正写入、信念修订 |
| CONTRADICTS | CONTRADICTS | created_at | 矛盾关系 | 反思检测到矛盾 |
| COGNITIVE_RELATES_TO | COGNITIVE_RELATES_TO | created_at | 认知关联 | DreamCycle Phase 4 自链接增强 |
| RELATES_TO | RELATES_TO | created_at | 一般关联 | 编译层、手动关联 |
| CO_OCCURS_WITH | CO_OCCURS_WITH | - | 共现关系 | 实体共现追踪 |
| PART_OF | PART_OF | created_at | 部分-整体 | 层次结构 |
| SUPPORTS | SUPPORTS | created_at | 支持关系 | 证据支持 |
| COG_SUPPORTED_BY | COG_SUPPORTED_BY | - | 证据支持（带贡献度） | 证据链 |

> **[关键设计点]**：`query_cognitive_edges` 根据边类型使用不同的时间字段（CONSOLIDATED_INTO 使用 `consolidated_at`，SUPERSEDES 使用 `superseded_at`，其余使用 `created_at`），避免查询失败。

### 16.2 更正传播边类型

更正传播沿以下边类型 BFS 遍历：
- **SUMMARIZED_AS**: mental_model 依赖的 observation 被更正 → mental_model 需刷新
- **CONSOLIDATED_INTO**: observation 依赖的 fragment 被更正 → observation 需重新归纳
- **COGNITIVE_RELATES_TO**: 关联实体被更正 → 需检查是否影响本实体

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| Agent 记忆设计总览 | `docs/02-design/agent-memory/README.md` |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 记忆生命周期设计 | `docs/02-design/agent-memory/memory-lifecycle.md` |
| Agent 友好接口设计 | `docs/02-design/agent-friendly-design.md` |
| 知识库流程主文档 | `docs/01-overview/10-kb-process.md` |
| 审查辩论文档 | `discuss/2026-04-30-kb-memory-design-adversarial-review.md` |
| 外部批判框架对照 | `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` |

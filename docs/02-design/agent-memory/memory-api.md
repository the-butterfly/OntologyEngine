# 认知操作 API 设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

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
        description="Memory type hint. 'fragment' for raw info, 'observation' for consolidated knowledge, 'episode' for experience events.",
        examples=["fragment", "observation", "episode"]
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
    1. IngestionService.ingest() → KnowledgeFragment created (Layer-R)
    2. ExtractionPipeline.extract() → entities/relations extracted
    3. EntityResolver.resolve() → entity disambiguation
    4. If memory_type != "fragment": create MemoryUnitNode directly (Layer-S)
    5. If auto_consolidate: ConsolidationEngine.consolidate()
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
        description="Optional type filter: mental_model, opinion, entity, observation, rule, episode, procedure, fragment. Auto-searches all types if not specified.",
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
    1. If memory_type specified: search only that type
    2. If memory_type not specified: search all types, apply type weights
    3. QueryEngine.query() → TEMPR retrieval + RRF fusion + type weights
    4. Optional: Cross-Encoder reranking
    5. If include_evidence: expand via mutual index edges
    6. If token_budget: trim results to fit
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
    1. ReflectAgent.reflect() → forced retrieval by type priority
       - mental_model → entity → observation → fragment
    2. LLM generates insights, detects contradictions
    3. New insights → upgrade to observation or mental_model
    4. Contradictions → generate contradiction_report
    5. Low-value memories → trigger forgetting (strength decay)
    6. Unconsolidated fragments → trigger consolidation
    7. Stale mental models → mark for refresh
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

---

## 8. CLI 命令

```
ontology-cli memory remember  --space space.finance --content "..." --tags domain:risk
ontology-cli memory recall    --space space.finance --query "..." --type entity
ontology-cli memory reflect   --space space.finance --query "..."

ontology-cli memory consolidate --space space.finance --dry-run
ontology-cli memory forget    --space space.finance --criteria stale --mode archive
ontology-cli memory stats     --space space.finance
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
| INVALID_MEMORY_TYPE | 422 | 无效的 memory_type | 使用有效类型：entity/observation/mental_model/episode/procedure/fragment |

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
recall(query="audit_trail", space_id=space_id,
       entity_name="华为", include_superseded=True) → dict
```

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

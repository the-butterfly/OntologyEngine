# Reflect Agent

> **status**: draft | **phase**: rewrite | **source_of_truth**: 本文档 | **last_verified**: 2026-04-30

## 目的

定义 OntologyEngine 的 Reflect Agent，通过多轮 Tool-Calling 推理对记忆进行深度分析，发现矛盾、生成洞察、触发巩固与遗忘。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | Agent 无法深度分析记忆间关系 | 矛盾长期存在不被发现 |
| 2 | 单次检索无法发现跨层洞察 | mental_model 与 observation 之间的关联被忽略 |
| 3 | 反思过程可能产生幻觉 | 无证据支撑的"洞察"被写入知识库 |
| 4 | 长反思过程上下文溢出 | Token 超限导致截断或崩溃 |
| 5 | 反思风格无法个性化 | 不同风险偏好的 Agent 应有不同反思深度 |

---

## 架构概览

```
┌─────────────────────────────────────────────┐
│              Reflect Agent                   │
│                                              │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐    │
│  │ search_ │  │ recall  │  │ detect_  │    │
│  │ by_type │  │         │  │ contrad. │    │
│  └────┬────┘  └────┬────┘  └────┬─────┘    │
│       │            │            │           │
│  ┌────┴────┐  ┌────┴────┐  ┌───┴──────┐    │
│  │ trigger │  │ trigger │  │  done     │    │
│  │ consoli │  │ forget  │  │ (验证)    │    │
│  └─────────┘  └─────────┘  └──────────┘    │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  迭代循环 (max 10 轮)                 │   │
│  │  前 3 轮：强制检索序列                │   │
│  │  后 7 轮：Agent 自主决策              │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  保护机制                            │   │
│  │  · 上下文溢出保护                    │   │
│  │  · 幻觉防护 (ID 追踪)               │   │
│  │  · Disposition 注入                  │   │
│  │  · Directives 硬规则                 │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 工具定义

### search_by_type

```python
@mcp_tool(name="search_by_type")
async def search_by_type(
    query: str,
    memory_type: str,
    space_id: str,
    top_k: int = 5,
) -> list[dict]:
    """
    按类型检索记忆。memory_type 可选：
    mental_model, entity, observation, fragment, opinion, rule, procedure, episode
    """
```

### recall

```python
@mcp_tool(name="recall")
async def recall(
    query: str,
    space_id: str,
    top_k: int = 10,
    memory_type: str | None = None,
    include_evidence: bool = True,
) -> list[dict]:
    """跨类型检索，走 RRF 四路融合"""
```

### detect_contradictions

```python
@mcp_tool(name="detect_contradictions")
async def detect_contradictions(
    node_ids: list[str],
    space_id: str,
) -> list[ContradictionReport]:
    """
    检测指定节点间的矛盾。
    返回：contradiction_type, contradiction_field, old_value, new_value, suggested_resolution
    """
```

### trigger_consolidation

```python
@mcp_tool(name="trigger_consolidation")
async def trigger_consolidation(
    space_id: str,
    fragment_ids: list[str] | None = None,
) -> dict:
    """触发巩固任务，返回 job_id"""
```

### trigger_forgetting

```python
@mcp_tool(name="trigger_forgetting")
async def trigger_forgetting(
    space_id: str,
    node_ids: list[str] | None = None,
) -> dict:
    """触发遗忘评估，返回 job_id"""
```

### done

```python
@mcp_tool(name="done")
async def done(
    insights: list[Insight],
    contradictions: list[ContradictionReport],
    consolidation_requests: list[str] | None = None,
    forgetting_requests: list[str] | None = None,
    mental_model_updates: list[MentalModelUpdate] | None = None,
    evidence_ids: list[str] | None = None,
) -> dict:
    """
    结束反思，提交结果。
    evidence_ids 必须是检索过程中获取的记忆 ID 子集。
    """
```

---

## 强制检索序列 [关键设计点]

```
轮次 1: search_by_type(query, "mental_model", space_id)
        → 获取高层认知框架

轮次 2: search_by_type(query, "entity", space_id)
        → 获取结构化实体知识

轮次 3: search_by_type(query, "observation", space_id)
        → 获取归纳观察

轮次 4+: Agent 自主选择工具调用
        → 可用 recall / search_by_type / detect_contradictions / ...
```

**强制序列理由**：前 3 轮确保从高到低遍历认知层，避免 Agent 过早陷入碎片层。

---

## 迭代循环

```python
async def run_reflect_agent(
    query: str,
    space_id: str,
    max_iterations: int = 10,
    focus_types: list[str] | None = None,
    disposition: DispositionProfile | None = None,
) -> ReflectResult:

    type_priority = focus_types or [
        "mental_model", "entity", "observation", "fragment"
    ]

    messages = build_system_messages(query, space_id, disposition)
    available_ids: set[str] = set()

    for iteration in range(max_iterations):
        if iteration < 3:
            tool_call = forced_search(iteration, type_priority, query, space_id)
            messages.append(tool_call)
        else:
            response = await llm.call(messages)
            if is_done_call(response):
                return await validate_and_return(response, available_ids)
            messages.append(response)

        tool_result = await execute_tool_call(messages[-1])
        available_ids.update(extract_ids(tool_result))
        messages.append(tool_result)

        if count_tokens(messages) >= max_context_tokens:
            return await force_final_answer(messages, available_ids)

    return await force_final_answer(messages, available_ids)
```

### 提前退出条件

| 条件 | 行为 |
|------|------|
| Agent 调用 done() | 正常返回 |
| Token 计数 ≥ max_context_tokens | 强制最终回答 |
| 达到 max_iterations | 强制最终回答 |
| 连续 2 轮无新发现 | 建议退出（Agent 可忽略） |

---

## 上下文溢出保护

```python
def count_tokens(messages: list[Message]) -> int:
    total = 0
    for msg in messages:
        total += len(msg.content) // 4
    return total

async def force_final_answer(
    messages: list[Message],
    available_ids: set[str],
) -> ReflectResult:
    messages.append({
        "role": "system",
        "content": (
            "上下文即将溢出，请立即调用 done() 提交当前发现。"
            "仅使用以下 ID 作为证据：" + ", ".join(available_ids)
        ),
    })
    response = await llm.call(messages)
    return await validate_and_return(response, available_ids)
```

---

## 幻觉防护 [关键设计点]

```python
async def validate_and_return(
    response: Message,
    available_ids: set[str],
) -> ReflectResult:
    result = parse_done_response(response)

    for insight in result.insights:
        for eid in insight.evidence_ids:
            if eid not in available_ids:
                raise HallucinationError(
                    f"Insight references unknown ID: {eid}. "
                    f"Available: {available_ids}"
                )

    for contradiction in result.contradictions:
        for nid in contradiction.node_ids:
            if nid not in available_ids:
                raise HallucinationError(
                    f"Contradiction references unknown ID: {nid}"
                )

    return result
```

**防护策略**：
1. 所有 evidence_ids 必须在 available_ids 集合中
2. 矛盾报告的 node_ids 必须在 available_ids 集合中
3. 不在集合中的引用视为幻觉，拒绝提交

---

## 结构化输出

```python
class Insight(BaseModel):
    text: str
    confidence: float
    evidence_ids: list[str]
    suggested_memory_type: str

class ContradictionReport(BaseModel):
    node_ids: list[str]
    contradiction_type: str
    contradiction_field: str
    old_value: str
    new_value: str
    suggested_resolution: str

class MentalModelUpdate(BaseModel):
    model_id: str
    update_type: str
    update_text: str
    evidence_ids: list[str]

class ReflectResult(BaseModel):
    insights: list[Insight]
    contradictions: list[ContradictionReport]
    consolidation_requests: list[str]
    forgetting_requests: list[str]
    mental_model_updates: list[MentalModelUpdate]
```

---

## Disposition 注入

```python
def build_system_messages(
    query: str,
    space_id: str,
    disposition: DispositionProfile | None,
) -> list[Message]:
    base = f"你是一个知识库反思引擎，正在分析空间 {space_id} 中的记忆。"

    if disposition:
        if disposition.skepticism > 0.7:
            base += "\n你对现有知识持高度怀疑态度，优先寻找矛盾和不一致。"
        if disposition.evidence_demand > 0.7:
            base += "\n你要求每个洞察必须有至少 2 个独立证据支撑。"
        if disposition.thoroughness > 0.7:
            base += "\n你需要彻底检查所有相关记忆，不要遗漏。"
        if disposition.risk_tolerance < 0.3:
            base += "\n你应保守判断，不确定的洞察标记为低置信度。"

    return [{"role": "system", "content": base}]
```

| Disposition 维度 | 对反思的影响 |
|-----------------|-------------|
| skepticism | 高值→优先检测矛盾，低值→优先发现一致性 |
| evidence_demand | 高值→要求更多证据，低值→接受弱证据 |
| thoroughness | 高值→增加检索轮次，低值→快速收敛 |
| recency_bias | 高值→优先分析近期记忆，低值→时间中性 |
| empathy | 高值→关注用户体验相关洞察 |
| risk_tolerance | 低值→保守判断，高值→大胆假设 |
| abstraction_preference | 高值→优先分析 mental_model，低值→优先分析 observation |

---

## Directives 硬规则

```
1. 禁止创建新的 CognitiveNode（反思只分析，不直接写入）
2. 禁止修改 belief_status（通过矛盾报告间接触发）
3. 禁止删除任何记忆（通过遗忘请求间接触发）
4. 所有洞察必须附带 evidence_ids
5. 矛盾报告必须包含 suggested_resolution
6. 不得引用检索范围外的记忆 ID
```

---

## 异步执行

```python
class ReflectionJob(BaseModel):
    job_id: str
    space_id: str
    query: str
    status: str  # pending | running | completed | failed
    progress: float
    partial_results: ReflectResult | None
    created_at: str
    updated_at: str

async def oe_reflect(
    query: str,
    space_id: str,
    max_iterations: int = 10,
    focus_types: list[str] | None = None,
) -> dict:
    job = ReflectionJob(
        job_id=generate_uuid(),
        space_id=space_id,
        query=query,
        status="pending",
    )
    await enqueue_job(job)
    return {"job_id": job.job_id, "status": "pending"}
```

---

## 与现有系统集成

| 系统 | 集成点 | 方向 |
|------|--------|------|
| recall API | search_by_type / recall 工具 | 调用 |
| Consolidation 引擎 | trigger_consolidation 工具 | 触发 |
| 矛盾处理器 | detect_contradictions → 矛盾报告 | 输入 |
| 遗忘评估器 | trigger_forgetting 工具 | 触发 |
| Mental Model 刷新 | mental_model_updates 输出 | 输出 |
| DispositionProfile | 系统消息注入 | 配置 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-REF-1 | 前 3 轮强制检索 | 确保从高到低遍历认知层，避免过早陷入碎片 |
| D-REF-2 | max_iterations=10 | 平衡深度与成本，Hindsight 验证 10 轮足够 |
| D-REF-3 | 幻觉防护基于 ID 集合 | 简单有效，避免引用检索范围外的记忆 |
| D-REF-4 | 上下文溢出强制最终回答 | 防止截断导致不完整输出 |
| D-REF-5 | 反思不直接写入 | 职责分离：反思只分析，巩固/遗忘负责写入 |
| D-REF-6 | Disposition 注入系统消息 | 灵活可扩展，不修改工具接口 |
| D-REF-7 | 结构化输出通过 done() 提交 | 统一出口，便于验证和审计 |

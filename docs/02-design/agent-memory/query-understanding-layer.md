# QueryUnderstandingLayer 设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: 本文档 + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-28
> **[关键设计点]**: 本文档定义任务约束驱动的检索架构，解决"RAG 式语义召回"与"任务约束驱动检索"之间的架构缺口。

[设计决策 2026-05-07] 完整实现 QUL：8种约束类型 + 规则层/LLM层双层提取 + 约束→策略映射 + 约束驱动重排序。当前约束提取逻辑散落在 rrf_fusion.py 中，需整合为统一的 QueryUnderstandingLayer 入口。

---

## 目的

当前 `oe_recall` 的核心是**语义相似度召回**——query 与记忆的表面语义越像，排名越高。但 lencx 的批判指出：**相关性不由表面语义决定**。

> 一个用户在讨论项目架构时的 query，与"他上周否决过微服务方案"高度相关，但表面语义完全不匹配。

QueryUnderstandingLayer（QUL）在检索前提取**任务约束**，并据此调整检索策略，实现从"语义相似"到"任务约束驱动"的升级。

---

## 核心洞察

### 当前检索的局限

```
用户: "这个项目用什么架构？"
  ↓
向量嵌入: [0.12, -0.05, 0.33, ...]
  ↓
语义相似召回: "微服务架构介绍"(0.92), "单体架构优势"(0.89), "架构选型指南"(0.85)
  ↓
问题: 没有召回 "用户上周否决过微服务方案"——这条记忆表面语义不匹配，但对当前决策至关重要
```

### QUL 的改进

```
用户: "这个项目用什么架构？"
  ↓
QueryUnderstandingLayer:
  - 检测到当前 task_id = "project_alpha"
  - 检测到用户偏好: "保守、厌恶复杂部署"
  - 检测到任务历史: "上周否决过微服务方案"
  - 检测到环境约束: "团队只有 3 人，无 DevOps 经验"
  ↓
任务约束: {user_preference: true, task_history: true, environmental: true}
  ↓
约束驱动检索:
  - 优先检索 model_domain=user 的 preference 记忆
  - 优先检索 scope.task_id="project_alpha" 的 decision_log
  - 优先检索 model_domain=world 的 constraint 记忆
  ↓
结果: "用户上周否决过微服务方案"(constraint_match=0.95) 排名第一
```

---

## 架构

### 2.1 输入输出

```python
class QueryUnderstandingLayer:
    async def extract_constraints(
        self,
        query: str,
        space_id: str,
        user_id: str | None = None,
        task_id: str | None = None,
        conversation_history: list[Message] | None = None,
    ) -> TaskConstraints:
        """
        从 query 和上下文中提取任务约束。
        """

class TaskConstraints(BaseModel):
    user_preference: bool = False      # 是否涉及用户偏好
    task_history: bool = False         # 是否涉及任务历史
    temporal_scope: str | None = None  # 时间范围（如"过去一个月"）
    decision_type: str | None = None   # 决策类型: factual/analytical/causal/comparative
    environmental: bool = False        # 是否涉及环境约束
    self_reference: bool = False       # 是否涉及 Agent 自身经验
    entity_targets: list[str] = []     # 提到的实体名称
    confidence_demand: float = 0.5     # 隐含的证据要求级别
```

### 2.2 约束提取规则

#### 规则层（轻量级，无需 LLM）

| 模式 | 约束类型 | 示例 |
|------|---------|------|
| "为什么..." / "怎么..." | `decision_type=causal` | "为什么波动？" |
| "过去X天/周/月" | `temporal_scope=X` | "过去一个月" |
| "我觉得..." / " prefer..." | `user_preference=true` | "我更喜欢简洁的" |
| "上次..." / "之前..." | `task_history=true` | "上次你建议的方案" |
| "能不能..." / "是否可以..." | `confidence_demand=0.7` | "能不能做到？" |
| "限制..." / "约束..." | `environmental=true` | "有什么限制？" |

#### LLM 层（语义理解）

当规则层无法确定时，使用轻量级 LLM 调用：

```python
async def llm_extract_constraints(query, context):
    prompt = f"""
    Analyze the following query and extract task constraints.

    Query: {query}
    Context: {context}

    Return JSON:
    {{
        "user_preference": bool,
        "task_history": bool,
        "temporal_scope": str | null,
        "decision_type": "factual" | "analytical" | "causal" | "comparative" | null,
        "environmental": bool,
        "self_reference": bool,
        "entity_targets": [str],
        "confidence_demand": float
    }}
    """
    return await llm.call(prompt, response_format="json")
```

### 2.3 约束到检索策略的映射

```python
CONSTRAINT_TO_RETRIEVAL_STRATEGY = {
    "user_preference": {
        "boost_model_domain": "user",
        "boost_memory_types": ["mental_model", "opinion"],
        "boost_cognitive_layers": ["opinion"],
    },
    "task_history": {
        "boost_model_domain": "task",
        "boost_memory_types": ["episode", "commitment", "task_state"],
        "filter_scope_task_id": "current_task",
    },
    "temporal_scope": {
        "apply_temporal_filter": True,
        "temporal_boost": 0.3,
    },
    "decision_type=causal": {
        "boost_memory_types": ["observation", "episode"],
        "expand_causal_edges": True,
    },
    "decision_type=factual": {
        "boost_memory_types": ["entity", "rule"],
        "short_circuit_on_high_confidence": True,
    },
    "environmental": {
        "boost_model_domain": "world",
        "boost_memory_types": ["constraint", "rule"],
    },
    "self_reference": {
        "boost_model_domain": "self",
        "boost_memory_types": ["self_experience", "procedure"],
    },
}
```

---

## 3. 与现有检索管线的集成

### 3.1 集成位置

```
recall(query, space_id, ...)
  │
  ├─ NEW: QueryUnderstandingLayer.extract_constraints(query, context)
  │       → TaskConstraints
  │
  ├─ 1. 类型过滤路由（根据 TaskConstraints 调整）
  │    ├── memory_type 指定 → search_by_type
  │    └── memory_type 未指定 → 分层漏斗（约束驱动调整）
  │
  ├─ 2. 置信度过滤
  │    └── min_confidence（根据 confidence_demand 动态调整）
  │
  ├─ 3. 信念状态过滤
  │
  ├─ 4. 可见性过滤
  │
  ├─ 5. DispositionProfile 动态权重
  │    └── 叠加 TaskConstraints 的 boost
  │
  ├─ 6. 时序邻近性评分
  │    └── 若 temporal_scope 存在，增强时序过滤
  │
  ├─ 7. [可选] Cross-Encoder 重排序
  │
  ├─ 8. 证据链展开
  │
  ├─ 9. Token 预算裁剪
  │
  └─ 10. 返回结果
```

### 3.2 约束驱动的重排序

在 RRF 融合 + DispositionProfile 权重之后，增加第二层重排序：

```python
def apply_constraint_boost(results, constraints):
    for result in results:
        boost = 1.0

        # model_domain 匹配 boost
        if constraints.user_preference and result.model_domain == "user":
            boost *= 1.5
        if constraints.task_history and result.model_domain == "task":
            boost *= 1.4
        if constraints.environmental and result.model_domain == "world":
            boost *= 1.3
        if constraints.self_reference and result.model_domain == "self":
            boost *= 1.3

        # memory_type 匹配 boost
        if constraints.decision_type == "causal" and result.memory_type in ("observation", "episode"):
            boost *= 1.2
        if constraints.decision_type == "factual" and result.memory_type in ("entity", "rule"):
            boost *= 1.2

        # scope 匹配 boost
        if constraints.task_history and result.scope:
            if result.scope.get("ref_id") == constraints.current_task_id:
                boost *= 1.3

        result.rank_score *= boost

    results.sort(key=lambda r: r.rank_score, reverse=True)
    return results
```

### 3.3 与语义召回的关系

> **[关键设计点]**：QUL **不替换**语义召回，而是**叠加**在语义召回之上。
>
> - 语义召回是基础层：找到"可能与 query 相关的记忆"
> - 约束驱动是重排序层：从"可能相关"中提升"对当前任务真正有用"的记忆

```
语义召回结果（100条）
  ↓ RRF 融合 + 类型权重
中间结果（20条）
  ↓ 约束驱动重排序
最终结果（10条）
```

---

## 4. 上下文加载

### 4.1 自动上下文检测

QUL 不仅分析 query，还自动加载相关上下文：

```python
async def load_task_context(space_id, user_id):
    context = {}

    # 加载最近激活的任务
    active_tasks = await get_active_tasks(user_id, space_id, limit=3)
    if active_tasks:
        context["active_tasks"] = active_tasks
        context["current_task_id"] = active_tasks[0].id

    # 加载用户模型
    user_model = await get_user_model(user_id, space_id)
    if user_model:
        context["user_preferences"] = user_model.attributes

    # 加载待履行承诺
    pending_commitments = await get_pending_commitments(space_id, user_id=user_id)
    if pending_commitments:
        context["pending_commitments"] = pending_commitments

    return context
```

### 4.2 上下文注入

```python
async def recall_with_qul(query, space_id, user_id, **kwargs):
    # 1. 加载上下文
    context = await load_task_context(space_id, user_id)

    # 2. 提取约束
    constraints = await QueryUnderstandingLayer.extract_constraints(
        query=query,
        space_id=space_id,
        user_id=user_id,
        task_id=context.get("current_task_id"),
        conversation_history=kwargs.get("conversation_history"),
    )

    # 3. 基础语义召回
    results = await base_recall(query, space_id, **kwargs)

    # 4. 约束驱动重排序
    results = apply_constraint_boost(results, constraints)

    # 5. 注入上下文摘要（供 LLM 生成回答时使用）
    results.metadata["task_constraints"] = constraints.dict()
    results.metadata["task_context"] = context

    return results
```

---

## 5. 典型场景

### 场景 1：项目架构讨论

```
用户: "这个项目用什么架构？"

QUL 分析:
  - active_tasks: [{id: "proj_alpha", name: "Project Alpha Setup"}]
  - user_preferences: {risk_appetite: "conservative", communication_style: "concise"}
  - pending_commitments: []

提取约束:
  - task_history: true（当前有活跃任务）
  - user_preference: true（涉及架构选择，与用户偏好相关）
  - decision_type: "analytical"
  - current_task_id: "proj_alpha"

检索调整:
  - 优先检索 scope.task_id="proj_alpha" 的 task_state / episode
  - 优先检索 model_domain="user" 的 preference
  - 发现: "上周否决过微服务方案" → 排名提升至 #1
```

### 场景 2：风险评估追问

```
用户: "为什么华为的风险等级波动这么大？"

QUL 分析:
  - entity_targets: ["华为"]
  - decision_type: "causal"
  - temporal_scope: "recent"

检索调整:
  - 优先检索 model_domain="world" 的 constraint（如"评级调整规则"）
  - 优先检索 memory_type="episode" 的时序记录
  - 展开 CAUSAL 边遍历
  - 发现: "Day 15 征信报告更新导致等级从 A 降至 D，Day 20 用户更正撤诉信息后回升至 B" → 完整因果链
```

### 场景 3：工具调用失败后的恢复

```
用户: "帮我执行一下风险分析"
（上次调用 oe_execute_rule 时超时了）

QUL 分析:
  - self_reference: true（上次工具调用失败）
  - task_history: true

检索调整:
  - 优先检索 model_domain="self" 的 self_experience
  - 发现: "上次 oe_execute_rule 超时，原因是 Company A 财务数据不完整"
  - Agent 自动调整: 先调用 oe_query 检查数据完整性，再执行规则
```

---

## 6. 性能考量

### 6.1 延迟预算

| 步骤 | 延迟 | 说明 |
|------|------|------|
| 规则层约束提取 | <10ms | 正则匹配，无 LLM |
| 上下文加载 | <50ms | 查询活跃任务 + 用户模型 |
| LLM 层约束提取（可选） | 200-500ms | 仅规则层不确定时触发 |
| 约束驱动重排序 | <5ms | 纯内存计算 |
| **总计** | **<65ms（规则层）/ <565ms（LLM 层）** | 在 recall 总延迟中占比 <10% |

### 6.2 缓存策略

```python
# 用户模型和活跃任务可以缓存
@cache(ttl=300)  # 5分钟缓存
async def get_user_model_cached(user_id, space_id):
    return await get_user_model(user_id, space_id)

@cache(ttl=60)   # 1分钟缓存
async def get_active_tasks_cached(user_id, space_id):
    return await get_active_tasks(user_id, space_id)
```

---

## 7. 与现有模块的关系

| 模块 | 集成点 | 方向 |
|------|--------|------|
| `memory-api.md` | `oe_recall` 内部调用 QUL | QUL 嵌入 recall 流程 |
| `memory-hierarchy.md` | `model_domain` 字段驱动约束匹配 | QUL 读取 CognitiveNode.model_domain |
| `modeling-objects.md` | 加载 User/Task/World/Self Model | QUL 调用四个模型的查询接口 |
| `query-engine/` | RRF 融合后叠加约束重排序 | QUL 在 QueryEngine 之后执行 |
| `reflect-agent.md` | ReflectAgent 的检索步骤也可使用 QUL | 可选集成 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| 知识库流程 | `docs/01-overview/10-kb-process.md` |
| 四建模对象 | `docs/02-design/agent-memory/modeling-objects.md` |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 认知操作 API | `docs/02-design/agent-memory/memory-api.md` |
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
| 外部批判框架 | `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` |

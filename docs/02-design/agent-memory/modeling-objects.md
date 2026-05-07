# 四建模对象设计：User / Task / World / Self

> **status**: draft | **phase**: phase2 | **source_of_truth**: 本文档 + `docs/01-overview/09-agent-memory.md` | **last_verified**: 2026-04-28
> **[关键设计点]**: 本文档定义 Agent 记忆系统中四个建模对象的详细设计。它们是 memory_type 和 cognitive_layer 之外的记忆第三维度。

---

## 目的

定义 OntologyEngine Agent 记忆系统中四个相互独立但可引用的模型：

| 建模对象 | 核心内容 | 当前覆盖度 | 缺口 |
|---------|---------|-----------|------|
| **User Model** | 用户偏好、风险容忍度、沟通习惯 | △ 部分（DispositionProfile） | 缺"沟通习惯"维度 |
| **Task Model** | 方案否决/确认历史、artifact 版本、承诺状态 | ✗ 缺失 | 完全缺失 |
| **World Model** | 环境约束（仓库结构、API 定义、组织规则） | △ 部分（Schema L1-L4） | 缺动态环境上下文 |
| **Self Model** | Agent 自身经验（失败路径、工具不稳定记录、暂定假设） | ✗ 缺失 | 完全缺失 |

---

## 设计原则

1. **model_domain 是正交维度**：与 `memory_type`（存储形态）和 `cognitive_layer`（认知抽象层）形成三维分类
2. **每个建模对象有自己的生命周期策略**：User Model 长期稳定，Task Model 随任务演进，World Model 版本化管理，Self Model 快速迭代
3. **跨模型引用通过 COGNITIVE_RELATES_TO 边实现**：例如 Task Model 中的 commitment 可以引用 User Model 中的偏好
4. **权限治理按 model_domain 分层**：用户必须能查看/编辑关于自己的 User Model 和 Task Model 记忆

---

## 1. User Model

### 1.1 概念

User Model 记录与特定用户相关的长期稳定特征。它不是用户档案（profile），而是 Agent 在与用户交互过程中**持续学习和更新**的认知模型。

### 1.2 与 DispositionProfile 的关系

```
UserModel（持久节点，多维度）
  └── DispositionProfile（检索偏好配置，7 维度）
        └── 只是 UserModel 的一个子集
```

DispositionProfile 当前覆盖：skepticism, evidence_demand, abstraction_preference, thoroughness, recency_bias, empathy, risk_tolerance

UserModel 扩展维度：

| 维度 | 语义 | 来源 | 更新频率 |
|------|------|------|---------|
| `communication_style` | 正式/口语/技术/业务 | 交互历史分析 | 慢 |
| `domain_expertise` | 专家/新手/跨领域 | 查询复杂度 + 反馈 | 慢 |
| `decision_style` | 数据驱动/直觉驱动/风险规避 | 决策历史分析 | 慢 |
| `preferred_evidence_format` | 表格/图表/文字/代码 | 显式反馈 | 中 |
| `attention_span` | 简短/详细/分层 | 交互模式分析 | 中 |
| `risk_appetite` | 保守/平衡/激进 | 决策结果反馈 | 慢 |

### 1.3 存储

```yaml
# CognitiveNode with model_domain="user"
id: "user_model_alice"
space_id: "space.finance"
cognitive_layer: "opinion"
memory_type: "mental_model"
model_domain: "user"
text: "Alice prefers concise risk summaries with charts. She is data-driven and skeptical of qualitative assessments."
attributes:
  user_id: "user_alice"
  communication_style: "concise_business"
  domain_expertise: "expert"
  decision_style: "data_driven"
  preferred_evidence_format: "chart"
  risk_appetite: "conservative"
  disposition_ref: "dp_alice_default"
confidence: 0.85
source_trust_tier: "behavior_inferred"
scope: '{"type": "user", "ref_id": "user_alice", "window": "permanent"}'
```

### 1.4 更新机制

```python
async def update_user_model(user_id, space_id, interaction_result):
    """从每次交互结果中提取用户偏好信号。"""
    user_model = await get_user_model(user_id, space_id)

    # 信号提取
    signals = extract_user_signals(interaction_result)
    # e.g., user asked for shorter answer → attention_span may be "short"
    # e.g., user corrected a data point → skepticism may increase

    # 渐进更新（高置信度信号才更新，防止噪声）
    for signal in signals:
        if signal.confidence > 0.7:
            user_model.attributes[signal.dimension] = signal.value
            user_model.last_confirmed_at = now()

    await update_cognitive_node(user_model)
```

---

## 2. Task Model

### 2.1 概念

Task Model 维护 Agent 与用户的**任务级上下文**，包括：
- 当前任务的状态和阶段
- 历史方案的否决/确认记录
- Artifact（产物）的版本演进
- Agent 对用户的承诺（commitment）及履行状态

### 2.2 核心记忆类型

#### commitment（承诺）

```yaml
# CognitiveNode with memory_type="commitment"
id: "commit_001"
space_id: "space.finance"
cognitive_layer: "opinion"
memory_type: "commitment"
model_domain: "task"
text: "Agent promised to deliver the risk assessment report by tomorrow 10am"
attributes:
  deadline: "2026-05-01T10:00:00Z"
  status: "pending"  # pending | fulfilled | overdue | cancelled
  task_id: "task_001"
  fulfilled_by: null  # episode_id when fulfilled
  reminder_sent: false
confidence: 0.95
source_trust_tier: "agent_generated"
scope: '{"type": "task", "ref_id": "task_001", "window": "until_deadline"}'
```

**生命周期**：
```
pending → [用户确认收到/Agent完成] → fulfilled
      → [deadline过期] → overdue → [用户宽容/Agent补救] → fulfilled
      → [用户取消] → cancelled
```

#### task_state（任务状态快照）

```yaml
# CognitiveNode with memory_type="task_state"
id: "task_state_001"
space_id: "space.finance"
cognitive_layer: "semantic"
memory_type: "task_state"
model_domain: "task"
text: "Task: Risk Assessment for Company A. Phase: data_collection. 2 commitments pending."
attributes:
  task_id: "task_001"
  task_name: "Risk Assessment for Company A"
  current_phase: "data_collection"  # data_collection | analysis | reporting | review
  decision_log:
    - decision: "reject_microservices"
      reason: "user_preference"
      timestamp: "2026-04-20T10:00:00Z"
  artifact_versions:
    - artifact_id: "report_001"
      version: "v1.2"
      created_at: "2026-04-25T10:00:00Z"
  pending_commitments: ["commit_001", "commit_002"]
confidence: 0.9
source_trust_tier: "agent_generated"
scope: '{"type": "task", "ref_id": "task_001", "window": "task_lifetime"}'
```

### 2.3 任务上下文检索

当用户 query 涉及当前任务时，系统应自动加载 Task Model：

```python
async def recall_with_task_context(query, space_id, user_id):
    # 1. 检测 query 是否涉及当前任务
    task_context = await detect_task_reference(query, space_id, user_id)

    # 2. 如果涉及，加载 Task Model
    if task_context:
        task_state = await get_task_state(task_context.task_id, space_id)
        commitments = await get_pending_commitments(task_context.task_id, space_id)
        decision_log = task_state.attributes["decision_log"]

        # 3. 将 Task Model 注入检索上下文
        enriched_query = f"{query}\n[Task Context] Phase: {task_state.current_phase}, Pending commitments: {len(commitments)}, Recent decisions: {decision_log[-3:]}"

    return await recall(enriched_query, space_id)
```

### 2.4 方案否决记忆

当用户否决 Agent 提出的方案时，记录否决原因，防止重复提议：

```python
async def record_decision(task_id, space_id, decision, reason, user_id):
    task_state = await get_task_state(task_id, space_id)
    task_state.attributes["decision_log"].append({
        "decision": decision,
        "reason": reason,
        "timestamp": now_iso(),
        "user_id": user_id,
    })

    # 生成 observation 记录否决
    await create_cognitive_node(
        memory_type="observation",
        model_domain="task",
        text=f"User {user_id} rejected '{decision}' because: {reason}",
        scope={"type": "task", "ref_id": task_id},
        source_trust_tier="behavior_inferred",
    )
```

---

## 3. World Model

### 3.1 概念

World Model 记录 Agent 运行环境的约束和结构。OntologyEngine 的 Schema L1-L4 已覆盖组织规则和业务约束，但缺少**动态环境上下文**。

### 3.2 与 Schema L1-L4 的关系

| 层级 | 当前覆盖 | 缺口 |
|------|---------|------|
| L1 EntityDeclaration | 实体类型定义 | — |
| L2 RelationDeclaration | 关系类型定义 | — |
| L3 MetricDeclaration | 指标计算规则 | — |
| L4 RuleDefinition | 业务规则 | — |
| **动态环境** | 无 | 代码库结构、API 状态、外部服务可用性 |

### 3.3 新增 constraint 类型

```yaml
# CognitiveNode with memory_type="constraint"
id: "constraint_001"
space_id: "space.finance"
cognitive_layer: "procedure"
memory_type: "constraint"
model_domain: "world"
text: "External API 'credit_check' has rate limit of 100 requests/minute"
attributes:
  constraint_type: "api_limit"
  enforceable: true
  violation_action: "throttle"
  affected_memory_types: ["observation", "opinion"]
  affected_tools: ["oe_execute_rule"]
confidence: 0.95
source_trust_tier: "environment_observed"
scope: '{"type": "global", "ref_id": "space.finance", "window": "until_updated"}'
```

**constraint 类型枚举**：
- `api_limit`: 外部 API 速率限制
- `business_rule`: 不可违反的业务规则（如"授信额度不超过注册资本 50%"）
- `technical_boundary`: 技术约束（如"单次查询最多返回 1000 条"）
- `temporal_constraint`: 时间约束（如"财报发布后 30 天内不可变更评级"）

### 3.4 动态环境感知

```python
async def observe_environment(space_id):
    """定期扫描环境状态，更新 World Model。"""
    # API 健康检查
    api_status = await check_api_health()
    for api_name, status in api_status.items():
        if status != "healthy":
            await create_or_update_constraint(
                space_id=space_id,
                constraint_type="api_limit",
                text=f"API {api_name} is {status}",
                source_trust_tier="environment_observed",
            )

    # 代码库结构变化（如果 Agent 有代码访问权限）
    repo_structure = await scan_repo_structure()
    await update_world_model(space_id, "repo_structure", repo_structure)
```

---

## 4. Self Model

### 4.1 概念

Self Model 是 Agent 关于**自身**的记忆——不是系统配置，而是 Agent 在运行过程中积累的**经验性知识**：
- 工具调用的成功/失败模式
- 特定环境下的异常行为
- Agent 自己的暂定假设和验证状态

> **[关键设计点]**：Self Model 使 Agent 能从失败中学习。没有 Self Model，Agent 每次调用工具都从零开始，无法记住"上次这个工具超时了"或"这个 API 在这个环境下不稳定"。

### 4.2 核心记忆类型：self_experience

```yaml
# CognitiveNode with memory_type="self_experience"
id: "self_exp_001"
space_id: "space.finance"
cognitive_layer: "perception"
memory_type: "self_experience"
model_domain: "self"
text: "Tool 'oe_execute_rule' timed out when evaluating rule R-101 on Company A with incomplete financial data"
attributes:
  tool_name: "oe_execute_rule"
  call_result: "timeout"  # success | timeout | error | rate_limited
  error_type: "timeout"
  latency_ms: 30000
  retry_count: 2
  context_summary: "Rule R-101 evaluation on Company A"
  lesson: "Pre-validate entity attributes before rule execution"
  suggested_workaround: "Use oe_query to check entity completeness first"
confidence: 0.9
source_trust_tier: "agent_generated"
scope: '{"type": "global", "ref_id": "space.finance", "window": "recent"}'
```

### 4.3 工具可靠性评分

```python
class ToolReliabilityTracker:
    async def record_call(self, tool_name, result, latency_ms, error_type=None):
        # 更新工具可靠性统计
        experiences = await get_self_experiences(tool_name=tool_name)

        success_count = sum(1 for e in experiences if e.call_result == "success")
        total_count = len(experiences)
        reliability = success_count / total_count if total_count > 0 else 1.0

        # 如果可靠性低于阈值，生成 constraint
        if reliability < 0.5 and total_count >= 5:
            await create_constraint(
                text=f"Tool {tool_name} has low reliability ({reliability:.0%}) in current environment",
                constraint_type="technical_boundary",
                affected_tools=[tool_name],
            )

    async def get_reliability(self, tool_name):
        experiences = await get_self_experiences(tool_name=tool_name)
        success_count = sum(1 for e in experiences if e.call_result == "success")
        return success_count / len(experiences) if experiences else 1.0
```

### 4.4 工具选择时的 Self Model 引用

```python
async def select_tool_with_self_model(available_tools, task_context):
    """选择工具时参考 Self Model 中的经验。"""
    candidates = []
    for tool in available_tools:
        reliability = await ToolReliabilityTracker.get_reliability(tool.name)

        # 获取相关经验
        experiences = await get_self_experiences(tool_name=tool.name)
        relevant_exp = [
            e for e in experiences
            if is_context_similar(e.context_summary, task_context)
        ]

        candidates.append({
            "tool": tool,
            "reliability": reliability,
            "relevant_experiences": relevant_exp,
            "score": tool.base_score * reliability + len(relevant_exp) * 0.1
        })

    # 按 score 排序，返回最佳工具
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]["tool"]
```

### 4.5 暂定假设（Working Hypothesis）

Agent 在信息不完整时可以形成暂定假设，并在后续验证：

```python
async def form_working_hypothesis(evidence, confidence_threshold=0.6):
    if evidence.confidence < confidence_threshold:
        hypothesis = await create_cognitive_node(
            memory_type="opinion",
            model_domain="self",
            text=f"Hypothesis: {evidence.text}",
            attributes={
                "hypothesis_type": "working",
                "based_on": evidence.id,
                "verification_status": "pending",
            },
            confidence=evidence.confidence,
            source_trust_tier="agent_generated",
        )
        return hypothesis
```

---

## 5. 四建模对象的检索影响

### 5.1 QueryUnderstandingLayer 中的模型加载

```python
async def extract_task_constraints(query, space_id, user_id):
    constraints = TaskConstraints()

    # 1. 检测是否涉及用户偏好
    if implies_user_preference(query):
        user_model = await get_user_model(user_id, space_id)
        constraints.user_preference = True
        constraints.user_model_ref = user_model.id

    # 2. 检测是否涉及任务历史
    if implies_task_history(query):
        active_tasks = await get_active_tasks(user_id, space_id)
        constraints.task_history = True
        constraints.task_ids = [t.id for t in active_tasks]

    # 3. 检测是否涉及环境约束
    if implies_environmental_constraint(query):
        constraints.environmental = True

    # 4. 检测是否涉及 Agent 自身经验
    if implies_self_reference(query):
        constraints.self_reference = True

    return constraints
```

### 5.2 检索策略调整

| 约束类型 | 检索调整 |
|---------|---------|
| `user_preference` | 优先检索 `model_domain=user` 的 mental_model/opinion |
| `task_history` | 优先检索 `scope.task_id=current_task` 的 episode/commitment/task_state |
| `environmental` | 优先检索 `model_domain=world` 的 constraint |
| `self_reference` | 优先检索 `model_domain=self` 的 self_experience |

---

## 6. 权限治理

### 6.1 按 model_domain 的权限矩阵

| 操作 | User Model | Task Model | World Model | Self Model |
|------|-----------|-----------|------------|-----------|
| 查看自己的 | ✅ 用户 | ✅ 用户 | ✅ 所有用户 | ✅ 用户 |
| 查看他人的 | ❌ | △（同空间共享任务可见） | ✅ | ❌ |
| 编辑自己的 | ✅ 用户 | ✅ 用户 | ❌（仅管理员） | ❌（Agent 自治） |
| 删除自己的 | ✅ 用户 | ✅ 用户 | ❌ | ❌ |
| 编辑他人的 | ❌ | ❌ | ❌ | ❌ |

### 6.2 API 权限检查

```python
async def check_permission(node_id, user_id, action):
    node = await get_cognitive_node(node_id)

    # 用户只能操作自己的 User Model 和 Task Model
    if node.model_domain in ("user", "task"):
        if node.attributes.get("user_id") != user_id:
            raise PermissionError("Cannot modify another user's personal memory")

    # World Model 只能由管理员编辑
    if node.model_domain == "world" and action in ("edit", "delete"):
        if not await is_admin(user_id):
            raise PermissionError("World Model can only be modified by admins")

    # Self Model 由 Agent 自治，用户可查看但不可编辑
    if node.model_domain == "self":
        if action in ("edit", "delete"):
            raise PermissionError("Self Model is autonomously managed by the Agent")
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| 知识库流程 | `docs/01-overview/10-kb-process.md` |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 记忆生命周期 | `docs/02-design/agent-memory/memory-lifecycle.md` |
| 认知操作 API | `docs/02-design/agent-memory/memory-api.md` |
| 外部批判框架 | `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` |
| Session 记录 | `discuss/2026-04-28-session-agent-memory-lencx-critique-integration.md` |

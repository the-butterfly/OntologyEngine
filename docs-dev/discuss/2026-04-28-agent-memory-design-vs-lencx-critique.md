# Agent 记忆设计审视：OntologyEngine vs lencx 外部批判框架

> **状态**: 待评审 | **撰写日期**: 2026-04-28 | **单一事实源**: 本文档（与 `docs/02-design/agent-memory/` 互补）
> **对比维度**: 记忆≠蒸馏、4 建模对象、6 记忆维度、3 闭环链路、治理优先

---

## 1. 外部批判框架总述

微信公众号文章《记忆不是蒸馏》提出的核心批判框架：

| 维度 | 主张 | 对 OntologyEngine 的直接质问 |
|------|------|----------------------------|
| **记忆本质** | 记忆≠蒸馏；蒸馏是管理环节的一个操作，不是记忆本身 | Consolidation 引擎是否过度将“碎片→结构化结论”当作记忆的核心？ |
| **4 建模对象** | User Model / Task Model / World Model / Self Model | 当前 7 种 memory_type 是否从建模对象维度覆盖？特别是 Self Model 缺失 |
| **6 记忆维度** | content / type / confidence / source / scope / time-decay | CognitiveNode 字段是否完整覆盖？scope 是否缺失？ |
| **3 闭环链路** | 写入（边际价值判断）/ 管理（冲突+衰减+来源+权限）/ 读取（任务约束驱动） | recall 是否仍是 RAG 式语义召回？写入是否缺少边际价值判断？ |
| **核心挑战** | 治理（governance）优先于容量 | 权限治理、来源可信层级、策略性遗忘是否充分？ |

---

## 2. 逐维度对照审视

### 2.1 记忆≠蒸馏：Consolidation 的定位是否过度？

**lencx 观点**: 蒸馏（distillation）本质是归档——把长期不被引用的信息压缩成摘要。它的输出是“静态结论”，不擅长保留“形成结论的轨迹”。**记忆必须保留形成判断的上下文**，否则 Agent 只能复述结论，无法解释“为什么现在信这个”。

**OntologyEngine 现状**:

| 机制 | 现状 | 是否满足"保留轨迹" |
|------|------|-------------------|
| `CONSOLIDATED_INTO` 边 | fragment → observation | ✓ 保留原始碎片到归纳结论的映射 |
| `source_fragment_ids` 数组 | CognitiveNode 强类型字段 | ✓ 快速溯源 |
| `history` 字段 | JSON 数组，记录每次变更 | △ 记录的是结论变更历史，不是推理轨迹 |
| Consolidation 输出 | observation/entity/mental_model | ✗ 是静态结论，不包含 LLM 归纳时的推理过程 |
| 反思报告 | `Insight` + `ContradictionReport` | △ 记录洞察和矛盾，但不记录"信念演变路径" |

**差距判定**: **P1（设计缺失）**

- **什么问题**: Consolidation 引擎把归纳产物（observation/entity）当作记忆的“升级形态”，但没有显式保留**归纳推理的上下文**（例如：LLM 为什么认为这 3 个碎片可以归纳为一条 observation）。
- **何时影响**: 当 Agent 需要解释“你为什么相信这个结论”时，只能给出碎片列表，无法给出归纳逻辑。
- **与 lencx 的偏差**: lencx 强调“记忆不仅要存结论，还要存结论的形成过程”。OntologyEngine 的 history 记录的是“结论变了什么”，不是“结论怎么来的”。

**建议**:
1. 在 `CognitiveNode` 中增加 `consolidation_reasoning` 字段（或独立的 `ReasoningTrace` 节点），记录 LLM 归纳时的关键推理步骤。
2. 将 Consolidation 的 LLM 输出从“仅返回结论”改为“返回结论 + 推理摘要”，后者作为轨迹存入。
3. 明确区分 **Consolidation（知识归纳）** 与 **Distillation（信息压缩归档）**：前者面向结构化升级，后者面向长期存储优化。当前设计没有独立的 Distillation 机制。

---

### 2.2 四建模对象：User / Task / World / Self

**lencx 观点**: 记忆系统必须维护四个相互独立但可引用的模型：

| 模型 | 核心内容 | 在 OntologyEngine 中的映射 |
|------|---------|---------------------------|
| **User Model** | 用户偏好、风险容忍度、沟通习惯 | △ `DispositionProfile` 部分覆盖偏好和风险，但没有“沟通习惯”维度 |
| **Task Model** | 方案否决/确认历史、artifact 版本、承诺状态、待办事项 | ✗ 完全缺失。没有 `commitment` 类型，没有 artifact 版本追踪 |
| **World Model** | 环境约束（仓库结构、API 定义、组织规则） | △ `Schema L1-L4` 覆盖组织规则，`rule` 类型部分覆盖环境约束，但缺少“仓库结构/代码库上下文”这类动态环境 |
| **Self Model** | Agent 自身经验（失败路径、工具不稳定记录、暂定假设） | ✗ 完全缺失。没有 `self_experience` 或 `tool_reliability` 类型 |

**差距判定**: **P0（架构缺口）**

- **Task Model 缺失**: 当前设计没有任何机制记录 Agent 对用户的承诺（如“我明天给你这个报告”）、任务方案的历史否决（如“方案 A 已被用户否定”）、或 artifact 版本演进。这意味着 Agent 在多轮交互中无法维护任务状态上下文。
- **Self Model 缺失**: Agent 无法记录“上次调用这个工具超时了”“这个 API 在这个环境下不稳定”等自我经验。这在 MCP/Tool-Calling 场景下是严重缺失——Agent 每次调用工具都从零开始，无法从失败中学习。

**建议**:
1. **新增记忆类型**: 在 `memory_type` 中增加 `commitment`（承诺）、`task_state`（任务状态快照）、`self_experience`（Agent 自身经验）。
2. **Task Model 设计**: 每个 task 对应一个 `TaskContext` 节点，关联 `commitment`（待履行承诺）、`artifact_version`（产物版本）、`decision_log`（方案否决/确认历史）。
3. **Self Model 设计**: 新增 `ToolReliabilityLog` 节点，记录工具调用结果（成功/失败/超时/错误类型），供后续工具选择时参考。
4. **建模对象作为一级属性**: 建议在 `CognitiveNode` 中增加 `model_domain` 字段（`user` / `task` / `world` / `self`），与 `memory_type` 正交，形成“建模对象 × 记忆类型”的二维分类。

---

### 2.3 六记忆维度：content / type / confidence / source / scope / time-decay

**lencx 六维度**与 **CognitiveNode 字段对照**:

| lencx 维度 | CognitiveNode 字段 | 覆盖度 | 差距 |
|-----------|-------------------|--------|------|
| content | `text`, `attributes` JSON | ✓ 完整 | — |
| type | `memory_type` (7 种) | △ 部分 | lencx 的 type 更偏语义（event/assertion/belief/constraint/commitment），OntologyEngine 的 type 偏存储形态（fragment/observation/entity/...）。两者不冲突，但缺少语义类型标签 |
| confidence | `confidence` (float) | ✓ 完整 | — |
| source | `source_fragment_ids`, `source_pipeline` | △ 部分 | 缺少来源的**可信层级**（user_declared vs behavior_inferred vs environment_observed vs agent_generated） |
| scope | 无统一字段 | ✗ 缺失 | `mental_model` 有 `scope` 属性，但 observation/entity/episode 没有。缺少“此记忆适用于哪个 task / user / time window” |
| time-decay | `valid_from`, `valid_to`, `strength`, `last_accessed_at` | △ 部分 | 缺少“上次被**确认/强化**的时间”（confirmation timestamp）。strength 衰减基于访问，不是基于“被证实的程度” |

**差距判定**:

- **来源可信层级（P1）**: 当前 `source_pipeline` 记录的是处理流程（`ingestion`/`extraction`/`consolidation`），不是来源的可信度。lencx 强调“没有 provenance 分层，Agent 无法区分扎实的用户声明和高置信幻觉”。
- **Scope 缺失（P0）**: 几乎所有记忆类型都没有显式 scope。这意味着 Agent 无法判断“这条 observation 只适用于 task A”还是“适用于所有任务”。跨任务污染风险高。
- **确认时间缺失（P1）**: `strength` 基于 Ebbinghaus 衰减，但衰减速度应与“被后续证据确认的次数”相关，而不只是“被访问的次数”。

**建议**:
1. **新增 `source_trust_tier` 字段**: `user_declared` (最高) > `behavior_inferred` > `environment_observed` > `agent_generated` (最低)。
2. **统一 `scope` 字段**: 所有 CognitiveNode 增加 `scope` 属性，格式为 `{ "type": "task|user|global", "ref_id": "...", "window": "..." }`。
3. **新增 `last_confirmed_at` 字段**: 每次后续证据支持该记忆时更新，用于替代/补充 `last_accessed_at` 作为衰减参考。

---

### 2.4 三条闭环链路

#### 2.4.1 写入链路：边际价值判断缺失

**lencx 观点**: “写入不是‘这个信息有没有价值’，而是‘相对于已有记忆，这个信息的**边际价值**是多少’。” 如果新信息只是重复已有知识，写入就是浪费 token；如果新信息与已有知识矛盾，写入价值极高。

**OntologyEngine 现状**:

- `oe_remember` → `IngestionService` → 直接写入 Layer-R (`KnowledgeFragmentNode`)
- 写入后触发异步 Consolidation（若碎片数超过阈值）
- **没有边际价值评估**: 来了就存，不判断“这条碎片是否增加新信息”

**差距判定**: **P1**

- **问题**: 存储膨胀。大量重复性碎片（如用户每天说类似的话）会不断累积，增加检索噪声和 Consolidation 负担。
- **建议**: 在写入前增加 **DeduplicationGate**：
  1. 快速向量相似度检查：若新碎片与已有碎片相似度 > 0.92，标记为 `duplicate`，不写入或仅更新访问时间。
  2. 矛盾检测前置：若新碎片与已有 observation 语义冲突（通过轻量级向量+规则），标记为 `contradiction_candidate`，高优先级触发 Consolidation。
  3. 边际价值评分：`marginal_value = novelty_score * relevance_score / redundancy_penalty`，低于阈值时延迟写入或写入低优先级队列。

#### 2.4.2 管理链路：冲突处理与策略性遗忘薄弱

**lencx 观点**: 管理是最难的一环，包括：整合（consolidation）、冲突处理（conflict resolution）、衰减与遗忘（decay & forgetting）、来源追踪（provenance）、权限治理（permission governance）。

**OntologyEngine 现状对照**:

| 管理子项 | 现状 | 差距 |
|---------|------|------|
| 整合 (Consolidation) | ConsolidationEngine 已实现，Create/Update/Delete 三动作模型 | ✓ 较完整 |
| 冲突处理 | `detect_contradictions`（规则+LLM 双层）+ `ContradictionReport` | △ 有检测但缺少**自动裁决机制**。检测到矛盾后，依赖人工或 ReflectAgent 间接触发，没有“证据权重自动裁决” |
| 衰减与遗忘 | `ForgettingEngine`（价值感知 Ebbinghaus）+ `strength` 字段 | △ 衰减基于访问频率，缺少“被后续证据否定”的**策略性遗忘** |
| 来源追踪 | `source_fragment_ids` + `source_pipeline` + `history` | △ 缺少可信层级（见 2.3） |
| 权限治理 | `tags` 隔离 + `ownership` 字段讨论中 | ✗ 没有正式的权限模型。用户无法查看/编辑/删除 Agent 记忆 |

**关键差距**:

1. **自动裁决（P1）**: 当前矛盾检测输出 `ContradictionReport`（包含 `suggested_resolution`），但没有**裁决引擎**自动执行 resolution。lencx 强调“检测到冲突后必须能裁决，否则 Agent 会在矛盾信息间摇摆”。
2. **策略性遗忘（P1）**: 遗忘当前是“strength 衰减到阈值以下就淘汰”，但 lencx 指出“什么该忘？被后续信号反复否定的旧 belief，高度情境依赖且低泛化的细节”。当前设计没有“否定信号”驱动的遗忘。
3. **权限治理（P0）**: 完全没有。用户必须能查看 Agent 记忆（特别是 self model 和 user model 中关于自己的部分），并有权删除或更正。

**建议**:
1. **裁决引擎**: 新增 `ArbitrationEngine`，基于证据权重（proof_count × source_trust_tier × recency）自动裁决矛盾，更新 `belief_status` 为 `accepted` / `superseded` / `rejected`。
2. **否定信号驱动遗忘**: 当 `ContradictionReport` 中某节点被裁决为 `superseded` 或 `rejected` 时，触发加速遗忘（strength 骤降，valid_to 提前）。
3. **权限治理**: 引入 `AccessControl` 模型，定义记忆的可视范围（owner / shared / private），并在 API 层增加 `oe_list_my_memories`、`oe_correct_memory`、`oe_delete_memory`。

#### 2.4.3 读取链路：从语义召回到任务约束驱动

**lencx 观点**: “当前 RAG 式语义相似召回的根本局限：相关性不由表面语义决定。一个用户在讨论项目架构时的 query，与‘他上周否决过微服务方案’高度相关，但表面语义完全不匹配。” **读取应从语义相似升级为“任务约束驱动的检索-推断耦合”**。

**OntologyEngine 现状**:

- `oe_recall` → `QueryService` → RRF 四路融合（向量检索 + 关键词 + 图遍历 + 结构化过滤）
- `ReflectAgent` → 强制检索序列（mental_model → entity → observation）
- **本质仍是语义驱动**: 用户 query → 向量嵌入 → 相似度召回

**差距判定**: **P0（架构方向偏差）**

- **问题**: 即使 RRF 融合四路，核心仍是“query 与记忆的表面语义相似度”。当用户说“这个项目用什么架构”时，系统无法自动联想到“用户上周否决过微服务”这一高度相关但语义不匹配的 memory。
- **与 lencx 的差距**: lencx 主张的读取是两层——先由**任务理解层**判断当前决策受什么约束（如“用户偏好单体架构”），再找对应记忆。OntologyEngine 缺少这个“任务理解→约束提取→记忆匹配”的中间层。

**建议**:
1. **引入 `QueryUnderstandingLayer`**:
   - 输入：用户 query + 当前 task context（task_id, 历史交互）
   - 输出：`TaskConstraints`（当前任务涉及的约束类型：用户偏好约束、时间约束、资源约束等）
2. **约束驱动的检索**: 根据 `TaskConstraints` 动态调整检索策略：
   - 若约束包含 `user_preference`，优先检索 `memory_type=opinion` + `model_domain=user` 的记忆
   - 若约束包含 `task_history`，优先检索 `memory_type=episode` + `scope.task_id=current_task` 的记忆
3. **不要替换语义召回，而是叠加**: 语义召回作为基础层，约束驱动作为重排序层（类似 RRF 之后的第二层融合）。

---

### 2.5 核心挑战：治理优先于容量

**lencx 观点**: “记忆系统最大的风险不是‘存不下’，而是‘管不好’——矛盾没人管、来源不可信、权限不透明、Agent 在幻觉和用户真实意图间无法区分。”

**OntologyEngine 治理成熟度自评**:

| 治理维度 | 成熟度 | 说明 |
|---------|--------|------|
| 矛盾检测 | ★★★☆☆ | 有规则+LLM 双层检测，但无自动裁决 |
| 来源追踪 | ★★★☆☆ | 有 source_fragment_ids，但无可信层级 |
| 权限治理 | ★☆☆☆☆ | 仅有 tags 隔离，无用户级权限 |
| 策略性遗忘 | ★★☆☆☆ | Ebbinghaus 衰减，无否定信号驱动 |
| 轨迹保留 | ★★☆☆☆ | history 记录变更，不记录推理过程 |
| 写入控制 | ★★☆☆☆ | 无去重门，无边际价值判断 |
| 读取质量 | ★★★☆☆ | RRF 四路融合，但无任务约束驱动 |

---

## 3. 设计修正建议汇总

### 3.1 Schema 变更（CognitiveNode）

```
CognitiveNode {
  # 已有字段
  id, space_id, cognitive_layer, memory_type, text,
  tags, source_fragment_ids, history, proof_count,
  confidence, consolidated_at, updated_at,
  valid_from, valid_to, strength, last_accessed_at,
  belief_status, superseded_by, attributes, schema_ref,
  schema_alignment_score,

  # 新增字段
  model_domain: "user" | "task" | "world" | "self" | null,
  source_trust_tier: "user_declared" | "behavior_inferred" | "environment_observed" | "agent_generated",
  scope: {
    type: "task" | "user" | "global",
    ref_id: str,        # task_id or user_id
    window: str | null, # 时间窗口描述
  },
  last_confirmed_at: str | null,  # ISO timestamp
  consolidation_reasoning: str | null,  # LLM 归纳时的推理摘要
}
```

### 3.2 新增记忆类型

| 新增类型 | 建模对象 | 语义 | 生命周期 |
|---------|---------|------|---------|
| `commitment` | Task | Agent 对用户的承诺（如“明天给你报告”） | 履行后归档，过期未履行升级为高优先级提醒 |
| `task_state` | Task | 任务快照（当前方案、否决历史、artifact 版本） | 随任务演进更新 |
| `self_experience` | Self | Agent 自身经验（工具失败、环境异常） | 成功后强化，失败后写入 |
| `constraint` | World | 不可违反的环境边界（API 限制、规则约束） | 长期有效，变更时版本化 |

### 3.3 新增/增强引擎

| 引擎 | 职责 | 优先级 |
|------|------|--------|
| `DeduplicationGate` | 写入前边际价值判断 + 去重 | P1 |
| `ArbitrationEngine` | 矛盾自动裁决（证据权重计算） | P1 |
| `QueryUnderstandingLayer` | 任务约束提取 → 驱动检索策略 | P0 |
| `PermissionGovernance` | 用户查看/编辑/删除记忆权限 | P0 |

### 3.4 API 扩展

```python
# 用户权限相关
oe_list_my_memories(space_id, scope_type="user")
oe_correct_memory(node_id, corrected_text, reason)
oe_delete_memory(node_id, cascade=False)

# 任务相关
oe_record_commitment(space_id, text, deadline, task_id)
oe_check_commitments(space_id, status="pending")

# 查询增强
oe_recall_with_constraints(query, space_id, task_context=None)
```

---

## 4. 与现有 discuss 报告的衔接

| 本报告发现 | 对应 discuss 报告 | 衔接关系 |
|-----------|-----------------|---------|
| 轨迹保留缺失 | `2026-04-27-agent-memory-design-analysis.md` 缺陷 #6 | 补充细化：不仅是“reflection 边界窄”，更是“推理轨迹未显式存储” |
| 四建模对象缺失 | `2026-04-27-four-layer-cognitive-interaction-analysis.md` | 四层认知（Perception/Semantic/Opinion/Procedure）与四建模对象（User/Task/World/Self）是正交维度，应形成 4×4 矩阵 |
| 来源可信层级 | `2026-04-27-key-decision-review-gbrain-llmwiki.md` 决策 #4 | 与“双栏（编译真理+时间线）”互补：可信层级解决“哪一栏更可信” |
| 任务约束驱动检索 | `2026-04-27-recommendation-schemes-detailed-design.md` 方案 #6 | 直接支持“读写分离一致性”中的读优化方向 |
| 权限治理 | `2026-04-27-recommendation-schemes-detailed-design.md` 方案 #7 | 为“分层所有权”提供具体字段和 API 设计 |
| Self Model | `2026-04-27-cognitive-schema-integration-deep-dive.md` | Schema 提取模板应包含 `self_experience` 的提取规则 |

---

## 5. 关键结论

1. **OntologyEngine 的 Agent 记忆设计在存储形态和生命周期管理上已较为完整**（Consolidation、Forgetting、Reflect 三引擎齐备），但在**认知语义维度**上存在系统性缺口。

2. **最大缺口是四建模对象的缺失**，尤其是 **Task Model**（承诺、任务状态）和 **Self Model**（Agent 自我经验）。这导致 Agent 在多轮任务交互和工具调用中无法维护上下文，也无法从失败中学习。

3. **读取链路的架构方向需要调整**：从“语义相似召回”叠加“任务约束驱动的重排序”是可行路径，不应完全推翻现有 RRF 设计，但需要在 `QueryService` 和 `ReflectAgent` 之间增加 `QueryUnderstandingLayer`。

4. **治理是核心挑战，当前成熟度不足**：权限治理几乎空白，自动裁决缺失，策略性遗忘未实现。建议将“治理层”作为 Phase 2b 之后的独立阶段（Phase 2e）重点投入。

5. **记忆≠蒸馏的批判直接命中当前设计的认知盲区**：Consolidation 不应被当作记忆的“终极目标”，而应被看作管理链路中的一个环节。记忆的终极目标是**支持 Agent 在特定任务约束下做出正确决策**，而非把一切都归纳为结构化结论。

# 四层认知功能的交互影响与检索架构设计分析

> **status**: analysis | **phase**: phase2 | **topic**: Agent记忆系统架构 | **date**: 2026-04-27
> **[关键设计点]**: 本文档分析感知/情景层、语义/事实层、观点/信念层、程序/技能层之间的交互机制，以及对检索架构的深层影响。

---

## 执行摘要

当前OntologyEngine采用"双层存储+类型标签"架构（Layer-R/Layer-S × memory_type），将四层次认知功能压缩到同一存储层内。这种设计在工程上简洁，但在**认知交互的表达能力**上存在结构性不足：

1. **层间影响是单向链**（fragment→observation→entity→mental_model），缺少反馈环和横向交叉连接
2. **检索是静态权重排序**，缺少Disposition驱动的动态权重调整
3. **证据传递只有自下而上**（CONSOLIDATED_INTO），缺少自上而下的注意力引导和程序约束
4. **时序更新是异步批处理**，缺少新信息到达时的级联更新机制

本文提出：在保留双层存储的前提下，通过**引入跨层影响边类型**、**Disposition驱动的动态检索权重**、**级联更新触发器**和**分层漏斗检索协议**，将OntologyEngine的认知交互能力从"静态标签"提升到"动态网络"。

---

## 问题1：四层认知之间如何互相影响？

### 1.1 自上而下的影响（高层→低层）

#### 1.1.1 Mental Model 如何引导感知层的注意力

**当前设计的问题**：

当前OntologyEngine的mental_model只是一个`memory_type="mental_model"`的MemoryUnitNode，与其他类型（entity/observation/fragment）的区别仅在于检索权重（3.0 vs 1.0-2.0）。它**不能主动影响**新碎片的提取、编码或检索优先级。

**对比Hindsight**：

Hindsight的Mental Model具有`trigger`配置和`last_refreshed_at`机制。当Consolidation完成后，系统检查`trigger.refresh_after_consolidation`，若命中则自动刷新Mental Model（`compute_mental_model_is_stale()`）。更重要的是，Hindsight的Reflect Agent在检索时**强制按优先级检索**：mental_models → observations → memories，这种强制顺序本身就是一种注意力引导。

**具体机制设计**：

引入`ATTENTION_GUIDE`边和`PerceptualFilter`数据结构：

```cypher
-- 新增边类型：高层对低层的注意力引导
CREATE REL TABLE ATTENTION_GUIDE (
    FROM MemoryUnitNode TO MemoryUnitNode,
    guide_type STRING,        -- "boost" | "suppress" | "expect"
    weight DOUBLE,            -- 引导强度 [0, 1]
    scope_tags STRING[],      -- 影响的标签范围
    created_at STRING,
    expires_at STRING         -- 注意力引导的有效期
)
```

```python
@dataclass
class PerceptualFilter:
    """Mental Model 对感知层的注意力配置"""
    mental_model_id: str
    boost_patterns: list[str]      -- 语义模式（如"debt_ratio", "risk_grade"）
    suppress_patterns: list[str]   -- 应忽略的噪声模式
    expected_tags: list[str]       -- 优先处理的标签
    freshness_window_hours: int    -- 对新碎片的时效偏好
    
    def apply_to_fragment(self, fragment: KnowledgeFragment) -> float:
        score = 1.0
        for pattern in self.boost_patterns:
            if pattern in fragment.text.lower():
                score *= 1.5
        for pattern in self.suppress_patterns:
            if pattern in fragment.text.lower():
                score *= 0.3
        return score
```

**工作流**：

```
新碎片到达 Layer-R
    ↓
查询与该碎片标签重叠的 active mental_models
    ↓
对每个 mental_model，检查其 ATTENTION_GUIDE 边
    ↓
应用 PerceptualFilter 调整碎片编码权重：
    - 匹配的碎片：embedding 权重 ×1.5，strength 初始值 +0.2
    - 抑制的碎片：embedding 权重 ×0.3，strength 初始值 -0.1
    - 期望标签：优先触发 consolidation
    ↓
碎片进入 Layer-R 存储
```

**算法**：`apply_attention_guidance`

```python
async def apply_attention_guidance(space_id: str, fragment: KnowledgeFragment):
    # 1. 查找活跃的 mental_models（is_stale=false）
    active_models = await kuzu.query("""
        MATCH (mm:MemoryUnitNode {space_id: $space_id, memory_type: 'mental_model'})
        WHERE mm.attributes['is_stale'] = 'false'
        RETURN mm.unit_id, mm.tags, mm.attributes
    """, {"space_id": space_id})
    
    # 2. 对每个 mental_model 查找其 ATTENTION_GUIDE 边
    for model in active_models:
        guides = await kuzu.query("""
            MATCH (mm:MemoryUnitNode {unit_id: $model_id})-[g:ATTENTION_GUIDE]->(target)
            RETURN g.guide_type, g.weight, g.scope_tags
        """, {"model_id": model["unit_id"]})
        
        # 3. 计算匹配度并调整碎片属性
        for guide in guides:
            if any(tag in fragment.tags for tag in guide["scope_tags"]):
                adjustment = guide["weight"] * (1.5 if guide["guide_type"] == "boost" else 0.3)
                fragment.strength = min(1.0, fragment.strength + adjustment * 0.2)
                fragment.metadata["attention_guided_by"] = model["unit_id"]
                break
    
    return fragment
```

#### 1.1.2 Opinion 如何过滤检索结果

**当前设计的问题**：

OntologyEngine没有显式的`opinion`或`belief`类型。观点层的内容被归入`observation`或`mental_model`，无法区分"客观事实"和"主观信念"。这导致检索时可能将矛盾的观点同时返回给用户。

**对比Hindsight**：

Hindsight明确区分了World Fact（客观事实）和Experience Fact（Agent经历）。更重要的是，Hindsight的Disposition系统（`skepticism`/`empathy`/`literalism`）通过Prompt注入影响Reflect Agent的推理风格——高`skepticism`的Agent会更积极地质疑和过滤检索结果。

**对比Kumiho**：

Kumiho的AGM信念修正框架中，`Supersedes`边表示新信念取代旧信念。检索时，被 superseded 的信念应被过滤或标记为过时。

**具体机制设计**：

引入`OPINION` memory_type 和`SUPERSEDES`/`CONTRADICTS`边：

```cypher
-- 扩展 memory_type 枚举
-- entity | observation | mental_model | episode | procedure | rule | opinion

CREATE REL TABLE SUPERSEDES (
    FROM MemoryUnitNode TO MemoryUnitNode,
    supersedence_reason STRING,    -- "newer_evidence" | "authority_override" | "retraction"
    supersedence_confidence DOUBLE,
    created_at STRING
)

CREATE REL TABLE CONTRADICTS (
    FROM MemoryUnitNode TO MemoryUnitNode,
    contradiction_type STRING,     -- "factual" | "temporal" | "value"
    detection_method STRING,       -- "llm_detected" | "rule_detected" | "user_flagged"
    confidence DOUBLE,
    created_at STRING
)
```

```python
@dataclass
class BeliefFilter:
    """检索时的信念过滤配置"""
    disposition_skepticism: float = 0.5   -- [0,1]，越高越倾向于过滤矛盾结果
    filter_superseded: bool = True        -- 是否过滤被取代的信念
    expose_contradictions: bool = True    -- 是否显式暴露矛盾（而非隐藏）
    
    async def apply(self, results: list[MemoryUnit]) -> list[MemoryUnit]:
        filtered = []
        for result in results:
            # 检查是否被 superseded
            if self.filter_superseded and await self._is_superseded(result.id):
                continue
            
            # 高怀疑倾向：降低矛盾信念的排序分数
            contradictions = await self._find_contradictions(result.id)
            if contradictions and self.disposition_skepticism > 0.7:
                result.effective_score *= 0.5
                result.metadata["has_contradictions"] = len(contradictions)
            
            filtered.append(result)
        return filtered
```

**Opinion 的检索过滤协议**：

```
检索结果候选池
    ↓
对每个 candidate(type=opinion 或 type=observation 且 confidence < 0.7):
    1. 查询 CONTRADICTS 入边：是否有其他记忆声称此记忆为假？
    2. 查询 SUPERSEDES 入边：是否有更新版本？
    3. 检查 occurred_at：是否有更新的 observation 覆盖同一主题？
    ↓
根据 Disposition.skepticism 决定：
    - skepticism >= 0.7: 过滤所有有矛盾的结果，仅保留最高置信度版本
    - skepticism 0.4-0.7: 保留但降权，标记 contradiction_count
    - skepticism < 0.4: 保留所有，由消费方决定
    ↓
输出过滤后的结果池
```

#### 1.1.3 Procedure 如何约束事件提取

**当前设计的问题**：

当前`procedure`类型存储操作步骤（`steps`列表），但**从未被主动调用**来约束新episode的提取或observation的生成。procedure与episode之间只有`LEARNED_INTO`归纳边，没有"procedure指导episode识别"的反向边。

**对比MAGMA**：

MAGMA的"策略引导遍历"（Adaptive Traversal Policy）允许高层程序（如"风险分析流程"）直接影响检索路径。Procedure不是被动存储，而是**主动指导**系统如何处理新信息。

**具体机制设计**：

引入`CONSTRAINS`边和`ExtractionConstraint`：

```cypher
CREATE REL TABLE CONSTRAINS (
    FROM MemoryUnitNode TO MemoryUnitNode,
    constraint_type STRING,    -- "required_field" | "validation_rule" | "tag_inheritance"
    constraint_expr STRING,    -- 约束表达式（如 "debt_ratio > 0.0"）
    enforcement_level STRING,  -- "hard" | "soft" | "suggest"
    created_at STRING
)
```

```python
@dataclass
class ExtractionConstraint:
    """Procedure 对新事件/碎片提取的约束"""
    procedure_id: str
    required_attributes: dict[str, str]   -- 提取时必须包含的字段
    validation_predicates: list[str]      -- CEL表达式列表
    tag_inheritance: list[str]            -- 新提取自动继承的标签
    
    def validate_fragment(self, fragment: KnowledgeFragment) -> tuple[bool, list[str]]:
        violations = []
        for attr, expected_type in self.required_attributes.items():
            if attr not in fragment.metadata:
                violations.append(f"Missing required attribute: {attr}")
        for predicate in self.validation_predicates:
            if not evaluate_cel(predicate, fragment.metadata):
                violations.append(f"Validation failed: {predicate}")
        return len(violations) == 0, violations
```

**约束工作流**：

```
新 episode/observation 提取请求
    ↓
识别与当前主题相关的 active procedures
    ↓
加载 procedure.attributes["constraints"]
    ↓
在提取Prompt中注入约束：
    "根据'风险评估流程'，提取时必须包含：
     - debt_ratio（数值）
     - revenue（数值，单位万元）
     - 验证：debt_ratio 必须在 [0, 1] 范围内"
    ↓
LLM 提取 → 后验约束验证
    ↓
验证通过 → 创建节点 + CONSTRAINS 边指向 procedure
验证失败 → 标记为 "constraint_violated"，等待人工确认
```

### 1.2 自下而上的影响（低层→高层）

#### 1.2.1 原始碎片如何经过 Consolidation 转化为 Observation

**当前设计的问题**：

当前Consolidation是**批处理**的（阈值触发/定时触发），且类型升级路径是线性的：fragment → observation → entity → mental_model。缺少两个关键机制：
1. **紧急升级**：当碎片具有高反馈权重或明确矛盾时，应立即触发consolidation而非等待批处理
2. **跨标签聚合**：当前标签隔离过于严格——`domain:risk`和`domain:supply`的碎片绝不合并，但某些观察（如"供应链风险"）需要跨域聚合

**对比Hindsight**：

Hindsight的ConsolidationJob有更灵活的触发机制（阈值/定时/事件/Reflect触发），且支持`observation_scopes`配置（`per_tag`/`all_combinations`/`combined`）。更重要的是，Hindsight在Consolidation后**自动触发Mental Model刷新**（`_trigger_mental_model_refreshes`）。

**对比Mem0**：

Mem0新算法的ADD-only策略保留了完整的变更历史，这意味着consolidation不再是"覆盖旧信息"，而是"创建新observation并关联旧fragments"。

**改进的Consolidation机制**：

```python
@dataclass
class ConsolidationTrigger:
    """Consolidation 触发条件（扩展当前设计）"""
    batch_threshold: int = 50          -- 碎片数量阈值
    emergency_conditions: list[Callable] = field(default_factory=list)
    
    def should_trigger(self, fragments: list[KnowledgeFragment]) -> tuple[bool, str]:
        if len(fragments) >= self.batch_threshold:
            return True, "threshold"
        
        for frag in fragments:
            -- 条件1：高反馈权重碎片应立即处理
            if frag.feedback_weight >= 0.9:
                return True, f"emergency:high_feedback({frag.id})"
            
            -- 条件2：与现有observation矛盾的碎片
            if frag.metadata.get("contradiction_detected"):
                return True, f"emergency:contradiction({frag.id})"
            
            -- 条件3：时间敏感的碎片（如财报发布）
            if frag.metadata.get("temporal_urgency") == "high":
                return True, f"emergency:temporal({frag.id})"
        
        return False, "none"
```

**跨域聚合策略**：

引入`AGGREGATED_WITH`边和软标签隔离：

```
当前：标签硬隔离
  observation(tags=["domain:risk"]) ← fragment(tags=["domain:risk"])
  observation(tags=["domain:supply"]) ← fragment(tags=["domain:supply"])

改进：保留硬隔离，增加跨域聚合通道
  observation(tags=["domain:risk", "aggregate:supply_risk"])
    ← fragment(tags=["domain:risk"])
    ← fragment(tags=["domain:supply"])  [通过 aggregate:supply_risk 标签桥接]
```

Consolidation引擎新增`cross_tag_aggregation_rules`配置：

```python
CROSS_TAG_RULES = {
    "aggregate:supply_risk": {
        "source_tags": ["domain:risk", "domain:supply"],
        "aggregation_predicate": "entity_overlap > 0.5"
    }
}
```

#### 1.2.2 Episode 如何提取为 Procedure

**当前设计的问题**：

当前`episode → procedure`的转换只有一个`LEARNED_INTO`边，没有定义**提取算法**。Episode只是被记录，procedure如何从episode中提取出来没有具体机制。

**对比MAGMA**：

MAGMA的"程序层"通过观察agent在多张图上的遍历策略来归纳。Procedure不是简单的步骤列表，而是**策略函数**——给定状态，选择下一步动作。

**具体机制设计**：

引入`ProcedureExtractionEngine`：

```python
class ProcedureExtractionEngine:
    """从 episode 序列中提取 procedure"""
    
    async def extract_procedure(self, episode_ids: list[str]) -> Procedure:
        -- 1. 获取 episode 序列
        episodes = await self._fetch_episodes(episode_ids)
        
        -- 2. 抽象化步骤（将具体实体替换为占位符）
        abstracted_steps = []
        for ep in episodes:
            step = {
                "action": ep.outcome["action"],
                "tool": ep.outcome["tool_used"],
                "abstract_params": self._abstract_entities(ep.outcome["params"]),
                "precondition": ep.attributes.get("precondition"),
                "postcondition": ep.outcome.get("result_status")
            }
            abstracted_steps.append(step)
        
        -- 3. 归纳通用模式（通过LLM或模板匹配）
        procedure_template = await self._induce_procedure_pattern(abstracted_steps)
        
        -- 4. 计算成功率
        success_rate = sum(1 for ep in episodes if ep.attributes.get("success", False)) / len(episodes)
        
        -- 5. 创建 procedure 节点
        procedure = Procedure(
            name=procedure_template["name"],
            steps=procedure_template["steps"],
            precondition=procedure_template["precondition"],
            postcondition=procedure_template["postcondition"],
            source_episode_ids=episode_ids,
            invocation_count=len(episodes),
            success_count=int(success_rate * len(episodes)),
            success_rate=success_rate
        )
        
        return procedure
    
    def _abstract_entities(self, params: dict) -> dict:
        """将具体实体ID替换为Schema类型占位符"""
        abstracted = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("ent_"):
                entity = self.kuzu.get_entity(value)
                abstracted[key] = f"{{entity:{entity._fact_object}}}"
            else:
                abstracted[key] = value
        return abstracted
```

**触发条件**：

```python
async def check_procedure_extraction_trigger(space_id: str):
    -- 条件1：同一主题下成功episode >= 3
    successful_episodes = await kuzu.query("""
        MATCH (ep:MemoryUnitNode {space_id: $space_id, memory_type: 'episode'})
        WHERE ep.attributes['success'] = 'true'
        WITH ep.tags AS tags, COUNT(*) AS cnt
        WHERE cnt >= 3
        RETURN tags, collect(ep.unit_id) AS episode_ids
    """, {"space_id": space_id})
    
    for row in successful_episodes:
        existing_procedure = await kuzu.query("""
            MATCH (p:MemoryUnitNode {memory_type: 'procedure'})
            WHERE p.tags = $tags
            RETURN p.unit_id
        """, {"tags": row["tags"]})
        
        if not existing_procedure:
            -- 触发提取
            procedure = await ProcedureExtractionEngine().extract_procedure(row["episode_ids"])
            await self._create_procedure_node(procedure)
```

#### 1.2.3 矛盾事件如何触发 Belief Revision

**当前设计的问题**：

当前Reflect Agent能"发现矛盾"，但发现的矛盾只是被记录到`contradiction_report`中，**不会自动触发信念修正**。没有`belief revision`的正式机制。

**对比Kumiho**：

Kumiho的AGM信念修正框架是其核心创新。当新信息A与旧信念B矛盾时，系统：
1. 找到包含B的最小信念子集（信念基）
2. 以最少改变原则（minimal change）移除导致矛盾的信念
3. 保留核心信念（core-retainment）
4. 通过`Supersedes`边记录修正历史

**具体机制设计**：

引入`BeliefRevisionEngine`和修正协议：

```python
class BeliefRevisionEngine:
    """AGM-style 信念修正引擎（简化版）"""
    
    async def revise(self, new_observation: MemoryUnit) -> RevisionResult:
        -- 1. 查找与新观察矛盾的现有记忆
        contradictions = await self._find_contradictions(new_observation)
        
        if not contradictions:
            -- 无矛盾：直接纳入
            return RevisionResult(action="accept", changes=[])
        
        -- 2. 计算每个矛盾信念的"可放弃性"
        -- 可放弃性 = f(feedback_weight, proof_count, age, belief_type)
        candidates_for_rejection = []
        for old_belief in contradictions:
            discardability = self._compute_discardability(old_belief)
            candidates_for_rejection.append((old_belief, discardability))
        
        -- 3. 按可放弃性排序，选择需要移除的最小集合
        candidates_for_rejection.sort(key=lambda x: x[1], reverse=True)
        to_reject = [candidates_for_rejection[0]]  -- 最可放弃的
        
        -- 4. 执行修正：创建 SUPERSEDES 边
        changes = []
        for old_belief, _ in to_reject:
            await self._create_supersedes_edge(
                from_id=new_observation.id,
                to_id=old_belief.id,
                reason="belief_revision",
                confidence=new_observation.confidence
            )
            
            -- 降低旧信念强度
            old_belief.strength *= 0.5
            await self._update_memory_unit(old_belief)
            
            changes.append({
                "action": "supersede",
                "new_id": new_observation.id,
                "old_id": old_belief.id,
                "reason": "contradiction_resolved"
            })
        
        return RevisionResult(action="revise", changes=changes)
    
    def _compute_discardability(self, belief: MemoryUnit) -> float:
        -- 反馈权重越低越容易放弃
        feedback_factor = 1.0 - belief.feedback_weight
        
        -- 证据越少越容易放弃
        evidence_factor = 1.0 - min(belief.proof_count / 10.0, 1.0)
        
        -- observation 比 entity/mental_model 更容易放弃
        type_factor = {
            "fragment": 1.0,
            "observation": 0.8,
            "entity": 0.3,
            "mental_model": 0.1
        }.get(belief.memory_type, 0.5)
        
        -- 越旧越容易放弃
        age_days = (datetime.utcnow() - belief.created_at).days
        age_factor = min(age_days / 365.0, 1.0)
        
        return (feedback_factor * 0.3 + 
                evidence_factor * 0.3 + 
                type_factor * 0.2 + 
                age_factor * 0.2)
```

**矛盾检测Cypher查询**：

```cypher
-- 查找与给定观察在相同实体/主题上矛盾的现有观察
MATCH (new:MemoryUnitNode {unit_id: $new_id})
MATCH (existing:MemoryUnitNode)
WHERE existing.memory_type IN ['observation', 'entity', 'opinion']
  AND existing.unit_id <> new.unit_id
  AND existing.space_id = new.space_id
  -- 主题重叠：共享至少一个标签或实体关联
  AND ANY(tag IN existing.tags WHERE tag IN new.tags)
  -- 时序邻近（同实体上的新旧信息更可能矛盾）
  AND (existing.occurred_at IS NULL OR new.occurred_at IS NULL 
       OR abs(duration.inDays(
            datetime(existing.occurred_at), 
            datetime(new.occurred_at)
          ).days) < 30)
RETURN existing.unit_id, existing.text, existing.confidence
```

### 1.3 横向交叉影响

#### 1.3.1 同一事件如何在不同层产生不同表示

**当前设计的问题**：

当前同一事件在不同层之间**没有显式的交叉链接**。一个财报发布事件可能在：
- fragment层：原始PDF文本段落
- observation层："2024Q4营收3.2亿"
- entity层：`Company.revenue=320000000`
- mental_model层："企业A财务稳健"

但这些表示之间只有单向的consolidation边，缺少横向的"同一事件不同表示"关联。

**对比Hindsight**：

Hindsight的`source_memory_ids`和`history`字段使observation能追踪到所有来源facts。但Hindsight也没有显式的"同一事件多视角"表示。

**对比MAGMA**：

MAGMA的四正交图（语义/时序/因果/实体）天然支持同一事件的多视角表示：一个事件在语义图中是一种表示，在时序图中是时间点，在因果图中是因果节点，在实体图中是实体关联。

**具体机制设计**：

引入`MULTI_VIEW_OF`边和`ViewPoint`结构：

```cypher
CREATE REL TABLE MULTI_VIEW_OF (
    FROM MemoryUnitNode TO MemoryUnitNode,
    view_type STRING,          -- "semantic" | "temporal" | "causal" | "entity"
    view_aspect STRING,        -- 视角方面（如"financial", "risk", "legal"）
    confidence DOUBLE,
    created_at STRING
)
```

```python
@dataclass
class ViewPoint:
    """同一事件的特定视角表示"""
    base_event_id: str           -- 基础事件ID（通常是episode）
    view_type: str               -- "semantic" | "temporal" | "causal" | "entity"
    view_aspect: str             -- 视角方面
    memory_unit_id: str          -- 该视角对应的MemoryUnit
    
    async def get_sibling_views(self) -> list[ViewPoint]:
        -- 获取同一事件的其他视角
        siblings = await kuzu.query("""
            MATCH (v:MemoryUnitNode {unit_id: $view_id})-[m:MULTI_VIEW_OF]-(other)
            WHERE other.unit_id <> $view_id
            RETURN other.unit_id, m.view_type, m.view_aspect
        """, {"view_id": self.memory_unit_id})
        return [ViewPoint(...) for s in siblings]
```

**创建多视角的工作流**：

```
Episode 创建（如"用户请求评估企业A风险"）
    ↓
自动提取多个视角：
    - 语义视角: observation("用户关注企业A的财务风险")
    - 实体视角: entity(企业A的 risk_grade 更新)
    - 因果视角: observation("营收下降导致风险评级上调")
    - 时序视角: observation("这是用户本周第二次询问企业A")
    ↓
创建 MULTI_VIEW_OF 边：
    (observation)-[MULTI_VIEW_OF {view_type: "semantic"}]->(episode)
    (entity)-[MULTI_VIEW_OF {view_type: "entity"}]->(episode)
    (observation2)-[MULTI_VIEW_OF {view_type: "causal"}]->(episode)
    ↓
检索时：若命中任一视角，可选择扩展至其他视角
```

#### 1.3.2 不同层的记忆如何相互验证/矛盾

**当前设计的问题**：

当前只有`CONTRADICTS`边的概念性提及，没有系统化的**跨层验证机制**。mental_model声称"企业A财务稳健"，但底层的entity显示`debt_ratio=0.85`——这种跨层矛盾应该被自动检测。

**具体机制设计**：

引入`CrossLayerValidator`和验证规则引擎：

```python
class CrossLayerValidator:
    """跨层一致性验证引擎"""
    
    VALIDATION_RULES = {
        "financial_health": {
            "mental_model_pattern": r"财务稳健|财务健康|低风险",
            "entity_predicate": "debt_ratio < 0.6 AND cash_flow > 0",
            "violation_severity": "high"
        },
        "risk_grade": {
            "mental_model_pattern": r"风险等级[为是]([A-D])",
            "entity_predicate": "risk_grade == '{extracted_grade}'",
            "violation_severity": "critical"
        }
    }
    
    async def validate_cross_layer(self, mental_model: MemoryUnit) -> list[ValidationViolation]:
        violations = []
        
        for rule_name, rule in self.VALIDATION_RULES.items():
            if re.search(rule["mental_model_pattern"], mental_model.text):
                -- 提取 mental_model 中声称的具体值
                extracted_values = self._extract_values(mental_model.text, rule)
                
                -- 查询底层 entity/observation 验证
                supporting_entities = await self._query_supporting_evidence(
                    mental_model, extracted_values
                )
                
                -- 验证predicate
                for entity in supporting_entities:
                    if not evaluate_predicate(rule["entity_predicate"], entity, extracted_values):
                        violations.append(ValidationViolation(
                            layer="mental_model",
                            unit_id=mental_model.id,
                            claimed=extracted_values,
                            actual=entity.attributes,
                            severity=rule["violation_severity"],
                            evidence_entity_id=entity.id
                        ))
        
        return violations
    
    async def auto_reconcile(self, violations: list[ValidationViolation]):
        -- 自动调和：标记mental_model为stale，或触发reflect刷新
        for v in violations:
            if v.severity == "critical":
                await self._mark_mental_model_stale(v.unit_id, reason=v)
                await self._trigger_refresh(v.unit_id)
            elif v.severity == "high":
                await self._create_contradiction_edge(v.unit_id, v.evidence_entity_id)
```

### 1.4 时序动态影响

#### 1.4.1 新信息到达时，四层如何级联更新

**当前设计的问题**：

当前更新流程是**离散的、非级联的**：
1. 新fragment到达 → 存入Layer-R
2. Consolidation定时触发 → fragment→observation（可能）
3. Reflect定时触发 → observation→mental_model（可能）

缺少"新信息到达→立即级联评估影响"的机制。

**对比Mem0**：

Mem0的ADD-only策略使每次新信息都是**独立的追加操作**，不需要级联更新。但代价是检索时必须处理更多历史版本。

**对比Zep/Graphiti**：

Graphiti的双时序模型中，新信息到达会触发：
1. 创建新Episode节点
2. 提取Semantic Entity Subgraph
3. 实体解析（判断是否为已知实体的新版本）
4. 若冲突：为旧边设置`t_invalid`，创建新边
5. 更新Community Subgraph

这是更完整的级联更新链。

**具体机制设计**：

引入`CascadeUpdateEngine`和更新优先级队列：

```python
class CascadeUpdateEngine:
    """新信息到达时的级联更新引擎"""
    
    UPDATE_PRIORITY = {
        "entity_core_attribute_change": 1,   -- 最高：核心属性变化
        "contradiction_detected": 2,          -- 高：矛盾发现
        "new_high_confidence_observation": 3, -- 中高：高置信度观察
        "routine_consolidation": 10           -- 最低：常规巩固
    }
    
    async def on_new_fragment(self, fragment: KnowledgeFragment):
        -- 1. 立即存入Layer-R（永不阻塞）
        await self._store_fragment(fragment)
        
        -- 2. 放入级联更新队列
        await self._enqueue_cascade(fragment)
    
    async def process_cascade_queue(self):
        while True:
            job = await self._dequeue_highest_priority()
            if job is None:
                await asyncio.sleep(1)
                continue
            
            await self._execute_cascade(job)
    
    async def _execute_cascade(self, job: CascadeJob):
        fragment = job.fragment
        
        -- 阶段1：提取实体和观察（立即）
        extraction_result = await ExtractionPipeline.extract(fragment)
        
        -- 阶段2：检查是否影响现有entity（5秒内）
        affected_entities = await self._find_affected_entities(extraction_result)
        for entity in affected_entities:
            -- 若entity核心属性变化，标记相关mental_model为stale
            if self._is_core_attribute_change(entity, extraction_result):
                await self._mark_dependent_models_stale(entity.id)
                await self._enqueue_priority_job(
                    "mental_model_refresh", 
                    entity_id=entity.id,
                    priority=self.UPDATE_PRIORITY["entity_core_attribute_change"]
                )
        
        -- 阶段3：检查矛盾（10秒内）
        contradictions = await BeliefRevisionEngine().find_contradictions(
            extraction_result.new_observations
        )
        if contradictions:
            await self._enqueue_priority_job(
                "belief_revision",
                observations=extraction_result.new_observations,
                contradictions=contradictions,
                priority=self.UPDATE_PRIORITY["contradiction_detected"]
            )
        
        -- 阶段4：检查是否触发procedure学习（异步，低优先级）
        if extraction_result.memory_type == "episode":
            await self._check_procedure_learning_trigger(extraction_result)
```

**级联更新时序图**：

```
t+0ms:  新 fragment 到达 → 同步存入 Layer-R
        ↓
t+50ms: ExtractionPipeline 提取 entity/observation
        ↓
t+100ms: 检查 affected_entities
         - 若核心属性变化 → 标记 mental_model stale（t+200ms）
         - 若新 entity → 创建 CONSOLIDATED_INTO 边（t+150ms）
        ↓
t+500ms: 矛盾检测（异步）
         - 若发现矛盾 → 入队 belief_revision 任务
        ↓
t+1s:   mental_model 刷新任务（若已入队）
         - 重新检索底层证据
         - 若摘要变化 > 阈值 → 更新 mental_model
        ↓
t+5s:   procedure 学习检查（低优先级）
         - 若同一主题 episode >= 3 → 提取 procedure
```

#### 1.4.2 哪层先更新？哪层可能滞后？

**更新优先级协议**：

| 优先级 | 层 | 更新时机 | 滞后容忍 |
|--------|-----|---------|---------|
| P0 | fragment（感知层） | 同步，t+0 | 零滞后 |
| P1 | entity（语义层核心属性） | 准同步，t+100ms | < 500ms |
| P2 | observation（归纳层） | 异步，t+1-5s | < 30s |
| P3 | belief revision（信念层） | 异步队列，t+5-30s | < 5min |
| P4 | mental_model（摘要层） | 异步/定时，t+30s-1h | < 24h |
| P5 | procedure（程序层） | 低优先级异步，t+1h+ | < 7d |

**滞后的原因**：
- **mental_model滞后**：需要多源证据聚合，且生成摘要的LLM调用成本高
- **procedure滞后**：需要足够样本量（≥3 episode），且归纳过程复杂
- **belief revision滞后**：矛盾检测需要跨记忆比较，计算复杂

**滞后的风险与缓解**：

```python
class StalenessMonitor:
    """监控各层滞后的风险"""
    
    STALENESS_RISK_MATRIX = {
        ("entity", "mental_model", "lag > 1h"): "medium",
        ("entity", "mental_model", "core_attr_changed + lag > 5min"): "high",
        ("observation", "entity", "lag > 30min"): "low",
        ("fragment", "observation", "lag > 1h"): "low"
    }
    
    async def monitor(self):
        -- 检查 mental_model 的 is_stale 标记和 last_refreshed_at
        stale_models = await kuzu.query("""
            MATCH (mm:MemoryUnitNode {memory_type: 'mental_model'})
            WHERE mm.attributes['is_stale'] = 'true'
               OR duration.inHours(
                    datetime(mm.attributes['last_refreshed_at']), 
                    datetime()
                  ).hours > 24
            RETURN mm.unit_id, mm.attributes['last_refreshed_at']
        """)
        
        for model in stale_models:
            await self._escalate_staleness_risk(model["unit_id"])
```

### 1.5 具体机制设计：层间边/链接/触发器

#### 1.5.1 完整边类型体系

在现有4种边类型（CONSOLIDATED_INTO/MAPPED_TO/SUMMARIZED_AS/LEARNED_INTO）基础上，新增以下边类型：

```cypher
-- 自上而下的影响边
CREATE REL TABLE ATTENTION_GUIDE (
    FROM MemoryUnitNode TO MemoryUnitNode,
    guide_type STRING,
    weight DOUBLE,
    scope_tags STRING[],
    created_at STRING,
    expires_at STRING
)

CREATE REL TABLE CONSTRAINS (
    FROM MemoryUnitNode TO MemoryUnitNode,
    constraint_type STRING,
    constraint_expr STRING,
    enforcement_level STRING,
    created_at STRING
)

-- 自下而上的影响边
CREATE REL TABLE EVIDENCE_FOR (
    FROM MemoryUnitNode TO MemoryUnitNode,
    evidence_type STRING,      -- "direct" | "supporting" | "indirect"
    contribution_score DOUBLE, -- 证据贡献度 [0, 1]
    created_at STRING
)

-- 横向交叉边
CREATE REL TABLE MULTI_VIEW_OF (
    FROM MemoryUnitNode TO MemoryUnitNode,
    view_type STRING,
    view_aspect STRING,
    confidence DOUBLE,
    created_at STRING
)

CREATE REL TABLE CONTRADICTS (
    FROM MemoryUnitNode TO MemoryUnitNode,
    contradiction_type STRING,
    detection_method STRING,
    confidence DOUBLE,
    created_at STRING
)

-- 时序/信念修正边
CREATE REL TABLE SUPERSEDES (
    FROM MemoryUnitNode TO MemoryUnitNode,
    supersedence_reason STRING,
    supersedence_confidence DOUBLE,
    created_at STRING
)

CREATE REL TABLE TRIGGERED_REFRESH (
    FROM MemoryUnitNode TO MemoryUnitNode,
    trigger_reason STRING,
    created_at STRING
)
```

#### 1.5.2 触发器机制

```python
@dataclass
class LayerTrigger:
    """层间触发器配置"""
    trigger_id: str
    source_layer: str           -- 触发源层
    target_layer: str           -- 目标层
    condition: TriggerCondition
    action: TriggerAction
    cooldown_seconds: int = 300 -- 冷却时间
    
@dataclass
class TriggerCondition:
    condition_type: str         -- "threshold" | "event" | "pattern"
    threshold_value: float | None
    event_type: str | None
    pattern_regex: str | None

@dataclass
class TriggerAction:
    action_type: str            -- "create_edge" | "update_strength" | "invoke_llm" | "enqueue_job"
    action_params: dict

-- 预定义触发器
DEFAULT_TRIGGERS = [
    LayerTrigger(
        trigger_id="entity_change_refresh_model",
        source_layer="entity",
        target_layer="mental_model",
        condition=TriggerCondition(
            condition_type="event",
            event_type="core_attribute_change"
        ),
        action=TriggerAction(
            action_type="create_edge",
            action_params={"edge_type": "TRIGGERED_REFRESH", "reason": "entity_changed"}
        ),
        cooldown_seconds=300
    ),
    LayerTrigger(
        trigger_id="fragment_contradiction_revisions",
        source_layer="fragment",
        target_layer="belief",
        condition=TriggerCondition(
            condition_type="pattern",
            pattern_regex=r"contradict|与.*不符|错误"
        ),
        action=TriggerAction(
            action_type="enqueue_job",
            action_params={"job_type": "belief_revision", "priority": 2}
        )
    ),
    LayerTrigger(
        trigger_id="episode_cluster_procedure",
        source_layer="episode",
        target_layer="procedure",
        condition=TriggerCondition(
            condition_type="threshold",
            threshold_value=3  -- 3个同主题episode
        ),
        action=TriggerAction(
            action_type="invoke_llm",
            action_params={"task": "extract_procedure"}
        ),
        cooldown_seconds=3600
    )
]
```

#### 1.5.3 级联更新状态机

```
状态: [idle] --(新fragment)--> [extracting]
                                      ↓
                              [validating_entity]
                                      ↓
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
              [no_change]     [core_changed]      [new_entity]
                    ↓                 ↓                 ↓
              [checking_      [mark_model_       [creating_]
               contradiction]   stale]             observation]
                    ↓                 ↓                 ↓
              [enqueue_       [enqueue_          [enqueue_]
               revision?]      refresh]           consolidation]
                    ↓                 ↓                 ↓
              [idle] <──────────────────────────────────┘
```

---

## 问题2：这对检索架构意味着什么？

### 2.1 检索不再是扁平的：分层漏斗 vs 并行池

**当前设计的问题**：

当前检索是**并行池模型**：recall()并行搜索所有memory_type，然后按类型权重排序。这类似于把所有记忆倒进一个大池子，按权重打捞。

**问题**：
1. 高层的mental_model和低层的fragment在检索阶段竞争同一个排序空间，破坏了认知层次
2. 没有"高层先命中则快速返回"的短路机制
3. 各层之间没有信息传递——Layer-S的图遍历结果不会影响Layer-R的向量检索参数

**对比Hindsight**：

Hindsight的TEMPR检索虽然是四路并行（Semantic/BM25/Graph/Temporal），但Reflect Agent的检索是**分层强制序列**：mental_models → observations → memories。这是**分层漏斗**模型——高层先过滤，不够再下沉。

**对比MAGMA**：

MAGMA是**策略引导的分层遍历**：查询先被分类为某种"策略"（如"因果解释"策略），然后在四张正交图上按策略优先级遍历。这不是简单的漏斗或池，而是**策略驱动的动态路径**。

**推荐架构：自适应分层漏斗**

```
┌──────────────────────────────────────────────────────────────┐
│                    自适应分层漏斗检索                           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  第1层：Mental Model 快速通道（top_k=3, 预算20%）            │
│    → 若命中且置信度 > 0.8 → 短路返回（高层摘要）              │
│    → 若命中但置信度 <= 0.8 → 标记为候选，继续下沉             │
│    → 若未命中 → 进入第2层                                     │
│                                                               │
│  第2层：Entity + Rule 确定性层（top_k=5, 预算30%）            │
│    → 执行图遍历 + 规则推理                                    │
│    → 若找到确定性答案 → 返回 + 证据链展开                     │
│    → 若找到相关实体 → 提取相关observation IDs，进入第3层      │
│                                                               │
│  第3层：Observation + Episode（top_k=10, 预算30%）            │
│    → 向量检索 + 时序过滤                                      │
│    → 若找到直接匹配的observation → 返回                       │
│    → 收集observation中的entity引用，用于第2层扩展             │
│                                                               │
│  第4层：Fragment 原始证据（top_k=10, 预算20%）                │
│    → 纯向量检索，补充语义证据                                 │
│    → 若上层结果不足 → fragment填充                            │
│                                                               │
│  层间反馈：                                                   │
│    - 第2层找到的entity IDs → 注入第3层作为过滤条件            │
│    - 第1层mental_model的source_entity_ids → 第2层优先遍历     │
│    - 第3层observation的source_fragment_ids → 第4层精确检索    │
└──────────────────────────────────────────────────────────────┘
```

**关键设计决策**：

| 维度 | 并行池（当前） | 分层漏斗（推荐） | 策略引导（MAGMA） |
|------|--------------|----------------|-----------------|
| 延迟 | 固定（等最慢一路） | 可短路（命中即返） | 取决于策略复杂度 |
| 召回率 | 高（全量竞争） | 中高（可能短路漏掉低层） | 中（策略可能剪枝过度） |
| 可解释性 | 低（权重黑盒） | 高（清晰分层路径） | 高（策略透明） |
| Token效率 | 中 | 高（短路节省token） | 高 |
| 工程复杂度 | 低 | 中 | 高 |

**推荐**：采用"分层漏斗+策略引导混合"——默认走分层漏斗，对复杂multi-hop查询启用MAGMA式策略引导。

### 2.2 跨层检索的路径设计

#### 2.2.1 案例：用户查询"企业A为什么风险高"

**当前路径**：

```
query → QueryRouter.detect_query_type() → "multi-hop"
    ↓
Layer-S图遍历（CAUSAL边优先）
    ↓
返回entity+relation列表
    ↓
可选EXTRACTED_FROM扩展到fragment
    ↓
RRF融合 → 返回
```

**问题**：
- 没有优先查mental_model（"企业A风险摘要"）
- 没有区分"为什么"需要因果层和"风险高"需要语义层
- 缺少从高层摘要向下展开证据的链路

**改进路径**：

```
Step 1: 查询意图分解
    "企业A为什么风险高" → 
        - 主意图: explain_causality（为什么）
        - 目标实体: 企业A
        - 属性: risk_level
        - 期望答案类型: causal_chain（因果链）
    
Step 2: 分层漏斗检索
    
    Layer 1: Mental Model 快速通道
        recall(query="企业A风险", memory_type="mental_model")
        → 命中 mm_001: "企业A因债务高企被评为D级"
        → 置信度 0.85 >= 0.8 → 短路候选，但继续收集证据
        → 记录 mm_001.source_entity_ids = ["ent_A_debt", "ent_A_grade"]
    
    Layer 2: Entity 确定性层（使用Layer 1的source_entity_ids作为入口）
        graph_traverse(
            start_nodes=["ent_A_debt", "ent_A_grade"],
            edge_types=["CAUSAL", "HAS_METRIC"],
            max_depth=2
        )
        → ent_A_debt: debt_ratio=0.78
        → ent_A_grade: risk_grade=D
        → 边: debt_ratio > 0.7 CAUSES risk_grade=D (weight=0.95)
    
    Layer 3: Observation 证据层
        recall(query="企业A 债务 风险", memory_type="observation")
        → obs_001: "2024Q4资产负债率升至78%"
        → obs_002: "连续两季度现金流为负"
        → 检查obs与entity的一致性：obs_001.debt_ratio ≈ entity.debt_ratio ✓
    
    Layer 4: Fragment 原始证据
        recall(fragment_ids=[obs_001.source_fragment_ids, obs_002.source_fragment_ids])
        → frag_001: "2024年报第32页：资产负债率78%..."
        → frag_002: "Q4现金流量表：经营活动现金流-500万..."

Step 3: 证据链组装
    {
        "answer": "企业A因资产负债率升至78%（超过70%阈值），连续两季度现金流为负，被评定为D级风险",
        "causal_chain": [
            {"cause": "debt_ratio=0.78", "effect": "risk_grade=D", "evidence": ["obs_001", "ent_A_debt"]},
            {"cause": "cash_flow_negative", "effect": "financial_stress", "evidence": ["obs_002"]}
        ],
        "mental_model": {"id": "mm_001", "text": "企业A因债务高企被评为D级", "confidence": 0.85},
        "source_fragments": ["frag_001", "frag_002"]
    }
```

### 2.3 层间证据传递

#### 2.3.1 从高层摘要向下展开到低层证据

**当前设计的问题**：

当前`include_evidence=true`时，recall返回的证据链是**单层**的（observation→fragment通过CONSOLIDATED_INTO）。没有从mental_model→entity→observation→fragment的多层展开。

**具体机制设计**：

引入`EvidenceExpander`和展开协议：

```python
class EvidenceExpander:
    """从检索结果向下展开完整证据链"""
    
    EXPANSION_RULES = {
        "mental_model": {
            "next_layers": ["entity", "observation"],
            "edge_types": ["SUMMARIZED_AS", "MAPPED_TO"],
            "max_expansion": 5
        },
        "entity": {
            "next_layers": ["observation", "fragment"],
            "edge_types": ["EXTRACTED_FROM", "SUPPORTED_BY", "CONSOLIDATED_INTO"],
            "max_expansion": 10
        },
        "observation": {
            "next_layers": ["fragment"],
            "edge_types": ["CONSOLIDATED_INTO"],
            "max_expansion": 5
        }
    }
    
    async def expand_evidence(
        self, 
        top_level_result: MemoryUnit,
        max_depth: int = 3,
        token_budget: int = 2000
    ) -> EvidenceTree:
        tree = EvidenceTree(root=top_level_result)
        current_level = [top_level_result]
        
        for depth in range(max_depth):
            next_level = []
            for unit in current_level:
                rule = self.EXPANSION_RULES.get(unit.memory_type)
                if not rule:
                    continue
                
                -- 查询支撑证据
                children = await self._expand_unit(unit, rule)
                tree.add_children(unit.id, children)
                next_level.extend(children)
                
                -- Token预算检查
                if tree.estimate_tokens() > token_budget:
                    tree.mark_truncated()
                    return tree
            
            current_level = next_level
        
        return tree
    
    async def _expand_unit(self, unit: MemoryUnit, rule: dict) -> list[MemoryUnit]:
        -- 根据边类型查询下级证据
        children = await kuzu.query("""
            MATCH (u:MemoryUnitNode {unit_id: $unit_id})-[r]->(child:MemoryUnitNode)
            WHERE type(r) IN $edge_types
              AND child.memory_type IN $next_layers
            RETURN child.*, r.confidence AS edge_confidence
            ORDER BY r.confidence DESC
            LIMIT $max_expansion
        """, {
            "unit_id": unit.id,
            "edge_types": rule["edge_types"],
            "next_layers": rule["next_layers"],
            "max_expansion": rule["max_expansion"]
        })
        return [MemoryUnit(**c) for c in children]
```

**证据树数据结构**：

```python
@dataclass
class EvidenceTree:
    root: MemoryUnit
    nodes: dict[str, EvidenceNode] = field(default_factory=dict)
    
    def add_children(self, parent_id: str, children: list[MemoryUnit]):
        for child in children:
            self.nodes[child.id] = EvidenceNode(
                unit=child,
                parent_id=parent_id,
                children_ids=[]
            )
            self.nodes[parent_id].children_ids.append(child.id)
    
    def estimate_tokens(self) -> int:
        total = 0
        for node in self.nodes.values():
            total += len(node.unit.text) // 4  -- 粗略估算
        return total
    
    def to_context_string(self, max_depth: int = 3) -> str:
        -- 将证据树转换为LLM上下文字符串
        lines = []
        self._format_node(self.root.id, 0, max_depth, lines)
        return "\n".join(lines)
    
    def _format_node(self, node_id: str, depth: int, max_depth: int, lines: list):
        if depth > max_depth:
            return
        node = self.nodes[node_id]
        indent = "  " * depth
        lines.append(f"{indent}[{node.unit.memory_type}] {node.unit.text[:100]}...")
        for child_id in node.children_ids:
            self._format_node(child_id, depth + 1, max_depth, lines)
```

### 2.4 检索的动态性：Disposition 如何调整各层权重

**当前设计的问题**：

当前类型权重是**静态的**：mental_model=3.0, entity=2.0, observation=1.5... 无论Agent当前的任务、用户偏好或上下文如何，权重不变。

**对比Hindsight**：

Hindsight的Disposition系统（`skepticism`/`empathy`/`literalism`）直接影响Reflect Agent的：
1. **Prompt风格**：高skepticism的系统prompt要求Agent"质疑所有断言"
2. **检索序列**：Disposition可以调整forced_sequence中各工具的调用顺序
3. **结果过滤**：高skepticism会过滤低置信度结果

**具体机制设计**：

引入`DispositionProfile`和动态权重调整：

```python
@dataclass
class DispositionProfile:
    """Agent 性格/倾向配置（对齐 Hindsight Disposition）"""
    skepticism: float = 0.5       -- [0,1] 怀疑倾向
    thoroughness: float = 0.5     -- [0,1]  thoroughness（ thoroughness高则深入低层）
    recency_bias: float = 0.5     -- [0,1] 时间偏好（高则偏好最新信息）
    abstraction_preference: float = 0.5  -- [0,1] 抽象偏好（高则偏好mental_model）
    evidence_demand: float = 0.5  -- [0,1] 证据要求（高则要求更多fragment）

class DynamicWeightAdjuster:
    """基于 Disposition 的动态检索权重调整器"""
    
    BASE_WEIGHTS = {
        "mental_model": 3.0,
        "entity": 2.0,
        "rule": 2.0,
        "procedure": 1.8,
        "observation": 1.5,
        "episode": 1.2,
        "fragment": 1.0
    }
    
    def adjust_weights(self, disposition: DispositionProfile, query_context: dict) -> dict:
        weights = self.BASE_WEIGHTS.copy()
        
        -- 1. 抽象偏好影响 mental_model vs fragment 权重
        if disposition.abstraction_preference > 0.7:
            weights["mental_model"] *= 1.5
            weights["fragment"] *= 0.6
        elif disposition.abstraction_preference < 0.3:
            weights["mental_model"] *= 0.7
            weights["fragment"] *= 1.3
        
        -- 2. thoroughness 影响层间分配
        if disposition.thoroughness > 0.7:
            -- thoroughness高：降低mental_model权重，增加底层权重
            weights["mental_model"] *= 0.8
            weights["observation"] *= 1.2
            weights["fragment"] *= 1.2
        
        -- 3. evidence_demand 影响是否展开证据链
        if disposition.evidence_demand > 0.8:
            query_context["evidence_expansion_depth"] = 3
            query_context["include_fragments"] = True
        else:
            query_context["evidence_expansion_depth"] = 1
            query_context["include_fragments"] = False
        
        -- 4. recency_bias 影响时序评分
        if disposition.recency_bias > 0.7:
            query_context["temporal_decay_lambda"] = 0.2  -- 快速衰减
        else:
            query_context["temporal_decay_lambda"] = 0.05  -- 慢速衰减
        
        -- 5. skepticism 影响置信度阈值
        if disposition.skepticism > 0.7:
            query_context["min_confidence"] = 0.8
            query_context["filter_superseded"] = True
        else:
            query_context["min_confidence"] = 0.5
            query_context["filter_superseded"] = False
        
        return weights
```

**Disposition 注入检索流程**：

```python
async def recall_with_disposition(
    query: str,
    space_id: str,
    disposition: DispositionProfile | None = None
) -> RecallResult:
    disposition = disposition or await self._load_default_disposition(space_id)
    
    -- 1. 动态调整权重
    adjuster = DynamicWeightAdjuster()
    weights = adjuster.adjust_weights(disposition, query_context={})
    
    -- 2. 根据 abstraction_preference 决定检索模式
    if disposition.abstraction_preference > 0.8:
        -- 高度抽象偏好：优先mental_model，可能短路
        results = await self._tiered_funnel(query, space_id, weights, allow_short_circuit=True)
    elif disposition.thoroughness > 0.8:
        -- 高度thoroughness：全层检索，不短路
        results = await self._full_layer_search(query, space_id, weights)
    else:
        -- 默认：分层漏斗
        results = await self._tiered_funnel(query, space_id, weights, allow_short_circuit=False)
    
    -- 3. 根据 skepticism 过滤
    if disposition.skepticism > 0.6:
        results = await BeliefFilter(disposition_skepticism=disposition.skepticism).apply(results)
    
    return results
```

### 2.5 Token 预算的分层分配

**当前设计的问题**：

当前`token_budget`参数只在最后一步做简单截断（`ContextAwareRetriever`按顺序累加直到超预算），没有按认知层次进行战略性分配。

**推荐分配策略**：

总token预算 = 8000 tokens

#### 2.5.1 预算分配矩阵

| 场景 | Mental Model | Entity/Rule | Observation | Fragment | 总计 |
|------|-------------|-------------|-------------|----------|------|
| **快速回答** | 1500 (19%) | 1500 (19%) | 2000 (25%) | 3000 (37%) | 8000 |
| **深度分析** | 1200 (15%) | 2000 (25%) | 2800 (35%) | 2000 (25%) | 8000 |
| **审计溯源** | 800 (10%) | 1200 (15%) | 2000 (25%) | 4000 (50%) | 8000 |
| **探索学习** | 2000 (25%) | 1500 (19%) | 2500 (31%) | 2000 (25%) | 8000 |

**分配逻辑**：

```python
class TokenBudgetAllocator:
    """Token预算的智能分层分配器"""
    
    ALLOCATION_PROFILES = {
        "quick_answer": {
            "mental_model": 0.19,
            "entity_rule": 0.19,
            "observation": 0.25,
            "fragment": 0.37,
            "description": "优先高层摘要+原始证据，适合事实性查询"
        },
        "deep_analysis": {
            "mental_model": 0.15,
            "entity_rule": 0.25,
            "observation": 0.35,
            "fragment": 0.25,
            "description": "平衡各层，适合分析性查询"
        },
        "audit_trail": {
            "mental_model": 0.10,
            "entity_rule": 0.15,
            "observation": 0.25,
            "fragment": 0.50,
            "description": "优先原始证据，适合合规审计"
        },
        "exploratory": {
            "mental_model": 0.25,
            "entity_rule": 0.19,
            "observation": 0.31,
            "fragment": 0.25,
            "description": "优先高层洞察，适合探索性查询"
        }
    }
    
    def allocate(self, total_budget: int, profile_name: str, disposition: DispositionProfile) -> BudgetPlan:
        profile = self.ALLOCATION_PROFILES[profile_name]
        
        -- 根据 Disposition 微调
        adjustments = self._disposition_adjustments(disposition)
        
        plan = BudgetPlan(
            mental_model=int(total_budget * (profile["mental_model"] + adjustments.get("mental_model", 0))),
            entity_rule=int(total_budget * (profile["entity_rule"] + adjustments.get("entity_rule", 0))),
            observation=int(total_budget * (profile["observation"] + adjustments.get("observation", 0))),
            fragment=int(total_budget * (profile["fragment"] + adjustments.get("fragment", 0)))
        )
        
        -- 确保总和不超过预算（处理舍入误差）
        return self._normalize(plan, total_budget)
    
    def _disposition_adjustments(self, disposition: DispositionProfile) -> dict:
        adjustments = {}
        
        if disposition.abstraction_preference > 0.7:
            adjustments["mental_model"] = 0.05
            adjustments["fragment"] = -0.05
        elif disposition.abstraction_preference < 0.3:
            adjustments["mental_model"] = -0.05
            adjustments["fragment"] = 0.05
        
        if disposition.evidence_demand > 0.7:
            adjustments["fragment"] = 0.10
            adjustments["mental_model"] = -0.05
            adjustments["entity_rule"] = -0.05
        
        return adjustments
```

#### 2.5.2 动态预算重分配

在检索过程中，如果某层结果不足，可以将预算重新分配给其他层：

```python
class DynamicBudgetReallocator:
    """检索过程中的动态预算重分配"""
    
    async def reallocate(
        self, 
        plan: BudgetPlan,
        layer_results: dict[str, list[MemoryUnit]]
    ) -> BudgetPlan:
        new_plan = plan.copy()
        
        -- 检查每层结果是否"充足"
        for layer, results in layer_results.items():
            layer_budget = getattr(plan, layer)
            used_tokens = sum(r.estimate_tokens() for r in results)
            
            if used_tokens < layer_budget * 0.5:
                -- 该层结果不足，释放50%未使用预算
                unused = layer_budget - used_tokens
                release = int(unused * 0.5)
                setattr(new_plan, layer, getattr(new_plan, layer) - release)
                
                -- 将释放的预算分配给下层
                if layer == "mental_model":
                    new_plan.entity_rule += release // 2
                    new_plan.observation += release // 2
                elif layer == "entity_rule":
                    new_plan.observation += release
                elif layer == "observation":
                    new_plan.fragment += release
        
        return new_plan
```

---

## 当前OntologyEngine设计的不足总结

| # | 不足 | 影响 | 严重程度 |
|---|------|------|---------|
| 1 | **mental_model只是静态标签**，不能主动引导注意力 | 高层知识无法影响新信息处理，错失"预期驱动感知"能力 | 高 |
| 2 | **缺少opinion/belief类型**，观点与事实混为一谈 | 矛盾观点无法被区分和管理，检索结果可能自相矛盾 | 高 |
| 3 | **procedure与episode单向关联**，程序不能约束提取 | 经验学习无法指导新事件的识别和提取 | 中 |
| 4 | **consolidation只有批处理**，缺少紧急升级通道 | 关键信息需要等待定时任务才能升级，时效性差 | 中 |
| 5 | **belief revision缺失**，矛盾只报告不修正 | 系统发现矛盾后无自动修正机制，知识一致性无法维护 | 高 |
| 6 | **检索是扁平并行池**，缺少分层漏斗 | 高层摘要与底层碎片竞争排序，token效率低 | 高 |
| 7 | **证据传递单向**（下→上），缺少上→下展开 | 用户无法从摘要追溯到完整证据链 | 中 |
| 8 | **Disposition系统缺失**，权重全局静态 | 无法根据Agent性格/任务动态调整检索策略 | 中 |
| 9 | **token预算只做截断**，不做战略性分配 | 可能浪费预算在低层碎片上，而高层摘要空间不足 | 中 |
| 10 | **级联更新非结构化**，缺少状态机 | 新信息到达后各层更新时序不确定，可能出现不一致窗口 | 中 |

---

## 可执行的改进建议

### Phase 1（立即执行）：基础设施扩展

1. **扩展 memory_type 枚举**
   - 新增 `opinion` 类型，与 `observation` 区分
   - 在 `MemoryUnitNode` 的 `attributes` JSON 中增加 `belief_status` 字段：`"active"|"superseded"|"retracted"`

2. **新增核心边类型**
   - `CONTRADICTS`：矛盾检测边
   - `SUPERSEDES`：信念修正边
   - `EVIDENCE_FOR`：证据支撑边（替换单向的CONSOLIDATED_INTO语义）

3. **引入 DispositionProfile**
   - 在space级别存储默认Disposition
   - 在recall API中增加可选`disposition`参数

### Phase 2（短期）：动态检索重构

4. **实现分层漏斗检索**
   - 修改 `recall()` 内部流程：mental_model → entity → observation → fragment
   - 增加短路机制：当mental_model置信度>0.8时，直接返回并可选展开证据
   - 保留`full_search`参数用于thoroughness场景

5. **实现 EvidenceExpander**
   - 新增 `expand_evidence()` 方法
   - 支持从任意层节点向下展开到fragment层的完整证据树
   - 受token_budget控制截断

6. **动态权重调整器**
   - 实现 `DynamicWeightAdjuster`
   - 基于Disposition调整类型权重和检索参数
   - 在 `ContextAwareRetriever` 中集成token预算的 strategic allocation

### Phase 3（中期）：级联更新与信念修正

7. **级联更新引擎**
   - 实现 `CascadeUpdateEngine` 和优先级队列
   - fragment到达后自动触发：提取→entity影响评估→mental_model stale标记
   - 增加 `StalenessMonitor` 后台任务

8. **信念修正引擎**
   - 实现简化版AGM信念修正（`BeliefRevisionEngine`）
   - 矛盾检测：对比新observation与现有entity属性
   - 修正执行：创建SUPERSEDES边，降低旧信念strength

9. **Procedure提取引擎**
   - 实现 `ProcedureExtractionEngine`
   - 从episode序列抽象化步骤
   - 触发条件：同主题成功episode >= 3

### Phase 4（长期）：认知交互网络

10. **注意力引导机制**
    - 实现 `PerceptualFilter` 和 `ATTENTION_GUIDE` 边
    - mental_model能够boost/suppress特定标签/模式的碎片编码

11. **跨层验证器**
    - 实现 `CrossLayerValidator`
    - 自动检测mental_model与底层entity的属性矛盾
    - 自动标记stale并触发refresh

12. **多视角表示**
    - 实现 `MULTI_VIEW_OF` 边
    - 同一episode自动提取语义/时序/因果/实体四种视角
    - 检索时支持视角切换和交叉引用

---

## 与SOTA系统的对齐总结

| 设计点 | Hindsight | MAGMA | Kumiho | Mem0 | OntologyEngine（建议） |
|--------|-----------|-------|--------|------|----------------------|
| 记忆层次 | 4层（MM/Obs/Wld/Exp） | 4正交图 | AGM信念基 | 扁平ADD-only | **双层+7类型标签**（扩展opinion） |
| 高层→低层影响 | Disposition+Trigger | 策略引导 | 信念基收缩 | 无 | **ATTENTION_GUIDE+CONSTRAINS** |
| 低层→高层归纳 | Consolidation+MM刷新 | 图归纳 | AGM修正 | ADD-only | **CascadeUpdate+BeliefRevision** |
| 矛盾处理 | 报告矛盾 | 无 | Supersedes+AGM | 保留历史 | **CONTRADICTS+SUPERSEDES** |
| 检索模式 | TEMPR分层强制 | 策略遍历 | 前瞻索引 | 多信号 | **分层漏斗+动态权重** |
| Token分配 | 截断 | 无 | 客户端重排序 | 固定预算 | **Strategic Allocation** |
| 证据展开 | source_memory_ids | 路径追溯 | 修订版本树 | 无 | **EvidenceTree** |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Hindsight深度调研 | `docs-dev/research/hindsight-deep-analysis.md` |
| Mem0算法分析 | `docs-dev/research/mem0-report/report.md` |
| Agent记忆概念框架 | `docs/01-overview/09-agent-memory.md` |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 认知操作API | `docs/02-design/agent-memory/memory-api.md` |
| 查询路由设计 | `docs/02-design/query-engine/query-routing.md` |
| Layer-S检索 | `docs/02-design/query-engine/layer-s-retrieval.md` |
| Layer-R检索 | `docs/02-design/query-engine/layer-r-retrieval.md` |
| RRF融合 | `docs/02-design/query-engine/rrf-fusion.md` |

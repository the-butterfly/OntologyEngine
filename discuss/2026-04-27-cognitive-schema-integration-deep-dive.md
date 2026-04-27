# 范式A+B的深度融合：四层认知×Schema骨架×资产治理

> **日期**: 2026-04-27 | **主题**: 认知-Schema融合、矛盾治理、案例辩论 | **前置阅读**: `discuss/2026-04-27-agent-memory-design-analysis.md` + `discuss/2026-04-27-four-layer-cognitive-interaction-analysis.md`
> **[关键设计点]**: 本报告回答四个核心问题：认知层互影响机制、Schema融合方式、矛盾/更正管理模式、以及通过实际案例进行的方案辩论

---

## 目录

1. [四层认知与Schema v2 L1-L4的融合映射](#一四层认知与schema-v2-l1-l4的融合映射)
2. [知识加工编译更新的管理模式](#二知识加工编译更新的管理模式)
3. [矛盾处理与信息更正的双轨治理](#三矛盾处理与信息更正的双轨治理)
4. [实际案例深度辩论：供应链金融风控Agent](#四实际案例深度辩论供应链金融风控agent)
5. [关键问题的多方向讨论：意义与代价](#五关键问题的多方向讨论意义与代价)
6. [资产构建规范与治理框架](#六资产构建规范与治理框架)

---

## 一、四层认知与Schema v2 L1-L4的融合映射

### 1.1 核心问题：memory_type 与 L1-L4 的归属关系

当前设计最大的断层在于：**memory_type 类型体系（7种）与 Schema v2 四层架构（L1-L4）缺乏显式的映射关系**。这导致 Agent 在存储记忆时不知道"这条记忆应该对应 Schema 的哪一层"，在检索时也无法利用 Schema 结构优化查询路径。

#### 1.1.1 融合映射表（核心设计）

| 认知层 | memory_type | Schema 归属 | 映射强度 | 双向关系 |
|--------|------------|-------------|---------|---------|
| **感知/情景层** | fragment | Layer-R KnowledgeFragment | 强（存储层映射） | 单向：碎片是Schema实例的原材料 |
| **感知/情景层** | episode | **L1 EventInstance（新增）** | 中（需新增Schema层） | 双向：episode提取entity，procedure反向约束提取 |
| **语义/事实层** | observation | **L3 MetricSource / L2 DerivedInput（新增）** | 中（弱关联→强关联） | 双向：observation聚合为metric输入，metric计算验证observation |
| **语义/事实层** | entity | L1 EntityInstance | **强（影子节点需消除）** | 双向：entity是L1的实例化，L1定义约束entity结构 |
| **语义/事实层** | rule | L4 RuleDefinition | **强（影子节点需消除）** | 双向：rule是L4的定义缓存，L4变更触发rule刷新 |
| **观点/信念层** | mental_model | **L2 DimensionView + L3 CompositeMetric（新增）** | 弱→中 | 双向：mental_model是跨L1-L4的摘要视图，Schema变更触发mm刷新 |
| **观点/信念层** | opinion | **L4 RuleInsight / L3 Assessment（新增）** | 弱（全新类型） | 双向：opinion积累可建议新增L4规则，L4规则执行生成opinion |
| **程序/技能层** | procedure | **L4 RuleLogic（候选升级）** | 弱→中 | 双向：procedure成功率高→建议升级为L4 rule_logic；L4规则模板指导procedure提取 |

#### 1.1.2 关键洞察：消除影子节点

当前设计中 `EntityNode`（Schema 驱动）与 `MemoryUnitNode(type=entity)`（记忆视角）通过 `MAPPED_TO` 边关联，形成**影子节点模式**。维护成本包括：一致性同步、更新传播、索引冗余。

**融合方案：统一节点模型**

```cypher
-- 统一后的 CognitiveNode（替代 EntityNode + MemoryUnitNode）
CREATE NODE TABLE CognitiveNode (
    -- 标识层
    node_id STRING PRIMARY KEY,
    space_id STRING,
    
    -- 认知层归属（四层之一）
    cognitive_layer STRING,       -- "sensory" | "semantic" | "opinion" | "procedural"
    memory_type STRING,           -- "fragment" | "episode" | "observation" | "entity" | 
                                  -- "rule" | "mental_model" | "opinion" | "procedure"
    
    -- Schema 绑定（关键新增）
    schema_layer STRING,          -- "L1" | "L2" | "L3" | "L4" | null（未绑定）
    schema_ref STRING,            -- 引用 Schema 定义ID（如 "finance:Counterparty"）
    schema_alignment_score DOUBLE, -- [0,1] 与Schema的匹配度
    
    -- 内容层
    text STRING,
    embedding_vector_id STRING,   -- ChromaDB引用
    
    -- 记忆元数据（保留所有记忆系统的核心字段）
    strength DOUBLE DEFAULT 1.0,
    confidence DOUBLE DEFAULT 1.0,
    feedback_weight DOUBLE DEFAULT 0.5,
    proof_count INT64 DEFAULT 1,
    access_count INT64 DEFAULT 0,
    last_accessed_at STRING,
    
    -- 时序层（双时序）
    valid_from STRING,            -- 事实有效期起始 (T)
    valid_to STRING,              -- 事实有效期终止 (T)
    recorded_at STRING,           -- 系统记录时间 (T')
    occurred_at STRING,           -- 事件发生时间
    
    -- 状态机
    status STRING DEFAULT "active",  -- "active" | "stale" | "superseded" | "archived" | "deprecated"
    
    -- 扩展属性
    attributes STRING,            -- JSON：类型特有字段 + Schema 约束字段的统一存储
    tags STRING[],
    
    -- 溯源
    source_ids STRING[],
    source_pipeline STRING,
    source_content_hash STRING,
    
    -- 变更追踪
    created_at STRING,
    updated_at STRING,
    consolidated_at STRING,
    version INT64 DEFAULT 1
)
```

**关键设计决策**：

| 决策 | 选择 | 理由 |
|------|------|------|
| 单表 vs 多表 | **单表+layer/type分区索引** | KuzuDB的节点表类型约束强，但认知节点共享80%字段，多表导致JOIN复杂。单表+复合索引（`cognitive_layer + memory_type + schema_layer`）在KuzuDB中性能足够 |
| JSON attributes vs 强类型列 | **JSON attributes + Schema约束校验** | 不同类型特有字段差异大，强类型列导致稀疏表。但L1/L3/L4绑定节点需额外Schema约束校验层 |
| 影子节点消除方式 | **统一CognitiveNode，Schema约束作为外部校验** | 消除MemoryUnitNode↔EntityNode的同步开销，Schema约束在写入/更新时通过校验层强制执行 |

#### 1.1.3 Schema 作为记忆巩固的提取模板

当前Consolidation依赖LLM判断"是否匹配Schema entity pattern"，但Schema本身应提供**结构化提取模板**：

```yaml
# L1 EntityDeclaration 自动转化为提取模板
L1_EntityDeclaration:
  name: "Counterparty"
  attributes:
    - name: "debt_ratio"
      type: "decimal"
      required: true
      extraction_hint: "资产负债率|debt ratio|负债率"
    - name: "registered_capital"
      type: "Money"
      required: true
      extraction_hint: "注册资本|registered capital"
    - name: "risk_grade"
      type: "enum"
      enum_type: "RiskGrade"
      required: false   # 可由L4规则推导
  
  # 自动生成的提取模板（由SchemaLoader构建）
  extraction_template:
    entity_name: "交易对手|企业|公司"
    required_fields: ["debt_ratio", "registered_capital"]
    confidence_threshold: 0.7
```

**Consolidation引擎的Schema感知提取**：

```python
class SchemaAwareExtraction:
    def __init__(self, schema_loader):
        self.templates = schema_loader.build_extraction_templates()
    
    async def extract_from_fragments(self, fragments, space_id):
        # 1. 识别碎片中可能涉及的Schema类型
        candidate_schemas = self._match_schema_hints(fragments)
        
        # 2. 对每个候选Schema，使用其提取模板引导LLM提取
        extractions = []
        for schema in candidate_schemas:
            template = self.templates[schema.name]
            result = await llm.extract_with_template(
                fragments=fragments,
                template=template,
                constraints=schema.attributes  # Schema约束注入Prompt
            )
            extractions.append(SchemaAlignedExtraction(
                schema_ref=schema.name,
                extracted_fields=result.fields,
                alignment_score=result.confidence,
                source_fragments=[f.id for f in fragments]
            ))
        
        # 3. 按alignment_score排序，高匹配度直接进入entity层
        extractions.sort(key=lambda x: x.alignment_score, reverse=True)
        return extractions
```

**这一设计的革命性意义**：
- **Schema不再是事后约束，而是事前引导**——LLM提取时就知道"应该提取什么字段"
- **alignment_score 成为记忆质量的量化指标**——高分记忆可自动升级为L1实例
- **低分记忆自动降级为observation**——避免不符合Schema的碎片强行entity化

---

### 1.2 Schema-Memory 双向反馈环

#### 1.2.1 记忆驱动 Schema 演化的量化标准

当Agent交互中积累大量observation/episode时，系统应能**自动建议Schema更新**。这需要可量化的标准：

| 触发条件 | 量化指标 | 建议的Schema变更 | 审批路径 |
|---------|---------|----------------|---------|
| 频繁提取同类型实体 | 某`schema_ref`的observation数 > 100且alignment_score > 0.8 | 建议将临时observation提升为正式L1 EntityDeclaration | 知识管理员审核 |
| 反复出现的计算模式 | 某metric的dependencies中出现高频非声明属性 | 建议L3 MetricDeclaration新增dependencies | 数据分析师审核 |
| procedure成功率达标 | success_rate > 0.8且invocation_count > 10 | 建议将procedure升级为L4 rule_logic | 领域专家审核 |
| observation跨域聚合需求 | cross_tag_aggregation触发频率 > 5次/天 | 建议新增L2 dimension或aggregate标签 | 架构师审核 |
| 新关系类型发现 | 提取到未在L1 RelationDeclaration中声明的关系 > 20次 | 建议新增L1 relation类型 | 领域专家审核 |

#### 1.2.2 反馈环的实现机制

```
CognitiveNode(observation/episode) 积累
    ↓
[PatternDetector] 统计高频模式
    - 高频提取字段 → 建议L1属性扩展
    - 高频计算链 → 建议L3 metric
    - 高频操作序列 → 建议L4 rule_logic
    - 高频标签组合 → 建议L2 dimension
    ↓
[SchemaProposal] 生成Schema变更提案
    - 包含：变更类型、影响范围、示例数据、confidence
    ↓
[ReviewQueue] 进入人工审核队列
    - 紧急度评分（基于影响范围 × 使用频率）
    ↓
[管理员审批] 确认/修改/拒绝
    ↓
[SchemaMigration] Schema版本更新
    - 版本号递增
    - 存量记忆的schema_alignment_score重新计算
    - 绑定旧Schema的记忆标记为"pending_realignment"
    ↓
[MemoryRealignment] 存量记忆重新对齐
    - 高alignment_score的记忆自动升级绑定
    - 低alignment_score的记忆保持原绑定+人工review标记
    ↓
[循环]
```

---

## 二、知识加工编译更新的管理模式

### 2.1 编译管道的阶段划分

将知识从原始输入到可检索记忆的过程定义为**五阶段编译管道**：

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Stage 1    │ → │  Stage 2    │ → │  Stage 3    │ → │  Stage 4    │ → │  Stage 5    │
│  Ingestion  │   │  Extraction │   │  Alignment  │   │  Indexing   │   │  Cascade    │
│  原始摄入    │   │  实体/事件   │   │  Schema对齐  │   │  索引构建    │   │  级联更新    │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
   同步(t+0)        准同步(t+1s)      异步(t+5s)       异步(t+10s)       异步(t+30s+)
```

| 阶段 | 输入 | 处理 | 输出 | SLA | 失败策略 |
|------|------|------|------|-----|---------|
| **Ingestion** | 原始文档/对话/API响应 | 分块、去重、哈希校验 | KnowledgeFragment | t+0同步 | 阻塞写入，返回错误 |
| **Extraction** | Fragment | LLM提取实体/事件/关系/观察 | RawExtraction（未校验） | t+1-5s | 标记failed，入重试队列 |
| **Alignment** | RawExtraction | Schema匹配、字段校验、alignment_score计算 | SchemaAlignedMemory | t+5-30s | 低分转observation，高分转entity |
| **Indexing** | SchemaAlignedMemory | 向量嵌入、图节点创建、边构建、互索引 | IndexedMemory | t+10-60s | 索引失败标记，后台重试 |
| **Cascade** | IndexedMemory | 影响分析、mental_model刷新检查、procedure学习检查 | UpdatedCognitiveState | t+30s-1h | 入低优先级队列，不阻塞 |

#### 2.1.1 脏标记与一致性状态机

每段记忆在各阶段的状态：

```python
class CompilationState(Enum):
    INGESTED = "ingested"           # 已摄入，待提取
    EXTRACTING = "extracting"       # 提取中
    EXTRACTED = "extracted"         # 已提取，待对齐
    ALIGNING = "aligning"           # 对齐中
    ALIGNED = "aligned"             # 已对齐，待索引
    INDEXING = "indexing"           # 索引中
    ACTIVE = "active"               # 完全可用
    STALE = "stale"                 # 依赖的上层记忆已更新
    SUPERCEDED = "superseded"       # 被新版本取代
    FAILED = "failed"               # 某阶段失败
    ARCHIVED = "archived"           # 已归档
```

状态转换图：

```
[INGESTED] --(提取成功)--> [EXTRACTED] --(对齐成功)--> [ALIGNED] --(索引成功)--> [ACTIVE]
     |                        |                      |                      |
     |--(提取失败)--> [FAILED] |--(对齐低分)--> [OBSERVATION_ONLY]   |--(索引失败)--> [INDEX_RETRY]
     |                        |                      |                      |
     |--(重试成功)------------┘                      |                      |
                                                   |--(级联更新)--> [STALE]
                                                   |
                                              [ACTIVE] --(信念修正)--> [SUPERCEDED]
```

### 2.2 增量更新策略

#### 2.2.1 增量更新决策矩阵

当新信息到达时，不是全量重编译，而是**精确影响分析**：

```python
class IncrementalUpdatePlanner:
    def plan_update(self, new_fragment, existing_memory_graph) -> UpdatePlan:
        # 1. 识别受影响节点
        affected_nodes = self._find_affected_nodes(new_fragment)
        
        # 2. 根据影响范围决定更新策略
        plan = UpdatePlan()
        
        for node in affected_nodes:
            impact = self._assess_impact(node, new_fragment)
            
            if impact.scope == "self_only":
                # 仅影响节点自身属性 → 原地更新
                plan.add_action(UpdateAction.UPDATE_IN_PLACE, node)
            
            elif impact.scope == "direct_neighbors":
                # 影响直接邻居 → 标记邻居为stale，触发局部刷新
                plan.add_action(UpdateAction.MARK_STALE, node.neighbors)
                plan.add_action(UpdateAction.LOCAL_REFRESH, node)
            
            elif impact.scope == "downstream_graph":
                # 影响下游图（如核心实体属性变化影响所有依赖的metric/rule）
                downstream = self._traverse_downstream(node, max_depth=3)
                plan.add_action(UpdateAction.MARK_STALE, downstream)
                plan.add_action(UpdateAction.ENQUEUE_CASCADE, node)
            
            elif impact.scope == "schema_level":
                # 影响Schema定义本身（如发现新实体类型）
                plan.add_action(UpdateAction.SCHEMA_PROPOSAL, node)
                plan.add_action(UpdateAction.MEMORY_REALIGNMENT, all_nodes_of_type(node.type))
        
        return plan
```

#### 2.2.2 影响分析算法

```cypher
-- 查找受影响的节点（基于实体ID和标签重叠）
MATCH (new:CognitiveNode {node_id: $new_id})
MATCH (existing:CognitiveNode)
WHERE existing.node_id <> new.node_id
  AND existing.space_id = new.space_id
  AND existing.status = "active"
  AND (
      -- 条件1：共享实体引用
      ANY(entity_ref IN existing.attributes['entity_refs'] 
          WHERE entity_ref IN new.attributes['entity_refs'])
      OR
      -- 条件2：标签重叠
      ANY(tag IN existing.tags WHERE tag IN new.tags)
      OR
      -- 条件3：时间邻近
      (existing.occurred_at IS NOT NULL AND new.occurred_at IS NOT NULL
       AND abs(duration.inDays(
            datetime(existing.occurred_at), 
            datetime(new.occurred_at)
          ).days) < 7)
  )
RETURN existing.node_id, existing.cognitive_layer, existing.memory_type,
       existing.schema_ref, existing.strength
```

---

## 三、矛盾处理与信息更正的双轨治理

### 3.1 矛盾分类学

不是所有矛盾都一样。**矛盾的性质决定了处理方式**：

| 矛盾类型 | 定义 | 检测方式 | 处理模式 | 责任方 |
|---------|------|---------|---------|--------|
| **事实型矛盾** | 同一实体同一属性有两个不同值 | Schema约束检查 + 确定性比对 | 双轨：企业场景人工确认 / Agent场景自动信念修正 | 系统+人工 |
| **时序型矛盾** | 同一属性的新旧版本冲突 | 双时序模型检测（T/T'） | 自动：新版本Supersedes旧版本 | 系统自治 |
| **观点型矛盾** | 不同来源对同一事实的不同解读 | LLM语义矛盾检测 | 自动：Opinion置信度更新，保留多视角 | 系统自治 |
| **规则型矛盾** | L4规则之间的逻辑冲突 | 规则引擎前置校验 | 人工：规则优先级调整或规则合并 | 领域专家 |
| **Schema型矛盾** | 数据不符合Schema约束 | Schema校验层 | 自动拒绝写入 + 错误报告 | 系统自治 |
| **跨域型矛盾** | 不同space对同一实体的描述冲突 | 跨域实体对齐检测 | 人工：域间canonical映射确认 | 架构师 |

### 3.2 双轨治理架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         矛盾检测层（统一入口）                                 │
│  DetectionEngine: Schema校验 + 语义比对 + 时序检查 + 规则冲突扫描             │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│  轨道A：企业知识治理轨道   │           │  轨道B：Agent记忆自治轨道 │
│  (Schema约束型矛盾)       │           │  (信念演化学型矛盾)       │
├─────────────────────────┤           ├─────────────────────────┤
│ • 事实型矛盾（实体属性）   │           │ • 时序型矛盾（新旧版本）   │
│ • 规则型矛盾（L4冲突）     │           │ • 观点型矛盾（不同解读）   │
│ • Schema型矛盾（约束违反） │           │ • 用户偏好变化            │
│ • 跨域型矛盾（域间不一致） │           │ • Agent经验修正           │
├─────────────────────────┤           ├─────────────────────────┤
│ 处理流程：               │           │ 处理流程：               │
│ 1. 自动检测              │           │ 1. 自动检测              │
│ 2. 生成矛盾报告           │           │ 2. 置信度比较            │
│ 3. 人工确认（阻塞）       │           │ 3. 自动信念修正           │
│ 4. 标记deprecated        │           │ 4. Supersedes边链接      │
│ 5. 审计日志              │           │ 5. 下游影响分析           │
│ 6. 通知下游消费者         │           │ 6. 置信度传播更新         │
├─────────────────────────┤           ├─────────────────────────┤
│ SLA：分钟级-小时级        │           │ SLA：秒级-分钟级          │
│ 准确率要求：>99%         │           │ 准确率要求：>85%（可接受误报）│
│ 人工介入：必须            │           │ 人工介入：可选review       │
└─────────────────────────┘           └─────────────────────────┘
              │                                   │
              └─────────────────┬─────────────────┘
                                ▼
              ┌─────────────────────────────────┐
              │      混合场景：信任边界仲裁        │
              │  当Agent自生记忆影响企业知识时      │
              │  → 触发轨道A的降级审核             │
              └─────────────────────────────────┘
```

### 3.3 信息更正的时序模型

#### 3.3.1 更正的图表示

参考Zep的双时序模型，设计更正链的图结构：

```cypher
-- 更正链：A（原始）→ B（第一次更正）→ C（第二次更正）
-- 每个节点都保留，通过SUPERSEDES链连接

CREATE REL TABLE SUPERCEDES (
    FROM CognitiveNode TO CognitiveNode,
    supersedence_type STRING,      -- "correction" | "update" | "retraction" | "belief_revision"
    supersedence_reason STRING,    -- 人类可读原因
    supersedence_confidence DOUBLE, -- 更正的置信度
    initiated_by STRING,           -- "user" | "agent" | "system" | "admin"
    review_status STRING,          -- "auto" | "pending_review" | "approved" | "rejected"
    created_at STRING
)

-- 查询某节点的当前有效版本（沿着SUPERSEDES链找到最新）
-- 注意：不是"最新"，而是"未被superseded的最新"
MATCH path = (start:CognitiveNode)-[s:SUPERCEDES*0..]->(current:CognitiveNode)
WHERE start.node_id = $original_id
  AND NOT EXISTS {
      MATCH (current)-[:SUPERCEDES]->(next)
      WHERE next.status <> "rejected"
  }
RETURN current
```

#### 3.3.2 更正传播协议

当一个L1实体属性被更正时，依赖它的所有上层知识都需要重新评估：

```python
class CorrectionPropagationEngine:
    async def propagate_correction(self, corrected_node_id, correction_type):
        # 1. 找到所有依赖该节点的上游节点
        dependents = await self._find_dependents(corrected_node_id)
        
        # 2. 分类处理
        for dep in dependents:
            if dep.cognitive_layer == "semantic" and dep.memory_type == "mental_model":
                # mental_model：标记stale，触发异步刷新
                await self._mark_stale(dep, reason=f"upstream_corrected:{corrected_node_id}")
                await self._enqueue_refresh(dep, priority="high")
            
            elif dep.cognitive_layer == "semantic" and dep.memory_type == "observation":
                # observation：检查是否与更正矛盾
                if await self._is_contradicted(dep, corrected_node_id):
                    await self._mark_for_review(dep, reason="possible_obsolescence")
                else:
                    await self._update_strength(dep, delta=-0.1)  # 轻微降权
            
            elif dep.cognitive_layer == "opinion" and dep.memory_type == "opinion":
                # opinion：重新计算置信度
                new_confidence = await self._recompute_opinion_confidence(dep)
                await self._update_opinion(dep, confidence=new_confidence)
                if new_confidence < 0.3:
                    await self._mark_superseded(dep, reason="confidence_fell_below_threshold")
            
            elif dep.schema_layer == "L4":
                # L4规则执行结果：标记ExecutionStepSnapshot为stale
                await self._invalidate_rule_execution(dep)
                await self._enqueue_rule_reexecution(dep)
        
        # 3. 生成影响报告
        impact_report = CorrectionImpactReport(
            corrected_node=corrected_node_id,
            affected_nodes=len(dependents),
            by_layer=self._group_by_layer(dependents),
            actions_taken=...
        )
        return impact_report
```

---

## 四、实际案例深度辩论：供应链金融风控Agent

### 4.1 场景设定

某银行使用OntologyEngine构建供应链金融风控Agent，核心功能：
1. 监控核心企业（华为）及其上下游供应商的信用风险
2. 当新财报、舆情、合同数据进入时，自动更新风险评估
3. 支持时序查询："华为2024年Q3的担保敞口是多少？"
4. 支持因果查询："为什么供应商B的信用等级从B降到了C？"
5. 支持经验复用："上次处理类似供应链金融暴雷事件时，Agent采取了什么措施？"

### 4.2 30天事件流

```
Day 1:  导入华为2024年报 → Agent提取财务指标 → 信用评分=A
Day 5:  新闻：华为某子公司涉及诉讼 → Agent记录episode → 触发observation更新
Day 10: 用户询问："华为风险如何？" → Agent检索并回答
Day 15: 新导入征信报告：华为债务率上升 → 与Day 1的observation矛盾
Day 20: 用户更正："那起诉讼已经撤诉了" → 需要信息更正
Day 25: Agent自动归纳：近30天3次类似"债务率上升但随后澄清"模式 → 触发procedure提取
Day 30: 用户问："过去一个月华为风险判断为什么波动？" → 需要时序追溯和因果解释
```

### 4.3 多方案对比分析

#### 方案A：当前OntologyEngine设计

**Day 1 处理**：
- 年报PDF → Layer-R fragments（按800字符分块）
- ExtractionPipeline提取entity：华为(debt_ratio=0.45, revenue=7000亿)
- EntityNode创建 + MemoryUnitNode(type=entity)影子节点创建 + MAPPED_TO边
- L3 metric计算：credit_score = f(debt_ratio, revenue, ...) = 850 → 等级A

**Day 5 处理**：
- 新闻文本 → Layer-R fragment
- LLM提取observation："华为子公司涉及诉讼"
- 问题：此observation与华为entity的哪个属性关联？当前设计无自动关联，需人工打标签

**Day 15 矛盾**：
- 新征信报告 → debt_ratio=0.65（与Day 1的0.45矛盾）
- 当前处理：生成contradiction_report → 等待人工确认
- 问题：在人工确认前，用户查询"华为债务率"返回哪个值？当前设计无自动时序处理

**Day 20 更正**：
- 用户输入："诉讼已撤诉"
- 当前处理：创建新observation → 与旧observation并存
- 问题：旧observation是否自动失效？当前设计无Supersedes机制

**Day 25 procedure提取**：
- 当前设计：检测同主题episode≥3 → 触发ProcedureExtractionEngine
- 问题：当前设计无此引擎，procedure只能手动创建

**Day 30 查询**：
- 查询："过去一个月华为风险判断为什么波动？"
- 当前检索：recall(query, space_id) → 并行搜索所有memory_type → RRF融合 → 按权重排序
- 返回结果： mental_model("华为风险中等") + entity(debt_ratio=0.65) + observation("诉讼已撤诉") + fragment(原始新闻)
- 问题：返回的是一堆记忆碎片，Agent需要自行从中推断"波动原因"，系统不提供因果链构建

**方案A总评**：
| 维度 | 评分 | 说明 |
|------|------|------|
| 时序追溯 | ⭐⭐ | valid_from/to可回答"某时点值"，但无法回答"为什么变化" |
| 因果解释 | ⭐ | 无因果边，无事件链，因果解释完全依赖LLM推理 |
| 矛盾处理 | ⭐⭐ | 能检测矛盾，但处理依赖人工，自治能力弱 |
| 信息更正 | ⭐⭐ | ADD-only保留历史，但无Supersedes链，更正可追溯性差 |
| 经验复用 | ⭐ | 无procedure自动提取，经验无法系统化复用 |
| Token效率 | ⭐⭐⭐ | RRF融合3路，但没有分层短路 |

---

#### 方案B：Hindsight式四网络分离 + Schema绑定

**核心改造**：在OntologyEngine中引入Hindsight的四网络架构，但绑定到Schema L1-L4

**Day 1 处理**：
- 年报 → **World Network**（事实）：华为(debt_ratio=0.45, revenue=7000亿)
- 同时创建 **Observation Network**（摘要）："华为2024财务稳健，债务率低"
- Schema绑定：World Network实体 → L1 EntityInstance
- L3 metric计算 → 结果存入World Network + Observation Network更新

**Day 5 处理**：
- 新闻 → **Experience Network**（Agent经历）："Agent观察到华为子公司诉讼新闻"
- 自动提取World Fact："华为子公司X涉及诉讼Y"
- Opinion Network更新："诉讼可能影响华为信用"（confidence=0.6，低置信度因为刚发生）

**Day 15 矛盾**：
- 新征信报告 → World Fact更新：debt_ratio=0.65
- **自动信念修正**：新事实与旧事实（debt_ratio=0.45）在数值上矛盾
- 处理：旧fact不删除，创建Supersedes边（新→旧），reason="updated_by_new_report"
- Opinion Network自动调整：原opinion("财务稳健") confidence从0.9降至0.5
- 触发Observation Network刷新：标记原摘要为stale

**Day 20 更正**：
- 用户输入："诉讼已撤诉"
- Experience Network记录："用户告知诉讼已撤诉"
- World Fact更新：创建新fact("诉讼Y已撤诉")，Supersedes旧fact("诉讼Y进行中")
- **级联影响**：
  - Opinion Network：原opinion("诉讼可能影响信用") confidence降至0.2 → 标记superseded
  - Observation Network：刷新华为摘要 → "华为2024财务稳健，曾涉诉但已撤诉"

**Day 25 procedure提取**：
- Experience Network中3次类似episode："债务率上升新闻→后续澄清"
- 自动提取 **Procedure**："当核心企业出现负面新闻时，先标记observation，等待72小时观察是否有澄清，再更新risk_grade"
- success_rate = 2/3（3次中2次确实有澄清）

**Day 30 查询**：
- 查询："过去一个月华为风险判断为什么波动？"
- Hindsight TEMPR检索：
  - Step 1：Observation Network → 命中华为摘要（已刷新）
  - Step 2：World Network → 检索debt_ratio变化历史（0.45→0.65，因新征信报告）
  - Step 3：Experience Network → 检索Agent的决策记录（"因诉讼新闻下调评级，后因撤诉恢复"）
  - Step 4：Opinion Network → 检索Agent的评估观点（"新闻驱动的短期波动，基本面未变"）
- CARA Reflect：结合Disposition参数生成解释
  - 若skepticism高："波动主要源于信息噪声，建议关注基本面"
  - 若empathy高："波动确实令人担忧，已记录完整时间线供您参考"

**证据链组装**：
```json
{
  "answer": "过去一个月华为风险判断经历两次波动：",
  "causal_chain": [
    {
      "event": "Day 5 诉讼新闻",
      "world_fact": "子公司涉诉",
      "agent_action": "记录episode，下调opinion置信度",
      "impact": "risk_grade从A→B（Opinion驱动）"
    },
    {
      "event": "Day 15 征信报告",
      "world_fact": "debt_ratio上升至0.65",
      "agent_action": "Supersedes旧debt_ratio，触发Observation刷新",
      "impact": "risk_grade保持B（数据支撑）"
    },
    {
      "event": "Day 20 用户更正",
      "world_fact": "诉讼已撤诉（Supersedes原诉讼fact）",
      "agent_action": "级联更新：Opinion降级，Observation刷新",
      "impact": "risk_grade从B→A（负面因素消除）"
    }
  ],
  "agent_reflection": "波动主要由外部信息驱动，非基本面恶化。已提取procedure供未来类似事件参考。",
  "source_fragments": ["frag_001(年报)", "frag_005(新闻)", "frag_015(征信)", "frag_020(用户更正)"]
}
```

**方案B总评**：
| 维度 | 评分 | 说明 |
|------|------|------|
| 时序追溯 | ⭐⭐⭐⭐⭐ | 双时序+Supersedes链，完整追溯任何时点的知识状态 |
| 因果解释 | ⭐⭐⭐⭐ | 四网络分离+Experience记录，Agent能解释"我为什么这么判断" |
| 矛盾处理 | ⭐⭐⭐⭐ | 自动信念修正+置信度传播，但AGM形式化较弱 |
| 信息更正 | ⭐⭐⭐⭐⭐ | Supersedes链+级联更新，更正完全可追溯 |
| 经验复用 | ⭐⭐⭐ | Procedure自动提取，但成功率统计较简单 |
| Token效率 | ⭐⭐⭐ | TEMPR四路并行成本较高，但分层检索可优化 |

**方案B的代价**：
- 存储成本：旧版本不删除，存储随时间线性增长（需归档策略）
- 查询复杂度：四网络检索+跨网络关联，Cypher查询复杂
- 工程成本：需重构当前双层架构为四网络

---

#### 方案C：MAGMA式四正交图 + Schema策略引导

**核心改造**：将记忆按关系维度分离为四张正交图，Schema定义遍历策略

**四张正交图**：

```
语义图（Semantic Graph）：
  节点：实体、概念
  边：语义关系（guarantees, supplies, employs）
  用途：回答"是什么"、"有什么关系"

时序图（Temporal Graph）：
  节点：事件、时间戳
  边：时序关系（PRECEDES, SUCCEEDS, TEMPORALLY_CLOSE）
  用途：回答"何时"、"先后顺序"

因果图（Causal Graph）：
  节点：状态变化、决策点
  边：因果关系（CAUSES, ENABLES, PREVENTS）
  用途：回答"为什么"、"如何导致"

实体图（Entity Graph）：
  节点：具体实例（华为、供应商B）
  边：实例关系（same_as, part_of, instance_of）
  用途：实体消歧、跨域对齐
```

**Day 1 处理**：
- 年报 → 同时写入四张图：
  - 语义图：华为 --[has_attribute]--> debt_ratio=0.45
  - 时序图：年报发布事件（2024-03-31）
  - 实体图：华为（canonical实体）

**Day 15 矛盾**：
- 新征信报告 → debt_ratio=0.65
- **四图级联更新**：
  - 语义图：更新属性值（旧值标记valid_to=Day15，新值valid_from=Day15）
  - 时序图：创建"征信报告导入事件"，链接到"年报事件"（SUCCEEDS）
  - 因果图：创建"新征信报告 → debt_ratio更新"因果边

**Day 30 查询**：
- 查询："过去一个月华为风险判断为什么波动？"
- **策略引导遍历**：
  1. 查询意图解析：`{intent: "causal_explanation", target: "华为", aspect: "risk_volatility", timeframe: "past_month"}`
  2. 策略选择器：因果解释 → 优先遍历**因果图**，辅以**时序图**和**语义图**
  3. 遍历路径：
     ```
     因果图起点：华为风险等级变化节点
       → CAUSES → 找出导致变化的事件节点
         → 事件1：诉讼新闻（Day5）
         → 事件2：征信报告更新（Day15）
         → 事件3：用户更正（Day20）
       → 每个事件节点 → 跳转时序图获取精确时间
       → 每个事件节点 → 跳转语义图获取具体数值变化
     ```
  4. 结果组装：按时间线排序的因果链

**方案C总评**：
| 维度 | 评分 | 说明 |
|------|------|------|
| 时序追溯 | ⭐⭐⭐⭐⭐ | 独立时序图，时序查询原生高效 |
| 因果解释 | ⭐⭐⭐⭐⭐ | 独立因果图+策略引导，因果解释是原生能力 |
| 矛盾处理 | ⭐⭐⭐ | 时序图天然支持版本，但信念修正需额外实现 |
| 信息更正 | ⭐⭐⭐⭐ | 时序图的valid_to机制支持更正追溯 |
| 经验复用 | ⭐⭐⭐ | 策略本身可被学习，但procedure提取需额外机制 |
| Token效率 | ⭐⭐⭐⭐ | 策略引导剪枝，避免全图扫描 |

**方案C的代价**：
- 存储成本：同一事实存储4次（四张图各一次）
- 一致性成本：四图同步更新，事务复杂
- 工程成本：需实现四图存储+策略引擎，工作量极大

---

### 4.4 关键设计决策辩论

#### 辩论1：统一节点 vs 分离节点

**观点A：统一CognitiveNode（推荐）**
- **论据**：当前EntityNode+MemoryUnitNode影子节点维护成本已证实过高。统一节点减少同步开销，单表查询优于JOIN。
- **代价**：JSON attributes丧失类型安全，需额外校验层；KuzuDB单表过大可能影响性能。
- **适用场景**：中小型知识库（<100万节点），追求工程简洁性。

**观点B：每层独立节点表（MAGMA式）**
- **论据**：认知层的功能差异根本（感知层不需要confidence，观点层需要belief_status），独立表可针对每层优化索引和存储。
- **代价**：跨层查询需JOIN或多次查询，代码复杂度显著增加。
- **适用场景**：超大规模知识库（>1000万节点），每层独立扩展。

**观点C：混合方案（折中）**
- **语义层/观点层统一**（共享字段多），**感知层独立**（原文存储差异大），**程序层独立**（结构化规则差异大）。
- **这是OntologyEngine当前双层架构的自然演进**：Layer-R保持独立（感知层），Layer-S扩展为统一CognitiveNode（语义+观点+程序）。

**我的判断**：推荐**观点C的演进版本**——不是完全统一，而是"两层存储 × 四层认知"的矩阵：
- Layer-R：独立（感知/情景）
- Layer-S：统一CognitiveNode，但通过`cognitive_layer`分区（语义/观点/程序）

#### 辩论2：ADD-only vs CUD

**观点A：ADD-only（Mem0式）**
- **论据**：保留完整历史，时序推理天然支持"之前如何想"。无需复杂的更新传播逻辑。
- **代价**：存储膨胀，检索噪声增加（旧版本可能干扰当前查询）。
- **关键问题**：10M token规模下，相似内容反复出现，如何精确检索？

**观点B：CUD + Supersedes（Kumiho式）**
- **论据**：旧版本标记superseded，当前查询默认只看到最新版本，噪声低。Supersedes链保留历史可追溯性。
- **代价**：更新传播复杂（AnalyzeImpact遍历下游），信念修正引擎实现难度大。
- **关键问题**：Supersedes链深度过大时，查询性能如何保障？

**观点C：分层策略（推荐）**
- **感知层ADD-only**：原始碎片永不删除，保真度优先。
- **语义层CUD+Supersedes**：entity/observation允许更新，旧版本标记。
- **观点层CUD+置信度更新**：opinion可更新confidence，不创建新版本（除非文本变化）。
- **程序层版本控制**：procedure/rule_logic使用语义版本（v1→v2）。

**我的判断**：推荐**观点C的分层策略**。不同认知层对历史的依赖程度不同：感知层需要完整历史（审计），语义层需要版本控制（可追溯），观点层需要置信度演化（动态），程序层需要版本管理（兼容性）。

#### 辩论3：自动信念修正 vs 人工审核

**观点A：完全自动（Agent自治）**
- **论据**：Agent记忆的本质是自治演化。人工审核引入延迟，破坏Agent的实时响应能力。
- **代价**：错误传播风险。一次错误的信念修正可能导致连锁反应。
- **适用边界**：仅适用于低风险的Agent自生记忆（用户偏好、交互历史）。

**观点B：完全人工（企业治理）**
- **论据**：金融风控场景下，任何知识变更都可能影响授信决策，必须人工确认。
- **代价**：不可扩展。Agent交互频率可能达到每秒数千次，人工无法跟上。
- **适用边界**：仅适用于高风险的企业核心知识（客户评级、授信额度、合规规则）。

**观点C：双轨制 + 信任边界（强烈推荐）**
- **设计**：
  - **轨道A（企业知识）**：Schema约束型记忆（entity属性、rule定义、metric计算）→ 人工审核或强规则自动校验。
  - **轨道B（Agent记忆）**：Agent自生记忆（observation、opinion、episode）→ 自动信念修正，置信度低于阈值时标记待review。
  - **信任边界**：Agent自生记忆默认不影响企业核心决策。当Agent记忆的confidence > 0.9且与Schema对齐时，可建议升级为轨道A。

**我的判断**：**观点C是唯一可行的方案**。完全自动在金融场景不可接受，完全人工在Agent场景不可扩展。双轨制通过"信任边界"平衡自治与治理。

#### 辩论4：Schema约束优先 vs 记忆演化优先

**观点A：Schema约束优先（强类型）**
- **论据**：金融系统的数据质量是生命线。强Schema约束确保所有数据符合业务规则，避免脏数据进入系统。
- **代价**：灵活性差。Agent发现的新知识类型无法快速纳入，Schema更新流程冗长。

**观点B：记忆演化优先（弱Schema）**
- **论据**：Agent的核心价值在于发现人类未预见的模式。强Schema约束扼杀创新。
- **代价**：知识库可能陷入混乱。无约束的记忆增长导致"记忆通货膨胀"。

**观点C：Schema引导 + 沙箱演化（推荐）**
- **设计**：
  - **主空间（Production Space）**：强Schema约束，仅允许符合Schema的记忆进入。
  - **沙箱空间（Sandbox Space）**：弱Schema约束，允许Agent自由演化记忆。
  - **晋升机制**：沙箱中的记忆满足条件（alignment_score > 0.9, proof_count > 10, 人工review通过）→ 晋升到主空间。

**我的判断**：**观点C**。这类似于软件开发的"dev/staging/prod"环境分离。Agent在沙箱中自由实验，有价值的发现经过验证后进入生产环境。

---

## 五、关键问题的多方向讨论：意义与代价

### 问题1：四层认知分离的粒度——过细还是过粗？

**方向A：更细（六层或更多）**
- 将"语义层"拆分为"事实层"（World Facts）和"经验层"（Experience Facts），对应Hindsight的区分。
- 将"观点层"拆分为"评估层"（assessment）和"偏好层"（preference）。
- **意义**：更精确的认知建模，检索时更精准地选择记忆类型。
- **代价**：层数增加导致检索路由复杂度指数级上升。Agent需要理解的层次从4层变为6层+。

**方向B：更粗（三层）**
- 感知层（原始输入）
- 工作记忆层（当前活跃的entity/observation/opinion，可推理）
- 长期记忆层（归档的mental_model/procedure）
- **意义**：与Letta的OS隐喻对齐，Agent更容易理解和管理。
- **代价**：丢失了观点/事实的区分，矛盾处理变得困难。

**方向C：动态层（推荐探索）**
- 不预设固定层数，而是根据知识的"抽象度"动态分层。
- 抽象度 = f(proof_count, consolidation_depth, generalization_scope)
- **意义**：知识自然沉淀到合适的抽象层次，无需人工指定memory_type。
- **代价**：动态分层算法复杂，可能导致同一知识在不同时间处于不同层，检索不确定性增加。

---

### 问题2：信念修正的形式化程度——AGM-lite还是启发式？

**方向A：完整AGM框架（Kumiho式）**
- 实现AGM信念修正的全部公设（Success, Consistency, Inclusion, Preservation, Relevance, Core-Retainment）。
- **意义**：形式化保证信念修正的逻辑正确性，可审计、可验证。
- **代价**：AGM框架的实现复杂度极高。在图数据库上的信念基操作（最小子集、交集、并集）性能开销大。

**方向B：启发式信念修正（Hindsight式）**
- 通过Opinion Network的confidence更新实现"实用主义"信念修正，无形式化保证。
- **意义**：实现简单，运行高效，在实践中已被验证有效（Hindsight LoCoMo 89.6%）。
- **代价**：无法保证一致性。极端情况下可能出现循环修正（A取代B，C取代A，B取代C）。

**方向C：规则驱动的信念修正（推荐）**
- 不追求完整AGM，而是定义一组可配置的信念修正规则：
  - "新证据confidence > 旧证据confidence × 2 → 自动取代"
  - "feedback_weight > 0.9的记忆永不被取代（除非用户明确撤销）"
  - "entity核心属性的变更必须触发下游所有metric重算"
- **意义**：在形式化和实用性之间取得平衡。规则可审计、可调整。
- **代价**：规则本身可能成为新的复杂源，规则间的冲突需要额外处理。

---

### 问题3：跨层一致性的维护时机——即时同步还是最终一致？

**方向A：即时同步（强一致性）**
- 任何L1实体属性的变更，立即触发所有依赖的L3 metric、L4 rule、mental_model更新。
- **意义**：用户查询时永远看到一致的状态，不存在"mental_model说A但entity说B"的情况。
- **代价**：写入延迟显著增加。级联更新可能涉及数百个节点，阻塞用户写入。

**方向B：最终一致（推荐）**
- L1变更立即写入，上层依赖标记为stale，异步后台刷新。
- **意义**：写入性能不受影响，符合"离线巩固"的认知科学模型。
- **代价**：存在短暂的不一致窗口（stale标记期间）。用户在窗口期内查询可能看到矛盾结果。
- **缓解**：stale标记期间，检索结果附加`staleness_warning`。

**方向C：读写分离的一致性模型**
- 写入路径：最终一致（快速响应）
- 读取路径：可配置一致性级别
  - `read_consistency=strong`：等待所有stale依赖刷新后返回（高延迟，高一致性）
  - `read_consistency=eventual`：返回当前状态+staleness标记（低延迟，最终一致）
  - `read_consistency=raw`：直接返回，不做任何一致性检查（最低延迟，用于调试）

---

### 问题4：记忆资产的权限模型——谁拥有Agent的记忆？

**方向A：用户完全拥有**
- Agent的记忆是用户数据的延伸，用户有权查看、修改、删除任何记忆。
- **意义**：符合数据隐私法规（GDPR等），用户信任度高。
- **代价**：Agent无法保留"系统级"知识（如从多用户交互中学习到的通用模式）。

**方向B：系统/企业拥有**
- Agent的记忆是企业知识资产，用户仅有使用权，无所有权。
- **意义**：企业可聚合多用户数据训练更优的Agent，保护商业机密。
- **代价**：用户可能拒绝使用（隐私担忧），合规风险高。

**方向C：分层所有权（推荐）**
- **用户私有层**：与用户个人相关的记忆（偏好、历史交互）→ 用户完全控制。
- **企业共享层**：经过去标识化的通用知识（行业模式、规则模板）→ 企业所有。
- **系统自治层**：Agent自生但未经验证的记忆（observation、opinion）→ Agent自治，用户可review。
- **意义**：平衡隐私、商业价值和Agent自治。
- **代价**：权限模型复杂，需要精细的访问控制实现。

---

## 六、资产构建规范与治理框架

### 6.1 记忆资产的定义与分级

| 资产级别 | 定义 | 晋升标准 | 维护要求 | 生命周期 |
|---------|------|---------|---------|---------|
| **L0 原始素材** | 未经处理的fragment/episode | 无（自动摄入） | 保留完整溯源 | 7-30天TTL，除非被引用 |
| **L1 提取记忆** | observation/entity（Schema对齐后） | alignment_score > 0.7 | 绑定Schema，参与级联更新 | 活跃期90天，后归档 |
| **L2 摘要记忆** | mental_model/opinion | proof_count > 5, confidence > 0.8 | 定期刷新，标记stale机制 | 活跃期30天，需持续强化 |
| **L3 程序资产** | procedure/rule_logic | success_rate > 0.7, invocation > 10 | 版本管理，A/B测试 | 长期保留，deprecated标记 |
| **L4 知识资产** | 经人工确认的L1-L4 Schema定义 | 人工审批通过 | 变更管理，影响分析 | 永久保留，版本历史 |

### 6.2 资产版本管理规范

```yaml
versioning_policy:
  semantic_versioning: true    # major.minor.patch
  
  major_increment_rules:
    - "Schema结构变更（属性增删）"
    - "关系类型变更"
    - "规则逻辑根本性重写"
  
  minor_increment_rules:
    - "属性值更新（不影响结构）"
    - "新增observation归纳"
    - "mental_model刷新"
  
  patch_increment_rules:
    - "confidence微调"
    - "typo修正"
    - "metadata补充"
  
  backward_compatibility:
    major: "不兼容，需人工迁移"
    minor: "兼容，自动适配"
    patch: "完全兼容，透明更新"
```

### 6.3 资产淘汰策略

```python
class AssetLifecycleManager:
    ARCHIVAL_RULES = {
        "fragment": {
            "condition": "not_referenced_for > 90_days AND not_linked_to_any_entity",
            "action": "archive_to_cold_storage",
            "retention": "7_years"  # 合规要求
        },
        "observation": {
            "condition": "superseded_by_newer AND strength < 0.1",
            "action": "mark_archived",
            "retention": "2_years"
        },
        "mental_model": {
            "condition": "is_stale_for > 30_days AND last_accessed > 90_days_ago",
            "action": "archive_and_schedule_refresh_or_deletion",
            "retention": "1_year"
        },
        "opinion": {
            "condition": "confidence < 0.2_for > 30_days",
            "action": "archive",
            "retention": "6_months"
        },
        "procedure": {
            "condition": "success_rate < 0.3_after > 10_invocations",
            "action": "mark_deprecated",
            "retention": "permanent"  # 保留失败经验
        }
    }
```

### 6.4 治理仪表盘指标

| 指标 | 定义 | 健康阈值 | 异常处理 |
|------|------|---------|---------|
| **知识新鲜度** | active记忆占比 / 总记忆数 | > 70% | 触发批量刷新或归档 |
| **Schema对齐率** | alignment_score > 0.7的记忆占比 | > 80% | 提示Schema扩展或提取优化 |
| **矛盾密度** | CONTRADICTS边数 / 总记忆数 | < 5% | 触发BeliefRevision批量任务 |
| **Stale率** | stale标记记忆占比 | < 15% | 增加CascadeUpdate资源 |
| **记忆通胀率** | 月度记忆增长率 | < 30% | 触发归档或TTL调整 |
| **Procedure成功率** | 成功procedure / 总procedure调用 | > 70% | 提示procedure优化或废弃 |

---

## 七、总结与推荐路径

### 7.1 核心结论

1. **四层认知的互影响是动态的、双向的、非线性的**。不是简单的"升级路径"，而是包含注意力引导、信念修正、跨层验证、级联更新的复杂网络。

2. **Schema不是约束，而是认知骨架**。L1-L4定义了知识的"骨骼结构"，四层认知则是"血肉填充"。两者需要双向反馈——Schema引导记忆提取，记忆演化驱动Schema更新。

3. **矛盾处理必须双轨**。企业知识（轨道A）需要人工治理，Agent记忆（轨道B）需要自治演化。信任边界是两者的防火墙。

4. **检索需要从"并行池"进化为"自适应分层漏斗"**。高层摘要优先，确定性答案短路，复杂查询下沉，Disposition动态调整权重。

5. **信息更正不是删除，是版本链**。Supersedes边+双时序模型+级联传播=完整的更正可追溯性。

### 7.2 推荐实施路径

| 阶段 | 时间 | 核心任务 | 参考方案 |
|------|------|---------|---------|
| **Phase 1** | 1-2月 | 统一CognitiveNode，消除影子节点；新增opinion/memory_type；引入SUPERSEDES/CONTRADICTS边 | 本报告§1.1 |
| **Phase 2** | 2-3月 | Schema-Aware提取模板；分层漏斗检索；EvidenceExpander | 本报告§2.1 + subagent1报告§2 |
| **Phase 3** | 3-4月 | 双轨矛盾治理；BeliefRevision引擎；CorrectionPropagation | 本报告§3 |
| **Phase 4** | 4-6月 | 四正交图实验（语义/时序/因果/实体）；策略引导遍历 | 方案C |
| **Phase 5** | 6-12月 | Schema-Memory双向反馈环；自动Schema演化建议；沙箱空间 | 本报告§1.2 |

### 7.3 最关键的3个设计决策

| 优先级 | 决策 | 推荐选择 | 理由 |
|--------|------|---------|------|
| P0 | 节点模型 | **统一CognitiveNode + cognitive_layer分区** | 消除影子节点是其他一切的基础 |
| P0 | 矛盾处理 | **双轨制（企业治理+Agent自治）** | 金融场景的合规底线 |
| P1 | 检索架构 | **自适应分层漏斗 + Disposition动态权重** | 直接影响用户体验和token成本 |

---

## 参考索引

| 文档 | 路径 | 作用 |
|------|------|------|
| 初始审视报告 | `discuss/2026-04-27-agent-memory-design-analysis.md` | 7个不足+3个范式 |
| 认知交互分析 | `discuss/2026-04-27-four-layer-cognitive-interaction-analysis.md` | 层间影响机制+检索设计 |
| 本报告 | `discuss/2026-04-27-cognitive-schema-integration-deep-dive.md` | Schema融合+矛盾治理+案例辩论 |

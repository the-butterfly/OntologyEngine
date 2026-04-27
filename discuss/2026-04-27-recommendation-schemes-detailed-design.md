# 推荐方案展开设计：以供应链金融风控Agent为案例的四层认知架构实现

> **日期**: 2026-04-27 | **主题**: 将辩论中的推荐方案具体化为可执行架构
> **前置阅读**: `discuss/2026-04-27-cognitive-schema-integration-deep-dive.md`
> **[关键设计点]**: 以具体案例为引子，打开每一项推荐方案的架构设计，阐明知识库的作用与Schema的认知骨架意义

---

## 目录

1. [案例背景：供应链金融风控Agent的30天事件流](#一案例背景)
2. [方案1：混合节点架构](#二方案1混合节点架构)
3. [方案2：分层CUD策略](#三方案2分层cud策略)
4. [方案3：双轨治理](#四方案3双轨治理)
5. [方案4：Schema引导+沙箱演化](#五方案4schema引导沙箱演化)
6. [方案5：规则驱动的信念修正](#六方案5规则驱动的信念修正)
7. [方案6：读写分离的一致性模型](#七方案6读写分离的一致性模型)
8. [方案7：分层所有权](#八方案7分层所有权)
9. [Schema作为认知骨架的贯穿作用](#九schema作为认知骨架的贯穿作用)
10. [知识库的整体作用定位](#十知识库的整体作用定位)

---

## 一、案例背景

某银行使用OntologyEngine构建供应链金融风控Agent，监控核心企业（华为）及其上下游供应商的信用风险。30天内发生以下业务事件：

```
Day 1:  导入华为2024年报 -> 提取财务指标 -> 信用评分=A
Day 5:  新闻：华为某子公司涉及诉讼 -> Agent记录episode -> 触发observation更新
Day 10: 用户询问："华为风险如何？" -> Agent检索并回答
Day 15: 新导入征信报告：华为债务率从45%上升至65% -> 与Day 1的observation矛盾
Day 20: 用户更正："那起诉讼已经撤诉了" -> 需要信息更正
Day 25: Agent自动归纳：近30天3次类似"债务率上升但随后澄清"模式 -> 触发procedure提取
Day 30: 用户问："过去一个月华为风险判断为什么波动？" -> 需要时序追溯和因果解释
```

这30天的事件流覆盖了Agent记忆系统需要处理的全部核心问题：**信息摄入、知识提取、矛盾检测、信息更正、模式归纳、时序追溯**。下面的每一个推荐方案都将围绕这个案例中的具体场景展开设计。

---

## 二、方案1：混合节点架构

### 2.1 案例引子：Day 1 年报导入后的存储困境

Day 1导入华为2024年报后，系统需要同时处理多种认知层次的数据：
- **原始PDF页**（感知层）：800字符分块的fragment，需要完整保留以备审计
- **提取的财务指标**（语义层）：debt_ratio=0.45, revenue=7000亿等结构化entity
- **Agent的初步评估**（观点层）："华为财务稳健，债务率低于行业均值"
- **提取规则本身**（程序层）："从年报中提取资产负债率的方法"

当前设计的问题：这些数据被存储在两个分离的系统中——原始fragment在Layer-R（ChromaDB），提取的entity在Layer-S的EntityNode，观察在MemoryUnitNode，两者之间通过MAPPED_TO边关联。当Day 15债务率更新时，需要同步更新EntityNode、MemoryUnitNode、以及所有依赖的mental_model，维护成本极高。

### 2.2 推荐架构：两层存储 x 四层认知矩阵

不是将四层认知强行塞进一个表，也不是拆成四个独立表，而是采用"两层存储 x 四层认知"的矩阵架构：

```
存储层 ->    Layer-R（感知存储）         Layer-S（认知存储）
|
v
认知层

感知/情景     原始fragment                  episode（情景摘要）
             ChromaDB向量存储              统一CognitiveNode表
             完整文本保留                  cognitive_layer="sensory"

语义/事实     <- 不存储（引用）              entity / observation / rule
             （通过source_ids               统一CognitiveNode表
              关联到Layer-R）               cognitive_layer="semantic"

观点/信念     <- 不存储（引用）              mental_model / opinion
                                          统一CognitiveNode表
                                          cognitive_layer="opinion"

程序/技能     <- 不存储（引用）              procedure
                                          统一CognitiveNode表（或独立规则存储）
                                          cognitive_layer="procedural"
```

### 2.3 核心设计：统一CognitiveNode

用一个统一的节点表替代当前的EntityNode+MemoryUnitNode影子节点对：

```cypher
CREATE NODE TABLE CognitiveNode (
    node_id STRING PRIMARY KEY,
    space_id STRING,
    
    -- 四层认知归属
    cognitive_layer STRING,       -- "sensory" | "semantic" | "opinion" | "procedural"
    
    -- 七种子类型
    memory_type STRING,
    
    -- Schema骨架绑定：认知与Schema的映射
    schema_layer STRING,          -- "L1" | "L2" | "L3" | "L4" | null
    schema_ref STRING,            -- 如 "finance:Counterparty"
    schema_alignment_score DOUBLE, -- [0,1] 匹配度，量化记忆质量
    
    -- 内容
    text STRING,
    embedding_vector_id STRING,
    
    -- 记忆元数据
    strength DOUBLE DEFAULT 1.0,
    confidence DOUBLE DEFAULT 1.0,
    proof_count INT64 DEFAULT 1,
    access_count INT64 DEFAULT 0,
    
    -- 双时序
    valid_from STRING,
    valid_to STRING,
    recorded_at STRING,
    occurred_at STRING,
    
    -- 状态机
    status STRING DEFAULT "active",
    
    -- 扩展属性（JSON，Schema约束校验）
    attributes STRING
)
```

### 2.4 案例映射：华为事件在矩阵中的存储

以Day 1和Day 15的债务率数据为例：

**Day 1 年报导入后存储状态：**

| 存储位置 | 认知层 | memory_type | schema_layer | schema_ref | text |
|---------|--------|------------|-------------|-----------|------|
| Layer-R | sensory | fragment | null | null | "2024年年报第32页：截至2024年12月31日，华为投资控股有限公司资产负债率为45.2%..." |
| Layer-S | semantic | entity | L1 | finance:Counterparty | "华为投资控股" |
| Layer-S | semantic | observation | L3 | finance:DebtRatio | "资产负债率45.2%" |
| Layer-S | opinion | mental_model | L2 | finance:RiskView | "华为财务稳健，债务率低于行业均值" |

**Day 15 征信报告更新后的存储状态：**

新observation创建：
- cognitive_layer="semantic", memory_type="observation", schema_layer="L3", schema_ref="finance:DebtRatio"
- text="征信报告显示资产负债率65%"
- 与旧observation（45%）通过CONTRADICTS边关联

**知识库的作用**：所有关于华为的数据都存储在同一个CognitiveNode表中，通过cognitive_layer和memory_type分区。查询时不再需要JOIN两个表（EntityNode + MemoryUnitNode），也不需要维护MAPPED_TO边的同步。

**Schema的意义**：每个节点都绑定了schema_ref（如finance:Counterparty），这意味着：
1. 提取时LLM知道"应该提取什么字段"（debt_ratio, revenue, risk_grade）
2. 查询时系统知道"这个observation属于哪个entity的哪个metric"
3. 矛盾检测时系统知道"debt_ratio是数值型，可以直接比对"

---

## 三、方案2：分层CUD策略

### 3.1 案例引子：Day 15 债务率矛盾与Day 20 诉讼更正

Day 15：征信报告显示华为债务率从45%上升到65%。旧的observation（45%）应该如何处理？删除？保留？标记？

Day 20：用户告知"诉讼已撤诉"。旧的episode（"子公司涉诉"）和observation（"华为面临法律风险"）应该如何处理？

当前设计采用ADD-only：所有数据都保留，导致知识库无限膨胀，且旧数据可能干扰当前查询。

### 3.2 推荐策略：不同认知层采用不同的历史管理模式

```
认知层          历史管理策略                  理由

感知/情景层     ADD-only（永不删除）           原始碎片是审计依据，必须完整保留
               fragment/episode保留全部版本

语义/事实层     CUD + Supersedes链            entity属性需要版本控制（如债务率变更）
               旧版本标记superseded，新版本active
               通过SUPERSEDES边链接版本链

观点/信念层     CUD + 置信度更新              opinion不需要保留旧版本文本
               文本不变时只更新confidence
               文本变化时创建新版本+SUPERSEDES

程序/技能层     语义版本控制（v1->v2）         procedure需要兼容性管理
               旧版本标记deprecated
               新版本经过A/B测试后推广
```

### 3.3 案例映射：分层CUD在华为事件中的应用

**Day 15 债务率更新（语义层 CUD + Supersedes）：**

```
旧节点：obs_001（debt_ratio=45%, status=active）
    |
    v 创建SUPERSEDES边
新节点：obs_002（debt_ratio=65%, status=active）
    |
    +-- supersedence_type="updated_by_new_report"
    +-- supersedence_confidence=0.95
    +-- initiated_by="system"
    +-- review_status="auto"

旧节点状态变更：obs_001.status="superseded"
```

**查询行为变化：**
- 默认查询：只返回status="active"的节点（返回65%）
- 时序查询："华为2024年Q1的债务率？" -> 返回valid_from/Q1且status="superseded"的obs_001（45%）
- 审计查询："华为债务率变更历史？" -> 遍历SUPERSEDES链，返回完整版本序列

**Day 20 诉讼更正（语义层 CUD + 观点层置信度更新）：**

```
语义层（entity/observation）：
  obs_003（"子公司涉诉"）status="superseded"
    |
    +-- SUPERSEDES <- obs_004（"诉讼已撤诉"）status="active"

观点层（opinion）：
  op_001（"华为面临法律风险", confidence=0.8）
    |
    +-- 收到更正信息后，confidence更新为0.2
    +-- 如果confidence < 0.3 持续7天，自动标记superseded
```

**知识库的作用**：通过分层CUD，知识库不再是无限膨胀的"数据垃圾场"。每一层都有清晰的生命周期管理：感知层保真、语义层可控版本、观点层动态置信、程序层兼容演进。

**Schema的意义**：Schema定义了哪些属性属于"语义层"（需要版本控制），哪些属于"观点层"（需要置信度管理）。例如，L1 Counterparty的debt_ratio是语义层（数值精确），而L4 RuleInsight的"风险评估"是观点层（置信度动态）。

---

## 四、方案3：双轨治理

### 4.1 案例引子：Day 15 债务率矛盾的处理权归属

Day 15：征信报告显示债务率65%，与年报的45%矛盾。这个矛盾应该由系统自动处理，还是必须人工确认？

- 如果自动处理：金融风控场景中，错误的数据可能导致错误的授信决策
- 如果人工处理：Agent每天处理数千条observation，人工无法跟上

### 4.2 推荐架构：企业知识轨道 + Agent记忆轨道

```
+-------------------+        信任边界         +-------------------+
|   轨道A：企业知识   |  <----------------->  |   轨道B：Agent记忆  |
|   (Schema约束型)    |    confidence>0.9     |   (自治演化型)      |
|                    |    + alignment>0.9    |                    |
+-------------------+    = 建议晋升到轨道A    +-------------------+

轨道A（企业知识）—— 高治理、低自治
  - 内容：entity核心属性、L4 rule定义、L3 metric计算逻辑、合规要求
  - 写入：强Schema约束，不符合Schema的数据拒绝写入
  - 更新：关键变更（客户评级、授信额度）必须人工审核
  - 矛盾：生成报告，入人工审核队列
  - 查询：返回强一致性结果，附加audit trail

轨道B（Agent记忆）—— 低治理、高自治
  - 内容：observation、opinion、episode、procedure
  - 写入：弱Schema约束，允许alignment_score<0.7的记忆存入
  - 更新：自动信念修正，confidence动态演化
  - 矛盾：自动检测，按规则自动解决（低置信度标记superseded）
  - 查询：返回最终一致结果，可能附加stale_warning
```

### 4.3 案例映射：华为事件的双轨处理

**Day 1 年报导入：**
- 原始fragment -> 轨道B（Agent记忆，自动处理）
- 提取的entity（华为，debt_ratio=0.45）-> 轨道A（企业知识，Schema校验通过）
- 信用评分=A -> 轨道A（L3 metric计算结果）

**Day 15 征信报告矛盾：**
- 新observation（debt_ratio=0.65）-> 先进入轨道B
- 系统检测到与轨道A的entity属性（0.45）矛盾
- 矛盾类型：数值更新（同属性不同值）
- 处理：根据预配置规则
  ```
  规则1：若新来源confidence > 旧来源confidence x 1.5 -> 自动更新轨道A
  规则2：若影响的是L1核心属性 -> 通知管理员，但不阻塞
  ```
- 结果：debt_ratio自动更新为0.65（轨道A更新），旧值标记superseded

**Day 20 用户更正（诉讼撤诉）：**
- 用户输入 -> 轨道B（作为新的observation）
- 系统检测到与轨道A的间接矛盾（旧opinion"华为面临法律风险"基于已撤诉的诉讼）
- 处理：轨道B的opinion自动降级（confidence从0.8降至0.2）
- 轨道A不受影响（因为轨道A从未正式记录"法律风险"为entity属性）

**知识库的作用**：双轨制让知识库同时满足两个看似矛盾的目标——**企业级数据质量**（轨道A）和**Agent自治演化**（轨道B）。同一物理存储（CognitiveNode表），通过schema_layer和trust_level字段区分轨道。

**Schema的意义**：Schema定义了"哪些数据属于轨道A"。L1 EntityDeclaration和L4 RuleDefinition是轨道A的基石，任何绑定到这些Schema的节点自动受轨道A的治理规则约束。未绑定Schema或alignment_score低的节点留在轨道B自治演化。

---

## 五、方案4：Schema引导 + 沙箱演化

### 5.1 案例引子：Day 25 模式归纳与Schema演进

Day 25：Agent发现近30天出现3次"债务率上升新闻 -> 后续澄清"的模式，建议提取为procedure。

但当前的Schema v2中并没有"债务率新闻模式"这种procedure类型。如果强行要求Schema预定义所有可能的procedure，Agent的创新能力将被扼杀。如果完全无Schema约束，知识库将陷入混乱。

### 5.2 推荐架构：生产空间 + 沙箱空间 + 晋升机制

```
+-------------------+     晋升条件      +-------------------+
|   沙箱空间         |  ------------->  |   生产空间         |
|   (Sandbox Space)  |  alignment>0.9   |   (Production)    |
|                    |  proof_count>10  |                   |
|   - 弱Schema约束    |  人工review通过  |   - 强Schema约束   |
|   - Agent自由实验   |                  |   - 仅允许符合     |
|   - 新类型探索      |                  |     Schema的记忆   |
|   - 失败容忍       |                  |   - 影响企业决策   |
+-------------------+                  +-------------------+

沙箱空间的设计：
  - schema_layer 可为 "sandbox" 或 null
  - 不触发轨道A的严格审核
  - 允许alignment_score < 0.7的记忆存在
  - 周期性扫描（梦境循环）评估是否有晋升候选

生产空间的设计：
  - schema_layer 必须为 "L1" | "L2" | "L3" | "L4"
  - 写入时Schema约束校验
  - 变更时AnalyzeImpact遍历下游依赖
  - 查询时返回强一致性结果
```

### 5.3 案例映射：华为事件的沙箱到生产晋升

**Day 5-20 的多次"债务率上升->澄清"模式：**

```
阶段1：沙箱积累（Day 5-20）
  - 每次债务率新闻产生一个episode（沙箱，cognitive_layer="sensory"）
  - 每次澄清产生另一个episode（沙箱）
  - Agent自动标记这两个episode的关联（"后续澄清"关系）

阶段2：模式检测（Day 25）
  - PatternDetector扫描沙箱：
    "同主题（债务率+澄清）episode >= 3次"
  - 生成PatternReport：
    pattern_name="debt_rate_news_then_clarification"
    frequency=3
    confidence=0.67（2次确实澄清，1次待观察）

阶段3：晋升建议（Day 25）
  - 系统生成SchemaProposal：
    建议新增L4 RuleLogic："当收到债务率上升新闻时，
                           先标记observation，
                           等待72小时观察是否有澄清，
                           再更新risk_grade"
  - 入ReviewQueue，通知领域专家

阶段4：人工审核（Day 26-30）
  - 领域专家审核："同意，但72小时应调整为5个工作日"
  - 修改后审批通过
  - procedure从沙箱晋升到生产空间
  - schema_layer从"sandbox"变为"L4"
  - 绑定到Schema：finance:DebtRateNewsProcedure
```

**知识库的作用**：沙箱空间是Agent的"实验室"，允许试错和创新。生产空间是"正式环境"，确保数据质量和一致性。两者的分离避免了"实验数据污染生产数据"的风险。

**Schema的意义**：Schema是沙箱到生产的"验收标准"。一个记忆要从沙箱晋升到生产，必须满足：
1. 能够绑定到现有Schema（或新Schema已通过审批）
2. alignment_score > 0.9（证明它与领域模型高度匹配）
3. proof_count > 10（证明它有足够的证据支撑）

Schema不是创新的阻碍，而是创新的" graduation ceremony"（毕业典礼）。

---

## 六、方案5：规则驱动的信念修正

### 6.1 案例引子：Day 15 债务率矛盾与Day 20 诉讼更正的自动处理

Day 15：新征信报告（debt_ratio=65%）与旧年报（45%）矛盾。如何处理？

Day 20：用户更正（诉讼撤诉）与旧episode（涉诉）矛盾。如何处理？

两个矛盾的性质不同：前者是"数值更新"（新版本替代旧版本），后者是"事实反转"（新证据否定旧结论）。不能用同一套规则处理。

### 6.2 推荐架构：可配置的信念修正规则引擎

不追求完整的AGM形式化框架（过于复杂），也不完全依赖启发式（无法保证一致性），而是定义一组**可审计、可调整**的信念修正规则：

```
规则类别1：数值更新规则（自动处理）
  条件：contradiction.type == "attribute_mismatch"
        AND new_source.confidence > old_source.confidence * 1.5
        AND attribute_type == "numeric"
  动作：自动创建SUPERSEDES边（新->旧）
        旧节点status="superseded"
        新节点status="active"
  通知：仅记录admin_log

规则类别2：时序版本规则（自动处理）
  条件：contradiction.type == "attribute_mismatch"
        AND new_source.recorded_at > old_source.recorded_at
        AND new_source.source_type == "official_report"
  动作：自动supersede旧版本
        附加note="updated_by_newer_official_report"
  通知：space_admin（异步通知，不阻塞）

规则类别3：事实反转规则（标记待审核）
  条件：contradiction.type == "factual_reversal"
        OR new_evidence.directly_contradicts(old_conclusion)
  动作：创建CONTRADICTS边
        旧节点status不变，附加"pending_review"标记
        新节点status="active"
  通知：管理员必须审核

规则类别4：观点分歧规则（保留多视角）
  条件：contradiction.type == "opinion_divergence"
  动作：不创建SUPERSEDES边
        创建MULTI_VIEW_OF边连接两个opinion
        分别标注source_analyst
  通知：无

规则类别5：核心资产保护规则（人工审核）
  条件：affected_nodes.any { it.schema_layer == "L4" }
        OR affected_nodes.any { it.memory_type == "rule" }
  动作：阻塞自动处理
        强制入人工审核队列
  通知：architect + 合规团队
```

### 6.3 案例映射：华为事件的规则驱动处理

**Day 15 债务率矛盾：**

```
矛盾检测：
  旧：obs_001（debt_ratio=45%, source="年报", confidence=0.9）
  新：obs_002（debt_ratio=65%, source="征信报告", confidence=0.95）

规则匹配：
  -> 匹配规则类别1（数值更新）：
     0.95 > 0.9 * 1.5 ? 否（0.95 < 1.35）
  -> 匹配规则类别2（时序版本）：
     征信报告(recorded_at=Day15) > 年报(recorded_at=Day1) ? 是
     且source_type="official_report" ? 是
     -> 触发自动supersede

处理结果：
  obs_001.status="superseded"
  obs_002.status="active"
  SUPERSEDES边：obs_002 -> obs_001
  note="updated_by_newer_official_report: 征信报告Day15"
  通知：space_admin（异步邮件）

下游影响：
  - mental_model（"华为财务稳健"）标记为stale
  - L3 metric（credit_score）入刷新队列
```

**Day 20 诉讼更正：**

```
矛盾检测：
  旧：episode_001（"子公司涉诉", source="新闻", confidence=0.7）
  新：obs_005（"诉讼已撤诉", source="用户更正", confidence=0.9）

规则匹配：
  -> 匹配规则类别3（事实反转）：
     "撤诉" directly_contradicts "涉诉" ? 是
     -> 标记待审核，不自动supersede

处理结果：
  episode_001.status="active"（保持不变）
  episode_001附加标记"pending_review: contradicted_by_obs_005"
  obs_005.status="active"
  CONTRADICTS边：obs_005 -> episode_001
  通知：管理员必须审核

管理员审核（Day 21）：
  - 确认诉讼确实已撤诉
  - 批准：episode_001.status="superseded"
  - 批准：opinion_001（"法律风险"）confidence降至0.2
  - 触发下游：mental_model刷新
```

**知识库的作用**：规则引擎让知识库具备了"自治判断力"——不是盲目接受所有新信息，也不是盲目拒绝矛盾，而是根据矛盾的**性质**（数值/时序/事实/观点/核心资产）采取不同的处理策略。

**Schema的意义**：Schema定义了"哪些属性属于核心资产"（受规则类别5保护），"哪些属性是数值型"（适用规则类别1），"哪些节点是观点型"（适用规则类别4）。没有Schema，规则引擎无法判断矛盾的严重程度。

---

## 七、方案6：读写分离的一致性模型

### 7.1 案例引子：Day 15 债务率更新后的查询一致性

Day 15 14:00：新征信报告导入，debt_ratio更新为65%。此时级联更新尚未完成（mental_model未刷新，L3 metric未重算）。

Day 15 14:05：用户查询"华为风险如何？"

当前设计的问题：查询可能返回不一致的结果——entity显示debt_ratio=65%，但mental_model仍然说"财务稳健"（基于旧的45%）。

### 7.2 推荐架构：读写分离的一致性级别

```
写入路径（Write Path）：最终一致，快速响应
  Step 1: 新observation写入CognitiveNode（同步，<100ms）
  Step 2: 矛盾检测 + 规则引擎处理（异步，1-5s）
  Step 3: 标记受影响的mental_model为stale（异步，1-5s）
  Step 4: 入CascadeUpdate队列，等待后台刷新（异步，5-30s）

读取路径（Read Path）：可配置一致性级别
  Level 1 - eventual（默认）：
    - 直接查询当前状态
    - 如果返回的节点有stale标记，附加stale_warning
    - 延迟最低，适合实时交互

  Level 2 - strong：
    - 检查查询涉及的所有节点是否有stale依赖
    - 如果有，触发同步刷新（等待CascadeUpdate完成）
    - 延迟较高（可能数秒），适合关键决策

  Level 3 - raw：
    - 直接查询，不做任何一致性检查
    - 用于调试和审计
```

### 7.3 案例映射：华为事件中的一致性处理

**Day 15 14:00 债务率更新后：**

```
写入流程：
  T+0s:   obs_002写入（debt_ratio=65%）
  T+1s:   规则引擎触发，obs_001标记superseded
  T+2s:   AnalyzeImpact发现受影响的mental_model_001
  T+3s:   mental_model_001.status="stale"
          mental_model_001.attributes["stale_reason"]="upstream_debt_ratio_updated"
  T+5s:   credit_score（L3 metric）入刷新队列
  T+30s:  CascadeUpdateEngine刷新mental_model_001
          刷新credit_score（从A降至B）
```

**Day 15 14:05 用户查询"华为风险如何？"：**

```
默认查询（eventual一致性）：
  返回：
    - entity: 华为, debt_ratio=65%（已更新）
    - mental_model: "华为财务稳健"（stale标记，基于旧数据）
    - credit_score: A（尚未刷新）
  附加：stale_warning="mental_model和credit_score基于旧数据，正在刷新中"

强一致性查询（用户要求"确保最新"）：
  系统检测到mental_model_001.status="stale"
  触发同步刷新（等待CascadeUpdate）
  返回：
    - entity: 华为, debt_ratio=65%
    - mental_model: "华为债务率上升，需关注"（已刷新）
    - credit_score: B（已重算）
  延迟：+3秒
```

**知识库的作用**：读写分离让知识库在"写入性能"和"读取一致性"之间取得平衡。Agent场景需要快速写入（用户不等待），但某些查询需要强一致性（关键决策）。

**Schema的意义**：Schema定义了"哪些节点的变更需要触发强一致性刷新"。L1 entity核心属性的变更会自动标记所有依赖的L3 metric和L2 dimension_view为stale。没有Schema的依赖关系图，系统不知道"debt_ratio变更影响了哪些下游节点"。

---

## 八、方案7：分层所有权

### 8.1 案例引子：谁拥有Agent的记忆？

Day 10：用户查询"华为风险如何？"，Agent基于用户的历史查询偏好（用户更关注法律风险而非财务指标）调整了回答重点。这些偏好数据属于用户还是银行？

Day 25：Agent从多个用户的交互中学习到"债务率上升+澄清"的行业模式。这种模式属于单个用户、银行、还是Agent自身？

### 8.2 推荐架构：三层所有权模型

```
+-------------------+  +-------------------+  +-------------------+
|   用户私有层       |  |   企业共享层       |  |   系统自治层       |
|   User Private    |  |   Enterprise      |  |   System          |
|                   |  |   Shared          |  |   Autonomous      |
+-------------------+  +-------------------+  +-------------------+

用户私有层：
  - 内容：用户个人偏好、历史交互、个人标注
  - 示例："用户A更关注法律风险"、"用户A偏好简明回答"
  - 权限：用户完全控制（查看、修改、删除）
  - 隔离：其他用户不可见
  - 生命周期：随用户账户存在

企业共享层：
  - 内容：去标识化的行业模式、通用规则模板、经审批的Schema定义
  - 示例："供应链金融风控通用指标"、"Counterparty标准评估模型"
  - 权限：企业所有，用户仅有使用权
  - 隔离：所有用户可见，但不可修改
  - 生命周期：永久保留，版本管理

系统自治层：
  - 内容：Agent自生但未经验证的记忆（observation、opinion、沙箱中的实验数据）
  - 示例："债务率上升+澄清模式"（尚未通过人工审核）
  - 权限：Agent自治，用户可review但不可直接修改
  - 隔离：仅对Agent可见，用户通过dashboard查看
  - 生命周期：满足条件后晋升到企业共享层，或被淘汰
```

### 8.3 案例映射：华为事件的所有权归属

**Day 1 年报导入：**
- 原始年报PDF -> 企业共享层（银行购买的公开数据）
- 提取的entity（华为，debt_ratio=0.45）-> 企业共享层（所有风控Agent共享）

**Day 10 用户查询：**
- 用户A的查询记录"华为风险如何？" -> 用户私有层
- 用户A的偏好"更关注法律风险" -> 用户私有层
- Agent的回答"华为风险等级A" -> 企业共享层（基于共享entity和rule计算）

**Day 25 模式归纳：**
- 检测到的模式"债务率上升+澄清" -> 系统自治层（初始）
- 经人工审核后升级为procedure -> 企业共享层
- 用户A在此模式中的具体交互记录 -> 用户私有层

**知识库的作用**：分层所有权让同一知识库服务于多个利益相关方（用户、企业、Agent），而不会产生数据归属冲突。用户获得个性化体验，企业保护核心资产，Agent获得自治空间。

**Schema的意义**：Schema定义了"哪些数据属于企业共享层"。L1-L4的Schema定义本身就是企业共享层的核心内容。任何绑定到企业Schema的节点自动归企业所有。未绑定Schema的节点默认属于系统自治层，等待审批后可能晋升到企业共享层。

---

## 九、Schema作为认知骨架的贯穿作用

以上7个方案看似独立，但**Schema是贯穿所有方案的隐线**。Schema在OntologyEngine中不是简单的"数据校验规则"，而是**认知骨架**——它定义了知识的骨骼结构，四层认知则是血肉填充。

### Schema在7个方案中的具体作用

| 方案 | Schema的作用 |
|------|-------------|
| **混合节点架构** | schema_ref将CognitiveNode绑定到L1-L4定义，消除影子节点；schema_alignment_score量化记忆质量 |
| **分层CUD策略** | Schema定义了哪些属性属于语义层（需要版本控制），哪些属于观点层（需要置信度管理） |
| **双轨治理** | Schema定义了轨道A的边界——L1/L3/L4绑定的节点受企业治理约束 |
| **沙箱演化** | Schema是沙箱到生产的"验收标准"——alignment_score>0.9才能绑定到生产Schema |
| **规则驱动信念修正** | Schema定义了核心资产（受保护）vs 普通属性（可自动更新）的区分 |
| **读写分离一致性** | Schema的依赖关系图（L1->L3->L4）决定了哪些节点需要在写入后标记stale |
| **分层所有权** | Schema定义本身就是企业共享层的核心资产，绑定到Schema的节点归企业所有 |

### Schema-记忆双向反馈环

```
Schema（L1-L4定义）          记忆（CognitiveNode）
      |                              |
      |  1. 事前引导                  |  2. 提取结果
      |  （提取模板）                  |  （alignment_score）
      v                              v
+-----------+                   +-----------+
| 提取时：   |                   | 积累后：   |
| LLM根据   |                   | PatternDetector|
| Schema属性 |                   | 统计高频模式  |
| 定义生成   |                   |             |
| 提取模板   |                   |             |
+-----------+                   +-----------+
      |                              |
      |  4. 更新Schema                |  3. 建议扩展
      |  （人工审批后）                |  （SchemaProposal）
      v                              v
+-----------+                   +-----------+
| Schema    | <---------------- | 自动建议   |
| Evolution |    反馈环闭环     | 新增属性/  |
|           |                   | metric/   |
|           |                   | rule_logic|
+-----------+                   +-----------+
```

**Schema不是静态的**：当Agent在沙箱中反复提取到某个Schema未定义的属性（如"ESG评分"），且proof_count>100、alignment_score>0.8时，系统应自动生成SchemaProposal："建议L1 Counterparty新增属性esg_score"。经知识管理员审批后，Schema演进，所有存量记忆的schema_alignment_score重新计算。

---

## 十、知识库的整体作用定位

经过以上7个方案的展开设计，OntologyEngine作为Agent记忆系统的整体定位可以概括为：

```
+------------------+
|   OntologyEngine  |
|   （Agent记忆系统） |
+------------------+
        |
        +---> 知识编译器（Write-time）
        |       - 原始文档 -> 结构化知识（ConsolidationPipeline）
        |       - Schema引导的提取（SchemaAwareExtraction）
        |       - 分层编译产物（L0->L1->L2->L3->L4）
        |
        +---> 记忆操作系统（Run-time）
        |       - 双轨治理（轨道A+轨道B）
        |       - 自动维护（梦境循环+级联更新）
        |       - 信念修正（规则引擎+置信度传播）
        |
        +---> 认知检索引擎（Query-time）
                - 自适应分层漏斗（mental_model优先）
                - 可配置一致性（eventual/strong/raw）
                - 证据链展开（EvidenceExpander）
```

### 知识库解决的6个核心问题

| 核心问题 | 传统RAG的局限 | OntologyEngine的解决方式 |
|---------|-------------|------------------------|
| **知识如何沉淀？** | 每次查询重新检索，无积累 | ConsolidationPipeline将碎片编译为分层知识 |
| **矛盾如何处理？** | 无矛盾检测，或简单去重 | 规则引擎根据矛盾性质自动/半自动处理 |
| **信息如何更正？** | ADD-only，旧数据干扰查询 | SUPERSEDES链+双时序模型，更正完全可追溯 |
| **时序如何追溯？** | 无版本历史，只能回答"现在如何" | 完整的valid_from/valid_to+recorded_at时间线 |
| **经验如何复用？** | 无procedure/skills概念 | ProcedureExtractionEngine从episode抽象技能 |
| **质量如何保障？** | 依赖文档质量，无治理机制 | Schema约束+双轨治理+沙箱晋升+自动化维护 |

### Schema的终极意义

Schema v2（L1-L4）不是OntologyEngine的附加功能，而是**认知骨架**。没有Schema，记忆系统只是"高级搜索引擎"；有了Schema，记忆系统才能：

1. **理解知识的结构**：知道"debt_ratio是Counterparty的数值属性，risk_grade是L4规则推导的枚举值"
2. **引导知识的提取**：LLM提取时不再盲目猜测，而是按照Schema模板精确提取
3. **约束知识的质量**：不符合Schema的observation自动降级，alignment_score量化记忆可信度
4. **驱动知识的演化**：Schema本身可以基于记忆积累自动建议扩展，形成Schema-记忆双向反馈环
5. **保障知识的治理**：Schema定义了企业核心资产的边界，是双轨治理和分层所有权的基石

---

## 参考索引

| 文档 | 路径 | 作用 |
|------|------|------|
| 原始辩论报告 | `discuss/2026-04-27-cognitive-schema-integration-deep-dive.md` | 7个推荐方案的辩论原型 |
| 本展开设计 | `discuss/2026-04-27-recommendation-schemes-detailed-design.md` | 推荐方案的具体架构与案例映射 |
| GBrain/LLM-Wiki审视 | `discuss/2026-04-27-key-decision-review-gbrain-llmwiki.md` | 编译型记忆与记忆OS视角 |

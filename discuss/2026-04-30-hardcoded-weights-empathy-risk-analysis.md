# 硬编码权重/阈值审查与 empathy/risk_tolerance 角色分析

> **日期**: 2026-04-30 | **审查范围**: 全部02-design + overview文档
> **定位**: 过程文档——硬编码值合理性分析 + empathy/risk_tolerance深度审视

---

## 一、硬编码值全景

### 1.1 统计

| 类别 | 数量 | 说明 |
|------|------|------|
| WEIGHT | ~45 | 权重/提升因子（类型权重、RRF权重、边权重、boost乘数） |
| THRESHOLD | ~50 | 比较边界（strength阈值、confidence阈值、Disposition触发阈值） |
| DEFAULT | ~25 | 字段默认值（DDL DEFAULT、API默认参数） |
| MAGIC_NUMBER | ~20 | 无明确推导的常量（迭代次数、深度限制、时间窗口） |
| SAFETY_BOUNDARY | 7 | DispositionProfile 7维度的[min, max]安全范围 |
| COST_LIMIT | 3 | Token消耗/预算限制 |
| SCENE_OVERRIDE | 4 | 场景强制覆盖值 |

### 1.2 核心问题

| # | 问题 | 严重程度 | 典型案例 |
|---|------|---------|---------|
| 1 | **重复定义**：同一阈值在3个文档中重复出现，无单一事实源 | 🔴高 | strength遗忘阈值(0.3/0.2/0.1/0.01)在3处重复 |
| 2 | **阈值不一致**：同一概念在不同文档中阈值不同 | 🔴高 | abstraction_preference触发阈值：memory-hierarchy用>0.7，10-kb-process用>0.8 |
| 3 | **权重体系分散**：缺乏统一的权重注册表 | 🟡中 | 类型权重在memory-hierarchy，RRF权重在query-routing，alignment权重在10-kb-process |
| 4 | **魔术数字无推导**：大量数值缺乏设计决策说明 | 🟡中 | 遗忘率0.1/0.4/0.85、衰减系数0.1、级联深度3 |
| 5 | **DDL默认值与YAML模型重复**：漂移风险 | 🟢低 | CognitiveNode默认值在YAML和DDL各写一遍 |

---

## 二、硬编码值合理性分类

### 2.1 应该保持硬编码（不变）

| 值 | 原因 | 位置 |
|----|------|------|
| DDL DEFAULT值（1.0, 0.5, 0等） | 数据库初始化默认值，变更需ALTER TABLE，不适合运行时配置 | kuzudb-schema.md |
| API默认参数（max_results=10等） | API接口默认值，变更影响所有调用方，需版本化 | memory-api.md |
| 安全边界[0.3,0.9]等 | 防止配置错误导致系统崩溃，属于硬约束 | memory-hierarchy.md |

### 2.2 应该提取为可配置（当前硬编码不合理）

| 值 | 当前位置 | 应提取为 | 原因 |
|----|---------|---------|------|
| **BASE_TYPE_WEIGHTS** (8个值) | memory-hierarchy.md | `SpaceConfig.type_weights` | 不同行业/场景的类型权重差异大 |
| **RRF权重** (15个值) | query-routing.md | `RetrievalConfig.rrf_weights` | 不同查询类型的RRF权重需要调优 |
| **边权重** (CAUSAL×2.0, TEMPORAL×3.0等) | query-routing.md | `RetrievalConfig.edge_weights` | 不同领域的边重要性不同 |
| **遗忘阈值** (0.3/0.2/0.1/0.01) | 3处重复 | `LifecycleConfig.forget_thresholds` | 不同场景的遗忘策略不同 |
| **自动晋升条件** (confidence>0.9, proof≥3) | 2处重复 | `GovernanceConfig.auto_promote` | 不同组织的治理策略不同 |
| **级联限制** (MAX_CASCADE=100, DEPTH=3) | memory-lifecycle.md | `GovernanceConfig.cascade_limits` | 大规模知识库需要更高限制 |
| **编译成本预算** (5M tokens/天) | memory-lifecycle.md | `CostConfig.daily_token_budget` | 不同预算需要不同限制 |
| **梦境循环采样窗口** (7天/1天) | memory-lifecycle.md | `MaintenanceConfig.dream_cycle` | 不同规模知识库需要不同采样策略 |

### 2.3 需要建立单一事实源的重复值

| 值 | 重复位置 | 建议单一事实源 |
|----|---------|---------------|
| strength遗忘阈值 | memory-hierarchy, memory-lifecycle, 10-kb-process | memory-lifecycle.md |
| feedback_weight保护阈值(0.9) | 同上 | memory-lifecycle.md |
| 自动晋升条件 | ingestion-service, temporal-modeling | ingestion-service.md |
| Disposition触发阈值 | memory-hierarchy, query-routing, 10-kb-process | memory-hierarchy.md |

---

## 三、empathy 和 risk_tolerance 深度审视

### 3.1 当前设计的问题

当前文档声明"empathy和risk_tolerance不影响检索，只影响Agent交互风格"。这个声明存在两个问题：

**问题1：如果两个维度不影响检索，为什么放在DispositionProfile中？**

DispositionProfile的定义是"驱动分层漏斗的动态权重和短路策略"。如果empathy和risk_tolerance不驱动任何检索行为，它们在DispositionProfile中就是"死参数"——存在但不生效，增加认知负担和配置复杂度。

**问题2："影响Agent交互风格"过于模糊，缺乏可操作定义**

"交互风格"可以有很多理解：
- 影响LLM的system prompt？
- 影响返回结果的措辞？
- 影响是否主动提出风险警告？
- 影响对不确定信息的处理策略？

如果不明确，实现时必然产生分歧。

### 3.2 empathy 的真实作用场景

| 场景 | 低empathy(0.2) | 高empathy(0.8) | 影响环节 |
|------|---------------|---------------|---------|
| **用户表达负面情绪** | "根据数据分析，风险等级为C" | "我理解您对风险的担忧。根据当前数据，风险等级为C，但我们可以一起看看缓解措施" | **回答生成**（LLM system prompt注入） |
| **用户提问模糊** | 严格按字面理解，返回最相关结果 | 推断用户意图，返回更广泛的结果 | **查询扩展**（recall时query重写） |
| **矛盾信息处理** | 直接报告矛盾，让用户决定 | 主动解释矛盾的可能原因，提供上下文 | **矛盾报告**（CONTRADICTS边描述生成） |
| **无结果场景** | "未找到相关信息" | "抱歉没有找到完全匹配的信息，以下是一些可能相关的内容" | **降级策略**（触发降级时的fallback回答） |

**结论**：empathy确实不直接影响检索权重，但它影响**检索后的回答生成策略**。这不是"死参数"，而是**检索-生成分界线**上的参数。

### 3.3 risk_tolerance 的真实作用场景

| 场景 | 低risk_tolerance(0.2) | 高risk_tolerance(0.8) | 影响环节 |
|------|----------------------|----------------------|---------|
| **不确定信息** | "该信息置信度仅0.6，建议进一步验证" | "根据现有信息，初步判断为..." | **置信度过滤**（recall时min_confidence动态调整） |
| **矛盾未解决** | "存在矛盾信息，无法给出确定结论" | "虽然存在矛盾，但更可能的情况是..." | **矛盾回答策略**（CONTRADICTS边的回答生成） |
| **自动晋升** | 严格条件：confidence>0.9 + proof≥3 | 宽松条件：confidence>0.7 + proof≥2 | **治理策略**（自动晋升条件动态调整） |
| **Agent决策** | 保守：需要更多证据才行动 | 积极：基于有限信息即可行动 | **Agent行为**（reflect时的决策阈值） |

**结论**：risk_tolerance不仅影响交互风格，还影响**置信度过滤和治理策略**。它实际上应该影响检索的min_confidence阈值。

### 3.4 修正方案

#### empathy：检索后回答生成参数

```python
def apply_empathy_to_response(query, results, disposition):
    if disposition.empathy > 0.7:
        system_prompt_addition = (
            "用户可能对结果有情绪反应。"
            "请在回答中加入共情表达，"
            "对负面结果提供缓解建议，"
            "对模糊查询主动推断意图。"
        )
        if not results:
            fallback = "抱歉没有找到完全匹配的信息，以下是一些可能相关的内容"
    elif disposition.empathy < 0.3:
        system_prompt_addition = "请简洁客观地呈现事实，不加情感修饰。"
    
    return system_prompt_addition
```

#### risk_tolerance：影响检索阈值+治理策略

```python
def apply_risk_tolerance_to_retrieval(disposition):
    min_confidence = 0.5
    if disposition.risk_tolerance < 0.3:
        min_confidence = 0.8
    elif disposition.risk_tolerance > 0.7:
        min_confidence = 0.3
    
    auto_promote_confidence = 0.9
    if disposition.risk_tolerance > 0.7:
        auto_promote_confidence = 0.7
    
    return RetrievalAdjustment(
        min_confidence=min_confidence,
        auto_promote_confidence=auto_promote_confidence,
        contradiction_strategy="cautious" if disposition.risk_tolerance < 0.3 else "pragmatic"
    )
```

### 3.5 修正后的7维度对检索消费的影响

| 维度 | 影响的检索环节 | 具体影响 |
|------|---------------|---------|
| skepticism | 矛盾检测+权重 | 高→降低mental_model权重，增加entity权重 |
| evidence_demand | 短路策略+证据展开 | 高→禁止短路，要求全层检索+证据链展开 |
| abstraction_preference | 分层漏斗权重 | 高→mental_model×1.5, fragment×0.5 |
| thoroughness | 检索深度+结果数量 | 高→增加top_k，遍历更多层 |
| recency_bias | 时序排序 | 高→优先返回recorded_at最近的结果 |
| **empathy** | **回答生成策略** | **高→共情表达+模糊查询推断+降级时提供替代** |
| **risk_tolerance** | **置信度过滤+治理策略** | **低→min_confidence=0.8+严格晋升；高→min_confidence=0.3+宽松晋升** |

---

## 四、硬编码值治理建议

### 4.1 建立参数注册表

在 `docs/02-design/` 下新增 `parameter-registry.md`，作为所有可配置参数的单一事实源：

```yaml
ParameterRegistry:
  retrieval:
    type_weights:
      source: memory-hierarchy.md
      values: {mental_model: 3.0, opinion: 2.5, entity: 2.0, ...}
      configurable: true
      scope: space
    
    rrf_weights:
      source: query-routing.md
      configurable: true
      scope: space
    
    edge_weights:
      source: query-routing.md
      configurable: true
      scope: space
  
  lifecycle:
    forget_thresholds:
      source: memory-lifecycle.md
      values: {soft_decay: 0.3, type_demotion: 0.2, archive: 0.1, hard_delete: 0.01}
      configurable: true
      scope: space
    
    auto_promote:
      source: ingestion-service.md
      values: {min_confidence: 0.9, min_proof_count: 3, max_skepticism: 0.7}
      configurable: true
      scope: space
  
  governance:
    cascade_limits:
      source: memory-lifecycle.md
      values: {max_nodes: 100, max_depth: 3}
      configurable: true
      scope: space
    
    daily_token_budget:
      source: memory-lifecycle.md
      value: 5000000
      configurable: true
      scope: space
```

### 4.2 重复值单一事实源标注

| 值 | 单一事实源 | 其他文档引用方式 |
|----|-----------|----------------|
| strength遗忘阈值 | memory-lifecycle.md | "见memory-lifecycle §5 遗忘阈值" |
| feedback_weight保护 | memory-lifecycle.md | "见memory-lifecycle §5 保护条件" |
| 自动晋升条件 | ingestion-service.md | "见ingestion-service §双轨治理" |
| Disposition触发阈值 | memory-hierarchy.md | "见memory-hierarchy §4.3" |

### 4.3 阈值不一致修复

| 阈值 | memory-hierarchy | 10-kb-process | 统一为 |
|------|-----------------|---------------|--------|
| abstraction_preference触发 | >0.7 | >0.8 | **>0.7**（更敏感，更早触发动态权重） |
| evidence_demand触发 | >0.8 | >0.8 | **>0.8**（一致，无需修改） |
| skepticism触发 | >0.7 | >0.7 | **>0.7**（一致，无需修改） |

---

## 五、典型案例：empathy/risk_tolerance如何影响Agent行为

### 案例1：金融风控Agent

```
DispositionProfile:
  skepticism: 0.7        # 金融场景需要高怀疑
  evidence_demand: 0.8   # 需要充分证据
  abstraction_preference: 0.5  # 平衡
  thoroughness: 0.7      # 需要彻底搜索
  recency_bias: 0.6      # 适度时效偏好
  empathy: 0.3           # 低共情——客观呈现事实
  risk_tolerance: 0.2    # 低风险容忍——严格置信度过滤

效果：
  recall → min_confidence=0.8（只返回高置信度结果）
  矛盾回答 → "存在矛盾信息，无法给出确定结论"
  自动晋升 → 严格条件（confidence>0.9 + proof≥3）
  回答风格 → "根据数据分析，风险等级为C"
```

### 案例2：客服Agent

```
DispositionProfile:
  skepticism: 0.4        # 客服场景不需要高怀疑
  evidence_demand: 0.4   # 不需要严格证据
  abstraction_preference: 0.6  # 偏好摘要
  thoroughness: 0.4      # 不需要彻底搜索
  recency_bias: 0.7      # 优先最新信息
  empathy: 0.8           # 高共情——友好表达
  risk_tolerance: 0.6    # 中等风险容忍

效果：
  recall → min_confidence=0.4（返回更多可能相关的结果）
  矛盾回答 → "虽然信息有些不一致，但最可能的情况是..."
  自动晋升 → 宽松条件（confidence>0.7 + proof≥2）
  回答风格 → "我理解您的困扰，让我帮您查看一下..."
```

### 案例3：审计Agent

```
DispositionProfile:
  skepticism: 0.9        # 审计需要最高怀疑
  evidence_demand: 1.0   # 强制全层检索
  abstraction_preference: 0.3  # 需要底层细节
  thoroughness: 0.8      # 彻底搜索
  recency_bias: 0.5      # 平衡时效
  empathy: 0.2           # 极低共情——纯事实
  risk_tolerance: 0.1    # 极低风险容忍

效果：
  recall → min_confidence=0.9（只返回最高置信度结果）
  矛盾回答 → "发现矛盾：[详细列出]，需要进一步核实"
  自动晋升 → 禁止自动晋升，所有晋升需人工审批
  回答风格 → "审计发现：[事实列表]"
```

# 知识库构建-管理-消费流程与关键决策

> **status**: draft | **phase**: phase2 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-28
> **[关键设计点]**: 本文档定义OntologyEngine知识库的全生命周期流程——从原始数据摄入到Agent消费的全链路，以及流程中的关键架构决策点
> **[待扩展]**: 部分流程细节待与代码逐项核验
> **[待核对代码]**: 编译层、梦境循环、双轨治理等模块尚未与当前代码完全对齐

---

## 目录

1. [核心命题：知识库不是存储，是编译-治理-消费的闭环](#一核心命题)
2. [构建流程（Build）](#二构建流程build)
3. [管理流程（Govern）](#三管理流程govern)
4. [消费流程（Consume）](#四消费流程consume)
5. [典型案例：供应链金融风控Agent的30天事件流](#五典型案例)
6. [关键决策点讨论](#六关键决策点讨论)
7. [当前设计与愿景的GAP分析](#七当前设计与愿景的gap分析)
8. [推荐演进路径](#八推荐演进路径)
9. [外部批判视角：lencx 框架对照](#九外部批判视角lencx-框架对照)

---

## 一、核心命题

### 1.1 知识库的本质重新定义

OntologyEngine的愿景是"把企业里分散、异构、持续变化的知识，变成可被Agent稳定消费的'事实+逻辑'执行环境"。这意味着知识库不是**文档仓库**，不是**向量数据库**，也不是**静态知识图谱**——而是一个**持续运行的认知基础设施**。

```
传统知识管理视角：           OntologyEngine视角：
原始文档 -> 存储 -> 检索      原始数据 -> 编译 -> 治理 -> 消费 -> 反馈 -> 再编译
   (被动)                       (主动、闭环、自我演化)
```

### 1.2 三层流程总览

```
+------------------+     +------------------+     +------------------+
|   构建 (Build)    | --> |   管理 (Govern)   | --> |   消费 (Consume)  |
+------------------+     +------------------+     +------------------+
| 原始数据摄入       |     | 矛盾检测与治理     |     | 检索策略编排       |
| 知识编译          |     | 生命周期管理       |     | 推理与执行         |
| Schema对齐        |     | 自动化维护         |     | 证据链组装         |
| 质量评分          |     | 版本控制与更正     |     | 一致性级别选择     |
+------------------+     +------------------+     +------------------+
         ^                                               |
         |                                               v
         +----------------- 反馈闭环 ---------------------+
```

### 1.3 与现有概念的对齐

| 本文档流程 | 对应01-vision概念 | 对应09-agent-memory概念 | 状态 |
|-----------|------------------|----------------------|------|
| 构建 | L1知识编译层 | remember + consolidation | 基本对齐 |
| 管理 | L2知识表示层 + 质量检测 | reflect + forgetting | 部分GAP |
| 消费 | L3推理执行层 | recall | 部分GAP |
| 反馈闭环 | L4Agent协同层 | reflect结果驱动 | 待实现 |

### 1.4 四建模对象与认知层的正交矩阵 [新增]

> 受外部批判框架（lencx, 2026）启发，记忆系统需同时维护四个建模对象。它们与四层认知（Perception/Semantic/Opinion/Procedure）形成正交维度：

```
              感知层(L0)   语义层(L1)   观点层(L2)   程序层(L3)
User Model    [偏好碎片]   [用户画像]   [风险容忍]   [沟通习惯]
Task Model    [交互记录]   [任务实体]   [方案评价]   [承诺状态]
World Model   [环境观测]   [Schema实例] [组织规则]   [API约束]
Self Model    [工具日志]   [失败路径]   [能力评估]   [调用模式]
```

**关键洞察**：当前 OntologyEngine 设计覆盖了 World Model（Schema L1-L4）和部分的 User Model（DispositionProfile），但 **Task Model**（承诺、artifact 版本、方案否决历史）和 **Self Model**（Agent 自身经验、工具可靠性记录）完全缺失。这导致 Agent 在多轮任务交互和工具调用中无法维护上下文，也无法从失败中学习。

---

## 二、构建流程（Build）

### 2.1 摄入管线（Ingestion Pipeline）

构建流程的起点不是"存储文档"，而是**编译知识**。参考LLM-Wiki-Agent的ingest.py设计，摄入管线分为五个阶段：

```
Raw Source到达
    |
    v
[Stage 0] 哈希校验（SHA256）
    - 比对已有缓存，仅处理变化文件
    - Markdown特殊处理：仅对YAML frontmatter以下的body内容哈希
    |
    v
[Stage 1] 智能分块（QMD算法）
    - 目标900 tokens，重叠15%，搜索窗口200 tokens
    - 断点评分：H1(100) > H2(90) > H3/代码块(80) > 空行(20) > 换行(1)
    - AST感知：class/interface(100) > function(90) > type/enum(80)
    - 代码围栏保护：不在代码块内部切分
    |
    v
[Stage 2] 两通道提取
    - Pass 1: 确定性AST提取（零LLM成本）
      -> 类/函数/导入/调用图/文档字符串
    - Pass 2: LLM语义提取（仅处理变化文件）
      -> 概念/关系/设计意图/超边
      -> Confidence标签：EXTRACTED(1.0) / INFERRED(0.4-0.9) / AMBIGUOUS(0.1-0.3)
    |
    v
[Stage 3] 实体消歧与对齐
    - L1: identity_fields + UUID5（结构化导入，O(1)）
    - L2: trigram + 共现 + 时序（非结构化提取）
    - L3: LLM辅助判断（跨域对齐）
    - 消歧评分：name_similarity*0.5 + cooccurrence*0.3 + temporal*0.2
    |
    v
[Stage 4] Schema绑定与质量评分
    - 使用Schema提取模板引导LLM精确提取（见2.3）
    - 计算schema_alignment_score [0,1]
    - 高alignment(>0.8) -> 直接绑定到L1-L4 Schema
    - 低alignment(<0.7) -> 暂存为observation，不绑定Schema
    |
    v
[Stage 5] 写入与索引
    - Layer-R: ChromaDB向量存储（原文保留）
    - Layer-S: KuzuDB图节点（统一CognitiveNode）
    - 互索引边：CONSOLIDATED_INTO / EXTRACTED_FROM / TRACE_TO
    - 边际价值判断：去重门（DeduplicationGate）过滤高冗余碎片
```

**边际价值判断（DeduplicationGate）** [新增]：

写入不是"这个信息有没有价值"，而是"相对于已有记忆，这个信息的**边际价值**是多少"。在 Stage 0 之后、Stage 1 之前插入去重门：

```
快速向量相似度检查
    |
    +---> 相似度 > 0.92 -> 标记 DUPLICATE，仅更新 last_accessed_at，跳过后续阶段
    |
    +---> 与已有 observation 语义冲突 -> 标记 CONTRADICTION_CANDIDATE，高优先级入队
    |
    +---> 边际价值评分 = novelty_score × relevance_score / redundancy_penalty
          |
          +---> 低于阈值 -> 延迟写入或入低优先级队列
          |
          +---> 高于阈值 -> 正常进入 Stage 1
```

**关键设计点**：摄入管线的核心目标是**编译一次，持续复用**。与RAG的"每次查询重新检索"不同，OntologyEngine在数据进入系统时就完成结构化和交叉引用建立。

### 2.2 编译层（Compilation Layer）

编译层是构建流程的核心创新。它的作用是将原始数据转化为**Agent可直接消费的结构化知识产物**。

```
编译产物类型：

Entity Page（实体页）
  - 每个高频实体一个
  - 包含：当前最优摘要 + 时间线（按时间排列的所有版本）
  - 用途：快速事实查询的直接响应（避免每次查询重新推理）

Topic Page（主题页）
  - 每个高频主题一个（如"供应链金融风险"）
  - 包含：综合观点 + 引用链接 + 相关实体列表
  - 用途：跨实体的综合查询

Contradiction Log（矛盾日志）
  - 全局矛盾记录
  - 包含：矛盾标记 + 待审核项 + 已解决项
  - 用途：知识质量治理的仪表盘数据源
```

**编译触发条件**：

| 触发条件 | 编译动作 | 产物类型 |
|---------|---------|---------|
| 新entity被提取（proof_count >= 3） | 生成/更新Entity Page | 结构化摘要+时间线 |
| 同主题observation >= 5条 | 生成Topic Page | 综合观点+引用 |
| 新observation与现有entity属性矛盾 | 更新Contradiction Log | 矛盾标记+待审核提示 |
| 用户高频查询某entity（access_count > 10/周） | 预热Entity Page | 预编译摘要 |
| 周期性任务（每日/每周） | 全局Lint检查 | 孤立页标记、死链报告、过期提醒 |

**知识库的作用**：编译层将知识库从"被动存储"变为"主动知识工厂"。原始数据在摄入时就完成了LLM能做的最大工作量，后续查询只需读取编译产物而非重新推理。

### 2.3 Schema作为编译的提取模板

> **[关键设计点]** Schema 不是"数据校验规则"，而是**认知提取的导航图**。

Schema在构建流程中发挥**事前引导**作用，而非事后约束：

```yaml
# L1 EntityDeclaration自动转化为提取模板
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

**Schema感知提取的工作流程**：

```
LLM提取时注入Schema模板
    |
    v
输出结构化字段（debt_ratio=0.45, revenue=7000亿）
    |
    v
计算schema_alignment_score
    - 所有required字段存在 -> +0.3
    - 字段类型匹配 -> +0.2
    - 数值在合理范围 -> +0.2
    - 有source_fragment支撑 -> +0.2
    - 与其他entity关系一致 -> +0.1
    |
    v
alignment_score > 0.8 -> 绑定到L1 Schema，升级为entity
alignment_score 0.5-0.8 -> 存储为observation，待进一步验证
alignment_score < 0.5 -> 降级为fragment，不进入结构化层
```

**Schema的意义**：Schema不是"数据校验规则"，而是**认知提取的导航图**。它告诉LLM"应该提取什么"、"提取的质量标准是什么"、"提取结果应该如何分类"。没有Schema，LLM提取是盲目的；有了Schema，提取是结构化的、可量化的、可自动分级的。

Schema在构建流程中发挥**事前引导**作用，而非事后约束：

```yaml
# L1 EntityDeclaration自动转化为提取模板
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

**Schema感知提取的工作流程**：

```
LLM提取时注入Schema模板
    |
    v
输出结构化字段（debt_ratio=0.45, revenue=7000亿）
    |
    v
计算schema_alignment_score
    - 所有required字段存在 -> +0.3
    - 字段类型匹配 -> +0.2
    - 数值在合理范围 -> +0.2
    - 有source_fragment支撑 -> +0.2
    - 与其他entity关系一致 -> +0.1
    |
    v
alignment_score > 0.8 -> 绑定到L1 Schema，升级为entity
alignment_score 0.5-0.8 -> 存储为observation，待进一步验证
alignment_score < 0.5 -> 降级为fragment，不进入结构化层
```

**Schema的意义**：Schema不是"数据校验规则"，而是**认知提取的导航图**。它告诉LLM"应该提取什么"、"提取的质量标准是什么"、"提取结果应该如何分类"。没有Schema，LLM提取是盲目的；有了Schema，提取是结构化的、可量化的、可自动分级的。

### 2.4 五阶段状态机

每段记忆在构建流程中的状态：

```
[INGESTED] --(提取成功)--> [EXTRACTED] --(对齐成功)--> [ALIGNED] --(索引成功)--> [ACTIVE]
     |                        |                      |                      |
     |--(提取失败)--> [FAILED] |--(对齐低分)--> [OBSERVATION_ONLY]   |--(索引失败)--> [INDEX_RETRY]
     |                        |                      |                      |
     |--(重试成功)------------┘                      |                      |
                                                   |--(级联更新)--> [STALE]
                                                   |
                                              [ACTIVE] --(信念修正)--> [SUPERSEDED]
```

| 状态 | 含义 | 可查询？ | 可推理？ |
|------|------|---------|---------|
| INGESTED | 已摄入，待提取 | 否（仅Layer-R原文） | 否 |
| EXTRACTED | 已提取，待对齐 | 否 | 否 |
| ALIGNED | 已对齐，待索引 | 否 | 否 |
| ACTIVE | 完全可用 | 是 | 是 |
| STALE | 依赖的上层记忆已更新 | 是（附加警告） | 是（带staleness_warning） |
| SUPERSEDED | 被新版本取代 | 是（时序查询时） | 否（默认查询排除） |
| FAILED | 某阶段失败 | 否 | 否 |

---

## 三、管理流程（Govern）

### 3.1 矛盾检测与双轨治理

知识管理的核心挑战是**矛盾不是错误，而是知识演化的正常信号**。系统应该帮助人类**管理矛盾**，而非试图**消除所有矛盾**。

```
矛盾检测层（统一入口）
    |
    +---> 轨道A：企业知识治理（Schema约束型矛盾）
    |       - 事实型矛盾（entity属性冲突）
    |       - 规则型矛盾（L4规则逻辑冲突）
    |       - Schema型矛盾（数据违反约束）
    |       - 处理：人工审核或强规则自动校验
    |
    +---> 轨道B：Agent记忆自治（信念演化学型矛盾）
            - 时序型矛盾（新旧版本冲突）
            - 观点型矛盾（不同来源的不同解读）
            - 处理：自动信念修正，置信度低于阈值时标记待review
```

**矛盾分类与处理矩阵**：

| 矛盾类型 | 检测方式 | 轨道 | 自动处理？ | 人工审核？ | 示例 |
|---------|---------|------|----------|-----------|------|
| 数值更新 | 属性值比对 | B | 是（新confidence>旧×1.5） | 日志记录 | debt_ratio 45%→65% |
| 时序版本 | 双时序模型（T/T'） | B | 是（新recorded_at>旧） | 异步通知 | 年报→征信报告 |
| 事实反转 | 语义矛盾检测 | A | 否 | 必须 | "诉讼已撤诉"否定"涉诉" |
| 观点分歧 | LLM语义矛盾 | B | 否 | 建议 | 分析师A看好评级，分析师B看跌 |
| 规则冲突 | 规则引擎前置校验 | A | 否 | 必须 | L4规则间逻辑冲突 |
| Schema违反 | Schema校验层 | A | 是（拒绝写入） | 错误报告 | 必填字段缺失 |

**信任边界**：Agent自生记忆（轨道B）默认不影响企业核心决策（轨道A）。当Agent记忆的confidence > 0.9且schema_alignment_score > 0.9时，系统生成**晋升建议**，经人工审批后可升级到轨道A。

### 3.2 记忆生命周期管理

记忆不是永久的。不同认知层次的记忆有不同的生命周期策略：

```
L0 原始素材（Raw Material）
  -> 生命周期：7-30天TTL，被引用则延长
  -> 管理策略：ADD-only，永不删除（审计需要）
  -> 归档条件：无引用 + TTL到期

L1 提取记忆（Extracted Memory）
  -> 生命周期：活跃期90天
  -> 管理策略：CUD+Supersedes（entity/observation允许更新）
  -> 升级条件：alignment_score > 0.8, proof_count >= 3
  -> 降级条件：alignment_score < 0.3 -> 退回L0

L2 摘要知识（Compiled Knowledge）
  -> 生命周期：活跃期30天，需持续强化
  -> 管理策略：CUD+置信度更新（opinion可更新confidence）
  -> 升级条件：confidence > 0.8, access_count > 10/周
  -> 降级条件：标记stale超过30天未刷新 -> 退回L1

L3 程序资产（Procedural Asset）
  -> 生命周期：长期保留
  -> 管理策略：语义版本控制（v1→v2）
  -> 升级条件：success_rate > 0.7, invocation_count >= 10, 人工审批
  -> 降级条件：success_rate < 0.3 -> 标记deprecated

L4 核心资产（Core Asset）
  -> 生命周期：永久保留，版本管理
  -> 管理策略：变更管理 + 影响分析
  -> 升级条件：人工审批 + 影响分析通过
  -> 降级条件：版本替换（旧版本标记deprecated，不删除）
```

**六记忆维度覆盖检查** [新增]：

| 维度 | 字段/机制 | 覆盖状态 | 说明 |
|------|----------|---------|------|
| content | `text`, `attributes` JSON | ✓ 完整 | — |
| type | `memory_type` (7种) + `cognitive_layer` (4层) | △ 部分 | 新增 `model_domain` 字段覆盖四建模对象 |
| confidence | `confidence` (float) | ✓ 完整 | — |
| source | `source_fragment_ids`, `source_pipeline` | △ 部分 | **待新增** `source_trust_tier`（用户声明>行为推断>环境观测>Agent生成） |
| scope | 无统一字段 | ✗ 缺失 | **待新增** `scope`（task/user/global + ref_id + window） |
| time-decay | `valid_from/to`, `strength`, `last_accessed_at` | △ 部分 | **待新增** `last_confirmed_at`（被后续证据确认的时间） |

**遗忘策略（与版本限制协同）**：

| 策略 | 触发条件 | 动作 |
|------|---------|------|
| 软衰减 | strength < 0.3 | 降低检索权重，不删除 |
| 类型降级 | strength < 0.2 | L2→L1→L0 |
| 归档 | strength < 0.1 | 移至冷存储，不参与常规检索 |
| 硬删除 | strength < 0.01且proof_count==0 | 永久删除 |
| 保护 | feedback_weight >= 0.9 | 永不遗忘 |

**版本限制与遗忘的协同**：
- 版本限制先执行（硬约束：单实体最大100版本）
- 遗忘机制后执行（软衰减）
- 被版本限制淘汰的版本如果strength > 0.3，先归档再删除

### 3.3 自动化维护（梦境循环）

知识库需要**主动自愈**能力，而非被动等待问题暴露。参考GBrain的梦境循环设计，引入周期性后台维护任务：

> **[关键设计点]** 治理（governance）优先于容量。记忆系统最大的风险不是"存不下"，而是"管不好"——矛盾没人管、来源不可信、权限不透明、Agent 在幻觉和真实意图间无法区分。

```
梦境循环（每小时/每日触发）：

Phase 1: 矛盾检测（Contradiction Detection）
  - 扫描所有Compiled Page
  - 对比Timeline中的不同版本
  - 标记逻辑不一致
  - 生成Contradiction Report

Phase 2: 过期检查（Freshness Audit）
  - 检查每个Compiled Page的"最后验证时间"
  - 超过阈值（如30天未更新）的标记为"可能过期"
  - 检查底层来源是否还有效

Phase 3: 孤立页清理（Orphan Detection）
  - 检查是否有Page无入链（从未被引用）
  - 检查是否有死链（指向不存在的Page）
  - 标记孤立页供人工review

Phase 4: 自链接增强（Auto-Linking）
  - LLM分析新创建的Page内容
  - 建议与其他Page的链接关系
  - 自动添加双向引用

Phase 5: 知识图谱补全（Graph Completion）
  - 检查知识图谱中的"缺口"
  - 如发现"华为"与"供应商B"有交易关系，但无"供应商B"的entity
  - 生成"缺失知识提示"
```

**维护架构**：事件驱动（近实时）+ 周期性后台（小时-天级）的混合：

```
事件驱动层：新信息到达 -> 局部影响分析 -> 标记stale -> 入刷新队列
                |
                v
周期性后台层：梦境循环 -> 全局矛盾扫描 + 过期检测 + 孤立清理 + 图谱补全
                |
                v
手动触发层：管理员审查仪表盘 -> 处理梦境循环报告 -> 确认/拒绝/修改
```

### 3.4 版本控制与更正追溯

信息更正不是删除，而是**版本链的延伸**。引入Supersedes边和双时序模型：

```
更正链：A（原始）-> B（第一次更正）-> C（第二次更正）
每个节点都保留，通过SUPERSEDES链连接

SUPERSEDES边属性：
  - supersedence_type: "correction" | "update" | "retraction" | "belief_revision"
  - supersedence_reason: 人类可读原因
  - supersedence_confidence: 更正的置信度
  - initiated_by: "user" | "agent" | "system" | "admin"
  - review_status: "auto" | "pending_review" | "approved" | "rejected"

双时序属性：
  - valid_from / valid_to: 事实有效期（T）——"这个债务率在什么时间段有效"
  - recorded_at: 系统记录时间（T'）——"系统什么时候知道这个事实"

查询某节点的当前有效版本：
  - 不是"最新"，而是"未被superseded的最新"
  - 遍历SUPERSEDES链找到末端
  - 末端节点的valid_to为null -> 当前有效
```

**更正传播协议**：当L1 entity属性被更正时，依赖它的所有上层知识都需要重新评估：

```
更正触发 -> AnalyzeImpact遍历下游依赖
    |
    +---> mental_model: 标记stale，触发异步刷新
    +---> observation: 检查是否矛盾，标记待review或降权
    +---> opinion: 重新计算confidence，低于阈值则标记superseded
    +---> L4规则执行结果: 标记stale，入重算队列
    +---> L3 metric: 触发重算
```

---

## 四、消费流程（Consume）

### 4.1 检索策略编排

消费流程的起点是**检索**。当前设计的并行池模型（Layer-R + Layer-S → RRF融合）需要进化为**自适应分层漏斗**：

> **[关键设计点]** 读取应从语义相似召回升级为**"任务约束驱动的检索-推断耦合"**。一个用户讨论项目架构时的 query，与"他上周否决过微服务方案"高度相关，但表面语义完全不匹配。系统需要先由**任务理解层**判断当前决策受什么约束，再找对应记忆。

```
默认检索模式：自适应分层漏斗

第1层：Mental Model快速通道（预算20%）
  - recall(query, memory_type="mental_model", top_k=3)
  - 若命中且confidence > 0.8 -> 短路返回（高层摘要）
  - 若命中但confidence <= 0.8 -> 标记为候选，继续下沉
  - 若未命中 -> 进入第2层

第2层：Entity + Rule确定性层（预算30%）
  - 图遍历 + 规则推理
  - 若找到确定性答案 -> 返回 + 证据链展开
  - 若找到相关entity -> 提取相关observation IDs，进入第3层

第3层：Observation + Episode证据层（预算30%）
  - 向量检索 + 时序过滤
  - 若找到直接匹配的observation -> 返回
  - 收集observation中的entity引用，用于第2层扩展

第4层：Fragment原始证据（预算20%）
  - 纯向量检索，补充语义证据
  - 若上层结果不足 -> fragment填充

层间反馈：
  - 第2层找到的entity IDs -> 注入第3层作为过滤条件
  - 第1层mental_model的source_entity_ids -> 第2层优先遍历
  - 第3层observation的source_fragment_ids -> 第4层精确检索
```

**QueryUnderstandingLayer** [新增]：

在分层漏斗之前引入任务理解层：

```
输入：用户 query + 当前 task_context（task_id, 历史交互, 当前轮次）
    |
    v
QueryUnderstandingLayer
    - 提取 TaskConstraints：
      - user_preference: bool   # 是否涉及用户偏好
      - task_history: bool      # 是否涉及任务历史
      - temporal_scope: str     # 时间范围（如"过去一个月"）
      - decision_type: str      # 决策类型（factual/analytical/causal）
    |
    v
约束驱动的检索策略调整：
    - user_preference=true -> 优先检索 model_domain=user 的 opinion/mental_model
    - task_history=true -> 优先检索 scope.task_id=current_task 的 episode/commitment
    - temporal_scope 存在 -> 注入时序过滤条件
    - decision_type=causal -> 展开 CAUSAL 边遍历
```

**Disposition驱动的动态权重**：

```
DispositionProfile:
  - skepticism: [0,1] 怀疑倾向
  - thoroughness: [0,1] 深入程度（高则深入低层）
  - recency_bias: [0,1] 时间偏好（高则偏好最新信息）
  - abstraction_preference: [0,1] 抽象偏好（高则偏好mental_model）
  - evidence_demand: [0,1] 证据要求（高则要求更多fragment）

动态调整：
  - abstraction_preference > 0.8 -> mental_model权重×1.5，可能短路
  - thoroughness > 0.8 -> 全层检索，不短路
  - skepticism > 0.7 -> min_confidence=0.8，filter_superseded=true
  - evidence_demand > 0.8 -> evidence_expansion_depth=3
```

### 4.2 推理与执行

检索之后的推理流程：

```
检索结果（分层漏斗输出）
    |
    v
[步骤1] 查询意图分解
  - 主意图: explain_causality / factual_lookup / temporal_trace / analytical_compute
  - 目标实体、属性、期望答案类型
    |
    v
[步骤2] Schema-Aware推理路由
  - 若查询涉及L3 metric -> 触发MetricEngine计算
  - 若查询涉及L4 rule -> 触发RuleEngine执行
  - 若查询涉及时序 -> 触发时序过滤
  - 若查询涉及因果 -> 触发CAUSAL边遍历
    |
    v
[步骤3] 证据链组装（可选）
  - include_evidence=true时
  - 从检索结果向下展开完整证据树
  - EvidenceExpander: mental_model -> entity/observation -> fragment
  - 受token_budget控制截断
    |
    v
[步骤4] LLM生成最终回答
  - 注入：检索结果 + 证据链 + Schema上下文
  - 输出：结构化回答 + 置信度 + 溯源
```

### 4.3 证据链组装

当前设计只有单层证据（observation→fragment通过CONSOLIDATED_INTO）。需要支持**多层展开**：

```
证据展开规则：

mental_model:
  next_layers: ["entity", "observation"]
  edge_types: ["SUMMARIZED_AS", "MAPPED_TO"]
  max_expansion: 5

entity:
  next_layers: ["observation", "fragment"]
  edge_types: ["EXTRACTED_FROM", "SUPPORTED_BY", "CONSOLIDATED_INTO"]
  max_expansion: 10

observation:
  next_layers: ["fragment"]
  edge_types: ["CONSOLIDATED_INTO"]
  max_expansion: 5

证据树输出示例：
  [mental_model] "华为因债务高企被评为D级风险"
    [entity] debt_ratio=0.78
      [observation] "2024Q4资产负债率升至78%"
        [fragment] "2024年报第32页：资产负债率78%..."
    [entity] risk_grade=D
      [observation] "连续两季度现金流为负"
        [fragment] "Q4现金流量表：经营活动现金流-500万..."
```

### 4.4 一致性级别

查询时可选择一致性级别，平衡响应速度与数据一致性：

| 级别 | 行为 | 延迟 | 适用场景 |
|------|------|------|---------|
| **eventual（默认）** | 直接查询当前状态，返回stale标记节点时附加warning | 低 | 实时交互、快速回答 |
| **strong** | 等待所有stale依赖刷新后返回 | 高（可能数秒） | 关键决策、授信审批 |
| **raw** | 直接返回，不做任何一致性检查 | 最低 | 调试、审计 |

---

## 五、典型案例

### 5.1 场景：供应链金融风控Agent的30天事件流

某银行使用OntologyEngine监控核心企业（华为）及其上下游供应商的信用风险。

```
Day 1:  导入华为2024年报 -> 提取财务指标 -> 信用评分=A
Day 5:  新闻：华为某子公司涉及诉讼 -> Agent记录episode -> 触发observation更新
Day 10: 用户询问："华为风险如何？" -> Agent检索并回答
Day 15: 新导入征信报告：华为债务率上升 -> 与Day 1的observation矛盾
Day 20: 用户更正："那起诉讼已经撤诉了" -> 需要信息更正
Day 25: Agent自动归纳：近30天3次类似"债务率上升但随后澄清"模式 -> 触发procedure提取
Day 30: 用户问："过去一个月华为风险判断为什么波动？" -> 需要时序追溯和因果解释
```

### 5.2 按流程拆解

**构建流程在案例中的表现：**

| 日期 | 事件 | 构建阶段 | 产物 |
|------|------|---------|------|
| Day 1 | 年报导入 | Stage 0-5完整执行 | Entity Page"华为"、Topic Page"华为财务"、L3 metric计算 |
| Day 5 | 新闻摄入 | Stage 0-4 | episode记录、observation"涉诉"、Entity Page更新（新增法律风险段） |
| Day 15 | 征信报告 | Stage 0-4 + 矛盾检测 | 新observation（debt_ratio=65%）、Contradiction Log更新、自动supersede旧值 |
| Day 20 | 用户更正 | Stage 0-3（用户输入作为新source） | 新observation"撤诉"、级联更新触发、旧episode标记superseded |
| Day 25 | 模式归纳 | PatternDetector扫描 | SchemaProposal（新增L4 rule_logic）、入ReviewQueue |

**管理流程在案例中的表现：**

| 日期 | 管理动作 | 轨道 | 结果 |
|------|---------|------|------|
| Day 1 | 年报entity绑定Schema | 轨道A（企业知识） | L1 Counterparty实例、L3 metric计算 |
| Day 5 | 新闻observation入沙箱 | 轨道B（Agent记忆） | episode/observation自治演化 |
| Day 15 | 债务率矛盾自动处理 | 轨道B -> 轨道A | 数值更新自动supersede，信用评分重算 |
| Day 20 | 诉讼更正人工审核 | 轨道A | 管理员确认后级联更新 |
| Day 25 | procedure晋升建议 | 沙箱 -> 生产 | 领域专家审核后升级为L4 RuleLogic |

**消费流程在案例中的表现：**

| 日期 | 查询 | 检索模式 | 响应 |
|------|------|---------|------|
| Day 10 | "华为风险如何？" | 分层漏斗 | 命中Entity Page"华为"预编译摘要 -> 直接返回（~1000 tokens） |
| Day 30 | "为什么波动？" | 分层漏斗 + 时序追溯 | mental_model快速通道 -> 展开Timeline -> 按时间线排序的因果链 |

---

## 六、关键决策点讨论

### 决策点1：统一CognitiveNode vs 保留影子节点

| 方案 | 论据 | 代价 | 推荐 |
|------|------|------|------|
| **A: 统一CognitiveNode** | 消除EntityNode+MemoryUnitNode影子节点的同步开销 | JSON attributes丧失类型安全，需额外校验层 | **推荐** |
| **B: 保留影子节点** | EntityNode有Schema约束的强类型属性 | 维护成本高（一致性同步、更新传播、索引冗余） | 不推荐 |

**判断**：采用混合方案——Layer-R保持独立（感知层），Layer-S扩展为统一CognitiveNode（语义+观点+程序），通过`cognitive_layer`分区。

### 决策点2：编译层（LLM-Wiki模式）vs 纯检索（RAG模式）

| 方案 | 论据 | 代价 | 推荐 |
|------|------|------|------|
| **A: 混合编译** | 热点知识预编译，Token效率提升80%+ | 编译需要一次性Token投入 | **推荐** |
| **B: 纯RAG** | 工程简单，无需编译逻辑 | 每次查询重新推理，Token浪费 | 当前状态 |

**判断**：引入Compilation Layer作为只读缓存+结构化索引，Layer-R和Layer-S仍是唯一事实源，Compiled Pages是加速查询的派生产物。

### 决策点3：双轨治理 vs 统一治理

| 方案 | 论据 | 代价 | 推荐 |
|------|------|------|------|
| **A: 双轨制** | 企业知识人工治理 + Agent记忆自治演化 | 权限模型复杂 | **推荐** |
| **B: 完全人工** | 金融场景安全要求 | 不可扩展 | 不适用 |
| **C: 完全自动** | Agent自治效率高 | 错误传播风险 | 不适用 |

**判断**：双轨制通过"信任边界"平衡自治与治理。轨道A（Schema约束型）人工审核，轨道B（Agent自生）自动演化，高confidence记忆可建议升级。

### 决策点4：ADD-only vs CUD+Supersedes

| 方案 | 论据 | 代价 | 适用层 |
|------|------|------|--------|
| **ADD-only** | 保留完整历史，时序推理天然 | 存储膨胀，检索噪声增加 | **感知层（L0）** |
| **CUD+Supersedes** | 当前查询默认最新版本，噪声低 | 更新传播复杂 | **语义层（L1）** |
| **置信度更新** | 无需创建新版本 | 无法追溯置信度变化历史 | **观点层（L2）** |
| **语义版本** | 程序兼容性管理 | 版本切换复杂 | **程序层（L3）** |

**判断**：分层策略——感知层ADD-only，语义层CUD+Supersedes，观点层置信度更新，程序层语义版本。

### 决策点5：即时同步 vs 最终一致

| 方案 | 论据 | 代价 | 推荐 |
|------|------|------|------|
| **即时同步** | 查询永远一致 | 写入阻塞，延迟高 | 不推荐 |
| **最终一致** | 写入性能不受影响 | 短暂不一致窗口 | **推荐（默认）** |
| **读写分离** | 写入最终一致 + 读取可配置 | 实现复杂 | **推荐（高级）** |

**判断**：默认最终一致，stale标记附加warning。支持强一致性查询（等待刷新后返回）。

---

## 七、当前设计与愿景的GAP分析

> **[关键设计点]** 本节 GAP 基于内部设计文档审视 + SOTA 对比 + 外部批判框架（lencx, 2026）三重输入综合判定。

### 7.1 已对齐的部分

| 愿景要求 | 当前设计 | 对齐度 |
|---------|---------|--------|
| Layer-R/Layer-S双层存储 | memory-hierarchy.md完整设计 | 100% |
| memory_type标签区分认知类型 | 09-agent-memory.md + memory-hierarchy.md | 100% |
| 三操作API（remember/recall/reflect） | memory-api.md完整设计 | 100% |
| Consolidation/Forgetting/Reflection | memory-lifecycle.md完整设计 | 90%（缺紧急升级通道） |
| Bundle Search边语义参与检索 | 08-knowledge-retrieval.md | 100% |
| 时序版本化（valid_from/to） | temporal-modeling.md | 80%（缺双时序T/T'） |
| ingest时矛盾检测 | 01-vision提及 | 30%（仅在Reflect时检测） |
| 知识编译一次 | 01-vision核心哲学 | 40%（Consolidation是后台任务，非ingest即时编译） |

### 7.2 存在GAP的部分

| GAP编号 | 领域 | 愿景要求 | 当前状态 | 严重程度 |
|---------|------|---------|---------|---------|
| **GAP-1** | 编译层 | ingest时即时编译，生成Entity Page/Topic Page | Consolidation是后台异步任务，无预编译摘要 | **高** |
| **GAP-2** | 存储层 | 消除影子节点，统一CognitiveNode | EntityNode+MemoryUnitNode通过MAPPED_TO关联 | **高** |
| **GAP-3** | Schema | Schema作为提取模板和检索路由 | Schema仅作约束定义，未参与提取和检索 | **高** |
| **GAP-4** | 检索 | 自适应分层漏斗，Disposition动态权重 | 并行池+静态权重（mental_model=3.0固定） | **高** |
| **GAP-5** | 矛盾治理 | ingest时矛盾检测，双轨治理，自动解决规则 | 仅在Reflect时检测，无自动解决，无轨道分离 | **高** |
| **GAP-6** | 时序 | 双时序模型（Event Time T + Ingestion Time T'） | 只有valid_from/to（有效性窗口），无recorded_at | **中** |
| **GAP-7** | 维护 | 梦境循环（自动化矛盾/过期/孤立检测） | 无周期性全局维护任务 | **中** |
| **GAP-8** | 晋升 | 沙箱空间+晋升机制（sandbox->production） | 无沙箱概念，所有记忆在同一空间 | **中** |
| **GAP-9** | 证据链 | 多层证据展开（mental_model->entity->observation->fragment） | 单层证据（CONSOLIDATED_INTO） | **中** |
| **GAP-10** | 一致性 | 可配置一致性级别（eventual/strong/raw） | 无一致性配置，直接返回当前状态 | **中** |

### 7.3 GAP根因分析

**根因1：存储范式与认知层次的混淆**

当前设计将Layer-R和Layer-S定义为"存储范式差异"（向量优先vs图优先），然后在Layer-S内通过memory_type标签区分认知类型。这导致了两个深层问题：
1. Layer-R（碎片）本质上是感知记忆的等价物，Layer-S内的fragment标签试图在同一存储层内模拟这一过程
2. EntityNode（Schema驱动）与MemoryUnitNode(type=entity)（记忆视角）形成影子节点

**根因2：Schema的认知作用被低估**

当前Schema v2的核心作用是数据约束和推理规则定义。但在Agent记忆系统中，Schema应该发挥更深层的认知组织作用：作为检索的语义骨架、作为记忆巩固的模板、作为L1-L4与memory_type的显式映射。

**根因3：检索是查询词驱动的而非Schema驱动的**

当前检索是特征词匹配进行查询分类（factual/multi-hop/temporal/analytical/mixed），无法利用Schema结构优化检索路径。当Agent查询"企业A的风险等级"时，Schema知道risk_grade是L3指标、由L4规则计算、依赖L1实体属性，但这一知识路径没有主动引导检索。

**根因4：Agent API抽象层次不够**

remember/recall/reflect三个操作对Agent足够简单，但面对复杂查询（如"过去一个月华为风险判断为什么波动"）时，recall返回的是碎片列表，Agent需要自行组装因果解释。系统不提供预编译的摘要页和叙事结构。

**根因5：记忆≠蒸馏的认知盲区 [新增]**

Consolidation 被过度定位为记忆的"终极目标"——把碎片归纳为 observation/entity 就是"好的记忆"。但 lencx 的批判指出：蒸馏只是管理环节的一个操作，不是记忆本身。记忆的终极目标是**支持 Agent 在特定任务约束下做出正确决策**。当前设计缺少独立的 Distillation 机制（信息压缩归档），也缺少归纳推理轨迹的显式保留，导致 Agent 只能复述结论，无法解释"为什么现在信这个"。

**根因6：治理成熟度不足 [新增]**

权限治理几乎空白，自动裁决缺失，策略性遗忘未实现。系统把重心放在"如何存储更多"而非"如何管理更好"。这与 lencx 强调的"治理优先于容量"原则相悖。

---

## 八、推荐演进路径

### Phase 1：基础设施扩展（1-2月）

| 任务 | 内容 | 解决GAP |
|------|------|--------|
| 统一CognitiveNode | 消除影子节点，单表+cognitive_layer分区 | GAP-2 |
| 新增opinion类型 | 与observation区分，支持belief_status | GAP-5 |
| 引入SUPERSEDES/CONTRADICTS边 | 版本链和矛盾标记 | GAP-5, GAP-6 |
| 双时序属性 | 增加recorded_at（T'） | GAP-6 |
| DispositionProfile | space级别存储默认Disposition | GAP-4 |
| **新增记忆维度字段** | `model_domain`, `source_trust_tier`, `scope`, `last_confirmed_at` | GAP-12 |
| **新增记忆类型** | `commitment`, `task_state`, `self_experience`, `constraint` | GAP-11, GAP-18 |

### Phase 2：编译层与检索重构（2-3月）

| 任务 | 内容 | 解决GAP |
|------|------|--------|
| Compiled Page生成 | Entity Page/Topic Page自动生成 | GAP-1 |
| Schema-Aware提取 | LLM提取时注入Schema模板 | GAP-3 |
| 分层漏斗检索 | mental_model->entity->observation->fragment | GAP-4 |
| EvidenceExpander | 多层证据展开 | GAP-9 |
| 动态权重调整器 | 基于Disposition调整类型权重 | GAP-4 |
| **QueryUnderstandingLayer** | 任务约束提取 → 驱动检索策略 | GAP-14 |
| **DeduplicationGate** | 写入前去重 + 边际价值判断 + 矛盾前置检测 | GAP-13 |
| **推理轨迹保留** | Consolidation 时记录 LLM 推理摘要 | GAP-17 |

### Phase 3：治理与维护（3-4月）

| 任务 | 内容 | 解决GAP |
|------|------|--------|
| 双轨矛盾治理 | 轨道A（企业）+ 轨道B（Agent） | GAP-5 |
| 规则引擎 | 可配置的信念修正规则 | GAP-5 |
| CorrectionPropagation | 更正自动传播到下游 | GAP-5 |
| 梦境循环 | 周期性全局维护任务 | GAP-7 |
| 沙箱空间 | 弱Schema约束的实验空间 | GAP-8 |
| **ArbitrationEngine** | 证据权重自动裁决矛盾 | GAP-15 |
| **权限治理** | 用户查看/编辑/删除记忆权限 + AccessControl | GAP-16 |
| **策略性遗忘** | 否定信号驱动加速遗忘 | GAP-12 |

### Phase 4：一致性与高级特性（4-6月）

| 任务 | 内容 | 解决GAP |
|------|------|--------|
| 读写分离一致性 | eventual/strong/raw三级 | GAP-10 |
| Schema-Memory双向反馈 | 记忆驱动Schema演化建议 | GAP-3 |
| 跨域实体对齐 | same_entity_as边 | - |
| 多Agent共享记忆 | MCP协议上下文共享 | - |

---

## 九、外部批判视角：lencx 框架对照

> 本节汇总外部批判框架（lencx, 2026）与 OntologyEngine 设计的系统性对照结果。完整分析见 `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md`。

### 9.1 记忆≠蒸馏：Consolidation 定位审视

| 批判点 | OntologyEngine 现状 | 结论 |
|--------|-------------------|------|
| 蒸馏只是归档，不是记忆 | Consolidation 被当作记忆"升级形态" | **偏差**：缺少独立的 Distillation 机制和推理轨迹保留 |
| 记忆必须保留形成判断的上下文 | `history` 记录结论变更，不记录推理过程 | **GAP-17**：需新增 `consolidation_reasoning` 字段 |

### 9.2 四建模对象覆盖度

| 建模对象 | 覆盖状态 | 缺失影响 |
|---------|---------|---------|
| User Model | △ 部分（DispositionProfile） | 缺"沟通习惯"维度 |
| Task Model | ✗ 缺失 | Agent 无法维护承诺、artifact 版本、方案否决历史 |
| World Model | △ 部分（Schema L1-L4） | 缺动态环境上下文（代码库、API 状态） |
| Self Model | ✗ 缺失 | Agent 无法记录工具失败经验，无法从失败中学习 |

### 9.3 六记忆维度覆盖度

| 维度 | 覆盖度 | 缺失 |
|------|--------|------|
| content | ✓ | — |
| type | △ | 缺语义类型标签（event/assertion/belief/constraint/commitment） |
| confidence | ✓ | — |
| source | △ | 缺可信层级（user_declared/behavior_inferred/environment_observed/agent_generated） |
| scope | ✗ | 无统一字段 |
| time-decay | △ | 缺 `last_confirmed_at` |

### 9.4 三条闭环链路审视

| 链路 | 现状 | 差距 |
|------|------|------|
| 写入 | 来了就存，无去重，无矛盾前置 | **GAP-13**：需 DeduplicationGate |
| 管理 | 有检测但无自动裁决，权限空白 | **GAP-15, GAP-16**：需 ArbitrationEngine + PermissionGovernance |
| 读取 | RAG 式语义召回 | **GAP-14**：需 QueryUnderstandingLayer |

### 9.5 核心挑战：治理优先于容量

OntologyEngine 治理成熟度自评：

| 治理维度 | 成熟度 | 关键缺失 |
|---------|--------|---------|
| 矛盾检测 | ★★★☆☆ | 有检测，无自动裁决 |
| 来源追踪 | ★★★☆☆ | 有来源，无可信层级 |
| 权限治理 | ★☆☆☆☆ | 几乎空白 |
| 策略性遗忘 | ★★☆☆☆ | 纯 Ebbinghaus，无否定信号驱动 |
| 轨迹保留 | ★★☆☆☆ | history 记录变更，不记录推理 |
| 写入控制 | ★★☆☆☆ | 无去重门，无边际价值判断 |
| 读取质量 | ★★★☆☆ | RRF 四路融合，无任务约束驱动 |

---

## 参考索引

| 文档 | 路径 | 作用 |
|------|------|------|
| 愿景 | `docs/01-overview/01-vision.md` | 项目北极星 |
| Agent记忆概念 | `docs/01-overview/09-agent-memory.md` | 记忆系统概念框架 |
| 知识检索 | `docs/01-overview/08-knowledge-retrieval.md` | 检索机制设计 |
| 记忆层次 | `docs/02-design/agent-memory/memory-hierarchy.md` | MemoryUnit数据模型 |
| 记忆生命周期 | `docs/02-design/agent-memory/memory-lifecycle.md` | 三大认知操作设计 |
| 认知操作API | `docs/02-design/agent-memory/memory-api.md` | Agent API设计 |
| Consolidation引擎 | `docs/02-design/agent-memory/consolidation-engine.md` | 巩固引擎实现 |
| Reflect Agent | `docs/02-design/agent-memory/reflect-agent.md` | 反思Agent设计 |
| SOTA审视报告 | `discuss/2026-04-27-agent-memory-design-analysis.md` | 7个不足+3个范式 |
| 认知交互分析 | `discuss/2026-04-27-four-layer-cognitive-interaction-analysis.md` | 层间影响+检索设计 |
| Schema融合治理 | `discuss/2026-04-27-cognitive-schema-integration-deep-dive.md` | Schema映射+矛盾治理 |
| GBrain/LLM-Wiki审视 | `discuss/2026-04-27-key-decision-review-gbrain-llmwiki.md` | 编译型记忆+记忆OS |
| 推荐方案展开 | `discuss/2026-04-27-recommendation-schemes-detailed-design.md` | 7个方案架构设计 |
| 五报告对照 | `discuss/2026-04-28-five-reports-vs-source-docs-gap-analysis.md` | 4共识+3分歧+10GAP |
| **lencx框架对照** | `discuss/2026-04-28-agent-memory-design-vs-lencx-critique.md` | 外部批判框架审视 |
| 本流程文档 | `docs/01-overview/10-kb-process.md` | 知识库全生命周期流程 |

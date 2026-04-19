# OntologyEngine 愿景

> **status**: proposed | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19
> **[关键设计点]**: 本文档定义 OntologyEngine 的目标愿景，是项目的北极星

---

## 一句话定义

面向 AI Agent 的**结构化知识推理引擎** —— 把企业里分散、异构、持续变化的知识，变成可被 Agent 稳定消费的"**事实 + 逻辑**"执行环境，使多个 Agent 能协同完成完整业务作业。

不要再把知识当“可以按需扫一遍的文档堆”，而是把它当成一个可以被编译、被查询、被执行、被记忆、被治理的“领域世界模型”。

---

## 核心命题：知识引擎要解决哪些具体问题？

### 问题 1：多源异构 → 统一可计算的知识表示

**痛点**：同一事实在不同系统有多种表达（字段名不同、口径不同），图文/表格/代码/对话混杂。

**OntologyEngine 解法**：LLM-Wiki 编译管线，把 Raw Sources 预编译为统一的"知识 Wiki"——保留原文以供追溯，同时抽取出**实体‑关系‑规则**的结构化表达。

### 问题 2：静态知识 + 动态知识 + 分析逻辑的对齐与长期维护

**痛点**：静态制度、SOP 与动态监控指标、用户行为混在一起，知识变更难以增量更新。

**OntologyEngine 解法**：Layer-R（原文层）+ Layer-S（结构化层）+ 时序版本化，支持"事实层 + 语义层 + 逻辑层"三层对齐，增量处理变化文件而非重建索引。

### 问题 3：从"原文检索"升级为"事实/逻辑的检索、执行与仿真"

**痛点**：传统 RAG 只"找段话"，无法执行关联规则或分析流程。

**OntologyEngine 解法**：混合检索（向量 + 图 + 符号）+ 规则引擎执行 + DAG 拓扑排序，结果可以是执行计划、流程图、SQL/代码。

### 问题 4：知识资产的可观测、可治理、可演化

**痛点**：知识从哪来、被谁改、何时失效，Agent 使用知识的效果无法追踪。

**OntologyEngine 解法**：ingest 时矛盾检测（LLM-Wiki 模式）+ 溯源链路（trace_to）+ 置信度标签 + 知识新鲜度评分。

### 问题 5：支持多 Agent 协同完成端到端任务

**痛点**：每个 Agent 自己一套 private RAG，导致一致性问题，跨 Agent 共享记忆缺失。

**OntologyEngine 解法**：统一知识引擎作为"公共世界模型"，MCP 协议暴露工具接口，多 Agent 通过知识引擎共享上下文而非私有 prompt。

### 问题 6：多域知识的隔离与协同

**痛点**：金融风控、供应链、合规审查等不同域的知识混在一起，域间隔离不足导致误用，域间协同不足导致信息孤岛。

**OntologyEngine 解法**：语义空间混合隔离——默认逻辑隔离（domain_id 元数据过滤），可选物理隔离（独立 DB 实例），通过配置切换。跨域实体通过 same_entity_as 边对齐，支持跨域查询时的自动扩展。

### 问题 7：知识全链路的可读、可见、可管理、可调整

**痛点**：自动化只是第一层，知识加工-存储-消费过程中缺乏人工介入点，错误知识无法纠正，过时知识无法标记，质量无法持续改进。

**OntologyEngine 解法**：四层人工介入机制——声明式规则编辑（结构化配置+表达式，非严格 DSL）、反馈闭环（检索结果评分→权重更新）、质量检测+自愈（lint→heal 循环）、知识时效管理（invalidate 而非 delete）。

### 问题 8：业务逻辑作为知识资产

**痛点**：风险评估、指标计算、图分析逻辑等业务逻辑散落在代码中，无法被 Agent 发现、理解和复用。

**OntologyEngine 解法**：双层表达——Schema 内嵌规则定义（逻辑边实时计算），同时规则也作为图节点存储（可编辑、可版本化、可溯源），逻辑边+规则节点互补。

---

## 五层架构总览

```
┌──────────────────────────────────────────────────────────────┐
│  L4: Agent 协同与应用层                                       │
│  ── 多 Agent 编排、任务分派、跨 Agent 共享记忆                 │
├──────────────────────────────────────────────────────────────┤
│  L3: 推理与执行层                                           │
│  ── 检索策略编排、规则/分析框架执行、仿真/规划                 │
├──────────────────────────────────────────────────────────────┤
│  L2: 知识表示与存储层                                        │
│  ── 向量索引、知识图谱、时序版本、长期记忆结构                 │
├──────────────────────────────────────────────────────────────┤
│  L1: 知识编译层                                              │
│  ── Raw Sources → 结构化 Wiki、矛盾检测、增量更新            │
├──────────────────────────────────────────────────────────────┤
│  L0: 数据源层                                                │
│  ── 文档、业务表、日志、对话、代码、API 元数据、监控           │
└──────────────────────────────────────────────────────────────┘
```

---

## 核心设计：Layer-R 与 Layer-S

OntologyEngine 的知识管理分为两层，各司其职：

```
┌──────────────────────────────────────────────────────────────┐
│  Layer-R: 原始知识层                                         │
│  ── verbatim 原文存储，向量检索                               │
│  ── 类比 MemPalace Drawer + ChromaDB                       │
│  ── 核心洞察：96.6% R@5 来自 verbatim 存储 + 元数据过滤     │
├──────────────────────────────────────────────────────────────┤
│  Layer-S: 结构化知识层                                      │
│  ── Entity/Relation/Rule 实例，Schema 驱动推理               │
│  ── 类比 m_flow Episode/Facet + KAG KnowledgeUnit            │
│  ── 核心洞察：Bundle Search 最小成本路径，一条强证据链足够   │
└──────────────────────────────────────────────────────────────┘
         ↑ extracted_from / trace_to 互索引链接 ↓
```

两层协同：**Layer-R 检索 → Layer-S 推理 → Layer-R 回溯证据**，完整覆盖从原始文档到可执行决策的全链路。

---

## 三类知识资产断裂：为什么需要 OntologyEngine

企业知识以三种形态并存，但彼此断裂：

```
┌──────────────────────────────────────────────────────────────┐
│  L4: 组织级资产                                              │
│  ── 业务规则、合规策略、行业标准、组织决策知识                   │
│  ── 特征：共识性、权威性、版本化管理                            │
├──────────────────────────────────────────────────────────────┤
│  L3: 个人知识沉淀                                            │
│  ── 专家经验、隐性知识、领域直觉、审查判断                       │
│  ── 特征：主观性、经验性、难以显性化                            │
├──────────────────────────────────────────────────────────────┤
│  L2: IT 资产                                                │
│  ── 数据源、API 接口、系统配置、基础设施元数据                    │
│  ── 特征：结构化、可自动化、实时变化                              │
└──────────────────────────────────────────────────────────────┘
         ↑ OntologyEngine 在三类资产之间建立可推理的链接 ↑
```

### 深度：三类资产的来源与特性差异

| 断裂类型 | 后果 | OntologyEngine 解法 |
|----------|------|---------------------|
| **IT ↔ 组织** | IT规则逻辑复杂，难以理解，可能与实际业务场景脱节 | Schema 驱动/规则结构化表达：IT规则白盒化, 数据资产统一建模, 结构化表达, Agent能看懂可执行逻辑 |
| **个人 ↔ 组织** | 经验无法传承，规则成谜 | 从碎片化的个人作业、线下文档、Agent对话中提取规则逻辑, 逐步沉淀为系统化的组织级资产 |
| **IT ↔ 个人** | 系统告警无人能解释 | 执行快照 + 条件拆解：每个推理步骤可审阅 |
| **三类资产孤岛** | 无法追溯完整决策链 | 统一本体模型 + 四层架构：所有资产用同一语言描述 |

---

## 关键设计点（来自 7 大参考系统）

### 1. Knowledge 编译一次（来自 LLM-Wiki-Agent + QMD）

> 知识在 ingest 时编译一次，之后持续复用，而非每次查询重新推理。

- **ingest 时矛盾检测**：新文档入库时立即比对已有知识，标记冲突而非查询时才发现
- **Living overview**：每次 ingest 后自动更新总览，反映最新知识状态
- **两通道图构建**：确定性 wikilink 解析（EXTRACTED）+ LLM 推断隐式关系（INFERRED/AMBIGUOUS）

**技术实现框架**：

```
Ingest Pipeline（参考 LLM-Wiki-Agent tools/ingest.py）:
  1. 读取 Raw Source → SHA256 哈希比对 → 仅处理变化文件
  2. 构建 Wiki 上下文：index.md + overview.md + 最近 5 个源页面
  3. LLM 编译：source_page + entity_pages + concept_pages + overview_update + contradictions
  4. 写入 Wiki 目录 + 图谱节点
  5. 后置验证：断裂 wikilink 检测 + 未索引页面检测

矛盾检测实现：
  - Ingest 时：LLM 编译时同时对比现有 Wiki，输出 contradictions 数组
  - Lint 时：采样 ≤20 页面，LLM 语义检查跨页面矛盾/过时内容/数据缺口
  - Graph-Aware：Hub Stub 检测（度数 > μ+2σ 且内容 < 500 字符）、脆弱桥检测（社区间仅 1 条边）、孤立社区检测

自愈机制（参考 LLM-Wiki-Agent tools/heal.py）：
  - 自动检测缺失实体页面（被 3+ 页面引用但无独立页面）
  - 搜索引用上下文（≤15 源页面，截断 800 字符）
  - LLM 生成实体定义页面
```

**QMD 智能分块算法**（参考 QMD src/store.ts）：

```
分块参数：目标 900 tokens（~3600 字符），重叠 15%（~540 字符），搜索窗口 200 tokens

断点评分体系：
  # H1        → 100 分（主章节边界）
  ## H2       → 90 分
  ### H3 / ``` → 80 分（三级标题/代码块边界）
  #### H4     → 70 分
  --- / ***   → 60 分（水平线）
  空行        → 20 分（段落边界）
  列表项      → 5 分
  换行        → 1 分

距离衰减公式：finalScore = baseScore × (1 - (distance/window)² × 0.7)
  → 平方衰减确保远处标题（30 分）仍胜过近处换行（1 分），但更近标题胜过更远标题
  → 代码围栏保护：不在代码块内部切分

AST 感知分块（参考 QMD src/ast.ts）：
  - web-tree-sitter 实现，支持 TS/JS/Python/Go/Rust
  - class/interface/struct → 100 分，function/method → 90 分，type/enum → 80 分
  - mergeBreakPoints()：regex 断点与 AST 断点合并，同一位置取最高分
  - 优雅降级：tree-sitter 不可用时回退到 regex-only
```

### 2. 三通道提取管线（来自 Graphify + codebase-memory-mcp）

> 确定性提取 + LLM 语义提取分离，SHA256 缓存实现增量处理。

```
Pass 1: 确定性 AST 提取（零 LLM 成本）
  → 类/函数/导入/调用图/文档字符串/注释
  → 按内容 SHA256 缓存

Pass 2: LLM 语义提取（仅处理变化文件）
  → 概念/关系/设计意图/超边/语义相似边
  → Confidence: EXTRACTED(1.0) / INFERRED(0.4-0.9) / AMBIGUOUS(0.1-0.3)
```

**技术实现框架**：

```
SHA256 缓存与增量处理（参考 Graphify cache.py + LLM-Wiki-Agent build_graph.py）：
  - 缓存键：SHA256(文件内容 + 相对路径)，使用相对路径使缓存可跨机器移植
  - Markdown 特殊处理：仅对 YAML frontmatter 以下的 body 内容哈希，元数据变更不使缓存失效
  - 语义缓存：check_semantic_cache() 按 source_file 分组，返回 (cached, uncached) 四元组
  - 推断检查点：.inferred_edges.jsonl（JSONL 格式，每行一个页面的推断结果），支持 resume
  - 原子写入：os.replace() 实现原子替换

置信度标签体系（参考 Graphify validate.py）：
  EXTRACTED  → 源码中明确存在（import 语句、直接调用），confidence_score = 1.0
  INFERRED   → 合理推断（调用图二遍扫描、上下文共现），附带 0.0-1.0 confidence_score
  AMBIGUOUS  → 不确定关系，标记为需人工审查

去重策略（参考 LLM-Wiki-Agent build_graph.py）：
  - 双向边合并：(min(a,b), max(a,b)) 作为 key
  - 保留最高置信度的边
  - 文件内去重（AST seen_ids）+ 文件间去重（NetworkX add_node 幂等性）+ 语义合并

codebase-memory-mcp 的 RAM-first 管线设计（参考 C 实现）：
  - 全部索引在内存中运行（LZ4 HC 压缩读取、内存 SQLite、最后一次性 dump）
  - 7 遍索引流水线：Discover → Structure → Bulk load → Definitions → Resolve → Post-passes → Dump
  - 原子自旋锁防止同一 DB 文件上的并发 pipeline 运行
  - 66 种语言 tree-sitter 语法编译进二进制，无需运行时安装
```

### 3. 倒锥形拓扑 + Bundle Search（来自 m_flow）

> 检索从尖端（原子断言）进入，在底部（完整场景）着陆。

```
         Tip (精确匹配)
              ↓
    FacetPoint + Entity  ← 向量检索入口
              ↓
    Facet  ← 维度分类
              ↓
    Episode  ← 最终着陆（完整知识单元）
```

Bundle Search 核心机制：
- **最小成本路径**：一条强证据链即可证明相关性
- **直接命中惩罚**：直接匹配 Episode 摘要需要额外惩罚，优先精确路径
- **边语义参与检索**：边文本向量化后参与路径评分

**技术实现框架**：

```
Bundle Search 四阶段算法（参考 m_flow bundle_search.py）：

Phase 1 — 宽网撒播：
  查询嵌入同时搜索 7 个向量集合：
  [Episode_summary, Facet_search_text, Facet_anchor_text,
   FacetPoint_search_text, Entity_name, Concept_name, RelationType_relationship_name]
  每个集合返回最多 100 个候选（wide_search_top_k=100）

Phase 2 — 投影到图：
  命中节点作为入口，提取周围子图，再扩展一跳邻居
  两阶段投影：命中 ID 投影 → 邻居扩展并按类型优先级排序（Episode > Facet > FacetPoint > Entity）

Phase 3 — 代价传播：
  从尖端向基底传播代价，对每个 Episode 评估所有可能路径
  路径代价 = 起始代价(锚点向量距离) + Σ(边代价 + 跳惩罚 0.05) + 未命中惩罚(0.9)

Phase 4 — 排序组装：
  按 bundle cost 排序取 top-k，根据 display_mode 组装输出

五种路径类型：
  direct_episode  → Episode 本身（但有惩罚 0.3）
  facet           → Facet → Episode
  point           → FacetPoint → Facet → Episode
  entity          → Entity → Episode
  facet_entity    → Entity → Facet → Episode

Facet 近似匹配折扣：
  当 Facet 向量距离 < 0.1 时，边代价和跳代价大幅折扣（分别降至 0.1 和 0.05）

自适应评分（参考 m_flow adaptive_scoring.py）：
  每个向量集合计算置信度 = f_dist(ratio) × f_gap(gap)
  按类型（node/edge）聚合，动态分配权重 W_node / W_edge
  最终评分：final = λ × semantic + (1-λ) × struct
  λ 由置信度、精确匹配、Gap 等多因素动态计算
```

### 4. 时序多图（来自 MAMGA）

> 事件节点通过时序、语义、因果关系链接，支持"某时点为真"查询。

- **时序链接**：PRECEDES/SUCCEEDS（严格顺序）+ TEMPORALLY_CLOSE（proximity 加权）
- **因果链接**：LEADS_TO / BECAUSE_OF / ENABLES / PREVENTS
- **双通道处理**：快速路径（同步写入）+ 慢速路径（后台推理）

**技术实现框架**：

```
时序共振图节点类型（参考 MAMGA trg_memory.py）：
  EVENT     → 原子事件节点，对应对话中的单个 turn
  EPISODE   → 语义分组的片段节点，由多个相关 EVENT 聚合
  NARRATIVE → 叙事节点，时间窗口内 ≥3 个事件时自动生成
  ENTITY    → 实体节点（人、地点、组织）
  SESSION   → 会话摘要节点，代表一次完整对话会话

四类链接类型系统（参考 MAMGA graph_db.py）：
  TEMPORAL: PRECEDES/SUCCEEDS(携带 time_delta) + TEMPORALLY_CLOSE(携带 time_diff_hours, weight 反比衰减)
  SEMANTIC: RELATED_TO/SIMILAR_TO + PART_OF/CONTAINS + SAME_ENTITY(多跳推理关键) + CONTEXT_NEIGHBOR
  CAUSAL:   LEADS_TO/BECAUSE_OF/ENABLES/PREVENTS + RESPONSE_TO/ANSWERED_BY(Q&A 模式检测)
  ENTITY:   REFERS_TO/MENTIONED_IN

双通道处理实现（参考 MAMGA trg_memory.py）：
  快速通道（Synaptic Ingestion）：
    - 不调用 LLM，直接创建 EventNode
    - 仅执行：节点创建 → 时序链接（PRECEDES）→ 向量索引
    - 将节点 ID 入队 consolidation_queue
    - 设计目标：非阻塞、即时响应

  慢速通道（Structural Consolidation）：
    - 从 consolidation_queue 取出待处理节点
    - 获取 2 跳邻域
    - LLM 推断潜在因果关系（_infer_latent_edges）
    - 创建实体边（_create_entity_edges）
    - 设计目标：后台推理、发现隐含连接

多阶段检索（参考 MAMGA query_engine.py）：
  向量搜索 → 关键词搜索 → 全扫描 → RRF 融合 → 自适应图遍历 → 重排序
  自适应参数：根据查询类型（multi_hop/temporal/entity/causal/activity/factual）调整 max_depth、similarity_threshold、scoring_weights
  概率束搜索：根据查询意图（WHY/WHEN/ENTITY）设置注意力权重，计算转移概率 p = λ₁×structural_alignment + λ₂×semantic_affinity
```

### 5. Verbatim 存储 + Validity Window（来自 MemPalace）

> 原文完整存储不摘要，元数据过滤提供 34% 检索提升。

- **Wing/Room/Hall/Drawer 分层**：元数据本身提供检索 boost，而非仅靠语义相似度
- **Validity window**：事实带 valid_from / valid_to，支持历史时点查询
- **4 层记忆栈**：L0（身份~50 tokens）→ L1（关键事实~120）→ L2（按需房间召回）→ L3（深度语义搜索）

**技术实现框架**：

```
Wing/Room/Hall/Drawer 分层实现（参考 MemPalace miner.py）：
  Palace → Wing（项目/知识领域）→ Room（主题/方面）→ Drawer（原文块 800 字符/块，100 字符重叠）
  Hall → 跨 Wing 的走廊，连接不同领域中相同主题的 Room
  文件路由逻辑（按优先级）：
    1. 文件夹路径匹配 room 名称
    2. 文件名匹配 room 名称或关键词
    3. 内容关键词评分
    4. 回退到 "general"

4 层记忆栈实现（参考 MemPalace layers.py）：
  L0 Identity（~100 tokens）：始终加载，读取 identity.txt（用户手写身份描述）
  L1 Essential Story（~500-800 tokens）：始终加载，按 importance/emotional_weight 排序取 top 15 drawer
  L2 On-Demand（~200-500 tokens/次）：按 wing/room 过滤的 ChromaDB 检索，不做语义搜索
  L3 Deep Search（无限制）：完整 ChromaDB 语义搜索 + wing/room 过滤

  MemoryStack 统一接口：
    stack.wake_up()                # L0 + L1，唤醒成本约 600-900 tokens
    stack.recall(wing="my_app")    # L2
    stack.search("pricing change") # L3

Validity Window 实现（参考 MemPalace knowledge_graph.py）：
  每个 triple 携带 valid_from 和 valid_to 时间戳
  invalidate() 方法设置 valid_to，标记事实不再为真
  查询时通过 as_of 参数获取特定时间点的事实
  示例：kg.add_triple("Max", "has_issue", "sports_injury", valid_from="2026-01", valid_to="2026-02")

96.6% R@5 的核心机制：
  - Verbatim 原文存储（永不摘要）+ ChromaDB 语义搜索 + 分层加载策略
  - 元数据过滤（wing/room）提供额外检索 boost
  - AAAK 压缩模式是有损摘要，原文无法从 AAAK 输出重建
```

### 6. Expert Rules DSL（来自 KAG）

> 业务逻辑表达为规则，在图遍历时动态计算。

```yaml
Define (s:Person)-[p:developed]->(o:App) {
  STRUCTURE {
    (s)-[:hasDevice]->(d:Device)-[:install]->(o)
  }
  CONSTRAINT {
    deviceNum = group(s,o).count(d)
    R1("设备超过5"): deviceNum > 5
  }
}
```

- **逻辑边与事实边分离**：事实边存储，逻辑边按需计算
- **ExternalGraphLoader**：外部领域知识图谱可挂载为先验知识

**技术实现框架**：

```
SPG Schema 四种类型（参考 KAG Schema 文档）：
  EntityType   → 定义实体属性和关系，属性值为基础类型或概念类型
  ConceptType  → 描述分类体系，通过 hypernymPredicate: isA 定义上下位关系
  EventType    → 支持多属性事件（time/location/subject/object/cause/process/outcome）
  IndexType    → 定义索引节点（KnowledgeUnit/AtomicQuery），属性可声明 index: TextAndVector

逻辑边 vs 事实边分离实现：
  事实边：显式存在于原始数据中，直接持久化到图数据库
  逻辑边：通过 DSL 规则从事实边推导，推理时实时计算生成
  推理查询转换：逻辑形式 get_spo(s=s1:Person, p=belongTo, o=TaxOfRiskUser)
    → Cypher MATCH (s1:Person)-[p1:belongTo]->(o1:TaxOfRiskUser) WHERE s1.id="张三" RETURN o1
    → 触发 OpenSPG 推理引擎实时计算逻辑边结果

IndexManager 三层框架（参考 KAG v0.8）：
  Extractor     → 构建阶段从原始数据抽取索引信息写入知识图谱
  Retriever     → 问答阶段使用适合该索引的检索方法从图谱检索
  IndexManager  → 管理索引元数据，负责创建 Extractor 和 Retriever 配置
  内置索引类型：summary_index（基于摘要）、kag_hybrid_index（文本块+图谱混合）
  可通过继承 KAGIndexManager 注册自定义索引

KnowledgeUnit + AtomicQuery 桥接结构：
  KnowledgeUnit → 文本中更纯粹、独立的命题提取（概念性/事实性/过程性/推理性知识）
  AtomicQuery   → 可通过单一知识单元回答的子问题，弥合"陈述句"与"问题式查询"的语义鸿沟
  关系：relatedQuery→AtomicQuery, semantictype→SemanticConcept, coreEntity→Entity

ExternalGraphLoader 领域知识挂载：
  三大基础能力：加载导入 + 辅助 NER + 实体链指
  ner(content)：基于 jieba 分词 + 字符串匹配，在领域知识图谱词汇表中识别实体
  match_entity(query)：支持 text_match 和 vector_match，通过 MatchConfig 控制返回数量/阈值
```

### 7. 多 Agent 并行分析（来自 Understand-Anything + Cognee）

> 可插拔 IndexManager 框架 + 并行 Agent 管线。

- **Extractor-Retriever 可插拔架构**：每种索引类型有独立的 Extractor、Retriever、IndexManager
- **5 并发 Agent**：每次处理 20-30 个文件，结果写盘而非返回 context
- **增量更新**：基于树结构的指纹检测，只重分析变化文件

**技术实现框架**：

```
多 Agent 流水线（参考 Understand-Anything）：
  project-scanner    → 发现文件、检测语言和框架
  file-analyzer      → 提取函数、类、导入，生成图节点和边
  architecture-analyzer → 识别架构层
  tour-builder       → 生成引导式学习导览
  graph-reviewer     → 验证图完整性和引用完整性
  domain-analyzer    → 提取业务域、流程和步骤

Cognee ECL 管道范式（参考 cognee/pipelines/）：
  Extract → Cognify → Load
  V2 记忆导向 API：remember → recall → forget → improve

  Cognify 6 步管道：
    1. classify_documents（文档分类）
    2. extract_chunks_from_data（文本分块，支持 TextChunker/CsvChunker/LangchainChunker）
    3. extract_graph_from_data（LLM 实体/关系抽取）
    4. summarize_text（层次化摘要）
    5. add_data_points（持久化到图+向量 DB）
    6. extract_dlt_fk_edges（DLT 外键边抽取）

  时序认知管道（temporal_cognify=True）：
    extract_events_and_timestamps → extract_knowledge_graph_from_events

  DataPoint 基类设计：
    - 版本管理（version, updated_at）
    - 元数据驱动索引（metadata.index_fields, metadata.identity_fields）
    - 确定性 ID 生成（uuid5 基于 identity_fields）
    - 来源溯源（source_pipeline, source_task, source_user, source_content_hash）
    - 反馈权重（feedback_weight, importance_weight）

  BaseRetriever 三步检索管道：
    get_retrieved_objects(query) → get_context_from_objects(query, objects) → get_completion_from_context(query, context)

  检索器注册机制（策略模式）：
    use_retriever(SearchType, RetrieverClass) 将搜索类型映射到具体检索器实现
    已有：chunks_retriever, completion_retriever, cypher_search_retriever, lexical_retriever,
          summaries_retriever, temporal_retriever, triplet_retriever, coding_rules_retriever

  分布式切换：@override_run_tasks(run_tasks_distributed) 装饰器，COGNEE_DISTRIBUTED=True 时透明切换到 Modal 分布式执行
```

---

## 五层架构详解

### L0：数据源层

原始文档/IT 系统/代码仓/日志/对话/API 元数据/监控数据。

### L1：知识编译层（对应 Layer-R 入口）

**核心思想**：把"按需检索"改成"预编译知识"。

```
Raw Sources → Ingest Agent → Wiki 页面 + 图谱节点
                              ↓
                        矛盾检测 + 增量更新
```

- **Wiki 模板**：文档/指标/API/代码/监控/经验各有对应结构
- **Ingest Agent**：监听新数据，根据类型调用模板，生成或更新 Wiki 页面
- **矛盾检测**：ingest 时立即比对已有知识，标记冲突

### L2：知识表示与存储层（Layer-R + Layer-S）

| 组件 | 作用 | 来源 |
|------|------|------|
| **向量索引** | 未知/模糊问题的入口点，覆盖广度 | MemPalace |
| **知识图谱** | 实体/关系/规则，多跳推理载体 | KAG + Graphify |
| **时序版本** | 事实的 valid_from/to，历史查询 | MAMGA + MemPalace |
| **长期记忆** | Agent 交互产生的经验沉淀 | M-Flow + MemPalace |

### L3：推理与执行层

**四阶段检索‑推理流水线**：

```
① 向量检索 → ② 图遍历 → ③ 记忆注入 → ④ LLM 推理
```

**输出形式**：
- 回答文本
- 执行计划 / 流程图
- SQL / 代码变更
- 工具调用序列
- 仿真结果

**规则/分析逻辑三种载体**：
1. **规则/本体化表达**：用 KG 本体语言表达概念层级、约束、指标推导
2. **可执行 Playbook**：YAML/DSL 描述诊断/分析流程及对应工具调用
3. **经验性自然语言**：结构化"案例 + 教训 + 注意事项"，由 LLM 在执行时解释

### L4：Agent 协同与应用层

**Producer Agents**：
- **Ingest/Compiler Agent**：抽取新文档/代码/接口，更新 Wiki + 图谱
- **Refiner Agent**：负责清洗冲突知识、做一致性检查（例如两个指标口径冲突时发起人工审查）；
- **Memory Curator Agent**：从对话和执行轨迹中筛选"值得升级为长期知识"的内容

**Consumer Agents**：
- **分析/诊断 Agent**：构建查询 → 四层检索流水线 → 产出结构化结果
- **执行 Agent**：根据决策调用外部系统（CI/CD、工单、CRM、ERP）

**编排层（Orchestration / Multi‑Agent Frameworks）​**：
LangGraph / CrewAI / MCP 协议，通过知识引擎共享上下文。
- Agent 间的任务分派与消息传递；
- 上下文共享（通过知识引擎读写，而不是互相塞 prompt）；
- 监控与安全（权限、审计、重试）。

---

## 关键操作旅程

### 旅程 1：用户上传文档 → 完成知识编译（LLM-Wiki 模式）

```
用户操作：
  1. 上传 PDF/PPT/Markdown 到 Dataset
  2. 触发 ingest

系统响应：
  Raw Sources → Ingest Agent → Wiki 页面 + 图谱节点
                              ↓
                        矛盾检测（发现冲突？标记待确认）
                              ↓
                        增量更新（SHA256 缓存，只处理变化文件）

用户看到：
  - 新增实体页 / 概念页 / 关系页
  - 矛盾警告（如有）
  - 溯源链接：每个实体 → 来源文档 + 段落偏移
```

### 旅程 2：用户问"这个企业的税务风险如何"（L3 推理 + L4 协同）

```
用户操作：
  1. 自然语言提问

系统响应（四阶段检索‑推理）：
  ① Layer-R 向量检索
     ChromaDB 查询 → 相关碎片（年报 PDF、申报记录）

  ② extracted_from 扩展
     碎片 → 对应 EntityInstance（税务指标实体）

  ③ Layer-S 推理
     EntityInstance → Indicator 计算 → RuleEngine 执行

  ④ trace_to 回溯
     推理步骤 → 来源碎片（提供证据）

用户看到：
  - 税务风险等级结论
  - 证据链（哪些文档支撑）
  - 执行快照（每步推理路径）
```

### 旅程 3：Claude Agent 查询"授信额度建议"（MCP 协议）

```
Agent 操作（MCP 工具调用）：
  oe_query("授信额度", entity_id="ent_001")

系统响应：
  ① Layer-R 检索 → 相关财务数据碎片
  ② Layer-S 推理 → 计算 credit_score + debt_ratio
  ③ RuleEngine 执行 → 应用授信规则
  ④ MCP 返回：
     - 结论（建议授信 500 万）
     - evidence（碎片溯源列表）
     - execution_snapshot（推理链）

Agent 后续：
  基于结论生成报告 / 调用外部 API / 写入工单
```

### 旅程 4：Agent 自动沉淀个人经验（作业即沉淀）

```
Agent 操作：
  1. 用户多次要求"关注发票金额波动"
  2. 系统检测：usage_count ≥ 20，confidence ≥ 0.8

系统响应：
  - 自动标记 candidate_for_organization: true
  - 通知知识管理员评审

专家评审：
  - 审核通过 → 发布为组织规则 v2.2
  - 审核拒绝 → 反馈理由，自动优化

知识闭环：
  个人经验 → 候选组织资产 → 评审发布 → 所有用户共享
```

### 旅程 5：Code Agent 分析代码仓（Graphify 模式）

```
Agent 操作：
  /graphify <path> --mcp

系统响应：
  Pass 1: 确定性 AST 提取（零 LLM 成本）
    → 类/函数/导入/调用图/注释
    → SHA256 缓存

  Pass 2: LLM 语义提取（仅变化文件）
    → 概念/关系/超边/语义相似边
    → Confidence 标签

Agent 查询：
  query_graph("风险传导路径", entity="ent_A")
  → BFS 遍历图，返回最短路径
  → 每个节点带 confidence 标签

Agent 后续：
  基于图路径生成重构建议 / 影响分析报告
```

### 旅程 6：多 Agent 协同完成风险识别（编排层）

```
编排器（LangGraph/CrewAI）：
  1. Ingest/Compiler Agent → 读取最新财报，更新 Wiki
  2. 分析/诊断 Agent → 查询担保圈，执行风险规则
  3. 执行 Agent → 生成风险报告，写入工单系统

共享记忆：
  所有 Agent 通过 OntologyEngine 读写：
  - 不共享私有 prompt
  - 通过 MCP 工具访问统一知识视图
  - 每次操作记录到 trace_to 链路
```

### 交互模式总结

| 触发方 | 操作 | 系统响应 | 典型输出 |
|--------|------|---------|---------|
| **用户** | 上传文档 | Ingest Agent 编译 | Wiki 页面 + 图谱节点 |
| **用户** | 自然语言提问 | 四阶段推理流水线 | 结论 + 证据链 + 执行快照 |
| **Agent** | MCP 工具调用 | Layer-R/S 检索 + 推理 | 结构化结论 + 溯源 |
| **Agent** | 多次重复操作 | 使用次数累积 | 候选组织资产标记 |
| **系统** | 夜间异步扫描 | 矛盾检测 | 矛盾报告 → 管理员确认 |
| **编排器** | 多 Agent 任务分派 | 共享知识 + 分头执行 | 端到端业务作业完成 |

---

## 资产融合、隔离与转换机制

### 融合：统一知识表示与推理

三类资产通过 KGML Schema 统一描述：

```yaml
entities:
  - name: LoanApplication
    # IT 资产：数据源
    source:
      type: database_table
      table: loan_applications
    # 个人资产：归类规则
    personal_categories:
      - name: high_risk_customer
        owner: user_123
        rule: "annual_income < 50000 AND debt_ratio > 0.7"
    # 组织资产：业务规则
    organization_rules:
      - name: credit_limit_formula
        version: v2.1
        formula: |
          IF (credit_score >= 700 AND annual_income >= 100000)
          THEN min(annual_income * 0.5, 500000)
```

### 隔离：保护边界与权限

| 维度 | IT 资产 | 个人资产 | 组织资产 |
|------|---------|----------|---------|
| **访问权限** | 按角色 | 仅本人 | 按角色 |
| **修改权限** | 数据管理员 | 本人自由 | 规则管理员审批 |
| **可见性** | 部分敏感 | 完全隐私 | 组织内公开 |
| **删除策略** | 数据保留策略 | 随时删除 | 保留历史版本 |

### 转换：个人→组织的知识沉淀闭环

```
个人经验（动态）
    ↓ 累积验证（使用次数 + 置信度提升）
候选沉淀（candidate_for_organization: true）
    ↓ 专家评审
组织资产（规范）
    ↓ 广泛应用
通用知识（共享）
    ↓ 持续优化
```

---

## 四层推理跃迁

| 层级 | 能力 | 对应资产层 | 示例 |
|------|------|-----------|------|
| **L1 事实层** | 存储实体关系 | IT 资产（数据实例化） | 供应商X向Y供货 |
| **L2 归类层** | 业务分类打标 | 个人知识（专家分类） | 行业=制造业，规模=中型 |
| **L3 分析层** | 计算指标评分 | 个人→组织（经验量化） | 供应商信用分85 |
| **L4 决策层** | 生成业务建议 | 组织级资产（规则执行） | 建议授信额度500万 |

---

## 技术哲学

1. **Schema 即代码** —— 业务知识用声明式 YAML 定义，非硬编码
2. **本地优先** —— 单机可运行百万级节点，零外部依赖
3. **AI Native** —— 为 Agent 设计 Memory 接口，非事后兼容
4. **资产可链接** —— 三层知识资产通过统一本体模型实现可推理关联
5. **作业即沉淀** —— Agent 交互本身就是知识生产过程
6. **Knowledge 编译一次** —— ingest 时处理变化文件，存量不变
7. **Verbatim 优先** —— 原文完整存储，96.6% R@5 验证
8. **世界模型观** —— 把知识当"可编译、可查询、可执行、可记忆、可治理的领域世界模型"
9. **语义空间隔离** —— 多域知识通过混合隔离（逻辑+物理）管理，域间实体对齐实现跨域协同
10. **人工可管理** —— 自动化只是第一层，知识全链路可读、可见、可管理、可调整
11. **业务逻辑资产化** —— 风险评估、指标计算、图分析逻辑等业务逻辑是一等知识资产，双层表达（Schema 内嵌+图节点）
12. **模块解耦优先** —— 模块设计优先解耦，保证扩展性，不同知识要素之间的运转逻辑和关联影响显式化

---

## 上下文栈定位

OntologyEngine 在 AI Agent 的上下文栈中占据**深度推理层**：

```
┌──────────────────────────────────────────────────────────────┐
│  连续性层 (Memory)                                          │
│  ── 跨会话状态、用户偏好、学习到的事实                          │
│  ── 类比 m-flow Procedural Memory                          │
├──────────────────────────────────────────────────────────────┤
│  广度层 (RAG)                                               │
│  ── 文档检索、知识密集型问答                                  │
│  ── 类比传统向量检索系统                                      │
├──────────────────────────────────────────────────────────────┤
│  ★ 深度推理层 (OntologyEngine) ★                           │
│  ── 实体关系、多跳推理、规则执行、三层资产链接                  │
│  ── 类比 m-flow Episodic Memory + KAG Logical Form          │
└──────────────────────────────────────────────────────────────┘
```

---

## 行业对标

| 方案 | 能力 | OntologyEngine 差异 |
|------|------|---------------------|
| **Microsoft GraphRAG** | 文档→图结构→多跳检索 | OntologyEngine 侧重业务规则推理，融合三类资产 |
| **M-flow** | 四层 cone graph + Bundle Search | OntologyEngine 增加个人资产隔离、组织资产转换 |
| **KAG** | 逻辑形式引导推理 + 互索引结构 | OntologyEngine 增加三类资产融合、作业即沉淀闭环 |
| **Drools** | 规则执行引擎 | 无图计算、无向量检索、无知识沉淀闭环 |
| **MemPalace** | 对话记忆持久化 | 扁平存储，无结构化推理，无资产转换机制 |
| **LightRAG** | 双层图 + 混合检索 | 无规则引擎，无三类资产链接 |

> **核心差异**：OntologyEngine 是唯一同时具备 —— ① 三类资产融合、② knowledge 编译一次、③ 关系语义参与推理、④ 确定推理与传递推理双模式、⑤ 作业即知识沉淀闭环、⑥ 五层架构统一 —— 的系统。

---

## 深度启示：参考系统与 OntologyEngine 的对齐分析

### 启示 1：语义空间隔离——从单域到多域

参考系统大多面向单域场景（MAMGA=对话记忆、MemPalace=个人知识、Graphify=代码分析），OntologyEngine 需要同时管理多个业务域的知识。

**对齐分析**：

| 参考系统 | 隔离模式 | OntologyEngine 适配 |
|----------|---------|-------------------|
| m_flow/cognee | Dataset 物理隔离 + ContextVar 请求级切换 | **采纳**：domain_id 逻辑隔离 + 可选物理隔离 |
| MemPalace | Wing/Room/Hall 元数据标签过滤 | **采纳**：domain_id + sub_domain 元数据过滤 |
| MAMGA | SESSION 节点逻辑隔离 | **部分采纳**：session 级记忆隔离，但不作为域隔离手段 |

**OntologyEngine 独有设计**：
- 混合隔离策略：默认逻辑隔离（domain_id 过滤），可选物理隔离（独立 DB），通过配置切换
- 跨域实体对齐：same_entity_as 边连接不同域中的同一实体，支持跨域查询自动扩展
- ContextVar 模式：参考 m_flow，请求级数据库配置切换，协程安全

### 启示 2：知识全链路可管理性——自动化只是第一层

参考系统在人工介入方面有四种角色模型：审核者、纠正者、领域专家、反馈者。

**对齐分析**：

| 人工介入机制 | 参考系统 | OntologyEngine 适配 |
|-------------|---------|-------------------|
| 声明式规则编辑 | KAG Expert Rules DSL | **简化采纳**：结构化配置参数+合理表达式，非严格 DSL |
| 反馈闭环 | Cognee feedback_weight + alpha 学习率 | **采纳**：检索结果评分→节点/边权重更新 |
| 质量检测+自愈 | LLM-Wiki-Agent lint+heal | **采纳**：lint→heal 循环，AMBIGUOUS 边引导人工审查 |
| 知识时效管理 | MemPalace invalidate() | **采纳**：valid_from/valid_to，invalidate 而非 delete |
| Schema 验证 | Graphify validate_extraction() | **采纳**：前置门禁，阻止不合规数据进入图谱 |

**OntologyEngine 独有设计**：
- 规则表达式：结构化配置参数+合理表达式（非严格 DSL），降低领域专家使用门槛
- 知识质量管理五阶段：摄入→验证→检测→修复→演化，形成可持续的质量管理闭环
- 人工可调节性三维度：可见性（Lint 报告+图可视化）、可管理性（直接编辑+精确删除）、可调节性（配置驱动+权重可调）

### 启示 3：业务逻辑资产化——双层表达

参考系统在业务逻辑表达方面有五种基本模式：规则即边、规则即节点、规则即 Schema、规则即文档结构、规则即检索策略。

**对齐分析**：

| 表达模式 | 参考系统 | OntologyEngine 适配 |
|---------|---------|-------------------|
| 规则即边 | KAG 逻辑边实时计算 | **采纳**：Schema 内嵌规则定义，逻辑边按需计算 |
| 规则即节点 | m_flow Procedure + Cognee Rule DataPoint | **采纳**：规则也作为图节点存储，可编辑、可版本化 |
| 规则适用性边界 | m_flow ContextPack (when/why/boundary) | **采纳**：规则节点携带适用性六维度 |
| 规则溯源 | Cognee DataPoint.source_pipeline/task | **采纳**：规则节点携带来源溯源字段 |
| 规则版本管理 | m_flow supersedes 边 | **采纳**：规则版本链追踪 |

**OntologyEngine 独有设计**：
- 双层表达：Schema 内嵌规则定义（逻辑边实时计算）+ 规则图节点（可编辑、可版本化、可溯源）
- 规则表达式简化：结构化配置参数+合理表达式，不使用严格 DSL
- 规则适用性六维度：when（何时触发）、why（为何存在）、boundary（边界限制）、outcome（预期结果）、prereq（前置条件）、exception（异常处理）

### 启示 4：知识要素运转逻辑——跨层交互与依赖

参考系统揭示了知识要素之间的五种核心交互模式。

**对齐分析**：

| 交互模式 | 参考系统 | OntologyEngine 适配 |
|---------|---------|-------------------|
| 分层聚合与语义浓缩 | m_flow Episode→Facet→FacetPoint | **采纳**：EntityInstance→Categorization→AnalyticalElement |
| 边语义参与检索 | m_flow edge_text 向量化 | **采纳**：边文本向量化后参与 Bundle Search 评分 |
| 查询桥接 | KAG AtomicQuery | **采纳**：互索引边实现 Layer-R↔Layer-S 双向导航 |
| 双通道处理 | MAMGA 快速/慢速路径 | **采纳**：IngestionService 双通道 |
| 实体链接 | m_flow same_entity_as | **采纳**：跨域实体对齐 + 跨 Episode 实体互连 |

**OntologyEngine 独有设计**：
- 知识要素依赖矩阵：下层决定上层索引字段、上层依赖下层存在性、边依赖两端节点、检索依赖索引完备性、路由依赖查询分类
- 跨域实体对齐：不同域中相同实体通过 canonical_name + same_entity_as 边互连
- 自适应查询路由：参考 MAMGA detect_query_type()，根据查询类型动态调整遍历深度、链接偏好和评分权重

---

## 参考来源

| 参考系统 | 关键贡献 | 引入位置 |
|----------|---------|---------|
| **LLM-Wiki-Agent** | ingest 时矛盾检测、knowledge 编译一次、两通道图构建 | L1 编译层 |
| **KAG** | SPG Schema、Expert Rules DSL、逻辑边计算、IndexManager | L2/L3 架构 |
| **m_flow** | 倒锥形拓扑、Bundle Search、最小成本路径、边语义参与 | L3 检索机制 |
| **MAMGA** | 时序多图、causal 链接、长期会话记忆 | L2 时序推理 |
| **MemPalace** | verbatim 存储、validity window、wing/room 分层 | L2 存储 |
| **Graphify** | 三通道提取（AST+Whisper+LLM）、SHA256 缓存 | L1 提取管线 |
| **Understand-Anything** | 多 Agent 并行、可插拔 IndexManager | L4 Agent 协同 |

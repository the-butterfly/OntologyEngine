# 7 大参考系统设计展开

> **作用**: 存放 `docs/01-overview/01-vision.md` §关键设计点 中引用的 7 大参考系统实现细节
> **最后更新**: 2026-05-15
> **来源**: 文章《深度解析LLM Wiki / Obsidian-Wiki / GBrain》(飞樰, 2026) + 各参考系统文档 + 本项目长期跟踪研究

---

## 1. LLM-Wiki-Agent + QMD

### Ingest Pipeline

参考 LLM-Wiki-Agent tools/ingest.py：

```
Ingest Pipeline:
  1. 读取 Raw Source → SHA256 哈希比对 → 仅处理变化文件
  2. 构建 Wiki 上下文：index.md + overview.md + 最近 5 个源页面
  3. LLM 编译：source_page + entity_pages + concept_pages + overview_update + contradictions
  4. 写入 Wiki 目录 + 图谱节点
  5. 后置验证：断裂 wikilink 检测 + 未索引页面检测
```

### 矛盾检测

- Ingest 时：LLM 编译时同时对比现有 Wiki，输出 contradictions 数组
- Lint 时：采样 ≤20 页面，LLM 语义检查跨页面矛盾/过时内容/数据缺口
- Graph-Aware：Hub Stub 检测（度数 > μ+2σ 且内容 < 500 字符）、脆弱桥检测（社区间仅 1 条边）、孤立社区检测

### 自愈机制

参考 LLM-Wiki-Agent tools/heal.py：
- 自动检测缺失实体页面（被 3+ 页面引用但无独立页面）
- 搜索引用上下文（≤15 源页面，截断 800 字符）
- LLM 生成实体定义页面

### QMD 智能分块算法

参考 QMD src/store.ts：

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
```

AST 感知分块（参考 QMD src/ast.ts）：
- web-tree-sitter 实现，支持 TS/JS/Python/Go/Rust
- class/interface/struct → 100 分，function/method → 90 分，type/enum → 80 分
- mergeBreakPoints()：regex 断点与 AST 断点合并，同一位置取最高分
- 优雅降级：tree-sitter 不可用时回退到 regex-only

---

## 2. Graphify + codebase-memory-mcp

### 三通道提取管线

```
Pass 1: 确定性 AST 提取（零 LLM 成本）
  → 类/函数/导入/调用图/文档字符串/注释
  → 按内容 SHA256 缓存

Pass 2: LLM 语义提取（仅处理变化文件）
  → 概念/关系/设计意图/超边/语义相似边
  → Confidence: EXTRACTED(1.0) / INFERRED(0.4-0.9) / AMBIGUOUS(0.1-0.3)
```

### SHA256 缓存与增量处理

参考 Graphify cache.py + LLM-Wiki-Agent build_graph.py：
- 缓存键：SHA256(文件内容 + 相对路径)，使用相对路径使缓存可跨机器移植
- Markdown 特殊处理：仅对 YAML frontmatter 以下的 body 内容哈希，元数据变更不使缓存失效
- 语义缓存：check_semantic_cache() 按 source_file 分组，返回 (cached, uncached) 四元组
- 推断检查点：.inferred_edges.jsonl（JSONL 格式），支持 resume
- 原子写入：os.replace() 实现原子替换

### 置信度标签体系

参考 Graphify validate.py：
- EXTRACTED → 源码中明确存在，confidence_score = 1.0
- INFERRED → 合理推断，附带 0.0-1.0 confidence_score
- AMBIGUOUS → 不确定关系，标记为需人工审查

### 去重策略

参考 LLM-Wiki-Agent build_graph.py：
- 双向边合并：(min(a,b), max(a,b)) 作为 key
- 保留最高置信度的边
- 文件内去重（AST seen_ids）+ 文件间去重（NetworkX add_node 幂等性）+ 语义合并

### codebase-memory-mcp RAM-first 管线

- 全部索引在内存中运行（LZ4 HC 压缩读取、内存 SQLite、最后一次性 dump）
- 7 遍索引流水线：Discover → Structure → Bulk load → Definitions → Resolve → Post-passes → Dump
- 原子自旋锁防止同一 DB 文件上的并发 pipeline 运行
- 66 种语言 tree-sitter 语法编译进二进制

---

## 3. m_flow Bundle Search

### 倒锥形拓扑

```
         Tip (精确匹配)
              ↓
    FacetPoint + Entity  ← 向量检索入口
              ↓
    Facet  ← 维度分类
              ↓
    Episode  ← 最终着陆（完整知识单元）
```

### Bundle Search 四阶段算法

参考 m_flow bundle_search.py：

**Phase 1 — 宽网撒播**：
查询嵌入同时搜索 7 个向量集合：
- Episode_summary, Facet_search_text, Facet_anchor_text
- FacetPoint_search_text, Entity_name, Concept_name, RelationType_relationship_name
每个集合返回最多 100 个候选（wide_search_top_k=100）

**Phase 2 — 投影到图**：
命中节点作为入口，提取周围子图，再扩展一跳邻居
两阶段投影：命中 ID 投影 → 邻居扩展并按类型优先级排序（Episode > Facet > FacetPoint > Entity）

**Phase 3 — 代价传播**：
从尖端向基底传播代价，对每个 Episode 评估所有可能路径
路径代价 = 起始代价(锚点向量距离) + Σ(边代价 + 跳惩罚 0.05) + 未命中惩罚(0.9)

**Phase 4 — 排序组装**：
按 bundle cost 排序取 top-k，根据 display_mode 组装输出

### 五种路径类型

| 类型 | 路径 | 说明 |
|------|------|------|
| direct_episode | Episode 本身 | 有惩罚 0.3 |
| facet | Facet → Episode | — |
| point | FacetPoint → Facet → Episode | — |
| entity | Entity → Episode | — |
| facet_entity | Entity → Facet → Episode | — |

### 自适应评分

参考 m_flow adaptive_scoring.py：
- 每个向量集合计算置信度 = f_dist(ratio) × f_gap(gap)
- 按类型（node/edge）聚合，动态分配权重 W_node / W_edge
- 最终评分：final = λ × semantic + (1-λ) × struct
- λ 由置信度、精确匹配、Gap 等多因素动态计算

---

## 4. MAMGA 时序多图

### 时序共振图节点类型

参考 MAMGA trg_memory.py：
- EVENT → 原子事件节点，对应对话中的单个 turn
- EPISODE → 语义分组的片段节点，由多个相关 EVENT 聚合
- NARRATIVE → 叙事节点，时间窗口内 ≥3 个事件时自动生成
- ENTITY → 实体节点（人、地点、组织）
- SESSION → 会话摘要节点，代表一次完整对话会话

### 四类链接类型

参考 MAMGA graph_db.py：
- TEMPORAL: PRECEDES/SUCCEEDS(携带 time_delta) + TEMPORALLY_CLOSE(携带 time_diff_hours, weight 反比衰减)
- SEMANTIC: RELATED_TO/SIMILAR_TO + PART_OF/CONTAINS + SAME_ENTITY + CONTEXT_NEIGHBOR
- CAUSAL: LEADS_TO/BECAUSE_OF/ENABLES/PREVENTS + RESPONSE_TO/ANSWERED_BY
- ENTITY: REFERS_TO/MENTIONED_IN

### 双通道处理

参考 MAMGA trg_memory.py：

**快速通道**（Synaptic Ingestion）：
- 不调用 LLM，直接创建 EventNode
- 仅执行：节点创建 → 时序链接（PRECEDES）→ 向量索引
- 将节点 ID 入队 consolidation_queue

**慢速通道**（Structural Consolidation）：
- 从 consolidation_queue 取出待处理节点
- 获取 2 跳邻域
- LLM 推断潜在因果关系
- 创建实体边

### 多阶段检索

参考 MAMGA query_engine.py：
- 向量搜索 → 关键词搜索 → 全扫描 → RRF 融合 → 自适应图遍历 → 重排序
- 自适应参数：根据查询类型调整 max_depth、similarity_threshold、scoring_weights
- 概率束搜索：p = λ₁×structural_alignment + λ₂×semantic_affinity

---

## 5. MemPalace Verbatim 存储

### Wing/Room/Hall/Drawer 分层

参考 MemPalace miner.py：
- Palace → Wing（项目/知识领域）→ Room（主题/方面）→ Drawer（原文块 800 字符/块，100 字符重叠）
- Hall → 跨 Wing 的走廊，连接不同领域中相同主题的 Room
- 文件路由逻辑：文件夹路径匹配 room 名称 > 文件名匹配 > 内容关键词评分 > 回退到 "general"

### 4 层记忆栈

参考 MemPalace layers.py：
- L0 Identity（~100 tokens）：始终加载，读取 identity.txt
- L1 Essential Story（~500-800 tokens）：始终加载，按 importance/emotional_weight 排序取 top 15 drawer
- L2 On-Demand（~200-500 tokens/次）：按 wing/room 过滤的 ChromaDB 检索
- L3 Deep Search（无限制）：完整 ChromaDB 语义搜索 + wing/room 过滤

统一接口：
```
stack.wake_up()                # L0 + L1
stack.recall(wing="my_app")    # L2
stack.search("pricing change") # L3
```

### Validity Window

参考 MemPalace knowledge_graph.py：
- 每个 triple 携带 valid_from 和 valid_to 时间戳
- invalidate() 方法设置 valid_to
- 查询时通过 as_of 参数获取特定时间点的事实
- 96.6% R@5 核心机制：Verbatim 原文存储 + ChromaDB 语义搜索 + 分层加载 + 元数据过滤

---

## 6. KAG Expert Rules DSL

### SPG Schema 四种类型

参考 KAG Schema 文档：
- EntityType → 定义实体属性和关系
- ConceptType → 描述分类体系，通过 hypernymPredicate: isA 定义上下位关系
- EventType → 支持多属性事件（time/location/subject/object/cause/process/outcome）
- IndexType → 定义索引节点（KnowledgeUnit/AtomicQuery）

### 逻辑边 vs 事实边分离

- 事实边：显式存在于原始数据中，直接持久化到图数据库
- 逻辑边：通过 DSL 规则从事实边推导，推理时实时计算生成
- 推理查询转换：逻辑形式 → Cypher MATCH → 触发推理引擎

### IndexManager 三层框架

参考 KAG v0.8：
- Extractor → 构建阶段从原始数据抽取索引信息
- Retriever → 问答阶段使用适合该索引的检索方法
- IndexManager → 管理索引元数据
- 内置索引类型：summary_index、kag_hybrid_index（文本块+图谱混合）

### KnowledgeUnit + AtomicQuery 桥接

- KnowledgeUnit → 文本中纯粹的命题提取
- AtomicQuery → 可通过单一知识单元回答的子问题
- 关系：relatedQuery→AtomicQuery, semantictype→SemanticConcept, coreEntity→Entity

### ExternalGraphLoader

三大基础能力：加载导入 + 辅助 NER + 实体链指

---

## 7. Understand-Anything + Cognee

### 多 Agent 流水线

参考 Understand-Anything：
- project-scanner → 发现文件、检测语言和框架
- file-analyzer → 提取函数、类、导入，生成图节点和边
- architecture-analyzer → 识别架构层
- tour-builder → 生成引导式学习导览
- graph-reviewer → 验证图完整性和引用完整性
- domain-analyzer → 提取业务域、流程和步骤

### Cognee ECL 管道范式

参考 cognee/pipelines/：
- Extract → Cognify → Load
- V2 记忆导向 API：remember → recall → forget → improve

Cognify 6 步管道：
1. classify_documents（文档分类）
2. extract_chunks_from_data（文本分块）
3. extract_graph_from_data（LLM 实体/关系抽取）
4. summarize_text（层次化摘要）
5. add_data_points（持久化到图+向量 DB）
6. extract_dlt_fk_edges（DLT 外键边抽取）

### DataPoint 基类

- 版本管理（version, updated_at）
- 元数据驱动索引（metadata.index_fields, metadata.identity_fields）
- 确定性 ID 生成（uuid5 基于 identity_fields）
- 来源溯源（source_pipeline, source_task, source_user, source_content_hash）
- 反馈权重（feedback_weight, importance_weight）

### BaseRetriever 三步检索

```
get_retrieved_objects(query) → get_context_from_objects(query, objects) → get_completion_from_context(query, context)
```

检索器注册机制（策略模式）：use_retriever(SearchType, RetrieverClass)

---

## 参考来源

| 系统 | 原始来源 | 对应 OE 设计文档 |
|------|---------|-----------------|
| LLM-Wiki-Agent | Karpathy gist | `02-design/services/ingestion-service.md` |
| QMD | tobi/qmd | `02-design/extraction-pipeline/` |
| Graphify | — | `02-design/extraction-pipeline/` |
| m_flow | — | `02-design/query-engine/bundle-search.md` |
| MAMGA | — | `02-design/schema/temporal-modeling.md` |
| MemPalace | — | `02-design/storage/chromadb-collections.md` |
| KAG | OpenSPG | `02-design/rule-engine/` |
| Understand-Anything | — | `02-design/services/` |
| Cognee | cognee | `02-design/services/` |

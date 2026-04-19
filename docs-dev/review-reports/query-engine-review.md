# 查询引擎设计评审报告

> **status**: draft | **phase**: rewrite | **last_verified**: 2026-04-19

## 评审概述

| 维度 | 内容 |
|------|------|
| 评审对象 | `docs/02-design/query-engine/` 全部 7 篇设计文档 |
| 评审方法 | Overview 对齐 → Baseline 审查 → 参考项目对齐 → 偏差标记 → 重写 |
| 评审日期 | 2026-04-19 |
| 评审结论 | **通过，有条件** — 核心架构与参考项目对齐良好，存在 3 项待解决偏差 |

---

## Step 1：Overview 对齐

### 对齐检查

| 概念文档 | 设计文档 | 对齐状态 | 说明 |
|----------|---------|---------|------|
| 08-knowledge-retrieval.md Layer-R/S 双路 | layer-r-retrieval.md + layer-s-retrieval.md | ✅ 完全对齐 | 双路检索路径、适用场景、检索流程均对齐 |
| 08-knowledge-retrieval.md 查询路由 | query-routing.md | ✅ 完全对齐 | 五种查询类型、特征词、边权重偏好均对齐 |
| 08-knowledge-retrieval.md Bundle Search | bundle-search.md | ✅ 完全对齐 | 四阶段算法、路径成本公式、五种路径类型均对齐 |
| 08-knowledge-retrieval.md RRF 融合 | rrf-fusion.md | ✅ 完全对齐 | 三路融合、k=60、权重分配均对齐 |
| 08-knowledge-retrieval.md 互索引协同 | mutual-index-retrieval.md | ✅ 完全对齐 | 完整协同流程、四种互索引边角色均对齐 |
| 05-concepts.md 查询路由分类 | query-routing.md | ✅ 完全对齐 | factual/multi-hop/temporal/analytical/mixed 均对齐 |
| 05-concepts.md 互索引四种关系 | mutual-index-retrieval.md | ✅ 完全对齐 | EXTRACTED_FROM/SUPPORTED_BY/DEFINED_IN/TRACE_TO 均对齐 |
| 05-concepts.md 时序建模 | layer-s-retrieval.md | ✅ 完全对齐 | valid_from/valid_to、as_of 查询、时间增强均对齐 |

### 对齐结论

Overview 层概念与设计文档完全对齐，无遗漏概念。

---

## Step 2：Baseline 审查

### 当前代码基线

| 文件 | 状态 | 说明 |
|------|------|------|
| `ontology_engine/engine/query/__init__.py` | 占位符 | 仅有 `"""Query engine for KGML queries."""` 一行 |
| 其他查询引擎文件 | 不存在 | 无任何检索实现代码 |

### Baseline 问题清单

| # | 问题 | 严重度 | 设计文档覆盖 |
|---|------|--------|-------------|
| 1 | 查询引擎完全缺失 | 🔴 严重 | README.md 架构总览 |
| 2 | 查询路由未实现 | 🔴 严重 | query-routing.md |
| 3 | Layer-R 向量检索未实现 | 🔴 严重 | layer-r-retrieval.md |
| 4 | Layer-S 图遍历未实现 | 🔴 严重 | layer-s-retrieval.md |
| 5 | Bundle Search 未实现 | 🟡 中等 | bundle-search.md |
| 6 | RRF 融合未实现 | 🟡 中等 | rrf-fusion.md |
| 7 | 互索引协同检索未实现 | 🟡 中等 | mutual-index-retrieval.md |
| 8 | BM25 关键词检索未实现 | 🟢 低 | rrf-fusion.md |
| 9 | Retriever 注册机制未实现 | 🟢 低 | mutual-index-retrieval.md |

---

## Step 3：参考项目对齐

### m_flow 对齐

| m_flow 组件 | OE 对应组件 | 对齐状态 | 偏差说明 |
|-------------|-----------|---------|---------|
| BaseRetriever | RetrieverRegistry | ✅ 对齐 | OE 增加注册机制 |
| EpisodicRetriever | Layer-R Retriever | ✅ 对齐 | m_flow Episode → OE KnowledgeFragment |
| bundle_search.py | bundle-search.md | ✅ 对齐 | 四阶段算法完全对齐 |
| bundle_scorer.py | bundle-search.md Phase 3 | ✅ 对齐 | 路径成本公式对齐 |
| EpisodeBundle | EntityBundle | ✅ 对齐 | 数据结构映射 |
| RelationshipIndex | OE 图关系索引 | ✅ 对齐 | Episode→Entity 映射 |
| AdaptiveScoringContext | 自适应评分 | ✅ 对齐 | f_dist + f_gap + lambda 融合 |
| EpisodicConfig | RetrievalParams | ✅ 对齐 | 参数映射表对齐 |
| MemoryOrchestrator | QueryRouter + 并行双路 | ⚠️ 偏差 | m_flow 三路并行，OE 双路 + BM25 |
| edge_text 向量化 | edge_text 集合 | ✅ 对齐 | ChromaDB edge_text 集合 |
| 时间增强 | 时间增强 | ✅ 对齐 | 时间解析 + 匹配奖励 + 不匹配惩罚 |

### KAG 对齐

| KAG 组件 | OE 对应组件 | 对齐状态 | 偏差说明 |
|----------|-----------|---------|---------|
| IndexManager | RetrieverRegistry | ⚠️ 偏差 | KAG 有产品化配置生成，OE Phase 1 简化 |
| RetrieverABC | BaseRetriever | ✅ 对齐 | 抽象基类模式 |
| DPR+PPR+RRF | Layer-R + Layer-S + RRF | ✅ 对齐 | 五步混合检索简化为三路融合 |
| Extractor+Retriever 配置化 | 无 | ⚠️ 偏差 | OE Phase 1 不实现配置化 |
| AtomicQuery 桥接 | 互索引边 | ✅ 对齐 | 四种专门关系替代单一桥接 |

### Cognee 对齐

| Cognee 组件 | OE 对应组件 | 对齐状态 | 偏差说明 |
|-------------|-----------|---------|---------|
| register_retriever | RetrieverRegistry | ✅ 对齐 | 注册机制对齐 |
| feedback_weight | feedback_weight | ✅ 对齐 | 反馈权重参与评分 |
| source_pipeline | source_pipeline + source_content_hash | ✅ 对齐 | 溯源链对齐 |

---

## Step 4：偏差标记

### 偏差清单

| # | 偏差 | 严重度 | 影响范围 | 解决方案 |
|---|------|--------|---------|---------|
| D-1 | TRACE_TO 源端暂用 EntityNode 而非 ExecutionStepSnapshotNode | 🟡 中等 | mutual-index-retrieval.md、kuzudb-schema.md | Phase 2 增加 ExecutionStepSnapshotNode 后修改 |
| D-2 | Retriever 注册机制简化，无 KAG 式产品化配置生成 | 🟢 低 | mutual-index-retrieval.md | Phase 1 策略模式足够，Phase 2 考虑配置化 |
| D-3 | m_flow 三路并行（atomic+episodic+procedural）vs OE 双路+BM25 | 🟢 低 | README.md | OE 的 procedural 对应 RuleEngine，不作为独立检索路 |

### 偏差评估

- **D-1** 是已知限制，在 `kuzudb-schema.md` 中已标注 `[待扩展]`
- **D-2** 是 Phase 1 有意简化，不影响核心检索功能
- **D-3** 是架构差异，OE 的 RuleEngine 等价于 m_flow 的 procedural memory，但走不同路径

---

## Step 5：重写评估

### 存储设计对齐检查

| 检查项 | ChromaDB 对齐 | KuzuDB 对齐 | 状态 |
|--------|-------------|------------|------|
| Layer-R 检索使用 knowledge_fragment 集合 | ✅ | — | 通过 |
| Bundle Search Phase 1 使用 6 个集合 | ✅ | — | 通过 |
| edge_text 集合存储边语义向量 | ✅ | — | 通过 |
| 互索引边向量存储在 edge_text 集合 | ✅ | — | 通过 |
| Layer-S 检索使用 EntityNode + RELATES_TO | — | ✅ | 通过 |
| 时序过滤使用 valid_from/valid_to | — | ✅ | 通过 |
| 互索引边查询使用 4 种关系表 | — | ✅ | 通过 |
| 邻域查询使用 CATEGORIZED_AS + HAS_METRIC | — | ✅ | 通过 |

### 模块边界检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| query engine → storage 直接调用 | ❌ 不违反 | 通过 storage/base.py 接口调用 |
| query engine → engine 直接调用 | ❌ 不违反 | 查询引擎是 engine 的子模块 |
| api → query engine 调用 | ✅ 允许 | api → services → engine/query |

### 文档完整性检查

| 文档 | "目的"小节 | "解决的问题"小节 | 元数据 | 状态 |
|------|-----------|-----------------|--------|------|
| README.md | ✅ | ✅ | ✅ | 通过 |
| query-routing.md | ✅ | ✅ | ✅ | 通过 |
| layer-r-retrieval.md | ✅ | ✅ | ✅ | 通过 |
| layer-s-retrieval.md | ✅ | ✅ | ✅ | 通过 |
| bundle-search.md | ✅ | ✅ | ✅ | 通过 |
| rrf-fusion.md | ✅ | ✅ | ✅ | 通过 |
| mutual-index-retrieval.md | ✅ | ✅ | ✅ | 通过 |

---

## 评审结论

### 通过条件

| # | 条件 | 状态 |
|---|------|------|
| 1 | Overview 概念完全覆盖 | ✅ 通过 |
| 2 | 存储设计完全对齐 | ✅ 通过 |
| 3 | 模块边界无违反 | ✅ 通过 |
| 4 | 参考项目核心机制对齐 | ✅ 通过 |
| 5 | 偏差已标记且有解决方案 | ✅ 通过 |
| 6 | 文档格式规范 | ✅ 通过 |

### 待办事项

| # | 事项 | 优先级 | 阶段 |
|---|------|--------|------|
| 1 | 实现 ExecutionStepSnapshotNode | 高 | Phase 2 |
| 2 | TRACE_TO 源端从 EntityNode 迁移到 ExecutionStepSnapshotNode | 高 | Phase 2 |
| 3 | Retriever 注册机制增加配置化 | 中 | Phase 2 |
| 4 | 本地 Reranker 集成 | 低 | Phase 2 |
| 5 | 查询扩展（HyDE） | 低 | Phase 2 |

### 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Bundle Search 性能不达标 | 中 | 高 | 限制 max_relevant_ids=300；两阶段投影控制子图规模 |
| ChromaDB 多集合并行搜索延迟 | 低 | 中 | asyncio.gather 并行；集合级超时控制 |
| 特征词匹配误路由 | 中 | 低 | 降级策略兜底；mixed 类型覆盖模糊场景 |
| 互索引边数量爆炸 | 低 | 高 | confidence 阈值过滤；跨层跳数惩罚抑制低质量跳转 |

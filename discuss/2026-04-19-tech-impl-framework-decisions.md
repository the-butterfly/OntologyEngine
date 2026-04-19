# 技术实现框架完善决策记录

> **日期**: 2026-04-19
> **范围**: docs/01-overview + docs/02-design 技术实现框架完善
> **参考系统**: llm-wiki-agent/qmd, KAG, m_flow, MAMGA, MemPalace, Cognee, Graphify, codebase-memory-mcp, Understand-Anything

## 关键决策

### 1. 存储架构迁移：DuckDB+Faiss → KuzuDB+ChromaDB+SQLite

**决策**：将主存储从 DuckDB 迁移到 KuzuDB，向量存储从 Faiss 迁移到 ChromaDB，元数据独立到 SQLite。

**依据**：
- Cognee 的 KuzuAdapter（2400+ 行）验证了 KuzuDB 作为嵌入式图数据库的可行性
- m_flow 的 GraphProvider 适配器模式证明了多后端切换的可行性
- MemPalace 验证 ChromaDB 达到 96.6% R@5
- codebase-memory-mcp 验证 SQLite WAL 模式适合元数据管理

**影响**：03-storage-design.md 中 DuckDB/Faiss 相关内容标注"已废弃"，新增 KuzuDB/ChromaDB/SQLite 目标架构设计。

### 2. 检索架构：Bundle Search + DPR+PPR+RRF 混合检索

**决策**：采用 m_flow 的 Bundle Search 四阶段算法作为 Layer-S 图遍历的核心，结合 KAG 的 DPR+PPR+RRF 五步混合检索。

**依据**：
- m_flow 的倒锥形拓扑 + 最小成本路径在 LoCoMo-10 达到 81.8%
- KAG 的 DPR+PPR+RRF 解决了"语义相似≠内容相关"的问题
- QMD 的 BM25+向量+RRF 验证了本地混合检索的可行性

### 3. 边语义参与检索

**决策**：边文本向量化后参与检索评分，未命中边施加 miss_penalty。

**依据**：
- m_flow 的 Edge.edge_text 设计是核心突破，边不再是被动连接器而是主动语义过滤器
- 在代价传播中，语义不相关的边贡献高代价，有效阻断路径

### 4. 双通道处理：快速路径+慢速路径

**决策**：IngestionService 采用 MAMGA 的双通道处理模式。

**依据**：
- MAMGA 的快速路径（同步写入）保证非阻塞即时响应
- 慢速路径（后台推理）发现隐含连接
- consolidation_queue 机制解耦了写入和推理

### 5. 置信度标签体系

**决策**：采用 Graphify 的 EXTRACTED/INFERRED/AMBIGUOUS 三级置信度标签。

**依据**：
- Graphify 验证了确定性提取与概率性提取分离的可行性
- LLM-Wiki-Agent 的两通道图构建（EXTRACTED wikilink + INFERRED LLM 推断）提供了具体实现参考
- 置信度标签让用户区分"发现的"vs"猜测的"

### 6. 管道编排模式

**决策**：采用 Cognee 的 ECL 管道范式 + Task 三层结构。

**依据**：
- Cognee 的 Task/TaskSpec/BoundTask 三层结构提供了精巧的任务抽象
- batch_size、enriches、_Drop 信号等特性增强了管道的健壮性
- @override_run_tasks 装饰器实现了分布式透明切换

## 不确定事项 → 已确认决策

1. **KuzuDB 性能上限**：KuzuDB 在 >1M 节点规模下的性能尚未验证，可能需要 Neo4j 回退
2. ~~**ChromaDB vs LanceDB**~~ → **已确认：双后端支持**（ChromaDB <100K，LanceDB >100K，通过配置切换）
3. **Leiden vs Louvain 社区检测** → **已确认：Leiden 优先 + Louvain 回退**（与 Graphify 一致）
4. ~~**嵌入模型选择**~~ → **已确认：双模式**（默认 OpenAI API，可选本地模型 Fastembed/Ollama，通过配置切换）
5. ~~**语义空间隔离策略**~~ → **已确认：混合模式**（默认逻辑隔离 domain_id 过滤，可选物理隔离独立 DB，ContextVar 请求级切换）
6. ~~**人工介入机制**~~ → **已确认：四层全选**（声明式规则编辑+反馈闭环+质量检测自愈+知识时效管理），规则表达式使用结构化配置+合理表达式，非严格 DSL
7. ~~**业务逻辑资产化表达**~~ → **已确认：双层表达**（Schema 内嵌规则定义+规则图节点存储，逻辑边实时计算+规则节点可编辑可版本化）
8. ~~**跨域知识流动**~~ → **已确认：实体对齐模式**（canonical_name + same_entity_as 边，跨域查询时自动扩展）

## 深度调研新增洞察

### 语义空间隔离

- m_flow/cognee 的 DatasetStoreHandlerInterface + ContextVar 模式是最成熟的多租户隔离方案
- MemPalace 的 Wing/Room/Hall 元数据过滤提供了轻量级域划分参考
- OntologyEngine 独有需求：跨域实体对齐（same_entity_as 边），参考 m_flow Entity.canonical_name

### 知识全链路可管理性

- 人在回路中的四种角色：审核者（Lint）、纠正者（invalidate）、领域专家（DSL）、反馈者（feedback_weight）
- 知识质量管理五阶段：摄入→验证→检测→修复→演化
- 规则表达式简化：用户明确要求不使用严格 DSL，使用结构化配置参数+合理表达式

### 业务逻辑资产化

- 五种基本模式：规则即边（KAG）、规则即节点（m_flow/cognee）、规则即 Schema（KAG）、规则即文档结构（LLM-Wiki-Agent）、规则即检索策略（m_flow/cognee）
- m_flow ContextPack 六维度模型（when/why/boundary/outcome/prereq/exception）是规则适用性边界的最佳实践
- Cognee DataPoint.source_pipeline/task 是规则溯源的最佳实践
- m_flow supersedes 边是规则版本管理的最佳实践

### 知识要素交互

- 边语义化光谱：传统 KG < Cognee < MAMGA < KAG < m_flow（edge_text 向量化）
- 查询桥接：KAG AtomicQuery 是最显式的设计，OntologyEngine 通过互索引边实现
- 因果推断：MAMGA _infer_latent_edges() 是唯一主动因果推断实现
- 领域知识注入：KAG ExternalGraphLoader 是最完整的领域知识注入机制

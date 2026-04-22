# 代码审查 P0/P1 修复决策记录

> **时间**：2026-04-22  
> **分支**：`implement/kb-llm-update`  
> **涉及文件**：`kuzu_store.py` / `mutual_index.py` / `bundle_search.py` / `llm_extractor.py` / `pipeline.py`

---

## 背景

本轮对上一次实现的代码进行深度审查，识别出以下优先级问题并逐一修复：

| 优先级 | 编号 | 问题描述 | 处理方式 |
|--------|------|---------|---------|
| P0 | P0-1 | KuzuDB 无 KnowledgeFragment 节点表，SUPPORTED_BY 为 Entity→Entity，与设计文档矛盾 | 修复 |
| P0 | P0-2 | get_neighbors 仅查 Relation 表，无法返回 SUPPORTED_BY 等专用边的 confidence/edge_text | 修复 |
| P0 | P0-3 | Bundle Search Phase 3 hop 代价语义注释缺失，可能被误解为"奖励" | 补注释 |
| P1 | P1-1 | collaborative_search entity_ids[:N] 按 first-seen 截取，不按质量排序 | 修复 |
| P1 | P1-2 | LLMExtractor extract prompt 静态，无 schema_context 注入 | 修复 |

---

## 关键决策

### D-1：SUPPORTED_BY 双表方案（P0-1）

**决策**：新增 `SUPPORTED_BY_FRAGMENT`（FROM KnowledgeFragment TO Entity），保留原有 `SUPPORTED_BY`（FROM Entity TO Entity）作为兼容路径。

**理由**：
- KuzuDB REL TABLE 不支持多 FROM 类型，必须用两张表分别建模
- 原有 `SUPPORTED_BY`（Entity→Entity）已有存量数据，强行迁移风险高
- 两张表语义清晰：Fragment 路径用 `_FRAGMENT` 后缀区分
- `_MUTUAL_INDEX_QUERIES["SUPPORTED_BY"]` 同时包含两张表，`get_mutual_index_edges()` 自动扇出查询

**被拒方案**：
- 方案B（维持 Entity→Entity，通过 get_mutual_index_edges 替代）：无法在 get_neighbors 中自然支持 fragment_id → entity 的查询路径
- 方案C（frag_id 映射到 entity_id）：间接映射破坏语义清晰度
- 方案D（重新对齐文档，SUPPORTED_BY=Entity→Entity）：违背设计规范的核心语义

### D-2：get_neighbors 路由机制（P0-2）

**决策**：`get_neighbors` 先检测 `node_id` 是否在 `KnowledgeFragment` 节点表中，若是则调用 `_get_fragment_neighbors`（查 `SUPPORTED_BY_FRAGMENT`，返回完整边属性），否则走原 `Relation` 表路径。

**关键约束**：
- `_get_fragment_neighbors` 返回包含 `confidence`、`edge_text`、`offset_start`、`offset_end` 的完整行
- 调用方（`_expand_via_supported_by`）无需感知内部路由细节
- `_is_knowledge_fragment` 是额外的 DB 查询，未来可考虑节点类型缓存优化

### D-3：entity_ids 排序（P1-1）

**决策**：按 `fragment_score × edge_confidence` 乘积降序排序，多路径命中同一 entity 时取 max。

**理由**：
- `fragment_score` 反映向量检索相关度（Layer-R 质量）
- `edge_confidence` 反映跨层链接的可信度（互索引边质量）
- 两者乘积综合表达"这个实体有多值得被 Layer-S 扩展"

### D-4：Bundle Search Phase 3 hop 代价语义（P0-3）

**决策**：保持现状（`path_cost += hop`，即连通也增加路径代价），补充详细注释说明这是**传播代价**而非惩罚。

**设计原则**（确认）：
- hop = 连通另一候选节点的遍历代价（小，HOP_COST=0.05）
- miss = 边指向候选集外的噪声惩罚（大，EDGE_MISS_COST=0.9）
- 两者都增加 path_cost，但 hop << miss
- 节点若要高排名，需要低 raw_distance（来自向量检索），而不是避免 intra-set 连通

### D-5：schema_context 注入链（P1-2）

**决策**：
1. `_EXTRACTION_SYSTEM_PROMPT` 拆分为 `BASE` + `WITH_SCHEMA` 两个模板
2. `_build_system_prompt(schema_context)` 函数根据是否有 schema 决定使用哪个模板
3. `LLMExtractor.extract(schema_context=None)` → `_extract_single(schema_context)` → `_call_llm(schema_context)` 完整传递链
4. `ExtractionPipeline` 新增 `schema_loader` 可选参数，`ingest()` 调用 `schema_loader.get_fact_object_descriptions()` 获取 schema_context
5. `schema_loader=None` 时静默降级（Phase 1 兼容模式）

**接口约定**：
- `schema_context: dict[str, str]`，格式为 `{fact_object_name: description}`
- `SchemaLoader.get_fact_object_descriptions()` 须返回此格式（待实现）

---

## 遗留问题（本轮未修复）

| # | 问题 | 原因 |
|---|------|------|
| S-1 | TRACE_TO 源端：Grammar=ExecutionStepSnapshot，KuzuDB=EntityNode | 未在本轮范围内 |
| S-3 | API 使用旧术语 concept_type，Schema v2 使用 _fact_object | 未在本轮范围内 |
| S-5 | KuzuDB 缺 7 种时序边表 | 未在本轮范围内 |
| P1-3 | `load_llm_config` 循环内 candidate 变量覆盖不影响逻辑，但缺乏 warning | 低风险，下轮处理 |
| P1-4 | ExtractionPipeline 缺 LLM 语义缓存（只有 AST 缓存） | Phase 2 特性，暂不实现 |
| P1-5 | `dedup.py` EdgeResult dataclass 和 dict 接口并存（edge_type vs relation_name） | 待下轮对齐 |

---

## 文档更新记录

| 文档 | 更新内容 |
|------|---------|
| `docs/02-design/schema/mutual-index-edges.md` | 存储实现章节：新增 KnowledgeFragment 节点表 + SUPPORTED_BY 双表设计说明 |
| `docs/02-design/query-engine/mutual-index-retrieval.md` | 更新 SUPPORTED_BY Cypher + 新增协同检索实现章节（entity_ids 排序 + MutualIndexConfig 参数） |
| `docs/02-design/extraction-pipeline/llm-extraction.md` | 新增 LLMClientProtocol 注入机制 + schema_context 注入链说明 |

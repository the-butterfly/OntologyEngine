# 提取管线设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

## 目的

定义 OntologyEngine 提取管线的整体架构——将异构数据源（代码、文档、结构化数据）编译为统一的知识图谱实例（EntityInstance、EdgeInstance、KnowledgeFragment）和互索引边（EXTRACTED_FROM 等）。提取管线是 L1 知识编译层的核心组件，衔接数据源层（L0）与知识表示层（L2）。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 异构数据源缺乏统一的提取入口 | 代码、文档、结构化数据各自处理，无法交叉引用 |
| 2 | 提取结果与 Schema v2 Instance 层不对齐 | 提取产物的字段结构隐含在代码中，跨模块无法对齐 |
| 3 | LLM 调用成本无控制 | 每次全量提取都调用 LLM，增量变更时浪费 token |
| 4 | 提取结果缺乏置信度分层 | 确定性提取与语义推断混为一谈，无法区分可信度 |
| 5 | 提取与互索引边创建脱节 | 实体提取后需手动关联 KnowledgeFragment，无法自动生成 EXTRACTED_FROM 边 |
| 6 | 跨文件实体去重缺失 | 同一业务实体从不同文件提取时产生重复实例 |

---

## 架构总览：三通道提取管线

```
┌─────────────────────────────────────────────────────────────────────┐
│  ExtractionPipeline                                                 │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│  │ Pass 1       │   │ Pass 2       │   │ Pass 3               │   │
│  │ AST 确定性提取│   │ LLM 语义提取 │   │ 去重与互索引边创建    │   │
│  │              │   │              │   │                      │   │
│  │ 零 LLM 成本  │   │ 仅处理变更文件│   │ 实体去重             │   │
│  │ confidence=1 │   │ confidence   │   │ 边合并               │   │
│  │ EXTRACTED    │   │ 0.4-0.9      │   │ EXTRACTED_FROM 边    │   │
│  │              │   │ INFERRED     │   │ SUPPORTED_BY 边      │   │
│  │              │   │              │   │ 矛盾检测             │   │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘   │
│         │                  │                      │               │
│         ▼                  ▼                      ▼               │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  增量缓存层（SHA256 + 语义缓存 + 推理检查点）                │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 三通道职责

| 通道 | 提取方式 | LLM 成本 | 置信度标签 | 输出 |
|------|----------|----------|-----------|------|
| **Pass 1: AST 确定性提取** | tree-sitter / 正则 / 结构化解析 | 零 | EXTRACTED (1.0) | EntityInstance + EdgeInstance + KnowledgeFragment |
| **Pass 2: LLM 语义提取** | LLM prompt 模板 | 仅变更文件 | INFERRED (0.4-0.9) / AMBIGUOUS (0.1-0.3) | EntityInstance + EdgeInstance + CategoryTag |
| **Pass 3: 去重与互索引边创建** | 确定性算法 | 零 | 继承来源 | 去重后实例 + EXTRACTED_FROM / SUPPORTED_BY 边 |

---

## 提取产出与 Schema v2 Instance 层对齐

提取管线的所有产出必须严格对齐 Instance 层数据结构（详见 `docs/02-design/schema/instance-layer.md`）：

| 提取产出 | 对齐的 Instance 层结构 | 关键对齐字段 |
|----------|----------------------|-------------|
| AST 提取的实体 | EntityInstance | id(UUID5), _fact_object, attributes, confidence=1.0, source_pipeline="ast_extraction" |
| AST 提取的关系 | EdgeInstance | from_id, to_id, relation_name, confidence=1.0, source_pipeline="ast_extraction" |
| LLM 提取的实体 | EntityInstance | id(UUID5), _fact_object, attributes, confidence∈[0.4,0.9], source_pipeline="llm_extraction" |
| LLM 提取的关系 | EdgeInstance | from_id, to_id, relation_name, edge_text, confidence∈[0.4,0.9] |
| LLM 提取的分类 | CategoryTag | entity_id, dimension_name, value_code, assigned_by="llm" |
| 文档分片 | KnowledgeFragment | id, dataset_id, document_id, chunk_index, offset_start/end, text, content_hash |
| 提取来源边 | EXTRACTED_FROM | from_id=EntityInstance, to_id=KnowledgeFragment, confidence=1.0 |
| 支撑关系边 | SUPPORTED_BY | from_id=KnowledgeFragment, to_id=EntityInstance, confidence∈[0.4,0.9] |

---

## 关键设计决策

| # | 决策 | 理由 | 参考项目 |
|---|------|------|----------|
| D-EP-1 | 三通道分离而非单通道混合 | AST 提取零成本且确定性高，应先执行；LLM 只处理 AST 无法覆盖的语义信息 | Graphify 三通道提取 |
| D-EP-2 | SHA256 增量缓存 | 文件内容未变更时跳过提取，避免重复 LLM 调用 | Graphify SHA256 caching |
| D-EP-3 | UUID5 确定性 ID | 同一业务实体从不同管道摄入时产出相同 ID，支持幂等写入 | Cognee identity_fields + UUID5 |
| D-EP-4 | EXTRACTED_FROM 边在提取时创建 | 提取是创建互索引边的唯一时机，延迟创建会导致溯源链断裂 | m_flow includes_chunk |
| D-EP-5 | 置信度标签体系（EXTRACTED/INFERRED/AMBIGUOUS） | 统一语义解读框架，低置信度触发人工审查 | Graphify validate_extraction |
| D-EP-6 | Markdown body-only 哈希 | YAML frontmatter 变更（如 status/tags）不应使缓存失效 | Graphify _body_content |
| D-EP-7 | 语义缓存分离 AST 缓存 | AST 提取结果可独立缓存，LLM 提取结果按文件缓存，两者生命周期不同 | Graphify check_semantic_cache |
| D-EP-8 | 去重在 Pass 3 统一执行 | Pass 1/2 各自产出原始结果，去重逻辑集中避免分散 | Cognee deduplicate_nodes_and_edges |

---

## 管线编排

### 端到端流程

```
IngestionService.ingest(dataset_id)
  │
  ├─ 1. 文件发现与分片
  │     scan_files() → chunk_text() → KnowledgeFragment[]
  │     每个碎片计算 content_hash (SHA256)
  │
  ├─ 2. Pass 1: AST 确定性提取
  │     check_ast_cache(fragments) → (cached, uncached)
  │     for uncached: ast_extract(fragment) → EntityInstance[] + EdgeInstance[]
  │     save_ast_cache(uncached_results)
  │
  ├─ 3. Pass 2: LLM 语义提取
  │     check_semantic_cache(fragments) → (cached, uncached)
  │     for uncached: llm_extract(fragment) → EntityInstance[] + EdgeInstance[] + CategoryTag[]
  │     save_semantic_cache(uncached_results)
  │
  ├─ 4. Pass 3: 去重与互索引边创建
  │     merge_results(ast_results, llm_results)
  │     dedup_entities(all_entities) → unique_entities
  │     dedup_edges(all_edges) → unique_edges
  │     create_extracted_from_edges(entities, fragments) → EXTRACTED_FROM[]
  │     create_supported_by_edges(fragments, entities) → SUPPORTED_BY[]
  │     detect_contradictions(new_entities, existing_entities)
  │
  └─ 5. 持久化
        write_to_kuzu(unique_entities, unique_edges)
        write_to_chroma(fragments, mutual_index_edges)
        update_extraction_status(fragments → "extracted")
```

### 参考项目对齐

| 参考项目 | 管线模式 | OntologyEngine 对应 |
|----------|----------|-------------------|
| Cognee Cognify | 6 步管道（resolve→ingest→chunk→extract→graph→contradict） | IngestionService 编排 5 步管线 |
| Graphify build | AST → Semantic → Merge → Validate | Pass 1 → Pass 2 → Pass 3 |
| MemPalace mine | scan → chunk → route → file | 文件发现与分片步骤 |
| Cognee Pipeline | Task 链式执行 + Drop 信号过滤 | 管线编排，支持异步 Task |

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [ast-extraction.md](ast-extraction.md) | Pass 1 AST 确定性提取设计 |
| [llm-extraction.md](llm-extraction.md) | Pass 2 LLM 语义提取设计 |
| [incremental-cache.md](incremental-cache.md) | SHA256 缓存与增量处理设计 |
| [dedup-strategy.md](dedup-strategy.md) | 去重策略与互索引边创建设计 |

---

## 与其他模块的关系

| 模块 | 关系 | 交互方式 |
|------|------|----------|
| SchemaLoader | 提取依赖 Schema 声明验证实例合规性 | 读取 EntityDeclaration / RelationDeclaration |
| IngestionService | 提取管线的编排入口 | IngestionService 调用 ExtractionPipeline |
| KuzuDBStorage | 提取产物的持久化目标 | 写入 EntityInstance / EdgeInstance / 互索引边 |
| ChromaVectorStore | KnowledgeFragment 和互索引边的向量存储 | 写入向量嵌入 |
| SQLiteStorage | 增量缓存和提取状态存储 | 读写缓存和状态 |

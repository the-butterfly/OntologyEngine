# 互索引协同检索

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` + `docs/02-design/schema/mutual-index-edges.md` | **last_verified**: 2026-04-19

## 目的

定义互索引边驱动的 Layer-R/Layer-S 协同检索机制，实现"检索→推理→回溯"的完整闭环。互索引协同检索是 OntologyEngine 双层架构的核心价值——它使 Layer-R 的碎片证据和 Layer-S 的结构化推理可以双向导航，构建完整的证据链。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | Layer-R 与 Layer-S 检索结果无法桥接 | 向量检索返回碎片后无法自动扩展到结构化知识 |
| 2 | 推理结果不可解释 | 无法回答"这个结论来自哪个文档的哪个段落" |
| 3 | 规则/指标定义来源不可追溯 | 规则变更时无法定位原始定义文档 |
| 4 | 缺乏 Retriever 注册机制 | 无法动态扩展检索策略 |
| 5 | 协同检索流程未定义 | mixed 查询无法自动执行跨层检索 |

---

## 完整协同流程

### 目的

定义互索引边驱动的 Layer-R → Layer-S → Layer-R 完整协同检索流程。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 双层检索缺乏桥接 | 互索引边作为跨层导航的显式链接 |
| 2 | 检索结果缺乏证据链 | TRACE_TO 边构建从推理结果到原始碎片的证据链 |

### 流程图

```
查询：explain_risk(customer_id="A")
     │
     ▼
┌─────────────────────────────────────┐
│ Step 1 — Layer-R 检索               │
│   query_raw("企业A 财务 风险")       │
│   → frag_001: "2024年报：营收3.2亿"  │
│   → frag_002: "征信报告：逾期2次"    │
└──────────────┬──────────────────────┘
               │
               ▼ extracted_from / supported_by
┌─────────────────────────────────────┐
│ Step 2 — Layer-R → Layer-S 扩展     │
│   frag_001 → ent_A_financial        │
│   frag_002 → ent_A_credit           │
│   KuzuDB: MATCH (e)-[r:EXTRACTED_FROM]->(kf) │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 3 — Layer-S 推理执行           │
│   MetricEngine: debt_ratio=0.65     │
│   RuleEngine: risk_level = "D"      │
│   产出 ExecutionStepSnapshot        │
└──────────────┬──────────────────────┘
               │
               ▼ trace_to
┌─────────────────────────────────────┐
│ Step 4 — Layer-S → Layer-R 回溯     │
│   snap_001 → frag_001               │
│   snap_001 → frag_002               │
│   KuzuDB: MATCH (snap)-[r:TRACE_TO]->(kf) │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ Step 5 — 输出                       │
│   risk_level: D                     │
│   evidence: [frag_001, frag_002]    │
│   execution_snapshot: {...}         │
│   trace_chain: [snap→frag_001,      │
│                  snap→frag_002]     │
└─────────────────────────────────────┘
```

---

## 四种互索引边的检索角色

### 目的

定义四种互索引边在协同检索中的具体角色和查询方式。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 不同互索引边的检索角色不明确 | 按边类型定义检索用途 |
| 2 | 跨层导航的 Cypher 查询未定义 | 为每种边类型定义查询模板 |

### EXTRACTED_FROM：碎片→实体扩展

```
角色：从 Layer-R 碎片导航到 Layer-S 实体
方向：Entity（实体提取来源）→ Entity（通过反向导航找到碎片，再找到其他实体）

Cypher 查询（反向：从 fragment_id 找到提取自该 fragment 的 Entity）：
  MATCH (e:Entity)-[r:EXTRACTED_FROM]->(src:Entity)
  WHERE src.entity_id IN $fragment_entity_ids
    AND r.confidence >= $min_confidence
  RETURN e, r

触发条件：
  - factual 查询类型的 EXTRACTED_FROM 扩展
  - mixed 查询的 Step 2
```

### SUPPORTED_BY：碎片→实体支撑

```
角色：从 Layer-R KnowledgeFragment 导航到 Layer-S 实体（协同检索的主扩展路径）
方向（规范路径）：KnowledgeFragment → Entity
方向（兼容路径）：Entity → Entity

规范路径 Cypher（SUPPORTED_BY_FRAGMENT 表）：
  MATCH (kf:KnowledgeFragment {fragment_id: $fragment_id})
        -[r:SUPPORTED_BY_FRAGMENT]->
        (e:Entity)
  WHERE r.confidence >= $min_confidence
  RETURN e.entity_id, r.confidence, r.edge_text, r.offset_start, r.offset_end

兼容路径 Cypher（SUPPORTED_BY 表，Entity→Entity 变体）：
  MATCH (src:Entity {entity_id: $entity_id})
        -[r:SUPPORTED_BY]->
        (e:Entity)
  WHERE r.confidence >= $min_confidence
  RETURN e.entity_id, r.confidence, r.edge_text

触发条件：
  - MutualIndexCollaborative._expand_via_supported_by（Step 2）
  - 需要查找 Fragment 的支撑实体
  - 证据链构建

实现说明（[关键设计点]）：
  get_neighbors(node_id=fragment_id, direction="outgoing") 会自动
  检测 node_id 是否在 KnowledgeFragment 节点表中，若是则查询
  SUPPORTED_BY_FRAGMENT 并返回完整边属性（confidence, edge_text,
  offset_start, offset_end），无需调用方额外处理。
```

### DEFINED_IN：规则→定义来源

```
角色：从 Layer-S 规则/指标导航到 Layer-R 定义文档
方向：RuleDefinitionNode → KnowledgeFragmentNode

Cypher 查询：
  MATCH (rd:RuleDefinitionNode)-[r:DEFINED_IN]->(kf:KnowledgeFragmentNode)
  WHERE rd.id IN $rule_ids
    AND r.confidence >= $min_confidence
  RETURN kf, r

触发条件：
  - analytical 查询类型的 TRACE_TO 回溯
  - 规则溯源审计
```

### TRACE_TO：推理→证据回溯

```
角色：从 Layer-S 推理步骤导航到 Layer-R 原始证据
方向：ExecutionStepSnapshotNode → KnowledgeFragmentNode

Cypher 查询：
  MATCH (snap:ExecutionStepSnapshotNode)-[r:TRACE_TO]->(kf:KnowledgeFragmentNode)
  WHERE snap.id IN $snapshot_ids
    AND r.confidence >= $min_confidence
  RETURN kf, r

触发条件：
  - analytical 查询的 TRACE_TO 回溯
  - mixed 查询的 Step 4
  - 合规审计证据链构建
```

> **[待扩展]**：TRACE_TO 的源端应为 ExecutionStepSnapshot，当前尚未定义 ExecutionStepSnapshotNode 节点表。Phase 2 增加 ExecutionStepSnapshotNode 后修改。

---

## Retriever 注册机制

### 目的

定义 Retriever 注册机制（策略模式），支持动态扩展检索策略，对齐 KAG IndexManager 和 Cognee register_retriever。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 检索策略硬编码 | 策略模式 + 注册表 |
| 2 | 无法动态添加新检索器 | register_retriever 注册机制 |
| 3 | 检索器缺乏元数据 | name + description + applicable_scenarios |

### 注册接口

```python
class RetrieverRegistry:
    _retrievers: Dict[str, RetrieverMeta] = {}

    @classmethod
    def register(
        cls,
        name: str,
        description: str,
        applicable_scenarios: list[str],
        retriever_cls: type,
    ) -> None:
        cls._retrievers[name] = RetrieverMeta(
            name=name,
            description=description,
            applicable_scenarios=applicable_scenarios,
            retriever_cls=retriever_cls,
        )

    @classmethod
    def get(cls, name: str) -> RetrieverMeta:
        return cls._retrievers[name]

    @classmethod
    def list_retrievers(cls) -> list[RetrieverMeta]:
        return list(cls._retrievers.values())
```

### 内置 Retriever 注册

| Retriever 名称 | 适用场景 | 对齐参考 |
|---------------|---------|---------|
| `layer_r_vector` | factual 查询、碎片检索 | MemPalace Drawer |
| `layer_s_graph` | multi-hop 查询、图遍历 | KAG PPR |
| `bundle_search` | 语义图检索、边语义评分 | m_flow Bundle Search |
| `bm25_keyword` | 精确匹配、关键词检索 | QMD FTS5 |
| `mutual_index_collaborative` | mixed 查询、跨层协同 | KAG IndexManager |
| `temporal_filter` | temporal 查询、时序过滤 | MAMGA 时序共振 |

### 与 KAG IndexManager 对齐

| 维度 | KAG IndexManager | Cognee register_retriever | OntologyEngine RetrieverRegistry |
|------|-----------------|--------------------------|----------------------------------|
| 注册方式 | `@KAGIndexManager.register("name")` | `register_retriever(name, cls)` | `RetrieverRegistry.register(name, ...)` |
| 元数据 | name + description + schema + cost + scenarios | name + cls | name + description + scenarios + cls |
| 配置生成 | `build_extractor_config` + `build_retriever_config` | 无 | 无（Phase 1 简化） |
| 产品化 | 支持产品界面选择 | 无 | 无（Phase 1 简化） |

---

## 查询路由与互索引边

### 目的

定义不同查询类型使用的互索引边和检索路径。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 不同查询类型的跨层策略不明确 | 按查询类型定义互索引边使用策略 |
| 2 | mixed 查询缺乏完整流程 | 定义 mixed 查询的五步协同流程 |

### 查询类型与互索引边映射

| 查询类型 | 使用的互索引边 | 检索路径 |
|----------|---------------|----------|
| factual | EXTRACTED_FROM | Layer-R 向量检索 → EXTRACTED_FROM 扩展到 EntityInstance |
| multi-hop | 无直接使用 | Layer-S 图遍历，互索引边参与 Bundle Search |
| temporal | EXTRACTED_FROM | valid_from/to 过滤 → EXTRACTED_FROM 扩展 |
| analytical | TRACE_TO | L4 RuleEngine 执行 → TRACE_TO 回溯碎片证据 |
| mixed | 全部四种 | Layer-R → SUPPORTED_BY → Layer-S → TRACE_TO → Layer-R |

### mixed 查询完整流程

```
mixed 查询："分析企业A的税务风险，并说明依据"

Step 1 — Layer-R 检索：
  query_raw("企业A 税务 风险")
  → frag_001, frag_002

Step 2 — SUPPORTED_BY 扩展（Layer-R → Layer-S）：
  frag_001 ──[SUPPORTED_BY]──▶ ent_A_tax
  frag_002 ──[SUPPORTED_BY]──▶ ent_A_compliance

Step 3 — Layer-S 推理：
  MetricEngine 计算：tax_risk_score=0.72
  RuleEngine 执行：IF tax_risk_score > 0.7 → risk_level = "C"
  产出 ExecutionStepSnapshot

Step 4 — DEFINED_IN 溯源：
  RuleDefinition[tax_risk_rule] ──[DEFINED_IN]──▶ frag_003（税法条款）

Step 5 — TRACE_TO 回溯（Layer-S → Layer-R）：
  ExecutionStepSnapshot ──[TRACE_TO]──▶ frag_001
  ExecutionStepSnapshot ──[TRACE_TO]──▶ frag_002
  ExecutionStepSnapshot ──[TRACE_TO]──▶ frag_003

Step 6 — 输出：
  risk_level: C
  evidence: [frag_001, frag_002, frag_003]
  rule_source: frag_003
  execution_snapshot: {...}
  trace_chain: [snap→frag_001, snap→frag_002, snap→frag_003]
```

---

## 协同检索实现（[关键设计点]）

### MutualIndexCollaborative 四步流程

```
Step 1 — Layer-R 向量检索
  LayerRRetriever.search_knowledge_fragments(query_embedding, top_k)
  → fragments: List[FragmentResult]  （包含 fragment_id 和 score）

Step 2 — SUPPORTED_BY 扩展（KnowledgeFragment → Entity）
  KuzuGraphStore.get_neighbors(node_id=frag_id, direction="outgoing")
  → 自动路由到 _get_fragment_neighbors，查询 SUPPORTED_BY_FRAGMENT
  → 返回 {neighbor_id, edge_type, confidence, edge_text, offset_start, offset_end}
  → 收集 edge_props_by_fragment: Dict[frag_id, List[edge_props]]

Step 3 — entity_ids 排序 + 并行 Layer-S 扩展
  排序规则：fragment_score × edge_confidence 乘积降序（[关键设计点]）
  取 top-N = MutualIndexConfig.max_parallel_entity_expansion（默认 5）
  asyncio.gather(*[layer_s.retrieve_neighbors(eid) for eid in top_entity_ids])
  → 合并去重 EntityResult + EdgeResult

Step 4 — 证据链构建
  从 edge_props_by_fragment 中读取真实边属性（confidence, edge_text, offsets）
  上限：MutualIndexConfig.evidence_chain_max_fragments（默认 10）
```

### entity_ids 排序设计

| 方案 | 排序依据 | 选择原因 |
|------|---------|---------|
| **当前实现** | fragment_score × edge_confidence 乘积 | 综合向量相关度（fragment_score）和跨层链接可信度（edge_confidence），平衡两者 |
| 放弃方案：first-seen | FIFO 顺序 | 忽略了 fragment 向量分数差异，top-N 截取质量低 |
| 放弃方案：仅 confidence | 边置信度 | 忽略了 fragment 本身的检索相关度 |

当一个 entity 通过多条 fragment→entity 路径被发现时，取所有路径的 `max(score × confidence)` 作为最终排序分。

### MutualIndexConfig 可配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_parallel_entity_expansion` | 5 | 并行 Layer-S 扩展的实体数上限 |
| `min_confidence_for_expansion` | 0.0 | SUPPORTED_BY 边的最低置信度阈值 |
| `evidence_chain_max_fragments` | 10 | 证据链最大链接数 |
| `evidence_chain_default_confidence` | 0.5 | 边无置信度属性时的降级值 |
| `supported_by_neighbor_limit` | 10 | Fragment 扩展时的 get_neighbors limit |
| `layer_s_neighbor_limit` | 50 | Layer-S 扩展时的 get_neighbors limit |

---

## 证据链数据结构

### 目的

定义协同检索输出的证据链数据结构，支持完整的推理可解释性。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 证据链缺乏结构化表达 | EvidenceLink 数据结构 |
| 2 | 推理步骤与证据的关联不明确 | trace_type + confidence 标注 |

### 数据结构

```python
@dataclass
class EvidenceLink:
    source_id: str
    source_type: str
    target_id: str
    target_type: str
    trace_type: str
    confidence: float
    edge_text: str
    offset_start: int
    offset_end: int

@dataclass
class CollaborativeResult:
    fragments: List[FragmentResult]
    entities: List[EntityResult]
    edges: List[EdgeResult]
    evidence_chain: List[EvidenceLink]
    execution_snapshot: Dict[str, Any] | None
    metadata: QueryMetadata
```

### 证据链示例

```json
{
    "evidence_chain": [
        {
            "source_id": "snap_001",
            "source_type": "ExecutionStepSnapshot",
            "target_id": "frag_001",
            "target_type": "KnowledgeFragment",
            "trace_type": "TRACE_TO",
            "confidence": 0.9,
            "edge_text": "授信额度决策基于企业A 2024年报财务数据",
            "offset_start": 4500,
            "offset_end": 4900
        },
        {
            "source_id": "frag_001",
            "source_type": "KnowledgeFragment",
            "target_id": "ent_A_financial",
            "target_type": "EntityInstance",
            "trace_type": "SUPPORTED_BY",
            "confidence": 0.85,
            "edge_text": "年报数据支撑了财务实体",
            "offset_start": 0,
            "offset_end": 0
        }
    ]
}
```

---

## 与参考项目的对齐

| 维度 | KAG | Cognee | m_flow | OntologyEngine |
|------|-----|--------|--------|----------------|
| 跨层桥接 | AtomicQuery 桥接 query→KU→chunk | DataPoint source_pipeline | includes_chunk / supported_by | 四种互索引边 |
| 注册机制 | IndexManager + RetrieverABC | register_retriever | 无 | RetrieverRegistry |
| 溯源粒度 | chunk 级 | pipeline + task 级 | ContentFragment 级 | 块 + 段落偏移 |
| 证据链 | Chunk → KU → Entity | source_pipeline 链 | ContentFragment → Facet | TRACE_TO → KnowledgeFragment |
| 双向导航 | 单向（chunk→KU） | 单向（pipeline） | 单向（supported_by） | 双向（EXTRACTED_FROM + SUPPORTED_BY） |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-MI-1 | Retriever 注册机制简化为策略模式 | Phase 1 不需要 KAG 的产品化配置生成，简化实现 |
| D-MI-2 | mixed 查询走完整五步协同流程 | mixed 查询需要多路信息，五步流程覆盖所有互索引边 |
| D-MI-3 | TRACE_TO 源端 Phase 1 暂用 EntityNode | ExecutionStepSnapshotNode 尚未定义，Phase 2 扩展 |
| D-MI-4 | 证据链包含 offset 信息 | 支持段落级溯源，对齐互索引边的 offset_start/offset_end |

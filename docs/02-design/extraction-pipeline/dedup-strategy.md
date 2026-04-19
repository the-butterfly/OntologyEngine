# 去重策略与互索引边创建

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

## 目的

定义提取管线 Pass 3 的去重策略——消除 Pass 1（AST）和 Pass 2（LLM）产出中的重复实体和边，并在此阶段创建互索引边（EXTRACTED_FROM / SUPPORTED_BY）。去重是确保知识图谱一致性的关键步骤。

## 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 同一业务实体从不同文件提取时产生重复实例 | UUID5 基于 identity_fields 确定性生成 ID，天然去重 |
| 2 | 双向边（A→B 和 B→A 同类型）冗余 | 双向边合并，保留最高置信度 |
| 3 | 同一文件内 AST 和 LLM 提取同一实体 | 文件级去重，AST 结果优先（confidence=1.0） |
| 4 | 跨文件提取同一业务实体 | 跨文件去重，基于 identity_fields + UUID5 |
| 5 | 去重后需创建互索引边 | Pass 3 统一创建 EXTRACTED_FROM 和 SUPPORTED_BY 边 |

---

## 去重层次

```
┌─────────────────────────────────────────────────────────────────┐
│  去重层次（由内到外）                                             │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 1. 文件内去重（Within-file Dedup）                         │  │
│  │    同一文件内 AST 和 LLM 提取的同一实体                     │  │
│  │    策略: AST 优先（confidence=1.0 > LLM confidence）        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 2. 跨文件去重（Cross-file Dedup）                          │  │
│  │    不同文件提取的同一业务实体                                │  │
│  │    策略: identity_fields + UUID5 确定性合并                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 3. 边去重（Edge Dedup）                                    │  │
│  │    双向边合并 + 同源边去重                                  │  │
│  │    策略: 保留最高置信度，合并属性                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 实体去重

### UUID5 确定性 ID

实体 ID 基于 UUID5 确定性生成，同一业务实体始终产出相同 ID：

```
entity_id = UUID5(
    namespace=UUID("ontology-engine:entity"),
    name=":".join(identity_fields_values)
)
```

| 参数 | 说明 | 参考项目 |
|------|------|----------|
| namespace | 固定命名空间 UUID | Cognee DataPoint UUID5 |
| identity_fields_values | EntityDeclaration.identity_fields 对应的属性值拼接 | Cognee identity_fields |

### identity_fields 定义

identity_fields 在 EntityDeclaration 中声明，用于确定实体的唯一性：

```yaml
fact_object:
  id: "finance:Counterparty"
  name: "交易对手"
  identity_fields: ["entity_id"]
  attributes:
    - name: "entity_id"
      type: "string"
      required: true
    - name: "name"
      type: "string"
```

| Fact Object | identity_fields | 说明 |
|-------------|----------------|------|
| finance:Counterparty | ["entity_id"] | 统一社会信用代码唯一标识 |
| code:Class | ["source_file", "class_name"] | 文件+类名唯一标识 |
| code:Function | ["source_file", "function_name"] | 文件+函数名唯一标识 |
| doc:Heading | ["source_file", "heading_level", "heading_text"] | 文件+标题唯一标识 |

### 文件内去重

```
dedup_within_file(ast_entities, llm_entities):
  seen = {}
  result = []

  for entity in ast_entities:
    key = entity.id
    if key not in seen:
      seen[key] = entity
      result.append(entity)

  for entity in llm_entities:
    key = entity.id
    if key not in seen:
      seen[key] = entity
      result.append(entity)
    else:
      existing = seen[key]
      merge_attributes(existing, entity)

  return result
```

**合并规则**：

| 场景 | 已有实体 | 新实体 | 合并策略 |
|------|----------|--------|----------|
| AST + LLM 同 ID | AST (confidence=1.0) | LLM (confidence=0.7) | 保留 AST，LLM 属性作为补充 |
| LLM + LLM 同 ID | LLM (confidence=0.7) | LLM (confidence=0.8) | 保留高置信度，低置信度属性补充 |
| AST + AST 同 ID | AST (confidence=1.0) | AST (confidence=1.0) | 保留先出现的，后者属性补充 |

### 跨文件去重

```
dedup_cross_file(file_results: dict[str, list[EntityInstance]]):
  global_seen = {}
  result = []

  for file_path, entities in file_results.items():
    for entity in entities:
      key = entity.id
      if key not in global_seen:
        global_seen[key] = entity
        result.append(entity)
      else:
        existing = global_seen[key]
        merge_entity(existing, entity, strategy="highest_confidence")

  return result
```

**跨文件合并策略**：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| highest_confidence | 保留置信度最高的实体 | 默认策略 |
| most_attributes | 保留属性最完整的实体 | 属性缺失场景 |
| latest_source | 保留最新来源的实体 | 时序敏感场景 |

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Cognee deduplicate_nodes_and_edges | 按 node.id 去重，首次出现优先 | 扩展为 UUID5 + identity_fields + 合并策略 |
| Cognee DataPoint UUID5 | 基于 identity 字段确定性生成 ID | 完全复用 UUID5 模式 |
| Graphify build | NetworkX add_node 幂等（后者覆盖前者） | 改为显式合并策略，保留最高置信度 |
| Graphify seen_ids | 文件内 seen_ids 集合去重 | 扩展为跨文件 global_seen |

---

## 边去重

### 双向边合并

当存在 A→B 和 B→A 两条同类型边时，合并为一条边，保留最高置信度：

```
dedup_bidirectional_edges(edges: list[EdgeInstance]):
  edge_map = {}

  for edge in edges:
    key = tuple(sorted([edge.from_id, edge.to_id])) + (edge.relation_name,)
    if key not in edge_map:
      edge_map[key] = edge
    else:
      existing = edge_map[key]
      if edge.confidence > existing.confidence:
        edge_map[key] = edge
        merge_edge_attributes(existing, edge)

  return list(edge_map.values())
```

**示例**：

```
原始边:
  EntityA ──[guarantees, confidence=0.7]──▶ EntityB
  EntityB ──[guarantees, confidence=0.8]──▶ EntityA

合并后:
  EntityA ──[guarantees, confidence=0.8]──▶ EntityB
  (保留高置信度方向，合并属性)
```

### 同源边去重

同一 source_file 中 from_id + to_id + relation_name 相同的边只保留一条：

```
dedup_same_source_edges(edges: list[EdgeInstance]):
  seen = {}
  result = []

  for edge in edges:
    key = (edge.from_id, edge.to_id, edge.relation_name, edge.source_pipeline)
    if key not in seen:
      seen[key] = edge
      result.append(edge)
    else:
      existing = seen[key]
      if edge.confidence > existing.confidence:
        seen[key] = edge

  return result
```

### 边去重规则总结

| 场景 | 去重键 | 合并策略 |
|------|--------|----------|
| 双向边 | sorted(from_id, to_id) + relation_name | 保留最高置信度方向 |
| 同源重复边 | from_id + to_id + relation_name + source_pipeline | 保留最高置信度 |
| AST + LLM 同边 | from_id + to_id + relation_name | AST 优先（confidence=1.0） |
| 不同 source_pipeline | from_id + to_id + relation_name + source_pipeline | 保留两者（来源不同） |

---

## 互索引边创建

### EXTRACTED_FROM 边

在 Pass 3 中，为每个去重后的 EntityInstance 创建 EXTRACTED_FROM 边：

```
create_extracted_from_edges(
    entities: list[EntityInstance],
    fragments: list[KnowledgeFragment]
) → list[EXTRACTED_FROM]:

  edges = []
  for entity in entities:
    fragment = find_fragment_by_source(entity.source_content_hash, fragments)
    if fragment:
      edges.append(EXTRACTED_FROM(
        from_id=entity.id,
        to_id=fragment.id,
        source_file=entity.source_file,
        offset_start=entity.offset_start,
        offset_end=entity.offset_end,
        confidence=1.0 if entity.source_pipeline == "ast_extraction" else entity.confidence,
        edge_text=f"{entity._fact_object} 从 {entity.source_file} 提取",
        created_at=datetime.now()
      ))
  return edges
```

### SUPPORTED_BY 边

为 LLM 提取的实体创建 SUPPORTED_BY 边：

```
create_supported_by_edges(
    entities: list[EntityInstance],
    fragments: list[KnowledgeFragment]
) → list[SUPPORTED_BY]:

  edges = []
  for entity in entities:
    if entity.source_pipeline != "llm_extraction":
      continue
    fragment = find_fragment_by_source(entity.source_content_hash, fragments)
    if fragment:
      edges.append(SUPPORTED_BY(
        from_id=fragment.id,
        to_id=entity.id,
        source_file=entity.source_file,
        offset_start=entity.offset_start,
        offset_end=entity.offset_end,
        confidence=entity.confidence,
        edge_text=f"文档片段支撑了 {entity._fact_object} 的业务判断",
        created_at=datetime.now()
      ))
  return edges
```

### 互索引边与 Instance 层对齐

| 互索引边字段 | Instance 层对齐 | 说明 |
|-------------|----------------|------|
| id | UUID5(namespace, from_id + to_id + edge_type) | 确定性 ID |
| from_id | EntityInstance.id / KnowledgeFragment.id | 引用 Instance 层 |
| to_id | KnowledgeFragment.id / EntityInstance.id | 引用 Instance 层 |
| source_file | EntityInstance.source_pipeline 推断 | 来源文件 |
| offset_start/end | 提取时记录的字符偏移 | 段落级溯源 |
| confidence | 继承实体置信度 | AST=1.0, LLM=0.4-0.9 |
| edge_text | 自动生成或 LLM 生成 | 语义描述 |

---

## 矛盾检测

### 目的

在去重过程中检测同一业务实体从不同来源获取时产生的矛盾。

### 检测策略

| 检测时机 | 检测方式 | 处理 |
|----------|----------|------|
| 跨文件合并时 | 属性值冲突检测 | 生成 contradiction_report |
| EXTRACTED_FROM 边创建时 | 同一实体指向多个碎片 | 正常（多来源），但检查属性一致性 |
| SUPPORTED_BY 边创建时 | 碎片支撑矛盾实体 | 标记矛盾 |

### 矛盾检测流程

```
detect_contradictions(new_entities, existing_entities):
  contradictions = []

  for new_entity in new_entities:
    existing = find_by_id(existing_entities, new_entity.id)
    if existing is None:
      continue

    for attr_name, new_value in new_entity.attributes.items():
      existing_value = existing.attributes.get(attr_name)
      if existing_value is not None and existing_value != new_value:
        contradictions.append({
          "entity_id": new_entity.id,
          "attribute": attr_name,
          "existing_value": existing_value,
          "new_value": new_value,
          "existing_source": existing.source_pipeline,
          "new_source": new_entity.source_pipeline,
          "severity": "high" if existing.confidence >= 0.8 and new_entity.confidence >= 0.8 else "medium"
        })

  return contradictions
```

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| LLM-Wiki-Agent ingest.py | ingest 时矛盾检测 | 跨文件合并时检测 |
| Graphify validate_extraction | schema 验证 + AMBIGUOUS 标记 | 矛盾检测结果标记为需人工审查 |
| Cognee deduplicate_nodes_and_edges | 简单 ID 去重 | 扩展为属性级矛盾检测 |

---

## Pass 3 完整流程

```
Pass 3: dedup_and_index(ast_results, llm_results, fragments)
  │
  ├─ 1. 文件内去重
  │     for each source_file:
  │       dedup_within_file(ast_entities, llm_entities)
  │       dedup_same_source_edges(ast_edges, llm_edges)
  │
  ├─ 2. 跨文件去重
  │     dedup_cross_file(all_file_results)
  │     dedup_bidirectional_edges(all_edges)
  │
  ├─ 3. 矛盾检测
  │     contradictions = detect_contradictions(new_entities, existing_entities)
  │     if contradictions:
  │       save_contradiction_reports(contradictions)
  │       notify_admin(contradictions)
  │
  ├─ 4. 创建 EXTRACTED_FROM 边
  │     extracted_from_edges = create_extracted_from_edges(unique_entities, fragments)
  │
  ├─ 5. 创建 SUPPORTED_BY 边
  │     supported_by_edges = create_supported_by_edges(llm_entities, fragments)
  │
  ├─ 6. 验证
  │     validate_all(unique_entities, unique_edges, extracted_from_edges, supported_by_edges)
  │     参考 Graphify validate_extraction 模式
  │
  └─ 7. 持久化
        write_to_kuzu(unique_entities, unique_edges, extracted_from_edges, supported_by_edges)
        write_to_chroma(fragments, mutual_index_edges)
        update_extraction_status(fragments → "extracted")
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-DEDUP-1 | UUID5 确定性 ID 而非 UUID4 | 同一业务实体从不同管道摄入时产出相同 ID，天然去重 |
| D-DEDUP-2 | AST 优先于 LLM | AST 提取确定性高（confidence=1.0），LLM 提取有不确定性 |
| D-DEDUP-3 | 双向边合并而非保留两条 | 业务关系通常无方向性差异（如 guarantees），合并减少冗余 |
| D-DEDUP-4 | 矛盾检测在去重时执行 | 去重是发现矛盾的自然时机，合并时即可比较属性 |
| D-DEDUP-5 | EXTRACTED_FROM 边在 Pass 3 创建 | 去重后实体 ID 确定不变，此时创建互索引边最可靠 |
| D-DEDUP-6 | SUPPORTED_BY 边仅对 LLM 提取实体创建 | AST 提取的实体有 EXTRACTED_FROM 边，LLM 提取的实体额外需要 SUPPORTED_BY 表达支撑关系 |
| D-DEDUP-7 | 不同 source_pipeline 的边不去重 | AST 边和 LLM 边来源不同，保留两者提供多视角 |

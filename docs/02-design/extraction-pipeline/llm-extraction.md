# Pass 2: LLM 语义提取

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

## 目的

定义提取管线第二通道——基于 LLM 的语义提取。此通道仅处理增量变更文件，提取 AST 无法覆盖的语义信息：概念关系、设计意图、超边、语义相似性边和分类标注。提取结果的置信度标签为 INFERRED（0.4-0.9）或 AMBIGUOUS（0.1-0.3）。

## 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 代码/文档中的隐含语义关系无法通过 AST 提取 | LLM 推断实体间的语义关系（如 "依赖"、"影响"、"约束"） |
| 2 | 设计意图和业务概念丢失 | LLM 从注释、文档中提取设计意图和业务概念 |
| 3 | 跨文件语义相似性不可见 | LLM 识别语义相似实体，创建 SIMILAR_TO 边 |
| 4 | 分类标注需要人工完成 | LLM 自动分类标注，产出 CategoryTag |
| 5 | 全量 LLM 提取成本过高 | 仅处理增量变更文件，缓存已有结果 |

---

## LLM 提取范围

### 仅 LLM 可提取的内容

| 提取类型 | 说明 | 置信度范围 | 产出 |
|----------|------|-----------|------|
| **概念关系** | 实体间的隐含语义关系（如"影响"、"约束"、"依赖"） | 0.4-0.9 (INFERRED) | EdgeInstance |
| **设计意图** | 从注释/文档中提取的设计决策和意图 | 0.5-0.8 (INFERRED) | EntityInstance + EdgeInstance |
| **超边** | 涉及 3 个以上实体的复杂关系 | 0.4-0.7 (INFERRED) | EdgeInstance (hyperedge) |
| **语义相似性边** | 语义相似但名称不同的实体间链接 | 0.3-0.7 (INFERRED) | EdgeInstance (SIMILAR_TO) |
| **分类标注** | 自动将实体归入分类体系 | 0.5-0.9 (INFERRED) | CategoryTag |
| **模糊匹配** | 低置信度的实体链接或跨域对齐 | 0.1-0.3 (AMBIGUOUS) | EdgeInstance (需人工审查) |

### 不应使用 LLM 提取的内容

| 内容 | 原因 | 正确通道 |
|------|------|----------|
| 类/函数定义 | AST 确定性提取，confidence=1.0 | Pass 1 |
| 导入/调用关系 | AST 确定性提取 | Pass 1 |
| YAML Schema 定义 | 结构化解析，confidence=1.0 | Pass 1 |
| 文档标题/表格 | 正则提取，confidence=1.0 | Pass 1 |

---

## Cognify 6 步管线对齐

参考 Cognee Cognify 管线的 6 步处理流程，OntologyEngine 的 LLM 提取对齐如下：

| Cognee 步骤 | Cognee 功能 | OntologyEngine 对应 | 说明 |
|-------------|------------|-------------------|------|
| 1. resolve_data_directories | 发现数据文件 | 文件发现与分片（Pass 1 前置） | 复用 IngestionService |
| 2. ingest_data | 数据摄入 | KnowledgeFragment 创建 | Pass 1 已完成 |
| 3. extract_chunks | 文本分片 | KnowledgeFragment 分片 | Pass 1 已完成 |
| 4. extract_graph | **图提取** | **Pass 2 LLM 语义提取** | 本文档核心 |
| 5. add_data_points | DataPoint 写入 | EntityInstance/EdgeInstance 写入 | Pass 3 去重后写入 |
| 6. detect_contradictions | 矛盾检测 | 矛盾检测 | Pass 3 执行 |

---

## LLM Prompt 模板

### 实体与关系提取 Prompt

```
你是一个知识图谱提取专家。从以下文档内容中提取实体和关系。

## Schema 定义
{schema_definitions}

## 文档内容
{document_content}

## 提取要求
1. 提取文档中提到的所有业务实体，每个实体必须对应一个已定义的 Fact Object
2. 提取实体间的关系，每个关系必须对应一个已定义的 Relation
3. 为每个提取结果标注置信度：
   - INFERRED (0.4-0.9): 有明确文本证据的语义推断
   - AMBIGUOUS (0.1-0.3): 模糊匹配或跨域对齐，需人工审查

## 输出格式
```json
{
  "entities": [
    {
      "name": "实体名称",
      "fact_object": "domain:FactObjectName",
      "attributes": {"key": "value"},
      "confidence": 0.8,
      "confidence_label": "INFERRED",
      "evidence_text": "支撑此提取的原文片段"
    }
  ],
  "relations": [
    {
      "from_entity": "源实体名称",
      "to_entity": "目标实体名称",
      "relation_name": "关系名称",
      "edge_text": "关系的自然语言描述",
      "confidence": 0.7,
      "confidence_label": "INFERRED",
      "evidence_text": "支撑此提取的原文片段"
    }
  ],
  "categories": [
    {
      "entity_name": "实体名称",
      "dimension_name": "维度名称",
      "value_code": "分类值编码",
      "confidence": 0.6,
      "confidence_label": "INFERRED"
    }
  ]
}
```
```

### 语义相似性检测 Prompt

```
你是一个实体对齐专家。判断以下两个实体是否为同一业务实体的不同表述。

## 实体 A
名称: {entity_a_name}
属性: {entity_a_attributes}
来源: {entity_a_source_file}

## 实体 B
名称: {entity_b_name}
属性: {entity_b_attributes}
来源: {entity_b_source_file}

## 判断标准
- INFERRED (0.4-0.9): 属性高度匹配，名称可能是别名/缩写/不同语言表述
- AMBIGUOUS (0.1-0.3): 名称相似但属性不完整，无法确定

## 输出格式
```json
{
  "is_same_entity": true/false,
  "confidence": 0.7,
  "confidence_label": "INFERRED",
  "reasoning": "判断理由"
}
```
```

### 分类标注 Prompt

```
你是一个分类专家。将以下实体归入合适的分类维度。

## 实体信息
名称: {entity_name}
属性: {entity_attributes}

## 可用分类维度
{available_dimensions}

## 输出格式
```json
{
  "category_assignments": [
    {
      "dimension_name": "维度名称",
      "value_code": "分类值编码",
      "confidence": 0.8,
      "confidence_label": "INFERRED"
    }
  ]
}
```
```

---

## LLM 提取流程

```
输入: uncached_fragments (增量变更文件的 KnowledgeFragment)
  │
  ├─ 1. 批量准备
  │     按 source_file 分组
  │     每组包含: 文件内容 + Schema 定义上下文
  │
  ├─ 2. 实体与关系提取
  │     for each group:
  │       prompt = 实体与关系提取 Prompt
  │       response = llm.invoke(prompt)
  │       entities = parse_entities(response)
  │       relations = parse_relations(response)
  │       categories = parse_categories(response)
  │
  │     产出:
  │       EntityInstance[] (confidence ∈ [0.4, 0.9])
  │       EdgeInstance[] (confidence ∈ [0.4, 0.9])
  │       CategoryTag[] (assigned_by = "llm")
  │
  ├─ 3. 语义相似性检测
  │     candidates = find_similar_entity_pairs(new_entities, existing_entities)
  │     for each pair:
  │       prompt = 语义相似性检测 Prompt
  │       response = llm.invoke(prompt)
  │       if is_same_entity and confidence >= 0.4:
  │         create SIMILAR_TO EdgeInstance
  │       if is_same_entity and confidence < 0.4:
  │         mark as AMBIGUOUS → 人工审查队列
  │
  ├─ 4. 生成 EntityInstance
  │     id = UUID5(namespace, identity_fields)
  │     _fact_object = 从 Schema 定义推断
  │     attributes = LLM 提取的属性
  │     confidence = LLM 输出的置信度
  │     source_pipeline = "llm_extraction"
  │     source_content_hash = SHA256(fragment.text + relative_path)
  │
  ├─ 5. 生成 EdgeInstance
  │     from_id / to_id = 通过实体名称查找或创建
  │     relation_name = LLM 提取的关系类型
  │     edge_text = LLM 生成的关系描述
  │     confidence = LLM 输出的置信度
  │     source_pipeline = "llm_extraction"
  │
  ├─ 6. 生成 CategoryTag
  │     entity_id = EntityInstance.id
  │     dimension_name = LLM 推断的维度
  │     value_code = LLM 推断的分类值
  │     assigned_by = "llm"
  │     confidence = LLM 输出的置信度
  │
  └─ 7. 创建 SUPPORTED_BY 边
        KnowledgeFragment → EntityInstance
        edge_text = "{fragment} 支撑了 {entity} 的业务判断"
        confidence = 继承 LLM 提取的置信度
```

---

## 置信度标签体系

### 标签定义

| 标签 | confidence 范围 | 语义 | 典型场景 | 后续动作 |
|------|----------------|------|----------|----------|
| EXTRACTED | 1.0 | AST 确定性提取 | 结构化数据直接映射 | 无需审查 |
| INFERRED | 0.4-0.9 | LLM 语义推断 | 实体关系提取、分类标注 | 可选审查 |
| AMBIGUOUS | 0.1-0.3 | 模糊匹配 | 低置信度实体链接、跨域对齐 | **必须人工审查** |

### 标签与产出类型的典型组合

| 产出类型 | EXTRACTED | INFERRED | AMBIGUOUS |
|----------|-----------|----------|-----------|
| EntityInstance | ✅ AST 提取 | ✅ LLM 提取 | ⚠️ 模糊匹配 |
| EdgeInstance (业务关系) | ✅ AST 提取 | ✅ LLM 提取 | ⚠️ 可能 |
| EdgeInstance (SIMILAR_TO) | ❌ | ✅ 语义相似 | ⚠️ 跨域对齐 |
| CategoryTag | ✅ 规则归类 (assigned_by="rule") | ✅ LLM 归类 (assigned_by="llm") | ⚠️ 可能 |
| EXTRACTED_FROM 边 | ✅ AST 提取时 | ❌ | ❌ |
| SUPPORTED_BY 边 | ⚠️ 少见 | ✅ LLM 推断 | ⚠️ 可能 |

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify VALID_CONFIDENCES | {EXTRACTED, INFERRED, AMBIGUOUS} 三级标签 | 复用三级标签体系，增加数值范围 |
| Graphify validate_extraction | AMBIGUOUS 边标记为需人工审查 | AMBIGUOUS 产出进入人工审查队列 |
| Cognee feedback_weight | 流式更新权重调整置信度 | feedback_weight 独立于 confidence，参与检索评分 |

---

## AMBIGUOUS 产出处理

### 目的

对低置信度（AMBIGUOUS）的 LLM 提取结果进行人工审查，确保知识图谱质量。

### 处理流程

```
AMBIGUOUS 产出
  │
  ├─ 1. 标记
  │     写入 SQLite ambiguity_reports 表
  │     包含: entity_id/edge_id, confidence, evidence_text, source_file
  │
  ├─ 2. 通知
  │     生成审查任务，通知知识管理员
  │
  ├─ 3. 人工审查
  │     管理员选择:
  │       ① 确认接受 → confidence 提升为 INFERRED 范围
  │       ② 修改后接受 → 更新 attributes/edge_text
  │       ③ 拒绝 → 标记 rejected，从图谱中移除
  │
  └─ 4. 反馈闭环
        审查结果反馈到 LLM prompt 优化
        接受率低的 prompt 模板需调整
```

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify validate_extraction | 强制 schema 验证 + AMBIGUOUS 标记 | 增加人工审查流程 |
| LLM-Wiki-Agent lint.py | 采样语义检查 + 确定性检查 | AMBIGUITY 审查对齐 lint 检测 |
| Cognee apply_feedback_weights | 反馈权重流式更新 | 审查结果影响 feedback_weight |

---

## LLM 调用优化

### 批量处理

| 策略 | 说明 | 参考项目 |
|------|------|----------|
| 文件级批处理 | 同一文件的多个 fragment 合并为一次 LLM 调用 | Cognee chunks_per_batch |
| Schema 上下文注入 | 只注入与当前文件相关的 Schema 定义，减少 token | — |
| 缓存优先 | 语义缓存命中时跳过 LLM 调用 | Graphify check_semantic_cache |
| 推理检查点 | 中断后从检查点恢复，避免重复调用 | — |

### Token 预算控制

```
单次 LLM 调用 token 预算:
  prompt_tokens ≤ 4096 (Schema 上下文 + 文档内容)
  completion_tokens ≤ 2048 (提取结果)

单文件处理策略:
  文件内容 > 4096 tokens → 分片处理，每片独立提取
  文件内容 ≤ 4096 tokens → 整体提取
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-LLM-1 | LLM 只处理 AST 无法覆盖的语义信息 | AST 提取零成本且确定性高，LLM 应只做 AST 做不到的事 |
| D-LLM-2 | 仅处理增量变更文件 | 全量 LLM 提取成本过高，增量处理大幅降低 token 消耗 |
| D-LLM-3 | 分类标注 assigned_by="llm" 而非 "rule" | LLM 推断的分类不是确定性的，必须与规则归类区分 |
| D-LLM-4 | AMBIGUOUS 产出必须人工审查 | 低置信度结果直接入库会污染知识图谱 |
| D-LLM-5 | edge_text 由 LLM 生成 | LLM 提取的关系应有自然语言描述，支持 Bundle Search |
| D-LLM-6 | SUPPORTED_BY 边在 LLM 提取时创建 | LLM 推断的支撑关系是 SUPPORTED_BY 的主要来源 |
| D-LLM-7 | Prompt 模板参数化 | Schema 定义作为参数注入，不同域使用不同的 Schema 上下文 |

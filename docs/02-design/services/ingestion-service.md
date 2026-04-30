# IngestionService 双通道设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

---

## 目的

定义 IngestionService 的双通道摄入架构，将当前同步顺序导入重写为快速通道（同步写入）+ 慢速通道（后台推理）的分离模式，并集成 Schema-Aware 提取、双轨矛盾治理、待审区和 Fragment 管理。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **无双通道分离** | `import_instances` 同步顺序写入实体和关系，LLM 推理阻塞主流程 | 快速通道同步写入 CognitiveNode + 时序链接 + 向量索引，慢速通道后台推理 |
| 2 | **无矛盾检测** | 导入时不检测矛盾，矛盾在查询时才暴露 | Ingest 时 LLM 比对已有知识，生成 CONTRADICTS 边，触发双轨治理 |
| 3 | **无 Dataset 注册** | IngestionService 不处理 Dataset 元数据声明 | Dataset 注册 + linkage_targets 关联 + Fragment 管理 |
| 4 | **无 Fragment 管理** | 不创建 KnowledgeFragment，Layer-R 为空 | 文档切分为 Fragment + 向量索引 + extraction_status 追踪 |
| 5 | **术语陈旧** | 使用 concept_type / EntityInstance(concept) | 统一为 Schema v2：_fact_object / EntityInstance |
| 6 | **无 Schema-Aware 提取** | LLM 提取不利用 Schema 结构，质量不稳定 | 双通道提取：Schema 引导 + 开放提取并行 |
| 7 | **单轨矛盾治理** | 矛盾=阻塞（阻止写入），Agent 无法自治 | 双轨治理：轨道A（企业）+ 轨道B（Agent）+ 待审区 |
| 8 | **无双时序写入** | 只有 valid_from/valid_to，无法区分"何时发生"与"何时知晓" | 增加 recorded_at (T') 同步写入 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│  IngestionService                                                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Dataset 注册                                                │    │
│  │  register_dataset(source_type, source_uri, linkage_targets)  │    │
│  └───────────────────────────┬─────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Fragment 管理                                               │    │
│  │  ingest_document(dataset_id, document)                       │    │
│  │  → 切分 → KnowledgeFragment → 向量索引                       │    │
│  └───────────────────────────┬─────────────────────────────────┘    │
│                              │                                       │
│                 ┌────────────┴────────────┐                         │
│                 ▼                         ▼                         │
│  ┌──────────────────────┐   ┌──────────────────────┐              │
│  │  快速通道 (Fast)      │   │  慢速通道 (Slow)      │              │
│  │  同步，无 LLM         │   │  后台，LLM 推理       │              │
│  │                      │   │                      │              │
│  │  1. EntityNode 写入  │   │  1. 因果推断          │              │
│  │  2. 时序链接         │   │  2. 实体边创建        │              │
│  │  3. 向量索引         │   │  3. 归类标注          │              │
│  │  4. 入队 consolidation│   │  4. 互索引边建立      │              │
│  │     _queue           │   │                      │              │
│  └──────────────────────┘   └──────────────────────┘              │
│                 │                         │                         │
│                 └────────────┬────────────┘                         │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  矛盾检测                                                    │    │
│  │  Ingest 时 LLM 比对 → contradiction_report → 人工确认       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 快速通道（Fast Channel）

### 目的

保证低延迟写入，不调用 LLM，同步完成实体节点创建和基础索引。

### 流程

```
输入: EntityInstance 数据
  ↓
1. 验证 _fact_object 引用存在（EntityDeclaration.name）
  ↓
2. UUID5 确定性 ID 生成（基于 identity_fields）
  ↓
3. 写入 KuzuDB EntityNode
  ↓
4. 时序链接：temporal=true 时创建 PRECEDES/SUCCEEDS 边
  ↓
5. 向量索引：entity_name + entity_summary 写入 ChromaDB
  ↓
6. 入队 consolidation_queue（供慢速通道消费）
  ↓
返回: FastChannelResult(entity_id, status="queued")
```

### 写入模型

```python
@dataclass
class FastChannelResult:
    entity_id: str
    status: str
    queued_for_consolidation: bool
    contradiction_check_pending: bool
```

### 事务边界

batch_size 内原子提交。单条失败记录到 error_log，不回滚整批。

---

## 慢速通道（Slow Channel）

### 目的

后台执行 LLM 推理密集型操作，不阻塞快速通道。

### 流程

```
消费 consolidation_queue
  ↓
1. 因果推断：LLM 分析实体间因果关系 → 创建 LEADS_TO/BECAUSE_OF 边
  ↓
2. 实体边创建：LLM 提取实体间语义关系 → 创建 EdgeInstance
  ↓
3. 归类标注：CategorizationEngine 自动归类 → 创建 CategoryTag
  ↓
4. 互索引边建立：Fragment ↔ EntityInstance 的 EXTRACTED_FROM/SUPPORTED_BY 边
  ↓
5. 更新 EntityInstance.extraction_status = "extracted"
  ↓
返回: SlowChannelResult(edges_created, categories_assigned, mutual_index_edges)
```

### 与 m_flow 对齐

| m_flow 阶段 | OntologyEngine 慢速通道 | 说明 |
|-------------|----------------------|------|
| Phase 0A: 三路并行（实体提取 + Facet 生成 + 匹配器准备） | 因果推断 + 实体边创建 | m_flow 用 LLM 并行提取实体和 Facet |
| Phase 0C: Entity 创建 | 归类标注 | m_flow 创建 Entity 节点并关联 EntityType |
| Step 3-5: Node/Edge 创建 | 互索引边建立 | m_flow 创建 has_facet / involves_entity / supported_by 边 |

### 队列模型

```python
@dataclass
class ConsolidationTask:
    entity_id: str
    fact_object: str
    attributes: dict[str, Any]
    source_fragment_ids: list[str]
    created_at: datetime
```

consolidation_queue 使用 SQLite 表实现，保证持久化和断电恢复。

---

## 矛盾检测

### 目的

在摄入时发现同一业务实体从不同来源获取时的矛盾，阻止不一致数据写入图谱。

### 检测时机

| 时机 | 触发条件 | 行为 |
|------|---------|------|
| **Ingest 时** | 新 EntityInstance 的 identity_fields 匹配已有实体 | LLM 比对新旧属性值，发现矛盾则创建 CONTRADICTS 边，分流到对应轨道 |
| **后台扫描** | 定期批次检测 | 发现矛盾通知管理员，不阻塞日常查询 |

### Ingest 时检测流程

```
新 EntityInstance
  ↓
1. 根据 identity_fields 查找已有实体（UUID5 确定性 ID）
  ↓
2. 已有实体存在？
  ├─ 否 → 直接写入（快速通道）
  └─ 是 → LLM 比对属性值
       ↓
3. LLM 判断是否矛盾
  ├─ 无矛盾 → 合并属性（取最新值）
  ├─ 矛盾 → 创建 CONTRADICTS 边 + belief_status=pending_review（分流到待审区）
  └─ 不确定 → 标记 AMBIGUOUS，入队人工审查
```

### contradiction_report 模型

```python
@dataclass
class ContradictionReport:
    report_id: str
    entity_id: str
    field: str
    old_value: Any
    new_value: Any
    old_source: str
    new_source: str
    confidence: float
    status: str
    resolution: str | None
```

### 人工确认

```
contradiction_report 生成
  ↓
通知知识管理员（API / MCP 事件）
  ↓
人工确认：
  ① 接受新，废弃旧（标记 deprecated）
  ② 保留旧，丢弃新（标记 rejected）
  ③ 修改后接受（手动编辑解决矛盾）
  ↓
更新 contradiction_report.status = "resolved"
```

### 与 LLM-Wiki-Agent 对齐

| LLM-Wiki-Agent | OntologyEngine | 说明 |
|----------------|----------------|------|
| ingest.py: LLM 编译时对比现有 Wiki 内容 | Ingest 时 LLM 比对已有实体属性 | 摄入时即检测矛盾 |
| lint.py: 采样 ≤20 页面语义检查 | 后台定期扫描 | 定期检测跨实体矛盾 |
| ## Contradictions 区块 | contradiction_report 表 | 矛盾记录持久化 |

---

## Dataset 注册

### 目的

管理外部数据源的元数据声明，告诉 OntologyEngine "数据在哪里、如何访问"。

### 接口

```python
async def register_dataset(
    self,
    source_type: str,
    source_uri: str,
    linkage_targets: list[str],
    metadata: dict | None = None,
) -> DatasetInfo
```

### Dataset 模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 唯一标识 |
| `source_type` | enum | table / api / file / stream |
| `source_uri` | string | 访问 URI |
| `linkage_targets` | list[str] | 链接到的 Schema ID |
| `metadata` | dict | owner、tags、sensitivity_level 等 |

### 数据流

```
Dataset（声明）
  └── linkage_targets → Schema ID
       ↓
  实际数据（外部系统）
       ↓ IngestionService.ingest_document()
  KnowledgeFragment（Layer-R 存储）
       ↓ extracted_from 边
  EntityInstance（Layer-S 实体）
```

---

## Fragment 管理

### 目的

将文档切分为 KnowledgeFragment，建立向量索引，管理提取状态。

### 接口

```python
async def ingest_document(
    self,
    dataset_id: str,
    document: DocumentInput,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> IngestDocumentResult
```

### 切分策略

| 数据类型 | 切分方式 | 说明 |
|----------|---------|------|
| 文档 | 800 字符块，100 字符 overlap，优先段落边界 | 默认策略 |
| 表格式数据 | 每行作为一个 Fragment | 结构化数据 |
| API 响应 | 每个字段值作为一个 Fragment | 键值对数据 |

### Fragment 生命周期

```
创建 (extraction_status=pending)
  ↓
快速通道写入 (vector_id=null)
  ↓
向量索引建立 (extraction_status → extracted, vector_id 赋值)
  ↓
慢速通道提取 (建立 extracted_from 边)
  ↓
提取失败 (extraction_status=failed)
```

---

## 完整接口清单

| 方法 | 通道 | 说明 |
|------|------|------|
| `register_dataset(source_type, source_uri, linkage_targets)` | — | Dataset 注册 |
| `ingest_document(dataset_id, document, chunk_size, chunk_overlap)` | 快速 | 文档切分 + Fragment 创建 + 向量索引 |
| `ingest_entity(fact_object, attributes, identity_fields)` | 快速 | EntityNode 同步写入 |
| `ingest_entities_batch(entities, batch_size)` | 快速 | 批量实体写入 |
| `get_consolidation_status(entity_id)` | — | 查询慢速通道处理状态 |
| `resolve_contradiction(report_id, resolution)` | — | 人工确认矛盾 |
| `list_contradictions(status, dataset_id)` | — | 列出矛盾报告 |
| `validate_import(request)` | — | 验证导入数据（不持久化） |

---

## 与 MAMGA Structural Consolidation 对齐

| MAMGA 概念 | OntologyEngine 对应 | 说明 |
|-----------|-------------------|------|
| EventNode（原始内容） | KnowledgeFragment | Layer-R 原始知识碎片 |
| EpisodeNode + SessionNode | EntityInstance + 时序链接 | Layer-S 结构化实体 |
| PRECEDES/SUCCEEDS 时序链 | valid_from/valid_to + PRECEDES/SUCCEEDS 边 | 时序建模 |
| LEADS_TO/BECAUSE_OF 因果边 | 慢速通道因果推断产出 | 因果关系 |
| NARRATIVE 叙事聚合 | 慢速通道归类标注 | 自动归类 |

---

## Schema-Aware 提取 [新增]

> **[关键设计点]**：双通道提取——Schema 引导通道 + 开放提取通道并行，保证 Schema 覆盖范围之外的发现能力。

### 通道 A：Schema 引导提取

```
输入: Fragment + Schema L1 EntityDeclaration
  ↓
1. 匹配 Fragment 内容到 Schema 实体类型
  ↓
2. 注入提取模板（"提取 Counterparty 时必须包含 debt_ratio 字段"）
  ↓
3. LLM 按模板提取 → 高 alignment_score（平均 0.8+）
  ↓
4. 写入 CognitiveNode(memory_type=entity, schema_ref=EntityDeclaration.name)
```

### 通道 B：开放提取

```
输入: Fragment（无 Schema 匹配）
  ↓
1. LLM 自由提取所有可能的关系和模式
  ↓
2. 不受 Schema 约束，可能发现 Schema 外的新实体/关系
  ↓
3. 写入 CognitiveNode(memory_type=observation, belief_status=pending_review)
  ↓
4. 积累到阈值后触发 Schema 扩展建议
```

### 双通道协调

```python
async def extract_with_dual_channel(fragment, schema_registry):
    schema_matches = schema_registry.match(fragment)
    
    if schema_matches:
        results_a = await schema_guided_extract(fragment, schema_matches)
        results_b = await open_extract(fragment, exclude=schema_matches)
    else:
        results_a = []
        results_b = await open_extract(fragment)
    
    all_results = results_a + results_b
    
    for result in all_results:
        if result.schema_aligned:
            result.belief_status = "accepted"
        else:
            result.belief_status = "pending_review"
    
    return all_results
```

---

## 双轨矛盾治理 [新增]

> **[关键设计点]**：矛盾不再阻塞写入，而是分流到不同轨道处理。

### 三区模型

```
Agent 自治区（轨道B）          待审区              企业治理区（轨道A）
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│ Agent 自动     │    │ belief_status=    │    │ 人工确认的    │
│ 生成/更新记忆 │───▶│ pending_review    │───▶│ 正式知识      │
│               │    │                   │    │               │
│ 可自由检索    │    │ 可检索但带标记    │    │ 可自由检索    │
│ 可自由遗忘    │    │ 不可遗忘          │    │ 不可自由遗忘  │
│ confidence自评│    │ 等待人工决策      │    │ confidence=1.0│
└──────────────┘    └──────────────────┘    └──────────────┘
```

### 矛盾检测流程

```
新 CognitiveNode
  ↓
1. 根据 entity_name + schema_ref 查找已有 CognitiveNode
  ↓
2. 已有节点存在？
  ├─ 否 → 直接写入（快速通道）
  └─ 是 → LLM 比对属性值
       ↓
3. LLM 判断是否矛盾
  ├─ 无矛盾 → 合并属性（取最新值）
  ├─ 矛盾（企业知识） → 创建 CONTRADICTS 边 + belief_status=pending_review
  └─ 矛盾（Agent 记忆） → 创建 CONTRADICTS 边 + 轨道B自治处理
```

### 自动晋升条件

```python
def can_auto_promote(node, disposition):
    if node.confidence > 0.9 and node.proof_count >= 3:
        if disposition.skepticism < 0.7:
            return True
    return False
```

### 人工审批接口

```python
async def approve_memory(node_id, action, modifier_id, comment=None):
    node = await get_cognitive_node(node_id)
    
    if action == "approve":
        node.belief_status = "accepted"
        node.confidence = 1.0
    elif action == "reject":
        node.belief_status = "rejected"
    elif action == "modify":
        node.belief_status = "accepted"
        node.attributes.update(modified_attrs)
    
    await update_cognitive_node(node)
    await create_approval_record(node_id, action, modifier_id, comment)
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-ING-1 | 快速通道不调用 LLM | 保证低延迟，LLM 调用延迟 1-5 秒不可接受 |
| D-ING-2 | 慢速通道使用 SQLite 持久化队列 | 断电恢复保证，比内存队列更可靠 |
| D-ING-3 | 矛盾检测在 Ingest 时触发 | 矛盾越早发现越好，但不阻塞写入 |
| D-ING-4 | UUID5 确定性 ID | 同一业务实体从不同管道摄入时产出相同 ID，支持幂等写入 |
| D-ING-5 | Fragment 切分默认 800 字符 | 平衡检索精度和上下文完整性，与 MemPalace 对齐 |
| D-ING-6 | 双通道提取（Schema引导+开放提取） | Schema引导保证质量，开放提取保证发现能力 |
| D-ING-7 | 矛盾分流而非阻塞 | Agent 需要自治工作流，阻塞会严重影响效率 |
| D-ING-8 | 待审区记忆可检索但带标记 | 不阻塞Agent工作流，同时保证信息透明 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Instance 层 EntityInstance 定义 | `docs/02-design/schema/instance-layer.md` |
| KnowledgeFragment 定义 | `docs/02-design/schema/instance-layer.md` |
| 矛盾检测概念 | `docs/01-overview/05-concepts.md` |
| Dataset 概念 | `docs/01-overview/05-concepts.md` |
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
| 知识库流程主文档 | `docs/01-overview/10-kb-process.md` |
| 审查辩论文档 | `discuss/2026-04-30-kb-memory-design-adversarial-review.md` |

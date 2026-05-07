# 时序建模 Grammar

> **status**: draft | **phase**: rewrite | **source_of_truth**: [01-overview/05-concepts.md](../../01-overview/05-concepts.md) + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

## 目的

定义 OntologyEngine 中时序数据（temporal data）的建模语法，使系统能够对时间敏感的业务实体进行版本化管理、时间点查询和历史轨迹追踪。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 无时序建模 grammar，时序实体与静态实体无法区分 | 金融数据、合同、担保敞口等时间敏感数据无法正确管理 |
| 2 | 缺少 valid_from / valid_to 语义定义 | 无法表达"某事实在何时有效" |
| 3 | 无时序查询语义规范 | 查询当前版本、指定时点、全量历史三种需求无法统一路由 |
| 4 | 无时序边类型定义 | 事件先后、因果关系无法在图中表达 |
| 5 | 无版本限制策略 | 时序实体版本无限增长导致存储膨胀 |
| 6 | 无双时序支持（recorded_at） | 无法区分"事件何时发生"与"系统何时知晓"，更正传播语义不完整 |
| 7 | 无 SUPERSEDES/CONTRADICTS 边 | 更正链和矛盾链无法在图中表达 |
| 8 | 版本淘汰策略不完善 | 被淘汰版本被引用时处理不完整，SUPERSEDED→ACTIVE 回退路径缺失 |

---

## 1. EntityDeclaration 级 temporal 声明

### 目的

在 L1 EntityDeclaration 层标注实体是否为时序实体，并声明确定性 ID 生成所需的字段。

### 解决的问题

静态实体（法人姓名、营业执照号）与时序实体（注册资本、营收数据）在存储和查询上需要完全不同的处理策略，必须在声明层显式区分。

### Grammar

```yaml
- name: string
  temporal: boolean = false
  identity_fields: [string]?
  attributes:
    - name: string
      type: string
  relations:
    - name: string
      target: string
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `temporal` | boolean | `false` | 是否为时序实体。`true` 时 Instance 层自动携带 valid_from / valid_to |
| `identity_fields` | list\[string\]? | `null` | 确定性 ID 生成字段（借鉴 Cognee identity_fields + UUID5）。指定后，相同字段值生成相同 ID，实现幂等写入 |

### 示例

```yaml
- name: Company
  temporal: true
  identity_fields: ["unified_social_credit_code"]
  attributes:
    - name: unified_social_credit_code
      type: string
    - name: registered_capital
      type: Money
    - name: risk_grade
      type: RiskGrade

- name: LegalForm
  temporal: false
  attributes:
    - name: name
      type: string
    - name: code
      type: string
```

---

## 2. EntityInstance 时序字段

### 目的

为时序实体的 Instance 定义 valid_from / valid_to 字段语义，明确三种查询语义的实现规则。

### 解决的问题

时序实体的 Instance 需要记录"事实何时生效、何时失效"，否则无法回答"该实体在某时点的状态是什么"。

### 字段定义

| 字段 | 类型 | 语义 | 约束 |
|------|------|------|------|
| `valid_from` | date? | 事实生效时间。`null` 表示从创建起生效 | 时序实体必填（可 null） |
| `valid_to` | date? | 事实失效时间。`null` 表示当前有效 | 时序实体必填（可 null） |

### Instance 示例

```yaml
entity_instance:
  id: "ent_001"
  _entity_declaration: "finance:Company"
  registered_capital: 50000000
  valid_from: "2025-06-01"
  valid_to: null
```

### 三种查询语义

| 查询类型 | 条件 | 返回 | 默认行为 |
|----------|------|------|----------|
| 当前版本 | `valid_to IS NULL` | 单条 | **默认**。`query_entity(id)` |
| 指定时点 | `valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)` | 单条 | `query_entity(id, as_of=date)` |
| 全量历史 | 无过滤 | 多条 | `query_entity(id, include_history=true)` |

**默认行为**：返回当前版本。若结果为空，调用方显式查询历史版本。

---

## 3. 时序边类型

### 目的

定义图中表达时间顺序和因果关系的边类型，使图结构能够承载时序推理。

### 解决的问题

传统知识图谱的边仅表达静态关系（如"担保"），无法表达"事件 A 先于事件 B"或"事件 A 导致事件 B"，时序推理无法在图上执行。

### 时序链接边

| 边类型 | 方向 | 携带属性 | 语义 |
|--------|------|----------|------|
| `PRECEDES` | A → B | `time_delta: timedelta` | A 在时间上先于 B |
| `SUCCEEDS` | B → A | `time_delta: timedelta` | B 在时间上后于 A（PRECEDES 的逆边） |

**参考**：MAMGA 时序共振图中 EVENT 节点通过 PRECEDES/SUCCEEDS 链接形成时序链。

### 因果链接边

| 边类型 | 方向 | 语义 | 参考来源 |
|--------|------|------|----------|
| `LEADS_TO` | A → B | A 导致 B | MAMGA |
| `BECAUSE_OF` | B → A | B 因为 A（LEADS_TO 逆边） | MAMGA |
| `ENABLES` | A → B | A 使 B 成为可能 | MAMGA |
| `PREVENTS` | A → B | A 阻止 B | MAMGA |

### 跨域实体对齐边

| 边类型 | 方向 | 携带属性 | 语义 |
|--------|------|----------|------|
| `same_entity_as` | A → B | `confidence: float` | A 与 B 是不同域中的同一实体 |

**参考**：m_flow canonical_name + same_entity_as 跨域对齐模式。

### 边权重与查询路由

| 查询类型 | 边权重偏好 | 说明 |
|----------|-----------|------|
| temporal | TEMPORAL×3.0 | 时序查询优先沿 PRECEDES/SUCCEEDS 遍历 |
| multi-hop | CAUSAL×2.0, TEMPORAL×1.0 | 多跳推理优先沿因果边遍历 |
| factual | 无偏好 | 事实查询不涉及时序边 |

---

## 4. 时序查询语义

### 目的

规范时序查询的四种模式及其实现条件，确保查询引擎对时序数据有一致的路由逻辑。

### 解决的问题

缺少统一的时序查询语义规范，不同查询场景（当前快照、历史回溯、变更轨迹）的实现逻辑分散且不一致。

### 查询语义表

| 查询类型 | 条件 | 返回 | 示例 |
|----------|------|------|------|
| 当前版本 | `valid_to IS NULL` | 单条 | "华为当前注册资本是多少" |
| 指定时点 | `valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)` | 单条 | "华为 2024 年底的注册资本" |
| 全量历史 | 无过滤 | 多条 | "华为注册资本的所有变更记录" |
| 变更轨迹 | `ORDER BY valid_from` | 有序列表 | "华为注册资本变更时间线" |

### 查询路由

```
query_entity(id)
  ↓ EntityDeclaration.temporal?
  ├── false → 直接返回唯一 Instance
  └── true  → valid_to IS NULL → 当前版本
              ↓ 为空?
              → 返回空 + 提示调用方查询历史

query_entity(id, as_of=date)
  ↓ EntityDeclaration.temporal?
  ├── false → 直接返回唯一 Instance（忽略 as_of）
  └── true  → valid_from <= date AND (valid_to IS NULL OR valid_to > date)

query_entity(id, include_history=true)
  ↓ EntityDeclaration.temporal?
  ├── false → 返回唯一 Instance
  └── true  → 返回所有版本，按 valid_from 排序
```

---

## 5. 版本限制策略

### 目的

防止单个时序实体的版本无限增长，确保存储和查询性能可预期。

### 解决的问题

时序实体（如每日更新的财务指标）长期运行后版本数可能达到数千甚至数万，导致查询性能退化、存储膨胀。

### 策略

| 参数 | 值 | 说明 |
|------|-----|------|
| 单实体最大版本数 | 100 | 超过此阈值触发版本淘汰 |
| 超限策略 | 删除最老版本 | 按 valid_from 升序，删除最早的版本 |
| 淘汰时机 | 写入新版本时 | 惰性淘汰，不主动扫描 |

### 实现逻辑

```
写入新版本
  ↓
查询当前版本数
  ↓ count > 100?
  ├── false → 直接写入
  └── true  → 删除 valid_from 最早的版本 → 写入新版本
```

**注意**：被淘汰的版本如果被互索引边引用，需先解除引用关系或标记为 `orphan_reference`。

---

## 6. 参考项目对齐

### 目的

明确 OntologyEngine 时序建模 grammar 与四个参考项目的对齐关系，确保设计决策有据可依。

### 解决的问题

时序建模涉及多个维度（时态窗口、时间置信度、事件时间戳、软删除），不同参考项目各有侧重，需要显式记录借鉴与偏离。

### 对齐矩阵

| OE 特性 | MemPalace | m_flow | Cognee | KAG |
|---------|-----------|--------|--------|-----|
| valid_from / valid_to 时态窗口 | ✅ 借鉴 | - | - | - |
| invalidate 软删除 | ✅ 借鉴 | - | - | - |
| mentioned_time_* 时间范围+置信度 | - | ✅ 借鉴 | - | - |
| Event.at/during (Timestamp/Interval) | - | - | ✅ 借鉴 | - |
| 显式时间模型 | - | - | - | ❌ 无 |

### 各项目详情

**MemPalace**：

- 每个 triple 携带 `valid_from` 和 `valid_to` 时间戳
- `invalidate()` 方法设置 `valid_to`，标记事实不再为真
- 查询时通过 `as_of` 参数获取特定时间点的事实
- 时间线查询：`mempalace_kg_timeline` 工具

**m_flow**：

- `mentioned_time_start` / `mentioned_time_end` 字段表达时间范围
- `mentioned_time_confidence` 字段表达时间信息的置信度
- 适用于非结构化文本中提取的时间信息（模糊、不精确）

**Cognee**：

- `Event.at`：精确时间戳（Timestamp）
- `Event.during`：时间区间（Interval）
- 明确区分时间点和时间段两种语义

**KAG**：

- 无显式时间模型
- 时间信息作为普通属性存储，无特殊查询语义
- OE 在此维度为独立设计

---

## 7. 双时序模型 [新增]

> **[关键设计点]**：双时序区分"事实有效时间"（T）和"系统记录时间"（T'），是更正传播和矛盾治理的基础。

### 目的

区分"事件何时发生"与"系统何时知晓"，使更正传播的时序语义完整。

### 解决的问题

单时序（valid_from/valid_to）无法回答：
- "系统何时收到更正？" → 需要 recorded_at (T')
- "更正的实际发生时间与系统记录时间是否一致？" → 需要 occurred_at
- "更正传播应基于哪个时间？" → 传播优先级应基于 occurred_at 而非 recorded_at

### 字段定义

| 字段 | 类型 | 语义 | 说明 |
|------|------|------|------|
| `valid_from` | datetime? | 事实有效起始时间（T） | 继承自单时序模型 |
| `valid_to` | datetime? | 事实有效终止时间（T） | 继承自单时序模型 |
| `recorded_at` | datetime? | 系统记录时间（T'） | **新增**——系统何时收到此信息 |
| `occurred_at` | datetime? | 事件实际发生时间 | **新增**——事件何时实际发生 |

### 典型案例

```
Day 10: observation("华为涉诉") 创建
  valid_from = Day 10, valid_to = null
  recorded_at = Day 10, occurred_at = Day 10

Day 20: 用户更正"诉讼已撤诉"
  旧 observation: valid_to = Day 20
  新 observation("撤诉"):
    valid_from = Day 20, valid_to = null
    recorded_at = Day 20  ← 系统何时收到更正
    occurred_at = Day 18  ← 撤诉实际发生时间

关键区别：
  recorded_at = Day 20 → 系统在 Day 20 才知道撤诉
  occurred_at = Day 18  → 撤诉实际在 Day 18 就发生了
  级联更新应基于 occurred_at 而非 recorded_at
```

### 新增查询语义

| 查询类型 | 条件 | 返回 | 示例 |
|----------|------|------|------|
| 更正历史 | `SUPERSEDES 边 + ORDER BY recorded_at` | 有序列表 | "华为涉诉信息的更正历史" |
| 系统知晓时点 | `recorded_at <= as_of` | 单条 | "系统在 Day 15 时知道什么" |
| 事件时序 | `occurred_at ORDER BY` | 有序列表 | "华为相关事件的时间线" |

---

## 8. SUPERSEDES 与 CONTRADICTS 边 [新增]

> **[关键设计点]**：SUPERSEDES 表达更正链，CONTRADICTS 表达矛盾链。两者是双轨矛盾治理的图结构基础。

### SUPERSEDES 边

| 字段 | 类型 | 语义 |
|------|------|------|
| `supersede_reason` | string | 更正原因：correction / update / invalidation |
| `supersede_type` | string | 更正类型：full（完全取代）/ partial（部分取代） |
| `confidence` | double | 更正置信度 |
| `recorded_at` | datetime | 系统记录更正的时间（T'） |

```cypher
CREATE REL TABLE SUPERSEDES (
    FROM CognitiveNode TO CognitiveNode,
    id              STRING,
    supersede_reason STRING,
    supersede_type  STRING,
    confidence      DOUBLE DEFAULT 1.0,
    recorded_at     DATETIME,
    created_at      DATETIME
)
```

### CONTRADICTS 边

| 字段 | 类型 | 语义 |
|------|------|------|
| `contradiction_type` | string | 矛盾类型：factual / temporal / semantic |
| `contradiction_field` | string | 矛盾字段名 |
| `old_value` | string | 旧值 |
| `new_value` | string | 新值 |
| `resolution_status` | string | 解决状态：pending / resolved_track_a / resolved_track_b / ignored |

```cypher
CREATE REL TABLE CONTRADICTS (
    FROM CognitiveNode TO CognitiveNode,
    id                  STRING,
    contradiction_type  STRING,
    contradiction_field STRING,
    old_value           STRING,
    new_value           STRING,
    confidence          DOUBLE DEFAULT 1.0,
    resolution_status   STRING DEFAULT 'pending',
    created_at          DATETIME
)
```

### SUPERSEDES 链查询

```cypher
MATCH (new:CognitiveNode)-[r:SUPERSEDES]->(old:CognitiveNode)
WHERE new.space_id = $space_id AND old.entity_name = $entity_name
RETURN new, old, r ORDER BY r.recorded_at DESC
```

### CONTRADICTS 链查询

```cypher
MATCH (a:CognitiveNode)-[r:CONTRADICTS]->(b:CognitiveNode)
WHERE a.space_id = $space_id AND r.resolution_status = 'pending'
RETURN a, b, r
```

### belief_status 状态机（含回退路径）

```
accepted ──[矛盾检测]──▶ pending_review ──[人工确认]──▶ accepted
                                              │
                                              ├──[人工拒绝]──▶ rejected
                                              └──[人工修改]──▶ accepted (modified)

accepted ──[更正写入]──▶ superseded (superseded_by 指向新版本)
superseded ──[更正撤销]──▶ accepted (superseded_by 清空)  ← 新增回退路径

pending_review ──[超时未审]──▶ accepted (自动晋升，需 confidence > 0.9)
rejected ──[重新提交]──▶ pending_review
```

---

## 9. 版本淘汰策略（修订）

### 修订内容

原策略"删除最老版本"存在引用完整性风险，修订为"先归档再删除+引用检查"。

### 新策略

| 参数 | 值 | 说明 |
|------|-----|------|
| 单实体最大版本数 | 100 | 超过此阈值触发版本淘汰 |
| 超限策略 | 先归档再删除 | 按 valid_from 升序，先检查引用再删除 |
| 淘汰时机 | 写入新版本时 | 惰性淘汰，不主动扫描 |
| 引用检查 | 检查 SUPERSEDES/CONTRADICTS 边 | 被引用的版本不删除，标记为 archived |

### 实现逻辑

```
写入新版本
  ↓
查询当前版本数
  ↓ count > 100?
  ├── false → 直接写入
  └── true  → 查找 valid_from 最早的版本
       ↓
       检查引用关系
       ├── 有 SUPERSEDES/CONTRADICTS 边引用 → 标记 archived，跳过删除
       └── 无引用 → 删除 → 写入新版本
```

---

## 10. CONTRADICTS 边自动触发条件 [新增]

### 触发时机

| 触发源 | 触发条件 | contradiction_type | 处理策略 |
|--------|---------|-------------------|---------|
| Ingestion 写入 | 新 CognitiveNode 与同 entity_name 已有节点的属性值冲突 | factual | 自动创建 CONTRADICTS 边 + belief_status → pending_review |
| Reflect Agent | detect_contradictions 工具检测到语义矛盾 | semantic | 创建 CONTRADICTS 边 + 生成矛盾报告 |
| 梦境循环 | 定期扫描同 entity_name 多版本间的时序重叠 | temporal | 创建 CONTRADICTS 边 + 标记 resolution_status |
| 人工标注 | 用户通过 UI 标注矛盾 | 任意 | 创建 CONTRADICTS 边 + resolution_status = pending |

### 自动触发逻辑

```python
async def check_contradiction_on_ingest(new_node: CognitiveNode, space_id: str):
    existing = await find_same_entity_nodes(
        entity_name=new_node.entity_name,
        entity_type=new_node.entity_type,
        space_id=space_id,
        belief_status="accepted",
    )

    for node in existing:
        if node.id == new_node.id:
            continue

        conflicts = detect_field_conflicts(new_node, node)
        for field, old_val, new_val in conflicts:
            await create_contradicts_edge(
                from_id=new_node.id,
                to_id=node.id,
                contradiction_type="factual",
                contradiction_field=field,
                old_value=old_val,
                new_value=new_val,
            )
            await update_belief_status(node.id, "pending_review")
            await update_belief_status(new_node.id, "pending_review")

def detect_field_conflicts(
    new_node: CognitiveNode, existing: CognitiveNode
) -> list[tuple[str, str, str]]:
    conflicts = []
    for key in set(new_node.attributes.keys()) & set(existing.attributes.keys()):
        if new_node.attributes[key] != existing.attributes[key]:
            conflicts.append((key, existing.attributes[key], new_node.attributes[key]))
    return conflicts
```

---

## 11. 双时序查询与 query-routing 集成 [新增]

### 查询语义映射

| temporal-modeling 查询语义 | query-routing 查询类型 | 参数 |
|---------------------------|----------------------|------|
| 当前版本 (valid_to IS NULL) | factual | 无时序参数 |
| 指定时点 (valid_from <= as_of AND valid_to > as_of) | temporal | as_of 参数 |
| 系统知晓时点 (recorded_at <= as_of) | temporal | as_of + use_recorded_at=true |
| 全量历史 | temporal | include_history=true |

### query-routing 参数扩展

```python
class TemporalQueryParams(BaseModel):
    as_of: datetime | None = None
    use_recorded_at: bool = False
    include_history: bool = False
    period_start: datetime | None = None
    period_end: datetime | None = None
```

---

## 12. occurred_at 提取策略 [新增]

### 提取方法

| 方法 | 优先级 | 适用场景 | 精度 |
|------|--------|---------|------|
| Schema L1 temporal_fields | 最高 | 结构化数据（如财报日期字段） | 精确 |
| LLM 提取 | 中 | 非结构化文本（如"2024年第三季度"） | 较高 |
| 正则提取 | 低 | 标准日期格式（如"2024-01-15"） | 中 |
| recorded_at 回退 | 最低 | 无法提取时 | 低 |

### 提取流程

```python
async def extract_occurred_at(
    text: str,
    schema: EntityDeclaration | None = None,
    extracted_attributes: dict | None = None,
) -> datetime | None:
    if schema and schema.temporal_fields:
        for field_name in schema.temporal_fields:
            if extracted_attributes and field_name in extracted_attributes:
                return parse_datetime(extracted_attributes[field_name])

    date_patterns = [
        r'\b(\d{4})年(\d{1,2})月(\d{1,2})日\b',
        r'\b(\d{4})-(\d{2})-(\d{2})\b',
        r'\b(\d{4})[年Q](\d{1,2})\b',
    ]
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return parse_date_match(match)

    return None
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 核心概念（单一事实源） | [01-overview/05-concepts.md](../../01-overview/05-concepts.md) |
| Schema v2 完整规范 | `docs/02-design/schema/01-schema-spec.md` |
| 查询路由设计 | [01-overview/08-knowledge-retrieval.md](../../01-overview/08-knowledge-retrieval.md) |
| 参考项目对齐分析 | [02-design/schema/reference-alignment.md](./reference-alignment.md) |
| 知识库流程主文档 | `docs/01-overview/10-kb-process.md` |
| 审查辩论文档 | `discuss/2026-04-30-kb-memory-design-adversarial-review.md` |

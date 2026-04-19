# 时序建模 Grammar

> **status**: draft | **phase**: rewrite | **source_of_truth**: [01-overview/05-concepts.md](../../01-overview/05-concepts.md) | **last_verified**: 2026-04-19

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

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 核心概念（单一事实源） | [01-overview/05-concepts.md](../../01-overview/05-concepts.md) |
| Schema v2 完整规范 | `docs/05-schema-v2/09-canonical-schema-spec.md` |
| 查询路由设计 | [01-overview/08-knowledge-retrieval.md](../../01-overview/08-knowledge-retrieval.md) |
| 参考项目对齐分析 | [02-design/schema/reference-alignment.md](./reference-alignment.md) |

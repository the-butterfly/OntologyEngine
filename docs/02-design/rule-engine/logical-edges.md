# 逻辑边按需计算

> **status**: draft | **phase**: design-only | **source_of_truth**: 本文档（逻辑边机制） | **last_verified**: 2026-04-20

---

## 目的

定义规则引擎中三类逻辑边的语义、触发机制和缓存策略，实现事实数据变更后推理结果的自动更新，对齐 KAG 的 STRUCTURE 块逻辑边模式。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **推理边无按需计算** | 当前代码无 `logical_type` 区分，所有关系同等对待 | 三类逻辑边分类，`inference` 边由规则引擎按需产出 |
| 2 | **事实变更不触发重算** | 事实数据更新后，推理结果仍为旧值 | 事实边变更事件 → 触发关联推理边重新推导 |
| 3 | **推理边无溯源** | 推理结果无法追溯到产生它的规则步骤 | `traceability` 边连接推理步骤与知识碎片 |
| 4 | **无计算缓存** | 每次查询都重新执行完整规则链 | 推理边结果缓存 + 版本标记，仅在依赖变更时重算 |

---

## 三类逻辑边

### 定义

| 类型 | `logical_type` 值 | 含义 | 来源 | 示例 |
|------|-------------------|------|------|------|
| **业务边** | `business` | 事实数据中直接存在的关系 | L1 `RelationDeclaration` 或外部数据导入 | `guarantees`（担保）、`supplies`（供应）、`employs`（雇佣） |
| **推理边** | `inference` | 由规则引擎推导产出的关系 | L4 `RuleLogicDeclaration` 执行结果 | `triggers`（触发）、`depends_on`（依赖）、`risk_contagion`（风险传导） |
| **溯源边** | `traceability` | 连接知识碎片的关系 | 互索引机制 | `extracted_from`、`defined_in`、`trace_to`、`supported_by` |

### 与 L1 Grammar 对齐

L1 `RelationDeclaration.logical_type` 字段声明关系的逻辑类型：

```yaml
relations:
  - name: guarantees
    from: Counterparty
    to: Counterparty
    logical_type: business
    attributes:
      - name: amount
        type: Money
      - name: period
        type: string

  - name: risk_contagion
    from: Counterparty
    to: Counterparty
    logical_type: inference
    attributes:
      - name: contagion_score
        type: decimal
      - name: derived_from_rule
        type: string
      - name: computed_at
        type: datetime
```

### 与 KAG IND# 对齐

KAG 的 `IND#belongTo` 是逻辑边的典型实现：

```
KAG:
  Person.properties:
    IND#belongTo(属于): TaxOfRiskUser

  推理规则 (concept.rule):
    Define (s:Person)-[p:developed]->(o:App) {
      STRUCTURE {
        (s)-[:hasDevice]->(d:Device)-[:install]->(o)
      }
      CONSTRAINT {
        deviceNum = group(s,o).count(d)
        R1("设备超过5"): deviceNum > 5
      }
    }

OntologyEngine 对应:
  Counterparty.relations:
    - name: risk_contagion
      logical_type: inference

  推理规则 (rule_logic):
    - name: determine_risk_contagion
      type: custom
      steps:
        - id: find_guarantee_chain
          action:
            type: compute
            operator: GRAPH
            output: guarantee_chain
        - id: calc_contagion
          depends_on: [find_guarantee_chain]
          action:
            type: compute
            operator: FORMULA
            formula: "sum(chain.weight for chain in guarantee_chain)"
            output: contagion_score
        - id: create_inference_edge
          depends_on: [calc_contagion]
          action:
            type: compute
            operator: FORMULA
            formula: "contagion_score > threshold"
            output: risk_contagion
```

**关键对齐点**：

| KAG 概念 | OntologyEngine 对应 | 说明 |
|----------|-------------------|------|
| `IND#` 前缀 | `logical_type: inference` | 标记推理边 |
| `STRUCTURE` 块 | `Step.depends_on` + `action.operator: GRAPH` | 定义事实边遍历模式 |
| `CONSTRAINT` 块 | `Step.condition` + `action.operator: FORMULA` | 定义约束条件和推导逻辑 |
| `group(s,o).count(d)` | `GRAPH` 算子 + `aggregation: count` | 聚合统计 |
| `R1("设备超过5")` | `Step.condition.expression` | 约束判断 |
| 实时计算 | 按需计算 + 缓存 | 事实变更触发重算 |

---

## 触发机制

### 事实边变更 → 推理边重算

```
外部数据更新 (Dataset 变更)
  ↓
IngestionService 处理
  ↓
Storage 层写入 business 边
  ↓
Storage 层发布 EdgeChangeEvent
  ↓
LogicalEdgeEngine 接收事件
  ↓
查询: 哪些 inference 边依赖此 business 边？
  ↓ (通过 rule_logic.steps 中的 GRAPH 算子依赖分析)
找到关联的 rule_logic
  ↓
触发 DAGExecutor 重新执行关联 rule_logic
  ↓
产出新的 inference 边
  ↓
更新 KuzuDB (替换旧 inference 边)
  ↓
发布 InferenceEdgeUpdatedEvent
```

### 事件模型

```python
class EdgeChangeEvent:
    edge_type: str
    source_id: str
    target_id: str
    change_type: enum
    old_values: dict | None
    new_values: dict | None
    timestamp: str

class InferenceEdgeUpdatedEvent:
    edge_type: str
    source_id: str
    target_id: str
    rule_logic_name: str
    pipeline_run_id: str
    timestamp: str
```

### 依赖分析

推理边对事实边的依赖关系通过 `rule_logic.steps` 中的 `GRAPH` 算子声明：

```yaml
steps:
  - id: find_guarantee_chain
    action:
      type: compute
      operator: GRAPH
      query:
        type: traversal
        relation: guarantees
        depth: 3
        direction: outgoing
      aggregation:
        - type: sum
          field: amount
          output: total_guarantee_amount
```

`LogicalEdgeEngine` 解析 `GRAPH` 算子的 `query.relation` 字段，建立推理边 → 事实边的依赖映射：

```
inference:risk_contagion ← depends_on ← business:guarantees
```

当 `guarantees` 边变更时，自动触发 `risk_contagion` 推理边的重算。

---

## 计算缓存策略

### 缓存模型

```python
class InferenceEdgeCache:
    edge_type: str
    source_id: str
    target_id: str
    computed_values: dict[str, Any]
    computed_at: str
    dependency_hash: str
    rule_logic_name: str
    pipeline_run_id: str
```

### 缓存策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| **版本标记** | 每次重算产出新版本，旧版本标记 `superseded` | 需要审计追踪的场景 |
| **依赖哈希** | 计算依赖事实边的哈希值，哈希不变则跳过重算 | 高频变更但实际值未变的场景 |
| **TTL 过期** | 推理边设置 TTL，过期后标记为 stale，下次查询时重算 | 对实时性要求不高的场景 |
| **主动重算** | 事实边变更事件触发立即重算 | 对实时性要求高的场景 |

### 缓存查询流程

```
查询 inference 边
  ↓
检查缓存:
  ├─ 缓存命中 + dependency_hash 一致 → 返回缓存值
  ├─ 缓存命中 + dependency_hash 不一致 → 触发重算 → 更新缓存 → 返回新值
  ├─ 缓存命中 + TTL 过期 → 标记 stale → 异步重算 → 返回旧值（可选等待新值）
  └─ 缓存未命中 → 同步重算 → 写入缓存 → 返回新值
```

### 依赖哈希计算

```
dependency_hash = SHA256(
  sorted([
    f"{edge.source_id}:{edge.target_id}:{edge.relation}:{json(edge.attributes, sort_keys=True)}"
    for edge in dependent_business_edges
  ])
)
```

---

## 推理边写入

### 写入时机

推理边在 DAGExecutor 执行完 `rule_logic` 后写入 KuzuDB：

```
DAGExecutor 完成 rule_logic 执行
  ↓
LogicalEdgeEngine.process_results()
  ↓
遍历 ExecutionResult:
  ├─ action.type == compute 且 logical_type == inference
  │   → 写入 inference 边到 KuzuDB
  │   → 携带 derived_from_rule、computed_at、dependency_hash
  │
  ├─ action.type == assign_category
  │   → 写入 inference 边 (实体 → 分类维度值)
  │
  └─ 其他 action.type
      → 不产生 inference 边
  ↓
为每条 inference 边建立 traceability 边:
  inference 边 → ExecutionStepSnapshot → KnowledgeFragment
```

### 推理边属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `derived_from_rule` | string | 产出此边的 rule_logic 名称 |
| `computed_at` | datetime | 计算时间 |
| `dependency_hash` | string | 依赖事实边的哈希值 |
| `pipeline_run_id` | string | 产出此边的管道运行 ID |
| `valid_from` | datetime | 推理结果生效时间 |
| `valid_to` | datetime | 推理结果失效时间（被新版本替代时设置） |

### 版本管理

推理边的版本管理对齐 m_flow Procedure 的 `supersedes` 模式：

```
inference:risk_contagion[A→B] v1 (computed_at=2026-04-18)
  ↓ 重算
inference:risk_contagion[A→B] v2 (computed_at=2026-04-19)
  ↓
v1.valid_to = v2.computed_at
v2.supersedes = [v1.id]
```

---

## 实现状态

> **2026-04-20 更新**: 逻辑边持久化暂未实现。当前 DAGExecutor 执行时会在 context 中维护推理结果，但尚不写入 KuzuDB 的 `logical_type=inference` 边。后续将按本文档设计实现按需计算和持久化。

### 与查询引擎协同

### 查询路由

| 查询类型 | 逻辑边偏好 | 说明 |
|----------|-----------|------|
| `factual` | `business` 边优先 | 事实查询不需要推理边 |
| `multi-hop` | `business` + `inference` 边 | 多跳推理可利用推理边 |
| `analytical` | `inference` 边优先 | 分析查询直接使用推理结果 |
| `mixed` | 自适应 | 根据查询意图动态选择 |

### 推理边过滤

QueryEngine 在图遍历时可按 `logical_type` 过滤边：

```python
def traverse_graph(
    start_entity: str,
    relation_types: list[str] | None = None,
    logical_types: list[str] | None = None,
    depth: int = 2,
):
    query = f"""
    MATCH (s)-[r]->(t)
    WHERE s.id = $start_id
    {"AND r.logical_type IN $logical_types" if logical_types else ""}
    {"AND type(r) IN $relation_types" if relation_types else ""}
    RETURN s, r, t
    """
```

---

## 参考文档

| 主题 | 文档 |
|------|------|
| 规则引擎设计概览 | [README.md](./README.md) |
| DAG 执行设计 | [dag-execution.md](./dag-execution.md) |
| L1 RelationDeclaration.logical_type | [L1-L4-declarations.md](../schema/L1-L4-declarations.md) |
| 互索引概念 | [05-concepts.md](../../01-overview/05-concepts.md) |
| KAG Expert Rules DSL | [KAG-Schema.md](file:///Users/dingxuxu/Projects/github/GraphRAGs/KAG-Docs/KAG-Schema.md) |
| m_flow Procedure 版本管理 | [Procedure.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/m_flow/m_flow/core/domain/models/Procedure.py) |

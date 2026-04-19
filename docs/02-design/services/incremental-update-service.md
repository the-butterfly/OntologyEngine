# IncrementalUpdateService 增量更新设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

---

## 目的

定义 IncrementalUpdateService 的完整增量更新架构，将当前仅支持手动 diff 检测的实现重写为支持自动轮询、SHA256 变更检测、影响分析、矛盾扫描和人工确认的完整增量更新服务。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **无自动更新机制** | 仅 `import_with_diff` 手动触发 | 定时轮询 Dataset source_uri，SHA256 变更检测自动触发更新 |
| 2 | **无 SHA256 变更检测** | 全量内容比对 O(n) | SHA256 哈希比对 O(1)，对齐 Cognee source_content_hash |
| 3 | **影响分析不完整** | `compute_impact` 仅列出受影响实体/规则 | 完整影响分析：affected_entities + affected_rules + potential_contradictions + cascade_depth |
| 4 | **无矛盾扫描** | 不检测变更是否引入矛盾 | 变更传播时检测矛盾，触发人工确认 |
| 5 | **无级联深度分析** | 不分析变更传播的深度 | cascade_depth 标识变更影响范围，深度过大时需人工确认 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│  IncrementalUpdateService                                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────┐      ┌─────────────────┐                      │
│  │ Dataset 注册声明  │      │ 自动更新        │ ← 定时轮询           │
│  │ (source_uri)     │ ───▶ │ (后台任务)       │                      │
│  └─────────────────┘      └────────┬────────┘                      │
│                                    │                                │
│  ┌─────────────────┐               │                                │
│  │ API 主动调用     │ ──────────────┤                                │
│  └─────────────────┘               │                                │
│                                    ▼                                │
│                           ┌─────────────────┐                      │
│                           │ SHA256 变更检测  │                      │
│                           │ (O(1) 哈希比对)  │                      │
│                           └────────┬────────┘                      │
│                                    │ 变更检测到                     │
│                                    ▼                                │
│                           ┌─────────────────┐                      │
│                           │ 影响分析        │                      │
│                           │ (Impact         │                      │
│                           │  Analysis)      │                      │
│                           └────────┬────────┘                      │
│                                    │                                │
│                                    ▼                                │
│                           ┌─────────────────┐                      │
│                           │ 关键确认点       │ ◀ 矛盾时触发         │
│                           │ (Critical       │                      │
│                           │  Checkpoints)   │                      │
│                           └────────┬────────┘                      │
│                                    │ 确认通过                      │
│                                    ▼                                │
│                           ┌─────────────────┐                      │
│                           │ 变更传播        │                      │
│                           │ (实体更新 +      │                      │
│                           │  指标重算 +      │                      │
│                           │  规则重执行)     │                      │
│                           └─────────────────┘                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 自动更新机制

### 目的

定期轮询已注册的 Dataset，检测数据源变更并自动触发更新流程。

### 轮询策略

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `poll_interval_seconds` | 3600 | 轮询间隔（秒） |
| `max_concurrent_polls` | 3 | 最大并发轮询数 |
| `retry_on_failure` | True | 失败时重试 |
| `retry_backoff_seconds` | 60 | 重试退避时间 |

### SHA256 变更检测

```
1. 读取 Dataset.source_uri
2. 计算内容 SHA256 哈希
3. 与上次记录的 source_content_hash 比对
4. 哈希相同 → 跳过（无变更）
5. 哈希不同 → 触发更新流程
```

### 检测模型

```python
@dataclass
class ChangeDetection:
    dataset_id: str
    old_hash: str | None
    new_hash: str
    changed: bool
    detected_at: datetime
    content_size_bytes: int
```

---

## 影响分析

### 目的

分析变更对下游实体、规则、指标的传播影响，为人工确认提供决策依据。

### 分析维度

| 维度 | 说明 | 计算方式 |
|------|------|---------|
| `affected_entities` | 直接受影响的实体 ID 列表 | 变更实体 + 关联实体（1 跳） |
| `affected_rules` | 受影响的规则 ID 列表 | 规则的 applies_to 包含受影响实体 |
| `potential_contradictions` | 可能引入的矛盾 | LLM 比对变更前后属性值 |
| `cascade_depth` | 变更传播深度 | 图遍历深度，从变更实体出发 |

### 影响分析输出

```python
@dataclass
class ImpactAnalysisResult:
    dataset_id: str
    affected_entities: list[str]
    affected_rules: list[str]
    affected_metrics: list[str]
    potential_contradictions: list[ContradictionPreview]
    cascade_depth: int
    requires_confirmation: bool
    estimated_recompute_count: int
```

### contradiction_preview 模型

```python
@dataclass
class ContradictionPreview:
    entity_id: str
    field: str
    old_value: Any
    new_value: Any
    old_source: str
    new_source: str
    severity: str
```

### 级联深度分析

```
变更实体 A
  ↓ 1 跳
关联实体 B（通过 guarantees 边）
  ↓ 2 跳
关联实体 C（通过 guarantees 边）
  ↓ 3 跳
...

cascade_depth = 最深传播层数
当 cascade_depth > threshold（默认 3）时，requires_confirmation = True
```

---

## 关键确认点

### 目的

在变更传播前提供人工确认机会，防止错误变更级联扩散。

### 触发条件

| 条件 | 说明 |
|------|------|
| `potential_contradictions` 非空 | 变更可能引入矛盾 |
| `cascade_depth > threshold` | 变更传播深度过大 |
| `affected_rules` 包含关键规则 | 关键业务规则受影响 |
| `estimated_recompute_count > limit` | 重算量过大 |

### 确认流程

```
影响分析完成
  ↓
requires_confirmation?
  ├─ 否 → 自动应用变更
  └─ 是 → 生成确认请求
       ↓
  通知知识管理员
       ↓
  人工确认：
    ① 确认应用（应用变更 + 标记矛盾为已知）
    ② 拒绝应用（回滚变更）
    ③ 部分应用（选择性地应用变更）
       ↓
  记录确认决策到 audit_log
```

---

## 变更传播

### 目的

确认通过后，将变更传播到受影响的实体、指标和规则。

### 传播步骤

```
1. 更新受影响实体的属性值
2. 失效相关指标缓存
3. 重算受影响的 L3 指标（MetricEngine）
4. 重执行受影响的 L4 规则（RuleEngine）
5. 更新 source_content_hash
6. 记录变更日志
```

### 传播模型

```python
@dataclass
class PropagationResult:
    dataset_id: str
    entities_updated: int
    metrics_recomputed: int
    rules_reexecuted: int
    contradictions_resolved: int
    propagation_duration_ms: float
```

---

## 完整接口清单

| 方法 | 说明 |
|------|------|
| `start_auto_polling(poll_interval, max_concurrent)` | 启动自动轮询 |
| `stop_auto_polling()` | 停止自动轮询 |
| `trigger_update(dataset_id)` | 手动触发更新 |
| `detect_changes(dataset_id)` | SHA256 变更检测 |
| `analyze_impact(dataset_id, changes)` | 影响分析 |
| `confirm_propagation(confirmation_id, decision)` | 人工确认 |
| `propagate_changes(dataset_id, changes)` | 执行变更传播 |
| `get_update_status(dataset_id)` | 查询更新状态 |
| `list_pending_confirmations()` | 列出待确认项 |

---

## 与 Cognee 增量处理对齐

| Cognee 概念 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| DataPoint.source_content_hash | EntityInstance.source_content_hash | SHA256 哈希用于增量缓存和去重 |
| SyncOperation（同步操作模型） | ChangeDetection + ImpactAnalysisResult | Cognee 的 SyncOperation 追踪同步状态 |
| create_sync_operation / update_sync_operation | detect_changes / propagate_changes | 同步操作生命周期管理 |
| Pipeline 增量执行 | 变更传播（指标重算 + 规则重执行） | Cognee 的 Pipeline 支持增量执行 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-IU-1 | SHA256 哈希比对而非全量内容比对 | O(1) vs O(n)，适合定时轮询场景 |
| D-IU-2 | 影响分析在变更传播前执行 | 防止错误变更级联扩散 |
| D-IU-3 | cascade_depth 阈值默认 3 | 3 跳以内为常见影响范围，超过则需人工确认 |
| D-IU-4 | 自动轮询使用 asyncio 后台任务 | 不阻塞主线程，可随时启停 |
| D-IU-5 | 确认决策记录到 audit_log | 审计追溯，谁在何时确认了什么变更 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 异步更新机制概念 | `docs/01-overview/04-modules.md` |
| 矛盾检测概念 | `docs/01-overview/05-concepts.md` |
| Instance 层 EntityInstance | `docs/02-design/schema/instance-layer.md` |
| AnalysisService 设计 | `docs/02-design/services/analysis-service.md` |

# FeedbackService 反馈闭环设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/05-concepts.md` | **last_verified**: 2026-04-19

---

## 目的

定义 FeedbackService 的反馈闭环架构，实现用户对检索结果的评分反馈、feedback_weight 流式更新、以及 feedback_weight 参与检索评分的完整闭环。当前代码库中不存在 FeedbackService，本文为全新设计。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **无反馈服务** | 不存在 FeedbackService | 新增 FeedbackService，提供反馈评分接口 |
| 2 | **无 feedback_weight 字段** | EntityInstance 无 feedback_weight | Instance 层已定义 feedback_weight，默认 0.5 |
| 3 | **反馈不影响检索排序** | 检索结果仅按语义相似度排序 | feedback_weight 参与检索评分公式 |
| 4 | **无流式更新机制** | 无权重更新逻辑 | 流式更新：updated = previous + α × (normalized - previous) |
| 5 | **无反馈记录** | 不存储用户反馈历史 | SQLite 存储反馈记录，支持审计和分析 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│  FeedbackService                                                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  反馈评分接口                                                │    │
│  │  submit_feedback(query_id, element_id, score, text)          │    │
│  └───────────────────────────┬─────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  分数归一化                                                  │    │
│  │  normalize(score) = (score - 1) / 4 → [0, 1]                │    │
│  └───────────────────────────┬─────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  流式更新 feedback_weight                                    │    │
│  │  updated = previous + α × (normalized - previous)            │    │
│  │  α = 0.1（学习率，可配置）                                   │    │
│  └───────────────────────────┬─────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  检索评分参与                                                │    │
│  │  final = λ × semantic + (1-λ) × feedback_weight              │    │
│  │  λ = 0.7（语义权重，可配置）                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 反馈评分接口

### 目的

接收用户对检索结果的质量评分，驱动 feedback_weight 更新。

### 接口

```python
async def submit_feedback(
    self,
    query_id: str,
    element_id: str,
    element_type: str,
    score: int,
    text_feedback: str | None = None,
) -> FeedbackResult
```

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `query_id` | string | 关联的查询 ID |
| `element_id` | string | 被评价的图元素 ID（EntityInstance 或 EdgeInstance） |
| `element_type` | string | "entity" 或 "edge" |
| `score` | int | 1-5 分评分（1=很差，5=很好） |
| `text_feedback` | string? | 文字反馈（可选） |

### 验证规则

| # | 规则 | 说明 |
|---|------|------|
| V-FB-1 | score ∈ [1, 5] | 评分范围约束 |
| V-FB-2 | element_id 必须引用已存在的图元素 | 引用完整性 |
| V-FB-3 | element_type ∈ {"entity", "edge"} | 类型枚举约束 |
| V-FB-4 | 同一 query_id + element_id 组合不重复提交 | 幂等性约束 |

---

## 分数归一化

### 公式

```
normalized = (score - 1) / 4

映射：
  score=1 → normalized=0.0  （很差）
  score=2 → normalized=0.25
  score=3 → normalized=0.5  （一般）
  score=4 → normalized=0.75
  score=5 → normalized=1.0  （很好）
```

---

## 流式更新 feedback_weight

### 目的

根据用户反馈流式更新图元素的 feedback_weight，无需全量重算。

### 更新公式

```
updated_weight = previous_weight + α × (normalized_feedback - previous_weight)

α = 0.1（学习率，可配置）

示例：
  previous_weight = 0.5, score = 5 → normalized = 1.0
  updated = 0.5 + 0.1 × (1.0 - 0.5) = 0.55

  previous_weight = 0.5, score = 1 → normalized = 0.0
  updated = 0.5 + 0.1 × (0.0 - 0.5) = 0.45
```

### 更新范围

只更新被检索使用过的图元素（used_graph_element_ids），避免无关元素被误更新。

### 权重范围约束

```
feedback_weight ∈ [0, 1]

若 updated_weight < 0 → clamped to 0
若 updated_weight > 1 → clamped to 1
```

---

## feedback_weight 参与检索评分

### 目的

feedback_weight 影响检索结果排序，高质量内容排名更高。

### 评分公式

```
final_score = λ × semantic_score + (1 - λ) × feedback_weight

λ = 0.7（语义权重，可配置）

示例：
  semantic_score = 0.85, feedback_weight = 0.9
  final = 0.7 × 0.85 + 0.3 × 0.9 = 0.595 + 0.27 = 0.865

  semantic_score = 0.85, feedback_weight = 0.3
  final = 0.7 × 0.85 + 0.3 × 0.3 = 0.595 + 0.09 = 0.685
```

### 与 QueryService 的集成

QueryService 在 RRF 融合后，对每个结果应用 feedback_weight 调整：

```
1. RRF 融合产出候选结果集
2. 对每个结果：
   a. 获取 EntityInstance.feedback_weight
   b. 计算 final_score = λ × rrf_score + (1-λ) × feedback_weight
3. 按 final_score 重新排序
4. 返回调整后的结果
```

---

## 反馈记录存储

### 目的

持久化反馈记录，支持审计和分析。

### 存储模型

```python
@dataclass
class FeedbackRecord:
    record_id: str
    query_id: str
    element_id: str
    element_type: str
    score: int
    normalized_score: float
    text_feedback: str | None
    previous_weight: float
    updated_weight: float
    alpha: float
    applied: bool
    created_at: datetime
```

### 存储位置

SQLite `feedback_records` 表。

### 已处理标记

反馈应用后标记 `applied=True`，避免重复应用。对齐 Cognee apply_feedback_weights 的已处理标记机制。

---

## 完整接口清单

| 方法 | 说明 |
|------|------|
| `submit_feedback(query_id, element_id, element_type, score, text_feedback)` | 提交反馈 |
| `batch_submit_feedback(feedbacks)` | 批量提交反馈 |
| `get_feedback_history(element_id, limit)` | 查询元素反馈历史 |
| `get_feedback_weight(element_id)` | 查询当前 feedback_weight |
| `reset_feedback_weight(element_id)` | 重置 feedback_weight 为默认值 0.5 |
| `get_feedback_stats(dataset_id)` | 反馈统计（平均分、数量等） |

---

## 与 Cognee apply_feedback_weights 对齐

| Cognee 概念 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| apply_feedback_weights_pipeline | FeedbackService.submit_feedback | Cognee 的 memify 管道处理反馈 |
| extract_feedback_qas | score + text_feedback | Cognee 从 QA 会话中提取反馈 |
| alpha=0.1 | α=0.1 | 学习率一致 |
| batch_size=100 | batch_submit_feedback | 批量处理反馈 |
| used_graph_element_ids | element_id + element_type | 只更新被检索使用过的图元素 |
| applied 标记 | applied=True | 已处理反馈标记，避免重复应用 |
| feedback_weight 参与检索 | final = λ × semantic + (1-λ) × feedback_weight | 权重参与检索评分 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-FB-1 | feedback_weight 默认 0.5 | 中性初始值，既不偏向也不偏离 |
| D-FB-2 | α=0.1 学习率 | 小学习率保证权重平稳变化，避免单次反馈剧烈波动 |
| D-FB-3 | λ=0.7 语义权重 | 语义相似度是主要排序依据，feedback_weight 作为辅助信号 |
| D-FB-4 | 只更新被检索使用过的图元素 | 避免无关元素被误更新，对齐 Cognee used_graph_element_ids |
| D-FB-5 | 反馈记录持久化到 SQLite | 审计追溯，支持反馈历史查询和统计分析 |
| D-FB-6 | 边不携带 feedback_weight | 边的反馈通过 weight 间接体现，避免字段冗余 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 反馈闭环概念 | `docs/01-overview/05-concepts.md` |
| Instance 层 feedback_weight | `docs/02-design/schema/instance-layer.md` |
| QueryService 设计 | `docs/02-design/services/query-service.md` |
| Cognee apply_feedback_weights | `cognee/memify_pipelines/apply_feedback_weights.py` |

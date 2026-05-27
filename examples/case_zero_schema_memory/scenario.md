# Case Zero Schema 场景说明 — 零 Schema 记忆闭环

> **文件角色**: 业务场景与资产说明
> **对应决策**: D-S3（Agent 操作接口 3+1）+ D-S4（Schema Light）
> **对应验收标准**: AC3-2（零参数 remember/recall 闭环）+ AC4-1（无 Schema 自动抽取）

---

## 一、目标用户

- **AI Agent 开发者**：需要最简单的记忆 API，无需理解 Schema、memory_type、cognitive_layer
- **快速原型验证者**：需要 5 行代码验证记忆系统是否工作
- **渐进式用户**：先零 Schema 使用，后续根据需要启用 Schema 提升精度

---

## 二、业务背景

OntologyEngine 简化后的核心设计原则：**Schema 是优化层，不是前提层**。

过去的问题：
- 用户必须先在 schema.yaml 中定义所有 Entity/Relation 才能使用系统
- Agent 调用记忆 API 时需要理解 memory_type、cognitive_layer、model_domain 等概念
- 学习曲线陡峭，阻碍快速采用

简化后的目标：
- `oe_remember("Alice works at Google")` — 零参数，系统自动完成一切
- `oe_recall("Where does Alice work?")` — 自然语言查询，自动路由
- 无需理解 Schema、无需指定类型、无需配置标签

本案例要证明：**零 Schema 模式下的完整记忆闭环**。

---

## 三、核心操作（3+1）

| 操作 | 签名 | 说明 |
|------|------|------|
| `oe_remember` | `(text, source?, tags?, space_id?)` | 存储记忆，自动完成抽取、消歧、链接、存储 |
| `oe_recall` | `(query, filters?, top_k?, space_id?)` | 检索记忆，RRF 混合多路检索 |
| `oe_reflect` | `(topic, space_id?)` | 深度分析，检索相关记忆 → LLM 综合 → 归档 |
| `oe_dream` | `(phase?, space_id?)` | 维护周期（可选手动触发） |

---

## 四、本案例中的场景

### 4.1 场景 A：零参数基础闭环

Agent 只需要记住和查询事实，不需要任何配置：

```python
# 存储
await oe_remember("Alice works at Google as a senior engineer")
await oe_remember("Google's headquarters is in Mountain View, California")
await oe_remember("Alice led the Kubernetes migration project in 2025")

# 查询
result = await oe_recall("Where does Alice work?")
# → 应返回含 "Google" 的结果

result = await oe_recall("What project did Alice lead?")
# → 应返回含 "Kubernetes" 的结果
```

### 4.2 场景 B：自动实体抽取验证

系统从自然语言中自动提取实体和关系：

```python
# 输入一段包含多个实体的文本
await oe_remember("""
TechNova is a cloud infrastructure company based in Shenzhen.
Their CTO is Wang Lei, who previously worked at Alibaba Cloud.
TechNova's main product is CloudGroup, a Kubernetes-based platform.
""")

# 验证自动提取的实体
result = await oe_recall("TechNova")
# → 应返回 entity 类型节点（公司实体）

result = await oe_recall("Wang Lei")
# → 应返回 entity 类型节点（人物实体）

result = await oe_recall("What is CloudGroup?")
# → 应返回含 "Kubernetes-based platform" 的结果
```

### 4.3 场景 C：多标签过滤

用户可选地添加标签，后续按标签过滤：

```python
await oe_remember("The Q3 revenue target is 500M", tags={"domain": "finance", "trust_tier": "high"})
await oe_remember("Revenue might be impacted by supply chain issues", tags={"domain": "finance", "fact_vs_opinion": "opinion"})
await oe_remember("API latency increased to 200ms", tags={"domain": "engineering", "trust_tier": "high"})

# 按标签过滤
result = await oe_recall("revenue", tags={"domain": "finance"})
# → 只返回 finance 域的结果

result = await oe_recall("revenue", tags={"fact_vs_opinion": "opinion"})
# → 只返回 opinion 类型结果
```

### 4.4 场景 D：Schema Light 对比

先零 Schema 使用，再启用 Schema 对比精度提升：

```python
# Phase 1: 零 Schema
await oe_remember("Counterparty ABC has a credit score of 720")
result_no_schema = await oe_recall("ABC credit score")

# Phase 2: 启用 Schema
await oe_load_schema("financial-risk.yaml")
await oe_remember("Counterparty DEF has a credit score of 680")
result_with_schema = await oe_recall("credit score")

# 对比：有 Schema 时提取更精确（字段映射、类型校验）
```

---

## 五、案例闭环

```text
oe_remember("Alice works at Google")  ← 零参数
  ↓
自动分块 → 实体抽取 → 消歧 → 链接 → 存储
  ↓
写入后钩子：低延迟 consolidate
  ↓
oe_recall("Where does Alice work?")  ← 自然语言查询
  ↓
RRF 混合检索（向量 + 关键词 + metadata）
  ↓
返回正确结果（含 "Google"）
  ↓
闭环验证 ✓
```

---

## 六、这个案例为什么重要

这是 **P0 里程碑** 的验收案例：

> **P0 里程碑**：Agent 可调用 `oe_remember("Alice works at Google")` → `oe_recall("Where does Alice work?")` 完成闭环。无需 Schema，无需理解 memory_type，一条命令即可。

如果这个案例不通过，OntologyEngine 简化后的核心承诺（易用性的最后一公里）就无法验证。

# Case Zero Schema 用户旅程 — 零参数记忆闭环

> **文件角色**: narrative journey
> **对应决策**: D-S3 + D-S4
> **对应验收标准**: AC3-2 + AC4-1

---

## 旅程概览

本案例通过 5 个步骤展示：

1. 零参数 remember：仅传入文本
2. 自然语言 recall：验证基础闭环
3. 自动实体抽取：验证系统从文本中提取实体/关系
4. 多标签过滤：验证 tags 系统的灵活性
5. Schema Light 对比：零 Schema vs 有 Schema 的精度差异

**预计演示时间**: 8-10 分钟

---

## Step 1：零参数 remember

### 操作

```python
from ontology_engine import OntologyEngine

engine = OntologyEngine.from_config("config.yaml")
space = engine.create_space("zero_schema_demo")

# 零参数 — 仅传入文本
space.remember("Alice works at Google as a senior engineer")
space.remember("Google's headquarters is in Mountain View, California")
space.remember("Alice led the Kubernetes migration project in 2025")
```

### 系统内部自动完成

```
remember("Alice works at Google as a senior engineer")
  → 1. 智能分块（单句无需分块）
  → 2. 实体抽取：Person(Alice), Organization(Google), Role(senior engineer)
  → 3. 关系抽取：works_at(Alice, Google), has_role(Alice, senior engineer)
  → 4. 消歧：Google 是否已存在？→ 创建新实体或链接已有
  → 5. 存储：fragment(ChromaDB) + entity(SQLite) 双写
  → 6. 后钩子：触发低延迟 consolidate（fragment → observation）
```

### 验证点

- [ ] 三次 remember 均成功返回 node_id
- [ ] 无需指定 memory_type、cognitive_layer、tags
- [ ] 无需预定义 Schema

---

## Step 2：自然语言 recall — 验证基础闭环

### 操作

```python
# 查询 1：单跳精确
result = space.recall("Where does Alice work?")
assert "Google" in result[0].text, "应返回含 Google 的结果"

# 查询 2：项目查询
result = space.recall("What project did Alice lead?")
assert "Kubernetes" in result[0].text, "应返回含 Kubernetes 的结果"

# 查询 3：地点查询
result = space.recall("Where is Google HQ?")
assert "Mountain View" in result[0].text, "应返回含 Mountain View 的结果"
```

### 期望输出

```
查询 "Where does Alice work?":
  Top 1: "Alice works at Google as a senior engineer" (score=0.95)
  → memory_type: observation (由 fragment consolidate 而来)
  → source_ids: [fragment_001]

查询 "What project did Alice lead?":
  Top 1: "Alice led the Kubernetes migration project in 2025" (score=0.92)

查询 "Where is Google HQ?":
  Top 1: "Google's headquarters is in Mountain View, California" (score=0.94)
```

### 验证点

- [ ] 三次查询均返回正确结果
- [ ] 自然语言查询无需指定 memory_type 过滤
- [ ] 结果带 score 和 memory_type 标签

---

## Step 3：自动实体抽取验证

### 操作

```python
# 输入包含多个实体的复杂文本
space.remember("""
TechNova is a cloud infrastructure company based in Shenzhen.
Their CTO is Wang Lei, who previously worked at Alibaba Cloud.
TechNova's main product is CloudGroup, a Kubernetes-based platform.
CloudGroup supports multi-cluster management and auto-scaling.
""")

# 验证自动提取的实体
entities = space.query_entities("TechNova")
assert len(entities) > 0, "应找到 TechNova 实体"

persons = space.query_entities("Wang Lei")
assert len(persons) > 0, "应找到 Wang Lei 实体"

products = space.query_entities("CloudGroup")
assert len(products) > 0, "应找到 CloudGroup 实体"
```

### 期望提取结果

| 实体类型 | 实体名称 | 属性 |
|---------|---------|------|
| Organization | TechNova | industry=cloud_infrastructure, location=Shenzhen |
| Person | Wang Lei | role=CTO, previous_employer=AlibabaCloud |
| Product | CloudGroup | type=Kubernetes_platform, features=[multi_cluster, auto_scaling] |

### 期望关系

| 关系 | 源 | 目标 |
|------|-----|------|
| has_cto | TechNova | Wang Lei |
| previously_worked_at | Wang Lei | AlibabaCloud |
| has_product | TechNova | CloudGroup |

### 验证点

- [ ] 3 个实体被正确提取
- [ ] 实体属性从文本中自动推断
- [ ] 实体间关系被正确建立
- [ ] 可通过 query_entities 查询到实体

---

## Step 4：多标签过滤

### 操作

```python
# 存储带标签的记忆
space.remember("The Q3 revenue target is 500M", tags={"domain": "finance", "trust_tier": "high"})
space.remember("Revenue might be impacted by supply chain issues", tags={"domain": "finance", "fact_vs_opinion": "opinion"})
space.remember("API latency increased to 200ms after deployment", tags={"domain": "engineering", "trust_tier": "high"})
space.remember("The new deployment pipeline reduced CI time by 40%", tags={"domain": "engineering", "fact_vs_opinion": "fact"})

# 按 domain 过滤
result = space.recall("revenue", tags={"domain": "finance"})
assert all(r.tags.get("domain") == "finance" for r in result), "应只返回 finance 域"

# 按 fact_vs_opinion 过滤
result = space.recall("revenue", tags={"fact_vs_opinion": "opinion"})
assert len(result) == 1, "应只返回 opinion 类型"
assert "might be" in result[0].text, "应包含不确定性表达"

# 组合过滤
result = space.recall("", tags={"domain": "engineering", "fact_vs_opinion": "fact"})
assert len(result) == 1, "应返回 engineering 域的 fact"
```

### 验证点

- [ ] 单标签过滤正确
- [ ] 多标签组合过滤正确
- [ ] 空查询 + 标签过滤返回所有匹配标签的记忆

---

## Step 5：Schema Light 对比（可选）

### 操作

```python
# Phase 1: 零 Schema 模式下的查询
result_no_schema = space.recall("credit score")
print(f"零 Schema 结果数: {len(result_no_schema)}")

# Phase 2: 启用 Schema
space.load_schema("financial-risk.yaml")

# 存储新记忆（有 Schema 约束）
space.remember("Counterparty DEF has a credit score of 680 and risk level of medium")

# 对比查询结果
result_with_schema = space.recall("credit score")
print(f"有 Schema 结果数: {len(result_with_schema)}")

# 验证 Schema 带来的精度提升
# 有 Schema 时：字段映射更精确（credit_score 为数值字段，非自由文本）
# 检索权重更合理（entity 类型权重高于 fragment）
```

### 期望对比

| 维度 | 零 Schema | 有 Schema |
|------|----------|----------|
| 提取精度 | LLM 自由格式 | Schema 约束字段 |
| 检索权重 | 统一权重 | entity 类型权重提升 |
| 类型校验 | 无 | credit_score 必须为数值 |
| 规则执行 | 不可用 | RuleEngine 可消费 |

### 验证点

- [ ] 零 Schema 模式可正常使用
- [ ] 启用 Schema 后提取更精确
- [ ] Schema 是可选优化，不是前提条件

---

## 结论

这个案例要证明：

- **`oe_remember("Alice works at Google")` 零参数即可工作**
- **系统自动完成分块、抽取、消歧、链接、存储**
- **自然语言查询返回正确结果**
- **标签系统提供灵活扩展能力**
- **Schema 是优化层，不是前提层**

这是 OntologyEngine 简化后的 **P0 里程碑** 验收案例。

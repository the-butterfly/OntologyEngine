# Case 5 用户旅程 — 专家经验知识沉淀闭环

> **文件角色**: narrative journey
> **对应愿景旅程**: J4

---

## 旅程概览

本案例通过 6 个步骤展示：

1. Agent 交互产生个人经验
2. 使用次数累积触发候选标记
3. 知识管理员收到评审通知
4. 专家评审并发布为组织规则
5. 所有用户/Agent 共享新规则
6. 规则被消费并持续优化

**预计演示时间**: 10-12 分钟

---

## Step 1：Agent 交互产生个人经验

### 操作

```python
# 模拟 Agent 与用户的多次交互
for i in range(25):
    space.remember(
        f"用户要求关注供应商发票金额波动，阈值设定为 {10 + i * 0.5}%",
        source=f"conversation_{i}",
        tags={"domain": "risk", "model": "user"}
    )

# 系统自动累积 usage_count
stats = space.get_memory_stats()
print(f"发票波动相关记忆数: {stats['invoice_fluctuation_count']}")
print(f"平均 usage_count: {stats['avg_usage_count']}")
print(f"平均 confidence: {stats['avg_confidence']}")
```

### 期望输出

```
发票波动相关记忆数: 25
平均 usage_count: 25
平均 confidence: 0.85
```

### 验证点

- [ ] 25 次交互产生 25 条相关记忆
- [ ] usage_count 和 confidence 正确累积

---

## Step 2：使用次数累积触发候选标记

### 操作

```python
# 系统自动检测候选条件
candidates = space.find_candidates(
    min_usage_count=20,
    min_confidence=0.8
)

print(f"候选知识数: {len(candidates)}")
for c in candidates:
    print(f"  - {c.text[:50]}... (usage={c.usage_count}, conf={c.confidence})")
```

### 期望输出

```
候选知识数: 1
  - 供应商发票金额波动超过 15% 需关注... (usage=25, conf=0.85)
```

### 系统自动行为

```
检测到 candidate:
  → 标记 candidate_for_organization: true
  → 创建评审任务: review_task_001
  → 通知知识管理员: "发现 1 条候选知识待评审"
```

### 验证点

- [ ] 候选条件（usage_count ≥ 20, confidence ≥ 0.8）正确触发
- [ ] candidate_for_organization 标记正确设置
- [ ] 评审任务创建并通知管理员

---

## Step 3：知识管理员评审

### 操作

```python
# 知识管理员查看候选知识
review = space.get_review_task("review_task_001")
print(f"候选知识: {review.candidate.text}")
print(f"来源: {review.candidate.source_ids}")
print(f"使用次数: {review.candidate.usage_count}")
print(f"置信度: {review.candidate.confidence}")

# 查看支撑证据
evidence = space.get_evidence(review.candidate.source_ids)
print(f"支撑证据数: {len(evidence)}")
```

### 期望输出

```
候选知识: 供应商发票金额波动超过 15% 需关注
来源: [conversation_0, conversation_1, ..., conversation_24]
使用次数: 25
置信度: 0.85
支撑证据数: 25
```

### 验证点

- [ ] 评审任务包含完整的候选知识信息
- [ ] 支撑证据可追溯
- [ ] 管理员可基于证据做出评审决策

---

## Step 4：专家评审并发布为组织规则

### 操作

```python
# 专家评审通过
space.approve_candidate(
    task_id="review_task_001",
    rule_id="rule.invoice_fluctuation_review",
    version="v1.0",
    rule_text="当供应商发票金额波动超过 15% 时，自动触发额外审查流程",
    review_comment="经验验证有效，发布为组织规则"
)

# 验证规则已发布
rule = space.get_rule("rule.invoice_fluctuation_review@v1.0")
print(f"规则 ID: {rule.id}")
print(f"规则文本: {rule.text}")
print(f"可见性: {rule.visibility}")
print(f"来源: 个人经验 → 组织规则")
```

### 期望输出

```
规则 ID: rule.invoice_fluctuation_review@v1.0
规则文本: 当供应商发票金额波动超过 15% 时，自动触发额外审查流程
可见性: public（组织内公开）
来源: 个人经验 → 组织规则
```

### 四类互索引关系

```
rule.invoice_fluctuation_review@v1.0
  ├─ extracted_from: conversation_0 ~ conversation_25（25 条交互）
  ├─ supported_by: 发票波动数据证据链
  ├─ defined_in: RiskRules@v2.1
  └─ trace_to: 待后续查询/分析消费
```

### 验证点

- [ ] 规则正确发布，带版本号
- [ ] 可见性从 private 变为 public
- [ ] 四类互索引关系建立

---

## Step 5：所有用户/Agent 共享新规则

### 操作

```python
# 其他用户查询该规则
result = space.recall("发票金额波动审查规则")
assert "15%" in result[0].text, "应返回含 15% 阈值的规则"

# 规则执行：检查某供应商是否触发审查
supplier_data = {"invoice_amount_change": 0.18}  # 18% 波动
analysis = space.analyze("SUP_001", dimension="invoice_fluctuation_check")
assert analysis.triggered is True, "18% 波动应触发审查"

# 另一个 Agent 也能访问该规则
other_space = engine.load_space("zero_schema_demo")
result = other_space.recall("发票审查", tags={"domain": "risk"})
assert len(result) > 0, "其他用户也能访问组织规则"
```

### 验证点

- [ ] 组织规则对所有用户可见
- [ ] 规则可被执行（触发条件判断）
- [ ] 跨空间可访问组织级知识

---

## Step 6：规则持续优化（版本迭代）

### 操作

```python
# 规则使用一段时间后，发现阈值需要调整
# 新的交互数据表明 12% 更合适
for i in range(15):
    space.remember(
        f"发票波动 {12 + i * 0.2}% 时触发审查效果最佳",
        source=f"feedback_{i}"
    )

# 系统检测规则需要优化
optimization_candidates = space.find_rule_optimization_candidates("rule.invoice_fluctuation_review")
print(f"优化候选数: {len(optimization_candidates)}")

# 专家评审通过新版本
space.approve_rule_update(
    rule_id="rule.invoice_fluctuation_review",
    from_version="v1.0",
    to_version="v1.1",
    change="阈值从 15% 调整为 12%",
    reason="基于 15 次反馈数据优化"
)

# 验证版本历史
versions = space.get_rule_versions("rule.invoice_fluctuation_review")
print(f"版本数: {len(versions)}")  # → 2
print(f"当前版本: {versions[-1].version}")  # → v1.1
```

### 期望输出

```
优化候选数: 1
版本数: 2
当前版本: v1.1
```

### 验证点

- [ ] 规则使用数据被持续收集
- [ ] 优化建议基于实际使用数据
- [ ] 规则版本历史可追溯
- [ ] SUPERSEDES 边记录版本更替

---

## 结论

这个案例最终要证明：

- **Agent 交互本身就是知识生产过程**（作业即沉淀）
- **个人经验可以自动转化为组织资产**（usage_count + confidence → candidate）
- **专家评审是知识质量的关键保障**（审核通过/拒绝 → 反馈优化）
- **知识闭环可追溯、可治理、可演化**（版本历史、SUPERSEDES 边、持续优化）

这是 OntologyEngine 区别于传统 RAG 和知识管理系统的核心差异化能力。

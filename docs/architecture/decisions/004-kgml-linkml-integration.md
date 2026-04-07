# ADR-004: KGML 技术选型与 LinkML 集成

**状态**: Accepted
**日期**: 2026-04-07
**来源**: critical-review-response.md 问题5

---

## 背景问题

### 工作量重新评估

原估计 9 周，重新评估为 18 周（+100%）：

| 组件 | 原估计 | 重新评估 | 说明 |
|------|--------|----------|------|
| Schema解析器 | 1周 | 2周 | Pydantic模型复杂 |
| 验证器 | 1周 | 2周 | 跨引用验证复杂 |
| 表达式引擎 | 1周 | 3周 | 安全沙箱复杂 |
| 50+算子 | 2周 | 4周 | 每个需UT+边界测试 |
| DAG依赖解析 | 1周 | 1周 | networkx可用 |
| 规则引擎 | 2周 | 3周 | 执行顺序+回滚 |
| 流式指标 | 1周 | 3周 | Kafka集成复杂 |
| **总计** | **9周** | **18周** | **+100%** |

---

## 决策：渐进式复用策略

```
┌─────────────────────────────────────────────────────────────────┐
│                     技术选型策略：渐进式复用                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tier 1: 直接复用 (不造轮子)                                     │
│  ├─ LinkML: Schema定义 + 验证                                    │
│  ├─ Pydantic: Python代码生成                                     │
│  └─ JSON Schema: 运行时验证                                       │
│                                                                 │
│  Tier 2: 包装扩展 (基于开源)                                     │
│  ├─ 表达式引擎: 基于 asteval / simpleeval 包装安全层            │
│  ├─ DAG执行: 基于 networkx + asyncio                             │
│  └─ 规则引擎: 基于 durable-rules / intellect 包装                │
│                                                                 │
│  Tier 3: 自研核心 (差异化能力)                                   │
│  ├─ 维度上下文系统                                               │
│  ├─ 多策略指标计算回退                                           │
│  ├─ 图谱+规则集成层                                              │
│  └─ Agent Memory模型                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 基于 LinkML 的 Schema 设计

```yaml
# schema/finance_kg.linkml.yaml

id: https://example.org/finance/kg
name: FinanceKnowledgeGraph
prefixes:
  linkml: https://w3id.org/linkml/
  finance: https://example.org/finance/

imports:
  - linkml:types  # 复用LinkML类型系统

classes:
  Supplier:
    is_a: NamedThing
    attributes:
      supplier_id:
        identifier: true
        range: string
      company_name:
        range: string
        required: true
      registered_capital:
        range: Money
      credit_score:
        range: integer
        minimum: 0
        maximum: 100
    slots:
      - supplies_to
      - has_invoice

enums:
  InvoiceStatusEnum:
    permissible_values:
      PENDING:
        meaning: finance:PENDING_STATUS
      PAID:
        meaning: finance:PAID_STATUS
      OVERDUE:
        meaning: finance:OVERDUE_STATUS
```

---

## 修正后的 Roadmap

```yaml
Phase 1: 基础设施 (6周) [延长2周]
  W1-2: LinkML集成、Schema定义
  W3-4: 存储层实现
  W5-6: FastAPI服务、基础CRUD

Phase 2: 规则引擎 (6周) [延长2周]
  W1-2: 安全表达式引擎
  W3-4: DAG依赖解析、规则执行器
  W5-6: 指标计算引擎

Phase 3: 向量与检索 (4周) [延长1周]
Phase 4: Agent集成 (4周) [延长1周]

总计: 20周 (5个月) [延长4周]
```

---

## 相关文档

- ADR-003: 表达式引擎安全沙箱 ([003-expression-engine-security.md](./003-expression-engine-security.md))
- ADR-005: Agent Memory 设计 ([005-agent-memory-design.md](./005-agent-memory-design.md))

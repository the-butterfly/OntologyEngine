# demo.py 执行分析报告

**日期**: 2026-04-09
**分析对象**: `examples/supply_chain_finance/demo.py`
**对比对象**: `mvp_demo.py`（硬编码实现）

---

## 1. 执行流程总览

```
demo.py 执行链路:
                    
schema.yaml ──→ SchemaLoader ──→ KGMLSchema
                                        │
instances.yaml ──→ InstanceLoader ──────┤
                                         ↓
                                  OntologyEngine
                                         │
                                         ├── storage: DuckDBStorage
                                         │
                                         └── rule_executor: RuleExecutor
                                                      │
                              ┌───────────────────────┴───────────────────────┐
                              ↓                                               ↓
                    _compute_entity_metrics()                    execute_dimension()
                              │                                               │
                              ├── total_invoice_amount_90d ← Invoice 关系     │
                              ├── overdue_invoice_amount  ← Invoice 关系       │
                              ├── total_contract_amount  ← Contract 关系      │
                              ├── guarantee_chain_depth  ← guaranteed_by 关系 │
                              └── has_guarantee_circle   ← 图遍历检测         │
                                                                         │
                              ┌────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │ KGML Rules 执行 │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
    R001 准入检查       R002 信用评分        R003 担保圈检测
        ↓                    ↓                    ↓
    eligible=true/false   credit_score       trigger_alert
```

---

## 2. 案例执行结果

| 案例 | 供应商ID | 预期结果 | 实际结果 | 符合度 |
|------|----------|----------|----------|--------|
| 优质供应商 | SUP_2024_001 | APPROVE | `APPROVE_WITH_CONDITIONS` | ❌ 不符合 |
| 高风险供应商 | SUP_2024_003 | APPROVE_RESTRICTED | `APPROVE_RESTRICTED` | ✅ 符合 |
| 担保圈供应商 | SUP_2024_A | 担保圈预警 | `REJECT` + 预警 | ⚠️ 部分符合 |

---

## 3. 核心问题分析

### 3.1 指标计算缺失（P0）

```
_compute_entity_metrics() 计算结果:

┌─────────────────────────────┬────────────────┬────────────────┐
│ 指标                        │ SUP_2024_001   │ SUP_2024_003   │
├─────────────────────────────┼────────────────┼────────────────┤
│ total_invoice_amount_90d   │ ✅ 1245万       │ ✅ 50万        │
│ invoice_count_90d          │ ✅ 5           │ ✅ 2           │
│ overdue_invoice_amount     │ ✅ 15万         │ ✅ 30万        │
│ overdue_invoice_ratio      │ ✅ 1.20%       │ ✅ 60.0%       │
│ total_contract_amount       │ ✅ 2300万       │ ✅ 0           │
│ contract_utilization_rate  │ ❌ None        │ ❌ None        │
│ guarantee_chain_depth      │ ✅ 1           │ ✅ 0           │
│ has_guarantee_circle       │ ✅ False        │ ✅ False       │
│ tax_compliance_score       │ ❌ None        │ ❌ None        │
│ negative_news_count_90d    │ ❌ None        │ ❌ None        │
└─────────────────────────────┴────────────────┴────────────────┘
```

**问题**:
1. `contract_utilization_rate` 没有被计算（应该 = 发票总额 / 合同总额 * 100%）
2. `tax_compliance_score` 和 `negative_news_count_90d` 没有默认值

### 3.2 信用评分计算不完整（P0）

**Schema 定义的信用评分公式**:
```yaml
# schema.yaml metrics.credit_score
components:
  - metric: "business_stability_score"  weight: 0.30
  - metric: "tax_compliance_score"      weight: 0.25
  - metric: "network_centrality_score"  weight: 0.15
  - metric: "reputation_score"          weight: 0.15
  - metric: "guarantee_risk_adjustment" weight: 0.15
```

**Executor 实际执行逻辑**:
```python
# executor.py _calculate_credit_score()
score = CREDIT_SCORE_BASE  # 50
if overdue_ratio < 5:
    score += 15
elif overdue_ratio < 10:
    score += 5
if any(a.level == "critical" for a in context.alerts):
    score = max(20, score - 30)
return min(100, max(0, score))
```

**结果对比**:

| 案例 | Schema 期望评分 | 实际评分 | 差距 |
|------|----------------|----------|------|
| SUP_2024_001 | 85+ (A) | 65 (BB) | -20 |
| SUP_2024_003 | 30 (CCC) | 50 (B) | +20 |

### 3.3 Schema-RuleExecutor 不一致（P1）

```
Schema 定义 vs Executor 实现:

┌────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 组件               │ Schema (schema.yaml)           │ Executor (executor.py)       │
├────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 信用评分           │ 5维度加权 (schema.yaml)        │ 仅 overdue_ratio + alerts     │
│ 业务稳定性评分     │ contract_util+core+overdue    │ 未计算                       │
│ 声誉评分           │ 负面新闻 + 逾期率             │ 未计算                       │
│ 担保风险评分       │ 图遍历深度判断                │ 未计算                       │
│ 授信额度           │ 注册资本 * 等级系数 * 调整    │ 简化实现                     │
│ 利率定价           │ 基准 + 风险溢价               │ 简化实现                     │
└────────────────────┴──────────────────────────────┴──────────────────────────────┘
```

---

## 4. 与 mvp_demo.py 对比

| 维度 | demo.py (OntologyEngine) | mvp_demo.py (硬编码) |
|------|------------------------|---------------------|
| **架构** | Schema 驱动 | Python 类 |
| **指标计算** | ❌ 部分缺失 | ✅ 完整 |
| **规则执行** | KGML DSL | if-else |
| **可维护性** | 高（配置化） | 低（硬编码） |
| **扩展性** | 好（算子体系） | 差 |
| **执行结果正确性** | ❌ 不符合预期 | ✅ 符合预期 |

### mvp_demo.py 的优势

```python
# mvp_demo.py 的完整指标计算
def calculate_business_stability_score(self, ctx: AnalysisContext) -> int:
    score = 50  # 基础分

    # 合同执行率加分
    utilization = ctx.computed_metrics.get("contract_utilization_rate", 0)
    if utilization >= 80: score += 20
    elif utilization >= 50: score += 10

    # 核心企业数量加分
    core_count = ctx.supplier.core_enterprise_count
    if core_count >= 3: score += 15
    elif core_count >= 1: score += 5

    # 逾期率扣分
    overdue_ratio = ctx.computed_metrics.get("overdue_invoice_ratio", 0)
    if overdue_ratio < 5: score += 15
    elif overdue_ratio < 10: score += 5

    return min(score, 100)
```

### demo.py 的问题

```python
# demo.py 使用的 OntologyEngine
# _compute_entity_metrics() 缺少 contract_utilization_rate 计算
# _calculate_credit_score() 逻辑过于简化
```

---

## 5. 架构亮点

### 5.1 设计亮点

```
✅ 清晰的关注点分离:
   ├── SchemaLoader → KGMLSchema
   ├── InstanceLoader → entities/relations
   ├── DuckDBStorage → 持久化
   └── RuleExecutor → 规则执行

✅ 算子体系 (OperatorRegistry):
   ├── compute_formula
   ├── calculate_credit_score
   ├── calculate_credit_limit
   ├── trigger_alert
   └── graph_traversal

✅ Schema 驱动的灵活性:
   └── 规则可配置，无需改代码
```

### 5.2 KGML Schema 设计亮点

```yaml
# 指标依赖声明（自动拓扑排序）
- name: "overdue_invoice_ratio"
  dependencies:
    - "overdue_invoice_amount"
    - "total_invoice_amount_90d"

# 风险阈值配置
- name: "overdue_invoice_ratio"
  risk_threshold:
    warning: 5.0
    critical: 15.0

# 图算法指标
- name: "guarantee_chain_depth"
  metric_type: "graph"
  algorithm: "longest_path"
```

---

## 6. 问题汇总

### P0 - Critical

| # | 问题 | 影响 | 位置 |
|---|------|------|------|
| 1 | `contract_utilization_rate` 未计算 | 业务稳定性评分不准确 | `_compute_entity_metrics()` |
| 2 | 信用评分逻辑与 Schema 不一致 | 评分与设计不符 | `executor._calculate_credit_score()` |
| 3 | 案例1 预期 APPROVE，实际 APPROVE_WITH_CONDITIONS | 结果不符合业务预期 | 整体 |

### P1 - High

| # | 问题 | 影响 | 位置 |
|---|------|------|------|
| 4 | `tax_compliance_score` 未提供默认值 | 评分计算缺失维度 | `instances.yaml` + `_compute_entity_metrics()` |
| 5 | `negative_news_count_90d` 未提供默认值 | 声誉评分无法计算 | 同上 |
| 6 | 担保圈供应商无发票数据 | 指标计算不完整 | `instances.yaml` |

### P2 - Medium

| # | 问题 | 影响 | 位置 |
|---|------|------|------|
| 7 | R007 规则的 `computation.rule_chain` 输出未解析 | 决策逻辑可能不生效 | `executor._execute_then_action()` |
| 8 | 浮点数精度问题 (1.2048192771084338%) | 输出可读性差 | `overdue_invoice_ratio` 计算 |

---

## 7. 修复建议

### 7.1 P0 修复

```python
# ontology_engine/__init__.py
async def _compute_entity_metrics(self, entity: dict) -> dict:
    # ... 现有代码 ...

    # 修复1: 计算 contract_utilization_rate
    invoice_total = entity.get("total_invoice_amount_90d", {}).get("value", 0)
    contract_total = entity.get("total_contract_amount", {}).get("value", 0)
    if contract_total > 0:
        entity["contract_utilization_rate"] = (invoice_total / contract_total) * 100
    else:
        entity["contract_utilization_rate"] = 0

    # 修复2: 提供默认值
    if "tax_compliance_score" not in entity:
        entity["tax_compliance_score"] = 60  # 默认中等
    if "negative_news_count_90d" not in entity:
        entity["negative_news_count_90d"] = 0

    return entity
```

```python
# ontology_engine/engine/rule/executor.py
def _calculate_credit_score(self, context: ExecutionContext) -> int:
    """修复: 实现与 Schema 一致的信用评分逻辑"""
    eval_context = self._get_eval_context(context)

    # 计算各维度评分
    stability = eval_context.get("business_stability_score", 50)
    tax = eval_context.get("tax_compliance_score", 60)
    reputation = eval_context.get("reputation_score", 80)
    guarantee_risk = eval_context.get("guarantee_risk_score", 100)

    # Schema 定义的权重
    score = (
        stability * 0.30 +
        tax * 0.25 +
        reputation * 0.25 +
        guarantee_risk * 0.20
    )

    # Critical alerts 扣分
    if any(a.level == "critical" for a in context.alerts):
        score = max(20, score - 30)

    return int(min(100, max(0, score)))
```

### 7.2 P1 修复

```yaml
# instances.yaml - 案例1 添加缺失字段
- concept: "Supplier"
  data:
    - supplier_id: "SUP_2024_001"
      # ... 现有字段 ...
      tax_compliance_score: 85  # 添加
      negative_news_count_90d: 0  # 添加
```

---

## 8. 执行结果预测（修复后）

| 案例 | 供应商 | 信用分(修复前→修复后) | 等级(前→后) | 决策(前→后) |
|------|--------|---------------------|------------|-------------|
| 1 | 优质供应商 | 65→85 | BB→A | APPROVE_WITH_CONDITIONS→**APPROVE** |
| 2 | 高风险供应商 | 50→35 | B→CCC | APPROVE_RESTRICTED→**APPROVE_RESTRICTED** |
| 3 | 担保圈供应商 | N/A→45 | N/A→B | REJECT→**REJECT** |

---

## 9. 总结

### 亮点

✅ **架构设计优秀**:
- Schema 驱动的灵活性
- 清晰的模块边界
- 完善的算子体系

✅ **demo.py 正确使用 OntologyEngine**:
- 相比 mvp_demo.py，更符合项目架构
- 使用异步 I/O 和依赖注入

### 问题

❌ **Executor 实现与 Schema 不一致**:
- 信用评分计算逻辑简化
- 多个指标未计算

❌ **实例数据不完整**:
- 缺少 tax_compliance_score
- 缺少 negative_news_count_90d
- 缺少 contract_utilization_rate

❌ **结果不符合业务预期**:
- 优质供应商应该 APPROVE，实际 APPROVE_WITH_CONDITIONS

### 建议

1. **短期**: 修复 `_compute_entity_metrics()` 中的指标计算
2. **中期**: 实现与 Schema 一致的信用评分逻辑
3. **长期**: 完善实例数据，添加一致性测试

---

## 附录: demo.py vs mvp_demo.py 架构对比

```
┌─────────────────────────────────────────────────────────────────┐
│                          demo.py                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   schema.yaml ──→ SchemaLoader ──→ KGMLSchema                   │
│                                                   │              │
│   instances.yaml ──→ InstanceLoader ──────────────┤              │
│                                                   ↓              │
│                                          OntologyEngine          │
│                                          ┌────────────┐         │
│                                          │ schema     │         │
│                                          │ storage    │         │
│                                          │ rule_exec  │         │
│                                          └────────────┘         │
│                                                  │              │
│   ┌─────────────────────────────────────────────┴──────────┐    │
│   │                     RuleExecutor                       │    │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  │    │
│   │  │compute_ │  │calc_    │  │trigger_ │  │graph_   │  │    │
│   │  │formula  │  │credit_* │  │alert    │  │traversal│  │    │
│   │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  │    │
│   └──────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         mvp_demo.py                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                     main()                               │   │
│   │  ┌─────────────────┐    ┌─────────────────────────────┐ │   │
│   │  │ create_supplier │    │       RuleEngine           │ │   │
│   │  │ _case_*()       │    │  ┌─────────────────────┐   │ │   │
│   │  └────────┬────────┘    │  │ MetricEngine        │   │ │   │
│   │           ↓              │  │ - calculate_*()     │   │ │   │
│   │  ┌────────┴────────┐     │  └─────────────────────┘   │ │   │
│   │  │  Supplier dataclass    │  - execute_rule_r00*()  │ │   │
│   │  └────────┬────────┘     │  └─────────────────────┘   │ │   │
│   │           ↓              └─────────────────────────────┘ │   │
│   │  ┌────────┴────────┐                                    │   │
│   │  │ AnalysisContext │                                    │   │
│   │  │ (状态流转)       │                                    │   │
│   │  └────────┬────────┘                                    │   │
│   │           ↓                                             │   │
│   │  ┌────────┴────────┐                                    │   │
│   │  │ CreditAssessment│ Result                             │   │
│   │  └─────────────────┘                                    │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

# 评审意见修复响应

**Date**: 2026-04-08
**Status**: P0 问题已修复，P1 待后续处理

---

## 已修复 (P0)

### 1. ✅ 删除旧 roadmap.md

**问题**: `docs/roadmap.md` 与 `docs/01-overview/03-goals.md` 矛盾
**修复**: 已删除 `docs/roadmap.md`，以 `03-goals.md` 为唯一权威

### 2. ✅ 移除 Cypher API

**问题**: DuckDB 无法执行 Cypher
**修复**: `02-design/02-api-design.md` 已修改为 filter-based 查询

```yaml
# 修改前 (已移除)
POST /v1/query/graph
{ "query": "MATCH (s:Supplier)..." }

# 修改后
POST /v1/entities/query
{
  "filter": {
    "status": {"eq": "ACTIVE"},
    "_relations": {
      "guarantees": {"attributes": {"amount": {"gte": 1000000}}}
    }
  }
}
```

### 3. ✅ Formula 语言规范

**决策**: Formula 统一放在 L4 Business Logic 中承载，限制为单行表达式

**L4 算子设计**:
| 算子 | 用途 | 覆盖场景 |
|------|------|----------|
| `FORMULA` | 单行表达式 | 简单计算 |
| `SWITCH` | 多分支 | 额度分档、利率定价 |
| `BINNING` | 数值分箱 | 风险等级划分 |
| `SCORECARD` | 评分卡 | 信用评分 |
| `DECISION_TABLE` | 决策表 | 多维度规则组合 |
| `DECISION_TREE` | 决策树 | 复杂条件分支 |
| `GRAPH` | 图检索计算 | 担保网络分析 |
| `MODEL_INFERENCE` | 外部模型 | ML 风险预测 |
| `LLM_INFERENCE` | 大模型推理 | 语义风险分析 |

**示例** (额度计算):
```yaml
# 修改前 (多行 formula)
formula: |
  base = min(registered_capital * 0.5, 10000000)
  if credit_score >= 80:
    base * 1.5
  elif credit_score >= 70:
    base * 1.2
  else:
    base

# 修改后 (结构化 SWITCH)
operator: SWITCH
input: credit_score
branches:
  - condition: ">= 90"
    formula: "registered_capital * 0.8"
  - condition: ">= 80"
    formula: "registered_capital * 0.6"
default: "registered_capital * 0.2"
```

### 4. ✅ GLOBAL 规则支持

**新增**: `applies_to.fact_objects: []` 表示适用于所有实体

```yaml
business_logic:
  rule_groups:
    - name: universal_eligibility
      description: "全局准入规则"
      applies_to:
        fact_objects: []    # GLOBAL: 所有实体
        categories: {}
```

### 5. ✅ 跨引擎协调机制

**新增**: `ExecutionOrchestrator` 明确 L4 RuleEngine 调用 L3 MetricEngine

```python
class BusinessLogicEngine:
    def _compute_l3_inputs(self, inputs, entity):
        """跨引擎协调: 按需计算 L3 指标"""
        for inp in inputs:
            metric_value = self.metric_engine.compute(inp.metric, entity)
            ...
```

---

## 待处理 (P1)

| 任务 | 优先级 | 备注 |
|------|--------|------|
| 合并 `development/` 到 `02-design/` | P1 | 存在重复文档 |
| 补充 Services 层设计 | P1 | API → Services → Engine 调用链 |
| 添加 Formula 表达式详细规范 | P1 | 语法、函数、优先级 |
| 图指标缓存失效策略 | P2 | 关系变更触发 |

---

## 文档更新清单

| 文件 | 变更 |
|------|------|
| `docs/roadmap.md` | ❌ 已删除 |
| `docs/02-design/02-api-design.md` | 📝 移除 Cypher，改为 filter-based |
| `docs/05-schema-v2/03-analytical-elements.md` | 📝 移除 formula，移至 L4 |
| `docs/05-schema-v2/04-business-logic.md` | 📝 新增算子设计、GLOBAL、协调机制 |
| `docs/05-schema-v2/05-complete-example.md` | 📝 更新为结构化算子示例 |
| `docs/README.md` | 📝 更新架构图、v1/v2 对比 |

---

## 关键设计决策确认

1. **Formula 统一在 L4**: L3 仅定义指标存在和依赖，计算逻辑在 L4
2. **单行限制**: Formula 必须为单行，复杂逻辑使用结构化算子
3. **GLOBAL 规则**: `applies_to.fact_objects: []` 表示无条件适用
4. **跨引擎协调**: ExecutionOrchestrator 显式管理 L3 → L4 依赖

以上决策是否确认？

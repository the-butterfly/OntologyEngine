# RFC-003: 规则执行模型

**Status**: ✅ Adopted
**Date**: 2026-04-08
**Author**: OntologyEngine Team

## 背景

规则引擎需支持：
1. 规则之间有依赖（规则A的输出是规则B的输入）
2. 条件分支（满足条件X执行A，否则执行B）
3. 可解释（能回答"为什么得出这个结论"）

## 决策

**DAG (有向无环图) 执行模型**

```
规则文件 ──▶ 解析为节点 ──▶ 构建依赖图 ──▶ 拓扑排序 ──▶ 顺序执行
```

## 规则结构

```yaml
ruleset:
  - id: R001
    priority: 100
    scope:
      dimensions: [credit_assessment]
    when:
      expression: "status == 'ACTIVE'"
    then:
      action: calculate_score
    else:
      action: reject
```

## 执行流程

```python
class RuleEngine:
    def execute(self, context: Context) -> Result:
        # 1. 筛选适用规则
        applicable = self.filter_by_scope(rules, context)

        # 2. 构建依赖图
        dag = self.build_dag(applicable)

        # 3. 拓扑排序
        order = topological_sort(dag)

        # 4. 顺序执行
        for rule in order:
            if evaluate(rule.when, context):
                result = execute(rule.then, context)
                context.update(result)
            else:
                result = execute(rule.else_, context)
                context.update(result)

        return context
```

## 依赖解析

```
R001: 基础准入
  └─▶ R002: 信用评分 (依赖 R001.eligible)
          └─▶ R003: 授信额度 (依赖 R002.score)
```

依赖声明：
```yaml
inputs:
  - name: eligible
    from: R001  # 显式声明依赖
```

## 回滚机制

执行失败时回滚该规则的副作用，保持数据一致性。

## 替代方案

| 方案 | 评价 |
|------|------|
| Rete 算法 | 适合大量事实匹配，实现复杂 |
| 顺序执行 | 简单，无法处理依赖 |
| **DAG** | 平衡，支持依赖且可解释 |

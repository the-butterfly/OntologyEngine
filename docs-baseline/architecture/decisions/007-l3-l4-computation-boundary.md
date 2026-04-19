# ADR-007: L3/L4 计算边界划分

**状态**: Accepted  
**日期**: 2026-04-12  
**来源**: Schema v2 语义层边界争议澄清

---

## 背景与上下文

L3 (`analytical_elements`) 和 L4 (`business_logic`) 之间的计算边界一直存在设计争议：

| 观点 | 立场 |
|------|------|
| **观点A** | L3 只声明依赖，所有计算逻辑都在 L4 |
| **观点B** | L3 可以保留标准公式，L4 仅在 `overridable=true` 时覆盖 |
| **现状** | 示例中 L3 直接包含 `formula`，但语义未明确 |

**争议焦点**：
- L3 的 `formula` 是"声明"还是"实现"？
- L4 覆盖时是"完全替换"还是"增量修改"？
- 这种边界划分对 Schema Loader 和 Expression Engine 的影响是什么？

---

## 决策

### 1. L3 职责：声明 + 可选标准公式

L3 的核心职责是**声明存在和依赖关系**，`standard_formula` 是附加的语义糖。

```yaml
# L3 - analytical_elements
analytical_elements:
  - name: "credit_risk_score"
    element_type: "metric"
    # 声明依赖
    dependencies:
      - ref: "balance"
        source: "financial_facts"
    # 可选：标准计算公式
    standard_formula:
      expression: "min(100, max(0, balance * 0.01))"
      overridable: true  # 默认为 false
```

**规则**：
- `standard_formula` 是可选的
- `overridable` 默认为 `false`
- 当 `overridable=false` 时，L4 不得覆盖

### 2. L4 职责：具体计算逻辑编排

L4 的核心职责是**具体计算逻辑编排**，包括规则触发、条件判断、覆盖逻辑。

```yaml
# L4 - business_logic
business_logic:
  rules:
    - name: "high_balance_risk_adjustment"
      trigger:
        condition: "balance > 1000000"
      actions:
        # 引用 L3 标准公式
        - type: "compute"
          target: "credit_risk_score"
          use_standard: true
        
        # 覆盖 L3 公式（仅当 overridable=true 允许）
        - type: "override"
          target: "credit_risk_score"
          expression: "95"  # 完全替换
```

### 3. 覆盖语义：完全替换

L4 对 L3 的 `standard_formula` 覆盖采用**完全替换**语义：

```yaml
# L3 定义
standard_formula:
  expression: "base * factor"
  overridable: true

# L4 覆盖 - 完全替换原公式
override:
  target: "metric_name"
  expression: "custom_formula"  # 不继承、不合并，完全替换
```

**注意**：L4 可以通过 `use_standard: true` 显式引用 L3 的原始公式。

### 4. 职责边界总结

| 层级 | 核心职责 | 计算相关能力 |
|------|----------|--------------|
| **L3** | 声明元素存在和依赖关系 | 可选声明 `standard_formula`（参考实现） |
| **L4** | 具体计算逻辑编排 | 规则触发、条件判断、公式覆盖 |

---

## 后果

### Schema Loader 变更

- 需要支持解析 L3 的 `standard_formula` 字段
- 需要验证 `overridable` 标志的有效性
- 需要检查 L4 覆盖是否违反 `overridable=false` 约束

### Expression Engine 变更

- 需要能执行 L3 和 L4 的公式（参见 [ADR-003: Expression Engine Security](./003-expression-engine-security.md)）
- 需要支持上下文变量解析，从 L3 `dependencies` 注入

### 待明确事项

1. **覆盖冲突处理**：当多个 L4 规则尝试覆盖同一 L3 元素时，优先级如何确定？
2. **增量修改语法**：是否需要支持"基于原公式修改"的语法糖？
3. **调试与追踪**：如何清晰展示"使用了 L3 公式"vs"使用了 L4 覆盖公式"？

---

## 相关文档

- [ADR-003: Expression Engine Security](./003-expression-engine-security.md) - 公式执行安全沙箱
- [ADR-004: KGML/LinkML Integration](./004-kgml-linkml-integration.md) - Schema 语义层定义

# 案例文档一致性审视报告

> **审查范围**: `docs/09-examples/` 与 `examples/` 下的配置文件
> **审查依据**: canonical grammar (`docs/05-schema-v2/09-canonical-schema-spec.md`) + 实际代码
> **审查日期**: 2026-04-14

---

## 一、总体结论

`docs/09-examples/supply_chain_finance.md` 描述的是**一套虚构的简化 Schema 实现**，与以下全部文件存在系统性不一致：

| 对比项 | 文档描述 | 实际情况 | 严重程度 |
|--------|----------|----------|----------|
| 实体名称 | `Company` | `Supplier` / `CoreEnterprise` / `Invoice` | 🔴 高 |
| Schema 结构 | 简化嵌套格式 | 完整 flat YAML + JSON 格式 | 🔴 高 |
| 关系名称 | `Guarantee` | `supplies_to` / `guarantees` / `issued_by` | 🔴 高 |
| Rule Logic 格式 | `steps[]` DAG | `when` / `then_action` / `else_action` | 🔴 高 |
| 示例数据 ID | `COMP001` | `SUP_001` / `CORE_001` | 🔴 高 |
| Semantic Space ID | `kg://scf/v2.0` | `space_supply_chain_demo` | 🟡 中 |
| MCP 工具名 | 5 个工具混用 | 实际工具定义不同 | 🟡 中 |
| API 路径 | 混用 v1/consumption/visualize | 实际 API 路径结构不同 | 🟡 中 |

---

## 二、逐项差异分析

### 2.1 实体定义 — `Company` vs `Supplier`

**文档** (`docs/09-examples/supply_chain_finance.md` Step 2):
```yaml
fact_objects:
  entities:
    - name: "Company"          # ← 文档
      attributes:
        - name: "uscc"         # ← 统一社会信用代码
```

**实际** (`examples/supply_chain_finance/schema.yaml`):
```yaml
fact_objects:
  entities:
    - id: "Supplier"           # ← 实际
      name: "供应商"
      properties:               # ← 用 properties，非 attributes
        - name: "entity_id"
```

**问题**: 文档使用 `Company` 概念，但实际实现中没有 `Company` 实体。文档中的 `uscc` 字段也不存在于实际 schema 中。实际使用 `Supplier` / `CoreEnterprise` / `Invoice` 三个实体。

---

### 2.2 Rule Logic 格式 — `steps[]` DAG vs `when/then_action`

**文档** (Step 2 — 虚构的简化格式):
```yaml
rule_logics:
  - name: "credit_assessment_logic"
    steps: [                    # ← 文档用 steps[] DAG 格式
      {
        "id": "R001",
        "condition": {"and": [{"expression": "..."}]},
        "action": {"type": "set_flag", "flag": "eligible", "value": true}
      }
    ]
```

**实际** (`examples/supply_chain_finance/schema.yaml`):
```yaml
rule_logics:
  - id: "R001_logic_1"
    definition_id: "R001_eligibility_check"
    when:
      expression: "credit_score >= 60"
    then_action:
      action_type: set_flag
      output: {eligible: true}
    else_action:
      action_type: set_flag
      output: {eligible: false}
```

**问题**: 文档使用的 `steps[]` DAG 格式是 **Phase 2 目标设计**（见 ADR-008），而当前 Phase 1 实现使用的是 `when/then_action/else_action` 格式。两者在结构上有本质差异：

- 文档格式: `{id, condition, action, depends_on, operator, computation, output_field}`
- 实际格式: `{when.expression, then_action.action_type, then_action.output, else_action}`

> **注**: `RuleStep` 模型已在 `ontology_engine/core/schema/models.py` 中实现，但 `RuleExecutor` 的 DAG 执行引擎尚未实现（Phase 2）。

---

### 2.3 示例数据 ID — `COMP001` vs `SUP_001`

**文档** (Step 1 前置条件):
> 实体 `COMP001` (北京智造科技有限公司) 已存在于系统中

**实际** (`examples/supply_chain_finance/demo_space.json`):
```json
{"entity_id": "SUP_001", "_concept": "Supplier", "company_name": "东方钢铁有限公司"}
{"entity_id": "CORE_001", "_concept": "CoreEnterprise", "company_name": "国家电网有限公司"}
```

**问题**: 文档引用了完全不存在的实体 ID。`COMP001` 从未在任何配置文件中定义过。

---

### 2.4 categorizations 结构

**文档**:
```yaml
categorizations:
  dimensions: [                  # ← 文档用 dimensions[]
    {"name": "industry", "type": "hierarchical", "values": [...]},
    {"name": "company_scale", "type": "derived", "rule_logic": "determine_scale"}
  ]
```

**实际** (`examples/supply_chain_finance/schema.yaml`):
```yaml
categorizations:
  - id: "industry_category"
    name: "行业分类"
    type: "hierarchical"         # ← 用 type，非 dimensions[]
    values: [...]
```

**问题**: 文档使用 `dimensions[]` 作为 key，但 canonical grammar 使用扁平列表，每个元素含 `id/name/type`。

---

### 2.5 examples/supply_chain_finance/README.md — v1 残留

**问题**: `examples/supply_chain_finance/README.md` (第 114-130 行) 使用 **v1 格式**：

```yaml
concepts:                         # ← v1 格式，应为 fact_objects:
  - name: "Supplier"
    attributes:                   # ← v1 格式，应为 properties:
      - supplier_id
```

该 README 还引用 `instances.yaml` 作为实例数据文件，但实际文件中实例数据是 `demo_space.json` (JSON 格式)。

---

### 2.6 examples/consumer_credit/README.md — 不存在

**问题**: `examples/consumer_credit/README.md` **文件不存在**。`docs/09-examples/README.md` 第 43-47 行引用了它：
```markdown
- **MCP 工具**: [`07-agent-interface.md`](../07-agent-interface.md)
- **API 架构**: [`10-api-architecture.md`](../10-api-architecture.md)
```

但这些引用文件（`07-agent-interface.md`、`10-api-architecture.md`、`08-visualization-system.md`）不在 `docs/` 下。

---

### 2.7 docs/09-examples/README.md — 引用不存在的文件

| 文档引用 | 实际位置 | 状态 |
|----------|----------|------|
| `SCHEMA_DESIGN.md` (under docs/09-examples/) | `examples/supply_chain_finance/SCHEMA_DESIGN.md` | 位置错误 |
| `07-agent-interface.md` | 不存在 | 🔴 |
| `10-api-architecture.md` | 不存在 | 🔴 |
| `08-visualization-system.md` | 不存在 | 🔴 |

---

## 三、testcases.yaml 覆盖场景审视

### 3.1 供应链金融 testcases.yaml — 不存在

`docs/09-examples/supply_chain_finance.md` 末尾数据清单引用了：
> 测试用例: `examples/supply_chain_finance/testcases.yaml`

该文件**不存在**。供应链金融只有 `demo_space.json` 作为数据文件，没有对应的 testcases.yaml。

### 3.2 个人消费信贷 testcases.yaml — 存在但未链接

`examples/consumer_credit/testcases.yaml` **存在且完整**，包含 6 个 TC:

| TC ID | 场景 | 关键验证点 |
|--------|------|-----------|
| TC-C01 | 优质借款人分期贷 | 五维评分卡、APPROVED 路径 |
| TC-C02 | 优质借款人快贷 | 产品分流（RL104_scoring_quick_loan） |
| TC-C03 | 中等风险快贷 | 收入不稳定 → REJECTED |
| TC-C04 | 中等风险大额信贷 | 模拟模式、R4 拒绝 |
| TC-C05 | 关联风险借款人 | 图遍历 co_borrower_risk_count=1 |
| TC-C06 | 黑名单一票否决 | 短路逻辑、仅执行 1 条规则 |

**问题**: 该文件存在但：
1. `examples/consumer_credit/` 下无 README.md 链接它
2. `docs/09-examples/` 下无对应文档描述它
3. testcases.yaml 中的 `expected_rule_steps` 引用的是 `rule_id` / `logic_id`（如 `RD101_veto_check` / `RL102_eligibility_base`），与实际 schema.yaml 中的 ID（`RD101_veto_check` / `RL102_eligibility_base`）匹配 ✓

---

## 四、consumer_credit schema.yaml 与文档的一致性

`examples/consumer_credit/schema.yaml` 已按 canonical grammar 更新：

| 字段 | 状态 |
|------|------|
| `type` (metric/indicator/scorecard) | ✅ 已使用 canonical |
| `applies_to` (rule) | ✅ 已使用 canonical |
| `inputs` / `outputs` (rule) | ✅ 已使用 canonical |
| `rule_logics` 含 `when/then_action` | ✅ 符合当前 Phase 1 实现 |
| `steps[]` DAG 格式 | ❌ 未实现（Phase 2 目标） |

**与 docs/09-examples 的一致性**: `docs/09-examples/` 中没有关于 consumer_credit 的文档，因此无一致性冲突。

---

## 五、覆盖场景总览

```
docs/09-examples/supply_chain_finance.md
├── Step 1: 创建管理空间        → API 路径部分正确（POST /v1/management/spaces 存在）
├── Step 2: Schema 上传         → 🔴 完全不一致（虚构的简化结构）
├── Step 3: 数据集注册          → 🟡 部分正确（API 路径存在但数据 ID 不匹配）
├── Step 4: 规则执行            → 🔴 虚构响应格式，与实际 rule_logics 结构不符
├── Step 5: What-if 模拟        → 🟡 API 路径 /v1/visualize/simulate 可能不存在
└── Step 6: Agent 调用          → 🟡 MCP 工具名可能不匹配

examples/consumer_credit/
├── schema.yaml                 → ✅ 符合 canonical grammar
├── testcases.yaml              → ✅ 完整（6 个 TC），但无文档链接
└── README.md                   → ❌ 文件不存在

examples/supply_chain_finance/
├── schema.yaml                 → ✅ 符合 canonical grammar
├── demo_space.json             → ✅ 符合 canonical grammar
├── README.md                   → 🔴 含 v1 格式残留（concepts: 而非 fact_objects:）
└── SCHEMA_DESIGN.md            → ✅ 内部一致，格式正确
```

---

## 六、解决的问题

1. **识别了文档与实现的系统性断裂**: `docs/09-examples/supply_chain_finance.md` 从未与实际代码对齐，是一套独立编写的"理想化"演示
2. **定位了 v1 残留**: `examples/supply_chain_finance/README.md` 的 `concepts:` / `attributes:` 是过时格式
3. **确认了 consumer_credit testcases.yaml 的完整性**: 6 个 TC 覆盖了主要场景，与 schema.yaml ID 匹配
4. **明确了 Phase 1/2 边界**: 文档中的 `steps[]` DAG 格式是 Phase 2 目标，当前实现用 `when/then_action`

---

## 七、修复建议（按优先级）

### P0 — 立即修复（阻断理解）

| 修复项 | 操作 |
|--------|------|
| `examples/supply_chain_finance/README.md` | 将 `concepts:` 改为 `fact_objects:`，`attributes:` 改为 `properties:` |
| `docs/09-examples/supply_chain_finance.md` | 废弃当前虚构文档，或标注为 **[未实现 / Phase 2 设计]** |

### P1 — 高优先级（影响案例验证）

| 修复项 | 操作 |
|--------|------|
| 创建 `examples/consumer_credit/README.md` | 链接 `schema.yaml`、`testcases.yaml`，说明 6 个 TC 的覆盖场景 |
| `docs/09-examples/README.md` | 删除对不存在文件的引用（`07-*.md` 等）|
| 供应链 testcases | 如需验收用例，从 `demo_space.json` 提取 3 个代表性场景写成 testcases.yaml |

### P2 — 中优先级（文档质量）

| 修复项 | 操作 |
|--------|------|
| `docs/09-examples/supply_chain_finance.md` 引用路径 | 修正为 `examples/supply_chain_finance/SCHEMA_DESIGN.md`（从 docs/09-examples/ 外部引用） |
| 补充 consumer_credit 端到端文档 | 在 `docs/09-examples/` 下增加 `consumer_credit.md` |

### P3 — 低优先级（Phase 2）

| 修复项 | 操作 |
|--------|------|
| `docs/09-examples/supply_chain_finance.md` 的 `steps[]` 部分 | 等 Phase 2 RuleEngine DAG 实现后，用实际输出替换虚构响应 |

---

## 八、审查结论

`docs/09-examples/supply_chain_finance.md` **不可作为实现参考**。它是：
1. 一套独立编写的虚构 Schema（与 `examples/supply_chain_finance/schema.yaml` 完全不符）
2. 引用了 4 个不存在的文档文件
3. 使用了 Phase 2 目标格式（`steps[]` DAG）描述 Phase 1 实现

**实际可用的文件**:
- `examples/supply_chain_finance/schema.yaml` + `demo_space.json` + `SCHEMA_DESIGN.md` — 三者内部一致，符合 canonical grammar
- `examples/consumer_credit/schema.yaml` + `testcases.yaml` — 两者一致，TC 覆盖主要场景

建议将 `docs/09-examples/supply_chain_finance.md` 标注为 **[已过期 / 待重构]**，或直接删除，以避免继续误导读者。

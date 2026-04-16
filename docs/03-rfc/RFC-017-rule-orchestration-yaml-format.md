# RFC-017: Phase 2 规则编排 YAML 格式设计

> **状态**: draft
> **父 RFC**: RFC-014 · RFC-016
> **创建日期**: 2026-04-16
> **作者**: the-butterfly
> **关联 PR**: （待提交）

---

## 摘要

本 RFC 定义 Phase 2 规则编排系统的 YAML 导入/导出格式，与 `RuleGroupDefinition` + `RuleStep` 数据模型完全对齐。解决当前 `import_from_yaml()` / `export_rule_group_to_yaml()` 格式与模型不匹配、与示例 `schema.yaml` 脱节的问题。

**核心变更**：导入/导出格式从扁平的 `rule_definitions[] + rule_logics[]` 升级为结构化的 `rule_group + rule_steps`，与四元素模型完全对应。

---

## 一、问题分析

### 1.1 当前 YAML 格式的问题

当前 `RuleService.import_from_yaml()` 和 `export_rule_group_to_yaml()` 使用扁平结构：

```yaml
rule_definitions:
  - name: "group_name"
    type: "decision"
    applies_to: {}          # ← 简单字典，非 AppliesToConfig
    ...
rule_logics:
  - rule_definition: "group_name"
    steps:
      - id: "step-1"
        when: {...}          # ← 直接字典，缺少 type 区分
```

与 `RuleGroupDefinition` 模型对比：

```python
@dataclass
class AppliesToConfig:
    fact_objects: list[str]           # ← 模型有 fact_objects
    categories: dict[str, list[str]]    # ← 模型有 categories

@dataclass
class RuleGroupDefinition:
    applies_to: AppliesToConfig         # ← 四元素 ①
    preconditions: list[Precondition]   # ← 四元素 ②
    inputs: list[IOElement]            # ← 四元素 ③
    outputs: list[IOElement]
```

`import_from_yaml` 读取 `applies_to: {}` 时，`AppliesToConfig.fact_objects` 永远为空。

### 1.2 与旧 L4 `schema.yaml` 的关系

示例 `examples/supply_chain_finance/schema.yaml` 使用嵌套在 `semantic_space.business_logic` 下的旧格式，与 Phase 2 完全是两套数据结构：

| | 旧 L4 (`schema.yaml`) | Phase 2 当前 | Phase 2 目标 |
|---|---|---|---|
| 结构 | 嵌套在 semantic_space 内 | 顶级扁平 | 结构化 `rule_group` + `rule_steps` |
| 条件 | `allOf`/`anyOf` 列表 | `type: all_of` + `sub_conditions` | 与当前一致 |
| 动作 | `action_type` + `output` | `operator` + `params` + `output_mapping` | 与当前一致 |
| 导入支持 | 无 | 格式不兼容 | 支持 Phase 2 格式 |

**结论**：Phase 2 YAML 是独立格式，与旧 `schema.yaml` 不互通。旧数据通过 `import_from_l4_schema_yaml()` 单向转换（见第五节）。

---

## 二、Phase 2 YAML 格式设计

### 2.1 目标格式（导入/导出对称）

```yaml
# ============================================================
# Phase 2 规则组 YAML
# 对应 RuleGroupDefinition（四元素 ①②③）+ RuleStep（四元素 ④）
# ============================================================

rule_group:
  name: "RD001_basic_eligibility"
  description: "供应商融资申请的基础资质门槛校验"
  type: "constraint"                          # constraint | inference | alert | decision
  priority: 100
  enabled: true

  # 四元素 ① 作用对象
  applies_to:
    fact_objects:
      - "Supplier"
    categories:                               # 可选：按分类维度过滤
      industry_type:
        - "MANUFACTURING"
        - "TECHNOLOGY"

  # 四元素 ② 前置条件
  preconditions:
    - expression: "entity.status == 'ACTIVE'"
      fail:
        action: "reject"
        reason: "企业经营状态异常"

  # 四元素 ③ I/O 要素声明
  inputs:
    - name: "is_eligible"
      type: "flag"
      metric: "is_eligible"
    - name: "rejection_reason"
      type: "computed_value"
      attribute: "rejection_reason"
  outputs:
    - name: "is_eligible"
      type: "flag"
    - name: "rejection_reason"
      type: "computed_value"

# 四元素 ④ 规则实例（RuleStep 列表）
rule_steps:
  - id: "step-1"
    name: "注册资本与成立年限检查"
    order: 1
    enabled: true
    description: "校验注册资本≥100万且成立≥1年"
    tags: ["eligibility", "credit"]

    # 条件从句 — 三种类型
    when:
      type: "all_of"                          # expression | all_of | any_of
      sub_conditions:
        - "entity.registered_capital_value >= 1000000"
        - "days_since(entity.establishment_date) >= 365"
        - "metrics.total_invoice_amount_90d >= 500000"

    # then 动作
    then:
      operator: "SET_FLAG"
      params:
        flag_name: "is_eligible"
        flag_value: true
      output_mapping: {}

    # else 动作（可选）
    else:
      operator: "SET_FLAG"
      params:
        flag_name: "is_eligible"
        flag_value: false
      output_mapping:
        rejection_reason: "不满足基础准入条件"

  - id: "step-2"
    name: "准入通过后计算信用评分"
    order: 2
    enabled: true
    when:
      type: "expression"
      expression: "computed.is_eligible == true"
    then:
      operator: "COMPUTE"
      params:
        formula: "$metric:credit_score"
      output_mapping:
        credit_score: "computed.credit_score"
```

### 2.2 字段说明

#### `rule_group` 顶层对象

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 规则组业务名称，在同一 `schema_id` 下唯一 |
| `description` | string | 否 | 规则组描述 |
| `type` | string | 否 | `constraint` \| `inference` \| `alert` \| `decision`，默认 `decision` |
| `priority` | integer | 否 | 优先级，默认 100，数字越小优先级越高 |
| `enabled` | boolean | 否 | 是否启用，默认 `true` |
| `applies_to` | object | 否 | 见 AppliesToConfig |
| `preconditions` | list[object] | 否 | 见 Precondition |
| `inputs` | list[object] | 否 | 见 IOElement |
| `outputs` | list[object] | 否 | 见 IOElement |

#### `applies_to` 配置

| 字段 | 类型 | 说明 |
|------|------|------|
| `fact_objects` | list[string] | 规则作用于哪些实体类型，如 `["Supplier", "Invoice"]` |
| `categories` | object | 按分类维度过滤，如 `{"industry_type": ["MANUFACTURING"]}` |

#### `preconditions[]` 条件

| 字段 | 类型 | 说明 |
|------|------|------|
| `expression` | string | 前置条件表达式，为空时表示无条件 |
| `fail` | object | 失败时的动作（可选） |

#### `inputs[]` / `outputs[]` 要素

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 要素名称 |
| `type` | string | `flag` \| `computed_value` \| `metric` \| `attribute` |
| `metric` | string | 引用指标名（当 type=metric 时） |
| `attribute` | string | 引用属性路径（当 type=attribute 时） |
| `description` | string | 描述 |

#### `rule_steps[]` 规则实例列表

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | ✅ | 步骤唯一标识 |
| `name` | string | 否 | 步骤名称 |
| `order` | integer | 否 | 执行顺序，默认按数组顺序 |
| `enabled` | boolean | 否 | 是否启用，默认 `true` |
| `description` | string | 否 | 步骤描述 |
| `tags` | list[string] | 否 | 标签 |
| `when` | object | ✅ | 条件从句（ConditionClause） |
| `then` | object | ✅ | 主动作从句（ActionClause） |
| `else` | object | 否 | 备选动作从句 |

#### `when` 条件从句

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | ✅ | `expression` \| `all_of` \| `any_of` |
| `expression` | string | 当 type=expression 时 | 单一条件表达式 |
| `sub_conditions` | list[string] | 当 type=all_of/any_of 时 | 多个子条件表达式 |

#### `then` / `else` 动作从句

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `operator` | string | ✅ | 算子名称：`SET_FLAG` \| `COMPUTE` \| `REJECT` \| `TRIGGER_ALERT` \| `BINNING` \| `SCORECARD` \| `WEIGHTED_SUM` \| `DECISION_TABLE` \| `LLM_JUDGE` |
| `params` | object | 否 | 算子参数，JSON Schema 约束 |
| `output_mapping` | object | 否 | 输出变量别名映射 |

---

## 三、实施计划

### T1: 重写 `import_from_yaml` 支持 Phase 2 格式

**文件**: `ontology_engine/services/rule_service.py`

**改动逻辑**：

```python
async def import_from_yaml(
    self,
    yaml_content: str,
    schema_id: str | None = None,
) -> RuleGroupDefinition:
    # 1. 检测格式类型
    data = yaml.safe_load(yaml_content)

    if "rule_group" in data:
        # Phase 2 格式（优先）
        rg_raw = data["rule_group"]
        steps_raw = data.get("rule_steps", [])
    elif "rule_definitions" in data:
        # 旧扁平格式（向后兼容）
        rg_raw = data["rule_definitions"][0]
        steps_raw = data.get("rule_logics", [{}])[0].get("steps", [])
    else:
        raise RuleServiceError("Unrecognized YAML format: no rule_group or rule_definitions root")

    # 2. 转换为 RuleGroupDefinition
    rg_data = {
        "id": str(uuid.uuid4()),
        "name": rg_raw["name"],
        "description": rg_raw.get("description", ""),
        "type": rg_raw.get("type", "decision"),
        "priority": rg_raw.get("priority", 100),
        "applies_to": _normalize_applies_to(rg_raw.get("applies_to", {})),
        "preconditions": _normalize_preconditions(rg_raw.get("preconditions", [])),
        "inputs": _normalize_io_elements(rg_raw.get("inputs", [])),
        "outputs": _normalize_io_elements(rg_raw.get("outputs", [])),
        "enabled": rg_raw.get("enabled", True),
        "schema_id": schema_id,
    }

    # 3. 转换为 RuleStep
    for order, step in enumerate(steps_raw):
        step_data = {
            "id": step.get("id"),
            "name": step.get("name", ""),
            "step_order": step.get("order", order),
            "when": _normalize_when(step.get("when", {})),
            "then": _normalize_action(step.get("then", {})),
            "else": _normalize_action(step.get("else")) if step.get("else") else None,
            "enabled": step.get("enabled", True),
        }
        await self._storage.save_rule_step(rg_data["name"], step_data)

    await self._storage.save_rule_group(rg_data, schema_id=schema_id)
    return RuleGroupDefinition.from_dict(rg_data)
```

### T2: 重写 `export_rule_group_to_yaml` 输出 Phase 2 格式

**文件**: `ontology_engine/services/rule_service.py`

**目标输出格式**：与 Phase 2 导入格式完全对称（见第二节 2.1）。

```python
async def export_rule_group_to_yaml(
    self,
    rule_group_name: str,
    schema_id: str | None = None,
) -> str:
    rg_data = await self._storage.get_rule_group(rule_group_name, schema_id=schema_id)
    if rg_data is None:
        raise RuleServiceError(f"Rule group '{rule_group_name}' not found")

    steps_data = await self._storage.list_rule_steps(rg_data["name"])

    yaml_data = {
        "rule_group": {
            "name": rg_data["name"],
            "description": rg_data.get("description", ""),
            "type": rg_data.get("type", "decision"),
            "priority": rg_data.get("priority", 100),
            "enabled": rg_data.get("enabled", True),
            "applies_to": rg_data.get("applies_to", {}),
            "preconditions": rg_data.get("preconditions", []),
            "inputs": rg_data.get("inputs", []),
            "outputs": rg_data.get("outputs", []),
        },
        "rule_steps": [
            {
                "id": s["id"],
                "name": s.get("name", ""),
                "order": s.get("step_order", 1),
                "enabled": s.get("enabled", True),
                "description": s.get("description", ""),
                "tags": s.get("tags", []),
                "when": s.get("when", {}),
                "then": s.get("then", {}),
                "else": s.get("else"),
            }
            for s in steps_data
        ],
    }

    return yaml.dump(yaml_data, allow_unicode=True, sort_keys=False)
```

### T3: 新增 `import_from_l4_schema_yaml` 单向转换（可选）

**文件**: `ontology_engine/services/rule_service.py`

将旧 `semantic_space.business_logic.rule_definitions[]` + `rule_logics[]` 单向转换为 Phase 2 格式。不提供反向转换（旧格式已废弃）。

```python
async def import_from_l4_schema_yaml(
    self,
    yaml_content: str,
    schema_id: str | None = None,
) -> list[RuleGroupDefinition]:
    """从旧 L4 schema.yaml 格式单向导入规则组。

    仅转换 rule_definitions 和 rule_logics。
    不支持 L1 fact_objects / L2 categorizations / L3 analytical_elements。
    """
    data = yaml.safe_load(yaml_content)
    business_logic = data.get("semantic_space", {}).get("business_logic", {})
    rule_defs = business_logic.get("rule_definitions", [])

    imported = []
    for rd in rule_defs:
        # 字段映射：id→name, rule_type→type, action_type→operator
        # allOf/anyOf → type: all_of/any_of + sub_conditions
        rg_data = _convert_l4_rule_definition(rd, schema_id)
        await self._storage.save_rule_group(rg_data, schema_id=schema_id)
        imported.append(RuleGroupDefinition.from_dict(rg_data))
    return imported
```

### T4: 新增 Phase 2 示例 YAML 文件

**新增目录**: `examples/supply_chain_finance/rules/`

| 文件 | 内容 |
|------|------|
| `RD001_basic_eligibility.yaml` | 准入规则（2个 step） |
| `RD002_credit_score.yaml` | 评分计算（标准 + 制造业加成） |
| `RD003_guarantee_risk.yaml` | 担保圈检测 |
| `RD004_credit_limit.yaml` | 授信额度计算 |
| `RD006_final_decision.yaml` | 最终决策 |

### T5: 更新 `examples/README.md`

在示例目录说明中增加 Phase 2 YAML 用法：

```markdown
## Phase 2 规则组 YAML

`rules/` 目录存放 Phase 2 格式的规则组 YAML 文件，可通过前端 UI 导入：

```bash
# 导入示例
curl -X POST http://localhost:8000/v1/rule-groups/import \
  -H "Content-Type: application/json" \
  -d '{"yaml_content": "...", "schema_id": "space.supply_chain_finance"}'
```
```

---

## 四、验证方案

### 往返一致性验证

```python
# T1+T2 验证：导入 → 导出 → 导入，内容一致
yaml_content = open("examples/supply_chain_finance/rules/RD001_basic_eligibility.yaml").read()
imported = await rule_service.import_from_yaml(yaml_content, schema_id="test")
exported = await rule_service.export_rule_group_to_yaml(imported.name, schema_id="test")
reimported = await rule_service.import_from_yaml(exported, schema_id="test")

assert imported.name == reimported.name
assert len(imported_steps) == len(reimported_steps)
# 所有 step 的 when.type / when.sub_conditions / then.operator 均一致
```

### 旧格式兼容验证

```python
# T3 验证：旧 schema.yaml 导入
l4_yaml = open("examples/supply_chain_finance/schema.yaml").read()
rule_groups = await rule_service.import_from_l4_schema_yaml(l4_yaml, schema_id="test")
assert len(rule_groups) >= 6  # 6 个 rule_definitions
for rg in rule_groups:
    assert rg.name.startswith("RD")
    assert rg.applies_to.fact_objects  # 不为空
```

---

## 五、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 现有 YAML 导出格式变更 | 已有导出文件与新格式不兼容 | 提供版本号字段 `format_version: "2.0"`，前端兼容旧格式导入 |
| 旧 schema.yaml 转换丢失信息 | `applicable_categorizations` 等字段无法完全映射 | 仅做单向转换，转换后人工审核 |
| 前端导入 UI 无变化但后端行为变 | 需确认前端调用参数不变 | 前端 API 层无需修改，仅后端解析逻辑变 |

---

## 六、关联文档

| 文档 | 说明 |
|------|------|
| [RFC-014](./RFC-014-rule-orchestration-system.md) | 规则编排系统设计（含四元素模型定义） |
| [RFC-016](./RFC-016-rule-orchestration-gap-analysis.md) | Gap 分析（含 YAML 格式问题识别） |
| `ontology_engine/engine/rule/models.py` | 数据模型（RuleGroupDefinition / RuleStep / ConditionClause / ActionClause） |
| `ontology_engine/services/rule_service.py` | 服务层（含 import/export 实现） |
| `examples/supply_chain_finance/rules/` | Phase 2 YAML 示例（实施后新增） |

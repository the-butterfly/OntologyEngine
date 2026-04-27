# 前后端类型一致性分析报告

> 日期: 2026-04-23
> 状态: 分析完成

---

## 一、前端类型定义

**文件**: `ontology-engine-ui/src/types/simulation.ts`

```typescript
interface ExecutionLayer {
  layer_index: number;
  rule_groups: string[];
  steps: ExecutableStep[];
  output_names: string[];
  input_requirements: InputRequirement[];  // ← 前端期望这个字段
}

interface ExecutableStep {
  step_id: string;
  step_name: string;
  rule_group_name: string;
  rule_group_type: 'constraint' | 'inference' | 'alert' | 'decision';
  condition: Condition;
  action: {
    operator: string;
    params: Record<string, unknown>;
  };
  output_names: string[];
  depends_on: string[];
}

interface InputRequirement {
  name: string;
  type: 'attribute' | 'metric' | 'flag';
  required: boolean;
  default_value?: unknown;
  description?: string;
}
```

---

## 二、后端当前返回结构

**文件**: `ontology_engine/services/simulation_tree_builder.py` (lines 95-100)

```python
layers.append({
    "layer_index": len(layers),
    "rule_groups": [g.name for g in next_groups],
    "steps": steps,           # ← 目前永远为空 []
    "output_names": list(current_outputs),
    # ← 缺少 input_requirements 字段
})
```

---

## 三、不一致项汇总

| # | 不一致项 | 前端期望 | 后端当前 | 严重度 |
|---|---------|----------|----------|--------|
| 1 | `input_requirements` 字段缺失 | ExecutionLayer 包含 `input_requirements: InputRequirement[]` | 无此字段 | **P0** |
| 2 | `steps` 永远为空 | `ExecutableStep[]` | `[]` (TODO 占位) | **P0** |
| 3 | `action` 结构不明确 | `{ operator: string; params: Record<string, unknown> }` | `dict[str, Any]` (无类型约束) | P1 |

---

## 四、详细分析

### 不一致项 1: `input_requirements` 字段缺失 [P0]

**前端使用方式** (SimulationPanel.tsx:130):
```typescript
<InputValuesForm
  inputs={executionTree.layers.flatMap(l => l.input_requirements || [])}
  values={inputValues}
  onChange={updateInputs}
/>
```

**前端依赖**: `flatMap(l => l.input_requirements)` - 如果字段缺失或为空，表单不会显示任何输入项

**后端需要**: 从规则的 `inputs` 定义计算 `input_requirements`

**示例** (RD001_basic_eligibility):
```yaml
inputs:
  - { id: status, name: "经营状态", type: attribute }
  - { id: registered_capital, name: "注册资本", type: attribute }
  - { id: establishment_date, name: "成立日期", type: attribute }
  - { id: total_invoice_amount_90d, name: "近90天交易额", type: metric }
```

**应转换为**:
```json
{
  "input_requirements": [
    { "name": "status", "type": "attribute", "required": true },
    { "name": "registered_capital", "type": "attribute", "required": true },
    { "name": "establishment_date", "type": "attribute", "required": true },
    { "name": "total_invoice_amount_90d", "type": "metric", "required": true }
  ]
}
```

---

### 不一致项 2: `steps` 永远为空 [P0]

**原因**: `_filter_steps()` 返回 `[]` (TODO 占位)

**影响**:
1. ExecutionTreeViewer 无内容可显示
2. InputValuesForm 无输入项
3. 用户无法看到执行树结构

**当实现后需要匹配的结构**:
```typescript
interface ExecutableStep {
  step_id: string;                    // e.g., "RD001.RL001"
  step_name: string;                  // e.g., "标准准入检查"
  rule_group_name: string;            // e.g., "RD001_basic_eligibility"
  rule_group_type: 'constraint' | 'inference' | 'alert' | 'decision';
  condition: Condition;               // { type: 'expression', expression: '...' }
  action: { operator: string; params: Record<string, unknown> };
  output_names: string[];              // e.g., ["is_eligible", "rejection_reason"]
  depends_on: string[];               // e.g., ["RD000.step-1"]
}
```

---

### 不一致项 3: `action` 结构不明确 [P1]

**前端定义**:
```typescript
action: {
  operator: string;                    // e.g., "SET_FLAG", "COMPUTE"
  params: Record<string, unknown>;    // e.g., { flag_name: "is_eligible", flag_value: true }
}
```

**后端当前**: `dict[str, Any]` 无类型约束

**建议**: 定义 Pydantic 模型或 TypeScript 接口统一

---

## 五、修复要求

### 后端需补充

1. **返回 `input_requirements`** - 从 L4 层规则的 inputs 定义计算
2. **实现 `_filter_steps()`** - 返回 `ExecutableStep[]`
3. **结构对齐** - action 字段需包含 `operator` 和 `params`

### 推荐的 ExecutionLayer 返回结构

```python
{
    "layer_index": 0,
    "rule_groups": ["RD001_basic_eligibility"],
    "steps": [
        {
            "step_id": "RD001.RL001",
            "step_name": "标准准入检查",
            "rule_group_name": "RD001_basic_eligibility",
            "rule_group_type": "constraint",
            "condition": {
                "type": "expression",
                "expression": "status == 'ACTIVE' AND ..."
            },
            "action": {
                "operator": "SET_FLAG",
                "params": {"flag_name": "is_eligible", "flag_value": True}
            },
            "output_names": ["is_eligible", "rejection_reason"],
            "depends_on": [],
            "priority": 100
        }
    ],
    "output_names": ["is_eligible"],
    "input_requirements": [
        {"name": "status", "type": "attribute", "required": True},
        {"name": "registered_capital", "type": "attribute", "required": True},
        {"name": "establishment_date", "type": "attribute", "required": True},
        {"name": "total_invoice_amount_90d", "type": "metric", "required": True}
    ]
}
```

---

## 六、Schema/规则一致性检查点

用户决策: **Schema 使用一致的标准化属性，加载时检查一致性**

需要在以下时机进行检查:

| 检查点 | 检查内容 | 失败处理 |
|--------|----------|----------|
| Schema 加载 | `registered_capital.value` 等嵌套属性是否存在 | 警告 + 回退默认值 |
| 规则加载 | 规则引用的 `inputs/outputs` 在 schema 中是否存在 | 报错 + 拒绝加载 |
| 实例加载 | 实例属性与 schema 定义的类型是否匹配 | 警告 + 类型转换 |

---

## 七、行动项

### 后端修复
- [ ] 实现 `_filter_steps()` 返回正确的 `ExecutableStep[]`
- [ ] 补充 `input_requirements` 字段计算
- [ ] 对齐 `action` 结构

### Schema/规则检查
- [ ] 实现 Schema 加载时的属性存在性检查
- [ ] 实现规则加载时的 inputs/outputs 引用验证
- [ ] 实现实例加载时的类型检查
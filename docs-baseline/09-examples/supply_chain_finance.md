# 供应链金融授信评估端到端案例

> **[已过期入口]** ⚠️ 本文档描述的是 Phase 2 目标设计，**不代表当前 Phase 1 实现**
>
> **文档状态**: deprecated（仅作 Phase 2 设计参考）
> **与实现不符点**:
> - 实体名称: `Company`（文档）vs `Supplier/CoreEnterprise/Invoice`（实际）
> - 关系名称: `Guarantee`（文档）vs `supplies_to/guarantees/issued_by`（实际）
> - Rule Logic 格式: `steps[]` DAG（文档，Phase 2）vs `when/then_action`（实际，Phase 1）
> - 示例数据 ID: `COMP001`（文档，从未定义）vs `SUP_001/CORE_001`（实际）
> - MCP 工具: 文档引用 `oe_*` 工具，但 `ontology_engine/mcp/` 尚未实现
>
> **当前实现参考**: 见 `examples/supply_chain_finance/schema.yaml` + `examples/supply_chain_finance/SCHEMA_DESIGN.md`
> **审视报告**: 见 [`REVIEW_REPORT.md`](./REVIEW_REPORT.md)

---

> **以下为 Phase 2 目标设计的原始内容，保留作参考用途**

# 供应链金融授信评估 Demo（Phase 2 目标设计）

基于 **OntologyEngine** 的完整知识图谱分析演示，展示 KGML Schema v3.0 Schema 驱动的多维度分析能力。

## 概述

本 Demo 演示了基于 **KGML Schema v3.0** 的完整分析链路：

```
KGML Schema (schema.yaml) → 实例数据 (instances.yaml) → OntologyEngine → 分析结果
```

### Phase 2 新增能力

> 以下能力在 Phase 2 实现，Phase 1 不包含

- **Schema 驱动**: 所有分析逻辑由 `schema.yaml` 定义，非硬编码
- **多维度分析**: 支持 `credit_assessment`、`risk_early_warning` 等维度
- **10+ 测试案例**: 覆盖优质/高风险/担保圈等多种场景
- **完整指标计算**: 原子指标 → 派生指标 → 复合指标 → 图算法指标
- **规则推理链**: 7条规则按优先级执行，生成最终决策
- **steps[] DAG 执行**: Phase 2 RuleExecutor DAG 拓扑排序（RFC-011）
- **MCP 工具**: Claude Desktop / Cursor 通过 MCP Server 调 用 oe_* 工具（RFC-013）

## 快速开始

### Phase 2 MCP 工具调用

```bash
# Claude Desktop 配置 (Phase 2)
# ~/.claude/settings.json 或 Claude Code 配置
{
  "mcpServers": {
    "ontology-engine": {
      "command": "uvicorn",
      "args": ["ontology_engine.mcp.server:app", "--host", "0.0.0.0", "--port", "8000"]
    }
  }
}
```

### Phase 2 API 调用示例

```bash
# Step 1: 创建管理空间
curl -X POST http://localhost:8000/v1/management/spaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "供应链金融v2",
    "description": "供应链金融风控模型管理空间",
    "domain": "supply_chain_finance",
    "space_type": "management"
  }'

# Step 2: Schema 上传（Phase 2 steps[] DAG 格式）
curl -X PUT http://localhost:8000/v1/management/{spaceId}/schema \
  -H "Content-Type: application/json" \
  -d @examples/supply_chain_finance/schema_v2.json

# Step 3: 数据集注册
curl -X POST http://localhost:8000/v1/management/{spaceId}/datasets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "北京智造科技企业数据",
    "source_type": "file",
    "source_config": {"format": "yaml", "path": "examples/supply_chain_finance/instances.yaml"},
    "target_concept": "Supplier"
  }'

# Step 4: 规则执行
curl -X POST http://localhost:8000/v1/consumption/views/{viewId}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "entity_id": "SUP_001",
    "dimension": "credit_assessment",
    "explain_level": "full"
  }'

# Step 5: MCP 工具调用（Claude Agent）
# oe_execute_rule(entity_id="SUP_001", dimension="credit_assessment", explain_level="full")
```

### Phase 2 MCP 工具清单

| 工具名 | Phase 2 功能 | 实现状态 |
|--------|-------------|---------|
| `oe_create_space` | 创建管理空间 | **未实现** |
| `oe_load_schema` | 加载 Schema | **未实现** |
| `oe_register_dataset` | 注册数据集 | **未实现** |
| `oe_execute_rule` | 执行规则 | **未实现** |
| `oe_query` | 知识检索 | **未实现** |
| `oe_trace_rule` | 规则追溯 | **未实现** |
| `oe_simulate` | What-if 模拟 | **未实现** |

详见: [`docs/09-examples/TOOL_AUDIT.md`](./TOOL_AUDIT.md)

## Phase 2 Schema 设计（目标）

> 以下为 Phase 2 steps[] DAG 格式的示例，与 Phase 1 `when/then_action` 格式不同

```yaml
# Phase 2 steps[] DAG 格式（RFC-011）
rule_logics:
  - id: "R001_logic_1"
    definition_id: "R001_eligibility_check"
    steps:
      - id: "step_1"
        name: "信用分准入"
        priority: 100
        condition:
          expression: "credit_score >= 60"
        action:
          type: "set_flag"
        output_field: "eligible"
        output_value: true

      - id: "step_2"
        name: "授信额度计算"
        priority: 80
        depends_on: ["step_1"]
        condition:
          expression: "eligible == true"
        action:
          type: "compute"
        operator: "SWITCH"
        input: "risk_bucket"
        branches:
          - condition: "LOW_RISK"
            formula: "min(registered_capital * 0.6, 15000000)"
        default: "min(registered_capital * 0.2, 5000000)"
        output_field: "credit_limit"
```

## 端到端验证清单（Phase 2 目标）

| 验证项 | Phase 2 预期结果 | Phase 1 实际 |
|--------|------------------|--------------|
| Space 创建 | `space_id` 非空 | ✅ `POST /v1/management/spaces` |
| Schema 上传 | L1-L4 完整加载 | ✅ `PUT /v1/management/{spaceId}/schema` |
| 数据集注册 | `dataset_id` 非空 | ✅ `POST /v1/management/{spaceId}/datasets` |
| 规则执行 DAG | steps[] 拓扑排序 | ❌ 顺序执行（Phase 1）|
| MCP 工具 | Claude Desktop 集成 | ❌ 未实现 |
| What-if 模拟 | MCP / API | ✅ `POST /v1/consumption/views/{viewId}/simulate` |

---

## 相关文档

- **审视报告**: [`REVIEW_REPORT.md`](./REVIEW_REPORT.md) — 当前实现 vs 文档的完整差异分析
- **工具核验**: [`TOOL_AUDIT.md`](./TOOL_AUDIT.md) — MCP 工具定义 vs 实现状态
- **Phase 2 RFC**: [`docs/03-rfc/RFC-010-phase2-roadmap.md`](../03-rfc/RFC-010-phase2-roadmap.md)
- **Schema 设计**: [`examples/supply_chain_finance/SCHEMA_DESIGN.md`](../../examples/supply_chain_finance/SCHEMA_DESIGN.md) — 当前 Phase 1 实现
- **Schema 规范**: [`docs/05-schema-v2/09-canonical-schema-spec.md`](../05-schema-v2/09-canonical-schema-spec.md)
- **示例数据**: [`examples/supply_chain_finance/demo_space.json`](../../examples/supply_chain_finance/demo_space.json)
- **测试用例**: [`examples/supply_chain_finance/testcases.yaml`](../../examples/supply_chain_finance/testcases.yaml)
